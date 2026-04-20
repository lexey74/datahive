#!/usr/bin/env python3
"""
Одноразовый скрипт для авторизации YouTube.

Режимы запуска:

  1. Браузер (локально или SSH с X11):
     python3 scripts/youtube_auth_setup.py

  2. VPS без GUI — из готового cookies.txt (экспорт из Chrome):
     python3 scripts/youtube_auth_setup.py --from-cookies /path/to/cookies.txt

     Как получить cookies.txt на маке:
       1. Установи расширение "Get cookies.txt LOCALLY" в Chrome
       2. Зайди на youtube.com (будучи залогиненным)
       3. Нажми расширение → Export → "cookies.txt (Netscape)"
       4. scp ~/Downloads/youtube.com_cookies.txt lexey@38.242.141.28:/tmp/
       5. python3 scripts/youtube_auth_setup.py --from-cookies /tmp/youtube.com_cookies.txt
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


async def _browser_auth(auth_dir: Path, storage_state_path: Path) -> None:
    """Авторизация через видимый браузер (требует GUI или X11)."""
    from playwright.async_api import async_playwright

    print("Откроется браузер. Войдите в Google-аккаунт на YouTube.")
    print()
    input("Нажмите Enter чтобы открыть браузер...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

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

        await asyncio.sleep(2)
        await context.storage_state(path=str(storage_state_path))
        print(f"Сессия сохранена: {storage_state_path}")

        await context.close()
        await browser.close()


def _netscape_to_playwright(cookies_txt: Path) -> list[dict]:
    """
    Конвертирует Netscape cookies.txt в список Playwright-совместимых куков.
    Используется для создания начального storage state из экспорта браузера.
    """
    cookies = []
    for line in cookies_txt.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            continue
        domain, flag, path, secure, expires, name, value = parts
        try:
            expires_int = int(expires)
        except ValueError:
            expires_int = 0
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "expires": expires_int if expires_int > 0 else -1,
            "httpOnly": False,
            "secure": secure.upper() == "TRUE",
            "sameSite": "None",
        })
    return cookies


def _create_storage_state(cookies: list[dict], storage_state_path: Path) -> None:
    """Создаёт минимальный Playwright storage state из списка куков."""
    # Группируем origins по домену для Playwright
    origin_map: dict[str, list[dict]] = {}
    for c in cookies:
        domain = c["domain"].lstrip(".")
        scheme = "https" if c["secure"] else "http"
        origin = f"{scheme}://{domain}"
        origin_map.setdefault(origin, []).append({
            "name": c["name"],
            "value": c["value"],
        })

    origins = [
        {"origin": origin, "localStorage": []}
        for origin in origin_map
    ]

    state = {
        "cookies": cookies,
        "origins": origins,
    }
    storage_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


async def _from_cookies_auth(cookies_txt_path: Path, auth_dir: Path, storage_state_path: Path) -> None:
    """
    Создаёт storage state из готового cookies.txt (экспорт из Chrome/Firefox).
    Затем делает headless refresh через Playwright для проверки сессии.
    """
    print(f"Читаю куки из: {cookies_txt_path}")
    cookies = _netscape_to_playwright(cookies_txt_path)
    print(f"Найдено куков: {len(cookies)}")

    if not cookies:
        print("Файл пустой или неверный формат (ожидается Netscape HTTP Cookie File).")
        sys.exit(1)

    _create_storage_state(cookies, storage_state_path)
    print(f"Storage state создан: {storage_state_path}")


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

    # Режим --from-cookies
    if "--from-cookies" in sys.argv:
        idx = sys.argv.index("--from-cookies")
        if idx + 1 >= len(sys.argv):
            print("Ошибка: укажи путь к cookies.txt после --from-cookies")
            sys.exit(1)
        cookies_txt_path = Path(sys.argv[idx + 1])
        if not cookies_txt_path.exists():
            print(f"Файл не найден: {cookies_txt_path}")
            sys.exit(1)
        await _from_cookies_auth(cookies_txt_path, auth_dir, storage_state_path)
    else:
        await _browser_auth(auth_dir, storage_state_path)

    # Первый headless refresh куков
    print()
    print("Проверяем сессию (headless refresh)...")
    from src.modules.youtube_cookie_manager import PlaywrightCookieManager

    cookie_file = auth_dir / "yt_cookies.txt"
    manager = PlaywrightCookieManager(
        storage_state_path=storage_state_path,
        cookie_file_path=cookie_file,
    )
    success = await manager.refresh_cookies()

    if success:
        print(f"Куки сохранены: {cookie_file}")
        print()
        print("Готово! Бот будет автоматически обновлять куки каждые 4 часа.")
    else:
        print()
        print("Сессия истекла или куки невалидны.")
        print("Попробуй заново — экспортируй свежие куки из браузера.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
