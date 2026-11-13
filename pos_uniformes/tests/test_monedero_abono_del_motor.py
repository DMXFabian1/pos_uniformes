"""El abono del Monedero sale de UNA sola cuenta: la del motor (2026-11-12).

Antes había tres cuentas: el motor (ticket con saldo y fotografía), el
estimado del kiosko y el abono del servidor (`acreditar_cashback`), que
hacía (cobrado − saldo − rebajado). Con saldo y prendas rebajadas juntas el
servidor restaba dos veces el saldo que caía en las prendas rebajadas:

    prenda normal $100 + prenda en Liquidación $100, $100 con saldo, 5 %
    motor:    base $50  → abono $2.50  (el saldo se reparte entre las dos)
    servidor: base $0   → abono $0.00  (200 − 100 de saldo − 100 rebajado)

Ahora el servidor toma la base de la fotografía del motor (la tasa sigue
siendo la suya) y el kiosko también. Desde 2026-11-12 la base del motor
manda SIEMPRE que haya fotografía, con o sin saldo: Daniel decidió «los
centavos no ganan» (los del redondeo R1 que caen en una prenda rebajada ya
no suman Monedero). Lo que se cuida aquí:
- el ejemplo da $2.50 en el ticket y en el abono;
- con fotografía la base es la del motor; sin saldo, sin rebaja y con un
  solo medio de pago es la misma que la de antes;
- sin saldo con rebaja solo cambian los centavos del redondeo;
- la venta sin fotografía (vieja o de respaldo) sigue con la cuenta de antes;
- con tarjeta la comisión se quita una sola vez, y en un pago mixto solo
  sobre lo pagado con tarjeta;
- el abono se compara y se anota en el recálculo del servidor, sin frenar
  el cobro.
"""

from __future__ import annotations

import os
import random
import unittest
import unittest.mock
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import beneficios_servidor as srv
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import ClienteCtx, EntradaVenta, LineaEntrada, Rebaja
from pos_uniformes.services.beneficios.fotografia import fotografia
from pos_uniformes.services.beneficios.motor import calcular
from pos_uniformes.tests.test_monedero_service import T0, _Base
from pos_uniformes.tests.test_motor_beneficios import CATALOGO, _carrito_aleatorio, _contexto_aleatorio

D = Decimal
FECHA = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
CLUB = ClienteCtx(9, "CLUB", D("5"), None)
LEAL = ClienteCtx(9, "LEAL", D("10"), None)


def _linea(n, precio, *, liquidacion=None, oferta=None, cantidad=1, sku=None):
    rebaja = None
    if liquidacion is not None:
        rebaja = Rebaja("liquidacion", D(liquidacion))
    if oferta is not None:
        rebaja = Rebaja("oferta", D(oferta))
    return LineaEntrada(str(uuid.UUID(int=n)), sku or f"SKU{n}", cantidad, D(precio), "Oficial", rebaja, False)


def _ejemplo(**kw) -> EntradaVenta:
    """Prenda normal $100 + prenda en Liquidación a $100, $100 con saldo."""
    return EntradaVenta(
        (_linea(1, "100"), _linea(2, "150", liquidacion="100")), FECHA, cliente=CLUB,
        saldo_a_usar=D("100"), saldo_disponible=D("100"), **kw,
    )


def _detalle(entrada: EntradaVenta) -> list[dict]:
    """Los renglones como los guarda la Libreta: el precio cobrado por pieza
    (el rebajado si lleva rebaja) y la marca de la rebaja."""
    salida = []
    for l in entrada.lineas:
        precio = l.rebaja.precio if l.rebaja else l.precio_lista
        renglon = {"sku": l.sku, "cantidad": l.cantidad, "precio": str(precio)}
        if l.rebaja:
            renglon.update(rebaja=l.rebaja.tipo, precio_normal=str(l.precio_lista))
        salida.append(renglon)
    return salida


def _fila(entrada, calculo, *, con_foto=True):
    return SimpleNamespace(
        id=1, monto_total=calculo.total, monto_monedero=calculo.saldo_usado,
        pago_tarjeta=bool(entrada.pago_tarjeta), detalle=_detalle(entrada),
        calculo=fotografia(entrada, calculo) if con_foto else None,
    )


class EjemploDelDobleDescuentoTests(unittest.TestCase):
    def test_ejemplo_200_pagando_100_con_saldo(self):
        """Prenda normal $100 + prenda en Liquidación a $100 → total $200."""
        e = _ejemplo()
        c = calcular(e)
        self.assertEqual((c.total, c.saldo_usado), (D("200.00"), D("100.00")))
        # El saldo se reparte entre las dos prendas; solo cuenta lo de la normal.
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("50.00"), D("2.50")))
        fila = _fila(e, c)
        self.assertEqual(mon.base_cashback_legada(fila)[0], D("0.00"))     # el doble descuento (antes)
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("50.00"), False))
        self.assertEqual(mon.calcular_cashback(mon.base_cashback_de_venta(fila)[0], D("5")), D("2.50"))


class LaBaseEsLaDelMotorTests(unittest.TestCase):
    """Con fotografía la base es la del motor; frente a la cuenta de antes
    solo cambian el doble descuento (saldo + rebaja) y los centavos del
    redondeo en prendas rebajadas."""

    N = 1500

    def _contexto(self, rng: random.Random) -> dict:
        if rng.random() < 0.5:
            return _contexto_aleatorio(rng)
        cliente = rng.choice([CLUB, LEAL])
        ctx = dict(cliente=cliente, pago_tarjeta=rng.random() < 0.4)
        if rng.random() < 0.5:
            ctx.update(saldo_a_usar=D(rng.randint(0, 400)), saldo_disponible=D(rng.randint(0, 400)))
        return ctx

    def test_catalogo_aleatorio(self):
        rng = random.Random(20261112)
        comparadas = cambiaron = redondeo = 0
        for _ in range(self.N):
            entrada = EntradaVenta(tuple(_carrito_aleatorio(rng)), FECHA, **self._contexto(rng))
            c = calcular(entrada)
            fila = _fila(entrada, c)
            nueva, _ = mon.base_cashback_de_venta(fila)
            vieja, _ = mon.base_cashback_legada(fila)
            rebajadas = [l for l in c.lineas if l.clasificacion_al_vender in ("oferta", "liquidacion")]
            with self.subTest(entrada=entrada):
                if c.monedero is None:
                    # Sin la parte del Monedero en la foto: la cuenta de antes.
                    self.assertEqual(nueva, vieja)
                    continue
                self.assertEqual(nueva, c.monedero.base)
                if c.saldo_usado > 0 and rebajadas:
                    cambiaron += nueva != vieja
                    continue
                comparadas += 1
                if not rebajadas:
                    self.assertEqual(nueva, vieja)
                else:
                    # «Los centavos no ganan»: solo el redondeo de las rebajadas.
                    centavos = sum((abs(l.parte_redondeo) for l in rebajadas), D("0"))
                    self.assertLessEqual(abs(nueva - vieja), centavos + D("0.01"))
                    redondeo += nueva != vieja
        self.assertGreater(comparadas, 600)
        self.assertGreater(cambiaron, 0)   # el caso del doble descuento sí aparece
        self.assertGreater(redondeo, 0)    # y el de los centavos también

    def test_catalogo_completo_pieza_por_pieza(self):
        """Cada prenda del catálogo, normal, en Oferta y en Liquidación (a
        precio entero, sin centavos de redondeo), en efectivo y con tarjeta,
        sin saldo: igual que antes."""
        for n, (sku, precio, cat) in enumerate(CATALOGO, start=1):
            for rebaja in (None, "oferta", "liquidacion"):
                for tarjeta in (False, True):
                    for cantidad in (1, 3):
                        kw = {rebaja: format((D(precio) * D("0.6")).quantize(D("1")), "f")} if rebaja else {}
                        e = EntradaVenta(
                            (_linea(n, precio, cantidad=cantidad, sku=sku, **kw), _linea(99, "250", sku="ZZ9")),
                            FECHA, cliente=LEAL, pago_tarjeta=tarjeta,
                        )
                        c = calcular(e)
                        fila = _fila(e, c)
                        with self.subTest(sku=sku, rebaja=rebaja, tarjeta=tarjeta, cantidad=cantidad):
                            self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))


class RedondeoEnPrendaRebajadaTests(unittest.TestCase):
    """Cuando el redondeo de la tienda (R1) le toca a una prenda rebajada, el
    motor deja esos centavos fuera de la base; la cuenta de antes los
    contaba. Daniel (2026-11-12): «los centavos no ganan». Manda el motor,
    con o sin saldo."""

    def _venta(self, **kw):
        e = EntradaVenta((_linea(1, "100"), _linea(2, "60", oferta="38.70")), FECHA, cliente=LEAL, **kw)
        c = calcular(e)
        rebajada = [l for l in c.lineas if l.clasificacion_al_vender == "oferta"][0]
        self.assertGreater(rebajada.parte_redondeo, 0)
        return e, c

    def test_sin_saldo_los_centavos_no_ganan(self):
        e, c = self._venta()
        self.assertEqual(c.saldo_usado, D("0"))
        fila = _fila(e, c)
        legada = mon.base_cashback_legada(fila)
        self.assertLess(c.monedero.base, legada[0])          # antes contaban
        self.assertEqual(mon.base_cashback_de_venta(fila), (c.monedero.base, False))
        self.assertEqual(mon.calcular_cashback(mon.base_cashback_de_venta(fila)[0], D("10")), c.monedero.abono)

    def test_con_tarjeta_tambien(self):
        e, c = self._venta(pago_tarjeta=True)
        fila = _fila(e, c)
        self.assertEqual(mon.base_cashback_de_venta(fila), (c.monedero.base, True))

    def test_sin_fotografia_cuenta_de_antes(self):
        e, c = self._venta()
        fila = _fila(e, c, con_foto=False)
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))
        self.assertGreater(mon.base_cashback_de_venta(fila)[0], c.monedero.base)


class SinFotografiaTests(unittest.TestCase):
    def test_sin_saldo_tambien_manda_la_fotografia(self):
        """2026-11-12: ya no hay «sin saldo = cuenta de antes»."""
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        c = calcular(e)
        fila = _fila(e, c)
        fila.calculo["calculo"]["monedero"] = {"base": "250.00"}
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("250.00"), False))

    def test_base_mayor_que_lo_pagado_no_se_usa(self):
        """2026-11-12: sin el max() contra la cuenta de antes, nada acotaba la
        base de la fotografía. Una base mayor que lo cobrado (kiosko con
        error, cola alterada) no describe la venta: cuenta de antes."""
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        fila = _fila(e, calcular(e))
        fila.calculo["calculo"]["monedero"] = {"base": "999.00"}
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("300.00"), False))
        fila.calculo["calculo"]["monedero"] = {"base": "300.00"}   # igual a lo pagado sí sirve
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("300.00"), False))

    def test_con_saldo_la_base_tampoco_pasa_de_lo_pagado(self):
        e = _ejemplo()
        c = calcular(e)
        self.assertGreater(c.saldo_usado, 0)
        fila = _fila(e, c)
        pagado = c.total - c.saldo_usado
        fila.calculo["calculo"]["monedero"] = {"base": str(pagado + D("0.01"))}
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))

    def test_sin_saldo_y_sin_fotografia_cuenta_de_antes(self):
        e = EntradaVenta((_linea(1, "300"), _linea(2, "60", oferta="38.70")), FECHA, cliente=CLUB)
        fila = _fila(e, calcular(e), con_foto=False)
        # $338.70 → R1 $339.00, menos lo rebajado ($38.70): los centavos cuentan.
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("300.30"), False))

    def test_venta_vieja_sigue_igual(self):
        fila = SimpleNamespace(
            monto_total=D("1000"), monto_monedero=D("300"), pago_tarjeta=True,
            detalle=[{"precio": "100", "cantidad": 1, "rebaja": "liquidacion"}], calculo=None,
        )
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))

    def test_fotografia_de_otra_venta_no_se_usa(self):
        e = _ejemplo()
        c = calcular(e)
        fila = _fila(e, c)
        fila.monto_total = D("999")
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))

    def test_fotografia_sin_monedero_o_danada(self):
        e = _ejemplo()
        c = calcular(e)
        fila = _fila(e, c)
        fila.calculo["calculo"]["monedero"] = None
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))
        fila.calculo["calculo"]["monedero"] = {"base": "no-es-numero"}
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))

    def test_medio_de_pago_distinto_no_se_usa(self):
        e = _ejemplo()
        c = calcular(e)
        fila = _fila(e, c)
        fila.pago_tarjeta = True   # la foto dice efectivo
        self.assertEqual(mon.base_cashback_de_venta(fila), mon.base_cashback_legada(fila))

    def test_prefiere_el_calculo_del_servidor(self):
        e = _ejemplo()
        c = calcular(e)
        fila = _fila(e, c)
        fila.calculo["servidor"] = {"calculo": {**fila.calculo["calculo"], "monedero": {"base": "40.00"}}}
        self.assertEqual(mon.base_cashback_de_venta(fila)[0], D("40.00"))
        fila.calculo["servidor"] = {"error": "boom"}
        self.assertEqual(mon.base_cashback_de_venta(fila)[0], D("50.00"))


class TarjetaTests(unittest.TestCase):
    def test_la_comision_se_quita_una_vez(self):
        e = EntradaVenta((_linea(1, "1000"),), FECHA, cliente=ClienteCtx(15, "PRO", D("13"), None), pago_tarjeta=True)
        c = calcular(e)
        fila = _fila(e, c)
        self.assertEqual(mon.base_cashback_de_venta(fila), (D("955.00"), True))
        self.assertEqual(mon.base_cashback_legada(fila), (D("955.00"), True))

    def test_saldo_rebaja_y_tarjeta(self):
        e = _ejemplo(pago_tarjeta=True)
        c = calcular(e)
        fila = _fila(e, c)
        base, con_tarjeta = mon.base_cashback_de_venta(fila)
        self.assertTrue(con_tarjeta)
        self.assertEqual(base, c.monedero.base)
        self.assertLess(base, D("100.00"))   # se le quitó la comisión

    def test_pago_mixto_comision_solo_sobre_la_tarjeta(self):
        """Efectivo + tarjeta con fotografía: la comisión es solo sobre lo
        pagado con tarjeta (regla B). La cuenta de antes, que solo sabe
        «hubo tarjeta», se la quitaba a todo."""
        from pos_uniformes.services.beneficios.contrato import Pago

        e = EntradaVenta(
            (_linea(1, "1000"),), FECHA, cliente=ClienteCtx(15, "PRO", D("13"), None), pago_tarjeta=True,
            pagos=(Pago("efectivo", D("500")), Pago("tarjeta", D("500"))),
        )
        c = calcular(e)
        self.assertGreater(c.comision_tarjeta, 0)
        fila = _fila(e, c)
        base, con_tarjeta = mon.base_cashback_de_venta(fila)
        self.assertTrue(con_tarjeta)
        self.assertEqual(base, c.monedero.base)
        self.assertEqual(base, D("1000.00") - c.comision_tarjeta)   # solo la de los $500
        self.assertEqual(mon.base_cashback_legada(fila), (D("955.00"), True))
        self.assertGreater(base, D("955.00"))

    def test_fotografia_de_antes_de_la_regla_b(self):
        """Un kiosko con el motor viejo no le quitaba la comisión a la base:
        el servidor se la quita (una sola vez)."""
        e = _ejemplo(pago_tarjeta=True)
        c = calcular(e)
        self.assertIn(M.MONEDERO_SIN_COMISION, c.motivos_ticket)
        fila = _fila(e, c)
        foto = fila.calculo["calculo"]
        foto["monedero"] = {**foto["monedero"], "base": "50.00"}   # sin quitarle la comisión
        foto["motivos_ticket"] = [m for m in foto["motivos_ticket"] if m != M.MONEDERO_SIN_COMISION]
        self.assertEqual(mon.base_cashback_de_venta(fila), (c.monedero.base, True))
        self.assertLess(c.monedero.base, D("50.00"))


class AbonoRealTests(_Base):
    """`acreditar_cashback` con la base del motor y la tasa del servidor."""

    def _venta_con_foto(self, entrada, *, con_foto=True):
        c = calcular(entrada)
        v = self._venta(str(c.total), monedero=str(c.saldo_usado))
        v.pago_tarjeta = bool(entrada.pago_tarjeta)
        v.detalle = _detalle(entrada)
        v.calculo = fotografia(entrada, c) if con_foto else None
        self.s.flush()
        return v

    def test_ejemplo_abona_2_50(self):
        self._tasa("5")
        e = _ejemplo()
        mov = mon.acreditar_cashback(self.s, libreta_venta=self._venta_con_foto(e), momento=T0)
        self.assertEqual((mov.base_calculo, mov.monto), (D("50.00"), D("2.50")))

    def test_la_tasa_es_la_del_servidor(self):
        self._tasa("10")   # el kiosko creía 5 %
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        mov = mon.acreditar_cashback(self.s, libreta_venta=self._venta_con_foto(e), momento=T0)
        self.assertEqual((mov.base_calculo, mov.monto, mov.tasa_snapshot), (D("300.00"), D("30.00"), D("10")))

    def test_venta_sin_foto_sigue_con_la_cuenta_de_antes(self):
        self._tasa("5")
        e = _ejemplo()
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=self._venta_con_foto(e, con_foto=False), momento=T0))

    def test_las_compuertas_no_cambian(self):
        self._tasa("5")
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        v = self._venta_con_foto(e)
        v.descuento_empleada = True
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0))
        v.descuento_empleada = False
        v.descuento_programa = D("15")
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0))
        v.descuento_programa = None
        primero = mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0)
        self.assertEqual(mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0).id, primero.id)

    def test_con_tarjeta(self):
        self._tasa("13")
        e = EntradaVenta((_linea(1, "1000"),), FECHA, cliente=ClienteCtx(15, "PRO", D("13"), None), pago_tarjeta=True)
        mov = mon.acreditar_cashback(self.s, libreta_venta=self._venta_con_foto(e), momento=T0)
        self.assertEqual((mov.base_calculo, mov.monto), (D("955.00"), D("124.15")))
        self.assertIn("tarjeta", mov.motivo)


class RecalculoDelServidorTests(unittest.TestCase):
    def test_el_monedero_se_compara_pero_no_frena_el_cobro(self):
        self.assertIn("monedero.abono", srv.CAMPOS_COMPARADOS)
        self.assertIn("monedero.base", srv.CAMPOS_COMPARADOS)
        self.assertNotIn("monedero.abono", srv.CAMPOS_DEL_COBRO)
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        kiosko = fotografia(e, calcular(e))["calculo"]
        servidor = calcular(replace(e, cliente=LEAL))
        dif = srv.diferencias(kiosko, servidor)
        self.assertEqual(dif, {"monedero.abono": ("15.00", "30.00")})

    def test_sin_monedero_cuenta_como_cero(self):
        e = EntradaVenta((_linea(1, "300"),), FECHA, cliente=CLUB)
        kiosko = fotografia(e, calcular(e))["calculo"]
        servidor = calcular(replace(e, descuento_empleada=True))
        dif = srv.diferencias(kiosko, servidor)
        self.assertEqual(dif.get("monedero.abono"), ("15.00", "0.00"))


class TicketDelKioskoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_ticket_dice_lo_mismo_que_el_abono(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        w._items = [
            {"sku": "SKU1", "nombre": "Playera", "talla": "8", "color": "", "precio": D("100.00"), "cantidad": 1,
             "linea_uid": str(uuid.UUID(int=1))},
            {"sku": "SKU2", "nombre": "Pants", "talla": "8", "color": "", "precio": D("100.00"), "cantidad": 1,
             "linea_uid": str(uuid.UUID(int=2)), "rebaja": "liquidacion", "precio_normal": D("150.00")},
        ]
        w._cliente = {
            "id": 9, "codigo": "CLI-000009", "nombre": "Ana", "por_qr": True, "en_linea": True,
            "tiene_monedero": True, "estado": "activo", "disponible": D("100"), "tasa": D("5"),
            "proximo_vencimiento": None, "monto_proximo_vencimiento": D("0"),
        }
        w._usar_saldo = True
        with unittest.mock.patch.object(w, "_en_linea", return_value=True):
            c = w._calculo_motor()
            self.assertEqual((c.total, c.saldo_usado), (D("200.00"), D("100.00")))
            self.assertEqual(w._cashback_estimado(D("200.00"), D("100.00")), D("2.50"))
            # Un total que no es el del motor: la cuenta de antes.
            self.assertEqual(w._cashback_estimado(D("500.00"), D("0")), D("20.00"))

    def test_sin_saldo_los_centavos_no_ganan_en_el_ticket(self):
        """El «Gana $X» sin saldo sale de la base del motor (2026-11-12)."""
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        w._items = [
            {"sku": "SKU1", "nombre": "Playera", "talla": "8", "color": "", "precio": D("100.00"), "cantidad": 1,
             "linea_uid": str(uuid.UUID(int=1))},
            {"sku": "SKU2", "nombre": "Pants", "talla": "8", "color": "", "precio": D("38.70"), "cantidad": 1,
             "linea_uid": str(uuid.UUID(int=2)), "rebaja": "oferta", "precio_normal": D("60.00")},
        ]
        w._cliente = {
            "id": 9, "codigo": "CLI-000009", "nombre": "Ana", "por_qr": True, "en_linea": True,
            "tiene_monedero": True, "estado": "activo", "disponible": D("0"), "tasa": D("10"),
            "proximo_vencimiento": None, "monto_proximo_vencimiento": D("0"),
        }
        w._usar_saldo = False
        with unittest.mock.patch.object(w, "_en_linea", return_value=True):
            c = w._calculo_motor()
            self.assertEqual(c.saldo_usado, D("0"))
            legada = w._base_cashback_legada(c.total, D("0"))
            self.assertLess(c.monedero.base, legada)
            self.assertEqual(w._base_cashback(c.total, D("0")), c.monedero.base)
            self.assertEqual(w._cashback_estimado(c.total, D("0")), c.monedero.abono)

if __name__ == "__main__":
    unittest.main()
