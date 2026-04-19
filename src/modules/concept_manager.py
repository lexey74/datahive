"""
ConceptManager — накопительные тематические wiki-страницы по паттерну Karpathy LLM Wiki.

При каждом ingest:
  1. Извлекает из Knowledge.md ключевые термины, имена, инструменты
  2. Для каждого нового концепта — создаёт страницу wiki/concepts/{slug}.md
    3. Для существующих концептов — обновляет «Упоминания» и «Синтез» через llama.cpp

Структура страницы концепта:
  ---
  type: concept
  term: "Python"
  first_seen: 2026-04-08
  mentions: 5
  tags: [programming, language]
  ---
  # Python

  ## Синтез
  ...AI-накопленное резюме...

  ## Упоминания
  - [[2026-04-08_youtube_python_tips]] — контекст использования
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Минимальная длина термина для создания концепт-страницы
_MIN_TERM_LEN = 3
# Максимум концептов за один ingest (чтобы не перегружать LLM)
_MAX_CONCEPTS_PER_INGEST = 8


class ConceptManager:
    """
    Ведёт тематические страницы в wiki/concepts/.

    Использование:
        cm = ConceptManager(
            concepts_dir=Path("users/lexey/wiki/concepts"),
            ollama_model="llama3.2",
            ollama_url="http://localhost:8080",
        )
        cm.update_concepts(
            knowledge_md_path=Path("users/lexey/downloads/2026-04-08_.../Knowledge.md"),
            folder_name="2026-04-08_youtube_transformers",
        )
    """

    def __init__(
        self,
        concepts_dir: Path,
        ollama_model: str = "llama3.2",
        ollama_url: str = "http://localhost:8080",
    ) -> None:
        self.concepts_dir = Path(concepts_dir)
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from .local_brain import LlamaCppClient

                self._client = LlamaCppClient(host=self.ollama_url)
            except ImportError as e:
                raise ImportError("Не удалось импортировать llama.cpp клиент") from e
        return self._client

    # ── Основной метод ────────────────────────────────────────────

    def update_concepts(
        self,
        knowledge_md_path: Path,
        folder_name: str,
        tags: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Извлечь концепты из Knowledge.md и обновить wiki/concepts/.

        Args:
            knowledge_md_path: Путь к Knowledge.md нового источника
            folder_name: Имя папки источника (для ссылок)
            tags: Теги из AI-анализа (дополнительный сигнал)

        Returns:
            Список обновлённых/созданных концепт-страниц (имена файлов).
        """
        self.concepts_dir.mkdir(parents=True, exist_ok=True)

        if not knowledge_md_path.exists():
            logger.warning(
                f"ConceptManager: Knowledge.md не найден: {knowledge_md_path}"
            )
            return []

        knowledge_text = knowledge_md_path.read_text(encoding="utf-8")

        # 1. Извлечь [[wiki-ссылки]] из Knowledge.md (оставлены LLM)
        wiki_terms = re.findall(r"\[\[([^\]]+)\]\]", knowledge_text)
        # Отфильтровать служебные ссылки на файлы (description.md, transcript.md и т.п.)
        # и числовые имена файлов изображений
        _skip_patterns = re.compile(
            r"\.(md|jpg|jpeg|png|mp4|webp)\b"  # ссылки на файлы
            r"|^\d{2}_\d+_",  # числовые имена (instagram media)
            re.IGNORECASE,
        )
        wiki_terms = [t for t in wiki_terms if not _skip_patterns.search(t)]
        # 2. Добавить теги как дополнительные концепты
        extra = [t.replace("_", " ").title() for t in (tags or [])]
        all_terms = _dedupe([*wiki_terms, *extra])[:_MAX_CONCEPTS_PER_INGEST]

        if not all_terms:
            logger.debug("ConceptManager: нет концептов для обновления")
            return []

        updated: list[str] = []
        for term in all_terms:
            if len(term) < _MIN_TERM_LEN:
                continue
            try:
                page_file = self._update_concept_page(
                    term=term,
                    folder_name=folder_name,
                    knowledge_text=knowledge_text,
                )
                if page_file:
                    updated.append(page_file.name)
            except Exception as e:
                logger.warning(f"ConceptManager: ошибка для '{term}': {e}")

        if updated:
            logger.info(f"✅ ConceptManager: обновлено {len(updated)} концептов")
        return updated

    # ── Работа с отдельной страницей ──────────────────────────────

    def _update_concept_page(
        self,
        term: str,
        folder_name: str,
        knowledge_text: str,
    ) -> Optional[Path]:
        """Создать или обновить страницу для одного концепта."""
        slug = _term_to_slug(term)
        page_path = self.concepts_dir / f"{slug}.md"
        today = datetime.now().strftime("%Y-%m-%d")

        # Извлечь контекст упоминания из knowledge_text
        context = _extract_context(knowledge_text, term, max_chars=300)

        if not page_path.exists():
            # Создать новую страницу
            page_content = self._build_new_page(term=term, slug=slug, today=today)
        else:
            page_content = page_path.read_text(encoding="utf-8")

        # Добавить упоминание
        mention_line = f"- [[{folder_name}]] — {context}"
        page_content = _append_mention(page_content, mention_line)

        # Обновить счётчик mentions в frontmatter
        page_content = _increment_mentions(page_content)

        # Обновить синтез через llama.cpp (только если накопилось ≥ 2 упоминаний)
        mention_count = page_content.count("- [[")
        if mention_count >= 2:
            page_content = self._update_synthesis(page_content, term)

        page_path.write_text(page_content, encoding="utf-8")
        logger.debug(
            f"ConceptManager: → {page_path.name} (упоминаний: {mention_count})"
        )
        return page_path

    def _build_new_page(self, term: str, slug: str, today: str) -> str:
        """Шаблон для новой концепт-страницы."""
        return (
            f'---\ntype: concept\nterm: "{term}"\n'
            f"first_seen: {today}\nmentions: 0\n---\n\n"
            f"# {term}\n\n"
            "## Синтез\n\n"
            "_Накапливается автоматически по мере появления новых источников._\n\n"
            "## Упоминания\n\n"
        )

    def _update_synthesis(self, page_content: str, term: str) -> str:
        """
        Обновить секцию '## Синтез' через llama.cpp.

        Читает все упоминания из страницы и просит LLM написать синтез.
        Если LLM недоступна — тихо пропускает.
        """
        # Извлечь упоминания
        mentions_block = _extract_section(page_content, "## Упоминания")
        if not mentions_block:
            return page_content

        prompt = (
            f"Ты — редактор wiki. Напиши краткий синтез (2-4 предложения на русском) "
            f"о концепте «{term}» на основе следующих упоминаний из разных источников:\n\n"
            f"{mentions_block}\n\n"
            "Синтез должен отражать: что это такое, как используется, ключевые связи. "
            "Только текст, без заголовков и списков."
        )

        try:
            client = self._get_client()
            response = client.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3, "num_predict": 200},
            )
            new_synthesis = response["message"]["content"].strip()
        except Exception as e:
            logger.debug(f"ConceptManager: llama.cpp синтез недоступен ({e})")
            return page_content

        # Заменить содержимое секции Синтез
        return _replace_section(page_content, "## Синтез", new_synthesis)

    # ── Публичные утилиты ─────────────────────────────────────────

    def list_concepts(self) -> list[dict]:
        """Вернуть список всех концептов с метаданными."""
        concepts: list[dict[str, object]] = []
        if not self.concepts_dir.exists():
            return concepts
        for page in sorted(self.concepts_dir.glob("*.md")):
            content = page.read_text(encoding="utf-8")
            term = _parse_frontmatter_field(content, "term") or page.stem
            mentions = int(_parse_frontmatter_field(content, "mentions") or 0)
            concepts.append({"term": term, "file": page.name, "mentions": mentions})
        return sorted(concepts, key=lambda x: x["mentions"], reverse=True)


# ── Текстовые утилиты ─────────────────────────────────────────────


def _term_to_slug(term: str) -> str:
    """Конвертировать название концепта в slug для имени файла."""
    slug = term.lower()
    # Оставляем только ASCII буквы, цифры, пробелы и дефис (убираем кириллицу и спецсимволы)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:60] or "concept"


def _dedupe(items: list[str]) -> list[str]:
    """Убрать дубликаты, сохранив порядок."""
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def _extract_context(text: str, term: str, max_chars: int = 200) -> str:
    """Извлечь контекстный фрагмент вокруг упоминания термина."""
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        # Нет прямого упоминания — берём первые строки саммари
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.startswith("---")
        ]
        return " ".join(lines[2:5])[:max_chars] or "упомянуто в источнике"

    start = max(0, match.start() - 80)
    end = min(len(text), match.end() + 120)
    snippet = text[start:end].replace("\n", " ").strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:max_chars]


def _append_mention(page_content: str, mention_line: str) -> str:
    """Добавить строку упоминания в секцию '## Упоминания'."""
    if "## Упоминания" in page_content:
        # Вставить после последней строки секции
        parts = page_content.split("## Упоминания")
        before = parts[0] + "## Упоминания"
        after = parts[1]
        return before + after.rstrip() + f"\n{mention_line}\n"
    return page_content + f"\n{mention_line}\n"


def _increment_mentions(page_content: str) -> str:
    """Увеличить счётчик mentions в YAML frontmatter."""

    def replacer(m: re.Match) -> str:
        n = int(m.group(1))
        return f"mentions: {n + 1}"

    return re.sub(r"mentions:\s*(\d+)", replacer, page_content, count=1)


def _extract_section(page_content: str, header: str) -> str:
    """Извлечь текст секции от header до следующего ## заголовка."""
    pattern = re.compile(rf"{re.escape(header)}\n(.*?)(?=\n## |\Z)", re.DOTALL)
    match = pattern.search(page_content)
    return match.group(1).strip() if match else ""


def _replace_section(page_content: str, header: str, new_content: str) -> str:
    """Заменить содержимое секции между header и следующим ## заголовком."""
    pattern = re.compile(rf"({re.escape(header)}\n)(.*?)(?=\n## |\Z)", re.DOTALL)
    replacement = rf"\g<1>{new_content}\n\n"
    result, n = pattern.subn(replacement, page_content, count=1)
    return result if n else page_content


def _parse_frontmatter_field(content: str, field: str) -> Optional[str]:
    """Извлечь поле из YAML frontmatter."""
    pattern = re.compile(rf"^{field}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    if match:
        return match.group(1).strip().strip("\"'")
    return None
