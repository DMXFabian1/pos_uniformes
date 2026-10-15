"""Una identidad por PC: el POS y el kiosko de la misma máquina firman igual."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import satellite_identity_service as ident


class IdentidadDeLaMaquinaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.appdata = base / "AppData"
        self.repo = base / "repo"
        self._p = patch.object(ident, "satellite_data_dir", return_value=self.repo)
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()
        self._tmp.cleanup()

    def _windows(self):
        from contextlib import ExitStack

        pila = ExitStack()
        pila.enter_context(patch.object(ident, "_es_windows", return_value=True))
        pila.enter_context(patch.dict(ident.os.environ, {"APPDATA": str(self.appdata)}))
        return pila

    def _kiosko_instalado(self, nombre: str) -> None:
        ruta = self.appdata / "PresupuestosSatelite" / "data" / "satellite_identity.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text(json.dumps({"id": "19c9cf2a4ed9", "nombre": nombre}), encoding="utf-8")

    def test_en_windows_el_pos_usa_la_identidad_del_kiosko_instalado(self) -> None:
        self._kiosko_instalado("PC principal")
        with self._windows():
            self.assertEqual(ident.get_satellite_name(), "PC principal")
            self.assertEqual(ident.get_satellite_id(), "19c9cf2a4ed9")

    def test_renombrar_desde_el_pos_cambia_al_kiosko_tambien(self) -> None:
        self._kiosko_instalado("SKU005638")
        with self._windows():
            ident.set_satellite_name("PC principal")
        ruta = self.appdata / "PresupuestosSatelite" / "data" / "satellite_identity.json"
        self.assertEqual(json.loads(ruta.read_text(encoding="utf-8"))["nombre"], "PC principal")

    def test_sin_kiosko_instalado_cada_quien_la_suya(self) -> None:
        with self._windows():
            ident.set_satellite_name("Solo POS")
            self.assertEqual(ident.get_satellite_name(), "Solo POS")
        self.assertTrue((self.repo / "data" / "satellite_identity.json").exists())

    def test_fuera_de_windows_no_cambia_nada(self) -> None:
        self._kiosko_instalado("Otra")
        with patch.object(ident, "_es_windows", return_value=False), \
                patch.dict(ident.os.environ, {"APPDATA": str(self.appdata)}):
            ident.set_satellite_name("Mac")
            self.assertEqual(ident.get_satellite_name(), "Mac")


if __name__ == "__main__":
    unittest.main()
