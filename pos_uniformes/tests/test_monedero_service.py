"""Monedero de clientes: reglas del saldo (cashback, canje, vencimiento,
reversas y ajustes). Casi todo es lo que NO debe pasar: saldo negativo,
cashback doble, gastar lo vencido, tasa inventada.

Base SQLite en memoria (como test_prestamos_service). Lo que solo Postgres
puede probar (FOR UPDATE, trigger de inmutabilidad, RESTRICT) está en
test_monedero_postgres.py.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Cliente,
    LibretaVenta,
    MonederoAplicacion,
    MonederoMovimiento,
    RolUsuario,
    Usuario,
)
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.tests._programa_de_prueba import inscribir, programa_de_prueba

D = Decimal
UTC = timezone.utc
T0 = datetime(2026, 3, 31, 15, 0, tzinfo=UTC)


class ReglasPurasTest(unittest.TestCase):
    def test_vence_a_los_12_meses_de_calendario(self):
        self.assertEqual(mon.vencimiento_de(T0), datetime(2027, 3, 31, 15, 0, tzinfo=UTC))

    def test_dia_que_no_existe_cae_al_ultimo_del_mes(self):
        self.assertEqual(mon.sumar_meses(datetime(2028, 2, 29, tzinfo=UTC), 12), datetime(2029, 2, 28, tzinfo=UTC))
        self.assertEqual(mon.sumar_meses(datetime(2026, 1, 31, tzinfo=UTC), 1), datetime(2026, 2, 28, tzinfo=UTC))
        self.assertEqual(mon.sumar_meses(datetime(2026, 12, 15, tzinfo=UTC), 1), datetime(2027, 1, 15, tzinfo=UTC))

    def test_cashback_se_trunca_al_centavo(self):
        self.assertEqual(mon.calcular_cashback(D("333.33"), D("3")), D("9.99"))   # 9.9999
        self.assertEqual(mon.calcular_cashback(D("100"), D("2.5")), D("2.50"))

    def test_sin_tasa_no_hay_cashback(self):
        self.assertEqual(mon.calcular_cashback(D("500"), None), D("0.00"))
        self.assertEqual(mon.calcular_cashback(D("500"), D("0")), D("0.00"))

    def test_lo_pagado_con_monedero_no_genera_cashback(self):
        self.assertEqual(mon.importe_elegible(D("450"), D("100")), D("350.00"))
        self.assertEqual(mon.importe_elegible(D("450"), D("450")), D("0.00"))
        self.assertEqual(mon.importe_elegible(D("450"), None), D("450.00"))

    def test_canje_nunca_pasa_saldo_ni_total(self):
        self.assertEqual(mon.canje_ajustado(D("450"), D("1000")), D("450.00"))
        self.assertEqual(mon.canje_ajustado(D("450"), D("0")), D("0.00"))
        self.assertEqual(mon.canje_ajustado(D("450"), D("100"), D("50")), D("50.00"))

    def test_lo_que_resta_cae_en_peso_o_medio_peso(self):
        # $37.42 de saldo sobre $450: quedarían $412.58 por cobrar; se usa
        # $37.00 y se cobran $413.00.
        self.assertEqual(mon.canje_ajustado(D("450"), D("37.42")), D("37.00"))
        # $37.62 → se cobran $412.50.
        self.assertEqual(mon.canje_ajustado(D("450"), D("37.62")), D("37.50"))
        # Saldo menor a medio peso: no alcanza para nada.
        self.assertEqual(mon.canje_ajustado(D("450"), D("0.30")), D("0.00"))
        # Total en .50: el resto también.
        self.assertEqual(mon.canje_ajustado(D("449.50"), D("10.20")), D("10.00"))


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cajero = Usuario(username="caja", nombre_completo="Caja", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000001", nombre="Ana López")
        self.otro = Cliente(codigo_cliente="CLI-000002", nombre="Bea Ruiz")
        self.s.add_all([self.admin, self.cajero, self.cliente, self.otro])
        self.s.flush()
        # E5-A: el % es el del programa del cliente; la configuración general
        # solo enciende o apaga el Monedero.
        self.programa = programa_de_prueba(self.s, "0", clave="PRUEBA")
        for c in (self.cliente, self.otro):
            inscribir(self.s, c.id, self.programa)

    def _tasa(self, tasa="5", habilitado=True, desde=None):
        cfg = mon.guardar_config(self.s, tasa=tasa, habilitado=habilitado, usuario_id=self.admin.id)
        cfg.vigente_desde = desde or datetime(2020, 1, 1, tzinfo=UTC)
        self.programa.tasa_monedero = D(tasa)
        self.s.flush()
        return cfg

    def _venta(self, total="100", *, cliente=None, monedero="0", tipo="venta", cuando=T0):
        v = LibretaVenta(
            employee_code="VEND-2",
            employee_name="Fanny",
            tipo=tipo,
            monto_total=D(total),
            monto_neto=D(total) - D(monedero),
            monto_monedero=D(monedero),
            cliente_id=(cliente or self.cliente).id,
            operacion_uuid=str(uuid.uuid4()),
            origen="Entrada",
            created_at=cuando,
            detalle=[],
        )
        self.s.add(v)
        self.s.flush()
        return v

    def _cashback(self, total="100", cuando=T0, **kw):
        v = self._venta(total, cuando=cuando, **kw)
        return v, mon.acreditar_cashback(self.s, libreta_venta=v, momento=cuando)

    def _disponible(self, cliente=None, momento=T0):
        return mon.resumen_cliente(self.s, (cliente or self.cliente).id, momento).disponible


class ConfiguracionTest(_Base):
    def test_sin_configurar_no_hay_cashback_ni_monedero(self):
        v = self._venta("500")
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0))
        self.assertIsNone(mon.monedero_de_cliente(self.s, self.cliente.id))
        self.assertIsNone(mon.tasa_vigente(self.s))

    def test_deshabilitado_no_da_cashback(self):
        self._tasa("5", habilitado=False)
        self.assertIsNone(mon.tasa_vigente(self.s))

    def test_solo_admin_configura(self):
        with self.assertRaises(mon.SinPermiso):
            mon.guardar_config(self.s, tasa="5", habilitado=True, usuario_id=self.cajero.id)

    def test_no_se_habilita_en_cero_ni_fuera_de_rango(self):
        with self.assertRaises(mon.MonederoError):
            mon.guardar_config(self.s, tasa="0", habilitado=True, usuario_id=self.admin.id)
        with self.assertRaises(mon.MonederoError):
            mon.guardar_config(self.s, tasa="101", habilitado=True, usuario_id=self.admin.id)

    def test_rige_la_tasa_vigente_cuando_se_hizo_la_venta(self):
        """E5-A: rige el programa que tenía el cliente cuando compró (Club 5 %
        hasta el 1 de abril, Leal 10 % desde entonces)."""
        self._tasa("5", desde=datetime(2026, 1, 1, tzinfo=UTC))
        cambio = datetime(2026, 4, 1, tzinfo=UTC)
        club = self.s.scalars(select(mon.Membresia).where(mon.Membresia.cliente_id == self.cliente.id)).one()
        club.estado, club.hasta = "reemplazada", cambio
        inscribir(self.s, self.cliente.id, programa_de_prueba(self.s, "10"), desde=cambio)
        _, antes = self._cashback("100", cuando=datetime(2026, 3, 15, tzinfo=UTC))
        _, despues = self._cashback("100", cuando=datetime(2026, 4, 15, tzinfo=UTC))
        self.assertEqual((antes.monto, antes.tasa_snapshot), (D("5.00"), D("5.00")))
        self.assertEqual((despues.monto, despues.tasa_snapshot), (D("10.00"), D("10.00")))

    def test_venta_anterior_a_la_primera_configuracion_no_gana(self):
        """Nada retroactivo: la tasa no aplica a ventas de antes."""
        self._tasa("5", desde=datetime(2026, 6, 1, tzinfo=UTC))
        _, mov = self._cashback("100", cuando=datetime(2026, 5, 1, tzinfo=UTC))
        self.assertIsNone(mov)


class CashbackTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self._tasa("5")

    def test_acredita_y_crea_el_monedero_la_primera_vez(self):
        v, mov = self._cashback("450")
        self.assertEqual(mov.monto, D("22.50"))
        self.assertEqual(mov.base_calculo, D("450.00"))
        self.assertEqual(mov.expira_at.replace(tzinfo=UTC), datetime(2027, 3, 31, 15, 0, tzinfo=UTC))
        self.assertEqual(mov.libreta_venta_id, v.id)
        self.assertEqual(self._disponible(), D("22.50"))

    def test_repetir_no_duplica(self):
        v, mov = self._cashback("450")
        otra = mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0)
        self.assertEqual(otra.id, mov.id)
        self.assertEqual(self._disponible(), D("22.50"))

    def test_sin_cliente_apartado_o_abono_no_genera(self):
        v = self._venta("300")
        v.cliente_id = None
        self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0))
        for tipo in ("apartado", "abono"):
            self.assertIsNone(mon.acreditar_cashback(self.s, libreta_venta=self._venta("300", tipo=tipo), momento=T0))

    def test_lo_pagado_con_saldo_no_genera(self):
        self._cashback("1000")  # 50 de saldo
        v = self._venta("200", monedero="50")
        mon.canjear(self.s, libreta_venta=v, monto="50", momento=T0)
        mov = mon.acreditar_cashback(self.s, libreta_venta=v, momento=T0)
        self.assertEqual(mov.base_calculo, D("150.00"))
        self.assertEqual(mov.monto, D("7.50"))

    def test_monedero_bloqueado_no_gana(self):
        mon.cambiar_estado(self.s, cliente_id=self.cliente.id, estado=mon.BLOQUEADO, motivo="revisión", usuario_id=self.admin.id)
        _, mov = self._cashback("100")
        self.assertIsNone(mov)


class CanjeTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self._tasa("10")
        self._cashback("1000")  # $100 de saldo

    def test_paga_y_descuenta(self):
        v = self._venta("80", monedero="80")
        mov = mon.canjear(self.s, libreta_venta=v, monto="80", momento=T0)
        self.assertEqual(mov.monto, D("-80.00"))
        self.assertEqual(self._disponible(), D("20.00"))

    def test_no_mas_que_el_saldo(self):
        v = self._venta("500", monedero="0")
        with self.assertRaises(mon.SaldoInsuficiente):
            mon.canjear(self.s, libreta_venta=v, monto="100.01", momento=T0)
        self.assertEqual(self._disponible(), D("100.00"))

    def test_no_mas_que_el_total(self):
        v = self._venta("50")
        with self.assertRaises(mon.MonederoError):
            mon.canjear(self.s, libreta_venta=v, monto="60", momento=T0)

    def test_sin_cliente_no_se_canjea(self):
        v = self._venta("50")
        v.cliente_id = None
        with self.assertRaises(mon.MonederoError):
            mon.canjear(self.s, libreta_venta=v, monto="10", momento=T0)

    def test_no_en_apartado(self):
        v = self._venta("50", tipo="apartado")
        with self.assertRaises(mon.MonederoError):
            mon.canjear(self.s, libreta_venta=v, monto="10", momento=T0)

    def test_repetir_no_cobra_dos_veces(self):
        v = self._venta("30", monedero="30")
        a = mon.canjear(self.s, libreta_venta=v, monto="30", momento=T0)
        b = mon.canjear(self.s, libreta_venta=v, monto="30", momento=T0)
        self.assertEqual(a.id, b.id)
        self.assertEqual(self._disponible(), D("70.00"))

    def test_bloqueado_no_canjea(self):
        mon.cambiar_estado(self.s, cliente_id=self.cliente.id, estado=mon.BLOQUEADO, motivo="x", usuario_id=self.admin.id)
        with self.assertRaises(mon.MonederoNoActivo):
            mon.canjear(self.s, libreta_venta=self._venta("10"), monto="10", momento=T0)

    def test_otro_cliente_sin_monedero(self):
        with self.assertRaises(mon.SaldoInsuficiente):
            mon.canjear(self.s, libreta_venta=self._venta("10", cliente=self.otro), monto="10", momento=T0)

    def test_consume_primero_lo_que_vence_antes(self):
        segundo = datetime(2026, 6, 1, tzinfo=UTC)
        _, nuevo = self._cashback("500", cuando=segundo)  # $50, vence después
        v = self._venta("120", cuando=segundo)
        debito = mon.canjear(self.s, libreta_venta=v, monto="120", momento=segundo)
        aplic = {a.credito_id: a.monto for a in self.s.scalars(
            select(MonederoAplicacion).where(MonederoAplicacion.debito_id == debito.id))}
        viejo_id = next(i for i in aplic if i != nuevo.id)
        self.assertEqual(aplic[viejo_id], D("100.00"))
        self.assertEqual(aplic[nuevo.id], D("20.00"))


class VencimientoTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self._tasa("10")
        self._cashback("1000")  # $100, vence 2027-03-31 15:00

    def test_lo_vencido_no_se_puede_usar_aunque_no_se_haya_procesado(self):
        despues = datetime(2027, 3, 31, 15, 0, 1, tzinfo=UTC)
        self.assertEqual(self._disponible(momento=despues), D("0.00"))
        v = self._venta("10", cuando=despues)
        with self.assertRaises(mon.SaldoInsuficiente):
            mon.canjear(self.s, libreta_venta=v, monto="10", momento=despues)

    def test_un_segundo_antes_aun_sirve(self):
        self.assertEqual(self._disponible(momento=datetime(2027, 3, 31, 14, 59, tzinfo=UTC)), D("100.00"))

    def test_procesar_asienta_solo_lo_que_quedaba_y_no_duplica(self):
        v = self._venta("30")
        mon.canjear(self.s, libreta_venta=v, monto="30", momento=T0)
        despues = datetime(2027, 4, 1, tzinfo=UTC)
        self.assertEqual(mon.procesar_vencimientos(self.s, despues), 1)
        self.assertEqual(mon.procesar_vencimientos(self.s, despues), 0)
        monedero = mon.monedero_de_cliente(self.s, self.cliente.id)
        s = mon.saldo(self.s, monedero.id, despues)
        self.assertEqual((s.disponible, s.vencido_por_procesar, s.expirado), (D("0.00"), D("0.00"), D("70.00")))

    def test_no_vence_antes_de_tiempo(self):
        self.assertEqual(mon.procesar_vencimientos(self.s, datetime(2027, 3, 1, tzinfo=UTC)), 0)


class AnulacionTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self._tasa("10")

    def test_revierte_cashback_no_gastado(self):
        v, _ = self._cashback("200")
        r = mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="devolución", momento=T0)
        self.assertEqual(r.cashback_revertido, D("20.00"))
        self.assertEqual(self._disponible(), D("0.00"))

    def test_bloquea_si_el_cashback_ya_se_gasto(self):
        v, _ = self._cashback("200")  # $20
        mon.canjear(self.s, libreta_venta=self._venta("5"), monto="5", momento=T0)
        with self.assertRaises(mon.CashbackYaGastado):
            mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="devolución", momento=T0)
        self.assertEqual(self._disponible(), D("15.00"))  # nada se movió

    def test_devuelve_el_saldo_usado_con_su_vencimiento_original(self):
        _, credito = self._cashback("1000")  # $100, vence 2027-03-31
        luego = datetime(2026, 9, 1, tzinfo=UTC)
        v = self._venta("100", monedero="40", cuando=luego)
        mon.canjear(self.s, libreta_venta=v, monto="40", momento=luego)
        mon.acreditar_cashback(self.s, libreta_venta=v, momento=luego)  # $6 sobre $60
        r = mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="se canceló", momento=luego)
        self.assertEqual(r.saldo_devuelto, D("40.00"))
        self.assertEqual(r.cashback_revertido, D("6.00"))
        self.assertEqual(r.devoluciones[0].expira_at.replace(tzinfo=UTC), credito.expira_at.replace(tzinfo=UTC))
        self.assertEqual(self._disponible(momento=luego), D("100.00"))

    def test_repetir_no_duplica(self):
        v, _ = self._cashback("200")
        mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="x", momento=T0)
        r = mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="x", momento=T0)
        self.assertEqual((r.reversas, r.devoluciones), ([], []))

    def test_solo_admin_y_con_motivo(self):
        v, _ = self._cashback("200")
        with self.assertRaises(mon.SinPermiso):
            mon.anular_operacion(self.s, v, usuario_id=self.cajero.id, motivo="x")
        with self.assertRaises(mon.MonederoError):
            mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="  ")

    def test_soltar_deja_la_venta_libre_y_conserva_uuid(self):
        v, mov = self._cashback("200")
        mon.anular_operacion(self.s, v, usuario_id=self.admin.id, motivo="x", momento=T0)
        mon.soltar_operacion(self.s, v.id)
        self.assertFalse(mon.tiene_movimientos(self.s, v.id))
        self.assertEqual(mov.operacion_uuid, v.operacion_uuid)


class AjusteTest(_Base):
    def test_a_favor_vence_a_12_meses(self):
        mov = mon.ajustar(self.s, cliente_id=self.cliente.id, monto="50", motivo="cortesía", usuario_id=self.admin.id, momento=T0)
        self.assertEqual(mov.tipo, mon.AJUSTE_ABONO)
        self.assertEqual(self._disponible(), D("50.00"))
        self.assertEqual(mov.expira_at.replace(tzinfo=UTC), mon.vencimiento_de(T0))

    def test_en_contra_no_deja_negativo(self):
        mon.ajustar(self.s, cliente_id=self.cliente.id, monto="50", motivo="a", usuario_id=self.admin.id, momento=T0)
        with self.assertRaises(mon.SaldoInsuficiente):
            mon.ajustar(self.s, cliente_id=self.cliente.id, monto="-50.01", motivo="b", usuario_id=self.admin.id, momento=T0)
        mon.ajustar(self.s, cliente_id=self.cliente.id, monto="-50", motivo="b", usuario_id=self.admin.id, momento=T0)
        self.assertEqual(self._disponible(), D("0.00"))

    def test_motivo_admin_y_monto_obligatorios(self):
        with self.assertRaises(mon.MonederoError):
            mon.ajustar(self.s, cliente_id=self.cliente.id, monto="5", motivo="", usuario_id=self.admin.id)
        with self.assertRaises(mon.MonederoError):
            mon.ajustar(self.s, cliente_id=self.cliente.id, monto="0", motivo="x", usuario_id=self.admin.id)
        with self.assertRaises(mon.SinPermiso):
            mon.ajustar(self.s, cliente_id=self.cliente.id, monto="5", motivo="x", usuario_id=self.cajero.id)


class ConsultasTest(_Base):
    def test_historial_con_saldo_acumulado(self):
        self._tasa("10")
        self._cashback("1000")
        mon.canjear(self.s, libreta_venta=self._venta("30"), monto="30", momento=T0 + timedelta(minutes=1))
        monedero = mon.monedero_de_cliente(self.s, self.cliente.id)
        filas = mon.historial(self.s, monedero.id)
        self.assertEqual([f.saldo_contable for f in filas], [D("70.00"), D("100.00")])
        self.assertEqual(filas[0].etiqueta, "Pago con saldo")

    def test_reporte(self):
        self._tasa("10")
        self._cashback("1000")
        mon.canjear(self.s, libreta_venta=self._venta("30"), monto="30", momento=T0)
        mon.ajustar(self.s, cliente_id=self.otro.id, monto="5", motivo="x", usuario_id=self.admin.id, momento=T0)
        r = mon.reporte(self.s, T0 - timedelta(days=1), T0 + timedelta(days=1), momento=T0)
        self.assertEqual(r.cashback_generado, D("100.00"))
        self.assertEqual(r.saldo_utilizado, D("30.00"))
        self.assertEqual(r.saldo_vigente_total, D("75.00"))
        self.assertEqual(r.clientes_con_monedero, 2)
        self.assertEqual(len(r.ajustes), 1)

    def test_buscar_por_nombre_o_codigo(self):
        self.assertEqual([c.codigo_cliente for c in mon.buscar_clientes(self.s, "ana")], ["CLI-000001"])
        self.assertEqual([c.nombre for c in mon.buscar_clientes(self.s, "000002")], ["Bea Ruiz"])

    def test_acreditar_faltantes_es_idempotente(self):
        self._tasa("10")
        v = self._venta("100", cuando=T0)
        self.assertEqual(mon.acreditar_faltantes(self.s, dias=30, momento=T0 + timedelta(days=1)), 1)
        self.assertEqual(mon.acreditar_faltantes(self.s, dias=30, momento=T0 + timedelta(days=1)), 0)
        self.assertTrue(mon.tiene_movimientos(self.s, v.id))
        self.assertEqual(
            self.s.scalar(select(MonederoMovimiento.tipo).where(MonederoMovimiento.libreta_venta_id == v.id)),
            mon.CASHBACK,
        )


if __name__ == "__main__":
    unittest.main()
