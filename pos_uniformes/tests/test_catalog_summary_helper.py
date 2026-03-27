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
            "0/0 resultados | stock 0 | ap. 0 | fallbacks 0",
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
            "2/5 resultados | stock 10 | ap. 1 | fallbacks 1",
        )
        self.assertEqual(
            view.active_filters_summary,
            'Filtros activos: texto="deportivo" | estado=Activas',
        )


if __name__ == "__main__":
    unittest.main()
