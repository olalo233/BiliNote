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
