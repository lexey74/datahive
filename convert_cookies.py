#!/usr/bin/env python3
"""
Конвертер cookies из формата Netscape (txt) в JSON для Playwright
"""
import json
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from datetime import datetime


def convert_cookies_txt_to_json(txt_file: str, json_file: str):
    """Конвертирует cookies из .txt в .json"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        Cookie Converter: Netscape → Playwright JSON       ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    txt_path = Path(txt_file)
    json_path = Path(json_file)
    
    if not txt_path.exists():
        print(f"❌ Файл не найден: {txt_file}")
        return False
    
    print(f"📖 Читаю cookies из: {txt_file}")
    
    # Читаем файл построчно
    cookies = []
    with open(txt_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Пропускаем комментарии и пустые строки
            if not line or line.startswith('#'):
                continue
            
            # Формат Netscape: domain flag path secure expiration name value
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            
            domain, flag, path, secure, expiration, name, value = parts[:7]
            
            # Конвертируем в формат Playwright
            cookie = {
                'name': name,
                'value': value,
                'domain': domain,
                'path': path,
                'expires': int(expiration) if expiration != '0' else -1,
                'httpOnly': False,  # Netscape формат не содержит эту информацию
                'secure': secure.upper() == 'TRUE',
                'sameSite': 'None' if secure.upper() == 'TRUE' else 'Lax'
            }
            
            cookies.append(cookie)
    
    if not cookies:
        print("⚠️  Cookies не найдены в файле")
        return False
    
    # Сохраняем в JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Конвертировано cookies: {len(cookies)}")
    print(f"💾 Сохранено в: {json_file}\n")
    
    # Проверяем важные cookies
    cookie_names = {c['name'] for c in cookies}
    important_cookies = ['sessionid', 'csrftoken', 'ds_user_id']
    
    print("🔍 Проверка важных cookies:")
    for cookie_name in important_cookies:
        status = "✅" if cookie_name in cookie_names else "❌"
        print(f"   {status} {cookie_name}")
    
    missing = [c for c in important_cookies if c not in cookie_names]
    if missing:
        print(f"\n⚠️  Отсутствуют: {', '.join(missing)}")
        print("💡 Убедитесь, что cookies актуальные")
    else:
        print("\n🎉 Все важные cookies присутствуют!")
    
    return True


if __name__ == "__main__":
    success = convert_cookies_txt_to_json(
        'instagram_cookies.txt',
        'instagram_cookies.json'
    )
    
    if success:
        print("\n" + "="*60)
        print("✅ Готово! Теперь можете тестировать парсер:")
        print("   python test_comments_scraper.py")
        print("   Выберите режим 2 (с cookies)")
        print("="*60)
