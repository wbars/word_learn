"""Handler for /start command."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


WELCOME_MESSAGE = """Hello! Welcome to Word Learner Bot!

Here are the available commands:

/start - Show this welcome message
/add word1 word2 - Add a word to learn
/addWords - Add words from the database
/practice - Start a practice session
/remind HH:mm - Set daily reminder
/reset - Reset current practice session

You can also send text directly to add words:
• "cat, kat" - comma-separated
• "cat kat" - space-separated (single words only)
"""


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(WELCOME_MESSAGE)
