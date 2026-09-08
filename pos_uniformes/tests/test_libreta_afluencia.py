"""Libreta del dueño: tabla de afluencia vs ventas por hora."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QHeaderView, QLabel, QTableWidget

from pos_uniformes.services.afluencia_service import FilaAfluencia
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

HOY = datetime.now().replace(minute=0, second=0, microsecond=0)


class PintarAfluenciaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fake(self, owner=True, periodo="hoy"):
        tabla = QTableWidget(0, 5)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return SimpleNamespace(
            _libreta_is_owner=owner,
            _libreta_periodo=periodo,
            libreta_afluencia_seccion=QLabel(),
            libreta_afluencia_table=tabla,
        )

    def _celda(self, fake, r, c) -> str:
        return fake.libreta_afluencia_table.item(r, c).text()

    def test_pinta_horas_de_hoy_y_total(self) -> None:
        fake = self._fake()
        filas = [
            FilaAfluencia(HOY.replace(hour=10), 10, 8, 40, 3),
            FilaAfluencia(HOY.replace(hour=11), 5, 5, 10, 0),
            FilaAfluencia(HOY.replace(hour=12), 0, 0, 0, 0),  # vacía: no se pinta
        ]
        QuoteSatelliteWindow._pintar_afluencia_libreta(fake, filas)
        self.assertFalse(fake.libreta_afluencia_table.isHidden())
        self.assertEqual(fake.libreta_afluencia_table.rowCount(), 3)  # 2 horas + total
        self.assertEqual(self._celda(fake, 0, 0), "10:00")
        self.assertEqual(self._celda(fake, 0, 4), "30%")
        self.assertEqual(self._celda(fake, 1, 4), "0%")
        self.assertEqual(self._celda(fake, 2, 0), "Total")
        self.assertEqual(self._celda(fake, 2, 1), "15")
        self.assertEqual(self._celda(fake, 2, 3), "3")
        self.assertEqual(self._celda(fake, 2, 4), "20%")

    def test_en_hoy_descarta_otros_dias(self) -> None:
        fake = self._fake(periodo="hoy")
        ayer = HOY - timedelta(days=1)
        QuoteSatelliteWindow._pintar_afluencia_libreta(fake, [FilaAfluencia(ayer, 7, 0, 0, 1)])
        self.assertTrue(fake.libreta_afluencia_table.isHidden())

    def test_en_rango_muestra_dia_y_hora(self) -> None:
        fake = self._fake(periodo="rango")
        ayer = HOY - timedelta(days=1)
        QuoteSatelliteWindow._pintar_afluencia_libreta(
            fake, [FilaAfluencia(ayer, 7, 0, 0, 1), FilaAfluencia(HOY, 3, 0, 0, 0)]
        )
        self.assertEqual(self._celda(fake, 0, 0), ayer.strftime("%d/%m %H:00"))

    def test_sin_entradas_muestra_guion(self) -> None:
        fake = self._fake()
        QuoteSatelliteWindow._pintar_afluencia_libreta(fake, [FilaAfluencia(HOY, 0, 0, 0, 2)])
        self.assertEqual(self._celda(fake, 0, 4), "—")

    def test_empleada_nunca_lo_ve(self) -> None:
        fake = self._fake(owner=False)
        QuoteSatelliteWindow._pintar_afluencia_libreta(fake, [FilaAfluencia(HOY, 10, 0, 0, 1)])
        self.assertTrue(fake.libreta_afluencia_table.isHidden())
        self.assertTrue(fake.libreta_afluencia_seccion.isHidden())


class CargarAfluenciaTests(unittest.TestCase):
    def test_falla_de_tabla_no_rompe_y_hace_rollback(self) -> None:
        session = MagicMock()
        session.execute.side_effect = RuntimeError("relation afluencia_hora does not exist")
        session.scalars.side_effect = RuntimeError("relation afluencia_hora does not exist")
        filas = QuoteSatelliteWindow._cargar_afluencia_libreta(session, datetime(2026, 9, 1), datetime(2026, 9, 8))
        self.assertEqual(filas, [])
        session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
