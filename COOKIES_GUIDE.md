# 🍪 Как получить Instagram Cookies для Playwright

## Способ 1: Экспорт из браузера (рекомендуется)

### Chrome/Edge:

1. **Установите расширение "EditThisCookie"** или "Get cookies.txt LOCALLY"
   - https://chrome.google.com/webstore

2. **Войдите в Instagram**
   - Откройте https://www.instagram.com
   - Войдите в свой аккаунт

3. **Экспортируйте cookies в JSON**
   - Кликните на иконку расширения
   - Выберите "Export" → "JSON"
   - Скопируйте содержимое

4. **Сохраните в файл**
   ```bash
   nano instagram_cookies.json
   # Вставьте скопированные cookies
   # Сохраните: Ctrl+O, Enter, Ctrl+X
   ```

### Firefox:

1. **Установите "Cookie Quick Manager"**
   - https://addons.mozilla.org/firefox

2. **Войдите в Instagram** и экспортируйте cookies аналогично

## Способ 2: Ручное создание через браузер

### Получение cookies через DevTools:

1. **Откройте DevTools** (F12) на instagram.com
2. **Перейдите на вкладку "Application"** (Chrome) или "Storage" (Firefox)
3. **Найдите "Cookies" → "https://www.instagram.com"**
4. **Скопируйте нужные cookies**

Минимально необходимые cookies:
- `sessionid` - самый важный!
- `csrftoken`
- `ds_user_id`

### Создайте JSON файл:

```json
[
  {
    "name": "sessionid",
    "value": "ВАШ_SESSION_ID",
    "domain": ".instagram.com",
    "path": "/",
    "httpOnly": true,
    "secure": true
  },
  {
    "name": "csrftoken",
    "value": "ВАШ_CSRF_TOKEN",
    "domain": ".instagram.com",
    "path": "/",
    "httpOnly": false,
    "secure": true
  },
  {
    "name": "ds_user_id",
    "value": "ВАШ_USER_ID",
    "domain": ".instagram.com",
    "path": "/",
    "httpOnly": false,
    "secure": true
  }
]
```

## Способ 3: Автоматический через Playwright (интерактивный)

Создайте скрипт для авторизации:

```python
from playwright.sync_api import sync_playwright
import json

def save_cookies():
    """Интерактивное сохранение cookies"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("🌐 Открываю Instagram...")
        page.goto("https://www.instagram.com")
        
        print("\n" + "="*60)
        print("ИНСТРУКЦИИ:")
        print("="*60)
        print("1. Войдите в свой аккаунт Instagram")
        print("2. Дождитесь полной загрузки страницы")
        print("3. Нажмите Enter в этом терминале")
        print("="*60)
        
        input("\n⏸️  Нажмите Enter после входа... ")
        
        # Сохраняем cookies
        cookies = context.cookies()
        with open('instagram_cookies.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        
        print("\n✅ Cookies сохранены в instagram_cookies.json")
        print(f"📊 Сохранено {len(cookies)} cookies")
        
        browser.close()

if __name__ == "__main__":
    save_cookies()
```

Запустите:
```bash
python save_cookies_script.py
```

## Проверка cookies

После создания файла проверьте:

```bash
# Проверка формата
python -c "import json; print('✅ JSON валиден' if json.load(open('instagram_cookies.json')) else '❌ Ошибка')"

# Проверка наличия sessionid
python -c "import json; cookies=json.load(open('instagram_cookies.json')); print('✅ sessionid найден' if any(c.get('name')=='sessionid' for c in cookies) else '❌ sessionid отсутствует')"
```

## Использование cookies в SecBrain

```bash
# Тест парсера с cookies
python test_comments_scraper.py
# Выберите режим 2

# Или в download.py
python src/download.py
# Ответьте 'y' на вопрос о комментариях
```

## ⚠️ Важно

1. **Безопасность**: Cookies дают полный доступ к вашему аккаунту
2. **Не публикуйте**: Держите `instagram_cookies.json` в `.gitignore`
3. **Обновление**: Cookies периодически истекают (обычно 90 дней)
4. **Приватность**: Не делитесь cookies файлом

## 🔄 Обновление cookies

Если cookies истекли:
1. Повторите процесс экспорта
2. Или используйте интерактивный скрипт (Способ 3)
3. Перезапустите парсер

## 🧪 Тестирование

После создания файла:

```bash
# Быстрый тест
python test_quick_scraper.py

# Полный тест
python test_comments_scraper.py
```

Ожидаемый результат:
```
✅ Успешно спарсено комментариев: 15+
```

## Troubleshooting

### "Cookies не найдены"
- Проверьте, что файл называется `instagram_cookies.json`
- Проверьте, что файл в корне проекта

### "sessionid отсутствует"
- Пересоздайте файл, убедитесь что включили sessionid
- Войдите в Instagram заново перед экспортом

### Комментарии все равно не загружаются
- Попробуйте режим 3 (visible browser) для проверки
- Проверьте, что аккаунт не заблокирован Instagram
- Увеличьте `scroll_duration` до 30 секунд
