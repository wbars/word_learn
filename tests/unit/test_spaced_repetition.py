"""Unit tests for spaced repetition algorithm."""
import random
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from word_learn.services.spaced_repetition import (
    MAX_STAGE,
    calculate_next_date,
    calculate_days_until_review,
)


class TestCalculateDaysUntilReview:
    """Tests for calculate_days_until_review function."""

    def test_stage_0_returns_0_days(self):
        """Stage 0 should return 0 days (review same day)."""
        assert calculate_days_until_review(0) == 0

    def test_stage_1_returns_1_day(self):
        """Stage 1 should return 1 day (2^0 = 1)."""
        assert calculate_days_until_review(1) == 1

    def test_stage_2_returns_2_days_base(self):
        """Stage 2 base should be 2 days (2^1 = 2), plus 0 or 1."""
        with patch.object(random, 'randint', return_value=0):
            assert calculate_days_until_review(2) == 2

    def test_stage_2_with_random_returns_3_days(self):
        """Stage 2 with random=1 should return 3 days."""
        with patch.object(random, 'randint', return_value=1):
            assert calculate_days_until_review(2) == 3

    def test_stage_3_returns_4_or_5_days(self):
        """Stage 3 should return 4-5 days (2^2 = 4, + rand(0,1))."""
        with patch.object(random, 'randint', return_value=0):
            assert calculate_days_until_review(3) == 4
        with patch.object(random, 'randint', return_value=1):
            assert calculate_days_until_review(3) == 5

    def test_stage_n_formula(self):
        """Test the general formula: 2^(n-1) + rand(0,1) for n>1."""
        test_cases = [
            (4, 8),   # 2^3 = 8
            (5, 16),  # 2^4 = 16
            (6, 32),  # 2^5 = 32
            (10, 512),  # 2^9 = 512
        ]
        with patch.object(random, 'randint', return_value=0):
            for stage, expected_days in test_cases:
                assert calculate_days_until_review(stage) == expected_days, \
                    f"Stage {stage} should return {expected_days} days"

    def test_stage_n_with_random_adds_one(self):
        """Test that random adds 1 day for stages > 1."""
        with patch.object(random, 'randint', return_value=1):
            assert calculate_days_until_review(4) == 9  # 8 + 1
            assert calculate_days_until_review(5) == 17  # 16 + 1

    def test_stage_1_no_random(self):
        """Stage 1 should not add random component."""
        # Even with random returning 1, stage 1 should return exactly 1
        with patch.object(random, 'randint', return_value=1):
            # Stage 1 doesn't call randint, so this shouldn't affect it
            assert calculate_days_until_review(1) == 1


class TestCalculateNextDate:
    """Tests for calculate_next_date function."""

    def test_stage_0_returns_today(self):
        """Stage 0 should return today's date."""
        today = date(2024, 1, 15)
        result = calculate_next_date(today, 0)
        assert result.date() == today

    def test_stage_1_returns_tomorrow(self):
        """Stage 1 should return tomorrow."""
        today = date(2024, 1, 15)
        result = calculate_next_date(today, 1)
        assert result.date() == date(2024, 1, 16)

    def test_stage_2_returns_2_or_3_days(self):
        """Stage 2 should return 2-3 days from today."""
        today = date(2024, 1, 15)
        with patch.object(random, 'randint', return_value=0):
            result = calculate_next_date(today, 2)
            assert result.date() == date(2024, 1, 17)
        with patch.object(random, 'randint', return_value=1):
            result = calculate_next_date(today, 2)
            assert result.date() == date(2024, 1, 18)

    def test_handles_month_boundary(self):
        """Test that date calculation works across month boundaries."""
        today = date(2024, 1, 30)
        with patch.object(random, 'randint', return_value=0):
            result = calculate_next_date(today, 2)
            assert result.date() == date(2024, 2, 1)

    def test_handles_year_boundary(self):
        """Test that date calculation works across year boundaries."""
        today = date(2024, 12, 31)
        result = calculate_next_date(today, 1)
        assert result.date() == date(2025, 1, 1)

    def test_without_tz_returns_naive(self):
        """Without tz parameter, result should be a naive datetime."""
        today = date(2024, 1, 15)
        result = calculate_next_date(today, 1)
        assert result.tzinfo is None

    def test_with_tz_returns_aware(self):
        """With tz parameter, result should be timezone-aware."""
        today = date(2024, 1, 15)
        tz = ZoneInfo("Europe/Amsterdam")
        result = calculate_next_date(today, 1, tz=tz)
        assert result.tzinfo is tz

    def test_with_tz_midnight_is_local(self):
        """With tz, midnight should be in the given timezone, not UTC."""
        today = date(2024, 1, 15)
        tz = ZoneInfo("Europe/Amsterdam")
        result = calculate_next_date(today, 0, tz=tz)
        # Midnight Amsterdam = 2024-01-15 00:00:00+01:00
        expected = datetime(2024, 1, 15, 0, 0, 0, tzinfo=tz)
        assert result == expected

    def test_with_tz_differs_from_utc(self):
        """Timezone-aware midnight Amsterdam != midnight UTC."""
        today = date(2024, 1, 15)
        tz_ams = ZoneInfo("Europe/Amsterdam")
        tz_utc = ZoneInfo("UTC")
        result_ams = calculate_next_date(today, 1, tz=tz_ams)
        result_utc = calculate_next_date(today, 1, tz=tz_utc)
        # Same local time, different instants in time
        assert result_ams.date() == result_utc.date()
        assert result_ams != result_utc
        # Amsterdam midnight is earlier in UTC than UTC midnight
        assert result_ams < result_utc

    def test_with_tz_stage_0_is_today(self):
        """Stage 0 with tz should still return today at midnight local."""
        today = date(2024, 6, 15)
        tz = ZoneInfo("Europe/Amsterdam")
        result = calculate_next_date(today, 0, tz=tz)
        assert result.date() == today
        assert result.hour == 0
        assert result.minute == 0
        assert result.tzinfo is tz

    def test_with_tz_stage_1_is_tomorrow(self):
        """Stage 1 with tz should return tomorrow at midnight local."""
        today = date(2024, 6, 15)
        tz = ZoneInfo("Europe/Amsterdam")
        result = calculate_next_date(today, 1, tz=tz)
        assert result.date() == date(2024, 6, 16)
        assert result == datetime(2024, 6, 16, 0, 0, 0, tzinfo=tz)


class TestMaxStage:
    """Tests for maximum stage handling."""

    def test_max_stage_is_33(self):
        """Maximum stage should be 33."""
        assert MAX_STAGE == 33

    def test_stage_above_max_is_capped(self):
        """Stages above max should be capped at max."""
        today = date(2024, 1, 15)
        # Stage 33 and 34 should return the same result
        with patch.object(random, 'randint', return_value=0):
            result_33 = calculate_next_date(today, 33)
            result_34 = calculate_next_date(today, 34)
            assert result_33 == result_34


class TestIncorrectAnswer:
    """Tests for incorrect answer handling (stage reset)."""

    def test_incorrect_resets_to_stage_1(self):
        """After incorrect answer, stage should reset to 1."""
        # This tests that stage 1 gives the expected review interval
        # The actual reset logic is in the repository/service layer
        today = date(2024, 1, 15)
        result = calculate_next_date(today, 1)
        expected = today + timedelta(days=1)
        assert result.date() == expected


class TestRandomDistribution:
    """Tests to verify random component works correctly."""

    def test_random_called_for_stage_above_1(self):
        """Verify random.randint is called for stages > 1."""
        with patch.object(random, 'randint') as mock_randint:
            mock_randint.return_value = 0
            calculate_days_until_review(2)
            mock_randint.assert_called_once_with(0, 1)

    def test_random_not_called_for_stage_0(self):
        """Verify random.randint is not called for stage 0."""
        with patch.object(random, 'randint') as mock_randint:
            calculate_days_until_review(0)
            mock_randint.assert_not_called()

    def test_random_not_called_for_stage_1(self):
        """Verify random.randint is not called for stage 1."""
        with patch.object(random, 'randint') as mock_randint:
            calculate_days_until_review(1)
            mock_randint.assert_not_called()
