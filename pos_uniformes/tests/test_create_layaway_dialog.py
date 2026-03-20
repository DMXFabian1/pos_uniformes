from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.create_layaway_dialog import build_create_layaway_dialog


class _DialogHost(QWidget):
    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        return dialog, layout


class CreateLayawayDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_returns_none_when_cancelled(self) -> None:
        host = _DialogHost()
        with patch("pos_uniformes.ui.dialogs.create_layaway_dialog.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                build_create_layaway_dialog(
                    host,
                    initial_items=[],
                    selected_catalog_row=None,
                )
            )

    def test_return_pressed_on_sku_adds_item_before_accept(self) -> None:
        host = _DialogHost()

        class _SessionContext:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_variant = type(
            "FakeVariant",
            (),
            {
                "producto": type("FakeProduct", (), {"nombre": "Playera Blanca"})(),
                "precio_venta": Decimal("175.00"),
            },
        )()

        def fake_exec(dialog: QDialog) -> int:
            sku_input = next(widget for widget in dialog.findChildren(QLineEdit) if widget.placeholderText() == "SKU")
            sku_input.setText("sku003941")
            sku_input.returnPressed.emit()
            return int(QDialog.DialogCode.Accepted)

        with patch("pos_uniformes.ui.dialogs.create_layaway_dialog.get_session", return_value=_SessionContext()), \
            patch("pos_uniformes.ui.dialogs.create_layaway_dialog.ClientService.list_clients", return_value=[]), \
            patch("pos_uniformes.ui.dialogs.create_layaway_dialog.ApartadoService.obtener_variante_por_sku", return_value=fake_variant), \
            patch("pos_uniformes.ui.dialogs.create_layaway_dialog.InventarioService.validar_stock_disponible", return_value=None), \
            patch("pos_uniformes.ui.dialogs.create_layaway_dialog.QDialog.exec", new=fake_exec):
            payload = build_create_layaway_dialog(
                host,
                initial_items=[],
                selected_catalog_row=None,
            )

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0].sku, "SKU003941")
        self.assertEqual(payload["items"][0].cantidad, 1)


if __name__ == "__main__":
    unittest.main()
