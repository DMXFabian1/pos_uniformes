from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.sale_payment_summary_helper import build_sale_payment_tooltip


class SalePaymentSummaryHelperTests(unittest.TestCase):
    def test_build_sale_payment_tooltip_handles_transfer_and_mixed(self) -> None:
        self.assertIn("datos bancarios", build_sale_payment_tooltip("Transferencia"))
        self.assertIn("transferencia", build_sale_payment_tooltip("Mixto"))
        self.assertIn("efectivo", build_sale_payment_tooltip("Efectivo"))


if __name__ == "__main__":
    unittest.main()
