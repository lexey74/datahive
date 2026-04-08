"""
Тесты для WikiManager, ConceptManager и WikiLinter.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# ── WikiManager ───────────────────────────────────────────────────

class TestWikiManager:
    def test_init_index_created_on_first_update(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.update_index("2026-04-08_youtube_test", "Тестовое видео", ["python", "ai"])
        assert (tmp_path / "index.md").exists()

    def test_index_contains_folder_name(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.update_index("2026-04-08_youtube_test", "Тестовое видео", ["python"])
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "2026-04-08_youtube_test" in content

    def test_index_update_existing(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.update_index("2026-04-08_youtube_test", "Первый саммари", ["python"])
        wm.update_index("2026-04-08_youtube_test", "Обновлённый саммари", ["python", "llm"])
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        # Должна быть только одна запись с этим именем
        assert content.count("2026-04-08_youtube_test") == 1

    def test_index_platform_section(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.update_index("folder_yt", "Видео", ["tag1"], source="youtube")
        wm.update_index("folder_ig", "Пост", ["tag2"], source="instagram")
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "### Youtube" in content
        assert "### Instagram" in content

    def test_log_created_on_append(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.append_log("ingest", "Test ingest", "Теги: python, ai")
        assert (tmp_path / "log.md").exists()

    def test_log_contains_entry(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.append_log("ingest", "YouTube | test_folder", folder_name="test_folder")
        content = (tmp_path / "log.md").read_text(encoding="utf-8")
        assert "ingest" in content
        assert "test_folder" in content

    def test_log_append_only(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.append_log("ingest", "Первый")
        wm.append_log("query", "Второй")
        wm.append_log("lint", "Третий")
        content = (tmp_path / "log.md").read_text(encoding="utf-8")
        assert content.count("## [") == 3

    def test_save_query_answer(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        path = wm.save_query_answer(
            question="Что такое RAG?",
            answer="RAG — это Retrieval Augmented Generation.",
            sources=["2026-04-08_youtube_test"],
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Что такое RAG?" in content
        assert "RAG — это" in content
        assert "2026-04-08_youtube_test" in content

    def test_get_stats_empty(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        stats = wm.get_stats()
        assert stats["total_sources"] == 0
        assert stats["log_entries"] == 0

    def test_get_stats_after_operations(self, tmp_path):
        from src.modules.wiki_manager import WikiManager
        wm = WikiManager(tmp_path)
        wm.update_index("folder1", "Первый", ["tag1"])
        wm.update_index("folder2", "Второй", ["tag2"])
        wm.append_log("ingest", "folder1")
        wm.append_log("ingest", "folder2")
        wm.save_query_answer("Вопрос?", "Ответ", [])
        stats = wm.get_stats()
        assert stats["total_sources"] == 2
        assert stats["log_entries"] == 3  # 2 ingest + 1 из save_query_answer
        assert stats["query_pages"] == 1


# ── ConceptManager ────────────────────────────────────────────────

class TestConceptManager:
    def _make_knowledge_md(self, tmp_path: Path, content: str) -> Path:
        folder = tmp_path / "2026-04-08_test_folder"
        folder.mkdir()
        kmd = folder / "Knowledge.md"
        kmd.write_text(content, encoding="utf-8")
        return kmd

    def test_update_concepts_creates_pages(self, tmp_path):
        from src.modules.concept_manager import ConceptManager
        kmd = self._make_knowledge_md(
            tmp_path,
            "---\ntags:\n  - python\n---\n\n## Саммари\n\n[[Python]] используется для [[Machine Learning]].\n"
        )
        concepts_dir = tmp_path / "wiki" / "concepts"
        cm = ConceptManager(concepts_dir=concepts_dir, ollama_model="llama3.2")
        updated = cm.update_concepts(
            knowledge_md_path=kmd,
            folder_name="2026-04-08_test_folder",
            tags=["python"],
        )
        assert len(updated) > 0
        assert concepts_dir.exists()
        pages = list(concepts_dir.glob("*.md"))
        assert len(pages) > 0

    def test_concept_page_has_correct_structure(self, tmp_path):
        from src.modules.concept_manager import ConceptManager
        kmd = self._make_knowledge_md(
            tmp_path,
            "---\ntags:\n  - ai\n---\n\n## Саммари\n\n[[Transformer]] — архитектура.\n"
        )
        concepts_dir = tmp_path / "wiki" / "concepts"
        cm = ConceptManager(concepts_dir=concepts_dir)
        cm.update_concepts(kmd, "test_folder")
        transformer_page = concepts_dir / "transformer.md"
        assert transformer_page.exists()
        content = transformer_page.read_text(encoding="utf-8")
        assert "type: concept" in content
        assert "## Синтез" in content
        assert "## Упоминания" in content
        assert "test_folder" in content

    def test_concept_mentions_increment(self, tmp_path):
        from src.modules.concept_manager import ConceptManager
        concepts_dir = tmp_path / "wiki" / "concepts"
        cm = ConceptManager(concepts_dir=concepts_dir)

        for i in range(3):
            src_dir = tmp_path / f"src{i}"
            folder = src_dir / "2026-04-08_test_folder"
            folder.mkdir(parents=True, exist_ok=True)
            kmd = folder / "Knowledge.md"
            kmd.write_text(f"---\n---\n\n[[Python]] упоминание {i}.", encoding="utf-8")
            cm.update_concepts(kmd, f"folder_{i}")

        python_page = concepts_dir / "python.md"
        assert python_page.exists()
        content = python_page.read_text(encoding="utf-8")
        match = re.search(r"mentions:\s*(\d+)", content)
        assert match and int(match.group(1)) == 3

    def test_list_concepts(self, tmp_path):
        from src.modules.concept_manager import ConceptManager
        kmd = self._make_knowledge_md(
            tmp_path,
            "## Саммари\n\n[[Python]] и [[AI]] в действии.\n"
        )
        concepts_dir = tmp_path / "wiki" / "concepts"
        cm = ConceptManager(concepts_dir=concepts_dir)
        cm.update_concepts(kmd, "test_folder")
        concepts = cm.list_concepts()
        assert len(concepts) >= 1
        assert all("term" in c and "mentions" in c for c in concepts)


# ── WikiLinter ────────────────────────────────────────────────────

class TestWikiLinter:
    def _setup_user_root(self, tmp_path: Path) -> Path:
        """Создать структуру пользователя для тестов."""
        downloads = tmp_path / "downloads"
        downloads.mkdir()
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "concepts").mkdir()
        (wiki / "queries").mkdir()
        return tmp_path

    def test_no_issues_empty_wiki(self, tmp_path):
        from src.modules.wiki_linter import WikiLinter
        user_root = self._setup_user_root(tmp_path)
        linter = WikiLinter(user_root)
        result = linter.run()
        assert result.total_issues == 0

    def test_orphan_folders_detected(self, tmp_path):
        from src.modules.wiki_linter import WikiLinter
        from src.modules.wiki_manager import WikiManager
        user_root = self._setup_user_root(tmp_path)
        # Создаём папку в downloads, но не добавляем в index
        (user_root / "downloads" / "2026-04-08_orphan_folder").mkdir()
        linter = WikiLinter(user_root)
        result = linter.run()
        assert "2026-04-08_orphan_folder" in result.orphan_folders

    def test_no_orphan_when_indexed(self, tmp_path):
        from src.modules.wiki_linter import WikiLinter
        from src.modules.wiki_manager import WikiManager
        user_root = self._setup_user_root(tmp_path)
        folder_name = "2026-04-08_indexed_folder"
        (user_root / "downloads" / folder_name).mkdir()
        # Добавляем в index
        wm = WikiManager(user_root)
        wm.update_index(folder_name, "Тест", ["tag1"])
        linter = WikiLinter(user_root)
        result = linter.run()
        assert folder_name not in result.orphan_folders

    def test_empty_concepts_detected(self, tmp_path):
        from src.modules.wiki_linter import WikiLinter
        user_root = self._setup_user_root(tmp_path)
        # Создаём концепт-страницу с шаблонным синтезом
        concept_page = user_root / "wiki" / "concepts" / "python.md"
        concept_page.write_text(
            "---\ntype: concept\nterm: \"Python\"\nmentions: 0\n---\n\n"
            "## Синтез\n\n_Накапливается автоматически по мере появления новых источников._\n\n"
            "## Упоминания\n\n",
            encoding="utf-8",
        )
        linter = WikiLinter(user_root)
        result = linter.run()
        assert "python" in result.empty_concepts

    def test_format_report_no_issues(self, tmp_path):
        from src.modules.wiki_linter import WikiLinter
        user_root = self._setup_user_root(tmp_path)
        linter = WikiLinter(user_root)
        result = linter.run()
        report = result.format_report()
        assert "✅" in report
        assert "0" in report

    def test_format_report_with_issues(self, tmp_path):
        from src.modules.wiki_linter import WikiLintResult
        result = WikiLintResult()
        result.orphan_folders = ["folder1", "folder2"]
        result.broken_links = [("concepts/python.md", "NonExistent")]
        result.unlinked_tags = ["machine_learning", "deep_learning"]
        report = result.format_report()
        assert "Осиротевшие папки" in report
        assert "Битые ссылки" in report
        assert "concept" in report  # "Теги без concept-страниц"
        assert str(result.total_issues) in report  # "5"


# ── WikiManager utils ─────────────────────────────────────────────

class TestWikiManagerUtils:
    def test_strip_markdown(self):
        from src.modules.wiki_manager import _strip_markdown
        assert _strip_markdown("**Привет** [[мир]]") == "Привет мир"
        assert _strip_markdown("[текст](http://url.com)") == "текст"
        assert _strip_markdown("# Заголовок") == "Заголовок"

    def test_make_slug(self):
        from src.modules.wiki_manager import _make_slug
        # ASCII слова работают корректно
        assert _make_slug("Python Machine Learning") == "python_machine_learning"
        # Нелатинские символы стрипаются, остаётся ASCII часть
        result = _make_slug("Что такое RAG?")
        assert "rag" in result  # RAG должен присутствовать
        # Пустая строка возвращает fallback
        assert _make_slug("???") == "query"
