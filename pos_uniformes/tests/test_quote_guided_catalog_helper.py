from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_guided_catalog_helper import build_guided_catalog_view


class QuoteGuidedCatalogHelperTests(unittest.TestCase):
    def test_school_mode_filters_schools_by_level_and_sorts_them(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niño"),
                _row("SKU-2", "Primaria", "Instituto Hidalgo", "Niña"),
                _row("SKU-3", "Secundaria", "Zavala", "Niño"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="",
            gender_filter="TODOS",
        )

        self.assertEqual([option.label for option in view.school_options], ["Colegio Mexico", "Instituto Hidalgo"])
        self.assertEqual(view.empty_label, "Selecciona una escuela para ver productos sugeridos.")

    def test_oficial_nina_keeps_official_unisex(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial", pieza="Falda"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Oficial", pieza="Suéter"),
                _row("SKU-3", "Primaria", "Colegio Mexico", "Niño", "Oficial", pieza="Pantalón"),
                _row("SKU-4", "Primaria", "Colegio Mexico", "", "Conjunto", producto="Pants Deportivo", pieza="Pants"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niña",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-1", "SKU-2"])

    def test_oficial_filters_keep_shared_camisa_even_if_gender_is_other_side(self) -> None:
        nina_view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Hombre", "Oficial", producto="Camisa Escolar", pieza="Camisa"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Mujer", "Oficial", producto="Blusa Escolar", pieza="Blusa"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niña",
        )
        nino_view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Mujer", "Oficial", producto="Playera Polo", pieza="Playera"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Mujer", "Oficial", producto="Falda Escolar", pieza="Falda"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niño",
        )

        self.assertEqual([card.sku for card in nina_view.product_cards], ["SKU-2", "SKU-1"])
        self.assertEqual([card.sku for card in nino_view.product_cards], ["SKU-1"])

    def test_oficial_nino_keeps_official_unisex(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial", pieza="Falda"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Oficial", pieza="Suéter"),
                _row("SKU-3", "Primaria", "Colegio Mexico", "Niño", "Oficial", pieza="Pantalón"),
                _row("SKU-4", "Primaria", "Colegio Mexico", None, "Conjunto", producto="Playera Deportiva", pieza="Playera"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niño",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-2", "SKU-3"])

    def test_oficial_filters_exclude_deportivo_named_only_in_product_title(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Conjunto", producto="Playera Deportiva", pieza="Playera"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Blusa Oficial", pieza="Blusa"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niña",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-2"])

    def test_deportivo_filter_shows_only_deportivo(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Deportivo"),
                _row("SKU-3", "Primaria", "Colegio Mexico", "Niño", "Deportivo"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Deportivo",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-2", "SKU-3"])

    def test_deportivo_filter_prioritizes_complete_uniforms_before_loose_pieces(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Playera Deportiva"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Chamarra Deportiva"),
                _row("SKU-3", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Pants Deportivo"),
                _row("SKU-4", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Uniforme Deportivo 3 Piezas"),
                _row("SKU-5", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Pants 2pz Deportivo"),
                _row("SKU-6", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Short Deportivo"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Deportivo",
        )

        self.assertEqual(
            [card.sku for card in view.product_cards],
            ["SKU-4", "SKU-5", "SKU-2", "SKU-3", "SKU-1", "SKU-6"],
        )

    def test_basics_mode_only_uses_general_products(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "General", "Unisex"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex"),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-1"])
        self.assertEqual(view.path_label, "Basicos > Todos")

    def test_oficial_filter_on_basics_keeps_only_official_general(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "General", "Unisex", "Oficial"),
                _row("SKU-2", "Primaria", "General", "", "Deportivo"),
                _row("SKU-3", "Primaria", "General", "Niña", "Oficial"),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Oficial Niña",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-1", "SKU-3"])


def _row(
    sku: str,
    nivel: str,
    escuela: str,
    genero: str | None,
    tipo_prenda: str = "Oficial",
    producto: str | None = None,
    pieza: str = "Uniforme",
) -> dict[str, object]:
    return {
        "sku": sku,
        "nivel_educativo_nombre": nivel,
        "escuela_nombre": escuela,
        "producto_genero": genero,
        "producto_nombre": producto or f"Producto {sku}",
        "producto_nombre_base": producto or f"Producto {sku}",
        "tipo_prenda_nombre": tipo_prenda,
        "tipo_pieza_nombre": pieza,
        "talla": "12",
        "color": "Azul",
        "precio_venta": Decimal("199.00"),
        "stock_actual": 5,
        "producto_activo": True,
        "variante_activo": True,
        "producto_descripcion": "",
    }


if __name__ == "__main__":
    unittest.main()
