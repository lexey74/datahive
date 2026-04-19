"""
Instagram Reels Downloader (HikerAPI)

Скачивает Instagram Reels через HikerAPI SaaS.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    InstagramContentType,
    InstagramReelsResult,
    DownloadSettings,
)
from .downloader_utils import (
    clean_filename,
    extract_shortcode_instagram,
    print_progress,
    format_duration,
    format_count,
)
from .hikerapi_client import HikerAPIClient, MediaInfo

logger = logging.getLogger(__name__)


class InstagramReelsDownloader(BaseDownloader):
    """
    Скачивает Instagram Reels через HikerAPI

    Требует:
    - HIKERAPI_TOKEN в переменных окружения
    """

    def __init__(self, settings: DownloadSettings, output_dir: Optional[Path] = None):
        super().__init__(settings, output_dir)
        self._client: Optional[HikerAPIClient] = None

    @property
    def client(self) -> HikerAPIClient:
        """Ленивая инициализация клиента"""
        if self._client is None:
            self._client = HikerAPIClient()
        return self._client

    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        url_lower = url.lower()
        return "instagram.com" in url_lower and (
            "/reel/" in url_lower or "/reels/" in url_lower
        )

    def download(self, url: str) -> InstagramReelsResult:
        """
        Скачивает Instagram Reel

        Args:
            url: URL reels

        Returns:
            InstagramReelsResult с результатами
        """
        print_progress(f"🎬 Анализ Reels: {url}")

        # Извлекаем shortcode
        shortcode = extract_shortcode_instagram(url)
        if not shortcode:
            raise ValueError(f"Не удалось извлечь shortcode из URL: {url}")

        # Получаем метаданные через HikerAPI
        media_info = self.client.get_media_by_shortcode(shortcode)
        if not media_info:
            raise ValueError(f"Не удалось получить информацию о Reels: {shortcode}")

        # Создаем папку
        title = self._extract_title(media_info)
        folder_path = self.create_folder(
            prefix=f"instagram_reels_{media_info.author_username}",
            content_id=shortcode,
            title=title,
        )

        print_progress(f"📁 Папка: {folder_path}", "")

        # Скачиваем видео
        video_path = self._download_video(media_info, folder_path)
        print_progress(f"✅ Видео скачано: {video_path.name}", "")

        # Сохраняем описание
        description_file = self.save_description(
            folder_path=folder_path, description=self._format_description(media_info)
        )

        # Скачиваем комментарии если нужно
        comments_file = None
        if self.settings.download_comments:
            print_progress("💬 Скачивание комментариев...", "")
            comments = self._download_comments(media_info.media_id)
            if comments:
                comments_file = self.save_comments(folder_path, comments)
                print_progress(f"✅ Комментариев: {len(comments)}", "")

        return InstagramReelsResult(
            source=ContentSource.INSTAGRAM,
            content_type=InstagramContentType.REELS,
            url=url,
            content_id=shortcode,
            folder_path=folder_path,
            media_files=[video_path],
            description_file=description_file,
            comments_file=comments_file,
            author=media_info.author_username,
            likes=media_info.like_count,
            comments_count=media_info.comment_count,
            views=media_info.view_count,
            duration=int(media_info.duration),
        )

    def download_comments_only(self, url: str, folder_path: Path) -> Optional[Path]:
        """Скачивает только комментарии"""
        shortcode = extract_shortcode_instagram(url)
        if not shortcode:
            return None

        # Получаем media_id
        media_info = self.client.get_media_by_shortcode(shortcode)
        if not media_info:
            return None

        print_progress("💬 Скачивание комментариев...", "")
        comments = self._download_comments(media_info.media_id)
        if comments:
            comments_file = self.save_comments(folder_path, comments)
            print_progress(f"✅ Комментариев: {len(comments)}", "")
            return comments_file
        return None

    def _download_video(self, media_info: MediaInfo, folder_path: Path) -> Path:
        """
        Скачивает видео Reels

        Args:
            media_info: Информация о медиа
            folder_path: Папка для сохранения

        Returns:
            Путь к видео файлу
        """
        if not media_info.video_url:
            raise ValueError("URL видео не найден в метаданных")

        video_path = folder_path / "reel.mp4"

        success = self.client.download_media(media_info.video_url, video_path)
        if not success:
            raise Exception("Не удалось скачать видео")

        return video_path

    def _download_comments(self, media_id: str) -> List[Dict]:
        """
        Скачивает комментарии к Reels через HikerAPI

        Args:
            media_id: ID медиа

        Returns:
            Список комментариев
        """
        try:
            raw_comments = self.client.get_media_comments(
                media_id, count=self.settings.max_comments
            )

            # Преобразуем в формат для save_comments
            comments = []
            for c in raw_comments:
                user = c.get("user", {})
                comments.append(
                    {
                        "author": user.get("username", "unknown"),
                        "text": c.get("text", ""),
                        "likes": c.get("comment_like_count", 0),
                        "date": c.get("created_at_utc", ""),
                    }
                )

            return comments
        except Exception as e:
            logger.warning(f"Не удалось загрузить комментарии: {e}")
            return []

    def _extract_title(self, media_info: MediaInfo) -> str:
        """Извлекает заголовок из описания"""
        caption = media_info.caption or ""
        if not caption:
            return "no_title"

        # Берем первые 50 символов
        title = caption[:50]
        return clean_filename(title)

    def _format_description(self, media_info: MediaInfo) -> str:
        """
        Форматирует описание в Markdown

        Args:
            media_info: Информация о медиа

        Returns:
            Markdown текст
        """
        lines = [
            "# Instagram Reels",
            "",
            f"**Автор:** @{media_info.author_username}",
            f"**Длительность:** {format_duration(int(media_info.duration))}",
            "",
            "## Статистика",
            "",
            f"- 👁️ Просмотры: {format_count(media_info.view_count)}",
            f"- ❤️ Лайки: {format_count(media_info.like_count)}",
            f"- 💬 Комментарии: {format_count(media_info.comment_count)}",
            "",
            "## Описание",
            "",
            media_info.caption or "Без описания",
        ]

        return "\n".join(lines)
