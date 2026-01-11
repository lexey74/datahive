#!/usr/bin/env python3
"""
Интерактивное сохранение Instagram cookies для Playwright
"""
from playwright.sync_api import sync_playwright
import json
from pathlib import Path


def save_cookies():
    """Интерактивное сохранение cookies"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        Instagram Cookies Saver (Playwright)               ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    output_file = Path("instagram_cookies.json")
    
    if output_file.exists():
        print(f"⚠️  Файл {output_file} уже существует!")
        overwrite = input("   Перезаписать? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("❌ Отменено")
            return
        print()
    
    print("🚀 Запуск браузера...")
    print()
    
    with sync_playwright() as p:
        # Запускаем браузер с видимым окном
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        print("🌐 Открываю Instagram...")
        page.goto("https://www.instagram.com", wait_until="networkidle")
        
        print()
        print("="*60)
        print("📋 ИНСТРУКЦИИ:")
        print("="*60)
        print()
        print("1️⃣  Войдите в свой Instagram аккаунт")
        print("2️⃣  Дождитесь полной загрузки главной страницы")
        print("3️⃣  Убедитесь, что вы видите свою ленту")
        print("4️⃣  Нажмите Enter в этом терминале")
        print()
        print("="*60)
        print()
        
        input("⏸️  Нажмите Enter после входа... ")
        
        print()
        print("💾 Сохранение cookies...")
        
        # Получаем все cookies
        cookies = context.cookies()
        
        # Фильтруем только Instagram cookies
        instagram_cookies = [
            c for c in cookies 
            if 'instagram.com' in c.get('domain', '')
        ]
        
        # Сохраняем в JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(instagram_cookies, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Cookies сохранены в: {output_file}")
        print(f"📊 Сохранено cookies: {len(instagram_cookies)}")
        
        # Проверяем наличие важных cookies
        cookie_names = {c['name'] for c in instagram_cookies}
        important_cookies = ['sessionid', 'csrftoken', 'ds_user_id']
        
        print()
        print("🔍 Проверка важных cookies:")
        for cookie_name in important_cookies:
            status = "✅" if cookie_name in cookie_names else "❌"
            print(f"   {status} {cookie_name}")
        
        missing = [c for c in important_cookies if c not in cookie_names]
        
        if missing:
            print()
            print(f"⚠️  Отсутствуют cookies: {', '.join(missing)}")
            print("💡 Убедитесь, что вы полностью вошли в аккаунт")
        else:
            print()
            print("✅ Все важные cookies присутствуют!")
            print()
            print("🎉 Готово! Теперь можете использовать парсер комментариев:")
            print("   python test_comments_scraper.py")
            print("   Выберите режим 2 (с cookies)")
        
        print()
        browser.close()


if __name__ == "__main__":
    try:
        save_cookies()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
