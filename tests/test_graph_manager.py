"""
Тесты для GraphManager — персистентный граф знаний.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.modules.graph_manager import GraphManager, parse_wiki_links


@pytest.fixture
def wiki_dir(tmp_path: Path) -> Path:
    """Временная wiki-директория."""
    d = tmp_path / "wiki"
    d.mkdir()
    return d


@pytest.fixture
def gm(wiki_dir: Path) -> GraphManager:
    """GraphManager с чистым graph.json."""
    return GraphManager(wiki_dir)


# ── Добавление узлов ──────────────────────────────────────────────


class TestNodes:
    def test_add_article_node(self, gm: GraphManager) -> None:
        gm.add_article_node("2026-04-08_youtube_transformers", "Transformers explained", "2026-04-08")
        assert "article:2026-04-08_youtube_transformers" in gm._nodes
        node = gm._nodes["article:2026-04-08_youtube_transformers"]
        assert node["type"] == "article"
        assert node["title"] == "Transformers explained"

    def test_add_concept_node(self, gm: GraphManager) -> None:
        gm.add_concept_node("Python", "python")
        assert "concept:python" in gm._nodes
        assert gm._nodes["concept:python"]["mentions"] == 1

    def test_concept_node_increments_mentions(self, gm: GraphManager) -> None:
        gm.add_concept_node("Python", "python")
        gm.add_concept_node("Python", "python")
        gm.add_concept_node("Python", "python")
        assert gm._nodes["concept:python"]["mentions"] == 3


# ── Добавление рёбер ─────────────────────────────────────────────


class TestEdges:
    def test_add_edge(self, gm: GraphManager) -> None:
        gm.add_article_node("art1", "Article 1", "2026-04-08")
        gm.add_concept_node("Python", "python")
        gm.add_edge("article:art1", "concept:python", "discusses")
        assert len(gm._edges) == 1
        assert gm._edges[0]["from"] == "article:art1"
        assert gm._edges[0]["to"] == "concept:python"
        assert gm._edges[0]["type"] == "discusses"

    def test_edge_deduplication(self, gm: GraphManager) -> None:
        """Одинаковые рёбра не дублируются."""
        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art1", "concept:python", "discusses")
        assert len(gm._edges) == 1

    def test_different_edge_types_not_deduplicated(self, gm: GraphManager) -> None:
        """Рёбра с разными типами — это разные рёбра."""
        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art1", "concept:python", "mentions")
        assert len(gm._edges) == 2

    def test_invalid_edge_type_ignored(self, gm: GraphManager) -> None:
        """Неизвестный тип ребра — пропускается."""
        gm.add_edge("a", "b", "invalid_type")
        assert len(gm._edges) == 0

    def test_remove_edge(self, gm: GraphManager) -> None:
        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art1", "concept:python", "mentions")
        gm.remove_edge("article:art1", "concept:python")
        assert len(gm._edges) == 0


# ── Запросы к графу ───────────────────────────────────────────────


class TestQueries:
    @pytest.fixture
    def populated_gm(self, gm: GraphManager) -> GraphManager:
        """Граф с тестовыми данными."""
        gm.add_article_node("art1", "Article 1", "2026-04-08")
        gm.add_article_node("art2", "Article 2", "2026-04-09")
        gm.add_concept_node("Python", "python")
        gm.add_concept_node("Transformer", "transformer")
        gm.add_concept_node("Attention", "attention")

        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art1", "concept:transformer", "discusses")
        gm.add_edge("article:art2", "concept:python", "discusses")
        gm.add_edge("concept:transformer", "concept:attention", "related_to")
        return gm

    def test_get_neighbors_depth_1(self, populated_gm: GraphManager) -> None:
        neighbors = populated_gm.get_neighbors("article:art1", depth=1)
        neighbor_ids = {n["id"] for n in neighbors}
        assert "concept:python" in neighbor_ids
        assert "concept:transformer" in neighbor_ids
        assert all(n["depth"] == 1 for n in neighbors)

    def test_get_neighbors_depth_2(self, populated_gm: GraphManager) -> None:
        neighbors = populated_gm.get_neighbors("article:art1", depth=2)
        neighbor_ids = {n["id"] for n in neighbors}
        # depth 1: python, transformer
        # depth 2: art2 (через python), attention (через transformer)
        assert "concept:attention" in neighbor_ids
        assert "article:art2" in neighbor_ids

    def test_get_neighbors_depth_0(self, populated_gm: GraphManager) -> None:
        neighbors = populated_gm.get_neighbors("article:art1", depth=0)
        assert neighbors == []

    def test_get_related_concepts(self, populated_gm: GraphManager) -> None:
        related = populated_gm.get_related_concepts("python")
        # python связан с transformer через art1, и с attention — нет (только через transformer)
        assert "transformer" in related

    def test_get_related_concepts_via_shared_article(self, populated_gm: GraphManager) -> None:
        """Концепты, связанные через общую статью."""
        related = populated_gm.get_related_concepts("transformer")
        # transformer → art1 → python
        assert "python" in related
        # transformer → attention (прямая связь)
        assert "attention" in related

    def test_find_paths(self, populated_gm: GraphManager) -> None:
        paths = populated_gm.find_paths("concept:python", "concept:attention")
        assert len(paths) > 0
        # Каждый путь должен начинаться с python и заканчиваться attention
        for path in paths:
            assert path[0] == "concept:python"
            assert path[-1] == "concept:attention"

    def test_find_paths_no_path(self, gm: GraphManager) -> None:
        gm.add_concept_node("A", "a")
        gm.add_concept_node("B", "b")
        # Нет рёбер — нет путей
        paths = gm.find_paths("concept:a", "concept:b")
        assert paths == []

    def test_find_paths_same_node(self, gm: GraphManager) -> None:
        paths = gm.find_paths("concept:a", "concept:a")
        assert paths == [["concept:a"]]


# ── Статистика и экспорт ──────────────────────────────────────────


class TestStatsAndExport:
    def test_get_stats_empty(self, gm: GraphManager) -> None:
        stats = gm.get_stats()
        assert stats["nodes"] == 0
        assert stats["edges"] == 0

    def test_get_stats(self, gm: GraphManager) -> None:
        gm.add_article_node("art1", "Art 1", "2026-04-08")
        gm.add_concept_node("Python", "python")
        gm.add_edge("article:art1", "concept:python", "discusses")

        stats = gm.get_stats()
        assert stats["nodes"] == 2
        assert stats["edges"] == 1
        assert stats["articles"] == 1
        assert stats["concepts"] == 1
        assert len(stats["most_connected"]) > 0

    def test_export_for_visualization(self, gm: GraphManager) -> None:
        gm.add_article_node("art1", "Art 1", "2026-04-08")
        gm.add_concept_node("Python", "python")
        gm.add_edge("article:art1", "concept:python", "discusses")

        export = gm.export_for_visualization()

        # D3.js формат
        assert "nodes" in export
        assert "links" in export
        assert len(export["nodes"]) == 2
        assert len(export["links"]) == 1

        # Проверить формат узлов
        node_ids = {n["id"] for n in export["nodes"]}
        assert "article:art1" in node_ids
        assert "concept:python" in node_ids

        # Проверить формат рёбер
        link = export["links"][0]
        assert "source" in link
        assert "target" in link
        assert "type" in link


# ── Персистентность ──────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self, wiki_dir: Path) -> None:
        """Данные сохраняются и восстанавливаются из graph.json."""
        gm1 = GraphManager(wiki_dir)
        gm1.add_article_node("art1", "Article 1", "2026-04-08")
        gm1.add_concept_node("Python", "python")
        gm1.add_edge("article:art1", "concept:python", "discusses")

        # Создать новый экземпляр — загрузит из файла
        gm2 = GraphManager(wiki_dir)
        assert "article:art1" in gm2._nodes
        assert "concept:python" in gm2._nodes
        assert len(gm2._edges) == 1

    def test_graph_json_format(self, wiki_dir: Path) -> None:
        """graph.json — валидный JSON с правильной структурой."""
        gm = GraphManager(wiki_dir)
        gm.add_article_node("art1", "Art 1", "2026-04-08")
        gm.add_concept_node("Test", "test")
        gm.add_edge("article:art1", "concept:test", "discusses")

        data = json.loads((wiki_dir / "graph.json").read_text(encoding="utf-8"))
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], dict)
        assert isinstance(data["edges"], list)

    def test_load_corrupted_json(self, wiki_dir: Path) -> None:
        """Повреждённый graph.json не крашит приложение."""
        (wiki_dir / "graph.json").write_text("{invalid json", encoding="utf-8")
        gm = GraphManager(wiki_dir)
        assert gm._nodes == {}
        assert gm._edges == []

    def test_load_nonexistent(self, wiki_dir: Path) -> None:
        """Отсутствующий graph.json — пустой граф."""
        gm = GraphManager(wiki_dir)
        assert gm._nodes == {}
        assert gm._edges == []


# ── Backlinks в concept pages ─────────────────────────────────────


class TestBacklinks:
    def test_update_backlinks(self, wiki_dir: Path) -> None:
        concepts_dir = wiki_dir / "concepts"
        concepts_dir.mkdir()

        # Создать concept page
        concept_page = concepts_dir / "python.md"
        concept_page.write_text(
            '---\ntype: concept\nterm: "Python"\nmentions: 1\n---\n\n'
            "# Python\n\n## Синтез\n\nОписание.\n\n## Упоминания\n\n"
            "- [[art1]] — контекст\n",
            encoding="utf-8",
        )

        gm = GraphManager(wiki_dir)
        gm.add_article_node("art1", "Art 1", "2026-04-08")
        gm.add_article_node("art2", "Art 2", "2026-04-09")
        gm.add_concept_node("Python", "python")
        gm.add_edge("article:art1", "concept:python", "discusses")
        gm.add_edge("article:art2", "concept:python", "mentions")

        updated = gm.update_backlinks_in_concepts(concepts_dir)
        assert updated == 1

        content = concept_page.read_text(encoding="utf-8")
        assert "## Обратные ссылки" in content
        assert "[[art1]]" in content
        assert "[[art2]]" in content
        assert "discusses" in content
        assert "mentions" in content

    def test_backlinks_no_concept_file(self, wiki_dir: Path) -> None:
        """Если concept-файл не существует, пропускаем без ошибки."""
        concepts_dir = wiki_dir / "concepts"
        concepts_dir.mkdir()

        gm = GraphManager(wiki_dir)
        gm.add_edge("article:art1", "concept:missing", "discusses")
        # Не должно бросить исключение
        updated = gm.update_backlinks_in_concepts(concepts_dir)
        assert updated == 0


# ── Batch-обновление ──────────────────────────────────────────────


class TestBatchUpdate:
    def test_update_from_knowledge(self, gm: GraphManager) -> None:
        gm.update_from_knowledge(
            folder_name="2026-04-08_youtube_transformers",
            title="Transformers explained",
            date="2026-04-08",
            wiki_links=["Python", "Transformer", "Attention"],
        )

        assert "article:2026-04-08_youtube_transformers" in gm._nodes
        assert "concept:python" in gm._nodes
        assert "concept:transformer" in gm._nodes
        assert "concept:attention" in gm._nodes
        assert len(gm._edges) == 3


# ── Утилиты ──────────────────────────────────────────────────────


class TestParseWikiLinks:
    def test_parse_wiki_links(self) -> None:
        text = "Изучаем [[Python]] и [[Machine Learning]] с помощью [[Ollama]]."
        links = parse_wiki_links(text)
        assert links == ["Python", "Machine Learning", "Ollama"]

    def test_filter_file_links(self) -> None:
        text = "Ссылка на [[description.md]] и [[media.jpg]] и [[Python]]."
        links = parse_wiki_links(text)
        assert links == ["Python"]

    def test_filter_numeric_media(self) -> None:
        text = "[[01_123456_image]] и [[Transformer]]"
        links = parse_wiki_links(text)
        assert links == ["Transformer"]

    def test_empty_text(self) -> None:
        assert parse_wiki_links("") == []
        assert parse_wiki_links("No links here") == []
