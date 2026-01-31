"""PracticeStats model for tracking session statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from word_learn.models.session_word_result import SessionWordResult


@dataclass
class PracticeStats:
    """Statistics for a practice session."""

    chat_id: int
    correct: int = 0
    total: int = 0

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.total == 0:
            return 0.0
        return (self.correct / self.total) * 100

    @property
    def accuracy_text(self) -> str:
        """Get formatted accuracy text."""
        return f"{self.correct}/{self.total}"

    @classmethod
    def from_row(cls, row: dict) -> "PracticeStats":
        """Create PracticeStats from database row."""
        return cls(
            chat_id=row["chat_id"],
            correct=row.get("correct", 0),
            total=row.get("total", 0),
        )


@dataclass
class SessionStats:
    """Enhanced statistics for a practice session with per-word results."""

    correct_words: list[SessionWordResult] = field(default_factory=list)
    incorrect_words: list[SessionWordResult] = field(default_factory=list)
    deleted_words: list[SessionWordResult] = field(default_factory=list)
    total_correct: int = 0
    total_count: int = 0

    @property
    def accuracy_text(self) -> str:
        """Get formatted accuracy text."""
        return f"{self.total_correct}/{self.total_count}"
