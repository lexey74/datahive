"""
Загрузчик YouTube-видео через внешний сайт-посредник (ssyoutube.com).
Используется для обхода блокировок IP на VPS.
"""

import logging
from pathlib import Path
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("datahive.external_site_grabber")

BASE_URL = "https://en.ssyoutube.com/en/download"


class ExternalSiteError(Exception):
    """Raised when external site grabber fails"""
    pass


class ExternalSiteGrabber:
    """Загружает YouTube-видео через внешний сайт ssyoutube.com."""

    def __init__(self, timeout_ms: int = 30_000) -> None:
        self.timeout_ms = timeout_ms

    async def download_video(
        self,
        url: str,
        output_dir: Path,
        quality: str = "best",
    ) -> Path:
        """
        Скачивает YouTube-видео через ssyoutube.com.

        Args:
            url: URL YouTube-видео
            output_dir: Директория для сохранения файла
            quality: Желаемое качество ('best' или конкретное разрешение)

        Returns:
            Путь к скачанному файлу

        Raises:
            ExternalSiteError: При любой ошибке загрузки
        """
        logger.debug("Начинаем загрузку через внешний сайт: %s", url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                target_url = f"{BASE_URL}?url={quote(url)}"
                await page.goto(target_url)

                try:
                    await page.wait_for_selector(
                        ".download-links",
                        timeout=self.timeout_ms,
                    )
                except PlaywrightTimeoutError as exc:
                    logger.warning(
                        "Таймаут ожидания .download-links для %s: %s", url, exc
                    )
                    raise ExternalSiteError(
                        f"Таймаут при ожидании ссылок для скачивания: {url}"
                    ) from exc

                # Собираем все mp4-ссылки и выбираем наилучшее качество
                download_url = await self._find_best_mp4_link(page, quality)
                if not download_url:
                    logger.warning(
                        "Не найдено подходящих mp4-ссылок для %s", url
                    )
                    raise ExternalSiteError(
                        f"Не найдено mp4-ссылок для скачивания: {url}"
                    )

                logger.info("Найдена ссылка для скачивания, начинаем загрузку файла")

                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / "video.mp4"

                await self._stream_download(download_url, output_path)
                return output_path

            finally:
                await browser.close()

    async def _find_best_mp4_link(
        self, page: object, quality: str
    ) -> str | None:
        """
        Ищет лучшую mp4-ссылку на странице.

        Args:
            page: Playwright Page объект
            quality: Желаемое качество

        Returns:
            URL для скачивания или None
        """
        # Получаем все ссылки внутри .download-links
        links = await page.query_selector_all(".download-links a[href]")  # type: ignore[attr-defined]

        candidates: list[tuple[int, str]] = []

        for link in links:
            href: str | None = await link.get_attribute("href")
            if not href or "mp4" not in href.lower():
                # Проверяем data-quality или текст кнопки
                data_quality: str | None = await link.get_attribute("data-quality")
                text: str = (await link.inner_text()).lower()
                if "mp4" not in text and not data_quality:
                    continue
                if not href:
                    continue

            # Пытаемся определить разрешение
            resolution = 0
            data_quality = await link.get_attribute("data-quality")
            if data_quality:
                try:
                    resolution = int(data_quality.replace("p", ""))
                except ValueError:
                    pass

            if resolution == 0:
                # Ищем в тексте кнопки
                text = (await link.inner_text()).lower()
                for res in (2160, 1440, 1080, 720, 480, 360, 240, 144):
                    if str(res) in text:
                        resolution = res
                        break

            candidates.append((resolution, href))

        if not candidates:
            return None

        # Сортируем по убыванию разрешения
        candidates.sort(key=lambda x: x[0], reverse=True)

        if quality == "best":
            return candidates[0][1]

        # Пытаемся найти конкретное качество
        requested_res = 0
        try:
            requested_res = int(quality.replace("p", ""))
        except ValueError:
            pass

        if requested_res:
            for res, href in candidates:
                if res == requested_res:
                    return href

        # Возвращаем лучшее доступное
        return candidates[0][1]

    async def _stream_download(self, url: str, output_path: Path) -> None:
        """
        Потоковая загрузка файла через httpx.

        Args:
            url: URL файла для скачивания
            output_path: Путь для сохранения

        Raises:
            ExternalSiteError: При HTTP-ошибке
        """
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=300.0) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code >= 400:
                        logger.warning(
                            "HTTP ошибка %d при загрузке файла", response.status_code
                        )
                        raise ExternalSiteError(
                            f"HTTP ошибка {response.status_code} при загрузке видео"
                        )
                    with output_path.open("wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
        except httpx.HTTPError as exc:
            logger.warning("Ошибка HTTP при загрузке файла: %s", exc)
            raise ExternalSiteError(f"Ошибка при загрузке видео: {exc}") from exc
