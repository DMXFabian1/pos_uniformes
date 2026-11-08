"""Monedero ↔ Libreta, cola offline y corte.

Lo que no debe pasar: que el saldo usado aparezca como efectivo en el cajón,
que una venta se suba dos veces y gane cashback doble, o que se borre una
venta que movió el monedero.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Cliente, LibretaVenta, MonederoMovimiento, RolUsuario, Usuario
from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.corte_caja_service import resumir_periodo

D = Decimal
UTC = timezone.utc


class PagosDeTest(unittest.TestCase):
    def _row(self, total, monedero="0", tarjeta=False, tipo="venta", neto=None):
        return SimpleNamespace(
            monto_total=D(total), monto_monedero=D(monedero), pago_tarjeta=tarjeta, tipo=tipo,
            piezas=1, monto_neto=D(neto or total),
        )

    def test_sin_monedero_igual_que_antes(self):
        self.assertEqual(lib.pagos_de(self._row("100")), lib.PagosOperacion(D("0.00"), D("0.00"), D("100.00")))
        self.assertEqual(lib.pagos_de(self._row("100", tarjeta=True)), lib.PagosOperacion(D("0.00"), D("100.00"), D("0.00")))

    def test_filas_viejas_sin_columna(self):
        row = SimpleNamespace(monto_total=D("80"), pago_tarjeta=False)
        self.assertEqual(lib.pagos_de(row).efectivo, D("80.00"))

    def test_el_saldo_no_es_efectivo_ni_tarjeta(self):
        self.assertEqual(lib.pagos_de(self._row("450", "37")), lib.PagosOperacion(D("37.00"), D("0.00"), D("413.00")))
        self.assertEqual(lib.pagos_de(self._row("450", "450", tarjeta=True)).tarjeta, D("0.00"))

    def test_neto_con_monedero_es_solo_el_dinero(self):
        self.assertEqual(lib.neto_de_cobro(D("450"), D("50"), False), D("400.00"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("450"), True), D("0.00"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("50"), True), lib.aplicar_comision_terminal(D("400")))

    def test_corte_no_infla_el_cajon(self):
        rows = [
            self._row("450", "50", neto="400"),
            self._row("200", "0", tarjeta=True, neto="191"),
            self._row("100", "100", neto="0"),
            self._row("300", tipo="apartado"),
        ]
        r = resumir_periodo(rows)
        self.assertEqual(r.efectivo, D("400.00"))
        self.assertEqual(r.tarjeta, D("200.00"))
        self.assertEqual(r.monedero, D("150.00"))
        self.assertEqual(r.ventas, D("750.00"))

    def test_corte_por_dia_en_caja(self):
        rows = [SimpleNamespace(
            monto_total=D("450"), monto_monedero=D("50"), pago_tarjeta=False, tipo="venta", piezas=1,
            monto_neto=D("400"), created_at=datetime(2026, 11, 8, 18, tzinfo=UTC),
        )]
        dia = lib.resumir_por_dia(rows)[0]
        self.assertEqual(dia.monto_en_caja, D("400.00"))
        self.assertEqual(dia.monto_neto_ventas, D("400.00"))
        self.assertEqual(dia.monto_ventas, D("450.00"))


class _Db(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000007", nombre="Ana")
        self.s.add_all([self.admin, self.cliente])
        self.s.flush()
        cfg = mon.guardar_config(self.s, tasa="10", habilitado=True, usuario_id=self.admin.id)
        cfg.vigente_desde = datetime(2020, 1, 1, tzinfo=UTC)
        self.s.flush()
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    def _saldo(self):
        return mon.resumen_cliente(self.s, self.cliente.id).disponible

    def _venta(self, total="100", **kw):
        return lib.registrar_operacion(
            self.s, employee_code="vend-2", employee_name="Fanny", tipo=kw.pop("tipo", "venta"),
            items=[], monto_total=D(total), origen="Entrada", **kw,
        )


class RegistrarConClienteTest(_Db):
    def test_venta_con_cliente_gana_cashback(self):
        v = self._venta("200", cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()))
        self.assertEqual(self._saldo(), D("20.00"))
        self.assertEqual(v.monto_monedero, D("0.00"))

    def test_sin_cliente_igual_que_antes(self):
        self._venta("200")
        self.assertEqual(self.s.scalar(select(func.count(MonederoMovimiento.id))), 0)

    def test_si_falla_el_cashback_la_venta_queda(self):
        with patch.object(mon, "acreditar_cashback", side_effect=RuntimeError("boom")):
            v = self._venta("200", cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()))
        self.assertIsNotNone(self.s.get(LibretaVenta, v.id))
        self.assertEqual(self._saldo(), D("0.00"))
        self.assertEqual(mon.acreditar_faltantes(self.s), 1)   # la red de seguridad lo repone
        self.assertEqual(self._saldo(), D("20.00"))


class VentaConMonederoTest(_Db):
    def setUp(self) -> None:
        super().setUp()
        self._venta("1000", cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()))  # $100

    def _con_saldo(self, total, usar, tarjeta=False, op=None):
        return lib.registrar_venta_con_monedero(
            self.s, employee_code="VEND-2", employee_name="Fanny", items=[], monto_total=D(total),
            monto_monedero=D(usar), cliente_id=self.cliente.id, operacion_uuid=op or str(uuid.uuid4()),
            pago_tarjeta=tarjeta, origen="Entrada",
        )

    def test_canje_y_cashback_sobre_lo_pagado_con_dinero(self):
        v, canje, cashback = self._con_saldo("450", "50")
        self.assertEqual(v.monto_monedero, D("50.00"))
        self.assertEqual(v.monto_neto, D("400.00"))
        self.assertEqual(canje.monto, D("-50.00"))
        self.assertEqual(cashback.monto, D("40.00"))
        self.assertEqual(self._saldo(), D("90.00"))

    def test_todo_con_saldo_no_genera_cashback(self):
        v, _, cashback = self._con_saldo("80", "80")
        self.assertIsNone(cashback)
        self.assertEqual(v.monto_neto, D("0.00"))
        self.assertEqual(self._saldo(), D("20.00"))

    def test_sin_saldo_suficiente_no_queda_nada(self):
        antes = self.s.scalar(select(func.count(LibretaVenta.id)))
        with self.assertRaises(mon.SaldoInsuficiente):
            with self.s.begin_nested():
                self._con_saldo("500", "150")
        self.assertEqual(self.s.scalar(select(func.count(LibretaVenta.id))), antes)
        self.assertEqual(self._saldo(), D("100.00"))

    def test_repetir_con_el_mismo_uuid_no_cobra_doble(self):
        op = str(uuid.uuid4())
        a, *_ = self._con_saldo("450", "50", op=op)
        b, *_ = self._con_saldo("450", "50", op=op)
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._saldo(), D("90.00"))

    def test_no_se_borra_y_se_anula_completa(self):
        v, *_ = self._con_saldo("450", "50")
        with self.assertRaises(mon.OperacionConMonedero):
            lib.eliminar_operacion(self.s, v.id)
        with patch.object(lib, "devolver_stock", return_value=0):
            r = lib.anular_operacion_con_monedero(self.s, v.id, usuario_id=self.admin.id, motivo="devolvió todo")
        self.assertEqual((r.saldo_devuelto, r.cashback_revertido), (D("50.00"), D("40.00")))
        self.assertIsNone(self.s.get(LibretaVenta, v.id))
        self.assertEqual(self._saldo(), D("100.00"))


class ColaOfflineTest(_Db):
    def _entry(self, **kw):
        base = {
            "employee_code": "VEND-2", "employee_name": "Fanny", "tipo": "venta", "items": [],
            "monto_total": "300", "monto_neto": "300", "pago_tarjeta": False, "origen": "Entrada",
            "created_at": datetime(2026, 11, 8, 17, tzinfo=UTC).isoformat(),
            "operacion_uuid": str(uuid.uuid4()),
        }
        base.update(kw)
        return base

    def _drenar(self, entries):
        guardadas: list = []
        with patch.object(cola, "_load_raw", return_value=list(entries)), \
             patch.object(cola, "_save_raw", side_effect=lambda e: guardadas.append(e)):
            subidas = cola.drenar_pendientes(self.s)
        return subidas, guardadas[-1]

    def test_qr_escaneado_sin_conexion_se_resuelve_al_subir(self):
        subidas, restantes = self._drenar([self._entry(cliente_codigo="cli-000007")])
        self.assertEqual((subidas, restantes), (1, []))
        self.assertEqual(self._saldo(), D("30.00"))

    def test_reintento_no_duplica_venta_ni_cashback(self):
        e = self._entry(cliente_id=self.cliente.id)
        self._drenar([e])
        self._drenar([e])
        self.assertEqual(self.s.scalar(select(func.count(LibretaVenta.id))), 1)
        self.assertEqual(self._saldo(), D("30.00"))

    def test_entrada_vieja_sin_uuid_sigue_subiendo(self):
        e = self._entry()
        del e["operacion_uuid"]
        subidas, _ = self._drenar([e])
        self.assertEqual(subidas, 1)

    def test_canje_en_la_cola_no_se_sube(self):
        subidas, restantes = self._drenar([self._entry(cliente_id=self.cliente.id, monto_monedero="50")])
        self.assertEqual(subidas, 0)
        self.assertEqual(len(restantes), 1)
        self.assertEqual(self.s.scalar(select(func.count(LibretaVenta.id))), 0)

    def test_cashback_pendiente_suma_lo_estimado(self):
        with patch.object(cola, "pendientes", return_value=[{"cashback_estimado": "12.30"}, {"x": 1}, {"cashback_estimado": "1.05"}]):
            self.assertEqual(cola.cashback_pendiente(), D("13.35"))


if __name__ == "__main__":
    unittest.main()
