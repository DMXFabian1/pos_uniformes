"""Auditoría del bot 2026-11-07, sección 4 (robustez): 33, 34, 35."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_service as tg
from pos_uniformes.utils import archivo_atomico


class ArchivoAtomicoTests(unittest.TestCase):
    """#33: un JSON de estado a medias dejaba el offset roto y el bot volvía
    a ejecutar los toques del último lote."""

    def test_escribe_y_no_deja_temporales(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "sub" / "bot_offset.json"
            archivo_atomico.escribir_json(ruta, {"offset": 5})
            archivo_atomico.escribir_json(ruta, {"offset": 6})
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), {"offset": 6})
            self.assertEqual([p.name for p in ruta.parent.iterdir()], ["bot_offset.json"])

    def test_si_falla_a_media_escritura_el_de_antes_sigue_entero(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "bot_offset.json"
            archivo_atomico.escribir_json(ruta, {"offset": 5})
            with patch("os.fsync", side_effect=OSError("disco")), self.assertRaises(OSError):
                archivo_atomico.escribir_json(ruta, {"offset": 6})
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), {"offset": 5})
            self.assertEqual(len(list(Path(d).iterdir())), 1)

    def test_el_offset_usa_la_escritura_atomica(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(bot, "ruta_offset", return_value=Path(d) / "o.json"), \
                patch.object(archivo_atomico, "escribir_texto", wraps=archivo_atomico.escribir_texto) as esc:
            bot._guardar_offset(41)
            self.assertEqual(bot._leer_offset(), 41)
        esc.assert_called_once()

    def test_nadie_escribe_estado_del_bot_con_write_text(self):
        base = Path(__file__).resolve().parent.parent
        for rel in ("services/telegram_bot_service.py", "services/telegram_limpieza_service.py",
                    "services/telegram_corte_botones_service.py", "services/alertas_service.py",
                    "services/bot_conexion_service.py", "scripts/resumen_diario_telegram.py"):
            fuente = (base / rel).read_text(encoding="utf-8")
            self.assertNotIn("write_text(json.dumps", fuente, rel)
            self.assertNotIn("ruta.write_text(\n", fuente, rel)


class SinDobleEnvioTests(unittest.TestCase):
    """#34: un timeout esperando la respuesta repetía el POST por urllib."""

    def setUp(self):
        tg.soltar_pool()

    def tearDown(self):
        tg.soltar_pool()

    def _pool_que_falla(self, exc):
        pool = MagicMock()
        pool.request.side_effect = exc
        return pool

    def test_timeout_de_lectura_no_repite_el_mensaje(self):
        from urllib3.exceptions import ReadTimeoutError

        pool = self._pool_que_falla(ReadTimeoutError(None, "/sendMessage", "lento"))
        with patch.object(tg, "_obtener_pool", return_value=pool), \
                patch("urllib.request.urlopen") as urlopen, self.assertRaises(ReadTimeoutError):
            tg._pedir("https://x/sendMessage", b"text=hola", 5, True)
        urlopen.assert_not_called()
        self.assertEqual(pool.request.call_count, 1)

    def test_conexion_vieja_cerrada_si_se_repite(self):
        """La red de seguridad sigue para lo que no llegó a salir."""
        from urllib3.exceptions import ProtocolError

        pool = self._pool_que_falla(ProtocolError("Connection aborted"))
        resp = MagicMock()
        resp.__enter__.return_value.read.return_value = b'{"ok": true}'
        with patch.object(tg, "_obtener_pool", return_value=pool), \
                patch("urllib.request.urlopen", return_value=resp) as urlopen:
            self.assertEqual(tg._pedir("https://x/sendMessage", b"text=hola", 5, True), '{"ok": true}')
        urlopen.assert_called_once()

    def test_un_get_lento_si_se_repite(self):
        from urllib3.exceptions import ReadTimeoutError

        pool = self._pool_que_falla(ReadTimeoutError(None, "/getMe", "lento"))
        resp = MagicMock()
        resp.__enter__.return_value.read.return_value = b"{}"
        with patch.object(tg, "_obtener_pool", return_value=pool), \
                patch("urllib.request.urlopen", return_value=resp) as urlopen:
            tg._pedir("https://x/getMe", None, 5, True)
        urlopen.assert_called_once()


class LimpiezaYMenuTests(unittest.TestCase):
    """#35: si fallaba la limpieza el menú no se refrescaba; editar cortaba callado."""

    def test_si_falla_la_limpieza_el_menu_igual_se_refresca(self):
        with patch.object(tg, "_llamar", return_value={"result": []}), \
                patch.object(bot, "asegurar_menu_fijado"), \
                patch.object(bot, "limpiar_si_toca", side_effect=RuntimeError("borrar")), \
                patch.object(bot, "refrescar_menu_si_toca") as refrescar:
            bot.escuchar(session_factory=MagicMock(), token="t", chat_id="1", una_vez=True, alertas=False)
        refrescar.assert_called_once()

    def test_editar_un_texto_largo_dice_que_se_corto(self):
        largo = "renglón\n" * 1000
        with patch.object(tg, "_llamar") as llamar:
            tg.editar_mensaje(9, largo, token="t", chat_id="1")
        texto = llamar.call_args.args[2]["text"]
        self.assertLessEqual(len(texto), 4096)
        self.assertTrue(texto.endswith(tg.AVISO_RECORTADO))

    def test_uno_corto_queda_igual(self):
        self.assertEqual(tg.recortar_para_editar("hola"), "hola")


if __name__ == "__main__":
    unittest.main()
