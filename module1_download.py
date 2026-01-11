#!/usr/bin/env python3
"""
Модуль 1: Загрузка контента (Refactored - Modular Architecture)

Скачивает контент из Instagram и YouTube.
Использует модульную архитектуру с отдельными скачивателями для каждого типа контента.

Архитектура:
- ContentRouter: маршрутизация к нужному скачивателю
- InstagramPostDownloader: посты Instagram
- InstagramReelsDownloader: reels Instagram
- YouTubeVideoDownloader: видео YouTube (с обходом блокировок)
- YouTubeShortsDownloader: shorts YouTube
"""
from pathlib import Path
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.content_router import ContentRouter
from src.modules.downloader_base import DownloadSettings


def main():
    """Точка входа"""
    print("\n" + "="*70)
    print("📥 МОДУЛЬ 1: ЗАГРУЗКА КОНТЕНТА (Modular Architecture)")
    print("="*70)
    print()
    print("Поддерживаемые источники:")
    print("  📸 Instagram:")
    print("     - Posts (фото + текст)")
    print("     - Carousels (множество фото)")
    print("     - Reels (вертикальное видео)")
    print("  🎬 YouTube:")
    print("     - Videos (обычные видео)")
    print("     - Shorts (вертикальное видео)")
    print()
    print("Возможности:")
    print("  ✅ Автоматическое определение типа контента")
    print("  ✅ Обход блокировок YouTube (rate limiting, retry, rotation)")
    print("  ✅ Множественные YouTube cookies (автоматическая ротация)")
    print("  ✅ Скачивание комментариев (опционально)")
    print("  ✅ Скачивание субтитров YouTube")
    print()
    print("Результат:")
    print("  📁 downloads/platform_author_ID_title/")
    print("  📄 description.md (описание + статистика)")
    print("  🖼️  media files (jpg/mp4/webp)")
    print("  💬 comments.md (если включено)")
    print()
    print("="*70)
    print()
    
    # Настройки
    cookies_dir = Path('cookies')
    
    # Ищем Instagram cookies
    instagram_cookies = None
    if (cookies_dir / 'instagram_cookies.txt').exists():
        instagram_cookies = cookies_dir / 'instagram_cookies.txt'
    elif (cookies_dir / 'instagram.txt').exists():
        instagram_cookies = cookies_dir / 'instagram.txt'
    
    # Проверяем наличие YouTube cookies
    youtube_cookies_files = list(cookies_dir.glob('youtube_cookies*.txt'))
    youtube_cookies_dir = cookies_dir if youtube_cookies_files else None
    
    settings = DownloadSettings(
        download_video=True,
        download_comments=False,  # По умолчанию выключено
        video_quality='best',
        max_comments=100,
        instagram_cookies=instagram_cookies,
        youtube_cookies_dir=youtube_cookies_dir
    )
    
    # Создаем роутер
    router = ContentRouter(settings)
    
    # Показываем статус cookies
    print("🍪 Cookies:")
    if settings.instagram_cookies:
        print(f"   ✅ Instagram: {settings.instagram_cookies.name}")
    else:
        print(f"   ⚠️  Instagram: не найдено")
        print(f"      Создайте: cookies/instagram_cookies.txt")
    
    if youtube_cookies_files:
        print(f"   ✅ YouTube: {len(youtube_cookies_files)} файлов (ротация)")
        for f in youtube_cookies_files:
            print(f"      - {f.name}")
    else:
        print(f"   ⚠️  YouTube: не найдено")
        print(f"      Создайте: cookies/youtube_cookies1.txt, youtube_cookies2.txt, ...")
    
    print()
    print("💡 Для добавления cookies:")
    print("   - Установите расширение Get cookies.txt")
    print("   - Экспортируйте cookies в cookies/instagram.txt или cookies/youtube.txt")
    print()
    print("="*70)
    print()
    
    # Основной цикл
    while True:
        try:
            # Запрашиваем URL
            url = input("🔗 Введите URL (или 'q' для выхода, 'comments' для переключения комментариев): ").strip()
            
            if not url:
                print("⚠️  URL не может быть пустым")
                continue
            
            if url.lower() in ['q', 'quit', 'exit']:
                print("\n👋 Выход...")
                break
            
            # Переключение комментариев
            if url.lower() in ['comments', 'c']:
                settings.download_comments = not settings.download_comments
                status = "включены" if settings.download_comments else "выключены"
                print(f"💬 Комментарии {status}")
                continue
            
            # Проверяем формат URL
            if not url.startswith(('http://', 'https://')):
                print("❌ Неверный формат URL. Должен начинаться с http:// или https://")
                continue
            
            # Проверяем поддержку URL
            if not router.is_supported(url):
                print(f"❌ URL не поддерживается: {url}")
                print()
                print("Поддерживаемые форматы:")
                print("  Instagram: instagram.com/p/..., instagram.com/reel/...")
                print("  YouTube: youtube.com/watch?v=..., youtube.com/shorts/..., youtu.be/...")
                continue
            
            # Показываем информацию о типе контента
            info = router.get_downloader_info(url)
            print()
            print(f"🎯 Платформа: {info['platform']}")
            print(f"📌 Тип: {info['content_type']}")
            print(f"🔧 Скачиватель: {info['downloader']}")
            print()
            
            # Скачиваем
            result = router.download(url)
            
            if result:
                print("\n" + "="*70)
                print("✅ УСПЕШНО ЗАГРУЖЕНО")
                print("="*70)
                print(f"📍 Источник: {result.source.value.upper()}")
                # content_type может быть строкой или Enum
                content_type_str = result.content_type.value if hasattr(result.content_type, 'value') else result.content_type
                print(f"📌 Тип: {content_type_str.upper()}")
                print(f"🆔 ID: {result.content_id}")
                print(f"📂 Папка: {result.folder_path.name}")
                print(f"🖼️  Медиа файлов: {len(result.media_files)}")
                
                # Дополнительная статистика по типу
                if hasattr(result, 'views'):
                    from src.modules.downloader_utils import format_count
                    print(f"�️  Просмотры: {format_count(result.views)}")
                    print(f"❤️  Лайки: {format_count(result.likes)}")
                
                if hasattr(result, 'comments_count') and result.comments_count:
                    print(f"💬 Комментариев: {format_count(result.comments_count)}")
                
                print()
                print("📂 Содержимое папки:")
                import os
                for file in sorted(os.listdir(result.folder_path)):
                    file_path = result.folder_path / file
                    if file_path.is_file():
                        size = file_path.stat().st_size / 1024
                        if size > 1024:
                            size_str = f"{size/1024:.1f} MB"
                        else:
                            size_str = f"{size:.1f} KB"
                        print(f"   - {file} ({size_str})")
                
                print()
                print("💡 Следующие шаги:")
                print("   1. Транскрибация: python module2_transcribe.py")
                print("   2. AI анализ: python module3_analyze.py")
            else:
                print("\n❌ Загрузка не удалась")
                print("💡 Возможные причины:")
                print("   - Требуется обновить cookies (YouTube/Instagram)")
                print("   - URL недоступен или приватный")
                print("   - Проблемы с сетью")
            
            print("\n" + "="*70)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем. Выход...")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("\n" + "="*70)
    print("📊 СТАТИСТИКА")
    print("="*70)
    
    # Показываем статистику
    downloads_dir = Path('downloads')
    if downloads_dir.exists():
        folders = list(downloads_dir.iterdir())
        if folders:
            print(f"📁 Всего папок: {len(folders)}")
            
            youtube_count = sum(1 for f in folders if f.name.startswith('youtube_'))
            instagram_count = sum(1 for f in folders if f.name.startswith('instagram_'))
            
            print(f"🎬 YouTube: {youtube_count}")
            print(f"📸 Instagram: {instagram_count}")
        else:
            print("📁 Папок нет")
    
    print("="*70)
    print()


if __name__ == "__main__":
    main()
