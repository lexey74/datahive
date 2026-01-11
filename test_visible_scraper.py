#!/usr/bin/env python3
"""
Отладочный тест с видимым браузером
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.safe_comments import SafeCommentsScraper
import json

def test_visible():
    """Тест с видимым браузером для отладки"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Отладка парсера (видимый браузер)                     ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    test_url = "https://www.instagram.com/reel/DTKyvv0jMux/"
    
    print(f"🔗 URL: {test_url}")
    print("👁️  Браузер: видимый (для отладки)")
    print("🍪 Cookies: instagram_cookies.json\n")
    
    cookies_file = Path("instagram_cookies.json")
    if not cookies_file.exists():
        print("❌ instagram_cookies.json не найден!")
        return
    
    scraper = SafeCommentsScraper(
        headless=False,  # Видимый браузер
        cookies_file=str(cookies_file)
    )
    
    try:
        print("🚀 Запуск...")
        print("💡 Наблюдайте за браузером для отладки")
        print()
        
        comments = scraper.scrape_comments(
            test_url,
            scroll_duration=20
        )
        
        print(f"\n📊 Результат: {len(comments)} комментариев\n")
        
        if comments:
            print("✅ Комментарии получены!")
            for i, c in enumerate(comments[:3], 1):
                print(f"{i}. {c.get('username', 'unknown')}: {c.get('text', '')[:50]}...")
            
            with open('test_visible_output.json', 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Сохранено: test_visible_output.json")
        else:
            print("⚠️  Комментарии не получены")
            print("\n💡 Проверьте:")
            print("   - Авторизованы ли вы в браузере?")
            print("   - Загрузилась ли страница полностью?")
            print("   - Есть ли комментарии на посте?")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_visible()
