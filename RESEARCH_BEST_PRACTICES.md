# 🎯 Лучшие практики из youtube-dl и Hitomi-Downloader

## Анализ репозиториев

### YouTube-DL: Ключевые находки

1. **Cookie управление** (`youtube_dl/utils.py`):
   - YoutubeDLCookieJar - специальный класс для Mozilla cookies
   - Обработка session cookies (expires=0)
   - YoutubeDLCookieProcessor для HTTP запросов

2. **Rate Limiting** (различные extractors):
   - Умные задержки между запросами
   - Retry механизм с экспоненциальной задержкой
   - Разные стратегии для разных сайтов

3. **User-Agent ротация** (`youtube_dl/extractor/youtube.py`):
   - INNERTUBE_CONTEXT с clientName/clientVersion
   - Разные клиенты: web, web_creator, android, ios
   - SAPISIDHASH генерация для авторизации

4. **Обход блокировок**:
   - `_apply_first_set_cookie_header()` - использует первый cookie, не последний
   - `_set_cookie()` с domain scoping
   - Geo-bypass через прокси

### Hitomi-Downloader: Ключевые находки

1. **Rate Limiting через декоратор** (`@limits`):
```python
@limits(1.5)  # Максимум 1 запрос за 1.5 секунды
def call(self, url):
    pass
```

2. **Cookie Accept Patterns**:
```python
ACCEPT_COOKIES = [r'(.*\.)?domain\.com']  # Regex для принятия cookies
```

3. **Retry с динамической задержкой**:
```python
@try_n(12, sleep=lambda try_: 10+try_*10)  # Увеличивающаяся задержка
def read_soup(*args, **kwargs):
    pass
```

4. **Session управление**:
```python
session.cookies.set(name='over18', value='yes', path='/', domain='.site.com')
```

5. **CloudFlare обход**:
   - clf2.solve() для решения challenge
   - Автоматическая обработка captcha

## Применение к нашему проекту

### 1. Улучшенный Rate Limiter

```python
from functools import wraps
import time
from threading import Lock

class RateLimiter:
    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self.timestamps = []
        self.lock = Lock()
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                now = time.time()
                # Удаляем старые timestamps
                self.timestamps = [t for t in self.timestamps if now - t < self.period]
                
                if len(self.timestamps) >= self.calls:
                    # Ждём до следующего доступного слота
                    sleep_time = self.period - (now - self.timestamps[0])
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    self.timestamps = self.timestamps[1:]
                
                self.timestamps.append(time.time())
            
            return func(*args, **kwargs)
        return wrapper
```

### 2. Умный Retry с экспоненциальной задержкой

```python
def smart_retry(max_attempts: int = 3, base_delay: float = 1.0, backoff: float = 2.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    
                    # Экспоненциальная задержка: 1s, 2s, 4s, 8s...
                    delay = base_delay * (backoff ** attempt)
                    # Добавляем jitter для избежания синхронизации
                    delay += random.uniform(0, delay * 0.1)
                    
                    print(f"Попытка {attempt + 1}/{max_attempts} не удалась: {e}")
                    print(f"Повтор через {delay:.1f} сек...")
                    time.sleep(delay)
        return wrapper
    return decorator
```

### 3. YouTube Client Rotation

```python
YOUTUBE_CLIENTS = [
    {
        'name': 'WEB',
        'version': '2.20250111.00.00',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    },
    {
        'name': 'ANDROID',
        'version': '19.09.36',
        'user_agent': 'com.google.android.youtube/19.09.36 (Linux; U; Android 13) gzip',
    },
    {
        'name': 'IOS',
        'version': '19.09.3',
        'user_agent': 'com.google.ios.youtube/19.09.3 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
    },
]
```

### 4. Cookie Domain Scoping

```python
def set_cookie_with_domain(session, domain, name, value, **kwargs):
    """Устанавливает cookie с правильным domain scoping"""
    cookie = requests.cookies.create_cookie(
        domain=domain,
        name=name,
        value=value,
        path='/',
        secure=True,
        **kwargs
    )
    session.cookies.set_cookie(cookie)
```

### 5. Обработка Session Cookies

```python
def load_cookies_with_session_fix(cookie_file):
    """Загружает cookies и исправляет session cookies"""
    jar = http.cookiejar.MozillaCookieJar(cookie_file)
    jar.load(ignore_discard=True, ignore_expires=True)
    
    # Исправляем session cookies (expires=0)
    for cookie in jar:
        if cookie.expires == 0:
            cookie.expires = None
            cookie.discard = True
    
    return jar
```

## Рекомендации для внедрения

### Приоритет 1 (Критично):
1. ✅ Rate limiting через декораторы
2. ✅ Умный retry с экспоненциальной задержкой
3. ✅ Session cookies обработка

### Приоритет 2 (Важно):
4. ✅ YouTube client rotation
5. ✅ Cookie domain scoping
6. ✅ Jitter в задержках

### Приоритет 3 (Желательно):
7. CloudFlare bypass (требует headless browser)
8. SAPISIDHASH для YouTube авторизации
9. Geo-bypass detection и обход

## Бенчмарки

### YouTube-DL:
- Rate limit: ~1 запрос/сек для YouTube
- Retry: до 10 попыток с увеличивающейся задержкой
- Поддержка 1000+ сайтов

### Hitomi-Downloader:
- Rate limit: настраиваемый через @limits
- Retry: до 12 попыток
- CloudFlare bypass встроен
- Cookie regex patterns для гибкой фильтрации

## Выводы

**Что взять из youtube-dl:**
- Архитектура cookie jar с session cookies
- Подход к retry с различными стратегиями
- User-Agent и client rotation для YouTube

**Что взять из Hitomi-Downloader:**
- Простые и элегантные декораторы @limits и @try_n
- Cookie accept patterns через regex
- CloudFlare bypass интеграция

**Наше преимущество:**
- Можем комбинировать лучшее из обоих
- Специализация на Instagram + YouTube (не 1000 сайтов)
- Современный Python 3.12+ (async/await)
