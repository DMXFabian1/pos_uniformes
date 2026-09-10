"""Supervisor único (bot + PWA): decisión, vuelta, bandera de reinicio."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.scripts import supervisor as sup


class DecidirTests(unittest.TestCase):
    def test_decision(self) -> None:
        self.assertEqual(sup.decidir(vivo=True, ultimo_arranque=0, ahora=1000), "nada")
        self.assertEqual(sup.decidir(vivo=False, ultimo_arranque=0, ahora=1000), "levantar")
        self.assertEqual(sup.decidir(vivo=False, ultimo_arranque=950, ahora=1000), "esperar")  # acaba de arrancar


class VueltaTests(unittest.TestCase):
    def _servicio(self, nombre, vivo):
        acciones = []
        s = sup.Servicio(nombre, vivo=lambda: vivo, levantar=lambda: acciones.append("levantar"), reiniciar=lambda: acciones.append("reiniciar"))
        return s, acciones

    def test_levanta_solo_al_caido_y_con_calma(self) -> None:
        bot, a_bot = self._servicio("bot", vivo=False)
        pwa, a_pwa = self._servicio("pwa", vivo=True)
        self.assertEqual(sup.vuelta([bot, pwa], ahora=1000), ["bot: levantado"])
        self.assertEqual(a_bot, ["levantar"])
        self.assertEqual(a_pwa, [])
        self.assertEqual(sup.vuelta([bot, pwa], ahora=1030), [])          # calma de 3 min
        self.assertEqual(sup.vuelta([bot, pwa], ahora=1300), ["bot: levantado"])

    def test_reiniciar_todo(self) -> None:
        bot, a_bot = self._servicio("bot", vivo=True)
        self.assertEqual(sup.vuelta([bot], ahora=1000, reiniciar_todo=True), ["bot: reiniciado"])
        self.assertEqual(a_bot, ["reiniciar"])

    def test_error_de_un_servicio_no_tumba_la_vuelta(self) -> None:
        def _truena():
            raise RuntimeError("x")

        malo = sup.Servicio("malo", vivo=lambda: False, levantar=_truena, reiniciar=_truena)
        bueno, _a = self._servicio("bueno", vivo=False)
        hechos = sup.vuelta([malo, bueno], ahora=1000)
        self.assertTrue(hechos[0].startswith("malo: error"))
        self.assertEqual(hechos[1], "bueno: levantado")


class BanderaTests(unittest.TestCase):
    def test_pedir_y_consumir(self) -> None:
        with tempfile.TemporaryDirectory() as d, patch.object(sup, "_base", return_value=Path(d)):
            self.assertFalse(sup.hay_bandera())
            sup.pedir_reinicio()
            self.assertTrue(sup.hay_bandera())
            self.assertFalse(sup.hay_bandera())  # se consume una sola vez

    def test_main_pedir_reinicio(self) -> None:
        with tempfile.TemporaryDirectory() as d, patch.object(sup, "_base", return_value=Path(d)):
            self.assertEqual(sup.main(["--pedir-reinicio"]), 0)
            self.assertTrue(sup.ruta_bandera().exists())


class ServiciosRealesTests(unittest.TestCase):
    def test_sin_token_solo_pwa(self) -> None:
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value=""):
            self.assertEqual([s.nombre for s in sup.servicios_reales()], ["PWA"])

    def test_con_token_bot_y_pwa(self) -> None:
        with patch("pos_uniformes.services.telegram_service.token_configurado", return_value="t"), patch(
            "pos_uniformes.services.telegram_service.chat_id_configurado", return_value="1"
        ):
            self.assertEqual([s.nombre for s in sup.servicios_reales()], ["Telegram bot", "PWA"])


if __name__ == "__main__":
    unittest.main()
