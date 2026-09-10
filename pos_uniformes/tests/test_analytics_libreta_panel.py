"""El bloque "Ventas reales" de Analítica: se construye y se llena."""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox

from pos_uniformes.services import analitica_libreta_service as an
from pos_uniformes.ui.helpers import analytics_libreta_helper as helper


def _filas():
    op = SimpleNamespace(
        tipo="venta", created_at=datetime(2026, 9, 7, 11, 30),
        employee_code="VEND-2", employee_name="Fanny Ortiz", pago_tarjeta=False,
        detalle=[{"sku": "SKU1", "nombre": "Playera Polo", "talla": "6", "cantidad": 3,
                  "precio": "89.00", "subtotal": "267.00"}],
    )
    catalogo = {"SKU1": {"escuela": "Benito Juárez", "tipo_pieza": "Playera",
                         "categoria": "P", "genero": "Unisex", "nivel": "Primaria"}}
    return an.enriquecer(an.desglosar([op]), catalogo)


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self):
        ventana = SimpleNamespace()
        caja = helper.construir(ventana)
        return ventana, caja

    def test_construye_las_seis_tablas(self) -> None:
        ventana, caja = self._ventana()
        self.assertIsInstance(caja, QGroupBox)
        for atributo, _titulo, _col in helper.TABLAS:
            tabla = getattr(ventana, atributo)
            self.assertEqual(tabla.columnCount(), 4)
            self.assertEqual(tabla.rowCount(), 0)

    def test_pinta_las_ventas(self) -> None:
        ventana, _caja = self._ventana()
        helper.pintar(ventana, _filas())
        resumen = ventana.libreta_analytics_resumen_label.text()
        self.assertIn("3 piezas", resumen)
        self.assertIn("$267.00", resumen)
        self.assertIn("Efectivo $267.00", ventana.libreta_analytics_pago_label.text())
        productos = ventana.libreta_top_productos_table
        self.assertEqual(productos.rowCount(), 1)
        self.assertEqual(productos.item(0, 0).text(), "Playera Polo")
        self.assertEqual(productos.item(0, 1).text(), "3")
        self.assertEqual(productos.item(0, 2).text(), "$267.00")
        self.assertEqual(productos.item(0, 3).text(), "$89.00")
        self.assertEqual(ventana.libreta_por_escuela_table.item(0, 0).text(), "Benito Juárez")
        self.assertEqual(ventana.libreta_por_hora_table.item(0, 0).text(), "11:00")
        self.assertEqual(ventana.libreta_por_talla_table.item(0, 0).text(), "6")

    def test_sin_ventas_lo_dice_y_deja_las_tablas_vacias(self) -> None:
        ventana, _caja = self._ventana()
        helper.pintar(ventana, [])
        self.assertIn("Sin ventas registradas", ventana.libreta_analytics_resumen_label.text())
        self.assertEqual(ventana.libreta_analytics_pago_label.text(), "")
        self.assertEqual(ventana.libreta_top_productos_table.rowCount(), 0)

    def test_si_la_consulta_falla_la_analitica_sigue_de_pie(self) -> None:
        ventana, _caja = self._ventana()
        with patch("pos_uniformes.services.analitica_libreta_service.filas_de_periodo",
                   side_effect=RuntimeError("sin base")):
            helper.cargar_y_pintar(ventana, object(), datetime(2026, 9, 1), datetime(2026, 9, 30))
        self.assertIn("Sin ventas registradas", ventana.libreta_analytics_resumen_label.text())

    def test_fechas_sin_zona_se_normalizan(self) -> None:
        vistos = {}

        def _fake(session, desde, hasta, **kw):
            vistos["desde"], vistos["hasta"] = desde, hasta
            return []

        ventana, _caja = self._ventana()
        with patch("pos_uniformes.services.analitica_libreta_service.filas_de_periodo", _fake):
            helper.cargar_y_pintar(ventana, object(), datetime(2026, 9, 1), datetime(2026, 9, 30))
        self.assertIsNotNone(vistos["desde"].tzinfo)
        self.assertIsNotNone(vistos["hasta"].tzinfo)

    def test_no_pinta_mas_de_doce_renglones(self) -> None:
        ventana, _caja = self._ventana()
        muchos = [an.Grupo(f"P{i}", i, Decimal(i * 10), 1) for i in range(30)]
        helper._llenar(ventana.libreta_top_productos_table, muchos)
        self.assertEqual(ventana.libreta_top_productos_table.rowCount(), helper.FILAS_MAX)


if __name__ == "__main__":
    unittest.main()
