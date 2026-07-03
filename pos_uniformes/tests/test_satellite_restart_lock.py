"""Tests del reinicio del satélite: liberar el candado de instancia única.

Bug original: "Guardar y reiniciar" del menú admin llamaba os.execv sin
soltar el QLockFile — en Windows la instancia nueva podía arrancar antes de
que muriera la vieja, ver el candado tomado y cerrarse con "Ya está abierto".
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.dialogs.satellite_admin_dialog import _release_instance_lock


class ReleaseInstanceLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self.app, "_instance_lock"):
            delattr(self.app, "_instance_lock")

    def test_releases_lock_so_a_new_instance_can_take_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = str(Path(tmp) / "presupuestos_satelite.lock")
            lock = QLockFile(lock_path)
            self.assertTrue(lock.tryLock(100))
            self.app._instance_lock = lock

            # Simula la "instancia nueva": con el candado tomado no puede entrar.
            new_instance_lock = QLockFile(lock_path)
            self.assertFalse(new_instance_lock.tryLock(100))

            _release_instance_lock()

            self.assertTrue(new_instance_lock.tryLock(100))
            new_instance_lock.unlock()

    def test_noop_when_no_lock_attached(self) -> None:
        # En dev o si el arranque no registró el candado, no debe lanzar.
        _release_instance_lock()


if __name__ == "__main__":
    unittest.main()
