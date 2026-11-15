"""Validaciones de la ventana de una talla (tanda 5: las del asistente viejo se retiraron)."""

from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_form_payload_helper import (
    build_catalog_variant_dialog_payload,
    invalid_catalog_prices,
    non_numeric_catalog_prices,
    validate_catalog_variant_submission,
)


class CatalogFormPayloadHelperTests(unittest.TestCase):
    def test_precio_con_signo_o_comas_dice_que_escriba_solo_el_numero(self) -> None:
        precios = {"CH": "$199", "MD": "1,200", "GD": "nan"}
        self.assertEqual(invalid_catalog_prices(precios), [])
        self.assertEqual(non_numeric_catalog_prices(precios), ["CH", "MD", "GD"])
        self.assertEqual(invalid_catalog_prices({"CH": "0", "MD": "-5", "GD": "199"}), ["CH", "MD"])
        self.assertIn(
            "solo el número",
            validate_catalog_variant_submission(
                {"producto_id": 1, "talla": "CH", "precio": "$199"}, require_stock=False
            ),
        )
        self.assertIn(
            "$0",
            validate_catalog_variant_submission({"producto_id": 1, "talla": "CH", "precio": "0"}, require_stock=False),
        )

    def test_build_and_validate_catalog_variant_payload(self) -> None:
        payload = build_catalog_variant_dialog_payload(
            product_id=10,
            sku=" SKU001 ",
            size=" MD ",
            color=" Negro ",
            price=" 249.00 ",
            cost=" 120.00 ",
            initial_stock=3,
        )

        self.assertEqual(payload["sku"], "SKU001")
        self.assertEqual(payload["talla"], "MD")
        self.assertEqual(payload["color"], "Negro")
        self.assertIsNone(validate_catalog_variant_submission(payload, require_stock=True))

    def test_validate_catalog_variant_payload_requires_product_size_and_price(self) -> None:
        payload = build_catalog_variant_dialog_payload(
            product_id=None,
            sku="",
            size="",
            color="",
            price="",
            cost="",
            initial_stock=0,
        )

        self.assertEqual(
            validate_catalog_variant_submission(payload, require_stock=False),
            "Selecciona un producto.",
        )


if __name__ == "__main__":
    unittest.main()
