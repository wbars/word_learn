"""Unit tests for the alternative-UX keyboards.

These also act as regression tests: they assert the *default* keyboards are
left exactly as they were, so chats that never opt in are unaffected.
"""
from word_learn.keyboards.practice import (
    answer_keyboard,
    answer_keyboard_alternative,
    reveal_keyboard,
)


def _callback_data(markup):
    """Flatten all button (text, callback_data) pairs from a markup."""
    return [
        (button.text, button.callback_data)
        for row in markup.inline_keyboard
        for button in row
    ]


class TestDefaultKeyboardsUnchanged:
    """The original keyboards must stay byte-for-byte the same."""

    def test_reveal_is_single_full_width_button(self):
        markup = reveal_keyboard(42)

        # One row with a single button => spans the full width.
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 1
        button = markup.inline_keyboard[0][0]
        assert button.text == "Reveal"
        assert button.callback_data == "reveal 42"

    def test_default_answer_keyboard_has_three_buttons_in_order(self):
        markup = answer_keyboard(7)

        assert len(markup.inline_keyboard) == 1
        row = markup.inline_keyboard[0]
        assert len(row) == 3
        assert row[0].text == "✅ Correct"
        assert row[0].callback_data == "finish 7 correct"
        assert row[1].text == "❌ Incorrect"
        assert row[1].callback_data == "finish 7 incorrect"
        assert row[2].text == "🗑️ Delete"
        assert row[2].callback_data == "finish 7 delete"


class TestAlternativeAnswerKeyboard:
    """The alternative answer keyboard layout."""

    def test_no_delete_button(self):
        markup = answer_keyboard_alternative(9)
        callbacks = [cb for _, cb in _callback_data(markup)]
        assert all("delete" not in cb for cb in callbacks)

    def test_two_buttons_in_one_full_width_row(self):
        markup = answer_keyboard_alternative(9)

        # Two buttons sharing one row => together they span the full width.
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2

    def test_incorrect_is_left_and_correct_is_right(self):
        markup = answer_keyboard_alternative(9)
        row = markup.inline_keyboard[0]

        # Incorrect on the left...
        assert row[0].text == "❌ Incorrect"
        assert row[0].callback_data == "finish 9 incorrect"
        # ...Correct on the right.
        assert row[1].text == "✅ Correct"
        assert row[1].callback_data == "finish 9 correct"

    def test_reuses_finish_callback_format(self):
        # Same callback contract as the default keyboard, so callback_finish
        # handles both keyboards identically.
        markup = answer_keyboard_alternative(123)
        callbacks = {cb for _, cb in _callback_data(markup)}
        assert callbacks == {"finish 123 incorrect", "finish 123 correct"}
