"""Handler for adding custom words."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.config import get_settings
from word_learn.keyboards.practice import practice_more_keyboard
from word_learn.repositories import PracticeRepository
from word_learn.services.practice_service import PracticeService

router = Router()


@router.message(Command("add"))
async def cmd_add_word(message: Message) -> None:
    """Handle /add command."""
    if not message.text:
        await message.answer("Please provide words to add: /add word1 word2")
        return

    # Parse arguments: /add word1 word2
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /add word1 word2")
        return

    target_word = parts[1].strip()
    source_word = parts[2].strip()

    await _add_word(message, target_word, source_word)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_direct_text(message: Message) -> None:
    """Handle direct text input for adding words."""
    if not message.text:
        return

    text = message.text.strip()
    repository = PracticeRepository()
    service = PracticeService(repository)

    # Several lines = a pasted list: one "word, translation" pair per line.
    # A single pair merely broken over two lines ("the cat,\nde kat") keeps
    # the original one-pair parsing.
    if "\n" in text and not _looks_like_one_pair(text):
        await _add_words_batch(message, text)
        return

    parsed = service.parse_word_input(text)
    if parsed is None:
        await message.answer(
            "Use ',' for words with multiple whitespaces.\n"
            "Examples:\n"
            "• cat, kat\n"
            "• the cat, de kat"
        )
        return

    target_word, source_word = parsed
    await _add_word(message, target_word, source_word)


MAX_REJECTED_LINES_SHOWN = 5


def _looks_like_one_pair(text: str) -> bool:
    """True for a single "word, translation" pair that just contains a line break."""
    lines = [line for line in text.splitlines() if line.strip()]
    return (
        text.count(",") == 1
        and len(lines) <= 2
        and not any(line.lstrip().startswith("#") for line in lines)
    )


async def _add_words_batch(message: Message, text: str) -> None:
    """Add every parsable line of a multi-line message and report the outcome."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    pairs, rejected = service.parse_batch_input(text)
    if not pairs:
        await message.answer(
            "No word pairs found. Put one pair per line:\n"
            "• cat, kat\n"
            "• the cat, de kat"
        )
        return

    added, skipped = await service.add_custom_words(chat_id, pairs)

    lines = [f"Done! Added {added} words to learn."]
    if skipped:
        lines.append(f"Already in your list, skipped: {skipped}")
    if rejected:
        lines.append(f"Could not parse {len(rejected)} lines (use \"word, translation\"):")
        lines.extend(f"• {line}" for line in rejected[:MAX_REJECTED_LINES_SHOWN])
        if len(rejected) > MAX_REJECTED_LINES_SHOWN:
            lines.append(f"... and {len(rejected) - MAX_REJECTED_LINES_SHOWN} more")

    count = await repository.count_words_to_practice(chat_id)
    await message.answer(
        "\n".join(lines),
        reply_markup=practice_more_keyboard(count, "Practice words"),
    )


async def _add_word(message: Message, target_word: str, source_word: str) -> None:
    """Add a word and send confirmation."""
    if not target_word or not source_word:
        await message.answer("Please provide both words.")
        return

    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)
    settings = get_settings()

    word1, word2 = await service.add_custom_word(chat_id, target_word, source_word)

    # Get count for keyboard
    count = await repository.count_words_to_practice(chat_id)

    await message.answer(
        f"Done! Added word to learn: {target_word} : {source_word}",
        reply_markup=practice_more_keyboard(count, "Practice words"),
    )
