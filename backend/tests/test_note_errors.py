import json

from app.services import note as note_module
from app.services.note import NoteGenerator


def test_failed_status_strips_ansi_codes(monkeypatch, tmp_path):
    monkeypatch.setattr(note_module, 'NOTE_OUTPUT_DIR', tmp_path)

    NoteGenerator.__new__(NoteGenerator)._handle_exception(
        'ansi-test', ValueError('\x1b[31mERROR:\x1b[0m format unavailable')
    )

    status = json.loads((tmp_path / 'ansi-test.status.json').read_text())
    assert status['status'] == 'FAILED'
    assert status['message'] == 'ERROR: format unavailable'
