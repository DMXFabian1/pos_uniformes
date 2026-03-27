from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_cart_view_helper import build_quote_cart_view


class QuoteCartViewHelperTests(unittest.TestCase):
    def test_builds_empty_quote_cart_view(self) -> None:
        view = build_quote_cart_view([])

        self.assertEqual(view.rows, ())
        self.assertEqual(view.total_items, 0)
        self.assertEqual(view.total, Decimal("0.00"))
        self.assertEqual(view.summary.total_label, "$0.00")
        self.assertEqual(view.summary.summary_label, "Presupuesto vacio.")

    def test_builds_rows_and_summary_for_quote_cart(self) -> None:
        view = build_quote_cart_view(
            [
                {
                    "sku": "SKU-001",
                    "nivel_educativo_nombre": "Primaria",
                    "escuela_nombre": "Colegio Norte",
                    "producto_nombre": "Playera deportiva",
                    "cantidad": 2,
                    "precio_unitario": Decimal("199.00"),
                },
                {
                    "sku": "SKU-002",
                    "nivel_educativo_nombre": "Secundaria",
                    "escuela_nombre": "Instituto Sur",
                    "producto_nombre": "Pants deportivo",
                    "cantidad": 1,
                    "precio_unitario": Decimal("350.50"),
                },
            ]
        )

        self.assertEqual(len(view.rows), 2)
        self.assertEqual(
            view.rows[0].values,
            (
                "SKU-001",
                "Primaria",
                "Colegio Norte",
                "Playera deportiva",
                2,
                Decimal("199.00"),
                Decimal("398.00"),
            ),
        )
        self.assertEqual(view.total_items, 3)
        self.assertEqual(view.total, Decimal("748.50"))
        self.assertEqual(view.summary.total_label, "$748.50")
        self.assertEqual(
            view.summary.summary_label,
            "Lineas: 2 | Piezas: 3 | Total estimado: $748.50",
        )
        self.assertEqual(
            view.summary.school_summary_label,
            "Colegio Norte (2) | Instituto Sur (1)",
        )
        self.assertEqual(view.school_options, ("Colegio Norte", "Instituto Sur"))

    def test_filters_rows_by_school_without_losing_school_summary(self) -> None:
        view = build_quote_cart_view(
            [
                {
                    "sku": "SKU-001",
                    "nivel_educativo_nombre": "Primaria",
                    "escuela_nombre": "Colegio Norte",
                    "producto_nombre": "Playera deportiva",
                    "cantidad": 2,
                    "precio_unitario": Decimal("199.00"),
                },
                {
                    "sku": "SKU-002",
                    "nivel_educativo_nombre": "General",
                    "escuela_nombre": "General",
                    "producto_nombre": "Calcetas",
                    "cantidad": 1,
                    "precio_unitario": Decimal("50.00"),
                },
            ],
            school_filter="Colegio Norte",
        )

        self.assertEqual(len(view.rows), 1)
        self.assertEqual(view.total, Decimal("398.00"))
        self.assertEqual(view.summary.school_summary_label, "Colegio Norte (2) | General (1)")


if __name__ == "__main__":
    unittest.main()
