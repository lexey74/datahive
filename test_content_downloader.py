#!/usr/bin/env python3
"""
Тест модуля ContentDownloader
"""
from pathlib import Path
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.content_downloader import (
    ContentDownloader,
    ContentSource,
    InstagramContentType,
    YouTubeContentType
)


def test_url_detection():
    """Тест определения источника и типа контента"""
    downloader = ContentDownloader()
    
    print("\n" + "="*70)
    print("ТЕСТ 1: Определение источника и типа контента")
    print("="*70)
    
    # Instagram примеры
    test_cases = [
        # Instagram
        ("https://www.instagram.com/p/ABC123/", ContentSource.INSTAGRAM, InstagramContentType.POST),
        ("https://www.instagram.com/reel/XYZ456/", ContentSource.INSTAGRAM, InstagramContentType.REELS),
        ("https://instagram.com/reels/TEST123/", ContentSource.INSTAGRAM, InstagramContentType.REELS),
        
        # YouTube
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ContentSource.YOUTUBE, YouTubeContentType.VIDEO),
        ("https://youtu.be/dQw4w9WgXcQ", ContentSource.YOUTUBE, YouTubeContentType.VIDEO),
        ("https://www.youtube.com/shorts/abc123", ContentSource.YOUTUBE, YouTubeContentType.SHORT),
    ]
    
    for url, expected_source, expected_type in test_cases:
        source = downloader.detect_source(url)
        
        if source == ContentSource.INSTAGRAM:
            content_type = downloader.detect_instagram_type(url)
        elif source == ContentSource.YOUTUBE:
            content_type = downloader.detect_youtube_type(url)
        else:
            content_type = None
        
        status = "✅" if source == expected_source and content_type == expected_type else "❌"
        print(f"\n{status} {url}")
        print(f"   Источник: {source.value} (ожидалось: {expected_source.value})")
        if content_type:
            print(f"   Тип: {content_type.value} (ожидалось: {expected_type.value})")


def test_id_extraction():
    """Тест извлечения ID"""
    downloader = ContentDownloader()
    
    print("\n" + "="*70)
    print("ТЕСТ 2: Извлечение ID из URL")
    print("="*70)
    
    # Instagram
    ig_urls = [
        ("https://www.instagram.com/p/ABC123xyz/", "ABC123xyz"),
        ("https://www.instagram.com/reel/XYZ-456_abc/", "XYZ-456_abc"),
    ]
    
    print("\n📸 Instagram ID:")
    for url, expected_id in ig_urls:
        extracted_id = downloader.extract_instagram_id(url)
        status = "✅" if extracted_id == expected_id else "❌"
        print(f"{status} {url}")
        print(f"   ID: {extracted_id} (ожидалось: {expected_id})")
    
    # YouTube
    yt_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abc12345678", "abc12345678"),
    ]
    
    print("\n🎬 YouTube ID:")
    for url, expected_id in yt_urls:
        extracted_id = downloader.extract_youtube_id(url)
        status = "✅" if extracted_id == expected_id else "❌"
        print(f"{status} {url}")
        print(f"   ID: {extracted_id} (ожидалось: {expected_id})")


def test_folder_creation():
    """Тест создания папок"""
    downloader = ContentDownloader(output_dir=Path("temp/test_downloads"))
    
    print("\n" + "="*70)
    print("ТЕСТ 3: Создание папок")
    print("="*70)
    
    test_cases = [
        ("Тестовое видео про программирование", "ABC123", ContentSource.INSTAGRAM),
        ("How to code in Python: Tutorial 2024", "dQw4w9WgXcQ", ContentSource.YOUTUBE),
        ("Видео с спец/символами?*<>:|", "TEST456", ContentSource.YOUTUBE),
    ]
    
    for title, content_id, source in test_cases:
        folder = downloader.create_folder(title, content_id, source)
        print(f"\n✅ {folder.name}")
        print(f"   Оригинал: {title}")


def test_real_download():
    """Тест реальной загрузки (опционально)"""
    print("\n" + "="*70)
    print("ТЕСТ 4: Реальная загрузка контента")
    print("="*70)
    
    print("\n⚠️  Реальная загрузка отключена в тесте")
    print("Для тестирования используйте:")
    print("\n  from src.modules.content_downloader import ContentDownloader")
    print("  downloader = ContentDownloader(output_dir=Path('downloads'))")
    print("  result = downloader.download('YOUR_URL')")


if __name__ == "__main__":
    print("\n🧪 ТЕСТИРОВАНИЕ CONTENT DOWNLOADER")
    print("="*70)
    
    try:
        test_url_detection()
        test_id_extraction()
        test_folder_creation()
        test_real_download()
        
        print("\n" + "="*70)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
