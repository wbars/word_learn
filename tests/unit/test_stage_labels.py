"""Unit tests for stage labels service."""
import pytest

from word_learn.services.stage_labels import get_stage_label


class TestGetStageLabel:
    """Tests for get_stage_label function."""

    def test_stage_0_returns_unknown(self):
        """Test stage 0 returns 'Unknown'."""
        assert get_stage_label(0) == "Unknown"

    def test_stage_1_returns_just_learned(self):
        """Test stage 1 returns 'Just learned'."""
        assert get_stage_label(1) == "Just learned"

    def test_stage_2_returns_learning(self):
        """Test stage 2 returns 'Learning'."""
        assert get_stage_label(2) == "Learning"

    def test_stage_3_returns_getting_familiar(self):
        """Test stage 3 returns 'Getting familiar'."""
        assert get_stage_label(3) == "Getting familiar"

    def test_stage_4_returns_familiar(self):
        """Test stage 4 returns 'Familiar'."""
        assert get_stage_label(4) == "Familiar"

    def test_stage_5_returns_confident(self):
        """Test stage 5 returns 'Confident'."""
        assert get_stage_label(5) == "Confident"

    def test_stage_6_returns_well_known(self):
        """Test stage 6 returns 'Well known'."""
        assert get_stage_label(6) == "Well known"

    def test_stage_7_returns_know_by_heart(self):
        """Test stage 7 returns 'Know by heart'."""
        assert get_stage_label(7) == "Know by heart"

    def test_stage_above_7_returns_know_by_heart(self):
        """Test stages above 7 also return 'Know by heart'."""
        assert get_stage_label(8) == "Know by heart"
        assert get_stage_label(10) == "Know by heart"
        assert get_stage_label(33) == "Know by heart"

    def test_max_stage_returns_know_by_heart(self):
        """Test max stage (33) returns 'Know by heart'."""
        assert get_stage_label(33) == "Know by heart"
