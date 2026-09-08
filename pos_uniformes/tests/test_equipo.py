"""Equipo: baja por temporada y reactivación sin borrar nada."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import Empleada, EmpleadaHorario, LibretaVenta
from pos_uniformes.services.equipo_service import FichaEmpleada, cambiar_estado, listar_equipo


class EquipoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        for t in (Empleada, EmpleadaHorario, LibretaVenta):
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add_all([
            Empleada(codigo="VEND-1", nombre_completo="Daniel", activo=True),
            Empleada(codigo="ENC-1", nombre_completo="León", activo=True),
            Empleada(codigo="VEND-2", nombre_completo="Ana López", activo=True),
            Empleada(codigo="VEND-9", nombre_completo="Lupita Mora", activo=True),
            EmpleadaHorario(employee_code="VEND-2", descanso_weekday=2, fecha_ultimo_pago=date(2026, 9, 2)),
            LibretaVenta(employee_code="VEND-2", employee_name="Ana", tipo="venta", piezas=1, comisiones=1,
                         monto_total=Decimal("100"), monto_neto=Decimal("100"), detalle=[],
                         created_at=datetime(2026, 9, 7, 12, 0)),
        ])
        self.session.commit()

    def test_listar_sin_dueno_ni_encargado_con_datos(self) -> None:
        fichas = listar_equipo(self.session)
        self.assertEqual([f.codigo for f in fichas], ["VEND-2", "VEND-9"])
        ana = fichas[0]
        self.assertEqual(ana.descanso, "miércoles")
        self.assertEqual(ana.ultimo_pago, date(2026, 9, 2))
        self.assertEqual(ana.ultimo_movimiento, date(2026, 9, 7))
        self.assertEqual(fichas[1].descanso, "sin configurar")

    def test_baja_y_reactivar_conserva_historial(self) -> None:
        cambiar_estado(self.session, "vend-9", activa=False)
        fichas = listar_equipo(self.session)
        self.assertEqual([(f.codigo, f.activa) for f in fichas], [("VEND-2", True), ("VEND-9", False)])  # inactivas al final
        cambiar_estado(self.session, "VEND-9", activa=True)
        self.assertTrue(self.session.query(Empleada).filter_by(codigo="VEND-9").one().activo)
        self.assertEqual(self.session.query(LibretaVenta).count(), 1)

    def test_no_se_puede_dar_de_baja_al_dueno_ni_al_encargado(self) -> None:
        with self.assertRaises(ValueError):
            cambiar_estado(self.session, "VEND-1", activa=False)
        with self.assertRaises(ValueError):
            cambiar_estado(self.session, "ENC-1", activa=False)
        with self.assertRaises(ValueError):
            cambiar_estado(self.session, "VEND-77", activa=False)


class EquipoDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_pinta_filas_y_botones(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        from pos_uniformes.ui.dialogs.equipo_dialog import EquipoDialog

        with patch.object(EquipoDialog, "recargar"):
            dlg = EquipoDialog(None)
        dlg.pintar([
            FichaEmpleada("VEND-2", "Ana López", True, "miércoles", date(2026, 9, 2), date(2026, 9, 7)),
            FichaEmpleada("VEND-9", "Lupita Mora", False, "sin configurar", None, None),
        ])
        self.assertEqual(dlg.tabla.rowCount(), 2)
        self.assertEqual(dlg.tabla.item(0, 2).text(), "Activa")
        self.assertEqual(dlg.tabla.item(1, 2).text(), "De baja")
        self.assertEqual(dlg.tabla.item(1, 4).text(), "—")
        b0 = dlg.tabla.cellWidget(0, 6)
        b1 = dlg.tabla.cellWidget(1, 6)
        self.assertIsInstance(b0, QPushButton)
        self.assertIn("Dar de baja", b0.text())
        self.assertIn("Reactivar", b1.text())


if __name__ == "__main__":
    unittest.main()
