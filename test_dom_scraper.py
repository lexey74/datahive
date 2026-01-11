#!/usr/bin/env python3
"""
Простой парсер комментариев через DOM (без GraphQL перехвата)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from playwright.sync_api import sync_playwright
import json
import time
import random


def scrape_comments_simple(post_url: str, cookies_file: str = None):
    """Простой парсер через DOM"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Простой парсер комментариев (через DOM)               ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    print(f"🔗 URL: {post_url}")
    print("👁️  Режим: headless")
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Загружаем cookies
        if cookies_file and Path(cookies_file).exists():
            cookies = json.load(open(cookies_file))
            context.add_cookies(cookies)
            print("✅ Cookies загружены\n")
        
        page = context.new_page()
        
        print("🔗 Загрузка страницы...")
        try:
            page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
            print("✅ Страница загружена\n")
        except Exception as e:
            print(f"⚠️  {e}\n")
        
        # Ждем загрузки контента
        time.sleep(5)
        
        print("🔍 Поиск комментариев в DOM...")
        
        # Пробуем разные селекторы для комментариев
        selectors_to_try = [
            'article[role="presentation"] ul li',  # Список комментариев
            'div[role="button"] span',  # Текст комментариев
            'ul._a9z6._a9za',  # Instagram список
            'div._a9zs',  # Контейнер комментария
        ]
        
        all_comments = []
        
        for selector in selectors_to_try:
            try:
                elements = page.query_selector_all(selector)
                print(f"   Селектор '{selector}': найдено {len(elements)} элементов")
                
                if elements:
                    for elem in elements[:10]:  # Первые 10 для проверки
                        try:
                            text = elem.inner_text().strip()
                            if text and len(text) > 5:  # Игнорируем короткие
                                all_comments.append({
                                    'selector': selector,
                                    'text': text[:100]
                                })
                        except:
                            pass
            except Exception as e:
                print(f"   Ошибка с селектором: {e}")
        
        print(f"\n📊 Найдено текстовых элементов: {len(all_comments)}\n")
        
        if all_comments:
            print("📝 Примеры:")
            for i, comment in enumerate(all_comments[:5], 1):
                print(f"{i}. [{comment['selector']}]")
                print(f"   {comment['text']}")
                print()
            
            # Сохраняем
            with open('test_dom_output.json', 'w', encoding='utf-8') as f:
                json.dump(all_comments, f, ensure_ascii=False, indent=2)
            print("💾 Сохранено: test_dom_output.json")
        else:
            print("❌ Комментарии не найдены")
            print("\n💡 Попробуйте:")
            print("   - Проверить, что cookies актуальные")
            print("   - Использовать другой пост с известными комментариями")
            
            # Сохраняем HTML для анализа
            html = page.content()
            with open('page_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("   - Сохранен page_debug.html для анализа")
        
        browser.close()


if __name__ == "__main__":
    scrape_comments_simple(
        "https://www.instagram.com/reel/DTKyvv0jMux/",
        "instagram_cookies.json"
    )
