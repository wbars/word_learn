"""Spaced repetition algorithm implementation.

This module implements the spaced repetition formula used for scheduling
word reviews. The algorithm increases the interval between reviews as
the user demonstrates mastery of a word.

Formula:
- Stage 0: Review same day (0 days)
- Stage 1: Review in 1 day (2^0 = 1)
- Stage N (N > 1): Review in 2^(N-1) + rand(0,1) days

The random component for stages > 1 adds variety and prevents
all words learned on the same day from coming up together.
"""
import random
from datetime import date, datetime, time, timedelta

# Maximum stage - caps the exponential growth
MAX_STAGE = 33


def calculate_days_until_review(stage: int) -> int:
    """Calculate the number of days until next review based on stage.

    Args:
        stage: Current learning stage (0 = new word, higher = more mastery)

    Returns:
        Number of days until the word should be reviewed again
    """
    # Cap at max stage
    stage = min(stage, MAX_STAGE)

    if stage == 0:
        return 0

    # Base formula: 2^(stage-1)
    diff_days = 2 ** (stage - 1)

    # Add random component for stages > 1 to spread out reviews
    if stage > 1:
        diff_days += random.randint(0, 1)

    return diff_days


def calculate_next_date(base_date: date, stage: int) -> datetime:
    """Calculate the next review date based on current date and stage.

    Args:
        base_date: The date from which to calculate (usually today)
        stage: Current learning stage

    Returns:
        Datetime of when the word should next be reviewed (at midnight)
    """
    days = calculate_days_until_review(stage)
    next_date = base_date + timedelta(days=days)
    # Return datetime at midnight
    return datetime.combine(next_date, time.min)


def get_new_stage_correct(current_stage: int) -> int:
    """Get new stage after correct answer.

    Args:
        current_stage: Current learning stage

    Returns:
        New stage (incremented, capped at MAX_STAGE)
    """
    return min(current_stage + 1, MAX_STAGE)


def get_new_stage_incorrect() -> int:
    """Get new stage after incorrect answer.

    Returns:
        New stage (always 1 - reset but not to 0)
    """
    return 1
