from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.layaway_history_helper import build_layaway_history_rows


class LayawayHistoryHelperTests(unittest.TestCase):
    def test_filters_rows_by_state_due_bucket_and_search(self) -> None:
        rows = build_layaway_history_rows(
            layaway_snapshots=[
                {
                    "id": 1,
                    "folio": "APT-001",
                    "cliente": "CLI-001 · Maria Lopez",
                    "estado": "ACTIVO",
                    "total": Decimal("499.00"),
                    "abonado": Decimal("300.00"),
                    "saldo": Decimal("199.00"),
                    "due_bucket": "week",
                    "due_text": "Vence 2026-03-25",
                    "due_tone": "warning",
                    "searchable": "APT-001 CLI-001 Maria Lopez 5551234567",
                },
                {
                    "id": 2,
                    "folio": "APT-002",
                    "cliente": "Manual · Mostrador",
                    "estado": "CANCELADO",
                    "total": Decimal("199.00"),
                    "abonado": Decimal("0.00"),
                    "saldo": Decimal("199.00"),
                    "due_bucket": "none",
                    "due_text": "Sin fecha",
                    "due_tone": "muted",
                    "searchable": "APT-002 Mostrador",
                },
            ],
            search_text="maria",
            state_filter="ACTIVO",
            due_filter="week",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["folio"], "APT-001")
        self.assertEqual(rows[0]["status_tone"], "warning")
        self.assertEqual(rows[0]["due_tone"], "warning")

    def test_marks_unknown_status_as_muted(self) -> None:
        rows = build_layaway_history_rows(
            layaway_snapshots=[
                {
                    "id": 3,
                    "folio": "APT-003",
                    "cliente": "Cliente prueba",
                    "estado": "DESCONOCIDO",
                    "total": Decimal("0.00"),
                    "abonado": Decimal("0.00"),
                    "saldo": Decimal("0.00"),
                    "due_bucket": "none",
                    "due_text": "Sin fecha",
                    "due_tone": "muted",
                    "searchable": "APT-003 Cliente prueba",
                }
            ],
            search_text="",
            state_filter="",
            due_filter="",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_tone"], "muted")


if __name__ == "__main__":
    unittest.main()
