"""Lista de asistencia para el bot: presencia deducida del primer movimiento."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    ConteoJornada,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    LibretaVenta,
)
from pos_uniformes.services import asistencia_service as asis
from pos_uniformes.services.calendario_empleadas_service import FALTA, guardar_horario, marcar_dia

HOY = date(2026, 9, 12)   # sábado


def _emp(s, code, nombre, *, descanso=None, activo=True):
    s.add(Empleada(codigo=code, nombre_completo=nombre, activo=activo))
    s.flush()
    if descanso is not None:
        guardar_horario(s, code, descanso_weekday=descanso, ciclo_dias_pago=7)


def _venta(s, code, hora: str, nombre="x"):
    h, m = map(int, hora.split(":"))
    s.add(LibretaVenta(
        employee_code=code, employee_name=nombre, tipo="venta", piezas=1,
        monto_total=Decimal("100"), monto_neto=Decimal("100"),
        created_at=datetime(HOY.year, HOY.month, HOY.day, h, m).astimezone(),
    ))
    s.commit()


class ClasificarTests(unittest.TestCase):
    def test_falta_y_descanso_mandan_sobre_la_actividad(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import DESCANSO, TRABAJO

        self.assertEqual(asis.clasificar(estado_dia=FALTA, movimientos=3, primera=None), asis.FALTA)
        self.assertEqual(asis.clasificar(estado_dia=DESCANSO, movimientos=0, primera=None), asis.DESCANSO)
        self.assertEqual(asis.clasificar(estado_dia=TRABAJO, movimientos=0, primera=None), asis.SIN_SENAL)
        self.assertEqual(asis.clasificar(estado_dia=TRABAJO, movimientos=2, primera=None), asis.PRESENTE)
        self.assertEqual(asis.clasificar(estado_dia=TRABAJO, movimientos=0, primera=datetime.now()), asis.PRESENTE)


class AsistenciaDelDiaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        s = self.s
        _emp(s, "VEND-2", "Fanny Ortiz", descanso=0)           # descansa lunes; hoy sábado trabaja
        _emp(s, "VEND-3", "Cristal Torres", descanso=1)
        _emp(s, "VEND-4", "Stayce Chavarria", descanso=5)      # descansa sábado = hoy
        _emp(s, "VEND-5", "Evelyn Ortiz", descanso=2)
        _emp(s, "VEND-6", "Katherine Posada", descanso=3)
        _emp(s, "VEND-9", "Lupita", descanso=4, activo=False)  # baja: no aparece
        _emp(s, "VEND-1", "Daniel", descanso=None)             # dueño: no aparece
        s.commit()
        _venta(s, "VEND-2", "09:40")
        _venta(s, "VEND-2", "10:15")
        _venta(s, "VEND-3", "09:12")
        marcar_dia(s, "VEND-5", HOY, FALTA, nota="apuntado por León")
        # Katherine no vendió, pero abrió un conteo: cuenta como presencia.
        s.add(ConteoJornada(
            escuela_id=None, tipo_pieza="Camisa", titulo="Básicos · Camisa",
            empleada_code="VEND-6", empleada_nombre="Katherine Posada", total_tallas=10,
            iniciada_at=datetime(HOY.year, HOY.month, HOY.day, 10, 5).astimezone(),
        ))
        s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def test_clasifica_a_todas_y_solo_a_las_activas_del_equipo(self) -> None:
        lista = asis.asistencia_del_dia(self.s, HOY)
        por_code = {a.code: a for a in lista}
        self.assertEqual(set(por_code), {"VEND-2", "VEND-3", "VEND-4", "VEND-5", "VEND-6"})
        self.assertEqual(por_code["VEND-2"].estado, asis.PRESENTE)
        self.assertEqual(por_code["VEND-2"].movimientos, 2)
        self.assertEqual(por_code["VEND-2"].primera_senal.strftime("%H:%M"), "09:40")
        self.assertEqual(por_code["VEND-3"].estado, asis.PRESENTE)
        self.assertEqual(por_code["VEND-4"].estado, asis.DESCANSO)
        self.assertEqual(por_code["VEND-5"].estado, asis.FALTA)
        self.assertEqual(por_code["VEND-5"].nota, "apuntado por León")   # la nota del calendario, tal cual
        self.assertEqual(por_code["VEND-6"].estado, asis.PRESENTE)   # por el conteo
        self.assertEqual(por_code["VEND-6"].primera_senal.strftime("%H:%M"), "10:05")

    def test_van_primero_las_presentes_por_hora_de_llegada(self) -> None:
        lista = asis.asistencia_del_dia(self.s, HOY)
        self.assertEqual([a.nombre_corto for a in lista][:3], ["Cristal", "Fanny", "Katherine"])
        self.assertEqual(lista[-1].estado, asis.DESCANSO)

    def test_el_mensaje_se_lee_de_un_vistazo(self) -> None:
        texto = asis.texto_asistencia(asis.asistencia_del_dia(self.s, HOY), HOY, datetime(2026, 9, 12, 11, 0))
        self.assertIn("👥 Asistencia · sáb 12/09 · 11:00", texto)
        self.assertIn("✅ Cristal — desde 09:12 · 1 mov.", texto)
        self.assertIn("✅ Fanny — desde 09:40 · 2 mov.", texto)
        self.assertIn("✅ Katherine — desde 10:05", texto)
        self.assertIn("✗ Evelyn — falta (apuntado por León)", texto)
        self.assertIn("🛌 Stayce — descansa", texto)
        self.assertIn("5 activas · 3 presentes · 1 descanso · 1 falta", texto)

    def test_sin_movimientos_dice_sin_senal_no_falta(self) -> None:
        """Una que no ha vendido puede estar en el piso: no se le cuelga la falta."""
        s = self.s
        _emp(s, "VEND-7", "Nayeli Herrera", descanso=6)
        s.commit()
        lista = {a.code: a for a in asis.asistencia_del_dia(s, HOY)}
        self.assertEqual(lista["VEND-7"].estado, asis.SIN_SENAL)
        texto = asis.texto_asistencia(list(lista.values()), HOY)
        self.assertIn("⏳ Nayeli — sin movimientos todavía", texto)
        self.assertIn("1 sin señal", texto)

    def test_sin_equipo_no_truena(self) -> None:
        self.assertIn("No hay empleadas activas", asis.texto_asistencia([], HOY))


class BotTests(unittest.TestCase):
    def test_el_bot_conoce_el_comando(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.assertIn("/asistencia", bot.AYUDA)
        self.assertEqual(bot.parsear("/asistencia").nombre, "asistencia")


if __name__ == "__main__":
    unittest.main()


class DanielTieneLaUltimaPalabraTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        _emp(self.s, "VEND-2", "Fanny Ortiz", descanso=0)
        _emp(self.s, "VEND-3", "Cristal Torres", descanso=1)
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def test_vino_sin_haber_vendido_cuenta_como_presente(self) -> None:
        self.assertEqual(asis.marcar(self.s, "VEND-2", asis.VINO, HOY), "Fanny: vino ✅")
        lista = {a.code: a for a in asis.asistencia_del_dia(self.s, HOY)}
        self.assertEqual(lista["VEND-2"].estado, asis.PRESENTE)
        self.assertTrue(lista["VEND-2"].confirmado)
        self.assertEqual(lista["VEND-2"].nota, "tú")
        self.assertIn("✅ Fanny — vino (tú)", asis.texto_asistencia(list(lista.values()), HOY))

    def test_falta_manda_aunque_haya_vendido(self) -> None:
        """Si Daniel dice que faltó, faltó: la venta pudo ser con otro gafete."""
        _venta(self.s, "VEND-3", "09:30")
        asis.marcar(self.s, "VEND-3", asis.NO_VINO, HOY)
        lista = {a.code: a for a in asis.asistencia_del_dia(self.s, HOY)}
        self.assertEqual(lista["VEND-3"].estado, asis.FALTA)
        self.assertIn("✗ Cristal — falta (tú)", asis.texto_asistencia(list(lista.values()), HOY))

    def test_se_puede_cambiar_de_opinion(self) -> None:
        asis.marcar(self.s, "VEND-2", asis.NO_VINO, HOY)
        asis.marcar(self.s, "VEND-2", asis.VINO, HOY)
        lista = {a.code: a for a in asis.asistencia_del_dia(self.s, HOY)}
        self.assertEqual(lista["VEND-2"].estado, asis.PRESENTE)

    def test_gafete_desconocido_no_truena(self) -> None:
        self.assertIn("No conozco", asis.marcar(self.s, "VEND-99", asis.VINO, HOY))

    def test_buscar_por_nombre(self) -> None:
        self.assertEqual(asis.buscar_code(self.s, "fanny"), "VEND-2")
        self.assertEqual(asis.buscar_code(self.s, "Cris"), "VEND-3")
        self.assertEqual(asis.buscar_code(self.s, "vend-2"), "VEND-2")
        self.assertIsNone(asis.buscar_code(self.s, "zzz"))
        self.assertIsNone(asis.buscar_code(self.s, ""))

    def test_el_teclado_lleva_una_fila_por_empleada_con_marca(self) -> None:
        asis.marcar(self.s, "VEND-2", asis.VINO, HOY)
        filas = asis.teclado_asistencia(asis.asistencia_del_dia(self.s, HOY))
        self.assertEqual(len(filas), 2)
        textos = {b[0] for fila in filas for b in fila}
        self.assertIn("✅ Fanny vino", textos)       # marcada
        self.assertIn("☐ Cristal vino", textos)     # sin marcar
        datos = {b[1] for fila in filas for b in fila}
        self.assertIn("asis:VEND-2:vino", datos)
        self.assertIn("asis:VEND-3:falta", datos)
        self.assertTrue(all(len(d) <= 64 for d in datos))

    def test_interpretar_toque(self) -> None:
        self.assertEqual(asis.interpretar_toque("asis:VEND-4:vino"), ("VEND-4", "vino"))
        self.assertEqual(asis.interpretar_toque("asis:vend-4:falta"), ("VEND-4", "falta"))
        self.assertIsNone(asis.interpretar_toque("otra:cosa"))
        self.assertIsNone(asis.interpretar_toque("asis:VEND-4:explotar"))
        self.assertIsNone(asis.interpretar_toque(""))


class BotConBotonesTests(unittest.TestCase):
    """El ciclo completo con un Telegram falso: toque → marca → misma lista editada."""

    def setUp(self) -> None:
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        with self.factory() as s:
            _emp(s, "VEND-2", "Fanny Ortiz", descanso=0)
            s.commit()

    def test_texto_vino_marca_y_devuelve_la_lista(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        r = bot.atender_texto("/vino Fanny", session_factory=self.factory, hoy=HOY)
        self.assertTrue(r.startswith("Fanny: vino ✅"))
        self.assertIn("👥 Asistencia", r)
        self.assertIn("✅ Fanny — vino (tú)", r)

    def test_texto_sin_nombre_pide_el_nombre(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.assertIn("¿Quién?", bot.atender_texto("/falta", session_factory=self.factory, hoy=HOY))

    def test_el_toque_marca_y_edita_el_mismo_mensaje(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        llamadas = []
        with patch.object(telegram_service, "_llamar", side_effect=lambda t, m, d=None, **k: llamadas.append((m, d)) or {"ok": True}):
            bot._atender_toque(
                {"id": "77", "data": "asis:VEND-2:falta", "message": {"message_id": 501, "chat": {"id": 123}}},
                session_factory=self.factory, token="tok", chat_id="123",
            )
        metodos = [m for m, _ in llamadas]
        self.assertEqual(metodos, ["answerCallbackQuery", "editMessageText"])
        self.assertEqual(llamadas[0][1]["text"], "Fanny: falta ✗")
        editado = llamadas[1][1]
        self.assertEqual(editado["message_id"], "501")
        self.assertIn("✗ Fanny — falta (tú)", editado["text"])
        self.assertIn("inline_keyboard", editado["reply_markup"])

    def test_un_toque_de_otro_chat_se_ignora(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "_llamar") as llamar:
            bot._atender_toque(
                {"id": "1", "data": "asis:VEND-2:vino", "message": {"message_id": 1, "chat": {"id": 999}}},
                session_factory=self.factory, token="tok", chat_id="123",
            )
        llamar.assert_not_called()
        with self.factory() as s:
            self.assertEqual(asis.asistencia_del_dia(s, HOY)[0].confirmado, False)

    def test_el_teclado_json_tiene_la_forma_que_telegram_espera(self) -> None:
        import json

        from pos_uniformes.services.telegram_service import teclado

        j = json.loads(teclado([[("a", "x:1"), ("b", "x:2")], [("c", "y" * 100)]]))
        self.assertEqual(j["inline_keyboard"][0][0], {"text": "a", "callback_data": "x:1"})
        self.assertEqual(len(j["inline_keyboard"][1][0]["callback_data"]), 64)
