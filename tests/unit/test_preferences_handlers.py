"""Unit tests for the per-chat preference toggles (no database required)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.handlers import preferences
from word_learn.handlers.preferences import (
    cmd_daily_limit_off,
    cmd_daily_limit_on,
    cmd_reverse_cards_off,
    cmd_reverse_cards_on,
)
from word_learn.handlers.start import BASE_WELCOME_MESSAGE

CHAT_ID = 12345


def _make_message():
    message = MagicMock()
    message.chat = MagicMock()
    message.chat.id = CHAT_ID
    message.answer = AsyncMock()
    return message


def _settings(pool_min: int = 67, pool_max: int = 76):
    settings = MagicMock()
    settings.daily_pool_min = pool_min
    settings.daily_pool_max = pool_max
    return settings


class TestReverseCardsCommands:
    """/reverse_cards_on and /reverse_cards_off."""

    @pytest.mark.asyncio
    async def test_on_sets_flag_true(self):
        message = _make_message()
        repo = MagicMock()
        repo.set_reverse_cards = AsyncMock()

        with patch.object(preferences, "PracticeRepository", return_value=repo):
            await cmd_reverse_cards_on(message)

        repo.set_reverse_cards.assert_awaited_once_with(CHAT_ID, True)
        text = message.answer.call_args.args[0]
        assert "enabled" in text
        assert "/reverse_cards_off" in text

    @pytest.mark.asyncio
    async def test_off_sets_flag_false(self):
        message = _make_message()
        repo = MagicMock()
        repo.set_reverse_cards = AsyncMock()

        with patch.object(preferences, "PracticeRepository", return_value=repo):
            await cmd_reverse_cards_off(message)

        repo.set_reverse_cards.assert_awaited_once_with(CHAT_ID, False)
        text = message.answer.call_args.args[0]
        assert "disabled" in text
        assert "/reverse_cards_on" in text

    @pytest.mark.asyncio
    async def test_reverse_commands_do_not_touch_other_settings(self):
        """Only the reverse-cards column is written, nothing else."""
        message = _make_message()
        repo = MagicMock()
        repo.set_reverse_cards = AsyncMock()
        repo.set_daily_limit = AsyncMock()
        repo.set_alternative_ux = AsyncMock()

        with patch.object(preferences, "PracticeRepository", return_value=repo):
            await cmd_reverse_cards_off(message)
            await cmd_reverse_cards_on(message)

        repo.set_daily_limit.assert_not_awaited()
        repo.set_alternative_ux.assert_not_awaited()


class TestDailyLimitCommands:
    """/daily_limit_on and /daily_limit_off."""

    def _patches(self, repo, service):
        return (
            patch.object(preferences, "PracticeRepository", return_value=repo),
            patch.object(preferences, "PracticeService", return_value=service),
            patch.object(preferences, "get_settings", return_value=_settings()),
        )

    @pytest.mark.asyncio
    async def test_off_sets_flag_then_fills_today_pool(self):
        message = _make_message()
        calls: list[str] = []

        repo = MagicMock()
        repo.set_daily_limit = AsyncMock(side_effect=lambda *a: calls.append("flag"))
        service = MagicMock()
        service.fill_today_pool = AsyncMock(
            side_effect=lambda *a: (calls.append("fill"), 312)[1]
        )

        repo_patch, service_patch, settings_patch = self._patches(repo, service)
        with repo_patch, service_patch, settings_patch:
            await cmd_daily_limit_off(message)

        repo.set_daily_limit.assert_awaited_once_with(CHAT_ID, False)
        service.fill_today_pool.assert_awaited_once_with(CHAT_ID)
        # The flag is persisted before the pool is filled.
        assert calls == ["flag", "fill"]

        text = message.answer.call_args.args[0]
        assert "disabled" in text
        assert "Today's list: 312 words." in text
        assert "67-76" in text
        assert "/daily_limit_on" in text

    @pytest.mark.asyncio
    async def test_on_sets_flag_then_trims_today_pool(self):
        message = _make_message()
        calls: list[str] = []

        repo = MagicMock()
        repo.get_daily_limit = AsyncMock(return_value=False)  # limit was off
        repo.set_daily_limit = AsyncMock(side_effect=lambda *a: calls.append("flag"))
        service = MagicMock()
        service.trim_today_pool = AsyncMock(
            side_effect=lambda *a: (calls.append("trim"), (240, 72))[1]
        )

        repo_patch, service_patch, settings_patch = self._patches(repo, service)
        with repo_patch, service_patch, settings_patch:
            await cmd_daily_limit_on(message)

        repo.set_daily_limit.assert_awaited_once_with(CHAT_ID, True)
        service.trim_today_pool.assert_awaited_once_with(CHAT_ID)
        assert calls == ["flag", "trim"]

        text = message.answer.call_args.args[0]
        assert "enabled" in text
        assert "67-76" in text
        assert "trimmed to 72 words" in text
        assert "other 240" in text
        assert "/daily_limit_off" in text

    @pytest.mark.asyncio
    async def test_on_without_trimming_does_not_mention_a_trim(self):
        message = _make_message()
        repo = MagicMock()
        repo.get_daily_limit = AsyncMock(return_value=False)
        repo.set_daily_limit = AsyncMock()
        service = MagicMock()
        service.trim_today_pool = AsyncMock(return_value=(0, 12))

        repo_patch, service_patch, settings_patch = self._patches(repo, service)
        with repo_patch, service_patch, settings_patch:
            await cmd_daily_limit_on(message)

        text = message.answer.call_args.args[0]
        assert "enabled" in text
        assert "trimmed" not in text

    @pytest.mark.asyncio
    async def test_on_when_already_on_never_touches_the_pool(self):
        """Re-sending the default setting is a no-op for today's list."""
        message = _make_message()
        repo = MagicMock()
        repo.get_daily_limit = AsyncMock(return_value=True)  # already on
        repo.set_daily_limit = AsyncMock()
        service = MagicMock()
        service.trim_today_pool = AsyncMock()

        repo_patch, service_patch, settings_patch = self._patches(repo, service)
        with repo_patch, service_patch, settings_patch:
            await cmd_daily_limit_on(message)

        service.trim_today_pool.assert_not_awaited()
        repo.set_daily_limit.assert_awaited_once_with(CHAT_ID, True)
        text = message.answer.call_args.args[0]
        assert "already on" in text
        assert "67-76" in text
        assert "/daily_limit_off" in text

    @pytest.mark.asyncio
    async def test_range_follows_settings(self):
        message = _make_message()
        repo = MagicMock()
        repo.set_daily_limit = AsyncMock()
        service = MagicMock()
        service.fill_today_pool = AsyncMock(return_value=5)

        with patch.object(
            preferences, "PracticeRepository", return_value=repo
        ), patch.object(
            preferences, "PracticeService", return_value=service
        ), patch.object(
            preferences, "get_settings", return_value=_settings(20, 30)
        ):
            await cmd_daily_limit_off(message)

        assert "20-30" in message.answer.call_args.args[0]


class TestStartMessageListsToggles:
    """The /start command list advertises the four new commands."""

    def test_all_four_commands_listed(self):
        for command in (
            "/reverse_cards_on",
            "/reverse_cards_off",
            "/daily_limit_on",
            "/daily_limit_off",
        ):
            assert command in BASE_WELCOME_MESSAGE

    def test_existing_commands_still_listed(self):
        for command in ("/start", "/add", "/practice", "/archive_words", "/unarchive_words"):
            assert command in BASE_WELCOME_MESSAGE
