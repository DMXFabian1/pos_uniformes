from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from pos_uniformes.importers.legacy_products_importer import LegacyProductRow, LegacyProductsImporter


class LegacyProductsImporterTests(unittest.TestCase):
    def test_rejects_unknown_import_mode(self) -> None:
        with self.assertRaises(ValueError):
            LegacyProductsImporter(sqlite_path=Path("/tmp/productos.db"), import_mode="otro")

    def test_filter_rows_by_missing_skus_skips_existing(self) -> None:
        rows = [
            LegacyProductRow(
                sku="SKU000001",
                nombre="Camisa Escolar Talla CH",
                tipo_prenda="Oficial",
                tipo_pieza="Camisa",
                color="Blanco",
                talla="CH",
                marca="Sin marca",
                atributo="",
                nivel_educativo="",
                genero="",
                escuela_id=1,
                qr_path="",
                label_split_path="",
                image_path="",
                ubicacion="",
                escudo="",
                inventario=0,
                precio=Decimal("100.00"),
                last_modified=None,
            ),
            LegacyProductRow(
                sku="SKU000002",
                nombre="Camisa Escolar Talla MD",
                tipo_prenda="Oficial",
                tipo_pieza="Camisa",
                color="Blanco",
                talla="MD",
                marca="Sin marca",
                atributo="",
                nivel_educativo="",
                genero="",
                escuela_id=1,
                qr_path="",
                label_split_path="",
                image_path="",
                ubicacion="",
                escudo="",
                inventario=0,
                precio=Decimal("110.00"),
                last_modified=None,
            ),
        ]
        session = MagicMock()
        session.scalars.return_value = ["SKU000001"]

        filtered = LegacyProductsImporter._filter_rows_by_missing_skus(session, rows)

        self.assertEqual([row.sku for row in filtered], ["SKU000002"])

    def test_prime_existing_catalog_state_reuses_existing_family_and_variants(self) -> None:
        importer = LegacyProductsImporter(sqlite_path=Path("/tmp/productos.db"), import_mode="missing_only")
        importer._display_name_counts = defaultdict(int)
        product = SimpleNamespace(
            id=7,
            nombre="Camisa Escolar | Escuela Demo | Oficial | Camisa",
            nombre_base="Camisa Escolar",
            genero="Niña",
            marca=SimpleNamespace(nombre="Sin marca"),
            escuela=SimpleNamespace(nombre="Escuela Demo"),
            tipo_prenda=SimpleNamespace(nombre="Oficial"),
            tipo_pieza=SimpleNamespace(nombre="Camisa"),
            nivel_educativo=SimpleNamespace(nombre="Primaria"),
            atributo=SimpleNamespace(nombre="Manga corta"),
            variantes=[
                SimpleNamespace(talla="CH", color="Blanco"),
                SimpleNamespace(talla="MD", color="Blanco"),
            ],
        )
        scalar_result = MagicMock()
        scalar_result.all.return_value = [product]
        session = MagicMock()
        session.scalars.return_value = scalar_result
        products: dict[tuple[str, str, str | None, str | None, str | None, str | None, str | None, str | None], object] = {}
        variant_keys: set[tuple[int, str, str]] = set()

        importer._prime_existing_catalog_state(session, products=products, variant_keys=variant_keys)

        family_key = (
            "Camisa Escolar",
            "Sin marca",
            "Escuela Demo",
            "Oficial",
            "Camisa",
            "Primaria",
            "Manga corta",
            "Niña",
        )
        self.assertIs(products[family_key], product)
        self.assertEqual(
            variant_keys,
            {
                (7, "CH", "Blanco"),
                (7, "MD", "Blanco"),
            },
        )
        self.assertEqual(
            importer._display_name_counts[("Sin marca", "Camisa Escolar | Escuela Demo | Oficial | Camisa")],
            1,
        )


if __name__ == "__main__":
    unittest.main()
