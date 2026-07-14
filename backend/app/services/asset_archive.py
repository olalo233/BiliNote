"""Asynchronous archival and restoration for per-video assets."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import object_storage
from app.services.object_storage import ObjectStorageError
from app.services.storage_config_manager import storage_config_manager


logger = logging.getLogger(__name__)

ARCHIVE_KINDS = ("video", "audio", "subtitle", "transcript")
_archive_states: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
_archive_states_lock = threading.Lock()
_LANGUAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _updated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_archive_state(
    platform: str,
    video_id: str,
    kind: str,
    state: str,
    error: str | None = None,
) -> None:
    entry: dict[str, Any] = {"state": state, "updated_at": _updated_at()}
    if error:
        entry["error"] = str(error)[:500]
    with _archive_states_lock:
        _archive_states.setdefault((platform, video_id), {})[kind] = entry


def _initialize_archive_state(platform: str, video_id: str, archive_video: bool) -> None:
    initial = {
        kind: ("pending" if kind != "video" or archive_video else "skipped")
        for kind in ARCHIVE_KINDS
    }
    with _archive_states_lock:
        _archive_states[(platform, video_id)] = {
            kind: {"state": state, "updated_at": _updated_at()}
            for kind, state in initial.items()
        }


def get_archive_status(platform: str, video_id: str) -> dict[str, dict[str, Any]]:
    """Return a snapshot so callers never observe a partially updated job."""
    with _archive_states_lock:
        status = _archive_states.get((platform, video_id), {})
        return {kind: dict(entry) for kind, entry in status.items()}


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


def _upload_if_needed(
    source: str,
    key: str,
    filepath: Path,
    content_type: str,
    errors: list[str] | None = None,
) -> bool:
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
            if errors is not None:
                errors.append(str(exc))
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


def _subtitle_filename(language: str | None) -> str | None:
    value = str(language or "")
    if not _LANGUAGE_RE.fullmatch(value):
        return None
    return f"subtitle.{value}.json"


def _archive_subtitles(
    source: str,
    platform: str,
    video_id: str,
    video_url: str,
    note: NoteResult,
) -> tuple[str, str | None]:
    """Archive the selected subtitle plus all successful YouTube manual tracks."""
    candidates: dict[str, TranscriptResult] = {}

    if platform == "youtube" and video_url:
        try:
            from app.downloaders.youtube_subtitle import YouTubeSubtitleFetcher

            for transcript in YouTubeSubtitleFetcher().fetch_all_manual(video_id):
                filename = _subtitle_filename(transcript.language)
                if filename:
                    candidates[filename] = transcript
        except Exception as exc:
            # The selected track can still be archived when the extra-track
            # lookup is unavailable.
            logger.warning("YouTube 多语字幕获取失败 video_id=%s: %s", video_id, exc)

    selected_filename = _subtitle_filename(note.transcript.language)
    if selected_filename and note.transcript.raw:
        candidates[selected_filename] = note.transcript

    if not candidates:
        return "skipped", "没有可归档字幕"

    errors: list[str] = []
    uploaded = 0
    with tempfile.TemporaryDirectory(prefix="bilinote-subtitles-") as temp_dir:
        for filename, transcript in candidates.items():
            path = Path(temp_dir) / filename
            path.write_text(
                json.dumps(asdict(transcript), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if _upload_if_needed(
                source,
                asset_key(platform, video_id, filename),
                path,
                "application/json",
                errors,
            ):
                uploaded += 1

    if uploaded:
        return "done", None
    return "failed", errors[-1] if errors else "字幕上传失败"


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

    if not get_archive_status(platform, video_id):
        _initialize_archive_state(platform, video_id, archive_video)

    temp_transcript: Path | None = None
    try:
        _set_archive_state(platform, video_id, "transcript", "running")
        try:
            if not transcript_cache_file.is_file():
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as file:
                    json.dump(_transcript_payload(note), file, ensure_ascii=False, indent=2)
                    temp_transcript = Path(file.name)
                transcript_path = temp_transcript
            else:
                transcript_path = transcript_cache_file
            errors: list[str] = []
            success = _upload_if_needed(
                source,
                asset_key(platform, video_id, "transcript.json"),
                transcript_path,
                "application/json",
                errors,
            )
            _set_archive_state(
                platform,
                video_id,
                "transcript",
                "done" if success else "failed",
                errors[-1] if errors else (None if success else "转写结果上传失败"),
            )
        except Exception as exc:
            _set_archive_state(platform, video_id, "transcript", "failed", str(exc))
            logger.error("转写结果归档异常 task_id=%s video_id=%s: %s", task_id, video_id, exc)

        _set_archive_state(platform, video_id, "subtitle", "running")
        try:
            state, error = _archive_subtitles(source, platform, video_id, video_url, note)
            _set_archive_state(platform, video_id, "subtitle", state, error)
        except Exception as exc:
            _set_archive_state(platform, video_id, "subtitle", "failed", str(exc))
            logger.error("字幕归档异常 task_id=%s video_id=%s: %s", task_id, video_id, exc)

        _set_archive_state(platform, video_id, "audio", "running")
        try:
            audio_path = Path(note.audio_meta.file_path) if note.audio_meta.file_path else None
            if not audio_path or not audio_path.is_file():
                _set_archive_state(platform, video_id, "audio", "skipped", "本地音频不存在")
            else:
                ext = audio_path.suffix.lower().lstrip(".") or "m4a"
                content_type = "audio/mpeg" if ext == "mp3" else "audio/mp4"
                errors = []
                success = _upload_if_needed(
                    source,
                    asset_key(platform, video_id, f"audio.{ext}"),
                    audio_path,
                    content_type,
                    errors,
                )
                _set_archive_state(
                    platform,
                    video_id,
                    "audio",
                    "done" if success else "failed",
                    errors[-1] if errors else (None if success else "音频上传失败"),
                )
        except Exception as exc:
            _set_archive_state(platform, video_id, "audio", "failed", str(exc))
            logger.error("音频归档异常 task_id=%s video_id=%s: %s", task_id, video_id, exc)

        if archive_video:
            _set_archive_state(platform, video_id, "video", "running")
            try:
                state, error = _archive_video(source, platform, video_id, video_url, note)
                _set_archive_state(platform, video_id, "video", state, error)
            except Exception as exc:
                _set_archive_state(platform, video_id, "video", "failed", str(exc))
                logger.error("视频归档异常 task_id=%s video_id=%s: %s", task_id, video_id, exc)
    except Exception as exc:
        logger.error("资产归档任务异常 task_id=%s video_id=%s: %s", task_id, video_id, exc, exc_info=True)
    finally:
        if temp_transcript:
            temp_transcript.unlink(missing_ok=True)


def _archive_video(
    source: str,
    platform: str,
    video_id: str,
    video_url: str,
    note: NoteResult,
) -> tuple[str, str | None]:
    video_path = Path(note.audio_meta.video_path) if note.audio_meta.video_path else None
    if not video_path or not video_path.is_file():
        from app.services.constant import SUPPORT_PLATFORM_MAP

        downloader = SUPPORT_PLATFORM_MAP.get(platform)
        if not downloader or not hasattr(downloader, "download_video"):
            return "skipped", "平台不支持完整视频归档"
        try:
            video_path = Path(downloader.download_video(video_url))
        except Exception as exc:
            logger.warning("原始视频下载失败，跳过视频归档 platform=%s video_id=%s: %s", platform, video_id, exc)
            return "failed", str(exc)

    errors: list[str] = []
    success = _upload_if_needed(
        source,
        asset_key(platform, video_id, "video.mp4"),
        video_path,
        "video/mp4",
        errors,
    )
    return ("done", None) if success else ("failed", errors[-1] if errors else "视频上传失败")


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

    video_id = note.audio_meta.video_id
    if not video_id:
        logger.warning("任务缺少 video_id，无法投递资产归档 task_id=%s", task_id)
        return None
    _initialize_archive_state(platform, video_id, archive_video)
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
