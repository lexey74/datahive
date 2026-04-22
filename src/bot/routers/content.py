import asyncio
import html
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from src.bot.config import BotConfig
from src.bot.states import ContentStates
from src.modules.content_router import ContentRouter
from src.modules.downloader_base import DownloadSettings
from src.modules.local_brain import LocalBrain
from src.modules.local_ears import LocalEars, TranscriptResult
from src.modules.wiki_manager import WikiManager

router = Router()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def typing_action(message: types.Message) -> AsyncIterator[None]:
    """Показывает статус 'Печатаю...' пока выполняется долгая операция."""

    async def _keep_typing() -> None:
        while True:
            try:
                bot = message.bot
                if bot is not None:
                    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            except Exception:
                pass
            await asyncio.sleep(4)

    task = asyncio.create_task(_keep_typing())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


URL_REGEX = re.compile(r"(https?://[^\s<>()]+|www\.[^\s<>()]+)", re.IGNORECASE)
DOWNLOAD_SOURCES_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "download_sources.txt"
)

YES_ANSWERS = {
    "да",
    "yes",
    "y",
    "ok",
    "ок",
    "окей",
    "ага",
    "угу",
    "конечно",
    "скачать",
    "1",
}
NO_ANSWERS = {"нет", "no", "n", "не", "не надо", "пропустить", "0"}
FINISH_DIALOG_WORDS = {"готово", "стоп", "хватит", "достаточно", "/done", "завершить"}
TRANSCRIBABLE_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mp3",
    ".m4a",
    ".wav",
    ".ogg",
    ".oga",
    ".webm",
    ".aac",
    ".flac",
    ".opus",
    ".mov",
    ".mkv",
}


def get_user_folder(user_id: int, username: str, config: BotConfig) -> Path:
    # Single user mode: folder from USER_NAME env var
    path = config.users_dir / config.user_name / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_download_source_patterns() -> list[str]:
    if not DOWNLOAD_SOURCES_PATH.exists():
        return []

    patterns: list[str] = []
    for raw in DOWNLOAD_SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lower()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _normalize_url(url: str) -> str:
    cleaned = url.strip().rstrip(").,!?:;\"]')")
    if cleaned.startswith("www."):
        return f"https://{cleaned}"
    return cleaned


def _extract_urls(text: str) -> list[str]:
    matches = [_normalize_url(m.group(0)) for m in URL_REGEX.finditer(text or "")]
    unique: list[str] = []
    for url in matches:
        if url not in unique:
            unique.append(url)
    return unique


def _url_matches_registry(url: str, patterns: list[str]) -> bool:
    if not patterns:
        return True

    parsed = urlparse(url)
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    candidate = f"{netloc}{path}{query}"

    for pattern in patterns:
        if fnmatch(candidate, pattern):
            return True
    return False


def _is_yes(text: str) -> bool:
    return (text or "").strip().lower() in YES_ANSWERS


def _is_no(text: str) -> bool:
    return (text or "").strip().lower() in NO_ANSWERS


def _parse_post_action(text: str) -> str | None:
    normalized = (text or "").strip().lower()
    if "полож" in normalized or "сохран" in normalized:
        return "put"
    if "раскры" in normalized or "углуб" in normalized or "обсуд" in normalized:
        return "expand"
    return None


def _is_finish_dialog(text: str) -> bool:
    return (text or "").strip().lower() in FINISH_DIALOG_WORDS


def _is_transcribable_media(media_path: Path) -> bool:
    return media_path.suffix.lower() in TRANSCRIBABLE_MEDIA_EXTENSIONS


def _split_text_chunks(text: str, max_len: int = 3500) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    lines = normalized.splitlines(keepends=True)
    chunks: list[str] = []
    current = ""
    for line in lines:
        if len(current) + len(line) <= max_len:
            current += line
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(line) <= max_len:
            current = line
            continue
        for i in range(0, len(line), max_len):
            chunks.append(line[i : i + max_len])
    if current:
        chunks.append(current)
    return chunks


def _write_transcript_markdown(
    transcript_path: Path,
    transcript_result: TranscriptResult,
    media_file_name: str,
    title: str,
) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    transcript_path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                f"date: {today}",
                f"media_file: {media_file_name}",
                "whisper_model: remote-whisper-service",
                f"language: {transcript_result.language}",
                f"duration: {transcript_result.duration:.1f}",
                "type: transcript",
                "---",
                "",
                "# Транскрипция",
                "",
                "## С таймкодами",
                "",
                transcript_result.timed_transcript,
                "",
                "## Полный текст",
                "",
                transcript_result.full_text,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _build_download_settings(config: BotConfig) -> DownloadSettings:
    playwright_cookie = config.youtube_auth_dir / "yt_cookies.txt"
    youtube_cookies = playwright_cookie if playwright_cookie.exists() else None
    if youtube_cookies is None and Path("cookies.txt").exists():
        youtube_cookies = Path("cookies.txt")

    youtube_cookies_dir = Path("cookies") if Path("cookies").exists() else None

    instagram_cookies = (
        Path("cookies/instagram_cookies.txt")
        if Path("cookies/instagram_cookies.txt").exists()
        else None
    )

    return DownloadSettings(
        youtube_cookies=youtube_cookies,
        instagram_cookies=instagram_cookies,
        youtube_cookies_dir=youtube_cookies_dir,
        external_site_url=config.external_site_url,
        external_site_timeout_ms=config.external_site_timeout_ms,
    )


def _ollama_chat(
    config: BotConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    num_predict: int = 250,
) -> str:
    model = config.ollama_model_complex or config.ollama_model
    brain = LocalBrain(model=model, base_url=config.ollama_url)
    brain.initialize()
    if brain.client is None:
        raise RuntimeError("LLM клиент не инициализирован")

    response = brain.client.chat(
        model=brain.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": temperature,
            "num_predict": num_predict,
        },
        think=False,  # отключаем thinking-mode для qwen3:4b и аналогов
    )
    raw = response["message"]["content"]
    # На случай если think=False не поддерживается моделью — убираем блоки вручную
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    result = raw.strip()
    if not result:
        raise ValueError("LLM вернул пустой ответ")
    return result


async def _analyze_message_context(
    text: str, urls: list[str], config: BotConfig
) -> str:
    system_prompt = (
        "Ты помощник для персональной базы знаний. "
        "Сделай очень короткий анализ сообщения на русском в 2-4 буллетах. "
        "Если есть ссылки, укажи, какую ценность из них можно получить."
    )
    user_prompt = f"Сообщение:\n{text}\n\nСсылки:\n" + (
        "\n".join(urls) if urls else "нет"
    )

    try:
        return await asyncio.to_thread(
            _ollama_chat, config, system_prompt, user_prompt, 0.2, 220
        )
    except Exception as e:
        logger.warning(f"LLM-анализ недоступен: {e}")
        if urls:
            return "- Нашел ссылки в сообщении.\n- Могу помочь определить, что скачать и как сохранить в базу знаний."
        return "- Сообщение получено.\n- Могу сохранить как заметку или раскрыть тему через диалог."


def _build_base_context_text(data: dict) -> str:
    original = data.get("original_text", "")
    analysis = data.get("analysis", "")
    decisions = data.get("link_decisions", [])

    lines = ["Исходное сообщение:", original]
    if analysis:
        lines += ["", "Краткий анализ:", analysis]

    if decisions:
        lines += ["", "Решения по ссылкам:"]
        for item in decisions:
            lines.append(f"- {item.get('url', '')}: {item.get('status', 'unknown')}")

    return "\n".join(lines).strip()


async def _generate_expansion_question(
    config: BotConfig, base_context: str, dialog: list[dict]
) -> str:
    system_prompt = (
        "Ты интервьюер для раскрытия темы. "
        "Задай ОДИН уточняющий вопрос на русском языке. "
        "Вопрос должен помогать извлечь практические детали. "
        "Верни только сам вопрос."
    )
    dialog_text = "\n".join(f"{item['role']}: {item['content']}" for item in dialog)
    user_prompt = f"Контекст:\n{base_context}\n\nДиалог:\n{dialog_text if dialog_text else 'пока пусто'}"

    try:
        question = await asyncio.to_thread(
            _ollama_chat, config, system_prompt, user_prompt, 0.3, 80
        )
        return question.strip().split("\n")[0]
    except Exception:
        fallbacks = [
            "Какую главную цель ты преследуешь в этой теме?",
            "Какие ключевые факты или примеры важно добавить?",
            "Какие практические выводы или шаги нужно зафиксировать?",
        ]
        asked = sum(1 for item in dialog if item.get("role") == "assistant")
        return fallbacks[min(asked, len(fallbacks) - 1)]


async def _generate_expansion_summary(
    config: BotConfig, base_context: str, dialog: list[dict]
) -> str:
    system_prompt = (
        "Ты редактор базы знаний. "
        "Собери краткое саммари на русском в 4-8 буллетов. "
        "Сфокусируйся на фактах, решениях и следующих шагах."
    )
    dialog_text = "\n".join(f"{item['role']}: {item['content']}" for item in dialog)
    user_prompt = (
        f"Контекст:\n{base_context}\n\nДиалог:\n{dialog_text if dialog_text else 'нет'}"
    )

    try:
        return await asyncio.to_thread(
            _ollama_chat, config, system_prompt, user_prompt, 0.2, 260
        )
    except Exception:
        answers = [item["content"] for item in dialog if item.get("role") == "user"]
        if not answers:
            return "- Тему не удалось дополнительно раскрыть."
        return "\n".join(f"- {line}" for line in answers[:6])


async def _save_note(
    config: BotConfig,
    message: types.Message,
    state_data: dict,
    mode: str,
    summary: str = "",
    dialog: list[dict] | None = None,
) -> Path:
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else ""
    user_folder = get_user_folder(user_id, username or "", config)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{ts}_telegram_note"
    note_dir = user_folder / folder_name
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / "Knowledge.md"

    original_text = state_data.get("original_text", "")
    analysis = state_data.get("analysis", "")
    link_decisions = state_data.get("link_decisions", [])

    lines = [
        "---",
        f'title: "Telegram note {ts}"',
        "source: telegram",
        "type: knowledge",
        f"mode: {mode}",
        "processed: true",
        "---",
        "",
        "## Исходное сообщение",
        "",
        original_text or "_пусто_",
    ]

    if analysis:
        lines += ["", "## AI анализ", "", analysis]

    if link_decisions:
        lines += ["", "## Ссылки и решения", ""]
        for item in link_decisions:
            line = f"- {item.get('url', '')} -> {item.get('status', 'unknown')}"
            if item.get("folder"):
                line += f" (папка: {item['folder']})"
            lines.append(line)

    if summary:
        lines += ["", "## Итоговое саммари", "", summary]

    if dialog:
        lines += ["", "## Диалог раскрытия темы", ""]
        for item in dialog:
            role = "Ты" if item.get("role") == "user" else "Бот"
            lines.append(f"- **{role}:** {item.get('content', '')}")

    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        user_root = config.users_dir / config.user_name
        wm = WikiManager(user_root)
        index_summary = summary or analysis or original_text[:180]
        wm.update_index(
            folder_name=folder_name,
            summary=index_summary,
            tags=["telegram", "note"],
            source="telegram",
        )
        wm.append_log(
            operation="ingest",
            title=f"Telegram note | {folder_name}",
            details=f"Режим: {mode}",
            folder_name=folder_name,
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить wiki index/log: {e}")

    return note_path


async def _ask_post_process_action(message: types.Message) -> None:
    await message.answer(
        "📚 Что делаем дальше?\n\n"
        "1) <b>Положить</b> в базу знаний в неизменном виде\n"
        "2) <b>Раскрыть</b> тему (задам уточняющие вопросы)\n\n"
        "Ответь: <b>положить</b> или <b>раскрыть</b>."
    )


async def _ask_next_link_decision(
    message: types.Message, links: list[str], index: int
) -> None:
    url = links[index]
    await message.answer(
        f"🔗 Ссылка {index + 1}/{len(links)}:\n{url}\n\n"
        "Скачать информацию по этой ссылке? (да/нет)"
    )


@router.message(Command("url"))
async def cmd_url(message: types.Message, state: FSMContext) -> None:
    """Start URL input flow"""
    await state.set_state(ContentStates.waiting_url)
    await message.answer("🔗 Пришли мне ссылку на YouTube или Instagram:")


@router.message(ContentStates.waiting_url)
@router.message(
    F.text
    & F.text.regexp(r"(https?://)?(www\.)?(youtube\.com|youtu\.be|instagram\.com)")
)
async def handle_url(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    """Handle YouTube/Instagram URLs"""
    # If we were waiting for URL, clear state
    current_state = await state.get_state()
    if current_state == ContentStates.waiting_url:
        await state.clear()

    url = (message.text or "").strip()
    status_msg = await message.reply("🔎 Анализирую ссылку...")

    try:
        user = message.from_user
        if user is None:
            await status_msg.edit_text("❌ Не удалось определить пользователя.")
            return
        user_folder = get_user_folder(user.id, user.username or "", config)

        settings = _build_download_settings(config)
        content_router = ContentRouter(settings, user_folder)

        if not content_router.is_supported(url):
            await status_msg.edit_text("❌ URL не поддерживается или не распознан.")
            return

        await status_msg.edit_text("⬇️ Начинаю загрузку...")

        async with typing_action(message):
            result = await asyncio.to_thread(content_router.download, url)
        if result.folder_path is None:
            raise RuntimeError("Контент скачан без целевой папки")

        await status_msg.edit_text(
            f"✅ <b>Загрузка завершена!</b>\n\n"
            f"📁 Папка: <code>{result.folder_path.name}</code>\n"
            f"📦 Файлов: {len(result.media_files)}\n\n"
            f"Теперь можно запустить /transcribe или /ai"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка загрузки: {str(e)[:200]}")


@router.message(ContentStates.waiting_link_download_decision, F.text)
async def handle_link_download_decision(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    answer = (message.text or "").strip().lower()
    if not (_is_yes(answer) or _is_no(answer)):
        await message.answer("Ответь, пожалуйста: <b>да</b> или <b>нет</b>.")
        return

    data = await state.get_data()
    links: list[str] = data.get("downloadable_links", [])
    index: int = data.get("current_link_index", 0)
    decisions: list[dict] = data.get("link_decisions", [])

    if index >= len(links):
        await state.set_state(ContentStates.waiting_post_process_action)
        await _ask_post_process_action(message)
        return

    current_url = links[index]
    if _is_yes(answer):
        status_msg = await message.answer(f"⬇️ Скачиваю: {current_url}")
        try:
            user_id = message.from_user.id if message.from_user else 0
            username = message.from_user.username if message.from_user else ""
            user_folder = get_user_folder(user_id, username or "", config)
            content_router = ContentRouter(_build_download_settings(config), user_folder)
            async with typing_action(message):
                result = await asyncio.to_thread(content_router.download, current_url)
            if result.folder_path is None:
                raise RuntimeError("Контент скачан без целевой папки")
            decisions.append(
                {
                    "url": current_url,
                    "status": "downloaded",
                    "folder": result.folder_path.name,
                }
            )
            await status_msg.edit_text(
                f"✅ Готово: <code>{result.folder_path.name}</code>\n"
                f"Файлов: {len(result.media_files)}"
            )
        except Exception as e:
            decisions.append(
                {
                    "url": current_url,
                    "status": "failed",
                    "error": str(e)[:200],
                }
            )
            await status_msg.edit_text(f"❌ Не удалось скачать: {str(e)[:200]}")
    else:
        decisions.append({"url": current_url, "status": "skipped"})

    next_index = index + 1
    await state.update_data(link_decisions=decisions, current_link_index=next_index)

    if next_index < len(links):
        await _ask_next_link_decision(message, links, next_index)
        return

    await state.set_state(ContentStates.waiting_post_process_action)
    await _ask_post_process_action(message)


@router.message(ContentStates.waiting_post_process_action, F.text)
async def handle_post_process_action(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    action = _parse_post_action(message.text or "")
    if action is None:
        await message.answer(
            "Не понял ответ. Напиши <b>положить</b> или <b>раскрыть</b>."
        )
        return

    data = await state.get_data()

    if action == "put":
        note_path = await _save_note(config, message, data, mode="raw")
        await state.clear()
        await message.answer(
            f"✅ Сохранил заметку в базу знаний:\n<code>{note_path.parent.name}/{note_path.name}</code>"
        )
        return

    dialog: list[dict] = []
    base_context = _build_base_context_text(data)
    async with typing_action(message):
        question = await _generate_expansion_question(config, base_context, dialog)
    dialog.append({"role": "assistant", "content": question})

    await state.update_data(
        expansion_dialog=dialog, expansion_base_context=base_context
    )
    await state.set_state(ContentStates.waiting_topic_expansion_dialog)
    await message.answer(
        "🧠 Отлично, раскрываем тему. Я задам несколько уточняющих вопросов.\n"
        "Когда захочешь завершить, напиши <b>готово</b>.\n\n"
        f"{question}"
    )


@router.message(ContentStates.waiting_topic_expansion_dialog, F.text)
async def handle_topic_expansion_dialog(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    data = await state.get_data()
    dialog: list[dict] = data.get("expansion_dialog", [])
    base_context = data.get("expansion_base_context", "")
    user_text = (message.text or "").strip()

    if _is_finish_dialog(user_text):
        async with typing_action(message):
            summary = await _generate_expansion_summary(config, base_context, dialog)
        await state.update_data(expansion_summary=summary)
        await state.set_state(ContentStates.waiting_expansion_save_confirmation)
        await message.answer(
            f"📝 Итоговое саммари:\n\n{summary}\n\nПоложить это в базу знаний? (да/нет)"
        )
        return

    dialog.append({"role": "user", "content": user_text})
    user_answers = sum(1 for item in dialog if item.get("role") == "user")

    if user_answers >= 4:
        async with typing_action(message):
            summary = await _generate_expansion_summary(config, base_context, dialog)
        await state.update_data(expansion_dialog=dialog, expansion_summary=summary)
        await state.set_state(ContentStates.waiting_expansion_save_confirmation)
        await message.answer(
            f"📝 Собрал итоговое саммари:\n\n{summary}\n\n"
            "Положить это в базу знаний? (да/нет)"
        )
        return

    async with typing_action(message):
        question = await _generate_expansion_question(config, base_context, dialog)
    dialog.append({"role": "assistant", "content": question})
    await state.update_data(expansion_dialog=dialog)
    await message.answer(question)


@router.message(ContentStates.waiting_expansion_save_confirmation, F.text)
async def handle_expansion_save_confirmation(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    answer = (message.text or "").strip().lower()
    if _is_no(answer):
        await state.clear()
        await message.answer("Ок, не сохраняю. Диалог завершен.")
        return

    if not _is_yes(answer):
        await message.answer("Ответь, пожалуйста: <b>да</b> или <b>нет</b>.")
        return

    data = await state.get_data()
    summary = data.get("expansion_summary", "")
    dialog = data.get("expansion_dialog", [])
    note_path = await _save_note(
        config, message, data, mode="expanded", summary=summary, dialog=dialog
    )

    await state.clear()
    await message.answer(
        f"✅ Сохранил раскрытую заметку:\n<code>{note_path.parent.name}/{note_path.name}</code>"
    )


@router.message(F.photo | F.video | F.document | F.audio | F.voice)
async def handle_media(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    """Handle forwarded/direct media messages (video, audio, voice, document, photo)."""
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else ""
    user_folder = get_user_folder(user_id, username or "", config)

    # --- Определяем тип и получаем file_id / имя файла ---
    media_obj: (
        types.Video | types.Document | types.PhotoSize | types.Audio | types.Voice
    )
    if message.video:
        media_obj = message.video
        media_type = "video"
        original_name = media_obj.file_name or f"video_{media_obj.file_id[:8]}.mp4"
        mime = media_obj.mime_type or "video/mp4"
    elif message.audio:
        media_obj = message.audio
        media_type = "audio"
        original_name = media_obj.file_name or f"audio_{media_obj.file_id[:8]}.mp3"
        mime = media_obj.mime_type or "audio/mpeg"
    elif message.voice:
        media_obj = message.voice
        media_type = "voice"
        original_name = f"voice_{media_obj.file_id[:8]}.ogg"
        mime = media_obj.mime_type or "audio/ogg"
    elif message.document:
        media_obj = message.document
        media_type = "document"
        original_name = media_obj.file_name or f"document_{media_obj.file_id[:8]}.bin"
        mime = media_obj.mime_type or "application/octet-stream"
    elif message.photo:
        media_obj = message.photo[-1]  # берём максимальное разрешение
        media_type = "photo"
        original_name = f"photo_{media_obj.file_id[:8]}.jpg"
        mime = "image/jpeg"
    else:
        await message.reply("❓ Неизвестный тип медиа.")
        return

    # --- Извлекаем caption и мета-данные пересланного сообщения ---
    caption = message.caption or ""
    forward_from: str = ""
    forward_date: str = ""
    if message.forward_origin:
        origin = message.forward_origin
        # MessageOriginUser / MessageOriginChannel / MessageOriginChat / MessageOriginHiddenUser
        if hasattr(origin, "sender_user") and origin.sender_user:
            forward_from = (
                f"@{origin.sender_user.username}"
                if origin.sender_user.username
                else origin.sender_user.full_name
            )
        elif hasattr(origin, "chat") and origin.chat:
            forward_from = (
                f"@{origin.chat.username}"
                if origin.chat.username
                else (origin.chat.title or "")
            )
        elif hasattr(origin, "sender_user_name") and origin.sender_user_name:
            forward_from = origin.sender_user_name
        if hasattr(origin, "date") and origin.date:
            forward_date = origin.date.strftime("%Y-%m-%d")

    # --- Сообщаем пользователю, что собираемся делать ---
    plan_lines = [f"📥 <b>Получено {media_type}:</b> <code>{original_name}</code>"]
    if forward_from:
        plan_lines.append(f"📤 Источник: {forward_from}")
    if caption:
        plan_lines.append(f"� Подпись: <i>{caption[:120]}</i>")
    plan_lines += [
        "",
        "⏳ <b>Что делаю:</b>",
        "• Скачиваю файл из Telegram",
        "• Создаю папку и сохраняю медиафайл",
        "• Генерирую description.md с метаданными",
        "• Обновляю wiki-индекс и лог",
    ]
    status_msg = await message.reply("\n".join(plan_lines))

    try:
        # --- Скачиваем файл через Telegram ---
        bot = message.bot
        if bot is None:
            raise RuntimeError("Bot instance недоступен")
        file = await bot.get_file(media_obj.file_id)
        ts = datetime.now()
        ts_folder = ts.strftime("%Y-%m-%d_%H-%M")
        ts_iso = ts.strftime("%Y-%m-%d")

        # Чистим имя для папки
        slug = re.sub(r"[^\w\s-]", "", caption[:50]).strip()
        slug = re.sub(r"[\s_]+", "_", slug) or media_type
        folder_name = f"{ts_folder}_telegram_{media_type}_{slug}"
        media_dir = user_folder / folder_name
        media_dir.mkdir(parents=True, exist_ok=True)

        # Определяем расширение
        ext = Path(original_name).suffix or ".bin"
        save_name = f"{media_type}{ext}"
        save_path = media_dir / save_name

        # Скачиваем файл (aiogram 3: download_file — async, принимает Path)
        async with typing_action(message):
            if not file.file_path:
                raise RuntimeError("Telegram не вернул путь к файлу")
            await bot.download_file(file.file_path, destination=save_path)

        # --- Создаём description.md с frontmatter ---
        desc_path = media_dir / "description.md"
        frontmatter_lines = [
            "---",
            f'title: "{caption[:80] or original_name}"',
            f'author: "{forward_from or "unknown"}"',
            f"date: {ts_iso}",
            "source: telegram",
            "type: description",
            f"media_type: {media_type}",
            f"mime: {mime}",
            f"original_file: {original_name}",
        ]
        if forward_date:
            frontmatter_lines.append(f"forward_date: {forward_date}")
        frontmatter_lines.append("---")

        desc_lines = frontmatter_lines + [
            "",
            f"# {caption[:80] or original_name}",
            "",
        ]
        if forward_from:
            desc_lines += [f"**Источник:** {forward_from}", ""]
        if caption:
            desc_lines += ["## Описание", "", caption, ""]
        desc_lines += [f"**Файл:** `{save_name}`", ""]

        desc_path.write_text("\n".join(desc_lines), encoding="utf-8")

        # --- Обновляем wiki index и log ---
        try:
            user_root = config.users_dir / config.user_name
            wm = WikiManager(user_root)
            wm.update_index(
                folder_name=folder_name,
                summary=caption[:200] or original_name,
                tags=["telegram", media_type],
                source="telegram",
            )
            wm.append_log(
                operation="ingest",
                title=f"Telegram {media_type} | {folder_name}",
                details=f"Файл: {save_name}, источник: {forward_from or 'direct'}",
                folder_name=folder_name,
            )
        except Exception as e:
            logger.warning(f"Не удалось обновить wiki: {e}")

        file_size_kb = save_path.stat().st_size // 1024 if save_path.exists() else 0
        done_lines = [
            "✅ <b>Готово! Вот что было сделано:</b>",
            "",
            f"📁 Папка: <code>{folder_name}</code>",
            f"🎞 Файл сохранён: <code>{save_name}</code> ({file_size_kb} КБ)",
            "📄 Создан: <code>description.md</code> с YAML-метаданными",
            "🗂 Обновлён wiki-индекс и лог",
        ]
        if forward_from:
            done_lines.append(f"📤 Источник: {forward_from}")
        if forward_date:
            done_lines.append(f"📅 Дата оригинала: {forward_date}")
        if caption:
            done_lines.append(f"\n💬 <i>{caption[:120]}</i>")
        await status_msg.edit_text("\n".join(done_lines))

        if _is_transcribable_media(save_path):
            await state.update_data(
                media_path=str(save_path),
                media_dir=str(media_dir),
                media_file_name=save_name,
                media_title=(caption[:80] or original_name),
            )
            await state.set_state(ContentStates.waiting_media_transcribe_confirmation)
            await message.answer("🎤 Транскрибировать этот файл сейчас? (да/нет)")

    except Exception as e:
        logger.exception(f"Ошибка сохранения медиа: {e}")
        await status_msg.edit_text(f"❌ Не удалось сохранить медиа: {str(e)[:200]}")


@router.message(ContentStates.waiting_media_transcribe_confirmation, F.text)
async def handle_media_transcribe_confirmation(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    answer = (message.text or "").strip().lower()
    if not (_is_yes(answer) or _is_no(answer)):
        await message.answer("Ответь, пожалуйста: <b>да</b> или <b>нет</b>.")
        return

    if _is_no(answer):
        await state.clear()
        await message.answer(
            "Ок, оставил файл в папке для последующей транскрибации. "
            "Можешь запустить её позже командой /transcribe."
        )
        return

    data = await state.get_data()
    media_path_raw = data.get("media_path")
    media_dir_raw = data.get("media_dir")
    media_file_name = data.get("media_file_name", "media.bin")
    media_title = data.get("media_title", media_file_name)

    if not media_path_raw or not media_dir_raw:
        await state.clear()
        await message.answer("⚠️ Не нашёл сохранённый файл. Пришли медиа ещё раз.")
        return

    media_path = Path(media_path_raw)
    media_dir = Path(media_dir_raw)
    status_msg = await message.answer(
        "🎤 Транскрибирую медиа...\nЭто может занять несколько минут."
    )

    try:
        ears = LocalEars(
            whisper_url=config.whisper_url,
            whisper_api_key=config.whisper_api_key,
        )
        transcript_result = await asyncio.to_thread(ears.transcribe, media_path)
        if not transcript_result:
            await state.clear()
            await status_msg.edit_text("⚠️ Не удалось транскрибировать этот файл.")
            return

        transcript_path = media_dir / "transcript.md"
        _write_transcript_markdown(
            transcript_path=transcript_path,
            transcript_result=transcript_result,
            media_file_name=media_file_name,
            title=media_title,
        )

        await status_msg.edit_text(
            f"✅ Транскрипция готова!\n\n"
            f"📂 Папка: <code>{media_dir.name}</code>\n"
            f"📄 Файл: <code>{transcript_path.name}</code>"
        )

        text_chunks = _split_text_chunks(transcript_result.full_text)
        if text_chunks:
            await message.answer("📝 <b>Извлеченный текст:</b>")
            for chunk in text_chunks:
                await message.answer(html.escape(chunk))
        else:
            await message.answer("📝 Извлеченный текст пустой.")

        await state.update_data(media_path=str(media_path))
        await state.set_state(ContentStates.waiting_media_delete_confirmation)
        await message.answer("Удалить исходный медиафайл из папки? (да/нет)")

    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}", exc_info=True)
        await state.clear()
        await status_msg.edit_text(f"❌ Ошибка транскрибации: {str(e)[:200]}")


@router.message(ContentStates.waiting_media_delete_confirmation, F.text)
async def handle_media_delete_confirmation(
    message: types.Message, state: FSMContext
) -> None:
    answer = (message.text or "").strip().lower()
    if not (_is_yes(answer) or _is_no(answer)):
        await message.answer("Ответь, пожалуйста: <b>да</b> или <b>нет</b>.")
        return

    if _is_no(answer):
        await state.clear()
        await message.answer("Ок, исходный медиафайл оставил в папке.")
        return

    data = await state.get_data()
    media_path_raw = data.get("media_path")
    if not media_path_raw:
        await state.clear()
        await message.answer("⚠️ Не нашёл путь к исходному файлу.")
        return

    media_path = Path(media_path_raw)
    try:
        if media_path.exists():
            media_path.unlink()
            await message.answer("🗑 Исходный медиафайл удалён. Оставил только транскрипцию.")
        else:
            await message.answer("ℹ️ Исходный медиафайл уже отсутствует.")
    except Exception as e:
        await message.answer(f"❌ Не удалось удалить исходный файл: {str(e)[:200]}")
    finally:
        await state.clear()


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def handle_text(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    """Handle text without command: AI analysis + interactive flow."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Похоже, сообщение пустое. Пришли текст для анализа.")
        return

    urls = _extract_urls(text)
    patterns = _load_download_source_patterns()

    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else ""
    user_folder = get_user_folder(user_id, username or "", config)
    content_router = ContentRouter(_build_download_settings(config), user_folder)

    downloadable_links: list[str] = []
    not_downloadable_links: list[str] = []
    for url in urls:
        in_registry = _url_matches_registry(url, patterns)
        supported = content_router.is_supported(url)
        if in_registry and supported:
            downloadable_links.append(url)
        else:
            not_downloadable_links.append(url)

    status_msg = await message.answer("🧠 Анализирую сообщение через LLM...")
    async with typing_action(message):
        analysis = await _analyze_message_context(text, urls, config)

    response_parts = ["🧠 <b>Краткий анализ</b>", analysis]
    if urls:
        response_parts.append(f"🔗 Найдено ссылок: <b>{len(urls)}</b>")
        if downloadable_links:
            response_parts.append(f"✅ Можно скачать: <b>{len(downloadable_links)}</b>")
        if not_downloadable_links:
            response_parts.append(
                "⚠️ Пока не поддерживаются:\n"
                + "\n".join(f"• {url}" for url in not_downloadable_links)
            )

    await status_msg.edit_text("\n\n".join(response_parts))

    await state.update_data(
        original_text=text,
        analysis=analysis,
        all_links=urls,
        downloadable_links=downloadable_links,
        not_downloadable_links=not_downloadable_links,
        link_decisions=[],
        current_link_index=0,
    )

    if downloadable_links:
        await state.set_state(ContentStates.waiting_link_download_decision)
        await _ask_next_link_decision(message, downloadable_links, 0)
        return

    await state.set_state(ContentStates.waiting_post_process_action)
    await _ask_post_process_action(message)
