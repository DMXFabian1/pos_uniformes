from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_history_helper import build_quote_history_rows


class QuoteHistoryHelperTests(unittest.TestCase):
    def test_filters_rows_by_state_and_search_text(self) -> None:
        rows = build_quote_history_rows(
            quote_snapshots=[
                {
                    "id": 1,
                    "folio": "P-001",
                    "cliente": "Maria Lopez",
                    "estado": "EMITIDO",
                    "total": Decimal("449.50"),
                    "usuario": "admin",
                    "vigencia": "2026-03-31",
                    "fecha": "2026-03-18 10:30",
                    "searchable": "P-001 Maria Lopez 5551234567 SKU-001 SKU-002",
                },
                {
                    "id": 2,
                    "folio": "P-002",
                    "cliente": "Mostrador / sin cliente",
                    "estado": "BORRADOR",
                    "total": Decimal("199.00"),
                    "usuario": "caja",
                    "vigencia": "Sin vigencia",
                    "fecha": "2026-03-18 11:00",
                    "searchable": "P-002 SKU-003",
                },
            ],
            search_text="maria",
            state_filter="EMITIDO",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 1)
        self.assertEqual(rows[0]["folio"], "P-001")
        self.assertEqual(rows[0]["cliente"], "Maria Lopez")
        self.assertEqual(rows[0]["estado"], "EMITIDO")
        self.assertEqual(rows[0]["total"], Decimal("449.50"))
        self.assertEqual(rows[0]["status_tone"], "positive")

    def test_marks_unknown_status_as_muted(self) -> None:
        rows = build_quote_history_rows(
            quote_snapshots=[
                {
                    "id": 3,
                    "folio": "P-003",
                    "cliente": "Cliente prueba",
                    "estado": "DESCONOCIDO",
                    "total": Decimal("0.00"),
                    "usuario": "",
                    "vigencia": "Sin vigencia",
                    "fecha": "",
                    "searchable": "P-003 Cliente prueba",
                }
            ],
            search_text="",
            state_filter="",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_tone"], "muted")


if __name__ == "__main__":
    unittest.main()
