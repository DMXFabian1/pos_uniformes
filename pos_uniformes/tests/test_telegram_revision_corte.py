"""Revisión 2026-11-20 del corte en UN mensaje: lo que quedaba suelto.

#1  un sendMessage que tarda (ReadTimeout) ya salió: no se encola otra vez.
#7  el mensaje reescrito con el corte deja de ser la propuesta: un segundo
    corte no lo borra.
#8  sin red, el mensaje tocado que dice el corte deja de ser la pantalla y
    se conserva; si ni eso, a la cola.
#9  el aviso de un corte del kiosko/PWA, al salir de la cola, quita la
    propuesta.
#10 la tarea sin token encola el aviso; el recordatorio se quita solo si el
    aviso salió o quedó en la cola.
#11 una propuesta que no se pudo borrar no se pierde al llegar el recordatorio.
#17 solo se conserva la respuesta de un /corte que sí se hizo.

Nada manda mensajes de verdad ni escribe en pos_uniformes/data.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from urllib3.exceptions import ReadTimeoutError

from pos_uniformes.scripts import corte_automatico as script
from pos_uniformes.services import alertas_service
from pos_uniformes.services import corte_caja_service
from pos_uniformes.services import corte_propuesta_service as prop
from pos_uniformes.services import corte_remoto_service
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_limpieza_service as limpieza
from pos_uniformes.services import telegram_service
from pos_uniformes.services.corte_remoto_service import ResultadoCorte

HOY = date(2026, 11, 20)


def _tardo() -> ReadTimeoutError:
    return ReadTimeoutError(None, "https://api.telegram.org", "Read timed out.")


class _Hoy(date):
    @classmethod
    def today(cls):
        return HOY


@contextmanager
def _sesion():
    yield MagicMock()


class _ConEstado(unittest.TestCase):
    def setUp(self) -> None:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        for p in (
            patch.object(prop, "ruta_estado", return_value=self.dir / "corte_propuesto.json"),
            patch.object(limpieza, "ruta_estado", return_value=self.dir / "bot_mensajes.json"),
            patch.object(prop, "date", _Hoy),
        ):
            p.start()
            self.addCleanup(p.stop)


# ── #1 ───────────────────────────────────────────────────────────────────────
class TimeoutNoSeEncolaTests(unittest.TestCase):
    def _con_token(self):
        return (patch.object(telegram_service, "token_configurado", return_value=True),
                patch.object(telegram_service, "chat_id_configurado", return_value=True))

    def test_la_propuesta_que_tardo_no_se_manda_dos_veces(self) -> None:
        a, b = self._con_token()
        with a, b, patch.object(telegram_service, "enviar_y_dar_id", side_effect=_tardo()), \
             patch.object(script, "_encolar") as encolar:
            self.assertEqual(script._mandar_y_dar_id("¿Hacemos el corte?", "{}"), 0)
        encolar.assert_not_called()

    def test_un_aviso_que_tardo_no_se_encola(self) -> None:
        a, b = self._con_token()
        with a, b, patch.object(telegram_service, "enviar_mensaje", side_effect=_tardo()), \
             patch.object(script, "_encolar") as encolar:
            self.assertTrue(script._mandar("🌙 Cerré el día"))
        encolar.assert_not_called()

    def test_sin_red_si_se_encola(self) -> None:
        a, b = self._con_token()
        with a, b, patch.object(telegram_service, "enviar_y_dar_id", side_effect=OSError("sin red")), \
             patch.object(script, "_encolar", return_value=True) as encolar:
            self.assertEqual(script._mandar_y_dar_id("¿Corte?", "{}"), 0)
        encolar.assert_called_once()


# ── #7 ───────────────────────────────────────────────────────────────────────
class SegundoCorteNoBorraElPrimeroTests(_ConEstado):
    def test_el_mensaje_del_primer_corte_se_queda(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "editar_mensaje"), \
             patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            bot._corte_hecho_en_un_mensaje(501, "🧾 Corte hecho", es_el_menu=False,
                                           token="t", chat_id="1")
            self.assertEqual(prop.mensaje_de_hoy(), 0)
            bot._retirar_propuesta_del_corte()        # el segundo corte (/corte segundo)
        self.assertNotIn(501, [c.args[0] for c in borrar.call_args_list])

    def test_si_no_se_pudo_reescribir_va_a_la_cola(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "editar_mensaje", side_effect=OSError("sin red")), \
             patch.object(bot, "_encolar_aviso_del_corte") as encolar:
            bot._corte_hecho_en_un_mensaje(501, "🧾 Corte hecho", es_el_menu=False,
                                           token="t", chat_id="1")
        encolar.assert_called_once_with("🧾 Corte hecho")
        self.assertEqual(prop.mensaje_de_hoy(), 501)   # la quita el aviso al salir


# ── #8 ───────────────────────────────────────────────────────────────────────
class SinRedLaPantallaNoSePisaTests(_ConEstado):
    def test_deja_de_ser_pantalla_y_se_conserva(self) -> None:
        limpieza.anotar(900)
        limpieza.recordar_pantalla(900, date.today().isoformat())
        with patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "borrar_con_motivo", return_value="red"), \
             patch.object(bot, "_encolar_aviso_del_corte") as encolar:
            bot._corte_hecho_en_un_mensaje(900, "🧾 Corte hecho", es_el_menu=False,
                                           token="t", chat_id="1")
        editar.assert_called_once()
        encolar.assert_not_called()                     # ya se ve en el chat: sin duplicado
        self.assertEqual(limpieza.pantalla()[0], 0)
        datos = json.loads((self.dir / "bot_mensajes.json").read_text(encoding="utf-8"))
        apunte = [m for m in datos["mensajes"] if m["id"] == 900]
        self.assertTrue(apunte and apunte[0].get("conservar"))

    def test_desde_el_menu_sin_red_va_a_la_cola(self) -> None:
        with patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(bot, "_encolar_aviso_del_corte") as encolar:
            bot._corte_hecho_en_un_mensaje(10, "🧾 Corte hecho", es_el_menu=True,
                                           token="t", chat_id="1")
        editar.assert_not_called()
        encolar.assert_called_once_with("🧾 Corte hecho")


# ── #9 ───────────────────────────────────────────────────────────────────────
class CorteDelKioskoQuitaLaPropuestaTests(_ConEstado):
    def _mandar_cola(self, texto: str, creada: datetime):
        alerta = SimpleNamespace(id=1, texto=texto, botones=None, created_at=creada,
                                 intentos=0, enviado_at=None)
        enviados = []
        with patch.object(alertas_service, "pendientes", return_value=[alerta]), \
             patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            alertas_service.enviar_pendientes(MagicMock(), enviados.append,
                                              ahora=creada)
        return enviados, borrar

    def test_el_aviso_del_corte_quita_la_propuesta(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        enviados, borrar = self._mandar_cola("🧾 CORTE DE CAJA · vie 20 nov · 18:00\n💰 $1.00",
                                             datetime(2026, 11, 20, 18, 0))
        self.assertEqual(len(enviados), 1)
        borrar.assert_called_once_with(501)
        self.assertEqual(prop.mensaje_de_hoy(), 0)

    def test_un_corte_de_antes_de_la_propuesta_no_la_toca(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        _, borrar = self._mandar_cola("🧾 CORTE DE CAJA · vie 20 nov · 12:00",
                                      datetime(2026, 11, 20, 12, 0))
        borrar.assert_not_called()

    def test_otro_aviso_no_la_toca(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        _, borrar = self._mandar_cola("💸 RETIRO DEL CAJÓN · vie 20 nov · 18:00",
                                      datetime(2026, 11, 20, 18, 0))
        borrar.assert_not_called()


# ── #10 ──────────────────────────────────────────────────────────────────────
class CierreSinTokenTests(unittest.TestCase):
    def test_sin_token_se_encola(self) -> None:
        with patch.object(telegram_service, "token_configurado", return_value=False), \
             patch.object(telegram_service, "chat_id_configurado", return_value=True), \
             patch.object(telegram_service, "enviar_mensaje") as enviar, \
             patch.object(script, "_encolar", return_value=True) as encolar:
            self.assertTrue(script._mandar("🌙 Cerré el día por ti"))
        enviar.assert_not_called()
        encolar.assert_called_once_with("🌙 Cerré el día por ti", None)

    def _cerrar(self, mandado: bool):
        estado = MagicMock()
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
             patch.object(corte_caja_service, "estado_caja", return_value=estado), \
             patch.object(corte_caja_service, "ultimo_corte", return_value=None), \
             patch.object(prop, "leer", return_value=prop.Propuesta()), \
             patch.object(prop, "toca_cerrar_solo", return_value=True), \
             patch.object(corte_remoto_service, "hacer_corte_y_avisar",
                          return_value=ResultadoCorte(True, "🧾 Corte hecho")), \
             patch.object(script, "_mandar", return_value=mandado), \
             patch.object(prop, "retirar_mensaje") as retirar:
            self.assertEqual(script._cerrar_si_nadie_contesto(), 0)
        return retirar

    def test_si_el_aviso_no_quedo_en_ningun_lado_el_recordatorio_se_queda(self) -> None:
        self._cerrar(False).assert_not_called()

    def test_si_el_aviso_salio_se_quita_el_recordatorio(self) -> None:
        self._cerrar(True).assert_called_once()


# ── #11 ──────────────────────────────────────────────────────────────────────
class PropuestaSinBorrarNoSePierdeTests(_ConEstado):
    def test_el_recordatorio_no_pisa_la_propuesta_sin_borrar(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            prop.retirar_mensaje(HOY, salvo=777)
        prop.anotar_recordatorio(777)
        self.assertEqual(prop.leer().message_id, 777)
        self.assertEqual(prop.leer().viejos, (501,))
        with patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            prop.retirar_mensaje(HOY)          # el corte
        self.assertEqual(sorted(c.args[0] for c in borrar.call_args_list), [501, 777])
        self.assertEqual(prop.leer().viejos, ())
        self.assertEqual(prop.leer().message_id, 0)

    def test_si_se_borro_no_queda_pendiente(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="ok"):
            prop.retirar_mensaje(HOY, salvo=777)
        prop.anotar_recordatorio(777)
        self.assertEqual(prop.leer().viejos, ())


# ── #17 ──────────────────────────────────────────────────────────────────────
class SoloSeConservaElCorteHechoTests(unittest.TestCase):
    def _corte(self, resultado: ResultadoCorte, argumento: str = "") -> str:
        with patch.object(corte_remoto_service, "hacer_corte_y_avisar", return_value=resultado), \
             patch.object(bot, "_retirar_propuesta_del_corte"):
            return bot.atender_texto("/corte" + argumento, session_factory=_sesion)

    def test_un_error_va_a_la_pantalla(self) -> None:
        r = self._corte(ResultadoCorte(False, "No hay tanto en el cajón… vuelve a mandar /corte"), " 99999")
        self.assertFalse(bot._conservar_respuesta("/corte 99999", r))

    def test_el_corte_hecho_se_conserva(self) -> None:
        r = self._corte(ResultadoCorte(True, "🧾 CORTE HECHO · vie 20 nov · 18:00"))
        self.assertTrue(bot._conservar_respuesta("/corte", r))
        self.assertIn("CORTE HECHO", r)

    def test_otra_consulta_no_se_conserva(self) -> None:
        self.assertFalse(bot._conservar_respuesta("/caja", bot.CorteHecho("x")))

    def test_si_no_sale_va_a_la_cola(self) -> None:
        with patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(bot, "_encolar_aviso_del_corte") as encolar:
            bot._mandar_corte_hecho(bot.CorteHecho("🧾 Corte hecho"), token="t", chat_id="1")
        encolar.assert_called_once()

    def test_si_tardo_no_se_encola(self) -> None:
        with patch.object(telegram_service, "enviar_mensaje", side_effect=_tardo()), \
             patch.object(bot, "_encolar_aviso_del_corte") as encolar:
            bot._mandar_corte_hecho(bot.CorteHecho("🧾 Corte hecho"), token="t", chat_id="1")
        encolar.assert_not_called()

    def test_encolar_usa_la_cola_de_alertas(self) -> None:
        with patch.object(alertas_service, "encolar", return_value=True) as encolar:
            self.assertTrue(bot._encolar_aviso_del_corte("🧾 Corte hecho", session_factory=_sesion))
        self.assertEqual(encolar.call_args.args[1], "🧾 Corte hecho")


if __name__ == "__main__":
    unittest.main()
