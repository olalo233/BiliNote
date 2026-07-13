"""Storage source, connection-test, and feature configuration APIs."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import object_storage
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import StorageConfigManager, storage_config_manager
from app.utils.response import ResponseWrapper as R


router = APIRouter()


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
    return R.success(msg="存储源已删除")


@router.post("/storage/feature")
def save_storage_feature(data: StorageFeatureRequest):
    values = data.model_dump(exclude={"feature"})
    if data.feature == "assets":
        values.pop("public_base_url", None)
        values.pop("path_prefix", None)
    feature = _manager().update_feature(data.feature, values)
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
