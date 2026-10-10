"""Bot de Telegram: comandos, respuestas y que solo atienda al chat autorizado."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
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


class DosCantidadesTests(unittest.TestCase):
    def test_dos_cifras_sueltas_no_se_adivinan(self) -> None:
        """«/corte 5000 3000»: la segunda pisaba a la primera sin decir nada."""
        with self.assertRaises(ValueError) as ctx:
            bot.leer_opciones_corte("5000 3000")
        self.assertIn("dos cantidades", str(ctx.exception))
        self.assertEqual(bot.leer_opciones_corte("5000 deposité 2 cajas").retirar, Decimal("5000.00"))


class LeerCifraTests(unittest.TestCase):
    """«/corte 5000,50» retiraba medio millón: se borraban todas las comas
    (2026-10-10). Una sola regla para /corte, /retiro y /ajustar."""

    def test_miles_con_coma(self) -> None:
        self.assertEqual(bot.leer_cifra("$5,000"), Decimal("5000.00"))
        self.assertEqual(bot.leer_cifra("1,250,000.75"), Decimal("1250000.75"))

    def test_coma_decimal_a_la_mexicana(self) -> None:
        self.assertEqual(bot.leer_cifra("5000,50"), Decimal("5000.50"))
        self.assertEqual(bot.leer_cifra("500,5"), Decimal("500.50"))

    def test_lo_ambiguo_no_se_adivina(self) -> None:
        for raro in ("5,00,0", "1,5,5", "5,0000", "nan", "inf", "abc", ""):
            with self.subTest(raro=raro):
                self.assertIsNone(bot.leer_cifra(raro))

    def test_lo_de_siempre_sigue_igual(self) -> None:
        self.assertEqual(bot.leer_cifra("5000"), Decimal("5000.00"))
        self.assertEqual(bot.leer_cifra("5000.5"), Decimal("5000.50"))


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
        suelto = bot.atender_texto("hola", session_factory=_sesion)
        self.assertIn("No entendí", suelto)
        self.assertNotIn("/corte 5000", suelto)   # ya no manda la ayuda entera
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


class ArgumentosQueNoSeTragaTests(unittest.TestCase):
    """«/faltas 30» ignoraba el 30; «/contar Playera» y «/pagos Fanny»
    tragaban el argumento en silencio (2026-10-10)."""

    def test_faltas_con_dias(self) -> None:
        with patch("pos_uniformes.services.telegram_inventario_service.faltas", return_value="F") as faltas:
            self.assertEqual(bot.atender_texto("/faltas 30", session_factory=_sesion), "F")
        self.assertEqual(faltas.call_args.args[1], 30)
        self.assertIn("como días", bot.atender_texto("/faltas treinta", session_factory=_sesion))

    def test_lo_que_no_lleva_argumento_lo_dice(self) -> None:
        with patch("pos_uniformes.services.telegram_inventario_service.contar", return_value="C"):
            r = bot.atender_texto("/contar Playera", session_factory=_sesion)
        self.assertTrue(r.startswith("(/contar no lleva nada después"))
        self.assertTrue(r.endswith("C"))
        with patch("pos_uniformes.services.telegram_inventario_service.contar", return_value="C"):
            self.assertEqual(bot.atender_texto("/contar", session_factory=_sesion), "C")


class ComandoEnPieDeFotoTests(unittest.TestCase):
    def test_un_corte_en_el_pie_de_una_foto_no_se_ejecuta(self) -> None:
        """Por ese camino «/corte abc» se saltaba la pregunta anti-dedazo
        (2026-10-10)."""
        msg = {"caption": "/corte abc", "photo": [{"file_id": "f", "width": 10, "height": 10}]}
        with patch.object(bot, "atender_texto") as atender:
            r = bot.atender_foto(msg, session_factory=_sesion, token="t")
        atender.assert_not_called()
        self.assertIn("No atiendo «/corte»", r)


class BotonDesconocidoTests(unittest.TestCase):
    def test_un_boton_de_otra_version_lo_dice(self) -> None:
        toque = {"id": "q1", "data": "zz:nada", "message": {"chat": {"id": "123"}, "message_id": 5}}
        with patch("pos_uniformes.services.telegram_service.responder_toque") as responder, \
             patch("pos_uniformes.services.telegram_service.editar_mensaje"):
            bot._atender_toque(toque, session_factory=_sesion, token="t", chat_id="123")
        self.assertIn("No conozco ese botón", responder.call_args.args[1])


class MensajesEditadosTests(unittest.TestCase):
    def test_una_edicion_se_avisa_y_no_se_ejecuta(self) -> None:
        updates = {"result": [
            {"update_id": 7, "edited_message": {"chat": {"id": 123}, "text": "/corte 500", "date": 1}},
        ]}
        with patch("pos_uniformes.services.telegram_service._llamar", return_value=updates), \
             patch("pos_uniformes.services.telegram_service.enviar_mensaje") as enviar, \
             patch.object(bot, "atender_texto") as atender:
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        atender.assert_not_called()
        self.assertIn("editados", enviar.call_args.args[0])
        self.assertEqual(bot._leer_offset(), 8)


class OtroBotConElMismoTokenTests(unittest.TestCase):
    def test_un_409_no_cuenta_como_apagon(self) -> None:
        """Dos bots con el mismo token (uno en la Mac) daban 409 en
        getUpdates y se contaba como «sin internet»: mensajes «Volví a tener
        línea» falsos (2026-10-10)."""
        from pos_uniformes.services import bot_conexion_service as conexion

        with patch("pos_uniformes.services.telegram_service._llamar",
                   side_effect=RuntimeError("Telegram respondió: Conflict: terminated by other getUpdates request")), \
             patch.object(conexion, "anotar_fallo") as fallo, patch.object(bot.time, "sleep"):
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        fallo.assert_not_called()

    def test_un_error_de_red_si_cuenta(self) -> None:
        from pos_uniformes.services import bot_conexion_service as conexion

        with patch("pos_uniformes.services.telegram_service._llamar", side_effect=OSError("sin red")), \
             patch.object(conexion, "anotar_fallo") as fallo, patch.object(bot.time, "sleep"):
            bot.escuchar(session_factory=_sesion, token="t", chat_id="123", una_vez=True, alertas=False)
        fallo.assert_called_once()


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
