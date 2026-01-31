"""Generator for practice session insights."""
from dataclasses import dataclass

from word_learn.models.practice_stats import SessionStats


@dataclass
class Insight:
    """A single insight about the practice session."""

    emoji: str
    text: str


# Milestone boundaries for confident words (stage 5+)
MILESTONES = [10, 25, 50, 100, 200, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 5000]

# Stage threshold for "Know by heart"
KNOW_BY_HEART_STAGE = 7

# Stage threshold for "Confident" (used in milestones)
CONFIDENT_STAGE = 5

# Minimum consecutive failures to show "struggling" insight
MIN_CONSECUTIVE_FAILURES = 2


def _check_perfect_round(stats: SessionStats) -> Insight | None:
    """Check if this was a perfect round (all correct)."""
    if stats.total_count > 0 and stats.total_correct == stats.total_count:
        return Insight(
            emoji="🎯",
            text=f"Идеальный раунд! {stats.total_correct}/{stats.total_count}!",
        )
    return None


def _check_know_by_heart(stats: SessionStats) -> list[Insight]:
    """Check if any words reached 'Know by heart' level."""
    insights = []
    for word in stats.correct_words:
        if (
            word.new_stage is not None
            and word.new_stage >= KNOW_BY_HEART_STAGE
            and word.old_stage < KNOW_BY_HEART_STAGE
        ):
            insights.append(
                Insight(
                    emoji="⭐",
                    text=f"'{word.word_source}' теперь Know by heart!",
                )
            )
    return insights


def _check_struggling_words(
    stats: SessionStats,
    consecutive_failures: dict[int, int],
) -> list[Insight]:
    """Check if any words are struggling (2+ consecutive failures)."""
    insights = []
    for word in stats.incorrect_words:
        failures = consecutive_failures.get(word.word_id, 0)
        if failures >= MIN_CONSECUTIVE_FAILURES:
            insights.append(
                Insight(
                    emoji="💡",
                    text=f"'{word.word_source}' пока не даётся",
                )
            )
    return insights


def _check_milestone(
    confident_count: int,
    previous_confident_count: int,
) -> Insight | None:
    """Check if user crossed a milestone for confident words."""
    for milestone in MILESTONES:
        if previous_confident_count < milestone <= confident_count:
            return Insight(
                emoji="🏆",
                text=f"У тебя уже {milestone} слов на уровне Confident и выше!",
            )
    return None


def generate_insights(
    stats: SessionStats,
    consecutive_failures: dict[int, int],
    confident_count: int,
    previous_confident_count: int,
) -> list[Insight]:
    """Generate insights based on session data.

    Args:
        stats: Session statistics with word results
        consecutive_failures: Map of word_id to consecutive failure count
        confident_count: Current count of words at stage 5+
        previous_confident_count: Count before this session

    Returns:
        List of insights (empty if none apply)
    """
    insights: list[Insight] = []

    # Check perfect round
    perfect = _check_perfect_round(stats)
    if perfect:
        insights.append(perfect)

    # Check know by heart
    insights.extend(_check_know_by_heart(stats))

    # Check struggling words
    insights.extend(_check_struggling_words(stats, consecutive_failures))

    # Check milestone
    milestone = _check_milestone(confident_count, previous_confident_count)
    if milestone:
        insights.append(milestone)

    return insights
