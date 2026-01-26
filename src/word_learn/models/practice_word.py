"""PracticeWord model representing a user's learning progress on a word."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from word_learn.config import Language
from word_learn.models.word import Word


@dataclass
class PracticeWord:
    """A word in a user's practice queue with learning progress."""

    id: int
    chat_id: int
    word: Word
    next_date: datetime
    stage: int
    deleted: bool = False

    def get_translation(self, language: Language) -> Optional[str]:
        """Get translation for a specific language."""
        return self.word.get_translation(language)

    @classmethod
    def from_row(cls, row: dict, word: Word) -> "PracticeWord":
        """Create PracticeWord from database row and Word object."""
        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            word=word,
            next_date=row["next_date"],
            stage=row["stage"],
            deleted=row.get("deleted", False),
        )
