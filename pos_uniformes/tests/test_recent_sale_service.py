from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.recent_sale_service import list_recent_sale_rows


class RecentSaleServiceTests(unittest.TestCase):
    def test_builds_recent_sale_rows_for_visible_table(self) -> None:
        sales = [
            SimpleNamespace(
                id=10,
                folio="VTA-001",
                cliente=SimpleNamespace(nombre="Maria Fernanda"),
                usuario=SimpleNamespace(username="cajero"),
                estado=SimpleNamespace(value="CONFIRMADA"),
                total=Decimal("199.00"),
                created_at=datetime(2026, 3, 18, 11, 5),
            ),
            SimpleNamespace(
                id=11,
                folio="VTA-002",
                cliente=None,
                usuario=None,
                estado=SimpleNamespace(value="BORRADOR"),
                total=Decimal("0.00"),
                created_at=None,
            ),
        ]
        session = SimpleNamespace(
            scalars=lambda _stmt: SimpleNamespace(all=lambda: sales),
        )

        fake_query = SimpleNamespace(order_by=lambda *args, **kwargs: SimpleNamespace(limit=lambda _limit: object()))

        with patch(
            "pos_uniformes.services.recent_sale_service._resolve_recent_sale_dependencies",
            return_value=(lambda value: value, lambda model: fake_query, SimpleNamespace(created_at=object())),
        ):
            rows = list_recent_sale_rows(session, limit=20)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].sale_id, 10)
        self.assertEqual(
            rows[0].values,
            (
                10,
                "VTA-001",
                "Maria Fernanda",
                "cajero",
                "CONFIRMADA",
                Decimal("199.00"),
                "2026-03-18 11:05",
            ),
        )
        self.assertEqual(
            rows[1].values,
            (
                11,
                "VTA-002",
                "Mostrador",
                "",
                "BORRADOR",
                Decimal("0.00"),
                "",
            ),
        )


if __name__ == "__main__":
    unittest.main()
