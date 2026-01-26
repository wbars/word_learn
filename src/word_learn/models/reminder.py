"""Reminder model for daily practice reminders."""
from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class Reminder:
    """A user's daily reminder settings."""

    chat_id: int
    remind_time: time
    next_remind: datetime

    @classmethod
    def from_row(cls, row: dict) -> "Reminder":
        """Create Reminder from database row."""
        return cls(
            chat_id=row["chat_id"],
            remind_time=row["remind_time"],
            next_remind=row["next_remind"],
        )
