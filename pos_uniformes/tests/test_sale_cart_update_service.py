from __future__ import annotations

from types import SimpleNamespace
import unittest

from pos_uniformes.services.sale_cart_update_service import update_sale_cart_item_quantity


class SaleCartUpdateServiceTests(unittest.TestCase):
    def test_updates_selected_line_quantity(self) -> None:
        sale_cart = [{"sku": "SKU-001", "cantidad": 1}]

        updated = update_sale_cart_item_quantity(
            SimpleNamespace(),
            sale_cart=sale_cart,
            row_index=0,
            new_quantity=3,
            variant_loader=lambda session, sku: SimpleNamespace(sku=sku, stock_actual=10),
            stock_validator=lambda variante, cantidad: None,
        )

        self.assertEqual(updated["cantidad"], 3)
        self.assertEqual(sale_cart[0]["cantidad"], 3)

    def test_rejects_invalid_row(self) -> None:
        with self.assertRaisesRegex(ValueError, "linea valida"):
            update_sale_cart_item_quantity(
                SimpleNamespace(),
                sale_cart=[],
                row_index=0,
                new_quantity=1,
                variant_loader=lambda session, sku: None,
                stock_validator=lambda variante, cantidad: None,
            )

    def test_rejects_non_positive_quantity(self) -> None:
        with self.assertRaisesRegex(ValueError, "mayor a cero"):
            update_sale_cart_item_quantity(
                SimpleNamespace(),
                sale_cart=[{"sku": "SKU-001", "cantidad": 1}],
                row_index=0,
                new_quantity=0,
                variant_loader=lambda session, sku: SimpleNamespace(sku=sku, stock_actual=10),
                stock_validator=lambda variante, cantidad: None,
            )


if __name__ == "__main__":
    unittest.main()
