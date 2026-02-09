#!/usr/bin/env python3
"""Reminder service for sending daily practice notifications.

This script runs continuously and checks for due reminders every minute.
When a reminder is due, it sends a notification to the user and schedules
the next reminder for the following day.

Usage:
    python scripts/run_reminders.py

Environment variables:
    BOT_TOKEN: Telegram bot token
    DATABASE_URL: PostgreSQL connection string
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from word_learn.config import get_settings
from word_learn.database import init_db, close_db
from word_learn.repositories import PracticeRepository


# Check interval in seconds
CHECK_INTERVAL = 60


async def send_reminder(bot: Bot, chat_id: int, word_count: int) -> bool:
    """Send a practice reminder to a user.

    Args:
        bot: Telegram bot instance
        chat_id: User's chat ID
        word_count: Number of words available to practice

    Returns:
        True if message was sent successfully
    """
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"Practice ({word_count})",
                    callback_data="practice"
                )]
            ]
        )

        await bot.send_message(
            chat_id=chat_id,
            text=f"Time to practice! You have {word_count} words waiting.",
            reply_markup=keyboard,
        )
        return True
    except Exception as e:
        logging.warning(f"Failed to send reminder to {chat_id}: {e}")
        return False


async def process_reminders(bot: Bot, repository: PracticeRepository) -> int:
    """Process all due reminders.

    Args:
        bot: Telegram bot instance
        repository: Practice repository instance

    Returns:
        Number of reminders sent
    """
    settings = get_settings()
    tz = settings.timezone
    now = datetime.now(tz)

    # Get all due reminders
    due_reminders = await repository.get_due_reminders()
    sent_count = 0

    for reminder in due_reminders:
        # Get word count for this user (all due words, not just today's pool)
        word_count = await repository.count_all_due_words(reminder.chat_id)

        if word_count > 0:
            # Send reminder
            if await send_reminder(bot, reminder.chat_id, word_count):
                sent_count += 1
                logging.info(f"Sent reminder to {reminder.chat_id} ({word_count} words)")

        # Schedule next reminder for tomorrow
        next_remind = datetime.combine(
            now.date() + timedelta(days=1),
            reminder.remind_time,
            tzinfo=tz,
        )
        await repository.update_next_reminder(reminder.chat_id, next_remind)

    return sent_count


async def main() -> None:
    """Main entry point for reminder service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    settings = get_settings()
    logger.info("Starting reminder service")

    # Initialize database
    await init_db()
    logger.info("Database connection initialized")

    # Create bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    repository = PracticeRepository()

    try:
        while True:
            try:
                sent = await process_reminders(bot, repository)
                if sent > 0:
                    logger.info(f"Sent {sent} reminders")
            except Exception as e:
                logger.error(f"Error processing reminders: {e}")

            # Wait before next check
            await asyncio.sleep(CHECK_INTERVAL)

    except asyncio.CancelledError:
        logger.info("Reminder service cancelled")
    finally:
        await close_db()
        await bot.session.close()
        logger.info("Reminder service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
