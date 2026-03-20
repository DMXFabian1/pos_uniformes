from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_product_form_mode_helper import (
    build_catalog_product_form_mode_view,
    detect_catalog_product_form_mode,
)


class CatalogProductFormModeHelperTests(unittest.TestCase):
    def test_detect_defaults_to_uniform_for_new_product(self) -> None:
        self.assertEqual(detect_catalog_product_form_mode(None), "uniform")

    def test_detect_keeps_uniform_for_uniform_categories(self) -> None:
        self.assertEqual(
            detect_catalog_product_form_mode(
                {
                    "categoria_nombre": "Básico",
                    "escuela": "",
                    "nivel_educativo": "",
                    "escudo": "",
                }
            ),
            "uniform",
        )

    def test_detect_returns_regular_for_non_uniform_category_without_school_context(self) -> None:
        self.assertEqual(
            detect_catalog_product_form_mode(
                {
                    "categoria_nombre": "Ropa casual",
                    "escuela": "",
                    "nivel_educativo": "",
                    "escudo": "",
                }
            ),
            "regular",
        )

    def test_build_regular_mode_disables_school_specific_fields(self) -> None:
        view = build_catalog_product_form_mode_view("regular")

        self.assertFalse(view.category_locked)
        self.assertFalse(view.school_enabled)
        self.assertFalse(view.level_enabled)
        self.assertFalse(view.shield_enabled)
        self.assertFalse(view.context_template_enabled)
        self.assertFalse(view.base_templates_visible)
        self.assertFalse(view.context_templates_visible)
        self.assertFalse(view.presentation_templates_visible)
        self.assertTrue(view.exclude_uniform_category_options)
        self.assertTrue(view.exclude_uniform_garment_options)
        self.assertEqual(view.garment_label, "Linea / estilo")

    def test_build_uniform_mode_locks_uniform_category(self) -> None:
        view = build_catalog_product_form_mode_view("uniform")

        self.assertTrue(view.category_locked)
        self.assertEqual(view.locked_category_label, "Uniformes")
        self.assertTrue(view.school_enabled)
        self.assertTrue(view.context_template_enabled)
        self.assertTrue(view.base_templates_visible)
        self.assertTrue(view.presentation_templates_visible)


if __name__ == "__main__":
    unittest.main()
