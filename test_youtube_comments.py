#!/usr/bin/env python3
"""
Тестирование YouTubeCommentsDownloader

Скачивает комментарии с тестовых YouTube видео и Shorts
"""
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.youtube_comments_downloader import YouTubeCommentsDownloader


def test_video_comments():
    """Тест скачивания комментариев с обычного видео"""
    print("\n" + "="*70)
    print("🎬 ТЕСТ: YouTube Video Comments")
    print("="*70)
    
    downloader = YouTubeCommentsDownloader()
    
    # Тестовое видео
    url = "https://youtu.be/K-entGTyNq4"
    output_file = Path("downloads/test_comments/video_comments.md")
    
    result = downloader.download_comments(
        url=url,
        output_file=output_file,
        max_comments=100,
        sort_by='popular'
    )
    
    if result['comments']:
        stats = downloader.get_comment_stats(result['comments'])
        
        print("\n📊 Статистика:")
        print(f"   📝 Всего: {stats['total']}")
        print(f"   💬 Основных: {stats['top_comments']}")
        print(f"   ↪️  Ответов: {stats['replies']}")
        print(f"   ❤️  Лайков: {stats['total_votes']:,}")
        print(f"   📈 Средние лайки: {stats['avg_votes']}")
        print(f"\n🏆 Топ комментарий: {stats['most_liked']['author']}")
        print(f"   Лайков: {stats['most_liked']['votes']:,}")
        print(f"   Текст: {stats['most_liked']['text']}")
        
        return True
    
    return False


def test_shorts_comments():
    """Тест скачивания комментариев с Shorts"""
    print("\n" + "="*70)
    print("🩳 ТЕСТ: YouTube Shorts Comments")
    print("="*70)
    
    downloader = YouTubeCommentsDownloader()
    
    # Тестовый Shorts
    url = "https://youtube.com/shorts/Umza3kEJtIw"
    output_file = Path("downloads/test_comments/shorts_comments.md")
    
    result = downloader.download_comments(
        url=url,
        output_file=output_file,
        max_comments=50,
        sort_by='popular'
    )
    
    if result['comments']:
        stats = downloader.get_comment_stats(result['comments'])
        
        print("\n📊 Статистика:")
        print(f"   📝 Всего: {stats['total']}")
        print(f"   💬 Основных: {stats['top_comments']}")
        print(f"   ↪️  Ответов: {stats['replies']}")
        print(f"   ❤️  Лайков: {stats['total_votes']:,}")
        print(f"   📈 Средние лайки: {stats['avg_votes']}")
        
        if stats['most_liked']:
            print(f"\n🏆 Топ комментарий: {stats['most_liked']['author']}")
            print(f"   Лайков: {stats['most_liked']['votes']:,}")
            print(f"   Текст: {stats['most_liked']['text']}")
        
        return True
    
    return False


def test_url_extraction():
    """Тест извлечения video ID из разных форматов URL"""
    print("\n" + "="*70)
    print("🔗 ТЕСТ: URL Extraction")
    print("="*70)
    
    downloader = YouTubeCommentsDownloader()
    
    test_urls = [
        ("https://youtube.com/watch?v=K-entGTyNq4", "K-entGTyNq4"),
        ("https://youtu.be/K-entGTyNq4", "K-entGTyNq4"),
        ("https://youtube.com/shorts/Umza3kEJtIw", "Umza3kEJtIw"),
        ("https://m.youtube.com/watch?v=K-entGTyNq4", "K-entGTyNq4"),
        ("https://youtube.com/embed/K-entGTyNq4", "K-entGTyNq4"),
    ]
    
    passed = 0
    failed = 0
    
    for url, expected_id in test_urls:
        video_id = downloader.extract_video_id(url)
        if video_id == expected_id:
            print(f"✅ {url[:50]}... → {video_id}")
            passed += 1
        else:
            print(f"❌ {url[:50]}... → {video_id} (ожидалось: {expected_id})")
            failed += 1
    
    print(f"\n📊 Результат: {passed} passed, {failed} failed")
    return failed == 0


def test_recent_sort():
    """Тест сортировки по времени"""
    print("\n" + "="*70)
    print("⏰ ТЕСТ: Recent Comments Sort")
    print("="*70)
    
    downloader = YouTubeCommentsDownloader()
    
    url = "https://youtu.be/K-entGTyNq4"
    output_file = Path("downloads/test_comments/recent_comments.md")
    
    result = downloader.download_comments(
        url=url,
        output_file=output_file,
        max_comments=20,
        sort_by='recent'  # Сортировка по времени
    )
    
    if result['comments']:
        print(f"\n✅ Загружено: {len(result['comments'])} свежих комментариев")
        print(f"📄 Сохранено в: {output_file}")
        return True
    
    return False


def main():
    """Запуск всех тестов"""
    print("\n" + "="*70)
    print("🧪 ТЕСТИРОВАНИЕ YOUTUBE COMMENTS DOWNLOADER")
    print("="*70)
    
    tests = [
        ("URL Extraction", test_url_extraction),
        ("Video Comments", test_video_comments),
        ("Shorts Comments", test_shorts_comments),
        ("Recent Sort", test_recent_sort),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n❌ ТЕСТ ПРОВАЛЕН: {name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ ОШИБКА В ТЕСТЕ {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Итоговый отчёт
    print("\n" + "="*70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("="*70)
    print(f"✅ Пройдено: {passed}/{len(tests)}")
    print(f"❌ Провалено: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print(f"\n⚠️  {failed} тест(ов) провалено")
    
    print("="*70)


if __name__ == "__main__":
    main()
