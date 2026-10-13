"""El receso de Daniel en el calendario (2026-10-13): «solo sí dejar mi
periodo vacacional claro». Vacaciones como módulo sigue en construcción."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.services import calendario_empleadas_service as cal
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_menu_service as menu
from pos_uniformes.services import vacaciones_service as vs

_MARTES = 1


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.F = sessionmaker(bind=engine)
        with self.F() as s:
            s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel", activo=True))
            s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-1", descanso_weekday=_MARTES))
            s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
            s.commit()


class RecesoEnElCalendarioTests(_Base):
    def test_marca_un_dia_por_fecha_y_su_martes_deja_de_contar_en_el_cupo(self) -> None:
        with self.F() as s:
            n = cal.marcar_receso(s, "VEND-1", date(2026, 10, 27), date(2026, 11, 4), actor="VEND-1")
            self.assertEqual(n, 9)
            horarios = {c: cal.cargar_horario(s, c) for c in ("VEND-1", "VEND-5")}
        martes = date(2026, 10, 27)
        self.assertEqual(cal.estado_del_dia(horarios["VEND-1"], martes), cal.VACACIONES)
        # El martes 27 ya no lo ocupa Daniel: Cristal puede pedirlo.
        self.assertEqual(cal.quienes_descansan(horarios, martes), [])
        # Fuera del receso su martes sigue siendo descanso.
        self.assertEqual(cal.quienes_descansan(horarios, date(2026, 11, 10)), ["VEND-1"])

    def test_volver_a_marcar_reemplaza_y_quitar_borra_solo_el_receso(self) -> None:
        with self.F() as s:
            cal.marcar_receso(s, "VEND-1", date(2026, 10, 27), date(2026, 11, 4))
            cal.marcar_dia(s, "VEND-1", date(2026, 12, 1), cal.FALTA, nota="otra cosa")
            cal.marcar_receso(s, "VEND-1", date(2026, 10, 28), date(2026, 10, 30))
            self.assertEqual(cal.receso_de(s, "VEND-1"), [date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30)])
            self.assertEqual(cal.quitar_receso(s, "VEND-1"), 3)
            self.assertEqual(cal.receso_de(s, "VEND-1"), [])
            # La falta de diciembre no era del receso: se queda.
            self.assertEqual(s.query(EmpleadaEvento).filter_by(tipo=cal.FALTA).count(), 1)

    def test_el_mes_pintado_dice_que_esta_de_vacaciones(self) -> None:
        with self.F() as s:
            cal.marcar_receso(s, "VEND-1", date(2026, 10, 27), date(2026, 11, 4))
            mes = cal.chips_calendario_mes(s, 2026, 10, date(2026, 10, 13))
        textos = [t for _tipo, t in mes.get(date(2026, 10, 28), [])]
        self.assertTrue(any("vacaciones" in t for t in textos), textos)


class ComandoRecesoTests(_Base):
    def test_apunta_enseña_y_quita(self) -> None:
        r = bot.atender_texto("/receso 2026-10-27 2026-11-04", session_factory=self.F, hoy=date(2026, 10, 13))
        self.assertIn("27/10/2026", r)
        self.assertIn("04/11/2026", r)
        self.assertIn("empieza en 14 días", r)
        r = bot.atender_texto("/receso", session_factory=self.F, hoy=date(2026, 10, 30))
        self.assertIn("va corriendo", r)
        self.assertIn("quité tu receso (9 días)", bot.atender_texto("/receso quitar", session_factory=self.F))
        self.assertIn("No tienes receso", bot.atender_texto("/receso", session_factory=self.F))

    def test_fechas_malas_se_explican(self) -> None:
        self.assertIn("Así:", bot.atender_texto("/receso mañana", session_factory=self.F))
        self.assertIn("No entendí", bot.atender_texto("/receso 27-10 04-11", session_factory=self.F))
        self.assertIn("después", bot.atender_texto("/receso 2026-11-04 2026-10-27", session_factory=self.F))
        self.assertIn("60 días", bot.atender_texto("/receso 2026-01-01 2026-12-31", session_factory=self.F))
        with self.F() as s:
            self.assertEqual(cal.receso_de(s, "VEND-1"), [])

    def test_esta_en_la_ayuda(self) -> None:
        self.assertIn("/receso 2026-10-27 2026-11-04", bot.AYUDA)


class VacacionesEnConstruccionTests(_Base):
    """Mientras `EN_CONSTRUCCION` sea True, nada de vacaciones se ofrece."""

    def test_la_bandera_esta_puesta(self) -> None:
        self.assertTrue(vs.EN_CONSTRUCCION)

    def test_los_comandos_contestan_en_construccion(self) -> None:
        for texto in ("/vacaciones", "/vacaciones no 1 x", "/primas", "/ingreso Cristal 2024-01-01"):
            with self.subTest(texto=texto):
                self.assertEqual(bot.atender_texto(texto, session_factory=self.F), vs.EN_CONSTRUCCION_TEXTO)
        self.assertEqual(bot.responder("/vacaciones", session_factory=self.F), (vs.EN_CONSTRUCCION_TEXTO, ""))
        self.assertNotIn("/vacaciones", bot.AYUDA)
        self.assertNotIn("/primas", bot.AYUDA)

    def test_los_botones_viejos_contestan_en_construccion(self) -> None:
        from pos_uniformes.services import telegram_vacaciones_service as tv

        r = bot.atender_toque(f"{tv.PREFIJO}ok:1", session_factory=self.F)
        self.assertEqual(r[0], vs.EN_CONSTRUCCION_TEXTO)

    def test_el_menu_no_lo_ofrece(self) -> None:
        self.assertNotIn("m:vacaciones", {d for fila in menu._gente() for _, d in fila})
        _, texto, botones = menu.atender("m:vacaciones", session_factory=self.F)
        self.assertEqual(texto, vs.EN_CONSTRUCCION_TEXTO)
        self.assertEqual(botones, "")

    def test_al_estrenarlo_todo_vuelve(self) -> None:
        with patch.object(vs, "EN_CONSTRUCCION", False):
            self.assertIn("m:vacaciones", {d for fila in menu._gente() for _, d in fila})
            with patch("pos_uniformes.services.telegram_vacaciones_service.primas", return_value=("P", "")):
                self.assertEqual(bot.atender_texto("/primas", session_factory=self.F), "P")


if __name__ == "__main__":
    unittest.main()
