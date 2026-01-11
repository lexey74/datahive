# YouTube Cookies для yt-dlp

YouTube теперь требует авторизацию для многих видео. Нужно экспортировать cookies из браузера.

## Быстрый способ (расширение для браузера)

### Шаг 1: Установите расширение
- **Chrome/Edge**: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- **Firefox**: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

### Шаг 2: Экспортируйте cookies
1. Откройте YouTube в браузере
2. Убедитесь, что вы залогинены
3. Нажмите на иконку расширения
4. Выберите "Export" или "Get cookies.txt"
5. Сохраните файл как `youtube_cookies.txt`

### Шаг 3: Загрузите на сервер
```bash
# На вашем компьютере
scp youtube_cookies.txt user@server:/home/lexey/projects/secbrain/

# Или используйте SFTP/WinSCP
```

### Шаг 4: Проверьте
```bash
cd /home/lexey/projects/secbrain
head -5 youtube_cookies.txt
```

Должно быть что-то вроде:
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	CONSENT	YES+
.youtube.com	TRUE	/	FALSE	1234567890	VISITOR_INFO1_LIVE	xxxxx
```

## Альтернатива: Ручной экспорт через DevTools

Если расширение не работает:

1. Откройте YouTube
2. Нажмите F12 (Developer Tools)
3. Перейдите в Console
4. Вставьте этот код:

```javascript
copy(document.cookie.split('; ').map(c => {
    const [name, ...v] = c.split('=');
    return `.youtube.com\tTRUE\t/\tFALSE\t0\t${name}\t${v.join('=')}`;
}).join('\n'))
```

5. Cookies скопированы в буфер обмена
6. Создайте файл `youtube_cookies.txt` и вставьте туда
7. Добавьте в начало файла:
```
# Netscape HTTP Cookie File
```

## Проверка работы

```bash
cd /home/lexey/projects/secbrain
yt-dlp --cookies youtube_cookies.txt --dump-json --no-download "https://www.youtube.com/watch?v=cQjqRz4HH9M"
```

Если работает, увидите JSON с метаданными видео.

## Важные cookies для YouTube

Основные cookies, которые нужны:
- `CONSENT` - согласие с политикой
- `VISITOR_INFO1_LIVE` - идентификатор посетителя  
- `PREF` - настройки
- `YSC` - YouTube session cookie
- `LOGIN_INFO` - информация о логине
- `SID`, `HSID`, `SSID`, `APISID`, `SAPISID` - токены авторизации

## Использование в коде

После создания файла `youtube_cookies.txt`:

```python
from src.modules.youtube_grabber import YouTubeGrabber

# Создаём grabber с cookies
grabber = YouTubeGrabber(
    output_dir=Path('temp'),
    cookies_file='youtube_cookies.txt'  # Путь к файлу cookies
)

# Теперь можно скачивать защищённые видео
content = grabber.grab('https://www.youtube.com/watch?v=cQjqRz4HH9M')
```

## Troubleshooting

### Ошибка "Sign in to confirm you're not a bot"
- Cookies устарели или не экспортированы
- Решение: экспортируйте свежие cookies

### Ошибка "could not find cookies database"
- На сервере нет браузера
- Решение: экспортируйте cookies на компьютере и загрузите на сервер

### Cookies не работают
- Возможно, они от другого аккаунта
- Убедитесь, что залогинены на YouTube при экспорте
- Попробуйте экспортировать заново

## Безопасность

⚠️ **ВАЖНО**: Файл cookies содержит токены авторизации!
- Не коммитьте в git (уже в .gitignore)
- Не передавайте третьим лицам
- Храните только на сервере
- Обновляйте регулярно (cookies имеют срок действия)

## Автоматизация

Добавьте в `.gitignore`:
```
youtube_cookies.txt
*_cookies.txt
cookies/
```

Уже добавлено в проект! ✅
