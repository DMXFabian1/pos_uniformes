from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.cash_session_history_service import build_cash_session_history_amounts


class CashSessionHistoryServiceTests(unittest.TestCase):
    def test_builds_recalculated_amounts_for_closed_session(self) -> None:
        cash_session = SimpleNamespace(
            cerrada_at=datetime(2026, 4, 6, 18, 0),
            monto_cierre_declarado=Decimal("790.00"),
        )
        summary = SimpleNamespace(esperado_en_caja=Decimal("800.00"))

        amounts = build_cash_session_history_amounts(cash_session, summary=summary)

        self.assertEqual(amounts.expected_amount, Decimal("800.00"))
        self.assertEqual(amounts.declared_amount, Decimal("790.00"))
        self.assertEqual(amounts.difference_amount, Decimal("-10.00"))

    def test_returns_empty_amounts_for_open_session(self) -> None:
        cash_session = SimpleNamespace(
            cerrada_at=None,
            monto_cierre_declarado=None,
        )
        summary = SimpleNamespace(esperado_en_caja=Decimal("500.00"))

        amounts = build_cash_session_history_amounts(cash_session, summary=summary)

        self.assertIsNone(amounts.expected_amount)
        self.assertIsNone(amounts.declared_amount)
        self.assertIsNone(amounts.difference_amount)


if __name__ == "__main__":
    unittest.main()
