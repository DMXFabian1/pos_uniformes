from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.history_summary_helper import build_history_summary_view


class HistorySummaryHelperTests(unittest.TestCase):
    def test_builds_summary_with_active_filters(self) -> None:
        view = build_history_summary_view(
            visible_count=12,
            search_text="sku-01",
            source_filter_value="inventory",
            source_filter_text="Inventario",
            entity_filter_value="",
            entity_filter_text="Todas",
            type_filter_value="inventory:ENTRADA",
            type_filter_text="Inv. ENTRADA",
            date_from_label="2026-03-01",
            date_to_label="2026-03-18",
        )

        self.assertEqual(
            view.status_label,
            (
                'Movimientos visibles: 12 | Filtros: texto="sku-01", origen=Inventario, '
                "tipo=Inv. ENTRADA, desde=2026-03-01, hasta=2026-03-18"
            ),
        )

    def test_builds_empty_message_without_filters(self) -> None:
        view = build_history_summary_view(
            visible_count=0,
            search_text="",
            source_filter_value="",
            source_filter_text="Todos",
            entity_filter_value="",
            entity_filter_text="Todas",
            type_filter_value="",
            type_filter_text="Todos",
            date_from_label="",
            date_to_label="",
        )

        self.assertEqual(view.status_label, "No hay movimientos recientes.")


if __name__ == "__main__":
    unittest.main()
