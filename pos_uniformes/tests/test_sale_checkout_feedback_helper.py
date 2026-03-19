from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_checkout_feedback_helper import (
    SaleCheckoutFeedbackView,
    build_sale_checkout_error_message,
    build_sale_checkout_success_feedback,
)


class SaleCheckoutFeedbackHelperTests(unittest.TestCase):
    def test_build_sale_checkout_error_message(self) -> None:
        self.assertEqual(
            build_sale_checkout_error_message("Stock insuficiente en SKU"),
            "Uno de los productos ya no tiene stock suficiente. Revisa el carrito y vuelve a intentar.",
        )
        self.assertEqual(build_sale_checkout_error_message("Otro error"), "Otro error")

    def test_build_sale_checkout_success_feedback(self) -> None:
        self.assertEqual(
            build_sale_checkout_success_feedback(
                folio="V-001",
                total=Decimal("180.00"),
                payment_method="Efectivo",
            ),
            SaleCheckoutFeedbackView(
                title="Venta registrada",
                message="Venta V-001 registrada. Total cobrado: 180.00 via Efectivo.",
                tone="positive",
                auto_clear_ms=2200,
            ),
        )


if __name__ == "__main__":
    unittest.main()
