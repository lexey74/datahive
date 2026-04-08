#!/usr/bin/env python3
"""
Одноразовый скрипт: создать concept-страницы для всех папок в downloads/.

Проходит по каждой папке с Knowledge.md, вызывает ConceptManager.update_concepts()
— создаёт wiki/concepts/{tag}.md для всех тегов и [[wiki-ссылок]].

Запуск:
    cd /home/lexey/projects/datahive
    venv/bin/python3 scripts/build_concepts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.concept_manager import ConceptManager
from src.modules.wiki_linter import WikiLinter, _parse_frontmatter_field

USER_ROOT = ROOT / "users" / "lexey"
DOWNLOADS_DIR = USER_ROOT / "downloads"
CONCEPTS_DIR = USER_ROOT / "wiki" / "concepts"

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"


def parse_tags(content: str) -> list[str]:
    """Извлечь теги из YAML frontmatter."""
    import re
    inline = re.search(r"^tags:\s*\[(.+)\]", content, re.MULTILINE)
    if inline:
        return [t.strip().lstrip("#") for t in inline.group(1).split(",") if t.strip()]
    block = re.search(r"^tags:\s*\n((?:[ \t]+-[ \t].+\n)*)", content, re.MULTILINE)
    if block:
        return [re.sub(r"^-\s*#?", "", t).strip() for t in re.findall(r"-\s+(.+)", block.group(1))]
    return []


def main() -> None:
    if not DOWNLOADS_DIR.exists():
        print(f"❌ downloads/ не найден: {DOWNLOADS_DIR}")
        sys.exit(1)

    folders = sorted(
        f for f in DOWNLOADS_DIR.iterdir()
        if f.is_dir() and (f / "Knowledge.md").exists()
    )

    print(f"📂 Папок с Knowledge.md: {len(folders)}")
    print(f"🧠 Модель: {OLLAMA_MODEL}\n")

    cm = ConceptManager(
        concepts_dir=CONCEPTS_DIR,
        ollama_model=OLLAMA_MODEL,
        ollama_url=OLLAMA_URL,
    )

    total_created = 0
    total_updated = 0

    for folder in folders:
        knowledge_path = folder / "Knowledge.md"
        content = knowledge_path.read_text(encoding="utf-8")
        tags = parse_tags(content)

        # Считаем сколько concept-страниц существовало до
        existing_before = set(p.stem for p in CONCEPTS_DIR.glob("*.md")) if CONCEPTS_DIR.exists() else set()

        updated = cm.update_concepts(
            knowledge_md_path=knowledge_path,
            folder_name=folder.name,
            tags=tags,
        )

        existing_after = set(p.stem for p in CONCEPTS_DIR.glob("*.md")) if CONCEPTS_DIR.exists() else set()
        new_pages = existing_after - existing_before

        if updated:
            label = f"+{len(new_pages)} новых" if new_pages else f"обновлено {len(updated)}"
            print(f"  ✅ {folder.name[:60]}  [{label}]")
            total_created += len(new_pages)
            total_updated += len(updated) - len(new_pages)
        else:
            print(f"  –  {folder.name[:60]}  [нет новых концептов]")

    print(f"\n{'─'*60}")
    print(f"📄 Concept-страниц создано:  {total_created}")
    print(f"📝 Concept-страниц обновлено: {total_updated}")
    print(f"📁 Папка: {CONCEPTS_DIR}")

    # Итоговый lint
    print(f"\n🔍 Проверяю lint...")
    linter = WikiLinter(USER_ROOT)
    result = linter.run()
    unlinked = len(result.unlinked_tags)
    print(f"   Осиротевших папок:   {len(result.orphan_folders)}")
    print(f"   Тегов без концептов: {unlinked}")
    if unlinked:
        print(f"   Оставшиеся теги: {', '.join(result.unlinked_tags[:15])}")


if __name__ == "__main__":
    main()
