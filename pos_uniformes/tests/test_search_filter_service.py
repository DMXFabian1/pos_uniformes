from __future__ import annotations

import unittest

from pos_uniformes.services.search_filter_service import row_matches_search, tokenize_search_text


class SearchFilterServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {
            "sku": "SKU000123",
            "categoria_nombre": "Uniformes",
            "marca_nombre": "Atlas",
            "escuela_nombre": "Colegio Mexico",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pantalon",
            "producto_nombre": "Pants Deportivo",
            "producto_nombre_base": "Pants",
            "producto_descripcion": "Pants azul marino",
            "nombre_legacy": "Pants dep",
            "talla": "14",
            "color": "Azul Marino",
            "origen_etiqueta": "IMPORTADO",
            "producto_estado": "ACTIVO",
            "variante_estado": "ACTIVA",
            "fallback_text": "sin incidencias",
        }
        self.alias_map = {
            "sku": ("sku",),
            "escuela": ("escuela_nombre",),
            "tipo": ("tipo_prenda_nombre",),
            "pieza": ("tipo_pieza_nombre",),
            "producto": ("producto_nombre_base", "producto_nombre"),
            "legacy": ("nombre_legacy",),
            "talla": ("talla",),
            "color": ("color",),
            "marca": ("marca_nombre",),
            "categoria": ("categoria_nombre",),
            "origen": ("origen_etiqueta",),
            "estado": ("producto_estado", "variante_estado"),
            "fallback": ("fallback_text",),
        }
        self.general_fields = (
            "sku",
            "categoria_nombre",
            "marca_nombre",
            "escuela_nombre",
            "tipo_prenda_nombre",
            "tipo_pieza_nombre",
            "producto_nombre",
            "producto_nombre_base",
            "producto_descripcion",
            "nombre_legacy",
            "talla",
            "color",
            "origen_etiqueta",
            "producto_estado",
            "variante_estado",
            "fallback_text",
        )

    def test_tokenize_search_text_supports_quotes(self) -> None:
        self.assertEqual(
            tokenize_search_text('producto:"pants deportivo" color:azul'),
            ["producto:pants deportivo", "color:azul"],
        )

    def test_tokenize_search_text_falls_back_on_invalid_quotes(self) -> None:
        self.assertEqual(
            tokenize_search_text('producto:"pants azul'),
            ['producto:"pants', "azul"],
        )

    def test_row_matches_general_text(self) -> None:
        self.assertTrue(
            row_matches_search(
                self.row,
                search_text="azul atlas",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_row_matches_alias_text(self) -> None:
        self.assertTrue(
            row_matches_search(
                self.row,
                search_text="tipo:deportivo escuela:mexico",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_row_matches_general_text_without_accent(self) -> None:
        accented_row = dict(
            self.row,
            producto_nombre="Corbatín Rojo",
            producto_nombre_base="Corbatín",
            producto_descripcion="Corbatín escolar",
            nombre_legacy="Corbatín rojo",
        )
        self.assertTrue(
            row_matches_search(
                accented_row,
                search_text="corbatin",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_row_matches_alias_text_without_accent(self) -> None:
        accented_row = dict(self.row, producto_nombre="Corbatín Rojo", producto_nombre_base="Corbatín")
        self.assertTrue(
            row_matches_search(
                accented_row,
                search_text="producto:corbatin",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_row_rejects_non_matching_alias(self) -> None:
        self.assertFalse(
            row_matches_search(
                self.row,
                search_text="color:rojo",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_unknown_alias_does_not_match_implicitly(self) -> None:
        self.assertFalse(
            row_matches_search(
                self.row,
                search_text="folio:sku000123",
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )

    def test_invalid_quote_in_alias_value_degrades_gracefully(self) -> None:
        self.assertTrue(
            row_matches_search(
                self.row,
                search_text='producto:"pants azul',
                alias_map=self.alias_map,
                general_fields=self.general_fields,
            )
        )
