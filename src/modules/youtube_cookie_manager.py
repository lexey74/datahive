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
