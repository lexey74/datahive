"""
Instagram Post Downloader

Скачивает посты Instagram (фото, карусели, видео).
Использует gallery-dl для получения медиа.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    InstagramContentType,
    InstagramPostResult,
    DownloadSettings
)
from .downloader_utils import (
    clean_filename,
    extract_shortcode_instagram,
    print_progress,
    get_file_size_mb
)


def get_gallery_dl_command():
    """Возвращает правильную команду gallery-dl"""
    # Проверяем, запущены ли мы из venv
    venv_path = Path(sys.prefix)
    gallery_dl_venv = venv_path / 'bin' / 'gallery-dl'
    
    if gallery_dl_venv.exists():
        return str(gallery_dl_venv)
    
    # Иначе используем системную команду
    return 'gallery-dl'


class InstagramPostDownloader(BaseDownloader):
    """
    Скачивает посты Instagram
    
    Поддерживает:
    - Одиночные фото
    - Карусели (множество фото/видео)
    - Посты с видео
    """
    
    def __init__(self, settings: DownloadSettings):
        super().__init__(settings)
        
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        return '/p/' in url.lower() and 'instagram.com' in url.lower()
    
    def download(self, url: str) -> InstagramPostResult:
        """
        Скачивает Instagram пост
        
        Args:
            url: URL поста
            
        Returns:
            InstagramPostResult с результатами
            
        Raises:
            Exception: При ошибке скачивания
        """
        print_progress(f"🔍 Анализ поста: {url}")
        
        # Извлекаем shortcode
        shortcode = extract_shortcode_instagram(url)
        if not shortcode:
            raise ValueError(f"Не удалось извлечь shortcode из URL: {url}")
        
        # Получаем метаданные
        metadata = self._get_metadata(url)
        
        # Определяем тип контента
        is_carousel = len(metadata.get('media', [])) > 1
        content_type = InstagramContentType.CAROUSEL if is_carousel else InstagramContentType.POST
        
        # Создаем папку
        author = metadata.get('author', 'unknown')
        title = self._extract_title(metadata)
        folder_path = self.create_folder(
            prefix=f"instagram_post_{author}",
            content_id=shortcode,
            title=title
        )
        
        print_progress(f"📁 Папка: {folder_path}", "")
        
        # Скачиваем медиа
        media_files = self._download_media(url, folder_path)
        print_progress(f"✅ Скачано файлов: {len(media_files)}", "")
        
        # Сохраняем описание
        description_file = self.save_description(
            folder_path=folder_path,
            description=self._format_description(metadata)
        )
        
        # Скачиваем комментарии если нужно
        comments_file = None
        if self.settings.download_comments:
            print_progress("💬 Скачивание комментариев...", "")
            comments = self._download_comments(shortcode)
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
            author=author,
            likes=metadata.get('likes', 0),
            comments_count=metadata.get('comments', 0),
            post_date=metadata.get('date')
        )
    
    def _get_metadata(self, url: str) -> Dict:
        """
        Получает метаданные поста через gallery-dl
        
        Args:
            url: URL поста
            
        Returns:
            Словарь с метаданными
        """
        try:
            cmd = [
                get_gallery_dl_command(),
                '--dump-json',
                '--no-download',
            ]
            
            # Добавляем cookies если есть
            if self.settings.instagram_cookies and self.settings.instagram_cookies.exists():
                cmd.extend(['--cookies', str(self.settings.instagram_cookies)])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Проверяем ошибку авторизации
            if 'login' in result.stdout.lower() or ('"error"' in result.stdout and 'AbortExtraction' in result.stdout):
                raise Exception(
                    "Instagram требует авторизацию. "
                    "Добавьте cookies в cookies/instagram_cookies.txt"
                )
            
            # gallery-dl возвращает JSON массив с разными элементами
            # Нам нужны только dict объекты с метаданными
            import ast
            data = json.loads(result.stdout)
            
            # Извлекаем объекты метаданных (это dict, не списки)
            metadata_list = []
            for item in data:
                if isinstance(item, list) and len(item) >= 2:
                    # Элемент вида [код, данные]
                    if isinstance(item[1], dict) and 'post_id' in item[1]:
                        metadata_list.append(item[1])
            
            if not metadata_list:
                raise ValueError("Не удалось получить метаданные")
            
            # Объединяем данные
            first_item = metadata_list[0]
            
            return {
                'author': first_item.get('username', 'unknown'),
                'title': first_item.get('description', ''),
                'likes': first_item.get('likes', 0),
                'comments': first_item.get('comments', 0),
                'date': first_item.get('date'),
                'media': metadata_list,
                'is_video': first_item.get('typename') == 'GraphVideo'
            }
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Ошибка gallery-dl: {e.stderr}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON: {e}")
    
    def _download_media(self, url: str, folder_path: Path) -> List[Path]:
        """
        Скачивает медиа файлы
        
        Args:
            url: URL поста
            folder_path: Папка для сохранения
            
        Returns:
            Список путей к файлам
        """
        try:
            cmd = [
                get_gallery_dl_command(),
                '--directory', str(folder_path),
                '--filename', '{num:>02}_{filename}.{extension}',
            ]
            
            # Добавляем cookies
            if self.settings.instagram_cookies and self.settings.instagram_cookies.exists():
                cmd.extend(['--cookies', str(self.settings.instagram_cookies)])
            
            cmd.append(url)
            
            # Выполняем
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Собираем скачанные файлы
            media_files = []
            for ext in ['jpg', 'jpeg', 'png', 'mp4', 'webp']:
                media_files.extend(folder_path.glob(f"*.{ext}"))
            
            return sorted(media_files)
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Ошибка скачивания: {e.stderr.decode()}")
    
    def _download_comments(self, shortcode: str) -> List[Dict]:
        """
        Скачивает комментарии к посту
        
        Args:
            shortcode: Shortcode поста
            
        Returns:
            Список комментариев
        """
        # TODO: Реализовать через API или scraping
        # Пока заглушка
        return []
    
    def _extract_title(self, metadata: Dict) -> str:
        """Извлекает заголовок из описания"""
        description = metadata.get('title', '')
        if not description:
            return 'no_title'
        
        # Берем первые 50 символов
        title = description[:50]
        return clean_filename(title)
    
    def _format_description(self, metadata: Dict) -> str:
        """
        Форматирует описание в Markdown
        
        Args:
            metadata: Метаданные
            
        Returns:
            Markdown текст
        """
        lines = [
            f"# Instagram Post",
            f"",
            f"**Автор:** @{metadata.get('author', 'unknown')}",
            f"**Дата:** {metadata.get('date', 'unknown')}",
            f"**Лайки:** {metadata.get('likes', 0):,}",
            f"**Комментарии:** {metadata.get('comments', 0):,}",
            f"",
            f"## Описание",
            f"",
            metadata.get('title', 'Без описания'),
            f"",
        ]
        
        # Добавляем инфо о медиа
        media = metadata.get('media', [])
        if len(media) > 1:
            lines.append(f"## Медиа файлы: {len(media)}")
            lines.append("")
            for i, item in enumerate(media, 1):
                typename = item.get('typename', 'unknown')
                lines.append(f"{i}. {typename}")
        
        return '\n'.join(lines)
