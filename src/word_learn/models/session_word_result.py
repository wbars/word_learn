"""SessionWordResult model for tracking per-word results in a practice session."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionWordResult:
    """Result of a single word in a practice session."""

    chat_id: int
    word_id: int
    result: str  # 'correct', 'incorrect', 'deleted'
    old_stage: int
    new_stage: Optional[int]  # None for deleted words
    word_source: str  # source language text (e.g., Dutch)
    word_target: str  # target language text (e.g., English)

    @classmethod
    def from_row(cls, row: dict) -> "SessionWordResult":
        """Create SessionWordResult from database row."""
        return cls(
            chat_id=row["chat_id"],
            word_id=row["word_id"],
            result=row["result"],
            old_stage=row["old_stage"],
            new_stage=row.get("new_stage"),
            word_source=row["word_source"],
            word_target=row["word_target"],
        )
