from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.employee_activity_service import (
    build_employee_activity_snapshot,
    build_employee_activity_state,
    build_employee_activity_sort_key,
)


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

    def test_build_activity_state_marks_today_activity_first(self) -> None:
        snapshot = SimpleNamespace(
            today_pieces=3,
            today_tickets=1,
            day_rows=(
                SimpleNamespace(pieces=3, tickets=1),
                SimpleNamespace(pieces=2, tickets=1),
            ),
        )

        state = build_employee_activity_state(snapshot)

        self.assertEqual(state.label, "Activa hoy")
        self.assertEqual(state.tone, "positive")

    def test_build_activity_state_marks_recent_activity_without_today_sales(self) -> None:
        snapshot = SimpleNamespace(
            today_pieces=0,
            today_tickets=0,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=2, tickets=1),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )

        state = build_employee_activity_state(snapshot)

        self.assertEqual(state.label, "Activa 7d")
        self.assertEqual(state.tone, "warning")

    def test_build_activity_state_marks_inactive_when_week_has_no_sales(self) -> None:
        snapshot = SimpleNamespace(
            today_pieces=0,
            today_tickets=0,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )

        state = build_employee_activity_state(snapshot)

        self.assertEqual(state.label, "Sin actividad")
        self.assertEqual(state.tone, "muted")

    def test_build_activity_sort_key_prioritizes_today_then_recent_then_inactive(self) -> None:
        active_today = SimpleNamespace(
            visible_name="Lupita Gomez",
            full_name="Guadalupe Gomez Ruiz",
            today_pieces=5,
            last_sale_at=datetime(2026, 4, 9, 16, 10),
            day_rows=(
                SimpleNamespace(pieces=5, tickets=2),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )
        active_7d = SimpleNamespace(
            visible_name="Andrea Lopez",
            full_name="Andrea Lopez",
            today_pieces=0,
            last_sale_at=datetime(2026, 4, 8, 10, 0),
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=1, tickets=1),
            ),
        )
        inactive = SimpleNamespace(
            visible_name="Berenice Cruz",
            full_name="Berenice Cruz",
            today_pieces=0,
            last_sale_at=None,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )

        ordered = sorted(
            [inactive, active_7d, active_today],
            key=build_employee_activity_sort_key,
        )

        self.assertEqual(ordered[0].visible_name, "Lupita Gomez")
        self.assertEqual(ordered[1].visible_name, "Andrea Lopez")
        self.assertEqual(ordered[2].visible_name, "Berenice Cruz")

    def test_build_snapshot_supports_period_totals_longer_than_history_table(self) -> None:
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
                detalles=[SimpleNamespace(cantidad=2)],
            ),
            SimpleNamespace(
                confirmada_at=datetime(2026, 3, 20, 10, 5),
                total=Decimal("99.00"),
                detalles=[SimpleNamespace(cantidad=1)],
            ),
        ]

        snapshot = build_employee_activity_snapshot(
            employee,
            pin_ready=True,
            qr_ready=False,
            card_ready=True,
            sales=sales,
            reference_date=date(2026, 4, 9),
            history_days=7,
            summary_days=30,
            visible_name_builder=lambda full_name: "Guadalupe Ruiz",
        )

        self.assertEqual(len(snapshot.day_rows), 7)
        self.assertEqual(snapshot.period_days, 30)
        self.assertEqual(snapshot.period_label, "30 dias")
        self.assertEqual(snapshot.period_pieces, 3)
        self.assertEqual(snapshot.period_tickets, 2)
        self.assertEqual(snapshot.period_amount, Decimal("349.00"))
        self.assertEqual(snapshot.day_rows[0].pieces, 2)


if __name__ == "__main__":
    unittest.main()
