import json
from datetime import datetime, timezone

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
    manager.update_feature("image_bed", {"enabled": True, "source": "images", "path_prefix": "bilinote"})
    return manager


def test_usage_is_cached_and_refresh_recalculates_asset_details(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    storage_router._clear_usage_cache()
    modified = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    objects = [
        ObjectInfo("youtube/id/video.mp4", 100, last_modified=modified),
        ObjectInfo("youtube/id/audio.m4a", 20, last_modified=modified),
        ObjectInfo("youtube/id/subtitle.en.json", 30, last_modified=modified),
        ObjectInfo("youtube/id/transcript.json", 40, last_modified=modified),
    ]
    stats_calls = []
    list_calls = []
    monkeypatch.setattr(
        storage_router.object_storage,
        "list_prefix_stats",
        lambda source, prefix: stats_calls.append((source, prefix))
        or {"object_count": 4, "total_size": 190, "latest_upload": modified},
    )
    monkeypatch.setattr(
        storage_router.object_storage,
        "list_objects",
        lambda source, prefix: list_calls.append((source, prefix)) or objects,
    )

    first = response_body(storage_router.get_storage_usage("assets"))
    second = response_body(storage_router.get_storage_usage("assets"))
    refreshed = response_body(storage_router.get_storage_usage("assets", refresh=True))

    assert first == second
    assert len(stats_calls) == 2
    assert len(list_calls) == 2
    assert first["data"]["object_count"] == 4
    assert first["data"]["total_size"] == 190
    assert first["data"]["latest_upload"] == modified.isoformat()
    assert refreshed["data"]["details"] == {
        "video": {"object_count": 1, "total_size": 100, "latest_upload": modified.isoformat()},
        "audio": {"object_count": 1, "total_size": 20, "latest_upload": modified.isoformat()},
        "text": {"object_count": 2, "total_size": 70, "latest_upload": modified.isoformat()},
    }


def test_image_usage_uses_configured_prefix(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(storage_router, "storage_config_manager", manager)
    storage_router._clear_usage_cache()
    calls = []
    monkeypatch.setattr(
        storage_router.object_storage,
        "list_prefix_stats",
        lambda source, prefix: calls.append((source, prefix))
        or {"object_count": 2, "total_size": 12, "latest_upload": None},
    )

    result = response_body(storage_router.get_storage_usage("image_bed", refresh=True))

    assert result["data"]["prefix"] == "bilinote/"
    assert calls == [("images", "bilinote/")]
