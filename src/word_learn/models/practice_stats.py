"""PracticeStats model for tracking session statistics."""
from dataclasses import dataclass


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
