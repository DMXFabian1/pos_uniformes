"""El corte del dueño ofrece los pagos que tocan hoy y los descuenta al guardar."""

from __future__ import annotations

import sys
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaParametros, Empleada, EmpleadaHorario, EmpleadaPago, LibretaCorte, LibretaVenta

app = QApplication.instance() or QApplication(sys.argv)

HOY = date.today()


class CortePagosDeHoyTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add_all([
            Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
            Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True),
            Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True),
            Empleada(codigo="VEND-8", nombre_completo="Katherine Posada", activo=True),
            EmpleadaHorario(employee_code="VEND-4", fecha_ultimo_pago=HOY - timedelta(days=7)),   # toca hoy
            EmpleadaHorario(employee_code="VEND-5", fecha_ultimo_pago=HOY - timedelta(days=7)),   # toca hoy
            EmpleadaHorario(employee_code="VEND-8", fecha_ultimo_pago=HOY - timedelta(days=3)),   # todavía no
            CajaParametros(id=1, reactivo_actual=Decimal("11160.00"), sueldo_base=Decimal("1300.00"),
                           tarifa_comision=Decimal("2.00"), descuento_falta=Decimal("216.67")),
            LibretaVenta(employee_code="VEND-4", tipo="venta", piezas=2, monto_total=Decimal("5000.00"), comisiones=2,
                         detalle=[], created_at=datetime.now() - timedelta(hours=2)),
        ])
        self.s.commit()

        s = self.s

        @contextmanager
        def _sesion():
            yield s

        self._parches = [
            patch("pos_uniformes.database.connection.get_session", _sesion),
            patch("pos_uniformes.ui.dialogs.corte_caja_dialog.QDialog.exec", lambda self_: QDialog.DialogCode.Accepted),
            patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets", lambda *a, **k: None),
            patch("pos_uniformes.services.corte_caja_service._avisar_corte", lambda *a, **k: None),
        ]
        for p in self._parches:
            p.start()

    def tearDown(self) -> None:
        for p in self._parches:
            p.stop()
        self.s.close()

    def test_los_pagos_de_hoy_se_registran_y_se_descuentan(self) -> None:
        from pos_uniformes.ui.dialogs.corte_caja_dialog import hacer_corte_caja

        vistas: list[tuple[str, bool]] = []

        def _exec_y_mira(dlg):
            # Lo que el dueño ve antes de aceptar: las casillas de pago.
            vistas.extend((cb.text(), cb.isChecked()) for cb in dlg.findChildren(QCheckBox) if "comisiones" in cb.text())
            return QDialog.DialogCode.Accepted

        with patch("pos_uniformes.ui.dialogs.corte_caja_dialog.QDialog.exec", _exec_y_mira):
            corte = hacer_corte_caja(None, creado_por="VEND-1")
        self.assertIsNotNone(corte)
        # Se ofrecieron Stayce y Fanny (no Katherine), marcadas de entrada.
        self.assertEqual(sorted(t.split()[0] for t, _ in vistas), ["Fanny", "Stayce"])
        self.assertTrue(all(marcada for _, marcada in vistas))
        self.assertTrue(all("$1,30" in t for t, _ in vistas), vistas)   # sueldo base + comisiones de la venta
        # Quedaron registrados y descontados del corte.
        pagos = list(self.s.scalars(select(EmpleadaPago)).all())
        self.assertEqual(sorted(p.employee_code for p in pagos), ["VEND-4", "VEND-5"])
        self.assertEqual(pagos[0].creado_por, "VEND-1")
        total_pagos = sum(p.total for p in pagos)
        corte_db = self.s.scalars(select(LibretaCorte)).one()
        self.assertEqual(corte_db.retiros_pagos, total_pagos)
        # esperado = reactivo + venta − pagos; el corte propuso ese contado
        self.assertEqual(corte_db.monto_esperado, Decimal("11160.00") + Decimal("5000.00") - total_pagos)
        self.assertEqual(corte_db.monto_final, corte_db.monto_esperado)
        for code in ("VEND-4", "VEND-5"):
            self.assertEqual(self.s.get(EmpleadaHorario, code).fecha_ultimo_pago, HOY)

    def test_desmarcado_no_se_registra(self) -> None:
        from pos_uniformes.ui.dialogs.corte_caja_dialog import hacer_corte_caja

        def _exec_desmarcando(dlg):
            for cb in dlg.findChildren(QCheckBox):
                if "Fanny" in cb.text():
                    cb.setChecked(False)
            return QDialog.DialogCode.Accepted

        with patch("pos_uniformes.ui.dialogs.corte_caja_dialog.QDialog.exec", _exec_desmarcando):
            hacer_corte_caja(None, creado_por="VEND-1")
        pagos = list(self.s.scalars(select(EmpleadaPago)).all())
        self.assertEqual([p.employee_code for p in pagos], ["VEND-4"])
        corte_db = self.s.scalars(select(LibretaCorte)).one()
        self.assertEqual(corte_db.retiros_pagos, pagos[0].total)


if __name__ == "__main__":
    unittest.main()
