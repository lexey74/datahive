from pathlib import Path

from scripts.youtube_auth_setup import (
    _is_youtube_auth_cookie_domain,
    _netscape_to_playwright,
    _normalize_cookie_expiry,
)


def test_normalize_cookie_expiry_from_webkit_microseconds() -> None:
    assert _normalize_cookie_expiry("13455712519381728") == 1811238919


def test_normalize_cookie_expiry_for_session_cookie() -> None:
    assert _normalize_cookie_expiry("0") == -1


def test_is_youtube_auth_cookie_domain() -> None:
    assert _is_youtube_auth_cookie_domain(".youtube.com") is True
    assert _is_youtube_auth_cookie_domain(".google.com") is True
    assert _is_youtube_auth_cookie_domain("accounts.google.com") is True
    assert _is_youtube_auth_cookie_domain(".vk.com") is False


def test_netscape_to_playwright_filters_irrelevant_domains(tmp_path: Path) -> None:
    cookies_txt = tmp_path / "cookies.txt"
    cookies_txt.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t13455712519381728\t__Secure-1PSID\tvalue1\n"
        ".google.com\tTRUE\t/\tTRUE\t13455712519384416\t__Secure-1PAPISID\tvalue2\n"
        ".vk.com\tTRUE\t/\tTRUE\t13455712519384416\tremixsid\tvalue3\n",
        encoding="utf-8",
    )

    cookies = _netscape_to_playwright(cookies_txt)

    assert len(cookies) == 2
    assert {cookie["domain"] for cookie in cookies} == {".youtube.com", ".google.com"}
    assert all(cookie["expires"] > 0 for cookie in cookies)