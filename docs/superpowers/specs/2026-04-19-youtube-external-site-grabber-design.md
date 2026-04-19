# Design: YouTube External-Site Grabber

**Date:** 2026-04-19  
**Status:** Approved

## Context

VPS (Contabo datacenter) IP-адреса агрессивно блокируются YouTube. yt-dlp требует свежих cookies, которые протухают быстро из-за блокировок. Нужен способ скачивать YouTube-видео через внешний сайт-посредник (ssyoutube.com и аналоги), который выполняет запросы к YouTube со своей инфраструктуры.

**Схема**: внешний сайт — первичный метод, yt-dlp — fallback.

---

## Architecture

```text
YouTubeDownloadStrategy (Protocol)         — новый интерфейс
    download_video(url, output_dir, quality) → Path

ExternalSiteGrabber                        — новый класс
    implements YouTubeDownloadStrategy
    Playwright headless → ssyoutube.com → mp4

ProductionYouTubeGrabber                   — существующий (youtube_grabber_v2.py)
    implements YouTubeDownloadStrategy
    yt-dlp (без изменений в логике)

YouTubeVideoDownloader                     — модифицируется
    strategies: [ExternalSiteGrabber, ProductionYouTubeGrabber]
    get_metadata() — по-прежнему через ProductionYouTubeGrabber (yt-dlp --dump-json)

YouTubeShortsDownloader                    — модифицируется (то же самое)
```

---

## Components

### 1. `YouTubeDownloadStrategy` (Protocol)

**Файл:** `src/modules/youtube_grabber_base.py`

```python
from typing import Protocol
from pathlib import Path

class YouTubeDownloadStrategy(Protocol):
    async def download_video(
        self,
        url: str,
        output_dir: Path,
        quality: str = "best",
    ) -> Path: ...
```

Простой структурный Protocol без наследования — оба граббера работают через duck typing.

---

### 2. `ExternalSiteGrabber`

**Файл:** `src/modules/external_site_grabber.py`

**Ответственность:** открыть headless-браузер, перейти на ssyoutube.com с YouTube-URL, дождаться появления ссылок на скачивание, выбрать лучшее mp4, скачать файл.

**Ключевые методы:**

```python
class ExternalSiteGrabber:
    BASE_URL = "https://en.ssyoutube.com/en/download"

    async def download_video(self, url: str, output_dir: Path, quality: str) -> Path:
        """
        1. async with async_playwright() as p
        2. browser = await p.chromium.launch(headless=True)
        3. page.goto(f"{BASE_URL}?url={quote(url)}")
        4. page.wait_for_selector(".download-links", timeout=30_000)
        5. Найти ссылку: best mp4 (фильтр по data-quality или тексту кнопки)
        6. Скачать через httpx.AsyncClient (stream) → output_dir/video.mp4
        7. return Path
        """
```

**Обработка ошибок:**

- `TimeoutError` — сайт не ответил за 30 сек → `ExternalSiteError`
- Нет подходящего mp4-линка → `ExternalSiteError`
- HTTP-ошибка при скачивании → `ExternalSiteError`

**Конфигурация:** `timeout_ms: int = 30_000` в конструкторе (настраивается через `BotConfig`).

---

### 3. Модификация `ProductionYouTubeGrabber`

**Файл:** `src/modules/youtube_grabber_v2.py`

Изменений в логике **нет**. Только добавить тайп-хинт, что класс соответствует `YouTubeDownloadStrategy`:

```python
from .youtube_grabber_base import YouTubeDownloadStrategy
# ProductionYouTubeGrabber уже имеет метод download_video с нужной сигнатурой
```

---

### 4. Модификация `YouTubeVideoDownloader` и `YouTubeShortsDownloader`

**Файлы:**

- `src/modules/youtube_video_downloader.py`
- `src/modules/youtube_shorts_downloader.py`

**Изменение конструктора:**

```python
def __init__(self, settings: DownloadSettings, output_dir: Path):
    self.grabber = ProductionYouTubeGrabber(settings)  # для метаданных
    self.strategies: list[YouTubeDownloadStrategy] = [
        ExternalSiteGrabber(timeout_ms=30_000),
        self.grabber,  # fallback
    ]
```

**Изменение метода `download()`:**

```python
# Метаданные — по-прежнему через yt-dlp (лёгкий запрос)
try:
    metadata = await self.grabber.get_metadata(url)
except Exception:
    metadata = self._minimal_metadata(url)  # заглушка: {title: video_id}

folder_path = self.create_folder(...)

# Скачивание — цепочка стратегий
video_path: Path | None = None
last_error: Exception | None = None
for strategy in self.strategies:
    try:
        video_path = await strategy.download_video(url, folder_path, quality)
        break
    except Exception as e:
        logger.warning("strategy %s failed: %s", type(strategy).__name__, e)
        last_error = e

if video_path is None:
    raise DownloadError("all strategies failed") from last_error
```

---

## Data Flow

```text
User sends YouTube URL
        │
YouTubeVideoDownloader.download(url)
        │
        ├─ get_metadata(url) via yt-dlp → title, author, description
        │   (если yt-dlp упал → minimal: {title: video_id из URL, author: "unknown", description: ""})
        │
        ├─ create_folder("{date}_{author}_{slug}")
        │
        ├─ ExternalSiteGrabber.download_video(url, folder, quality)
        │       Playwright → ssyoutube.com → mp4 download
        │       ✓ success → video_path
        │       ✗ fail → warning, next strategy
        │
        ├─ ProductionYouTubeGrabber.download_video(url, folder, quality)
        │       yt-dlp → mp4 download
        │       ✓ success → video_path
        │       ✗ fail → raise DownloadError
        │
        └─ save_description.md → return DownloadResult
```

---

## Error Handling

| Ситуация | Поведение |
| --- | --- |
| ssyoutube.com недоступен (timeout) | Warning + fallback на yt-dlp |
| ssyoutube.com изменил DOM | Warning + fallback на yt-dlp |
| yt-dlp заблокирован | Warning, вернуть ошибку пользователю |
| Оба метода упали | `DownloadError` → бот уведомляет пользователя |
| yt-dlp metadata упала | Использовать заглушку, продолжить скачивание |

---

## Configuration

Добавить в `BotConfig` (или `DownloadSettings`):

```python
external_site_url: str = "https://en.ssyoutube.com/en/download"
external_site_timeout_ms: int = 30_000
```

---

## Testing

- `tests/test_external_site_grabber.py`:
  - Мокировать `async_playwright` — проверить корректный URL, правильный CSS-селектор
  - Проверить fallback: `ExternalSiteGrabber` поднимает ошибку → `ProductionYouTubeGrabber` вызывается
  - Проверить minimal metadata при падении yt-dlp

- End-to-end вручную:
  1. Запустить бота, отправить YouTube-ссылку
  2. Убедиться, что файл скачан через внешний сайт (смотреть логи: `"ExternalSiteGrabber: success"`)
  3. Имитировать сбой внешнего сайта (неверный URL в конфиге), убедиться что fallback работает

---

## Files Changed

| Файл | Действие |
| --- | --- |
| `src/modules/youtube_grabber_base.py` | Создать |
| `src/modules/external_site_grabber.py` | Создать |
| `src/modules/youtube_grabber_v2.py` | Минорно: добавить type hint |
| `src/modules/youtube_video_downloader.py` | Модифицировать |
| `src/modules/youtube_shorts_downloader.py` | Модифицировать |
| `src/bot/config.py` | Добавить 2 поля конфига |
| `tests/test_external_site_grabber.py` | Создать |
