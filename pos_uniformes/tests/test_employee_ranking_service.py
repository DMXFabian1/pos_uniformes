from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services.employee_ranking_service import (
    build_ranking_period_dates,
    load_employee_ranking,
)
from pos_uniformes.ui.helpers.settings_employee_ranking_helper import build_employee_ranking_view


def _make_sale(code: str, total: str, pieces: int, confirmed_at: datetime):
    return SimpleNamespace(
        seller_employee_code=code,
        total=Decimal(total),
        confirmada_at=confirmed_at,
        detalles=[SimpleNamespace(cantidad=pieces)],
    )


def _make_employee(emp_id: int, codigo: str, nombre: str):
    return SimpleNamespace(id=emp_id, codigo=codigo, nombre_completo=nombre)


class _FakeSession:
    def __init__(self, sales, employees):
        self._sales = sales
        self._employees = employees

    def scalars(self, stmt):
        from sqlalchemy import inspect
        entity = stmt.column_descriptions[0]["entity"] if hasattr(stmt, "column_descriptions") else None
        return _FakeResult(self._sales if str(getattr(entity, "__name__", "")) == "Venta" else self._employees)

    def get(self, model, pk):
        return None


class _FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return self._items


class EmployeeRankingServiceTests(unittest.TestCase):
    def _make_session(self, sales, employees):
        return _FakeSession(sales, employees)

    def test_ranks_by_amount_descending(self) -> None:
        from pos_uniformes.services.employee_ranking_service import (
            EmployeeRankingRow,
            load_employee_ranking,
        )
        dt = lambda d: datetime(2026, 5, d, 10, 0, tzinfo=timezone.utc)
        sales = [
            _make_sale("ANA", "500.00", 5, dt(10)),
            _make_sale("ANA", "300.00", 3, dt(11)),
            _make_sale("LUZ", "1200.00", 12, dt(10)),
        ]
        employees = [
            _make_employee(1, "ANA", "Ana Lopez"),
            _make_employee(2, "LUZ", "Luz Ramirez"),
        ]

        from unittest.mock import patch, MagicMock
        mock_session = MagicMock()
        scalars_returns = [
            MagicMock(all=MagicMock(return_value=sales)),
            MagicMock(all=MagicMock(return_value=employees)),
        ]
        mock_session.scalars.side_effect = scalars_returns

        with patch(
            "pos_uniformes.services.employee_identity_service.EmployeeIdentityService.build_visible_employee_name",
            side_effect=lambda name: name.split()[0],
        ):
            rows = load_employee_ranking(
                mock_session,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].rank, 1)
        self.assertEqual(rows[0].employee_code, "LUZ")
        self.assertEqual(rows[0].amount, Decimal("1200.00"))
        self.assertEqual(rows[0].tickets, 1)
        self.assertEqual(rows[0].pieces, 12)

        self.assertEqual(rows[1].rank, 2)
        self.assertEqual(rows[1].employee_code, "ANA")
        self.assertEqual(rows[1].amount, Decimal("800.00"))
        self.assertEqual(rows[1].tickets, 2)
        self.assertEqual(rows[1].pieces, 8)

    def test_excludes_employees_with_no_sales_in_period(self) -> None:
        from unittest.mock import patch, MagicMock

        mock_session = MagicMock()
        scalars_returns = [
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(all=MagicMock(return_value=[_make_employee(1, "ANA", "Ana Lopez")])),
        ]
        mock_session.scalars.side_effect = scalars_returns

        with patch(
            "pos_uniformes.services.employee_identity_service.EmployeeIdentityService.build_visible_employee_name",
            side_effect=lambda name: name,
        ):
            rows = load_employee_ranking(
                mock_session,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
            )

        self.assertEqual(rows, ())

    def test_skips_sales_without_employee_code(self) -> None:
        from unittest.mock import patch, MagicMock

        dt = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
        sales = [
            _make_sale("", "500.00", 5, dt),
            _make_sale("ANA", "200.00", 2, dt),
        ]
        mock_session = MagicMock()
        scalars_returns = [
            MagicMock(all=MagicMock(return_value=sales)),
            MagicMock(all=MagicMock(return_value=[_make_employee(1, "ANA", "Ana Lopez")])),
        ]
        mock_session.scalars.side_effect = scalars_returns

        with patch(
            "pos_uniformes.services.employee_identity_service.EmployeeIdentityService.build_visible_employee_name",
            side_effect=lambda name: name,
        ):
            rows = load_employee_ranking(
                mock_session,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].employee_code, "ANA")


class BuildRankingPeriodDatesTests(unittest.TestCase):
    def test_hoy_returns_same_start_and_end(self) -> None:
        today = date(2026, 5, 14)
        start, end = build_ranking_period_dates("Hoy", reference_date=today)
        self.assertEqual(start, today)
        self.assertEqual(end, today)

    def test_7_dias_returns_6_days_ago_to_today(self) -> None:
        today = date(2026, 5, 14)
        start, end = build_ranking_period_dates("7 dias", reference_date=today)
        self.assertEqual(start, date(2026, 5, 8))
        self.assertEqual(end, today)

    def test_este_mes_returns_first_of_month_to_today(self) -> None:
        today = date(2026, 5, 14)
        start, end = build_ranking_period_dates("Este mes", reference_date=today)
        self.assertEqual(start, date(2026, 5, 1))
        self.assertEqual(end, today)


class BuildEmployeeRankingViewTests(unittest.TestCase):
    def _make_row(self, rank, code, name, tickets, pieces, amount):
        return SimpleNamespace(
            rank=rank,
            employee_id=None,
            employee_code=code,
            display_name=name,
            tickets=tickets,
            pieces=pieces,
            amount=Decimal(amount),
            last_sale_at=None,
        )

    def test_empty_rows_return_empty_status(self) -> None:
        view = build_employee_ranking_view([], period_label="hoy")
        self.assertEqual(view.rows, ())
        self.assertIn("hoy", view.status_label)
        self.assertEqual(view.total_amount, Decimal("0.00"))

    def test_status_label_summarizes_totals(self) -> None:
        rows = [
            self._make_row(1, "ANA", "Ana", 3, 10, "500.00"),
            self._make_row(2, "LUZ", "Luz", 2, 6, "300.00"),
        ]
        view = build_employee_ranking_view(rows, period_label="este mes")
        self.assertIn("2 empleadas", view.status_label)
        self.assertIn("5 tickets", view.status_label)
        self.assertIn("16 piezas", view.status_label)
        self.assertIn("$800.00", view.status_label)
        self.assertEqual(view.total_tickets, 5)
        self.assertEqual(view.total_pieces, 16)
        self.assertEqual(view.total_amount, Decimal("800.00"))

    def test_top_row_is_flagged(self) -> None:
        rows = [
            self._make_row(1, "ANA", "Ana", 3, 10, "500.00"),
            self._make_row(2, "LUZ", "Luz", 2, 6, "300.00"),
        ]
        view = build_employee_ranking_view(rows)
        self.assertTrue(view.rows[0].is_top)
        self.assertFalse(view.rows[1].is_top)

    def test_amounts_hidden_when_flag_is_false(self) -> None:
        rows = [self._make_row(1, "ANA", "Ana", 3, 10, "500.00")]
        view = build_employee_ranking_view(rows, amounts_visible=False)
        amount_cell = view.rows[0].values[4]
        self.assertEqual(amount_cell, "---")
        self.assertNotIn("$500", view.status_label)
