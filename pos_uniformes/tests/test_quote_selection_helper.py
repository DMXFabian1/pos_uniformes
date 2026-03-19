from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.quote_selection_helper import (
    QuoteActionState,
    build_quote_action_state,
    resolve_selected_quote_id,
)


class _FakeItem:
    def __init__(self, value):
        self._value = value

    def data(self, role):
        return self._value


class _FakeTable:
    def __init__(self, current_row: int, value=None):
        self._current_row = current_row
        self._value = value

    def currentRow(self):
        return self._current_row

    def item(self, row, column):
        if self._current_row < 0 or self._value is None:
            return None
        return _FakeItem(self._value)


class QuoteSelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_quote_id(self) -> None:
        self.assertEqual(resolve_selected_quote_id(_FakeTable(0, 10)), 10)
        self.assertIsNone(resolve_selected_quote_id(_FakeTable(-1)))

    def test_build_quote_action_state(self) -> None:
        self.assertEqual(
            build_quote_action_state(can_sell=True, has_selection=True),
            QuoteActionState(cancel_enabled=True),
        )


if __name__ == "__main__":
    unittest.main()
