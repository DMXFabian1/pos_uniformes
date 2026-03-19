from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.ui.helpers.cash_session_feedback_helper import (
    build_cash_close_success_feedback,
    build_cash_movement_success_feedback,
    build_cash_opening_correction_success_feedback,
    build_cash_session_gate_feedback,
)


class CashSessionFeedbackHelperTests(unittest.TestCase):
    def test_build_cash_session_gate_feedback_handles_stale_and_resumed_session(self) -> None:
        stale = build_cash_session_gate_feedback(
            requires_cut=True,
            opened_at_label="2026-03-18 09:00",
            opened_by="Daniel",
            opening_amount=Decimal("500.00"),
        )
        resumed = build_cash_session_gate_feedback(
            requires_cut=False,
            opened_at_label="2026-03-19 09:00",
            opened_by="Daniel",
            opening_amount=Decimal("300.00"),
        )

        self.assertEqual(stale.title, "Caja pendiente de corte")
        self.assertIn("dia anterior", stale.message)
        self.assertEqual(resumed.title, "Caja abierta detectada")

    def test_build_cash_movement_success_feedback_formats_reactivo_and_regular_movements(self) -> None:
        reactivo = build_cash_movement_success_feedback(
            movement_type=SimpleNamespace(value="reactivo"),
            amount=Decimal("0.00"),
            target_total="650.00",
        )
        retiro = build_cash_movement_success_feedback(
            movement_type=SimpleNamespace(value="retiro"),
            amount=Decimal("100.00"),
            target_total=None,
        )

        self.assertIn("Total objetivo", reactivo.message)
        self.assertIn("$100.00", retiro.message)

    def test_build_cash_opening_and_close_feedback(self) -> None:
        correction = build_cash_opening_correction_success_feedback(
            previous_amount=Decimal("300.00"),
            new_amount=Decimal("450.00"),
        )
        close = build_cash_close_success_feedback(
            expected_amount=Decimal("800.00"),
            counted_amount=Decimal("790.00"),
            difference=Decimal("-10.00"),
        )

        self.assertIn("$300.00", correction.message)
        self.assertIn("$800.00", close.message)


if __name__ == "__main__":
    unittest.main()
