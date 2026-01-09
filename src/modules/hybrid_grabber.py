"""
HybridGrabber - Парсинг Instagram через yt-dlp + instagrapi
"""
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
import re


@dataclass
class InstagramContent:
    """Структура данных Instagram поста"""
    url: str
    media_path: Optional[Path] = None
    caption: str = ""
    author: str = ""
    date: str = ""
    comments: List[str] = None
    media_type: str = "unknown"  # video, image, carousel
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class HybridGrabber:
    """Гибридный парсер Instagram контента"""
    
    def __init__(self, output_dir: Path, cookies_file: Path = None):
        """
        Инициализация grabber
        
        Args:
            output_dir: Директория для сохранения медиа
            cookies_file: Путь к cookies.txt для yt-dlp
        """
        self.output_dir = output_dir
        self.cookies_file = cookies_file
        self.instagrapi_client = None
    
    def grab(self, url: str) -> InstagramContent:
        """
        Основной метод: комбинированный парсинг
        
        Args:
            url: URL Instagram поста/рилса
            
        Returns:
            InstagramContent с медиа и метаданными
        """
        content = InstagramContent(url=url)
        
        # Шаг 1: Загрузка медиа через yt-dlp
        print("📥 Загрузка медиа через yt-dlp...")
        content.media_path = self._download_with_ytdlp(url)
        
        # Шаг 2: Парсинг метаданных через instagrapi
        print("📝 Получение метаданных через instagrapi...")
        try:
            metadata = self._fetch_with_instagrapi(url)
            content.caption = metadata.get('caption', '')
            content.author = metadata.get('author', '')
            content.date = metadata.get('date', '')
            content.comments = metadata.get('comments', [])
            content.media_type = metadata.get('media_type', 'unknown')
        except Exception as e:
            print(f"⚠️  Ошибка instagrapi: {e}")
            print("ℹ️  Продолжаем только с медиа...")
        
        return content
    
    def _download_with_ytdlp(self, url: str) -> Optional[Path]:
        """
        Загрузка медиафайла через yt-dlp
        
        Args:
            url: URL Instagram
            
        Returns:
            Путь к скачанному файлу или None
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Временное имя файла (будет переименовано позже)
        output_template = str(self.output_dir / "media.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-o", output_template,
        ]
        
        if self.cookies_file and self.cookies_file.exists():
            cmd.extend(["--cookies", str(self.cookies_file)])
        
        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Ищем созданный файл
            for file in self.output_dir.glob("media.*"):
                if file.suffix in ['.mp4', '.jpg', '.png', '.webp']:
                    return file
            
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка yt-dlp: {e.stderr}")
            return None
    
    def _fetch_with_instagrapi(self, url: str) -> Dict:
        """
        Парсинг метаданных через instagrapi
        
        Args:
            url: URL Instagram
            
        Returns:
            Словарь с метаданными
        """
        # TODO: Реализация через instagrapi
        # Требуется:
        # 1. Инициализация клиента с session.json
        # 2. Извлечение media_pk из URL
        # 3. Получение caption, author, date
        # 4. Загрузка комментариев (до 50)
        
        # Заглушка:
        return {
            'caption': '',
            'author': self._extract_username_from_url(url),
            'date': '',
            'comments': [],
            'media_type': 'unknown'
        }
    
    def _extract_username_from_url(self, url: str) -> str:
        """Извлечение username из URL"""
        match = re.search(r'instagram\.com/([^/]+)/', url)
        return match.group(1) if match else 'unknown'
    
    def setup_instagrapi(self, session_file: Path) -> None:
        """
        Настройка клиента instagrapi
        
        Args:
            session_file: Путь к session.json
        """
        try:
            from instagrapi import Client
            
            self.instagrapi_client = Client()
            
            if session_file.exists():
                self.instagrapi_client.load_settings(session_file)
                print("✅ Сессия Instagrapi загружена")
            else:
                print("⚠️  Файл session.json не найден")
                
        except ImportError:
            print("⚠️  Библиотека instagrapi не установлена")
        except Exception as e:
            print(f"⚠️  Ошибка настройки instagrapi: {e}")
