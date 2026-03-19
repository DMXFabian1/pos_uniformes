from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.ui.helpers.analytics_payment_helper import build_analytics_payment_rows


class AnalyticsPaymentHelperTests(unittest.TestCase):
    def test_build_analytics_payment_rows_groups_sales_by_method(self) -> None:
        sales = [
            SimpleNamespace(total=Decimal("100.00"), observacion="Metodo de pago: Efectivo"),
            SimpleNamespace(total=Decimal("250.00"), observacion="Metodo de pago: Transferencia"),
            SimpleNamespace(total=Decimal("80.00"), observacion="Metodo de pago: Transferencia"),
            SimpleNamespace(total=Decimal("50.00"), observacion="Sin nota"),
        ]

        rows = build_analytics_payment_rows(sales)

        self.assertEqual(
            rows,
            (
                ("Efectivo", 2, Decimal("150.00")),
                ("Transferencia", 2, Decimal("330.00")),
            ),
        )


if __name__ == "__main__":
    unittest.main()
