from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services.inventario_precio_service import (
    adjuntar_rebajas,
    aviso_precio,
    precio_efectivo,
    texto_precio,
)
from pos_uniformes.services.rebaja_service import LIQUIDACION, OFERTA, RebajaVigente


def _rebaja(sku: str, tipo: str, precio: str, antes: str, hasta: date | None = None) -> RebajaVigente:
    return RebajaVigente(sku=sku, tipo=tipo, precio=Decimal(precio), precio_antes=Decimal(antes), hasta=hasta)


class TextoPrecioTests(unittest.TestCase):
    def test_formato_de_la_tienda(self) -> None:
        self.assertEqual(texto_precio({"precio_venta": Decimal("320.00")}), "$320")
        self.assertEqual(texto_precio({"precio_venta": Decimal("1250")}), "$1,250")
        self.assertEqual(texto_precio({"precio_venta": Decimal("99.50")}), "$99.50")

    def test_sin_precio(self) -> None:
        self.assertEqual(texto_precio({}), "—")

    def test_oferta_y_liquidacion(self) -> None:
        fila = {"precio_venta": Decimal("250"), "rebaja_tipo": OFERTA, "rebaja_precio": Decimal("175")}
        self.assertEqual(texto_precio(fila), "Oferta $175")
        fila = {"precio_venta": Decimal("250"), "rebaja_tipo": LIQUIDACION, "rebaja_precio": Decimal("150")}
        self.assertEqual(texto_precio(fila), "Liquidación $150")


class AvisoPrecioTests(unittest.TestCase):
    def test_sin_rebaja_no_hay_aviso(self) -> None:
        self.assertIsNone(aviso_precio({"precio_venta": Decimal("250")}))

    def test_con_rebaja_dice_el_precio_normal_y_hasta_cuando(self) -> None:
        fila = {
            "precio_venta": Decimal("250"),
            "rebaja_tipo": OFERTA,
            "rebaja_precio": Decimal("175"),
            "rebaja_hasta": date(2026, 11, 30),
        }
        self.assertEqual(aviso_precio(fila), "Precio normal $250 · Oferta hasta el 30/11/2026")

    def test_liquidacion_sin_fecha(self) -> None:
        fila = {"precio_venta": Decimal("250"), "rebaja_tipo": LIQUIDACION, "rebaja_precio": Decimal("150")}
        self.assertEqual(aviso_precio(fila), "Precio normal $250")


class AdjuntarRebajasTests(unittest.TestCase):
    def test_pega_por_sku_sin_importar_mayusculas(self) -> None:
        filas = [{"sku": "abc-1", "precio_venta": Decimal("250")}, {"sku": "XYZ", "precio_venta": Decimal("99")}]
        adjuntar_rebajas(filas, {"ABC-1": _rebaja("ABC-1", OFERTA, "175", "250")})
        self.assertEqual((filas[0]["rebaja_tipo"], filas[0]["rebaja_precio"]), (OFERTA, Decimal("175")))
        self.assertIsNone(filas[1]["rebaja_tipo"])
        self.assertEqual(texto_precio(filas[1]), "$99")

    def test_sin_rebajas_deja_todo_en_none(self) -> None:
        filas = [{"sku": "A"}]
        adjuntar_rebajas(filas, {})
        self.assertEqual((filas[0]["rebaja_tipo"], filas[0]["rebaja_precio"], filas[0]["rebaja_hasta"]), (None, None, None))


if __name__ == "__main__":
    unittest.main()


class PrecioEfectivoTests(unittest.TestCase):
    def test_sin_rebaja_es_el_normal(self) -> None:
        self.assertEqual(precio_efectivo({"precio_venta": Decimal("250")}), Decimal("250"))

    def test_con_rebaja_es_el_rebajado(self) -> None:
        fila = {"precio_venta": Decimal("250"), "rebaja_tipo": OFERTA, "rebaja_precio": Decimal("175")}
        self.assertEqual(precio_efectivo(fila), Decimal("175"))

    def test_tipo_sin_precio_no_cuenta(self) -> None:
        fila = {"precio_venta": Decimal("250"), "rebaja_tipo": OFERTA, "rebaja_precio": None}
        self.assertEqual(precio_efectivo(fila), Decimal("250"))
