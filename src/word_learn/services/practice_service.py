"""Practice service for managing word learning sessions."""
import random
from datetime import date, datetime
from typing import Optional

from word_learn.config import Language, get_settings
from word_learn.models import PracticeWord, Word
from word_learn.services.spaced_repetition import (
    calculate_next_date,
    get_new_stage_correct,
    get_new_stage_incorrect,
)


class PracticeService:
    """Service for managing word practice operations."""

    def __init__(self, repository):
        """Initialize with repository instance.

        Args:
            repository: PracticeRepository instance for database operations
        """
        self.repository = repository
        self.settings = get_settings()

    async def add_custom_word(
        self,
        chat_id: int,
        target_word: str,
        source_word: str,
    ) -> tuple[Word, Word]:
        """Add a custom word with bidirectional translations.

        Creates two word entries and adds both to the user's practice queue:
        1. target_lang -> source_lang
        2. source_lang -> target_lang

        Args:
            chat_id: Telegram chat ID
            target_word: Word in target language
            source_word: Word in source language

        Returns:
            Tuple of (word1, word2) created
        """
        target_lang = self.settings.target_lang
        source_lang = self.settings.source_lang

        # Create first word: target -> source
        translations1 = {
            target_lang.column_name: target_word,
            source_lang.column_name: source_word,
        }
        word1 = await self.repository.add_word(translations1)
        await self.repository.add_to_practice(chat_id, [word1.id])

        # Create second word: source -> target (reversed)
        translations2 = {
            target_lang.column_name: source_word,
            source_lang.column_name: target_word,
        }
        word2 = await self.repository.add_word(translations2)
        await self.repository.add_to_practice(chat_id, [word2.id])

        return word1, word2

    async def get_daily_pool_count(self) -> int:
        """Get random count for daily practice pool.

        Returns:
            Random number between daily_pool_min and daily_pool_max
        """
        return random.randint(
            self.settings.daily_pool_min,
            self.settings.daily_pool_max,
        )

    async def create_daily_pool(self, chat_id: int) -> list[int]:
        """Create daily practice pool for a user.

        Selects a random subset (67-76) of due words for today's practice.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of word_practice IDs in today's pool
        """
        pool_size = await self.get_daily_pool_count()
        return await self.repository.create_today_practice(chat_id, pool_size)

    async def start_practice_session(
        self,
        chat_id: int,
    ) -> list[PracticeWord]:
        """Start a practice session for the user.

        Gets up to batch_size words from today's pool and adds them
        to the current practice session.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of PracticeWord objects for the session
        """
        # Ensure daily pool exists
        pool = await self.repository.get_today_practice(chat_id)
        if not pool:
            pool = await self.create_daily_pool(chat_id)

        # Get words to practice (up to batch size)
        words = await self.repository.get_words_to_practice(
            chat_id,
            limit=self.settings.practice_batch_size,
        )

        # Add to current practice session
        if words:
            word_ids = [w.word.id for w in words]
            await self.repository.start_practice(chat_id, word_ids)

        return words

    async def mark_correct(
        self,
        chat_id: int,
        word_id: int,
        today: Optional[date] = None,
    ) -> None:
        """Mark a word as correctly answered.

        Increments stage and calculates next review date.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            today: Optional date to use (defaults to current date)
        """
        if today is None:
            today = date.today()

        practice_word = await self.repository.get_practice_word(chat_id, word_id)
        old_stage = practice_word.stage
        new_stage = get_new_stage_correct(old_stage)
        next_date = calculate_next_date(today, new_stage)

        # Get word translations for session result
        word_source = practice_word.get_translation(self.settings.target_lang) or "?"
        word_target = practice_word.get_translation(self.settings.source_lang) or "?"

        # Save per-word result
        await self.repository.save_word_result(
            chat_id=chat_id,
            word_id=word_id,
            result="correct",
            old_stage=old_stage,
            new_stage=new_stage,
            word_source=word_source,
            word_target=word_target,
        )

        await self.repository.update_practice_word(
            chat_id,
            word_id,
            stage=new_stage,
            next_date=next_date,
        )
        await self.repository.increment_statistics(chat_id, correct=True)
        await self.repository.remove_from_current_practice(chat_id, word_id)

    async def mark_incorrect(
        self,
        chat_id: int,
        word_id: int,
        today: Optional[date] = None,
    ) -> None:
        """Mark a word as incorrectly answered.

        Resets stage to 1 and sets next review to tomorrow.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            today: Optional date to use (defaults to current date)
        """
        if today is None:
            today = date.today()

        practice_word = await self.repository.get_practice_word(chat_id, word_id)
        old_stage = practice_word.stage
        new_stage = get_new_stage_incorrect()
        next_date = calculate_next_date(today, new_stage)

        # Get word translations for session result
        word_source = practice_word.get_translation(self.settings.target_lang) or "?"
        word_target = practice_word.get_translation(self.settings.source_lang) or "?"

        # Save per-word result
        await self.repository.save_word_result(
            chat_id=chat_id,
            word_id=word_id,
            result="incorrect",
            old_stage=old_stage,
            new_stage=new_stage,
            word_source=word_source,
            word_target=word_target,
        )

        await self.repository.update_practice_word(
            chat_id,
            word_id,
            stage=new_stage,
            next_date=next_date,
        )
        await self.repository.increment_statistics(chat_id, correct=False)
        await self.repository.remove_from_current_practice(chat_id, word_id)

    async def mark_deleted(self, chat_id: int, word_id: int) -> None:
        """Mark a word as deleted (soft delete).

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
        """
        practice_word = await self.repository.get_practice_word(chat_id, word_id)
        old_stage = practice_word.stage

        # Get word translations for session result
        word_source = practice_word.get_translation(self.settings.target_lang) or "?"
        word_target = practice_word.get_translation(self.settings.source_lang) or "?"

        # Save per-word result (new_stage=None for deleted)
        await self.repository.save_word_result(
            chat_id=chat_id,
            word_id=word_id,
            result="deleted",
            old_stage=old_stage,
            new_stage=None,
            word_source=word_source,
            word_target=word_target,
        )

        await self.repository.mark_deleted(chat_id, word_id)
        await self.repository.remove_from_current_practice(chat_id, word_id)

    def parse_word_input(self, text: str) -> Optional[tuple[str, str]]:
        """Parse user input for adding a word.

        Supports two formats:
        - "word1, word2" (comma-separated)
        - "word1 word2" (single space, no commas)

        Args:
            text: User input text

        Returns:
            Tuple of (word1, word2) or None if invalid format
        """
        text = text.strip()

        if "," in text:
            # Comma-separated format
            parts = text.split(",", 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
        else:
            # Single space format (only valid if exactly one space)
            if text.count(" ") == 1:
                parts = text.split(" ")
                return parts[0].strip(), parts[1].strip()

        return None
