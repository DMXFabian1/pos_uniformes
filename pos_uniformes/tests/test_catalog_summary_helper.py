from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_summary_helper import build_catalog_summary_view


class CatalogSummaryHelperTests(unittest.TestCase):
    def test_builds_empty_summary_without_filters(self) -> None:
        view = build_catalog_summary_view(
            total_rows=0,
            visible_rows=[],
            active_filter_labels=[],
        )

        self.assertEqual(
            view.results_summary,
            "Resultados: 0 de 0 | Stock visible: 0 | Con apartados: 0 | Fallbacks: 0 | Filtros: sin filtros",
        )
        self.assertEqual(view.active_filters_summary, "Filtros activos: ninguno")

    def test_builds_summary_for_visible_rows_and_filters(self) -> None:
        visible_rows = [
            {
                "stock_actual": 3,
                "apartado_cantidad": 1,
                "fallback_importacion": True,
            },
            {
                "stock_actual": 7,
                "apartado_cantidad": 0,
                "fallback_importacion": False,
            },
        ]

        view = build_catalog_summary_view(
            total_rows=5,
            visible_rows=visible_rows,
            active_filter_labels=["texto=\"deportivo\"", "estado=Activas"],
        )

        self.assertEqual(
            view.results_summary,
            'Resultados: 2 de 5 | Stock visible: 10 | Con apartados: 1 | Fallbacks: 1 | Filtros: texto="deportivo", estado=Activas',
        )
        self.assertEqual(
            view.active_filters_summary,
            'Filtros activos: texto="deportivo" | estado=Activas',
        )


if __name__ == "__main__":
    unittest.main()
