from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.ui.helpers.recent_sale_table_helper import (
    RecentSaleTableRowView,
    build_recent_sale_table_row_views,
)


class RecentSaleTableHelperTests(unittest.TestCase):
    def test_build_recent_sale_table_row_views(self) -> None:
        rows = [
            SimpleNamespace(
                sale_id=10,
                values=(10, "VTA-001", "Maria", "cajero", "CONFIRMADA", Decimal("199.00"), "2026-03-18 11:05"),
            ),
            SimpleNamespace(
                sale_id=11,
                values=(11, "VTA-002", "Mostrador", "", "BORRADOR", Decimal("0.00"), ""),
            ),
        ]

        row_views = build_recent_sale_table_row_views(rows)

        self.assertEqual(
            row_views,
            (
                RecentSaleTableRowView(
                    sale_id=10,
                    values=(10, "VTA-001", "Maria", "cajero", "CONFIRMADA", Decimal("199.00"), "2026-03-18 11:05"),
                ),
                RecentSaleTableRowView(
                    sale_id=11,
                    values=(11, "VTA-002", "Mostrador", "", "BORRADOR", Decimal("0.00"), ""),
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
