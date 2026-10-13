"""Dos solicitudes de vacaciones AL MISMO TIEMPO no gastan el mismo saldo.

En Postgres de verdad (base de prueba). Le quedan 12 días; las dos piden 7.
Solo una entra: la otra, al pasar el candado, ve los 7 apartados.
"""

from __future__ import annotations

import threading
import time
import unittest
from datetime import date, timedelta

from sqlalchemy import delete

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AuditoriaAusencias,
    Empleada,
    EmpleadaHorario,
    ExpedienteVacacional,
    MovimientoVacaciones,
    PeriodoVacaciones,
    SolicitudVacaciones,
)
from pos_uniformes.services import vacaciones_service as vs


def _con_autoservicio(session, code, **kw):
    """Expediente + autoservicio abierto: estas pruebas son de ella pidiendo."""
    exp = vs.capturar_expediente(session, code, **kw)
    vs.habilitar_autoservicio(session, code, True, quien="VEND-1")
    return exp

CODE = "TST-VA"


class VacacionesAlMismoTiempoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._limpiar()
        self.hoy = date.today()
        with get_session() as s:
            s.add(Empleada(codigo=CODE, nombre_completo="Prueba Vacaciones", activo=True))
            s.add(EmpleadaHorario(employee_code=CODE, descanso_weekday=6))
            s.commit()
            _con_autoservicio(s, CODE, fecha_ingreso=self.hoy - timedelta(days=400), quien="VEND-1")
            vs.generar_periodos(s, CODE, hoy=self.hoy)
            s.commit()

    def tearDown(self) -> None:
        self._limpiar()

    def _limpiar(self) -> None:
        with get_session() as s:
            s.execute(delete(MovimientoVacaciones).where(MovimientoVacaciones.employee_code == CODE))
            s.execute(delete(SolicitudVacaciones).where(SolicitudVacaciones.employee_code == CODE))
            s.execute(delete(PeriodoVacaciones).where(PeriodoVacaciones.employee_code == CODE))
            s.execute(delete(ExpedienteVacacional).where(ExpedienteVacacional.employee_code == CODE))
            s.execute(delete(AuditoriaAusencias).where(AuditoriaAusencias.employee_code == CODE))
            s.execute(delete(EmpleadaHorario).where(EmpleadaHorario.employee_code == CODE))
            s.execute(delete(Empleada).where(Empleada.codigo == CODE))
            s.commit()

    def test_solo_una_aparta_el_saldo(self) -> None:
        lunes = self.hoy + timedelta(days=30)
        while lunes.weekday() != 0:
            lunes += timedelta(days=1)
        rangos = {"A": (lunes, lunes + timedelta(days=7)),            # 7 laborables
                  "B": (lunes + timedelta(days=21), lunes + timedelta(days=28))}
        resultados: dict[str, str] = {}
        primera = threading.Event()

        def pedir(cual: str, espera: float) -> None:
            try:
                with get_session() as s:
                    desde, hasta = rangos[cual]
                    vs.pedir(s, employee_code=CODE, nombre="x", desde=desde, hasta=hasta, hoy=self.hoy)
                    primera.set()
                    time.sleep(espera)
                    s.commit()
                resultados[cual] = "ok"
            except vs.NoSePuede as exc:
                resultados[cual] = f"no: {exc}"

        a = threading.Thread(target=pedir, args=("A", 0.8))
        a.start()
        self.assertTrue(primera.wait(5))
        b = threading.Thread(target=pedir, args=("B", 0))
        b.start()
        a.join(10)
        b.join(10)
        self.assertEqual(resultados["A"], "ok")
        self.assertTrue(resultados["B"].startswith("no:"), resultados)


if __name__ == "__main__":
    unittest.main()
