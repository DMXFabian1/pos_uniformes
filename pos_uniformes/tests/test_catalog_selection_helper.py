from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.catalog_selection_helper import (
    build_catalog_selection_view,
    build_catalog_selection_view_from_row,
    build_empty_catalog_selection_view,
    find_catalog_row_index_by_variant_id,
    resolve_catalog_row,
)


class CatalogSelectionHelperTests(unittest.TestCase):
    def test_builds_empty_selection_view(self) -> None:
        view = build_empty_catalog_selection_view()

        self.assertEqual(
            view.selection_label,
            "Consulta uniformes y usa filtros macro como Deportivo, Oficial, Basico, Escolta o Accesorio.",
        )

    def test_builds_admin_selection_view_with_legacy_note(self) -> None:
        view = build_catalog_selection_view(
            is_admin=True,
            sku="SKU-001",
            product_name="Playera deportiva azul",
            product_base_name="Playera deportiva",
            school_name="General",
            uniform_type_name="Deportivo",
            piece_type_name="Playera",
            sale_price=Decimal("199.00"),
            stock_actual=4,
            layaway_reserved=1,
            variant_status="ACTIVA",
            origin_label="LEGACY",
            origin_legacy=True,
            legacy_name="Legacy azul",
        )

        self.assertEqual(
            view.selection_label,
            "SKU-001 | Playera deportiva | General | Deportivo | Playera | precio 199.00 | stock 4 | apartado 1 | ACTIVA | LEGACY | legacy: Legacy azul",
        )

    def test_builds_cashier_selection_view_without_admin_fields(self) -> None:
        view = build_catalog_selection_view(
            is_admin=False,
            sku="SKU-002",
            product_name="Falda oficial negra",
            product_base_name="Falda oficial",
            school_name="Colegio Norte",
            uniform_type_name="-",
            piece_type_name="Falda",
            sale_price=Decimal("249.00"),
            stock_actual=0,
            layaway_reserved=0,
            variant_status="INACTIVA",
            origin_label="NUEVO",
            origin_legacy=False,
            legacy_name="",
        )

        self.assertEqual(
            view.selection_label,
            "Falda oficial | SKU-002 | Colegio Norte | Falda | precio 249.00 | stock 0",
        )

    def test_builds_selection_view_from_catalog_row(self) -> None:
        view = build_catalog_selection_view_from_row(
            is_admin=True,
            row={
                "sku": "SKU-003",
                "producto_nombre": "Pants Deportivo | Morelos | Pants #3",
                "producto_nombre_base": "Pants Deportivo",
                "escuela_nombre": "Morelos",
                "tipo_prenda_nombre": "Deportivo",
                "tipo_pieza_nombre": "Pants",
                "precio_venta": Decimal("219.00"),
                "stock_actual": 5,
                "apartado_cantidad": 2,
                "variante_estado": "ACTIVA",
                "origen_etiqueta": "LEGACY",
                "origen_legacy": True,
                "nombre_legacy": "Pants viejo",
            },
        )

        self.assertEqual(
            view.selection_label,
            "SKU-003 | Pants Deportivo | Morelos | Deportivo | Pants | precio 219.00 | stock 5 | apartado 2 | ACTIVA | LEGACY | legacy: Pants viejo",
        )

    def test_resolve_catalog_row_returns_none_for_invalid_index(self) -> None:
        self.assertIsNone(resolve_catalog_row([{"sku": "SKU-001"}], -1))
        self.assertIsNone(resolve_catalog_row([{"sku": "SKU-001"}], 4))

    def test_find_catalog_row_index_by_variant_id_supports_string_and_int(self) -> None:
        row_index = find_catalog_row_index_by_variant_id(
            [
                {"variante_id": "7"},
                {"variante_id": 8},
                {"variante_id": "9"},
            ],
            "8",
        )

        self.assertEqual(row_index, 1)

    def test_find_catalog_row_index_by_variant_id_returns_none_for_missing_value(self) -> None:
        row_index = find_catalog_row_index_by_variant_id(
            [{"variante_id": 7}],
            "xyz",
        )

        self.assertIsNone(row_index)


if __name__ == "__main__":
    unittest.main()
