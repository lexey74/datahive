"""
Utilities for content downloaders

Вспомогательные функции для всех подмодулей.
"""
import re
from pathlib import Path
from typing import Optional


def clean_filename(filename: str, max_length: int = 100) -> str:
    """
    Очищает имя файла от недопустимых символов
    
    Args:
        filename: Исходное имя
        max_length: Максимальная длина
        
    Returns:
        Очищенное имя
    """
    # Убираем недопустимые символы
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Заменяем множественные пробелы на один
    filename = re.sub(r'\s+', ' ', filename)
    
    # Убираем пробелы в начале и конце
    filename = filename.strip()
    
    # Заменяем пробелы на подчеркивания
    filename = filename.replace(' ', '_')
    
    # Ограничиваем длину
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    # Если пусто, используем fallback
    if not filename:
        filename = 'untitled'
    
    return filename


def extract_video_id_youtube(url: str) -> Optional[str]:
    """
    Извлекает video ID из YouTube URL
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID или None
    """
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def extract_shortcode_instagram(url: str) -> Optional[str]:
    """
    Извлекает shortcode из Instagram URL
    
    Args:
        url: Instagram URL
        
    Returns:
        Shortcode или None
    """
    patterns = [
        r'instagram\.com/p/([a-zA-Z0-9_-]+)',
        r'instagram\.com/reel/([a-zA-Z0-9_-]+)',
        r'instagram\.com/reels/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def is_youtube_short(url: str) -> bool:
    """
    Определяет, является ли URL YouTube Short
    
    Args:
        url: YouTube URL
        
    Returns:
        True если Short, False иначе
    """
    return '/shorts/' in url.lower()


def is_instagram_reel(url: str) -> bool:
    """
    Определяет, является ли URL Instagram Reel
    
    Args:
        url: Instagram URL
        
    Returns:
        True если Reel, False иначе
    """
    url_lower = url.lower()
    return '/reel/' in url_lower or '/reels/' in url_lower


def format_duration(seconds: int) -> str:
    """
    Форматирует длительность в читаемый вид
    
    Args:
        seconds: Секунды
        
    Returns:
        Строка вида "1:23:45" или "12:34"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_count(count: int) -> str:
    """
    Форматирует большие числа (1.2K, 3.4M)
    
    Args:
        count: Число
        
    Returns:
        Отформатированная строка
    """
    if count >= 1_000_000:
        return f"{count/1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count/1_000:.1f}K"
    else:
        return str(count)


def get_file_size_mb(file_path: Path) -> float:
    """
    Возвращает размер файла в MB
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Размер в MB
    """
    if not file_path.exists():
        return 0.0
    
    return file_path.stat().st_size / (1024 * 1024)


def print_progress(message: str, prefix: str = ""):
    """
    Выводит сообщение о прогрессе
    
    Args:
        message: Сообщение
        prefix: Префикс (emoji)
    """
    if prefix:
        print(f"{prefix} {message}")
    else:
        print(message)
