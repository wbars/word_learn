"""callback_finish must not crash on a card that is no longer active."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from word_learn.handlers import practice as practice_handler
from word_learn.handlers.practice import callback_finish

CHAT_ID = 4242


def _make_callback(action: str):
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.data = f"finish 42 {action}"
    callback.message = MagicMock()
    callback.message.chat = MagicMock()
    callback.message.chat.id = CHAT_ID
    callback.message.answer = AsyncMock()
    return callback


@pytest.mark.parametrize("action", ["correct", "incorrect", "delete"])
@pytest.mark.asyncio
async def test_stale_tap_on_archived_or_deleted_card_answers_not_found(action):
    callback = _make_callback(action)

    repo = MagicMock()
    repo.get_practice_word = AsyncMock(return_value=None)
    service = MagicMock()
    service.mark_correct = AsyncMock()
    service.mark_incorrect = AsyncMock()
    service.mark_deleted = AsyncMock()

    with patch.object(practice_handler, "PracticeRepository", return_value=repo), patch.object(
        practice_handler, "PracticeService", return_value=service
    ), patch.object(practice_handler, "_show_practice_word", AsyncMock()) as show_next:
        await callback_finish(callback)

    repo.get_practice_word.assert_awaited_once_with(CHAT_ID, 42)
    service.mark_correct.assert_not_awaited()
    service.mark_incorrect.assert_not_awaited()
    service.mark_deleted.assert_not_awaited()
    show_next.assert_not_awaited()
    callback.message.answer.assert_awaited_once_with("Word not found.")


@pytest.mark.asyncio
async def test_active_card_still_goes_through_the_normal_path():
    callback = _make_callback("correct")

    repo = MagicMock()
    repo.get_practice_word = AsyncMock(return_value=MagicMock())
    service = MagicMock()
    service.mark_correct = AsyncMock(return_value=(1, 2))

    with patch.object(practice_handler, "PracticeRepository", return_value=repo), patch.object(
        practice_handler, "PracticeService", return_value=service
    ), patch.object(practice_handler, "_show_practice_word", AsyncMock()) as show_next:
        await callback_finish(callback)

    service.mark_correct.assert_awaited_once_with(CHAT_ID, 42)
    show_next.assert_awaited_once()
    assert "Correct!" in callback.message.answer.call_args.args[0]
