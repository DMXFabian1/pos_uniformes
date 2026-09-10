"""El bloque "Lo que se perdió" de la pestaña Analítica."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from pos_uniformes.services import demanda_service as dm  # noqa: E402
from pos_uniformes.ui.helpers import analytics_demanda_helper as panel  # noqa: E402

_APP = QApplication.instance() or QApplication([])
_AHORA = datetime(2026, 9, 10, 12, 0)


def _fila(tipo, *, texto="", producto="", talla="", piezas=1, seg=0):
    return SimpleNamespace(
        tipo=tipo, texto=texto, producto=producto, talla=talla, piezas=piezas,
        created_at=_AHORA + timedelta(seconds=seg),
    )


class PanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window = QWidget()
        self.caja = panel.construir(self.window)

    def test_construye_las_dos_tablas(self) -> None:
        self.assertIn("perdió", self.caja.title())
        self.assertEqual(self.window.demanda_pedir_table.columnCount(), 4)
        self.assertIsNotNone(self.window.demanda_buscado_table)

    def test_sin_senales_lo_dice_y_no_truena(self) -> None:
        panel.pintar(self.window, [])
        self.assertIn("Todavía no hay", self.window.demanda_resumen_label.text())
        self.assertEqual(self.window.demanda_pedir_table.rowCount(), 0)

    def test_pinta_lo_que_hay_que_pedir(self) -> None:
        filas = [
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear", talla="6"),
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear", talla="6", seg=60),
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear", talla="6", seg=90),
            _fila(dm.BUSQUEDA_VACIA, texto="chamarra sabes"),
        ]
        panel.pintar(self.window, filas)
        tabla = self.window.demanda_pedir_table
        self.assertEqual(tabla.item(0, 0).text(), "Camisa Prowear · 6")
        self.assertEqual(tabla.item(0, 1).text(), "3")
        self.assertEqual(self.window.demanda_buscado_table.item(0, 0).text(), "chamarra sabes")
        self.assertIn("3 veces pidieron", self.window.demanda_resumen_label.text())

    def test_lo_repetido_sale_en_rojo(self) -> None:
        repetido = [_fila(dm.TALLA_AGOTADA, producto="Calceta", talla="6", seg=i) for i in range(3)]
        suelto = [_fila(dm.TALLA_AGOTADA, producto="Bata", talla="Uni")]
        panel.pintar(self.window, repetido + suelto)
        tabla = self.window.demanda_pedir_table
        self.assertEqual(tabla.item(0, 0).foreground().color().name(), panel._ROJO)
        self.assertNotEqual(tabla.item(1, 0).foreground().color().name(), panel._ROJO)

    def test_si_la_consulta_falla_la_analitica_sigue(self) -> None:
        rota = SimpleNamespace()  # no es una sesión: `listar` va a reventar
        panel.cargar_y_pintar(self.window, rota, _AHORA, _AHORA)
        self.assertIn("Todavía no hay", self.window.demanda_resumen_label.text())


if __name__ == "__main__":
    unittest.main()
