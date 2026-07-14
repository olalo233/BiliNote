from app.downloaders.base import PLAYABLE_VIDEO_FORMAT
from app.downloaders.youtube_downloader import _build_download_options


def test_metadata_only_options_do_not_select_a_media_format():
    options = _build_download_options('/tmp/%(id)s.%(ext)s', skip_download=True)

    assert 'format' not in options
    assert options['skip_download'] is True
    assert options['ignore_no_formats_error'] is True


def test_media_download_options_keep_format_selection():
    options = _build_download_options('/tmp/%(id)s.%(ext)s')

    assert options['format'] == 'bestaudio[ext=m4a]/bestaudio/best'
    assert 'ignore_no_formats_error' not in options


def test_archived_video_format_prefers_h264_with_fallbacks():
    from app.downloaders.youtube_downloader import YoutubeDownloader

    # Avoid network work; inspect the format through the shared constant used
    # by download_video and the platform adapters.
    assert PLAYABLE_VIDEO_FORMAT == (
        'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    )
    assert YoutubeDownloader.download_video.__qualname__.startswith('YoutubeDownloader.')
