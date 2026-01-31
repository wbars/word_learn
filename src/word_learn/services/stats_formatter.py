"""Formatter for session statistics display."""
from typing import Optional

from word_learn.models.practice_stats import SessionStats
from word_learn.models.session_word_result import SessionWordResult
from word_learn.services.stage_labels import get_stage_label
from word_learn.services.insights_generator import Insight


def format_stage_transition(old_stage: int, new_stage: Optional[int]) -> str:
    """Format a stage transition for display.

    Args:
        old_stage: The stage before the action
        new_stage: The stage after the action (None for deleted words)

    Returns:
        Formatted string showing the transition or just the stage
    """
    old_label = get_stage_label(old_stage)

    # Deleted words only show old stage
    if new_stage is None:
        return f"{old_label} ({old_stage})"

    # Same stage: no arrow
    if old_stage == new_stage:
        return f"{old_label} ({old_stage})"

    # Different stages: show transition with arrow
    new_label = get_stage_label(new_stage)
    return f"{old_label} ({old_stage}) → {new_label} ({new_stage})"


def _format_word_entry(result: SessionWordResult) -> str:
    """Format a single word entry.

    Args:
        result: SessionWordResult for the word

    Returns:
        Formatted string for the word entry
    """
    transition = format_stage_transition(result.old_stage, result.new_stage)
    return f"• {result.word_source} → {result.word_target}: {transition}"


def format_insights(insights: list[Insight]) -> str:
    """Format insights section.

    Args:
        insights: List of insights to display

    Returns:
        Formatted string for insights section, empty if no insights
    """
    if not insights:
        return ""

    lines = ["", "💡 Practice Insights:"]
    for insight in insights:
        lines.append(f"• {insight.emoji} {insight.text}")

    return "\n".join(lines)


def format_session_stats(
    stats: SessionStats,
    insights: Optional[list[Insight]] = None,
) -> str:
    """Format session statistics for display.

    Args:
        stats: SessionStats containing all word results
        insights: Optional list of insights to append

    Returns:
        Formatted string for Telegram message
    """
    lines = ["Practiced all words!"]

    # Add accuracy if there were any words
    if stats.total_count > 0:
        lines.append(f"{stats.accuracy_text} of words were guessed correctly")

    # Add correct words section
    if stats.correct_words:
        lines.append("")
        lines.append("✅ Correct:")
        for result in stats.correct_words:
            lines.append(_format_word_entry(result))

    # Add incorrect words section
    if stats.incorrect_words:
        lines.append("")
        lines.append("❌ Incorrect:")
        for result in stats.incorrect_words:
            lines.append(_format_word_entry(result))

    # Add deleted words section
    if stats.deleted_words:
        lines.append("")
        lines.append("🗑️ Deleted:")
        for result in stats.deleted_words:
            lines.append(_format_word_entry(result))

    # Add insights section
    if insights:
        lines.append(format_insights(insights))

    return "\n".join(lines)
