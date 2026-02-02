import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from src.bot.config import BotConfig

logger = logging.getLogger(__name__)

class AdminAccessMiddleware(BaseMiddleware):
    """
    Blocks updates from users other than the configured ADMIN_ID.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        # Get config from data (injected in main.py)
        config: BotConfig = data.get("config")
        if not config:
            logger.error("Config not found in middleware data!")
            return await handler(event, data)

        # Get user from event
        user = data.get("event_from_user")
        if not user:
            # Maybe a system update or something without user context
            return await handler(event, data)
            
        if user.id != config.admin_id:
            logger.warning(f"🚫 Blocked unauthorized access from user: {user.id} ({user.username})")
            # We silently ignore unauthorized users to avoid spam
            return
            
        return await handler(event, data)
