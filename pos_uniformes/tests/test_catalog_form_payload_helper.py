from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_form_payload_helper import (
    build_catalog_batch_variant_dialog_payload,
    build_catalog_product_dialog_payload,
    build_catalog_variant_dialog_payload,
    validate_catalog_product_base_step,
    validate_catalog_product_presentations_step,
    validate_catalog_product_submission,
    validate_catalog_variant_submission,
)


class CatalogFormPayloadHelperTests(unittest.TestCase):
    def test_validate_catalog_product_base_step_requires_category_brand_and_name(self) -> None:
        self.assertEqual(
            validate_catalog_product_base_step(category_id=None, category_name="", brand_id=1, base_name="Playera"),
            "Selecciona una categoria antes de continuar.",
        )
        self.assertEqual(
            validate_catalog_product_base_step(category_id=1, category_name="Uniformes", brand_id=None, base_name="Playera"),
            "Selecciona una marca antes de continuar.",
        )
        self.assertEqual(
            validate_catalog_product_base_step(category_id=1, category_name="Uniformes", brand_id=2, base_name=" "),
            "Captura o genera el nombre base antes de continuar.",
        )

    def test_build_catalog_product_dialog_payload_clears_uniform_only_fields_for_regular_mode(self) -> None:
        payload = build_catalog_product_dialog_payload(
            mode_key="regular",
            category_id=7,
            category_name="Ropa casual",
            brand_id=9,
            base_name="Sudadera",
            school="General",
            garment_type="Casual",
            piece_type="Sudadera",
            attribute="Afelpada",
            education_level="Primaria",
            gender="Unisex",
            shield="Bordado",
            location="Bodega A",
            description="Invierno",
            sizes=["CH", " ", "MD"],
            colors=["Negro", ""],
            variant_price="299.00",
            price_mode="single",
            prices_by_size={"CH": "299.00", "": "120"},
            price_summary="Precio unico: 299.00",
            variant_cost="150.00",
            initial_stock=5,
        )

        self.assertEqual(payload["modo_catalogo"], "regular")
        self.assertEqual(payload["escuela"], "")
        self.assertEqual(payload["nivel_educativo"], "")
        self.assertEqual(payload["escudo"], "")
        self.assertEqual(payload["tallas"], ["CH", "MD"])
        self.assertEqual(payload["colores"], ["Negro"])
        self.assertEqual(payload["precios_por_talla"], {"CH": "299.00"})

    def test_validate_catalog_product_presentations_step_only_blocks_missing_prices_when_needed(self) -> None:
        self.assertIsNone(
            validate_catalog_product_presentations_step(has_variant_intent=False, missing_prices=["CH"])
        )
        self.assertIsNotNone(
            validate_catalog_product_presentations_step(has_variant_intent=True, missing_prices=["CH"])
        )

    def test_validate_catalog_product_submission_reuses_base_validation(self) -> None:
        payload = build_catalog_product_dialog_payload(
            mode_key="uniform",
            category_id=3,
            category_name="Uniformes",
            brand_id=4,
            base_name="Playera",
            school="General",
            garment_type="Deportivo",
            piece_type="Playera",
            attribute="Manga corta",
            education_level="Primaria",
            gender="Unisex",
            shield="",
            location="",
            description="",
            sizes=[],
            colors=[],
            variant_price="",
            price_mode="single",
            prices_by_size={},
            price_summary="",
            variant_cost="",
            initial_stock=0,
        )

        self.assertIsNone(validate_catalog_product_submission(payload))

    def test_validate_catalog_product_submission_accepts_regular_category_name_without_id(self) -> None:
        payload = build_catalog_product_dialog_payload(
            mode_key="regular",
            category_id=None,
            category_name="Calzado",
            brand_id=4,
            base_name="Tenis",
            school="",
            garment_type="Casual",
            piece_type="Tenis",
            attribute="Ligero",
            education_level="",
            gender="Unisex",
            shield="",
            location="Piso de venta",
            description="",
            sizes=[],
            colors=[],
            variant_price="",
            price_mode="single",
            prices_by_size={},
            price_summary="",
            variant_cost="",
            initial_stock=0,
        )

        self.assertIsNone(validate_catalog_product_submission(payload))

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

    def test_build_catalog_batch_variant_dialog_payload_normalizes_lists(self) -> None:
        payload = build_catalog_batch_variant_dialog_payload(
            sizes=["CH", "", "MD"],
            colors=["Negro", " ", "Rojo"],
            initial_price="199.00",
            pricing_mode="manual",
            prices_by_size={"CH": "199.00", "MD": "205.00", "": "0"},
            price_summary="CH: 199.00 | MD: 205.00",
            initial_cost="100.00",
            initial_stock=7,
        )

        self.assertEqual(payload["tallas"], ["CH", "MD"])
        self.assertEqual(payload["colores"], ["Negro", "Rojo"])
        self.assertEqual(payload["precios_por_talla"], {"CH": "199.00", "MD": "205.00"})


if __name__ == "__main__":
    unittest.main()
