"""Vacaciones desde Telegram: aprobar, rechazar con motivo, primas e ingreso.

Contra una base de verdad (SQLite): los botones viejos no deciden nada y la
prima no se marca pagada dos veces.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CajaParametros,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    SolicitudVacaciones,
)
from pos_uniformes.services import telegram_vacaciones_service as tv
from pos_uniformes.services import vacaciones_service as vs


def _con_autoservicio(session, code, **kw):
    """Expediente + autoservicio abierto: estas pruebas son de ella pidiendo."""
    exp = vs.capturar_expediente(session, code, **kw)
    vs.habilitar_autoservicio(session, code, True, quien="VEND-1")
    return exp


class TelegramVacacionesTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        hoy = date.today()
        with self.factory() as s:
            s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
            s.add(CajaParametros(sueldo_base=Decimal("1300")))
            s.commit()
            _con_autoservicio(s, "VEND-5", fecha_ingreso=hoy - timedelta(days=800), quien="VEND-1")
            vs.generar_periodos(s, "VEND-5", hoy=hoy)
            sol = vs.pedir(s, employee_code="VEND-5", nombre="Cristal Torres",
                           desde=hoy + timedelta(days=20), hasta=hoy + timedelta(days=26), hoy=hoy)
            s.commit()
            self.sid = sol.id

    def _estado(self):
        with self.factory() as s:
            return s.get(SolicitudVacaciones, self.sid).estado

    def _vacaciones_en_calendario(self):
        with self.factory() as s:
            return s.query(EmpleadaEvento).filter(EmpleadaEvento.tipo == "vacaciones").count()

    def test_el_detalle_trae_saldo_ley_y_quien_falta(self) -> None:
        with self.factory() as s:
            texto, filas = tv.detalle(s, self.sid)
        self.assertIn("disponibles", texto)
        self.assertIn("art. 81", texto)
        self.assertIn("también faltan", texto.replace("no falta nadie más", "también faltan"))
        self.assertTrue(filas)

    def test_aprobar_y_un_boton_viejo_no_hace_nada(self) -> None:
        aviso, texto, _b = tv.atender(f"vc:ok:{self.sid}", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(aviso, "Aprobado")
        self.assertIn("Prima pendiente", texto)
        n = self._vacaciones_en_calendario()
        aviso, _t, _b = tv.atender(f"vc:no:{self.sid}", session_factory=self.factory, quien="VEND-1")
        self.assertIn("ya está aprobado", aviso)
        self.assertEqual((self._estado(), self._vacaciones_en_calendario()), (vs.APROBADO, n))

    def test_rechazar_con_motivo(self) -> None:
        with self.factory() as s:
            texto = tv.comando(s, f"no {self.sid} temporada alta", quien="VEND-1")
        self.assertIn("temporada alta", texto)
        with self.factory() as s:
            self.assertEqual(s.get(SolicitudVacaciones, self.sid).respuesta, "temporada alta")

    def test_la_prima_se_marca_pagada_una_vez(self) -> None:
        tv.atender(f"vc:ok:{self.sid}", session_factory=self.factory, quien="VEND-1")
        with self.factory() as s:
            texto, botones = tv.primas(s)
            [p] = vs.primas_pendientes(s)
        self.assertIn("vc:pp:", botones)
        self.assertEqual(tv.atender(f"vc:pp:{p.id}", session_factory=self.factory, quien="VEND-1")[0], "Pagada")
        aviso, _t, _b = tv.atender(f"vc:pp:{p.id}", session_factory=self.factory, quien="VEND-1")
        self.assertIn("ya está pagada", aviso)

    def test_ingreso_por_telegram(self) -> None:
        with self.factory() as s:
            s.add(Empleada(codigo="VEND-4", nombre_completo="Stayce Ruiz", activo=True))
            s.commit()
            texto = tv.ingreso(s, "Stayce 2023-01-15", quien="VEND-1")
        self.assertIn("VEND-4", texto)
        with self.factory() as s:
            self.assertTrue(vs.expediente(s, "VEND-4").completo)
            self.assertIn("AAAA-MM-DD", tv.ingreso(s, "Stayce 15/01/2023", quien="VEND-1"))


class OrigenDelDiaTests(unittest.TestCase):
    def test_dice_de_donde_sale_cada_dia(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            aplicar_solicitud_descanso, cargar_horarios_todos, origen_del_dia,
        )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        s = sessionmaker(bind=engine)()
        s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
        s.commit()
        hoy = date(2026, 10, 5)
        aplicar_solicitud_descanso(s, cargar_horarios_todos(s), "VEND-5", date(2026, 10, 14), hoy)
        self.assertIn("cambio de descanso", origen_del_dia(s, "VEND-5", date(2026, 10, 14)))
        self.assertIn("las reglas del Calendario", origen_del_dia(s, "VEND-5", date(2026, 10, 18)))
        self.assertIn("descanso fijo", origen_del_dia(s, "VEND-5", date(2026, 10, 25)))
        self.assertIn("día normal", origen_del_dia(s, "VEND-5", date(2026, 10, 20)))
        s.close()


if __name__ == "__main__":
    unittest.main()
