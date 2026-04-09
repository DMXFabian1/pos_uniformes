from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.employee_activity_service import build_employee_activity_snapshot


class EmployeeActivityServiceTests(unittest.TestCase):
    def test_build_snapshot_groups_last_7_days_and_today_metrics(self) -> None:
        employee = SimpleNamespace(
            id=4,
            codigo="VEND-1",
            nombre_completo="Guadalupe Gomez Ruiz",
            activo=True,
        )
        sales = [
            SimpleNamespace(
                confirmada_at=datetime(2026, 4, 9, 11, 20),
                total=Decimal("250.00"),
                detalles=[SimpleNamespace(cantidad=2), SimpleNamespace(cantidad=1)],
            ),
            SimpleNamespace(
                confirmada_at=datetime(2026, 4, 9, 16, 10),
                total=Decimal("180.00"),
                detalles=[SimpleNamespace(cantidad=4)],
            ),
            SimpleNamespace(
                confirmada_at=datetime(2026, 4, 7, 10, 5),
                total=Decimal("99.00"),
                detalles=[SimpleNamespace(cantidad=1)],
            ),
            SimpleNamespace(
                confirmada_at=datetime(2026, 4, 1, 10, 5),
                total=Decimal("999.00"),
                detalles=[SimpleNamespace(cantidad=8)],
            ),
        ]

        snapshot = build_employee_activity_snapshot(
            employee,
            pin_ready=True,
            qr_ready=False,
            card_ready=True,
            sales=sales,
            reference_date=date(2026, 4, 9),
            visible_name_builder=lambda full_name: "Guadalupe Ruiz",
        )

        self.assertEqual(snapshot.visible_name, "Guadalupe Ruiz")
        self.assertEqual(snapshot.active_label, "ACTIVA")
        self.assertEqual(snapshot.pin_label, "Listo")
        self.assertEqual(snapshot.qr_label, "Pendiente")
        self.assertEqual(snapshot.card_label, "Lista")
        self.assertEqual(snapshot.today_pieces, 7)
        self.assertEqual(snapshot.today_tickets, 2)
        self.assertEqual(snapshot.today_amount, Decimal("430.00"))
        self.assertEqual(snapshot.last_sale_at, datetime(2026, 4, 9, 16, 10))
        self.assertEqual(len(snapshot.day_rows), 7)
        self.assertEqual(snapshot.day_rows[0].day, date(2026, 4, 9))
        self.assertEqual(snapshot.day_rows[0].pieces, 7)
        self.assertEqual(snapshot.day_rows[0].tickets, 2)
        self.assertEqual(snapshot.day_rows[0].amount, Decimal("430.00"))
        self.assertEqual(snapshot.day_rows[2].day, date(2026, 4, 7))
        self.assertEqual(snapshot.day_rows[2].pieces, 1)
        self.assertEqual(snapshot.day_rows[2].tickets, 1)
        self.assertEqual(snapshot.day_rows[2].amount, Decimal("99.00"))

    def test_build_snapshot_returns_zero_rows_when_employee_has_no_sales(self) -> None:
        employee = SimpleNamespace(
            id=8,
            codigo="VEND-8",
            nombre_completo="Lupita Gomez",
            activo=False,
        )

        snapshot = build_employee_activity_snapshot(
            employee,
            pin_ready=False,
            qr_ready=False,
            card_ready=False,
            sales=(),
            reference_date=date(2026, 4, 9),
            visible_name_builder=lambda full_name: "Lupita Gomez",
        )

        self.assertEqual(snapshot.active_label, "INACTIVA")
        self.assertEqual(snapshot.today_pieces, 0)
        self.assertEqual(snapshot.today_tickets, 0)
        self.assertEqual(snapshot.today_amount, Decimal("0.00"))
        self.assertIsNone(snapshot.last_sale_at)
        self.assertTrue(all(row.pieces == 0 and row.tickets == 0 for row in snapshot.day_rows))


if __name__ == "__main__":
    unittest.main()
