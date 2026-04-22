"""
Base class for YouTube downloaders, providing shared strategy-chain logic.
"""
import asyncio
import inspect
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import structlog

from .downloader_base import BaseDownloader, DownloadError, DownloadSettings
from .youtube_grabber_base import YouTubeDownloadStrategy
from .youtube_grabber_v2 import ImprovedCookieManager, ProductionYouTubeGrabber

if TYPE_CHECKING:
    from .youtube_cookie_manager import PlaywrightCookieManager


logger = structlog.get_logger(__name__)


def _is_youtube_cookie_file(cookie_file: Path) -> bool:
    """Определяет, относится ли файл cookies к YouTube."""
    if not cookie_file.is_file():
        return False

    normalized_name = cookie_file.name.lower()
    return normalized_name.endswith(".txt") and (
        "youtube" in normalized_name or "youtu" in normalized_name or normalized_name.startswith("yt_")
    )


def _collect_youtube_cookie_files(settings: DownloadSettings) -> list[Path]:
    """Собирает все доступные YouTube cookie-файлы без дубликатов."""
    cookie_files: list[Path] = []
    seen_paths: set[Path] = set()

    if settings.youtube_cookies_dir and settings.youtube_cookies_dir.exists():
        for cookie_file in settings.youtube_cookies_dir.iterdir():
            if not _is_youtube_cookie_file(cookie_file):
                continue
            resolved_path = cookie_file.resolve()
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            cookie_files.append(cookie_file)

    if settings.youtube_cookies and settings.youtube_cookies.exists():
        resolved_path = settings.youtube_cookies.resolve()
        if resolved_path not in seen_paths:
            cookie_files.append(settings.youtube_cookies)

    return cookie_files


class YouTubeBaseDownloader(BaseDownloader):
    """Base class for YouTube downloaders with strategy chain support."""

    def __init__(
        self,
        settings: DownloadSettings,
        output_dir: Optional[Path] = None,
        playwright_cookie_manager: Optional["PlaywrightCookieManager"] = None,
    ) -> None:
        super().__init__(settings, output_dir)

        # Cookie manager setup
        cookie_manager = None
        cookie_files = _collect_youtube_cookie_files(settings)
        if cookie_files:
            cookies_dir = (
                settings.youtube_cookies_dir
                or cookie_files[0].parent
            )
            cookie_manager = ImprovedCookieManager(cookies_dir=cookies_dir)
            for cookie_file in cookie_files:
                cookie_manager.add_cookies(cookie_file)

        # Если передан PlaywrightCookieManager — добавляем его куки-файл в пул
        self._playwright_cookie_manager = playwright_cookie_manager
        if playwright_cookie_manager and playwright_cookie_manager.is_configured():
            if cookie_manager is None:
                cookie_file = playwright_cookie_manager.cookie_file_path
                cookie_manager = ImprovedCookieManager(
                    cookies_dir=cookie_file.parent
                )
            if playwright_cookie_manager.cookie_file_path.exists():
                cookie_manager.add_cookies(playwright_cookie_manager.cookie_file_path)

        self.grabber = ProductionYouTubeGrabber(cookie_manager=cookie_manager)

    @property
    def strategies(self) -> list[YouTubeDownloadStrategy]:
        # ExternalSiteGrabber убран: googlevideo.com URLs привязаны к IP стороннего сервиса
        return [self.grabber]

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
