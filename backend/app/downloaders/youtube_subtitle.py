"""
通过 youtube-transcript-api 获取 YouTube 字幕。
优先人工字幕，其次自动生成字幕。不依赖 yt_dlp，无需下载任何文件。
"""

from typing import Optional, List

from youtube_transcript_api import YouTubeTranscriptApi

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.proxy_config_manager import ProxyConfigManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class YouTubeSubtitleFetcher:
    """通过 youtube-transcript-api 获取 YouTube 字幕。"""

    def __init__(self):
        # 配了全局代理就给 youtube-transcript-api 套一个带 proxies 的 requests.Session，
        # 否则国内拉字幕同样会超时。代理未配置时退回默认无代理客户端。
        proxy = ProxyConfigManager().get_proxy_url()
        if proxy:
            try:
                import requests
                session = requests.Session()
                session.proxies = {"http": proxy, "https": proxy}
                self._api = YouTubeTranscriptApi(http_client=session)
                logger.info(f"YouTube 字幕走代理: {proxy}")
            except Exception as e:
                logger.warning(f"为 youtube-transcript-api 注入代理失败，回退无代理: {e}")
                self._api = YouTubeTranscriptApi()
        else:
            self._api = YouTubeTranscriptApi()

    def _fetch_track(self, transcript) -> Optional[TranscriptResult]:
        """Fetch one track and normalize both supported API result shapes."""
        fetched = transcript.fetch()
        segments = []
        for snippet in fetched:
            # youtube-transcript-api >=1.0 returns FetchedTranscriptSnippet
            # objects; older versions return dictionaries.
            if isinstance(snippet, dict):
                text = (snippet.get("text") or "").strip()
                start = snippet.get("start", 0)
                duration = snippet.get("duration", 0)
            else:
                text = (getattr(snippet, "text", "") or "").strip()
                start = getattr(snippet, "start", 0)
                duration = getattr(snippet, "duration", 0)
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=float(start),
                    end=float(start) + float(duration),
                    text=text,
                )
            )

        if not segments:
            return None

        return TranscriptResult(
            language=transcript.language_code,
            full_text=" ".join(segment.text for segment in segments),
            segments=segments,
            raw={
                "source": "youtube_transcript_api",
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": bool(transcript.is_generated),
            },
        )

    def fetch_all_manual(self, video_id: str) -> List[TranscriptResult]:
        """Fetch every manual track, isolating failures to one language."""
        try:
            transcript_list = self._api.list(video_id)
        except Exception as exc:
            logger.warning(f"YouTube 人工字幕列表获取失败 video_id={video_id}: {exc}")
            return []

        results: List[TranscriptResult] = []
        for transcript in transcript_list:
            if getattr(transcript, "is_generated", False):
                continue
            language_code = getattr(transcript, "language_code", "")
            try:
                result = self._fetch_track(transcript)
                if result:
                    results.append(result)
                    logger.info(f"归档人工字幕轨道: {language_code}")
                else:
                    logger.warning(f"YouTube 人工字幕内容为空 video_id={video_id} lang={language_code}")
            except Exception as exc:
                logger.warning(
                    f"YouTube 人工字幕轨道获取失败 video_id={video_id} lang={language_code}: {exc}"
                )
        return results

    def fetch_subtitles(
        self,
        video_id: str,
        langs: Optional[List[str]] = None,
    ) -> Optional[TranscriptResult]:
        if langs is None:
            langs = ["zh-Hans", "zh", "zh-CN", "zh-TW", "en", "en-US", "ja"]

        try:
            # 1. 列出所有可用字幕
            transcript_list = self._api.list(video_id)

            available = []
            for t in transcript_list:
                available.append(
                    f"{t.language_code}({'auto' if t.is_generated else 'manual'})"
                )
            logger.info(f"可用字幕轨道: {', '.join(available)}")

            # 2. 按优先级查找：先人工字幕，再自动字幕
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(langs)
                logger.info(f"选中人工字幕: {transcript.language_code} ({transcript.language})")
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(langs)
                    logger.info(f"选中自动字幕: {transcript.language_code} ({transcript.language})")
                except Exception:
                    # 都没匹配，取第一个可用的
                    for t in transcript_list:
                        transcript = t
                        source = "auto" if t.is_generated else "manual"
                        logger.info(f"使用首个可用字幕: {t.language_code} ({source})")
                        break

            if not transcript:
                logger.info(f"YouTube 视频 {video_id} 没有任何可用字幕")
                return None

            # 3. 获取字幕内容
            result = self._fetch_track(transcript)
            if not result:
                logger.warning(f"YouTube 字幕内容为空: {video_id}")
                return None
            logger.info(f"成功获取 YouTube 字幕，共 {len(result.segments)} 段")
            return result

        except Exception as e:
            logger.warning(f"YouTube 字幕获取失败: {e}")
            return None
