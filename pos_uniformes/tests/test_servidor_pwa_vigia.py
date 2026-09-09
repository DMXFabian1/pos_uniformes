"""Vigía del servidor de la PWA: decisión, arranque y reinicio."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.scripts import servidor_pwa_vigia as vigia


class DecidirTests(unittest.TestCase):
    def test_decision(self) -> None:
        self.assertEqual(vigia.decidir(vivo=True, reiniciar=False), "nada")
        self.assertEqual(vigia.decidir(vivo=False, reiniciar=False), "levantar")
        self.assertEqual(vigia.decidir(vivo=True, reiniciar=True), "reiniciar")


class ComandoTests(unittest.TestCase):
    def test_levanta_uvicorn_en_la_lan(self) -> None:
        cmd = vigia.comando()
        self.assertIn("uvicorn", cmd)
        self.assertIn("pos_uniformes.api.main:app", cmd)
        # Los celulares entran por la IP de la PC: no puede ser solo localhost.
        self.assertEqual(cmd[cmd.index("--host") + 1], "0.0.0.0")
        self.assertEqual(cmd[cmd.index("--port") + 1], str(vigia.PUERTO))


class MainTests(unittest.TestCase):
    def test_servidor_vivo_no_toca_nada(self) -> None:
        with patch.object(vigia, "responde", return_value=True), patch.object(
            vigia, "levantar"
        ) as lev, patch.object(vigia, "matar") as mat:
            self.assertEqual(vigia.main([]), 0)
        lev.assert_not_called()
        mat.assert_not_called()

    def test_caido_lo_levanta_matando_lo_pegado(self) -> None:
        with patch.object(vigia, "responde", side_effect=[False, True]), patch.object(
            vigia, "levantar", return_value=42
        ) as lev, patch.object(vigia, "matar") as mat, patch.object(
            vigia, "_pid_guardado", return_value=7
        ), patch.object(vigia.time, "sleep"):
            self.assertEqual(vigia.main([]), 0)
        mat.assert_called_once_with(7)
        lev.assert_called_once()

    def test_reiniciar_lo_relanza_aunque_este_vivo(self) -> None:
        with patch.object(vigia, "responde", return_value=True), patch.object(
            vigia, "levantar", return_value=43
        ) as lev, patch.object(vigia, "matar") as mat, patch.object(
            vigia, "_pid_guardado", return_value=8
        ), patch.object(vigia.time, "sleep"):
            self.assertEqual(vigia.main(["--reiniciar"]), 0)
        mat.assert_called_once_with(8)
        lev.assert_called_once()


class RespondeTests(unittest.TestCase):
    def test_sin_servidor_es_falso(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("no hay nadie")):
            self.assertFalse(vigia.responde(timeout=0.1))


if __name__ == "__main__":
    unittest.main()
