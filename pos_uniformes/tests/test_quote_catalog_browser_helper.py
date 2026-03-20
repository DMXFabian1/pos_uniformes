from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_catalog_browser_helper import (
    build_quote_catalog_browser,
    build_quote_catalog_level_options,
    build_quote_catalog_school_options,
)


class QuoteCatalogBrowserHelperTests(unittest.TestCase):
    def test_build_school_options_skips_general(self) -> None:
        options = build_quote_catalog_school_options(
            [
                {"escuela_nombre": "General", "nivel_educativo_nombre": "Primaria"},
                {"escuela_nombre": "Colegio Mexico", "nivel_educativo_nombre": "Primaria"},
                {"escuela_nombre": "Instituto Hidalgo", "nivel_educativo_nombre": "Secundaria"},
                {"escuela_nombre": "Colegio Mexico", "nivel_educativo_nombre": "Primaria"},
            ]
        )

        self.assertEqual(options, ("Colegio Mexico", "Instituto Hidalgo"))

    def test_build_school_options_respects_selected_level(self) -> None:
        options = build_quote_catalog_school_options(
            [
                {"escuela_nombre": "Colegio Mexico", "nivel_educativo_nombre": "Primaria"},
                {"escuela_nombre": "Instituto Hidalgo", "nivel_educativo_nombre": "Secundaria"},
                {"escuela_nombre": "Jean Piaget", "nivel_educativo_nombre": "Preescolar"},
                {"escuela_nombre": "General", "nivel_educativo_nombre": "Preescolar"},
            ],
            level_filter="Preescolar",
        )

        self.assertEqual(options, ("Jean Piaget",))

    def test_filters_school_and_general_extras(self) -> None:
        rows, summary = build_quote_catalog_browser(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Pantalon", "Pantalon", "32", "Azul"),
                _row("SKU-2", "Primaria", "General", "Calcetas", "Accesorio", "U", "Blanco"),
                _row("SKU-3", "Secundaria", "Instituto Hidalgo", "Falda", "Falda", "30", "Gris"),
            ],
            level_filter="Primaria",
            school_filter="Colegio Mexico",
            include_general=True,
            search_text="",
        )

        self.assertEqual([row.sku for row in rows], ["SKU-1", "SKU-2"])
        self.assertIn("incluye extras generales", summary.status_label)

    def test_filters_by_search_text(self) -> None:
        rows, _ = build_quote_catalog_browser(
            snapshot_rows=[
                _row("SKU-1", "Primaria", "Colegio Mexico", "Pantalon", "Pantalon", "32", "Azul"),
                _row("SKU-2", "Primaria", "General", "Calcetas", "Accesorio", "U", "Blanco"),
            ],
            level_filter="",
            school_filter="",
            include_general=True,
            search_text="calcetas",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].sku, "SKU-2")

    def test_build_level_options_skips_empty_and_sin_nivel(self) -> None:
        options = build_quote_catalog_level_options(
            [
                {"nivel_educativo_nombre": "Sin nivel"},
                {"nivel_educativo_nombre": "Primaria"},
                {"nivel_educativo_nombre": "Secundaria"},
                {"nivel_educativo_nombre": "Primaria"},
            ]
        )

        self.assertEqual(options, ("Primaria", "Secundaria"))


def _row(
    sku: str,
    nivel: str,
    escuela: str,
    producto: str,
    tipo_prenda: str,
    talla: str,
    color: str,
) -> dict[str, object]:
    return {
        "sku": sku,
        "nivel_educativo_nombre": nivel,
        "escuela_nombre": escuela,
        "producto_nombre": producto,
        "producto_nombre_base": producto,
        "tipo_prenda_nombre": tipo_prenda,
        "tipo_pieza_nombre": "Uniforme",
        "talla": talla,
        "color": color,
        "precio_venta": Decimal("199.00"),
        "stock_actual": 5,
        "producto_activo": True,
        "variante_activo": True,
        "producto_descripcion": "",
    }


if __name__ == "__main__":
    unittest.main()
