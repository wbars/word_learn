"""Integration tests for the reversible word archive (require a test database)."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from word_learn.config import get_settings
from word_learn.services import word_archive
from word_learn.services.vocabulary_batches import VocabularyBatchService
from word_learn.services.word_archive import WordArchiveService, pause_days

OTHER_CHAT_ID = 67890
TZ = ZoneInfo("Europe/Amsterdam")


@pytest.fixture(autouse=True)
def _amsterdam_settings():
    """Pin the service's calendar so the DST assertions do not depend on $TZ."""
    settings = get_settings().model_copy(update={"tz": "Europe/Amsterdam"})
    with patch.object(word_archive, "get_settings", return_value=settings):
        yield


@pytest_asyncio.fixture
async def archive_service(db_pool) -> WordArchiveService:
    return WordArchiveService()


async def _add_cards(practice_repository, chat_id: int, count: int, prefix: str = "w") -> list[int]:
    """Create ``count`` words and add each to the chat's practice; return word ids."""
    word_ids = []
    for i in range(count):
        word = await practice_repository.add_word({"en": f"{prefix}{i}", "ru": f"r{i}"})
        await practice_repository.add_to_practice(chat_id, [word.id])
        word_ids.append(word.id)
    return word_ids


def _frozen_now(moment: datetime):
    """Patch the service's clock so archive/unarchive happen at ``moment``."""

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is None else moment.astimezone(tz)

    return patch.object(word_archive, "datetime", _FrozenDatetime)


class TestPauseDays:
    def test_same_day_is_zero(self):
        archived = datetime(2026, 6, 1, 9, 0, tzinfo=TZ)
        assert pause_days(archived, datetime(2026, 6, 1, 23, 0, tzinfo=TZ)) == 0

    def test_counts_local_calendar_days(self):
        # 23:30 local, stored as UTC 21:30; the next local morning is one day later.
        archived = datetime(2026, 6, 1, 23, 30, tzinfo=TZ)
        assert pause_days(archived, datetime(2026, 6, 2, 8, 0, tzinfo=TZ)) == 1
        assert pause_days(archived, datetime(2026, 6, 22, 8, 0, tzinfo=TZ)) == 21

    def test_never_negative(self):
        archived = datetime(2026, 6, 5, tzinfo=TZ)
        assert pause_days(archived, datetime(2026, 6, 1, tzinfo=TZ)) == 0


class TestArchiveAll:
    @pytest.mark.asyncio
    async def test_noop_when_nothing_active(self, archive_service, chat_id):
        result = await archive_service.archive_all(chat_id)

        assert result.archived_cards == 0
        assert result.previously_archived_cards == 0
        assert result.total_archived_cards == 0

    @pytest.mark.asyncio
    async def test_archives_active_cards_only(self, archive_service, practice_repository, chat_id):
        word_ids = await _add_cards(practice_repository, chat_id, 4)
        await practice_repository.mark_deleted(chat_id, word_ids[3])

        result = await archive_service.archive_all(chat_id)

        assert result.archived_cards == 3
        status = await archive_service.get_status(chat_id)
        assert status.active_cards == 0
        assert status.archived_cards == 3
        assert status.generations == 1
        assert status.newest_archived_at is not None
        assert status.newest_archived_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_archived_cards_are_hidden_from_every_active_query(
        self, archive_service, practice_repository, chat_id
    ):
        word_ids = await _add_cards(practice_repository, chat_id, 3)
        await practice_repository.create_today_practice(chat_id, limit=10)
        await practice_repository.start_practice(chat_id, word_ids)

        await archive_service.archive_all(chat_id)

        assert await practice_repository.get_practice_word(chat_id, word_ids[0]) is None
        assert await practice_repository.get_next_practice_word(chat_id) is None
        assert await practice_repository.count_words_to_practice(chat_id) == 0
        assert await practice_repository.count_all_due_words(chat_id) == 0
        assert await practice_repository.count_confident_words(chat_id) == 0
        assert await practice_repository.get_words_to_practice(chat_id) == []
        assert await practice_repository.create_today_practice(chat_id, limit=10) == []
        # start_practice_session relies on this to know a fresh pool is needed
        assert await practice_repository.get_today_practice(chat_id) == []

    @pytest.mark.asyncio
    async def test_stale_pool_row_for_archived_card_does_not_block_a_new_pool(
        self, archive_service, practice_repository, chat_id, db_pool
    ):
        """Simulates /practice racing /archive_words and re-inserting a pool row."""
        word_ids = await _add_cards(practice_repository, chat_id, 2)
        await archive_service.archive_all(chat_id)
        new_ids = await _add_cards(practice_repository, chat_id, 1, prefix="new")
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO today_practice (word_practice_id, date)
                SELECT id, CURRENT_DATE FROM word_practice
                WHERE chat_id = $1 AND word_id = $2
                """,
                chat_id,
                word_ids[0],
            )

        assert await practice_repository.get_today_practice(chat_id) == []
        pool = await practice_repository.create_today_practice(chat_id, limit=10)
        assert len(pool) == 1
        assert await practice_repository.count_words_to_practice(chat_id) == 1
        assert (await practice_repository.get_words_to_practice(chat_id))[0].word.id == new_ids[0]

    @pytest.mark.asyncio
    async def test_clears_session_state(self, archive_service, practice_repository, chat_id):
        word_ids = await _add_cards(practice_repository, chat_id, 3)
        await practice_repository.create_today_practice(chat_id, limit=10)
        await practice_repository.start_practice(chat_id, word_ids[:2])
        await practice_repository.increment_statistics(chat_id, correct=True)
        await practice_repository.save_word_result(
            chat_id, word_ids[0], "correct", 0, 1, "w0", "r0"
        )

        result = await archive_service.archive_all(chat_id)

        assert result.today_practice_removed == 3
        assert result.current_practice_removed == 2
        stats = await practice_repository.get_statistics(chat_id)
        assert stats.total == 0
        assert await practice_repository.get_session_results(chat_id) == []

    @pytest.mark.asyncio
    async def test_other_chats_are_untouched(self, archive_service, practice_repository, chat_id):
        await _add_cards(practice_repository, chat_id, 2)
        other_ids = await _add_cards(practice_repository, OTHER_CHAT_ID, 2, prefix="o")
        await practice_repository.create_today_practice(OTHER_CHAT_ID, limit=10)

        await archive_service.archive_all(chat_id)

        assert await practice_repository.count_all_due_words(OTHER_CHAT_ID) == 2
        assert await practice_repository.count_words_to_practice(OTHER_CHAT_ID) == 2
        assert await practice_repository.get_practice_word(OTHER_CHAT_ID, other_ids[0]) is not None
        assert (await archive_service.get_status(OTHER_CHAT_ID)).archived_cards == 0

    @pytest.mark.asyncio
    async def test_second_archive_creates_a_new_generation(
        self, archive_service, practice_repository, chat_id
    ):
        await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        await _add_cards(practice_repository, chat_id, 2, prefix="new")

        result = await archive_service.archive_all(chat_id)

        assert result.archived_cards == 2
        assert result.previously_archived_cards == 3
        assert result.total_archived_cards == 5
        status = await archive_service.get_status(chat_id)
        assert status.active_cards == 0
        assert status.archived_cards == 5
        assert status.generations == 2

    @pytest.mark.asyncio
    async def test_does_not_touch_stage_or_failures(
        self, archive_service, practice_repository, chat_id
    ):
        word_ids = await _add_cards(practice_repository, chat_id, 1)
        next_date = datetime.now(TZ) + timedelta(days=7)
        await practice_repository.update_practice_word(
            chat_id, word_ids[0], stage=6, next_date=next_date
        )
        await practice_repository.increment_consecutive_failures(chat_id, word_ids[0])

        await archive_service.archive_all(chat_id)
        await archive_service.unarchive(chat_id)  # same day -> no date shift

        restored = await practice_repository.get_practice_word(chat_id, word_ids[0])
        assert restored is not None
        assert restored.stage == 6
        assert restored.next_date == next_date
        failures = await practice_repository.get_consecutive_failures(chat_id, word_ids)
        assert failures[word_ids[0]] == 1


class TestUnarchive:
    @pytest.mark.asyncio
    async def test_noop_when_nothing_archived(self, archive_service, practice_repository, chat_id):
        await _add_cards(practice_repository, chat_id, 2)

        result = await archive_service.unarchive(chat_id)

        assert result.restored_cards == 0
        assert result.generations == []
        assert result.active_cards == 2

    @pytest.mark.asyncio
    async def test_restores_next_to_current_words(
        self, archive_service, practice_repository, chat_id
    ):
        old_ids = await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        new_ids = await _add_cards(practice_repository, chat_id, 2, prefix="new")

        result = await archive_service.unarchive(chat_id)

        assert result.restored_cards == 3
        assert result.active_cards == 5
        assert result.remaining_archived_cards == 0
        assert result.remaining_generations == 0
        assert len(result.generations) == 1
        assert result.generations[0].shifted_days == 0
        for word_id in old_ids + new_ids:
            assert await practice_repository.get_practice_word(chat_id, word_id) is not None
        assert await practice_repository.count_all_due_words(chat_id) == 5
        status = await archive_service.get_status(chat_id)
        assert status.archived_cards == 0
        assert status.newest_archived_at is None

    @pytest.mark.asyncio
    async def test_deleted_cards_stay_deleted(self, archive_service, practice_repository, chat_id):
        word_ids = await _add_cards(practice_repository, chat_id, 2)
        await practice_repository.mark_deleted(chat_id, word_ids[1])
        await archive_service.archive_all(chat_id)

        result = await archive_service.unarchive(chat_id)

        assert result.restored_cards == 1
        assert await practice_repository.get_practice_word(chat_id, word_ids[0]) is not None
        assert await practice_repository.get_practice_word(chat_id, word_ids[1]) is None

    @pytest.mark.asyncio
    async def test_restored_cards_enter_the_next_daily_pool(
        self, archive_service, practice_repository, chat_id
    ):
        await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        await archive_service.unarchive(chat_id)

        pool = await practice_repository.create_today_practice(chat_id, limit=10)

        assert len(pool) == 3
        assert await practice_repository.count_words_to_practice(chat_id) == 3

    @pytest.mark.asyncio
    async def test_pops_newest_generation_first(
        self, archive_service, practice_repository, chat_id
    ):
        a_ids = await _add_cards(practice_repository, chat_id, 3, prefix="a")
        await archive_service.archive_all(chat_id)
        b_ids = await _add_cards(practice_repository, chat_id, 2, prefix="b")
        await archive_service.archive_all(chat_id)

        first = await archive_service.unarchive(chat_id)

        assert first.restored_cards == 2
        assert first.active_cards == 2
        assert first.remaining_archived_cards == 3
        assert first.remaining_generations == 1
        for word_id in b_ids:
            assert await practice_repository.get_practice_word(chat_id, word_id) is not None
        for word_id in a_ids:
            assert await practice_repository.get_practice_word(chat_id, word_id) is None

        second = await archive_service.unarchive(chat_id)

        assert second.restored_cards == 3
        assert second.active_cards == 5
        assert second.remaining_archived_cards == 0

    @pytest.mark.asyncio
    async def test_everything_restores_all_generations(
        self, archive_service, practice_repository, chat_id
    ):
        await _add_cards(practice_repository, chat_id, 3, prefix="a")
        await archive_service.archive_all(chat_id)
        await _add_cards(practice_repository, chat_id, 2, prefix="b")
        await archive_service.archive_all(chat_id)

        result = await archive_service.unarchive(chat_id, everything=True)

        assert result.restored_cards == 5
        assert len(result.generations) == 2
        assert [g.cards for g in result.generations] == [2, 3]  # newest first
        assert result.active_cards == 5
        assert result.remaining_archived_cards == 0

    @pytest.mark.asyncio
    async def test_shifts_next_date_by_pause_length_on_local_calendar(
        self, archive_service, practice_repository, chat_id
    ):
        word_ids = await _add_cards(practice_repository, chat_id, 2)
        # Card 0 was due at local midnight a day before the archive (overdue),
        # card 1 in a week. Archive on 15 Oct, restore on 5 Nov: 21 days that
        # cross the 25 Oct DST change in Europe/Amsterdam.
        archived_at = datetime(2026, 10, 15, 12, 0, tzinfo=TZ)
        restored_at = datetime(2026, 11, 5, 9, 30, tzinfo=TZ)
        due_0 = datetime(2026, 10, 14, 0, 0, tzinfo=TZ)
        due_1 = datetime(2026, 10, 22, 0, 0, tzinfo=TZ)
        await practice_repository.update_practice_word(chat_id, word_ids[0], stage=1, next_date=due_0)
        await practice_repository.update_practice_word(chat_id, word_ids[1], stage=4, next_date=due_1)

        with _frozen_now(archived_at):
            await archive_service.archive_all(chat_id)
        with _frozen_now(restored_at):
            result = await archive_service.unarchive(chat_id)

        assert result.generations[0].shifted_days == 21
        assert result.generations[0].archived_at == archived_at
        card_0 = await practice_repository.get_practice_word(chat_id, word_ids[0])
        card_1 = await practice_repository.get_practice_word(chat_id, word_ids[1])
        # Still local midnight on the shifted calendar day despite the DST change.
        assert card_0.next_date.astimezone(TZ) == datetime(2026, 11, 4, 0, 0, tzinfo=TZ)
        assert card_1.next_date.astimezone(TZ) == datetime(2026, 11, 12, 0, 0, tzinfo=TZ)
        # Stages are untouched by the pause.
        assert (card_0.stage, card_1.stage) == (1, 4)

    @pytest.mark.asyncio
    async def test_each_generation_shifts_by_its_own_pause(
        self, archive_service, practice_repository, chat_id
    ):
        a_ids = await _add_cards(practice_repository, chat_id, 1, prefix="a")
        due = datetime(2026, 6, 10, 0, 0, tzinfo=TZ)
        await practice_repository.update_practice_word(chat_id, a_ids[0], stage=2, next_date=due)
        with _frozen_now(datetime(2026, 6, 1, 10, 0, tzinfo=TZ)):
            await archive_service.archive_all(chat_id)

        b_ids = await _add_cards(practice_repository, chat_id, 1, prefix="b")
        await practice_repository.update_practice_word(chat_id, b_ids[0], stage=2, next_date=due)
        with _frozen_now(datetime(2026, 6, 11, 10, 0, tzinfo=TZ)):
            await archive_service.archive_all(chat_id)

        with _frozen_now(datetime(2026, 6, 21, 10, 0, tzinfo=TZ)):
            result = await archive_service.unarchive(chat_id, everything=True)

        assert [g.shifted_days for g in result.generations] == [10, 20]  # newest first
        card_a = await practice_repository.get_practice_word(chat_id, a_ids[0])
        card_b = await practice_repository.get_practice_word(chat_id, b_ids[0])
        assert card_a.next_date.astimezone(TZ) == due + timedelta(days=20)
        assert card_b.next_date.astimezone(TZ) == due + timedelta(days=10)


class TestArchiveStatus:
    @pytest.mark.asyncio
    async def test_empty_chat(self, archive_service, chat_id):
        status = await archive_service.get_status(chat_id)

        assert status.active_cards == 0
        assert status.archived_cards == 0
        assert status.generations == 0
        assert status.newest_archived_at is None

    @pytest.mark.asyncio
    async def test_counts_split(self, archive_service, practice_repository, chat_id):
        await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        await _add_cards(practice_repository, chat_id, 1, prefix="new")

        status = await archive_service.get_status(chat_id)

        assert status.active_cards == 1
        assert status.archived_cards == 3


class TestInterplayWithBatchCommands:
    @pytest.mark.asyncio
    async def test_batch_status_reports_archived_cards(
        self, archive_service, practice_repository, chat_id, tmp_path
    ):
        course = tmp_path / "course.tsv"
        course.write_text("batch\tlevel\tnl\ten\n1\tA0\thallo\thello\n", encoding="utf-8")
        await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        await _add_cards(practice_repository, chat_id, 1, prefix="new")

        status = await VocabularyBatchService(batches_path=course).get_status(chat_id)

        assert status.active_cards == 1
        assert status.archived_cards == 3

    @pytest.mark.asyncio
    async def test_reset_my_words_keeps_archived_cards(
        self, archive_service, practice_repository, chat_id, tmp_path
    ):
        course = tmp_path / "course.tsv"
        course.write_text("batch\tlevel\tnl\ten\n1\tA0\thallo\thello\n", encoding="utf-8")
        old_ids = await _add_cards(practice_repository, chat_id, 3)
        await archive_service.archive_all(chat_id)
        new_ids = await _add_cards(practice_repository, chat_id, 2, prefix="new")

        result = await VocabularyBatchService(batches_path=course).reset_user_words(chat_id)

        assert result.word_practice_marked_deleted == 2
        assert result.archived_cards_kept == 3
        for word_id in new_ids:
            assert await practice_repository.get_practice_word(chat_id, word_id) is None
        restored = await archive_service.unarchive(chat_id)
        assert restored.restored_cards == 3
        for word_id in old_ids:
            assert await practice_repository.get_practice_word(chat_id, word_id) is not None
