"""Unit tests for multi-line (batch) word adding via direct text."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.handlers import add_word as add_word_handler
from word_learn.handlers.add_word import handle_direct_text
from word_learn.services.practice_service import PracticeService

CHAT_ID = 777


class TestParseBatchInput:
    def setup_method(self):
        self.service = PracticeService(repository=MagicMock())

    def test_one_pair_per_line_with_comments_and_blanks(self):
        text = (
            "# 2 Gezondheidszorg in Nederland\n"
            "\n"
            "de zorg, уход (healthcare)\n"
            "  de premie, страховой взнос (insurance premium)  \n"
            "\n"
            "declareren, подавать на возмещение (to claim)\n"
        )
        pairs, rejected = self.service.parse_batch_input(text)

        assert pairs == [
            ("de zorg", "уход (healthcare)"),
            ("de premie", "страховой взнос (insurance premium)"),
            ("declareren", "подавать на возмещение (to claim)"),
        ]
        assert rejected == []

    def test_unparsable_lines_are_reported_in_order(self):
        text = "de zorg, уход\nthis has no comma at all\ncat kat\nlonely,\n"
        pairs, rejected = self.service.parse_batch_input(text)

        assert pairs == [("de zorg", "уход"), ("cat", "kat")]
        assert rejected == ["this has no comma at all", "lonely,"]

    def test_only_first_comma_splits(self):
        pairs, _ = self.service.parse_batch_input("a\nde slaaf, раб, невольник (slave)\n")
        assert pairs == [("de slaaf", "раб, невольник (slave)")]


def _make_message(text: str):
    message = MagicMock()
    message.text = text
    message.chat = MagicMock()
    message.chat.id = CHAT_ID
    message.answer = AsyncMock()
    return message


def _patch(service, repo):
    return (
        patch.object(add_word_handler, "PracticeService", return_value=service),
        patch.object(add_word_handler, "PracticeRepository", return_value=repo),
    )


def _service_mock(added: int, skipped: int):
    real = PracticeService(repository=MagicMock())
    service = MagicMock()
    service.parse_batch_input = real.parse_batch_input
    service.parse_word_input = real.parse_word_input
    service.add_custom_words = AsyncMock(return_value=(added, skipped))
    service.add_custom_word = AsyncMock()
    return service


class TestHandleDirectTextBatch:
    @pytest.mark.asyncio
    async def test_multi_line_message_adds_all_pairs_in_one_go(self):
        message = _make_message("de zorg, уход (healthcare)\nde premie, взнос (premium)\n")
        service = _service_mock(added=2, skipped=0)
        repo = MagicMock()
        repo.count_words_to_practice = AsyncMock(return_value=4)

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch:
            await handle_direct_text(message)

        service.add_custom_words.assert_awaited_once_with(
            CHAT_ID,
            [("de zorg", "уход (healthcare)"), ("de premie", "взнос (premium)")],
        )
        service.add_custom_word.assert_not_awaited()
        text = message.answer.call_args.args[0]
        assert text == "Done! Added 2 words to learn."
        markup = message.answer.call_args.kwargs["reply_markup"]
        assert markup.inline_keyboard[0][0].text == "Practice words (4)"

    @pytest.mark.asyncio
    async def test_reports_duplicates_and_unparsable_lines(self):
        message = _make_message("de zorg, уход\nbroken line here\nde zorg, уход\n")
        service = _service_mock(added=1, skipped=1)
        repo = MagicMock()
        repo.count_words_to_practice = AsyncMock(return_value=2)

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch:
            await handle_direct_text(message)

        text = message.answer.call_args.args[0]
        assert "Done! Added 1 words to learn." in text
        assert "Already in your list, skipped: 1" in text
        assert "Could not parse 1 lines" in text
        assert "• broken line here" in text

    @pytest.mark.asyncio
    async def test_no_valid_lines_gives_usage_hint(self):
        message = _make_message("just some text here\nand more text here\n")
        service = _service_mock(added=0, skipped=0)
        repo = MagicMock()

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch:
            await handle_direct_text(message)

        service.add_custom_words.assert_not_awaited()
        assert "No word pairs found" in message.answer.call_args.args[0]

    @pytest.mark.asyncio
    async def test_one_pair_broken_over_two_lines_keeps_original_parsing(self):
        message = _make_message("the cat,\nde kat")
        service = _service_mock(added=0, skipped=0)
        service.add_custom_word = AsyncMock(return_value=(MagicMock(), MagicMock()))
        repo = MagicMock()
        repo.count_words_to_practice = AsyncMock(return_value=1)

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch, patch.object(
            add_word_handler, "get_settings", return_value=MagicMock()
        ):
            await handle_direct_text(message)

        service.add_custom_words.assert_not_awaited()
        service.add_custom_word.assert_awaited_once_with(CHAT_ID, "the cat", "de kat")

    @pytest.mark.asyncio
    async def test_header_plus_one_pair_is_a_batch(self):
        message = _make_message("# 1  Samenleven in Nederland\nafzeggen, отменять (to cancel)")
        service = _service_mock(added=1, skipped=0)
        repo = MagicMock()
        repo.count_words_to_practice = AsyncMock(return_value=2)

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch:
            await handle_direct_text(message)

        service.add_custom_words.assert_awaited_once_with(
            CHAT_ID, [("afzeggen", "отменять (to cancel)")]
        )
        assert message.answer.call_args.args[0] == "Done! Added 1 words to learn."

    @pytest.mark.asyncio
    async def test_single_line_still_uses_the_original_path(self):
        message = _make_message("cat, kat")
        service = _service_mock(added=0, skipped=0)
        repo = MagicMock()
        repo.count_words_to_practice = AsyncMock(return_value=1)
        service.add_custom_word = AsyncMock(return_value=(MagicMock(), MagicMock()))

        service_patch, repo_patch = _patch(service, repo)
        with service_patch, repo_patch, patch.object(
            add_word_handler, "get_settings", return_value=MagicMock()
        ):
            await handle_direct_text(message)

        service.add_custom_words.assert_not_awaited()
        service.add_custom_word.assert_awaited_once_with(CHAT_ID, "cat", "kat")
        assert "Done! Added word to learn: cat : kat" in message.answer.call_args.args[0]
