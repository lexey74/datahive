#!/usr/bin/env python3
"""
Тест Instagram Post Downloader

Проверяет работу скачивателя Instagram постов.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.modules import InstagramPostDownloader, DownloadSettings

def test_instagram_post():
    """Тестирует Instagram Post Downloader"""
    print("=" * 70)
    print("🧪 ТЕСТ: Instagram Post Downloader")
    print("=" * 70)
    print()
    
    # Настройки
    cookies_dir = Path('cookies')
    
    # Ищем Instagram cookies
    instagram_cookies = None
    if (cookies_dir / 'instagram_cookies.txt').exists():
        instagram_cookies = cookies_dir / 'instagram_cookies.txt'
    elif (cookies_dir / 'instagram.txt').exists():
        instagram_cookies = cookies_dir / 'instagram.txt'
    
    settings = DownloadSettings(
        download_video=True,
        download_comments=False,
        instagram_cookies=instagram_cookies,
        youtube_cookies=None
    )
    
    # Проверка cookies
    print("🍪 Проверка cookies:")
    if settings.instagram_cookies and settings.instagram_cookies.exists():
        print(f"   ✅ Instagram cookies найдены: {settings.instagram_cookies}")
    else:
        print(f"   ⚠️  Instagram cookies не найдены (может не скачать приватные посты)")
    print()
    
    # Создаем downloader
    downloader = InstagramPostDownloader(settings)
    
    # Тестовые URL
    test_urls = [
        "https://www.instagram.com/p/ABC123/",  # Пример
        "https://www.instagram.com/reel/XYZ789/",  # Не должен обработать
    ]
    
    print("🔍 Тест can_handle():")
    for url in test_urls:
        can_handle = downloader.can_handle(url)
        emoji = "✅" if can_handle else "❌"
        print(f"   {emoji} {url}: {can_handle}")
    print()
    
    # Запрашиваем URL у пользователя
    print("📝 Введите Instagram Post URL для теста:")
    print("   Пример: https://www.instagram.com/p/ABC123/")
    print("   Или нажмите Enter для пропуска")
    print()
    
    url = input("URL: ").strip()
    
    if not url:
        print("⏭️  Тест пропущен")
        return
    
    # Проверяем, что это Instagram Post
    if not downloader.can_handle(url):
        print(f"❌ Этот URL не обрабатывается InstagramPostDownloader")
        print(f"   Используйте URL вида: https://www.instagram.com/p/...")
        return
    
    print()
    print("⬇️  Начинаем скачивание...")
    print()
    
    try:
        result = downloader.download(url)
        
        print()
        print("=" * 70)
        print("✅ УСПЕШНО")
        print("=" * 70)
        print(f"📍 Источник: {result.source.value}")
        print(f"📌 Тип: {result.content_type.value}")
        print(f"🆔 ID: {result.content_id}")
        print(f"📂 Папка: {result.folder_path}")
        print(f"👤 Автор: {result.author}")
        print(f"❤️  Лайки: {result.likes:,}")
        print(f"💬 Комментарии: {result.comments_count:,}")
        print()
        print(f"📦 Файлы ({len(result.media_files)}):")
        for f in result.media_files:
            size = f.stat().st_size / (1024 * 1024)
            print(f"   - {f.name} ({size:.1f} MB)")
        print()
        
        if result.description_file and result.description_file.exists():
            print(f"📄 Описание: {result.description_file}")
        
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ОШИБКА")
        print("=" * 70)
        print(f"{e}")
        print()
        import traceback
        traceback.print_exc()
        print("=" * 70)

if __name__ == "__main__":
    test_instagram_post()
