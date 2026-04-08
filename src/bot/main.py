import asyncio
import logging
import sys
import uvloop
from pathlib import Path

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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from src.bot.config import BotConfig
from src.bot.routers import base
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

    if config.webhook_mode:
        # --- Webhook режим ---
        if not config.webhook_public_url:
            logger.error("WEBHOOK_PUBLIC_URL не задан! Установите его в .env")
            sys.exit(1)

        webhook_url = f"{config.webhook_public_url.rstrip('/')}/{config.webhook_path}"
        logger.info(f"🌐 Webhook режим: {webhook_url}")

        await bot.set_webhook(
            url=webhook_url,
            secret_token=config.webhook_secret_token,
            drop_pending_updates=True,
        )

        app = web.Application()
        handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=config.webhook_secret_token,
        )
        handler.register(app, path=f"/{config.webhook_path}")
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=config.webhook_listen, port=config.webhook_port)
        await site.start()

        logger.info(f"🚀 Data Hive Bot запущен (webhook, {config.webhook_listen}:{config.webhook_port})")

        # Ждём до остановки
        await asyncio.Event().wait()
    else:
        # --- Polling режим ---
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
