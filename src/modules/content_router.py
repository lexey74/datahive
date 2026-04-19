"""
Content Router

Оркестратор всех подмодулей скачивания.
Автоматически определяет тип контента и маршрутизирует к нужному скачивателю.
"""

from typing import List, Optional
from pathlib import Path

from .downloader_base import BaseDownloader, DownloadResult, DownloadSettings
from .instagram_post_downloader import InstagramPostDownloader
from .instagram_reels_downloader import InstagramReelsDownloader
from .youtube_video_downloader import YouTubeVideoDownloader
from .youtube_shorts_downloader import YouTubeShortsDownloader
from .downloader_utils import print_progress


class ContentRouter:
    """
    Маршрутизирует URL к соответствующему скачивателю

    Автоматически определяет:
    - Instagram Post vs Reels
    - YouTube Video vs Shorts
    - Другие платформы (TODO)
    """

    def __init__(self, settings: DownloadSettings, output_dir: Optional[Path] = None):
        """
        Args:
            settings: Настройки скачивания
            output_dir: Директория для сохранения
        """
        self.settings = settings
        self.output_dir = output_dir or Path("downloads")

        # Инициализируем все скачиватели
        self.downloaders: List[BaseDownloader] = [
            InstagramPostDownloader(settings, self.output_dir),
            InstagramReelsDownloader(settings, self.output_dir),
            YouTubeVideoDownloader(settings, self.output_dir),
            YouTubeShortsDownloader(settings, self.output_dir),
        ]

    def download(self, url: str) -> DownloadResult:
        """
        Скачивает контент по URL

        Автоматически определяет тип и выбирает подходящий скачиватель.

        Args:
            url: URL контента

        Returns:
            DownloadResult с результатами

        Raises:
            ValueError: Если URL не поддерживается
            Exception: При ошибке скачивания
        """
        # Находим подходящий скачиватель
        downloader = self.detect_downloader(url)

        if not downloader:
            raise ValueError(
                f"URL не поддерживается: {url}\n"
                f"Поддерживаемые платформы:\n"
                f"  - Instagram: /p/, /reel/, /reels/\n"
                f"  - YouTube: /watch, /shorts/, youtu.be"
            )

        # Скачиваем
        print_progress(f"🎯 Скачиватель: {downloader.__class__.__name__}", "")
        result = downloader.download(url)
        if result is None:
            raise RuntimeError(f"Не удалось скачать контент: {url}")

        print_progress("✅ Скачивание завершено!", "")
        print_progress(f"📁 Папка: {result.folder_path}", "")
        print_progress(f"📦 Файлов: {len(result.media_files)}", "")

        return result

    def download_comments(self, url: str, folder_path: Path) -> Optional[Path]:
        """
        Скачивает только комментарии для контента

        Args:
            url: URL контента
            folder_path: Папка для сохранения

        Returns:
            Путь к файлу комментариев или None
        """
        downloader = self.detect_downloader(url)
        if not downloader:
            return None

        print_progress(
            f"🎯 Скачивание комментариев: {downloader.__class__.__name__}", ""
        )
        return downloader.download_comments_only(url, folder_path)

    def detect_downloader(self, url: str) -> Optional[BaseDownloader]:
        """
        Определяет подходящий скачиватель для URL

        Args:
            url: URL контента

        Returns:
            BaseDownloader или None если не найден
        """
        for downloader in self.downloaders:
            if downloader.can_handle(url):
                return downloader

        return None

    def is_supported(self, url: str) -> bool:
        """
        Проверяет, поддерживается ли URL

        Args:
            url: URL контента

        Returns:
            True если поддерживается
        """
        return self.detect_downloader(url) is not None

    def get_supported_platforms(self) -> List[str]:
        """
        Возвращает список поддерживаемых платформ

        Returns:
            Список названий платформ
        """
        platforms = set()

        for downloader in self.downloaders:
            class_name = downloader.__class__.__name__
            if "Instagram" in class_name:
                platforms.add("Instagram")
            elif "YouTube" in class_name:
                platforms.add("YouTube")

        return sorted(list(platforms))

    def get_downloader_info(self, url: str) -> dict:
        """
        Возвращает информацию о скачивателе для URL

        Args:
            url: URL контента

        Returns:
            Словарь с информацией
        """
        downloader = self.detect_downloader(url)

        if not downloader:
            return {
                "supported": False,
                "downloader": None,
                "platform": "Unknown",
                "content_type": "Unknown",
            }

        class_name = downloader.__class__.__name__

        # Определяем платформу
        if "Instagram" in class_name:
            platform = "Instagram"
            if "Post" in class_name:
                content_type = "Post/Carousel"
            elif "Reels" in class_name:
                content_type = "Reels"
            else:
                content_type = "Unknown"
        elif "YouTube" in class_name:
            platform = "YouTube"
            if "Shorts" in class_name:
                content_type = "Shorts"
            elif "Video" in class_name:
                content_type = "Video"
            else:
                content_type = "Unknown"
        else:
            platform = "Unknown"
            content_type = "Unknown"

        return {
            "supported": True,
            "downloader": class_name,
            "platform": platform,
            "content_type": content_type,
        }
