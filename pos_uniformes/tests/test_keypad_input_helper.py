from __future__ import annotations

import unittest

from pos_uniformes.ui.keypad_input_helper import (
    append_keypad_text,
    backspace_keypad_text,
    clear_keypad_text,
)


class KeypadInputHelperTests(unittest.TestCase):
    def test_append_replaces_default_zero_value(self) -> None:
        self.assertEqual(append_keypad_text("0.00", "1"), "1")

    def test_append_ignores_second_decimal_point(self) -> None:
        self.assertEqual(append_keypad_text("12.3", "."), "12.3")

    def test_clear_returns_default_value(self) -> None:
        self.assertEqual(clear_keypad_text(), "0.00")

    def test_backspace_restores_default_when_value_becomes_empty(self) -> None:
        self.assertEqual(backspace_keypad_text("1"), "0.00")

    def test_backspace_removes_one_character_at_a_time(self) -> None:
        self.assertEqual(backspace_keypad_text("150"), "15")
        self.assertEqual(backspace_keypad_text("12.30"), "12.3")
        self.assertEqual(backspace_keypad_text("12."), "12")


if __name__ == "__main__":
    unittest.main()
