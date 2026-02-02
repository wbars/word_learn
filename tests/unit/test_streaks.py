"""Unit tests for streak helpers."""
from datetime import date, timedelta

from word_learn.services.streaks import (
    compute_streak_update,
    format_streak_line,
    get_streak_label,
)


def test_first_use_starts_streak():
    today = date(2024, 1, 15)
    streak, last_active = compute_streak_update(None, 0, today)
    assert streak == 1
    assert last_active == today


def test_same_day_keeps_streak():
    today = date(2024, 1, 15)
    streak, last_active = compute_streak_update(today, 5, today)
    assert streak == 5
    assert last_active == today


def test_next_day_increments_streak():
    today = date(2024, 1, 15)
    yesterday = today - timedelta(days=1)
    streak, last_active = compute_streak_update(yesterday, 5, today)
    assert streak == 6
    assert last_active == today


def test_gap_resets_streak():
    today = date(2024, 1, 15)
    two_days_ago = today - timedelta(days=2)
    streak, last_active = compute_streak_update(two_days_ago, 5, today)
    assert streak == 1
    assert last_active == today


def test_future_date_does_not_decrease_streak():
    today = date(2024, 1, 15)
    tomorrow = today + timedelta(days=1)
    streak, last_active = compute_streak_update(tomorrow, 5, today)
    assert streak == 5
    assert last_active == today


def test_get_streak_label_for_milestone():
    assert get_streak_label(7) == "Week Warrior"


def test_format_streak_line_with_label():
    assert format_streak_line(7) == "🔥 Streak: 7 days (Week Warrior)"


def test_format_streak_line_without_label():
    assert format_streak_line(5) == "🔥 Streak: 5 days"


def test_format_streak_line_singular():
    assert format_streak_line(1) == "🔥 Streak: 1 day"
