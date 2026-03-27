from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.quote_scanned_client_helper import build_quote_scanned_client_ui_state


class QuoteScannedClientHelperTests(unittest.TestCase):
    def test_returns_already_linked_feedback_when_same_client_is_scanned(self) -> None:
        state = build_quote_scanned_client_ui_state(
            current_client_id=4,
            current_client_label="CLI-004 · Maria",
            scanned_client_id=4,
            scanned_client_code="CLI-004",
            scanned_client_name="Maria",
            has_quote_cart=False,
        )

        self.assertEqual(state.action, "already_linked")
        self.assertEqual(state.immediate_message, "Cliente CLI-004 ya estaba enlazado.")

    def test_requires_confirmation_when_replacing_client_with_items_in_quote(self) -> None:
        state = build_quote_scanned_client_ui_state(
            current_client_id=4,
            current_client_label="CLI-004 · Maria",
            scanned_client_id=8,
            scanned_client_code="CLI-008",
            scanned_client_name="Luisa",
            has_quote_cart=True,
        )

        self.assertEqual(state.action, "confirm_replace")
        assert state.confirmation_message is not None
        self.assertIn("CLI-004 · Maria", state.confirmation_message)
        self.assertIn("CLI-008 · Luisa", state.confirmation_message)
        self.assertEqual(state.rejected_message, "Se conservo el cliente asignado al presupuesto.")
        self.assertEqual(state.applied_message, "Cliente asignado: CLI-008 · Luisa.")

    def test_applies_client_directly_when_quote_has_no_items(self) -> None:
        state = build_quote_scanned_client_ui_state(
            current_client_id=None,
            current_client_label="Sin cliente",
            scanned_client_id=8,
            scanned_client_code="CLI-008",
            scanned_client_name="Luisa",
            has_quote_cart=False,
        )

        self.assertEqual(state.action, "apply")
        self.assertEqual(state.applied_message, "Cliente asignado: CLI-008 · Luisa.")


if __name__ == "__main__":
    unittest.main()
