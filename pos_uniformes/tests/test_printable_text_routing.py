"""open_printable_text_dialog respeta el rol de impresión de la PC.

Servidor (MODO_LOCAL): imprime local (abre el diálogo con preview).
Estación (MODO_SATELITE): encola el documento al servidor, sin tocar impresora.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from pos_uniformes.services.print_routing_cache_service import (
    MODO_LOCAL,
    MODO_SATELITE,
    save_print_routing,
)
from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog

_SDD = "pos_uniformes.services.print_routing_cache_service.satellite_data_dir"


class PrintableTextRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_servidor_imprime_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                save_print_routing(MODO_LOCAL, "principal")
                with patch(
                    "pos_uniformes.ui.dialogs.printable_text_dialog.open_tickets_print_dialog"
                ) as otd:
                    open_printable_text_dialog(QDialog(), "Presupuesto 1", "contenido")
                otd.assert_called_once()
                # El contenido se pasa como lista de un elemento.
                self.assertEqual(otd.call_args.args[2], ["contenido"])

    def test_estacion_encola_sin_imprimir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                save_print_routing(MODO_SATELITE, "caja 2")
                with patch(
                    "pos_uniformes.database.connection.get_session"
                ) as gs, patch(
                    "pos_uniformes.services.trabajos_service.enviar_tickets"
                ) as enviar, patch(
                    "pos_uniformes.ui.dialogs.printable_text_dialog.open_tickets_print_dialog"
                ) as otd, patch(
                    "PyQt6.QtWidgets.QMessageBox.information"
                ):
                    gs.return_value.__enter__.return_value = MagicMock()
                    enviar.return_value = [MagicMock()]
                    open_printable_text_dialog(QDialog(), "Presupuesto 1", "contenido")
                # Encoló el documento y NO abrió el diálogo de impresión local.
                enviar.assert_called_once()
                otd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
