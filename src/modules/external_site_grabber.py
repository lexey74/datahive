"""
Загрузчик YouTube-видео через внешний сайт-посредник (ssyoutube.com).
Используется для обхода блокировок IP на VPS.

Алгоритм:
  1. Открыть страницу ssyoutube.com
  2. Перехватить AJAX-ответ от api-wh.ssyoutube.com/api/convert
  3. Заполнить форму URL и отправить
  4. Из API-ответа выбрать лучший mp4-поток (isBundle=True, max qualityNumber)
  5. Скачать файл через httpx
"""

import asyncio
from pathlib import Path

import httpx
import structlog
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = structlog.get_logger("datahive.external_site_grabber")

# Таймаут ожидания API-ответа в секундах
_API_WAIT_TIMEOUT = 30.0


class ExternalSiteError(Exception):
    """Raised when external site grabber fails"""
    pass


class ExternalSiteGrabber:
    """Загружает YouTube-видео через внешний сайт ssyoutube.com."""

    def __init__(self, base_url: str = "https://en.ssyoutube.com/", timeout_ms: int = 30_000) -> None:
        self.base_url = base_url
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
            quality: Желаемое качество ('best' или конкретное разрешение, напр. '720')

        Returns:
            Путь к скачанному файлу

        Raises:
            ExternalSiteError: При любой ошибке загрузки
        """
        logger.debug("Начинаем загрузку через внешний сайт", url=url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                try:
                    page = await context.new_page()

                    # Перехватываем ответ API с прямыми ссылками
                    api_future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

                    async def _on_response(response) -> None:
                        if "api-wh.ssyoutube.com/api/convert" in response.url:
                            try:
                                data = await response.json()
                                if not api_future.done():
                                    api_future.set_result(data)
                            except Exception as exc:
                                if not api_future.done():
                                    api_future.set_exception(exc)

                    page.on("response", _on_response)

                    await page.goto(self.base_url, wait_until="networkidle", timeout=self.timeout_ms)

                    # Заполняем форму и отправляем
                    await page.fill('input[name="url"]', url)
                    await page.click("form button")

                    # Ждём API-ответа
                    try:
                        api_data = await asyncio.wait_for(api_future, timeout=_API_WAIT_TIMEOUT)
                    except asyncio.TimeoutError as exc:
                        raise ExternalSiteError(
                            f"Таймаут ожидания API-ответа от ssyoutube: {url}"
                        ) from exc

                    # Выбираем лучший URL
                    download_url = self._pick_best_url(api_data, quality)
                    if not download_url:
                        raise ExternalSiteError(
                            f"Не найдено подходящих mp4-ссылок в API-ответе: {url}"
                        )

                    logger.info("Найдена ссылка для скачивания, начинаем загрузку файла")

                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = output_dir / "video.mp4"

                    await self._stream_download(download_url, output_path)
                    return output_path

                finally:
                    await context.close()
            finally:
                await browser.close()

    def _pick_best_url(self, api_data: dict, quality: str) -> str | None:
        """
        Выбирает лучший mp4-URL из API-ответа.

        Приоритет: isBundle=True (видео+аудио) с максимальным qualityNumber.
        При конкретном quality — ищем точное совпадение среди bundle-потоков,
        иначе отдаём лучший bundle.

        Args:
            api_data: Распарсенный JSON-ответ от api-wh.ssyoutube.com
            quality: 'best' или конкретное разрешение ('720', '1080', ...)

        Returns:
            URL для скачивания или None
        """
        url_list: list[dict] = api_data.get("url", [])

        # Фильтруем: только mp4 с видео+аудио (isBundle=True)
        bundles = [
            entry for entry in url_list
            if entry.get("ext") == "mp4"
            and entry.get("isBundle") is True
            and entry.get("url")
        ]

        if not bundles:
            # Запасной вариант: любой downloadable mp4
            bundles = [
                entry for entry in url_list
                if entry.get("ext") == "mp4"
                and entry.get("downloadable") is True
                and entry.get("url")
            ]

        if not bundles:
            return None

        # Сортируем по убыванию разрешения
        bundles.sort(key=lambda e: e.get("qualityNumber", 0), reverse=True)

        if quality == "best":
            return bundles[0]["url"]

        # Ищем точное совпадение по quality
        requested = quality.replace("p", "")
        for entry in bundles:
            if str(entry.get("quality", "")) == requested or str(entry.get("qualityNumber", "")) == requested:
                return entry["url"]

        # Не нашли точного — отдаём лучшее доступное
        return bundles[0]["url"]

    async def _stream_download(self, url: str, output_path: Path) -> None:
        """
        Потоковая загрузка файла через httpx.

        Args:
            url: URL файла для скачивания
            output_path: Путь для сохранения

        Raises:
            ExternalSiteError: При HTTP-ошибке
        """
        loop = asyncio.get_running_loop()
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=300.0) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    # Собираем чанки в памяти, затем записываем через executor,
                    # чтобы не блокировать event loop синхронным file I/O
                    chunks: list[bytes] = []
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        chunks.append(chunk)
                    await loop.run_in_executor(
                        None, output_path.write_bytes, b"".join(chunks)
                    )
        except httpx.HTTPStatusError as exc:
            if output_path.exists():
                output_path.unlink()
            logger.warning("HTTP ошибка при загрузке файла", status_code=exc.response.status_code, error=str(exc))
            raise ExternalSiteError(
                f"HTTP ошибка {exc.response.status_code} при загрузке видео"
            ) from exc
        except httpx.HTTPError as exc:
            if output_path.exists():
                output_path.unlink()
            logger.warning("Ошибка HTTP при загрузке файла", error=str(exc))
            raise ExternalSiteError(f"Ошибка при загрузке видео: {exc}") from exc
        except Exception:
            if output_path.exists():
                output_path.unlink()
            raise
