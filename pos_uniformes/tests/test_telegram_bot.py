"""Bot de Telegram: comandos, respuestas y que solo atienda al chat autorizado."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services.corte_remoto_service import ResultadoCorte


@contextmanager
def _sesion():
    yield MagicMock()


class ParsearTests(unittest.TestCase):
    def test_comandos(self) -> None:
        self.assertEqual(bot.parsear("/corte"), bot.Comando("corte"))
        self.assertEqual(bot.parsear("  /Estado@mi_bot  "), bot.Comando("estado"))
        self.assertEqual(bot.parsear("/resumen 2026-09-07"), bot.Comando("resumen", "2026-09-07"))
        self.assertIsNone(bot.parsear("hola"))


class AtenderTests(unittest.TestCase):
    def test_corte(self) -> None:
        with patch("pos_uniformes.services.corte_remoto_service.hacer_corte_y_avisar",
                   return_value=ResultadoCorte(True, "🧾 Corte hecho", True)) as hacer:
            r = bot.atender_texto("/corte", session_factory=_sesion)
        self.assertEqual(r, "🧾 Corte hecho")
        self.assertEqual(hacer.call_args.kwargs["creado_por"], "VEND-1")

    def test_estado_resumen_pendientes_ayuda(self) -> None:
        with patch("pos_uniformes.services.corte_remoto_service.texto_estado_actual", return_value="💰 Caja"):
            self.assertEqual(bot.atender_texto("/estado", session_factory=_sesion), "💰 Caja")
        with patch("pos_uniformes.services.resumen_diario_service.recolectar", return_value="D"), patch(
            "pos_uniformes.services.resumen_diario_service.formatear", return_value="📒 R"
        ):
            self.assertEqual(bot.atender_texto("/resumen", session_factory=_sesion, hoy=date(2026, 9, 8)), "📒 R")
        with patch("pos_uniformes.services.resumen_diario_service.texto_solo_pendientes", return_value=""):
            self.assertEqual(bot.atender_texto("/pendientes", session_factory=_sesion), "Sin pendientes. ✅")
        self.assertIn("/corte", bot.atender_texto("/ayuda", session_factory=_sesion))
        self.assertIn("No entendí", bot.atender_texto("hola", session_factory=_sesion))
        self.assertIn("No conozco /x", bot.atender_texto("/x", session_factory=_sesion))


class EscucharTests(unittest.TestCase):
    def test_solo_atiende_al_chat_autorizado(self) -> None:
        updates = {"result": [
            {"update_id": 1, "message": {"chat": {"id": 999}, "text": "/corte"}},   # intruso
            {"update_id": 2, "message": {"chat": {"id": 123}, "text": "/ayuda"}},   # Daniel
        ]}
        with patch("pos_uniformes.services.telegram_service._llamar", return_value=updates), patch(
            "pos_uniformes.services.telegram_service.enviar_mensaje"
        ) as enviar, patch.object(bot, "atender_texto", wraps=bot.atender_texto) as atender:
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        self.assertEqual(atender.call_count, 1)
        self.assertEqual(atender.call_args.args[0], "/ayuda")
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.kwargs["chat_id"], "123")

    def test_mensajes_viejos_no_se_ejecutan(self) -> None:
        import time

        viejo = int(time.time()) - 3600
        updates = {"result": [
            {"update_id": 1, "message": {"chat": {"id": 123}, "text": "/corte", "date": viejo}},
            {"update_id": 2, "message": {"chat": {"id": 123}, "text": "hola", "date": viejo}},
            {"update_id": 3, "message": {"chat": {"id": 123}, "text": "/ayuda", "date": int(time.time())}},
        ]}
        with patch("pos_uniformes.services.telegram_service._llamar", return_value=updates), patch(
            "pos_uniformes.services.telegram_service.enviar_mensaje"
        ) as enviar, patch.object(bot, "atender_texto", wraps=bot.atender_texto) as atender:
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        self.assertEqual(atender.call_count, 1)
        self.assertEqual(atender.call_args.args[0], "/ayuda")
        textos = [c.args[0] for c in enviar.call_args_list]
        self.assertEqual(len(textos), 2)  # aviso del /corte viejo + respuesta de /ayuda; el "hola" viejo, nada
        self.assertIn("No atendí «/corte»", textos[0])


class ElOffsetSobreviveAlReinicioTests(unittest.TestCase):
    """El offset vivía solo en memoria: tras un reinicio Telegram reenviaba el
    último lote y un /retiro o un botón se ejecutaba dos veces (2026-10-10)."""

    def test_lo_atendido_queda_en_disco_y_el_siguiente_arranque_lo_salta(self) -> None:
        import time

        updates = {"result": [
            {"update_id": 41, "message": {"chat": {"id": 123}, "text": "/ayuda", "date": int(time.time())}},
            {"update_id": 42, "callback_query": {"id": "q", "data": "x:nada",
                                                 "message": {"chat": {"id": 123}}}},
        ]}
        llamadas = []

        def falso_llamar(token, metodo, datos=None, timeout=None):
            llamadas.append((metodo, dict(datos or {})))
            return updates if metodo == "getUpdates" else {"ok": True}

        with patch("pos_uniformes.services.telegram_service._llamar", side_effect=falso_llamar), \
             patch("pos_uniformes.services.telegram_service.enviar_mensaje"):
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        self.assertEqual(bot._leer_offset(), 43)
        primera = next(d for m, d in llamadas if m == "getUpdates")
        self.assertNotIn("offset", primera)          # primer arranque: sin memoria

        llamadas.clear()
        updates["result"] = []
        with patch("pos_uniformes.services.telegram_service._llamar", side_effect=falso_llamar), \
             patch("pos_uniformes.services.telegram_service.enviar_mensaje"):
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        segunda = next(d for m, d in llamadas if m == "getUpdates")
        self.assertEqual(segunda.get("offset"), 43)  # «reiniciado»: no pide lo ya atendido

    def test_una_memoria_rota_arranca_como_antes(self) -> None:
        bot.ruta_offset().parent.mkdir(parents=True, exist_ok=True)
        bot.ruta_offset().write_text("{nada", encoding="utf-8")
        self.assertIsNone(bot._leer_offset())


if __name__ == "__main__":
    unittest.main()
