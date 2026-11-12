"""El aviso breve de la barra de escaneo del kiosko muere con su widget.

`QuickSaleWidget._flash_scan_hint` programaba `QTimer.singleShot(1800,
lambda: …)` sin dueño Qt. Si el kiosko se destruía antes de los 1.8 s, la
lambda caía sobre la etiqueta ya borrada y PyQt6 tumbaba el proceso
(RuntimeError en un slot → Fatal Python error: Aborted). En la suite pasaba
1 de cada 4-5 corridas con -n 6. Desde 2026-11-12 el timer es hijo del widget.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

# Se cierran, pero no se destruyen a media corrida.
_VIVOS: list = []


class AvisoDeEscaneoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
        _VIVOS.append(self.w)
        self.addCleanup(self.w.close)

    def test_el_aviso_se_va_solo_y_el_timer_es_del_widget(self) -> None:
        self.w._flash_scan_hint("Agregado")
        self.assertEqual(self.w._scan_hint.text(), "Agregado")
        timer = self.w._scan_hint_timer
        self.assertIs(timer.parent(), self.w)  # muere con el widget
        self.assertTrue(timer.isSingleShot())
        self.assertTrue(timer.isActive())
        disparos = QSignalSpy(timer.timeout)
        self.assertTrue(disparos.wait(5_000), "el aviso nunca se quitó")
        self.assertEqual(self.w._scan_hint.text(), QuickSaleWidget._SCAN_HINT_DEFAULT)
        self.assertFalse(timer.isActive())

    def test_un_aviso_nuevo_reinicia_la_cuenta_con_el_mismo_timer(self) -> None:
        self.w._flash_scan_hint("Agregado")
        timer = self.w._scan_hint_timer
        time.sleep(QuickSaleWidget._SCAN_HINT_MS * 0.6 / 1000)  # el ciclo no corre
        antes = timer.remainingTime()
        self.w._flash_scan_hint("Gafete ignorado")
        self.assertIs(self.w._scan_hint_timer, timer)
        self.assertGreater(timer.remainingTime(), antes)
        self.assertEqual(self.w._scan_hint.text(), "Gafete ignorado")

    def test_borrar_el_kiosko_con_el_aviso_pendiente_no_tumba_el_proceso(self) -> None:
        """En un pytest aparte: si vuelve el error, aborta ese proceso, no este."""
        aqui = Path(__file__).resolve().parent.parent
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PYTEST_XDIST") and k != "PYTEST_CURRENT_TEST"}
        env["QT_QPA_PLATFORM"] = "offscreen"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/_ayuda_aviso_borrado.py",
             "-p", "no:xdist", "-p", "no:cacheprovider", "-q"],
            cwd=aqui, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
        )
        salida = r.stdout + r.stderr
        self.assertNotIn("Fatal Python error", salida)
        self.assertNotIn("has been deleted", salida)
        self.assertEqual(r.returncode, 0, salida[-3000:])
        self.assertIn("2 passed", r.stdout)


if __name__ == "__main__":
    unittest.main()
