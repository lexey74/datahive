"""
Base class for YouTube downloaders, providing shared strategy-chain logic.
"""
import asyncio
import inspect
from pathlib import Path
from typing import Optional

import structlog

from .downloader_base import BaseDownloader, DownloadError, DownloadSettings
from .external_site_grabber import ExternalSiteGrabber
from .youtube_grabber_base import YouTubeDownloadStrategy
from .youtube_grabber_v2 import ImprovedCookieManager, ProductionYouTubeGrabber


logger = structlog.get_logger(__name__)


class YouTubeBaseDownloader(BaseDownloader):
    """Base class for YouTube downloaders with strategy chain support."""

    def __init__(
        self,
        settings: DownloadSettings,
        output_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(settings, output_dir)

        # Cookie manager setup
        cookie_manager = None
        if settings.youtube_cookies_dir:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies_dir
            )
            for cookie_file in settings.youtube_cookies_dir.glob("youtube_cookies*.txt"):
                cookie_manager.add_cookies(cookie_file)
        elif settings.youtube_cookies:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies.parent
            )
            cookie_manager.add_cookies(settings.youtube_cookies)

        self.grabber = ProductionYouTubeGrabber(cookie_manager=cookie_manager)
        self._external_grabber = ExternalSiteGrabber(
            base_url=settings.external_site_url,
            timeout_ms=settings.external_site_timeout_ms,
        )

    @property
    def strategies(self) -> list[YouTubeDownloadStrategy]:
        return [self._external_grabber, self.grabber]

    async def _call_strategy(
        self,
        strategy: YouTubeDownloadStrategy,
        url: str,
        output_dir: Path,
        quality: str,
    ) -> Path:
        """Вызывает стратегию, определяя sync/async реализацию."""
        if inspect.iscoroutinefunction(strategy.download_video):
            return await strategy.download_video(url, output_dir, quality)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, strategy.download_video, url, output_dir, quality
            )

    async def _run_strategy_chain(self, url: str, output_dir: Path, quality: str) -> Path:
        """Перебирает стратегии по цепочке; поднимает DownloadError если все не сработали."""
        last_error: Optional[Exception] = None
        for strategy in self.strategies:
            try:
                path = await self._call_strategy(strategy, url, output_dir, quality)
                logger.info(
                    "Стратегия загрузки сработала",
                    strategy=type(strategy).__name__,
                    url=url,
                )
                return path
            except Exception as e:
                logger.warning(
                    "Стратегия загрузки не сработала, переходим к следующей",
                    strategy=type(strategy).__name__,
                    error=str(e),
                )
                last_error = e
        raise DownloadError(f"Все стратегии загрузки не сработали для {url}") from last_error
