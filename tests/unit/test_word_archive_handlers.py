"""Unit tests for the word-archive command handlers (no database required)."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from word_learn.handlers import word_archive
from word_learn.handlers.word_archive import (
    cmd_archive_words,
    cmd_unarchive_words,
    format_unarchive_reply,
)
from word_learn.services.word_archive import (
    ArchiveResult,
    RestoredGeneration,
    UnarchiveResult,
)

CHAT_ID = 12345
TZ = ZoneInfo("Europe/Amsterdam")


def _make_message():
    message = MagicMock()
    message.chat = MagicMock()
    message.chat.id = CHAT_ID
    message.answer = AsyncMock()
    return message


def _archive_result(archived=0, previously=0, today=0, current=0) -> ArchiveResult:
    return ArchiveResult(
        archived_cards=archived,
        previously_archived_cards=previously,
        today_practice_removed=today,
        current_practice_removed=current,
    )


def _patch_service(**methods):
    service = MagicMock()
    for name, return_value in methods.items():
        setattr(service, name, AsyncMock(return_value=return_value))
    return service, patch.object(word_archive, "WordArchiveService", return_value=service)


def _patch_pool_remaining(count: int):
    repo = MagicMock()
    repo.count_words_to_practice = AsyncMock(return_value=count)
    return patch.object(word_archive, "PracticeRepository", return_value=repo)


def _reply_text(message) -> str:
    return message.answer.call_args.args[0]


class TestArchiveWords:
    @pytest.mark.asyncio
    async def test_archives_and_explains_next_steps(self):
        message = _make_message()
        service, patched = _patch_service(archive_all=_archive_result(archived=800, today=40))
        with patched:
            await cmd_archive_words(message)

        service.archive_all.assert_awaited_once_with(CHAT_ID)
        text = _reply_text(message)
        assert text.startswith("Archived 800 cards.")
        assert "/add word1 word2" in text
        assert "/unarchive_words" in text
        assert "in total" not in text
        assert "session cleared" not in text

    @pytest.mark.asyncio
    async def test_mentions_cleared_session_when_one_was_running(self):
        message = _make_message()
        _, patched = _patch_service(archive_all=_archive_result(archived=800, current=3))
        with patched:
            await cmd_archive_words(message)

        assert "Current practice session cleared." in _reply_text(message)

    @pytest.mark.asyncio
    async def test_second_archive_reports_total(self):
        message = _make_message()
        _, patched = _patch_service(archive_all=_archive_result(archived=40, previously=800))
        with patched:
            await cmd_archive_words(message)

        assert _reply_text(message).startswith("Archived 40 cards (840 archived in total).")

    @pytest.mark.asyncio
    async def test_nothing_to_archive_and_no_archive(self):
        message = _make_message()
        _, patched = _patch_service(archive_all=_archive_result())
        with patched:
            await cmd_archive_words(message)

        assert _reply_text(message) == "No active cards to archive."

    @pytest.mark.asyncio
    async def test_nothing_to_archive_but_archive_exists_points_to_unarchive(self):
        message = _make_message()
        _, patched = _patch_service(archive_all=_archive_result(previously=800))
        with patched:
            await cmd_archive_words(message)

        text = _reply_text(message)
        assert text.startswith("No active cards to archive.")
        assert "800 cards are archived" in text
        assert "/unarchive_words" in text


def _generation(cards: int, day: int, shifted: int = 0) -> RestoredGeneration:
    return RestoredGeneration(
        archived_at=datetime(2026, 6, day, 10, 0, tzinfo=TZ),
        cards=cards,
        shifted_days=shifted,
    )


class TestUnarchiveWords:
    @pytest.mark.asyncio
    async def test_restores_newest_generation_by_default(self):
        message = _make_message()
        command = SimpleNamespace(args=None)
        result = UnarchiveResult(
            generations=[_generation(800, 1, shifted=21)],
            active_cards=840,
        )
        service, patched = _patch_service(unarchive=result)
        with patched, _patch_pool_remaining(0):
            await cmd_unarchive_words(message, command)

        service.unarchive.assert_awaited_once_with(CHAT_ID, everything=False)
        text = _reply_text(message)
        assert "Restored 800 cards archived on 01 Jun" in text
        assert "moved forward 21 days" in text
        assert "Active cards: 840." in text
        assert "remain archived" not in text
        assert "come first" not in text
        assert text.endswith("Send /practice to continue.")

    @pytest.mark.asyncio
    async def test_all_argument_restores_everything(self):
        message = _make_message()
        command = SimpleNamespace(args=" ALL ")
        result = UnarchiveResult(
            generations=[_generation(40, 11, shifted=10), _generation(800, 1, shifted=20)],
            active_cards=840,
        )
        service, patched = _patch_service(unarchive=result)
        with patched, _patch_pool_remaining(0):
            await cmd_unarchive_words(message, command)

        service.unarchive.assert_awaited_once_with(CHAT_ID, everything=True)
        assert "Restored 840 cards from 2 archives. Active cards: 840." in _reply_text(message)

    @pytest.mark.asyncio
    async def test_points_to_older_archives_and_todays_pool(self):
        message = _make_message()
        command = SimpleNamespace(args=None)
        result = UnarchiveResult(
            generations=[_generation(40, 11)],
            active_cards=55,
            remaining_archived_cards=800,
            remaining_generations=1,
        )
        _, patched = _patch_service(unarchive=result)
        with patched, _patch_pool_remaining(12):
            await cmd_unarchive_words(message, command)

        text = _reply_text(message)
        assert "Restored 40 cards archived on 11 Jun. Active cards: 55." in text
        assert "moved forward" not in text
        assert "800 older cards remain archived" in text
        assert "/unarchive_words all" in text
        assert "12 cards from today's list come first" in text

    @pytest.mark.asyncio
    async def test_nothing_to_restore(self):
        message = _make_message()
        command = SimpleNamespace(args=None)
        _, patched = _patch_service(unarchive=UnarchiveResult(active_cards=15))
        with patched, _patch_pool_remaining(3):
            await cmd_unarchive_words(message, command)

        assert _reply_text(message) == "No archived cards to restore."


class TestFormatUnarchiveReply:
    def test_one_day_shift_is_singular(self):
        result = UnarchiveResult(generations=[_generation(3, 5, shifted=1)], active_cards=3)

        text = format_unarchive_reply(result, pool_remaining=0)

        assert "(review dates moved forward 1 day)" in text

    def test_single_generation_without_shift(self):
        result = UnarchiveResult(generations=[_generation(3, 5)], active_cards=3)

        text = format_unarchive_reply(result, pool_remaining=0)

        assert text == (
            "Restored 3 cards archived on 05 Jun. Active cards: 3.\n"
            "Send /practice to continue."
        )
