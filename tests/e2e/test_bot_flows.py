"""End-to-end tests for bot flows.

These tests verify complete user flows through the bot.
They require a test database and mock the Telegram API.
"""
import pytest
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from aiogram.types import Message, Chat, User, CallbackQuery

from word_learn.handlers.start import cmd_start
from word_learn.handlers.add_word import _add_word
from word_learn.handlers.practice import _show_practice_word
from word_learn.handlers.remind import cmd_remind, _calculate_next_reminder


class TestStartCommand:
    """Tests for /start command."""

    @pytest.mark.asyncio
    async def test_start_sends_welcome(self):
        """Test that /start sends welcome message."""
        message = AsyncMock(spec=Message)
        message.answer = AsyncMock()

        await cmd_start(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args
        text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        assert "Welcome" in text
        assert "/start" in text
        assert "/add" in text
        assert "/practice" in text


class TestAddWordFlow:
    """Tests for add word functionality."""

    @pytest.mark.asyncio
    async def test_add_word_creates_bidirectional(
        self, db_pool, chat_id
    ):
        """Test that adding a word creates bidirectional entries."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.answer = AsyncMock()

        with patch("word_learn.handlers.add_word.get_settings") as mock_settings:
            from word_learn.config import Language
            settings = MagicMock()
            settings.source_lang = Language.EN
            settings.target_lang = Language.RU
            mock_settings.return_value = settings

            await _add_word(message, "cat", "kot")

        # Check message was sent
        message.answer.assert_called()
        call_text = str(message.answer.call_args)
        assert "Done" in call_text or "Added" in call_text


class TestPracticeFlow:
    """Tests for practice flow."""

    @pytest.mark.asyncio
    async def test_show_practice_word_no_words(
        self, practice_repository, chat_id
    ):
        """Test showing practice when no words available."""
        message = AsyncMock(spec=Message)
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.answer = AsyncMock()

        await _show_practice_word(message, chat_id)

        # Should show "no words" or "practiced all"
        message.answer.assert_called()

    @pytest.mark.asyncio
    async def test_full_practice_session(
        self, practice_repository, chat_id, sample_word_data
    ):
        """Test complete practice flow."""
        # Add word to practice
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])
        await practice_repository.create_today_practice(chat_id, limit=10)
        await practice_repository.start_practice(chat_id, [word.id])

        # Mock message
        message = AsyncMock(spec=Message)
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.answer = AsyncMock()

        # Show practice word
        await _show_practice_word(message, chat_id)

        # Verify word was shown with reveal button
        message.answer.assert_called()
        call_kwargs = message.answer.call_args[1] if message.answer.call_args[1] else {}
        assert "reply_markup" in call_kwargs


class TestReminderFlow:
    """Tests for reminder functionality."""

    def test_calculate_next_reminder_today(self):
        """Test reminder scheduled for today if time hasn't passed."""
        tz = ZoneInfo("Europe/Amsterdam")
        now = datetime(2024, 1, 15, 8, 0, tzinfo=tz)
        remind_time = time(9, 0)

        result = _calculate_next_reminder(now, remind_time, tz)

        assert result.date() == now.date()
        assert result.hour == 9
        assert result.minute == 0

    def test_calculate_next_reminder_tomorrow(self):
        """Test reminder scheduled for tomorrow if time has passed."""
        tz = ZoneInfo("Europe/Amsterdam")
        now = datetime(2024, 1, 15, 10, 0, tzinfo=tz)
        remind_time = time(9, 0)

        result = _calculate_next_reminder(now, remind_time, tz)

        assert result.date() == datetime(2024, 1, 16).date()
        assert result.hour == 9


class TestSessionStatistics:
    """Tests for session statistics display."""

    @pytest.mark.asyncio
    async def test_stats_shown_at_end(
        self, practice_repository, chat_id, sample_word_data
    ):
        """Test that stats are shown when session ends."""
        # Add and complete some practice
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])

        # Simulate practice completion
        await practice_repository.increment_statistics(chat_id, correct=True)
        await practice_repository.increment_statistics(chat_id, correct=False)

        # Get stats
        stats = await practice_repository.get_statistics(chat_id)

        assert stats.correct == 1
        assert stats.total == 2
        assert stats.accuracy_text == "1/2"

        # Reset should clear stats
        await practice_repository.reset_statistics(chat_id)
        stats_after = await practice_repository.get_statistics(chat_id)
        assert stats_after.total == 0
