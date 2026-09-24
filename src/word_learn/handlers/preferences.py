"""Per-chat on/off preferences: reverse cards and the daily practice limit.

Both follow the ``/alternative_ux_on`` / ``/alternative_ux_off`` pattern: one
command switches the flag on, its twin switches it off, and the flag lives in
the chat's ``user_settings`` row. Unlike the alternative UX both default to
ON, so every chat keeps the behaviour it had before the commands existed
until it opts out.

- ``/reverse_cards_on`` / ``/reverse_cards_off``: whether adding a word
  (``/add``, "cat, kat", a multi-line paste) also creates the reversed card
  (translation → word). The curated admin batches (``/add_next_batch``) and
  ``/addWords`` are not affected.
- ``/daily_limit_on`` / ``/daily_limit_off``: whether the daily practice
  list is capped at ``daily_pool_min``-``daily_pool_max`` due words.
  Switching it off puts every due word into today's list right away;
  switching it back on (a real off -> on change) trims today's list to the
  cap (words of the running session are kept, the removed ones come back in
  the next list). Re-sending ``/daily_limit_on`` while it is already on
  leaves the list alone.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from word_learn.config import get_settings
from word_learn.repositories import PracticeRepository
from word_learn.services.practice_service import PracticeService

router = Router()


@router.message(Command("reverse_cards_on"))
async def cmd_reverse_cards_on(message: Message) -> None:
    """Add both directions again when a word is added (the default)."""
    chat_id = message.chat.id
    await PracticeRepository().set_reverse_cards(chat_id, True)

    await message.answer(
        "Reverse cards enabled. Every word you add gets two cards: "
        "word → translation and translation → word.\n"
        "Send /reverse_cards_off to add only word → translation."
    )


@router.message(Command("reverse_cards_off"))
async def cmd_reverse_cards_off(message: Message) -> None:
    """Add only the card as typed when a word is added."""
    chat_id = message.chat.id
    await PracticeRepository().set_reverse_cards(chat_id, False)

    await message.answer(
        "Reverse cards disabled. Every word you add gets one card: "
        "word → translation.\n"
        "Words already in your list are not changed.\n"
        "Send /reverse_cards_on to also add translation → word again."
    )


def _daily_limit_range() -> str:
    settings = get_settings()
    return f"{settings.daily_pool_min}-{settings.daily_pool_max}"


@router.message(Command("daily_limit_on"))
async def cmd_daily_limit_on(message: Message) -> None:
    """Cap the daily practice list again (the default) and trim today's list."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    was_on = await repository.get_daily_limit(chat_id)
    # Flag first, so a /practice arriving meanwhile already builds a capped pool.
    await repository.set_daily_limit(chat_id, True)

    if was_on:
        # Re-sending the default setting must not touch today's list.
        await message.answer(
            f"Daily limit is already on. Your practice list takes {_daily_limit_range()} "
            "due words a day.\n"
            "Send /daily_limit_off to practice all due words at once."
        )
        return

    removed, remaining = await service.trim_today_pool(chat_id)

    lines = [
        f"Daily limit enabled. Your practice list takes {_daily_limit_range()} "
        "due words a day."
    ]
    if removed:
        lines.append(
            f"Today's list trimmed to {remaining} words; the other {removed} "
            "stay due and come back in the next list."
        )
    lines.append("Send /daily_limit_off to practice all due words at once.")
    await message.answer("\n".join(lines))


@router.message(Command("daily_limit_off"))
async def cmd_daily_limit_off(message: Message) -> None:
    """Remove the daily cap and put every due word into today's list now."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    # Flag first, so a /practice arriving meanwhile already builds an uncapped pool.
    await repository.set_daily_limit(chat_id, False)
    pool_size = await service.fill_today_pool(chat_id)

    await message.answer(
        "Daily limit disabled. Your practice list now takes every due word "
        f"instead of {_daily_limit_range()} a day.\n"
        f"Today's list: {pool_size} words.\n"
        "Send /daily_limit_on to bring the limit back."
    )
