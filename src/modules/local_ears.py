"""
LocalEars - Транскрибация видео через HTTP-сервис whisper.inno.co.

Запросы к DataHive Whisper Service (services/whisper/main.py).
"""

import logging
import urllib.request
import urllib.error
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    """Результат транскрибации"""

    timed_transcript: str  # С таймкодами [MM:SS]
    full_text: str  # Чистый текст
    language: str = "ru"
    duration: float = 0.0


class LocalEars:
    """Транскрибация аудио/видео через HTTP-сервис Whisper."""

    def __init__(
        self,
        whisper_url: str = "",
        whisper_api_key: str = "",
        **kwargs: object,  # поглощает устаревшие параметры (model_size, device, и др.)
    ) -> None:
        del kwargs
        """
        Args:
            whisper_url: Базовый URL whisper-сервиса (напр. https://whisper.inno.co).
            whisper_api_key: Bearer-токен для авторизации. Если пуст — заголовок не отправляется.
        """
        self.whisper_url = whisper_url.rstrip("/")
        self.whisper_api_key = whisper_api_key

        if not self.whisper_url:
            raise RuntimeError(
                "WHISPER_URL не задан. Укажите адрес whisper-сервиса в .env: "
                "WHISPER_URL=https://whisper.inno.co"
            )
        logger.info(f"🌐 LocalEars: HTTP-режим → {self.whisper_url}")

    def transcribe(self, media_path: Path) -> Optional[TranscriptResult]:
        """
        Транскрибация медиафайла через HTTP-сервис.

        Args:
            media_path: Путь к видео/аудио файлу

        Returns:
            TranscriptResult или None если файл не является аудио/видео
        """
        if not media_path or not media_path.exists():
            return None

        valid_extensions = [
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".webm",
            ".mp3",
            ".m4a",
            ".wav",
            ".flac",
            ".ogg",
        ]
        if media_path.suffix.lower() not in valid_extensions:
            logger.info("ℹ️  Это изображение, транскрибация не требуется")
            return None

        return self._transcribe_remote(media_path)

    # ------------------------------------------------------------------
    # HTTP-режим (whisper-сервис в контейнере)
    # ------------------------------------------------------------------

    def _transcribe_remote(self, media_path: Path) -> Optional[TranscriptResult]:
        """Отправляет файл на HTTP-сервис и возвращает TranscriptResult."""
        url = f"{self.whisper_url}/transcribe"
        logger.info(f"🌐 HTTP-транскрибация → {url}  ({media_path.name})")

        # Определяем MIME-тип
        mime_type, _ = mimetypes.guess_type(str(media_path))
        mime_type = mime_type or "application/octet-stream"

        # Формируем multipart/form-data вручную (без зависимостей типа requests)
        boundary = uuid.uuid4().hex
        with open(media_path, "rb") as fh:
            file_data = fh.read()

        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{media_path.name}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode()
            + file_data
            + f"\r\n--{boundary}--\r\n".encode()
        )

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        if self.whisper_api_key:
            req.add_header("Authorization", f"Bearer {self.whisper_api_key}")

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"Whisper-сервис вернул {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Не удалось подключиться к whisper-сервису ({url}): {exc.reason}"
            ) from exc

        logger.info(
            f"✅ HTTP-транскрибация завершена "
            f"(lang={payload.get('language')}, duration={payload.get('duration', 0):.1f}s)"
        )
        return TranscriptResult(
            timed_transcript=payload["timed_transcript"],
            full_text=payload["full_text"],
            language=payload.get("language", "ru"),
            duration=float(payload.get("duration", 0.0)),
        )
