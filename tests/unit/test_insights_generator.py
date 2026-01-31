"""Unit tests for insights generator service."""
import pytest

from word_learn.models.session_word_result import SessionWordResult
from word_learn.models.practice_stats import SessionStats
from word_learn.services.insights_generator import generate_insights, MILESTONES


class TestGenerateInsights:
    """Tests for generate_insights function."""

    def test_perfect_round_insight(self):
        """Test perfect round insight when all answers correct."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=1, new_stage=2, word_source="huis", word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=10,
            total_count=10,
        )
        insights = generate_insights(stats, {}, 50, 50)
        assert any("Идеальный раунд" in i.text for i in insights)

    def test_no_perfect_round_when_has_errors(self):
        """Test no perfect round insight when there are errors."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="incorrect",
                    old_stage=2, new_stage=1, word_source="boek", word_target="book",
                ),
            ],
            deleted_words=[],
            total_correct=8,
            total_count=10,
        )
        insights = generate_insights(stats, {1: 1}, 50, 50)
        assert not any("Идеальный раунд" in i.text for i in insights)

    def test_no_perfect_round_when_empty_session(self):
        """Test no perfect round insight when session is empty."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[],
            total_correct=0,
            total_count=0,
        )
        insights = generate_insights(stats, {}, 50, 50)
        assert not any("Идеальный раунд" in i.text for i in insights)

    def test_know_by_heart_insight(self):
        """Test know by heart insight when word reaches stage 7."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=6, new_stage=7, word_source="huis", word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=1,
            total_count=1,
        )
        insights = generate_insights(stats, {}, 50, 50)
        assert any("huis" in i.text and "Know by heart" in i.text for i in insights)

    def test_know_by_heart_multiple_words(self):
        """Test know by heart insight for multiple words."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=6, new_stage=7, word_source="huis", word_target="house",
                ),
                SessionWordResult(
                    chat_id=123, word_id=2, result="correct",
                    old_stage=6, new_stage=7, word_source="kat", word_target="cat",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=2,
            total_count=2,
        )
        insights = generate_insights(stats, {}, 50, 50)
        know_by_heart_insights = [i for i in insights if "Know by heart" in i.text]
        assert len(know_by_heart_insights) == 2

    def test_no_know_by_heart_when_already_at_max(self):
        """Test no know by heart insight when word was already at stage 7+."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=7, new_stage=7, word_source="huis", word_target="house",
                ),
            ],
            incorrect_words=[],
            deleted_words=[],
            total_correct=1,
            total_count=1,
        )
        insights = generate_insights(stats, {}, 50, 50)
        assert not any("Know by heart" in i.text for i in insights)

    def test_struggling_word_insight(self):
        """Test struggling word insight when 2+ consecutive failures."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="incorrect",
                    old_stage=2, new_stage=1, word_source="appel", word_target="apple",
                ),
            ],
            deleted_words=[],
            total_correct=0,
            total_count=1,
        )
        insights = generate_insights(stats, {1: 2}, 50, 50)
        assert any("appel" in i.text and "не даётся" in i.text for i in insights)

    def test_no_struggling_when_only_one_failure(self):
        """Test no struggling insight when only 1 consecutive failure."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="incorrect",
                    old_stage=2, new_stage=1, word_source="appel", word_target="apple",
                ),
            ],
            deleted_words=[],
            total_correct=0,
            total_count=1,
        )
        insights = generate_insights(stats, {1: 1}, 50, 50)
        assert not any("не даётся" in i.text for i in insights)

    def test_milestone_100_insight(self):
        """Test milestone insight when crossing 100 confident words."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[],
            total_correct=5,
            total_count=5,
        )
        # Previous was 99, now 100
        insights = generate_insights(stats, {}, 100, 99)
        assert any("100" in i.text and "Confident" in i.text for i in insights)

    def test_milestone_500_insight(self):
        """Test milestone insight when crossing 500 confident words."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[],
            total_correct=5,
            total_count=5,
        )
        insights = generate_insights(stats, {}, 500, 499)
        assert any("500" in i.text for i in insights)

    def test_no_milestone_when_not_crossed(self):
        """Test no milestone insight when not crossing boundary."""
        stats = SessionStats(
            correct_words=[],
            incorrect_words=[],
            deleted_words=[],
            total_correct=5,
            total_count=5,
        )
        # 101 -> 102, no milestone crossed
        insights = generate_insights(stats, {}, 102, 101)
        assert not any("Confident" in i.text for i in insights)

    def test_multiple_insights_combined(self):
        """Test multiple insights in one session."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=6, new_stage=7, word_source="huis", word_target="house",
                ),
            ],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123, word_id=2, result="incorrect",
                    old_stage=2, new_stage=1, word_source="appel", word_target="apple",
                ),
            ],
            deleted_words=[],
            total_correct=9,
            total_count=10,
        )
        insights = generate_insights(stats, {2: 3}, 100, 99)

        # Should have: know by heart, struggling, milestone
        assert any("Know by heart" in i.text for i in insights)
        assert any("не даётся" in i.text for i in insights)
        assert any("100" in i.text for i in insights)

    def test_no_insights_returns_empty_list(self):
        """Test empty list when no insights apply."""
        stats = SessionStats(
            correct_words=[
                SessionWordResult(
                    chat_id=123, word_id=1, result="correct",
                    old_stage=1, new_stage=2, word_source="huis", word_target="house",
                ),
            ],
            incorrect_words=[
                SessionWordResult(
                    chat_id=123, word_id=2, result="incorrect",
                    old_stage=2, new_stage=1, word_source="boek", word_target="book",
                ),
            ],
            deleted_words=[],
            total_correct=8,
            total_count=10,
        )
        # No consecutive failures >= 2, no milestone, no know by heart, not perfect
        insights = generate_insights(stats, {2: 1}, 55, 54)
        assert insights == []


class TestMilestones:
    """Tests for milestone boundaries."""

    def test_milestones_list_is_sorted(self):
        """Test that milestones list is sorted ascending."""
        assert MILESTONES == sorted(MILESTONES)

    def test_milestones_contains_expected_values(self):
        """Test that milestones contains key values."""
        assert 100 in MILESTONES
        assert 500 in MILESTONES
        assert 1000 in MILESTONES
