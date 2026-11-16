"""Aviso por Telegram de cada venta con QR de descuento (2026-11-16).

Puras: el texto y que un fallo no tumbe la venta. Con la base local de
prueba (`pos_uniformes_test`, en una transacción que se revierte): la venta
anotada deja su aviso en la cola `alerta_telegram`.
"""

from __future__ import annotations

import contextlib
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select

from pos_uniformes.database.models import AlertaTelegram
from pos_uniformes.services import beneficios_carrito as bc
from pos_uniformes.services import descuento_qr_aviso_service as aviso
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services.beneficios.fotografia import fotografia
from pos_uniformes.services.beneficios.motor import calcular
from pos_uniformes.tests.test_e4a_membresias import _Base

D = Decimal


def _foto(qr="10"):
    items = [
        {"sku": "SC1", "nombre": "Sudadera", "talla": "M", "precio": D("400"), "cantidad": 1, "categoria": "Ropa casual"},
        {"sku": "PO1", "nombre": "Playera", "talla": "8", "precio": D("180"), "cantidad": 1, "categoria": "Oficial"},
    ]
    entrada = bc.entrada_desde_carrito(items, fecha_venta=datetime.now(timezone.utc), descuento_qr_pct=qr,
                                       vendedora="VEND-2")
    return items, fotografia(entrada, calcular(entrada))


class _SesionFalsa:
    def __init__(self, falla=False):
        self.agregados = []
        self.falla = falla
        self.commits = 0

    @contextlib.contextmanager
    def begin_nested(self):
        yield

    def add(self, obj):
        if self.falla:
            raise RuntimeError("sin tabla")
        self.agregados.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1


def _entry(foto):
    return SimpleNamespace(calculo=foto, operacion_uuid="0f1e2d3c-aaaa-4bbb-8ccc-123456789abc", id=55,
                           employee_name="Fanny", employee_code="VEND-2", monto_total=D("540.00"))


class TextoTests(unittest.TestCase):
    def test_lleva_folio_empleada_pct_importe_y_total(self) -> None:
        _items, foto = _foto("10")
        s = _SesionFalsa()
        self.assertTrue(aviso.avisar_venta_con_qr(s, _entry(foto)))
        self.assertEqual(s.commits, 0)   # va con la transacción de la venta
        texto = s.agregados[0].texto
        for parte in ("QR de descuento", "Folio 0f1e2d3c", "#55", "Fanny (VEND-2)", "10 %", "−$40.00",
                      "Cobrado: $540.00"):
            self.assertIn(parte, texto)

    def test_sin_qr_no_avisa(self) -> None:
        _items, foto = _foto(None)
        s = _SesionFalsa()
        self.assertFalse(aviso.avisar_venta_con_qr(s, _entry(foto)))
        self.assertEqual(s.agregados, [])
        self.assertFalse(aviso.avisar_venta_con_qr(s, _entry(None)))

    def test_qr_que_no_desconto_no_avisa(self) -> None:
        _items, foto = _foto("10")
        foto["calculo"]["descuento_qr"]["importe"] = "0.00"
        self.assertIsNone(aviso.qr_de_la_fotografia(foto))

    def test_manda_lo_del_servidor(self) -> None:
        _items, foto = _foto("10")
        foto["servidor"] = {"calculo": {**foto["calculo"], "total": "999.00"}}
        self.assertEqual(aviso.qr_de_la_fotografia(foto)["total"], "999.00")

    def test_si_falla_la_venta_sigue(self) -> None:
        _items, foto = _foto("10")
        self.assertFalse(aviso.avisar_venta_con_qr(_SesionFalsa(falla=True), _entry(foto)))


class ColaEnLaBaseTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    def _venta(self, qr):
        items, foto = _foto(qr)
        return lib.registrar_operacion(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta",
            items=[{**it, "precio": str(it["precio"])} for it in items],
            monto_total=D(foto["calculo"]["total"]), origen="Entrada",
            operacion_uuid=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), calculo=foto,
        )

    def _avisos(self, venta):
        return [a for a in self.s.scalars(select(AlertaTelegram).where(AlertaTelegram.texto.contains(f"#{venta.id}")))]

    def test_venta_con_qr_deja_su_aviso(self) -> None:
        venta = self._venta("10")
        avisos = self._avisos(venta)
        self.assertEqual(len(avisos), 1)
        self.assertIn("−$40.00", avisos[0].texto)
        self.assertIn("Lupita", avisos[0].texto)
        self.assertIsNone(avisos[0].enviado_at)

    def test_venta_sin_qr_no_avisa(self) -> None:
        self.assertEqual(self._avisos(self._venta(None)), [])

    def test_si_el_aviso_falla_la_venta_queda(self) -> None:
        with patch.object(AlertaTelegram, "__init__", side_effect=RuntimeError("sin tabla")):
            venta = self._venta("10")
        self.assertIsNotNone(venta.id)


if __name__ == "__main__":
    unittest.main()
