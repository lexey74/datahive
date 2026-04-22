"""
Тесты для ConceptManager — создание concept pages, relationships, compile_wiki.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.modules.concept_manager import (
    ConceptManager,
    RELATIONSHIP_TYPES,
    _term_to_slug,
    _extract_section,
    _append_relationship,
    _dedupe,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def concepts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "wiki" / "concepts"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def cm(concepts_dir: Path) -> ConceptManager:
    return ConceptManager(
        concepts_dir=concepts_dir,
        ollama_model="test-model",
        ollama_url="http://localhost:9999",
    )


@pytest.fixture
def knowledge_md(tmp_path: Path) -> Path:
    """Создать тестовый Knowledge.md с wiki-ссылками."""
    p = tmp_path / "Knowledge.md"
    p.write_text(
        "---\ntitle: Test\n---\n\n"
        "# Test Knowledge\n\n"
        "## AI Summary\n"
        "- [[Python]] is used for building [[Transformer]] models\n"
        "- [[RAG]] depends on [[ChromaDB]] for vector search\n",
        encoding="utf-8",
    )
    return p


def _mock_llm_response(content: str) -> dict:
    """Хелпер: формат ответа LlamaCppClient.chat()."""
    return {"message": {"content": content}}


# ── Утилиты ──────────────────────────────────────────────────────


class TestUtilities:
    def test_term_to_slug(self):
        assert _term_to_slug("Python") == "python"
        assert _term_to_slug("GPT-4") == "gpt_4"
        assert _term_to_slug("RAG Pipeline") == "rag_pipeline"

    def test_dedupe_preserves_order(self):
        assert _dedupe(["Python", "python", "RAG", "rag"]) == ["Python", "RAG"]

    def test_extract_section(self):
        content = "## Синтез\nТекст синтеза\n\n## Связи\nСвязь1\n\n## Упоминания\n"
        assert "Текст синтеза" in _extract_section(content, "## Синтез")
        assert "Связь1" in _extract_section(content, "## Связи")

    def test_append_relationship_to_existing_section(self):
        content = (
            "# Test\n\n## Связи\n- [[A]] →(uses)→ [[B]]\n\n## Упоминания\n"
        )
        result = _append_relationship(content, "- [[C]] →(extends)→ [[D]]")
        assert "- [[C]] →(extends)→ [[D]]" in result
        # Секция Упоминания не затронута
        assert "## Упоминания" in result

    def test_append_relationship_creates_section(self):
        content = "# Test\n\n## Упоминания\n- [[folder1]]\n"
        result = _append_relationship(content, "- [[A]] →(uses)→ [[B]]")
        assert "## Связи\n- [[A]] →(uses)→ [[B]]" in result
        assert result.index("## Связи") < result.index("## Упоминания")


# ── Создание concept page ────────────────────────────────────────


class TestCreateConceptPage:
    def test_creates_new_concept_page(self, cm, concepts_dir, knowledge_md):
        """update_concepts создаёт .md файлы для каждого wiki-term."""
        # Мокаем LLM клиент — при первом вызове не нужен (mentions < 2)
        with patch.object(cm, "_get_client"):
            result = cm.update_concepts(
                knowledge_md_path=knowledge_md,
                folder_name="2026-04-22_test_folder",
            )

        assert len(result) > 0
        # Проверяем что файл Python создан
        python_page = concepts_dir / "python.md"
        assert python_page.exists()

        content = python_page.read_text(encoding="utf-8")
        assert 'term: "Python"' in content
        assert "## Синтез" in content
        assert "## Связи" in content
        assert "## Упоминания" in content
        assert "2026-04-22_test_folder" in content

    def test_missing_knowledge_md(self, cm):
        """Несуществующий Knowledge.md не вызывает ошибку."""
        result = cm.update_concepts(
            knowledge_md_path=Path("/nonexistent/Knowledge.md"),
            folder_name="test",
        )
        assert result == []

    def test_tags_added_as_concepts(self, cm, concepts_dir, tmp_path):
        """Теги из ai_result добавляются как дополнительные концепты."""
        km = tmp_path / "Knowledge.md"
        km.write_text("---\ntitle: T\n---\n# T\nSimple content", encoding="utf-8")

        with patch.object(cm, "_get_client"):
            result = cm.update_concepts(
                knowledge_md_path=km,
                folder_name="test_folder",
                tags=["machine_learning", "deep_learning"],
            )

        assert any("machine_learning" in f for f in result)

    def test_updates_existing_page_mentions(self, cm, concepts_dir, knowledge_md):
        """Повторный ingest добавляет новое упоминание."""
        with patch.object(cm, "_get_client"):
            cm.update_concepts(knowledge_md_path=knowledge_md, folder_name="folder_1")
            cm.update_concepts(knowledge_md_path=knowledge_md, folder_name="folder_2")

        python_page = concepts_dir / "python.md"
        content = python_page.read_text(encoding="utf-8")
        assert "folder_1" in content
        assert "folder_2" in content
        assert "mentions: 2" in content


# ── Relationships ────────────────────────────────────────────────


class TestCompileRelationships:
    def test_compile_relationships_adds_links(self, cm, concepts_dir):
        """compile_relationships записывает связи в concept pages."""
        # Создать две concept pages вручную
        for term in ["Python", "Transformer"]:
            slug = _term_to_slug(term)
            (concepts_dir / f"{slug}.md").write_text(
                f'---\ntype: concept\nterm: "{term}"\nfirst_seen: 2026-04-22\n'
                f"mentions: 2\n---\n\n# {term}\n\n## Синтез\nTest\n\n"
                f"## Связи\n\n## Упоминания\n- [[folder_1]] — ctx\n- [[folder_2]] — ctx\n",
                encoding="utf-8",
            )

        # Мокаем LLM ответ с одной связью
        mock_client = MagicMock()
        mock_client.chat.return_value = _mock_llm_response(
            json.dumps([{"from": "Python", "type": "uses", "to": "Transformer"}])
        )
        cm._client = mock_client

        added = cm.compile_relationships(
            updated_terms=["Python"],
            knowledge_text="Python uses Transformer architecture",
        )

        assert added >= 1
        python_content = (concepts_dir / "python.md").read_text(encoding="utf-8")
        assert "→(uses)→" in python_content

    def test_compile_relationships_skips_duplicates(self, cm, concepts_dir):
        """Существующие связи не дублируются."""
        rel_line = "- [[Python]] →(uses)→ [[Transformer]]"
        (concepts_dir / "python.md").write_text(
            f'---\ntype: concept\nterm: "Python"\nfirst_seen: 2026-04-22\n'
            f"mentions: 2\n---\n\n# Python\n\n## Синтез\nTest\n\n"
            f"## Связи\n{rel_line}\n\n## Упоминания\n- [[f1]] — ctx\n- [[f2]] — ctx\n",
            encoding="utf-8",
        )
        (concepts_dir / "transformer.md").write_text(
            f'---\ntype: concept\nterm: "Transformer"\nfirst_seen: 2026-04-22\n'
            f"mentions: 1\n---\n\n# Transformer\n\n## Синтез\nTest\n\n"
            f"## Связи\n\n## Упоминания\n- [[f1]] — ctx\n",
            encoding="utf-8",
        )

        mock_client = MagicMock()
        mock_client.chat.return_value = _mock_llm_response(
            json.dumps([{"from": "Python", "type": "uses", "to": "Transformer"}])
        )
        cm._client = mock_client

        added = cm.compile_relationships(
            updated_terms=["Python"],
            knowledge_text="Python uses Transformer",
        )

        # Только одна сторона добавлена (Transformer), Python уже имеет эту связь
        python_content = (concepts_dir / "python.md").read_text(encoding="utf-8")
        assert python_content.count("→(uses)→") == 1

    def test_compile_relationships_validates_type(self, cm, concepts_dir):
        """Неизвестные типы связей заменяются на related-to."""
        for term in ["Alpha", "Beta"]:
            slug = _term_to_slug(term)
            (concepts_dir / f"{slug}.md").write_text(
                f'---\ntype: concept\nterm: "{term}"\nfirst_seen: 2026-04-22\n'
                f"mentions: 2\n---\n\n# {term}\n\n## Синтез\nTest\n\n"
                f"## Связи\n\n## Упоминания\n- [[f1]] — ctx\n- [[f2]] — ctx\n",
                encoding="utf-8",
            )

        mock_client = MagicMock()
        mock_client.chat.return_value = _mock_llm_response(
            json.dumps([{"from": "Alpha", "type": "invented-type", "to": "Beta"}])
        )
        cm._client = mock_client

        cm.compile_relationships(
            updated_terms=["Alpha"],
            knowledge_text="Alpha and Beta",
        )

        content = (concepts_dir / "alpha.md").read_text(encoding="utf-8")
        assert "→(related-to)→" in content

    def test_compile_relationships_no_concepts(self, cm):
        """Пустая директория — 0 связей, без ошибок."""
        assert cm.compile_relationships([], "text") == 0


# ── compile_wiki (полная компиляция) ─────────────────────────────


class TestCompileWiki:
    def test_compile_wiki_merges_duplicates(self, cm, concepts_dir):
        """compile_wiki мержит дубликаты по решению LLM."""
        # Создать два «дубликата»
        (concepts_dir / "python.md").write_text(
            '---\ntype: concept\nterm: "Python"\nfirst_seen: 2026-04-22\n'
            "mentions: 5\n---\n\n# Python\n\n## Синтез\nЯзык программирования\n\n"
            "## Связи\n\n## Упоминания\n- [[f1]] — ctx1\n- [[f2]] — ctx2\n",
            encoding="utf-8",
        )
        (concepts_dir / "python_programming.md").write_text(
            '---\ntype: concept\nterm: "Python Programming"\nfirst_seen: 2026-04-22\n'
            "mentions: 1\n---\n\n# Python Programming\n\n## Синтез\nTest\n\n"
            "## Связи\n\n## Упоминания\n- [[f3]] — ctx3\n",
            encoding="utf-8",
        )

        mock_client = MagicMock()
        # Первый вызов — анализ графа
        mock_client.chat.side_effect = [
            _mock_llm_response(json.dumps({
                "duplicates": [{"keep": "Python", "remove": "Python Programming"}],
                "relationships": [],
            })),
            # Последующие вызовы — обновление синтезов
            _mock_llm_response("Python — мощный язык программирования."),
        ]
        cm._client = mock_client

        result = cm.compile_wiki()

        assert result["duplicates_merged"] == 1
        assert not (concepts_dir / "python_programming.md").exists()
        # Упоминания перенесены
        python_content = (concepts_dir / "python.md").read_text(encoding="utf-8")
        assert "f3" in python_content

    def test_compile_wiki_adds_missing_relationships(self, cm, concepts_dir):
        """compile_wiki добавляет недостающие связи."""
        for term in ["RAG", "ChromaDB"]:
            slug = _term_to_slug(term)
            (concepts_dir / f"{slug}.md").write_text(
                f'---\ntype: concept\nterm: "{term}"\nfirst_seen: 2026-04-22\n'
                f"mentions: 3\n---\n\n# {term}\n\n## Синтез\nTest synthesis\n\n"
                f"## Связи\n\n## Упоминания\n- [[f1]] — a\n- [[f2]] — b\n- [[f3]] — c\n",
                encoding="utf-8",
            )

        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            # Анализ графа
            _mock_llm_response(json.dumps({
                "duplicates": [],
                "relationships": [
                    {"from": "RAG", "type": "depends-on", "to": "ChromaDB"},
                ],
            })),
            # Обновление синтеза RAG
            _mock_llm_response("RAG — техника поиска."),
            # Обновление синтеза ChromaDB
            _mock_llm_response("ChromaDB — векторная БД."),
        ]
        cm._client = mock_client

        result = cm.compile_wiki()

        assert result["relationships_added"] >= 1
        rag_content = (concepts_dir / "rag.md").read_text(encoding="utf-8")
        assert "→(depends-on)→" in rag_content

    def test_compile_wiki_empty_dir(self, cm, concepts_dir):
        """Пустая wiki — пустой результат, без ошибок."""
        result = cm.compile_wiki()
        assert result["relationships_added"] == 0
        assert result["duplicates_merged"] == 0
        assert result["syntheses_updated"] == 0

    def test_compile_wiki_llm_error(self, cm, concepts_dir):
        """Ошибка LLM не ломает compile_wiki."""
        (concepts_dir / "test.md").write_text(
            '---\ntype: concept\nterm: "Test"\nfirst_seen: 2026-04-22\n'
            "mentions: 1\n---\n\n# Test\n\n## Синтез\nX\n\n## Связи\n\n## Упоминания\n- [[f1]] — a\n",
            encoding="utf-8",
        )
        (concepts_dir / "test2.md").write_text(
            '---\ntype: concept\nterm: "Test2"\nfirst_seen: 2026-04-22\n'
            "mentions: 1\n---\n\n# Test2\n\n## Синтез\nY\n\n## Связи\n\n## Упоминания\n- [[f1]] — b\n",
            encoding="utf-8",
        )

        mock_client = MagicMock()
        mock_client.chat.side_effect = ConnectionError("LLM down")
        cm._client = mock_client

        result = cm.compile_wiki()
        assert result["relationships_added"] == 0


# ── Relationship types ───────────────────────────────────────────


class TestRelationshipTypes:
    def test_all_types_defined(self):
        expected = {"uses", "depends-on", "related-to", "contradicts",
                    "extends", "supersedes", "caused"}
        assert RELATIONSHIP_TYPES == expected
