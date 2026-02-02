"""Streak calculations and formatting."""
from __future__ import annotations

from datetime import date, timedelta

STREAK_MILESTONES: dict[int, str] = {
    3: "Warm-Up Run",
    7: "Week Warrior",
    14: "Fortnight Force",
    21: "Habit Locked",
    30: "Month Master",
    40: "Momentum Maker",
    60: "Two-Month Titan",
    90: "Seasoned Streak",
    120: "Quarter Champion",
    180: "Half-Year Hero",
    240: "Eight-Month Engine",
    300: "Three-Hundred Club",
    365: "Year Legend",
}


def compute_streak_update(
    last_active: date | None,
    current_streak: int,
    today: date,
) -> tuple[int, date]:
    """Compute updated streak based on last activity date."""
    if last_active is None:
        return 1, today

    if last_active > today:
        return max(current_streak, 1), today

    if last_active == today:
        return max(current_streak, 1), today

    if last_active == today - timedelta(days=1):
        return max(current_streak, 1) + 1, today

    return 1, today


def get_streak_label(streak_days: int) -> str | None:
    """Return milestone label for a streak value if any."""
    return STREAK_MILESTONES.get(streak_days)


def format_streak_line(streak_days: int) -> str:
    """Format a streak line for end-of-session text."""
    day_label = "day" if streak_days == 1 else "days"
    label = get_streak_label(streak_days)
    if label:
        return f"🔥 Streak: {streak_days} {day_label} ({label})"
    return f"🔥 Streak: {streak_days} {day_label}"
