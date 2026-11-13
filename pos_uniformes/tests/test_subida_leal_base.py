"""Qué cuenta para subir de Club a Leal (Daniel, 2026-11-12).

Antes `gasto_del_periodo` sumaba `monto_total` completo: $3,000 en
Liquidación, pagados con saldo del Monedero o comprados con descuento de
empleada subían a Leal. Ahora cuenta la «base Leal» de cada venta: la que
guardó el motor en su fotografía o, en las ventas de antes, la regla
aproximada (lo normal menos su parte del saldo; 0 si fue compra de empleada).

Parte pura (sin base) y parte con la base local de prueba
(`pos_uniformes_test`), en una transacción que se revierte.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services import beneficios_carrito as bc
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import rebaja_service as reb
from pos_uniformes.services.beneficios import calcular
from pos_uniformes.services.beneficios.fotografia import fotografia
from pos_uniformes.services.fidelizacion import subida_leal_service as leal
from pos_uniformes.tests.test_e5a_monedero_por_programa import _Monedero

D = Decimal
AHORA = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
LIQ = reb.RebajaVigente("SL1", reb.LIQUIDACION, D("200"), D("300"), None)


def playera(precio="180"):
    return {"sku": "PO1", "nombre": "Playera polo", "talla": "8", "precio": D(precio), "cantidad": 1}


def sudadera_liquidacion():
    return reb.aplicar({"sku": "SL1", "nombre": "Sudadera", "talla": "10", "precio": D("300"), "cantidad": 1,
                        "categoria": "Ropa casual"}, LIQ)


def renglon_libreta(item) -> dict:
    """El renglón como queda en `libreta_venta.detalle` (precios en texto)."""
    out = {"sku": item["sku"], "cantidad": item["cantidad"], "precio": str(item["precio"])}
    out.update(reb.marca_para_libreta(item))
    return out


def venta(total, *, monedero="0", detalle=None, empleada=False, calculo=None):
    return SimpleNamespace(monto_total=D(total), monto_monedero=D(monedero), detalle=detalle or [],
                           descuento_empleada=empleada, calculo=calculo)


class BaseLealPuraTests(unittest.TestCase):
    def test_venta_normal_cuenta_completa(self) -> None:
        self.assertEqual(leal.base_leal_de_venta(venta("450")), D("450.00"))

    def test_sin_fotografia_lo_rebajado_no_cuenta(self) -> None:
        detalle = [renglon_libreta(playera()), renglon_libreta(sudadera_liquidacion())]
        self.assertEqual(leal.base_leal_de_venta(venta("380", detalle=detalle)), D("180.00"))

    def test_sin_fotografia_lo_pagado_con_saldo_no_cuenta(self) -> None:
        self.assertEqual(leal.base_leal_de_venta(venta("450", monedero="37")), D("413.00"))

    def test_sin_fotografia_el_saldo_se_reparte_como_el_motor(self) -> None:
        """2026-11-12: $600 normal + $400 rebajado, $400 pagados con saldo.
        El motor reparte el saldo: a lo normal le tocan 240 → base 360 (antes
        la regla daba 1000 − 400 − 400 = 200)."""
        detalle = [{"precio_unitario": "600", "cantidad": 1, "subtotal": "600"},
                   {"precio_unitario": "400", "cantidad": 1, "subtotal": "400", "rebaja": "liquidacion"}]
        with patch.object(leal.rebaja_service, "importe_rebajado", return_value=D("400")):
            self.assertEqual(leal.base_leal_de_venta(venta("1000", monedero="400", detalle=detalle)),
                             D("360.00"))

    def test_compra_de_empleada_no_cuenta(self) -> None:
        self.assertEqual(leal.base_leal_de_venta(venta("450", empleada=True)), D("0.00"))
        foto = {"calculo": {"base_leal_total": "450.00"}}
        self.assertEqual(leal.base_leal_de_venta(venta("450", empleada=True, calculo=foto)), D("0.00"))

    def test_nunca_negativa(self) -> None:
        detalle = [renglon_libreta(sudadera_liquidacion())]
        self.assertEqual(leal.base_leal_de_venta(venta("150", monedero="100", detalle=detalle)), D("0.00"))

    def test_con_fotografia_manda_el_motor(self) -> None:
        foto = {"calculo": {"base_leal_total": "123.45"}}
        self.assertEqual(leal.base_leal_de_venta(venta("999", calculo=foto)), D("123.45"))

    def test_fotografia_sin_base_usa_la_regla_aproximada(self) -> None:
        for calculo in ({"cambio": {"venta_id": 1}}, {"calculo": {}}, {"calculo": {"base_leal_total": "x"}}):
            with self.subTest(calculo=calculo):
                self.assertEqual(leal.base_leal_de_venta(venta("450", monedero="50", calculo=calculo)),
                                 D("400.00"))

    def test_fotografia_real_del_motor(self) -> None:
        """Con la fotografía que guarda la venta: la Liquidación queda fuera."""
        entrada = bc.entrada_desde_carrito([playera(), sudadera_liquidacion()], fecha_venta=AHORA)
        foto = fotografia(entrada, calcular(entrada))
        base = leal.base_leal_de_venta(venta(foto["calculo"]["total"], calculo=foto))
        self.assertEqual(base, D(foto["calculo"]["base_leal_total"]).quantize(D("0.01")))
        self.assertEqual(base, D("180.00"))


class GastoDelPeriodoTests(_Monedero):
    def _gasto(self) -> Decimal:
        return leal.gasto_del_periodo(self.s, self.cliente.id, hasta=datetime.now(timezone.utc), dias=365)

    def _venta_items(self, total, items, **kw):
        return lib.registrar_operacion(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta", items=items,
            monto_total=D(total), origen="Entrada", cliente_id=self.cliente.id,
            operacion_uuid=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **kw,
        )

    def test_venta_normal_cuenta_completa_y_sube(self) -> None:
        self._club()
        self._venta("3000")
        self.assertEqual(self._gasto(), D("3000.00"))
        self.assertEqual(self._clave(), "LEAL")

    def test_liquidacion_no_cuenta(self) -> None:
        self._club()
        items = [sudadera_liquidacion() for _ in range(15)]
        self._venta_items("3000", items)
        self.assertEqual(self._gasto(), D("0.00"))
        self.assertEqual(self._clave(), "CLUB")

    def test_lo_pagado_con_saldo_no_cuenta(self) -> None:
        self._club()
        v = self._venta("2900")
        v.monto_monedero = D("200")
        self.s.flush()
        self._venta("200")                      # 2,700 + 200 = 2,900: no llega
        self.assertEqual(self._gasto(), D("2900.00"))
        self.assertEqual(self._clave(), "CLUB")

    def test_compra_de_empleada_no_cuenta(self) -> None:
        self._club()
        self._venta_items("3000", [], descuento_empleada=True)
        self.assertEqual(self._gasto(), D("0.00"))
        self.assertEqual(self._clave(), "CLUB")

    def test_venta_con_fotografia_cuenta_su_base_leal(self) -> None:
        self._club()
        v = self._venta("500")
        v.calculo = {"calculo": {"base_leal_total": "320.00"}}
        self.s.flush()
        self.assertEqual(self._gasto(), D("320.00"))

    def test_venta_vieja_sin_fotografia_regla_aproximada(self) -> None:
        self._club()
        detalle = [renglon_libreta(playera()), renglon_libreta(sudadera_liquidacion())]
        v = self._venta("380")
        v.detalle, v.monto_monedero, v.calculo = detalle, D("30"), None
        self.s.flush()
        # Lo normal es 180 (380 − 200 de Liquidación); del saldo de 30 le
        # toca 30 × 180/380 = 14.21, como lo repartiría el motor.
        self.assertEqual(self._gasto(), D("165.79"))

    def test_apartados_y_abonos_no_cuentan(self) -> None:
        self._club()
        for tipo in ("apartado", "abono"):
            lib.registrar_operacion(self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo=tipo,
                                    items=[], monto_total=D("5000"), cliente_id=self.cliente.id,
                                    created_at=datetime.now(timezone.utc))
        self.assertEqual(self._gasto(), D("0.00"))
        self.assertEqual(self._clave(), "CLUB")

    def test_fuera_de_la_ventana_no_cuenta(self) -> None:
        self._club()
        vieja = self._venta("2900")
        vieja.created_at = datetime.now(timezone.utc) - timedelta(days=400)
        self.s.flush()
        self.assertEqual(self._gasto(), D("0.00"))


if __name__ == "__main__":
    unittest.main()
