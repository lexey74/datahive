import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch


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
