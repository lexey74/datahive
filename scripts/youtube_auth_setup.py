#!/usr/bin/env python3
"""
Одноразовый скрипт для авторизации YouTube.

Открывает ВИДИМЫЙ браузер. Пользователь логинится в Google.
После входа storage state (сессия) сохраняется автоматически.

Запуск:
    python3 scripts/youtube_auth_setup.py

Примечание для VPS без GUI:
    Используйте X11 forwarding: ssh -X user@server
    Или запустите скрипт локально и скопируйте yt_storage_state.json на сервер.
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
        print(f"Сессия сохранена: {storage_state_path}")

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
        print(f"Куки сохранены: {cookie_file}")
        print()
        print("Готово! Теперь запустите бота — он будет автоматически обновлять куки.")
    else:
        print("Не удалось получить куки. Проверьте что вы вошли в аккаунт.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
