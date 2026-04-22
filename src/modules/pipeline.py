"""
Pipeline - Оркестрация всего процесса обработки контента (Data Hive)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from datetime import datetime
import re
import logging
from .tag_manager import TagManager
from .hybrid_grabber import HybridGrabber
from .local_ears import LocalEars
from .local_brain import LocalBrain
from .wiki_manager import WikiManager
from .concept_manager import ConceptManager
from .graph_manager import parse_wiki_links

if TYPE_CHECKING:
    from src.bot.config import BotConfig

logger = logging.getLogger(__name__)


class DataHivePipeline:
    """Главный пайплайн обработки"""

    def __init__(self, config: dict) -> None:
        """
        Инициализация пайплайна.

        Args:
            config: Словарь с конфигурацией (обратная совместимость с CLI).
                    Для нового кода используй :meth:`from_bot_config`.
        """
        self.config = config

        self.tag_manager = TagManager()
        self.grabber = HybridGrabber(
            output_dir=Path(config["temp_dir"]),
            cookies_file=Path(config.get("cookies_file", "cookies.txt")),
        )
        self.ears = LocalEars(
            whisper_url=config.get("whisper_url", ""),
            whisper_api_key=config.get("whisper_api_key", ""),
        )
        # Предпочитаем новые llama.cpp ключи, но сохраняем совместимость со старыми именами.
        self.brain = LocalBrain(
            model=config.get("llama_cpp_model") or config.get("ollama_model", "llama3.2"),
            base_url=config.get("llama_cpp_url") or config.get("ollama_url", "http://localhost:8080"),
            api_key=config.get("llama_cpp_api_key") or config.get("ollama_api_key", ""),
        )

        if config.get("num_threads"):
            self.brain.num_threads = config["num_threads"]
        if config.get("num_ctx"):
            self.brain.num_ctx = config["num_ctx"]

        # WikiManager — user_root задаётся позже через process()
        self.wiki_manager: Optional[WikiManager] = None
        # ConceptManager — инициализируется вместе с WikiManager
        self.concept_manager: Optional[ConceptManager] = None

        session_file = Path(config.get("session_file", "session.json"))
        if session_file.exists():
            self.grabber.setup_instagrapi(session_file)

    @classmethod
    def from_bot_config(
        cls, bot_config: "BotConfig", output_dir: Path, user_root: Optional[Path] = None
    ) -> "DataHivePipeline":
        """
        Создать пайплайн из BotConfig (aiogram-бот).

        Args:
            bot_config: Pydantic BotConfig из src/bot/config.py
            output_dir: Папка для сохранения контента
            user_root: Корневая папка пользователя (для wiki). Если None — wiki отключена.
        """
        config_dict = {
            "temp_dir": str(output_dir),
            "whisper_url": bot_config.whisper_url,
            "whisper_api_key": bot_config.whisper_api_key,
            "llama_cpp_model": bot_config.ollama_model,
            "llama_cpp_url": bot_config.ollama_url,
            "llama_cpp_api_key": bot_config.ollama_api_key,
            "ollama_model": bot_config.ollama_model,
            "ollama_url": bot_config.ollama_url,
            "ollama_api_key": bot_config.ollama_api_key,
        }
        pipeline = cls(config_dict)
        if user_root:
            pipeline.wiki_manager = WikiManager(user_root)
            pipeline.concept_manager = ConceptManager(
                concepts_dir=user_root / "wiki" / "concepts",
                ollama_model=bot_config.ollama_model,
                ollama_url=bot_config.ollama_url,
            )
        return pipeline

    def process(self, url: str) -> Optional[Path]:
        """
        Полный цикл обработки Instagram URL

        Args:
            url: URL Instagram поста/рилса

        Returns:
            Путь к созданной заметке или None
        """
        logger.info("=" * 60)
        logger.info(f"🚀 Обработка: {url}")
        logger.info("=" * 60)

        # Шаг 1: Загрузка контента
        content = self.grabber.grab(url)
        if not content.media_path:
            logger.error("❌ Не удалось загрузить медиа")
            return None

        # Шаг 2: Транскрибация (если видео)
        transcript_result = self.ears.transcribe(content.media_path)
        transcript_text = (
            transcript_result.timed_transcript if transcript_result else ""
        )
        full_text = transcript_result.full_text if transcript_result else ""

        # Шаг 3: AI анализ
        known_tags_string = self.tag_manager.get_tags_string()

        ai_result = self.brain.analyze(
            caption=content.caption,
            transcript=transcript_text,
            comments=content.comments,
            author=content.author,
            known_tags=known_tags_string,
        )

        if not ai_result:
            logger.error("❌ Ошибка AI анализа")
            return None

        # Шаг 4: Обновление тегов
        new_tags = ai_result.get("tags", [])
        added_count = self.tag_manager.add_tags(new_tags)
        if added_count > 0:
            logger.info(f"✅ Добавлено новых тегов: {added_count}")

        # Шаг 5: Создание Asset Bundle
        logger.info("📝 Создание заметки...")
        try:
            note_path = self._create_note_bundle(
                content=content,
                ai_result=ai_result,
                transcript_text=transcript_text,
                full_text=full_text,
            )
            logger.info("✅ Заметка создана")
        except Exception as e:
            logger.error(f"❌ Ошибка создания заметки: {e}")
            return None

        logger.info(f"✅ Готово! Заметка: {note_path}")

        # Шаг 6: Обновление wiki (index.md + log.md)
        if self.wiki_manager:
            try:
                folder_name = note_path.parent.name
                source = getattr(content, "platform", "unknown") or "unknown"
                tags = ai_result.get("tags", [])
                summary = ai_result.get("summary", "")

                self.wiki_manager.update_index(
                    folder_name=folder_name,
                    summary=summary,
                    tags=tags,
                    source=source,
                    url=getattr(content, "url", ""),
                )
                self.wiki_manager.append_log(
                    operation="ingest",
                    title=f"{source.capitalize()} | {folder_name}",
                    details=f"Теги: {', '.join(tags[:8])}\nСаммари: {summary[:120] if isinstance(summary, str) else ''}",
                    folder_name=folder_name,
                )
                # Шаг 7: Обновление графа знаний
                knowledge_text = note_path.read_text(encoding="utf-8")
                wiki_links = parse_wiki_links(knowledge_text)
                if wiki_links:
                    title_str = summary[:100] if isinstance(summary, str) else folder_name
                    date_str_graph = content.date or datetime.now().strftime("%Y-%m-%d")
                    self.wiki_manager.update_graph(
                        folder_name=folder_name,
                        title=title_str,
                        date=date_str_graph,
                        wiki_links=wiki_links,
                    )
            except Exception as e:
                logger.warning(f"⚠️ WikiManager ошибка: {e}")

        # Шаг 8: Обновление concept pages (wiki compiler)
        if self.concept_manager:
            try:
                folder_name = note_path.parent.name
                tags = ai_result.get("tags", [])
                self.concept_manager.update_concepts(
                    knowledge_md_path=note_path,
                    folder_name=folder_name,
                    tags=tags,
                )
            except Exception as e:
                logger.warning(f"⚠️ ConceptManager ошибка: {e}")

        return note_path

    def _create_note_bundle(
        self,
        content: Any,
        ai_result: dict[str, Any],
        transcript_text: str,
        full_text: str,
    ) -> Path:
        """
        Создание Asset Bundle (папка + Knowledge.md + медиа)

        Args:
            content: InstagramContent
            ai_result: Результат AI анализа
            transcript_text: Транскрипт с таймкодами
            full_text: Чистый текст транскрипта

        Returns:
            Путь к Knowledge.md
        """
        # Формирование имени папки
        date_str = content.date or datetime.now().strftime("%Y-%m-%d")
        author = self._sanitize_filename(content.author or "unknown")
        slug = self._generate_slug(ai_result.get("summary", "note"))

        bundle_name = f"{date_str}_{author}_{slug}"
        bundle_path = Path(self.config["output_dir"]) / bundle_name
        bundle_path.mkdir(parents=True, exist_ok=True)

        # Перемещение медиа в bundle
        media_ext = ".jpg"  # default
        if content.media_path and content.media_path.exists():
            media_ext = content.media_path.suffix
            media_dest = bundle_path / f"media{media_ext}"
            content.media_path.rename(media_dest)

        # Генерация Knowledge.md
        note_content = self._generate_markdown(
            content=content,
            ai_result=ai_result,
            transcript_text=transcript_text,
            full_text=full_text,
            media_filename=f"media{media_ext}",
        )

        note_path = bundle_path / "Knowledge.md"
        note_path.write_text(note_content, encoding="utf-8")

        return note_path

    def _generate_markdown(
        self,
        content: Any,
        ai_result: dict[str, Any],
        transcript_text: str,
        full_text: str,
        media_filename: str,
    ) -> str:
        """Генерация Markdown заметки по шаблону"""

        tags_yaml = "\n".join(f"  - {tag}" for tag in ai_result.get("tags", []))
        tags_yaml += "\n  - inbox"

        # Форматирование комментариев
        comments_md = ""
        for comment in ai_result.get("valuable_comments", []):
            comments_md += f"> {comment}\n\n"

        # Генерация заголовка
        title = (
            f"{content.author}: {self._generate_slug(ai_result.get('summary', 'Note'))}"
        )

        template = f"""---
created: {content.date or datetime.now().strftime("%Y-%m-%d")}
author: {content.author}
url: {content.url}
category: {ai_result.get("category", "Other")}
tags:
{tags_yaml}
---

# {title}

![[{media_filename}]]

## 🧠 AI Summary
{ai_result.get("summary", "No summary available")}

## 💬 Valuable Insights (Comments)
{comments_md if comments_md else "_No valuable comments found_"}

---
<details>
<summary>📂 Raw Data (Transcript & Caption)</summary>

### Caption
{content.caption if content.caption else "_No caption_"}

### Transcript
{transcript_text if transcript_text else "_No transcript (image or transcription failed)_"}
</details>
"""
        return template

    def _sanitize_filename(self, text: str) -> str:
        """Очистка текста для использования в имени файла"""
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text)
        return text[:30].lower()

    def _generate_slug(self, text: str) -> str:
        """Генерация короткого slug из текста"""
        # Если это список, берём первый элемент
        if isinstance(text, list):
            text = text[0] if text else "note"
        # Если не строка, конвертируем
        if not isinstance(text, str):
            text = str(text)

        words = text.split()[:4]
        slug = "_".join(words)
        return self._sanitize_filename(slug)


# Алиас для обратной совместимости со старым кодом
SecBrainPipeline = DataHivePipeline
