"""Unit tests for data models."""
from datetime import datetime, time

import pytest

from word_learn.config import Language
from word_learn.models.word import Word
from word_learn.models.practice_word import PracticeWord
from word_learn.models.practice_stats import PracticeStats
from word_learn.models.reminder import Reminder


class TestWord:
    """Tests for Word model."""

    def test_word_from_row(self):
        """Test creating Word from database row."""
        row = {"id": 1, "en": "cat", "nl": "kat", "ru": "кот"}
        word = Word.from_row(row)
        assert word.id == 1
        assert word.en == "cat"
        assert word.nl == "kat"
        assert word.ru == "кот"

    def test_word_from_row_with_nulls(self):
        """Test creating Word with missing translations."""
        row = {"id": 2, "en": "dog", "nl": None, "ru": None}
        word = Word.from_row(row)
        assert word.id == 2
        assert word.en == "dog"
        assert word.nl is None
        assert word.ru is None

    def test_get_translation_en(self):
        """Test getting English translation."""
        word = Word(id=1, en="cat", nl="kat", ru="кот")
        assert word.get_translation(Language.EN) == "cat"

    def test_get_translation_nl(self):
        """Test getting Dutch translation."""
        word = Word(id=1, en="cat", nl="kat", ru="кот")
        assert word.get_translation(Language.NL) == "kat"

    def test_get_translation_ru(self):
        """Test getting Russian translation."""
        word = Word(id=1, en="cat", nl="kat", ru="кот")
        assert word.get_translation(Language.RU) == "кот"

    def test_get_translation_missing(self):
        """Test getting missing translation returns None."""
        word = Word(id=1, en="cat")
        assert word.get_translation(Language.NL) is None


class TestPracticeWord:
    """Tests for PracticeWord model."""

    def test_practice_word_from_row(self):
        """Test creating PracticeWord from database row."""
        word = Word(id=1, en="cat", nl="kat")
        row = {
            "id": 10,
            "chat_id": 12345,
            "word_id": 1,
            "next_date": datetime(2024, 1, 15, 0, 0),
            "stage": 5,
            "deleted": False,
        }
        practice_word = PracticeWord.from_row(row, word)
        assert practice_word.id == 10
        assert practice_word.chat_id == 12345
        assert practice_word.word == word
        assert practice_word.next_date == datetime(2024, 1, 15, 0, 0)
        assert practice_word.stage == 5
        assert practice_word.deleted is False

    def test_practice_word_get_translation(self):
        """Test getting translation through PracticeWord."""
        word = Word(id=1, en="cat", nl="kat")
        practice_word = PracticeWord(
            id=10,
            chat_id=12345,
            word=word,
            next_date=datetime(2024, 1, 15),
            stage=1,
        )
        assert practice_word.get_translation(Language.EN) == "cat"
        assert practice_word.get_translation(Language.NL) == "kat"


class TestPracticeStats:
    """Tests for PracticeStats model."""

    def test_stats_from_row(self):
        """Test creating PracticeStats from database row."""
        row = {"chat_id": 12345, "correct": 8, "total": 10}
        stats = PracticeStats.from_row(row)
        assert stats.chat_id == 12345
        assert stats.correct == 8
        assert stats.total == 10

    def test_accuracy_calculation(self):
        """Test accuracy percentage calculation."""
        stats = PracticeStats(chat_id=12345, correct=8, total=10)
        assert stats.accuracy == 80.0

    def test_accuracy_zero_total(self):
        """Test accuracy with zero total returns 0."""
        stats = PracticeStats(chat_id=12345, correct=0, total=0)
        assert stats.accuracy == 0.0

    def test_accuracy_text(self):
        """Test accuracy text formatting."""
        stats = PracticeStats(chat_id=12345, correct=8, total=10)
        assert stats.accuracy_text == "8/10"

    def test_accuracy_perfect(self):
        """Test perfect accuracy."""
        stats = PracticeStats(chat_id=12345, correct=10, total=10)
        assert stats.accuracy == 100.0

    def test_accuracy_none(self):
        """Test zero accuracy."""
        stats = PracticeStats(chat_id=12345, correct=0, total=10)
        assert stats.accuracy == 0.0


class TestReminder:
    """Tests for Reminder model."""

    def test_reminder_from_row(self):
        """Test creating Reminder from database row."""
        row = {
            "chat_id": 12345,
            "remind_time": time(9, 0),
            "next_remind": datetime(2024, 1, 15, 9, 0),
        }
        reminder = Reminder.from_row(row)
        assert reminder.chat_id == 12345
        assert reminder.remind_time == time(9, 0)
        assert reminder.next_remind == datetime(2024, 1, 15, 9, 0)
