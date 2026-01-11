# Quick Start: Модульная Архитектура Module 1

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Подготовка cookies (опционально, но рекомендуется)

```bash
mkdir cookies

# Для YouTube (от блокировок)
# 1. Установите расширение "Get cookies.txt LOCALLY"
# 2. Зайдите на YouTube
# 3. Экспортируйте cookies в cookies/youtube.txt

# Для Instagram (для приватных аккаунтов)
# 1. Установите расширение "Get cookies.txt LOCALLY"
# 2. Зайдите в Instagram
# 3. Экспортируйте cookies в cookies/instagram.txt
```

### 3. Запуск

```bash
python module1_download.py
```

## Примеры использования

### CLI режим

```bash
$ python module1_download.py

🔗 Введите URL: https://www.youtube.com/watch?v=abc123

🎯 Платформа: YouTube
📌 Тип: Video
🔧 Скачиватель: YouTubeVideoDownloader

🎥 Анализ видео: https://www.youtube.com/watch?v=abc123
📁 Папка: downloads/youtube_channel_abc123_title
⬇️  Скачивание видео качество=best...
✅ Видео скачано: video.mp4
📝 Субтитры: 2 языков

✅ УСПЕШНО ЗАГРУЖЕНО
📍 Источник: YOUTUBE
📌 Тип: VIDEO
🆔 ID: abc123
📂 Папка: youtube_channel_abc123_title
🖼️  Медиа файлов: 3
👁️  Просмотры: 1.2M
❤️  Лайки: 50K
```

### Программный интерфейс

```python
from pathlib import Path
from src.modules import ContentRouter, DownloadSettings

# Настройки
settings = DownloadSettings(
    download_video=True,
    download_comments=True,
    video_quality='1080p',
    max_comments=200,
    instagram_cookies=Path('cookies/instagram.txt'),
    youtube_cookies=Path('cookies/youtube.txt')
)

# Создаем роутер
router = ContentRouter(settings)

# Скачиваем
url = "https://www.youtube.com/watch?v=abc123"
result = router.download(url)

# Результат
print(f"Скачано в: {result.folder_path}")
print(f"Медиа файлов: {len(result.media_files)}")
print(f"Просмотры: {result.views}")
```

## Поддерживаемые URL

### Instagram

```python
# Posts
"https://www.instagram.com/p/ABC123/"

# Reels
"https://www.instagram.com/reel/XYZ789/"
"https://www.instagram.com/reels/XYZ789/"
```

### YouTube

```python
# Videos
"https://www.youtube.com/watch?v=abc123"
"https://youtu.be/abc123"

# Shorts
"https://www.youtube.com/shorts/xyz789"
```

## Проверка поддержки URL

```python
from src.modules import ContentRouter, DownloadSettings

router = ContentRouter(DownloadSettings())

# Проверка поддержки
url = "https://www.youtube.com/watch?v=abc123"
if router.is_supported(url):
    print("✅ URL поддерживается")
else:
    print("❌ URL не поддерживается")

# Информация о скачивателе
info = router.get_downloader_info(url)
print(f"Платформа: {info['platform']}")
print(f"Тип: {info['content_type']}")
print(f"Скачиватель: {info['downloader']}")
```

## Настройки скачивания

### Качество видео

```python
settings = DownloadSettings(
    video_quality='best'      # Лучшее доступное
    # video_quality='1080p'   # 1080p
    # video_quality='720p'    # 720p
    # video_quality='480p'    # 480p
)
```

### Комментарии

```python
settings = DownloadSettings(
    download_comments=True,   # Включить скачивание комментариев
    max_comments=200          # Максимум 200 комментариев
)
```

### Полный пример настроек

```python
from pathlib import Path

settings = DownloadSettings(
    download_video=True,              # Скачивать видео
    download_comments=True,           # Скачивать комментарии
    video_quality='1080p',            # Качество 1080p
    max_comments=500,                 # Максимум 500 комментариев
    instagram_cookies=Path('cookies/instagram.txt'),
    youtube_cookies=Path('cookies/youtube.txt')
)
```

## Структура результатов

После скачивания создается папка:

```
downloads/platform_author_ID_title/
├── video.mp4                # Видео файл
├── subtitles.en.vtt         # Субтитры (YouTube)
├── subtitles.ru.vtt
├── description.md           # Описание + статистика
└── comments.md              # Комментарии (если включено)
```

## Обработка ошибок

```python
try:
    result = router.download(url)
    print(f"✅ Успешно: {result.folder_path}")
except ValueError as e:
    print(f"❌ Неверный URL: {e}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
```

## Автоматический обход блокировок YouTube

Для YouTube автоматически применяются:

1. **Rate Limiting**: пауза между запросами
2. **Retry с Exponential Backoff**: автоповтор при ошибках
3. **Client Rotation**: смена User-Agent (WEB/ANDROID/IOS)
4. **Cookie Health Scoring**: выбор лучшего cookie файла

Никаких дополнительных действий не требуется!

```python
# Просто скачиваем - обход блокировок автоматический
result = router.download("https://www.youtube.com/watch?v=abc123")
```

## Множественное скачивание

```python
from src.modules import ContentRouter, DownloadSettings

router = ContentRouter(DownloadSettings())

urls = [
    "https://www.youtube.com/watch?v=abc123",
    "https://www.youtube.com/watch?v=def456",
    "https://www.instagram.com/p/ABC123/",
]

for url in urls:
    try:
        result = router.download(url)
        print(f"✅ {result.content_id}: {result.folder_path}")
    except Exception as e:
        print(f"❌ {url}: {e}")
```

## CLI команды

### Переключение комментариев

В интерактивном режиме:

```
🔗 Введите URL: comments
💬 Комментарии включены
```

Повторный ввод `comments` выключает:

```
🔗 Введите URL: comments
💬 Комментарии выключены
```

### Выход

```
🔗 Введите URL: q
👋 Выход...
```

## Troubleshooting

### YouTube блокирует

1. Добавьте cookies:
   ```bash
   # Экспортируйте cookies в cookies/youtube.txt
   ```

2. Проверьте, что используется ProductionYouTubeGrabber:
   ```python
   # Должно быть автоматически в YouTubeVideoDownloader
   ```

### Instagram приватный аккаунт

1. Добавьте cookies авторизованного пользователя:
   ```bash
   # Экспортируйте cookies в cookies/instagram.txt
   ```

### Ошибка "URL не поддерживается"

Проверьте формат URL:
```python
# ✅ Правильно
"https://www.youtube.com/watch?v=abc123"
"https://www.instagram.com/p/ABC123/"

# ❌ Неправильно
"youtube.com/watch?v=abc123"  # Нет https://
"instagram.com/user/"         # Профиль, а не пост
```

## Расширение функциональности

### Добавление новой платформы (TikTok)

```python
from src.modules import BaseDownloader, DownloadResult

class TikTokDownloader(BaseDownloader):
    def can_handle(self, url: str) -> bool:
        return 'tiktok.com' in url.lower()
    
    def download(self, url: str) -> DownloadResult:
        # Ваша реализация
        pass

# Добавляем в роутер
router.downloaders.append(TikTokDownloader(settings))
```

### Кастомный обработчик результатов

```python
def custom_handler(result):
    print(f"Обработка: {result.content_id}")
    # Ваша логика
    # Например: загрузка в облако, обработка AI и т.д.

result = router.download(url)
custom_handler(result)
```

## Следующие шаги

После скачивания контента:

1. **Module 2**: Транскрибация
   ```bash
   python module2_transcribe.py
   ```

2. **Module 3**: AI анализ
   ```bash
   python module3_analyze.py
   ```

## Документация

- **MODULE1_ARCHITECTURE.md**: Подробная архитектура
- **BYPASS_YOUTUBE_BLOCKS.md**: Обход блокировок YouTube
- **QUICKSTART_BYPASS.md**: Быстрый старт обхода блокировок

## Лицензия

MIT
