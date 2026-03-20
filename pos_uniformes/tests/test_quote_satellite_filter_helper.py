from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_satellite_filter_helper import (
    QuoteSatelliteActionState,
    build_quote_satellite_action_state,
    build_quote_satellite_rows,
)


class QuoteSatelliteFilterHelperTests(unittest.TestCase):
    def test_matches_phone_even_with_formatting(self) -> None:
        rows = build_quote_satellite_rows(
            quote_snapshots=[
                {
                    "id": 1,
                    "folio": "PRE-2026-001",
                    "cliente": "Maria Lopez",
                    "estado": "BORRADOR",
                    "total": Decimal("199.00"),
                    "usuario": "admin",
                    "vigencia": "2026-03-31",
                    "fecha": "2026-03-18 12:00",
                    "searchable": "PRE-2026-001 Maria Lopez (555) 123-4567 SKU-001",
                }
            ],
            search_text="5551234567",
            state_filter="",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 1)
        self.assertEqual(rows[0]["status_tone"], "warning")

    def test_build_quote_satellite_action_state(self) -> None:
        self.assertEqual(
            build_quote_satellite_action_state(
                can_operate=True,
                has_selection=True,
                selected_state="BORRADOR",
                has_phone=True,
            ),
            QuoteSatelliteActionState(
                resume_enabled=True,
                emit_enabled=True,
                cancel_enabled=True,
                whatsapp_enabled=True,
                print_enabled=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
