"""Unit tests for how PracticeService honours the per-chat toggles (mocked repository)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from word_learn.config import Language
from word_learn.models import Word
from word_learn.services.practice_service import PracticeService

CHAT_ID = 4242


def _repo(reverse_cards: bool = True, daily_limit: bool = True):
    repo = MagicMock()
    repo.get_reverse_cards = AsyncMock(return_value=reverse_cards)
    repo.get_daily_limit = AsyncMock(return_value=daily_limit)
    repo.has_active_custom_word = AsyncMock(return_value=False)
    repo.add_to_practice = AsyncMock()
    repo.create_today_practice = AsyncMock(return_value=[1, 2, 3])
    repo.count_words_to_practice = AsyncMock(return_value=3)
    repo.trim_today_practice = AsyncMock(return_value=0)

    counter = {"id": 0}

    async def add_word(translations):
        counter["id"] += 1
        return Word(id=counter["id"], **translations)

    repo.add_word = AsyncMock(side_effect=add_word)
    return repo


def _service(repo):
    service = PracticeService(repo)
    service.settings = MagicMock()
    service.settings.source_lang = Language.NL
    service.settings.target_lang = Language.EN
    service.settings.daily_pool_min = 67
    service.settings.daily_pool_max = 76
    return service


class TestAddCustomWordReverseToggle:
    @pytest.mark.asyncio
    async def test_default_creates_forward_and_reversed_card(self):
        repo = _repo(reverse_cards=True)
        service = _service(repo)

        word1, word2 = await service.add_custom_word(CHAT_ID, "de kat", "кот (cat)")

        repo.get_reverse_cards.assert_awaited_once_with(CHAT_ID)
        assert repo.add_word.await_count == 2
        # Forward card: prompt (target column) is the word as typed.
        assert (word1.en, word1.nl) == ("de kat", "кот (cat)")
        # Reversed card: prompt is the translation.
        assert (word2.en, word2.nl) == ("кот (cat)", "de kat")
        assert repo.add_to_practice.await_args_list[0].args == (CHAT_ID, [word1.id])
        assert repo.add_to_practice.await_args_list[1].args == (CHAT_ID, [word2.id])

    @pytest.mark.asyncio
    async def test_reverse_off_creates_only_the_forward_card(self):
        repo = _repo(reverse_cards=False)
        service = _service(repo)

        word1, word2 = await service.add_custom_word(CHAT_ID, "de kat", "кот (cat)")

        assert repo.add_word.await_count == 1
        assert (word1.en, word1.nl) == ("de kat", "кот (cat)")
        assert word2 is None
        repo.add_to_practice.assert_awaited_once_with(CHAT_ID, [word1.id])

    @pytest.mark.asyncio
    async def test_explicit_reverse_argument_skips_the_lookup(self):
        repo = _repo(reverse_cards=True)
        service = _service(repo)

        _, word2 = await service.add_custom_word(CHAT_ID, "a", "b", reverse=False)
        assert word2 is None
        repo.get_reverse_cards.assert_not_awaited()

        _, word2 = await service.add_custom_word(CHAT_ID, "a", "b", reverse=True)
        assert word2 is not None
        repo.get_reverse_cards.assert_not_awaited()


class TestAddCustomWordsReverseToggle:
    @pytest.mark.asyncio
    async def test_batch_reads_the_setting_once_and_applies_it_to_every_pair(self):
        repo = _repo(reverse_cards=False)
        service = _service(repo)
        pairs = [("a", "1"), ("b", "2"), ("c", "3")]

        added, skipped = await service.add_custom_words(CHAT_ID, pairs)

        assert (added, skipped) == (3, 0)
        repo.get_reverse_cards.assert_awaited_once_with(CHAT_ID)
        assert repo.add_word.await_count == 3  # one card per pair

    @pytest.mark.asyncio
    async def test_batch_default_creates_two_cards_per_pair(self):
        repo = _repo(reverse_cards=True)
        service = _service(repo)

        added, _ = await service.add_custom_words(CHAT_ID, [("a", "1"), ("b", "2")])

        assert added == 2
        assert repo.add_word.await_count == 4


class TestDailyPoolSizeToggle:
    @pytest.mark.asyncio
    async def test_limit_on_uses_a_random_size_within_the_configured_range(self):
        repo = _repo(daily_limit=True)
        service = _service(repo)

        for _ in range(20):
            size = await service.get_daily_pool_size(CHAT_ID)
            assert 67 <= size <= 76

    @pytest.mark.asyncio
    async def test_limit_off_means_no_cap(self):
        repo = _repo(daily_limit=False)
        service = _service(repo)

        assert await service.get_daily_pool_size(CHAT_ID) is None

    @pytest.mark.asyncio
    async def test_create_daily_pool_passes_none_when_limit_is_off(self):
        repo = _repo(daily_limit=False)
        service = _service(repo)

        await service.create_daily_pool(CHAT_ID)

        repo.create_today_practice.assert_awaited_once_with(CHAT_ID, None)

    @pytest.mark.asyncio
    async def test_create_daily_pool_passes_a_capped_size_when_limit_is_on(self):
        repo = _repo(daily_limit=True)
        service = _service(repo)

        await service.create_daily_pool(CHAT_ID)

        size = repo.create_today_practice.await_args.args[1]
        assert 67 <= size <= 76


class TestFillAndTrimTodayPool:
    @pytest.mark.asyncio
    async def test_fill_today_pool_adds_everything_and_reports_the_pool_size(self):
        repo = _repo()
        repo.count_words_to_practice = AsyncMock(return_value=250)
        service = _service(repo)

        assert await service.fill_today_pool(CHAT_ID) == 250
        repo.create_today_practice.assert_awaited_once_with(CHAT_ID, limit=None)

    @pytest.mark.asyncio
    async def test_trim_today_pool_uses_a_capped_size_and_reports_both_counts(self):
        repo = _repo()
        repo.trim_today_practice = AsyncMock(return_value=180)
        # 250 before the trim (over the cap), 70 after it.
        repo.count_words_to_practice = AsyncMock(side_effect=[250, 70])
        service = _service(repo)

        removed, remaining = await service.trim_today_pool(CHAT_ID)

        assert (removed, remaining) == (180, 70)
        limit = repo.trim_today_practice.await_args.args[1]
        assert 67 <= limit <= 76

    @pytest.mark.asyncio
    async def test_trim_today_pool_leaves_a_pool_within_the_cap_alone(self):
        """A pool of at most daily_pool_max cards is never re-rolled to a smaller size."""
        repo = _repo()
        service = _service(repo)

        for size in (0, 1, 67, 70, 76):
            repo.count_words_to_practice = AsyncMock(return_value=size)
            repo.trim_today_practice.reset_mock()

            assert await service.trim_today_pool(CHAT_ID) == (0, size)
            repo.trim_today_practice.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trim_today_pool_trims_just_above_the_cap(self):
        repo = _repo()
        repo.count_words_to_practice = AsyncMock(side_effect=[77, 70])
        repo.trim_today_practice = AsyncMock(return_value=7)
        service = _service(repo)

        assert await service.trim_today_pool(CHAT_ID) == (7, 70)
        repo.trim_today_practice.assert_awaited_once()
