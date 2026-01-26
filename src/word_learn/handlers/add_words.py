"""Handler for /addWords command - add words from database."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from word_learn.config import get_settings
from word_learn.models import Word
from word_learn.repositories import PracticeRepository

router = Router()


class AddWordsState(StatesGroup):
    """States for adding words flow."""
    choosing = State()


LEARN_BUTTON = "Learn"
SKIP_BUTTON = "Skip"

learn_skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=LEARN_BUTTON), KeyboardButton(text=SKIP_BUTTON)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


@router.message(Command("addWords"))
async def cmd_add_words(message: Message, state: FSMContext) -> None:
    """Handle /addWords command."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    settings = get_settings()

    # Get words to add
    words = await repository.get_words_to_add(chat_id, limit=10)

    if not words:
        await message.answer("No new words available to add!")
        return

    # Store words in state
    await state.update_data(
        words=[_word_to_dict(w) for w in words],
        current_index=0,
        words_to_learn=[],
        words_to_skip=[],
    )

    # Show first word
    await _show_next_word(message, state)


async def _show_next_word(message: Message, state: FSMContext) -> None:
    """Show the next word for learning decision."""
    data = await state.get_data()
    words = data["words"]
    current_index = data["current_index"]
    settings = get_settings()

    if current_index >= len(words):
        # All words processed
        await _finish_adding(message, state)
        return

    word_data = words[current_index]
    source_text = word_data.get(settings.source_lang.column_name, "?")
    target_text = word_data.get(settings.target_lang.column_name, "?")

    await state.set_state(AddWordsState.choosing)
    await message.answer(
        f"{source_text} : {target_text}",
        reply_markup=learn_skip_keyboard,
    )


@router.message(AddWordsState.choosing, F.text == LEARN_BUTTON)
async def handle_learn(message: Message, state: FSMContext) -> None:
    """Handle Learn button press."""
    data = await state.get_data()
    word_data = data["words"][data["current_index"]]

    words_to_learn = data["words_to_learn"]
    words_to_learn.append(word_data["id"])

    await state.update_data(
        current_index=data["current_index"] + 1,
        words_to_learn=words_to_learn,
    )

    await _show_next_word(message, state)


@router.message(AddWordsState.choosing, F.text == SKIP_BUTTON)
async def handle_skip(message: Message, state: FSMContext) -> None:
    """Handle Skip button press."""
    data = await state.get_data()
    word_data = data["words"][data["current_index"]]

    words_to_skip = data["words_to_skip"]
    words_to_skip.append(word_data["id"])

    await state.update_data(
        current_index=data["current_index"] + 1,
        words_to_skip=words_to_skip,
    )

    await _show_next_word(message, state)


async def _finish_adding(message: Message, state: FSMContext) -> None:
    """Finish adding words flow."""
    data = await state.get_data()
    chat_id = message.chat.id
    repository = PracticeRepository()

    words_to_learn = data["words_to_learn"]
    words_to_skip = data["words_to_skip"]

    # Add words to practice
    if words_to_learn:
        await repository.add_to_practice(chat_id, words_to_learn)

    # Add words to skiplist
    if words_to_skip:
        await repository.add_to_skiplist(chat_id, words_to_skip)

    await state.clear()
    await message.answer(
        f"Done! Added words to learn: {len(words_to_learn)}",
        reply_markup=ReplyKeyboardRemove(),
    )


def _word_to_dict(word: Word) -> dict:
    """Convert Word to dict for state storage."""
    return {
        "id": word.id,
        "en": word.en,
        "nl": word.nl,
        "ru": word.ru,
    }
