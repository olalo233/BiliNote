import json
import threading
from pathlib import Path

from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import asset_archive
from app.services import note as note_module
from app.routers import note as note_router
from app.services.object_storage import ObjectInfo, ObjectStorageError
from app.services.storage_config_manager import StorageConfigManager


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
    manager.update_feature("assets", {"enabled": True, "source": "assets"})
    return manager


def make_note(tmp_path, raw=True):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"audio")
    transcript = TranscriptResult(
        language="en-US",
        full_text="hello world",
        segments=[TranscriptSegment(start=0, end=1, text="hello world")],
        raw={"source": "youtube"} if raw else None,
    )
    from app.models.audio_model import AudioDownloadResult

    return NoteResult(
        markdown="# note",
        transcript=transcript,
        audio_meta=AudioDownloadResult(
            file_path=str(audio),
            title="video",
            duration=1,
            cover_url=None,
            platform="youtube",
            video_id="abc123",
            raw_info={},
        ),
    )


def test_asset_key_uses_platform_video_and_rejects_traversal():
    assert asset_archive.asset_key("youtube", "abc123", "audio.m4a") == "youtube/abc123/audio.m4a"

    try:
        asset_archive.asset_key("youtube", "abc123", "../audio.m4a")
    except ValueError as exc:
        assert ".." in str(exc)
    else:
        raise AssertionError("expected traversal key to be rejected")


def test_archive_skips_same_size_objects_and_archives_subtitle(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(asset_archive, "storage_config_manager", manager)
    transcript_path = tmp_path / "task_transcript.json"
    transcript_path.write_text(json.dumps({"full_text": "hello", "segments": []}), encoding="utf-8")
    note = make_note(tmp_path)
    skipped = {
        "youtube/abc123/transcript.json": 42,
        "youtube/abc123/audio.m4a": 5,
    }
    uploaded = []

    def fake_stat(_source, key):
        if key in skipped:
            return ObjectInfo(key=key, size=skipped[key])
        raise ObjectStorageError("assets", key, "missing")

    monkeypatch.setattr(asset_archive.object_storage, "stat_object", fake_stat)
    monkeypatch.setattr(
        asset_archive.object_storage,
        "put_file",
        lambda source, key, path, content_type: uploaded.append((source, key, Path(path).name, content_type)),
    )

    # Make transcript.json the same size as the mocked remote object.
    skipped["youtube/abc123/transcript.json"] = transcript_path.stat().st_size
    asset_archive.archive_note("task-1", "youtube", "https://youtu.be/abc12345678", note, transcript_path)

    assert ("assets", "youtube/abc123/transcript.json", "task_transcript.json", "application/json") not in uploaded
    assert ("assets", "youtube/abc123/audio.m4a", "audio.m4a", "audio/mp4") not in uploaded
    assert any(item[1] == "youtube/abc123/subtitle.en-US.json" for item in uploaded)


def test_archive_retries_upload_once(tmp_path, monkeypatch, caplog):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(asset_archive, "storage_config_manager", manager)
    transcript_path = tmp_path / "task_transcript.json"
    transcript_path.write_text(json.dumps({"full_text": "hello", "segments": []}), encoding="utf-8")
    note = make_note(tmp_path, raw=False)
    attempts = []

    monkeypatch.setattr(
        asset_archive.object_storage,
        "stat_object",
        lambda *_args: (_ for _ in ()).throw(ObjectStorageError("assets", "missing", "missing")),
    )

    def flaky_put(*args, **kwargs):
        attempts.append(args[1])
        if len(attempts) == 1:
            raise ObjectStorageError("assets", args[1], "temporary")

    monkeypatch.setattr(asset_archive.object_storage, "put_file", flaky_put)
    with caplog.at_level("WARNING"):
        asset_archive.archive_note("task-1", "youtube", "https://youtu.be/abc12345678", note, transcript_path)

    assert attempts[:2] == ["youtube/abc123/transcript.json"] * 2
    assert "重试一次" in caplog.text


def test_restore_prefers_transcript_and_writes_back_cache(tmp_path, monkeypatch, caplog):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(asset_archive, "storage_config_manager", manager)
    raw = {
        "language": "en-US",
        "full_text": "from object storage",
        "segments": [{"start": 0, "end": 1, "text": "from object storage"}],
        "raw": {"source": "youtube"},
    }

    monkeypatch.setattr(
        asset_archive.object_storage,
        "list_objects",
        lambda *_args: [ObjectInfo("youtube/abc123/subtitle.en-US.json", 10)],
    )

    def fake_get_file(_source, key, path):
        Path(path).write_text(json.dumps(raw), encoding="utf-8")

    monkeypatch.setattr(asset_archive.object_storage, "get_file", fake_get_file)
    cache = tmp_path / "task_transcript.json"
    with caplog.at_level("INFO"):
        restored = asset_archive.restore_transcript("youtube", "abc123", cache)

    assert restored is not None
    assert restored.full_text == "from object storage"
    assert restored.raw == {"source": "youtube"}
    assert cache.exists()
    assert "从资产桶还原转写结果" in caplog.text


def test_enqueue_archive_exposes_pending_running_and_done_states(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(asset_archive, "storage_config_manager", manager)
    transcript_path = tmp_path / "status-task_transcript.json"
    transcript_path.write_text(json.dumps({"full_text": "hello", "segments": [], "raw": {"source": "cache"}}))
    note = make_note(tmp_path)
    started = threading.Event()
    release = threading.Event()

    monkeypatch.setattr(
        asset_archive.object_storage,
        "stat_object",
        lambda *_args: (_ for _ in ()).throw(ObjectStorageError("assets", "missing", "missing")),
    )

    def fake_put(_source, key, _path, _content_type):
        if key.endswith("transcript.json"):
            started.set()
            assert release.wait(timeout=2)

    monkeypatch.setattr(asset_archive.object_storage, "put_file", fake_put)
    thread = asset_archive.enqueue_archive(
        "status-task",
        "bilibili",
        "https://www.bilibili.com/video/BV1abc",
        note,
        transcript_path,
    )
    assert thread is not None
    pending = asset_archive.get_archive_status("bilibili", "abc123")
    assert pending["transcript"]["state"] in {"pending", "running"}
    assert pending["video"]["state"] == "skipped"

    assert started.wait(timeout=2)
    assert asset_archive.get_archive_status("bilibili", "abc123")["transcript"]["state"] == "running"
    release.set()
    thread.join(timeout=2)
    final = asset_archive.get_archive_status("bilibili", "abc123")
    assert final["transcript"]["state"] == "done"
    assert final["audio"]["state"] == "done"
    assert final["subtitle"]["state"] == "done"


def test_youtube_archive_includes_selected_and_manual_subtitle_tracks(tmp_path, monkeypatch):
    manager = configured_manager(tmp_path)
    monkeypatch.setattr(asset_archive, "storage_config_manager", manager)
    note = make_note(tmp_path)
    french = TranscriptResult(
        language="fr",
        full_text="bonjour",
        segments=[TranscriptSegment(start=0, end=1, text="bonjour")],
        raw={"source": "youtube", "is_generated": False},
    )
    from app.downloaders.youtube_subtitle import YouTubeSubtitleFetcher

    monkeypatch.setattr(YouTubeSubtitleFetcher, "fetch_all_manual", lambda self, _video_id: [french])
    monkeypatch.setattr(
        asset_archive.object_storage,
        "stat_object",
        lambda *_args: (_ for _ in ()).throw(ObjectStorageError("assets", "missing", "missing")),
    )
    uploaded = []
    monkeypatch.setattr(
        asset_archive.object_storage,
        "put_file",
        lambda _source, key, _path, _content_type: uploaded.append(key),
    )

    asset_archive.archive_note(
        "multi-subtitle",
        "youtube",
        "https://www.youtube.com/watch?v=abc12345678",
        note,
        tmp_path / "missing-transcript.json",
    )

    assert "youtube/abc123/subtitle.en-US.json" in uploaded
    assert "youtube/abc123/subtitle.fr.json" in uploaded


def test_note_cache_load_preserves_raw_and_accepts_old_cache(tmp_path, monkeypatch):
    generator = note_module.NoteGenerator.__new__(note_module.NoteGenerator)
    monkeypatch.setattr(generator, "_update_status", lambda *_args, **_kwargs: None)

    class Downloader:
        def download_subtitles(self, _url):
            raise AssertionError("cache should be used")

    cache = tmp_path / "task_transcript.json"
    cache.write_text(
        json.dumps(
            {
                "language": "zh",
                "full_text": "缓存字幕",
                "segments": [{"start": 0, "end": 1, "text": "缓存字幕"}],
                "raw": {"source": "youtube"},
            }
        ),
        encoding="utf-8",
    )
    loaded = generator._get_transcript(
        Downloader(), "https://example.com/video", "", cache, "transcribing", "task"
    )
    assert loaded is not None
    assert loaded.raw == {"source": "youtube"}

    cache.write_text(
        json.dumps(
            {
                "language": "zh",
                "full_text": "旧缓存",
                "segments": [{"start": 0, "end": 1, "text": "旧缓存"}],
            }
        ),
        encoding="utf-8",
    )
    old_loaded = generator._get_transcript(
        Downloader(), "https://example.com/video", "", cache, "transcribing", "task"
    )
    assert old_loaded is not None
    assert old_loaded.raw is None


def test_prefetched_subtitle_cache_marks_raw_for_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(note_router, "NOTE_OUTPUT_DIR", str(tmp_path))
    note_router._persist_prefetched_transcript(
        "prefetched-task",
        {
            "language": "zh-Hans",
            "full_text": "你好",
            "segments": [{"start": 0, "end": 1, "text": "你好"}],
        },
    )
    cached = json.loads((tmp_path / "prefetched-task_transcript.json").read_text(encoding="utf-8"))
    assert cached["raw"] == {"source": "prefetched"}


def test_note_generation_uses_asset_restore_before_platform(tmp_path, monkeypatch):
    restored = TranscriptResult(
        language="en-US",
        full_text="restored transcript",
        segments=[TranscriptSegment(start=0, end=1, text="restored transcript")],
    )
    generator = note_module.NoteGenerator.__new__(note_module.NoteGenerator)
    generator.video_path = None
    generator.video_img_urls = []
    monkeypatch.setattr(note_module, "NOTE_OUTPUT_DIR", tmp_path)

    class Downloader:
        def download_subtitles(self, _url):
            raise AssertionError("platform subtitle API should not be called after asset restore")

    monkeypatch.setattr(generator, "_get_downloader", lambda _platform: Downloader())
    monkeypatch.setattr(generator, "_get_gpt", lambda *_args: object())
    monkeypatch.setattr(asset_archive, "restore_transcript", lambda *_args: restored)
    monkeypatch.setattr(generator, "_summarize_text", lambda **_kwargs: "# restored note")
    monkeypatch.setattr(generator, "_save_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(generator, "_update_status", lambda *_args, **_kwargs: None)

    result = generator.generate(
        video_url="https://www.youtube.com/watch?v=abc12345678",
        platform="youtube",
        task_id="restore-task",
        model_name="model",
        provider_id="provider",
        _format=[],
    )

    assert result is not None
    assert result.transcript.full_text == "restored transcript"
    assert result.audio_meta.video_id == "abc12345678"
    assert (tmp_path / "restore-task_audio.json").exists()
