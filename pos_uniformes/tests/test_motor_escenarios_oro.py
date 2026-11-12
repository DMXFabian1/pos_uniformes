"""M0 — Pruebas de oro: el comportamiento ACTUAL de descuentos, Monedero,
Leal, tope de empleadas, tarjeta y redondeo (Daniel, 2026-11-11).

No prueban cómo debería ser: fijan cómo ES hoy (`0d47a04c`), para que el
motor central (M1 en adelante) no cambie nada sin que se note. Cuando una
decisión comercial (C1–C13 de `diseno_motor_beneficios.md`) cambie un
caso, se cambia su prueba a propósito y se anota cuál decisión fue.

Los casos marcados «HOY» documentan un comportamiento que está en revisión
(D4, D5, D6, D7, D13, anulación que borra): pasan porque así funciona hoy,
no porque así deba quedar.

Tres grupos:
- Reglas puras (sin base ni Qt).
- Kiosko (Venta Rápida, con Qt y sin base: las categorías van en el renglón).
- Base local de prueba `pos_uniformes_test`, en una transacción que se
  revierte (la misma base y protección que `test_e4a_membresias`).

Precios de ejemplo: playera $180 (Oficial), pants liso lista $250 en Oferta a
$175, sudadera $300 en Liquidación a $200, sudadera casual $400, promo 3pz:
pants base $300 + playera promo $150.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select

from pos_uniformes.database.models import LibretaVenta, MonederoConfig, MonederoMovimiento
from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services import rebaja_service as reb
from pos_uniformes.services.fidelizacion import descuento_programa_service as dps
from pos_uniformes.services.fidelizacion import subida_leal_service as leal
from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding
from pos_uniformes.tests.test_e5a_monedero_por_programa import _Monedero

D = Decimal

# ─── Catálogo de ejemplo ────────────────────────────────────────────────────


def playera(cantidad=1, sku="PO1"):
    return {"sku": sku, "nombre": "Playera polo", "talla": "8", "precio": D("180"), "cantidad": cantidad,
            "categoria": "Oficial"}


def sudadera_casual(precio="400", sku="SC1"):
    return {"sku": sku, "nombre": "Sudadera casual", "talla": "M", "precio": D(precio), "cantidad": 1,
            "categoria": "Ropa casual"}


def promo_base():
    return {"sku": "B3", "nombre": "Pants base 3pz", "talla": "8", "precio": D("300"), "cantidad": 1,
            "categoria": "Deportivo", "sports_uniform_role": "base"}


def promo_playera():
    return {"sku": "P3", "nombre": "Playera 3pz", "talla": "8", "precio": D("150"), "cantidad": 1,
            "categoria": "Deportivo", "sports_uniform_role": "playera"}


OFERTA_PANTS = reb.RebajaVigente("PL2", reb.OFERTA, D("175"), D("250"), None)
LIQ_SUDADERA = reb.RebajaVigente("SL1", reb.LIQUIDACION, D("200"), D("300"), None)


def pants_oferta():
    return reb.aplicar({"sku": "PL2", "nombre": "Pants 2pz liso", "talla": "6", "precio": D("250"), "cantidad": 1,
                        "categoria": "Uniformes"}, OFERTA_PANTS)


def sudadera_liquidacion():
    return reb.aplicar({"sku": "SL1", "nombre": "Sudadera", "talla": "10", "precio": D("300"), "cantidad": 1,
                        "categoria": "Ropa casual"}, LIQ_SUDADERA)


def con_pcts(items, pcts):
    """Los renglones con el % de empleada que les tocó (como en el kiosko)."""
    out = []
    for it, pct in zip(items, pcts):
        nuevo = dict(it)
        nuevo[inc.LLAVE_PCT] = pct
        out.append(nuevo)
    return out


# ═══ 1. Reglas puras ════════════════════════════════════════════════════════


class ProgramasYMonederoTests(unittest.TestCase):
    """Escenarios 1–5 y 15: el abono por programa."""

    def test_e01_e02_e03_e05_tasas_sobre_360(self) -> None:
        for tasa, abono in (("5", "18.00"), ("10", "36.00"), ("13", "46.80"), ("15", "54.00")):
            with self.subTest(tasa=tasa):
                self.assertEqual(mon.calcular_cashback(D("360"), D(tasa)), D(abono))

    def test_el_abono_se_trunca_al_centavo(self) -> None:
        # 333.33 × 13 % = 43.3329 → 43.33 (nunca hacia arriba)
        self.assertEqual(mon.calcular_cashback(D("333.33"), D("13")), D("43.33"))
        self.assertEqual(mon.calcular_cashback(D("0.19"), D("5")), D("0.00"))

    def test_e15_sin_programa_no_hay_abono(self) -> None:
        self.assertEqual(mon.calcular_cashback(D("360"), None), D("0.00"))

    def test_base_es_lo_pagado_menos_el_saldo(self) -> None:
        self.assertEqual(mon.importe_elegible(D("450"), D("37")), D("413.00"))
        self.assertEqual(mon.importe_elegible(D("450"), D("450")), D("0.00"))
        self.assertEqual(mon.importe_elegible(D("450"), None), D("450.00"))


class MayoristaPuroTests(unittest.TestCase):
    """Escenarios 4 y 7: el descuento de mayoreo por renglón."""

    def test_e04_dos_playeras_descuento_15(self) -> None:
        self.assertEqual(dps.descuento([playera(2)], programa=D("15")), D("54.00"))

    def test_e07_la_promo_3pz_no_lleva_mayoreo(self) -> None:
        carrito = [playera(), promo_base(), promo_playera()]
        self.assertEqual(dps.descuento(carrito, programa=D("15")), D("27.00"))
        self.assertEqual(dps.porcentaje_de_linea(promo_base(), programa=D("15")), D("0"))

    def test_lo_rebajado_no_lleva_ningun_descuento(self) -> None:
        for item in (pants_oferta(), sudadera_liquidacion()):
            with self.subTest(item=item["rebaja"]):
                self.assertEqual(dps.porcentaje_de_linea(item, empleada=D("20"), programa=D("15")), D("0"))

    def test_gana_el_mayor_entre_mayoreo_y_empleada(self) -> None:
        self.assertEqual(dps.porcentaje_de_linea(playera(), empleada=D("5"), programa=D("15")), D("15"))
        alto = con_pcts([sudadera_casual()], [D("20")])[0]
        self.assertEqual(dps.porcentaje_de_linea(alto, empleada=D("5"), programa=D("15")), D("20"))

    def test_la_3pz_si_lleva_el_de_empleada(self) -> None:
        """HOY: la exclusión de 3pz es solo para el mayoreo; con empleada lleva su %."""
        self.assertEqual(dps.porcentaje_de_linea(promo_base(), empleada=D("5")), D("5"))


class TopeEmpleadaTests(unittest.TestCase):
    """Escenarios 9–11: niveles, máximo en uniforme y tope de $3,000."""

    def test_e09_uniforme_llega_a_10(self) -> None:
        pcts = inc.repartir([playera(2)], pct_nivel=D("15"), restante=D("3000"))
        self.assertEqual(pcts, [D("10")])
        renglones = con_pcts([playera(2)], pcts)
        self.assertEqual(dps.descuento(renglones, empleada=D("5")), D("36.00"))      # paga $324
        self.assertEqual(inc.importe_con_nivel(renglones), D("360.00"))                 # gasta $360 del tope

    def test_e10_ropa_casual_lleva_el_nivel(self) -> None:
        pcts = inc.repartir([sudadera_casual()], pct_nivel=D("15"), restante=D("3000"))
        self.assertEqual(pcts, [D("15")])
        renglones = con_pcts([sudadera_casual()], pcts)
        self.assertEqual(dps.descuento(renglones, empleada=D("5")), D("60.00"))      # paga $340
        self.assertEqual(inc.importe_con_nivel(renglones), D("400.00"))

    def test_3pz_y_rebajas_no_gastan_tope(self) -> None:
        carrito = [promo_base(), pants_oferta(), sudadera_casual()]
        pcts = inc.repartir(carrito, pct_nivel=D("20"), restante=D("400"))
        self.assertEqual(pcts, [D("5"), D("0"), D("20")])
        self.assertEqual(inc.importe_con_nivel(con_pcts(carrito, pcts)), D("400.00"))

    def test_sin_tope_todo_con_nivel(self) -> None:
        self.assertEqual(inc.repartir([sudadera_casual()] * 3, pct_nivel=D("20"), restante=None), [D("20")] * 3)

    def test_categorias(self) -> None:
        for categoria, uniforme in (("Oficial", True), ("Deportivo", True), ("Uniformes", True), ("Escolta", True),
                                    ("Básico", True), ("", True), ("Ropa casual", False), ("Temporada", False),
                                    ("Accesorio", False), ("Ropa interior", False), ("Deportivo casual", False)):
            with self.subTest(categoria=categoria):
                self.assertEqual(inc.es_uniforme({"categoria": categoria}), uniforme)


class SaldoTarjetaRedondeoTests(unittest.TestCase):
    """Escenario 12 y las reglas de cobro."""

    def test_e12_saldo_ajustado_al_medio_peso(self) -> None:
        canje = mon.canje_ajustado(D("450"), D("37.42"))
        self.assertEqual(canje, D("37.00"))
        self.assertEqual(mon.calcular_cashback(mon.importe_elegible(D("450"), canje), D("5")), D("20.65"))

    def test_saldo_nunca_pasa_del_total_ni_de_lo_pedido(self) -> None:
        self.assertEqual(mon.canje_ajustado(D("100"), D("500")), D("100.00"))
        self.assertEqual(mon.canje_ajustado(D("450"), D("500"), deseado=D("50")), D("50.00"))
        self.assertEqual(mon.canje_ajustado(D("450"), D("0")), D("0"))

    def test_redondeo_de_la_tienda(self) -> None:
        """HOY: de .01 a .19 se baja al peso; de .20 a .69, a medio peso; de .70 en adelante, al peso de arriba."""
        for monto, cobrado in (("152.00", "152"), ("152.15", "152"), ("152.19", "152"), ("152.20", "152.50"),
                               ("152.69", "152.50"), ("152.70", "153.00")):
            with self.subTest(monto=monto):
                self.assertEqual(resolve_sale_rounding(D(monto)).collected_total, D(cobrado))

    def test_comision_de_tarjeta(self) -> None:
        self.assertEqual(lib.TERMINAL_COMMISSION_PERCENT, D("4.5"))
        self.assertEqual(lib.aplicar_comision_terminal(D("413")), D("394.50"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("37"), True), D("394.50"))   # comisión solo a lo de tarjeta
        self.assertEqual(lib.neto_de_cobro(D("450"), D("37"), False), D("413.00"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("0"), True), D("430.00"))


class RebajasPurasTests(unittest.TestCase):
    """Escenario 8: lo rebajado no abona y el ahorro del ticket."""

    def test_e08_importe_rebajado_y_ahorro(self) -> None:
        carrito = [pants_oferta(), sudadera_liquidacion(), playera()]
        self.assertEqual(reb.importe_rebajado(carrito), D("375.00"))
        self.assertEqual(reb.ahorro_total(carrito), D("175"))
        self.assertEqual(reb.texto_ahorro_total(carrito), "¡Hoy ahorraste $175 en ofertas!")
        self.assertEqual(reb.texto_ahorro_total(carrito, D("27")), "¡Hoy ahorraste $202!")
        self.assertEqual(reb.texto_ahorro_total([playera()]), "")


class SinConexionPuroTests(unittest.TestCase):
    """Escenario 16: el saldo nunca viaja por la cola."""

    def test_e16_la_cola_rechaza_un_canje(self) -> None:
        with self.assertRaises(ValueError):
            cola._subir(None, {"monto_monedero": "37.00", "tipo": "venta"})


# ═══ 2. Kiosko ══════════════════════════════════════════════════════════════


class _Kiosko(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, items, *, tasa="5", descuento=None, en_linea=True, disponible="0"):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=not en_linea, _kiosk_lookup_from_cache=None, _db_online=en_linea))
        w._employee_code = "VEND-2"
        w._employee_name = "Fanny"
        w._cliente = {"id": 9, "codigo": "CLI-000009", "nombre": "Cliente Oro", "por_qr": True, "en_linea": en_linea,
                      "tiene_monedero": True, "estado": "activo", "disponible": D(disponible),
                      "tasa": D(tasa) if tasa else None, "descuento_disponible": D(descuento) if descuento else None,
                      "programa": None, "proximo_vencimiento": None, "monto_proximo_vencimiento": D("0")}
        w._items = [dict(it) for it in items]
        return w

    def _con_mayoreo(self, w):
        w._usar_descuento_programa = True
        return w


class KioskoMayoristaTests(_Kiosko):
    """Escenarios 5, 6, 7 y D6."""

    def test_e05_mayorista_monedero(self) -> None:
        w = self._kiosko([playera(2)], tasa="15", descuento="15")
        self.assertEqual(w._compute_totals(), (D("360"), D("0.00"), D("360")))
        self.assertEqual(w._cashback_estimado(D("360"), D("0")), D("54.00"))

    def test_e06_mayorista_monedero_acumula_sobre_la_3pz(self) -> None:
        """Decisión aprobada (2026-11-11): con Monedero la 3pz SÍ acumula 15 %."""
        w = self._kiosko([playera(), promo_base(), promo_playera()], tasa="15", descuento="15")
        self.assertEqual(w._compute_totals()[2], D("630"))
        self.assertEqual(w._cashback_estimado(D("630"), D("0")), D("94.50"))

    def test_e07_mayorista_descuento_con_3pz(self) -> None:
        w = self._con_mayoreo(self._kiosko([playera(), promo_base(), promo_playera()], tasa="15", descuento="15"))
        self.assertEqual(w._compute_totals(), (D("630"), D("27.00"), D("603")))
        self.assertEqual(w._cashback_estimado(D("603"), D("0")), D("0.00"))
        self.assertEqual(w._etiqueta_descuento_ticket(), "Desc. mayoreo 15 %:")

    def test_e04_mayorista_descuento_dos_playeras(self) -> None:
        w = self._con_mayoreo(self._kiosko([playera(2)], tasa="15", descuento="15"))
        self.assertEqual(w._compute_totals(), (D("360"), D("54.00"), D("306")))
        self.assertEqual(w._cashback_estimado(D("306"), D("0")), D("0.00"))

    def test_d6_descuento_sin_renglones_que_lo_reciban(self) -> None:
        """CAMBIADA EN M2 por C4 (§6): sin abono (igual); la venta queda con
        modalidad «descuento» y `descuento_aplicado = false`."""
        w = self._con_mayoreo(self._kiosko([promo_base(), promo_playera()], tasa="15", descuento="15"))
        self.assertEqual(w._compute_totals(), (D("450"), D("0.00"), D("450")))
        calculo = w._calculo_motor()
        self.assertEqual(calculo.modalidad_mayorista_elegida, "descuento")
        self.assertFalse(calculo.descuento_aplicado)
        self.assertIsNone(calculo.monedero)
        self.assertIn("MAYOREO_SIN_LINEAS_ELEGIBLES", calculo.motivos_ticket)
        self.assertEqual(w._cashback_estimado(D("450"), D("0")), D("0.00"))


class KioskoTopeTests(_Kiosko):
    """Escenario 11 y el tope por pieza, cobrados con el motor (M2: C8, C9, P4).

    Antes de M2 estas pruebas fijaban `inc.repartir`, renglón por renglón en
    el orden del carrito (D7). Cambiadas una por una según §6."""

    def _empleada(self, items, *, restante="300", pct="20"):
        w = self._kiosko(items, tasa=None)
        w._cliente = None
        w._discount_active = True
        w._compradora = inc.EstadoCompradora("VEND-3", "Ana", D(pct), D("3000"), D("3000") - D(restante))
        return w

    def test_e11_el_orden_ya_no_cambia_el_total(self) -> None:
        """CAMBIADA EN M2 por C8: antes $461.50 o $466.00 según el orden; ahora siempre $461.50."""
        chamarra = sudadera_casual("280", sku="CH1")
        sudadera = sudadera_casual("250", sku="SU1")
        for carrito in ([chamarra, sudadera], [sudadera, chamarra]):
            self.assertEqual(self._empleada(carrito)._compute_totals()[2], D("461.50"))

    def test_un_renglon_que_no_cabe_completo_se_parte_por_pieza(self) -> None:
        """CAMBIADA EN M2 por C9: antes «2 × $180» iba todo al 5 % y «1 + 1» daba 20 % y 5 %;
        ahora los dos dan una pieza al 20 % y otra al 5 % ($315.00)."""
        junto = [dict(sudadera_casual("180"), cantidad=2)]
        partido = [sudadera_casual("180"), sudadera_casual("180")]
        self.assertEqual(self._empleada(junto)._compute_totals()[2], D("315.00"))
        self.assertEqual(self._empleada(partido)._compute_totals()[2], D("315.00"))

    def test_un_renglon_posterior_mas_chico_si_cabe(self) -> None:
        """CAMBIADA EN M2 por C8/C9: el mismo resultado ($400 al 5 %, $100 al 20 %), ahora por
        precio y por pieza, en cualquier orden."""
        a, b = sudadera_casual("400", sku="A"), sudadera_casual("100", sku="B")
        for carrito in ([a, b], [b, a]):
            w = self._empleada(carrito)
            self.assertEqual(w._compute_totals(), (D("500"), D("40.00"), D("460")))


class KioskoRebajasTests(_Kiosko):
    """Escenarios 8 y 8b."""

    CARRITO = staticmethod(lambda: [pants_oferta(), sudadera_liquidacion(), playera()])

    def test_e08_club_con_oferta_y_liquidacion(self) -> None:
        w = self._kiosko(self.CARRITO(), tasa="5")
        self.assertEqual(w._compute_totals()[2], D("555"))
        self.assertEqual(w._cashback_estimado(D("555"), D("0")), D("9.00"))

    def test_e08b_mayorista_descuento_con_rebajas(self) -> None:
        w = self._con_mayoreo(self._kiosko(self.CARRITO(), tasa="15", descuento="15"))
        self.assertEqual(w._compute_totals(), (D("555"), D("27.00"), D("528")))
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        self.assertIn("¡Hoy ahorraste $202!", texto)
        self.assertIn("Desc. mayoreo 15 %:", texto)
        self.assertIn("sin cambios ni devoluciones", texto)


class KioskoEmpleadaTests(_Kiosko):
    """D1, el 5 % de «otra persona» y el redondeo."""

    def test_d1_con_descuento_de_empleada_no_hay_monedero(self) -> None:
        w = self._kiosko([playera(2)], tasa="5")
        w._discount_active = True
        self.assertEqual(w._compute_totals(), (D("360"), D("18.00"), D("342")))
        self.assertEqual(w._cashback_estimado(D("342"), D("0")), D("0.00"))

    def test_otra_persona_5_parejo_incluida_la_3pz(self) -> None:
        """HOY: sin compradora elegida, 5 % sobre todo el subtotal (la 3pz también)."""
        w = self._kiosko([promo_base(), promo_playera()], tasa=None)
        w._discount_active = True
        self.assertEqual(w._compute_totals(), (D("450"), D("22.50"), D("427.50")))

    def test_el_redondeo_puede_bajar(self) -> None:
        """HOY: $179 − 5 % = $170.05 se cobra $170."""
        w = self._kiosko([dict(playera(), precio=D("179"))], tasa=None)
        w._discount_active = True
        self.assertEqual(w._compute_totals(), (D("179"), D("8.95"), D("170")))

    def test_la_compradora_con_nivel_en_el_kiosko(self) -> None:
        w = self._kiosko([playera(2), sudadera_casual()], tasa=None)
        w._discount_active = True
        w._compradora = inc.EstadoCompradora(codigo="VEND-3", nombre="Lupita", porcentaje=D("15"), tope=D("3000"),
                                             usado=D("0"))
        # playeras al 10 % (uniforme) = −36; sudadera al 15 % = −60
        self.assertEqual(w._compute_totals(), (D("760"), D("96.00"), D("664")))


class KioskoTarjetaTests(_Kiosko):
    """Tarjeta: el cliente paga lo mismo; el neto de la tienda baja."""

    def test_con_tarjeta_el_total_y_el_abono_no_cambian(self) -> None:
        w = self._kiosko([dict(playera(), precio=D("150"), cantidad=3)], tasa="5")
        total = w._compute_totals()[2]
        self.assertEqual(total, D("450"))
        self.assertEqual(w._cashback_estimado(total, D("0")), D("22.50"))
        self.assertEqual(w._monto_neto_actual(total, pago_tarjeta=False), D("450"))

    def test_d13_el_neto_depende_del_camino(self) -> None:
        """CAMBIADA EN M2 por T4 (§6): antes 3 × $150 con tarjeta daba $430.50 en el
        kiosko (por pieza) y $430.00 en la Libreta. Ahora $430.00 por cualquier camino."""
        w = self._kiosko([dict(playera(), precio=D("150"), cantidad=3)], tasa="5")
        self.assertEqual(w._monto_neto_actual(D("450"), pago_tarjeta=True), D("430.00"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("0"), True), D("430.00"))


class KioskoSinConexionTests(_Kiosko):
    """Escenario 16 en el kiosko."""

    def test_e16_sin_conexion(self) -> None:
        w = self._kiosko([playera(2)], tasa="15")
        w._cliente_sin_conexion("CLI-000009", True)
        self.assertFalse(w._cliente["en_linea"])
        self.assertIsNone(w._cliente["descuento_disponible"])      # no se ofrece el mayoreo
        self.assertEqual(w._canje_actual(D("360")), D("0.00"))      # no se puede usar saldo
        self.assertEqual(w._cashback_estimado(D("360"), D("0")), D("0.00"))   # el ticket no lo promete
        self.assertIsNone(w._monedero_para_ticket(D("360"), False))     # ni abono ni saldo en el ticket


# ═══ 3. Base local de prueba ════════════════════════════════════════════════


class BaseOroTests(_Monedero):
    """Escenarios 12, 13 y 14, y los casos de Leal y abono que dependen de la base."""

    def _venta(self, total: str, *, items=None, descuento_empleada=False, acreditar=True, cliente=None):
        return lib.registrar_operacion(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta",
            items=items or [], monto_total=D(total), origen="Entrada", cliente_id=(cliente or self.cliente).id,
            descuento_empleada=descuento_empleada, acreditar_cashback=acreditar,
            operacion_uuid=str(uuid.uuid4()), created_at=datetime.now(timezone.utc),
        )

    def _atrasar_un_dia(self, membresia) -> None:
        """`registrar_venta_con_monedero` no recibe la hora: la base pone la de
        inicio de la transacción de prueba, que es anterior a la membresía y a
        la configuración creadas en la prueba. Se atrasan un día para que la
        venta caiga dentro de su vigencia (solo en la base de prueba)."""
        ayer = datetime.now(timezone.utc) - timedelta(days=1)
        membresia.desde = ayer
        for cfg in self.s.scalars(select(MonederoConfig)):
            cfg.vigente_desde = min(cfg.vigente_desde, ayer)
        self.s.flush()

    def _saldo(self) -> Decimal:
        return mon.resumen_cliente(self.s, self.cliente.id).disponible

    def _con_saldo_37_42(self) -> None:
        self._atrasar_un_dia(self._club())
        self._venta("748.40")                     # 5 % = 37.42
        self.assertEqual(self._saldo(), D("37.42"))

    def _venta_con_saldo(self, total="450", saldo="37", tarjeta=True):
        return lib.registrar_venta_con_monedero(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", items=[], monto_total=D(total),
            monto_monedero=D(saldo), cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()),
            pago_tarjeta=tarjeta, origen="Entrada",
        )

    def test_e12_pago_mixto_saldo_y_tarjeta(self) -> None:
        """CAMBIA (regla B, 2026-11-12): la parte con tarjeta ($413) deja $394.50
        tras la comisión; el 5 % se da sobre eso."""
        self._con_saldo_37_42()
        venta, canje, abono = self._venta_con_saldo()
        self.assertEqual(canje.monto, D("-37.00"))
        self.assertEqual((abono.monto, abono.base_calculo), (D("19.72"), D("394.50")))
        self.assertIn("(pago con tarjeta)", abono.motivo)
        self.assertEqual(venta.monto_neto, D("394.50"))
        self.assertEqual(self._saldo(), D("20.14"))
        self.assertEqual(abono.expira_at.year - abono.created_at.year, 1)

    def test_e12_repetir_la_venta_no_duplica(self) -> None:
        self._con_saldo_37_42()
        uid = str(uuid.uuid4())
        kw = dict(employee_code=self.lupita.codigo, employee_name="Lupita", items=[], monto_total=D("450"),
                  monto_monedero=D("37"), cliente_id=self.cliente.id, operacion_uuid=uid, pago_tarjeta=True)
        primera = lib.registrar_venta_con_monedero(self.s, **kw)
        segunda = lib.registrar_venta_con_monedero(self.s, **kw)
        self.assertEqual(primera[0].id, segunda[0].id)
        self.assertEqual(self._saldo(), D("20.14"))

    def test_e13_e14_solo_hay_anulacion_completa_y_borra_la_venta(self) -> None:
        """HOY: no hay devolución parcial; anular revierte todo y BORRA la venta (punto 10)."""
        self._con_saldo_37_42()
        venta, _canje, _abono = self._venta_con_saldo()
        venta_id = venta.id
        res = lib.anular_operacion_con_monedero(self.s, venta_id, usuario_id=self.admin.id, motivo="prueba de oro")
        self.assertEqual(res.cashback_revertido, D("19.72"))
        self.assertEqual(res.saldo_devuelto, D("37.00"))
        self.assertEqual(self._saldo(), D("37.42"))
        self.s.expire_all()
        self.assertIsNone(self.s.get(LibretaVenta, venta_id))
        self.assertFalse(hasattr(lib, "devolver_parcial"))

    def test_e14_si_ya_gasto_el_abono_no_se_puede_anular(self) -> None:
        self._con_saldo_37_42()
        venta, _c, _a = self._venta_con_saldo()                     # queda 0.42 + 19.72
        self._venta_con_saldo(total="100", saldo="20", tarjeta=False)   # gasta 0.42 y 19.58 del abono
        with self.assertRaises(mon.CashbackYaGastado):
            lib.anular_operacion_con_monedero(self.s, venta.id, usuario_id=self.admin.id, motivo="prueba de oro")

    def test_d5_saldo_y_rebajas_se_restan_completos(self) -> None:
        """HOY (D5): $555 con $375 rebajados y $100 de saldo → base $80 (no proporcional)."""
        self._club()
        renglones = [pants_oferta(), sudadera_liquidacion(), playera()]
        venta = self._venta("555", items=renglones, acreditar=False)
        venta.monto_monedero = D("100")
        self.s.flush()
        abono = mon.acreditar_cashback(self.s, libreta_venta=venta)
        self.assertEqual((abono.base_calculo, abono.monto), (D("80.00"), D("4.00")))

    def test_e08_lo_rebajado_no_abona_en_el_servidor(self) -> None:
        self._club()
        venta = self._venta("555", items=[pants_oferta(), sudadera_liquidacion(), playera()])
        abono = self._cashback(venta)
        self.assertEqual((abono.base_calculo, abono.monto), (D("180.00"), D("9.00")))

    def test_e06_servidor_mayorista_monedero_con_3pz(self) -> None:
        self._aprobado("MAYORISTA")
        venta = self._venta("630", items=[playera(), promo_base(), promo_playera()], acreditar=False)
        abono = mon.acreditar_cashback(self.s, libreta_venta=venta)
        self.assertEqual(abono.monto, D("94.50"))

    def test_e07_servidor_mayorista_descuento_no_abona(self) -> None:
        self._aprobado("MAYORISTA")
        venta = lib.registrar_operacion(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta", items=[],
            monto_total=D("603"), origen="Entrada", cliente_id=self.cliente.id, descuento_programa=D("15"),
            operacion_uuid=str(uuid.uuid4()), created_at=datetime.now(timezone.utc),
        )
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=venta))

    # ─── Leal (D4 y C1–C3) ───

    def test_leal_cuenta_lo_pagado_con_saldo(self) -> None:
        """HOY (D4): el umbral suma `monto_total`, incluido lo que se pagó con Monedero."""
        self._club()
        venta = self._venta("3000", acreditar=False)
        venta.monto_monedero = D("200")
        self.s.flush()
        gasto = leal.gasto_del_periodo(self.s, self.cliente.id, hasta=datetime.now(timezone.utc), dias=365)
        self.assertEqual(gasto, D("3000.00"))

    def test_leal_cuenta_las_ofertas(self) -> None:
        """HOY: lo rebajado suma para Leal (la propuesta 1 dice que no)."""
        self._club()
        self._venta("3000", items=[pants_oferta()])
        self.assertEqual(self._clave(), "LEAL")

    def test_leal_cuenta_compras_de_empleada_con_cliente(self) -> None:
        """HOY: una compra con descuento de empleada y cliente identificado suma para Leal."""
        self._club()
        self._venta("3000", descuento_empleada=True)
        self.assertEqual(self._clave(), "LEAL")

    def test_leal_la_venta_anulada_deja_de_contar_y_no_baja(self) -> None:
        """HOY: la anulación borra la venta (deja de sumar), pero quien ya subió se queda en Leal."""
        self._club()
        venta = self._venta("3000")
        self.assertEqual(self._clave(), "LEAL")
        lib.anular_operacion_con_monedero(self.s, venta.id, usuario_id=self.admin.id, motivo="prueba de oro")
        gasto = leal.gasto_del_periodo(self.s, self.cliente.id, hasta=datetime.now(timezone.utc), dias=365)
        self.assertEqual(gasto, D("0.00"))
        self.assertEqual(self._clave(), "LEAL")

    def test_d1_empleada_no_abona_en_el_servidor(self) -> None:
        self._club()
        venta = self._venta("450", descuento_empleada=True)
        self.assertIsNone(self._cashback(venta))


if __name__ == "__main__":
    unittest.main()
