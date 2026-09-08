"""Libreta → "Ver momento": abre la grabación del DVR a la hora del movimiento."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

_DIALOG = "pos_uniformes.ui.dialogs.camera_playback_dialog.CameraPlaybackDialog"


def _row(created_at, tipo="venta", nombre="Coraima"):
    return SimpleNamespace(
        created_at=created_at,
        tipo=tipo,
        employee_name=nombre,
        employee_code="VEND-2",
        piezas=1,
        detalle=[],
        monto_total=100,
    )


class MomentoLocalTests(unittest.TestCase):
    def test_utc_aware_se_convierte_a_local_naive(self) -> None:
        utc = datetime(2026, 9, 8, 18, 30, 15, tzinfo=timezone.utc)
        local = QuoteSatelliteWindow._momento_local_libreta(_row(utc))
        self.assertIsNone(local.tzinfo)
        self.assertEqual(local, utc.astimezone().replace(tzinfo=None))

    def test_naive_se_respeta(self) -> None:
        naive = datetime(2026, 9, 8, 12, 30, 15)
        self.assertEqual(QuoteSatelliteWindow._momento_local_libreta(_row(naive)), naive)


class VerMomentoLibretaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fake(self, rows, current_row=0, owner=True):
        table = MagicMock()
        table.currentRow.return_value = current_row
        return SimpleNamespace(
            _libreta_is_owner=owner,
            _libreta_rows_pintadas=rows,
            libreta_table=table,
            _set_status=MagicMock(),
            _momento_local_libreta=QuoteSatelliteWindow._momento_local_libreta,
        )

    def test_dueno_abre_en_modo_admin_con_el_movimiento_seleccionado(self) -> None:
        naive = datetime(2026, 9, 8, 12, 30, 15)
        fake = self._fake([_row(naive)], owner=True)
        with patch(_DIALOG) as dialog_cls:
            QuoteSatelliteWindow._ver_momento_libreta(fake)
        dialog_cls.assert_called_once()
        args, kwargs = dialog_cls.call_args
        self.assertEqual(args[0], naive)
        self.assertTrue(kwargs["admin"])
        self.assertIn("Venta", kwargs["titulo"])
        self.assertIn("Coraima", kwargs["titulo"])
        dialog_cls.return_value.show.assert_called_once()
        self.assertIs(fake._camera_playback_dialog, dialog_cls.return_value)

    def test_empleada_abre_sin_admin(self) -> None:
        fake = self._fake([_row(datetime(2026, 9, 8, 12, 0))], owner=False)
        with patch(_DIALOG) as dialog_cls:
            QuoteSatelliteWindow._ver_momento_libreta(fake, fake._libreta_rows_pintadas[0])
        self.assertFalse(dialog_cls.call_args.kwargs["admin"])

    def test_sin_seleccion_avisa_y_no_abre(self) -> None:
        fake = self._fake([], current_row=-1)
        with patch(_DIALOG) as dialog_cls:
            QuoteSatelliteWindow._ver_momento_libreta(fake)
        dialog_cls.assert_not_called()
        fake._set_status.assert_called_once()

    def test_abrir_otro_cierra_el_anterior(self) -> None:
        fake = self._fake([_row(datetime(2026, 9, 8, 12, 0))])
        anterior = MagicMock()
        fake._camera_playback_dialog = anterior
        with patch(_DIALOG):
            QuoteSatelliteWindow._ver_momento_libreta(fake)
        anterior.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
