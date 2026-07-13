"""youtube-transcript-api >=1.0 返回 FetchedTranscriptSnippet 对象而非 dict。
回归保护：禁止把对象 repr 当字幕文本（曾产出整篇 FetchedTranscriptSnippet(...) 垃圾笔记）。"""
from dataclasses import dataclass
from unittest.mock import MagicMock

from app.downloaders.youtube_subtitle import YouTubeSubtitleFetcher


@dataclass
class FakeSnippet:
    text: str
    start: float
    duration: float


def _fetcher_with_snippets(snippets):
    transcript = MagicMock()
    transcript.language_code = "en-US"
    transcript.language = "English (United States)"
    transcript.is_generated = False
    transcript.fetch.return_value = snippets

    transcript_list = MagicMock()
    transcript_list.__iter__ = lambda _self: iter([transcript])
    transcript_list.find_manually_created_transcript.return_value = transcript

    fetcher = YouTubeSubtitleFetcher()
    fetcher._api = MagicMock()
    fetcher._api.list.return_value = transcript_list
    return fetcher


def test_object_snippets_use_attributes_not_repr():
    fetcher = _fetcher_with_snippets([
        FakeSnippet(text="hello world", start=0.5, duration=2.0),
        FakeSnippet(text="second line", start=2.5, duration=1.5),
    ])
    result = fetcher.fetch_subtitles("dummy")
    assert result is not None
    assert result.full_text == "hello world second line"
    assert "FakeSnippet" not in result.full_text
    assert result.segments[0].start == 0.5
    assert result.segments[0].end == 2.5
    assert result.segments[1].start == 2.5


def test_dict_snippets_still_supported():
    fetcher = _fetcher_with_snippets([
        {"text": "legacy dict", "start": 1.0, "duration": 3.0},
    ])
    result = fetcher.fetch_subtitles("dummy")
    assert result is not None
    assert result.full_text == "legacy dict"
    assert result.segments[0].start == 1.0
    assert result.segments[0].end == 4.0
