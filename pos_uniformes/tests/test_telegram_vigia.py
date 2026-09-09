"""Vigía del bot de Telegram: latido, decisión y arranque."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.scripts import telegram_bot as bot_mod
from pos_uniformes.scripts import telegram_bot_vigia as vigia


class DecidirTests(unittest.TestCase):
    def test_decision(self) -> None:
        self.assertEqual(vigia.decidir(fresco=True, reiniciar=False), "nada")
        self.assertEqual(vigia.decidir(fresco=False, reiniciar=False), "levantar")
        self.assertEqual(vigia.decidir(fresco=True, reiniciar=True), "reiniciar")


class LatidoTests(unittest.TestCase):
    def test_latir_y_frescura(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d, patch.object(bot_mod, "_base", return_value=Path(d)):
            self.assertFalse(bot_mod.latido_fresco())  # sin archivo
            bot_mod.latir()
            self.assertTrue(bot_mod.latido_fresco())
            import time

            self.assertFalse(bot_mod.latido_fresco(ahora=time.time() + 600))  # viejo


class MainTests(unittest.TestCase):
    def test_sin_token_no_hace_nada(self) -> None:
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value=""), patch.object(vigia, "levantar") as lev:
            self.assertEqual(vigia.main([]), 0)
        lev.assert_not_called()

    def test_bot_vivo_no_toca_nada(self) -> None:
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value="t"), patch(
            "pos_uniformes.services.telegram_service.chat_id_configurado", return_value="1"
        ), patch.object(bot_mod, "latido_fresco", return_value=True), patch.object(vigia, "levantar") as lev, patch.object(vigia, "matar") as mat:
            self.assertEqual(vigia.main([]), 0)
        lev.assert_not_called()
        mat.assert_not_called()

    def test_sin_latido_lo_levanta_y_reiniciar_lo_mata_antes(self) -> None:
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value="t"), patch(
            "pos_uniformes.services.telegram_service.chat_id_configurado", return_value="1"
        ), patch.object(bot_mod, "latido_fresco", return_value=False), patch.object(vigia, "levantar", return_value=42) as lev, patch.object(
            vigia, "matar"
        ) as mat, patch.object(vigia, "_pid_guardado", return_value=7), patch.object(vigia.time, "sleep"):
            self.assertEqual(vigia.main([]), 0)
            lev.assert_called_once()
            mat.assert_called_once_with(7)
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value="t"), patch(
            "pos_uniformes.services.telegram_service.chat_id_configurado", return_value="1"
        ), patch.object(bot_mod, "latido_fresco", return_value=True), patch.object(vigia, "levantar", return_value=43) as lev, patch.object(
            vigia, "matar"
        ) as mat, patch.object(vigia, "_pid_guardado", return_value=8), patch.object(vigia.time, "sleep"):
            self.assertEqual(vigia.main(["--reiniciar"]), 0)
            mat.assert_called_once_with(8)
            lev.assert_called_once()


class EscucharLatidoTests(unittest.TestCase):
    def test_escuchar_llama_on_tick(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        from pos_uniformes.services import telegram_bot_service as bot

        @contextmanager
        def _sesion():
            yield MagicMock()

        latidos = []
        with patch("pos_uniformes.services.telegram_service._llamar", return_value={"result": []}), patch(
            "pos_uniformes.services.telegram_service.enviar_mensaje"
        ):
            bot.escuchar(session_factory=_sesion, token="t", chat_id="1", una_vez=True, alertas=False, on_tick=lambda: latidos.append(1))
        self.assertEqual(latidos, [1])


if __name__ == "__main__":
    unittest.main()
