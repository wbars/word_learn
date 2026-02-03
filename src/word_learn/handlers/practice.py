"""Handlers for practice flow."""
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from word_learn.config import get_settings
from word_learn.keyboards.practice import (
    reveal_keyboard,
    answer_keyboard,
    practice_more_keyboard,
)
from word_learn.repositories import PracticeRepository
from word_learn.services.practice_service import PracticeService
from word_learn.services.session_messages import format_session_complete_message
from word_learn.services.stage_labels import get_stage_label

router = Router()


@router.message(Command("practice"))
async def cmd_practice(message: Message) -> None:
    """Handle /practice command - start practice session."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    # Start practice session
    words = await service.start_practice_session(chat_id)

    if not words:
        await message.answer("No words to practice!")
        return

    # Show first word
    await _show_practice_word(message, chat_id)


@router.callback_query(F.data == "practice")
async def callback_practice(callback: CallbackQuery) -> None:
    """Handle practice button callback."""
    await callback.answer()

    if not callback.message:
        return

    chat_id = callback.message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    # Start new practice batch
    words = await service.start_practice_session(chat_id)

    if not words:
        await callback.message.answer("No words to practice!")
        return

    await _show_practice_word(callback.message, chat_id)


@router.callback_query(F.data.startswith("reveal "))
async def callback_reveal(callback: CallbackQuery) -> None:
    """Handle reveal button callback."""
    await callback.answer()

    if not callback.message:
        return

    # Parse word_id from callback data
    data_parts = callback.data.split()
    if len(data_parts) < 2:
        return

    word_id = int(data_parts[1])
    chat_id = callback.message.chat.id
    repository = PracticeRepository()
    settings = get_settings()

    # Get practice word
    practice_word = await repository.get_practice_word(chat_id, word_id)
    if not practice_word:
        await callback.message.answer("Word not found.")
        return

    source_text = practice_word.get_translation(settings.source_lang) or "?"
    target_text = practice_word.get_translation(settings.target_lang) or "?"

    await callback.message.answer(
        f"{source_text} : {target_text}",
        reply_markup=answer_keyboard(word_id),
    )


@router.callback_query(F.data.startswith("finish "))
async def callback_finish(callback: CallbackQuery) -> None:
    """Handle finish (correct/incorrect/delete) button callback."""
    await callback.answer()

    if not callback.message:
        return

    # Parse callback data: finish {word_id} {action}
    data_parts = callback.data.split()
    if len(data_parts) < 3:
        return

    word_id = int(data_parts[1])
    action = data_parts[2]
    chat_id = callback.message.chat.id

    repository = PracticeRepository()
    service = PracticeService(repository)

    # Handle action
    if action == "correct":
        old_stage, new_stage = await service.mark_correct(chat_id, word_id)
        old_label = get_stage_label(old_stage)
        new_label = get_stage_label(new_stage)
        if old_stage == new_stage:
            text = f"Correct! {new_label}"
        else:
            text = f"Correct! {old_label} → {new_label}"
        await callback.message.answer(text)
    elif action == "delete":
        await service.mark_deleted(chat_id, word_id)
        await callback.message.answer("Deleted!")
    else:  # incorrect
        old_stage, new_stage = await service.mark_incorrect(chat_id, word_id)
        old_label = get_stage_label(old_stage)
        new_label = get_stage_label(new_stage)
        text = f"Incorrect! {old_label} → {new_label}"
        await callback.message.answer(text)

    # Show next word
    await _show_practice_word(callback.message, chat_id)


async def _show_practice_word(message: Message, chat_id: int) -> None:
    """Show the next practice word or session completion."""
    repository = PracticeRepository()
    settings = get_settings()

    # Get next word from current practice
    practice_word = await repository.get_next_practice_word(chat_id)

    if practice_word is None:
        # Session complete
        count = await repository.count_words_to_practice(chat_id)
        settings = get_settings()
        today = datetime.now(settings.timezone).date()
        streak_days = await repository.update_streak(chat_id, today)

        if count == 0:
            # All daily words done - show simple stats
            stats = await repository.get_statistics(chat_id)
            text = format_session_complete_message(count, stats, streak_days)
            await repository.reset_statistics(chat_id)
            await repository.clear_session_results(chat_id)
        else:
            # Batch complete, more words remain
            text = format_session_complete_message(count)

        await message.answer(
            text,
            reply_markup=practice_more_keyboard(count, "Practice more"),
        )
        return

    # Show word with reveal button
    target_text = practice_word.get_translation(settings.target_lang) or "?"
    await message.answer(
        target_text,
        reply_markup=reveal_keyboard(practice_word.word.id),
    )
