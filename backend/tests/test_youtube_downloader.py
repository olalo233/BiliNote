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


def test_archived_video_format_keeps_best_codec_not_forcing_h264():
    import inspect

    from app.downloaders.youtube_downloader import YoutubeDownloader

    # 归档取源站最佳编码（含 av1），不得强制 avc1/h264。
    src = inspect.getsource(YoutubeDownloader.download_video)
    assert "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" in src
    assert "vcodec^=avc1" not in src
