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
        base_url="https://en.ssyoutube.com/",
        timeout_ms=5_000,
    )


@pytest.fixture
def settings(tmp_path: Path) -> DownloadSettings:
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    return DownloadSettings(youtube_cookies_dir=cookies_dir)


def _make_playwright_mocks_ajax(
    *,
    api_response_data: dict | None = None,
    trigger_callback: bool = True,
):
    """
    Строит цепочку моков для async_playwright (AJAX-interception API).

    trigger_callback=True: page.click() вызывает перехваченный response-handler
    trigger_callback=False: ответ никогда не приходит (для теста таймаута)
    """
    captured_handlers: list = []

    mock_api_response = AsyncMock()
    mock_api_response.url = "https://api-wh.ssyoutube.com/api/convert"
    mock_api_response.json = AsyncMock(return_value=api_response_data or {})

    def on_side_effect(event: str, handler) -> None:
        if event == "response":
            captured_handlers.append(handler)

    async def click_side_effect(*args, **kwargs) -> None:
        if trigger_callback:
            for handler in captured_handlers:
                await handler(mock_api_response)

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.fill = AsyncMock(return_value=None)
    mock_page.click = AsyncMock(side_effect=click_side_effect)
    mock_page.on = MagicMock(side_effect=on_side_effect)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock(return_value=None)

    # Ключевое исправление: AsyncMock, не MagicMock — т.к. код делает
    # `context = await browser.new_context()`
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock(return_value=None)

    mock_chromium = MagicMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_p = MagicMock()
    mock_p.chromium = mock_chromium

    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_p)
    mock_playwright_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_playwright_cm, mock_page


# Сэмпл данных API: два mp4-бандла + один webm (должен быть отфильтрован)
_SAMPLE_API_DATA = {
    "url": [
        {
            "ext": "mp4",
            "isBundle": True,
            "qualityNumber": 720,
            "quality": "720",
            "url": "https://cdn.example.com/video_720.mp4",
            "downloadable": True,
        },
        {
            "ext": "mp4",
            "isBundle": True,
            "qualityNumber": 1080,
            "quality": "1080",
            "url": "https://cdn.example.com/video_1080.mp4",
            "downloadable": True,
        },
        {
            "ext": "webm",
            "isBundle": True,
            "qualityNumber": 1080,
            "quality": "1080",
            "url": "https://cdn.example.com/video.webm",
            "downloadable": True,
        },
    ]
}


# ---------------------------------------------------------------------------
# Test 1: Успешная загрузка
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_success(grabber: ExternalSiteGrabber, tmp_path: Path):
    """Успешный сценарий: AJAX-ответ от ssyoutube API, httpx скачивает файл."""
    mock_playwright_cm, _ = _make_playwright_mocks_ajax(
        api_response_data=_SAMPLE_API_DATA
    )

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
# Test 2: Таймаут AJAX-ответа → ExternalSiteError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_api_timeout(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """API-ответ не приходит → ExternalSiteError (asyncio.TimeoutError)."""
    mock_playwright_cm, _ = _make_playwright_mocks_ajax(trigger_callback=False)

    with (
        patch(
            "src.modules.external_site_grabber.async_playwright",
            return_value=mock_playwright_cm,
        ),
        patch("src.modules.external_site_grabber._API_WAIT_TIMEOUT", 0.01),
    ):
        with pytest.raises(ExternalSiteError, match="Таймаут"):
            await grabber.download_video(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# Test 3: Нет mp4-ссылок в ответе → ExternalSiteError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_no_mp4_links(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """API возвращает ответ без mp4-бандлов → ExternalSiteError."""
    empty_api_data = {"url": []}
    mock_playwright_cm, _ = _make_playwright_mocks_ajax(api_response_data=empty_api_data)

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
# Test 4: HTTP ошибка при загрузке → ExternalSiteError, файл не создан
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_video_http_error_cleanup(
    grabber: ExternalSiteGrabber, tmp_path: Path
):
    """HTTP 403 при скачивании → ExternalSiteError, video.mp4 не создаётся."""
    import httpx

    mock_playwright_cm, _ = _make_playwright_mocks_ajax(
        api_response_data=_SAMPLE_API_DATA
    )

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

    assert not (tmp_path / "video.mp4").exists()


# ---------------------------------------------------------------------------
# Test 5: _pick_best_url — выбирает лучший mp4 bundle
# ---------------------------------------------------------------------------


def test_pick_best_url_returns_highest_quality(grabber: ExternalSiteGrabber):
    """_pick_best_url выбирает bundle с максимальным qualityNumber."""
    api_data = {
        "url": [
            {"ext": "mp4", "isBundle": True, "qualityNumber": 720, "quality": "720",
             "url": "https://cdn.example.com/video_720.mp4"},
            {"ext": "mp4", "isBundle": True, "qualityNumber": 1080, "quality": "1080",
             "url": "https://cdn.example.com/video_1080.mp4"},
        ]
    }
    result = grabber._pick_best_url(api_data, "best")
    assert result == "https://cdn.example.com/video_1080.mp4"


def test_pick_best_url_filters_non_mp4(grabber: ExternalSiteGrabber):
    """_pick_best_url фильтрует не-mp4 форматы."""
    api_data = {
        "url": [
            {"ext": "webm", "isBundle": True, "qualityNumber": 1080, "quality": "1080",
             "url": "https://cdn.example.com/video.webm"},
            {"ext": "mp4", "isBundle": True, "qualityNumber": 720, "quality": "720",
             "url": "https://cdn.example.com/video_720.mp4"},
        ]
    }
    result = grabber._pick_best_url(api_data, "best")
    assert result == "https://cdn.example.com/video_720.mp4"


def test_pick_best_url_returns_none_when_empty(grabber: ExternalSiteGrabber):
    """_pick_best_url возвращает None если нет подходящих ссылок."""
    assert grabber._pick_best_url({"url": []}, "best") is None
    assert grabber._pick_best_url({}, "best") is None


# ---------------------------------------------------------------------------
# Test 6: Цепочка стратегий — стратегия успешно загружает
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_chain_success(settings: DownloadSettings, tmp_path: Path):
    """Единственная стратегия возвращает путь к файлу."""
    expected_path = Path("/tmp/video.mp4")

    strategy = AsyncMock()
    strategy.download_video = AsyncMock(return_value=expected_path)

    with patch("src.modules.youtube_downloader_base.ProductionYouTubeGrabber"):
        downloader = _ConcreteDownloader(settings)
        downloader.grabber = strategy

    result = await downloader._run_strategy_chain(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=tmp_path,
        quality="best",
    )

    assert result == expected_path
    strategy.download_video.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7: Стратегия падает → DownloadError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_chain_all_fail(settings: DownloadSettings, tmp_path: Path):
    """Стратегия падает → DownloadError с цепочкой причин."""
    original_error = RuntimeError("download failed")

    strategy = AsyncMock()
    strategy.download_video = AsyncMock(side_effect=original_error)

    with patch("src.modules.youtube_downloader_base.ProductionYouTubeGrabber"):
        downloader = _ConcreteDownloader(settings)
        downloader.grabber = strategy

    with pytest.raises(DownloadError) as exc_info:
        await downloader._run_strategy_chain(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_dir=tmp_path,
            quality="best",
        )

    assert exc_info.value.__cause__ is not None
