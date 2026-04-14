"""Dialogo experimental para imprimir etiquetas por lote desde Inventario."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.inventory_label_preview_helper import build_inventory_label_mode_hint

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow
    from pos_uniformes.services.inventory_label_service import InventoryLabelContext
    from pos_uniformes.utils.label_generator import LabelRenderResult


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class _BatchQuantityTabNavigator(QObject):
    def __init__(
        self,
        *,
        mode_combo: QComboBox,
        quantity_spins: list[QSpinBox],
        close_button: QPushButton,
        print_button: QPushButton,
    ) -> None:
        super().__init__(close_button.window())
        self._mode_combo = mode_combo
        self._quantity_spins = quantity_spins
        self._close_button = close_button
        self._print_button = print_button

    def install(self) -> None:
        for quantity_spin in self._quantity_spins:
            quantity_spin.installEventFilter(self)
            line_edit = quantity_spin.lineEdit()
            if line_edit is not None:
                line_edit.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key_event = event
        if key_event.key() not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return super().eventFilter(watched, event)
        direction = -1 if key_event.key() == Qt.Key.Key_Backtab else 1
        owner_spin = self._resolve_spin_owner(watched)
        if owner_spin is None:
            return super().eventFilter(watched, event)
        return self._focus_relative_to(owner_spin, direction)

    def _resolve_spin_owner(self, watched: QObject) -> QSpinBox | None:
        if isinstance(watched, QSpinBox):
            return watched
        for quantity_spin in self._quantity_spins:
            if quantity_spin.lineEdit() is watched:
                return quantity_spin
        return None

    def _focus_relative_to(self, source_spin: QSpinBox, direction: int) -> bool:
        try:
            current_index = self._quantity_spins.index(source_spin)
        except ValueError:
            return False
        if direction > 0:
            if current_index + 1 < len(self._quantity_spins):
                target: QWidget = self._quantity_spins[current_index + 1]
            else:
                target = self._close_button
        else:
            if current_index - 1 >= 0:
                target = self._quantity_spins[current_index - 1]
            else:
                target = self._mode_combo
        target.setFocus(Qt.FocusReason.TabFocusReason)
        if isinstance(target, QSpinBox):
            line_edit = target.lineEdit()
            if line_edit is not None:
                line_edit.selectAll()
        return True


def build_inventory_label_batch_dialog(
    window: "MainWindow",
    *,
    contexts: list["InventoryLabelContext"],
    render_label: Callable[[int, str, int], "LabelRenderResult"],
    print_label: Callable[[Path, int, str, QDialog | None], bool],
) -> None:
    dialog, layout = window._create_modal_dialog(
        "Imprimir etiquetas por lote",
        "Experimental: ajusta cuantas piezas imprimir por presentacion y usa el mismo motor de etiquetas actual.",
        width=980,
    )
    dialog.resize(980, 660)
    layout.setSpacing(14)

    controls_layout = QGridLayout()
    controls_layout.setHorizontalSpacing(12)
    controls_layout.setVerticalSpacing(8)
    mode_combo = QComboBox()
    mode_combo.addItem("Normal", "standard")
    mode_combo.addItem("Split", "split")
    mode_hint = QLabel(build_inventory_label_mode_hint("standard"))
    mode_hint.setWordWrap(True)
    mode_hint.setObjectName("subtleLine")
    controls_layout.addWidget(QLabel("Modo de impresion"), 0, 0)
    controls_layout.addWidget(mode_combo, 0, 1)
    controls_layout.addWidget(mode_hint, 1, 0, 1, 2)
    layout.addLayout(controls_layout)

    table = QTableWidget()
    table.setObjectName("inventoryLabelBatchTable")
    table.setColumnCount(5)
    table.setHorizontalHeaderLabels(["SKU", "Producto", "Talla", "Color", "Cantidad"])
    table.setRowCount(len(contexts))
    table.verticalHeader().setVisible(False)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setMinimumHeight(320)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(False)

    quantity_spins: list[QSpinBox] = []
    for row_index, context in enumerate(contexts):
        table.setItem(row_index, 0, _table_item(context.sku))
        table.setItem(row_index, 1, _table_item(context.product_name))
        table.setItem(row_index, 2, _table_item(context.talla))
        table.setItem(row_index, 3, _table_item(context.color))
        quantity_spin = QSpinBox()
        quantity_spin.setRange(0, 500)
        quantity_spin.setValue(1)
        quantity_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_index, 4, quantity_spin)
        quantity_spins.append(quantity_spin)
    layout.addWidget(table, 1)

    summary_label = QLabel("")
    summary_label.setObjectName("inventoryMetaCard")
    summary_label.setWordWrap(True)
    layout.addWidget(summary_label)

    buttons_layout = QHBoxLayout()
    buttons_layout.addStretch(1)
    close_button = QPushButton("Cerrar")
    close_button.setObjectName("secondaryButton")
    print_button = QPushButton("Imprimir lote")
    print_button.setObjectName("primaryButton")
    buttons_layout.addWidget(close_button)
    buttons_layout.addWidget(print_button)
    layout.addLayout(buttons_layout)

    def selected_jobs() -> list[tuple["InventoryLabelContext", int]]:
        jobs: list[tuple["InventoryLabelContext", int]] = []
        for context, quantity_spin in zip(contexts, quantity_spins, strict=False):
            quantity = int(quantity_spin.value())
            if quantity > 0:
                jobs.append((context, quantity))
        return jobs

    def refresh_summary() -> None:
        jobs = selected_jobs()
        total_pieces = sum(quantity for _context, quantity in jobs)
        summary_label.setText(
            f"Presentaciones activas: {len(jobs)} | Piezas solicitadas: {total_pieces} | "
            f"Modo: {mode_combo.currentText()}"
        )

    def handle_print() -> None:
        jobs = selected_jobs()
        if not jobs:
            QMessageBox.warning(
                dialog,
                "Sin piezas",
                "Captura al menos una cantidad mayor a cero para imprimir el lote.",
            )
            return
        success_lines: list[str] = []
        failed_lines: list[str] = []
        selected_mode = str(mode_combo.currentData() or "standard")
        for context, requested_copies in jobs:
            try:
                result = render_label(int(context.variant_id), selected_mode, requested_copies)
                printed = print_label(
                    result.image_path,
                    int(result.effective_copies),
                    str(context.sku),
                    dialog,
                )
            except Exception as exc:  # noqa: BLE001
                failed_lines.append(f"{context.sku}: {exc}")
                continue
            if printed:
                success_lines.append(
                    f"{context.sku}: {requested_copies} pieza(s) -> {result.effective_copies} copia(s)/hoja(s)"
                )
            else:
                failed_lines.append(f"{context.sku}: impresion cancelada")
        message_parts = []
        if success_lines:
            message_parts.append("Impresiones enviadas:\n" + "\n".join(success_lines))
        if failed_lines:
            message_parts.append("Pendientes o fallidas:\n" + "\n".join(failed_lines))
        if failed_lines:
            QMessageBox.warning(dialog, "Lote enviado con incidencias", "\n\n".join(message_parts))
        else:
            QMessageBox.information(dialog, "Lote enviado", "\n\n".join(message_parts))

    mode_combo.currentIndexChanged.connect(lambda _: mode_hint.setText(build_inventory_label_mode_hint(str(mode_combo.currentData() or "standard"))))
    mode_combo.currentIndexChanged.connect(lambda _: refresh_summary())
    for quantity_spin in quantity_spins:
        quantity_spin.valueChanged.connect(lambda _value: refresh_summary())
    close_button.clicked.connect(dialog.reject)
    print_button.clicked.connect(handle_print)

    # Fuerza una captura por teclado predecible en la prueba de impresion por lote.
    previous_tab_widget: QWidget = mode_combo
    for quantity_spin in quantity_spins:
        QWidget.setTabOrder(previous_tab_widget, quantity_spin)
        previous_tab_widget = quantity_spin
    QWidget.setTabOrder(previous_tab_widget, close_button)
    QWidget.setTabOrder(close_button, print_button)
    tab_navigator = _BatchQuantityTabNavigator(
        mode_combo=mode_combo,
        quantity_spins=quantity_spins,
        close_button=close_button,
        print_button=print_button,
    )
    tab_navigator.install()
    dialog._batch_tab_navigator = tab_navigator

    refresh_summary()
    dialog.exec()
