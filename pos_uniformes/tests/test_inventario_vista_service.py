"""Orden, escaneo, textos de la ficha y topes de impresión (Inventario, tanda 3)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pos_uniformes.services.inventario_vista_service import (
    BLOQUEAR,
    CONFIRMAR,
    IMPRIMIR,
    NADA,
    UMBRAL_CONFIRMAR_ETIQUETAS,
    buscar_sku_exacto,
    confirmacion_coincide,
    contar_activos,
    decidir_impresion_lote,
    ordenar_por_columna,
    resumir_lote,
    siguiente_orden,
    texto_contada_corto,
    texto_paginacion,
    texto_talla_color,
)

AHORA = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def fila(vid: int, **datos) -> dict:
    base = {"variante_id": vid, "sku": f"SKU{vid:03d}", "producto_nombre_base": "Pants", "talla": "8",
            "color": "Azul", "stock_actual": 0, "precio_venta": Decimal("100")}
    base.update(datos)
    return base


class OrdenTests(unittest.TestCase):
    def test_hay_ordena_todas_las_filas_por_su_numero(self) -> None:
        filas = [fila(1, stock_actual=5), fila(2, stock_actual=-2), fila(3, stock_actual=0)]
        self.assertEqual([f["variante_id"] for f in ordenar_por_columna(filas, "Hay")], [2, 3, 1])
        self.assertEqual([f["variante_id"] for f in ordenar_por_columna(filas, "Hay", descendente=True)], [1, 3, 2])

    def test_talla_en_orden_de_talla_no_de_texto(self) -> None:
        filas = [fila(1, talla="10"), fila(2, talla="2"), fila(3, talla="CH"), fila(4, talla="6")]
        orden = [f["talla"] for f in ordenar_por_columna(filas, "Talla")]
        self.assertLess(orden.index("2"), orden.index("6"))
        self.assertLess(orden.index("6"), orden.index("10"))

    def test_precio_usa_el_de_oferta(self) -> None:
        filas = [
            fila(1, precio_venta=Decimal("300"), rebaja_tipo="oferta", rebaja_precio=Decimal("150")),
            fila(2, precio_venta=Decimal("200")),
        ]
        self.assertEqual([f["variante_id"] for f in ordenar_por_columna(filas, "Precio")], [1, 2])

    def test_contada_nunca_primero(self) -> None:
        filas = [
            fila(1, ultimo_conteo_at=AHORA - timedelta(days=1)),
            fila(2, ultimo_conteo_at=None),
            fila(3, ultimo_conteo_at=AHORA - timedelta(days=30)),
        ]
        self.assertEqual([f["variante_id"] for f in ordenar_por_columna(filas, "Contada")], [2, 3, 1])

    def test_sin_columna_deja_el_orden_de_siempre(self) -> None:
        filas = [fila(3), fila(1), fila(2)]
        self.assertEqual(ordenar_por_columna(filas, None), filas)
        self.assertEqual(ordenar_por_columna(filas, "Otra"), filas)

    def test_tres_toques_vuelven_al_orden_de_siempre(self) -> None:
        estado = (None, False)
        estado = siguiente_orden(estado, "Hay")
        self.assertEqual(estado, ("Hay", False))
        estado = siguiente_orden(estado, "Hay")
        self.assertEqual(estado, ("Hay", True))
        self.assertEqual(siguiente_orden(estado, "Hay"), (None, False))
        self.assertEqual(siguiente_orden(estado, "Precio"), ("Precio", False))


class EscaneoTests(unittest.TestCase):
    def test_sku_exacto_sin_importar_mayusculas_ni_espacios(self) -> None:
        filas = [fila(1), fila(2)]
        self.assertEqual(buscar_sku_exacto(filas, "  sku002 "), 2)
        self.assertIsNone(buscar_sku_exacto(filas, "SKU00"))
        self.assertIsNone(buscar_sku_exacto(filas, ""))


class TextosTests(unittest.TestCase):
    def test_paginacion_humana(self) -> None:
        self.assertEqual(texto_paginacion(214, 0, 100), "Mostrando 1–100 de 214")
        self.assertEqual(texto_paginacion(214, 2, 100), "Mostrando 201–214 de 214")
        self.assertEqual(texto_paginacion(14, 0, 100), "Mostrando 14 tallas")
        self.assertEqual(texto_paginacion(1, 0, 100), "Mostrando 1 talla")
        self.assertEqual(texto_paginacion(0, 0, 100), "Sin tallas con estos filtros")

    def test_contada_sin_repetir_la_palabra(self) -> None:
        # Va junto a la etiqueta «CONTADA» de la ficha: no se repite «Contada».
        self.assertEqual(texto_contada_corto({"ultimo_conteo_at": None}, ahora=AHORA), "Nunca")
        self.assertEqual(texto_contada_corto({"ultimo_conteo_at": AHORA}, ahora=AHORA), "Hoy")
        self.assertEqual(texto_contada_corto({"ultimo_conteo_at": AHORA - timedelta(days=1)}, ahora=AHORA), "Ayer")
        self.assertEqual(
            texto_contada_corto({"ultimo_conteo_at": AHORA - timedelta(days=52)}, ahora=AHORA), "Hace 52 días"
        )

    def test_talla_y_color(self) -> None:
        self.assertEqual(texto_talla_color({"talla": "8", "color": "Azul marino"}), "Talla 8 · Azul marino")
        self.assertEqual(texto_talla_color({"talla": "UNI", "color": ""}), "Talla UNI")

    def test_resumen_de_lote_no_resta_negativos(self) -> None:
        resumen = resumir_lote([fila(1, stock_actual=10), fila(2, stock_actual=-2), fila(3, stock_actual=24)])
        self.assertEqual(resumen.texto, "3 tallas · 34 piezas")
        self.assertEqual(resumir_lote([fila(1, stock_actual=1)]).texto, "1 talla · 1 pieza")

    def test_contar_activos(self) -> None:
        self.assertEqual(contar_activos(["", None, "low", {"x"}, set()]), 2)


class ImpresionYConfirmacionTests(unittest.TestCase):
    def test_tope_de_etiquetas(self) -> None:
        self.assertEqual(UMBRAL_CONFIRMAR_ETIQUETAS, 200)
        self.assertEqual(decidir_impresion_lote(0, hay_filtro=True), NADA)
        self.assertEqual(decidir_impresion_lote(200, hay_filtro=False), IMPRIMIR)
        self.assertEqual(decidir_impresion_lote(201, hay_filtro=False), CONFIRMAR)

    def test_todo_lo_filtrado_sin_filtro_no_se_deja(self) -> None:
        self.assertEqual(decidir_impresion_lote(5153, hay_filtro=False, todo_lo_filtrado=True), BLOQUEAR)
        self.assertEqual(decidir_impresion_lote(30, hay_filtro=True, todo_lo_filtrado=True), IMPRIMIR)

    def test_confirmacion_fuerte_escribiendo_el_nombre(self) -> None:
        self.assertTrue(confirmacion_coincide("  pants 2PZ   colegio muestra ", "Pants 2pz Colegio Muestra"))
        self.assertTrue(confirmacion_coincide("Camisa Educacion", "Camisa Educación"))
        self.assertFalse(confirmacion_coincide("Pants", "Pants 2pz Colegio Muestra"))
        self.assertFalse(confirmacion_coincide("", ""))


if __name__ == "__main__":
    unittest.main()
