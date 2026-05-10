"""Admin vocabulary course seeding for Dutch-English batches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from word_learn.config import get_settings
from word_learn.database import Database

COURSE_ID = "nl_en_a0_a2"


@dataclass(frozen=True)
class VocabularyEntry:
    """One Dutch-English word pair assigned to a numbered batch."""

    batch: int
    level: str
    nl: str
    en: str


@dataclass(frozen=True)
class BatchAddResult:
    """Result of adding one vocabulary batch to a user."""

    course_id: str
    batch: int
    total_batches: int
    level: str
    pairs: list[VocabularyEntry]
    inserted_pairs: int
    inserted_cards: int
    skipped_pairs: int


@dataclass(frozen=True)
class BatchStatus:
    """Current progress for a user's vocabulary course."""

    course_id: str
    last_added_batch: int
    total_batches: int
    active_cards: int
    next_batch: int | None


@dataclass(frozen=True)
class ResetResult:
    """Counts removed while resetting a user's learning state."""

    word_practice_marked_deleted: int
    current_practice: int
    today_practice: int
    current_practice_stats: int
    word_skiplist: int
    session_word_results: int
    practice_streaks: int
    course_progress: int


def resolve_batches_path(path_value: str) -> Path:
    """Resolve a configured batch file path."""
    path = Path(path_value)
    if path.is_absolute():
        return path

    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path

    package_root_path = Path(__file__).resolve().parents[3] / path
    if package_root_path.exists():
        return package_root_path

    return cwd_path


def load_vocabulary_entries(path: Path) -> list[VocabularyEntry]:
    """Load course entries from a TSV file.

    Expected columns: batch, level, nl, en. Lines starting with # are ignored.
    """
    entries: list[VocabularyEntry] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) != 4:
                raise ValueError(f"{path}:{line_number}: expected 4 tab-separated columns")

            batch_text, level, nl, en = [part.strip() for part in parts]
            if batch_text == "batch":
                continue

            if not level or not nl or not en:
                raise ValueError(f"{path}:{line_number}: empty level, Dutch, or English value")

            try:
                batch = int(batch_text)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid batch number {batch_text!r}") from exc

            if batch <= 0:
                raise ValueError(f"{path}:{line_number}: batch must be positive")

            entries.append(VocabularyEntry(batch=batch, level=level, nl=nl, en=en))

    if not entries:
        raise ValueError(f"{path}: no vocabulary entries found")

    return entries


def total_batches(entries: Iterable[VocabularyEntry]) -> int:
    """Return the highest batch number in a course."""
    return max(entry.batch for entry in entries)


async def get_or_insert_word_id(conn, nl: str, en: str) -> int:
    """Return an existing word ID for a pair, or insert a new word row."""
    word_id = await conn.fetchval(
        """
        SELECT id
        FROM words
        WHERE nl = $1 AND en = $2
        LIMIT 1
        """,
        nl,
        en,
    )
    if word_id is not None:
        return word_id

    return await conn.fetchval(
        """
        INSERT INTO words (nl, en)
        VALUES ($1, $2)
        RETURNING id
        """,
        nl,
        en,
    )


class VocabularyBatchService:
    """Adds curated course batches to one user's practice queue."""

    def __init__(self, batches_path: Path | None = None) -> None:
        settings = get_settings()
        self.course_id = COURSE_ID
        self.batches_path = batches_path or resolve_batches_path(settings.vocabulary_batches_file)

    def load_entries(self) -> list[VocabularyEntry]:
        """Load entries from the configured course file."""
        return load_vocabulary_entries(self.batches_path)

    async def ensure_progress_table(self) -> None:
        """Create the progress table for deployments that predate migration 005."""
        query = """
            CREATE TABLE IF NOT EXISTS vocabulary_course_progress (
                chat_id BIGINT NOT NULL,
                course_id TEXT NOT NULL,
                last_added_batch INTEGER NOT NULL DEFAULT 0,
                last_added_at TIMESTAMPTZ,
                PRIMARY KEY (chat_id, course_id)
            )
        """

        async with Database.connection() as conn:
            await conn.execute(query)

    async def get_status(self, chat_id: int) -> BatchStatus:
        """Return user's course progress and active practice card count."""
        entries = self.load_entries()
        total = total_batches(entries)
        await self.ensure_progress_table()

        query = """
            SELECT last_added_batch
            FROM vocabulary_course_progress
            WHERE chat_id = $1 AND course_id = $2
        """
        count_query = """
            SELECT COUNT(*)
            FROM word_practice
            WHERE chat_id = $1 AND deleted = FALSE
        """

        async with Database.connection() as conn:
            last_added_batch = await conn.fetchval(query, chat_id, self.course_id) or 0
            active_cards = await conn.fetchval(count_query, chat_id) or 0

        next_batch = last_added_batch + 1 if last_added_batch < total else None
        return BatchStatus(
            course_id=self.course_id,
            last_added_batch=last_added_batch,
            total_batches=total,
            active_cards=active_cards,
            next_batch=next_batch,
        )

    async def add_next_batch(self, chat_id: int) -> BatchAddResult | None:
        """Add the next course batch to a user's practice queue.

        Each pair creates two cards: Dutch -> English and English -> Dutch.
        """
        entries = self.load_entries()
        total = total_batches(entries)
        await self.ensure_progress_table()

        async with Database.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO vocabulary_course_progress
                    (chat_id, course_id, last_added_batch, last_added_at)
                VALUES ($1, $2, 0, NULL)
                ON CONFLICT DO NOTHING
                """,
                chat_id,
                self.course_id,
            )
            last_added_batch = await conn.fetchval(
                """
                SELECT last_added_batch
                FROM vocabulary_course_progress
                WHERE chat_id = $1 AND course_id = $2
                FOR UPDATE
                """,
                chat_id,
                self.course_id,
            )

            next_batch = last_added_batch + 1
            if next_batch > total:
                return None

            pairs = [entry for entry in entries if entry.batch == next_batch]
            if not pairs:
                raise ValueError(f"No vocabulary entries for batch {next_batch}")

            now = datetime.now(get_settings().timezone)
            inserted_pairs = 0
            inserted_cards = 0
            skipped_pairs = 0
            inserted_practice_ids: list[int] = []

            for entry in pairs:
                exists = await conn.fetchval(
                    """
                    SELECT 1
                    FROM word_practice wp
                    JOIN words w ON w.id = wp.word_id
                    WHERE wp.chat_id = $1
                      AND wp.deleted = FALSE
                      AND (
                          (w.nl = $2 AND w.en = $3)
                          OR (w.nl = $3 AND w.en = $2)
                      )
                    LIMIT 1
                    """,
                    chat_id,
                    entry.nl,
                    entry.en,
                )

                if exists:
                    skipped_pairs += 1
                    continue

                nl_to_en_id = await get_or_insert_word_id(conn, entry.nl, entry.en)
                en_to_nl_id = await get_or_insert_word_id(conn, entry.en, entry.nl)
                for word_id in (nl_to_en_id, en_to_nl_id):
                    practice_id = await conn.fetchval(
                        """
                        INSERT INTO word_practice
                            (word_id, chat_id, next_date, stage, deleted, consecutive_failures)
                        VALUES ($1, $2, $3, 0, FALSE, 0)
                        RETURNING id
                        """,
                        word_id,
                        chat_id,
                        now,
                    )
                    if practice_id is not None:
                        inserted_practice_ids.append(practice_id)

                inserted_pairs += 1
                inserted_cards += 2

            if inserted_practice_ids:
                await conn.executemany(
                    """
                    INSERT INTO today_practice (word_practice_id, date)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    [(practice_id, now.date()) for practice_id in inserted_practice_ids],
                )

            await conn.execute(
                """
                UPDATE vocabulary_course_progress
                SET last_added_batch = $3, last_added_at = $4
                WHERE chat_id = $1 AND course_id = $2
                """,
                chat_id,
                self.course_id,
                next_batch,
                now,
            )

            return BatchAddResult(
                course_id=self.course_id,
                batch=next_batch,
                total_batches=total,
                level=pairs[0].level,
                pairs=pairs,
                inserted_pairs=inserted_pairs,
                inserted_cards=inserted_cards,
                skipped_pairs=skipped_pairs,
            )

    async def reset_user_words(self, chat_id: int) -> ResetResult:
        """Soft-delete all practice cards for one chat and reset course progress."""
        await self.ensure_progress_table()

        async with Database.transaction() as conn:
            today_practice = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM today_practice tp
                    USING word_practice wp
                    WHERE tp.word_practice_id = wp.id AND wp.chat_id = $1
                    RETURNING tp.word_practice_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            current_practice = await conn.fetchval(
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
            current_practice_stats = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM current_practice_stats
                    WHERE chat_id = $1
                    RETURNING chat_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            word_skiplist = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM word_skiplist
                    WHERE chat_id = $1
                    RETURNING word_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            session_word_results = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM session_word_results
                    WHERE chat_id = $1
                    RETURNING word_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            practice_streaks = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM practice_streaks
                    WHERE chat_id = $1
                    RETURNING chat_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
            )
            word_practice_marked_deleted = await conn.fetchval(
                """
                WITH updated_rows AS (
                    UPDATE word_practice
                    SET deleted = TRUE
                    WHERE chat_id = $1 AND deleted = FALSE
                    RETURNING id
                )
                SELECT COUNT(*) FROM updated_rows
                """,
                chat_id,
            )
            course_progress = await conn.fetchval(
                """
                WITH deleted_rows AS (
                    DELETE FROM vocabulary_course_progress
                    WHERE chat_id = $1 AND course_id = $2
                    RETURNING course_id
                )
                SELECT COUNT(*) FROM deleted_rows
                """,
                chat_id,
                self.course_id,
            )

            return ResetResult(
                word_practice_marked_deleted=word_practice_marked_deleted or 0,
                current_practice=current_practice or 0,
                today_practice=today_practice or 0,
                current_practice_stats=current_practice_stats or 0,
                word_skiplist=word_skiplist or 0,
                session_word_results=session_word_results or 0,
                practice_streaks=practice_streaks or 0,
                course_progress=course_progress or 0,
            )
