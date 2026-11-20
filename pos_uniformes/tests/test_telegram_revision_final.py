"""Últimos detalles de la revisión del bot (2026-11-20)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import corte_propuesta_service as prop
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_limpieza_service as limpieza
from pos_uniformes.services import telegram_service

HOY = date(2026, 11, 20)


class _Hoy(date):
    @classmethod
    def today(cls):
        return HOY


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        for p in (
            patch.object(prop, "ruta_estado", return_value=Path(d.name) / "corte_propuesto.json"),
            patch.object(limpieza, "ruta_estado", return_value=Path(d.name) / "bot_mensajes.json"),
            patch.object(prop, "date", _Hoy),
        ):
            p.start()
            self.addCleanup(p.stop)


class MenuDeUnaSolaLecturaTests(_Base):
    def test_si_la_segunda_lectura_falla_no_sale_otro_menu(self) -> None:
        limpieza.recordar_menu(10)
        with patch.object(limpieza, "menu_fijado", return_value=0), \
             patch.object(limpieza, "huella_del_menu", return_value=""), \
             patch("pos_uniformes.services.telegram_menu_service.menu_raiz", return_value=("📋 TIENDA", "{}")), \
             patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "_llamar") as llamar:
            mid = bot.asegurar_menu_fijado(session_factory=MagicMock(side_effect=RuntimeError), token="t", chat_id="1")
        self.assertEqual(mid, 10)
        editar.assert_called_once()
        self.assertNotIn("sendMessage", [c.args[1] for c in llamar.call_args_list])


class CorteSobreLaPropuestaViejaTests(_Base):
    def test_sin_red_el_corte_escrito_en_la_vieja_no_se_borra(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            prop.retirar_mensaje(HOY, salvo=777)
        prop.anotar_recordatorio(777)
        self.assertIn(501, prop.leer().viejos)
        borrados = []

        def _borrar(mid, **_k):
            borrados.append(mid)
            return "ok"

        with patch.object(telegram_service, "enviar_mensaje", side_effect=RuntimeError("Telegram respondió: Bad Gateway")), \
             patch.object(telegram_service, "editar_mensaje"), \
             patch.object(telegram_service, "borrar_con_motivo", side_effect=_borrar):
            bot._corte_hecho_en_un_mensaje(501, "🧾 CORTE HECHO", es_el_menu=False, token="t", chat_id="1")
        self.assertNotIn(501, borrados)


class PropuestaDeLaColaTests(_Base):
    def test_reconoce_la_propuesta_y_el_recordatorio(self) -> None:
        self.assertTrue(bot._es_propuesta_del_corte("🧾 ¿HACEMOS EL CORTE? · vie 20 nov", '{"x":"cc:ok"}'))
        self.assertTrue(bot._es_propuesta_del_corte("⏰ SIGUE PENDIENTE EL CORTE · vie 20 nov", '{"x":"cc:ok"}'))
        self.assertFalse(bot._es_propuesta_del_corte("🧾 CORTE HECHO · vie 20 nov", '{"x":"cc:ok"}'))
        self.assertFalse(bot._es_propuesta_del_corte("🧾 ¿HACEMOS EL CORTE?", ""))

    def test_adoptar_guarda_el_id_y_el_anterior_queda_para_quitar(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=0)
        self.assertTrue(prop.adoptar_mensaje(600))
        self.assertEqual(prop.leer().message_id, 600)
        self.assertTrue(prop.adoptar_mensaje(700))
        self.assertEqual(prop.leer().message_id, 700)
        self.assertIn(600, prop.leer().viejos)

    def test_no_adopta_si_la_propuesta_es_de_otro_dia(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 19, 17, 30), message_id=0)
        self.assertFalse(prop.adoptar_mensaje(600))


if __name__ == "__main__":
    unittest.main()
