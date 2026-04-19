from __future__ import annotations

from pathlib import Path
from typing import Any

from src.modules.local_ears import LocalEars, TranscriptResult


class _DeferredLocalEars:
    """Простая заглушка для тестов без настроенного Whisper URL."""

    model_size = "small"

    def transcribe(self, media_path: Path) -> TranscriptResult | None:
        raise RuntimeError("WHISPER_URL не задан")


class TranscriptionProcessor:
    """Совместимый процессор для старых unit-тестов module2_transcribe."""

    MEDIA_EXTENSIONS = {
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
    }

    def __init__(
        self, content_dir: Path, whisper_url: str = "", whisper_api_key: str = ""
    ) -> None:
        self.content_dir = Path(content_dir)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.ears: LocalEars | _DeferredLocalEars
        if whisper_url:
            self.ears = LocalEars(
                whisper_url=whisper_url, whisper_api_key=whisper_api_key
            )
        else:
            self.ears = _DeferredLocalEars()

    def find_content_folders(self) -> list[Path]:
        return sorted([path for path in self.content_dir.iterdir() if path.is_dir()])

    def find_media_files(self, folder: Path) -> list[Path]:
        return sorted(
            [
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in self.MEDIA_EXTENSIONS
            ]
        )

    def process_folder(self, folder: Path) -> dict[str, Any]:
        transcript_path = folder / "transcript.md"
        if transcript_path.exists():
            return {"success": False, "already_has_transcript": True}

        media_files = self.find_media_files(folder)
        if not media_files:
            return {"success": False, "no_media": True}

        result = self.ears.transcribe(media_files[0])
        if result is None:
            return {"success": False, "transcription_failed": True}

        transcript_path.write_text(
            self._build_transcript_markdown(result), encoding="utf-8"
        )
        return {"success": True, "transcript_file": transcript_path}

    def _build_transcript_markdown(self, result: TranscriptResult) -> str:
        model_size = getattr(self.ears, "model_size", "unknown")
        return (
            "---\n"
            f"whisper_model: {model_size}\n"
            f"language: {result.language}\n"
            f"duration: {result.duration}\n"
            "type: transcript\n"
            "---\n\n"
            "## С таймкодами\n\n"
            f"{result.timed_transcript}\n\n"
            "## Полный текст\n\n"
            f"{result.full_text}\n"
        )
