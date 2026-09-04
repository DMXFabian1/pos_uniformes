"""Tests de app_version(): la fuente del número que compara el updater.

El bug real en tienda: dentro del exe (PyInstaller) el archivo VERSION
vive en la raíz del bundle (sys._MEIPASS), no junto al paquete, así que
app_version() caía al DEFAULT viejo y la app creía por siempre que había
una actualización disponible.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from pos_uniformes.utils import app_metadata


class AppVersionTests(unittest.TestCase):
    def tearDown(self):
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS

    def test_en_desarrollo_lee_el_version_del_repo(self):
        esperado = (app_metadata.project_root() / "VERSION").read_text().strip()
        self.assertEqual(app_metadata.app_version(), esperado)

    def test_empaquetado_lee_el_version_del_bundle(self):
        with tempfile.TemporaryDirectory() as bundle:
            (Path(bundle) / "VERSION").write_text("2099.01.01\n", encoding="utf-8")
            sys._MEIPASS = bundle
            self.assertEqual(app_metadata.app_version(), "2099.01.01")

    def test_empaquetado_sin_version_cae_al_repo_y_luego_al_default(self):
        with tempfile.TemporaryDirectory() as bundle:
            sys._MEIPASS = bundle  # bundle sin archivo VERSION
            esperado = (app_metadata.project_root() / "VERSION").read_text().strip()
            self.assertEqual(app_metadata.app_version(), esperado)


if __name__ == "__main__":
    unittest.main()
