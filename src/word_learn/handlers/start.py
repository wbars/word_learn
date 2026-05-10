"""Handler for /start command."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.config import Language, get_settings

router = Router()


BASE_WELCOME_MESSAGE = """Hello! Welcome to Word Learner Bot!

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

ADMIN_BATCH_COMMANDS = """
Admin Dutch-English course commands:
/add_next_batch - Add the next curated batch
/batch_status - Show curated batch progress
/reset_my_words confirm - Reset all words for this chat
"""


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    text = BASE_WELCOME_MESSAGE
    settings = get_settings()
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    if (
        settings.admin_chat_id is not None
        and chat_id == settings.admin_chat_id
        and settings.source_lang == Language.NL
        and settings.target_lang == Language.EN
    ):
        text += ADMIN_BATCH_COMMANDS
    await message.answer(text)
