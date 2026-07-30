from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import note


def test_upload_streams_chunks_and_sanitizes_filename(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(note.router)
    monkeypatch.setattr(note, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(note, "UPLOAD_CHUNK_SIZE", 3)

    payload = b"video-content-that-requires-multiple-chunks"
    response = TestClient(app).post(
        "/upload",
        files={"file": ("../recording.mp4", payload, "video/mp4")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    stored_filename = data["url"].removeprefix("/uploads/")
    assert stored_filename.endswith("_recording.mp4")
    assert (tmp_path / stored_filename).read_bytes() == payload
