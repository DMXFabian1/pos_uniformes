"""Test del diálogo de hojas de conteo.

Bug original: tenía su propia cola QTimer sin guard — cerrar el diálogo a
media impresión (12 hojas ≈ 18s) tocaba el botón destruido → qFatal → se
cerraba el POS completo. Ahora delega en open_tickets_print_dialog, que usa
TicketPrintQueue (segura ante cierre, cubierta por test_ticket_print_queue).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.dialogs.conteo_print_dialog import open_conteo_print_dialog


class ConteoPrintDialogTests(unittest.TestCase):
    def test_delegates_to_safe_tickets_dialog_with_hoja_label(self) -> None:
        # El ruteo a satelite se apaga a proposito: depende de la config de cada
        # maquina (print_routing) y no es lo que este test cubre. Sin esto, en una
        # PC en modo satelite el test escribia un trabajo real en la base y luego
        # abortaba el proceso al levantar un QMessageBox sin QApplication.
        with patch(
            "pos_uniformes.ui.helpers.conteo_routing_helper."
            "maybe_route_conteo_to_satellite",
            return_value=False,
        ), patch(
            "pos_uniformes.ui.dialogs.conteo_print_dialog.open_tickets_print_dialog"
        ) as safe_dialog, patch(
            "pos_uniformes.ui.dialogs.printable_text_dialog.print_conteo_sheet"
        ) as print_fn:
            open_conteo_print_dialog(None, "Hojas de conteo", ["hoja 1", "hoja 2"])
        safe_dialog.assert_called_once_with(
            None,
            "Hojas de conteo",
            ["hoja 1", "hoja 2"],
            unit_label="hoja",
            print_fn=print_fn,
        )

    def test_satellite_mode_skips_local_dialog(self) -> None:
        """En modo satelite las hojas se encolan y el dialogo local no se abre."""
        with patch(
            "pos_uniformes.ui.helpers.conteo_routing_helper."
            "maybe_route_conteo_to_satellite",
            return_value=True,
        ) as routed, patch(
            "pos_uniformes.ui.dialogs.conteo_print_dialog.open_tickets_print_dialog"
        ) as safe_dialog:
            open_conteo_print_dialog(None, "Hojas de conteo", ["hoja 1"])
        routed.assert_called_once()
        safe_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
