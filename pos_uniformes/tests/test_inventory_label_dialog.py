from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
from pos_uniformes.utils.label_generator import LabelRenderResult


class _DialogHost(QWidget):
    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
        layout = QVBoxLayout()
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        dialog.setLayout(layout)
        return dialog, layout


class InventoryLabelDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_inventory_label_dialog_renders_initial_preview_before_exec(self) -> None:
        host = _DialogHost()
        render_calls: list[tuple[str, int]] = []
        captured: dict[str, QDialog] = {}
        contexts = {
            1: SimpleNamespace(
                variant_id=1,
                sku="SKU-001",
                product_name="Pants Deportivo",
                talla="14",
                color="Azul Marino",
            ),
            2: SimpleNamespace(
                variant_id=2,
                sku="SKU-002",
                product_name="Pants Deportivo",
                talla="16",
                color="Negro",
            ),
        }
        dialog_variant_state = {"variant_id": 1}
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"not-a-real-png")

            def render_label(mode: str, requested_copies: int, show_price: bool | None = None) -> LabelRenderResult:
                render_calls.append((mode, requested_copies))
                return LabelRenderResult(
                    mode=mode,
                    image_path=image_path,
                    effective_copies=requested_copies,
                    requested_copies=requested_copies,
                )

            def load_context(variant_id: int):
                dialog_variant_state["variant_id"] = variant_id
                return contexts[variant_id]

            def fake_exec(dialog: QDialog) -> int:
                captured["dialog"] = dialog
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_dialog.QDialog.exec", new=fake_exec):
                build_inventory_label_dialog(
                    host,
                    initial_context=contexts[1],
                    variant_ids=[1, 2],
                    current_index=0,
                    load_context=load_context,
                    render_label=render_label,
                    print_label=lambda _path, _copies, _sku, _dialog: True,
                )

        self.assertEqual(render_calls, [("dk1221", 1)])          # la cuadrada es la de todos los días
        dialog = captured["dialog"]
        preview_label = dialog.findChild(QLabel, "inventoryLabelPreviewImage")
        self.assertIsNotNone(preview_label)
        self.assertGreaterEqual(preview_label.minimumWidth(), 400)
        mode_hint = dialog.findChild(QLabel, "inventoryLabelModeHint")
        self.assertIsNotNone(mode_hint)
        self.assertIn("etiqueta por pieza", mode_hint.text())
        print_button = dialog.findChild(QPushButton, "primaryButton")
        self.assertIsNotNone(print_button)
        self.assertEqual(print_button.text(), "Imprimir 1 etiqueta")     # el botón dice cuántas
        next_button = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Siguiente")
        next_button.click()
        self.assertEqual(dialog_variant_state["variant_id"], 2)
        self.assertEqual(render_calls, [("dk1221", 1), ("dk1221", 1)])
        self.assertEqual(dialog.findChild(QLabel, "inventoryLabelNombre").text(), "Pants Deportivo")
        self.assertEqual(dialog.findChild(QLabel, "inventoryLabelPosicion").text(), "2 de 2")
        self.assertIn("SKU-002", dialog.findChild(QLabel, "inventoryMetaCard").text())

    def test_con_una_sola_presentacion_no_se_ofrece_navegar(self) -> None:
        host = _DialogHost()
        captured: dict[str, QDialog] = {}
        contexto = SimpleNamespace(variant_id=1, sku="SKU-001", product_name="Pijama CN", talla="Unitalla", color="Sin color")
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"x")

            def fake_exec(dialog: QDialog) -> int:
                captured["dialog"] = dialog
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_dialog.QDialog.exec", new=fake_exec):
                build_inventory_label_dialog(
                    host, initial_context=contexto, variant_ids=[1], current_index=0, load_context=lambda _i: contexto,
                    render_label=lambda mode, copies, show_price=None: LabelRenderResult(
                        mode=mode, image_path=image_path, effective_copies=copies, requested_copies=copies),
                    print_label=lambda *_a: True,
                )
        dialog = captured["dialog"]
        for texto in ("Anterior", "Siguiente"):
            self.assertTrue(next(b for b in dialog.findChildren(QPushButton) if b.text() == texto).isHidden())
        self.assertTrue(dialog.findChild(QLabel, "inventoryLabelPosicion").isHidden())
        # «Sin color» no es un dato: no se enseña.
        self.assertEqual(dialog.findChild(QLabel, "inventoryMetaCard").text(), "Talla Unitalla   ·   SKU-001")


if __name__ == "__main__":
    unittest.main()


class InventoryLabelDialogTouchTests(unittest.TestCase):
    """Rediseño táctil: modo por toggles, copias con −/+, precio como toggle."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_en_un_uniforme_ni_aparece_la_opcion_de_precio(self) -> None:
        """El precio de un uniforme cambia; para eso está el QR. El botón salía
        marcado y no hacía nada: ahora no se ofrece (Daniel, 2026-11-05)."""
        host = _DialogHost()
        render_calls: list[tuple[str, int, bool | None]] = []
        captured: dict[str, QDialog] = {}
        uniforme = SimpleNamespace(variant_id=1, sku="SKU-001", product_name="Pants", talla="14", color="Azul", precio_por_defecto=False)
        ropa = SimpleNamespace(variant_id=2, sku="SKU-002", product_name="Pijama", talla="Unitalla", color="Surtido", precio_por_defecto=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"x")

            def render_label(mode, copies, show_price=None):
                render_calls.append((mode, copies, show_price))
                return LabelRenderResult(mode=mode, image_path=image_path,
                                         effective_copies=copies, requested_copies=copies)

            def fake_exec(dialog):
                captured["dialog"] = dialog
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_dialog.QDialog.exec", new=fake_exec):
                build_inventory_label_dialog(
                    host, initial_context=uniforme, variant_ids=[1, 2], current_index=0,
                    load_context=lambda i: ropa if int(i) == 2 else uniforme, render_label=render_label,
                    print_label=lambda *_a: True,
                )
            dialog = captured["dialog"]
            precio = next(b for b in dialog.findChildren(QPushButton) if "Mostrar precio" in b.text())
            titulo = next(lbl for lbl in dialog.findChildren(QLabel) if lbl.text() == "PRECIO EN LA ETIQUETA")
            self.assertTrue(precio.isHidden())                         # ni el botón…
            self.assertTrue(titulo.isHidden())                         # …ni su título
            self.assertEqual(render_calls[-1], ("dk1221", 1, False))
            # Al pasar a una prenda de ropa normal vuelve, prendido.
            next(b for b in dialog.findChildren(QPushButton) if b.text() == "Siguiente").click()
            self.assertFalse(precio.isHidden())
            self.assertFalse(titulo.isHidden())
            self.assertTrue(precio.isChecked())
            self.assertEqual(render_calls[-1], ("dk1221", 1, True))

    def test_toggles_alimentan_el_render(self) -> None:
        host = _DialogHost()
        render_calls: list[tuple[str, int, bool | None]] = []
        captured: dict[str, QDialog] = {}
        contexto = SimpleNamespace(variant_id=1, sku="SKU-001", product_name="Pants", talla="14", color="Azul")
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"x")

            def render_label(mode, copies, show_price=None):
                render_calls.append((mode, copies, show_price))
                return LabelRenderResult(mode=mode, image_path=image_path,
                                         effective_copies=copies, requested_copies=copies)

            def fake_exec(dialog):
                captured["dialog"] = dialog
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_dialog.QDialog.exec", new=fake_exec):
                build_inventory_label_dialog(
                    host, initial_context=contexto, variant_ids=[1], current_index=0,
                    load_context=lambda _i: contexto, render_label=render_label,
                    print_label=lambda *_a: True,
                )
            dialog = captured["dialog"]
            botones = {b.text().split("\n")[0]: b for b in dialog.findChildren(QPushButton)}
            botones["Tira de 4"].click()
            botones["+"].click()
            botones["+"].click()
            botones["−"].click()
            # El render de copias va con retraso (debounce de 250 ms). Se dispara
            # su timer a mano en vez de esperar con `QTest.qWait`: bombear el
            # bucle de eventos aquí dejaba entrar cosas de otras pruebas y el
            # proceso se caía al azar en la suite en paralelo (2026-09-22).
            timer = next(t for t in dialog.findChildren(QTimer) if t.isSingleShot() and t.interval() == 250)
            timer.stop()
            timer.timeout.emit()
            botones["✓  💲 Mostrar precio"].click()  # apaga el precio

            self.assertEqual(render_calls[0], ("dk1221", 1, True))
            self.assertEqual(render_calls[1][0], "split")
            self.assertEqual(render_calls[-1], ("split", 2, False))
            self.assertTrue(botones["Tira de 4"].isChecked())
            self.assertFalse(botones["Cuadrada"].isChecked())
            self.assertFalse(botones["Grande"].isChecked())
            self.assertEqual(dialog.findChild(QPushButton, "primaryButton").text(), "Imprimir 2 hojas")   # el render de prueba devuelve una hoja por pieza

            # Chip rápido: un toque fija 20 copias (y el chip queda marcado)
            botones["20"].click()
            timer.stop(); timer.timeout.emit()
            self.assertEqual(render_calls[-1], ("split", 20, False))
            self.assertTrue(botones["20"].isChecked())
            # Mantener presionado: los botones cuentan solos
            self.assertTrue(botones["+"].autoRepeat())
