"""Storage source, connection-test, and feature configuration APIs."""

from __future__ import annotations

import tempfile
import uuid
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import object_storage
from app.services.asset_archive import enqueue_archive
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import StorageConfigManager, storage_config_manager
from app.db.video_task_dao import get_task_by_video, get_tasks_by_video
from app.models.audio_model import AudioDownloadResult
from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.response import ResponseWrapper as R


router = APIRouter()
logger = logging.getLogger(__name__)
_USAGE_CACHE_TTL_SECONDS = 3600
_usage_cache: dict[str, tuple[float, dict[str, object]]] = {}


class StorageSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["s3"] = "s3"
    endpoint: str = Field(min_length=1)
    access_key: str = ""
    secret_key: str = ""
    bucket: str = Field(min_length=1)
    path_style: bool = True
    use_ssl: bool = False


class StorageFeatureRequest(BaseModel):
    feature: Literal["image_bed", "assets"]
    enabled: bool
    source: str = ""
    public_base_url: str = ""
    path_prefix: str = ""


class ResourceArchiveRequest(BaseModel):
    platform: str
    video_id: str
    task_id: str | None = None
    video_url: str = ""
    archive_video: bool = False


def _clear_usage_cache() -> None:
    _usage_cache.clear()


def _manager() -> StorageConfigManager:
    return storage_config_manager


@router.get("/storage/config")
def get_storage_config():
    return R.success(data=_manager().get_public_config())


@router.post("/storage/source")
def save_storage_source(data: StorageSourceRequest):
    source = data.model_dump()
    name = source.pop("name")
    saved = _manager().upsert_source(name, source)
    saved["secret_key"] = _manager().get_public_config()["sources"][name]["secret_key"]
    _clear_usage_cache()
    return R.success(data={"name": name, **saved})


@router.delete("/storage/source/{name}")
def delete_storage_source(name: str):
    config = _manager().get_config()
    references = [
        feature
        for feature in ("image_bed", "assets")
        if config.get(feature, {}).get("source") == name
    ]
    if references:
        raise HTTPException(
            status_code=400,
            detail=f"source {name} 正被功能引用: {', '.join(references)}",
        )
    if not _manager().delete_source(name):
        raise HTTPException(status_code=404, detail=f"source {name} 不存在")
    _clear_usage_cache()
    return R.success(msg="存储源已删除")


@router.post("/storage/feature")
def save_storage_feature(data: StorageFeatureRequest):
    values = data.model_dump(exclude={"feature"})
    if data.feature == "assets":
        values.pop("public_base_url", None)
        values.pop("path_prefix", None)
    feature = _manager().update_feature(data.feature, values)
    _clear_usage_cache()
    return R.success(data={data.feature: feature})


def _failed_steps(message: str) -> dict[str, dict[str, object]]:
    return {
        "put": {"ok": False, "message": message},
        "get": {"ok": False},
        "delete": {"ok": False},
    }


@router.post("/storage/test/{name}")
def test_storage_source(name: str):
    config = _manager().get_config()
    source = config.get("sources", {}).get(name)
    if not source:
        raise HTTPException(status_code=404, detail=f"source {name} 不存在")

    feature = config.get("image_bed", {})
    configured_prefix = ""
    if feature.get("source") == name:
        configured_prefix = str(feature.get("path_prefix") or "").strip("/")
    probe_prefix = f"{configured_prefix}/" if configured_prefix else ""
    key = f"{probe_prefix}_probe/{uuid.uuid4()}"
    steps = _failed_steps("")
    probe_path: Path | None = None
    put_succeeded = False
    try:
        with tempfile.NamedTemporaryFile(prefix="bilinote-probe-", suffix=".bin", delete=False) as probe:
            probe.write(b"x")
            probe_path = Path(probe.name)

        object_storage.put_file(name, key, probe_path, "application/octet-stream")
        put_succeeded = True
        steps["put"] = {"ok": True, "key": key}

        object_storage.get_bytes(name, key)
        steps["get"] = {"ok": True, "key": key}

        if feature.get("source") == name and feature.get("public_base_url"):
            public_url = f"{feature['public_base_url'].rstrip('/')}/{key}"
            response = httpx.get(public_url, timeout=10.0)
            steps["public_get"] = {
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
            }
            if response.status_code != 200:
                raise RuntimeError(f"public GET 返回 HTTP {response.status_code}")

        object_storage.delete_object(name, key)
        steps["delete"] = {"ok": True, "key": key}
        return R.success(data=steps)
    except ObjectStorageError as exc:
        failed_step = next(
            (step for step in ("put", "get", "public_get", "delete") if not steps.get(step, {}).get("ok")),
            "get",
        )
        steps[failed_step] = {"ok": False, "message": str(exc)}
        return R.error(msg=str(exc), code=502, data=steps)
    except Exception as exc:
        return R.error(msg=f"存储测试失败 source={name} key={key}: {exc}", code=502, data=steps)
    finally:
        if put_succeeded and not steps["delete"].get("ok"):
            try:
                object_storage.delete_object(name, key)
                steps["delete"] = {"ok": True, "key": key, "cleanup": True}
            except ObjectStorageError as cleanup_exc:
                steps["delete"] = {"ok": False, "message": str(cleanup_exc), "cleanup": True}
        if probe_path:
            probe_path.unlink(missing_ok=True)


def _usage_metric(objects: list[object_storage.ObjectInfo]) -> dict[str, object]:
    latest = max(
        (item.last_modified for item in objects if item.last_modified is not None),
        default=None,
    )
    return {
        "object_count": len(objects),
        "total_size": sum(item.size for item in objects),
        "latest_upload": latest.isoformat() if latest else None,
    }


@router.get("/storage/usage/{feature}")
def get_storage_usage(feature: str, refresh: bool = False):
    if feature not in ("image_bed", "assets"):
        raise HTTPException(status_code=404, detail=f"不支持的存储功能: {feature}")
    if not _manager().is_feature_enabled(feature):
        return R.error(msg="存储功能未启用", code=400)

    now = time.monotonic()
    cached = _usage_cache.get(feature)
    if cached and not refresh and now - cached[0] < _USAGE_CACHE_TTL_SECONDS:
        return R.success(data=cached[1])

    config = _manager().get_effective_feature(feature)
    source = str(config.get("source") or "")
    prefix = ""
    if feature == "image_bed":
        prefix = f"{str(config.get('path_prefix') or '').strip('/')}/"

    try:
        total = object_storage.list_prefix_stats(source, prefix)
        data: dict[str, object] = {
            "feature": feature,
            "source": source,
            "prefix": prefix,
            "object_count": int(total.get("object_count", 0)),
            "total_size": int(total.get("total_size", 0)),
            "latest_upload": (
                total["latest_upload"].isoformat()
                if total.get("latest_upload") is not None
                else None
            ),
        }
        if feature == "assets":
            objects = object_storage.list_objects(source, prefix)
            groups: dict[str, list[object_storage.ObjectInfo]] = {
                "video": [],
                "audio": [],
                "text": [],
            }
            for item in objects:
                filename = Path(item.key).name
                if filename == "video.mp4":
                    groups["video"].append(item)
                elif filename.startswith("audio."):
                    groups["audio"].append(item)
                elif filename == "transcript.json" or filename.startswith("subtitle."):
                    groups["text"].append(item)
            data["details"] = {name: _usage_metric(items) for name, items in groups.items()}
        _usage_cache[feature] = (now, data)
        return R.success(data=data)
    except ObjectStorageError as exc:
        return R.error(msg=str(exc), code=502)


_ASSET_FILENAME_RE = re.compile(
    r"^(?:video\.mp4|audio\.[A-Za-z0-9]+|transcript\.json|subtitle\.[^/]+\.json)$"
)


def _validate_asset_key(key: str) -> str:
    normalized = str(key or "").strip("/")
    parts = normalized.split("/")
    if len(parts) != 3 or any(not part or part in {".", ".."} for part in parts):
        raise HTTPException(status_code=400, detail="非法资产 key")
    if ".." in normalized or not _ASSET_FILENAME_RE.fullmatch(parts[-1]):
        raise HTTPException(status_code=400, detail="非法资产 key")
    configured_buckets = {
        str(source.get("bucket") or "").strip("/")
        for source in _manager().get_config().get("sources", {}).values()
        if source.get("bucket")
    }
    if parts[0] in configured_buckets:
        raise HTTPException(status_code=400, detail="资产 key 不得携带桶名")
    return normalized


def _local_task_assets(task_ids: list[str]) -> dict[str, object]:
    note_output_dir = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
    local = {"video": False, "audio": False, "subtitle": False, "transcript": False}
    for task_id in task_ids:
        transcript_path = note_output_dir / f"{task_id}_transcript.json"
        local["transcript"] = local["transcript"] or transcript_path.exists()
        if transcript_path.exists():
            try:
                transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
                local["subtitle"] = local["subtitle"] or bool(transcript.get("raw"))
            except (OSError, json.JSONDecodeError):
                pass
        audio_meta_path = note_output_dir / f"{task_id}_audio.json"
        if not audio_meta_path.exists():
            continue
        try:
            audio_meta = json.loads(audio_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        audio_path = Path(audio_meta.get("file_path") or "")
        video_path = Path(audio_meta.get("video_path") or "")
        local["audio"] = local["audio"] or audio_path.is_file()
        local["video"] = local["video"] or video_path.is_file()
    return local


def _resource_items(platform: str, video_id: str) -> list[dict[str, object]]:
    task_rows = get_tasks_by_video(video_id, platform)
    task_ids = [row["task_id"] for row in task_rows]
    local = _local_task_assets(task_ids)
    archived: dict[str, list[object_storage.ObjectInfo]] = {
        "video": [],
        "audio": [],
        "subtitle": [],
        "transcript": [],
    }

    asset_config = _manager().get_effective_feature("assets")
    if asset_config.get("enabled"):
        source = str(asset_config.get("source") or "")
        try:
            for item in object_storage.list_objects(source, f"{platform}/{video_id}/"):
                filename = Path(item.key).name
                if filename == "video.mp4":
                    archived["video"].append(item)
                elif filename.startswith("audio."):
                    archived["audio"].append(item)
                elif filename.startswith("subtitle."):
                    archived["subtitle"].append(item)
                elif filename == "transcript.json":
                    archived["transcript"].append(item)
        except ObjectStorageError as exc:
            logger.warning("资源包列举资产失败 platform=%s video_id=%s: %s", platform, video_id, exc)

    items = []
    labels = ("video", "audio", "subtitle", "transcript")
    for kind in labels:
        objects = archived[kind]
        items.append(
            {
                "kind": kind,
                "archived": bool(objects),
                "local": bool(local[kind]),
                "size": sum(item.size for item in objects),
                "key": objects[0].key if objects else None,
                "count": len(objects) if kind == "subtitle" else (1 if objects else 0),
            }
        )

    image_count = 0
    image_size = 0
    image_keys: list[str] = []
    image_config = _manager().get_effective_feature("image_bed")
    if image_config.get("enabled") and task_ids:
        try:
            image_source = str(image_config.get("source") or "")
            image_prefix = f"{str(image_config.get('path_prefix') or '').strip('/')}/"
            for item in object_storage.list_objects(image_source, image_prefix):
                if any(f"/{task_id}/" in f"/{item.key}" for task_id in task_ids):
                    image_count += 1
                    image_size += item.size
                    image_keys.append(item.key)
        except ObjectStorageError as exc:
            logger.warning("资源包列举图床图片失败 platform=%s video_id=%s: %s", platform, video_id, exc)
    items.append(
        {
            "kind": "images",
            "archived": image_count > 0,
            "local": bool(task_ids and any(Path("static/screenshots").glob("*"))),
            "size": image_size,
            "count": image_count,
            "keys": image_keys,
        }
    )
    return items


@router.get("/resource_pack/{platform}/{video_id}")
def get_resource_pack(platform: str, video_id: str):
    return R.success(
        data={
            "platform": platform,
            "video_id": video_id,
            "items": _resource_items(platform, video_id),
        }
    )


@router.get("/resource_pack/presign")
def presign_resource(key: str):
    try:
        normalized = _validate_asset_key(key)
        source = _manager().get_effective_feature("assets").get("source")
        if not _manager().is_feature_enabled("assets"):
            return R.error(msg="资产功能未启用", code=400)
        url = object_storage.get_presigned_url(str(source), normalized, 3600)
        return R.success(data={"key": normalized, "url": url, "expires_in": 3600})
    except HTTPException:
        raise
    except ObjectStorageError as exc:
        return R.error(msg=str(exc), code=404)


@router.delete("/resource_pack/object")
def delete_resource_object(key: str):
    try:
        normalized = _validate_asset_key(key)
        config = _manager().get_effective_feature("assets")
        if not config.get("enabled"):
            return R.error(msg="资产功能未启用", code=400)
        object_storage.delete_object(str(config["source"]), normalized)
        return R.success(data={"key": normalized}, msg="资产副本已删除")
    except HTTPException:
        raise
    except ObjectStorageError as exc:
        return R.error(msg=str(exc), code=404)


@router.post("/resource_pack/archive")
def archive_resource(data: ResourceArchiveRequest):
    if not _manager().is_feature_enabled("assets"):
        return R.error(msg="资产功能未启用", code=400)
    task_id = data.task_id or get_task_by_video(data.video_id, data.platform)
    if not task_id:
        raise HTTPException(status_code=404, detail="未找到该视频的笔记任务")
    result_path = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results")) / f"{task_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="笔记结果不存在")
    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        transcript_raw = raw["transcript"]
        transcript = TranscriptResult(
            language=transcript_raw.get("language"),
            full_text=transcript_raw["full_text"],
            segments=[TranscriptSegment(**segment) for segment in transcript_raw.get("segments", [])],
            raw=transcript_raw.get("raw"),
        )
        note = NoteResult(
            markdown=raw["markdown"],
            transcript=transcript,
            audio_meta=AudioDownloadResult(**raw["audio_meta"]),
        )
        enqueue_archive(
            task_id=task_id,
            platform=data.platform,
            video_url=data.video_url,
            note=note,
            transcript_cache_file=Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
            / f"{task_id}_transcript.json",
            archive_video=data.archive_video,
        )
        return R.success(data={"task_id": task_id, "queued": True})
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"笔记结果格式无效: {exc}") from exc
