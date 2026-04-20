# YouTube Cookie Auto-Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить ручное обновление YouTube-куков — Playwright сам генерирует и обновляет их каждые 4 часа из сохранённой сессии.

**Architecture:** `PlaywrightCookieManager` хранит Playwright storage state (сессию Google-аккаунта), периодически открывает headless YouTube, экспортирует куки в Netscape-файл. `ProductionYouTubeGrabber` уже использует `ImprovedCookieManager` — достаточно добавить новый файл в его пул. `ExternalSiteGrabber` убирается из цепочки стратегий.

**Tech Stack:** Playwright (async_playwright), yt-dlp, aiogram 3.x, asyncio, structlog.

---

## File Map

| Файл | Действие |
|---|---|
| `src/modules/youtube_cookie_manager.py` | **Создать** — PlaywrightCookieManager |
| `scripts/youtube_auth_setup.py` | **Создать** — одноразовый скрипт логина |
| `src/bot/config.py` | **Изменить** — добавить `youtube_auth_dir` |
| `src/modules/youtube_downloader_base.py` | **Изменить** — убрать ExternalSiteGrabber из strategies, добавить PlaywrightCookieManager |
| `src/bot/main.py` | **Изменить** — запускать фоновый refresh |
| `tests/test_youtube_cookie_manager.py` | **Создать** — юнит-тесты |

---

## Task 1: PlaywrightCookieManager — экспорт куков

**Files:**
- Create: `src/modules/youtube_cookie_manager.py`
- Test: `tests/test_youtube_cookie_manager.py`

- [ ] **Step 1.1: Написать failing тест на экспорт куков в Netscape-формат**

```python
# tests/test_youtube_cookie_manager.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def test_cookies_to_netscape_format():
    """Конвертация playwright cookies → Netscape HTTP Cookie File"""
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    manager = PlaywrightCookieManager(
        storage_state_path=Path("/tmp/state.json"),
        cookie_file_path=Path("/tmp/cookies.txt"),
    )

    playwright_cookies = [
        {
            "name": "CONSENT",
            "value": "YES+",
            "domain": ".youtube.com",
            "path": "/",
            "expires": 1999999999.0,
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "YSC",
            "value": "abc123",
            "domain": ".youtube.com",
            "path": "/",
            "expires": -1,  # session cookie
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
    ]

    result = manager._cookies_to_netscape(playwright_cookies)

    assert result.startswith("# Netscape HTTP Cookie File\n")
    assert ".youtube.com\tTRUE\t/\tTRUE\t1999999999\tCONSENT\tYES+" in result
    # Session cookies (expires=-1) получают expires=0
    assert ".youtube.com\tTRUE\t/\tTRUE\t0\tYSC\tabc123" in result
```

- [ ] **Step 1.2: Запустить тест и убедиться что FAILED**

```bash
venv/bin/pytest tests/test_youtube_cookie_manager.py::test_cookies_to_netscape_format -v
```
Ожидаем: `ImportError: cannot import name 'PlaywrightCookieManager'`

- [ ] **Step 1.3: Создать `src/modules/youtube_cookie_manager.py`**

```python
"""
PlaywrightCookieManager — автоматическое обновление YouTube-куков.

Playwright хранит сессию Google-аккаунта в storage state.
При refresh: открывает headless YouTube, экспортирует куки в Netscape-формат.
"""

import asyncio
from pathlib import Path

import structlog
from playwright.async_api import async_playwright

logger = structlog.get_logger("datahive.youtube_cookie_manager")


class PlaywrightCookieManager:
    """Поддерживает YouTube-куки актуальными через Playwright-сессию."""

    def __init__(
        self,
        storage_state_path: Path,
        cookie_file_path: Path,
        refresh_interval: int = 4 * 3600,
    ) -> None:
        self.storage_state_path = storage_state_path
        self.cookie_file_path = cookie_file_path
        self.refresh_interval = refresh_interval

    def is_configured(self) -> bool:
        """True если storage state существует (пользователь уже логинился)."""
        return self.storage_state_path.exists()

    def _cookies_to_netscape(self, cookies: list[dict]) -> str:
        """
        Конвертирует список Playwright-куков в Netscape HTTP Cookie File формат.

        Формат строки: domain flag path secure expires name value
        (разделители — табуляции)
        """
        lines = ["# Netscape HTTP Cookie File", ""]
        for c in cookies:
            domain = c["domain"]
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure") else "FALSE"
            expires_raw = c.get("expires", -1)
            # Session cookies (expires=-1 или None) → 0
            expires = int(expires_raw) if expires_raw and expires_raw > 0 else 0
            name = c["name"]
            value = c["value"]
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
        return "\n".join(lines) + "\n"

    async def refresh_cookies(self) -> bool:
        """
        Открывает headless Playwright с сохранённой сессией, заходит на YouTube,
        экспортирует куки в Netscape-формат.

        Returns:
            True — сессия жива и куки экспортированы.
            False — сессия умерла (редирект на login).
        """
        if not self.is_configured():
            logger.warning(
                "YouTube storage state не найден. "
                "Запустите: python3 scripts/youtube_auth_setup.py"
            )
            return False

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    storage_state=str(self.storage_state_path)
                )
                page = await context.new_page()

                await page.goto(
                    "https://www.youtube.com",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

                # Если редирект на accounts.google.com → сессия умерла
                if "accounts.google.com" in page.url:
                    logger.warning(
                        "YouTube-сессия истекла. "
                        "Перелогиньтесь: python3 scripts/youtube_auth_setup.py"
                    )
                    await context.close()
                    await browser.close()
                    return False

                cookies = await context.cookies()
                netscape = self._cookies_to_netscape(cookies)

                self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
                self.cookie_file_path.write_text(netscape, encoding="utf-8")

                # Обновляем storage state (продлеваем сессию)
                await context.storage_state(path=str(self.storage_state_path))

                await context.close()
                await browser.close()

            logger.info(
                "YouTube-куки обновлены",
                cookie_count=len(cookies),
                path=str(self.cookie_file_path),
            )
            return True

        except Exception as exc:
            logger.warning("Ошибка обновления YouTube-куков", error=str(exc))
            return False

    async def start_background_refresh(self) -> None:
        """Бесконечный цикл: refresh каждые refresh_interval секунд."""
        while True:
            await self.refresh_cookies()
            await asyncio.sleep(self.refresh_interval)
```

- [ ] **Step 1.4: Запустить тест — должен пройти**

```bash
venv/bin/pytest tests/test_youtube_cookie_manager.py::test_cookies_to_netscape_format -v
```
Ожидаем: `PASSED`

- [ ] **Step 1.5: Commit**

```bash
git add src/modules/youtube_cookie_manager.py tests/test_youtube_cookie_manager.py
git commit -m "feat: add PlaywrightCookieManager with Netscape cookie export"
```

---

## Task 2: PlaywrightCookieManager — refresh и живость сессии

- [ ] **Step 2.1: Написать тест на определение мёртвой сессии**

```python
# tests/test_youtube_cookie_manager.py — добавить:

@pytest.mark.asyncio
async def test_refresh_detects_dead_session(tmp_path):
    """Если YouTube редиректит на accounts.google.com — возвращает False"""
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    storage_state = tmp_path / "state.json"
    storage_state.write_text("{}")  # Пустой state — имитируем "сконфигурировано"
    cookie_file = tmp_path / "cookies.txt"

    manager = PlaywrightCookieManager(
        storage_state_path=storage_state,
        cookie_file_path=cookie_file,
    )

    # Мокируем Playwright
    mock_page = AsyncMock()
    mock_page.url = "https://accounts.google.com/signin/..."
    mock_page.goto = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.cookies = AsyncMock(return_value=[])

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch(
        "src.modules.youtube_cookie_manager.async_playwright",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_playwright)),
    ):
        result = await manager.refresh_cookies()

    assert result is False
    assert not cookie_file.exists()


@pytest.mark.asyncio
async def test_refresh_exports_cookies_on_live_session(tmp_path):
    """Если сессия жива — экспортирует куки и возвращает True"""
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    storage_state = tmp_path / "state.json"
    storage_state.write_text("{}")
    cookie_file = tmp_path / "cookies.txt"

    manager = PlaywrightCookieManager(
        storage_state_path=storage_state,
        cookie_file_path=cookie_file,
    )

    sample_cookies = [
        {
            "name": "CONSENT",
            "value": "YES+",
            "domain": ".youtube.com",
            "path": "/",
            "expires": 1999999999.0,
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        }
    ]

    mock_page = AsyncMock()
    mock_page.url = "https://www.youtube.com"
    mock_page.goto = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.cookies = AsyncMock(return_value=sample_cookies)
    mock_context.storage_state = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch(
        "src.modules.youtube_cookie_manager.async_playwright",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_playwright)),
    ):
        result = await manager.refresh_cookies()

    assert result is True
    assert cookie_file.exists()
    content = cookie_file.read_text()
    assert "# Netscape HTTP Cookie File" in content
    assert "CONSENT" in content


def test_is_configured_false_when_no_state(tmp_path):
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    manager = PlaywrightCookieManager(
        storage_state_path=tmp_path / "nonexistent.json",
        cookie_file_path=tmp_path / "cookies.txt",
    )
    assert manager.is_configured() is False


def test_is_configured_true_when_state_exists(tmp_path):
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    state = tmp_path / "state.json"
    state.write_text("{}")
    manager = PlaywrightCookieManager(
        storage_state_path=state,
        cookie_file_path=tmp_path / "cookies.txt",
    )
    assert manager.is_configured() is True
```

- [ ] **Step 2.2: Установить pytest-asyncio**

```bash
venv/bin/pip install pytest-asyncio
```

- [ ] **Step 2.3: Запустить тесты — должны пройти**

```bash
venv/bin/pytest tests/test_youtube_cookie_manager.py -v
```
Ожидаем: все 5 тестов `PASSED`

- [ ] **Step 2.4: Commit**

```bash
git add tests/test_youtube_cookie_manager.py
git commit -m "test: add PlaywrightCookieManager session and refresh tests"
```

---

## Task 3: BotConfig — добавить youtube_auth_dir

**Files:**
- Modify: `src/bot/config.py`

- [ ] **Step 3.1: Добавить поле в BotConfig**

В [src/bot/config.py](src/bot/config.py), после блока `# External Site Grabber`, добавить:

```python
    # YouTube Cookie Auto-Refresh
    youtube_auth_dir: Path = Field(
        Path.home() / ".config" / "datahive",
        alias="YOUTUBE_AUTH_DIR",
    )
```

Полный блок:
```python
    # External Site Grabber (YouTube bypass)
    external_site_url: str = Field(
        "https://en.ssyoutube.com/", alias="EXTERNAL_SITE_URL"
    )
    external_site_timeout_ms: int = Field(30_000, alias="EXTERNAL_SITE_TIMEOUT_MS")

    # YouTube Cookie Auto-Refresh
    youtube_auth_dir: Path = Field(
        Path.home() / ".config" / "datahive",
        alias="YOUTUBE_AUTH_DIR",
    )
```

- [ ] **Step 3.2: Убедиться что конфиг импортируется без ошибок**

```bash
venv/bin/python3 -c "from src.bot.config import BotConfig; c = BotConfig(); print(c.youtube_auth_dir)"
```
Ожидаем: путь типа `/home/lexey/.config/datahive`

- [ ] **Step 3.3: Commit**

```bash
git add src/bot/config.py
git commit -m "feat: add youtube_auth_dir to BotConfig"
```

---

## Task 4: Скрипт первоначальной авторизации

**Files:**
- Create: `scripts/youtube_auth_setup.py`

- [ ] **Step 4.1: Создать `scripts/youtube_auth_setup.py`**

```bash
mkdir -p scripts
```

```python
#!/usr/bin/env python3
"""
Одноразовый скрипт для авторизации YouTube.

Открывает ВИДИМЫЙ браузер. Пользователь логинится в Google.
После входа storage state (сессия) сохраняется автоматически.

Запуск:
    python3 scripts/youtube_auth_setup.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright


async def main() -> None:
    from src.bot.config import BotConfig

    config = BotConfig()
    auth_dir = config.youtube_auth_dir
    auth_dir.mkdir(parents=True, exist_ok=True)

    storage_state_path = auth_dir / "yt_storage_state.json"

    print("=" * 60)
    print("YouTube Auth Setup")
    print("=" * 60)
    print()
    print("Откроется браузер. Войдите в Google-аккаунт на YouTube.")
    print("После входа нажмите Enter в этом терминале.")
    print()
    input("Нажмите Enter чтобы открыть браузер...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        # Загружаем существующий state если есть
        if storage_state_path.exists():
            print(f"Загружаем существующую сессию из {storage_state_path}")
            context = await browser.new_context(
                storage_state=str(storage_state_path)
            )
        else:
            context = await browser.new_context()

        page = await context.new_page()
        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")

        print()
        print("Залогиньтесь в браузере, затем вернитесь сюда.")
        input("Нажмите Enter когда будете на youtube.com после входа...")

        # Даём странице загрузиться
        await asyncio.sleep(2)

        # Сохраняем storage state
        await context.storage_state(path=str(storage_state_path))
        print(f"✅ Сессия сохранена: {storage_state_path}")

        await context.close()
        await browser.close()

    # Сразу делаем первый refresh
    print()
    print("Делаем первый refresh куков...")
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    cookie_file = auth_dir / "yt_cookies.txt"
    manager = PlaywrightCookieManager(
        storage_state_path=storage_state_path,
        cookie_file_path=cookie_file,
    )
    success = await manager.refresh_cookies()

    if success:
        print(f"✅ Куки сохранены: {cookie_file}")
        print()
        print("Готово! Теперь запустите бота — он будет автоматически обновлять куки.")
    else:
        print("❌ Не удалось получить куки. Проверьте что вы вошли в аккаунт.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4.2: Сделать файл исполняемым**

```bash
chmod +x scripts/youtube_auth_setup.py
```

- [ ] **Step 4.3: Проверить что скрипт импортируется без ошибок**

```bash
venv/bin/python3 -c "import ast; ast.parse(open('scripts/youtube_auth_setup.py').read()); print('OK')"
```
Ожидаем: `OK`

- [ ] **Step 4.4: Commit**

```bash
git add scripts/youtube_auth_setup.py
git commit -m "feat: add youtube_auth_setup.py interactive login script"
```

---

## Task 5: YouTubeBaseDownloader — убрать ExternalSiteGrabber, добавить PlaywrightCookieManager

**Files:**
- Modify: `src/modules/youtube_downloader_base.py`

- [ ] **Step 5.1: Прочитать текущий файл**

```bash
cat src/modules/youtube_downloader_base.py
```

- [ ] **Step 5.2: Обновить `YouTubeBaseDownloader.__init__`**

Заменить весь файл `src/modules/youtube_downloader_base.py`:

```python
"""
Base class for YouTube downloaders, providing shared strategy-chain logic.
"""
import asyncio
import inspect
from pathlib import Path
from typing import Optional

import structlog

from .downloader_base import BaseDownloader, DownloadError, DownloadSettings
from .youtube_grabber_base import YouTubeDownloadStrategy
from .youtube_grabber_v2 import ImprovedCookieManager, ProductionYouTubeGrabber
from .youtube_cookie_manager import PlaywrightCookieManager


logger = structlog.get_logger(__name__)

_COOKIE_REFRESH_INTERVAL = 4 * 3600  # секунды


class YouTubeBaseDownloader(BaseDownloader):
    """Base class for YouTube downloaders with strategy chain support."""

    def __init__(
        self,
        settings: DownloadSettings,
        output_dir: Optional[Path] = None,
        playwright_cookie_manager: Optional[PlaywrightCookieManager] = None,
    ) -> None:
        super().__init__(settings, output_dir)

        # Cookie manager setup
        cookie_manager = None
        if settings.youtube_cookies_dir:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies_dir
            )
            for cookie_file in settings.youtube_cookies_dir.glob("youtube_cookies*.txt"):
                cookie_manager.add_cookies(cookie_file)
        elif settings.youtube_cookies:
            cookie_manager = ImprovedCookieManager(
                cookies_dir=settings.youtube_cookies.parent
            )
            cookie_manager.add_cookies(settings.youtube_cookies)

        # Если передан PlaywrightCookieManager — добавляем его куки в пул
        self._playwright_cookie_manager = playwright_cookie_manager
        if playwright_cookie_manager and playwright_cookie_manager.is_configured():
            if cookie_manager is None:
                cookie_file = playwright_cookie_manager.cookie_file_path
                cookie_manager = ImprovedCookieManager(
                    cookies_dir=cookie_file.parent
                )
            if playwright_cookie_manager.cookie_file_path.exists():
                cookie_manager.add_cookies(playwright_cookie_manager.cookie_file_path)

        self.grabber = ProductionYouTubeGrabber(cookie_manager=cookie_manager)

    @property
    def strategies(self) -> list[YouTubeDownloadStrategy]:
        # ExternalSiteGrabber убран: googlevideo.com URLs привязаны к IP стороннего сервиса
        return [self.grabber]

    async def _call_strategy(
        self,
        strategy: YouTubeDownloadStrategy,
        url: str,
        output_dir: Path,
        quality: str,
    ) -> Path:
        """Вызывает стратегию, определяя sync/async реализацию."""
        if inspect.iscoroutinefunction(strategy.download_video):
            return await strategy.download_video(url, output_dir, quality)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, strategy.download_video, url, output_dir, quality
            )

    async def _run_strategy_chain(self, url: str, output_dir: Path, quality: str) -> Path:
        """Перебирает стратегии по цепочке; поднимает DownloadError если все не сработали."""
        last_error: Optional[Exception] = None
        for strategy in self.strategies:
            try:
                path = await self._call_strategy(strategy, url, output_dir, quality)
                logger.info(
                    "Стратегия загрузки сработала",
                    strategy=type(strategy).__name__,
                    url=url,
                )
                return path
            except Exception as e:
                logger.warning(
                    "Стратегия загрузки не сработала, переходим к следующей",
                    strategy=type(strategy).__name__,
                    error=str(e),
                )
                last_error = e
        raise DownloadError(f"Все стратегии загрузки не сработали для {url}") from last_error
```

- [ ] **Step 5.3: Проверить что файл импортируется без ошибок**

```bash
venv/bin/python3 -c "from src.modules.youtube_downloader_base import YouTubeBaseDownloader; print('OK')"
```
Ожидаем: `OK`

- [ ] **Step 5.4: Запустить существующие тесты**

```bash
venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```
Убеждаемся что существующие тесты не сломались.

- [ ] **Step 5.5: Commit**

```bash
git add src/modules/youtube_downloader_base.py
git commit -m "refactor: remove ExternalSiteGrabber from strategy chain, add PlaywrightCookieManager support"
```

---

## Task 6: Интеграция в src/bot/main.py

**Files:**
- Modify: `src/bot/main.py`

- [ ] **Step 6.1: Обновить `src/bot/main.py`**

Добавить инициализацию `PlaywrightCookieManager` и фоновый таск в функцию `main()`.

Найти в [src/bot/main.py](src/bot/main.py) строку `config = BotConfig()` и добавить после неё:

```python
    config = BotConfig()

    # YouTube Cookie Auto-Refresh
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    auth_dir = config.youtube_auth_dir
    auth_dir.mkdir(parents=True, exist_ok=True)
    playwright_cookie_manager = PlaywrightCookieManager(
        storage_state_path=auth_dir / "yt_storage_state.json",
        cookie_file_path=auth_dir / "yt_cookies.txt",
    )

    if playwright_cookie_manager.is_configured():
        logger.info("YouTube: запускаем первичный refresh куков...")
        await playwright_cookie_manager.refresh_cookies()
    else:
        logger.info(
            "YouTube: storage state не настроен. "
            "Для авторизации запустите: python3 scripts/youtube_auth_setup.py"
        )
```

Найти строку `await init_db()` и добавить перед `if config.webhook_mode:` фоновый таск:

```python
    # Запускаем фоновый refresh куков
    asyncio.create_task(playwright_cookie_manager.start_background_refresh())
```

Полная функция `main()` после изменений:

```python
async def main() -> None:
    config = BotConfig()

    # YouTube Cookie Auto-Refresh
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    auth_dir = config.youtube_auth_dir
    auth_dir.mkdir(parents=True, exist_ok=True)
    playwright_cookie_manager = PlaywrightCookieManager(
        storage_state_path=auth_dir / "yt_storage_state.json",
        cookie_file_path=auth_dir / "yt_cookies.txt",
    )

    if playwright_cookie_manager.is_configured():
        logger.info("YouTube: запускаем первичный refresh куков...")
        await playwright_cookie_manager.refresh_cookies()
    else:
        logger.info(
            "YouTube: storage state не настроен. "
            "Для авторизации запустите: python3 scripts/youtube_auth_setup.py"
        )

    # Инициализация БД очереди задач
    await init_db()

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    from src.bot.routers import base, content, worker_cmds
    from src.bot.routers.wiki_cmds import router as wiki_router
    from src.bot.middlewares.auth import AdminAccessMiddleware

    dp.include_router(base.router)
    dp.include_router(content.router)
    dp.include_router(worker_cmds.router)
    dp.include_router(wiki_router)

    dp.update.outer_middleware(AdminAccessMiddleware())
    dp["config"] = config
    dp["playwright_cookie_manager"] = playwright_cookie_manager

    # Запускаем фоновый refresh куков
    asyncio.create_task(playwright_cookie_manager.start_background_refresh())

    if config.webhook_mode:
        # ... остальной код без изменений
```

- [ ] **Step 6.2: Проверить что main.py импортируется без ошибок**

```bash
venv/bin/python3 -c "import ast; ast.parse(open('src/bot/main.py').read()); print('OK')"
```
Ожидаем: `OK`

- [ ] **Step 6.3: Commit**

```bash
git add src/bot/main.py
git commit -m "feat: start PlaywrightCookieManager background refresh on bot startup"
```

---

## Task 7: Сквозная проверка

- [ ] **Step 7.1: Запустить все тесты**

```bash
venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -40
```
Ожидаем: все тесты `PASSED`.

- [ ] **Step 7.2: Проверить что yt-dlp работает с куками из Playwright-сессии**

Запустить auth setup (один раз — интерактивно):
```bash
venv/bin/python3 scripts/youtube_auth_setup.py
```
Следовать инструкциям: залогиниться в Google.

- [ ] **Step 7.3: Проверить скачивание с куками**

```bash
# Убедиться что куки созданы
ls -la ~/.config/datahive/yt_cookies.txt

# Проверить yt-dlp с куками
venv/bin/python3 -m yt_dlp \
  --cookies ~/.config/datahive/yt_cookies.txt \
  --skip-download --print "%(title)s" \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```
Ожидаем: `Me at the zoo` (без ошибки "Sign in to confirm")

- [ ] **Step 7.4: Финальный commit**

```bash
git add -A
git commit -m "feat: YouTube cookie auto-refresh via Playwright — complete implementation"
```

---

## Примечания по эксплуатации

**Первоначальная настройка (один раз на сервере):**
```bash
venv/bin/python3 scripts/youtube_auth_setup.py
```
Нужен графический дисплей или X11 forwarding (`ssh -X`). Альтернатива: запустить локально, скопировать `yt_storage_state.json` на VPS.

**Когда сессия протухнет** (видно по WARNING в логах):
```bash
venv/bin/python3 scripts/youtube_auth_setup.py
# Затем перезапустить бота — reload куков произойдёт автоматически
```

**Переменная окружения** для нестандартного пути:
```
YOUTUBE_AUTH_DIR=/path/to/custom/dir
```
