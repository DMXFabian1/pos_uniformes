from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.recent_sale_selection_helper import (
    RecentSaleActionState,
    build_recent_sale_action_state,
    resolve_selected_recent_sale_id,
)


class _FakeItem:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def text(self) -> str | None:
        return self._text


class _FakeTable:
    def __init__(self, current_row: int, cells: dict[tuple[int, int], str | None]) -> None:
        self._current_row = current_row
        self._cells = cells

    def currentRow(self) -> int:
        return self._current_row

    def item(self, row: int, column: int):
        if (row, column) not in self._cells:
            return None
        return _FakeItem(self._cells[(row, column)])


class RecentSaleSelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_recent_sale_id(self) -> None:
        table = _FakeTable(0, {(0, 0): "10"})
        self.assertEqual(resolve_selected_recent_sale_id(table), 10)
        self.assertIsNone(resolve_selected_recent_sale_id(_FakeTable(-1, {})))
        self.assertIsNone(resolve_selected_recent_sale_id(_FakeTable(0, {(0, 0): "x"})))

    def test_build_recent_sale_action_state(self) -> None:
        self.assertEqual(
            build_recent_sale_action_state(has_selection=True, is_admin=False),
            RecentSaleActionState(ticket_enabled=True, cancel_enabled=False),
        )


if __name__ == "__main__":
    unittest.main()
