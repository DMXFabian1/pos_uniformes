from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.layaway_summary_helper import build_layaway_summary_view


class LayawaySummaryHelperTests(unittest.TestCase):
    def test_builds_summary_without_filters(self) -> None:
        view = build_layaway_summary_view(
            visible_rows=[
                {"saldo": Decimal("199.00")},
                {"saldo": Decimal("50.00")},
            ],
            search_text="",
            state_filter_value="",
            state_filter_text="Estado: todos",
            due_filter_value="",
            due_filter_text="Vencimiento: todos",
        )

        self.assertEqual(
            view.status_label,
            "Apartados visibles: 2 | Filtros: sin filtros",
        )
        self.assertEqual(view.active_filter_labels, [])

    def test_builds_summary_with_active_filters(self) -> None:
        view = build_layaway_summary_view(
            visible_rows=[{"saldo": Decimal("0.00")}],
            search_text="maria",
            state_filter_value="ACTIVO",
            state_filter_text="Activos",
            due_filter_value="week",
            due_filter_text="Proximos 7 dias",
        )

        self.assertEqual(
            view.status_label,
            'Apartados visibles: 1 | Filtros: texto="maria", estado=Activos, vencimiento=Proximos 7 dias',
        )
        self.assertEqual(
            view.active_filter_labels,
            ['texto="maria"', "estado=Activos", "vencimiento=Proximos 7 dias"],
        )

    def test_reports_empty_recent_layaways_without_filters(self) -> None:
        view = build_layaway_summary_view(
            visible_rows=[],
            search_text="",
            state_filter_value="",
            state_filter_text="Estado: todos",
            due_filter_value="",
            due_filter_text="Vencimiento: todos",
        )

        self.assertEqual(view.status_label, "No hay apartados recientes.")

    def test_reports_no_results_when_filters_are_active(self) -> None:
        view = build_layaway_summary_view(
            visible_rows=[],
            search_text="apt-999",
            state_filter_value="CANCELADO",
            state_filter_text="Cancelados",
            due_filter_value="overdue",
            due_filter_text="Vencidos",
        )

        self.assertEqual(view.status_label, "No hay apartados con esos filtros.")


if __name__ == "__main__":
    unittest.main()
