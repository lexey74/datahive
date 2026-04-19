#!/usr/bin/env python3
"""
Одноразовый скрипт: построить index.md из уже существующих папок в downloads/.

Читает Knowledge.md каждой папки, извлекает title/tags/source,
и добавляет запись в WikiManager.update_index().

Запуск:
    cd /home/lexey/projects/datahive
    venv/bin/python3 scripts/reindex_downloads.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from src.modules.wiki_manager import WikiManager

USER_ROOT = ROOT / "users" / "lexey"
DOWNLOADS_DIR = USER_ROOT / "downloads"


def parse_frontmatter_field(content: str, field: str) -> str | None:
    pattern = re.compile(rf"^{field}:\s*(.+)$", re.MULTILINE)
    m = pattern.search(content)
    return m.group(1).strip().strip("\"'") if m else None


def parse_tags(content: str) -> list[str]:
    """Извлекает теги из YAML frontmatter (block или inline)."""
    # inline: tags: [#ai, #technology]
    inline = re.search(r"^tags:\s*\[(.+)\]", content, re.MULTILINE)
    if inline:
        return [t.strip().lstrip("#") for t in inline.group(1).split(",") if t.strip()]
    # block:
    # tags:
    #   - ai
    block = re.search(r"^tags:\s*\n((?:\s+- .+\n)*)", content, re.MULTILINE)
    if block:
        return [
            re.sub(r"^-\s*#?", "", t).strip()
            for t in re.findall(r"- (.+)", block.group(1))
        ]
    return []


def extract_summary(content: str) -> str:
    """Берём первый непустой bullet из раздела 📝 Саммари."""
    m = re.search(r"## 📝 Саммари\n\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return ""
    lines = [
        line.strip().lstrip("- ").strip()
        for line in m.group(1).splitlines()
        if line.strip()
    ]
    return lines[0] if lines else ""


def main() -> None:
    if not DOWNLOADS_DIR.exists():
        print(f"❌ downloads/ не найден: {DOWNLOADS_DIR}")
        sys.exit(1)

    wm = WikiManager(USER_ROOT)

    folders = sorted(f for f in DOWNLOADS_DIR.iterdir() if f.is_dir())
    print(f"📂 Найдено папок: {len(folders)}")

    ok = 0
    for folder in folders:
        knowledge = folder / "Knowledge.md"

        if knowledge.exists():
            # Полностью обработанная папка
            content = knowledge.read_text(encoding="utf-8")
            title = parse_frontmatter_field(content, "title") or folder.name
            source = parse_frontmatter_field(content, "source") or "unknown"
            tags = parse_tags(content)
            summary = extract_summary(content) or title
            wm.update_index(
                folder_name=folder.name, summary=summary, tags=tags, source=source
            )
            print(f"  ✅ {folder.name[:65]}")
        else:
            # Нет Knowledge.md — незавершённая обработка, добавляем как inbox
            desc_path = folder / "description.md"
            source = "unknown"
            summary = folder.name
            inbox_tags: list[str] = ["inbox"]

            # Определяем платформу из имени папки
            name_lower = folder.name.lower()
            for platform in (
                "instagram",
                "youtube",
                "telegram",
                "tiktok",
                "note",
                "temp",
            ):
                if platform in name_lower:
                    source = platform
                    break

            if desc_path.exists():
                desc = desc_path.read_text(encoding="utf-8")
                src_fm = parse_frontmatter_field(desc, "source")
                if src_fm:
                    source = src_fm

            wm.update_index(
                folder_name=folder.name,
                summary=f"[не обработано] {summary[:80]}",
                tags=inbox_tags,
                source=source,
            )
            print(f"  📋 {folder.name[:65]}  ← inbox")

        ok += 1

    print(f"\n✅ Проиндексировано: {ok} папок")
    print(f"📄 index.md: {USER_ROOT / 'index.md'}")


if __name__ == "__main__":
    main()
