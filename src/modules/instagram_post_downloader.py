"""
Instagram Post Downloader (HikerAPI)

Скачивает посты Instagram (фото, карусели, видео) через HikerAPI SaaS.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    InstagramContentType,
    InstagramPostResult,
    DownloadSettings,
)
from .downloader_utils import (
    clean_filename,
    extract_shortcode_instagram,
    print_progress,
)
from .hikerapi_client import HikerAPIClient, MediaInfo

logger = logging.getLogger(__name__)


class InstagramPostDownloader(BaseDownloader):
    """
    Скачивает посты Instagram через HikerAPI

    Поддерживает:
    - Одиночные фото
    - Карусели (множество фото/видео)
    - Посты с видео

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
        return "/p/" in url.lower() and "instagram.com" in url.lower()

    def download(self, url: str) -> InstagramPostResult:
        """
        Скачивает Instagram пост

        Args:
            url: URL поста

        Returns:
            InstagramPostResult с результатами
        """
        print_progress(f"🔍 Анализ поста: {url}")

        # Извлекаем shortcode
        shortcode = extract_shortcode_instagram(url)
        if not shortcode:
            raise ValueError(f"Не удалось извлечь shortcode из URL: {url}")

        # Получаем метаданные через HikerAPI
        media_info = self.client.get_media_by_shortcode(shortcode)
        if not media_info:
            raise ValueError(f"Не удалось получить информацию о посте: {shortcode}")

        # Определяем тип контента
        is_carousel = media_info.media_type == "carousel"
        content_type = (
            InstagramContentType.CAROUSEL if is_carousel else InstagramContentType.POST
        )

        # Создаем папку
        title = self._extract_title(media_info)
        folder_path = self.create_folder(
            prefix=f"instagram_post_{media_info.author_username}",
            content_id=shortcode,
            title=title,
        )

        print_progress(f"📁 Папка: {folder_path}", "")

        # Скачиваем медиа
        media_files = self._download_media(media_info, folder_path)
        print_progress(f"✅ Скачано файлов: {len(media_files)}", "")

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

        return InstagramPostResult(
            source=ContentSource.INSTAGRAM,
            content_type=content_type,
            url=url,
            content_id=shortcode,
            folder_path=folder_path,
            media_files=media_files,
            description_file=description_file,
            comments_file=comments_file,
            author=media_info.author_username,
            likes=media_info.like_count,
            comments_count=media_info.comment_count,
            post_date=media_info.taken_at,
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

    def _download_media(self, media_info: MediaInfo, folder_path: Path) -> List[Path]:
        """
        Скачивает медиа файлы

        Args:
            media_info: Информация о медиа
            folder_path: Папка для сохранения

        Returns:
            Список путей к файлам
        """
        media_files = []

        # Скачиваем видео если есть
        if media_info.video_url:
            video_path = folder_path / "video.mp4"
            if self.client.download_media(media_info.video_url, video_path):
                media_files.append(video_path)

        # Скачиваем изображения
        for i, img_url in enumerate(media_info.image_urls):
            # Определяем расширение
            ext = "jpg"
            if ".mp4" in img_url or "video" in img_url:
                ext = "mp4"
            elif ".png" in img_url:
                ext = "png"
            elif ".webp" in img_url:
                ext = "webp"

            file_path = folder_path / f"{i + 1:02d}_media.{ext}"
            if self.client.download_media(img_url, file_path):
                media_files.append(file_path)

        if not media_files:
            raise Exception("Не удалось скачать ни одного медиа-файла")

        return sorted(media_files)

    def _download_comments(self, media_id: str) -> List[Dict]:
        """
        Скачивает комментарии к посту через HikerAPI

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
        type_label = "Carousel" if media_info.media_type == "carousel" else "Post"

        lines = [
            f"# Instagram {type_label}",
            "",
            f"**Автор:** @{media_info.author_username}",
            f"**Лайки:** {media_info.like_count:,}",
            f"**Комментарии:** {media_info.comment_count:,}",
            "",
            "## Описание",
            "",
            media_info.caption or "Без описания",
            "",
        ]

        # Добавляем инфо о медиа
        if media_info.image_urls:
            lines.append(f"## Медиа файлы: {len(media_info.image_urls)}")

        return "\n".join(lines)
