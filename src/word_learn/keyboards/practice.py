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
                    text="✅ Correct",
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


def answer_keyboard_alternative(word_id: int) -> InlineKeyboardMarkup:
    """Create the alternative-UX answer keyboard.

    Differs from :func:`answer_keyboard`: there is no Delete button (deletion is
    done by replying "delete" to the word), and the remaining two buttons are
    ordered with Incorrect on the left and Correct on the right. Both share a
    single row so together they span the full width of the screen.

    Args:
        word_id: Word ID being answered

    Returns:
        InlineKeyboardMarkup with Incorrect/Correct buttons
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Incorrect",
                    callback_data=f"finish {word_id} incorrect",
                ),
                InlineKeyboardButton(
                    text="✅ Correct",
                    callback_data=f"finish {word_id} correct",
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
