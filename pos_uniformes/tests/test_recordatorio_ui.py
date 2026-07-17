"""Tests de la UI de recordatorios: diálogo de alta e integración en el calendario."""

from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services.recordatorio_service import crear_recordatorio, listar_recordatorios


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


class RecordatorioDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_agregar_desde_el_dialogo(self) -> None:
        from pos_uniformes.ui.dialogs.recordatorio_dialog import RecordatoriosDialog

        eng = _make_engine()
        d = RecordatoriosDialog(session_factory=lambda: Session(eng))
        d._tipo_combo.setCurrentIndex(d._tipo_combo.findData("pago"))
        d._titulo_edit.setText("Renta")
        d._recurrencia_combo.setCurrentIndex(d._recurrencia_combo.findData("mensual"))
        d._dia_mes_spin.setValue(1)
        d._monto_edit.setText("8000")
        d._agregar()
        with Session(eng) as s:
            recs = listar_recordatorios(s)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].titulo, "Renta")
        self.assertEqual(recs[0].dia_mes, 1)

    def test_monto_solo_visible_para_pago(self) -> None:
        from pos_uniformes.ui.dialogs.recordatorio_dialog import RecordatoriosDialog

        eng = _make_engine()
        d = RecordatoriosDialog(session_factory=lambda: Session(eng))
        d._tipo_combo.setCurrentIndex(d._tipo_combo.findData("pago"))
        self.assertFalse(d._monto_edit.isHidden())
        d._tipo_combo.setCurrentIndex(d._tipo_combo.findData("descanso"))
        self.assertTrue(d._monto_edit.isHidden())


class CalendarioRecordatoriosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_carga_recordatorios_y_banner(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_calendario_mes_panel import ConteoCalendarioMesPanel

        eng = _make_engine()
        with Session(eng) as s:
            crear_recordatorio(s, tipo="pago", titulo="Renta", recurrencia="mensual", dia_mes=17)
            s.commit()
        panel = ConteoCalendarioMesPanel(
            session_factory=lambda: Session(eng), hoy=date(2026, 6, 16)
        )
        # Cargó el recordatorio y el banner muestra "Renta" (mañana, día 17).
        self.assertEqual(len(panel._recordatorios), 1)
        self.assertFalse(panel._proximos_label.isHidden())
        self.assertIn("Renta", panel._proximos_label.text())


if __name__ == "__main__":
    unittest.main()
