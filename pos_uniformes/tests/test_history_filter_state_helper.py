from __future__ import annotations

from datetime import date, datetime
import unittest

from pos_uniformes.ui.helpers.history_filter_state_helper import (
    build_history_clear_filter_state,
    build_history_date_range_state,
    build_history_filter_state,
    build_history_today_filter_dates,
    build_history_type_options_state,
)


class HistoryFilterStateHelperTests(unittest.TestCase):
    def test_build_history_date_range_state(self) -> None:
        state = build_history_date_range_state(
            from_date=date(2026, 3, 10),
            to_date=date(2026, 3, 12),
            minimum_date=date(2000, 1, 1),
        )
        self.assertEqual(state.start_datetime, datetime(2026, 3, 10, 0, 0))
        self.assertEqual(state.end_datetime, datetime(2026, 3, 13, 0, 0))
        self.assertEqual(state.start_date_label, "2026-03-10")
        self.assertEqual(state.end_date_label, "2026-03-12")

    def test_build_history_filter_state(self) -> None:
        state = build_history_filter_state(
            source_filter="inventory",
            entity_filter="PRESENTACION",
            sku_filter=" sku-01 ",
            type_filter="inventory:ENTRADA_COMPRA",
            source_filter_text="Inventario",
            entity_filter_text="Presentacion",
            type_filter_text="Inv. ENTRADA_COMPRA",
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 2),
            minimum_date=date(2000, 1, 1),
        )
        self.assertEqual(state.sku_filter, "sku-01")
        self.assertEqual(state.date_range.start_date_label, "2026-03-01")

    def test_build_history_type_options_state_and_resets(self) -> None:
        type_state = build_history_type_options_state(
            source_filter="inventory",
            current_type="inventory:ENTRADA_COMPRA",
            build_options=lambda source: (("Todos", ""), ("Inv. ENTRADA_COMPRA", "inventory:ENTRADA_COMPRA")),
        )
        self.assertEqual(type_state.selected_type_value, "inventory:ENTRADA_COMPRA")

        today_from, today_to = build_history_today_filter_dates(date(2026, 3, 19))
        self.assertEqual(today_from, date(2026, 3, 19))
        self.assertEqual(today_to, date(2026, 3, 19))

        clear_state = build_history_clear_filter_state(date(2000, 1, 1))
        self.assertEqual(clear_state.sku_text, "")
        self.assertEqual(clear_state.from_date, date(2000, 1, 1))


if __name__ == "__main__":
    unittest.main()
