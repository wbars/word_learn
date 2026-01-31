"""Unit tests for stats formatter service."""
import pytest

from word_learn.models.session_word_result import SessionWordResult
from word_learn.models.practice_stats import SessionStats
from word_learn.services.stats_formatter import (
    format_stage_transition,
    format_session_stats,
)


class TestFormatStageTransition:
    """Tests for format_stage_transition function."""

    def test_different_stages_shows_arrow(self):
        """Test transition between different stages shows arrow."""
        result = format_stage_transition(1, 2)
        assert result == "Just learned (1) → Learning (2)"

    def test_same_stages_shows_no_arrow(self):
        """Test same stage (no change) shows single label without arrow."""
        result = format_stage_transition(7, 7)
        assert result == "Know by heart (7)"

    def test_max_stage_unchanged_shows_single_label(self):
        """Test max stage staying at max shows single label."""
        result = format_stage_transition(33, 33)
        assert result == "Know by heart (33)"

    def test_stage_downgrade_shows_arrow(self):
        """Test downgrade from higher to lower stage shows arrow."""
        result = format_stage_transition(4, 1)
        assert result == "Familiar (4) → Just learned (1)"

    def test_deleted_word_shows_old_stage_only(self):
        """Test deleted word (new_stage=None) shows old stage only."""
        result = format_stage_transition(4, None)
        assert result == "Familiar (4)"


class TestFormatSessionStats:
    """Tests for format_session_stats function."""

    def test_correct_words_section(self):
        """Test correct words are displayed with checkmark."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=1,
                    result="correct",
                    old_stage=1,
                    new_stage=2,
                    word_source="huis",
                    word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=1,
            total_count=1,
        )
        result = format_session_stats(stats)
        assert "✅ Correct:" in result
        assert "huis → house" in result
        assert "Just learned (1) → Learning (2)" in result

    def test_incorrect_words_section(self):
        """Test incorrect words are displayed with X mark."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=2,
                    result="incorrect",
                    old_stage=4,
                    new_stage=1,
                    word_source="boek",
                    word_target="book",
                ),
            ],
            deleted_words=[],
            total_correct=0,
            total_count=1,
        )
        result = format_session_stats(stats)
        assert "❌ Incorrect:" in result
        assert "boek → book" in result
        assert "Familiar (4) → Just learned (1)" in result

    def test_deleted_words_section(self):
        """Test deleted words are displayed with trash icon."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=3,
                    result="deleted",
                    old_stage=4,
                    new_stage=None,
                    word_source="oude_woord",
                    word_target="old_word",
                ),
            ],
            total_correct=0,
            total_count=0,
        )
        result = format_session_stats(stats)
        assert "🗑️ Deleted:" in result
        assert "oude_woord → old_word" in result
        assert "Familiar (4)" in result

    def test_mixed_results(self):
        """Test stats with correct, incorrect, and deleted words."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=1,
                    result="correct",
                    old_stage=1,
                    new_stage=2,
                    word_source="huis",
                    word_target="house",
                ),
                SessionWordResult(
                    chat_id=123,
                    word_id=2,
                    result="correct",
                    old_stage=7,
                    new_stage=7,
                    word_source="kat",
                    word_target="cat",
                ),
            ],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=3,
                    result="incorrect",
                    old_stage=4,
                    new_stage=1,
                    word_source="boek",
                    word_target="book",
                ),
            ],
            deleted_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=4,
                    result="deleted",
                    old_stage=3,
                    new_stage=None,
                    word_source="oud",
                    word_target="old",
                ),
            ],
            total_correct=2,
            total_count=3,
        )
        result = format_session_stats(stats)

        # Check header
        assert "Practiced all words!" in result
        assert "2/3 of words were guessed correctly" in result

        # Check sections exist
        assert "✅ Correct:" in result
        assert "❌ Incorrect:" in result
        assert "🗑️ Deleted:" in result

        # Check word entries
        assert "huis → house" in result
        assert "kat → cat" in result
        assert "Know by heart (7)" in result  # Same stage, no arrow
        assert "boek → book" in result
        assert "oud → old" in result

    def test_empty_session(self):
        """Test empty session returns basic message."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[],
            total_correct=0,
            total_count=0,
        )
        result = format_session_stats(stats)
        assert "Practiced all words!" in result

    def test_no_deleted_section_when_empty(self):
        """Test deleted section is not shown when no words were deleted."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=1,
                    result="correct",
                    old_stage=1,
                    new_stage=2,
                    word_source="huis",
                    word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=1,
            total_count=1,
        )
        result = format_session_stats(stats)
        assert "🗑️ Deleted:" not in result

    def test_no_incorrect_section_when_empty(self):
        """Test incorrect section is not shown when no words were incorrect."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=1,
                    result="correct",
                    old_stage=1,
                    new_stage=2,
                    word_source="huis",
                    word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=1,
            total_count=1,
        )
        result = format_session_stats(stats)
        assert "❌ Incorrect:" not in result

    def test_no_correct_section_when_empty(self):
        """Test correct section is not shown when no words were correct."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123,
                    word_id=1,
                    result="incorrect",
                    old_stage=2,
                    new_stage=1,
                    word_source="huis",
                    word_target="house",
                ),
            ],
            deleted_words=[],
            total_correct=0,
            total_count=1,
        )
        result = format_session_stats(stats)
        assert "✅ Correct:" not in result
