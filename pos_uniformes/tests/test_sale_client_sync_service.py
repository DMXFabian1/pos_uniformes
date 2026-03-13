from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_client_sync_service import resolve_sale_client_sync_state
from pos_uniformes.services.sale_discount_service import normalize_discount_value


class SaleClientSyncServiceTests(unittest.TestCase):
    def test_resolve_sale_client_sync_state_unlocks_when_no_client_is_selected(self) -> None:
        state = resolve_sale_client_sync_state(
            has_selected_client=False,
            discount_percent=Decimal("15.00"),
            source_label="Leal",
            normalize_discount_value=normalize_discount_value,
        )

        self.assertFalse(state.locked)
        self.assertEqual(state.discount_percent, Decimal("0.00"))
        self.assertEqual(state.source_label, "")

    def test_resolve_sale_client_sync_state_locks_and_normalizes_when_client_exists(self) -> None:
        state = resolve_sale_client_sync_state(
            has_selected_client=True,
            discount_percent="12.5",
            source_label="  Profesor  ",
            normalize_discount_value=normalize_discount_value,
        )

        self.assertTrue(state.locked)
        self.assertEqual(state.discount_percent, Decimal("12.50"))
        self.assertEqual(state.source_label, "Profesor")
