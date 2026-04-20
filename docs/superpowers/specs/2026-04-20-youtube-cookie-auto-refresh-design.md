# Design: YouTube Cookie Auto-Refresh via Playwright

**Date:** 2026-04-20
**Status:** Approved

## Context

VPS (Contabo) IP заблокирован YouTube для bot-client запросов. yt-dlp возвращает
`"Sign in to confirm you're not a bot"` без авторизации. Ни один публичный
посредник (ssyoutube, cobalt) не решает проблему с нашего IP.

**Единственное рабочее решение:** куки от реального Google-аккаунта + автоматический
refresh через Playwright. Куки из авторизованной сессии живут намного дольше, чем
анонимные, а Playwright поддерживает сессию живой без ручного вмешательства.

**Ключевое наблюдение:** Playwright успешно загружает YouTube с нашего VPS —
проблема не в загрузке страниц, а только в player API запросах yt-dlp без куков.

---

## Архитектура

```text
PlaywrightCookieManager (новый)
    Playwright Chromium (persistent storage state)
    → ~/.config/datahive/yt_storage_state.json  (session + cookies)
    → downloads/yt_cookies.txt                   (Netscape format → yt-dlp)
    → фоновый таск: refresh каждые 4 ч

ProductionYouTubeGrabber (модифицируется)
    yt-dlp --cookies yt_cookies.txt

YouTubeBaseDownloader (модифицируется)
    strategies: [ProductionYouTubeGrabber]   ← ExternalSiteGrabber убирается

main.py (модифицируется)
    asyncio.create_task(cookie_manager.start_background_refresh())

scripts/youtube_auth_setup.py (новый)
    Одноразовый скрипт: открывает видимый браузер, пользователь логинится вручную,
    сохраняет storage state
```

---

## Компоненты

### 1. `PlaywrightCookieManager`

**Файл:** `src/modules/youtube_cookie_manager.py`

**Ответственность:** поддерживать живую Playwright-сессию YouTube, экспортировать
куки в Netscape-формат для yt-dlp.

```python
class PlaywrightCookieManager:
    def __init__(
        self,
        storage_state_path: Path,   # ~/.config/datahive/yt_storage_state.json
        cookie_file_path: Path,     # downloads/yt_cookies.txt
        refresh_interval: int = 4 * 3600,  # секунды
    ) -> None: ...

    async def refresh_cookies(self) -> bool:
        """
        Открывает Playwright-браузер с сохранённой сессией, заходит на youtube.com,
        экспортирует куки в Netscape-формат. Возвращает True если сессия жива.
        Если сессия сдохла (редирект на /login) — возвращает False и логирует warning.
        """

    async def start_background_refresh(self) -> None:
        """Бесконечный цикл: refresh каждые refresh_interval секунд."""

    def is_configured(self) -> bool:
        """True если storage_state_path существует."""

    def get_cookie_file(self) -> Path | None:
        """Путь к cookie-файлу, если он существует и не пустой."""
```

**Детали экспорта куков:** Playwright хранит куки в storage state (JSON). Для yt-dlp
нужен Netscape-формат (`# Netscape HTTP Cookie File\n<domain>\t<flag>\t...`).
Преобразование: из `context.cookies()` в текстовый файл.

**Детали определения живости сессии:** после `page.goto('https://youtube.com')`,
проверяем `page.url` — если редиректнуло на `accounts.google.com` → сессия мертва.

---

### 2. Скрипт первоначальной авторизации

**Файл:** `scripts/youtube_auth_setup.py`

```python
# Запускается вручную один раз:
# python3 scripts/youtube_auth_setup.py

async def main():
    """
    Открывает ВИДИМЫЙ (не headless) браузер.
    Пользователь логинится в Google аккаунт.
    После успешного входа (URL = youtube.com) — сохраняет storage state.
    Печатает инструкции и ждёт нажатия Enter.
    """
```

---

### 3. Изменения в `ProductionYouTubeGrabber`

**Файл:** `src/modules/youtube_grabber_v2.py`

`download_video()` и `get_metadata()` получают опциональный `cookie_file: Path | None`.
Если задан — добавляет `--cookies <path>` в yt-dlp args.

---

### 4. Изменения в `YouTubeBaseDownloader`

**Файл:** `src/modules/youtube_downloader_base.py`

- Конструктор принимает `cookie_manager: PlaywrightCookieManager | None`
- `strategies` теперь только `[self.grabber]` (ExternalSiteGrabber убран)
- При вызове `_run_strategy_chain` передаёт `cookie_file` из `cookie_manager.get_cookie_file()`

---

### 5. Изменения в `BotConfig`

**Файл:** `src/bot/config.py`

```python
youtube_auth_dir: Path = Field(
    Path.home() / ".config/datahive",
    alias="YOUTUBE_AUTH_DIR"
)
```

---

### 6. Изменения в `main.py`

При старте бота:
1. Инициализировать `PlaywrightCookieManager` 
2. Если `is_configured()` → сразу вызвать `refresh_cookies()` (без ожидания 4 ч)
3. Запустить фоновый таск `start_background_refresh()`
4. Если НЕ configured → логировать INFO о необходимости запустить `youtube_auth_setup.py`

---

## Data Flow

```text
[Одноразово]
scripts/youtube_auth_setup.py
    → visible browser → пользователь логинится
    → storage_state.json сохранён

[При старте бота / каждые 4 ч]
PlaywrightCookieManager.refresh_cookies()
    → headless browser + storage_state.json
    → youtube.com (сессия живая)
    → context.cookies() → Netscape format → yt_cookies.txt

[При скачивании видео]
YouTubeBaseDownloader._run_strategy_chain(url)
    → ProductionYouTubeGrabber.download_video(url, ..., cookie_file=yt_cookies.txt)
        → yt-dlp --cookies yt_cookies.txt <url>
            → YouTube принимает запрос (авторизованный аккаунт)
            → format URLs подписаны нашим VPS IP
            → скачивание работает
```

---

## Error Handling

| Ситуация | Поведение |
|---|---|
| `youtube_auth_setup.py` не запускался | WARNING в логах, скачивание продолжается без куков (может провалиться) |
| Сессия протухла | WARNING + рекомендация перезапустить `youtube_auth_setup.py` |
| Playwright не может открыть браузер | WARNING + скачивание без куков |
| yt-dlp с куками провалился | DownloadError → бот уведомляет пользователя |

---

## Тестирование

- `tests/test_youtube_cookie_manager.py`:
  - Мокировать `async_playwright` — проверить что cookies экспортируются в правильный Netscape-формат
  - Проверить определение мёртвой сессии (мок redirect на accounts.google.com)
  - Проверить `is_configured()` с/без storage_state файла

- Ручная проверка:
  1. Запустить `scripts/youtube_auth_setup.py`, залогиниться
  2. Запустить `python3 -c "import asyncio; from src.modules.youtube_cookie_manager import PlaywrightCookieManager; ..."`
  3. Убедиться, что куки экспортируются
  4. Проверить `yt-dlp --cookies yt_cookies.txt https://www.youtube.com/watch?v=...`

---

## Files Changed

| Файл | Действие |
|---|---|
| `src/modules/youtube_cookie_manager.py` | Создать |
| `src/modules/youtube_grabber_v2.py` | Модифицировать: добавить cookie_file |
| `src/modules/youtube_downloader_base.py` | Модифицировать: убрать ExternalSiteGrabber, добавить cookie_manager |
| `src/bot/config.py` | Добавить youtube_auth_dir |
| `src/main.py` | Добавить инициализацию и фоновый таск |
| `scripts/youtube_auth_setup.py` | Создать |
| `tests/test_youtube_cookie_manager.py` | Создать |
