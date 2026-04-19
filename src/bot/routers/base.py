from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """
    Handler for /start command
    """
    user_name = message.from_user.first_name if message.from_user else "User"

    welcome_text = f"""
🐝 <b>Data Hive — Personal Knowledge Manager</b>

👋 Привет, {user_name}!

Я помогу тебе сохранять и систематизировать контент из разных источников в твою персональную базу знаний.

━━━━━━━━━━━━━━━━━━━━━━━
📥 <b>Что я умею:</b>

🔗 <b>Социальные сети</b>
   • Instagram (Posts, Reels, Stories)
   • YouTube (Videos, Shorts)
   • TikTok (скоро)

🎤 <b>Транскрипция</b>
   • Распознавание речи (Whisper AI)
   • Поддержка 99+ языков
   • Сохранение в Markdown

🤖 <b>AI Анализ</b>
   • Автоматическое саммари
   • Умные теги
   • Категоризация

━━━━━━━━━━━━━━━━━━━━━━━
🚀 <b>Как использовать:</b>

1️⃣ Отправь ссылку (YouTube/Instagram)
2️⃣ Или отправь файл (фото/видео)
3️⃣ Или отправь текст для заметки

Я скачаю, транскрибирую и сохраню всё в Obsidian!
"""
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """
    Handler for /help command
    """
    help_text = """
📖 <b>Полное руководство Data Hive</b>

<b>📥 1. Загрузка контента:</b>
• <b>Файлы и текст (отправляй без команды):</b>
  - Отправьте фото/видео/документ → сохраню в личную папку
  - Отправьте текст → сохраню как заметку

• <b>Отправьте команду /url</b>
Я запрошу ссылку. Пришли ссылку на Youtube или Instagram.

<b>Я умею скачивать по ссылке в локальную базу данных:</b>
• <b>YouTube:</b>
  - Видео (watch?v=..., youtu.be/...)
  - Shorts (shorts/...)
  - Комментарии (предложу скачать после видео)

• <b>Instagram:</b>
  - Posts (p/...) - Фото/Карусели/Видео
  - Reels (reel/...) - Видео

<b>🧠 2. Обработка и AI:</b>
• /transcribe - Транскрибировать все видео в папке (Whisper)
• /ai - Запустить AI анализ: тегирование, саммари (llama.cpp)
• /ask &lt;вопрос&gt; - Умный поиск по вашей базе (RAG)

<b>� 3. Wiki (LLM Knowledge Base):</b>
• /wiki - Статистика базы знаний (источники, концепты, запросы)
• /lint - Проверка здоровья wiki (битые ссылки, осиротевшие папки)
• /concepts - Топ концептов по упоминаниям
• /save - Сохранить последний ответ /ask в wiki

<b>🔧 4. Утилиты:</b>
• /mcp - Получить ключ для подключения IDE
• /check - Проверить статус фоновых задач
• /status - Детальный статус + health-check llama.cpp
• /show - Показать файлы последней папки

📊 <b>Как это работает:</b>
1. Вы скидываете контент → Бот сохраняет в <code>downloads/...</code>
2. Бот предлагает скачать комментарии (если есть)
3. Бот спрашивает название для папки
4. Вы запускаете /transcribe или /ai для обогащения данных
5. Ищете ответы через /ask или подключаетесь через MCP прямо из IDE
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)
