import asyncio
import logging
import sys
import uvloop

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.config import BotConfig
from src.bot.services.queue_store import init_db

async def main() -> None:
    config = BotConfig()

    # Инициализация БД очереди задач
    await init_db()

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())

    from src.bot.routers import base, content, worker_cmds
    from src.bot.routers.wiki_cmds import router as wiki_router
    from src.bot.middlewares.auth import AdminAccessMiddleware

    dp.include_router(base.router)
    dp.include_router(content.router)
    dp.include_router(worker_cmds.router)
    dp.include_router(wiki_router)

    dp.update.outer_middleware(AdminAccessMiddleware())
    dp["config"] = config

    logger.info("🚀 Data Hive Bot запущен (polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform != "win32":
        uvloop.install()

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped!")
