"""
WikiManager — управление персистентной wiki по паттерну Karpathy LLM Wiki.

Ведёт два специальных файла:
  index.md  — каталог всех обработанных источников (обновляется при каждом ingest)
  log.md    — хронологический append-only журнал операций (ingest / query / lint)

Структура в users/{username}/:
  index.md
  log.md
  wiki/
    concepts/   — тематические страницы (создаются ConceptManager)
    queries/    — сохранённые ответы на вопросы
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from .graph_manager import GraphManager

logger = logging.getLogger(__name__)


class WikiManager:
    """
    Ведёт index.md и log.md для пользователя.

    Пример использования:
        wm = WikiManager(user_root=Path("users/lexey"))
        wm.update_index(folder_name="2026-04-08_instagram_sunset",
                        summary="Пейзажная фотография", tags=["photography"])
        wm.append_log("ingest", "Instagram | beautiful_sunset",
                      details="Теги: photography, sunset")
    """

    def __init__(self, user_root: Path) -> None:
        self.user_root = Path(user_root)
        self.index_path = self.user_root / "index.md"
        self.log_path = self.user_root / "log.md"
        self.wiki_dir = self.user_root / "wiki"
        self.concepts_dir = self.wiki_dir / "concepts"
        self.queries_dir = self.wiki_dir / "queries"
        self.graph_manager = GraphManager(self.wiki_dir)

    def ensure_dirs(self) -> None:
        """Создать нужные папки если не существуют."""
        self.user_root.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(exist_ok=True)
        self.concepts_dir.mkdir(exist_ok=True)
        self.queries_dir.mkdir(exist_ok=True)

    # ── index.md ──────────────────────────────────────────────────

    def update_index(
        self,
        folder_name: str,
        summary: str,
        tags: list[str],
        source: str = "unknown",
        url: str = "",
    ) -> None:
        """
        Добавить/обновить запись об обработанном источнике в index.md.

        Если запись с этим folder_name уже есть — обновляет строку.
        Иначе — добавляет в нужную секцию по платформе.
        """
        self.ensure_dirs()
        today = datetime.now().strftime("%Y-%m-%d")
        # Короткий саммари: первая строка, без markdown разметки, до 100 символов
        clean_summary = _strip_markdown(summary).split("\n")[0][:100]
        tags_str = ", ".join(f"`{t}`" for t in tags[:5])
        link = f"[[{folder_name}]]"
        entry_line = f"| {link} | {source} | {today} | {clean_summary} | {tags_str} |"

        if not self.index_path.exists():
            self._init_index()

        content = self.index_path.read_text(encoding="utf-8")

        # Обновить существующую запись, если есть
        if folder_name in content:
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if folder_name in line and "|" in line:
                    new_lines.append(entry_line)
                else:
                    new_lines.append(line)
            self.index_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.debug(f"WikiManager: обновлена запись index.md → {folder_name}")
            return

        # Найти секцию платформы или добавить новую
        section_header = f"### {source.capitalize()}"
        table_header = "| Источник | Платформа | Дата | Краткое содержание | Теги |"
        table_sep = "|---|---|---|---|---|"

        if section_header in content:
            # Вставить строку после заголовка таблицы
            lines = content.splitlines()
            new_lines = []
            i = 0
            while i < len(lines):
                new_lines.append(lines[i])
                if lines[i].strip() == section_header:
                    # пропустить заголовок таблицы и разделитель
                    if i + 1 < len(lines) and "|" in lines[i + 1]:
                        new_lines.append(lines[i + 1])
                        i += 1
                    if i + 1 < len(lines) and lines[i + 1].startswith("|---"):
                        new_lines.append(lines[i + 1])
                        i += 1
                    new_lines.append(entry_line)
                i += 1
            self.index_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        else:
            # Добавить новую секцию платформы в конец
            new_section = (
                f"\n{section_header}\n\n{table_header}\n{table_sep}\n{entry_line}\n"
            )
            with self.index_path.open("a", encoding="utf-8") as f:
                f.write(new_section)

        logger.info(f"✅ WikiManager: index.md обновлён → {folder_name}")

    def _init_index(self) -> None:
        """Создать пустой index.md с frontmatter."""
        today = datetime.now().strftime("%Y-%m-%d")
        content = (
            f"---\ntype: index\nupdated: {today}\n---\n\n"
            "# 📚 Индекс базы знаний\n\n"
            "Этот файл автоматически обновляется при каждой обработке контента.\n\n"
            "## По платформам\n\n"
        )
        self.index_path.write_text(content, encoding="utf-8")

    # ── log.md ────────────────────────────────────────────────────

    def append_log(
        self,
        operation: str,
        title: str,
        details: str = "",
        folder_name: str = "",
    ) -> None:
        """
        Добавить запись в log.md.

        Args:
            operation: 'ingest' | 'query' | 'lint'
            title: Короткое описание операции
            details: Дополнительные детали (теги, ответ и т.п.)
            folder_name: Имя папки (для ingest)
        """
        self.ensure_dirs()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        link_part = f" | [[{folder_name}]]" if folder_name else ""
        header = f"## [{date_str} {time_str}] {operation} | {title}{link_part}"

        details_block = ""
        if details:
            details_block = "\n".join(
                f"- {line}" for line in details.strip().split("\n") if line.strip()
            )
            details_block = "\n" + details_block

        entry = f"\n{header}{details_block}\n"

        if not self.log_path.exists():
            self._init_log()

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(entry)

        logger.debug(f"WikiManager: log.md ← [{operation}] {title}")

    def _init_log(self) -> None:
        """Создать пустой log.md с frontmatter."""
        today = datetime.now().strftime("%Y-%m-%d")
        content = (
            f"---\ntype: log\ncreated: {today}\n---\n\n"
            "# 📋 Журнал операций\n\n"
            "Append-only хронологическая запись всех операций Data Hive.\n"
            'Поиск по журналу: `grep "^## \\[" log.md | tail -20`\n\n'
        )
        self.log_path.write_text(content, encoding="utf-8")

    # ── Queries → wiki ────────────────────────────────────────────

    def save_query_answer(self, question: str, answer: str, sources: list[str]) -> Path:
        """
        Сохранить ответ на вопрос как wiki-страницу в wiki/queries/.

        Returns:
            Путь к созданному файлу.
        """
        self.ensure_dirs()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M")
        slug = _make_slug(question)
        filename = f"{date_str}_{time_str}_{slug}.md"
        file_path = self.queries_dir / filename

        sources_md = (
            "\n".join(f"- [[{s}]]" for s in sources) if sources else "_нет источников_"
        )
        content = (
            f'---\ntype: query\ndate: {date_str}\nquestion: "{question[:120]}"\n---\n\n'
            f"# {question}\n\n"
            f"## Ответ\n\n{answer}\n\n"
            f"## Источники\n\n{sources_md}\n"
        )
        file_path.write_text(content, encoding="utf-8")

        # Добавить в log
        self.append_log(
            operation="query",
            title=question[:80],
            details=f"Источники: {', '.join(sources[:3])}",
        )
        logger.info(f"✅ WikiManager: вопрос сохранён → {file_path.name}")
        return file_path

    # ── Граф знаний ─────────────────────────────────────────────────

    def update_graph(
        self,
        folder_name: str,
        title: str,
        date: str,
        wiki_links: list[str],
    ) -> None:
        """
        Обновить граф знаний: добавить article node + edges к концептам.

        Также обновляет секцию «Обратные ссылки» в concept pages.

        Args:
            folder_name: Имя папки статьи
            title: Заголовок статьи
            date: Дата создания
            wiki_links: Список терминов из [[wiki-ссылок]] Knowledge.md
        """
        self.ensure_dirs()
        self.graph_manager.update_from_knowledge(
            folder_name=folder_name,
            title=title,
            date=date,
            wiki_links=wiki_links,
        )
        # Обновить backlinks в concept pages
        self.graph_manager.update_backlinks_in_concepts(self.concepts_dir)
        logger.info(f"✅ WikiManager: граф обновлён → {folder_name} ({len(wiki_links)} связей)")

    def get_graph_stats(self) -> dict:
        """Статистика графа знаний."""
        return self.graph_manager.get_stats()

    # ── Статистика ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Быстрая статистика по wiki пользователя."""
        stats: dict = {
            "total_sources": 0,
            "log_entries": 0,
            "concept_pages": 0,
            "query_pages": 0,
        }
        if self.index_path.exists():
            content = self.index_path.read_text(encoding="utf-8")
            # Считаем строки таблицы (содержат | [[)
            stats["total_sources"] = content.count("| [[")

        if self.log_path.exists():
            content = self.log_path.read_text(encoding="utf-8")
            stats["log_entries"] = content.count("## [")

        if self.concepts_dir.exists():
            stats["concept_pages"] = len(list(self.concepts_dir.glob("*.md")))

        if self.queries_dir.exists():
            stats["query_pages"] = len(list(self.queries_dir.glob("*.md")))

        # Статистика графа
        graph_stats = self.graph_manager.get_stats()
        stats["graph_nodes"] = graph_stats.get("nodes", 0)
        stats["graph_edges"] = graph_stats.get("edges", 0)

        return stats


# ── Утилиты ───────────────────────────────────────────────────────


def _strip_markdown(text: str) -> str:
    """Убрать markdown-разметку для читаемого превью."""
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)  # [[links]]
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # [text](url)
    text = re.sub(r"[*_`#>]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_slug(text: str, max_words: int = 5) -> str:
    """Сделать slug из произвольного текста."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    words = text.split()[:max_words]
    slug = "_".join(words)
    return re.sub(r"[^a-z0-9_]", "", slug) or "query"
