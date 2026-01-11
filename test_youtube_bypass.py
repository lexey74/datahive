#!/usr/bin/env python3
"""
Тест системы обхода блокировок YouTube
"""
from pathlib import Path
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.youtube_grabber_advanced import AdvancedYouTubeGrabber
from cookie_manager import CookieManager


def test_single_cookie():
    """Тест с одним cookies файлом"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Один cookies файл")
    print("="*60)
    
    cookies_file = Path('youtube_cookies.txt')
    if not cookies_file.exists():
        print("❌ Файл youtube_cookies.txt не найден")
        print("💡 Создайте cookies файл и повторите")
        return False
    
    grabber = AdvancedYouTubeGrabber(
        output_dir=Path('test_downloads'),
        cookies_files=[cookies_file],
        min_delay=2.0,
        max_delay=4.0
    )
    
    # Тестовое видео (короткое)
    test_url = "https://youtu.be/jNQXAC9IVRw"  # "Me at the zoo" - первое видео на YouTube
    
    metadata = grabber.get_metadata(test_url)
    if metadata:
        print(f"✅ Метаданные получены: {metadata['title']}")
        grabber.print_stats()
        return True
    else:
        print("❌ Не удалось получить метаданные")
        grabber.print_stats()
        return False


def test_multiple_cookies():
    """Тест с множественными cookies"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Множественные cookies (ротация)")
    print("="*60)
    
    # Загружаем cookies через Cookie Manager
    cookie_mgr = CookieManager()
    cookies_files = cookie_mgr.get_all_cookies()
    
    if len(cookies_files) < 2:
        print(f"⚠️  Найдено только {len(cookies_files)} cookies файлов")
        print("💡 Добавьте больше cookies для ротации:")
        print("   python cookie_manager.py add --file youtube_cookies_2.txt --name account2")
        
        if len(cookies_files) == 0:
            return False
    else:
        print(f"✅ Найдено {len(cookies_files)} cookies файлов")
    
    grabber = AdvancedYouTubeGrabber(
        output_dir=Path('test_downloads'),
        cookies_files=cookies_files,
        min_delay=3.0,
        max_delay=6.0
    )
    
    # Тестируем несколько видео для проверки ротации
    test_urls = [
        "https://youtu.be/jNQXAC9IVRw",  # Me at the zoo
        "https://youtu.be/dQw4w9WgXcQ",  # Rick Roll
    ]
    
    success_count = 0
    for url in test_urls:
        print(f"\n📊 Тестируем: {url}")
        metadata = grabber.get_metadata(url)
        if metadata:
            print(f"✅ Успех: {metadata['title']}")
            success_count += 1
        else:
            print(f"❌ Неудача: {url}")
    
    print(f"\n📈 Результат: {success_count}/{len(test_urls)} успешных")
    grabber.print_stats()
    
    return success_count > 0


def test_with_proxy():
    """Тест с прокси"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Прокси + cookies")
    print("="*60)
    
    proxies_file = Path('proxies.txt')
    if not proxies_file.exists():
        print("⚠️  Файл proxies.txt не найден")
        print("💡 Создайте файл с прокси для тестирования")
        return False
    
    # Проверяем, есть ли активные прокси
    with open(proxies_file) as f:
        proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not proxies:
        print("⚠️  Нет активных прокси в proxies.txt")
        print("💡 Добавьте прокси серверы для тестирования")
        return False
    
    print(f"✅ Найдено {len(proxies)} прокси")
    
    cookie_mgr = CookieManager()
    cookies_files = cookie_mgr.get_all_cookies()
    
    if not cookies_files:
        cookies_files = [Path('youtube_cookies.txt')]
    
    grabber = AdvancedYouTubeGrabber(
        output_dir=Path('test_downloads'),
        cookies_files=cookies_files,
        proxies_file=proxies_file,
        min_delay=2.0,
        max_delay=4.0
    )
    
    test_url = "https://youtu.be/jNQXAC9IVRw"
    
    metadata = grabber.get_metadata(test_url)
    if metadata:
        print(f"✅ Метаданные получены через прокси: {metadata['title']}")
        grabber.print_stats()
        return True
    else:
        print("❌ Не удалось получить метаданные через прокси")
        grabber.print_stats()
        return False


def test_download():
    """Тест загрузки видео"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Загрузка видео")
    print("="*60)
    
    cookie_mgr = CookieManager()
    cookies_files = cookie_mgr.get_all_cookies()
    
    if not cookies_files:
        cookies_files = [Path('youtube_cookies.txt')]
    
    grabber = AdvancedYouTubeGrabber(
        output_dir=Path('test_downloads'),
        cookies_files=cookies_files,
        min_delay=3.0,
        max_delay=5.0
    )
    
    # Короткое видео для быстрого теста
    test_url = "https://youtu.be/jNQXAC9IVRw"  # 18 секунд
    
    print("📥 Загружаем короткое видео (18 сек) для теста...")
    video_path = grabber.download_video(test_url, quality='worst', max_retries=3)
    
    if video_path and video_path.exists():
        print(f"✅ Видео загружено: {video_path}")
        print(f"   Размер: {video_path.stat().st_size / 1024:.1f} KB")
        grabber.print_stats()
        return True
    else:
        print("❌ Не удалось загрузить видео")
        grabber.print_stats()
        return False


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ОБХОДА БЛОКИРОВОК")
    print("="*60)
    
    tests = [
        ("Один cookies", test_single_cookie),
        ("Множественные cookies", test_multiple_cookies),
        ("Прокси", test_with_proxy),
        ("Загрузка видео", test_download),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except KeyboardInterrupt:
            print("\n\n⚠️  Тестирование прервано пользователем")
            break
        except Exception as e:
            print(f"\n❌ Ошибка в тесте '{name}': {e}")
            results.append((name, False))
    
    # Итоговый отчёт
    print("\n" + "="*60)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n📈 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 Все тесты успешно пройдены!")
    elif passed > 0:
        print(f"\n⚠️  Частичный успех: {passed} из {total}")
    else:
        print("\n❌ Все тесты провалены. Проверьте:")
        print("   1. Наличие актуальных cookies")
        print("   2. Подключение к интернету")
        print("   3. Настройки прокси (если используются)")
    
    print("\n💡 Рекомендации:")
    print("   - Для улучшения результатов добавьте больше cookies")
    print("   - Используйте прокси для массовых загрузок")
    print("   - Обновляйте cookies каждые 3-7 дней")
    
    # Статистика Cookie Manager
    print("\n" + "="*60)
    cookie_mgr = CookieManager()
    cookie_mgr.print_stats()


if __name__ == '__main__':
    main()
