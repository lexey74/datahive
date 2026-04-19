from __future__ import annotations

from pathlib import Path
from typing import Any

from src.modules.local_brain import LocalBrain
from src.modules.tag_manager import TagManager


class AIProcessor:
    """Совместимый процессор для старых unit-тестов module3_analyze."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    VIDEO_EXTENSIONS = {
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

    def __init__(self, content_dir: Path, tags_file: Path) -> None:
        self.content_dir = Path(content_dir)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.tag_manager = TagManager(tags_file)
        self.brain = LocalBrain()

    def find_images(self, folder: Path) -> list[Path]:
        return sorted(
            [
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in self.IMAGE_EXTENSIONS
            ]
        )

    def should_process_folder(self, folder: Path) -> tuple[bool, str]:
        knowledge = folder / "Knowledge.md"
        if knowledge.exists():
            return False, "Knowledge.md существует"

        description = folder / "description.md"
        transcript = folder / "transcript.md"
        media_files = [
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in self.VIDEO_EXTENSIONS
        ]

        if not description.exists() and not transcript.exists() and not media_files:
            return False, "нет контента"
        if media_files and not transcript.exists():
            return False, "требуется Модуль 2"
        if transcript.exists():
            return True, "готово: transcript.md"
        if description.exists():
            return True, "готово: description.md"
        return False, "нет контента"

    def process_folder(self, folder: Path) -> dict[str, Any]:
        should_process, reason = self.should_process_folder(folder)
        if not should_process:
            return {"success": False, "reason": reason}

        description_text = self._read_file(folder / "description.md")
        transcript_text = self._read_file(folder / "transcript.md")
        ai_result = self.brain.analyze(
            caption=description_text,
            transcript=transcript_text,
            comments=[],
            author="",
            known_tags=self.tag_manager.get_tags_string(),
        )

        if not ai_result:
            return {"success": False, "reason": "analyze returned None"}

        self.tag_manager.add_tags(ai_result.get("tags", []))
        knowledge_path = folder / "Knowledge.md"
        knowledge_path.write_text(
            self._build_knowledge_markdown(folder, ai_result), encoding="utf-8"
        )
        return {"success": True, "knowledge_file": knowledge_path}

    def _read_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _build_knowledge_markdown(self, folder: Path, ai_result: dict[str, Any]) -> str:
        tags = ai_result.get("tags", [])
        tag_lines = "\n".join(f"- #{tag}" for tag in tags)
        return (
            "---\n"
            f'title: "{folder.name}"\n'
            "type: knowledge\n"
            "processed: true\n"
            "---\n\n"
            "## Саммари\n\n"
            f"{ai_result.get('summary', '')}\n\n"
            "## Теги\n\n"
            f"{tag_lines}\n\n"
            "## Категория\n\n"
            f"{ai_result.get('category', '')}\n"
        )
