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
        reverse: Optional[bool] = None,
    ) -> tuple[Word, Optional[Word]]:
        """Add a custom word, by default with its reversed card.

        Creates the word entry (target_lang -> source_lang) and adds it to the
        user's practice queue. Unless the chat switched reverse cards off
        (``/reverse_cards_off``), a second, reversed entry
        (source_lang -> target_lang) is created and queued as well.

        Args:
            chat_id: Telegram chat ID
            target_word: Word in target language
            source_word: Word in source language
            reverse: Whether to also create the reversed card. None (default)
                reads the chat's reverse-cards setting, which is on unless the
                chat turned it off.

        Returns:
            Tuple of (word1, word2); word2 is None when no reversed card was
            created
        """
        if reverse is None:
            reverse = await self.repository.get_reverse_cards(chat_id)

        target_lang = self.settings.target_lang
        source_lang = self.settings.source_lang

        # Create first word: target -> source
        translations1 = {
            target_lang.column_name: target_word,
            source_lang.column_name: source_word,
        }
        word1 = await self.repository.add_word(translations1)
        await self.repository.add_to_practice(chat_id, [word1.id])

        if not reverse:
            return word1, None

        # Create second word: source -> target (reversed)
        translations2 = {
            target_lang.column_name: source_word,
            source_lang.column_name: target_word,
        }
        word2 = await self.repository.add_word(translations2)
        await self.repository.add_to_practice(chat_id, [word2.id])

        return word1, word2

    async def add_custom_words(
        self,
        chat_id: int,
        pairs: list[tuple[str, str]],
    ) -> tuple[int, int]:
        """Add several custom word pairs at once.

        Pairs whose exact text is already an active card for the chat are
        skipped, so pasting an overlapping list twice does not double cards.
        The chat's reverse-cards setting is read once for the whole list.

        Args:
            chat_id: Telegram chat ID
            pairs: (target_word, source_word) tuples, in message order

        Returns:
            Tuple of (pairs_added, pairs_skipped_as_duplicates)
        """
        reverse = await self.repository.get_reverse_cards(chat_id)
        added = skipped = 0
        seen: set[tuple[str, str]] = set()
        for target_word, source_word in pairs:
            key = (target_word.casefold(), source_word.casefold())
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            if await self.repository.has_active_custom_word(
                chat_id,
                {
                    self.settings.target_lang.column_name: target_word,
                    self.settings.source_lang.column_name: source_word,
                },
            ):
                skipped += 1
                continue
            await self.add_custom_word(chat_id, target_word, source_word, reverse=reverse)
            added += 1
        return added, skipped

    async def get_daily_pool_count(self) -> int:
        """Get random count for daily practice pool.

        Returns:
            Random number between daily_pool_min and daily_pool_max
        """
        return random.randint(
            self.settings.daily_pool_min,
            self.settings.daily_pool_max,
        )

    async def get_daily_pool_size(self, chat_id: int) -> Optional[int]:
        """Get the cap for the chat's next daily pool.

        Args:
            chat_id: Telegram chat ID

        Returns:
            A random 67-76 while the chat's daily limit is on (the default),
            None when the chat switched it off with /daily_limit_off
        """
        if await self.repository.get_daily_limit(chat_id):
            return await self.get_daily_pool_count()
        return None

    async def create_daily_pool(self, chat_id: int) -> list[int]:
        """Create daily practice pool for a user.

        Selects a random subset (67-76) of due words for today's practice, or
        every due word when the chat switched the daily limit off.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of word_practice IDs in today's pool
        """
        pool_size = await self.get_daily_pool_size(chat_id)
        return await self.repository.create_today_practice(chat_id, pool_size)

    async def fill_today_pool(self, chat_id: int) -> int:
        """Put every due word into today's pool right away.

        Called when the chat switches the daily limit off, so the change is
        visible immediately instead of after the current pool runs out. Cards
        already in the pool stay; the pool is created if it does not exist.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Number of cards in today's pool afterwards
        """
        await self.repository.create_today_practice(chat_id, limit=None)
        return await self.repository.count_words_to_practice(chat_id)

    async def trim_today_pool(self, chat_id: int) -> tuple[int, int]:
        """Shrink today's pool back to a daily-limit size.

        Called when the chat switches the daily limit back on. Cards of the
        running session are kept; removed cards stay due and return in the
        next pool. Does nothing when the pool already holds at most
        ``daily_pool_max`` cards, so a pool that was built with the limit on
        is never re-rolled to a smaller random size.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Tuple of (cards_removed, cards_remaining_in_pool)
        """
        current = await self.repository.count_words_to_practice(chat_id)
        if current <= self.settings.daily_pool_max:
            return 0, current

        limit = await self.get_daily_pool_count()
        removed = await self.repository.trim_today_practice(chat_id, limit)
        # Recount instead of subtracting: the trim also drops stale pool rows
        # of deleted/archived cards, which the count above never included.
        remaining = await self.repository.count_words_to_practice(chat_id)
        return removed, remaining

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
    ) -> tuple[int, int]:
        """Mark a word as correctly answered.

        Increments stage and calculates next review date.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            today: Optional date to use (defaults to current date in configured timezone)

        Returns:
            Tuple of (old_stage, new_stage)
        """
        if today is None:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(self.settings.tz)).date()

        practice_word = await self.repository.get_practice_word(chat_id, word_id)
        old_stage = practice_word.stage
        new_stage = get_new_stage_correct(old_stage)
        next_date = calculate_next_date(today, new_stage, tz=self.settings.timezone)

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
        await self.repository.reset_consecutive_failures(chat_id, word_id)
        await self.repository.increment_statistics(chat_id, correct=True)
        await self.repository.remove_from_current_practice(chat_id, word_id)
        await self.repository.remove_from_today_practice(chat_id, word_id)

        return old_stage, new_stage

    async def mark_incorrect(
        self,
        chat_id: int,
        word_id: int,
        today: Optional[date] = None,
    ) -> tuple[int, int]:
        """Mark a word as incorrectly answered.

        Resets stage to 1 and sets next review to tomorrow.

        Args:
            chat_id: Telegram chat ID
            word_id: Word ID
            today: Optional date to use (defaults to current date in configured timezone)

        Returns:
            Tuple of (old_stage, new_stage)
        """
        if today is None:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(self.settings.tz)).date()

        practice_word = await self.repository.get_practice_word(chat_id, word_id)
        old_stage = practice_word.stage
        new_stage = get_new_stage_incorrect()
        next_date = calculate_next_date(today, new_stage, tz=self.settings.timezone)

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
        await self.repository.increment_consecutive_failures(chat_id, word_id)
        await self.repository.increment_statistics(chat_id, correct=False)
        await self.repository.remove_from_current_practice(chat_id, word_id)
        await self.repository.remove_from_today_practice(chat_id, word_id)

        return old_stage, new_stage

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
        await self.repository.remove_from_today_practice(chat_id, word_id)

    def parse_batch_input(self, text: str) -> tuple[list[tuple[str, str]], list[str]]:
        """Parse a multi-line message into word pairs, one pair per line.

        Blank lines and lines starting with ``#`` (block headers/comments in a
        pasted list) are ignored. Every other line goes through
        :meth:`parse_word_input`.

        Args:
            text: Multi-line user input

        Returns:
            Tuple of (parsed pairs in order, lines that could not be parsed)
        """
        pairs: list[tuple[str, str]] = []
        rejected: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parsed = self.parse_word_input(line)
            if parsed is None or not parsed[0] or not parsed[1]:
                rejected.append(line)
            else:
                pairs.append(parsed)
        return pairs, rejected

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
