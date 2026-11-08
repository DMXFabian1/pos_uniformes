"""Monedero en Postgres de verdad (base de prueba local).

Lo que SQLite no puede probar:
- dos canjes AL MISMO TIEMPO no gastan el mismo peso (SELECT … FOR UPDATE);
- dos terminales que crean el monedero a la vez terminan con uno solo;
- el trigger no deja editar ni borrar movimientos;
- un kiosko viejo no puede borrar una venta que movió el monedero (RESTRICT);
- los CHECK y el índice único de la Libreta.

Limpieza: los movimientos son inmutables por diseño, así que el tearDown
apaga los triggers SOLO dentro de su transacción (base de prueba).
"""

from __future__ import annotations

import threading
import time
import unittest
import uuid
from decimal import Decimal

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    Cliente,
    LibretaVenta,
    Monedero,
    MonederoAplicacion,
    MonederoConfig,
    MonederoMovimiento,
    RolUsuario,
    Usuario,
)
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon

D = Decimal
_SUFIJO = uuid.uuid4().hex[:8].upper()
CODIGO = f"CLI-T{_SUFIJO}"
ADMIN = f"tst_monedero_{_SUFIJO.lower()}"


class _Pg(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as s:
            admin = Usuario(username=ADMIN, nombre_completo="Admin monedero", password_hash="x",
                            rol=RolUsuario.ADMIN, activo=True)
            cliente = Cliente(codigo_cliente=CODIGO, nombre="Prueba Monedero")
            s.add_all([admin, cliente])
            s.flush()
            self.admin_id, self.cliente_id = admin.id, cliente.id
            cfg = mon.guardar_config(s, tasa="10", habilitado=True, usuario_id=admin.id, nota="test")
            self.config_id = cfg.id
            s.commit()

    def tearDown(self) -> None:
        with get_session() as s:
            s.execute(text("ALTER TABLE monedero_aplicacion DISABLE TRIGGER monedero_aplicacion_inmutable"))
            s.execute(text("ALTER TABLE monedero_movimiento DISABLE TRIGGER monedero_movimiento_inmutable"))
            ids = select(Monedero.id).where(Monedero.cliente_id == self.cliente_id)
            movs = select(MonederoMovimiento.id).where(MonederoMovimiento.monedero_id.in_(ids))
            s.execute(delete(MonederoAplicacion).where(MonederoAplicacion.debito_id.in_(movs)))
            s.execute(update(MonederoMovimiento).where(MonederoMovimiento.monedero_id.in_(ids))
                      .values(movimiento_relacionado_id=None))
            s.execute(delete(MonederoMovimiento).where(MonederoMovimiento.monedero_id.in_(ids)))
            s.execute(text("ALTER TABLE monedero_aplicacion ENABLE TRIGGER monedero_aplicacion_inmutable"))
            s.execute(text("ALTER TABLE monedero_movimiento ENABLE TRIGGER monedero_movimiento_inmutable"))
            s.execute(delete(Monedero).where(Monedero.cliente_id == self.cliente_id))
            s.execute(delete(LibretaVenta).where(LibretaVenta.cliente_id == self.cliente_id))
            s.execute(delete(MonederoConfig).where(MonederoConfig.id == self.config_id))
            s.execute(delete(Cliente).where(Cliente.id == self.cliente_id))
            s.execute(delete(Usuario).where(Usuario.id == self.admin_id))
            s.commit()

    def _venta(self, s, total, **kw) -> LibretaVenta:
        return lib.registrar_operacion(
            s, employee_code="TST-MON", employee_name="Prueba", tipo="venta", items=[],
            monto_total=D(total), cliente_id=self.cliente_id, operacion_uuid=str(uuid.uuid4()),
            origen="test-monedero", **kw,
        )

    def _saldo(self) -> Decimal:
        with get_session() as s:
            return mon.resumen_cliente(s, self.cliente_id).disponible

    def _dar_saldo(self, total="1000") -> LibretaVenta:
        with get_session() as s:
            v = self._venta(s, total)
            s.commit()
            return v


class InmutableTest(_Pg):
    def test_no_se_edita_ni_se_borra(self):
        v = self._dar_saldo()
        with get_session() as s:
            mov = s.scalars(select(MonederoMovimiento).where(MonederoMovimiento.libreta_venta_id == v.id)).one()
            mov.monto = D("999")
            with self.assertRaises(DBAPIError):
                s.flush()
            s.rollback()
            mov = s.scalars(select(MonederoMovimiento).where(MonederoMovimiento.libreta_venta_id == v.id)).one()
            s.delete(mov)
            with self.assertRaises(DBAPIError):
                s.flush()
            s.rollback()

    def test_solo_se_puede_soltar_la_liga(self):
        v = self._dar_saldo()
        with get_session() as s:
            mon.soltar_operacion(s, v.id)
            s.commit()
            self.assertFalse(mon.tiene_movimientos(s, v.id))

    def test_kiosko_viejo_no_puede_borrar_la_venta(self):
        """Un kiosko sin esta versión haría session.delete(): la base lo frena."""
        v = self._dar_saldo()
        with get_session() as s:
            with self.assertRaises(IntegrityError):
                s.execute(delete(LibretaVenta).where(LibretaVenta.id == v.id))
            s.rollback()

    def test_anulacion_completa_si_puede(self):
        v = self._dar_saldo("200")
        with get_session() as s:
            lib.anular_operacion_con_monedero(s, v.id, usuario_id=self.admin_id, motivo="prueba")
            s.commit()
        self.assertEqual(self._saldo(), D("0.00"))
        with get_session() as s:
            self.assertIsNone(s.get(LibretaVenta, v.id))


class RestriccionesTest(_Pg):
    def test_monto_monedero_no_pasa_el_total(self):
        with get_session() as s:
            v = self._venta(s, "100")
            v.monto_monedero = D("100.01")
            with self.assertRaises(IntegrityError):
                s.flush()
            s.rollback()

    def test_operacion_uuid_unico(self):
        op = str(uuid.uuid4())
        with get_session() as s:
            lib.registrar_operacion(s, employee_code="TST-MON", employee_name="", tipo="venta", items=[],
                                    monto_total=D("10"), operacion_uuid=op, cliente_id=self.cliente_id)
            s.flush()
            with self.assertRaises(IntegrityError):
                lib.registrar_operacion(s, employee_code="TST-MON", employee_name="", tipo="venta", items=[],
                                        monto_total=D("10"), operacion_uuid=op, cliente_id=self.cliente_id)
            s.rollback()


class ConcurrenciaTest(_Pg):
    def test_dos_canjes_a_la_vez_no_gastan_el_mismo_saldo(self):
        self._dar_saldo("1000")   # $100
        resultados: dict[str, str] = {}
        primero_bloqueo = threading.Event()

        def canjear(nombre: str, espera: float) -> None:
            try:
                with get_session() as s:
                    lib.registrar_venta_con_monedero(
                        s, employee_code="TST-MON", employee_name="", items=[], monto_total=D("80"),
                        monto_monedero=D("80"), cliente_id=self.cliente_id, operacion_uuid=str(uuid.uuid4()),
                        origen="test-monedero",
                    )
                    primero_bloqueo.set()
                    time.sleep(espera)
                    s.commit()
                    resultados[nombre] = "ok"
            except mon.SaldoInsuficiente:
                resultados[nombre] = "sin saldo"
            except Exception as exc:  # noqa: BLE001
                resultados[nombre] = f"error {exc!r}"

        a = threading.Thread(target=canjear, args=("A", 0.8))
        a.start()
        self.assertTrue(primero_bloqueo.wait(5))
        b = threading.Thread(target=canjear, args=("B", 0))
        b.start()
        a.join(10)
        b.join(10)
        self.assertEqual(sorted(resultados.values()), ["ok", "sin saldo"], resultados)
        self.assertEqual(self._saldo(), D("20.00"))

    def test_dos_terminales_crean_un_solo_monedero(self):
        resultados: list[str] = []
        listo = threading.Event()

        def vender(espera: float) -> None:
            try:
                with get_session() as s:
                    self._venta(s, "100")
                    listo.set()
                    time.sleep(espera)
                    s.commit()
                    resultados.append("ok")
            except Exception as exc:  # noqa: BLE001
                resultados.append(f"error {exc!r}")

        a = threading.Thread(target=vender, args=(0.8,))
        a.start()
        self.assertTrue(listo.wait(5))
        b = threading.Thread(target=vender, args=(0,))
        b.start()
        a.join(10)
        b.join(10)
        self.assertEqual(resultados, ["ok", "ok"])
        with get_session() as s:
            self.assertEqual(len(s.scalars(select(Monedero).where(Monedero.cliente_id == self.cliente_id)).all()), 1)
        self.assertEqual(self._saldo(), D("20.00"))


if __name__ == "__main__":
    unittest.main()
