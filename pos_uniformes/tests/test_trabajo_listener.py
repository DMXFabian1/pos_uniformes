"""Test del cableado del listener de NOTIFY (sin red real)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.helpers.trabajo_listener import TrabajoNotifyListener


class TrabajoListenerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_notificado_dispara_el_slot(self) -> None:
        # No arrancamos el hilo (run); solo verificamos que la señal despierta
        # al despachador. connect_fn se inyecta para no tocar la red.
        listener = TrabajoNotifyListener(connect_fn=lambda: None)
        llamado = {"n": 0}
        listener.notificado.connect(lambda: llamado.__setitem__("n", llamado["n"] + 1))
        listener.notificado.emit()
        self.assertEqual(llamado["n"], 1)
        listener.stop()

    def test_stop_marca_bandera(self) -> None:
        listener = TrabajoNotifyListener(connect_fn=lambda: None)
        self.assertFalse(listener._stop)
        listener.stop()
        self.assertTrue(listener._stop)


if __name__ == "__main__":
    unittest.main()
