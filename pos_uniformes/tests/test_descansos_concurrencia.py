"""Dos autoservicios al MISMO tiempo para el mismo día — solo uno gana el cupo.

En Postgres de verdad (la base de prueba): el candado de `descansos_service`
pone en fila a la segunda hasta que la primera confirma, y entonces la segunda
ve el día ocupado. Sin el candado, las dos leían "libre" y las dos entraban.
"""

from __future__ import annotations

import threading
import time
import unittest
from datetime import date, timedelta
from unittest import mock

from sqlalchemy import delete

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AuditoriaAusencias,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    SolicitudDescanso,
)
from pos_uniformes.services import descansos_service as ds

CODES = ("TST-DA", "TST-DB")


class PedidosAlMismoTiempoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._limpiar()
        with get_session() as s:
            for code in CODES:
                s.add(Empleada(codigo=code, nombre_completo=f"Prueba {code}", activo=True))
                s.add(EmpleadaHorario(employee_code=code, descanso_weekday=6))
            s.commit()
        self.hoy = date.today()
        dia = self.hoy + timedelta(days=9)
        while dia.weekday() != 2:   # un miércoles: ninguna de las dos descansa
            dia += timedelta(days=1)
        self.dia = dia
        # Solo ellas dos cuentan para el cupo: los horarios que haya en la
        # base de prueba no tienen por qué estorbar.
        from pos_uniformes.services.calendario_empleadas_service import cargar_horario

        self._parche = mock.patch.object(
            ds, "_horarios_frescos",
            lambda session, horarios=None: {c: cargar_horario(session, c) for c in CODES},
        )
        self._parche.start()

    def tearDown(self) -> None:
        self._parche.stop()
        self._limpiar()

    def _limpiar(self) -> None:
        with get_session() as s:
            ids = [i for (i,) in s.query(SolicitudDescanso.id).filter(
                SolicitudDescanso.employee_code.in_(CODES)).all()]
            s.execute(delete(EmpleadaEvento).where(EmpleadaEvento.employee_code.in_(CODES)))
            if ids:
                s.execute(delete(AuditoriaAusencias).where(AuditoriaAusencias.solicitud_id.in_(ids)))
            s.execute(delete(AuditoriaAusencias).where(AuditoriaAusencias.employee_code.in_(CODES)))
            s.execute(delete(SolicitudDescanso).where(SolicitudDescanso.employee_code.in_(CODES)))
            s.execute(delete(EmpleadaHorario).where(EmpleadaHorario.employee_code.in_(CODES)))
            s.execute(delete(Empleada).where(Empleada.codigo.in_(CODES)))
            s.commit()

    def test_solo_una_gana_el_dia(self) -> None:
        resultados: dict[str, str] = {}
        primera_adentro = threading.Event()

        def pedir(code: str, esperar_antes_de_confirmar: float) -> None:
            try:
                with get_session() as s:
                    ds.autoservicio(s, {}, code, self.dia, self.hoy)
                    primera_adentro.set()
                    time.sleep(esperar_antes_de_confirmar)
                    s.commit()
                resultados[code] = "ok"
            except ds.NoSePuede as exc:
                resultados[code] = f"no: {exc}"

        a = threading.Thread(target=pedir, args=("TST-DA", 0.8))
        a.start()
        self.assertTrue(primera_adentro.wait(5))
        b = threading.Thread(target=pedir, args=("TST-DB", 0))
        b.start()
        a.join(10)
        b.join(10)

        self.assertEqual(resultados["TST-DA"], "ok")
        self.assertTrue(resultados["TST-DB"].startswith("no:"), resultados)
        with get_session() as s:
            vivas = s.query(SolicitudDescanso).filter(
                SolicitudDescanso.employee_code.in_(CODES),
                SolicitudDescanso.estado == ds.APROBADO,
            ).count()
        self.assertEqual(vivas, 1)


if __name__ == "__main__":
    unittest.main()
