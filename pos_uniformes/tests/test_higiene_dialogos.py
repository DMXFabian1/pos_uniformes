"""La red de conftest que obliga a cada prueba a cerrar sus diálogos.

Antes, un diálogo olvidado (conteo físico, detalle del día, aviso de la
Libreta) seguía modal en ese proceso y la prueba de higiene de
`test_sin_anotar_persistencia` fallaba según cómo repartía xdist (2026-11-11).
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from tests.conftest import _dialogos_visibles, cerrar_dialogos


class CerrarDialogosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cierra_un_modal_y_ya_no_hay_modal_activo(self) -> None:
        d = QDialog()
        d.setModal(True)
        d.show()
        self.assertIs(QApplication.activeModalWidget(), d)
        self.assertIn(d, _dialogos_visibles().values())
        cerrar_dialogos([d])
        self.assertFalse(d.isVisible())
        self.assertIsNone(QApplication.activeModalWidget())

    def test_cierra_un_aviso_aunque_ignore_el_close(self) -> None:
        caja = QMessageBox(QMessageBox.Icon.Warning, "Aviso", "texto")
        caja.setModal(True)
        caja.show()
        cerrar_dialogos([caja])
        self.assertFalse(caja.isVisible())
        self.assertIsNone(QApplication.activeModalWidget())


class RedDeConftestTests(unittest.TestCase):
    """Un pytest aparte: la prueba que deja un diálogo falla con su nombre y la
    siguiente arranca sin modal. Nada se esconde: se señala."""

    def test_senala_a_la_que_deja_abierto_y_limpia_para_la_siguiente(self) -> None:
        aqui = Path(__file__).resolve().parent.parent
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PYTEST_XDIST") and k not in {"POS_PRUEBAS_CORRIDA", "PYTEST_CURRENT_TEST"}}
        env["QT_QPA_PLATFORM"] = "offscreen"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/_ayuda_dialogo_que_se_queda.py",
             "-p", "no:xdist", "-p", "no:cacheprovider", "-q", "-rA"],
            cwd=aqui, env=env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL,
        )
        salida = r.stdout
        self.assertNotEqual(r.returncode, 0, salida)
        # pytest cuenta la llamada como pasada y el cierre como error.
        self.assertIn("4 passed", salida)
        self.assertIn("2 errors", salida)
        self.assertIn("test_1_deja_un_modal_abierto dejó abierto: QDialog «Olvidado a propósito»", salida)
        # En macOS el QMessageBox no guarda título: basta con la clase.
        self.assertIn("test_2_deja_un_aviso_sin_boton_de_escape dejó abierto: QMessageBox", salida)
        self.assertIn("ERROR tests/_ayuda_dialogo_que_se_queda.py::test_1_deja_un_modal_abierto", salida)
        self.assertNotIn("ERROR tests/_ayuda_dialogo_que_se_queda.py::test_3", salida)
        self.assertNotIn("ERROR tests/_ayuda_dialogo_que_se_queda.py::test_4", salida)
        self.assertIn("PASSED tests/_ayuda_dialogo_que_se_queda.py::test_3_la_siguiente_arranca_limpia", salida)
        self.assertIn("PASSED tests/_ayuda_dialogo_que_se_queda.py::test_4_la_que_cierra_lo_suyo_pasa", salida)


if __name__ == "__main__":
    unittest.main()
