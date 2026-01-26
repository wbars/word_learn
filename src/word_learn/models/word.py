"""Word model representing a vocabulary entry."""
from dataclasses import dataclass
from typing import Optional

from word_learn.config import Language


@dataclass
class Word:
    """A vocabulary word with translations in multiple languages."""

    id: int
    en: Optional[str] = None
    nl: Optional[str] = None
    ru: Optional[str] = None

    def get_translation(self, language: Language) -> Optional[str]:
        """Get translation for a specific language."""
        return getattr(self, language.column_name, None)

    @classmethod
    def from_row(cls, row: dict) -> "Word":
        """Create Word from database row."""
        return cls(
            id=row["id"],
            en=row.get("en"),
            nl=row.get("nl"),
            ru=row.get("ru"),
        )
