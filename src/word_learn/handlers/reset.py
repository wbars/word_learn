"""Handler for /reset command."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.repositories import PracticeRepository

router = Router()


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    """Handle /reset command - reset current practice session."""
    chat_id = message.chat.id
    repository = PracticeRepository()

    await repository.clear_current_practice(chat_id)
    await repository.reset_statistics(chat_id)

    await message.answer("Reset is done")
