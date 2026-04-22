import asyncio
import json
import logging
from pathlib import Path
from urllib import error as url_error
from urllib import request as url_request
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.bot.config import BotConfig
from src.bot.services.queue_store import queue_store
from src.modules.local_ears import LocalEars
from src.modules.wiki_manager import WikiManager
from src.modules.concept_manager import ConceptManager

router = Router()
logger = logging.getLogger(__name__)


async def _llama_cpp_health(config: BotConfig) -> tuple[str, str]:
    """Проверка доступности llama.cpp и выбранной модели."""
    from src.modules.local_brain import LocalBrain

    def _probe_model() -> None:
        brain = LocalBrain(model=config.ollama_model, base_url=config.ollama_url)
        brain.initialize()
        if brain.client is None:
            raise RuntimeError("LLM клиент не инициализирован")
        response = brain.client.chat(
            model=brain.model,
            messages=[{"role": "user", "content": "ping"}],
            options={"temperature": 0.0, "num_predict": 1},
        )
        content = response.get("message", {}).get("content", "")
        if not str(content).strip():
            raise RuntimeError("модель вернула пустой ответ")

    try:
        await asyncio.to_thread(_probe_model)
        return "ok", f"модель {config.ollama_model} доступна"
    except Exception as e:
        return "error", str(e)[:180]


async def _whisper_health(config: BotConfig) -> tuple[str, str]:
    """Проверка доступности Whisper HTTP-сервиса."""
    whisper_url = (config.whisper_url or "").rstrip("/")
    if not whisper_url:
        return "not_configured", "WHISPER_URL не задан"

    def _probe_whisper() -> str:
        endpoint = f"{whisper_url}/health"
        req = url_request.Request(endpoint, method="GET")
        with url_request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        model = payload.get("model") or "unknown"
        loaded = payload.get("model_loaded")
        if loaded is True:
            return f"модель {model} загружена"
        if loaded is False:
            return f"модель {model} не загружена (lazy-load)"
        return f"модель {model}"

    try:
        details = await asyncio.to_thread(_probe_whisper)
        return "ok", details
    except url_error.HTTPError as e:
        return "error", f"HTTP {e.code}"[:180]
    except Exception as e:
        return "error", str(e)[:180]


async def _build_status_text(user_id: int, config: BotConfig) -> str:
    """Собрать расширенный статус задач и сервисов."""
    t_status = await queue_store.get_status("transcribe", user_id)
    ai_status = await queue_store.get_status("ai", user_id)
    whisper_status, whisper_details = await _whisper_health(config)
    llm_status, llm_details = await _llama_cpp_health(config)

    status_text = (
        "📊 <b>Статус задач и сервисов:</b>\n\n"
        f"🎤 Transcribe: <code>{t_status['status']}</code>\n"
        f"🤖 AI: <code>{ai_status['status']}</code>\n"
        f"🗣 Whisper: <code>{whisper_status}</code>\n"
        f"   └ URL: <code>{config.whisper_url or '-'}</code>\n"
        f"   └ детали: {whisper_details}\n"
        f"🧠 llama.cpp: <code>{llm_status}</code>\n"
        f"   └ модель: <code>{config.ollama_model}</code>\n"
        f"   └ URL: <code>{config.ollama_url}</code>\n"
        f"   └ детали: {llm_details}\n"
    )
    if t_status["status"] == "queued":
        status_text += f"   └ позиция в очереди: {t_status.get('position', '?')}\n"
    if ai_status["status"] == "queued":
        status_text += f"   └ AI в очереди: {ai_status.get('position', '?')}\n"

    status_text += (
        "\nℹ️ <b>Легенда:</b> "
        "<code>ok</code> — сервис отвечает; "
        "<code>error</code> — сервис недоступен/ошибка; "
        "<code>not_configured</code> — URL не задан."
    )

    return status_text


async def run_transcription(
    file_path: Path, output_dir: Path, config: BotConfig, message: types.Message
) -> None:
    """Запуск транскрибации в executor (не блокирует event loop)"""
    user = message.from_user
    if user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return
    user_id = user.id
    status_msg = await message.answer(
        "🎤 Транскрибирую медиа...\nЭто может занять несколько минут."
    )

    try:
        ears = LocalEars(
            whisper_url=config.whisper_url,
            whisper_api_key=config.whisper_api_key,
        )

        transcript_result = await asyncio.to_thread(ears.transcribe, file_path)

        if transcript_result:
            transcript_path = output_dir / "transcript.md"
            transcript_path.write_text(
                f"---\ntype: transcript\ndate: {transcript_result.language}\n"
                f"duration: {transcript_result.duration:.1f}\n---\n\n"
                f"# Транскрипция\n\n"
                f"**Язык:** {transcript_result.language}\n"
                f"**Длительность:** {transcript_result.duration:.1f} сек\n\n"
                f"## С таймкодами\n\n{transcript_result.timed_transcript}\n\n"
                f"## Полный текст\n\n{transcript_result.full_text}\n",
                encoding="utf-8",
            )
            await status_msg.edit_text(
                f"✅ Транскрипция готова!\n\n"
                f"📂 Папка: <code>{output_dir.name}</code>\n"
                f"Запусти /ai для анализа."
            )
        else:
            await status_msg.edit_text("⚠️ Не удалось транскрибировать.")

    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка транскрибации: {str(e)[:200]}")
        await queue_store.set_error("transcribe", user_id)
        return
    finally:
        await queue_store.set_done("transcribe", user_id)


@router.message(Command("transcribe"))
async def cmd_transcribe(
    message: types.Message, state: FSMContext, config: BotConfig
) -> None:
    """Handler for /transcribe"""
    user = message.from_user
    if user is None:
        await message.reply("❌ Не удалось определить пользователя.")
        return
    user_id = user.id
    username = user.username or ""

    user_folder = config.users_dir / config.user_name / "downloads"
    if not user_folder.exists():
        await message.reply("📂 Нет загруженных файлов.")
        return

    folders = sorted(
        [f for f in user_folder.iterdir() if f.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not folders:
        await message.reply("📂 Нет папок с контентом.")
        return

    latest_folder = folders[0]
    supported_media_ext = {
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
    media_files = [
        file
        for file in latest_folder.iterdir()
        if file.is_file() and file.suffix.lower() in supported_media_ext
    ]

    if not media_files:
        await message.reply(
            f"⚠️ В папке <code>{latest_folder.name}</code> нет медиа для транскрибации."
        )
        return

    # Проверяем очередь
    if await queue_store.is_running("transcribe"):
        pos = await queue_store.enqueue("transcribe", user_id, username)
        await message.reply(f"⏳ Транскрибация уже идёт. Вы в очереди (позиция {pos}).")
        return

    await queue_store.set_running("transcribe", user_id)
    asyncio.create_task(
        run_transcription(media_files[0], latest_folder, config, message)
    )


@router.message(Command("ai"))
async def cmd_ai(message: types.Message, config: BotConfig, bot: Bot) -> None:
    del bot
    """Handler for /ai — запускает AI анализ через Ollama"""
    user = message.from_user
    if user is None:
        await message.reply("❌ Не удалось определить пользователя.")
        return
    user_id = user.id

    if await queue_store.is_running("ai"):
        await message.reply("⚠️ AI анализ уже запущен.")
        return

    status_msg = await message.reply("🤖 Запускаю AI обработку...")

    try:
        from src.modules.local_brain import LocalBrain
        from src.modules.tag_manager import TagManager

        user_folder = config.users_dir / config.user_name / "downloads"
        folders = sorted(
            [f for f in user_folder.iterdir() if f.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if not folders:
            await status_msg.edit_text("📂 Нет папок для анализа.")
            return

        latest_folder = folders[0]
        transcript_file = latest_folder / "transcript.md"
        transcript_text = (
            transcript_file.read_text(encoding="utf-8")
            if transcript_file.exists()
            else ""
        )

        await queue_store.set_running("ai", user_id)

        brain = LocalBrain(model=config.ollama_model, base_url=config.ollama_url)
        tag_manager = TagManager()

        ai_result = await asyncio.to_thread(
            brain.analyze,
            caption="",
            transcript=transcript_text,
            comments=[],
            author="",
            known_tags=tag_manager.get_tags_string(),
        )

        if ai_result:
            knowledge_path = latest_folder / "Knowledge.md"
            tags_yaml = "\n  - ".join(ai_result.get("tags", []))
            knowledge_path.write_text(
                f'---\ntitle: "{latest_folder.name}"\ndate: ""\n'
                f"tags:\n  - {tags_yaml}\nsource: unknown\ntype: knowledge\nprocessed: true\n---\n\n"
                f"## Саммари\n\n{ai_result.get('summary', '')}\n\n"
                f"**Категория:** {ai_result.get('category', '')}\n",
                encoding="utf-8",
            )

            # Обновить wiki (index.md + log.md)
            try:
                user_root = config.users_dir / config.user_name
                wm = WikiManager(user_root)
                wm.update_index(
                    folder_name=latest_folder.name,
                    summary=ai_result.get("summary", ""),
                    tags=ai_result.get("tags", []),
                    source="unknown",
                )
                wm.append_log(
                    operation="ingest",
                    title=f"AI анализ | {latest_folder.name}",
                    details=f"Теги: {', '.join(ai_result.get('tags', [])[:8])}",
                    folder_name=latest_folder.name,
                )

                # Обновить концепт-страницы (в фоне — не блокирует ответ боту)
                cm = ConceptManager(
                    concepts_dir=user_root / "wiki" / "concepts",
                    ollama_model=config.ollama_model,
                    ollama_url=config.ollama_url,
                )
                asyncio.create_task(
                    asyncio.to_thread(
                        cm.update_concepts,
                        knowledge_path,
                        latest_folder.name,
                        ai_result.get("tags", []),
                    )
                )
            except Exception as wiki_err:
                logger.warning(f"WikiManager: {wiki_err}")

            await status_msg.edit_text(
                f"✅ AI анализ завершён!\n\n"
                f"📂 <code>{latest_folder.name}</code>\n"
                f"🏷 Теги: {', '.join(ai_result.get('tags', [])[:5])}"
            )
        else:
            await status_msg.edit_text("⚠️ AI анализ не дал результата.")

    except Exception as e:
        logger.error(f"Ошибка AI анализа: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:200]}")
        await queue_store.set_error("ai", user_id)
        return
    finally:
        await queue_store.set_done("ai", user_id)


@router.message(Command("check"))
async def cmd_check(message: types.Message, config: BotConfig) -> None:
    """Handler for /check — статус фоновых задач"""
    user = message.from_user
    if user is None:
        await message.reply("❌ Не удалось определить пользователя.")
        return
    user_id = user.id

    status_text = await _build_status_text(user_id, config)
    await message.reply(status_text)


@router.message(Command("status"))
async def cmd_status(message: types.Message, config: BotConfig) -> None:
    """Handler for /status — детальный статус с health-check llama.cpp"""
    user = message.from_user
    if user is None:
        await message.reply("❌ Не удалось определить пользователя.")
        return
    user_id = user.id

    status_text = await _build_status_text(user_id, config)
    await message.reply(status_text)


@router.message(Command("ask"))
async def cmd_ask(message: types.Message, config: BotConfig) -> None:
    """Handler for /ask — RAG-поиск по базе знаний с кнопкой сохранения в wiki."""
    from src.modules.module4_rag import RAGEngine
    from src.bot.routers.wiki_cmds import register_answer, save_answer_keyboard

    user_id = message.from_user.id if message.from_user else 0

    # Извлечь вопрос из текста команды
    text = message.text or ""
    question = text.removeprefix("/ask").strip()
    if not question:
        await message.reply(
            "❓ Использование: <code>/ask ваш вопрос</code>\n"
            "Например: <code>/ask что такое трансформеры?</code>"
        )
        return

    status_msg = await message.reply(f"🔍 Ищу ответ на: «{question[:80]}»...")

    try:
        user_root = config.users_dir / config.user_name
        downloads_dir = user_root / "downloads"

        if not downloads_dir.exists() or not any(downloads_dir.iterdir()):
            await status_msg.edit_text(
                "📭 База знаний пуста.\nСначала скачай и обработай контент через /ai."
            )
            return

        rag = RAGEngine(user_root=downloads_dir)

        # Индексируем все неиндексированные папки
        for folder in downloads_dir.iterdir():
            if folder.is_dir():
                await asyncio.to_thread(rag.index_folder, folder)

        result = await asyncio.to_thread(rag.query, question)
        answer = result.get("answer", "_Ответ не получен_")
        sources = result.get("sources", [])

        # Регистрируем ответ для возможного сохранения
        register_answer(user_id, question, answer, sources)

        # Логируем запрос в wiki log.md
        try:
            from src.modules.wiki_manager import WikiManager

            wm = WikiManager(user_root)
            wm.append_log(
                operation="query",
                title=question[:80],
                details=f"Источники: {', '.join(sources[:3])}"
                if sources
                else "без источников",
            )
        except Exception:
            pass

        sources_text = ""
        if sources:
            sources_text = "\n\n📂 <b>Источники:</b>\n" + "\n".join(
                f"• <code>{s}</code>" for s in sources[:5]
            )

        response_text = f"❓ <b>{question}</b>\n\n{answer}{sources_text}"

        await status_msg.edit_text(
            response_text,
            reply_markup=save_answer_keyboard(user_id),
        )

    except ImportError:
        await status_msg.edit_text(
            "⚠️ RAG-поиск недоступен.\n"
            "Установите зависимости: <code>pip install chromadb sentence-transformers langchain-text-splitters</code>"
        )
    except Exception as e:
        logger.error(f"Ошибка /ask: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка поиска: {str(e)[:200]}")
