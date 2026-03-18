from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.catalog_selection_helper import (
    build_catalog_selection_view,
    build_empty_catalog_selection_view,
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


if __name__ == "__main__":
    unittest.main()
