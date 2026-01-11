# 🛡️ Обход блокировок YouTube

YouTube агрессивно блокирует cookies при автоматизации. Это руководство поможет решить проблему.

## 🔍 Проблема

**Симптомы:**
- ❌ "Sign in to confirm you're not a bot"
- ❌ Cookies работают 10-15 минут, потом блокируются
- ❌ Постоянные капчи и блокировки

**Причины:**
1. YouTube детектирует yt-dlp по поведению
2. Быстрые повторяющиеся запросы с одних cookies
3. Нетипичные заголовки HTTP
4. Отсутствие прокси при массовой загрузке

## ✅ Решения

### Решение 1: Множественные Cookies (Рекомендуется)

Используйте несколько аккаунтов Google и ротацию cookies.

#### Шаг 1: Экспорт cookies с разных аккаунтов

На **локальном компьютере** с браузером:

```bash
# Аккаунт 1
# Откройте youtube.com в Chrome под аккаунтом 1
yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_1.txt --skip-download "https://youtube.com/watch?v=test"

# Аккаунт 2 (используйте другой профиль Chrome)
yt-dlp --cookies-from-browser chrome:Profile2 --cookies youtube_cookies_2.txt --skip-download "https://youtube.com/watch?v=test"

# Аккаунт 3 (Firefox)
yt-dlp --cookies-from-browser firefox --cookies youtube_cookies_3.txt --skip-download "https://youtube.com/watch?v=test"
```

**Или через расширение браузера:**
1. Установите [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Откройте youtube.com под разными аккаунтами
3. Экспортируйте cookies для каждого → `youtube_cookies_1.txt`, `youtube_cookies_2.txt`, ...

#### Шаг 2: Загрузка на сервер

```bash
# Загрузите все cookies на сервер
scp youtube_cookies_*.txt lexey@38.242.141.28:/home/lexey/projects/secbrain/
```

#### Шаг 3: Добавление в Cookie Manager

```bash
cd /home/lexey/projects/secbrain

# Добавляем cookies
python cookie_manager.py add --file youtube_cookies_1.txt --name account1
python cookie_manager.py add --file youtube_cookies_2.txt --name account2
python cookie_manager.py add --file youtube_cookies_3.txt --name account3

# Проверяем
python cookie_manager.py list
```

#### Шаг 4: Использование в коде

Обновите `content_downloader.py` или используйте новый `youtube_grabber_advanced.py`:

```python
from pathlib import Path
from src.modules.youtube_grabber_advanced import AdvancedYouTubeGrabber
from cookie_manager import CookieManager

# Получаем все cookies
cookie_mgr = CookieManager()
cookies_files = cookie_mgr.get_all_cookies()

print(f"✅ Найдено {len(cookies_files)} cookies файлов")

# Создаём загрузчик с ротацией
grabber = AdvancedYouTubeGrabber(
    output_dir=Path('downloads'),
    cookies_files=cookies_files,  # Передаём список cookies
    min_delay=3.0,  # Задержка между запросами
    max_delay=7.0
)

# Скачиваем с автоматической ротацией
result = grabber.download_video("https://youtu.be/VIDEO_ID")
```

### Решение 2: Прокси-серверы

Используйте прокси для смены IP-адреса.

#### Бесплатные прокси (ненадёжные)

```bash
# Добавьте прокси в proxies.txt
nano proxies.txt

# Формат:
http://proxy1.com:8080
socks5://proxy2.com:1080
```

#### Платные прокси (рекомендуется)

**Рекомендуемые сервисы:**
- **Bright Data** - $500/100GB, 72M+ IP, высокая надёжность
- **Smartproxy** - $75/8GB, 40M+ IP, хорошее соотношение цена/качество
- **Oxylabs** - от $300/month, премиум качество

```bash
# Пример с Bright Data
echo "http://username:password@brd.superproxy.io:22225" >> proxies.txt
```

#### Использование прокси в коде

```python
from pathlib import Path
from src.modules.youtube_grabber_advanced import AdvancedYouTubeGrabber

grabber = AdvancedYouTubeGrabber(
    output_dir=Path('downloads'),
    cookies_files=[Path('youtube_cookies.txt')],
    proxies_file=Path('proxies.txt'),  # Включаем прокси
    min_delay=2.0,
    max_delay=5.0
)

result = grabber.download_video("https://youtu.be/VIDEO_ID")
grabber.print_stats()
```

### Решение 3: Комбинированный подход (Максимальная надёжность)

Комбинируйте множественные cookies + прокси + задержки:

```python
from pathlib import Path
from src.modules.youtube_grabber_advanced import AdvancedYouTubeGrabber
from cookie_manager import CookieManager

# Загружаем все cookies
cookie_mgr = CookieManager()
cookies_files = cookie_mgr.get_all_cookies()

# Создаём загрузчик с полной защитой
grabber = AdvancedYouTubeGrabber(
    output_dir=Path('downloads'),
    cookies_files=cookies_files,     # Ротация cookies
    proxies_file=Path('proxies.txt'),  # Ротация прокси
    min_delay=5.0,                     # Увеличенная задержка
    max_delay=10.0
)

# Массовая загрузка
urls = [
    "https://youtu.be/VIDEO_1",
    "https://youtu.be/VIDEO_2",
    "https://youtu.be/VIDEO_3",
]

for url in urls:
    print(f"\n{'='*60}")
    result = grabber.download_video(url, max_retries=5)
    if result:
        print(f"✅ Успешно: {result}")
    else:
        print(f"❌ Неудача: {url}")

# Статистика
grabber.print_stats()
```

## 🔧 Утилиты

### Cookie Manager

```bash
# Добавить cookies
python cookie_manager.py add --file youtube_cookies.txt --name my_account

# Показать список активных cookies
python cookie_manager.py list

# Статистика использования
python cookie_manager.py stats

# Разблокировать все cookies (после обновления)
python cookie_manager.py unblock

# Удалить старые cookies (>7 дней)
python cookie_manager.py clean --days 7
```

### Проверка cookies

```bash
# Проверить, работает ли cookies файл
yt-dlp --cookies youtube_cookies.txt --dump-json "https://youtu.be/VIDEO_ID"

# Если видите метаданные - cookies работает ✅
# Если "Sign in to confirm you're not a bot" - cookies заблокирован ❌
```

## 📊 Мониторинг

### Статистика загрузчика

```python
grabber.print_stats()

# Выведет:
# ============================================================
# 📊 СТАТИСТИКА ЗАГРУЗЧИКА
# ============================================================
# Всего запросов: 50
# Успешных: 45
# Неудачных: 5
# Success Rate: 90.0%
# Cookies файлов: 3
# Прокси: 5
# ============================================================
```

### Статистика cookies

```bash
python cookie_manager.py stats

# Выведет статистику каждого cookies:
# - Когда добавлен
# - Сколько раз использован
# - Success rate
# - Блокирован или нет
```

## ⚡ Best Practices

1. **Используйте 3+ аккаунта Google** для ротации cookies
2. **Обновляйте cookies каждые 3-7 дней** (даже если не заблокированы)
3. **Используйте платные прокси** для массовой загрузки (>100 видео/день)
4. **Увеличивайте задержки** между запросами (5-10 сек)
5. **Мониторьте Success Rate** - если падает ниже 70%, обновите cookies
6. **Не используйте один аккаунт Google** для всех загрузок
7. **Храните резервные cookies** на случай блокировки

## 🆘 Troubleshooting

### Все cookies быстро блокируются

**Решения:**
1. Используйте прокси (меняйте IP)
2. Увеличьте задержки между запросами до 10+ секунд
3. Создайте новые Google аккаунты
4. Не логинтесь с аккаунтов на VPS (используйте только локальный браузер)

### Прокси не работают

**Проверка:**
```bash
# Тест прокси
curl -x http://proxy.com:8080 https://ipinfo.io/ip

# Если не работает - прокси нерабочий
```

### Низкий Success Rate (<50%)

**Действия:**
1. Обновите все cookies
2. Добавьте больше аккаунтов
3. Используйте прокси
4. Увеличьте задержки
5. Проверьте, не забанен ли IP VPS

### YouTube детектирует yt-dlp

**Альтернативы:**
- Используйте Selenium + undetected-chromedriver (медленно, но надёжно)
- Используйте YouTube API (лимиты, но официально)
- Используйте сторонние сервисы (платно)

## 📚 Дополнительные ресурсы

- [yt-dlp документация](https://github.com/yt-dlp/yt-dlp)
- [YouTube cookies обход](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [Прокси для scraping](https://brightdata.com/)

## 🎯 Итого

**Для редких загрузок (1-10 видео/день):**
- ✅ Один свежий cookies файл
- ✅ Задержки 5-10 сек

**Для умеренных загрузок (10-50 видео/день):**
- ✅ 2-3 cookies файла (ротация)
- ✅ Задержки 5-10 сек
- ✅ Обновление cookies раз в неделю

**Для массовых загрузок (50+ видео/день):**
- ✅ 5+ cookies файлов
- ✅ Платные прокси
- ✅ Задержки 10+ сек
- ✅ Обновление cookies каждые 3 дня
- ✅ Мониторинг статистики
