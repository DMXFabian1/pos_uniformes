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


def _op(momento, monto, *, piezas=1, tipo="venta", empleada=False):
    """Una operación de la Libreta (2026-11-12: la ficha ya no lee `venta`)."""
    return SimpleNamespace(
        created_at=momento, monto_total=monto, piezas=piezas, tipo=tipo, descuento_empleada=empleada,
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
            _op(datetime(2026, 4, 9, 11, 20), Decimal("250.00"), piezas=3),
            _op(datetime(2026, 4, 9, 16, 10), Decimal("180.00"), piezas=4),
            _op(datetime(2026, 4, 7, 10, 5), Decimal("99.00"), piezas=1),
            _op(datetime(2026, 4, 1, 10, 5), Decimal("999.00"), piezas=8),
        ]

        snapshot = build_employee_activity_snapshot(
            employee,
            pin_ready=True,
            qr_ready=False,
            card_ready=True,
            operaciones=sales,
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
            operaciones=(),
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
            _op(datetime(2026, 4, 9, 11, 20), Decimal("250.00"), piezas=2),
            _op(datetime(2026, 3, 20, 10, 5), Decimal("99.00"), piezas=1),
        ]

        snapshot = build_employee_activity_snapshot(
            employee,
            pin_ready=True,
            qr_ready=False,
            card_ready=True,
            operaciones=sales,
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


class EmployeeActivityLibretaTests(unittest.TestCase):
    """2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo demás
    corre en libreta y kioskos» → «Pantallas con datos viejos». La ficha cuenta
    lo que VENDE la empleada en la Libreta, con el criterio del ranking."""

    def _snapshot(self, operaciones):
        employee = SimpleNamespace(id=4, codigo="VEND-1", nombre_completo="Guadalupe Gomez Ruiz", activo=True)
        return build_employee_activity_snapshot(
            employee,
            pin_ready=True,
            qr_ready=True,
            card_ready=True,
            operaciones=operaciones,
            reference_date=date(2026, 11, 12),
            visible_name_builder=lambda full_name: "Guadalupe Ruiz",
        )

    def test_el_apartado_cuenta_como_operacion_pero_su_valor_no_es_monto(self) -> None:
        snapshot = self._snapshot([
            _op(datetime(2026, 11, 12, 10, 0), Decimal("300.00"), piezas=2),
            _op(datetime(2026, 11, 12, 11, 0), Decimal("900.00"), piezas=3, tipo="apartado"),
        ])
        self.assertEqual(snapshot.today_tickets, 2)
        self.assertEqual(snapshot.today_pieces, 5)
        self.assertEqual(snapshot.today_amount, Decimal("300.00"))
        self.assertEqual(build_employee_activity_state(snapshot).label, "Activa hoy")

    def test_el_abono_y_su_propia_compra_no_son_actividad(self) -> None:
        snapshot = self._snapshot([
            _op(datetime(2026, 11, 12, 10, 0), Decimal("250.00"), piezas=0, tipo="abono"),
            _op(datetime(2026, 11, 12, 11, 0), Decimal("400.00"), piezas=1, empleada=True),
        ])
        self.assertEqual(snapshot.today_tickets, 0)
        self.assertEqual(snapshot.today_amount, Decimal("0.00"))
        self.assertIsNone(snapshot.last_sale_at)
        self.assertEqual(build_employee_activity_state(snapshot).label, "Sin actividad")

    def test_empleada_sin_ventas(self) -> None:
        snapshot = self._snapshot([])
        self.assertEqual(snapshot.period_tickets, 0)
        self.assertEqual(build_employee_activity_state(snapshot).label, "Sin actividad")


class EmployeeActivityDesdeLaBaseTests(unittest.TestCase):
    """La consulta real: lee `libreta_venta` por `employee_code`."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool

        from pos_uniformes.database.connection import Base

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def test_con_y_sin_ventas_en_la_libreta(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.employee_activity_service import load_employee_activity_snapshots

        hoy = date.today()
        momento = datetime.combine(hoy, datetime.min.time()).replace(hour=12).astimezone()
        self.s.add_all([
            LibretaVenta(employee_code="VEND-1", employee_name="Lupita", tipo="venta", piezas=2,
                         monto_total=Decimal("300"), monto_neto=Decimal("300"), detalle=[], created_at=momento),
            LibretaVenta(employee_code="VEND-1", employee_name="Lupita", tipo="abono", piezas=0,
                         monto_total=Decimal("100"), monto_neto=Decimal("100"), detalle=[], created_at=momento),
        ])
        self.s.commit()
        employees = [
            SimpleNamespace(id=1, codigo="VEND-1", nombre_completo="Lupita", activo=True),
            SimpleNamespace(id=2, codigo="VEND-2", nombre_completo="Andrea", activo=True),
        ]
        svc = "pos_uniformes.services"
        with patch(f"{svc}.employee_identity_service.EmployeeIdentityService.has_pin", return_value=False), patch(
            "pos_uniformes.utils.qr_generator.QrGenerator.exists_for_employee", return_value=False
        ), patch(f"{svc}.employee_card_service.EmployeeCardService.exists_for_employee", return_value=False):
            snapshots = load_employee_activity_snapshots(self.s, employees, reference_date=hoy)

        self.assertEqual(snapshots[1].today_tickets, 1)
        self.assertEqual(snapshots[1].today_pieces, 2)
        self.assertEqual(snapshots[1].today_amount, Decimal("300.00"))
        self.assertEqual(build_employee_activity_state(snapshots[1]).label, "Activa hoy")
        self.assertEqual(snapshots[2].today_tickets, 0)
        self.assertEqual(build_employee_activity_state(snapshots[2]).label, "Sin actividad")


if __name__ == "__main__":
    unittest.main()
