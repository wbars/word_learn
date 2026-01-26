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
