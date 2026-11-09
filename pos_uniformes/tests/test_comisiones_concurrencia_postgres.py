"""Candados por empleada en Postgres de verdad (decisión D4, 2026-11-08).

Solo corre contra la base LOCAL de prueba (127.0.0.1/pos_uniformes_test, la
fija conftest). Lo que SQLite no puede probar:
- dos pagos simultáneos a la misma empleada dejan UN pago;
- un pago y una reasignación simultáneos no cuentan la venta dos veces ni la
  pierden, sin importar cuál llegue primero.

Para que el choque sea seguro (y no cuestión de suerte), el primer hilo toma
el candado de la empleada y se queda dentro un momento; el segundo arranca
mientras tanto y debe esperar.
"""

from __future__ import annotations

import threading
import time
import unittest
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AuditoriaAusencias,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    EmpleadaPago,
    LibretaVenta,
)
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import nomina_service as nom
from pos_uniformes.services.calendario_empleadas_service import (
    bloquear_empleadas,
    cargar_horario,
    comisiones_desde_ultimo_pago,
)

_SUF = uuid.uuid4().hex[:6].upper()
A, B, C = f"TSTA-{_SUF}", f"TSTB-{_SUF}", f"TSTC-{_SUF}"
ESPERA = 0.8  # lo que el primer hilo se queda con el candado


def _verificar_base_local(s) -> None:
    url = s.get_bind().url
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
        raise unittest.SkipTest("Solo corre contra la base local pos_uniformes_test")


class _Pg(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as s:
            _verificar_base_local(s)
            if s.get_bind().dialect.name != "postgresql":
                raise unittest.SkipTest("requiere PostgreSQL")
            s.add_all([
                Empleada(codigo=A, nombre_completo="Prueba A", activo=True),
                Empleada(codigo=B, nombre_completo="Prueba B", activo=True),
                Empleada(codigo=C, nombre_completo="Prueba C", activo=True),
            ])
            s.commit()

    def tearDown(self) -> None:
        with get_session() as s:
            codes = [A, B, C]
            s.execute(delete(AuditoriaAusencias).where(AuditoriaAusencias.employee_code.in_(codes)))
            s.execute(delete(EmpleadaPago).where(EmpleadaPago.employee_code.in_(codes)))
            s.execute(delete(EmpleadaEvento).where(EmpleadaEvento.employee_code.in_(codes)))
            s.execute(delete(EmpleadaHorario).where(EmpleadaHorario.employee_code.in_(codes)))
            s.execute(delete(LibretaVenta).where(LibretaVenta.employee_code.in_(codes)))
            s.execute(delete(Empleada).where(Empleada.codigo.in_(codes)))
            s.commit()

    def _venta(self, code=A) -> int:
        with get_session() as s:
            v = lib.registrar_operacion(
                s, employee_code=code, employee_name="Prueba A", tipo="venta",
                items=[{"sku": "S", "nombre": "Pants 3pz", "talla": "8", "cantidad": 2, "precio": "590"}],
                monto_total=Decimal("1180.00"), operacion_uuid=str(uuid.uuid4()),
                acreditar_cashback=False,
            )
            s.commit()
            self.assertEqual(v.comisiones, 4)  # 3pz vale 2 por pieza
            return int(v.id)

    def _pendiente(self, code) -> int:
        with get_session() as s:
            return comisiones_desde_ultimo_pago(s, code, cargar_horario(s, code))

    def _pagos(self, code) -> list[EmpleadaPago]:
        with get_session() as s:
            return list(s.scalars(select(EmpleadaPago).where(EmpleadaPago.employee_code == code)))

    @staticmethod
    def _correr(primero, segundo) -> dict:
        """`primero` toma el candado y espera; `segundo` arranca a la mitad."""
        out: dict = {}

        def envolver(nombre, fn):
            try:
                out[nombre] = fn()
            except Exception as exc:  # noqa: BLE001 — se revisa en la prueba
                out[nombre] = exc
            out[f"{nombre}_fin"] = time.monotonic()

        h1 = threading.Thread(target=envolver, args=("primero", primero))
        h2 = threading.Thread(target=envolver, args=("segundo", segundo))
        h1.start()
        time.sleep(ESPERA / 4)
        out["segundo_inicio"] = time.monotonic()
        h2.start()
        h1.join(15)
        h2.join(15)
        return out


class PagosSimultaneosTests(_Pg):
    def test_dos_pagos_a_la_vez_dejan_uno_solo(self) -> None:
        self._venta()

        def pagar_lento():
            with get_session() as s:
                bloquear_empleadas(s, [A])  # mismo candado que usará el servicio
                time.sleep(ESPERA)
                return nom.registrar_pago_con_monto(s, A, creado_por="VEND-1").id

        def pagar():
            with get_session() as s:
                return nom.registrar_pago_con_monto(s, A, creado_por="VEND-1").id

        out = self._correr(pagar_lento, pagar)
        self.assertIsInstance(out["primero"], int, out["primero"])
        self.assertIsInstance(out["segundo"], ValueError, out["segundo"])
        self.assertIn("Ya se le pagó hoy", str(out["segundo"]))
        # El segundo esperó al primero (no revisó con el estado viejo).
        self.assertGreaterEqual(out["segundo_fin"], out["primero_fin"])
        pagos = self._pagos(A)
        self.assertEqual(len(pagos), 1)
        self.assertEqual(pagos[0].comisiones, 4)


class PagoYReasignacionTests(_Pg):
    def test_pago_primero_luego_reasignacion_queda_bloqueada(self) -> None:
        venta_id = self._venta()

        def pagar_lento():
            with get_session() as s:
                bloquear_empleadas(s, [A])
                time.sleep(ESPERA)
                return nom.registrar_pago_con_monto(s, A, creado_por="VEND-1").comisiones

        def reasignar():
            with get_session() as s:
                return lib.reasignar_empleada(s, venta_id, B, actor="VEND-1", hoy=date.today())

        out = self._correr(pagar_lento, reasignar)
        self.assertEqual(out["primero"], 4)  # el pago incluyó la venta
        self.assertIsInstance(out["segundo"], lib.ReasignacionNoPermitida, out["segundo"])
        # La venta sigue siendo de A y B no la cobrará: una sola vez en total.
        with get_session() as s:
            self.assertEqual(s.get(LibretaVenta, venta_id).employee_code, A)
        self.assertEqual(self._pendiente(B), 0)

    def test_reasignacion_primero_luego_pago_no_la_cuenta(self) -> None:
        venta_id = self._venta()

        def reasignar_lento():
            with get_session() as s:
                bloquear_empleadas(s, [A, B])
                time.sleep(ESPERA)
                return lib.reasignar_empleada(s, venta_id, B, actor="VEND-1", hoy=date.today()).employee_code

        def pagar():
            with get_session() as s:
                return nom.registrar_pago_con_monto(s, A, creado_por="VEND-1").comisiones

        out = self._correr(reasignar_lento, pagar)
        self.assertEqual(out["primero"], B)
        self.assertEqual(out["segundo"], 0)  # el pago de A ya no la trae
        self.assertEqual(self._pendiente(B), 4)  # B la cobrará: ni doble ni perdida
        with get_session() as s:
            [aud] = s.scalars(select(AuditoriaAusencias).where(
                AuditoriaAusencias.operacion == "reasignar_venta",
                AuditoriaAusencias.entidad_id == venta_id,
            )).all()
            self.assertEqual((aud.antes["employee_code"], aud.despues["employee_code"]), (A, B))


class ReasignacionCambiadaTests(_Pg):
    """M2: la segunda reasignación leyó «es de A» y tomó el candado de A; al
    obtenerlo, la venta ya es de C. Se rechaza sin tocar nada."""

    def test_a_c_gana_y_a_b_se_rechaza_sin_bitacora(self) -> None:
        venta_id = self._venta()

        def primera_a_c():
            with get_session() as s:
                bloquear_empleadas(s, [A, C])
                time.sleep(ESPERA)  # la segunda lee «A» y se queda esperando
                return lib.reasignar_empleada(s, venta_id, C, actor="VEND-1", hoy=date.today()).employee_code

        def segunda_a_b():
            with get_session() as s:
                return lib.reasignar_empleada(s, venta_id, B, actor="VEND-1", hoy=date.today())

        out = self._correr(primera_a_c, segunda_a_b)
        self.assertEqual(out["primero"], C)
        self.assertIsInstance(out["segundo"], lib.ReasignacionNoPermitida, out["segundo"])
        self.assertIn("cambió de empleada", str(out["segundo"]))
        with get_session() as s:
            self.assertEqual(s.get(LibretaVenta, venta_id).employee_code, C)
            auds = s.scalars(select(AuditoriaAusencias).where(
                AuditoriaAusencias.operacion == "reasignar_venta",
                AuditoriaAusencias.entidad_id == venta_id,
            )).all()
            self.assertEqual([(a.antes["employee_code"], a.despues["employee_code"]) for a in auds], [(A, C)])
        # Los puntos están exactamente una vez: en C.
        self.assertEqual((self._pendiente(A), self._pendiente(B), self._pendiente(C)), (0, 0, 4))


class SesionConDatosViejosTests(_Pg):
    """M3: el /pagar de Telegram calcula el pendiente ANTES de pagar; si
    mientras espera el candado otro proceso deshace el último pago, el pago
    debe salir del estado nuevo, y el mensaje decir lo que se guardó.

    Nota: el mapa de identidad de SQLAlchemy guarda referencias DÉBILES. Si
    nadie conserva el horario cargado antes del candado, Python lo libera y
    la siguiente lectura va a la base (por eso hoy el /pagar solo no lo
    reproduce). El riesgo real es cuando algo de la misma sesión SÍ lo
    conserva; la prueba lo simula reteniéndolo, y así falla sin la corrección."""

    def test_pagar_por_telegram_usa_lo_que_hay_despues_del_candado(self) -> None:
        from pos_uniformes.services import telegram_pagos_service as tg

        hoy = date.today()
        ayer = hoy - timedelta(days=1)
        # Venta vieja (4 puntos) ya pagada ayer en P1; venta de hoy (1 punto) pendiente.
        with get_session() as s:
            v = lib.registrar_operacion(
                s, employee_code=A, employee_name="Prueba A", tipo="venta",
                items=[{"sku": "S", "nombre": "Pants 3pz", "talla": "8", "cantidad": 2, "precio": "590"}],
                monto_total=Decimal("1180.00"), operacion_uuid=str(uuid.uuid4()), acreditar_cashback=False,
                created_at=datetime.now().astimezone() - timedelta(days=2),
            )
            s.commit()
        with get_session() as s:
            p1 = nom.registrar_pago_con_monto(s, A, creado_por="VEND-1", fecha=ayer)
            self.assertEqual(p1.comisiones, 4)
            p1_id = int(p1.id)
        with get_session() as s:
            lib.registrar_operacion(
                s, employee_code=A, employee_name="Prueba A", tipo="venta",
                items=[{"sku": "S", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "200"}],
                monto_total=Decimal("200.00"), operacion_uuid=str(uuid.uuid4()), acreditar_cashback=False,
            )
            s.commit()
        self.assertEqual(self._pendiente(A), 1)

        def deshacer_mientras_espera():
            with get_session() as s:
                bloquear_empleadas(s, [A])
                time.sleep(ESPERA)  # el bot ya calculó y está esperando el candado
                nom.deshacer_pago(s, p1_id, creado_por="VEND-1")
                s.commit()
                return True

        def pagar_por_telegram():
            with get_session() as s:
                retenido = s.get(EmpleadaHorario, A)  # algo de la sesión lo conserva
                self.assertEqual(retenido.fecha_ultimo_pago, ayer)
                texto = tg.pagar_por_code(s, A, quien="VEND-1", hoy=hoy)
                self.assertEqual(retenido.fecha_ultimo_pago, hoy)  # ya no es el viejo
                return texto

        out = self._correr(deshacer_mientras_espera, pagar_por_telegram)
        self.assertIs(out["primero"], True, out["primero"])
        texto = out["segundo"]
        self.assertIsInstance(texto, str, texto)
        [pago] = self._pagos(A)  # P1 se deshizo; queda solo el de hoy
        self.assertEqual(pago.fecha, hoy)
        # Con datos viejos habría cobrado solo 1 punto (el corte de P1).
        self.assertEqual(pago.comisiones, 5)
        self.assertIn(f"${pago.total:,.2f}", texto)  # el mensaje dice lo guardado
        with get_session() as s:
            horario = s.get(EmpleadaHorario, A)
            self.assertEqual(horario.fecha_ultimo_pago, hoy)
        self.assertEqual(self._pendiente(A), 0)


if __name__ == "__main__":
    unittest.main()
