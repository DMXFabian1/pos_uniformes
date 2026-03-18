from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.quote_summary_helper import build_quote_summary_view


class QuoteSummaryHelperTests(unittest.TestCase):
    def test_builds_summary_without_filters(self) -> None:
        view = build_quote_summary_view(
            visible_count=4,
            search_text="",
            state_filter_value="",
            state_filter_text="Estado: todos",
        )

        self.assertEqual(
            view.status_label,
            "Presupuestos visibles: 4 | Filtros: sin filtros",
        )
        self.assertEqual(view.active_filter_labels, [])

    def test_builds_summary_with_search_and_state_filter(self) -> None:
        view = build_quote_summary_view(
            visible_count=2,
            search_text="maria",
            state_filter_value="EMITIDO",
            state_filter_text="Emitidos",
        )

        self.assertEqual(
            view.status_label,
            'Presupuestos visibles: 2 | Filtros: texto="maria", estado=Emitidos',
        )
        self.assertEqual(view.active_filter_labels, ['texto="maria"', "estado=Emitidos"])

    def test_reports_empty_recent_quotes_without_filters(self) -> None:
        view = build_quote_summary_view(
            visible_count=0,
            search_text="",
            state_filter_value="",
            state_filter_text="Estado: todos",
        )

        self.assertEqual(view.status_label, "No hay presupuestos recientes.")

    def test_reports_no_results_when_filters_are_active(self) -> None:
        view = build_quote_summary_view(
            visible_count=0,
            search_text="folio-404",
            state_filter_value="CANCELADO",
            state_filter_text="Cancelados",
        )

        self.assertEqual(view.status_label, "No hay presupuestos con esos filtros.")


if __name__ == "__main__":
    unittest.main()
