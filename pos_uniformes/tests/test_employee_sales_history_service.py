from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.employee_sales_history_service import (
    build_employee_day_sale_rows,
    build_employee_sale_detail_snapshot,
)


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

    def test_build_employee_sale_detail_snapshot_formats_ticket_products(self) -> None:
        sale = SimpleNamespace(
            id=11,
            folio="VTA-011",
            cliente=SimpleNamespace(nombre="Maria Fernanda"),
            confirmada_at=datetime(2026, 4, 9, 10, 30),
            total=Decimal("399.00"),
            detalles=[
                SimpleNamespace(
                    cantidad=2,
                    precio_unitario=Decimal("100.00"),
                    subtotal_linea=Decimal("200.00"),
                    variante=SimpleNamespace(
                        sku="SKU-001",
                        producto=SimpleNamespace(nombre="Playera Polo"),
                    ),
                ),
                SimpleNamespace(
                    cantidad=1,
                    precio_unitario=Decimal("199.00"),
                    subtotal_linea=Decimal("199.00"),
                    variante=SimpleNamespace(
                        sku="SKU-002",
                        producto=SimpleNamespace(nombre="Sueter Escolar"),
                    ),
                ),
            ],
        )

        snapshot = build_employee_sale_detail_snapshot(sale)

        self.assertEqual(snapshot.sale_id, 11)
        self.assertEqual(snapshot.folio, "VTA-011")
        self.assertEqual(snapshot.time_label, "10:30")
        self.assertEqual(snapshot.client_name, "Maria Fernanda")
        self.assertEqual(snapshot.pieces, 3)
        self.assertEqual(snapshot.total, Decimal("399.00"))
        self.assertEqual(
            snapshot.rows[0].values,
            ("SKU-001", "Playera Polo", 2, Decimal("100.00"), Decimal("200.00")),
        )
        self.assertEqual(
            snapshot.rows[1].values,
            ("SKU-002", "Sueter Escolar", 1, Decimal("199.00"), Decimal("199.00")),
        )


if __name__ == "__main__":
    unittest.main()
