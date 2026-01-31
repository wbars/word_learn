"""Keyboards for practice flow."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def reveal_keyboard(word_id: int) -> InlineKeyboardMarkup:
    """Create keyboard with Reveal button.

    Args:
        word_id: Word ID to reveal

    Returns:
        InlineKeyboardMarkup with Reveal button
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Reveal", callback_data=f"reveal {word_id}")]
        ]
    )


def answer_keyboard(word_id: int) -> InlineKeyboardMarkup:
    """Create keyboard with Correct/Incorrect/Delete buttons.

    Args:
        word_id: Word ID being answered

    Returns:
        InlineKeyboardMarkup with answer buttons
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Done",
                    callback_data=f"finish {word_id} correct",
                ),
                InlineKeyboardButton(
                    text="❌ Incorrect",
                    callback_data=f"finish {word_id} incorrect",
                ),
                InlineKeyboardButton(
                    text="🗑️ Delete",
                    callback_data=f"finish {word_id} delete",
                ),
            ]
        ]
    )


def practice_more_keyboard(count: int, text: str = "Practice") -> InlineKeyboardMarkup:
    """Create keyboard with Practice button showing count.

    Args:
        count: Number of words available to practice
        text: Button text prefix

    Returns:
        InlineKeyboardMarkup with Practice button
    """
    button_text = f"{text} ({count})"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data="practice")]
        ]
    )
