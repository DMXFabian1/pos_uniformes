"""Los kioskos de prueba no se destruyen con un aviso diferido pendiente.

`QuickSaleWidget._flash_scan_hint` programa una lambda de 1.8 s sin dueño Qt.
Borrar el widget antes tumbaba el proceso en la siguiente prueba que corriera
el ciclo de eventos (1 de cada 4-5 corridas con -n 6; 2026-11-11). La causa
está en la vista y queda reportada; aquí se protege lo de las pruebas.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PyQt6 import sip
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


class E4cYDespuesElCicloTests(unittest.TestCase):
    """La pareja que tumbaba el proceso, en un pytest aparte: e4c y luego una
    prueba que solo espera 2.3 s corriendo el ciclo de eventos."""

    def test_e4c_no_deja_kioskos_borrados_con_aviso_pendiente(self) -> None:
        aqui = Path(__file__).resolve().parent.parent
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PYTEST_XDIST") and k not in {"POS_PRUEBAS_CORRIDA", "PYTEST_CURRENT_TEST"}}
        env["QT_QPA_PLATFORM"] = "offscreen"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_e4c_kiosko_programas.py",
             "tests/_ayuda_kiosko_soltado.py", "-p", "no:xdist", "-p", "no:cacheprovider", "-q"],
            cwd=aqui, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
        )
        salida = r.stdout + r.stderr
        self.assertNotIn("Fatal Python error", salida)
        self.assertNotIn("has been deleted", salida)
        self.assertEqual(r.returncode, 0, salida[-3000:])


if __name__ == "__main__":
    unittest.main()
