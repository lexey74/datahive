"""
WikiLinter — проверка здоровья wiki по паттерну Karpathy LLM Wiki.

Проверяет:
  1. Осиротевшие папки (есть в downloads/, но нет в index.md)
  2. Битые wiki-ссылки [[...]] (упомянуты в md-файлах, но файл не существует)
  3. Пустые/шаблонные concept-страницы (нет реального синтеза, 0 упоминаний)
  4. Теги без собственной concept-страницы (встречаются в Knowledge.md, но нет wiki/concepts/{tag}.md)
  5. Orphan-страницы в wiki/queries/ без обратных ссылок
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Не считать концепты пустыми в течение этого количества дней после создания
EMPTY_CONCEPT_GRACE_DAYS = int(os.getenv("CONCEPT_GRACE_DAYS", "7"))


class WikiLintResult:
    """Результат lint-прогона."""

    def __init__(self) -> None:
        self.orphan_folders: list[str] = []          # папки не в index.md
        self.broken_links: list[tuple[str, str]] = [] # (файл, [[link]])
        self.empty_concepts: list[str] = []           # концепты без синтеза
        self.unlinked_tags: list[str] = []            # теги без concept-страницы
        self.orphan_queries: list[str] = []           # queries без источников

    @property
    def total_issues(self) -> int:
        return (
            len(self.orphan_folders)
            + len(self.broken_links)
            + len(self.empty_concepts)
            + len(self.unlinked_tags)
            + len(self.orphan_queries)
        )

    def format_report(self) -> str:
        """Форматированный отчёт для отправки в Telegram."""
        lines = [f"🔍 <b>Wiki Lint Report</b> — найдено проблем: <b>{self.total_issues}</b>\n"]

        if self.orphan_folders:
            lines.append(f"📂 <b>Осиротевшие папки</b> ({len(self.orphan_folders)}):")
            for f in self.orphan_folders[:10]:
                lines.append(f"  • <code>{f}</code>")
            if len(self.orphan_folders) > 10:
                lines.append(f"  … и ещё {len(self.orphan_folders) - 10}")
            lines.append("")

        if self.broken_links:
            lines.append(f"🔗 <b>Битые ссылки</b> ({len(self.broken_links)}):")
            for file, link in self.broken_links[:8]:
                lines.append(f"  • <code>{file}</code> → <code>{link}</code>")
            if len(self.broken_links) > 8:
                lines.append(f"  … и ещё {len(self.broken_links) - 8}")
            lines.append("")

        if self.empty_concepts:
            lines.append(f"📄 <b>Пустые концепты</b> ({len(self.empty_concepts)}):")
            for c in self.empty_concepts[:8]:
                lines.append(f"  • <code>{c}</code>")
            lines.append("")

        if self.unlinked_tags:
            lines.append(f"🏷 <b>Теги без concept-страниц</b> ({len(self.unlinked_tags)}):")
            tags_str = ", ".join(f"<code>{t}</code>" for t in self.unlinked_tags[:12])
            lines.append(f"  {tags_str}")
            lines.append("")

        if self.orphan_queries:
            lines.append(f"❓ <b>Запросы без источников</b> ({len(self.orphan_queries)}):")
            for q in self.orphan_queries[:5]:
                lines.append(f"  • <code>{q}</code>")
            lines.append("")

        if self.total_issues == 0:
            lines.append("✅ Проблем не найдено — wiki в хорошем состоянии!")

        return "\n".join(lines)


class WikiLinter:
    """
    Проверяет здоровье wiki пользователя.

    Использование:
        linter = WikiLinter(user_root=Path("users/lexey"))
        result = linter.run()
        print(result.format_report())
    """

    def __init__(self, user_root: Path) -> None:
        self.user_root = Path(user_root)
        self.downloads_dir = user_root / "downloads"
        self.index_path = user_root / "index.md"
        self.wiki_dir = user_root / "wiki"
        self.concepts_dir = self.wiki_dir / "concepts"
        self.queries_dir = self.wiki_dir / "queries"

    def run(self) -> WikiLintResult:
        """Запустить все проверки и вернуть результат."""
        result = WikiLintResult()

        self._check_orphan_folders(result)
        self._check_broken_links(result)
        self._check_empty_concepts(result)
        self._check_unlinked_tags(result)
        self._check_orphan_queries(result)

        logger.info(
            f"WikiLinter: завершён — найдено {result.total_issues} проблем "
            f"(orphan_folders={len(result.orphan_folders)}, "
            f"broken_links={len(result.broken_links)}, "
            f"empty_concepts={len(result.empty_concepts)})"
        )
        return result

    # ── Проверка 1: осиротевшие папки ─────────────────────────────

    def _check_orphan_folders(self, result: WikiLintResult) -> None:
        """Папки в downloads/, которые не упомянуты в index.md."""
        if not self.downloads_dir.exists():
            return
        index_content = self._read_safe(self.index_path)
        for folder in self.downloads_dir.iterdir():
            if folder.is_dir() and folder.name not in index_content:
                result.orphan_folders.append(folder.name)

    # ── Проверка 2: битые wiki-ссылки ─────────────────────────────

    def _check_broken_links(self, result: WikiLintResult) -> None:
        """[[ссылки]], которые упомянуты в md-файлах, но не существуют как папка или файл."""
        # Собираем все валидные имена: папки в downloads/ + файлы в wiki/
        valid_names: set[str] = set()
        if self.downloads_dir.exists():
            valid_names.update(f.name for f in self.downloads_dir.iterdir() if f.is_dir())
        if self.wiki_dir.exists():
            valid_names.update(f.stem for f in self.wiki_dir.rglob("*.md"))

        # Сканируем все md-файлы в wiki/ (не в downloads/)
        if not self.wiki_dir.exists():
            return
        for md_file in self.wiki_dir.rglob("*.md"):
            content = self._read_safe(md_file)
            links = re.findall(r"\[\[([^\]|#]+)\]\]", content)
            for link in links:
                link_clean = link.split("|")[0].strip()
                # slug-версия ссылки
                slug = re.sub(r"[^\w\s-]", "", link_clean.lower())
                slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
                if link_clean not in valid_names and slug not in valid_names:
                    result.broken_links.append((md_file.name, link_clean))

    # ── Проверка 3: пустые концепт-страницы ───────────────────────

    def _check_empty_concepts(self, result: WikiLintResult) -> None:
        """Концепт-страницы с шаблонным Синтезом и 0 упоминаний.

        Концепты, созданные недавно (младше EMPTY_CONCEPT_GRACE_DAYS),
        не считаются пустыми — допускается период «grace», когда страницы
        могли быть созданы автоматически и ещё не набрали упоминаний.
        """
        if not self.concepts_dir.exists():
            return

        for page in self.concepts_dir.glob("*.md"):
            content = self._read_safe(page)
            mentions_val = _parse_frontmatter_field(content, "mentions")
            mentions_count = int(mentions_val) if mentions_val and mentions_val.isdigit() else 0
            has_template_synthesis = "_Накапливается автоматически" in content

            # Если есть упоминания или нет шаблонного синтеза — не считать пустым
            if mentions_count != 0 or not has_template_synthesis:
                continue

            # Если есть поле first_seen и дата внутри grace-period — пропускаем
            first_seen_val = _parse_frontmatter_field(content, "first_seen")
            if first_seen_val:
                try:
                    first_seen_date = datetime.strptime(first_seen_val, "%Y-%m-%d")
                    age_days = (datetime.now() - first_seen_date).days
                    if age_days < EMPTY_CONCEPT_GRACE_DAYS:
                        continue
                except Exception:
                    # Если не удалось распарсить дату — считаем страницу старой
                    pass

            result.empty_concepts.append(page.stem)

    # ── Проверка 4: теги без concept-страниц ──────────────────────

    def _check_unlinked_tags(self, result: WikiLintResult) -> None:
        """Теги из Knowledge.md, для которых нет concept-страницы."""
        if not self.downloads_dir.exists():
            return

        all_tags: set[str] = set()
        for knowledge_md in self.downloads_dir.rglob("Knowledge.md"):
            content = self._read_safe(knowledge_md)
            # Формат 1: tags:\n  - tag_name  (YAML-список)
            tags_block = re.search(r"^tags:\s*\n((?:\s+- .+\n)*)", content, re.MULTILINE)
            if tags_block:
                tags = re.findall(r"- (.+)", tags_block.group(1))
                all_tags.update(t.strip() for t in tags if t.strip() not in ("inbox",))
            # Формат 2: tags: [#tag1, #tag2]  (inline с опциональным #)
            inline = re.search(r"^tags:\s*\[(.+)\]", content, re.MULTILINE)
            if inline:
                for t in inline.group(1).split(","):
                    t = t.strip().lstrip("#")
                    if t and t not in ("inbox",):
                        all_tags.add(t)

        existing_concepts: set[str] = set()
        if self.concepts_dir.exists():
            existing_concepts.update(f.stem for f in self.concepts_dir.glob("*.md"))

        for tag in all_tags:
            slug = re.sub(r"[^a-z0-9]", "_", tag.lower()).strip("_")
            if slug not in existing_concepts and tag.lower() not in existing_concepts:
                result.unlinked_tags.append(tag)

        # Сортируем для читаемости
        result.unlinked_tags.sort()

    # ── Проверка 5: orphan queries ─────────────────────────────────

    def _check_orphan_queries(self, result: WikiLintResult) -> None:
        """Файлы в wiki/queries/ без указанных источников (пустой раздел Источники)."""
        if not self.queries_dir.exists():
            return
        for query_file in self.queries_dir.glob("*.md"):
            content = self._read_safe(query_file)
            sources_section = _extract_section(content, "## Источники")
            if not sources_section or "_нет источников_" in sources_section:
                result.orphan_queries.append(query_file.stem)

    # ── Утилиты ───────────────────────────────────────────────────

    @staticmethod
    def _read_safe(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""


# ── Текстовые утилиты ─────────────────────────────────────────────

def _parse_frontmatter_field(content: str, field: str) -> str | None:
    pattern = re.compile(rf"^{field}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    return match.group(1).strip().strip("\"'") if match else None


def _extract_section(content: str, header: str) -> str:
    pattern = re.compile(rf"{re.escape(header)}\n(.*?)(?=\n## |\Z)", re.DOTALL)
    match = pattern.search(content)
    return match.group(1).strip() if match else ""
