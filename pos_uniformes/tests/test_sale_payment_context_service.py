from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_payment_context_service import build_sale_payment_note_context
from pos_uniformes.services.sale_payment_note_service import SalePaymentDetails


class SalePaymentContextServiceTests(unittest.TestCase):
    def test_build_sale_payment_note_context_normalizes_method_and_merges_notes(self) -> None:
        context = build_sale_payment_note_context(
            payment_method="  ",
            discount_percent=Decimal("15.00"),
            applied_discount=Decimal("29.85"),
            rounding_adjustment=Decimal("-0.15"),
            breakdown={
                "loyalty_discount": Decimal("10.00"),
                "promo_discount": Decimal("15.00"),
                "loyalty_source": "Profesor",
                "winner_label": "Promo manual 15%",
            },
            format_discount_label=lambda value: f"{Decimal(str(value)).quantize(Decimal('0.01'))}%",
            payment_details=SalePaymentDetails(note_lines=("Cambio: 31.00",)),
        )

        self.assertEqual(context.payment_method, "Efectivo")
        self.assertIn("Metodo de pago: Efectivo", context.note_parts)
        self.assertIn("Promocion manual autorizada con codigo", context.note_parts)
        self.assertIn("Cambio: 31.00", context.note_parts)


if __name__ == "__main__":
    unittest.main()
