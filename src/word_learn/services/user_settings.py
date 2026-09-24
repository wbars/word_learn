"""Helpers for per-chat preferences (one row per chat in ``user_settings``).

Every flag is toggled with a pair of commands (``/<flag>_on`` and
``/<flag>_off``) and read here with a sensible default for chats that never
sent either command:

- alternative UX: strictly opt-in, defaults to ``False`` so that users who
  never opted in keep the original experience unchanged;
- reverse cards (``/reverse_cards_on|off``): defaults to ``True``, adding a
  word also creates the reversed card, as it always did;
- daily limit (``/daily_limit_on|off``): defaults to ``True``, the daily
  practice pool is capped at 67-76 due words, as it always was.
"""
from word_learn.repositories import PracticeRepository


async def is_alternative_ux_enabled(chat_id: int) -> bool:
    """Return True when the chat enabled the alternative UX.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Whether the alternative UX is active for this chat (False by default)
    """
    repository = PracticeRepository()
    return await repository.get_alternative_ux(chat_id)


async def is_reverse_cards_enabled(chat_id: int) -> bool:
    """Return True when adding a word should also create the reversed card.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Whether reversed cards are created for this chat (True by default)
    """
    repository = PracticeRepository()
    return await repository.get_reverse_cards(chat_id)


async def is_daily_limit_enabled(chat_id: int) -> bool:
    """Return True when the chat's daily practice pool is capped.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Whether the daily limit applies to this chat (True by default)
    """
    repository = PracticeRepository()
    return await repository.get_daily_limit(chat_id)
