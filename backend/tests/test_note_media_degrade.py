from pathlib import Path

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import note as note_module
from app.services.note import NoteGenerator


def test_subtitled_task_degrades_to_text_when_media_download_fails(monkeypatch, tmp_path):
    transcript = TranscriptResult(
        language='en',
        full_text='hello world',
        segments=[TranscriptSegment(start=0, end=1, text='hello world')],
    )
    generator = NoteGenerator.__new__(NoteGenerator)
    generator.video_path = Path('/tmp/should-not-be-used.mp4')
    generator.video_img_urls = ['stale-image']
    statuses = []
    summary_args = {}

    class Downloader:
        def download_subtitles(self, video_url):
            return transcript

    monkeypatch.setattr(note_module, 'NOTE_OUTPUT_DIR', tmp_path)
    monkeypatch.setattr(generator, '_get_downloader', lambda platform: Downloader())
    monkeypatch.setattr(generator, '_get_gpt', lambda model_name, provider_id: object())
    monkeypatch.setattr(
        generator,
        '_download_media',
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError('format unavailable')),
    )

    def summarize(**kwargs):
        summary_args.update(kwargs)
        return '# note'

    monkeypatch.setattr(generator, '_summarize_text', summarize)
    monkeypatch.setattr(generator, '_save_metadata', lambda **kwargs: None)
    monkeypatch.setattr(
        generator,
        '_update_status',
        lambda task_id, status, message=None: statuses.append((status, message)),
    )

    result = generator.generate(
        video_url='https://www.youtube.com/watch?v=YM0_8mOaKic',
        platform='youtube',
        task_id='degrade-test',
        model_name='test-model',
        provider_id='test-provider',
        screenshot=True,
        video_understanding=True,
        _format=['screenshot', 'link'],
    )

    assert result is not None
    assert result.markdown == '> 来源链接：https://www.youtube.com/watch?v=YM0_8mOaKic\n\n# note'
    assert result.audio_meta.file_path == ''
    assert result.audio_meta.video_id == 'YM0_8mOaKic'
    assert summary_args['screenshot'] is False
    assert summary_args['formats'] == ['link']
    assert summary_args['video_img_urls'] == []
    assert statuses[-1][0].value == 'SUCCESS'
