"""Admin commands for adding curated Dutch-English vocabulary batches."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.config import Language, get_settings
from word_learn.services.vocabulary_batches import VocabularyBatchService

router = Router()


def _is_admin(chat_id: int) -> bool:
    """Return true when the chat can use destructive batch commands."""
    settings = get_settings()
    return (
        settings.admin_chat_id is not None
        and chat_id == settings.admin_chat_id
        and settings.source_lang == Language.NL
        and settings.target_lang == Language.EN
    )


async def _answer_unauthorized(message: Message) -> None:
    await message.answer("This command is not available in this chat.")


@router.message(Command("add_next_batch"))
async def cmd_add_next_batch(message: Message) -> None:
    """Add the next curated vocabulary batch for the admin chat."""
    chat_id = message.chat.id
    if not _is_admin(chat_id):
        await _answer_unauthorized(message)
        return

    service = VocabularyBatchService()
    result = await service.add_next_batch(chat_id)
    if result is None:
        status = await service.get_status(chat_id)
        await message.answer(
            f"All batches are already added ({status.total_batches}/{status.total_batches})."
        )
        return

    preview = "\n".join(f"- {entry.nl} : {entry.en}" for entry in result.pairs[:10])
    suffix = ""
    if len(result.pairs) > 10:
        suffix = f"\n... and {len(result.pairs) - 10} more"

    await message.answer(
        "Added vocabulary batch "
        f"{result.batch}/{result.total_batches} ({result.level}).\n"
        f"Pairs added: {result.inserted_pairs}; cards added: {result.inserted_cards}.\n"
        f"Skipped pairs already in practice: {result.skipped_pairs}.\n\n"
        f"{preview}{suffix}"
    )


@router.message(Command("batch_status"))
async def cmd_batch_status(message: Message) -> None:
    """Show current curated vocabulary course progress."""
    chat_id = message.chat.id
    if not _is_admin(chat_id):
        await _answer_unauthorized(message)
        return

    status = await VocabularyBatchService().get_status(chat_id)
    if status.next_batch is None:
        next_text = "all batches added"
    else:
        next_text = f"next batch: {status.next_batch}/{status.total_batches}"

    await message.answer(
        f"Course: {status.course_id}\n"
        f"Added batches: {status.last_added_batch}/{status.total_batches}\n"
        f"Active cards: {status.active_cards}\n"
        f"{next_text}"
    )


@router.message(Command("reset_my_words"))
async def cmd_reset_my_words(message: Message) -> None:
    """Reset all learning state for the admin chat after explicit confirmation."""
    chat_id = message.chat.id
    if not _is_admin(chat_id):
        await _answer_unauthorized(message)
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or parts[1].strip().lower() != "confirm":
        await message.answer(
            "This will mark all practice cards as deleted and reset batch progress "
            "for this chat only.\n"
            "Send /reset_my_words confirm to continue."
        )
        return

    result = await VocabularyBatchService().reset_user_words(chat_id)
    await message.answer(
        "Reset complete for this chat.\n"
        f"Practice cards marked deleted: {result.word_practice_marked_deleted}\n"
        f"Today's pool removed: {result.today_practice}\n"
        f"Current session words removed: {result.current_practice}\n"
        f"Skipped words removed: {result.word_skiplist}\n"
        f"Session results removed: {result.session_word_results}\n"
        "Use /add_next_batch to add the first new batch."
    )
