"""Handlers for the reversible word archive.

``/archive_words`` parks every active card of the chat so a fresh word list
can be built from scratch; ``/unarchive_words`` brings the most recently
archived cards back next to the current ones (``/unarchive_words all``
restores every archive at once).

The commands only touch the sender's own rows and are fully reversible, so
they are open to every chat and need no confirmation step.
"""
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from word_learn.repositories import PracticeRepository
from word_learn.services.word_archive import UnarchiveResult, WordArchiveService

router = Router()

UNARCHIVE_ALL_ARGUMENT = "all"


def _format_day(moment: datetime) -> str:
    return moment.strftime("%d %b")


@router.message(Command("archive_words"))
async def cmd_archive_words(message: Message) -> None:
    """Archive all active cards of this chat."""
    chat_id = message.chat.id
    result = await WordArchiveService().archive_all(chat_id)

    if result.archived_cards == 0:
        if result.previously_archived_cards == 0:
            await message.answer("No active cards to archive.")
        else:
            await message.answer(
                "No active cards to archive. "
                f"{result.previously_archived_cards} cards are archived - "
                "/unarchive_words brings them back."
            )
        return

    if result.previously_archived_cards:
        lines = [
            f"Archived {result.archived_cards} cards "
            f"({result.total_archived_cards} archived in total)."
        ]
    else:
        lines = [f"Archived {result.archived_cards} cards."]
    if result.current_practice_removed:
        lines.append("Current practice session cleared.")
    lines.append('Add words with /add word1 word2 or send "cat, kat".')
    lines.append("Undo any time: /unarchive_words")
    await message.answer("\n".join(lines))


def format_unarchive_reply(result: UnarchiveResult, pool_remaining: int) -> str:
    """Build the /unarchive_words reply for a successful restore."""
    if len(result.generations) == 1:
        generation = result.generations[0]
        first = f"Restored {generation.cards} cards archived on {_format_day(generation.archived_at)}"
        if generation.shifted_days:
            unit = "day" if generation.shifted_days == 1 else "days"
            first += f" (review dates moved forward {generation.shifted_days} {unit})"
        lines = [first + f". Active cards: {result.active_cards}."]
    else:
        lines = [
            f"Restored {result.restored_cards} cards from {len(result.generations)} archives. "
            f"Active cards: {result.active_cards}."
        ]

    if result.remaining_archived_cards:
        lines.append(
            f"{result.remaining_archived_cards} older cards remain archived - "
            "send /unarchive_words again to bring them back too, "
            "or /unarchive_words all for everything."
        )

    if pool_remaining:
        lines.append(
            f"{pool_remaining} cards from today's list come first, "
            "then the restored cards are mixed in."
        )
    lines.append("Send /practice to continue.")
    return "\n".join(lines)


@router.message(Command("unarchive_words"))
async def cmd_unarchive_words(message: Message, command: CommandObject) -> None:
    """Restore the newest archive (or all archives with the "all" argument)."""
    chat_id = message.chat.id
    everything = (command.args or "").strip().lower() == UNARCHIVE_ALL_ARGUMENT

    result = await WordArchiveService().unarchive(chat_id, everything=everything)

    if result.restored_cards == 0:
        await message.answer("No archived cards to restore.")
        return

    pool_remaining = await PracticeRepository().count_words_to_practice(chat_id)
    await message.answer(format_unarchive_reply(result, pool_remaining))
