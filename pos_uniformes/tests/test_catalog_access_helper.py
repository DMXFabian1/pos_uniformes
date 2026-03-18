from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_access_helper import build_catalog_access_view


class CatalogAccessHelperTests(unittest.TestCase):
    def test_builds_admin_access_view(self) -> None:
        view = build_catalog_access_view(is_admin=True)

        self.assertEqual(
            view.permission_label,
            "Esta pestaña es de consulta. Las altas, cambios de precio y existencias se gestionan en Inventario.",
        )
        self.assertTrue(view.create_product_enabled)
        self.assertTrue(view.create_variant_enabled)
        self.assertTrue(view.update_product_enabled)
        self.assertTrue(view.update_variant_enabled)
        self.assertTrue(view.toggle_product_enabled)
        self.assertTrue(view.toggle_variant_enabled)
        self.assertTrue(view.delete_product_enabled)
        self.assertTrue(view.delete_variant_enabled)
        self.assertTrue(view.quick_setup_visible)

    def test_builds_cashier_access_view(self) -> None:
        view = build_catalog_access_view(is_admin=False)

        self.assertEqual(
            view.permission_label,
            "Consulta precio, stock y estado de cada presentacion sin salir de caja.",
        )
        self.assertFalse(view.create_product_enabled)
        self.assertFalse(view.create_variant_enabled)
        self.assertFalse(view.update_product_enabled)
        self.assertFalse(view.update_variant_enabled)
        self.assertFalse(view.toggle_product_enabled)
        self.assertFalse(view.toggle_variant_enabled)
        self.assertFalse(view.delete_product_enabled)
        self.assertFalse(view.delete_variant_enabled)
        self.assertFalse(view.quick_setup_visible)


if __name__ == "__main__":
    unittest.main()
