#!/usr/bin/env python3
"""
Одноразовый скрипт: прогнать через LocalBrain все папки в downloads/,
у которых нет Knowledge.md, и создать его.

После этого все папки можно проиндексировать через reindex_downloads.py.

Запуск:
    cd /home/lexey/projects/datahive
    venv/bin/python3 scripts/analyze_missing.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.local_brain import LocalBrain
from src.modules.tag_manager import TagManager
from src.modules.wiki_manager import WikiManager

USER_ROOT = ROOT / "users" / "lexey"
DOWNLOADS_DIR = USER_ROOT / "downloads"

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:4b"


# ── Утилиты чтения ────────────────────────────────────────────────

def read_description(folder: Path) -> tuple[str, str, str]:
    """Вернуть (caption, author, source) из description.md или caption.md."""
    caption = ""
    author = ""
    source = "unknown"

    # Определяем source из имени папки
    name_lower = folder.name.lower()
    for platform in ("instagram", "youtube", "telegram", "tiktok", "note", "temp"):
        if platform in name_lower:
            source = platform
            break

    for fname in ("description.md", "caption.md"):
        fpath = folder / fname
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")

        # Извлечь автора
        m = re.search(r"\*\*Автор:\*\*\s*(@?\S+)", text)
        if m:
            author = m.group(1)

        # Извлечь описание/caption (всё что после ## Описание или # Caption / # Заметка)
        for header in ("## Описание", "# Caption", "# Заметка"):
            idx = text.find(header)
            if idx != -1:
                caption = text[idx + len(header):].strip()
                break
        if not caption:
            # Fallback: весь текст без frontmatter
            caption = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL).strip()

        if caption:
            break

    return caption[:3000], author, source


def read_transcript(folder: Path) -> str:
    """Вернуть текст транскрипта (раздел ## Полный текст)."""
    tpath = folder / "transcript.md"
    if not tpath.exists():
        return ""
    text = tpath.read_text(encoding="utf-8")
    m = re.search(r"## Полный текст\s*\n(.*)", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def extract_date(folder_name: str) -> str:
    """Извлечь дату YYYY-MM-DD из имени папки."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", folder_name)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d")


# ── Генерация Knowledge.md ────────────────────────────────────────

def write_knowledge(folder: Path, ai_result: dict, source: str, author: str) -> Path:
    tags_yaml = "\n  - ".join(ai_result.get("tags", ["inbox"]))
    date = extract_date(folder.name)
    path = folder / "Knowledge.md"
    path.write_text(
        f'---\ntitle: "{folder.name}"\ndate: {date}\nauthor: "{author}"\n'
        f"tags:\n  - {tags_yaml}\n"
        f"source: {source}\ntype: knowledge\nprocessed: true\n---\n\n"
        f"## 📝 Саммари\n\n{ai_result.get('summary', '')}\n\n"
        f"**Категория:** {ai_result.get('category', '')}\n",
        encoding="utf-8",
    )
    return path


# ── Основной цикл ─────────────────────────────────────────────────

def main() -> None:
    if not DOWNLOADS_DIR.exists():
        print(f"❌ downloads/ не найден: {DOWNLOADS_DIR}")
        sys.exit(1)

    # Находим папки без Knowledge.md
    missing = sorted(
        f for f in DOWNLOADS_DIR.iterdir()
        if f.is_dir() and not (f / "Knowledge.md").exists()
    )

    if not missing:
        print("✅ Все папки уже имеют Knowledge.md")
        return

    print(f"📂 Папок без Knowledge.md: {len(missing)}\n")

    brain = LocalBrain(model=OLLAMA_MODEL, base_url=OLLAMA_URL)
    tag_manager = TagManager()
    wm = WikiManager(USER_ROOT)

    # Проверим Ollama
    print(f"🔌 Подключение к Ollama ({OLLAMA_URL})...")
    try:
        brain.initialize()
        print("✅ Ollama доступен\n")
    except Exception as e:
        print(f"❌ Ollama недоступен: {e}")
        sys.exit(1)

    ok = 0
    errors = 0

    for folder in missing:
        print(f"🧠 {folder.name[:65]}")

        caption, author, source = read_description(folder)
        transcript = read_transcript(folder)

        if not caption and not transcript:
            print(f"   ⚠️  Нет контента для анализа — пропускаем\n")
            errors += 1
            continue

        try:
            ai_result = brain.analyze(
                caption=caption,
                transcript=transcript,
                comments=[],
                author=author,
                known_tags=tag_manager.get_tags_string(),
            )
        except Exception as e:
            print(f"   ❌ Ошибка LLM: {e}\n")
            errors += 1
            continue

        if not ai_result:
            print(f"   ❌ LLM вернул None\n")
            errors += 1
            continue

        knowledge_path = write_knowledge(folder, ai_result, source, author)
        tags_str = ", ".join(ai_result.get("tags", [])[:5])
        print(f"   ✅ Knowledge.md создан | теги: {tags_str}")

        # Обновить index.md
        try:
            wm.update_index(
                folder_name=folder.name,
                summary=ai_result.get("summary", ""),
                tags=ai_result.get("tags", []),
                source=source,
            )
            wm.append_log(
                operation="ingest",
                title=f"Retroanalyze | {folder.name}",
                details=f"Теги: {tags_str}",
                folder_name=folder.name,
            )
        except Exception as wiki_err:
            print(f"   ⚠️  WikiManager: {wiki_err}")

        print()
        ok += 1

    print(f"{'─'*60}")
    print(f"✅ Обработано: {ok}  |  ❌ Ошибок: {errors}")
    if ok > 0:
        print(f"📄 Теперь запустите reindex_downloads.py для полной индексации")


if __name__ == "__main__":
    main()
