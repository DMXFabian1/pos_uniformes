from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.employee_sales_history_service import build_employee_day_sale_rows


class EmployeeSalesHistoryServiceTests(unittest.TestCase):
    def test_build_employee_day_sale_rows_formats_time_pieces_and_total(self) -> None:
        sales = [
            SimpleNamespace(
                id=11,
                folio="VTA-011",
                cliente=SimpleNamespace(nombre="Maria Fernanda"),
                confirmada_at=datetime(2026, 4, 9, 10, 30),
                total=Decimal("399.00"),
                detalles=[SimpleNamespace(cantidad=2), SimpleNamespace(cantidad=1)],
            ),
            SimpleNamespace(
                id=12,
                folio="VTA-012",
                cliente=None,
                confirmada_at=datetime(2026, 4, 9, 12, 5),
                total=Decimal("120.00"),
                detalles=[SimpleNamespace(cantidad=1)],
            ),
        ]

        rows = build_employee_day_sale_rows(sales)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].sale_id, 11)
        self.assertEqual(rows[0].values, ("10:30", "VTA-011", "Maria Fernanda", 3, Decimal("399.00")))
        self.assertEqual(rows[1].values, ("12:05", "VTA-012", "Mostrador", 1, Decimal("120.00")))


if __name__ == "__main__":
    unittest.main()
