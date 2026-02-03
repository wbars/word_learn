"""Session completion message formatting."""
from word_learn.models import PracticeStats
from word_learn.services.streaks import format_streak_line


def format_session_complete_message(
    words_remaining: int,
    stats: PracticeStats | None = None,
    streak_days: int | None = None,
) -> str:
    """Format the message shown when a practice batch is complete.

    Args:
        words_remaining: Number of words still left to practice today
        stats: Practice statistics (only used when all words are done)
        streak_days: Current streak in days (only used when all words are done)

    Returns:
        Formatted message string
    """
    if words_remaining > 0:
        return f"{words_remaining} words left"

    # All daily words done
    text = "Practiced all words!"
    if stats and stats.total > 0:
        text += f"\n{stats.accuracy_text} of words were guessed correctly"
    if streak_days is not None:
        text += f"\n{format_streak_line(streak_days)}"
    return text
