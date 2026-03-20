from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_product_form_summary_helper import (
    build_catalog_capture_summary_html,
    build_catalog_product_display_name_preview,
    build_catalog_review_details_html,
    build_catalog_variant_examples_preview,
)


class CatalogProductFormSummaryHelperTests(unittest.TestCase):
    def test_build_catalog_product_display_name_preview_skips_repeated_context(self) -> None:
        preview = build_catalog_product_display_name_preview(
            base_name="Pants Deportivo",
            context_values=("General", "Deportivo", "Pants"),
        )

        self.assertEqual(preview, "Pants Deportivo | General")

    def test_build_catalog_variant_examples_preview_uses_defaults_when_empty(self) -> None:
        preview = build_catalog_variant_examples_preview(
            sizes=[],
            colors=[],
            default_size="Unitalla",
            default_color="Sin color",
        )

        self.assertEqual(preview, "Unitalla / Sin color")

    def test_build_catalog_capture_summary_html_includes_notes(self) -> None:
        html = build_catalog_capture_summary_html(
            final_name="Playera basica",
            total_variants=2,
            sku_summary="SKU000101, SKU000102",
            variant_examples="CH / Negro, MD / Negro",
            price_summary="Precio unico: 199.00",
            stock_text="10",
            notes=["Sin colores elegidos"],
        )

        self.assertIn("Resumen en vivo", html)
        self.assertIn("Sin colores elegidos", html)
        self.assertIn("SKU000101, SKU000102", html)

    def test_build_catalog_review_details_html_uses_empty_context_label(self) -> None:
        html = build_catalog_review_details_html(
            product_name="Sudadera casual",
            category_label="Ropa casual",
            brand_label="Marca Norte",
            context_values=("", "", ""),
            context_empty_label="Sin contexto adicional de ropa normal",
            sizes_preview="M, G",
            colors_preview="Negro",
            sku_summary="SKU000200 -> SKU000201",
            price_summary="Precio unico: 299.00",
            stock_value=5,
            review_notes=[],
        )

        self.assertIn("Sin contexto adicional de ropa normal", html)
        self.assertIn("Ropa casual / Marca Norte", html)


if __name__ == "__main__":
    unittest.main()
