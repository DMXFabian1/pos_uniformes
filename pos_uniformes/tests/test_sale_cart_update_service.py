from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.sale_cart_update_service import (
    add_sale_cart_variant,
    add_sale_cart_variants,
    update_sale_cart_item_quantity,
)


class SaleCartUpdateServiceTests(unittest.TestCase):
    def test_adds_new_variant_line(self) -> None:
        sale_cart: list[dict[str, object]] = []
        variant = SimpleNamespace(
            id=101,
            sku="SKU-NEW",
            precio_venta="149.90",
            producto=SimpleNamespace(nombre="Pants Deportivo | Primaria | Pants 2pz #3"),
        )

        line_item = add_sale_cart_variant(
            sale_cart,
            variante=variant,
            quantity=2,
            stock_validator=lambda variante, cantidad: None,
        )

        self.assertEqual(line_item["sku"], "SKU-NEW")
        self.assertEqual(line_item["cantidad"], 2)
        self.assertEqual(line_item["producto_nombre"], "Pants Deportivo | Primaria | Pants 2pz")
        self.assertEqual(len(sale_cart), 1)

    def test_increments_existing_variant_line(self) -> None:
        variant = SimpleNamespace(
            id=101,
            sku="SKU-NEW",
            precio_venta="149.90",
            producto=SimpleNamespace(nombre="Pants Deportivo"),
        )
        sale_cart = [{"sku": "SKU-NEW", "cantidad": 1, "precio_unitario": "149.90"}]

        line_item = add_sale_cart_variant(
            sale_cart,
            variante=variant,
            quantity=2,
            stock_validator=lambda variante, cantidad: None,
        )

        self.assertEqual(line_item["cantidad"], 3)
        self.assertEqual(sale_cart[0]["cantidad"], 3)

    def test_add_sale_cart_variants_validates_batched_target_quantities(self) -> None:
        variant = SimpleNamespace(
            id=201,
            sku="SKU-001",
            precio_venta="99.00",
            producto=SimpleNamespace(nombre="Playera Deportiva"),
        )
        validated_quantities: list[int] = []

        add_sale_cart_variants(
            [],
            variants=[variant, variant],
            quantity=2,
            stock_validator=lambda variante, cantidad: validated_quantities.append(cantidad),
        )

        self.assertEqual(validated_quantities, [4])

    def test_add_sale_cart_variants_applies_price_override_to_matching_line(self) -> None:
        variant = SimpleNamespace(
            id=301,
            sku="PLY-001",
            precio_venta="189.00",
            producto=SimpleNamespace(nombre="Playera Deportiva"),
        )
        sale_cart: list[dict[str, object]] = []

        updated_lines = add_sale_cart_variants(
            sale_cart,
            variants=[variant],
            quantity=1,
            stock_validator=lambda variante, cantidad: None,
            line_overrides_by_sku={
                "PLY-001": {
                    "precio_unitario": Decimal("100.00"),
                    "precio_base": Decimal("189.00"),
                    "pricing_rule_key": "SPORTS_UNIFORM_3PZ_PLAYERA",
                    "pricing_rule_label": "Conjunto deportivo 3pz",
                }
            },
        )

        self.assertEqual(updated_lines[0]["precio_unitario"], Decimal("100.00"))
        self.assertEqual(updated_lines[0]["precio_base"], Decimal("189.00"))
        self.assertEqual(updated_lines[0]["pricing_rule_key"], "SPORTS_UNIFORM_3PZ_PLAYERA")

    def test_add_sale_cart_variants_keeps_separate_line_when_same_sku_uses_different_pricing_rule(self) -> None:
        variant = SimpleNamespace(
            id=302,
            sku="PLY-001",
            precio_venta="189.00",
            producto=SimpleNamespace(nombre="Playera Deportiva"),
        )
        sale_cart = [{"sku": "PLY-001", "cantidad": 1, "precio_unitario": Decimal("189.00"), "pricing_rule_key": ""}]

        add_sale_cart_variants(
            sale_cart,
            variants=[variant],
            quantity=1,
            stock_validator=lambda variante, cantidad: None,
            line_overrides_by_sku={
                "PLY-001": {
                    "precio_unitario": Decimal("100.00"),
                    "precio_base": Decimal("189.00"),
                    "pricing_rule_key": "SPORTS_UNIFORM_3PZ_PLAYERA",
                    "pricing_rule_label": "Conjunto deportivo 3pz",
                }
            },
        )

        self.assertEqual(len(sale_cart), 2)
        self.assertEqual(sale_cart[1]["precio_unitario"], Decimal("100.00"))

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
