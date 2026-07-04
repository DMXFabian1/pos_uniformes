"""Test del guard del timer de status en school_product_link_dialog.

Bug original: QTimer.singleShot(4000, lambda: self._status_label.setText(""))
podía disparar con el diálogo ya destruido → RuntimeError en slot → qFatal.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.dialogs.school_product_link_dialog import SchoolProductLinkDialog


class ClearStatusGuardTests(unittest.TestCase):
    """Se prueba el método sin ligar, con un stand-in que solo tiene
    _status_label (instanciar el QDialog completo requiere DB)."""

    def test_clear_status_swallows_runtime_error_of_dead_widget(self) -> None:
        dead_label = Mock()
        dead_label.setText.side_effect = RuntimeError(
            "wrapped C/C++ object of type QLabel has been deleted"
        )
        fake_dialog = SimpleNamespace(_status_label=dead_label)
        SchoolProductLinkDialog._clear_status(fake_dialog)  # no debe lanzar

    def test_clear_status_clears_live_widget(self) -> None:
        label = Mock()
        fake_dialog = SimpleNamespace(_status_label=label)
        SchoolProductLinkDialog._clear_status(fake_dialog)
        label.setText.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
