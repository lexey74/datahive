#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Playwright парсера комментариев
"""
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.safe_comments import SafeCommentsScraper


def test_scraper():
    """Тест парсера комментариев"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║       Тест Playwright парсера комментариев Instagram       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Тестовый URL (публичный пост с комментариями)
    test_url = "https://www.instagram.com/reel/DTKyvv0jMux/"
    
    print(f"🔗 Тестовый URL: {test_url}")
    print()
    
    # Варианты тестирования
    print("Выберите режим тестирования:")
    print("1. Без cookies (headless) - для публичных постов")
    print("2. С cookies (headless) - если есть instagram_cookies.json")
    print("3. С браузером (visible) - для ручного входа")
    print()
    
    choice = input("Ваш выбор (1/2/3): ").strip()
    
    if choice == "1":
        print("\n🚀 Запуск в headless режиме без cookies...")
        scraper = SafeCommentsScraper(headless=True)
        
    elif choice == "2":
        cookies_file = Path("instagram_cookies.json")
        if not cookies_file.exists():
            print("\n❌ Файл instagram_cookies.json не найден!")
            print("💡 Создайте файл или выберите другой режим")
            return
        
        print("\n🚀 Запуск в headless режиме с cookies...")
        scraper = SafeCommentsScraper(
            headless=True,
            cookies_file=str(cookies_file)
        )
        
    elif choice == "3":
        print("\n🚀 Запуск с видимым браузером...")
        print("💡 Войдите в Instagram вручную, если потребуется")
        scraper = SafeCommentsScraper(headless=False)
        
    else:
        print("❌ Неверный выбор")
        return
    
    try:
        print("\n" + "="*60)
        print("📥 Начинаю парсинг комментариев...")
        print("="*60)
        print()
        
        # Запускаем парсинг с увеличенным временем прокрутки
        comments = scraper.scrape_comments(
            test_url,
            scroll_duration=15  # 15 секунд прокрутки
        )
        
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ")
        print("="*60)
        
        if comments:
            print(f"\n✅ Успешно спарсено комментариев: {len(comments)}")
            print("\n" + "-"*60)
            print("📝 Первые 5 комментариев:")
            print("-"*60)
            
            for i, comment in enumerate(comments[:5], 1):
                print(f"\n{i}. Автор: {comment.get('username', 'unknown')}")
                print(f"   Текст: {comment.get('text', '')[:100]}...")
                print(f"   Лайки: {comment.get('likes', 0)}")
                if comment.get('replies'):
                    print(f"   Ответов: {len(comment['replies'])}")
            
            print("\n" + "-"*60)
            print(f"💾 Всего комментариев: {len(comments)}")
            
            # Статистика
            total_likes = sum(c.get('likes', 0) for c in comments)
            total_replies = sum(len(c.get('replies', [])) for c in comments)
            
            print(f"❤️  Всего лайков: {total_likes}")
            print(f"💬 Всего ответов: {total_replies}")
            
            # Сохраняем в файл для проверки
            import json
            output_file = Path("test_comments_output.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Комментарии сохранены в: {output_file}")
            
        else:
            print("\n⚠️  Комментарии не найдены")
            print("\n💡 Возможные причины:")
            print("   - Пост без комментариев")
            print("   - Требуется авторизация")
            print("   - Нужно больше времени на прокрутку")
            print("   - Instagram заблокировал запрос")
        
        print("\n" + "="*60)
        print("✅ Тест завершён")
        print("="*60)
        
    except Exception as e:
        print("\n❌ Ошибка при парсинге:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print("\n🔍 Детали:")
        traceback.print_exc()
    
    finally:
        print("\n👋 Закрытие браузера...")


if __name__ == "__main__":
    test_scraper()
