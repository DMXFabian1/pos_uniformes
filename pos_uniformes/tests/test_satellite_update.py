"""Buscar/aplicar actualizaciones del satélite desde la app.

La app no puede sobreescribirse corriendo: "aplicar" = cerrar y relanzar
vía lanzador_satelite.bat, que copia la versión nueva del share.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import satellite_update_service as upd

_QSW = "pos_uniformes.ui.quote_satellite_window"


class EstadoActualizacionTests(unittest.TestCase):
    def test_hay_actualizacion_solo_si_difiere(self) -> None:
        with patch.object(upd, "version_local", return_value="2026.09.06"), \
                patch.object(upd, "version_remota", return_value="2026.09.07"):
            local, remota, hay = upd.estado_actualizacion()
        self.assertTrue(hay)
        self.assertEqual((local, remota), ("2026.09.06", "2026.09.07"))

        with patch.object(upd, "version_local", return_value="2026.09.07"), \
                patch.object(upd, "version_remota", return_value="2026.09.07"):
            self.assertFalse(upd.estado_actualizacion()[2])

        # Share inaccesible: no hay actualización (y remota es None)
        with patch.object(upd, "version_local", return_value="2026.09.06"), \
                patch.object(upd, "version_remota", return_value=None):
            _l, remota, hay = upd.estado_actualizacion()
        self.assertIsNone(remota)
        self.assertFalse(hay)

    def test_version_remota_lee_el_share(self) -> None:
        tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"upd_test_{os.getpid()}"
        (tmp / "PresupuestosSatelite").mkdir(parents=True, exist_ok=True)
        (tmp / "PresupuestosSatelite" / "VERSION.txt").write_text(
            "2026.09.07\n", encoding="utf-8"
        )
        with patch.object(upd, "_share_dir", return_value=tmp):
            self.assertEqual(upd.version_remota(), "2026.09.07")

    def test_version_remota_sin_share_es_none(self) -> None:
        with patch.object(upd, "_share_dir", return_value=None):
            self.assertIsNone(upd.version_remota())

    def test_lanzar_actualizador_usa_el_primer_lanzador_que_exista(self) -> None:
        tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"upd_bat_{os.getpid()}"
        tmp.mkdir(parents=True, exist_ok=True)
        bat = tmp / "lanzador_satelite.bat"
        bat.write_text("@echo off\n", encoding="utf-8")
        with patch.object(upd, "_share_dir", return_value=tmp.parent), \
                patch.object(upd.subprocess, "Popen") as popen, \
                patch.object(Path, "exists", autospec=True,
                             side_effect=lambda p: str(p) == str(bat)):
            # Los candidatos fijos no existen; cae al del share (tmp.parent/bat)
            with patch.object(upd, "_share_dir", return_value=tmp):
                self.assertTrue(upd.lanzar_actualizador())
        popen.assert_called_once()
        self.assertIn(str(bat), popen.call_args.args[0])

    def test_lanzar_actualizador_sin_lanzador_devuelve_false(self) -> None:
        with patch.object(upd, "_share_dir", return_value=None), \
                patch.object(Path, "exists", return_value=False), \
                patch.object(upd.subprocess, "Popen") as popen:
            self.assertFalse(upd.lanzar_actualizador())
        popen.assert_not_called()


class FlujoActualizacionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_aplicar_lanza_y_cierra(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(close=MagicMock())
        with patch(
            "pos_uniformes.services.satellite_update_service.lanzar_actualizador",
            return_value=True,
        ):
            QuoteSatelliteWindow._aplicar_actualizacion(fake)
        fake.close.assert_called_once()

    def test_aplicar_sin_lanzador_no_cierra(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(close=MagicMock())
        with patch(
            "pos_uniformes.services.satellite_update_service.lanzar_actualizador",
            return_value=False,
        ), patch(f"{_QSW}.QMessageBox") as mb:
            QuoteSatelliteWindow._aplicar_actualizacion(fake)
        fake.close.assert_not_called()
        mb.warning.assert_called_once()

    def test_ofrecer_actualiza_solo_si_acepta(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(_aplicar_actualizacion=MagicMock())
        box = MagicMock()
        botones = ["SI", "NO"]
        box.addButton.side_effect = botones
        with patch(f"{_QSW}.QMessageBox", return_value=box), patch(
            "pos_uniformes.services.satellite_update_service.version_local",
            return_value="2026.09.06",
        ):
            box.clickedButton.return_value = "SI"
            QuoteSatelliteWindow._ofrecer_actualizacion(fake, "2026.09.07")
            fake._aplicar_actualizacion.assert_called_once()

            box.addButton.side_effect = botones
            box.clickedButton.return_value = "NO"
            QuoteSatelliteWindow._ofrecer_actualizacion(fake, "2026.09.07")
            fake._aplicar_actualizacion.assert_called_once()  # sigue en 1


if __name__ == "__main__":
    unittest.main()
