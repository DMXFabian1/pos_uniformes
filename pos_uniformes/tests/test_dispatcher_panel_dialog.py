"""Tests del panel del despachador (Fase 2), corriendo Qt offscreen."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.ui.dialogs.dispatcher_panel_dialog import DispatcherPanelDialog

_MOD = "pos_uniformes.ui.dialogs.dispatcher_panel_dialog"


class DispatcherPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _seed_ticket(self, texto: str) -> int:
        s = self.factory()
        t = svc.enviar_ticket(s, texto)
        s.commit()
        tid = t.id
        s.close()
        return tid

    def _panel(self) -> DispatcherPanelDialog:
        return DispatcherPanelDialog(session_factory=self.factory, auto_refresh_ms=0)

    def test_refresh_muestra_filas(self) -> None:
        self._seed_ticket("MAXIMODA\nProducto")
        self._seed_ticket("OTRO")
        panel = self._panel()
        self.assertEqual(panel._table.rowCount(), 2)
        # Columna Detalle (4) = primera línea del ticket.
        self.assertEqual(panel._table.item(0, 4).text(), "MAXIMODA")

    def test_filtro_por_estado(self) -> None:
        a = self._seed_ticket("A")
        self._seed_ticket("B")
        s = self.factory()
        svc.marcar_hecho(s, a)
        s.commit()
        s.close()
        panel = self._panel()
        self.assertEqual(panel._table.rowCount(), 2)
        # Filtrar a "En espera" (índice 1) -> solo el pendiente.
        panel._estado_combo.setCurrentIndex(1)
        self.assertEqual(panel._table.rowCount(), 1)

    def test_cancelar_pendiente(self) -> None:
        tid = self._seed_ticket("X")
        panel = self._panel()
        panel._table.selectRow(0)
        with patch(f"{_MOD}.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            panel._cancelar()
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.CANCELADO)
        s.close()

    def test_reimprimir_crea_nuevo_pendiente(self) -> None:
        tid = self._seed_ticket("TICKET")
        s = self.factory()
        svc.marcar_hecho(s, tid)
        s.commit()
        s.close()
        panel = self._panel()
        panel._table.selectRow(0)
        panel._reimprimir()
        # Ahora hay 2 filas: el HECHO original + la copia PENDIENTE.
        self.assertEqual(panel._table.rowCount(), 2)
        s = self.factory()
        pendientes = svc.listar(s, estados=[EstadoTrabajo.PENDIENTE])
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0].contenido, {"texto": "TICKET"})
        s.close()

    def test_reintentar_error(self) -> None:
        tid = self._seed_ticket("X")
        s = self.factory()
        svc.marcar_error(s, tid, "sin papel")
        s.commit()
        s.close()
        panel = self._panel()
        panel._table.selectRow(0)
        panel._reintentar()
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.PENDIENTE)
        s.close()

    def test_mover_reordena_pendientes(self) -> None:
        ids = [self._seed_ticket(f"T{i}") for i in range(3)]
        panel = self._panel()
        panel._table.selectRow(2)  # el último (T2)
        panel._mover(-1)  # subirlo una posición
        s = self.factory()
        orden = [t.id for t in svc.listar(s, estados=[EstadoTrabajo.PENDIENTE])]
        s.close()
        # T2 (ids[2]) ahora va antes que T1 (ids[1]).
        self.assertEqual(orden, [ids[0], ids[2], ids[1]])

    def test_botones_segun_estado(self) -> None:
        self._seed_ticket("X")
        panel = self._panel()
        panel._table.selectRow(0)
        panel._update_action_buttons()
        self.assertTrue(panel._btn_cancelar.isEnabled())
        self.assertFalse(panel._btn_reimprimir.isEnabled())
        self.assertTrue(panel._btn_subir.isEnabled())


if __name__ == "__main__":
    unittest.main()
