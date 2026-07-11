from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_guided_catalog_helper import (
    build_guided_catalog_view,
    build_search_price_groups,
    favorites_variant_sort_key,
)


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

    def test_school_mode_excludes_non_uniform_school_rows(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Camisa Escolar", pieza="Camisa"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Casual", producto="Short Mezclilla", pieza="Short"),
                _row("SKU-3", "Primaria", "Instituto Hidalgo", "Niña", "Deportivo", producto="Playera Deportiva", pieza="Playera"),
            ],
            mode_key="school",
            level_filter="Primaria",
            school_filter="",
            gender_filter="TODOS",
        )

        self.assertEqual([option.label for option in view.school_options], ["Colegio Mexico", "Instituto Hidalgo"])

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
                # _PIEZA_ORDER: Playera va antes que Camisa (2026-05-24)
                ("Playera", "Prendas principales"),
                ("Camisa", "Prendas principales"),
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

        # Suéter (unisex) antes que Falda por _PIEZA_ORDER; lo importante es
        # que ambas piezas se conservan para Oficial Niña.
        self.assertEqual([card.sku for card in view.product_cards], ["SKU-2", "SKU-1"])

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

        # Camisa antes que Blusa por _PIEZA_ORDER; lo importante es que la
        # camisa compartida se conserva en la vista de Niña.
        self.assertEqual([card.sku for card in nina_view.product_cards], ["SKU-1", "SKU-2"])
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
                # El orden de tarjetas viene de tipo_pieza (_PIEZA_ORDER),
                # como en la DB real — no del nombre del producto.
                _row("SKU-1", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Playera Deportiva", pieza="Playera"),
                _row("SKU-2", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Chamarra Deportiva", pieza="Chamarra"),
                _row("SKU-3", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Pants Deportivo", pieza="Pants Suelto"),
                _row("SKU-4", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Uniforme Deportivo 3 Piezas", pieza="Pants 3pz"),
                _row("SKU-5", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Pants 2pz Deportivo", pieza="Pants 2pz"),
                _row("SKU-6", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Short Deportivo", pieza="Short"),
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

    def test_basics_mode_excludes_regular_categories_even_if_school_is_general(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=[
                _row(
                    "SKU-1",
                    "Sin nivel",
                    "General",
                    "Unisex",
                    "Básico",
                    producto="Pants Escolar",
                    pieza="Pants 2pz",
                    categoria="Básico",
                ),
                _row(
                    "SKU-2",
                    "Sin nivel",
                    "General",
                    "Unisex",
                    "Deportivo casual",
                    producto="Short Deportivo",
                    pieza="Short",
                    categoria="Deportivo casual",
                ),
            ],
            mode_key="basics",
            level_filter="",
            school_filter="",
            gender_filter="Todos",
            bucket_filter="Todos",
            piece_filter="Pants 2pz",
        )

        self.assertEqual([card.sku for card in view.product_cards], ["SKU-1"])

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
        # _PIEZA_ORDER: Playera antes que Pantalón
        self.assertEqual([option.label for option in basics_view.piece_options], ["Playera", "Pantalón"])
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

    def test_school_mode_groups_models_before_variants(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Falda Escolar Tabla", pieza="Falda", talla="10"),
            _row("SKU-2", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Falda Escolar Tabla", pieza="Falda", talla="12"),
            _row("SKU-3", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Blusa Escolar Blanca", pieza="Camisa", talla="8"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial Niña",
        )

        self.assertEqual([card.title for card in view.product_cards], ["Blusa Escolar Blanca", "Falda Escolar Tabla"])
        self.assertEqual(view.product_cards[0].subtitle, "Tallas: 8")
        self.assertEqual(view.selected_product_key, view.product_cards[0].key)
        self.assertEqual(
            [option.label for option in view.variant_options],
            ["Talla 8 · $199.00"],
        )

    def test_school_mode_exposes_line_and_profile_options_for_official(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Suéter Escolar", pieza="Suéter"),
            _row("SKU-2", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Suéter Escolar", pieza="Suéter"),
            _row("SKU-3", "Primaria", "Colegio Mexico", "Unisex", "Deportivo", producto="Playera Deportiva", pieza="Playera"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial",
        )

        self.assertEqual([option.label for option in view.gender_options], ["Deportivo", "Oficial", "Todos"])
        self.assertEqual([option.label for option in view.profile_options], ["Niña", "Niño", "Compartido", "Todos"])

    def test_school_official_profile_ignores_shared_pants(self) -> None:
        snapshot_rows = [
            _row("SKU-1", "Primaria", "Colegio Mexico", "Niña", "Oficial", producto="Suéter Escolar", pieza="Suéter"),
            _row("SKU-2", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Suéter Escolar", pieza="Suéter"),
            _row("SKU-3", "Primaria", "Colegio Mexico", "Unisex", "Oficial", producto="Pants Escolar", pieza="Pants Suelto"),
        ]

        nina_view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial",
            profile_filter="Niña",
        )
        shared_view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="Oficial",
            profile_filter="Compartido",
        )

        self.assertEqual([card.title for card in nina_view.product_cards], ["Suéter Escolar"])
        self.assertEqual([card.title for card in shared_view.product_cards], ["Pants Escolar"])

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
        self.assertEqual(view.product_cards[0].subtitle, "Tallas: 12")
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

        self.assertEqual(view.product_cards[0].subtitle, "Tallas: 12")

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


_SCHOOL_ID: dict[str, int] = {"General": 0, "Colegio Mexico": 1, "Escuela Deportiva": 2}


def _row(
    sku: str,
    nivel: str,
    escuela: str,
    genero: str | None,
    tipo_prenda: str = "Oficial",
    producto: str | None = None,
    pieza: str = "Uniforme",
    talla: str = "12",
    categoria: str = "Uniformes",
) -> dict[str, object]:
    return {
        "sku": sku,
        "nivel_educativo_nombre": nivel,
        "escuela_nombre": escuela,
        "escuela_id": _SCHOOL_ID.get(escuela, 99),
        "categoria_nombre": categoria,
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


    def test_school_links_inject_general_product_into_school(self) -> None:
        school_links = [
            {
                "escuela_id": 1,
                "escuela_nombre": "Colegio Mexico",
                "producto_nombre_base": "Pantalón Azul",
            }
        ]
        snapshot_rows = [
            _row("SKU-OFICIAL", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Camisa Escolar", pieza="Camisa"),
            _row("SKU-GENERAL", "Sin nivel", "General", "Unisex", "Oficial", producto="Pantalón Azul", pieza="Pantalón"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="TODOS",
            school_links=school_links,
        )

        titles = [card.title for card in view.product_cards]
        self.assertIn("Pantalón Azul", titles)
        self.assertIn("Camisa Escolar", titles)

    def test_school_links_respect_own_nivel_over_school_first_level(self) -> None:
        """Un general ligado CON su propio nivel cae en ese nivel, no en el primero de la escuela.

        La escuela tiene productos propios en Primaria (primero) y Secundaria.
        Un general ligado con nivel=Secundaria debe salir solo en Secundaria.
        """
        school_links = [
            {
                "escuela_id": 1,
                "escuela_nombre": "Colegio Mexico",
                "producto_nombre_base": "Falda Gales",
            }
        ]
        snapshot_rows = [
            _row("SKU-PRI", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Camisa Prim", pieza="Camisa"),
            _row("SKU-SEC", "Secundaria", "Colegio Mexico", "Niño", "Oficial", producto="Camisa Sec", pieza="Camisa"),
            # General ligado con su PROPIO nivel = Secundaria
            _row("SKU-GEN", "Secundaria", "General", "Unisex", "Oficial", producto="Falda Gales", pieza="Falda"),
        ]

        def _titles(level: str) -> list[str]:
            view = build_guided_catalog_view(
                snapshot_rows=snapshot_rows,
                mode_key="school",
                level_filter=level,
                school_filter="Colegio Mexico",
                gender_filter="TODOS",
                school_links=school_links,
            )
            return [card.title for card in view.product_cards]

        self.assertIn("Falda Gales", _titles("Secundaria"))     # aparece en Secundaria
        self.assertNotIn("Falda Gales", _titles("Primaria"))    # NO en Primaria (antes sí caía aquí)

    def test_school_links_nivel_derived_from_all_rows_not_just_official(self) -> None:
        """School with only OTRO-type own products still gets correct nivel for injected products."""
        school_links = [
            {
                "escuela_id": 1,
                "escuela_nombre": "Colegio Mexico",
                "producto_nombre_base": "Pantalón General",
            }
        ]
        snapshot_rows = [
            # School has a product but it's OTRO type (not OFICIAL/DEPORTIVO) — won't appear in school_mode_rows
            _row("SKU-OTRO", "Primaria", "Colegio Mexico", "Unisex", "Casual", producto="Bolso Escolar", pieza="Accesorio"),
            # General product to inject
            _row("SKU-GENERAL", "Sin nivel", "General", "Unisex", "Oficial", producto="Pantalón General", pieza="Pantalón"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="TODOS",
            school_links=school_links,
        )

        self.assertIn("Primaria", [opt.key for opt in view.level_options])
        self.assertIn("Colegio Mexico", [opt.key for opt in view.school_options])
        titles = [card.title for card in view.product_cards]
        self.assertIn("Pantalón General", titles)

    def test_school_links_no_duplicate_if_school_already_has_product(self) -> None:
        school_links = [
            {
                "escuela_id": 1,
                "escuela_nombre": "Colegio Mexico",
                "producto_nombre_base": "Camisa Escolar",
            }
        ]
        snapshot_rows = [
            _row("SKU-OWN", "Primaria", "Colegio Mexico", "Niño", "Oficial", producto="Camisa Escolar", pieza="Camisa"),
            _row("SKU-GEN", "Sin nivel", "General", "Unisex", "Oficial", producto="Camisa Escolar", pieza="Camisa"),
        ]

        view = build_guided_catalog_view(
            snapshot_rows=snapshot_rows,
            mode_key="school",
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            gender_filter="TODOS",
            school_links=school_links,
        )

        titles = [card.title for card in view.product_cards]
        self.assertEqual(titles.count("Camisa Escolar"), 1)


class SearchPriceGroupsTests(unittest.TestCase):
    """Tallas de menor a mayor dentro de cada grupo de precio en la búsqueda guiada.

    Bug original: la tarjeta de resultados pintaba las variantes en el orden
    de relevancia de Meilisearch — las tallas salían revueltas.
    """

    @staticmethod
    def _variant(talla: str, precio: float = 100.0, sku: str = "") -> dict[str, object]:
        return {"talla": talla, "precio_venta": precio, "sku": sku or f"SKU-{talla}", "color": ""}

    def test_numeric_sizes_sort_numerically_not_as_strings(self) -> None:
        groups = build_search_price_groups(
            [self._variant(t) for t in ["12", "4", "10", "6", "8"]]
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual([v["talla"] for v in groups[0][1]], ["4", "6", "8", "10", "12"])

    def test_letter_sizes_sort_by_size_scale_not_alphabet(self) -> None:
        groups = build_search_price_groups(
            [self._variant(t) for t in ["EXG", "CH", "GD", "MD"]]
        )
        self.assertEqual([v["talla"] for v in groups[0][1]], ["CH", "MD", "GD", "EXG"])

    def test_numeric_sizes_come_before_letter_sizes(self) -> None:
        groups = build_search_price_groups(
            [self._variant(t) for t in ["GD", "14", "CH", "16"]]
        )
        self.assertEqual([v["talla"] for v in groups[0][1]], ["14", "16", "CH", "GD"])

    def test_price_groups_sorted_ascending(self) -> None:
        groups = build_search_price_groups(
            [
                self._variant("6", precio=250.0),
                self._variant("4", precio=150.0),
                self._variant("8", precio=250.0),
            ]
        )
        self.assertEqual([precio for precio, _ in groups], [150.0, 250.0])
        self.assertEqual([v["talla"] for v in groups[1][1]], ["6", "8"])

    def test_empty_variantes_returns_empty(self) -> None:
        self.assertEqual(build_search_price_groups([]), [])

    def test_range_sizes_sort_by_numeric_start_not_as_strings(self) -> None:
        # Tallas reales de calcetas: como texto "13-18" quedaba antes que "3-5".
        groups = build_search_price_groups(
            [self._variant(t) for t in ["13-18", "0-0", "3-5", "9-12", "0-2", "6-8"]]
        )
        self.assertEqual(
            [v["talla"] for v in groups[0][1]],
            ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18"],
        )

    def test_ranges_and_plain_numbers_interleave_numerically(self) -> None:
        groups = build_search_price_groups(
            [self._variant(t) for t in ["4", "13-18", "3-5", "12"]]
        )
        self.assertEqual([v["talla"] for v in groups[0][1]], ["3-5", "4", "12", "13-18"])


class FavoritesVariantSortKeyTests(unittest.TestCase):
    """Orden del picker de variantes del diálogo de favoritos.

    Bug original: las tallas de letra ordenaban alfabético (CH < EXG < GD < MD).
    """

    @staticmethod
    def _row(talla: str, escuela: str = "General", precio: str = "100") -> dict[str, object]:
        return {"talla": talla, "escuela_nombre": escuela, "precio_venta": precio}

    def test_letter_sizes_sort_by_scale_not_alphabet(self) -> None:
        rows = [self._row(t) for t in ["EXG", "CH", "GD", "MD"]]
        rows.sort(key=favorites_variant_sort_key)
        self.assertEqual([r["talla"] for r in rows], ["CH", "MD", "GD", "EXG"])

    def test_numeric_sizes_sort_numerically(self) -> None:
        rows = [self._row(t) for t in ["12", "4", "10", "6"]]
        rows.sort(key=favorites_variant_sort_key)
        self.assertEqual([r["talla"] for r in rows], ["4", "6", "10", "12"])

    def test_general_school_comes_first_then_price_ascending(self) -> None:
        rows = [
            self._row("4", escuela="Colegio Mexico", precio="150"),
            self._row("6", escuela="General", precio="250"),
            self._row("4", escuela="General", precio="150"),
        ]
        rows.sort(key=favorites_variant_sort_key)
        self.assertEqual(
            [(r["escuela_nombre"], r["talla"]) for r in rows],
            [("General", "4"), ("General", "6"), ("Colegio Mexico", "4")],
        )


if __name__ == "__main__":
    unittest.main()
