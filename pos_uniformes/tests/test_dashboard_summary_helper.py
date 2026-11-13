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
            ventas_hoy=2,
            ventas_mes=8,
            is_admin=True,
        )

        self.assertIn("Usuarios: 2", view.metrics_text)
        self.assertIn("Proveedores: 4", view.metrics_text)
        self.assertIn("Compras: 3", view.metrics_text)
        self.assertIn("Ventas hoy: 2", view.metrics_text)
        self.assertIn("Ventas del mes: 8", view.metrics_text)

    def test_build_dashboard_status_view_for_non_admin_omits_admin_counts(self) -> None:
        view = build_dashboard_status_view(
            usuarios=2,
            proveedores=4,
            productos=10,
            variantes=20,
            stock_total=55,
            compras=3,
            ventas_hoy=2,
            ventas_mes=8,
            is_admin=False,
        )

        self.assertNotIn("Usuarios:", view.metrics_text)
        self.assertNotIn("Proveedores:", view.metrics_text)
        self.assertIn("Productos: 10", view.metrics_text)

    def test_build_dashboard_operations_view_for_admin_splits_primary_and_secondary(self) -> None:
        view = build_dashboard_operations_view(
            ventas_hoy=5,
            cobrado_hoy=Decimal("1234.50"),
            ventas_mes=40,
            cobrado_mes=Decimal("15000.00"),
            compras_confirmadas=Decimal("450.00"),
            stock_bajo=12,
            is_admin=True,
        )

        self.assertEqual(
            view.primary_text,
            "Hoy: 5 ventas · cobrado $1,234.50 | Mes: 40 ventas · cobrado $15,000.00",
        )
        self.assertIn("Compras confirmadas: $450.00", view.secondary_text)
        self.assertIn("Presentaciones con stock bajo (<=3): 12", view.secondary_text)

    def test_el_cobrado_solo_lo_ve_el_admin(self) -> None:
        # 2026-11-12: «Ingreso» sigue siendo solo para ADMIN.
        view = build_dashboard_operations_view(
            ventas_hoy=5,
            cobrado_hoy=Decimal("1234.50"),
            ventas_mes=40,
            cobrado_mes=Decimal("15000.00"),
            compras_confirmadas=Decimal("450.00"),
            stock_bajo=12,
            is_admin=False,
        )

        self.assertEqual(view.primary_text, "Hoy: 5 ventas | Mes: 40 ventas")
        self.assertNotIn("$", view.primary_text)

    def test_build_dashboard_future_alerts_view_mentions_operational_area(self) -> None:
        admin_view = build_dashboard_future_alerts_view(is_admin=True)
        cashier_view = build_dashboard_future_alerts_view(is_admin=False)

        self.assertIn("notificaciones", admin_view.title_text.lower())
        self.assertIn("respaldos automaticos", admin_view.body_text.lower())
        self.assertIn("apartados", cashier_view.body_text.lower())
        # 2026-11-12: la Caja antigua se retiró; ya no hay «caja abierta».
        self.assertNotIn("caja abierta", admin_view.body_text.lower())

    def test_build_dashboard_kpi_cards_view_marks_stock_risk(self) -> None:
        view = build_dashboard_kpi_cards_view(
            usuarios=2,
            productos=10,
            variantes=20,
            stock_total=55,
            ventas_hoy=1,
            ventas_mes=8,
            apartados_hoy=2,
            stock_bajo=140,
            is_admin=True,
        )

        self.assertEqual(view.stock.tone, "danger")
        self.assertIn("140", view.stock.detail_text)
        self.assertIn("20 presentaciones", view.products.detail_text)
        # 2026-11-12: sin los textos de la Caja antigua.
        self.assertNotIn("caja", view.products.subtitle_text.lower())
        self.assertNotIn("documentos", view.sales.detail_text)
        self.assertEqual(view.sales.tone, "positive")
        self.assertIn("8 ventas en el mes", view.sales.detail_text)
        self.assertIn("2 apartados hoy", view.sales.detail_text)

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
