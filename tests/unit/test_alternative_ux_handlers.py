"""Unit tests for the alternative-UX handlers (no database required)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.handlers import alternative_ux
from word_learn.handlers.alternative_ux import (
    ALTERNATIVE_MENU_COMMANDS,
    cmd_alternative_ux_off,
    cmd_alternative_ux_on,
    extract_word_id,
    handle_delete_reply,
    is_delete_reply,
)
from word_learn.keyboards.practice import (
    answer_keyboard,
    answer_keyboard_alternative,
    practice_more_keyboard,
    reveal_keyboard,
)

CHAT_ID = 12345


def _make_message():
    message = MagicMock()
    message.chat = MagicMock()
    message.chat.id = CHAT_ID
    message.answer = AsyncMock()
    return message


class TestExtractWordId:
    """extract_word_id pulls the word ID out of a message's inline keyboard."""

    def test_from_reveal_keyboard(self):
        msg = SimpleNamespace(reply_markup=reveal_keyboard(42))
        assert extract_word_id(msg) == 42

    def test_from_default_answer_keyboard(self):
        msg = SimpleNamespace(reply_markup=answer_keyboard(7))
        assert extract_word_id(msg) == 7

    def test_from_alternative_answer_keyboard(self):
        msg = SimpleNamespace(reply_markup=answer_keyboard_alternative(9))
        assert extract_word_id(msg) == 9

    def test_none_message(self):
        assert extract_word_id(None) is None

    def test_message_without_markup(self):
        assert extract_word_id(SimpleNamespace(reply_markup=None)) is None

    def test_unrelated_keyboard_returns_none(self):
        # The "Practice more" button carries no word id.
        msg = SimpleNamespace(reply_markup=practice_more_keyboard(3))
        assert extract_word_id(msg) is None


class TestIsDeleteReply:
    """The filter that gates the delete-by-reply handler."""

    @pytest.mark.asyncio
    async def test_matches_delete_reply_when_enabled(self):
        message = SimpleNamespace(
            text="delete",
            reply_to_message=SimpleNamespace(reply_markup=reveal_keyboard(1)),
            chat=SimpleNamespace(id=CHAT_ID),
        )
        with patch.object(
            alternative_ux, "is_alternative_ux_enabled", AsyncMock(return_value=True)
        ) as enabled:
            assert await is_delete_reply(message) is True
            enabled.assert_awaited_once_with(CHAT_ID)

    @pytest.mark.asyncio
    async def test_case_insensitive_and_trims_whitespace(self):
        message = SimpleNamespace(
            text="  Delete ",
            reply_to_message=SimpleNamespace(reply_markup=reveal_keyboard(1)),
            chat=SimpleNamespace(id=CHAT_ID),
        )
        with patch.object(
            alternative_ux, "is_alternative_ux_enabled", AsyncMock(return_value=True)
        ):
            assert await is_delete_reply(message) is True

    @pytest.mark.asyncio
    async def test_disabled_chat_does_not_match(self):
        """A chat that never opted in falls through to the default handlers."""
        message = SimpleNamespace(
            text="delete",
            reply_to_message=SimpleNamespace(reply_markup=reveal_keyboard(1)),
            chat=SimpleNamespace(id=CHAT_ID),
        )
        with patch.object(
            alternative_ux, "is_alternative_ux_enabled", AsyncMock(return_value=False)
        ):
            assert await is_delete_reply(message) is False

    @pytest.mark.asyncio
    async def test_non_delete_text_skips_db_lookup(self):
        message = SimpleNamespace(
            text="cat, kat",
            reply_to_message=SimpleNamespace(reply_markup=reveal_keyboard(1)),
            chat=SimpleNamespace(id=CHAT_ID),
        )
        with patch.object(
            alternative_ux, "is_alternative_ux_enabled", AsyncMock()
        ) as enabled:
            assert await is_delete_reply(message) is False
            enabled.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_without_reply_skips_db_lookup(self):
        message = SimpleNamespace(
            text="delete",
            reply_to_message=None,
            chat=SimpleNamespace(id=CHAT_ID),
        )
        with patch.object(
            alternative_ux, "is_alternative_ux_enabled", AsyncMock()
        ) as enabled:
            assert await is_delete_reply(message) is False
            enabled.assert_not_awaited()


class TestToggleCommands:
    """/alternative_ux_on and /alternative_ux_off."""

    @pytest.mark.asyncio
    async def test_turn_on_sets_flag_and_chat_scoped_menu(self):
        message = _make_message()
        bot = AsyncMock()

        repo = MagicMock()
        repo.set_alternative_ux = AsyncMock()
        with patch.object(alternative_ux, "PracticeRepository", return_value=repo):
            await cmd_alternative_ux_on(message, bot)

        repo.set_alternative_ux.assert_awaited_once_with(CHAT_ID, True)

        bot.set_my_commands.assert_awaited_once()
        commands = bot.set_my_commands.call_args.args[0]
        assert commands is ALTERNATIVE_MENU_COMMANDS
        assert [c.command for c in commands] == [
            "add_next_batch",
            "practice",
            "alternative_ux_off",
        ]
        scope = bot.set_my_commands.call_args.kwargs["scope"]
        assert scope.chat_id == CHAT_ID
        message.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_turn_off_clears_flag_and_chat_scoped_menu(self):
        message = _make_message()
        bot = AsyncMock()

        repo = MagicMock()
        repo.set_alternative_ux = AsyncMock()
        with patch.object(alternative_ux, "PracticeRepository", return_value=repo):
            await cmd_alternative_ux_off(message, bot)

        repo.set_alternative_ux.assert_awaited_once_with(CHAT_ID, False)

        bot.delete_my_commands.assert_awaited_once()
        scope = bot.delete_my_commands.call_args.kwargs["scope"]
        assert scope.chat_id == CHAT_ID
        # The default (global) menu must not be touched.
        bot.set_my_commands.assert_not_called()
        message.answer.assert_awaited_once()


class TestHandleDeleteReply:
    """The delete-by-reply handler itself."""

    @pytest.mark.asyncio
    async def test_deletes_word_from_reply(self):
        message = _make_message()
        message.reply_to_message = SimpleNamespace(reply_markup=reveal_keyboard(55))

        repo = MagicMock()
        repo.get_practice_word = AsyncMock(return_value=MagicMock())
        service = MagicMock()
        service.mark_deleted = AsyncMock()

        with patch.object(
            alternative_ux, "PracticeRepository", return_value=repo
        ), patch.object(alternative_ux, "PracticeService", return_value=service):
            await handle_delete_reply(message)

        service.mark_deleted.assert_awaited_once_with(CHAT_ID, 55)
        assert "Deleted" in str(message.answer.call_args)

    @pytest.mark.asyncio
    async def test_word_not_found(self):
        message = _make_message()
        message.reply_to_message = SimpleNamespace(reply_markup=reveal_keyboard(55))

        repo = MagicMock()
        repo.get_practice_word = AsyncMock(return_value=None)
        service = MagicMock()
        service.mark_deleted = AsyncMock()

        with patch.object(
            alternative_ux, "PracticeRepository", return_value=repo
        ), patch.object(alternative_ux, "PracticeService", return_value=service):
            await handle_delete_reply(message)

        service.mark_deleted.assert_not_awaited()
        assert "not found" in str(message.answer.call_args).lower()

    @pytest.mark.asyncio
    async def test_reply_without_word_id(self):
        message = _make_message()
        # Replying to a message that carries no word id.
        message.reply_to_message = SimpleNamespace(reply_markup=practice_more_keyboard(3))

        repo = MagicMock()
        repo.get_practice_word = AsyncMock()
        service = MagicMock()
        service.mark_deleted = AsyncMock()

        with patch.object(
            alternative_ux, "PracticeRepository", return_value=repo
        ), patch.object(alternative_ux, "PracticeService", return_value=service):
            await handle_delete_reply(message)

        repo.get_practice_word.assert_not_awaited()
        service.mark_deleted.assert_not_awaited()
        message.answer.assert_awaited_once()
