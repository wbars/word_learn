"""Regression tests around the alternative-UX keyboard selection.

The headline guarantee: a chat that did not opt in must receive the exact same
answer keyboard as before. These tests run without a database by mocking the
repository, settings and the opt-in lookup.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.config import Language
from word_learn.handlers import practice as practice_handler
from word_learn.handlers.practice import callback_reveal

CHAT_ID = 999


def _make_callback():
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.data = "reveal 42"
    callback.message = MagicMock()
    callback.message.chat = MagicMock()
    callback.message.chat.id = CHAT_ID
    callback.message.answer = AsyncMock()
    return callback


def _patches(alternative_enabled: bool):
    practice_word = MagicMock()
    practice_word.get_translation.return_value = "x"

    repo = MagicMock()
    repo.get_practice_word = AsyncMock(return_value=practice_word)

    settings = MagicMock()
    settings.source_lang = Language.EN
    settings.target_lang = Language.RU

    return (
        patch.object(practice_handler, "PracticeRepository", return_value=repo),
        patch.object(practice_handler, "get_settings", return_value=settings),
        patch.object(
            practice_handler,
            "is_alternative_ux_enabled",
            AsyncMock(return_value=alternative_enabled),
        ),
    )


async def _reveal_markup(alternative_enabled: bool):
    callback = _make_callback()
    repo_patch, settings_patch, flag_patch = _patches(alternative_enabled)
    with repo_patch, settings_patch, flag_patch:
        await callback_reveal(callback)
    return callback.message.answer.call_args.kwargs["reply_markup"]


class TestRevealKeyboardSelection:
    @pytest.mark.asyncio
    async def test_default_user_gets_unchanged_three_button_keyboard(self):
        """Opt-out chats keep Correct / Incorrect / Delete, unchanged."""
        markup = await _reveal_markup(alternative_enabled=False)

        assert len(markup.inline_keyboard) == 1
        row = markup.inline_keyboard[0]
        assert [b.text for b in row] == ["✅ Correct", "❌ Incorrect", "🗑️ Delete"]
        assert [b.callback_data for b in row] == [
            "finish 42 correct",
            "finish 42 incorrect",
            "finish 42 delete",
        ]

    @pytest.mark.asyncio
    async def test_alternative_user_gets_two_button_keyboard_without_delete(self):
        markup = await _reveal_markup(alternative_enabled=True)

        assert len(markup.inline_keyboard) == 1
        row = markup.inline_keyboard[0]
        # Incorrect left, Correct right, no Delete.
        assert [b.text for b in row] == ["❌ Incorrect", "✅ Correct"]
        assert all("delete" not in b.callback_data for b in row)
