"""Precios que bajan en el cambio de precio en lote (Inventario, tanda 5)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from pos_uniformes.services.inventario_precio_lote_service import (
    MAXIMO_RENGLONES,
    precios_que_bajan,
    renglones_bajas,
    titulo_bajas,
)


def _fila(vid: int, precio: object, talla: str = "8") -> dict:
    return {"variante_id": vid, "sku": f"SKU{vid:06d}", "talla": talla, "precio_venta": precio,
            "producto_nombre_base": "Pants 2pz Muestra"}


class PreciosQueBajanTests(unittest.TestCase):
    def test_solo_las_que_bajan_en_el_orden_del_lote(self) -> None:
        filas = [_fila(1, Decimal("289")), _fila(2, Decimal("289")), _fila(3, Decimal("250")), _fila(4, Decimal("100"))]
        items = [(3, Decimal("249.50")), (1, Decimal("300")), (2, Decimal("289.00")), (4, Decimal("90"))]
        bajas = precios_que_bajan(items, filas)
        self.assertEqual([b.variante_id for b in bajas], [3, 4])
        self.assertEqual(bajas[0].texto(), "SKU000003 · talla 8: baja de $250 a $249.50")
        self.assertEqual(bajas[1].texto(), "SKU000004 · talla 8: baja de $100 a $90")

    def test_si_nada_baja_lista_vacia(self) -> None:
        filas = [_fila(1, "289"), _fila(2, None)]
        self.assertEqual(precios_que_bajan([(1, "289"), (1, "310"), (2, "10"), (9, "1")], filas), [])

    def test_sin_talla_no_deja_el_punto_suelto(self) -> None:
        bajas = precios_que_bajan([(1, "100")], [_fila(1, "120", talla="")])
        self.assertEqual(bajas[0].texto(), "SKU000001: baja de $120 a $100")

    def test_resumido_si_son_muchas(self) -> None:
        filas = [_fila(i, "300") for i in range(1, 21)]
        bajas = precios_que_bajan([(i, "250") for i in range(1, 21)], filas)
        renglones = renglones_bajas(bajas)
        self.assertEqual(len(renglones), MAXIMO_RENGLONES + 1)
        self.assertEqual(renglones[-1], f"… y {20 - MAXIMO_RENGLONES} más")
        self.assertEqual(titulo_bajas(20), "20 precios bajan")
        self.assertEqual(titulo_bajas(1), "1 precio baja")


if __name__ == "__main__":
    unittest.main()
