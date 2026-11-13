from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_summary_helper import build_inventory_summary_view


class InventorySummaryHelperTests(unittest.TestCase):
    def test_builds_empty_summary_without_filters(self) -> None:
        view = build_inventory_summary_view(
            total_rows=0,
            visible_rows=[],
            active_filter_labels=[],
        )

        self.assertEqual(
            view.results_summary,
            "0/0 resultados | stock 0 | ap. 0 | fallbacks 0",
        )
        self.assertEqual(view.negative_counter.text, "En negativo: 0")
        self.assertEqual(view.negative_counter.tone, "positive")
        self.assertEqual(view.out_counter.text, "Agotados: 0")
        self.assertEqual(view.out_counter.tone, "positive")
        self.assertEqual(view.low_counter.text, "Bajo stock: 0")
        self.assertEqual(view.qr_pending_counter.text, "Sin QR: 0")
        self.assertEqual(view.inactive_counter.text, "Inactivas: 0")

    def test_builds_summary_and_counters_for_visible_rows(self) -> None:
        visible_rows = [
            {
                "stock_actual": 0,
                "apartado_cantidad": 1,
                "fallback_importacion": True,
                "qr_exists": False,
                "variante_activa": False,
            },
            {
                "stock_actual": 2,
                "apartado_cantidad": 0,
                "fallback_importacion": False,
                "qr_exists": True,
                "variante_activa": True,
            },
            {
                "stock_actual": 8,
                "apartado_cantidad": 0,
                "fallback_importacion": False,
                "qr_exists": False,
                "variante_activa": True,
            },
        ]

        view = build_inventory_summary_view(
            total_rows=5,
            visible_rows=visible_rows,
            active_filter_labels=["texto=\"pants\"", "estado=\"Activas\""],
        )

        self.assertEqual(
            view.results_summary,
            "3/5 resultados | stock 10 | ap. 1 | fallbacks 1",
        )
        self.assertEqual(view.out_counter.text, "Agotados: 1")
        self.assertEqual(view.out_counter.tone, "danger")
        self.assertEqual(view.low_counter.text, "Bajo stock: 1")
        self.assertEqual(view.low_counter.tone, "warning")
        self.assertEqual(view.qr_pending_counter.text, "Sin QR: 2")
        self.assertEqual(view.qr_pending_counter.tone, "warning")
        self.assertEqual(view.inactive_counter.text, "Inactivas: 1")
        self.assertEqual(view.inactive_counter.tone, "muted")

    def test_negativos_tienen_su_chip_y_no_cuentan_como_bajo_ni_agotado(self) -> None:
        filas = [
            {"stock_actual": -2, "apartado_cantidad": 0, "qr_exists": True, "variante_activa": True},
            {"stock_actual": 0, "apartado_cantidad": 0, "qr_exists": True, "variante_activa": True},
            {"stock_actual": 2, "apartado_cantidad": 0, "qr_exists": True, "variante_activa": True},
        ]
        view = build_inventory_summary_view(total_rows=3, visible_rows=filas, active_filter_labels=[])
        self.assertEqual(view.negative_counter.text, "En negativo: 1")
        self.assertEqual(view.negative_counter.tone, "danger")
        self.assertEqual(view.out_counter.text, "Agotados: 1")
        self.assertEqual(view.low_counter.text, "Bajo stock: 1")


if __name__ == "__main__":
    unittest.main()
