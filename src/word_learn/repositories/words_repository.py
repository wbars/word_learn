"""Repository for word-related database operations."""
from typing import Optional

from word_learn.database import Database
from word_learn.models import Word


class WordsRepository:
    """Repository for managing words in the database."""

    async def add_word(self, translations: dict[str, str]) -> Word:
        """Add a new word with translations.

        Args:
            translations: Dict mapping language codes to translations
                         e.g., {"en": "cat", "nl": "kat"}

        Returns:
            Created Word object
        """
        # Build dynamic query based on provided translations
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

    async def get_word_by_id(self, word_id: int) -> Optional[Word]:
        """Get a word by its ID.

        Args:
            word_id: Word ID

        Returns:
            Word object or None if not found
        """
        query = "SELECT id, en, nl, ru FROM words WHERE id = $1"

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, word_id)
            if row:
                return Word.from_row(dict(row))
            return None

    async def get_words_to_add(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[Word]:
        """Get words available for user to add to their practice.

        Returns words that the user hasn't:
        - Already added to practice
        - Already skipped

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of words to return

        Returns:
            List of available Word objects
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

    async def is_word_skipped(self, chat_id: int, word_id: int) -> bool:
        """Check if a word is in user's skiplist.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID

        Returns:
            True if word is skipped
        """
        query = """
            SELECT 1 FROM word_skiplist
            WHERE chat_id = $1 AND word_id = $2
        """

        async with Database.connection() as conn:
            row = await conn.fetchrow(query, chat_id, word_id)
            return row is not None
