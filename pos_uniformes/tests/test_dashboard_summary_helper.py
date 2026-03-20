from __future__ import annotations

import unittest
from decimal import Decimal

from pos_uniformes.ui.helpers.dashboard_summary_helper import (
    build_dashboard_future_alerts_view,
    build_dashboard_kpi_cards_view,
    build_dashboard_operational_alerts_view,
    build_dashboard_operations_view,
    build_dashboard_status_view,
)


class DashboardSummaryHelperTests(unittest.TestCase):
    def test_build_dashboard_status_view_for_admin_includes_full_context(self) -> None:
        view = build_dashboard_status_view(
            usuarios=2,
            proveedores=4,
            productos=10,
            variantes=20,
            stock_total=55,
            compras=3,
            ventas=8,
            is_admin=True,
        )

        self.assertIn("Usuarios: 2", view.metrics_text)
        self.assertIn("Proveedores: 4", view.metrics_text)
        self.assertIn("Compras: 3", view.metrics_text)

    def test_build_dashboard_status_view_for_non_admin_omits_admin_counts(self) -> None:
        view = build_dashboard_status_view(
            usuarios=2,
            proveedores=4,
            productos=10,
            variantes=20,
            stock_total=55,
            compras=3,
            ventas=8,
            is_admin=False,
        )

        self.assertNotIn("Usuarios:", view.metrics_text)
        self.assertNotIn("Proveedores:", view.metrics_text)
        self.assertIn("Productos: 10", view.metrics_text)

    def test_build_dashboard_operations_view_for_admin_splits_primary_and_secondary(self) -> None:
        view = build_dashboard_operations_view(
            ventas_confirmadas=5,
            ingresos=Decimal("1234.50"),
            compras_confirmadas=Decimal("450.00"),
            stock_bajo=12,
            is_admin=True,
        )

        self.assertEqual(
            view.primary_text,
            "Ventas confirmadas: 5 | Ingreso confirmado: $1234.50",
        )
        self.assertIn("Compras confirmadas: $450.00", view.secondary_text)
        self.assertIn("Presentaciones con stock bajo (<=3): 12", view.secondary_text)

    def test_build_dashboard_future_alerts_view_mentions_operational_area(self) -> None:
        admin_view = build_dashboard_future_alerts_view(is_admin=True)
        cashier_view = build_dashboard_future_alerts_view(is_admin=False)

        self.assertIn("notificaciones", admin_view.title_text.lower())
        self.assertIn("respaldos automaticos", admin_view.body_text.lower())
        self.assertIn("apartados", cashier_view.body_text.lower())

    def test_build_dashboard_kpi_cards_view_marks_stock_risk(self) -> None:
        view = build_dashboard_kpi_cards_view(
            usuarios=2,
            productos=10,
            variantes=20,
            stock_total=55,
            ventas=8,
            ventas_confirmadas=1,
            stock_bajo=140,
            is_admin=True,
        )

        self.assertEqual(view.stock.tone, "danger")
        self.assertIn("140", view.stock.detail_text)
        self.assertIn("20 presentaciones", view.products.detail_text)

    def test_build_dashboard_operational_alerts_view_highlights_first_alerts(self) -> None:
        view = build_dashboard_operational_alerts_view(
            (
                "Stock critico alto: 20 presentaciones.",
                "Apartados vencidos: 2.",
                "Ultimo respaldo automatico ya esta viejo.",
            )
        )

        self.assertEqual(view.tone, "danger")
        self.assertIn("Stock critico alto", view.text)
        self.assertIn("Apartados vencidos", view.text)


if __name__ == "__main__":
    unittest.main()
