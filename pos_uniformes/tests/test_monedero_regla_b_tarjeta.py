"""Regla B (Daniel, 2026-11-12): con tarjeta, el Monedero se gana sobre lo
que de verdad entra, ya sin la comisión de la terminal (4.5 %).

Ejemplo de Daniel: $1,000 con tarjeta, Profesional 13 % → base $955 →
abono $124.15. Los descuentos (Mayorista, empleada) no cambian. En un pago
mixto (saldo + tarjeta) solo la parte con tarjeta paga comisión.

Lo que se cuida: que el motor (ticket), el abono del servidor y el estimado
del kiosko digan lo mismo.
"""

from __future__ import annotations

import os
import random
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import (
    ClienteCtx,
    EntradaVenta,
    LineaEntrada,
    Pago,
    Rebaja,
)
from pos_uniformes.services.beneficios.motor import base_monedero_con_comision, calcular

D = Decimal
PROFESIONAL = ClienteCtx(id=15, programa_clave="profesional", tasa_monedero=D("13"), pct_mayoreo=None, activo=True)
CLUB = ClienteCtx(id=7, programa_clave="club", tasa_monedero=D("5"), pct_mayoreo=None, activo=True)


def _linea(precio, cantidad=1, rebaja=None, precio_lista=None):
    return LineaEntrada(
        linea_uid=str(uuid.uuid4()), sku=f"SKU-{uuid.uuid4().hex[:6]}", cantidad=cantidad,
        precio_lista=D(precio_lista or precio), categoria="uniforme", rebaja=rebaja, promo_3pz=False,
        nombre="Pants", talla="8",
    )


def _venta(lineas, cliente=PROFESIONAL, **kw):
    return calcular(EntradaVenta(lineas=tuple(lineas), fecha_venta=datetime.now(timezone.utc), cliente=cliente, **kw))


class MotorReglaBTests(unittest.TestCase):
    def test_ejemplo_de_daniel_1000_con_tarjeta(self):
        c = _venta([_linea("1000")], pago_tarjeta=True)
        self.assertEqual((c.total, c.comision_tarjeta), (D("1000.00"), D("45.00")))
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("955.00"), D("124.15")))
        self.assertIn(M.MONEDERO_SIN_COMISION, c.motivos_ticket)

    def test_en_efectivo_no_cambia(self):
        c = _venta([_linea("1000")])
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("1000.00"), D("130.00")))
        self.assertNotIn(M.MONEDERO_SIN_COMISION, c.motivos_ticket)

    def test_el_total_y_el_neto_no_cambian(self):
        efectivo = _venta([_linea("1095")])
        tarjeta = _venta([_linea("1095")], pago_tarjeta=True)
        self.assertEqual(tarjeta.total, efectivo.total)
        self.assertEqual(tarjeta.neto_tienda, lib.neto_de_cobro(D("1095"), D("0"), True))
        # La base es lo que deja la terminal (= neto de la Libreta).
        self.assertEqual(tarjeta.monedero.base, tarjeta.neto_tienda)

    def test_mixto_saldo_y_tarjeta_solo_la_parte_con_tarjeta(self):
        c = _venta([_linea("1000")], pago_tarjeta=True, saldo_a_usar=D("300"), saldo_disponible=D("300"))
        self.assertEqual((c.saldo_usado, c.por_cobrar, c.comision_tarjeta), (D("300.00"), D("700.00"), D("31.50")))
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("668.50"), D("86.90")))

    def test_mixto_efectivo_y_tarjeta(self):
        c = _venta([_linea("1000")], pagos=(Pago("efectivo", D("600.00")), Pago("tarjeta", D("400.00"))))
        self.assertEqual(c.comision_tarjeta, D("400.00") - lib.aplicar_comision_terminal(D("400")))
        self.assertEqual(c.monedero.base, D("1000.00") - c.comision_tarjeta)

    def test_con_rebaja_la_comision_se_reparte(self):
        """La parte rebajada no gana Monedero; la comisión se reparte entre lo
        rebajado y lo demás, y a la base solo le toca su parte."""
        oferta = Rebaja(tipo="oferta", precio=D("200"))
        c = _venta([_linea("800"), _linea("200", rebaja=oferta, precio_lista="300")], pago_tarjeta=True)
        self.assertEqual(c.total, D("1000.00"))
        self.assertEqual(c.monedero.base, base_monedero_con_comision(D("800.00"), D("1000.00"), c.comision_tarjeta))
        self.assertEqual(c.monedero.base, D("764.00"))
        self.assertEqual(sum(l.base_monedero for l in c.lineas), c.monedero.base)
        self.assertEqual(sum(l.abono_linea for l in c.lineas), c.monedero.abono)

    def test_mayoreo_y_empleada_siguen_sin_monedero(self):
        mayorista = ClienteCtx(id=9, programa_clave="mayorista", tasa_monedero=D("15"), pct_mayoreo=D("15"), activo=True)
        c = _venta([_linea("1000")], cliente=mayorista, modalidad_mayorista="descuento", pago_tarjeta=True)
        self.assertIsNone(c.monedero)
        self.assertEqual(c.descuento_total, D("150.00"))   # el descuento no cambia
        c = _venta([_linea("1000")], descuento_empleada=True, pago_tarjeta=True)
        self.assertIsNone(c.monedero)

    def test_version_de_reglas(self):
        self.assertEqual(_venta([_linea("100")]).version_reglas, "2026-11-12")


class BaseConComisionTests(unittest.TestCase):
    def test_casos(self):
        self.assertEqual(base_monedero_con_comision(D("1000"), D("1000"), D("45")), D("955.00"))
        self.assertEqual(base_monedero_con_comision(D("500"), D("1000"), D("45")), D("477.50"))
        self.assertEqual(base_monedero_con_comision(D("1000"), D("1000"), D("0")), D("1000.00"))
        self.assertEqual(base_monedero_con_comision(D("0"), D("1000"), D("45")), D("0"))
        self.assertEqual(base_monedero_con_comision(D("10"), D("10"), D("20")), D("0"))


class ServidorIgualAlMotorTests(unittest.TestCase):
    """El abono del servidor (`acreditar_cashback`) usa la misma cuenta que
    el motor: lo que dice el ticket es lo que se abona."""

    def _servidor(self, total, saldo="0", tarjeta=True, tasa="13"):
        row = SimpleNamespace(monto_total=D(total), monto_monedero=D(saldo), pago_tarjeta=tarjeta)
        base = mon.importe_elegible(row.monto_total, row.monto_monedero)
        base, _ = mon.base_sin_comision_tarjeta(row, base)
        return base, mon.calcular_cashback(base, D(tasa))

    def test_ejemplo_de_daniel(self):
        self.assertEqual(self._servidor("1000"), (D("955.00"), D("124.15")))
        self.assertEqual(self._servidor("1000", tarjeta=False), (D("1000.00"), D("130.00")))
        self.assertEqual(self._servidor("1000", saldo="300"), (D("668.50"), D("86.90")))

    def test_iguales_en_mil_ventas(self):
        rng = random.Random(12)
        for _ in range(1000):
            precio = D(rng.randint(100, 300000)) / 100
            tarjeta = rng.random() < 0.7
            c = _venta([_linea(precio)], pago_tarjeta=tarjeta)
            base, abono = self._servidor(str(c.total), tarjeta=tarjeta)
            self.assertEqual((c.monedero.base, c.monedero.abono), (base, abono), precio)

    def test_motivo_del_movimiento(self):
        row = SimpleNamespace(monto_total=D("1000"), monto_monedero=D("0"), pago_tarjeta=True)
        self.assertEqual(mon.base_sin_comision_tarjeta(row, D("1000")), (D("955.00"), True))
        row.pago_tarjeta = False
        self.assertEqual(mon.base_sin_comision_tarjeta(row, D("1000")), (D("1000"), False))


class KioskoReglaBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _widget(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        w._items = [{"sku": "SKU1", "nombre": "Pants", "talla": "6", "color": "", "precio": D("1000.00"), "cantidad": 1}]
        w._cliente = {
            "id": 15, "codigo": "CLI-000015", "nombre": "Ana", "por_qr": True, "en_linea": True,
            "tiene_monedero": True, "estado": "activo", "disponible": D("0"), "tasa": D("13"),
            "proximo_vencimiento": None, "monto_proximo_vencimiento": D("0"),
        }
        return w

    def test_estimado_con_y_sin_tarjeta(self):
        w = self._widget()
        self.assertEqual(w._cashback_estimado(D("1000"), D("0")), D("130.00"))
        self.assertEqual(w._cashback_estimado(D("1000"), D("0"), True), D("124.15"))
        self.assertEqual(w._cashback_estimado(D("1000"), D("300"), True), D("86.90"))

    def test_la_cola_lleva_el_estimado_con_tarjeta(self):
        w = self._widget()
        self.assertEqual(w._datos_cliente_para_cola("venta", D("1000"), True)["cashback_estimado"], "124.15")
        self.assertEqual(w._datos_cliente_para_cola("venta", D("1000"))["cashback_estimado"], "130.00")

    def test_ticket_dice_sobre_cuanto_con_tarjeta(self):
        from pos_uniformes.ui.helpers import quick_sale_monedero_helper as helper
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import tk_row

        w = self._widget()
        info = w._monedero_para_ticket(D("1000"), True)
        self.assertEqual((info["cashback"], info["base_tarjeta"]), (D("124.15"), D("955.00")))
        texto = "\n".join(helper.lineas_ticket_monedero(info, tk_row))
        self.assertIn("$124.15", texto)
        self.assertIn(tk_row("  13 % sobre:", "$955.00 (tarjeta)"), texto)
        # En efectivo no sale el renglón.
        info = w._monedero_para_ticket(D("1000"), False)
        self.assertNotIn("base_tarjeta", info)
        self.assertNotIn("sobre:", "\n".join(helper.lineas_ticket_monedero(info, tk_row)))

    def test_la_barra_avisa_cuanto_gana_con_tarjeta(self):
        w = self._widget()
        w._pintar_cliente_bar()
        texto = w._cliente_label.text()
        self.assertIn("Gana <b>$130.00</b>", texto)
        self.assertIn("con tarjeta $124.15", texto)


if __name__ == "__main__":
    unittest.main()
