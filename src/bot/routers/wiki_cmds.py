"""
wiki_cmds.py — команды для управления LLM Wiki в боте Data Hive.

Команды:
  /wiki   — статистика wiki (количество источников, концептов, запросов)
  /lint   — проверка здоровья wiki (битые ссылки, осиротевшие папки, пустые концепты)
  /save   — сохранить последний ответ /ask в wiki/queries/

Inline-кнопка [💾 Сохранить в wiki] добавляется к ответам /ask через callback.
"""
import asyncio
import logging
from pathlib import Path

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from src.bot.config import BotConfig
from src.modules.wiki_manager import WikiManager
from src.modules.wiki_linter import WikiLinter
from src.modules.concept_manager import ConceptManager

router = Router()
logger = logging.getLogger(__name__)

# Храним последний ответ /ask на user_id для возможности сохранить в wiki
# Формат: { user_id: {"question": str, "answer": str, "sources": list[str]} }
_last_answers: dict[int, dict] = {}


def _get_user_root(config: BotConfig, user_id: int | None = None) -> Path:
    """Вернуть корневую папку пользователя."""
    # TODO: в будущем разделить по user_id; сейчас — admin
    return config.users_dir / "admin"


def save_answer_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Inline-клавиатура с кнопкой сохранения ответа в wiki."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💾 Сохранить в wiki",
            callback_data=f"save_answer:{user_id}"
        )
    ]])


def register_answer(user_id: int, question: str, answer: str, sources: list[str]) -> None:
    """Зарегистрировать ответ для последующего сохранения через inline-кнопку."""
    _last_answers[user_id] = {
        "question": question,
        "answer": answer,
        "sources": sources,
    }


# ── /wiki — статистика ────────────────────────────────────────────

@router.message(Command("wiki"))
async def cmd_wiki(message: types.Message, config: BotConfig) -> None:
    """Статистика wiki пользователя."""
    user_root = _get_user_root(config, message.from_user.id if message.from_user else None)
    wm = WikiManager(user_root)

    await message.answer("📊 Собираю статистику wiki...")

    stats = await asyncio.to_thread(wm.get_stats)

    text = (
        "📚 <b>Wiki статистика</b>\n\n"
        f"📥 Источников в index: <b>{stats['total_sources']}</b>\n"
        f"📋 Записей в журнале: <b>{stats['log_entries']}</b>\n"
        f"💡 Concept-страниц: <b>{stats['concept_pages']}</b>\n"
        f"❓ Сохранённых запросов: <b>{stats['query_pages']}</b>\n\n"
        f"📄 <code>{user_root / 'index.md'}</code>\n"
        f"📋 <code>{user_root / 'log.md'}</code>"
    )
    await message.answer(text)


# ── /lint — проверка здоровья ─────────────────────────────────────

@router.message(Command("lint"))
async def cmd_lint(message: types.Message, config: BotConfig) -> None:
    """Проверка здоровья wiki."""
    user_root = _get_user_root(config, message.from_user.id if message.from_user else None)

    status_msg = await message.answer("🔍 Запускаю wiki lint...")

    try:
        linter = WikiLinter(user_root)
        result = await asyncio.to_thread(linter.run)
        report = result.format_report()

        # Логируем lint в log.md
        try:
            wm = WikiManager(user_root)
            wm.append_log(
                operation="lint",
                title=f"Найдено проблем: {result.total_issues}",
                details=(
                    f"Осиротевших папок: {len(result.orphan_folders)}\n"
                    f"Битых ссылок: {len(result.broken_links)}\n"
                    f"Пустых концептов: {len(result.empty_concepts)}\n"
                    f"Тегов без страниц: {len(result.unlinked_tags)}"
                ),
            )
        except Exception:
            pass

        await status_msg.edit_text(report)

    except Exception as e:
        logger.error(f"Ошибка lint: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка lint: {str(e)[:200]}")


# ── /save — сохранить последний ответ вручную ─────────────────────

@router.message(Command("save"))
async def cmd_save(message: types.Message, config: BotConfig) -> None:
    """Сохранить последний ответ /ask в wiki/queries/."""
    user_id = message.from_user.id if message.from_user else 0
    data = _last_answers.get(user_id)

    if not data:
        await message.answer(
            "⚠️ Нет недавнего ответа для сохранения.\n"
            "Используй /ask чтобы задать вопрос, затем /save чтобы сохранить ответ."
        )
        return

    user_root = _get_user_root(config, user_id)
    wm = WikiManager(user_root)

    try:
        file_path = await asyncio.to_thread(
            wm.save_query_answer,
            data["question"],
            data["answer"],
            data["sources"],
        )
        del _last_answers[user_id]  # Очистить после сохранения
        await message.answer(
            f"✅ Ответ сохранён в wiki!\n\n"
            f"📄 <code>{file_path.parent.name}/{file_path.name}</code>"
        )
    except Exception as e:
        logger.error(f"Ошибка save: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка сохранения: {str(e)[:200]}")


# ── Callback: inline-кнопка "Сохранить в wiki" ────────────────────

@router.callback_query(F.data.startswith("save_answer:"))
async def cb_save_answer(callback: types.CallbackQuery, config: BotConfig) -> None:
    """Обработчик нажатия кнопки '💾 Сохранить в wiki'."""
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    data = _last_answers.get(user_id)

    if not data:
        await callback.message.answer("⚠️ Ответ уже сохранён или устарел.")
        return

    user_root = _get_user_root(config, user_id)
    wm = WikiManager(user_root)

    try:
        file_path = await asyncio.to_thread(
            wm.save_query_answer,
            data["question"],
            data["answer"],
            data["sources"],
        )
        del _last_answers[user_id]

        # Редактируем сообщение: убираем кнопку, добавляем подтверждение
        original_text = callback.message.text or ""
        await callback.message.edit_text(
            original_text + f"\n\n✅ <i>Сохранено: <code>{file_path.name}</code></i>",
            reply_markup=None,
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка сохранения: {str(e)[:200]}")


# ── /concepts — список концептов ──────────────────────────────────

@router.message(Command("concepts"))
async def cmd_concepts(message: types.Message, config: BotConfig) -> None:
    """Показать топ концепт-страниц по количеству упоминаний."""
    user_root = _get_user_root(config, message.from_user.id if message.from_user else None)
    cm = ConceptManager(
        concepts_dir=user_root / "wiki" / "concepts",
        ollama_model=config.ollama_model,
        ollama_url=config.ollama_url,
    )

    try:
        concepts = await asyncio.to_thread(cm.list_concepts)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        return

    if not concepts:
        await message.answer(
            "📭 Концепт-страниц пока нет.\n"
            "Они появятся автоматически после AI-анализа контента через /ai."
        )
        return

    lines = ["💡 <b>Топ концептов по упоминаниям:</b>\n"]
    for i, c in enumerate(concepts[:20], 1):
        lines.append(f"{i}. <b>{c['term']}</b> — {c['mentions']} упом.")

    if len(concepts) > 20:
        lines.append(f"\n… и ещё {len(concepts) - 20} концептов")

    await message.answer("\n".join(lines))
