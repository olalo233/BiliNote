import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers import storage as storage_router
from app.services import object_storage
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import SECRET_MASK, StorageConfigManager


def response_body(response):
    return json.loads(response.body)


def source_payload(secret_key="secret-1234"):
    return {
        "type": "s3",
        "endpoint": "minio.example:9000",
        "access_key": "access",
        "secret_key": secret_key,
        "bucket": "bucket",
        "path_style": True,
        "use_ssl": False,
    }


def test_storage_config_manager_masks_secret_and_reads_live_file(tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))

    assert manager.get_public_config() == {
        "sources": {},
        "image_bed": {
            "enabled": False,
            "source": "",
            "public_base_url": "",
            "path_prefix": "",
        },
        "assets": {"enabled": False, "source": ""},
    }

    manager.upsert_source("minio-img", source_payload())
    manager.update_feature(
        "image_bed",
        {
            "enabled": True,
            "source": "minio-img",
            "public_base_url": "http://minio.example/img",
            "path_prefix": "bilinote",
        },
    )
    public = manager.get_public_config()
    assert public["sources"]["minio-img"]["secret_key"] == f"{SECRET_MASK}1234"
    assert public["image_bed"]["enabled"] is True
    assert "secret-1234" not in json.dumps(public)

    # A masked update retains the raw secret in the file while public reads stay masked.
    manager.upsert_source("minio-img", {**source_payload(""), "secret_key": f"{SECRET_MASK}1234"})
    assert manager.get_source("minio-img")["secret_key"] == "secret-1234"


def test_storage_config_manager_treats_dangling_feature_as_disabled(tmp_path, caplog):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.update_feature("assets", {"enabled": True, "source": "missing"})

    with caplog.at_level("WARNING"):
        assert manager.is_feature_enabled("assets") is False
    assert "不存在的 source=missing" in caplog.text


def test_object_storage_wraps_sdk_errors_with_source_and_key(monkeypatch, tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.upsert_source("broken", source_payload())
    monkeypatch.setattr(object_storage, "storage_config_manager", manager)

    class BrokenClient:
        def fput_object(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(object_storage, "Minio", lambda *args, **kwargs: BrokenClient())
    local_file = Path(tmp_path / "one.txt")
    local_file.write_text("x")

    with pytest.raises(ObjectStorageError, match=r"source=broken key=folder/one.txt"):
        object_storage.put_file("broken", "folder/one.txt", local_file, "text/plain")


def test_stat_missing_object_is_debug_without_traceback(monkeypatch, caplog):
    class MissingClient:
        def stat_object(self, *_args):
            error = RuntimeError("object missing")
            error.code = "NoSuchKey"
            raise error

    monkeypatch.setattr(object_storage, "get_client", lambda *_args: MissingClient())
    monkeypatch.setattr(object_storage, "_bucket", lambda *_args: "bucket")

    with caplog.at_level("DEBUG"):
        with pytest.raises(ObjectStorageError):
            object_storage.stat_object("assets", "youtube/abc/missing.json")

    assert "对象不存在，按预期跳过查询" in caplog.text
    assert "Traceback" not in caplog.text


def test_storage_source_routes_mask_and_retain_secret(monkeypatch, tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    first = storage_router.save_storage_source(
        storage_router.StorageSourceRequest(name="source", **source_payload())
    )
    assert response_body(first)["data"]["secret_key"] == f"{SECRET_MASK}1234"

    second = storage_router.save_storage_source(
        storage_router.StorageSourceRequest(
            name="source",
            **source_payload(f"{SECRET_MASK}1234"),
        )
    )
    assert response_body(second)["data"]["secret_key"] == f"{SECRET_MASK}1234"
    assert manager.get_source("source")["secret_key"] == "secret-1234"


def test_storage_source_routes_accept_minio_type_and_feature_scope(monkeypatch, tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    response = storage_router.save_storage_source(
        storage_router.StorageSourceRequest(
            name="image-source",
            feature="image_bed",
            **{**source_payload(), "type": "minio"},
        )
    )

    assert response_body(response)["data"]["name"] == "image-source"
    assert manager.get_source("image-source")["type"] == "minio"
    assert manager.get_source("image-source")["feature"] == "image_bed"


def test_delete_storage_source_removes_unreferenced_source_and_protects_references(
    monkeypatch, tmp_path
):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.upsert_source("source", source_payload())
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    deleted = storage_router.delete_storage_source("source")
    assert response_body(deleted)["code"] == 0
    assert manager.get_source("source") is None

    manager.upsert_source("source", source_payload())
    manager.update_feature("image_bed", {"enabled": True, "source": "source"})
    with pytest.raises(HTTPException) as exc_info:
        storage_router.delete_storage_source("source")
    assert exc_info.value.status_code == 400
    assert "正被功能引用" in str(exc_info.value.detail)


def test_storage_test_uses_explicit_prefix_for_unbound_source(monkeypatch, tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.upsert_source("image-source", source_payload())
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    operations = []
    monkeypatch.setattr(
        storage_router.object_storage,
        "put_file",
        lambda source, key, filepath, content_type: operations.append(
            ("put", source, key, content_type)
        ),
    )
    monkeypatch.setattr(
        storage_router.object_storage,
        "get_bytes",
        lambda source, key: operations.append(("get", source, key)),
    )
    monkeypatch.setattr(
        storage_router.object_storage,
        "delete_object",
        lambda source, key: operations.append(("delete", source, key)),
    )

    response = storage_router.test_storage_source("image-source", prefix="bilinote")

    assert response_body(response)["code"] == 0
    assert operations[0][2].startswith("bilinote/_probe/")
    assert [operation[0] for operation in operations] == ["put", "get", "delete"]
