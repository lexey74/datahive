"""
YouTube Shorts Downloader

Скачивает YouTube Shorts (вертикальные короткие видео).
Использует цепочку стратегий: ExternalSiteGrabber → ProductionYouTubeGrabber (fallback).
"""

import asyncio
from pathlib import Path
from typing import Dict, Optional

import structlog

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    YouTubeContentType,
    YouTubeVideoResult,
    DownloadSettings,
)
from .downloader_utils import (
    clean_filename,
    extract_video_id_youtube,
    print_progress,
    format_duration,
    format_count,
)
from .external_site_grabber import ExternalSiteGrabber
from .youtube_grabber_base import YouTubeDownloadStrategy
from .youtube_grabber_v2 import ProductionYouTubeGrabber, ImprovedCookieManager
from .youtube_comment_service import YouTubeCommentService

logger = structlog.get_logger("datahive.youtube_shorts_downloader")


class DownloadError(Exception):
    """Ошибка загрузки Shorts — все стратегии не сработали"""
    pass


class YouTubeShortsDownloader(BaseDownloader):
    """
    Скачивает YouTube Shorts

    Поддерживает:
    - Вертикальные короткие видео
    - Цепочку стратегий: ExternalSiteGrabber → ProductionYouTubeGrabber (fallback)
    - Скачивание комментариев через YouTubeCommentService
    """

    def __init__(
        self,
        settings: DownloadSettings,
        output_dir: Optional[Path] = None,
        external_site_url: str = "https://en.ssyoutube.com/en/download",
        external_site_timeout_ms: int = 30_000,
    ):
        super().__init__(settings, output_dir)

        # Создаем cookie manager
        cookie_manager = None
        if settings.youtube_cookies_dir:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies_dir
            )
            # Добавляем все YouTube cookies
            for cookie_file in settings.youtube_cookies_dir.glob(
                "youtube_cookies*.txt"
            ):
                cookie_manager.add_cookies(cookie_file)
        elif settings.youtube_cookies:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies.parent
            )
            cookie_manager.add_cookies(settings.youtube_cookies)

        # Используем тот же ProductionYouTubeGrabber
        self.grabber = ProductionYouTubeGrabber(cookie_manager=cookie_manager)

        # Первичная стратегия — внешний сайт-посредник
        self._external_grabber = ExternalSiteGrabber(
            base_url=external_site_url,
            timeout_ms=external_site_timeout_ms,
        )

        # Инициализируем сервис комментариев
        self.comment_service = YouTubeCommentService()

    @property
    def strategies(self) -> list[YouTubeDownloadStrategy]:
        """Цепочка стратегий: ExternalSiteGrabber первым, ProductionYouTubeGrabber как fallback."""
        return [self._external_grabber, self.grabber]

    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        return "/shorts/" in url.lower() and "youtube.com" in url.lower()

    def download(self, url: str) -> YouTubeVideoResult:
        """
        Скачивает YouTube Short

        Args:
            url: URL short

        Returns:
            YouTubeVideoResult с результатами
        """
        print_progress(f"🩳 Анализ Shorts: {url}")

        # Извлекаем video ID
        video_id = extract_video_id_youtube(url)
        if not video_id:
            raise ValueError(f"Не удалось извлечь video ID из URL: {url}")

        # Получаем метаданные
        metadata = self.grabber.get_metadata(url)

        # Создаем папку
        channel = metadata.get("channel", "unknown_channel")
        title = clean_filename(metadata.get("title", "no_title"))
        folder_path = self.create_folder(
            prefix=f"youtube_shorts_{channel}", content_id=video_id, title=title
        )

        print_progress(f"📁 Папка: {folder_path}", "")

        # Скачиваем видео через цепочку стратегий
        # Для Shorts всегда берем лучшее доступное качество
        print_progress("⬇️  Скачивание Shorts...", "")
        video_path = asyncio.run(
            self._run_strategy_chain(url, folder_path, quality="best")
        )
        print_progress(f"✅ Shorts скачан: {video_path.name}", "")

        # Сохраняем описание
        description_file = self.save_description(
            folder_path=folder_path, description=self._format_description(metadata)
        )

        # Скачиваем комментарии если нужно
        comments_file = None
        if self.settings.download_comments:
            comments_file = self._download_comments(video_id, url, folder_path)

        return YouTubeVideoResult(
            source=ContentSource.YOUTUBE,
            content_type=YouTubeContentType.SHORT,
            url=url,
            content_id=video_id,
            folder_path=folder_path,
            media_files=[video_path],
            description_file=description_file,
            comments_file=comments_file,
            channel=channel,
            views=metadata.get("view_count", 0),
            likes=metadata.get("like_count", 0),
            duration=metadata.get("duration", 0),
        )

    async def _call_strategy(
        self, strategy: YouTubeDownloadStrategy, url: str, folder_path: Path, quality: str
    ) -> Path:
        """
        Вызывает стратегию, автоматически определяя sync/async реализацию.

        Если `download_video` является корутиной — вызываем через await.
        Если синхронная — запускаем в executor, чтобы не блокировать event loop.
        """
        import inspect
        import functools
        method = strategy.download_video
        if inspect.iscoroutinefunction(method):
            return await method(url, folder_path, quality)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, functools.partial(method, url, folder_path, quality)
            )

    async def _run_strategy_chain(
        self, url: str, folder_path: Path, quality: str
    ) -> Path:
        """
        Перебирает стратегии по цепочке, возвращает путь к файлу при первом успехе.

        Args:
            url: URL Shorts-видео
            folder_path: Директория для сохранения
            quality: Желаемое качество

        Returns:
            Путь к скачанному файлу

        Raises:
            DownloadError: Если все стратегии завершились неудачей
        """
        last_error: Optional[Exception] = None
        for strategy in self.strategies:
            strategy_name = type(strategy).__name__
            try:
                video_path = await self._call_strategy(strategy, url, folder_path, quality)
                logger.info(
                    "Стратегия загрузки сработала",
                    strategy=strategy_name,
                    url=url,
                )
                return video_path
            except Exception as exc:
                logger.warning(
                    "Стратегия загрузки не сработала, переходим к следующей",
                    strategy=strategy_name,
                    error=str(exc),
                )
                last_error = exc

        raise DownloadError(
            f"Все стратегии загрузки не сработали для {url}"
        ) from last_error

    def download_comments_only(self, url: str, folder_path: Path) -> Optional[Path]:
        """Скачивает только комментарии"""
        video_id = extract_video_id_youtube(url)
        if not video_id:
            return None

        return self._download_comments(video_id, url, folder_path)

    def _download_comments(
        self, video_id: str, url: str, folder_path: Path
    ) -> Optional[Path]:
        """
        Скачивает комментарии через YouTubeCommentService

        Returns:
            Путь к файлу комментариев или None
        """
        try:
            print_progress("💬 Скачивание комментариев...", "")
            output_file = folder_path / "comments.md"

            result = self.comment_service.download_comments(
                url=url,
                output_file=output_file,
                max_comments=self.settings.max_comments,
                sort_by="popular",
            )

            if result["comments"]:
                print_progress(f"✅ Комментариев: {len(result['comments'])}", "")
                return output_file

            return None
        except Exception as e:
            print_progress(f"⚠️  Комментарии недоступны: {e}", "")
            return None

    def _format_description(self, metadata: Dict) -> str:
        """
        Форматирует описание в Markdown

        Args:
            metadata: Метаданные

        Returns:
            Markdown текст
        """
        lines = [
            f"# {metadata.get('title', 'Без названия')}",
            "",
            "🩳 **YouTube Shorts**",
            "",
            f"**Канал:** {metadata.get('channel', 'unknown')}",
            f"**Дата публикации:** {metadata.get('upload_date', 'unknown')}",
            f"**Длительность:** {format_duration(metadata.get('duration', 0))}",
            "",
            "## Статистика",
            "",
            f"- 👁️ Просмотры: {format_count(metadata.get('view_count', 0))}",
            f"- 👍 Лайки: {format_count(metadata.get('like_count', 0))}",
            "",
            "## Описание",
            "",
            metadata.get("description", "Без описания"),
        ]

        # Добавляем теги если есть
        tags = metadata.get("tags", [])
        if tags:
            lines.append("")
            lines.append("## Теги")
            lines.append("")
            lines.append(", ".join([f"`{tag}`" for tag in tags]))

        return "\n".join(lines)
