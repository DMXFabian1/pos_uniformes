from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_summary_helper import (
    build_inventory_summary_view,
    build_search_cut_notice,
)


class InventorySummaryHelperTests(unittest.TestCase):
    def test_builds_empty_summary_without_filters(self) -> None:
        view = build_inventory_summary_view(
            total_rows=0,
            visible_rows=[],
            active_filter_labels=[],
        )

        self.assertEqual(
            view.results_summary,
            "0 tallas · 0 piezas",
        )
        self.assertEqual(view.negative_counter.text, "En negativo: 0")
        self.assertEqual(view.negative_counter.tone, "positive")
        self.assertEqual(view.out_counter.text, "Agotadas: 0")
        self.assertEqual(view.out_counter.tone, "positive")
        self.assertEqual(view.low_counter.text, "Quedan pocas: 0")
        self.assertEqual(view.inactive_counter.text, "Desactivadas: 0")

    def test_builds_summary_and_counters_for_visible_rows(self) -> None:
        visible_rows = [
            {
                "stock_actual": 0,
                "apartado_cantidad": 1,
                "fallback_importacion": True,
                "variante_activa": False,
            },
            {
                "stock_actual": 2,
                "apartado_cantidad": 0,
                "fallback_importacion": False,
                "variante_activa": True,
            },
            {
                "stock_actual": 8,
                "apartado_cantidad": 0,
                "fallback_importacion": False,
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
            "3 de 5 tallas · 10 piezas",
        )
        self.assertEqual(view.out_counter.text, "Agotadas: 1")
        self.assertEqual(view.out_counter.tone, "danger")
        self.assertEqual(view.low_counter.text, "Quedan pocas: 1")
        self.assertEqual(view.low_counter.tone, "warning")
        self.assertEqual(view.inactive_counter.text, "Desactivadas: 1")
        self.assertEqual(view.inactive_counter.tone, "muted")

    def test_negativos_tienen_su_chip_y_no_cuentan_como_bajo_ni_agotado(self) -> None:
        filas = [
            {"stock_actual": -2, "apartado_cantidad": 0, "variante_activa": True},
            {"stock_actual": 0, "apartado_cantidad": 0, "variante_activa": True},
            {"stock_actual": 2, "apartado_cantidad": 0, "variante_activa": True},
        ]
        view = build_inventory_summary_view(total_rows=3, visible_rows=filas, active_filter_labels=[])
        self.assertEqual(view.negative_counter.text, "En negativo: 1")
        self.assertEqual(view.negative_counter.tone, "danger")
        self.assertEqual(view.out_counter.text, "Agotadas: 1")
        self.assertEqual(view.low_counter.text, "Quedan pocas: 1")

    def test_avisa_cuando_la_busqueda_llega_al_tope(self) -> None:
        view = build_inventory_summary_view(
            total_rows=500, visible_rows=[], active_filter_labels=[], search_hits_count=500
        )
        self.assertTrue(
            view.results_summary.endswith(" · ⚠ Mostrando los primeros 500; afina la búsqueda")
        )

    def test_no_avisa_debajo_del_tope_ni_sin_busqueda(self) -> None:
        self.assertEqual(build_search_cut_notice(499), "")
        self.assertEqual(build_search_cut_notice(None), "")
        self.assertEqual(build_search_cut_notice(500), "Mostrando los primeros 500; afina la búsqueda")
        view = build_inventory_summary_view(
            total_rows=10, visible_rows=[], active_filter_labels=[], search_hits_count=12
        )
        self.assertNotIn("⚠", view.results_summary)


class PieEnPalabrasDeLaTiendaTests(unittest.TestCase):
    def test_sin_jerga(self) -> None:
        from pos_uniformes.ui.helpers.inventory_summary_helper import build_results_summary

        texto = build_results_summary(214, 5153, 18420)
        self.assertEqual(texto, "214 de 5,153 tallas · 18,420 piezas")
        for jerga in ("resultados", "stock", "ap.", "fallbacks", "|"):
            self.assertNotIn(jerga, texto)

    def test_todo_visible_y_singular(self) -> None:
        from pos_uniformes.ui.helpers.inventory_summary_helper import build_results_summary

        self.assertEqual(build_results_summary(5153, 5153, 1), "5,153 tallas · 1 pieza")
        self.assertEqual(build_results_summary(1, 1, 0), "1 talla · 0 piezas")


if __name__ == "__main__":
    unittest.main()
