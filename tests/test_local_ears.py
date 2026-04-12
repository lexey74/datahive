"""
Unit Tests for LocalEars (Whisper Transcription via HTTP)
=========================================================

Тесты для модуля транскрибации через whisper-сервис (HTTP-режим).
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from modules.local_ears import LocalEars, TranscriptResult


WHISPER_URL = "https://whisper.inno.co"
API_KEY = "test-api-key"


class TestLocalEars:
    """Тесты для LocalEars"""

    def test_init_http_mode(self):
        """Инициализация с заданным whisper_url"""
        ears = LocalEars(whisper_url=WHISPER_URL, whisper_api_key=API_KEY)
        assert ears.whisper_url == WHISPER_URL
        assert ears.whisper_api_key == API_KEY

    def test_init_no_url_raises(self):
        """Без WHISPER_URL должен бросать RuntimeError"""
        with pytest.raises(RuntimeError, match="WHISPER_URL не задан"):
            LocalEars(whisper_url="")

    def test_transcribe_image_returns_none(self, tmp_path):
        """Изображения не транскрибируются"""
        ears = LocalEars(whisper_url=WHISPER_URL)
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"fake image")
        assert ears.transcribe(img) is None

    def test_transcribe_nonexistent_returns_none(self, tmp_path):
        """Несуществующий файл возвращает None"""
        ears = LocalEars(whisper_url=WHISPER_URL)
        assert ears.transcribe(tmp_path / "missing.mp4") is None

    def test_transcribe_remote_success(self, tmp_path):
        """Успешный HTTP-запрос возвращает TranscriptResult"""
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"fake audio data")

        payload = {
            "timed_transcript": "[00:00] Привет мир",
            "full_text": "Привет мир",
            "language": "ru",
            "duration": 3.5,
        }

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(payload).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp):
            ears = LocalEars(whisper_url=WHISPER_URL, whisper_api_key=API_KEY)
            result = ears.transcribe(audio)

        assert isinstance(result, TranscriptResult)
        assert result.full_text == "Привет мир"
        assert result.language == "ru"
        assert result.duration == 3.5
        assert "[00:00]" in result.timed_transcript

    def test_transcribe_remote_sends_auth_header(self, tmp_path):
        """Bearer-токен добавляется в заголовок запроса"""
        audio = tmp_path / "test.mp4"
        audio.write_bytes(b"fake video")

        payload = {
            "timed_transcript": "[00:00] Текст",
            "full_text": "Текст",
            "language": "ru",
            "duration": 1.0,
        }

        captured_req = {}

        def fake_urlopen(req, timeout=None):
            captured_req['headers'] = dict(req.headers)
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = json.dumps(payload).encode()
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ears = LocalEars(whisper_url=WHISPER_URL, whisper_api_key=API_KEY)
            ears.transcribe(audio)

        assert captured_req['headers'].get('Authorization') == f"Bearer {API_KEY}"

    def test_transcribe_remote_http_error(self, tmp_path):
        """HTTP-ошибка от сервиса пробрасывается как RuntimeError"""
        import urllib.error
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"fake audio")

        http_err = urllib.error.HTTPError(
            url=f"{WHISPER_URL}/transcribe",
            code=500,
            msg="Internal Server Error",
            hdrs=MagicMock(),
            fp=BytesIO(b"server error"),
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            ears = LocalEars(whisper_url=WHISPER_URL)
            with pytest.raises(RuntimeError, match="Whisper-сервис вернул 500"):
                ears.transcribe(audio)

    def test_transcribe_remote_connection_error(self, tmp_path):
        """Недоступность сервиса пробрасывается как RuntimeError"""
        import urllib.error
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"fake audio")

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            ears = LocalEars(whisper_url=WHISPER_URL)
            with pytest.raises(RuntimeError, match="Не удалось подключиться"):
                ears.transcribe(audio)

