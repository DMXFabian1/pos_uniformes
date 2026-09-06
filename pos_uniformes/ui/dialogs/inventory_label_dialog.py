"""Dialogo reutilizable para vista previa e impresion de etiquetas de inventario."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.inventory_label_preview_helper import (
    build_error_inventory_label_preview_view,
    build_inventory_label_mode_hint,
    build_inventory_label_preview_view,
    build_inventory_label_print_confirmation,
)
from pos_uniformes.ui.helpers.scanner_enter_guard import ScannerEnterGuard

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow
    from pos_uniformes.services.inventory_label_service import InventoryLabelContext
    from pos_uniformes.utils.label_generator import LabelRenderResult


def _build_inventory_label_dialog_styles() -> str:
    return """
        QWidget#inventoryLabelControlsCard, QWidget#inventoryLabelPreviewCard {
            background: #fdfaf6;
            border: 1px solid #ddd0c0;
            border-radius: 18px;
        }
        QLabel#inventoryLabelSectionTitle {
            color: #7b2d14;
            font-size: 15px;
            font-weight: 800;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelPreviewCaption, QLabel#inventoryLabelModeHint {
            color: #7a6d60;
            font-size: 12px;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelPreviewImage {
            background: #fffdf8;
            border: 1px dashed #d5c9b9;
            border-radius: 18px;
            color: #7a6d60;
            padding: 18px;
        }
        QLabel#inventoryLabelSummaryCard {
            background: #fdf5ee;
            border: 1px solid #ddd0c0;
            border-radius: 16px;
            color: #5a4a3f;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton#inventoryLabelNavButton {
            min-width: 130px;
            min-height: 52px;
            border-radius: 14px;
            padding: 6px 16px;
            font-size: 16px;
            font-weight: 800;
        }
        /* Toggles de modo / precio: seleccionado = tinte claro + borde grueso */
        QPushButton#inventoryLabelToggle {
            background: #ffffff;
            color: #2c2a27;
            border: 2px solid #ddd0c0;
            border-radius: 14px;
            min-height: 54px;
            padding: 0 18px;
            font-size: 16px;
            font-weight: 700;
        }
        QPushButton#inventoryLabelToggle:checked {
            background: #f7e3d8;
            color: #73341c;
            border: 3px solid #a84f2d;
        }
        QPushButton#inventoryLabelStep {
            background: #ffffff;
            color: #2c2a27;
            border: 2px solid #ddd0c0;
            border-radius: 14px;
            min-width: 64px;
            max-width: 64px;
            min-height: 54px;
            font-size: 24px;
            font-weight: 800;
        }
        QPushButton#inventoryLabelStep:pressed { background: #f1e6d6; }
        QPushButton#inventoryLabelChip {
            background: #ffffff;
            color: #73341c;
            border: 1.5px solid #ddd0c0;
            border-radius: 12px;
            min-width: 44px;
            max-width: 44px;
            min-height: 40px;
            font-size: 15px;
            font-weight: 800;
        }
        QPushButton#inventoryLabelChip:checked {
            background: #f7e3d8;
            border: 2px solid #a84f2d;
        }
        QLabel#inventoryLabelCopies {
            font-size: 28px;
            font-weight: 800;
            color: #73341c;
            min-width: 64px;
            background: transparent;
            border: none;
        }
        QLabel#inventoryLabelFieldTitle {
            color: #7a6d60;
            font-size: 13px;
            font-weight: 700;
            background: transparent;
            border: none;
        }
        QPushButton#primaryButton, QPushButton#secondaryButton {
            min-height: 60px;
            font-size: 17px;
            font-weight: 800;
            border-radius: 14px;
            padding: 0 26px;
        }
        /* Colores explícitos (a prueba de modo oscuro y de hojas de estilo ajenas) */
        QPushButton#primaryButton { background: #a84f2d; color: #ffffff; border: none; }
        QPushButton#primaryButton:pressed { background: #8a4326; }
        QPushButton#primaryButton:disabled { background: #c9a996; color: #f4ede2; }
        QPushButton#secondaryButton, QPushButton#inventoryLabelNavButton {
            background: #f8f2e9; color: #73341c; border: 1px solid #ddd0c0;
        }
        QPushButton#secondaryButton:pressed, QPushButton#inventoryLabelNavButton:pressed {
            background: #e8dbc7;
        }
        QPushButton#inventoryLabelNavButton:disabled { color: #b3a794; background: #efe9de; }
    """


def build_inventory_label_dialog(
    window: "MainWindow",
    *,
    initial_context: "InventoryLabelContext",
    variant_ids: list[int],
    current_index: int,
    load_context: Callable[[int], "InventoryLabelContext"],
    render_label: Callable[[str, int, bool | None], "LabelRenderResult"],
    print_label: Callable[[Path, int, str, QDialog | None, str], bool],
) -> None:
    dialog, layout = window._create_modal_dialog(
        "Imprimir etiqueta",
        "Prepara la vista previa de la etiqueta y confirma la impresion cuando el formato se vea correcto.",
        width=860,
    )
    dialog.resize(860, 680)
    dialog.setStyleSheet(_build_inventory_label_dialog_styles())
    ScannerEnterGuard(dialog)
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

    # Rediseño táctil (2026-09-05): toggles grandes en vez de combo,
    # stepper −/+ en vez de spinbox y toggle en vez de checkbox.
    estado: dict[str, object] = {"mode": "standard", "copies": 1, "price": True}

    controls = QGridLayout()
    controls.setHorizontalSpacing(18)
    controls.setVerticalSpacing(8)

    modo_title = QLabel("Modo")
    modo_title.setObjectName("inventoryLabelFieldTitle")
    mode_row = QHBoxLayout()
    mode_row.setSpacing(8)
    mode_buttons: dict[str, QPushButton] = {}
    for texto, valor in (("Normal", "standard"), ("Split", "split"), ("Label", "dk1221")):
        btn = QPushButton(texto)
        btn.setObjectName("inventoryLabelToggle")
        btn.setCheckable(True)
        btn.setAutoDefault(False)
        mode_buttons[valor] = btn
        mode_row.addWidget(btn, 1)
    mode_buttons["standard"].setChecked(True)

    copias_title = QLabel("Piezas / copias")
    copias_title.setObjectName("inventoryLabelFieldTitle")
    copies_row = QHBoxLayout()
    copies_row.setSpacing(8)
    copies_minus = QPushButton("−")
    copies_minus.setObjectName("inventoryLabelStep")
    copies_minus.setAutoDefault(False)
    copies_label = QLabel("1")
    copies_label.setObjectName("inventoryLabelCopies")
    copies_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    copies_plus = QPushButton("+")
    copies_plus.setObjectName("inventoryLabelStep")
    copies_plus.setAutoDefault(False)
    # Mantener presionado cuenta solo (sin 20 taps)
    for btn in (copies_minus, copies_plus):
        btn.setAutoRepeat(True)
        btn.setAutoRepeatDelay(350)
        btn.setAutoRepeatInterval(70)
    copies_row.addWidget(copies_minus)
    copies_row.addWidget(copies_label)
    copies_row.addWidget(copies_plus)
    # Chips rápidos: un toque fija la cantidad
    chip_buttons: dict[int, QPushButton] = {}
    for n in (5, 10, 20, 50):
        chip = QPushButton(str(n))
        chip.setObjectName("inventoryLabelChip")
        chip.setAutoDefault(False)
        chip.setCheckable(True)
        chip_buttons[n] = chip
        copies_row.addWidget(chip)
    copies_row.addStretch(1)

    precio_title = QLabel("Precio en la etiqueta")
    precio_title.setObjectName("inventoryLabelFieldTitle")
    price_button = QPushButton("✓  💲 Mostrar precio")
    price_button.setObjectName("inventoryLabelToggle")
    price_button.setCheckable(True)
    price_button.setChecked(True)
    price_button.setAutoDefault(False)
    price_button.setToolTip("Incluir o quitar el precio de venta en la etiqueta impresa")

    mode_hint = QLabel(build_inventory_label_mode_hint("standard"))
    mode_hint.setWordWrap(True)
    mode_hint.setObjectName("inventoryLabelModeHint")

    controls.addWidget(modo_title, 0, 0)
    controls.addLayout(mode_row, 1, 0)
    controls.addWidget(copias_title, 0, 1)
    controls.addLayout(copies_row, 1, 1)
    controls.addWidget(precio_title, 0, 2)
    controls.addWidget(price_button, 1, 2)
    controls.addWidget(mode_hint, 2, 0, 1, 3)
    controls.setColumnStretch(0, 3)
    controls.setColumnStretch(1, 2)
    controls.setColumnStretch(2, 2)
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
        mode_hint.setText(build_inventory_label_mode_hint(str(estado["mode"])))
        show_price = bool(estado["price"])
        try:
            result = render_label(
                str(estado["mode"]),
                int(estado["copies"]),
                show_price,
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
                result.mode,
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

    def set_mode(valor: str) -> None:
        estado["mode"] = valor
        for v, btn in mode_buttons.items():
            btn.setChecked(v == valor)
        refresh_preview()

    # La vista previa se regenera 250 ms después del último cambio de
    # cantidad: mantener + presionado no re-renderiza la etiqueta 20 veces.
    from PyQt6.QtCore import QTimer

    preview_timer = QTimer(dialog)
    preview_timer.setSingleShot(True)
    preview_timer.setInterval(250)
    preview_timer.timeout.connect(refresh_preview)

    def _sync_chips() -> None:
        for n, chip in chip_buttons.items():
            chip.setChecked(int(estado["copies"]) == n)

    def set_copies_abs(valor: int) -> None:
        estado["copies"] = max(1, min(500, int(valor)))
        copies_label.setText(str(estado["copies"]))
        _sync_chips()
        preview_timer.start()

    def set_copies(delta: int) -> None:
        set_copies_abs(int(estado["copies"]) + delta)

    def toggle_price() -> None:
        estado["price"] = price_button.isChecked()
        price_button.setText("✓  💲 Mostrar precio" if estado["price"] else "💲 Mostrar precio")
        refresh_preview()

    for valor, btn in mode_buttons.items():
        btn.clicked.connect(lambda _=False, v=valor: set_mode(v))
    copies_minus.clicked.connect(lambda: set_copies(-1))
    copies_plus.clicked.connect(lambda: set_copies(1))
    for n, chip in chip_buttons.items():
        chip.clicked.connect(lambda _=False, v=n: set_copies_abs(v))
    price_button.clicked.connect(toggle_price)
    previous_button.clicked.connect(lambda: navigate_variant(-1))
    next_button.clicked.connect(lambda: navigate_variant(1))
    print_button.clicked.connect(handle_print)
    close_button.clicked.connect(dialog.reject)
    layout.addLayout(buttons_layout)
    apply_context(initial_context)
    refresh_navigation_buttons()
    refresh_preview()
    dialog.exec()
