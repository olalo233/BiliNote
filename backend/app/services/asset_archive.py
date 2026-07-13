"""Asynchronous archival and restoration for per-video assets."""

from __future__ import annotations

from dataclasses import asdict
import json
import logging
from pathlib import Path
import tempfile
import threading
from typing import Any

from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import object_storage
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import storage_config_manager


logger = logging.getLogger(__name__)


def asset_key(platform: str, video_id: str, filename: str) -> str:
    safe_platform = str(platform).strip("/")
    safe_video_id = str(video_id).strip("/")
    safe_filename = str(filename).lstrip("/")
    if ".." in safe_filename.split("/"):
        raise ValueError("资产 key 不允许包含 ..")
    return f"{safe_platform}/{safe_video_id}/{safe_filename}"


def _asset_config() -> dict[str, Any]:
    return storage_config_manager.get_effective_feature("assets")


def assets_enabled() -> bool:
    return bool(_asset_config().get("enabled"))


def _upload_if_needed(source: str, key: str, filepath: Path, content_type: str) -> bool:
    if not filepath.is_file():
        logger.warning("资产本地文件不存在，跳过归档 key=%s path=%s", key, filepath)
        return False

    size = filepath.stat().st_size
    try:
        existing = object_storage.stat_object(source, key)
        if existing.size == size:
            logger.info("资产已存在且大小一致，跳过上传 key=%s size=%s", key, size)
            return True
    except ObjectStorageError:
        # Missing objects and transient stat failures both fall through to the
        # upload attempt; the upload error is the actionable failure to report.
        pass

    for attempt in range(2):
        try:
            object_storage.put_file(source, key, filepath, content_type)
            logger.info("资产归档成功 key=%s size=%s", key, size)
            return True
        except ObjectStorageError as exc:
            if attempt == 0:
                logger.warning("资产归档失败，重试一次 key=%s: %s", key, exc)
            else:
                logger.error("资产归档失败，已重试一次 key=%s: %s", key, exc)
    return False


def _transcript_payload(note: NoteResult) -> dict[str, Any]:
    return asdict(note.transcript)


def _restore_payload(raw: dict[str, Any]) -> TranscriptResult:
    segments = [TranscriptSegment(**segment) for segment in raw.get("segments", [])]
    return TranscriptResult(
        language=raw.get("language"),
        full_text=raw["full_text"],
        segments=segments,
        raw=raw.get("raw"),
    )


def restore_transcript(platform: str, video_id: str, local_cache_file: Path) -> TranscriptResult | None:
    """Restore transcript.json, then subtitle.*.json, into the task cache."""

    config = _asset_config()
    if not config.get("enabled") or not video_id:
        return None
    source = str(config.get("source") or "")
    prefix = f"{platform}/{video_id}/"

    candidates = [asset_key(platform, video_id, "transcript.json")]
    try:
        candidates.extend(
            item.key
            for item in object_storage.list_objects(source, prefix)
            if item.key.startswith(prefix) and "/subtitle." in item.key and item.key.endswith(".json")
        )
    except ObjectStorageError as exc:
        logger.warning("列举资产字幕失败，仍尝试 transcript.json video_id=%s: %s", video_id, exc)

    with tempfile.TemporaryDirectory(prefix="bilinote-asset-restore-") as temp_dir:
        for key in candidates:
            target = Path(temp_dir) / Path(key).name
            try:
                object_storage.get_file(source, key, target)
                raw = json.loads(target.read_text(encoding="utf-8"))
                transcript = _restore_payload(raw)
                local_cache_file.parent.mkdir(parents=True, exist_ok=True)
                local_cache_file.write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info("从资产桶还原转写结果 key=%s video_id=%s", key, video_id)
                return transcript
            except (ObjectStorageError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("资产还原失败，尝试下一个 key=%s: %s", key, exc)
    return None


def archive_note(
    task_id: str,
    platform: str,
    video_url: str,
    note: NoteResult,
    transcript_cache_file: Path,
    archive_video: bool = False,
) -> None:
    """Archive all available local assets for one completed note."""

    config = _asset_config()
    if not config.get("enabled"):
        return

    source = str(config.get("source") or "")
    video_id = note.audio_meta.video_id
    if not video_id:
        logger.warning("任务缺少 video_id，跳过资产归档 task_id=%s", task_id)
        return

    temp_transcript: Path | None = None
    try:
        if not transcript_cache_file.is_file():
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as file:
                json.dump(_transcript_payload(note), file, ensure_ascii=False, indent=2)
                temp_transcript = Path(file.name)
            transcript_path = temp_transcript
        else:
            transcript_path = transcript_cache_file
        _upload_if_needed(
            source,
            asset_key(platform, video_id, "transcript.json"),
            transcript_path,
            "application/json",
        )

        if note.transcript.language and note.transcript.raw:
            subtitle_filename = f"subtitle.{note.transcript.language}.json"
            _upload_if_needed(
                source,
                asset_key(platform, video_id, subtitle_filename),
                transcript_path,
                "application/json",
            )

        audio_path = Path(note.audio_meta.file_path) if note.audio_meta.file_path else None
        if audio_path and audio_path.is_file():
            ext = audio_path.suffix.lower().lstrip(".") or "m4a"
            content_type = "audio/mpeg" if ext == "mp3" else "audio/mp4"
            _upload_if_needed(
                source,
                asset_key(platform, video_id, f"audio.{ext}"),
                audio_path,
                content_type,
            )

        if archive_video:
            _archive_video(source, platform, video_id, video_url, note)
    except Exception as exc:
        logger.error("资产归档任务异常 task_id=%s video_id=%s: %s", task_id, video_id, exc, exc_info=True)
    finally:
        if temp_transcript:
            temp_transcript.unlink(missing_ok=True)


def _archive_video(source: str, platform: str, video_id: str, video_url: str, note: NoteResult) -> None:
    video_path = Path(note.audio_meta.video_path) if note.audio_meta.video_path else None
    if not video_path or not video_path.is_file():
        from app.services.constant import SUPPORT_PLATFORM_MAP

        downloader = SUPPORT_PLATFORM_MAP.get(platform)
        if not downloader or not hasattr(downloader, "download_video"):
            logger.warning("平台不支持完整视频归档 platform=%s video_id=%s", platform, video_id)
            return
        try:
            video_path = Path(downloader.download_video(video_url))
        except Exception as exc:
            logger.warning("原始视频下载失败，跳过视频归档 platform=%s video_id=%s: %s", platform, video_id, exc)
            return

    _upload_if_needed(
        source,
        asset_key(platform, video_id, "video.mp4"),
        video_path,
        "video/mp4",
    )


def enqueue_archive(
    task_id: str,
    platform: str,
    video_url: str,
    note: NoteResult,
    transcript_cache_file: Path,
    archive_video: bool = False,
) -> threading.Thread | None:
    if not assets_enabled():
        return None
    thread = threading.Thread(
        target=archive_note,
        kwargs={
            "task_id": task_id,
            "platform": platform,
            "video_url": video_url,
            "note": note,
            "transcript_cache_file": transcript_cache_file,
            "archive_video": archive_video,
        },
        name=f"asset-archive-{task_id}",
        daemon=True,
    )
    thread.start()
    logger.info("已投递异步资产归档 task_id=%s archive_video=%s", task_id, archive_video)
    return thread
