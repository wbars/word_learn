"""Handler for /remind command."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.config import get_settings
from word_learn.repositories import PracticeRepository

router = Router()


@router.message(Command("remind"))
async def cmd_remind(message: Message) -> None:
    """Handle /remind command."""
    if not message.text:
        await message.answer("Usage: /remind HH:mm")
        return

    # Parse arguments: /remind HH:mm
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /remind HH:mm (e.g., /remind 09:00)")
        return

    time_str = parts[1]
    settings = get_settings()
    tz = settings.timezone

    try:
        # Parse time
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        await message.answer("Invalid time format. Use HH:mm (e.g., 09:00)")
        return

    chat_id = message.chat.id
    repository = PracticeRepository()

    # Calculate next reminder
    now = datetime.now(tz)
    next_remind = _calculate_next_reminder(now, parsed_time, tz)

    # Save reminder
    await repository.set_reminder(chat_id, parsed_time, next_remind)

    # Format response
    next_remind_str = next_remind.strftime("%d %b %H:%M")
    await message.answer(
        f"OK, set reminder daily on {time_str}. Next reminder: {next_remind_str}"
    )


def _calculate_next_reminder(
    now: datetime,
    remind_time: time,
    tz: ZoneInfo,
) -> datetime:
    """Calculate the next reminder datetime.

    If the time has already passed today, schedule for tomorrow.
    """
    # Create datetime for today at remind_time
    today_remind = datetime.combine(now.date(), remind_time, tzinfo=tz)

    if today_remind <= now:
        # Time has passed today, schedule for tomorrow
        from datetime import timedelta
        today_remind = today_remind + timedelta(days=1)

    return today_remind
