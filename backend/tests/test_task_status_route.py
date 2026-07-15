import pytest
from fastapi import HTTPException

from app.routers import note as note_router


def test_task_status_returns_not_found_for_missing_note(tmp_path, monkeypatch):
    monkeypatch.setattr(note_router, "NOTE_OUTPUT_DIR", str(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        note_router.get_task_status("missing-task")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "笔记不存在或已删除"
