# Модульная Архитектура Module 1

## Обзор

Module 1 был рефакторен из монолитного `content_downloader.py` (429 строк) в модульную архитектуру с отдельными специализированными скачивателями.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     module1_download.py                     │
│                     (CLI интерфейс)                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    ContentRouter                            │
│              (Маршрутизатор контента)                       │
│                                                             │
│  • detect_downloader(url) → BaseDownloader                 │
│  • download(url) → DownloadResult                          │
│  • is_supported(url) → bool                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    Instagram       YouTube         Comments
    Downloaders     Downloaders     Downloader
        │               │               │
    ┌───┴───┐       ┌───┴───┐          │
    ▼       ▼       ▼       ▼          ▼
  Posts  Reels   Videos  Shorts   CommentsDownloader
    │       │       │       │          │
    │       │       └───┬───┘          │
    │       │           │              │
    ▼       ▼           ▼              ▼
┌────────────────────────────────────────┐
│        ProductionYouTubeGrabber        │
│     (Обход блокировок YouTube)         │
│                                        │
│  • @rate_limit decorator               │
│  • @smart_retry with backoff           │
│  • Client rotation (WEB/ANDROID/IOS)   │
│  • ImprovedCookieManager               │
└────────────────────────────────────────┘
```

## Структура файлов

```
src/modules/
│
├── downloader_base.py              # Базовые классы
│   ├── ContentSource (Enum)
│   ├── InstagramContentType (Enum)
│   ├── YouTubeContentType (Enum)
│   ├── DownloadResult (dataclass)
│   ├── DownloadSettings (dataclass)
│   └── BaseDownloader (ABC)
│
├── downloader_utils.py             # Утилиты
│   ├── clean_filename()
│   ├── extract_video_id_youtube()
│   ├── extract_shortcode_instagram()
│   ├── format_duration()
│   ├── format_count()
│   └── ...
│
├── instagram_post_downloader.py    # Instagram посты
│   └── InstagramPostDownloader(BaseDownloader)
│       ├── can_handle(url) → bool
│       ├── download(url) → InstagramPostResult
│       └── используeт gallery-dl
│
├── instagram_reels_downloader.py   # Instagram Reels
│   └── InstagramReelsDownloader(BaseDownloader)
│       ├── can_handle(url) → bool
│       ├── download(url) → InstagramReelsResult
│       └── используeт gallery-dl
│
├── youtube_video_downloader.py     # YouTube видео
│   └── YouTubeVideoDownloader(BaseDownloader)
│       ├── can_handle(url) → bool
│       ├── download(url) → YouTubeVideoResult
│       └── использует ProductionYouTubeGrabber
│
├── youtube_shorts_downloader.py    # YouTube Shorts
│   └── YouTubeShortsDownloader(BaseDownloader)
│       ├── can_handle(url) → bool
│       ├── download(url) → YouTubeVideoResult
│       └── использует ProductionYouTubeGrabber
│
├── comments_downloader.py          # Комментарии
│   └── CommentsDownloader
│       ├── download_youtube_comments()
│       └── download_instagram_comments()
│
├── content_router.py               # Роутер (оркестратор)
│   └── ContentRouter
│       ├── download(url) → DownloadResult
│       ├── detect_downloader(url) → BaseDownloader
│       ├── is_supported(url) → bool
│       └── get_downloader_info(url) → dict
│
└── youtube_grabber_v2.py           # Продакшн YouTube grabber
    └── ProductionYouTubeGrabber
        ├── @rate_limit декоратор
        ├── @smart_retry декоратор
        ├── get_metadata(url) → dict
        ├── download_video(url) → Path
        ├── download_subtitles(url) → List[Path]
        └── get_comments(video_id) → List[dict]
```

## Интерфейс BaseDownloader

Все скачиватели реализуют единый интерфейс:

```python
class BaseDownloader(ABC):
    def __init__(self, settings: DownloadSettings):
        self.settings = settings
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Может ли обработать этот URL"""
        pass
    
    @abstractmethod
    def download(self, url: str) -> DownloadResult:
        """Скачивает контент"""
        pass
    
    # Вспомогательные методы
    def create_folder(self, prefix, content_id, title) -> Path
    def save_description(self, folder_path, description) -> Path
    def save_comments(self, folder_path, comments) -> Path
```

## Data Flow (Поток данных)

### 1. Пользователь вводит URL

```
https://www.youtube.com/watch?v=abc123
```

### 2. ContentRouter определяет тип

```python
router.detect_downloader(url)
# → YouTubeVideoDownloader
```

### 3. Скачивание

```python
downloader.download(url)
```

**Этапы:**

1. **Извлечение ID**: `extract_video_id_youtube(url)` → `"abc123"`
2. **Получение метаданных**: `ProductionYouTubeGrabber.get_metadata(url)`
   - Применяется `@rate_limit` (пауза 2 секунды)
   - Применяется `@smart_retry` (до 4 попыток)
   - Выбирается лучший cookie (по health score)
   - Ротация клиентов (WEB → ANDROID → IOS)
3. **Создание папки**: `create_folder()` → `downloads/youtube_channel_abc123_title/`
4. **Скачивание видео**: `ProductionYouTubeGrabber.download_video()`
   - Применяется `@rate_limit` (пауза 3 секунды)
   - Применяется `@smart_retry` (до 3 попыток)
5. **Скачивание субтитров**: `download_subtitles()` (опционально)
6. **Скачивание комментариев**: `CommentsDownloader` (если `download_comments=True`)
7. **Сохранение описания**: `save_description()` → `description.md`

### 4. Возврат результата

```python
YouTubeVideoResult(
    source=ContentSource.YOUTUBE,
    content_type=YouTubeContentType.VIDEO,
    url=url,
    content_id="abc123",
    folder_path=Path("downloads/youtube_channel_abc123_title"),
    media_files=[Path("video.mp4"), Path("subtitles.en.vtt")],
    description_file=Path("description.md"),
    comments_file=Path("comments.md"),
    channel="ChannelName",
    views=1000000,
    likes=50000,
    duration=600
)
```

## Преимущества модульной архитектуры

### ✅ Разделение ответственности

- **Instagram Post**: только логика постов
- **Instagram Reels**: только логика reels
- **YouTube Video**: только логика видео
- **YouTube Shorts**: только логика shorts

### ✅ Легкость тестирования

Каждый модуль тестируется независимо:

```python
def test_instagram_post():
    downloader = InstagramPostDownloader(settings)
    assert downloader.can_handle("https://instagram.com/p/abc123")
    result = downloader.download(url)
    assert isinstance(result, InstagramPostResult)
```

### ✅ Простота расширения

Добавление новой платформы (например, TikTok):

```python
class TikTokDownloader(BaseDownloader):
    def can_handle(self, url: str) -> bool:
        return 'tiktok.com' in url.lower()
    
    def download(self, url: str) -> DownloadResult:
        # Реализация
        pass

# Добавляем в ContentRouter
router.downloaders.append(TikTokDownloader(settings))
```

### ✅ Изоляция изменений

Изменения в Instagram логике не влияют на YouTube и наоборот.

### ✅ Переиспользование кода

- `ProductionYouTubeGrabber` используется и в `YouTubeVideoDownloader`, и в `YouTubeShortsDownloader`
- `CommentsDownloader` универсален для всех платформ
- Утилиты в `downloader_utils.py` используются везде

## Интеграция с ProductionYouTubeGrabber

YouTube скачиватели используют продакшн-готовый grabber с обходом блокировок:

```python
class YouTubeVideoDownloader(BaseDownloader):
    def __init__(self, settings: DownloadSettings):
        super().__init__(settings)
        
        # Инициализируем ProductionYouTubeGrabber
        self.grabber = ProductionYouTubeGrabber(
            cookies_dir=settings.youtube_cookies.parent
        )
    
    def download(self, url: str) -> YouTubeVideoResult:
        # Используем grabber с автоматическим:
        # - Rate limiting
        # - Retry с exponential backoff
        # - Client rotation
        # - Cookie health scoring
        metadata = self.grabber.get_metadata(url)
        video_path = self.grabber.download_video(url, ...)
```

### Особенности ProductionYouTubeGrabber

1. **Rate Limiting**: `@rate_limit(calls=1, period=2.0)`
   - Максимум 1 запрос за 2 секунды
   - Автоматическая пауза между запросами

2. **Smart Retry**: `@smart_retry(max_attempts=4, base_delay=2.0, backoff=2.0)`
   - Экспоненциальная задержка: 2s → 4s → 8s → 16s
   - Jitter ±10% для избежания синхронизации
   - До 4 попыток

3. **Client Rotation**:
   ```python
   YOUTUBE_CLIENTS = {
       'WEB': {...},
       'ANDROID': {...},
       'IOS': {...}
   }
   ```
   - Автоматическое переключение между клиентами
   - Каждый клиент имеет свой User-Agent

4. **Cookie Health Scoring**:
   ```python
   health_score = usage_count * 10 + fail_count * 100
   ```
   - Выбирается cookie с наименьшим score
   - Автоблокировка после 3 неудач подряд
   - Auto-recovery: fail_count уменьшается при успехе

## Настройки (DownloadSettings)

```python
@dataclass
class DownloadSettings:
    download_video: bool = True
    download_comments: bool = False
    video_quality: str = 'best'
    max_comments: int = 100
    instagram_cookies: Optional[Path] = None
    youtube_cookies: Optional[Path] = None
```

## Использование

### CLI (module1_download.py)

```bash
python module1_download.py
```

Интерактивный режим:
- Вводим URL
- Автоматически определяется тип
- Скачивается контент
- Показывается статистика

### Программный интерфейс

```python
from src.modules import ContentRouter, DownloadSettings
from pathlib import Path

# Настройки
settings = DownloadSettings(
    download_video=True,
    download_comments=True,
    video_quality='1080p',
    max_comments=200,
    youtube_cookies=Path('cookies/youtube.txt')
)

# Создаем роутер
router = ContentRouter(settings)

# Скачиваем
result = router.download("https://www.youtube.com/watch?v=abc123")

print(f"Скачано: {result.folder_path}")
print(f"Файлов: {len(result.media_files)}")
print(f"Просмотры: {result.views}")
```

## Миграция со старого кода

### Было (монолитный ContentDownloader):

```python
from src.modules.content_downloader import ContentDownloader

downloader = ContentDownloader(output_dir=Path('downloads'))
result = downloader.download(url, download_video=True)
```

### Стало (модульная архитектура):

```python
from src.modules import ContentRouter, DownloadSettings

settings = DownloadSettings(
    download_video=True,
    youtube_cookies=Path('cookies/youtube.txt')
)
router = ContentRouter(settings)
result = router.download(url)
```

## Тестирование

```bash
# Тест Instagram Post
python -c "
from src.modules import ContentRouter, DownloadSettings
router = ContentRouter(DownloadSettings())
info = router.get_downloader_info('https://instagram.com/p/abc123')
print(info)
"

# Тест YouTube Video
python -c "
from src.modules import ContentRouter, DownloadSettings
router = ContentRouter(DownloadSettings())
info = router.get_downloader_info('https://youtube.com/watch?v=abc123')
print(info)
"

# Тест YouTube Short
python -c "
from src.modules import ContentRouter, DownloadSettings
router = ContentRouter(DownloadSettings())
info = router.get_downloader_info('https://youtube.com/shorts/abc123')
print(info)
"
```

## Следующие шаги

1. ✅ **Создана базовая архитектура**
2. ✅ **Созданы все подмодули**
3. ✅ **Интегрирован ProductionYouTubeGrabber**
4. ✅ **Обновлен module1_download.py**
5. 🔄 **Тестирование на реальных URL**
6. 📝 **Обновить Module 2 и Module 3** (если нужно)

## Файловая структура результатов

```
downloads/
├── instagram_post_username_ABC123_title/
│   ├── 01_photo.jpg
│   ├── 02_photo.jpg
│   ├── description.md
│   └── comments.md (если включено)
│
├── instagram_reels_username_XYZ789_title/
│   ├── reel.mp4
│   ├── description.md
│   └── comments.md (если включено)
│
├── youtube_channel_abc123_title/
│   ├── video.mp4
│   ├── subtitles.en.vtt
│   ├── subtitles.ru.vtt
│   ├── description.md
│   └── comments.md (если включено)
│
└── youtube_shorts_channel_xyz789_title/
    ├── shorts.mp4
    ├── description.md
    └── comments.md (если включено)
```

## Заключение

Модульная архитектура обеспечивает:
- ✅ Чистый код (каждый модуль < 200 строк)
- ✅ Легкое тестирование
- ✅ Простое расширение
- ✅ Изоляцию изменений
- ✅ Переиспользование кода
- ✅ Продакшн-готовый обход блокировок YouTube
