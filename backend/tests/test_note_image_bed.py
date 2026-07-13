from datetime import datetime, timezone
from pathlib import Path

from app.services import note as note_module
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import StorageConfigManager
from app.services.note import NoteGenerator


def image_bed_manager(tmp_path, enabled=True):
    manager = StorageConfigManager(str(tmp_path / "storage.json"))
    manager.upsert_source(
        "img",
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
    manager.update_feature(
        "image_bed",
        {
            "enabled": enabled,
            "source": "img",
            "public_base_url": "http://images.example/img",
            "path_prefix": "bilinote",
        },
    )
    return manager


def test_image_bed_key_uses_prefix_month_task_and_basename(tmp_path, monkeypatch):
    monkeypatch.setattr(note_module, "storage_config_manager", image_bed_manager(tmp_path))
    generator = NoteGenerator.__new__(NoteGenerator)

    key = generator._image_bed_key(
        "task/with/slashes",
        "/tmp/screenshot_001.webp",
        now=datetime(2026, 7, 13, tzinfo=timezone.utc),
    )

    assert key == "bilinote/2026-07/task/with/slashes/screenshot_001.webp"


def test_screenshot_is_uploaded_and_markdown_uses_public_url(tmp_path, monkeypatch):
    manager = image_bed_manager(tmp_path)
    monkeypatch.setattr(note_module, "storage_config_manager", manager)
    generator = NoteGenerator.__new__(NoteGenerator)
    screenshot = tmp_path / "screenshot_000.jpg"
    screenshot.write_bytes(b"jpeg")
    uploads = []

    def fake_generate(*_args, **_kwargs):
        return str(screenshot)

    def fake_put(source, key, filepath, content_type):
        uploads.append((source, key, Path(filepath), content_type))

    monkeypatch.setattr(note_module, "generate_screenshot", fake_generate)
    monkeypatch.setattr(note_module.object_storage, "put_file", fake_put)

    markdown = generator._insert_screenshots(
        "说明 *Screenshot-00:01",
        Path("video.mp4"),
        task_id="task-1",
    )

    assert markdown == "说明 ![](http://images.example/img/bilinote/2026-07/task-1/screenshot_000.jpg)"
    assert uploads == [
        (
            "img",
            "bilinote/2026-07/task-1/screenshot_000.jpg",
            screenshot,
            "image/jpeg",
        )
    ]


def test_screenshot_upload_failure_falls_back_to_local_url(tmp_path, monkeypatch, caplog):
    manager = image_bed_manager(tmp_path)
    monkeypatch.setattr(note_module, "storage_config_manager", manager)
    generator = NoteGenerator.__new__(NoteGenerator)
    screenshot = tmp_path / "screenshot_000.png"
    screenshot.write_bytes(b"png")

    monkeypatch.setattr(note_module, "generate_screenshot", lambda *_args, **_kwargs: str(screenshot))
    monkeypatch.setattr(
        note_module.object_storage,
        "put_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ObjectStorageError("img", "bilinote/2026-07/task-1/screenshot_000.png", "denied")
        ),
    )

    with caplog.at_level("WARNING"):
        markdown = generator._insert_screenshots(
            "说明 *Screenshot-00:01",
            Path("video.mp4"),
            task_id="task-1",
        )

    assert markdown == "说明 ![](/static/screenshots/screenshot_000.png)"
    assert "回退本地 URL" in caplog.text


def test_disabled_image_bed_keeps_local_markdown_url(tmp_path, monkeypatch):
    monkeypatch.setattr(note_module, "storage_config_manager", image_bed_manager(tmp_path, enabled=False))
    generator = NoteGenerator.__new__(NoteGenerator)
    screenshot = tmp_path / "screenshot_000.jpg"
    screenshot.write_bytes(b"jpeg")
    put_called = False

    monkeypatch.setattr(note_module, "generate_screenshot", lambda *_args, **_kwargs: str(screenshot))

    def fail_if_called(*_args, **_kwargs):
        nonlocal put_called
        put_called = True

    monkeypatch.setattr(note_module.object_storage, "put_file", fail_if_called)
    markdown = generator._insert_screenshots("*Screenshot-00:01", Path("video.mp4"), task_id="task-1")

    assert markdown == "![](/static/screenshots/screenshot_000.jpg)"
    assert put_called is False
