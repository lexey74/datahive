#!/usr/bin/env python3
"""
Rebuild users/lexey/wiki/graph.json from existing Knowledge.md files.

This fast deterministic pass creates article -> concept edges from Obsidian
[[wiki-links]] and frontmatter tags. It does not call llama.cpp.

Run:
    python3 scripts/rebuild_graph.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from src.modules.graph_manager import parse_wiki_links
from src.modules.wiki_manager import WikiManager

DEFAULT_USER_ROOT = ROOT / "users" / "lexey"


def parse_frontmatter_field(content: str, field: str) -> str | None:
    pattern = re.compile(rf"^{field}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    return match.group(1).strip().strip("\"'") if match else None


def parse_tags(content: str) -> list[str]:
    inline = re.search(r"^tags:\s*\[(.+)\]", content, re.MULTILINE)
    if inline:
        return [t.strip().lstrip("#") for t in inline.group(1).split(",") if t.strip()]

    block = re.search(r"^tags:\s*\n((?:[ \t]+-[ \t].+\n)*)", content, re.MULTILINE)
    if block:
        return [
            re.sub(r"^#?", "", t).strip()
            for t in re.findall(r"-\s+(.+)", block.group(1))
            if t.strip()
        ]

    return []


def concept_terms(content: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    for term in [*parse_wiki_links(content), *parse_tags(content)]:
        normalized = term.split("|", 1)[0].strip()
        normalized = normalized.lstrip("#").replace("_", " ")
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(normalized)

    return terms


def rebuild_graph(user_root: Path) -> dict[str, Any]:
    user_root = Path(user_root)
    downloads_dir = user_root / "downloads"

    if not downloads_dir.exists():
        raise FileNotFoundError(f"downloads/ not found: {downloads_dir}")

    wm = WikiManager(user_root)
    wm.ensure_dirs()

    # Full rebuild, so repeated runs do not inflate concept mention counters.
    wm.graph_manager._nodes = {}
    wm.graph_manager._edges = []
    wm.graph_manager._save()

    folders = sorted(
        folder
        for folder in downloads_dir.iterdir()
        if folder.is_dir() and (folder / "Knowledge.md").exists()
    )

    linked = 0
    unlinked: list[str] = []
    input_edges = 0

    for folder in folders:
        knowledge_path = folder / "Knowledge.md"
        content = knowledge_path.read_text(encoding="utf-8")
        terms = concept_terms(content)

        title = parse_frontmatter_field(content, "title") or folder.name
        date = parse_frontmatter_field(content, "date") or ""

        if terms:
            linked += 1
            input_edges += len(terms)
        else:
            unlinked.append(folder.name)

        wm.update_graph(
            folder_name=folder.name,
            title=title,
            date=date,
            wiki_links=terms,
        )

    stats = wm.get_graph_stats()
    return {
        "knowledge_files": len(folders),
        "linked_documents": linked,
        "unlinked_documents": len(unlinked),
        "unlinked": unlinked,
        "graph_nodes": stats["nodes"],
        "graph_edges": stats["edges"],
        "input_terms": input_edges,
        "graph_file": wm.wiki_dir / "graph.json",
    }


def main() -> None:
    user_root = DEFAULT_USER_ROOT
    downloads_dir = user_root / "downloads"

    if not downloads_dir.exists():
        print(f"downloads/ not found: {downloads_dir}")
        sys.exit(1)

    result = rebuild_graph(user_root)
    print(f"Knowledge.md files: {result['knowledge_files']}")
    print(f"Documents with concept edges: {result['linked_documents']}")
    print(f"Documents without concept edges: {result['unlinked_documents']}")
    print(f"Graph nodes: {result['graph_nodes']}")
    print(f"Graph edges: {result['graph_edges']} (input terms: {result['input_terms']})")
    print(f"Graph file: {result['graph_file']}")

    unlinked = result["unlinked"]
    if unlinked:
        print("\nUnlinked documents:")
        for name in unlinked[:20]:
            print(f"- {name}")
        if len(unlinked) > 20:
            print(f"- ... and {len(unlinked) - 20} more")


if __name__ == "__main__":
    main()
