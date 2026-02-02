"""Repository for practice-related database operations."""
import random
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from word_learn.config import get_settings
from word_learn.database import Database
from word_learn.models import PracticeWord, PracticeStats, Word, Reminder, SessionWordResult
from word_learn.services.streaks import compute_streak_update


class PracticeRepository:
    """Repository for managing word practice in the database."""

    # Word Practice Operations

    async def add_word(self, translations: dict[str, str]) -> Word:
        """Add a new word with translations.

        Args:
            translations: Dict mapping language codes to translations

        Returns:
            Created Word object
        """
        columns = list(translations.keys())
        values = list(translations.values())
        placeholders = [f"${i+1}" for i in range(len(values))]

        query = f"""
            INSERT INTO words ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING id, en, nl, ru
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, *values)
            return Word.from_row(dict(row))

    async def add_to_practice(
        self,
        chat_id: int,
        word_ids: list[int],
    ) -> None:
        """Add words to user's practice queue.

        Args:
            chat_id: Telegram chat ID
            word_ids: List of word IDs to add
        """
        if not word_ids:
            return

        now = datetime.now(ZoneInfo(get_settings().tz))

        query = """
            INSERT INTO word_practice (word_id, chat_id, next_date, stage)
            VALUES ($1, $2, $3, 0)
            ON CONFLICT DO NOTHING
        """

        async with Database.connection() as conn:
            await conn.executemany(
                query,
                [(word_id, chat_id, now) for word_id in word_ids],
            )

    async def get_word_by_id(self, word_id: int) -> Optional[Word]:
        """Get a word by its ID.

        Args:
            word_id: Word ID

        Returns:
            Word object or None
        """
        query = "SELECT id, en, nl, ru FROM words WHERE id = $1"

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, word_id)
            if row:
                return Word.from_row(dict(row))
            return None

    async def get_practice_word(
        self,
        chat_id: int,
        word_id: int,
    ) -> Optional[PracticeWord]:
        """Get a practice word by chat ID and word ID.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID

        Returns:
            PracticeWord object or None
        """
        query = """
            SELECT wp.id, wp.word_id, wp.chat_id, wp.next_date, wp.stage, wp.deleted,
                   w.id as w_id, w.en, w.nl, w.ru
            FROM word_practice wp
            JOIN words w ON w.id = wp.word_id
            WHERE wp.chat_id = $1 AND wp.word_id = $2 AND wp.deleted = FALSE
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id, word_id)
            if row:
                row_dict = dict(row)
                word = Word(
                    id=row_dict["w_id"],
                    en=row_dict["en"],
                    nl=row_dict["nl"],
                    ru=row_dict["ru"],
                )
                return PracticeWord.from_row(row_dict, word)
            return None

    async def update_practice_word(
        self,
        chat_id: int,
        word_id: int,
        stage: int,
        next_date: datetime,
    ) -> None:
        """Update practice word's stage and next review date.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            stage: New stage
            next_date: Next review datetime
        """
        query = """
            UPDATE word_practice
            SET stage = $3, next_date = $4
            WHERE chat_id = $1 AND word_id = $2
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, word_id, stage, next_date)

    async def mark_deleted(self, chat_id: int, word_id: int) -> None:
        """Soft delete a word from practice.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
        """
        query = """
            UPDATE word_practice
            SET deleted = TRUE
            WHERE chat_id = $1 AND word_id = $2
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, word_id)

    # Today Practice Operations

    async def get_today_practice(self, chat_id: int) -> list[int]:
        """Get today's practice pool for a user.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of word_practice IDs in today's pool
        """
        today = datetime.now(ZoneInfo(get_settings().tz)).date()

        query = """
            SELECT tp.word_practice_id
            FROM today_practice tp
            JOIN word_practice wp ON wp.id = tp.word_practice_id
            WHERE tp.date = $1 AND wp.chat_id = $2
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, today, chat_id)
            return [row["word_practice_id"] for row in rows]

    async def create_today_practice(
        self,
        chat_id: int,
        limit: int,
    ) -> list[int]:
        """Create today's practice pool.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of words to include

        Returns:
            List of word_practice IDs added to today's pool
        """
        now = datetime.now(ZoneInfo(get_settings().tz))
        today = now.date()

        # First, get eligible practice words
        select_query = """
            SELECT id FROM word_practice
            WHERE chat_id = $1
              AND next_date <= $2
              AND deleted = FALSE
            ORDER BY RANDOM()
            LIMIT $3
        """

        insert_query = """
            INSERT INTO today_practice (word_practice_id, date)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(select_query, chat_id, now, limit)
            practice_ids = [row["id"] for row in rows]

            if practice_ids:
                await conn.executemany(
                    insert_query,
                    [(pid, today) for pid in practice_ids],
                )

            return practice_ids

    # Current Practice Operations

    async def get_words_to_practice(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[PracticeWord]:
        """Get words due for practice from today's pool.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of words

        Returns:
            List of PracticeWord objects
        """
        now = datetime.now(ZoneInfo(get_settings().tz))
        today = now.date()

        query = """
            SELECT wp.id, wp.word_id, wp.chat_id, wp.next_date, wp.stage, wp.deleted,
                   w.id as w_id, w.en, w.nl, w.ru
            FROM word_practice wp
            JOIN words w ON w.id = wp.word_id
            JOIN today_practice tp ON tp.word_practice_id = wp.id AND tp.date = $4
            WHERE wp.chat_id = $1
              AND wp.next_date <= $2
              AND wp.deleted = FALSE
              AND wp.word_id NOT IN (
                  SELECT word_id FROM current_practice WHERE chat_id = $1
              )
            ORDER BY RANDOM()
            LIMIT $3
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, chat_id, now, limit, today)
            result = []
            for row in rows:
                row_dict = dict(row)
                word = Word(
                    id=row_dict["w_id"],
                    en=row_dict["en"],
                    nl=row_dict["nl"],
                    ru=row_dict["ru"],
                )
                result.append(PracticeWord.from_row(row_dict, word))
            return result

    async def count_words_to_practice(self, chat_id: int) -> int:
        """Count words due for practice from today's pool.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Count of due words
        """
        now = datetime.now(ZoneInfo(get_settings().tz))
        today = now.date()

        query = """
            SELECT COUNT(*) as count
            FROM word_practice wp
            JOIN today_practice tp ON tp.word_practice_id = wp.id AND tp.date = $3
            WHERE wp.chat_id = $1
              AND wp.next_date <= $2
              AND wp.deleted = FALSE
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id, now, today)
            return row["count"] if row else 0

    async def start_practice(
        self,
        chat_id: int,
        word_ids: list[int],
    ) -> None:
        """Start practice session by adding words to current_practice.

        Args:
            chat_id: Telegram chat ID
            word_ids: List of word IDs
        """
        if not word_ids:
            return

        query = """
            INSERT INTO current_practice (chat_id, word_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """

        async with Database.connection() as conn:
            await conn.executemany(
                query,
                [(chat_id, word_id) for word_id in word_ids],
            )

    async def get_next_practice_word(
        self,
        chat_id: int,
    ) -> Optional[PracticeWord]:
        """Get next word from current practice session.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Next PracticeWord or None if session is complete
        """
        query = """
            SELECT wp.id, wp.word_id, wp.chat_id, wp.next_date, wp.stage, wp.deleted,
                   w.id as w_id, w.en, w.nl, w.ru
            FROM current_practice cp
            JOIN word_practice wp ON wp.word_id = cp.word_id AND wp.chat_id = cp.chat_id
            JOIN words w ON w.id = wp.word_id
            WHERE cp.chat_id = $1 AND wp.deleted = FALSE
            LIMIT 1
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id)
            if row:
                row_dict = dict(row)
                word = Word(
                    id=row_dict["w_id"],
                    en=row_dict["en"],
                    nl=row_dict["nl"],
                    ru=row_dict["ru"],
                )
                return PracticeWord.from_row(row_dict, word)
            return None

    async def remove_from_current_practice(
        self,
        chat_id: int,
        word_id: int,
    ) -> None:
        """Remove a word from current practice session.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
        """
        query = """
            DELETE FROM current_practice
            WHERE chat_id = $1 AND word_id = $2
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, word_id)

    async def clear_current_practice(self, chat_id: int) -> None:
        """Clear all words from current practice session.

        Args:
            chat_id: Telegram chat ID
        """
        query = "DELETE FROM current_practice WHERE chat_id = $1"

        async with Database.connection() as conn:
            await conn.execute(query, chat_id)

    # Statistics Operations

    async def get_statistics(self, chat_id: int) -> PracticeStats:
        """Get practice statistics for a session.

        Args:
            chat_id: Telegram chat ID

        Returns:
            PracticeStats object
        """
        query = """
            SELECT chat_id, correct, total
            FROM current_practice_stats
            WHERE chat_id = $1
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id)
            if row:
                return PracticeStats.from_row(dict(row))
            return PracticeStats(chat_id=chat_id)

    async def increment_statistics(
        self,
        chat_id: int,
        correct: bool,
    ) -> None:
        """Increment practice statistics.

        Args:
            chat_id: Telegram chat ID
            correct: Whether answer was correct
        """
        correct_inc = 1 if correct else 0

        query = """
            INSERT INTO current_practice_stats (chat_id, correct, total)
            VALUES ($1, $2, 1)
            ON CONFLICT (chat_id)
            DO UPDATE SET correct = current_practice_stats.correct + $2,
                          total = current_practice_stats.total + 1
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, correct_inc)

    async def reset_statistics(self, chat_id: int) -> None:
        """Reset practice statistics for a session.

        Args:
            chat_id: Telegram chat ID
        """
        query = "DELETE FROM current_practice_stats WHERE chat_id = $1"

        async with Database.connection() as conn:
            await conn.execute(query, chat_id)

    # Reminder Operations

    async def get_reminder(self, chat_id: int) -> Optional[Reminder]:
        """Get reminder settings for a user.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Reminder object or None
        """
        query = """
            SELECT chat_id, remind_time, next_remind
            FROM reminders
            WHERE chat_id = $1
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id)
            if row:
                return Reminder.from_row(dict(row))
            return None

    async def set_reminder(
        self,
        chat_id: int,
        remind_time: time,
        next_remind: datetime,
    ) -> None:
        """Set or update reminder for a user.

        Args:
            chat_id: Telegram chat ID
            remind_time: Daily reminder time
            next_remind: Next reminder datetime
        """
        query = """
            INSERT INTO reminders (chat_id, remind_time, next_remind)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id)
            DO UPDATE SET remind_time = $2, next_remind = $3
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, remind_time, next_remind)

    async def get_due_reminders(self) -> list[Reminder]:
        """Get all reminders that are due to be sent.

        Returns:
            List of due Reminder objects
        """
        now = datetime.now(ZoneInfo(get_settings().tz))

        query = """
            SELECT chat_id, remind_time, next_remind
            FROM reminders
            WHERE next_remind <= $1
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, now)
            return [Reminder.from_row(dict(row)) for row in rows]

    async def update_next_reminder(
        self,
        chat_id: int,
        next_remind: datetime,
    ) -> None:
        """Update the next reminder time.

        Args:
            chat_id: Telegram chat ID
            next_remind: New next reminder datetime
        """
        query = """
            UPDATE reminders
            SET next_remind = $2
            WHERE chat_id = $1
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, next_remind)

    # Words to Add Operations

    async def get_words_to_add(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[Word]:
        """Get words available for user to add to practice.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of words

        Returns:
            List of Word objects
        """
        query = """
            SELECT w.id, w.en, w.nl, w.ru
            FROM words w
            WHERE w.id NOT IN (
                SELECT word_id FROM word_practice WHERE chat_id = $1
            )
            AND w.id NOT IN (
                SELECT word_id FROM word_skiplist WHERE chat_id = $1
            )
            ORDER BY RANDOM()
            LIMIT $2
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, chat_id, limit)
            return [Word.from_row(dict(row)) for row in rows]

    async def add_to_skiplist(
        self,
        chat_id: int,
        word_ids: list[int],
    ) -> None:
        """Add words to user's skiplist.

        Args:
            chat_id: Telegram chat ID
            word_ids: List of word IDs to skip
        """
        if not word_ids:
            return

        query = """
            INSERT INTO word_skiplist (word_id, chat_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """

        async with Database.connection() as conn:
            await conn.executemany(
                query,
                [(word_id, chat_id) for word_id in word_ids],
            )

    # Session Word Results Operations

    async def save_word_result(
        self,
        chat_id: int,
        word_id: int,
        result: str,
        old_stage: int,
        new_stage: Optional[int],
        word_source: str,
        word_target: str,
    ) -> None:
        """Save a per-word result during a practice session.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            result: 'correct', 'incorrect', or 'deleted'
            old_stage: Stage before the action
            new_stage: Stage after the action (None for deleted)
            word_source: Source language text
            word_target: Target language text
        """
        query = """
            INSERT INTO session_word_results
                (chat_id, word_id, result, old_stage, new_stage, word_source, word_target)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id, word_id)
            DO UPDATE SET result = $3, old_stage = $4, new_stage = $5,
                          word_source = $6, word_target = $7
        """

        async with Database.connection() as conn:
            await conn.execute(
                query,
                chat_id,
                word_id,
                result,
                old_stage,
                new_stage,
                word_source,
                word_target,
            )

    async def get_session_results(self, chat_id: int) -> list[SessionWordResult]:
        """Get all session word results for a user.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of SessionWordResult objects
        """
        query = """
            SELECT chat_id, word_id, result, old_stage, new_stage, word_source, word_target
            FROM session_word_results
            WHERE chat_id = $1
            ORDER BY word_id
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, chat_id)
            return [SessionWordResult.from_row(dict(row)) for row in rows]

    async def clear_session_results(self, chat_id: int) -> None:
        """Clear all session word results for a user.

        Args:
            chat_id: Telegram chat ID
        """
        query = "DELETE FROM session_word_results WHERE chat_id = $1"

        async with Database.connection() as conn:
            await conn.execute(query, chat_id)

    # Streak Operations

    async def update_streak(self, chat_id: int, today: date) -> int:
        """Update and return the user's current streak.

        Args:
            chat_id: Telegram chat ID
            today: Date of activity in configured timezone

        Returns:
            Updated streak length in days
        """
        select_query = """
            SELECT current_streak, last_active_date
            FROM practice_streaks
            WHERE chat_id = $1
        """
        upsert_query = """
            INSERT INTO practice_streaks (chat_id, current_streak, last_active_date)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id)
            DO UPDATE SET current_streak = $2, last_active_date = $3
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(select_query, chat_id)
            current_streak = row["current_streak"] if row else 0
            last_active = row["last_active_date"] if row else None
            new_streak, new_last_active = compute_streak_update(
                last_active,
                current_streak,
                today,
            )
            await conn.execute(
                upsert_query,
                chat_id,
                new_streak,
                new_last_active,
            )
            return new_streak

    # Consecutive Failures Operations

    async def increment_consecutive_failures(
        self,
        chat_id: int,
        word_id: int,
    ) -> int:
        """Increment consecutive failures counter for a word.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID

        Returns:
            New consecutive failures count
        """
        query = """
            UPDATE word_practice
            SET consecutive_failures = consecutive_failures + 1
            WHERE chat_id = $1 AND word_id = $2
            RETURNING consecutive_failures
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id, word_id)
            return row["consecutive_failures"] if row else 0

    async def reset_consecutive_failures(
        self,
        chat_id: int,
        word_id: int,
    ) -> None:
        """Reset consecutive failures counter to 0.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
        """
        query = """
            UPDATE word_practice
            SET consecutive_failures = 0
            WHERE chat_id = $1 AND word_id = $2
        """

        async with Database.connection() as conn:
            await conn.execute(query, chat_id, word_id)

    async def get_consecutive_failures(
        self,
        chat_id: int,
        word_ids: list[int],
    ) -> dict[int, int]:
        """Get consecutive failures for multiple words.

        Args:
            chat_id: Telegram chat ID
            word_ids: List of word IDs

        Returns:
            Dict mapping word_id to consecutive_failures count
        """
        if not word_ids:
            return {}

        query = """
            SELECT word_id, consecutive_failures
            FROM word_practice
            WHERE chat_id = $1 AND word_id = ANY($2)
        """

        async with Database.connection() as conn:
            rows = await conn.fetch(query, chat_id, word_ids)
            return {row["word_id"]: row["consecutive_failures"] for row in rows}

    # Confident Words Operations

    async def count_confident_words(self, chat_id: int) -> int:
        """Count words at stage 5+ (Confident and above).

        Args:
            chat_id: Telegram chat ID

        Returns:
            Count of confident words
        """
        query = """
            SELECT COUNT(*) as count
            FROM word_practice
            WHERE chat_id = $1 AND stage >= 5 AND deleted = FALSE
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id)
            return row["count"] if row else 0
