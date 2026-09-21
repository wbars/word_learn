"""/reset_my_words confirmation prompt must not depend on the course file."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.handlers import vocabulary_batches as handler_module
from word_learn.handlers.vocabulary_batches import cmd_reset_my_words
from word_learn.services.word_archive import ArchiveStatus

CHAT_ID = 4242


def _make_message(text: str):
    message = MagicMock()
    message.text = text
    message.chat = MagicMock()
    message.chat.id = CHAT_ID
    message.answer = AsyncMock()
    return message


def _patches(archived_cards: int):
    archive = MagicMock()
    archive.get_status = AsyncMock(
        return_value=ArchiveStatus(
            active_cards=5, archived_cards=archived_cards, generations=1 if archived_cards else 0,
            newest_archived_at=None,
        )
    )
    batch_service = MagicMock()
    batch_service.get_status = AsyncMock(side_effect=AssertionError("must not load the course file"))
    batch_service.reset_user_words = AsyncMock()
    return (
        patch.object(handler_module, "_is_admin", return_value=True),
        patch.object(handler_module, "WordArchiveService", return_value=archive),
        patch.object(handler_module, "VocabularyBatchService", return_value=batch_service),
        batch_service,
    )


@pytest.mark.asyncio
async def test_prompt_without_archive_uses_db_only_and_mentions_active_cards():
    message = _make_message("/reset_my_words")
    admin, archive, batches, batch_service = _patches(archived_cards=0)
    with admin, archive, batches:
        await cmd_reset_my_words(message)

    text = message.answer.call_args.args[0]
    assert text.startswith("This will mark all active practice cards as deleted")
    assert "archived" not in text
    assert "/reset_my_words confirm" in text
    batch_service.reset_user_words.assert_not_awaited()


@pytest.mark.asyncio
async def test_prompt_with_archive_says_archived_cards_are_kept():
    message = _make_message("/reset_my_words")
    admin, archive, batches, _ = _patches(archived_cards=800)
    with admin, archive, batches:
        await cmd_reset_my_words(message)

    text = message.answer.call_args.args[0]
    assert "Your 800 archived cards are kept" in text
    assert "/unarchive_words" in text
