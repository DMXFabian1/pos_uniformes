"""Cambiar el descanso fijo solo afecta de ahí en adelante.

Stayce pidió pasar su descanso de sábado a lunes (2026-11-05). El sistema solo
guardaba «descansa el sábado», sin fecha: al cambiarlo, todos los sábados
pasados se volvían días trabajados y todos los lunes pasados, descansos.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EmpleadaDescansoAnterior, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.services import calendario_empleadas_service as cal
from pos_uniformes.services.calendario_empleadas_service import DESCANSO, TRABAJO, HorarioEmpleada

SABADO, LUNES, MIERCOLES = 5, 0, 2
CAMBIO = date(2026, 11, 9)              # lunes: desde aquí descansa en lunes


class DescansoFijoEnTests(unittest.TestCase):
    def test_sin_cambios_es_el_de_siempre(self) -> None:
        h = HorarioEmpleada(employee_code="VEND-4", descanso_weekday=SABADO)
        self.assertEqual(h.descanso_fijo_en(date(2020, 1, 4)), SABADO)
        self.assertIsNone(h.descanso_desde)

    def test_antes_del_cambio_vale_el_anterior(self) -> None:
        h = HorarioEmpleada(employee_code="VEND-4", descanso_weekday=LUNES,
                            descansos_anteriores=[(CAMBIO - timedelta(days=1), SABADO)])
        self.assertEqual(cal.estado_del_dia(h, date(2026, 10, 31)), DESCANSO)     # sábado de antes: sigue siendo descanso
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 2)), TRABAJO)       # lunes de antes: trabajó
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 7)), DESCANSO)      # el último sábado
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 9)), DESCANSO)      # el primer lunes
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 14)), TRABAJO)      # sábado ya trabaja
        self.assertEqual(h.descanso_desde, CAMBIO)
        self.assertEqual(cal.proximo_descanso(h, date(2026, 11, 5)), date(2026, 11, 7))
        self.assertEqual(cal.proximo_descanso(h, date(2026, 11, 7)), date(2026, 11, 9))

    def test_los_dias_de_mas_se_cuentan_con_el_descanso_de_esa_fecha(self) -> None:
        # Trabajó el sábado 31-oct, que ENTONCES era su descanso: un día de más.
        h = HorarioEmpleada(employee_code="VEND-4", descanso_weekday=LUNES,
                            descansos_anteriores=[(CAMBIO - timedelta(days=1), SABADO)],
                            eventos={date(2026, 10, 31): TRABAJO})
        self.assertEqual(cal.dias_extra_en_rango(h, date(2026, 10, 26), date(2026, 11, 1)), 1)
        # Con el descanso de hoy (lunes) aplicado a toda la historia, ese sábado no contaba.
        sin_historia = HorarioEmpleada(employee_code="VEND-4", descanso_weekday=LUNES, eventos={date(2026, 10, 31): TRABAJO})
        self.assertEqual(cal.dias_extra_en_rango(sin_historia, date(2026, 10, 26), date(2026, 11, 1)), 0)


class GuardarConFechaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=SABADO, fecha_ultimo_pago=date(2026, 11, 1)))
        self.s.add(EmpleadaEvento(employee_code="VEND-4", fecha=date(2026, 10, 31), tipo="trabajo"))
        self.s.commit()

    def test_el_cambio_guarda_el_anterior_y_el_pasado_no_se_mueve(self) -> None:
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=LUNES, ciclo_dias_pago=7, descanso_desde=CAMBIO, creado_por="VEND-1")
        fila = self.s.query(EmpleadaDescansoAnterior).one()
        self.assertEqual((fila.employee_code, fila.weekday, fila.hasta, fila.creado_por), ("VEND-4", SABADO, date(2026, 11, 8), "VEND-1"))
        h = cal.cargar_horario(self.s, "VEND-4")
        self.assertEqual(h.descanso_weekday, LUNES)
        self.assertEqual(cal.estado_del_dia(h, date(2026, 10, 24)), DESCANSO)
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 16)), DESCANSO)
        self.assertEqual(cal.estado_del_dia(h, date(2026, 11, 21)), TRABAJO)
        self.assertEqual(self.s.get(EmpleadaHorario, "VEND-4").fecha_ultimo_pago, date(2026, 11, 1))   # lo demás, intacto

    def test_dos_cambios_seguidos(self) -> None:
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=LUNES, ciclo_dias_pago=7, descanso_desde=CAMBIO)
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=MIERCOLES, ciclo_dias_pago=7, descanso_desde=date(2026, 12, 7))
        h = cal.cargar_horario(self.s, "VEND-4")
        self.assertEqual([h.descanso_fijo_en(d) for d in (date(2026, 11, 1), date(2026, 11, 20), date(2026, 12, 20))],
                         [SABADO, LUNES, MIERCOLES])

    def test_un_cambio_no_puede_empezar_antes_del_anterior(self) -> None:
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=LUNES, ciclo_dias_pago=7, descanso_desde=CAMBIO)
        with self.assertRaisesRegex(ValueError, "tiene que empezar después"):
            cal.guardar_horario(self.s, "VEND-4", descanso_weekday=MIERCOLES, ciclo_dias_pago=7, descanso_desde=date(2026, 11, 2))

    def test_sin_fecha_corrige_toda_la_historia_como_antes(self) -> None:
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=LUNES, ciclo_dias_pago=7)
        self.assertEqual(self.s.query(EmpleadaDescansoAnterior).count(), 0)
        h = cal.cargar_horario(self.s, "VEND-4")
        self.assertEqual(cal.estado_del_dia(h, date(2026, 10, 24)), TRABAJO)

    def test_guardar_sin_cambiar_el_dia_no_deja_rastro(self) -> None:
        cal.guardar_horario(self.s, "VEND-4", descanso_weekday=SABADO, ciclo_dias_pago=14, descanso_desde=CAMBIO)
        self.assertEqual(self.s.query(EmpleadaDescansoAnterior).count(), 0)


if __name__ == "__main__":
    unittest.main()
