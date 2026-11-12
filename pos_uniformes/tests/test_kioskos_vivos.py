"""El aviso breve de la barra de escaneo del kiosko y la vida de los kioskos.

`QuickSaleWidget._flash_scan_hint` programaba una lambda de 1.8 s sin dueño Qt.
Borrar el widget antes tumbaba el proceso en la siguiente prueba que corriera
el ciclo de eventos (1 de cada 4-5 corridas con -n 6; 2026-11-11). Desde
2026-11-12 el timer es hijo del widget y muere con él.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PyQt6 import sip
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget
from tests.conftest import _VENTANAS_SATELITE, conservar_hasta_el_final


class ConservarHastaElFinalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cierra_pero_no_destruye(self) -> None:
        w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
        w.show()
        w._flash_scan_hint("Agregado")
        conservar_hasta_el_final(w)
        self.assertFalse(w.isVisible())
        self.assertIn(w, _VENTANAS_SATELITE)
        QApplication.processEvents()
        self.assertFalse(sip.isdeleted(w._scan_hint))


def _pytest_aparte(*archivos: str) -> subprocess.CompletedProcess:
    aqui = Path(__file__).resolve().parent.parent
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYTEST_XDIST") and k not in {"POS_PRUEBAS_CORRIDA", "PYTEST_CURRENT_TEST"}}
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-m", "pytest", *archivos, "-p", "no:xdist", "-p", "no:cacheprovider", "-q"],
        cwd=aqui, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
    )


class AvisoDeEscaneoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
        self.addCleanup(conservar_hasta_el_final, self.w)

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
        r = _pytest_aparte("tests/_ayuda_aviso_borrado.py")
        salida = r.stdout + r.stderr
        self.assertNotIn("Fatal Python error", salida)
        self.assertNotIn("has been deleted", salida)
        self.assertEqual(r.returncode, 0, salida[-3000:])
        self.assertIn("2 passed", r.stdout)


class E4cYDespuesElCicloTests(unittest.TestCase):
    """La pareja que tumbaba el proceso, en un pytest aparte: e4c y luego una
    prueba que solo espera 2.3 s corriendo el ciclo de eventos."""

    def test_e4c_no_deja_kioskos_borrados_con_aviso_pendiente(self) -> None:
        r = _pytest_aparte("tests/test_e4c_kiosko_programas.py", "tests/_ayuda_kiosko_soltado.py")
        salida = r.stdout + r.stderr
        self.assertNotIn("Fatal Python error", salida)
        self.assertNotIn("has been deleted", salida)
        self.assertEqual(r.returncode, 0, salida[-3000:])


if __name__ == "__main__":
    unittest.main()
