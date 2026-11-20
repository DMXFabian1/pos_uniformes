"""Formato común del bot (2026-11-20): los mensajes que arman el bot y su
menú empiezan con un encabezado (emoji, TÍTULO, fecha). Nada sale a Telegram."""

from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_menu_service as menu
from pos_uniformes.services.telegram_formato import es_encabezado


@contextmanager
def _sesion():
    yield object()


def _primera(texto: str) -> str:
    return texto.splitlines()[0]


class AyudaTests(unittest.TestCase):
    def test_la_ayuda_corta_empieza_con_encabezado_y_manda_al_menu(self) -> None:
        self.assertTrue(es_encabezado(_primera(bot.AYUDA)))
        self.assertIn("/menu", bot.AYUDA)
        self.assertLess(len(bot.AYUDA), len(bot.AYUDA_COMPLETA) / 2)

    def test_la_completa_tambien_y_sale_con_todo(self) -> None:
        self.assertTrue(es_encabezado(_primera(bot.AYUDA_COMPLETA)))
        r = bot.atender_texto("/ayuda todo", session_factory=_sesion)
        self.assertEqual(r, bot.AYUDA_COMPLETA)

    def test_la_ayuda_lleva_los_botones_del_tablero(self) -> None:
        texto, botones = bot.responder("/ayuda", session_factory=_sesion)
        self.assertEqual(texto, bot.AYUDA)
        datos = {b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila}
        self.assertIn("m:pagos", datos)

    def test_los_comandos_que_no_salen_en_la_corta_se_siguen_reconociendo(self) -> None:
        self.assertIn("/mepagaron", bot.comando_desconocido("mepagron"))


class ComandosMenuTests(unittest.TestCase):
    def test_son_los_doce_de_diario(self) -> None:
        self.assertEqual(
            [c for c, _ in bot.COMANDOS_MENU],
            ["menu", "hoy", "estado", "corte", "nocorte", "resumen", "pagos", "mipago",
             "retiro", "prenda", "pendientes", "ayuda"],
        )


class TextosDelBotTests(unittest.TestCase):
    def test_sin_pendientes(self) -> None:
        with patch("pos_uniformes.services.resumen_diario_service.texto_solo_pendientes", return_value=""):
            r = bot.atender_texto("/pendientes", session_factory=_sesion, hoy=date(2026, 11, 20))
        self.assertEqual(_primera(r), "📝 PENDIENTES · vie 20 nov")

    def test_nocorte(self) -> None:
        with patch("pos_uniformes.services.corte_propuesta_service.cancelar", return_value=True):
            r = bot.atender_texto("/nocorte", session_factory=_sesion, hoy=date(2026, 11, 20))
        self.assertEqual(_primera(r), "🧾 SIN CORTE HOY · vie 20 nov")
        self.assertIn("no se hace el corte", r)

    def test_la_nota_de_argumento_va_al_pie(self) -> None:
        with patch("pos_uniformes.services.telegram_inventario_service.contar", return_value="🏪 QUÉ CONTAR\nx"):
            r = bot.atender_texto("/contar Playera", session_factory=_sesion)
        self.assertTrue(es_encabezado(_primera(r)))

    def test_aviso_de_otro_bot(self) -> None:
        c = bot._Conflicto()
        c.otro(1_000_000)
        self.assertTrue(es_encabezado(_primera(c.otro(1_000_200))))


class MenuTests(unittest.TestCase):
    def test_tablero_sin_base(self) -> None:
        texto, _ = menu.menu_raiz()
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertTrue(_primera(texto).startswith("📋 TIENDA · "))

    def test_tablero_con_el_dia_lleva_un_solo_encabezado(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        dia = rd.DatosResumen(fecha=date(2026, 11, 20))
        with patch.object(rd, "recolectar", return_value=dia), \
             patch("pos_uniformes.services.asistencia_service.asistencia_del_dia", return_value=[]), \
             patch("pos_uniformes.services.telegram_mi_pago_service.aviso", return_value=""):
            texto = menu.cabecera(object(), hoy=date(2026, 11, 20))
        lineas = texto.splitlines()
        self.assertTrue(lineas[0].startswith("📋 TIENDA · vie 20 nov"))
        self.assertFalse(any(es_encabezado(l) for l in lineas[1:]), texto)
        self.assertNotIn("📅", texto)            # el de texto_hoy se quitó
        self.assertTrue(texto.endswith("¿Qué quieres ver?"))

    def test_las_muchachas(self) -> None:
        _, texto, _b = menu.atender("m:gente", session_factory=None)
        self.assertTrue(es_encabezado(_primera(texto)))


if __name__ == "__main__":
    unittest.main()
