"""
Тесты для ExternalSiteGrabber и цепочки стратегий YouTubeBaseDownloader.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.external_site_grabber import ExternalSiteError, ExternalSiteGrabber
from src.modules.downloader_base import DownloadError, DownloadSettings
from src.modules.youtube_downloader_base import YouTubeBaseDownloader


class _ConcreteDownloader(YouTubeBaseDownloader):
    """Минимальный конкретный подкласс для тестирования цепочки стратегий."""

    def can_handle(self, url: str) -> bool:
        return True

    def download(self, url: str):  # type: ignore[override]
        raise NotImplementedError("не используется в тестах")


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def grabber() -> ExternalSiteGrabber:
    return ExternalSiteGrabber(
        base_url="https://en.ssyoutube.com/en/download",
        timeout_ms=5_000,
    )


@pytest.fixture
def settings(tmp_path: Path) -> DownloadSettings:
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    return DownloadSettings(youtube_cookies_dir=cookies_dir)


def _make_playwright_mocks(
    *,
    wait_for_selector_side_effect=None,
    link_href: str | None = "https://example.com/video.mp4",
    link_data_quality: str | None = "720",
    links_count: int = 1,
):
    """
    Строит полную цепочку моков для async_playwright.

    Возвращает кортеж (mock_playwright_cm, mock_page, mock_links).
    """
    # Ссылки
    mock_links = []
    for _ in range(links_count):
        link = AsyncMock()
        link.get_attribute = AsyncMock(
            side_effect=lambda attr, href=link_href, dq=link_data_quality: (
                href if attr == "href" else (dq if attr == "data-quality" else None)
            )
        )
        link.inner_text = AsyncMock(return_value="720p mp4")
        mock_links.append(link)

    # Page
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=None)
    if wait_for_selector_side_effect is not None:
        mock_page.wait_for_selector = AsyncMock(
            side_effect=wait_for_selector_side_effect
        )
    else:
        mock_page.wait_for_selector = AsyncMock(return_value=None)
    mock_page.query_selector_all = AsyncMock(return_value=mock_links)
    mock_page.new_page = AsyncMock(return_value=mock_page)

    # Context — async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_context)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_context.new_page = AsyncMock(return_value=mock_page)

    # Browser
    mock_browser = AsyncMock()
    mock_browser.new_context = MagicMock(return_value=mock_context)
    mock_browser.close = AsyncMock(return_value=None)

    # p.chromium
    mock_chromium = MagicMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    # async_playwright() → async context manager
    mock_p = MagicMock()
    mock_p.chromium = mock_chromium

    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_p)
    mock_playwright_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_playwright_cm, mock_page, mock_links


# ---------------------------------------------------------------------------
# Test 1: Успешная загрузка
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_success(grabber: ExternalSiteGrabber, tmp_path: Path):
    """Успешный сценарий: playwright находит mp4-ссылку, httpx скачивает файл."""
    mock_playwright_cm, mock_page, _ = _make_playwright_mocks()

    # Мокируем _stream_download, чтобы обойти async file IO
    async def fake_stream_download(url: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake_video_data")

    with (
        patch(
            "src.modules.external_site_grabber.async_playwright",
            return_value=mock_playwright_cm,
        ),
        patch.object(grabber, "_stream_download", side_effect=fake_stream_download),
    ):
        result = await grabber.download_video(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=tmp_path,
            quality="best",
        )

    assert result == tmp_path / "video.mp4"
    assert result.exists()
    assert result.read_bytes() == b"fake_video_data"


# ---------------------------------------------------------------------------
# Test 2: Таймаут playwright → ExternalSiteError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_playwright_timeout(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """wait_for_selector бросает PlaywrightTimeoutError → ExternalSiteError."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    mock_playwright_cm, _, _ = _make_playwright_mocks(
        wait_for_selector_side_effect=PlaywrightTimeoutError("timeout")
    )

    with patch(
        "src.modules.external_site_grabber.async_playwright",
        return_value=mock_playwright_cm,
    ):
        with pytest.raises(ExternalSiteError):
            await grabber.download_video(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# Test 3: Нет mp4-ссылок → ExternalSiteError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_no_mp4_links(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """query_selector_all возвращает пустой список → ExternalSiteError."""
    mock_playwright_cm, mock_page, _ = _make_playwright_mocks(links_count=0)
    mock_page.query_selector_all = AsyncMock(return_value=[])

    with patch(
        "src.modules.external_site_grabber.async_playwright",
        return_value=mock_playwright_cm,
    ):
        with pytest.raises(ExternalSiteError):
            await grabber.download_video(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# Test 4: HTTP ошибка при загрузке → ExternalSiteError, файл удалён
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_http_error_cleanup(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """HTTP 403 при скачивании → ExternalSiteError.

    Файл не создаётся: ошибка возникает на raise_for_status() до записи данных,
    поэтому video.mp4 никогда не появляется на диске.
    """
    import httpx

    mock_playwright_cm, _, _ = _make_playwright_mocks()

    # Строим поддельный HTTPStatusError
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 403

    def raise_for_status():
        raise httpx.HTTPStatusError(
            "403 Forbidden",
            request=MagicMock(),
            response=mock_response,
        )

    mock_response.raise_for_status = raise_for_status
    mock_response.aiter_bytes = AsyncMock(return_value=iter([]))

    # stream() — async context manager, возвращающий mock_response
    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_http_client = AsyncMock()
    mock_http_client.stream = MagicMock(return_value=mock_stream_cm)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "src.modules.external_site_grabber.async_playwright",
            return_value=mock_playwright_cm,
        ),
        patch(
            "src.modules.external_site_grabber.httpx.AsyncClient",
            return_value=mock_http_client,
        ),
    ):
        with pytest.raises(ExternalSiteError):
            await grabber.download_video(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir=tmp_path,
            )

    # Файл не был создан — ошибка произошла до записи (raise_for_status выброшен до write_bytes)
    assert not (tmp_path / "video.mp4").exists()


# ---------------------------------------------------------------------------
# Test 5: Цепочка стратегий — первая падает, вторая срабатывает
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_chain_fallback(settings: DownloadSettings, tmp_path: Path):
    """
    Первая стратегия бросает ExternalSiteError,
    вторая возвращает путь к файлу.
    """
    expected_path = Path("/tmp/video.mp4")

    strategy1 = AsyncMock()
    strategy1.download_video = AsyncMock(
        side_effect=ExternalSiteError("first failed")
    )

    strategy2 = AsyncMock()
    strategy2.download_video = AsyncMock(return_value=expected_path)

    with patch(
        "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
    ), patch(
        "src.modules.youtube_downloader_base.ExternalSiteGrabber"
    ):
        downloader = _ConcreteDownloader(settings)
        downloader._external_grabber = strategy1
        downloader.grabber = strategy2

    result = await downloader._run_strategy_chain(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=tmp_path,
        quality="best",
    )

    assert result == expected_path
    strategy1.download_video.assert_called_once()
    strategy2.download_video.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6: Все стратегии падают → DownloadError с причиной
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_chain_all_fail(settings: DownloadSettings, tmp_path: Path):
    """Обе стратегии падают → DownloadError с цепочкой причин."""
    original_error = ExternalSiteError("все упали")

    strategy1 = AsyncMock()
    strategy1.download_video = AsyncMock(side_effect=original_error)

    strategy2 = AsyncMock()
    strategy2.download_video = AsyncMock(
        side_effect=RuntimeError("secondary failure")
    )

    with patch(
        "src.modules.youtube_downloader_base.ProductionYouTubeGrabber"
    ), patch(
        "src.modules.youtube_downloader_base.ExternalSiteGrabber"
    ):
        downloader = _ConcreteDownloader(settings)
        downloader._external_grabber = strategy1
        downloader.grabber = strategy2

    with pytest.raises(DownloadError) as exc_info:
        await downloader._run_strategy_chain(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=tmp_path,
            quality="best",
        )

    assert exc_info.value.__cause__ is not None
