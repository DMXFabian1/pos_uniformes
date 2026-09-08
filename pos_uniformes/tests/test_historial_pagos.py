"""Historial de pagos a empleadas: totales por empleada y filas de la tabla."""

from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services.nomina_service import rango_mes, resumir_pagos_por_empleada


def _pago(code, nombre, fecha, total, comisiones=0, faltas=0, desde=None):
    return SimpleNamespace(
        employee_code=code, employee_name=nombre, fecha=fecha, desde=desde, hasta=fecha,
        comisiones=comisiones, sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"),
        monto_comisiones=Decimal(2 * comisiones), faltas=faltas,
        descuento_faltas=(Decimal("216.67") * faltas).quantize(Decimal("0.01")),
        total=Decimal(total), creado_por="ENC-1",
    )


class ResumirPagosTests(unittest.TestCase):
    def test_totales_por_empleada_ordenados(self) -> None:
        pagos = [
            _pago("VEND-2", "Ana", date(2026, 9, 1), "1390.00", 45),
            _pago("VEND-2", "Ana", date(2026, 9, 8), "1300.00", 0),
            _pago("VEND-3", "Bety", date(2026, 9, 8), "1103.33", 10, faltas=1),
        ]
        t = resumir_pagos_por_empleada(pagos)
        self.assertEqual([x.employee_name for x in t], ["Ana", "Bety"])
        self.assertEqual(t[0].pagos, 2)
        self.assertEqual(t[0].comisiones, 45)
        self.assertEqual(t[0].total, Decimal("2690.00"))
        self.assertEqual(t[1].faltas, 1)
        self.assertEqual(t[1].descuento_faltas, Decimal("216.67"))

    def test_rango_mes(self) -> None:
        self.assertEqual(rango_mes(2026, 9), (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(rango_mes(2026, 12), (date(2026, 12, 1), date(2026, 12, 31)))
        self.assertEqual(rango_mes(2028, 2), (date(2028, 2, 1), date(2028, 2, 29)))


class HistorialDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_pinta_pagos_y_totales(self) -> None:
        from pos_uniformes.ui.dialogs.historial_pagos_dialog import HistorialPagosDialog, filas_tabla

        pagos = [
            _pago("VEND-2", "Ana López", date(2026, 9, 8), "1390.00", 45, desde=date(2026, 9, 2)),
            _pago("VEND-3", "Bety Ruiz", date(2026, 9, 8), "1103.33", 10, faltas=1),
        ]
        with patch.object(HistorialPagosDialog, "_cargar_empleadas"), patch.object(
            HistorialPagosDialog, "recargar"
        ):
            dlg = HistorialPagosDialog(None, hoy=date(2026, 9, 8))
        self.assertEqual(dlg.mes_combo.itemText(0), "Septiembre 2026")
        self.assertEqual(dlg.mes_combo.itemText(1), "Agosto 2026")
        dlg.pintar(pagos)
        self.assertEqual(dlg.tabla.rowCount(), 2)
        self.assertEqual(dlg.tabla.item(0, 2).text(), "02/09 → 08/09")
        self.assertEqual(dlg.tabla.item(0, 4).text(), "45 × $2.00 = $90.00")
        self.assertEqual(dlg.tabla.item(1, 5).text(), "1 (−$216.67)")
        self.assertEqual(dlg.tabla.item(0, 6).text(), "$1,390.00")
        self.assertEqual(dlg.resumen_tabla.rowCount(), 2)
        self.assertIn("Total pagado: $2,493.33", dlg.totales_label.text())
        self.assertEqual(filas_tabla([])[:0], [])

    def test_sin_pagos(self) -> None:
        from pos_uniformes.ui.dialogs.historial_pagos_dialog import HistorialPagosDialog

        with patch.object(HistorialPagosDialog, "_cargar_empleadas"), patch.object(
            HistorialPagosDialog, "recargar"
        ):
            dlg = HistorialPagosDialog(None, hoy=date(2026, 9, 8))
        dlg.pintar([])
        self.assertEqual(dlg.tabla.rowCount(), 0)
        self.assertIn("No hay pagos", dlg.totales_label.text())


if __name__ == "__main__":
    unittest.main()
