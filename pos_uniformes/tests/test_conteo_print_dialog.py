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
        with patch(
            "pos_uniformes.ui.dialogs.conteo_print_dialog.open_tickets_print_dialog"
        ) as safe_dialog:
            open_conteo_print_dialog(None, "Hojas de conteo", ["hoja 1", "hoja 2"])
        safe_dialog.assert_called_once_with(
            None, "Hojas de conteo", ["hoja 1", "hoja 2"], unit_label="hoja"
        )


if __name__ == "__main__":
    unittest.main()
