from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_table_row_helper import (
    QuoteTableRowView,
    build_quote_table_row_views,
)


class QuoteTableRowHelperTests(unittest.TestCase):
    def test_build_quote_table_row_views(self) -> None:
        rows = [
            {
                "id": 10,
                "folio": "PRE-001",
                "cliente": "Maria",
                "estado": "EMITIDO",
                "total": Decimal("350.00"),
                "usuario": "cajero",
                "vigencia": "2026-03-25",
                "fecha": "2026-03-19 11:05",
                "status_tone": "positive",
            }
        ]

        row_views = build_quote_table_row_views(rows)

        self.assertEqual(
            row_views,
            (
                QuoteTableRowView(
                    quote_id=10,
                    values=("PRE-001", "Maria", "EMITIDO", Decimal("350.00"), "cajero", "2026-03-25", "2026-03-19 11:05"),
                    status_tone="positive",
                    total_tone="positive",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
