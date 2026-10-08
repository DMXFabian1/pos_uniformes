"""El aviso de respaldo viejo trae su botón para hacerlo.

Daniel (2026-10-08): «el bot solo me avisa que no hay respaldo, en vez de
darme un botón para hacerlo». El aviso terminaba diciendo «en la tienda:
scripts\\respaldo_diario.bat», o sea «ve a la PC».
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_respaldo_service as rs


def _datos(botones: str) -> list[str]:
    return [b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


class ElAvisoTraeSuBotonTests(unittest.TestCase):
    def test_el_vigilante_lo_manda_con_botones(self) -> None:
        from datetime import datetime

        from pos_uniformes.services import alertas_service as al
        from pos_uniformes.services import respaldo_estado_service as est

        vig = al.Vigilante()
        viejo = MagicMock(al_dia=False)
        ahora = datetime(2026, 10, 8, 12, 0)
        with patch.object(est, "leer_estado", return_value=viejo), \
             patch.object(est, "texto_sin_respaldo", return_value="sin respaldo"):
            avisos = vig._respaldo_viejo(ahora)
        self.assertEqual(len(avisos), 1)
        texto, botones = avisos[0]
        self.assertEqual(texto, "sin respaldo")
        self.assertIn("rs:ahora", _datos(botones))

    def test_cuando_esta_al_dia_no_avisa_ni_ofrece_nada(self) -> None:
        from datetime import datetime

        from pos_uniformes.services import alertas_service as al
        from pos_uniformes.services import respaldo_estado_service as est

        with patch.object(est, "leer_estado", return_value=MagicMock(al_dia=True)):
            self.assertEqual(al.Vigilante()._respaldo_viejo(datetime(2026, 10, 8, 12, 0)), [])

    def test_la_cola_guarda_los_botones(self) -> None:
        """Si se perdieran al encolar, el aviso llegaría pelón."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import AlertaTelegram
        from pos_uniformes.services import alertas_service as al

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as ses:
            al.encolar(ses, "ojo", rs.botones_del_aviso())
            fila = ses.query(AlertaTelegram).one()
            self.assertIn("rs:ahora", _datos(fila.botones))

    def test_un_aviso_normal_no_guarda_teclado(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import AlertaTelegram
        from pos_uniformes.services import alertas_service as al

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as ses:
            al.encolar(ses, "solo aviso")
            self.assertIsNone(ses.query(AlertaTelegram).one().botones)

    def test_al_mandarla_van_los_botones(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import AlertaTelegram  # noqa: F401
        from pos_uniformes.services import alertas_service as al

        # Importar el modelo NO es de adorno: sin eso la tabla no está en el
        # metadata y `create_all` la deja fuera.
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        mandados = []
        with Session(engine) as ses:
            al.encolar(ses, "ojo", rs.botones_del_aviso())
            al.enviar_pendientes(ses, lambda t, b="": mandados.append((t, b)))
        self.assertEqual(len(mandados), 1)
        self.assertIn("rs:ahora", _datos(mandados[0][1]))


class TocarElBotonTests(unittest.TestCase):
    def test_contesta_al_instante_y_avisa_despues(self) -> None:
        """Telegram da unos segundos para contestar un toque, y un pg_dump
        tarda más: el botón se quedaría girando y el bot sordo."""
        hilos = []

        class _Hilo:
            def __init__(self, target=None, **kw):
                self.target = target
                hilos.append(self)

            def start(self):
                self.target()

        mandados = []
        with patch("threading.Thread", _Hilo), \
             patch.object(rs, "_correr_respaldo", return_value=(True, "✅ listo")):
            aviso, texto, _ = rs.atender("rs:ahora", enviar=mandados.append)

        self.assertEqual(aviso, "Haciendo el respaldo…")
        self.assertIn("Te aviso en cuanto termine", texto)
        self.assertEqual(mandados, ["✅ listo"])

    def test_el_resultado_llega_tambien_cuando_falla(self) -> None:
        """La tarea de siempre avisa solo si truena; aquí alguien apretó un
        botón y está esperando. El silencio no es éxito."""
        class _Hilo:
            def __init__(self, target=None, **kw):
                self.target = target

            def start(self):
                self.target()

        mandados = []
        with patch("threading.Thread", _Hilo), \
             patch.object(rs, "_correr_respaldo", return_value=(False, "🛑 no quedó")):
            rs.atender("rs:ahora", enviar=mandados.append)
        self.assertEqual(mandados, ["🛑 no quedó"])

    def test_si_el_respaldo_revienta_igual_contesta(self) -> None:
        class _Hilo:
            def __init__(self, target=None, **kw):
                self.target = target

            def start(self):
                self.target()

        mandados = []
        with patch("threading.Thread", _Hilo), \
             patch.object(rs, "_correr_respaldo", side_effect=OSError("boom")):
            rs.atender("rs:ahora", enviar=mandados.append)
        self.assertEqual(len(mandados), 1)
        self.assertIn("falló", mandados[0])

    def test_un_boton_que_no_conozco(self) -> None:
        self.assertEqual(
            rs.atender("rs:vete", enviar=lambda *_: None)[0], "No conozco ese botón"
        )

    def test_es_de_respaldo(self) -> None:
        self.assertTrue(rs.es_de_respaldo("rs:ahora"))
        self.assertFalse(rs.es_de_respaldo("m:cortes"))


class ElBotLoEnrutaTests(unittest.TestCase):
    def test_el_despachador_lo_conoce(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        with patch.object(rs, "atender", return_value=("ok", "", "")) as atender:
            bot.atender_toque("rs:ahora", session_factory=None, enviar=lambda *_: None)
        atender.assert_called_once()

    def test_sin_manera_de_avisar_lo_dice_en_vez_de_reventar(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        aviso, _, _ = bot.atender_toque("rs:ahora", session_factory=None)
        self.assertIn("No puedo", aviso)


if __name__ == "__main__":
    unittest.main()


class LosEnviadoresDeAntesSiguenSirviendoTests(unittest.TestCase):
    """Cambiar la firma a (texto, botones) rompía a todo el que reciba solo
    el texto. Los avisos sin teclado son casi todos."""

    def _cola(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import AlertaTelegram  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return Session(engine)

    def test_un_aviso_pelon_llega_con_un_solo_argumento(self) -> None:
        from pos_uniformes.services import alertas_service as al

        salidas = []
        with self._cola() as ses:
            al.encolar(ses, "solo aviso")
            al.enviar_pendientes(ses, salidas.append)   # recibe UN argumento
        self.assertEqual(salidas, ["solo aviso"])

    def test_uno_con_teclado_llega_con_los_dos(self) -> None:
        from pos_uniformes.services import alertas_service as al

        salidas = []
        with self._cola() as ses:
            al.encolar(ses, "ojo", rs.botones_del_aviso())
            al.enviar_pendientes(ses, lambda t, b: salidas.append((t, b)))
        self.assertEqual(len(salidas), 1)
        self.assertIn("rs:ahora", _datos(salidas[0][1]))
