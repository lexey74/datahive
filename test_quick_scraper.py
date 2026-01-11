#!/usr/bin/env python3
"""
Быстрый тест парсера комментариев с разными постами
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.safe_comments import SafeCommentsScraper
import json

def test_quick():
    """Быстрый тест"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         Быстрый тест парсера комментариев                  ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Публичный популярный пост
    test_url = "https://www.instagram.com/reel/DTKyvv0jMux/"
    
    print(f"🔗 URL: {test_url}")
    print("⏳ Прокрутка: 20 секунд")
    print("👁️  Режим: headless\n")
    
    scraper = SafeCommentsScraper(headless=True)
    
    try:
        comments = scraper.scrape_comments(
            test_url,
            scroll_duration=20  # Увеличиваем до 20 секунд
        )
        
        print(f"\n📊 Результат: {len(comments)} комментариев\n")
        
        if comments:
            print("📝 Примеры комментариев:")
            print("-" * 60)
            for i, c in enumerate(comments[:3], 1):
                username = c.get('username', c.get('user', 'unknown'))
                text = c.get('text', '')[:80]
                likes = c.get('likes', 0)
                print(f"{i}. @{username}")
                print(f"   {text}")
                print(f"   ❤️  {likes} likes")
                print()
            
            # Сохраняем
            with open('test_quick_output.json', 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            print("💾 Сохранено в: test_quick_output.json")
        else:
            print("⚠️  Комментарии не найдены")
            print("\n💡 Возможные причины:")
            print("   - Instagram требует авторизацию для комментариев")
            print("   - Пост имеет ограниченный доступ")
            print("   - Нужно использовать cookies")
            
            print("\n🔧 Попробуйте:")
            print("   1. Создайте instagram_cookies.json с вашими cookies")
            print("   2. Запустите: python test_comments_scraper.py")
            print("   3. Выберите режим 2 (с cookies)")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quick()
