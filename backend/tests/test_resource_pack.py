import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers import storage as storage_router
from app.services.object_storage import ObjectInfo
from app.services.storage_config_manager import StorageConfigManager


def response_body(response):
    return json.loads(response.body)


def configured_manager(tmp_path):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.upsert_source(
        "assets",
        {
            "type": "s3",
            "endpoint": "minio.example:9000",
            "access_key": "access",
            "secret_key": "secret",
            "bucket": "bilinote-assets",
            "path_style": True,
            "use_ssl": False,
        },
    )
    manager.upsert_source(
        "images",
        {
            "type": "s3",
            "endpoint": "minio.example:9000",
            "access_key": "access",
            "secret_key": "secret",
            "bucket": "img",
            "path_style": True,
            "use_ssl": False,
        },
    )
    manager.update_feature("assets", {"enabled": True, "source": "assets"})
    manager.update_feature(
        "image_bed",
        {
            "enabled": True,
            "source": "images",
            "public_base_url": "http://minio.example/img",
            "path_prefix": "bilinote",
        },
    )
    return manager


def test_resource_pack_aggregates_archived_assets_and_images(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    monkeypatch.setattr(
        storage_router,
        "get_tasks_by_video",
        lambda video_id, platform: [{"task_id": "task-1", "video_id": video_id, "platform": platform}],
    )
    monkeypatch.setenv("NOTE_OUTPUT_DIR", str(tmp_path))
    (tmp_path / "task-1_transcript.json").write_text(
        json.dumps({"full_text": "local", "segments": [], "raw": {"source": "subtitle"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        storage_router.object_storage,
        "list_objects",
        lambda source, prefix: (
            [
                ObjectInfo("youtube/abc/video.mp4", 100),
                ObjectInfo("youtube/abc/audio.m4a", 20),
                ObjectInfo("youtube/abc/subtitle.en.json", 30),
                ObjectInfo("youtube/abc/transcript.json", 40),
            ]
            if source == "assets"
            else [ObjectInfo("bilinote/2026-07/task-1/frame.jpg", 5)]
        ),
    )

    response = storage_router.get_resource_pack("youtube", "abc")
    body = response_body(response)
    assert body["code"] == 0
    items = {item["kind"]: item for item in body["data"]["items"]}
    assert items["video"] == {
        "kind": "video",
        "archived": True,
        "local": False,
        "size": 100,
        "key": "youtube/abc/video.mp4",
        "count": 1,
    }
    assert items["audio"]["size"] == 20
    assert items["subtitle"]["count"] == 1
    assert items["transcript"]["archived"] is True
    assert items["images"]["count"] == 1
    assert items["images"]["keys"] == ["bilinote/2026-07/task-1/frame.jpg"]


def test_presign_rejects_bucket_prefixed_and_traversal_keys(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    with pytest.raises(HTTPException) as bucket_error:
        storage_router._validate_asset_key("img/abc/video.mp4")
    assert bucket_error.value.status_code == 400

    with pytest.raises(HTTPException) as traversal_error:
        storage_router._validate_asset_key("youtube/../video.mp4")
    assert traversal_error.value.status_code == 400


def test_delete_resource_uses_only_assets_source(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    deleted = []
    monkeypatch.setattr(
        storage_router.object_storage,
        "delete_object",
        lambda source, key: deleted.append((source, key)),
    )

    response = storage_router.delete_resource_object(key="youtube/abc/audio.m4a")

    assert response_body(response)["code"] == 0
    assert deleted == [("assets", "youtube/abc/audio.m4a")]


def test_resource_pack_exposes_archive_status_and_subtitle_languages(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    monkeypatch.setattr(storage_router, "get_tasks_by_video", lambda *_args: [])
    monkeypatch.setattr(
        storage_router,
        "get_archive_status",
        lambda _platform, _video_id: {
            "video": {"state": "running", "updated_at": "2026-07-14T00:00:00+00:00"},
            "subtitle": {
                "state": "failed",
                "error": "credential rejected",
                "updated_at": "2026-07-14T00:00:01+00:00",
            },
        },
    )
    monkeypatch.setattr(
        storage_router.object_storage,
        "list_objects",
        lambda *_args: [
            ObjectInfo("youtube/abc/subtitle.en-US.json", 10),
            ObjectInfo("youtube/abc/subtitle.zh-Hans.json", 12),
        ],
    )

    body = response_body(storage_router.get_resource_pack("youtube", "abc"))
    items = {item["kind"]: item for item in body["data"]["items"]}
    assert items["video"]["archive_status"]["state"] == "running"
    assert items["subtitle"]["languages"] == ["en-US", "zh-Hans"]
    assert items["subtitle"]["archive_status"]["error"] == "credential rejected"


def test_subtitle_vtt_formats_unicode_multiline_and_escaped_text(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    monkeypatch.setattr(
        storage_router.object_storage,
        "get_bytes",
        lambda _source, _key: json.dumps(
            {
                "segments": [
                    {"start": 0, "end": 1.234, "text": "你好\n第二行 <tag> &"},
                    {"start": 3661.5, "end": 3662, "text": "later"},
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    response = storage_router.get_subtitle_vtt("youtube", "abc", "zh-Hans")
    assert response.media_type == "text/vtt"
    assert response.body.decode("utf-8") == (
        "WEBVTT\n\n"
        "1\n00:00:00.000 --> 00:00:01.234\n你好\n第二行 &lt;tag&gt; &amp;\n\n"
        "2\n01:01:01.500 --> 01:01:02.000\nlater\n"
    )


def test_subtitle_vtt_rejects_missing_language_and_path_traversal(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)

    with pytest.raises(HTTPException) as traversal:
        storage_router.get_subtitle_vtt("youtube", "abc", "../secret")
    assert traversal.value.status_code == 400

    monkeypatch.setattr(
        storage_router.object_storage,
        "get_bytes",
        lambda *_args: (_ for _ in ()).throw(
            storage_router.ObjectStorageError("assets", "youtube/abc/subtitle.fr.json", "NoSuchKey")
        ),
    )
    with pytest.raises(HTTPException) as missing:
        storage_router.get_subtitle_vtt("youtube", "abc", "fr")
    assert missing.value.status_code == 404
