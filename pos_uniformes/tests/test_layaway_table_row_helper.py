from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.layaway_table_row_helper import (
    LayawayTableRowView,
    build_layaway_table_row_views,
)


class LayawayTableRowHelperTests(unittest.TestCase):
    def test_build_layaway_table_row_views_sets_values_and_tones(self) -> None:
        rows = [
            {
                "id": 10,
                "folio": "AP-001",
                "cliente": "C001 · Maria",
                "estado": "ACTIVO",
                "total": Decimal("500.00"),
                "abonado": Decimal("200.00"),
                "saldo": Decimal("300.00"),
                "due_text": "Vencido",
                "due_tone": "danger",
                "status_tone": "warning",
            },
            {
                "id": 11,
                "folio": "AP-002",
                "cliente": "Manual · Juan",
                "estado": "LIQUIDADO",
                "total": Decimal("800.00"),
                "abonado": Decimal("800.00"),
                "saldo": Decimal("0.00"),
                "due_text": "Sin fecha",
                "due_tone": "neutral",
                "status_tone": "positive",
            },
        ]

        row_views = build_layaway_table_row_views(rows)

        self.assertEqual(
            row_views,
            (
                LayawayTableRowView(
                    layaway_id=10,
                    values=("AP-001", "C001 · Maria", "ACTIVO", Decimal("500.00"), Decimal("200.00"), Decimal("300.00"), "Vencido"),
                    status_tone="warning",
                    balance_tone="warning",
                    due_tone="danger",
                ),
                LayawayTableRowView(
                    layaway_id=11,
                    values=("AP-002", "Manual · Juan", "LIQUIDADO", Decimal("800.00"), Decimal("800.00"), Decimal("0.00"), "Sin fecha"),
                    status_tone="positive",
                    balance_tone="positive",
                    due_tone="neutral",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
