#!/usr/bin/env python3
"""
Тест YouTube Grabber
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.youtube_grabber import YouTubeGrabber


def test_youtube_grabber():
    """Тест загрузки с YouTube"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              YouTube Grabber Test                         ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Тестовое видео (короткое для быстрого теста)
    test_url = input("Введите YouTube URL (или Enter для теста): ").strip()
    
    if not test_url:
        # Тестовое видео по умолчанию
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        print(f"📺 Используем тестовое видео: {test_url}\n")
    
    # Создаем grabber
    grabber = YouTubeGrabber(output_dir=Path('temp'))
    
    try:
        # Сначала только метаданные
        print("\n" + "="*60)
        print("📊 ТЕСТ 1: Метаданные")
        print("="*60 + "\n")
        
        metadata = grabber.get_metadata(test_url)
        if metadata:
            print(f"✅ Название: {metadata.get('title', 'Unknown')}")
            print(f"✅ Автор: {metadata.get('uploader', 'Unknown')}")
            print(f"✅ Длительность: {metadata.get('duration', 0)} сек")
            print(f"✅ Просмотры: {metadata.get('view_count', 0):,}")
            print(f"✅ Лайки: {metadata.get('like_count', 0):,}")
            print(f"✅ Комментарии: {metadata.get('comment_count', 0):,}")
        
        # Спрашиваем про полную загрузку
        print("\n" + "="*60)
        full_download = input("Загрузить видео и аудио? (y/n): ").strip().lower()
        
        if full_download == 'y':
            print("\n" + "="*60)
            print("📥 ТЕСТ 2: Полная загрузка")
            print("="*60 + "\n")
            
            content = grabber.grab(
                test_url,
                download_video=True,
                download_audio=True
            )
            
            if content:
                print("\n" + "="*60)
                print("📊 РЕЗУЛЬТАТЫ")
                print("="*60)
                print(f"\n📺 Видео: {content.title}")
                print(f"👤 Автор: {content.author}")
                print(f"⏱️  Длительность: {content.duration} сек")
                print(f"👁️  Просмотры: {content.view_count:,}")
                print(f"❤️  Лайки: {content.like_count:,}")
                
                if content.video_path:
                    print(f"\n✅ Видео: {content.video_path.name}")
                if content.audio_path:
                    print(f"✅ Аудио: {content.audio_path.name}")
                if content.thumbnail_path:
                    print(f"✅ Thumbnail: {content.thumbnail_path.name}")
                
                print(f"\n💬 Комментарии: {len(content.comments)}")
                if content.comments:
                    print("\n📝 Первые 3 комментария:")
                    for i, comment in enumerate(content.comments[:3], 1):
                        print(f"\n{i}. {comment['author']}")
                        print(f"   {comment['text'][:100]}...")
                        print(f"   ❤️  {comment['likes']} likes")
                
                print("\n" + "="*60)
                print("✅ Тест завершён успешно!")
                print("="*60)
            else:
                print("❌ Ошибка загрузки контента")
        else:
            print("\n✅ Тест метаданных завершён")
        
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_youtube_grabber()
