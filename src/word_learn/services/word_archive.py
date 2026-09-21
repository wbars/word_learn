"""Reversible archive of one chat's practice cards.

``/archive_words`` parks every active card of a chat so the user can build a
fresh word list from scratch; ``/unarchive_words`` brings the most recently
archived cards back next to whatever was added in the meantime (or all of
them with ``/unarchive_words all``).

Archiving stamps ``word_practice.archived_at`` and leaves ``stage`` and
``consecutive_failures`` alone. Restoring clears the stamp and moves each
card's ``next_date`` forward by the number of days it spent archived, so the
review schedule resumes where it paused instead of dumping every card that
came due meanwhile into the pool at once and crowding out the new words.
Cards that were genuinely forgotten still self-correct through the normal
Incorrect -> stage 1 path.

Each ``/archive_words`` call is one *generation*: all cards it archives share
the same ``archived_at`` value. ``/unarchive_words`` pops the newest
generation, so parking list B to try list C does not also bring back list A.

Card states (``word_practice``):

- active:   ``deleted = FALSE AND archived_at IS NULL``
- archived: ``deleted = FALSE AND archived_at IS NOT NULL``
- deleted:  ``deleted = TRUE`` (``archived_at`` is irrelevant)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from word_learn.config import get_settings
from word_learn.database import Database


@dataclass(frozen=True)
class ArchiveResult:
    """Outcome of archiving a chat's active cards."""

    archived_cards: int
    previously_archived_cards: int
    today_practice_removed: int
    current_practice_removed: int

    @property
    def total_archived_cards(self) -> int:
        """Cards in the archive after this call (old generations + this one)."""
        return self.archived_cards + self.previously_archived_cards


@dataclass(frozen=True)
class RestoredGeneration:
    """One archive generation brought back by ``unarchive``."""

    archived_at: datetime
    cards: int
    shifted_days: int


@dataclass(frozen=True)
class UnarchiveResult:
    """Outcome of restoring one or all archive generations."""

    generations: list[RestoredGeneration] = field(default_factory=list)
    active_cards: int = 0
    remaining_archived_cards: int = 0
    remaining_generations: int = 0

    @property
    def restored_cards(self) -> int:
        return sum(generation.cards for generation in self.generations)


@dataclass(frozen=True)
class ArchiveStatus:
    """Current split between active and archived cards for a chat."""

    active_cards: int
    archived_cards: int
    generations: int
    newest_archived_at: datetime | None


_COUNT_ACTIVE = """
    SELECT COUNT(*)
    FROM word_practice
    WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NULL
"""

_COUNT_ARCHIVED = """
    SELECT COUNT(*)
    FROM word_practice
    WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NOT NULL
"""

_COUNT_GENERATIONS = """
    SELECT COUNT(DISTINCT archived_at)
    FROM word_practice
    WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NOT NULL
"""

_ARCHIVED_GENERATIONS_NEWEST_FIRST = """
    SELECT archived_at
    FROM word_practice
    WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NOT NULL
    GROUP BY archived_at
    ORDER BY archived_at DESC
"""


def pause_days(archived_at: datetime, now: datetime) -> int:
    """Whole calendar days (in ``now``'s timezone) a generation spent archived."""
    tz = now.tzinfo
    return max(0, (now.date() - archived_at.astimezone(tz).date()).days)


class WordArchiveService:
    """Archive and restore the practice cards of a single chat."""

    async def archive_all(self, chat_id: int) -> ArchiveResult:
        """Archive every active card of the chat as one new generation.

        Runs in one transaction. Besides stamping ``archived_at`` it clears the
        chat's in-flight practice state (today's pool entries for the archived
        cards, the current session, its statistics and per-word results) so the
        user starts from a clean slate. When nothing is active it is a no-op.
        """
        now = datetime.now(get_settings().timezone)

        async with Database.transaction() as conn:
            previously_archived = await conn.fetchval(_COUNT_ARCHIVED, chat_id) or 0

            active_ids = [
                row["id"]
                for row in await conn.fetch(
                    """
                    SELECT id
                    FROM word_practice
                    WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NULL
                    FOR UPDATE
                    """,
                    chat_id,
                )
            ]
            if not active_ids:
                return ArchiveResult(
                    archived_cards=0,
                    previously_archived_cards=previously_archived,
                    today_practice_removed=0,
                    current_practice_removed=0,
                )

            today_practice_removed = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM today_practice
                    WHERE word_practice_id = ANY($1::int[])
                    RETURNING word_practice_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                active_ids,
            )
            current_practice_removed = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM current_practice
                    WHERE chat_id = $1
                    RETURNING word_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            await conn.execute(
                "DELETE FROM current_practice_stats WHERE chat_id = $1",
                chat_id,
            )
            await conn.execute(
                "DELETE FROM session_word_results WHERE chat_id = $1",
                chat_id,
            )
            archived_cards = await conn.fetchval(
                """
                WITH updated_rows AS (
                    UPDATE word_practice
                    SET archived_at = $2
                    WHERE id = ANY($1::int[])
                    RETURNING id
                )
                SELECT COUNT(*) FROM updated_rows
                """,
                active_ids,
                now,
            )

            return ArchiveResult(
                archived_cards=archived_cards or 0,
                previously_archived_cards=previously_archived,
                today_practice_removed=today_practice_removed or 0,
                current_practice_removed=current_practice_removed or 0,
            )

    async def unarchive(self, chat_id: int, *, everything: bool = False) -> UnarchiveResult:
        """Restore the newest archive generation (or every generation).

        For each restored generation ``next_date`` is moved forward by the
        whole days it spent archived (computed in the configured timezone and
        applied on the local calendar, so cards stay at local midnight across
        DST changes). Restored cards are not pushed into today's pool; they
        join the next pool the practice flow creates once the current one runs
        out, so they line up behind whatever the user is practicing right now.
        """
        settings = get_settings()
        now = datetime.now(settings.timezone)

        async with Database.transaction() as conn:
            stamps = [
                row["archived_at"]
                for row in await conn.fetch(_ARCHIVED_GENERATIONS_NEWEST_FIRST, chat_id)
            ]
            if not everything:
                stamps = stamps[:1]

            generations: list[RestoredGeneration] = []
            for archived_at in stamps:
                days = pause_days(archived_at, now)
                if days:
                    restored = await conn.fetchval(
                        """
                        WITH updated_rows AS (
                            UPDATE word_practice
                            SET archived_at = NULL,
                                next_date = ((next_date AT TIME ZONE $3) + $4::interval)
                                            AT TIME ZONE $3
                            WHERE chat_id = $1 AND deleted = FALSE AND archived_at = $2
                            RETURNING id
                        )
                        SELECT COUNT(*) FROM updated_rows
                        """,
                        chat_id,
                        archived_at,
                        settings.tz,
                        timedelta(days=days),
                    )
                else:
                    restored = await conn.fetchval(
                        """
                        WITH updated_rows AS (
                            UPDATE word_practice
                            SET archived_at = NULL
                            WHERE chat_id = $1 AND deleted = FALSE AND archived_at = $2
                            RETURNING id
                        )
                        SELECT COUNT(*) FROM updated_rows
                        """,
                        chat_id,
                        archived_at,
                    )
                generations.append(
                    RestoredGeneration(
                        archived_at=archived_at.astimezone(settings.timezone),
                        cards=restored or 0,
                        shifted_days=days,
                    )
                )

            active_cards = await conn.fetchval(_COUNT_ACTIVE, chat_id)
            remaining_cards = await conn.fetchval(_COUNT_ARCHIVED, chat_id)
            remaining_generations = await conn.fetchval(_COUNT_GENERATIONS, chat_id)

            return UnarchiveResult(
                generations=generations,
                active_cards=active_cards or 0,
                remaining_archived_cards=remaining_cards or 0,
                remaining_generations=remaining_generations or 0,
            )

    async def get_status(self, chat_id: int) -> ArchiveStatus:
        """Return active/archived card counts and the number of generations."""
        settings = get_settings()

        async with Database.connection() as conn:
            active_cards = await conn.fetchval(_COUNT_ACTIVE, chat_id)
            archived_cards = await conn.fetchval(_COUNT_ARCHIVED, chat_id)
            generations = await conn.fetchval(_COUNT_GENERATIONS, chat_id)
            newest = await conn.fetchval(
                """
                SELECT MAX(archived_at)
                FROM word_practice
                WHERE chat_id = $1 AND deleted = FALSE AND archived_at IS NOT NULL
                """,
                chat_id,
            )

        return ArchiveStatus(
            active_cards=active_cards or 0,
            archived_cards=archived_cards or 0,
            generations=generations or 0,
            newest_archived_at=newest.astimezone(settings.timezone) if newest else None,
        )
