"""Handlers for the opt-in alternative UX.

The alternative UX is enabled per chat with ``/alternative_ux_on`` and disabled
with ``/alternative_ux_off``. Everything here is gated on that per-chat flag so
that chats which never opted in keep the original experience untouched.

While enabled, a chat gets:
- native Telegram "menu" shortcuts for ``add_next_batch``, ``Practice words``
  and ``alternative_ux_off`` (set with a per-chat command scope);
- a wider answer keyboard without a Delete button (see
  :func:`word_learn.keyboards.practice.answer_keyboard_alternative`);
- the ability to delete a word by replying "delete" to it.
"""
from typing import Optional

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from word_learn.repositories import PracticeRepository
from word_learn.services.practice_service import PracticeService
from word_learn.services.user_settings import is_alternative_ux_enabled

router = Router()


# Commands surfaced through the native Telegram menu button while the
# alternative UX is enabled for a chat.
ALTERNATIVE_MENU_COMMANDS = [
    BotCommand(command="add_next_batch", description="Add next batch"),
    BotCommand(command="practice", description="Practice words"),
    BotCommand(command="alternative_ux_off", description="Turn off alternative UX"),
]

DELETE_REPLY_KEYWORD = "delete"


@router.message(Command("alternative_ux_on"))
async def cmd_alternative_ux_on(message: Message, bot: Bot) -> None:
    """Enable the alternative UX for this chat."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    await repository.set_alternative_ux(chat_id, True)

    # Per-chat scope keeps the menu shortcuts private to this chat.
    await bot.set_my_commands(
        ALTERNATIVE_MENU_COMMANDS,
        scope=BotCommandScopeChat(chat_id=chat_id),
    )

    await message.answer(
        "Alternative UX enabled.\n\n"
        "• Use the Telegram menu button for quick commands.\n"
        "• Reply \"delete\" to a word to remove it from practice.\n\n"
        "Send /alternative_ux_off to switch back to the default experience."
    )


@router.message(Command("alternative_ux_off"))
async def cmd_alternative_ux_off(message: Message, bot: Bot) -> None:
    """Disable the alternative UX for this chat and restore defaults."""
    chat_id = message.chat.id
    repository = PracticeRepository()
    await repository.set_alternative_ux(chat_id, False)

    # Remove the per-chat menu so this chat falls back to the default menu.
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))

    await message.answer(
        "Alternative UX disabled. Back to the default experience.\n"
        "Send /alternative_ux_on to enable it again."
    )


def extract_word_id(message: Optional[Message]) -> Optional[int]:
    """Extract the word ID encoded in a practice message's inline keyboard.

    Both the prompt ("reveal {id}") and the revealed message
    ("finish {id} {action}") carry the word ID inside their button callback
    data, so a reply to either can be resolved without extra storage.

    Args:
        message: The message that was replied to (may be None)

    Returns:
        The word ID, or None when it cannot be determined
    """
    if message is None or message.reply_markup is None:
        return None

    for row in message.reply_markup.inline_keyboard:
        for button in row:
            data = button.callback_data
            if not data:
                continue
            parts = data.split()
            if len(parts) >= 2 and parts[0] in ("reveal", "finish"):
                try:
                    return int(parts[1])
                except ValueError:
                    return None
    return None


async def is_delete_reply(message: Message) -> bool:
    """Filter: a "delete" reply from a chat with the alternative UX enabled.

    Returns False (so the update falls through to the normal text handlers)
    for any chat that has not opted in, guaranteeing the default UX is never
    altered. The cheap text/reply checks run before the database lookup.
    """
    if not message.text or message.text.strip().lower() != DELETE_REPLY_KEYWORD:
        return False
    if message.reply_to_message is None:
        return False

    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        return False

    return await is_alternative_ux_enabled(chat_id)


@router.message(is_delete_reply)
async def handle_delete_reply(message: Message) -> None:
    """Delete the replied-to word when the alternative UX is enabled."""
    word_id = extract_word_id(message.reply_to_message)
    if word_id is None:
        await message.answer("Reply to a word message with \"delete\" to remove it.")
        return

    chat_id = message.chat.id
    repository = PracticeRepository()
    service = PracticeService(repository)

    practice_word = await repository.get_practice_word(chat_id, word_id)
    if practice_word is None:
        await message.answer("Word not found.")
        return

    await service.mark_deleted(chat_id, word_id)
    await message.answer("Deleted!")
