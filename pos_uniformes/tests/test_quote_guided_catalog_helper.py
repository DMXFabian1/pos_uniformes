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

    def test_basics_mode_groups_piece_options_by_mental_category(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "", "General", "", "Oficial", pieza="Camisa"),
                _row("SKU-2", "", "General", "", "Oficial", pieza="Playera"),
                _row("SKU-3", "", "General", "", "Oficial", pieza="Chaleco"),
                _row("SKU-4", "", "General", "", "Oficial", pieza="Calceta"),
                _row("SKU-5", "", "General", "", "Oficial", pieza="Bata"),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Todos",
        )

        self.assertEqual(
            [(option.label, option.group_label) for option in view.piece_options],
            [
                ("Camisa", "Prendas principales"),
                ("Playera", "Prendas principales"),
                ("Chaleco", "Complementos"),
                ("Calceta", "Accesorios"),
                ("Bata", "Especial"),
            ],
        )

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
                _row("SKU-1", "Primaria", "General", "Unisex", pieza="Uniforme"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex"),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            piece_filter="Uniforme",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-1"])
        self.assertEqual(view.path_label, "Basicos > Todos > Uniforme")

    def test_basics_mode_can_filter_basicos_vs_extras(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Sin nivel", "General", "Unisex", "Básico", producto="Pantalón Escolar", pieza="Pantalón"),
            _row("SKU-2", "Sin nivel", "General", "Unisex", "Accesorio", producto="Calceta Escolar", pieza="Calceta"),
            _row("SKU-3", "Sin nivel", "General", "Unisex", "Accesorio", producto="Playera Polo Blanca", pieza="Playera"),
        ]

        basics_view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Basicos",
            piece_filter="Pantalón",
        )
        extras_view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Extras",
            piece_filter="Calceta",
        )

        self.assertEqual([card.sku for card in basics_view.product_cards], ["SKU-1"])
        self.assertEqual([card.sku for card in extras_view.product_cards], ["SKU-2"])
        self.assertEqual([option.label for option in basics_view.bucket_options], ["Basicos", "Extras", "Todos"])
        self.assertEqual([option.label for option in basics_view.piece_options], ["Pantalón", "Playera"])
        self.assertEqual(basics_view.path_label, "Basicos > Todos > Basicos > Pantalón")

    def test_basics_mode_requires_piece_and_groups_models_before_variants(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Sin nivel", "General", "Unisex", "Accesorio", producto="Bata Manga Corta Blanca", pieza="Bata", talla="40"),
            _row("SKU-2", "Sin nivel", "General", "Unisex", "Accesorio", producto="Bata Manga Corta Blanca", pieza="Bata", talla="42"),
            _row("SKU-3", "Sin nivel", "General", "Unisex", "Accesorio", producto="Bata Manga Larga Blanca", pieza="Bata", talla="12"),
        ]

        without_piece = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Extras",
        )
        with_piece = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Extras",
            piece_filter="Bata",
        )

        self.assertEqual(without_piece.empty_label, "Selecciona un tipo de pieza para ver modelos.")
        self.assertEqual([option.label for option in without_piece.piece_options], ["Bata"])
        self.assertEqual(len(with_piece.product_cards), 2)
        self.assertEqual(with_piece.product_cards[0].title, "Bata Manga Corta Blanca")
        self.assertEqual(with_piece.selected_product_key, with_piece.product_cards[0].key)
        self.assertEqual(
            [option.label for option in with_piece.variant_options],
            ["Talla 40 · $199.00", "Talla 42 · $199.00"],
        )

    def test_variant_options_sort_sizes_from_small_to_large(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Sin nivel", "General", "Unisex", "Oficial", producto="Chaleco Claudia", pieza="Chaleco", talla="32"),
            _row("SKU-2", "Sin nivel", "General", "Unisex", "Oficial", producto="Chaleco Claudia", pieza="Chaleco", talla="10"),
            _row("SKU-3", "Sin nivel", "General", "Unisex", "Oficial", producto="Chaleco Claudia", pieza="Chaleco", talla="14"),
            _row("SKU-4", "Sin nivel", "General", "Unisex", "Oficial", producto="Chaleco Claudia", pieza="Chaleco", talla="28"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Basicos",
            piece_filter="Chaleco",
        )

        self.assertEqual(
            [option.label for option in view.variant_options],
            ["Talla 10 · $199.00", "Talla 14 · $199.00", "Talla 28 · $199.00", "Talla 32 · $199.00"],
        )

    def test_product_cards_only_keep_name_talla_color_and_price(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row(
                    "SKU-1",
                    "Secundaria",
                    "ESTV 663",
                    "Unisex",
                    "Deportivo",
                    producto="Pants 2pz Lobito Liso ESTV 663",
                    pieza="Pants",
                ),
            ],
            mode_key="school",
            level_filter="Secundaria",
            school_filter="ESTV 663",
            gender_filter="Deportivo",
        )

        self.assertEqual(view.product_cards[0].title, "Pants 2pz Lobito Liso ESTV 663")
        self.assertEqual(view.product_cards[0].subtitle, "Talla 12 · Azul")
        self.assertEqual(view.product_cards[0].meta_label, "")
        self.assertEqual(view.product_cards[0].price_label, "$199.00")

    def test_product_cards_hide_ad_hoc_color(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row(
                    "SKU-1",
                    "Secundaria",
                    "ESTV 663",
                    "Unisex",
                    "Deportivo",
                    producto="Playera Deportiva Blanca",
                    pieza="Playera",
                )
            ],
            mode_key="school",
            level_filter="Secundaria",
            school_filter="ESTV 663",
            gender_filter="Deportivo",
        )

        row = dict(_row("SKU-1", "Secundaria", "ESTV 663", "Unisex", "Deportivo", producto="Playera Deportiva Blanca", pieza="Playera"))
        row["color"] = "Ad hoc"
        view = build_guided_catalog_view(
            snapshot_rows=[row],
            mode_key="school",
            level_filter="Secundaria",
            school_filter="ESTV 663",
            gender_filter="Deportivo",
        )

        self.assertEqual(view.product_cards[0].subtitle, "Talla 12")

    def test_oficial_filter_on_basics_keeps_only_official_general(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "General", "Unisex", "Oficial", pieza="Uniforme"),
                _row("SKU-2", "Primaria", "General", "", "Deportivo"),
                _row("SKU-3", "Primaria", "General", "Niña", "Oficial", pieza="Uniforme"),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Oficial Niña",
            piece_filter="Uniforme",
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
    talla: str = "12",
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
        "talla": talla,
        "color": "Azul",
        "precio_venta": Decimal("199.00"),
        "stock_actual": 5,
        "producto_activo": True,
        "variante_activo": True,
        "producto_descripcion": "",
    }


if __name__ == "__main__":
    unittest.main()
