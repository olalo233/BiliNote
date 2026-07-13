"""Small MinIO/S3 adapter used by the image-bed and asset features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

from minio import Minio

from app.services.storage_config_manager import StorageConfigManager, storage_config_manager


logger = logging.getLogger(__name__)


class ObjectStorageError(RuntimeError):
    def __init__(self, source: str, key: str, message: str):
        self.source = source
        self.key = key
        super().__init__(f"object storage source={source} key={key}: {message}")


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size: int
    last_modified: datetime | None = None
    etag: str | None = None
    content_type: str | None = None


def _source(source_name: str, manager: StorageConfigManager | None = None) -> dict[str, Any]:
    source = (manager or storage_config_manager).get_source(source_name)
    if not source:
        raise ObjectStorageError(source_name, "", "source 不存在")
    if source.get("type", "s3") not in {"minio", "s3"}:
        raise ObjectStorageError(source_name, "", f"不支持的 source type={source.get('type')}")
    return source


def get_client(source_name: str, manager: StorageConfigManager | None = None) -> Minio:
    source = _source(source_name, manager)
    endpoint = str(source.get("endpoint", "")).strip()
    if not endpoint:
        raise ObjectStorageError(source_name, "", "endpoint 不能为空")
    try:
        return Minio(
            endpoint,
            access_key=source.get("access_key", ""),
            secret_key=source.get("secret_key", ""),
            secure=bool(source.get("use_ssl", False)),
        )
    except Exception as exc:
        logger.exception("构造对象存储客户端失败 source=%s", source_name)
        raise ObjectStorageError(source_name, "", str(exc)) from exc


def _bucket(source_name: str, manager: StorageConfigManager | None = None) -> str:
    bucket = str(_source(source_name, manager).get("bucket", "")).strip()
    if not bucket:
        raise ObjectStorageError(source_name, "", "bucket 不能为空")
    return bucket


def put_file(source: str, key: str, filepath: str | Path, content_type: str | None = None) -> ObjectInfo:
    path = Path(filepath)
    try:
        client = get_client(source)
        result = client.fput_object(
            _bucket(source),
            key,
            str(path),
            content_type=content_type,
        )
        return ObjectInfo(key=key, size=path.stat().st_size, etag=getattr(result, "etag", None))
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("对象上传失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc


def get_presigned_url(source: str, key: str, expires: int | timedelta = 3600) -> str:
    try:
        client = get_client(source)
        duration = expires if isinstance(expires, timedelta) else timedelta(seconds=expires)
        return client.presigned_get_object(_bucket(source), key, expires=duration)
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("生成预签名 URL 失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc


def delete_object(source: str, key: str) -> None:
    try:
        get_client(source).remove_object(_bucket(source), key)
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("对象删除失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc


def stat_object(source: str, key: str) -> ObjectInfo:
    try:
        stat = get_client(source).stat_object(_bucket(source), key)
        return ObjectInfo(
            key=key,
            size=int(getattr(stat, "size", 0)),
            last_modified=getattr(stat, "last_modified", None),
            etag=getattr(stat, "etag", None),
            content_type=getattr(stat, "content_type", None),
        )
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("对象查询失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc


def get_file(source: str, key: str, filepath: str | Path) -> None:
    try:
        get_client(source).fget_object(_bucket(source), key, str(filepath))
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("对象下载失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc


def get_bytes(source: str, key: str) -> bytes:
    response = None
    try:
        response = get_client(source).get_object(_bucket(source), key)
        return response.read()
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("对象读取失败 source=%s key=%s", source, key)
        raise ObjectStorageError(source, key, str(exc)) from exc
    finally:
        if response is not None:
            try:
                response.close()
                response.release_conn()
            except Exception:
                logger.debug("关闭对象响应失败 source=%s key=%s", source, key, exc_info=True)


def list_prefix_stats(source: str, prefix: str = "") -> dict[str, Any]:
    try:
        objects = list_objects(source, prefix)
        count = 0
        total_size = 0
        latest_upload: datetime | None = None
        for item in objects:
            count += 1
            total_size += item.size
            modified = item.last_modified
            if modified and (latest_upload is None or modified > latest_upload):
                latest_upload = modified
        return {"object_count": count, "total_size": total_size, "latest_upload": latest_upload}
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("列举对象失败 source=%s key=%s", source, prefix)
        raise ObjectStorageError(source, prefix, str(exc)) from exc


def list_objects(source: str, prefix: str = "") -> list[ObjectInfo]:
    """List object metadata under a prefix for restore and resource-pack views."""

    try:
        objects = get_client(source).list_objects(_bucket(source), prefix=prefix, recursive=True)
        result = []
        for item in objects:
            result.append(
                ObjectInfo(
                    key=str(getattr(item, "object_name", "")),
                    size=int(getattr(item, "size", 0) or 0),
                    last_modified=getattr(item, "last_modified", None),
                    etag=getattr(item, "etag", None),
                )
            )
        return result
    except ObjectStorageError:
        raise
    except Exception as exc:
        logger.exception("列举对象失败 source=%s key=%s", source, prefix)
        raise ObjectStorageError(source, prefix, str(exc)) from exc
