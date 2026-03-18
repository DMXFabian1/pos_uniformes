from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.settings_cash_history_detail_helper import (
    build_settings_cash_history_detail_view,
)


class SettingsCashHistoryDetailHelperTests(unittest.TestCase):
    def test_builds_open_session_detail_view(self) -> None:
        view = build_settings_cash_history_detail_view(
            session_id=21,
            is_closed=False,
            opened_at="2026-03-18 09:00",
            opened_by="Admin Uno",
            opening_amount=Decimal("100.00"),
            opening_note="Sin observacion",
            opening_corrections=[],
            reactivo_count=1,
            reactivo_total=Decimal("50.00"),
            ingresos_count=0,
            ingresos_total=Decimal("0.00"),
            retiros_count=0,
            retiros_total=Decimal("0.00"),
            cash_sales_count=3,
            cash_sales_total=Decimal("450.00"),
            cash_payments_count=1,
            cash_payments_total=Decimal("100.00"),
            movement_rows=[],
            closed_at="-",
            closed_by="-",
            expected_amount=Decimal("0.00"),
            declared_amount=Decimal("0.00"),
            difference=Decimal("0.00"),
            closing_note="Sin observacion",
        )

        self.assertEqual(view.dialog_title, "Detalle del corte #21")
        self.assertEqual(view.status_badge.text, "Abierta")
        self.assertEqual(view.status_badge.tone, "positive")
        self.assertFalse(view.closing_visible)
        self.assertIsNone(view.difference_badge)

    def test_builds_closed_session_detail_view(self) -> None:
        view = build_settings_cash_history_detail_view(
            session_id=22,
            is_closed=True,
            opened_at="2026-03-17 09:00",
            opened_by="Admin Uno",
            opening_amount=Decimal("100.00"),
            opening_note="Sin observacion",
            opening_corrections=["Correccion de apertura +$50.00"],
            reactivo_count=1,
            reactivo_total=Decimal("50.00"),
            ingresos_count=2,
            ingresos_total=Decimal("120.00"),
            retiros_count=1,
            retiros_total=Decimal("30.00"),
            cash_sales_count=5,
            cash_sales_total=Decimal("800.00"),
            cash_payments_count=2,
            cash_payments_total=Decimal("200.00"),
            movement_rows=[
                {
                    "fecha": "2026-03-17 10:00",
                    "tipo": "INGRESO",
                    "monto": Decimal("120.00"),
                    "usuario": "Admin Uno",
                    "concepto": "Fondo extra",
                }
            ],
            closed_at="2026-03-17 19:00",
            closed_by="Admin Dos",
            expected_amount=Decimal("1240.00"),
            declared_amount=Decimal("1230.00"),
            difference=Decimal("-10.00"),
            closing_note="Cierre con faltante menor.",
        )

        self.assertEqual(view.status_badge.text, "Cerrada")
        self.assertEqual(view.status_badge.tone, "muted")
        self.assertEqual(view.opening_corrections, ("Correccion de apertura +$50.00",))
        self.assertEqual(view.movement_rows[0].type_tone, "warning")
        self.assertTrue(view.closing_visible)
        self.assertEqual(view.difference_badge.text, "$-10.00")
        self.assertEqual(view.difference_badge.tone, "danger")


if __name__ == "__main__":
    unittest.main()
