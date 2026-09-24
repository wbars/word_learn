"""Integration tests for repositories."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from word_learn.models import Word, PracticeWord, PracticeStats


class TestWordsRepository:
    """Tests for WordsRepository."""

    @pytest.mark.asyncio
    async def test_add_word_returns_word(self, words_repository, sample_word_data):
        """Test that add_word creates and returns a Word."""
        word = await words_repository.add_word(sample_word_data)

        assert word.id is not None
        assert word.en == "cat"
        assert word.nl == "kat"
        assert word.ru == "кот"

    @pytest.mark.asyncio
    async def test_add_word_with_partial_translations(self, words_repository):
        """Test adding word with only some translations."""
        word = await words_repository.add_word({"en": "hello", "ru": "привет"})

        assert word.id is not None
        assert word.en == "hello"
        assert word.ru == "привет"
        assert word.nl is None

    @pytest.mark.asyncio
    async def test_get_word_by_id(self, words_repository, sample_word_data):
        """Test retrieving word by ID."""
        created = await words_repository.add_word(sample_word_data)
        fetched = await words_repository.get_word_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.en == "cat"

    @pytest.mark.asyncio
    async def test_get_word_by_id_not_found(self, words_repository):
        """Test retrieving non-existent word returns None."""
        result = await words_repository.get_word_by_id(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_words_to_add_excludes_practiced(
        self, words_repository, practice_repository, chat_id, sample_word_data
    ):
        """Test that practiced words are excluded from add suggestions."""
        # Create word and add to practice
        word = await words_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])

        # Should not appear in words to add
        words_to_add = await words_repository.get_words_to_add(chat_id)
        word_ids = [w.id for w in words_to_add]
        assert word.id not in word_ids

    @pytest.mark.asyncio
    async def test_get_words_to_add_excludes_skipped(
        self, words_repository, chat_id, sample_word_data
    ):
        """Test that skipped words are excluded from add suggestions."""
        word = await words_repository.add_word(sample_word_data)
        await words_repository.add_to_skiplist(chat_id, [word.id])

        words_to_add = await words_repository.get_words_to_add(chat_id)
        word_ids = [w.id for w in words_to_add]
        assert word.id not in word_ids


class TestPracticeRepository:
    """Tests for PracticeRepository."""

    @pytest.mark.asyncio
    async def test_add_to_practice_creates_entry(
        self, practice_repository, sample_word_data, chat_id
    ):
        """Test adding word to practice."""
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])

        practice_word = await practice_repository.get_practice_word(chat_id, word.id)
        assert practice_word is not None
        assert practice_word.word.id == word.id
        assert practice_word.stage == 0
        assert practice_word.deleted is False

    @pytest.mark.asyncio
    async def test_update_practice_word(
        self, practice_repository, sample_word_data, chat_id
    ):
        """Test updating practice word stage and next_date."""
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])

        new_date = datetime.now(ZoneInfo("Europe/Amsterdam")) + timedelta(days=5)
        await practice_repository.update_practice_word(chat_id, word.id, stage=5, next_date=new_date)

        updated = await practice_repository.get_practice_word(chat_id, word.id)
        assert updated.stage == 5

    @pytest.mark.asyncio
    async def test_mark_deleted_hides_word(
        self, practice_repository, sample_word_data, chat_id
    ):
        """Test that marking deleted hides word from queries."""
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])

        await practice_repository.mark_deleted(chat_id, word.id)

        # Should not be retrievable
        result = await practice_repository.get_practice_word(chat_id, word.id)
        assert result is None


class TestTodayPractice:
    """Tests for daily practice pool."""

    @pytest.mark.asyncio
    async def test_create_today_practice(
        self, practice_repository, chat_id
    ):
        """Test creating daily practice pool."""
        # Add multiple words to practice
        for i in range(10):
            word = await practice_repository.add_word({"en": f"word{i}"})
            await practice_repository.add_to_practice(chat_id, [word.id])

        # Create today's pool with limit
        pool = await practice_repository.create_today_practice(chat_id, limit=5)

        assert len(pool) == 5

    @pytest.mark.asyncio
    async def test_get_today_practice_returns_pool(
        self, practice_repository, chat_id
    ):
        """Test retrieving today's practice pool."""
        word = await practice_repository.add_word({"en": "test"})
        await practice_repository.add_to_practice(chat_id, [word.id])
        await practice_repository.create_today_practice(chat_id, limit=10)

        pool = await practice_repository.get_today_practice(chat_id)
        assert len(pool) >= 1


class TestCurrentPractice:
    """Tests for current practice session."""

    @pytest.mark.asyncio
    async def test_start_practice_adds_words(
        self, practice_repository, sample_word_data, chat_id
    ):
        """Test starting practice session."""
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])
        await practice_repository.create_today_practice(chat_id, limit=10)

        await practice_repository.start_practice(chat_id, [word.id])

        next_word = await practice_repository.get_next_practice_word(chat_id)
        assert next_word is not None
        assert next_word.word.id == word.id

    @pytest.mark.asyncio
    async def test_remove_from_current_practice(
        self, practice_repository, sample_word_data, chat_id
    ):
        """Test removing word from current practice."""
        word = await practice_repository.add_word(sample_word_data)
        await practice_repository.add_to_practice(chat_id, [word.id])
        await practice_repository.start_practice(chat_id, [word.id])

        await practice_repository.remove_from_current_practice(chat_id, word.id)

        next_word = await practice_repository.get_next_practice_word(chat_id)
        assert next_word is None

    @pytest.mark.asyncio
    async def test_clear_current_practice(
        self, practice_repository, sample_word_data, sample_word_data_2, chat_id
    ):
        """Test clearing all current practice."""
        word1 = await practice_repository.add_word(sample_word_data)
        word2 = await practice_repository.add_word(sample_word_data_2)
        await practice_repository.start_practice(chat_id, [word1.id, word2.id])

        await practice_repository.clear_current_practice(chat_id)

        next_word = await practice_repository.get_next_practice_word(chat_id)
        assert next_word is None


class TestStatistics:
    """Tests for practice statistics."""

    @pytest.mark.asyncio
    async def test_increment_statistics_correct(self, practice_repository, chat_id):
        """Test incrementing correct count."""
        await practice_repository.increment_statistics(chat_id, correct=True)

        stats = await practice_repository.get_statistics(chat_id)
        assert stats.correct == 1
        assert stats.total == 1

    @pytest.mark.asyncio
    async def test_increment_statistics_incorrect(self, practice_repository, chat_id):
        """Test incrementing only total for incorrect."""
        await practice_repository.increment_statistics(chat_id, correct=False)

        stats = await practice_repository.get_statistics(chat_id)
        assert stats.correct == 0
        assert stats.total == 1

    @pytest.mark.asyncio
    async def test_increment_statistics_multiple(self, practice_repository, chat_id):
        """Test multiple increments."""
        await practice_repository.increment_statistics(chat_id, correct=True)
        await practice_repository.increment_statistics(chat_id, correct=True)
        await practice_repository.increment_statistics(chat_id, correct=False)

        stats = await practice_repository.get_statistics(chat_id)
        assert stats.correct == 2
        assert stats.total == 3

    @pytest.mark.asyncio
    async def test_reset_statistics(self, practice_repository, chat_id):
        """Test resetting statistics."""
        await practice_repository.increment_statistics(chat_id, correct=True)
        await practice_repository.reset_statistics(chat_id)

        stats = await practice_repository.get_statistics(chat_id)
        assert stats.correct == 0
        assert stats.total == 0


class TestReminders:
    """Tests for reminder functionality."""

    @pytest.mark.asyncio
    async def test_set_reminder(self, practice_repository, chat_id):
        """Test setting a reminder."""
        remind_time = time(9, 0)
        next_remind = datetime.now(ZoneInfo("Europe/Amsterdam")) + timedelta(hours=1)

        await practice_repository.set_reminder(chat_id, remind_time, next_remind)

        reminder = await practice_repository.get_reminder(chat_id)
        assert reminder is not None
        assert reminder.remind_time == remind_time

    @pytest.mark.asyncio
    async def test_get_reminder_not_set(self, practice_repository, chat_id):
        """Test getting reminder when not set."""
        reminder = await practice_repository.get_reminder(chat_id)
        assert reminder is None

    @pytest.mark.asyncio
    async def test_update_reminder(self, practice_repository, chat_id):
        """Test updating existing reminder."""
        await practice_repository.set_reminder(
            chat_id, time(9, 0), datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        await practice_repository.set_reminder(
            chat_id, time(10, 0), datetime.now(ZoneInfo("Europe/Amsterdam"))
        )

        reminder = await practice_repository.get_reminder(chat_id)
        assert reminder.remind_time == time(10, 0)


class TestAlternativeUxSetting:
    """Tests for the per-chat alternative UX flag."""

    @pytest.mark.asyncio
    async def test_defaults_to_false(self, practice_repository, chat_id):
        """A chat that never opted in must read as disabled."""
        assert await practice_repository.get_alternative_ux(chat_id) is False

    @pytest.mark.asyncio
    async def test_enable_and_disable(self, practice_repository, chat_id):
        """Toggling persists and is idempotent via upsert."""
        await practice_repository.set_alternative_ux(chat_id, True)
        assert await practice_repository.get_alternative_ux(chat_id) is True

        await practice_repository.set_alternative_ux(chat_id, False)
        assert await practice_repository.get_alternative_ux(chat_id) is False

    @pytest.mark.asyncio
    async def test_setting_is_per_chat(self, practice_repository, chat_id):
        """One chat opting in does not affect another chat."""
        other_chat_id = chat_id + 1
        await practice_repository.set_alternative_ux(chat_id, True)

        assert await practice_repository.get_alternative_ux(chat_id) is True
        assert await practice_repository.get_alternative_ux(other_chat_id) is False


class TestBatchCustomWords:
    """PracticeService.add_custom_words against the database."""

    @pytest.mark.asyncio
    async def test_adds_two_cards_per_pair_and_skips_active_duplicates(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        pairs = [("de zorg", "уход (healthcare)"), ("de premie", "взнос (premium)")]

        added, skipped = await service.add_custom_words(chat_id, pairs)
        assert (added, skipped) == (2, 0)
        assert await practice_repository.count_all_due_words(chat_id) == 4

        # Same list again (plus an in-message duplicate): nothing new is created.
        added, skipped = await service.add_custom_words(chat_id, pairs + [pairs[0]])
        assert (added, skipped) == (0, 3)
        assert await practice_repository.count_all_due_words(chat_id) == 4

    @pytest.mark.asyncio
    async def test_archived_or_deleted_cards_do_not_count_as_duplicates(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService
        from word_learn.services.word_archive import WordArchiveService

        service = PracticeService(practice_repository)
        await service.add_custom_words(chat_id, [("de zorg", "уход")])
        await WordArchiveService().archive_all(chat_id)

        added, skipped = await service.add_custom_words(chat_id, [("de zorg", "уход")])

        assert (added, skipped) == (1, 0)
        assert await practice_repository.count_all_due_words(chat_id) == 2


class TestReverseCardsSetting:
    """Per-chat reverse-cards flag (on by default)."""

    @pytest.mark.asyncio
    async def test_defaults_to_true(self, practice_repository, chat_id):
        assert await practice_repository.get_reverse_cards(chat_id) is True

    @pytest.mark.asyncio
    async def test_disable_and_enable(self, practice_repository, chat_id):
        await practice_repository.set_reverse_cards(chat_id, False)
        assert await practice_repository.get_reverse_cards(chat_id) is False

        await practice_repository.set_reverse_cards(chat_id, True)
        assert await practice_repository.get_reverse_cards(chat_id) is True

    @pytest.mark.asyncio
    async def test_setting_is_per_chat(self, practice_repository, chat_id):
        await practice_repository.set_reverse_cards(chat_id, False)

        assert await practice_repository.get_reverse_cards(chat_id) is False
        assert await practice_repository.get_reverse_cards(chat_id + 1) is True

    @pytest.mark.asyncio
    async def test_toggles_are_independent(self, practice_repository, chat_id):
        """Writing one flag leaves the others at their current/default values."""
        await practice_repository.set_alternative_ux(chat_id, True)
        await practice_repository.set_reverse_cards(chat_id, False)

        assert await practice_repository.get_alternative_ux(chat_id) is True
        assert await practice_repository.get_reverse_cards(chat_id) is False
        assert await practice_repository.get_daily_limit(chat_id) is True

        await practice_repository.set_daily_limit(chat_id, False)
        assert await practice_repository.get_alternative_ux(chat_id) is True
        assert await practice_repository.get_reverse_cards(chat_id) is False
        assert await practice_repository.get_daily_limit(chat_id) is False

        await practice_repository.set_alternative_ux(chat_id, False)
        assert await practice_repository.get_reverse_cards(chat_id) is False
        assert await practice_repository.get_daily_limit(chat_id) is False

    @pytest.mark.asyncio
    async def test_row_created_by_another_flag_keeps_defaults(self, practice_repository, chat_id):
        """A row created by /alternative_ux_on must not flip the defaults of the new flags."""
        await practice_repository.set_alternative_ux(chat_id, True)

        assert await practice_repository.get_reverse_cards(chat_id) is True
        assert await practice_repository.get_daily_limit(chat_id) is True

    @pytest.mark.asyncio
    async def test_unknown_column_is_rejected(self, practice_repository, chat_id):
        with pytest.raises(ValueError):
            await practice_repository._get_user_flag(chat_id, "chat_id; DROP TABLE x", True)
        with pytest.raises(ValueError):
            await practice_repository._set_user_flag(chat_id, "nope", True)


class TestDailyLimitSetting:
    """Per-chat daily-limit flag (on by default)."""

    @pytest.mark.asyncio
    async def test_defaults_to_true(self, practice_repository, chat_id):
        assert await practice_repository.get_daily_limit(chat_id) is True

    @pytest.mark.asyncio
    async def test_disable_and_enable(self, practice_repository, chat_id):
        await practice_repository.set_daily_limit(chat_id, False)
        assert await practice_repository.get_daily_limit(chat_id) is False

        await practice_repository.set_daily_limit(chat_id, True)
        assert await practice_repository.get_daily_limit(chat_id) is True

    @pytest.mark.asyncio
    async def test_setting_is_per_chat(self, practice_repository, chat_id):
        await practice_repository.set_daily_limit(chat_id, False)

        assert await practice_repository.get_daily_limit(chat_id) is False
        assert await practice_repository.get_daily_limit(chat_id + 1) is True


async def _add_due_cards(practice_repository, chat_id: int, count: int) -> list[int]:
    """Create ``count`` due cards for the chat; return their word ids."""
    word_ids = []
    for i in range(count):
        word = await practice_repository.add_word({"en": f"due{i}", "ru": f"r{i}"})
        await practice_repository.add_to_practice(chat_id, [word.id])
        word_ids.append(word.id)
    return word_ids


class TestTodayPracticeWithoutLimit:
    """create_today_practice(limit=None) and trim_today_practice."""

    @pytest.mark.asyncio
    async def test_no_limit_takes_every_due_card(self, practice_repository, chat_id):
        await _add_due_cards(practice_repository, chat_id, 100)

        pool = await practice_repository.create_today_practice(chat_id, limit=None)

        assert len(pool) == 100
        assert await practice_repository.count_words_to_practice(chat_id) == 100

    @pytest.mark.asyncio
    async def test_no_limit_skips_deleted_archived_and_other_chats(
        self, practice_repository, chat_id
    ):
        from word_learn.services.word_archive import WordArchiveService

        other_chat = chat_id + 1
        await _add_due_cards(practice_repository, other_chat, 3)
        await WordArchiveService().archive_all(other_chat)  # archived, other chat
        await _add_due_cards(practice_repository, other_chat, 2)  # active, other chat

        word_ids = await _add_due_cards(practice_repository, chat_id, 5)
        await practice_repository.mark_deleted(chat_id, word_ids[0])

        pool = await practice_repository.create_today_practice(chat_id, limit=None)

        assert len(pool) == 4
        assert await practice_repository.count_words_to_practice(chat_id) == 4
        assert await practice_repository.count_words_to_practice(other_chat) == 0

    @pytest.mark.asyncio
    async def test_no_limit_tops_up_an_existing_pool_without_duplicates(
        self, practice_repository, chat_id
    ):
        await _add_due_cards(practice_repository, chat_id, 30)
        first = await practice_repository.create_today_practice(chat_id, limit=10)
        assert len(first) == 10

        await practice_repository.create_today_practice(chat_id, limit=None)

        assert await practice_repository.count_words_to_practice(chat_id) == 30
        assert set(first) <= set(await practice_repository.get_today_practice(chat_id))

    @pytest.mark.asyncio
    async def test_explicit_limit_still_caps(self, practice_repository, chat_id):
        await _add_due_cards(practice_repository, chat_id, 100)

        pool = await practice_repository.create_today_practice(chat_id, limit=7)

        assert len(pool) == 7

    @pytest.mark.asyncio
    async def test_trim_keeps_session_words_and_limit(self, practice_repository, chat_id):
        word_ids = await _add_due_cards(practice_repository, chat_id, 40)
        await practice_repository.create_today_practice(chat_id, limit=None)
        in_session = word_ids[:5]
        await practice_repository.start_practice(chat_id, in_session)

        removed = await practice_repository.trim_today_practice(chat_id, limit=12)

        assert removed == 28
        assert await practice_repository.count_words_to_practice(chat_id) == 12
        remaining_pool = set(await practice_repository.get_today_practice(chat_id))
        for word_id in in_session:
            pw = await practice_repository.get_practice_word(chat_id, word_id)
            assert pw.id in remaining_pool

    @pytest.mark.asyncio
    async def test_trim_is_a_noop_within_the_limit(self, practice_repository, chat_id):
        await _add_due_cards(practice_repository, chat_id, 8)
        await practice_repository.create_today_practice(chat_id, limit=None)

        removed = await practice_repository.trim_today_practice(chat_id, limit=10)

        assert removed == 0
        assert await practice_repository.count_words_to_practice(chat_id) == 8

    @pytest.mark.asyncio
    async def test_trim_touches_only_this_chat(self, practice_repository, chat_id):
        other_chat = chat_id + 1
        await _add_due_cards(practice_repository, other_chat, 20)
        await practice_repository.create_today_practice(other_chat, limit=None)
        await _add_due_cards(practice_repository, chat_id, 20)
        await practice_repository.create_today_practice(chat_id, limit=None)

        removed = await practice_repository.trim_today_practice(chat_id, limit=5)

        assert removed == 15
        assert await practice_repository.count_words_to_practice(chat_id) == 5
        assert await practice_repository.count_words_to_practice(other_chat) == 20

    @pytest.mark.asyncio
    async def test_trimmed_cards_stay_due(self, practice_repository, chat_id):
        await _add_due_cards(practice_repository, chat_id, 20)
        await practice_repository.create_today_practice(chat_id, limit=None)

        await practice_repository.trim_today_practice(chat_id, limit=5)

        assert await practice_repository.count_all_due_words(chat_id) == 20
        # ... and come back when the pool is topped up again.
        await practice_repository.create_today_practice(chat_id, limit=None)
        assert await practice_repository.count_words_to_practice(chat_id) == 20


class TestPracticeServiceToggles:
    """PracticeService honouring the toggles against the database."""

    @pytest.mark.asyncio
    async def test_add_custom_word_reverse_off_creates_one_card(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await practice_repository.set_reverse_cards(chat_id, False)

        word1, word2 = await service.add_custom_word(chat_id, "cat", "kot")

        assert word2 is None
        assert await practice_repository.count_all_due_words(chat_id) == 1
        assert await practice_repository.get_practice_word(chat_id, word1.id) is not None

    @pytest.mark.asyncio
    async def test_add_custom_word_default_still_creates_two_cards(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)

        word1, word2 = await service.add_custom_word(chat_id, "cat", "kot")

        assert word2 is not None
        assert await practice_repository.count_all_due_words(chat_id) == 2

    @pytest.mark.asyncio
    async def test_add_custom_words_reverse_off_creates_one_card_per_pair(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await practice_repository.set_reverse_cards(chat_id, False)
        pairs = [("de zorg", "уход"), ("de premie", "взнос")]

        added, skipped = await service.add_custom_words(chat_id, pairs)
        assert (added, skipped) == (2, 0)
        assert await practice_repository.count_all_due_words(chat_id) == 2

        # Duplicate detection still works on the forward card.
        added, skipped = await service.add_custom_words(chat_id, pairs)
        assert (added, skipped) == (0, 2)
        assert await practice_repository.count_all_due_words(chat_id) == 2

    @pytest.mark.asyncio
    async def test_daily_pool_limit_off_takes_all_due_words(self, practice_repository, chat_id):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await _add_due_cards(practice_repository, chat_id, 100)
        await practice_repository.set_daily_limit(chat_id, False)

        pool = await service.create_daily_pool(chat_id)

        assert len(pool) == 100
        assert await practice_repository.count_words_to_practice(chat_id) == 100

    @pytest.mark.asyncio
    async def test_daily_pool_limit_on_is_capped(self, practice_repository, chat_id):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await _add_due_cards(practice_repository, chat_id, 100)

        pool = await service.create_daily_pool(chat_id)

        assert 67 <= len(pool) <= 76

    @pytest.mark.asyncio
    async def test_fill_then_trim_round_trip(self, practice_repository, chat_id):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await _add_due_cards(practice_repository, chat_id, 120)
        await practice_repository.create_today_practice(chat_id, limit=10)

        assert await service.fill_today_pool(chat_id) == 120

        removed, remaining = await service.trim_today_pool(chat_id)
        assert 67 <= remaining <= 76
        assert removed == 120 - remaining
        assert await practice_repository.count_words_to_practice(chat_id) == remaining

    @pytest.mark.asyncio
    async def test_trim_never_touches_a_pool_built_with_the_limit_on(
        self, practice_repository, chat_id
    ):
        """Re-sending /daily_limit_on must not re-roll a 67-76 pool to a smaller one."""
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await _add_due_cards(practice_repository, chat_id, 200)
        pool = await service.create_daily_pool(chat_id)  # limit on by default
        before = await practice_repository.count_words_to_practice(chat_id)
        assert 67 <= before <= 76

        for _ in range(10):
            removed, remaining = await service.trim_today_pool(chat_id)
            assert (removed, remaining) == (0, before)

        assert set(await practice_repository.get_today_practice(chat_id)) == set(pool)

    @pytest.mark.asyncio
    async def test_daily_limit_on_handler_is_idempotent_against_the_db(
        self, practice_repository, chat_id
    ):
        """Real handler + real DB: already-on -> no trim; off -> on -> trim once."""
        from unittest.mock import AsyncMock, MagicMock

        from word_learn.handlers.preferences import cmd_daily_limit_off, cmd_daily_limit_on

        await _add_due_cards(practice_repository, chat_id, 150)
        await practice_repository.create_today_practice(chat_id, limit=76)

        message = MagicMock()
        message.chat = MagicMock()
        message.chat.id = chat_id
        message.answer = AsyncMock()

        await cmd_daily_limit_on(message)  # already on
        assert "already on" in message.answer.call_args.args[0]
        assert await practice_repository.count_words_to_practice(chat_id) == 76

        await cmd_daily_limit_off(message)
        assert "Today's list: 150 words." in message.answer.call_args.args[0]
        assert await practice_repository.count_words_to_practice(chat_id) == 150

        await cmd_daily_limit_on(message)
        text = message.answer.call_args.args[0]
        assert "Daily limit enabled." in text
        assert "trimmed to" in text
        assert 67 <= await practice_repository.count_words_to_practice(chat_id) <= 76

    @pytest.mark.asyncio
    async def test_start_practice_session_without_limit_sees_everything(
        self, practice_repository, chat_id
    ):
        from word_learn.services.practice_service import PracticeService

        service = PracticeService(practice_repository)
        await _add_due_cards(practice_repository, chat_id, 90)
        await practice_repository.set_daily_limit(chat_id, False)

        words = await service.start_practice_session(chat_id)

        assert len(words) == 10  # one practice batch
        assert await practice_repository.count_words_to_practice(chat_id) == 90
