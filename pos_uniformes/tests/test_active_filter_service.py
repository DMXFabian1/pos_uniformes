from __future__ import annotations

import unittest

from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_active_filters_summary,
    build_filters_label,
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
