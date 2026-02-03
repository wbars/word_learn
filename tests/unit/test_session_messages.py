"""Unit tests for session message formatting."""
from word_learn.models import PracticeStats
from word_learn.services.session_messages import format_session_complete_message


class TestFormatSessionCompleteMessage:
    """Tests for format_session_complete_message."""

    def test_words_remaining_shows_count(self):
        """When words remain, show count only."""
        result = format_session_complete_message(words_remaining=59)
        assert result == "59 words left"

    def test_words_remaining_ignores_stats(self):
        """When words remain, stats are ignored."""
        stats = PracticeStats(chat_id=1, correct=5, total=10)
        result = format_session_complete_message(
            words_remaining=42,
            stats=stats,
            streak_days=7,
        )
        assert result == "42 words left"

    def test_all_done_basic_message(self):
        """When all done with no stats, show basic message."""
        result = format_session_complete_message(words_remaining=0)
        assert result == "Practiced all words!"

    def test_all_done_with_stats(self):
        """When all done with stats, show accuracy."""
        stats = PracticeStats(chat_id=1, correct=8, total=10)
        result = format_session_complete_message(
            words_remaining=0,
            stats=stats,
        )
        assert "Practiced all words!" in result
        assert "8/10 of words were guessed correctly" in result

    def test_all_done_with_streak(self):
        """When all done with streak, show streak line."""
        result = format_session_complete_message(
            words_remaining=0,
            streak_days=5,
        )
        assert "Practiced all words!" in result
        assert "🔥 Streak: 5 days" in result

    def test_all_done_with_stats_and_streak(self):
        """When all done with both stats and streak, show both."""
        stats = PracticeStats(chat_id=1, correct=3, total=5)
        result = format_session_complete_message(
            words_remaining=0,
            stats=stats,
            streak_days=7,
        )
        assert "Practiced all words!" in result
        assert "3/5 of words were guessed correctly" in result
        assert "🔥 Streak: 7 days" in result

    def test_all_done_zero_total_no_accuracy(self):
        """When stats have zero total, don't show accuracy line."""
        stats = PracticeStats(chat_id=1, correct=0, total=0)
        result = format_session_complete_message(
            words_remaining=0,
            stats=stats,
            streak_days=1,
        )
        assert "Practiced all words!" in result
        assert "guessed correctly" not in result
        assert "🔥 Streak: 1 day" in result

    def test_single_word_remaining(self):
        """Single word remaining shows correct grammar."""
        result = format_session_complete_message(words_remaining=1)
        assert result == "1 words left"
