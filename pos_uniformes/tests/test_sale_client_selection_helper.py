from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_client_sync_service import SaleClientSyncState
from pos_uniformes.services.sale_discount_service import format_discount_label, normalize_discount_value
from pos_uniformes.ui.helpers.sale_client_selection_helper import (
    build_empty_sale_client_selection_ui_state,
    build_sale_client_selection_ui_state,
)


class SaleClientSelectionHelperTests(unittest.TestCase):
    def test_builds_locked_ui_state_without_resetting_manual_when_not_requested(self) -> None:
        ui_state = build_sale_client_selection_ui_state(
            sync_state=SaleClientSyncState(
                locked=True,
                discount_percent=Decimal("12.50"),
                source_label="Profesor",
            ),
            reset_manual=False,
            normalize_discount_value=normalize_discount_value,
            format_discount_label=format_discount_label,
        )

        self.assertIsNone(ui_state.combo_discount_percent)
        self.assertFalse(ui_state.clear_manual_promo)
        self.assertTrue(ui_state.lock_state.locked)
        self.assertEqual(ui_state.lock_state.discount_percent, Decimal("12.50"))
        self.assertEqual(ui_state.lock_state.source_label, "Profesor")
        self.assertIn("Profesor (12.5%)", ui_state.lock_tooltip)

    def test_builds_reset_state_when_client_change_should_clear_manual_promo(self) -> None:
        ui_state = build_sale_client_selection_ui_state(
            sync_state=SaleClientSyncState(
                locked=False,
                discount_percent=Decimal("0.00"),
                source_label="",
            ),
            reset_manual=True,
            normalize_discount_value=normalize_discount_value,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(ui_state.combo_discount_percent, Decimal("0.00"))
        self.assertTrue(ui_state.clear_manual_promo)
        self.assertFalse(ui_state.lock_state.locked)
        self.assertEqual(
            ui_state.lock_tooltip,
            "Aplica una promocion manual no acumulable. Si hay lealtad, se aplicara el mayor beneficio.",
        )

    def test_builds_empty_state_for_sale_form_reset(self) -> None:
        ui_state = build_empty_sale_client_selection_ui_state(
            normalize_discount_value=normalize_discount_value,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(ui_state.combo_discount_percent, Decimal("0.00"))
        self.assertTrue(ui_state.clear_manual_promo)
        self.assertFalse(ui_state.lock_state.locked)
        self.assertEqual(ui_state.lock_state.discount_percent, Decimal("0.00"))
        self.assertEqual(ui_state.lock_state.source_label, "")


if __name__ == "__main__":
    unittest.main()
