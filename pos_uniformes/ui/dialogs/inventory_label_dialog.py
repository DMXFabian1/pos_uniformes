"""Dialogo reutilizable para vista previa e impresion de etiquetas de inventario."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.inventory_label_preview_helper import (
    build_error_inventory_label_preview_view,
    build_inventory_label_mode_hint,
    build_inventory_label_preview_view,
    build_inventory_label_print_confirmation,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow
    from pos_uniformes.services.inventory_label_service import InventoryLabelContext
    from pos_uniformes.utils.label_generator import LabelRenderResult


def _build_inventory_label_dialog_styles() -> str:
    return """
        QWidget#inventoryLabelControlsCard, QWidget#inventoryLabelPreviewCard {
            background: #fbf6ee;
            border: 1px solid #e4d8c9;
            border-radius: 18px;
        }
        QLabel#inventoryLabelSectionTitle {
            color: #7e3a22;
            font-size: 15px;
            font-weight: 800;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelPreviewCaption, QLabel#inventoryLabelModeHint {
            color: #6f665f;
            font-size: 12px;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelPreviewImage {
            background: #fffdf9;
            border: 1px dashed #c5b8a7;
            border-radius: 18px;
            color: #857a70;
            padding: 18px;
        }
        QLabel#inventoryLabelSummaryCard {
            background: #fffaf2;
            border: 1px solid #e4d8c9;
            border-radius: 16px;
            color: #5f564d;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton#inventoryLabelNavButton {
            min-width: 110px;
            min-height: 34px;
            border-radius: 10px;
            padding: 6px 12px;
        }
    """


def build_inventory_label_dialog(
    window: "MainWindow",
    *,
    initial_context: "InventoryLabelContext",
    variant_ids: list[int],
    current_index: int,
    load_context: Callable[[int], "InventoryLabelContext"],
    render_label: Callable[[str, int], "LabelRenderResult"],
    print_label: Callable[[Path, int, str, QDialog | None], bool],
) -> None:
    dialog, layout = window._create_modal_dialog(
        "Imprimir etiqueta",
        "Prepara la vista previa de la etiqueta y confirma la impresion cuando el formato se vea correcto.",
        width=860,
    )
    dialog.resize(860, 680)
    dialog.setStyleSheet(_build_inventory_label_dialog_styles())
    layout.setSpacing(14)

    header_row = QHBoxLayout()
    header_row.setSpacing(10)
    header = QLabel("")
    header.setWordWrap(True)
    header.setObjectName("inventoryMetaCard")
    header_row.addWidget(header, 1)
    previous_button = QPushButton("Anterior")
    previous_button.setObjectName("inventoryLabelNavButton")
    previous_button.setAutoDefault(False)
    next_button = QPushButton("Siguiente")
    next_button.setObjectName("inventoryLabelNavButton")
    next_button.setAutoDefault(False)
    header_row.addWidget(previous_button)
    header_row.addWidget(next_button)
    layout.addLayout(header_row)

    controls_card = QWidget()
    controls_card.setObjectName("inventoryLabelControlsCard")
    controls_layout = QVBoxLayout(controls_card)
    controls_layout.setContentsMargins(16, 14, 16, 14)
    controls_layout.setSpacing(8)

    controls_title = QLabel("Formato de impresion")
    controls_title.setObjectName("inventoryLabelSectionTitle")
    controls_layout.addWidget(controls_title)

    controls = QGridLayout()
    controls.setHorizontalSpacing(14)
    controls.setVerticalSpacing(10)
    mode_combo = QComboBox()
    mode_combo.addItem("Normal", "standard")
    mode_combo.addItem("Split", "split")
    copies_spin = QSpinBox()
    copies_spin.setRange(1, 500)
    copies_spin.setValue(1)
    mode_hint = QLabel(build_inventory_label_mode_hint("standard"))
    mode_hint.setWordWrap(True)
    mode_hint.setObjectName("inventoryLabelModeHint")
    controls.addWidget(QLabel("Modo"), 0, 0)
    controls.addWidget(mode_combo, 0, 1)
    controls.addWidget(QLabel("Piezas / copias"), 0, 2)
    controls.addWidget(copies_spin, 0, 3)
    controls.addWidget(mode_hint, 1, 0, 1, 4)
    controls_layout.addLayout(controls)
    layout.addWidget(controls_card)

    preview_section_title = QLabel("Vista previa")
    preview_section_title.setObjectName("inventoryLabelSectionTitle")
    layout.addWidget(preview_section_title)

    preview_caption = QLabel(
        "La imagen se escala solo para esta vista. La impresion usa el archivo generado sin alterar su tamaño real."
    )
    preview_caption.setWordWrap(True)
    preview_caption.setObjectName("inventoryLabelPreviewCaption")
    layout.addWidget(preview_caption)

    preview_card = QWidget()
    preview_card.setObjectName("inventoryLabelPreviewCard")
    preview_card_layout = QVBoxLayout(preview_card)
    preview_card_layout.setContentsMargins(16, 16, 16, 16)
    preview_card_layout.setSpacing(10)

    preview_label = QLabel("Generando vista previa...")
    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview_label.setMinimumSize(640, 240)
    preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    preview_label.setObjectName("inventoryLabelPreviewImage")
    summary_label = QLabel("")
    summary_label.setWordWrap(True)
    summary_label.setObjectName("inventoryLabelSummaryCard")
    preview_card_layout.addWidget(preview_label, 1)
    preview_card_layout.addWidget(summary_label)
    layout.addWidget(preview_card, 1)

    buttons_layout = QHBoxLayout()
    buttons_layout.addStretch(1)
    close_button = QPushButton("Cerrar")
    close_button.setObjectName("secondaryButton")
    close_button.setAutoDefault(False)
    close_button.setDefault(False)
    print_button = QPushButton("Imprimir etiqueta")
    print_button.setObjectName("primaryButton")
    print_button.setDefault(True)
    print_button.setAutoDefault(True)
    buttons_layout.addWidget(close_button)
    buttons_layout.addWidget(print_button)
    preview_state: dict[str, LabelRenderResult | None] = {"result": None}
    dialog_state: dict[str, object] = {
        "variant_ids": [int(variant_id) for variant_id in variant_ids],
        "current_index": max(0, min(int(current_index), max(0, len(variant_ids) - 1))),
        "context": initial_context,
    }

    def apply_context(context: "InventoryLabelContext") -> None:
        header.setText(
            f"{context.sku} | {context.product_name} | talla {context.talla} | color {context.color}"
        )

    def refresh_navigation_buttons() -> None:
        current_position = int(dialog_state["current_index"])
        total = len(dialog_state["variant_ids"])
        previous_button.setEnabled(current_position > 0)
        next_button.setEnabled(current_position < total - 1)

    def refresh_preview() -> None:
        mode_hint.setText(build_inventory_label_mode_hint(str(mode_combo.currentData() or "standard")))
        try:
            result = render_label(
                str(mode_combo.currentData() or "standard"),
                int(copies_spin.value()),
            )
        except Exception as exc:  # noqa: BLE001
            preview_state["result"] = None
            preview_view = build_error_inventory_label_preview_view(str(exc))
            preview_label.clear()
            preview_label.setText(preview_view.preview_text)
            summary_label.setText(preview_view.summary_text)
            print_button.setEnabled(preview_view.print_enabled)
            return

        preview_state["result"] = result
        preview_view = build_inventory_label_preview_view(result)
        pixmap = QPixmap(str(result.image_path))
        if pixmap.isNull():
            preview_label.clear()
            preview_label.setText(preview_view.preview_text)
        else:
            scaled = pixmap.scaled(
                preview_label.contentsRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            preview_label.setText("")
            preview_label.setPixmap(scaled)
        summary_label.setText(preview_view.summary_text)
        print_button.setEnabled(preview_view.print_enabled)

    def navigate_variant(step: int) -> None:
        target_index = int(dialog_state["current_index"]) + step
        variant_id_list = dialog_state["variant_ids"]
        if target_index < 0 or target_index >= len(variant_id_list):
            return
        try:
            context = load_context(int(variant_id_list[target_index]))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Presentacion no disponible", str(exc))
            return
        dialog_state["current_index"] = target_index
        dialog_state["context"] = context
        apply_context(context)
        refresh_navigation_buttons()
        refresh_preview()

    def handle_print() -> None:
        result = preview_state.get("result")
        if result is None:
            refresh_preview()
            result = preview_state.get("result")
        if result is None:
            return
        context = dialog_state["context"]
        try:
            printed = print_label(
                result.image_path,
                int(result.effective_copies),
                str(context.sku),
                dialog,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Impresion fallida", str(exc))
            return
        if printed:
            QMessageBox.information(
                dialog,
                "Etiqueta enviada",
                build_inventory_label_print_confirmation(sku=str(context.sku), result=result),
            )

    mode_combo.currentIndexChanged.connect(lambda _: refresh_preview())
    copies_spin.valueChanged.connect(lambda _: refresh_preview())
    previous_button.clicked.connect(lambda: navigate_variant(-1))
    next_button.clicked.connect(lambda: navigate_variant(1))
    print_button.clicked.connect(handle_print)
    close_button.clicked.connect(dialog.reject)
    layout.addLayout(buttons_layout)
    apply_context(initial_context)
    refresh_navigation_buttons()
    refresh_preview()
    dialog.exec()
