"""El color va en el nombre solo cuando el producto tiene más de uno.

Short Deportivo (7 colores) salía «Short Deportivo T: Unitalla» en las siete
etiquetas, y en la Libreta no se sabía cuál se vendió (2026-10-13).
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services.nombre_con_color_service import (
    es_multicolor,
    multicolor_de_producto,
    multicolor_en_filas,
    nombre_con_color,
    nombre_de_variante,
)


def _producto(nombre, colores, **extra):
    p = SimpleNamespace(nombre=nombre, nombre_base=nombre, escuela=None, **extra)
    p.variantes = [SimpleNamespace(color=c, activo=True, producto=p) for c in colores]
    return p


class ReglaTests(unittest.TestCase):
    def test_mas_de_un_color_de_verdad(self) -> None:
        self.assertTrue(es_multicolor(["Rojo", "Negro"]))
        self.assertFalse(es_multicolor(["Rojo", "rojo ", "ROJO"]))
        self.assertFalse(es_multicolor(["Rojo", "Sin color", ""]))
        self.assertFalse(es_multicolor([]))

    def test_nombre_con_color_solo_si_hace_falta(self) -> None:
        self.assertEqual(nombre_con_color("Short Deportivo", "Rojo", multicolor=True), "Short Deportivo Rojo")
        self.assertEqual(nombre_con_color("Pijama de Cuadros", "Cuadros", multicolor=False), "Pijama de Cuadros")
        self.assertEqual(nombre_con_color("Short Deportivo", "Sin color", multicolor=True), "Short Deportivo")

    def test_no_repite_el_color_si_ya_viene_en_el_nombre(self) -> None:
        self.assertEqual(
            nombre_con_color("Camisa Manga Larga Borgoña", "Borgoña", multicolor=True),
            "Camisa Manga Larga Borgoña",
        )

    def test_variantes_inactivas_no_cuentan(self) -> None:
        p = _producto("Licra", ["Negro"])
        p.variantes.append(SimpleNamespace(color="Blanca", activo=False, producto=p))
        self.assertFalse(multicolor_de_producto(p))

    def test_en_el_catalogo_guardado_del_kiosko(self) -> None:
        filas = [
            {"producto_id": 421, "color": "Rojo", "variante_activo": True},
            {"producto_id": 421, "color": "Negro", "variante_activo": True},
            {"producto_id": 615, "color": "Cuadros", "variante_activo": True},
        ]
        self.assertTrue(multicolor_en_filas(filas, 421))
        self.assertFalse(multicolor_en_filas(filas, 615))
        self.assertFalse(multicolor_en_filas(filas, None))


class DondeSeVeTests(unittest.TestCase):
    def test_etiqueta(self) -> None:
        from pos_uniformes.utils.label_generator import LabelGenerator

        short = _producto("Short Deportivo", ["Rojo", "Negro"])
        rojo = SimpleNamespace(producto=short, talla="Unitalla", color="Rojo", sku="SKU1", precio_venta=Decimal("89"))
        self.assertEqual(LabelGenerator._label_title(rojo), "Short Deportivo Rojo")
        pijama = _producto("Pijama de Cuadros", ["Cuadros"])
        ad = SimpleNamespace(producto=pijama, talla="Adulto", color="Cuadros", sku="SKU2", precio_venta=Decimal("169"))
        self.assertEqual(LabelGenerator._label_title(ad), "Pijama de Cuadros")

    def test_etiqueta_desde_el_catalogo_guardado(self) -> None:
        from pos_uniformes.services.inventory_label_service import _build_fake_variante_from_cache_row
        from pos_uniformes.utils.label_generator import LabelGenerator

        fila = {"sku": "SKU1", "producto_nombre": "Short Deportivo", "producto_nombre_base": "Short Deportivo",
                "talla": "Unitalla", "color": "Gris", "precio_venta": "89", "producto_multicolor": True}
        self.assertEqual(LabelGenerator._label_title(_build_fake_variante_from_cache_row(fila)),
                         "Short Deportivo Gris")
        fila["producto_multicolor"] = False
        self.assertEqual(LabelGenerator._label_title(_build_fake_variante_from_cache_row(fila)), "Short Deportivo")

    def test_ticket_y_recibo_del_pos(self) -> None:
        from pos_uniformes.utils.product_name import build_ticket_product_name

        short = _producto("Short Deportivo", ["Rojo", "Vino"])
        vino = short.variantes[1]
        self.assertEqual(nombre_de_variante(vino, build_ticket_product_name(short)), "Short Deportivo Vino")

    def test_carrito_del_kiosko_ticket_y_libreta(self) -> None:
        """El carrito guarda `sale_name`; de ahí salen ticket, Libreta y demanda."""
        from pos_uniformes.services.quote_kiosk_lookup_service import QuoteKioskLookupSnapshot

        base = dict(sku="SKU1", product_name="Short Deportivo", school_name="General",
                    garment_type_name="-", piece_type_name="Short", size_label="Unitalla",
                    color_label="Morado", price=Decimal("89"), stock_actual=3, location_label="",
                    description_text="", origin_label="")
        self.assertEqual(QuoteKioskLookupSnapshot(**base, multicolor=True).sale_name, "Short Deportivo Morado")
        self.assertEqual(QuoteKioskLookupSnapshot(**base).sale_name, "Short Deportivo")


class PresupuestoTests(unittest.TestCase):
    def test_linea_del_presupuesto_con_conexion(self) -> None:
        from pos_uniformes.ui.helpers.quote_sports_uniform_helper import _enrich_quote_line_item

        short = _producto("Short Deportivo", ["Rojo", "Negro"])
        negro = short.variantes[1]
        linea = {"producto_nombre": "", "pricing_rule_label": ""}
        _enrich_quote_line_item(linea, variant=negro)
        self.assertEqual(linea["producto_nombre"], "Short Deportivo Negro")

    def test_un_solo_color_queda_igual(self) -> None:
        from pos_uniformes.ui.helpers.quote_sports_uniform_helper import _enrich_quote_line_item

        pijama = _producto("Pijama de Cuadros", ["Cuadros"])
        linea = {"producto_nombre": "", "pricing_rule_label": ""}
        _enrich_quote_line_item(linea, variant=pijama.variantes[0])
        self.assertEqual(linea["producto_nombre"], "Pijama de Cuadros")


if __name__ == "__main__":
    unittest.main()
