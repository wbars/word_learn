"""Main bot entry point."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from word_learn.config import get_settings
from word_learn.database import init_db, close_db
from word_learn.handlers import setup_routers


async def main() -> None:
    """Initialize and start the bot."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    # Load settings
    settings = get_settings()
    logger.info(
        f"Starting bot with {settings.source_lang.value}->{settings.target_lang.value} language pair"
    )

    # Initialize database
    await init_db()
    logger.info("Database connection initialized")

    # Create bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Setup handlers
    dp.include_router(setup_routers())
    logger.info("Handlers registered")

    try:
        # Delete webhook and start polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
