"""
GraphManager — персистентный граф знаний wiki/graph.json.

Управляет двунаправленными связями между статьями и концептами.
Обеспечивает backlinks, поиск соседей и экспорт для визуализации.

Структура graph.json:
  {
    "nodes": { "article:slug": {...}, "concept:slug": {...} },
    "edges": [ { "from": ..., "to": ..., "type": ..., "created": ... } ]
  }
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Допустимые типы рёбер
EDGE_TYPES = frozenset({
    "discusses",
    "mentions",
    "related_to",
    "uses",
    "depends_on",
    "contradicts",
    "extends",
    "supersedes",
})


class GraphManager:
    """
    Управляет wiki/graph.json — персистентный граф знаний.

    Использование:
        gm = GraphManager(wiki_dir=Path("users/lexey/wiki"))
        gm.add_article_node("2026-04-08_youtube_transformers", "Transformers explained", "2026-04-08")
        gm.add_concept_node("Python", "python")
        gm.add_edge("article:2026-04-08_youtube_transformers", "concept:python", "discusses")
    """

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = Path(wiki_dir)
        self.graph_path = self.wiki_dir / "graph.json"
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, str]] = []
        self._auto_save = True
        self._load()

    # ── Управление узлами ─────────────────────────────────────────

    def add_article_node(self, folder_name: str, title: str, date: str) -> None:
        """Добавить или обновить узел статьи."""
        node_id = f"article:{folder_name}"
        self._nodes[node_id] = {
            "type": "article",
            "title": title,
            "created": date,
        }
        if self._auto_save:
            self._save()

    def add_concept_node(self, term: str, slug: str) -> None:
        """Добавить или обновить узел концепта."""
        node_id = f"concept:{slug}"
        if node_id in self._nodes:
            # Увеличить счётчик упоминаний
            self._nodes[node_id]["mentions"] = self._nodes[node_id].get("mentions", 0) + 1
        else:
            self._nodes[node_id] = {
                "type": "concept",
                "term": term,
                "mentions": 1,
            }
        if self._auto_save:
            self._save()

    # ── Управление рёбрами ────────────────────────────────────────

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """
        Добавить ребро между двумя узлами.

        Дедупликация: ребро с тем же (from, to, type) не добавляется повторно.
        """
        if edge_type not in EDGE_TYPES:
            logger.warning(f"GraphManager: неизвестный тип ребра '{edge_type}', пропуск")
            return

        # Дедупликация
        for edge in self._edges:
            if edge["from"] == from_id and edge["to"] == to_id and edge["type"] == edge_type:
                return

        self._edges.append({
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "created": datetime.now().strftime("%Y-%m-%d"),
        })
        if self._auto_save:
            self._save()

    def remove_edge(self, from_id: str, to_id: str) -> None:
        """Удалить все рёбра между from_id и to_id."""
        self._edges = [
            e for e in self._edges
            if not (e["from"] == from_id and e["to"] == to_id)
        ]
        self._save()

    # ── Запросы к графу ───────────────────────────────────────────

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        """
        Получить соседей узла до заданной глубины (BFS).

        Returns:
            Список словарей: {"id": node_id, "depth": int, "edge_type": str}
        """
        if depth < 1:
            return []

        visited: set[str] = {node_id}
        result: list[dict] = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            # Исходящие и входящие рёбра (двунаправленный обход)
            for edge in self._edges:
                neighbor = None
                if edge["from"] == current:
                    neighbor = edge["to"]
                elif edge["to"] == current:
                    neighbor = edge["from"]

                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    result.append({
                        "id": neighbor,
                        "depth": current_depth + 1,
                        "edge_type": edge["type"],
                    })
                    queue.append((neighbor, current_depth + 1))

        return result

    def get_related_concepts(self, concept_slug: str) -> list[str]:
        """
        Получить связанные концепты (через общие статьи или прямые связи).

        Returns:
            Список slug-ов связанных концептов.
        """
        node_id = f"concept:{concept_slug}"
        related: set[str] = set()

        # Прямые связи concept↔concept
        for edge in self._edges:
            if edge["from"] == node_id and edge["to"].startswith("concept:"):
                related.add(edge["to"].removeprefix("concept:"))
            elif edge["to"] == node_id and edge["from"].startswith("concept:"):
                related.add(edge["from"].removeprefix("concept:"))

        # Через общие статьи (concept→article→concept)
        connected_articles: set[str] = set()
        for edge in self._edges:
            if edge["from"] == node_id and edge["to"].startswith("article:"):
                connected_articles.add(edge["to"])
            elif edge["to"] == node_id and edge["from"].startswith("article:"):
                connected_articles.add(edge["from"])

        for article_id in connected_articles:
            for edge in self._edges:
                candidate = None
                if edge["from"] == article_id and edge["to"].startswith("concept:"):
                    candidate = edge["to"].removeprefix("concept:")
                elif edge["to"] == article_id and edge["from"].startswith("concept:"):
                    candidate = edge["from"].removeprefix("concept:")
                if candidate and candidate != concept_slug:
                    related.add(candidate)

        return sorted(related)

    def find_paths(
        self, from_id: str, to_id: str, max_depth: int = 3, max_results: int = 50
    ) -> list[list[str]]:
        """
        Найти все пути между двумя уз��ами (BFS, до max_depth).

        Returns:
            Список путей, каждый путь — список node_id.
        """
        if from_id == to_id:
            return [[from_id]]

        paths: list[list[str]] = []
        queue: deque[list[str]] = deque([[from_id]])

        # Построить adjacency list для скорости
        adj: dict[str, set[str]] = {}
        for edge in self._edges:
            adj.setdefault(edge["from"], set()).add(edge["to"])
            adj.setdefault(edge["to"], set()).add(edge["from"])

        while queue:
            if len(paths) >= max_results:
                break
            path = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            current = path[-1]
            for neighbor in adj.get(current, set()):
                if neighbor in path:
                    continue  # Избегаем циклов
                new_path = path + [neighbor]
                if neighbor == to_id:
                    paths.append(new_path)
                elif len(new_path) <= max_depth:
                    queue.append(new_path)

        return paths

    # ── Статистика и экспорт ──────────────────────────────────────

    def get_stats(self) -> dict:
        """Статистика графа: количество узлов, рёбер, самые связанные узлы."""
        if not self._nodes:
            return {"nodes": 0, "edges": 0, "articles": 0, "concepts": 0, "most_connected": []}

        # Подсчёт связей каждого узла
        connection_count: dict[str, int] = {}
        for edge in self._edges:
            connection_count[edge["from"]] = connection_count.get(edge["from"], 0) + 1
            connection_count[edge["to"]] = connection_count.get(edge["to"], 0) + 1

        # Топ-5 самых связанных
        sorted_nodes = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)
        most_connected = [
            {"id": nid, "connections": count}
            for nid, count in sorted_nodes[:5]
        ]

        articles = sum(1 for n in self._nodes.values() if n.get("type") == "article")
        concepts = sum(1 for n in self._nodes.values() if n.get("type") == "concept")

        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "articles": articles,
            "concepts": concepts,
            "most_connected": most_connected,
        }

    def export_for_visualization(self) -> dict:
        """
        Экспорт в D3.js-совместимый формат.

        Returns:
            {"nodes": [{"id": ..., "group": ..., ...}], "links": [{"source": ..., "target": ..., ...}]}
        """
        nodes_list = []
        for node_id, data in self._nodes.items():
            node_entry = {
                "id": node_id,
                "group": data.get("type", "unknown"),
                **data,
            }
            nodes_list.append(node_entry)

        links_list = []
        for edge in self._edges:
            links_list.append({
                "source": edge["from"],
                "target": edge["to"],
                "type": edge["type"],
                "created": edge.get("created", ""),
            })

        return {"nodes": nodes_list, "links": links_list}

    # ── Backlinks в concept pages ─────────────────────────────────

    def update_backlinks_in_concepts(self, concepts_dir: Path) -> int:
        """
        Обновить секцию '## Обратные ссылки' во всех concept pages.

        Для каждого concept-узла в графе находит все входящие рёбра от статей
        и записывает их в соответствующий concept-файл.

        Returns:
            Количество обновлённых файлов.
        """
        updated = 0

        # Собрать backlinks для каждого концепта: slug → [(folder_name, edge_type)]
        backlinks: dict[str, list[tuple[str, str]]] = {}
        for edge in self._edges:
            if edge["to"].startswith("concept:") and edge["from"].startswith("article:"):
                slug = edge["to"].removeprefix("concept:")
                folder = edge["from"].removeprefix("article:")
                backlinks.setdefault(slug, []).append((folder, edge["type"]))
            elif edge["from"].startswith("concept:") and edge["to"].startswith("article:"):
                slug = edge["from"].removeprefix("concept:")
                folder = edge["to"].removeprefix("article:")
                backlinks.setdefault(slug, []).append((folder, edge["type"]))

        for slug, links in backlinks.items():
            concept_path = concepts_dir / f"{slug}.md"
            if not concept_path.exists():
                continue

            content = concept_path.read_text(encoding="utf-8")

            # Сформировать блок обратных ссылок (дедупликация по (folder, type))
            unique_links = sorted(set(links))
            backlinks_lines = [f"- [[{folder}]] — {etype}" for folder, etype in unique_links]
            backlinks_block = "\n".join(backlinks_lines)

            # Вставить/обновить секцию "## Обратные ссылки"
            section_header = "## Обратные ссылки"
            new_section = f"{section_header}\n\n{backlinks_block}\n"

            if section_header in content:
                # Заменить существующую секцию
                pattern = re.compile(
                    rf"({re.escape(section_header)}\n)(.*?)(?=\n## |\Z)", re.DOTALL
                )
                new_content = pattern.sub(f"\\g<1>\n{backlinks_block}\n", content, count=1)
            else:
                # Вставить перед "## Упоминания" или в конец файла
                if "## Упоминания" in content:
                    new_content = content.replace(
                        "## Упоминания",
                        f"{new_section}\n## Упомин��ния",
                    )
                else:
                    new_content = content.rstrip() + f"\n\n{new_section}"

            if new_content != content:
                concept_path.write_text(new_content, encoding="utf-8")
                updated += 1

        logger.debug(f"GraphManager: обновлено backlinks в {updated} concept pages")
        return updated

    # ── Batch-обновление из Knowledge.md ──────────────────────────

    def update_from_knowledge(
        self,
        folder_name: str,
        title: str,
        date: str,
        wiki_links: list[str],
    ) -> None:
        """
        Batch-обновление графа: добавить article node + edges к концептам.

        Вызывается из pipeline после создания Knowledge.md.
        Использует batch-режим (одна запись на диск в конце).

        Args:
            folder_name: Имя папки статьи
            title: Заголовок статьи
            date: Дата создания (YYYY-MM-DD)
            wiki_links: Список терминов из [[wiki-ссылок]]
        """
        article_id = f"article:{folder_name}"

        # Batch-режим: подавляем промежуточные _save()
        self._auto_save = False
        try:
            self.add_article_node(folder_name, title, date)

            for term in wiki_links:
                slug = _term_to_slug(term)
                if not slug:
                    continue
                concept_id = f"concept:{slug}"
                self.add_concept_node(term, slug)
                self.add_edge(article_id, concept_id, "discusses")
        finally:
            self._auto_save = True
            self._save()

    # ── Персистентность ───────────────────────────────────────────

    def _load(self) -> None:
        """Загрузить граф из graph.json."""
        if not self.graph_path.exists():
            self._nodes = {}
            self._edges = []
            return

        try:
            data = json.loads(self.graph_path.read_text(encoding="utf-8"))
            self._nodes = data.get("nodes", {})
            self._edges = data.get("edges", [])
            logger.debug(
                f"GraphManager: загружен граф — {len(self._nodes)} узлов, {len(self._edges)} рёбер"
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"GraphManager: ошибка чтения graph.json: {e}")
            self._nodes = {}
            self._edges = []

    def _save(self) -> None:
        """
        Атомарная запись graph.json (через temp file + rename).

        П��едотвращает повреждение файла при прерывании процесса.
        """
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": self._nodes,
            "edges": self._edges,
        }

        # Атомарная запись: пишем во временный файл, потом rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.wiki_dir), suffix=".tmp", prefix="graph_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.graph_path))
        except Exception:
            # Удалить временный файл в случае ошибки
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


# ── Утилиты ──────────────────────────────────────────────────────


def _term_to_slug(term: str) -> str:
    """Конвертировать название концепта в slug (совместимо с ConceptManager).

    Поддерживает Unicode (кириллицу, латиницу, CJK и т.п.).
    """
    slug = term.lower()
    # \w включает Unicode word characters (кириллица, латиница, цифры и _)
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:60] or ""


def parse_wiki_links(text: str) -> list[str]:
    """
    Извлечь [[wiki-ссылки]] из markdown-текста.

    Фильтрует служебные ссылки на файлы (description.md, медиа и т.п.)
    и date-prefixed folder names (2026-04-08_youtube_...).
    """
    raw_links = re.findall(r"\[\[([^\]]+)\]\]", text)
    skip = re.compile(
        r"\.(md|jpg|jpeg|png|mp4|webp)\b"    # ссылки на файлы
        r"|^\d{4}-\d{2}-\d{2}_"               # folder names (YYYY-MM-DD_...)
        r"|^\d{2}_\d+_",                      # числовые имена (instagram media)
        re.IGNORECASE,
    )
    return [link for link in raw_links if not skip.search(link)]
