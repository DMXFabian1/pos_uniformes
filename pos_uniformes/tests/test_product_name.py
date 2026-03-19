from __future__ import annotations

from pathlib import Path
import unittest

from pos_uniformes.importers.legacy_products_importer import LegacyProductsImporter
from pos_uniformes.utils.product_name import sanitize_product_display_name


class ProductNameUtilsTests(unittest.TestCase):
    def test_sanitize_product_display_name_removes_legacy_duplicate_suffix(self) -> None:
        self.assertEqual(
            sanitize_product_display_name("Playera Deportiva | Patria | Deportivo | Playera #4"),
            "Playera Deportiva | Patria | Deportivo | Playera",
        )

    def test_sanitize_product_display_name_keeps_normal_names(self) -> None:
        self.assertEqual(
            sanitize_product_display_name("Playera Deportiva | Frida Kahlo | Deportivo | Playera"),
            "Playera Deportiva | Frida Kahlo | Deportivo | Playera",
        )

    def test_importer_only_adds_hash_for_exact_display_name_collisions(self) -> None:
        importer = LegacyProductsImporter(Path("/tmp/productos.db"))

        first = importer._build_product_display_name(
            base_name="Playera Deportiva",
            brand_name="Ad hoc",
            school_name="Frida Kahlo",
            garment_type_name="Deportivo",
            piece_type_name="Playera",
        )
        second = importer._build_product_display_name(
            base_name="Playera Deportiva",
            brand_name="Ad hoc",
            school_name="Patria",
            garment_type_name="Deportivo",
            piece_type_name="Playera",
        )
        repeated = importer._build_product_display_name(
            base_name="Playera Deportiva",
            brand_name="Ad hoc",
            school_name="Frida Kahlo",
            garment_type_name="Deportivo",
            piece_type_name="Playera",
        )

        self.assertEqual(first, "Playera Deportiva | Frida Kahlo | Deportivo | Playera")
        self.assertEqual(second, "Playera Deportiva | Patria | Deportivo | Playera")
        self.assertEqual(repeated, "Playera Deportiva | Frida Kahlo | Deportivo | Playera #2")


if __name__ == "__main__":
    unittest.main()
