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
/archive_words - Archive all your words (reversible)
/unarchive_words - Bring archived words back

Settings (each is on by default):
/reverse_cards_off - Add only "word → translation" when adding a word
/reverse_cards_on - Also add the reversed "translation → word" card
/daily_limit_off - Practice all due words, no daily cap
/daily_limit_on - Cap the daily practice list at 67-76 words

You can also send text directly to add words:
• "cat, kat" - comma-separated
• "cat kat" - space-separated (single words only)
• several lines at once - one "word, translation" per line
"""

ADMIN_BATCH_COMMANDS = """
Admin Dutch-English course commands:
/add_next_batch - Add the next curated batch
/batch_status - Show curated batch progress
/reset_my_words confirm - Delete active cards and reset batch progress (archived cards are kept)
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
