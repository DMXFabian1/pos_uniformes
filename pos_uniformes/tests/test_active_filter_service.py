from __future__ import annotations

import unittest

from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_active_filters_summary,
    build_filters_label,
    build_active_filter_tokens,
)


class ActiveFilterServiceTests(unittest.TestCase):
    def test_build_active_filter_labels_preserves_order(self) -> None:
        labels = build_active_filter_labels(
            search_text="  pants azul  ",
            multi_filters=(
                ("categoria", ["Uniformes"]),
                ("marca", []),
                ("color", ["Azul", "Marino"]),
            ),
            combo_filters=(
                ("estado", "ACTIVO", "Activos"),
                ("stock", "", "Todos"),
            ),
        )

        self.assertEqual(
            labels,
            [
                'texto="pants azul"',
                "categoria=Uniformes",
                "color=Azul, Marino",
                "estado=Activos",
            ],
        )

    def test_build_active_filters_summary_handles_empty_case(self) -> None:
        self.assertEqual(build_active_filters_summary([]), "Filtros activos: ninguno")

    def test_build_active_filters_summary_joins_with_pipe(self) -> None:
        self.assertEqual(
            build_active_filters_summary(['texto="azul"', "color=Azul"]),
            'Filtros activos: texto="azul" | color=Azul',
        )

    def test_build_filters_label_handles_empty_case(self) -> None:
        self.assertEqual(build_filters_label([]), "sin filtros")

    def test_build_filters_label_joins_with_commas(self) -> None:
        self.assertEqual(
            build_filters_label(['texto="azul"', "color=Azul"]),
            'texto="azul", color=Azul',
        )

    def test_build_active_filter_tokens_expands_individual_filters(self) -> None:
        tokens = build_active_filter_tokens(
            search_text="  azul  ",
            multi_filters=(
                ("categoria", ["Uniformes", "Básico"]),
                ("marca", []),
            ),
            combo_filters=(
                ("uso", "school_only", "Uniforme escolar"),
                ("estado", "", "Estado: todos"),
            ),
        )

        self.assertEqual(
            [(token.key, token.display_text, token.value) for token in tokens],
            [
                ("texto", 'Texto: "azul"', "azul"),
                ("categoria", "Categoria: Uniformes", "Uniformes"),
                ("categoria", "Categoria: Básico", "Básico"),
                ("uso", "Uso: Uniforme escolar", "Uniforme escolar"),
            ],
        )

    def test_fichas_de_inventario_en_palabras_de_la_tienda(self) -> None:
        from pos_uniformes.services.active_filter_service import TITULOS_FILTROS_INVENTARIO

        tokens = build_active_filter_tokens(
            search_text="pants",
            multi_filters=(("pieza", ["Pants 2pz"]),),
            combo_filters=(("stock", "negative", "En negativo"), ("estado", "inactive", "Desactivadas")),
            titles=TITULOS_FILTROS_INVENTARIO,
        )
        self.assertEqual(
            [t.display_text for t in tokens],
            ['Busca: "pants"', "Prenda: Pants 2pz", "Hay: En negativo", "Estado: Desactivadas"],
        )
        # La llave no cambia: quitar la ficha sigue funcionando igual.
        self.assertEqual([t.key for t in tokens], ["texto", "pieza", "stock", "estado"])
