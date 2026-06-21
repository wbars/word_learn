"""Helpers for per-chat UX preferences.

The alternative UX is strictly opt-in: a chat only sees it after sending the
``/alternative_ux_on`` command. Every lookup defaults to ``False`` so that
users who never opted in keep the original experience unchanged.
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
