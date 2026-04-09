"""Dialogo V1 para conteo fisico rapido por SKU."""

from __future__ import annotations

from uuid import uuid4

from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.inventory_count_service import (
    InventoryCountRow,
    InventoryCountVariantView,
    accumulate_inventory_count_scan,
    build_inventory_count_payload,
    build_inventory_count_row,
    load_inventory_count_variant_by_sku,
    remove_inventory_count_row,
    update_inventory_count_row_counted_stock,
    upsert_inventory_count_row,
)
from pos_uniformes.ui.helpers.inventory_count_view_helper import build_inventory_count_batch_view


def prompt_inventory_count_data(
    parent=None,
    *,
    initial_rows: list[InventoryCountRow] | None = None,
    initial_context_label: str | None = None,
) -> dict[str, object] | None:
    dialog = InventoryCountDialog(
        parent=parent,
        initial_rows=initial_rows,
        initial_context_label=initial_context_label,
    )
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dialog.get_result()


class InventoryCountDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_rows: list[InventoryCountRow] | None = None,
        initial_context_label: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected_variant: InventoryCountVariantView | None = None
        self._rows: list[InventoryCountRow] = list(initial_rows or [])
        self._initial_context_label = str(initial_context_label or "").strip()
        self._scan_accumulation_enabled = not bool(initial_rows)
        self._result: dict[str, object] | None = None
        self._reference_value = f"CONTEO-{uuid4().hex[:8].upper()}"
        self.setWindowTitle("Conteo fisico")
        self.setModal(True)
        self.resize(960, 720)
        self._build_ui()
        self._refresh_selected_variant_card()
        self._refresh_batch_table()
        self._clear_batch_selection()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        helper = QLabel(
            "Conteo rapido por SKU. Sin lote previo, cada escaneo suma 1 al contado; con lote base desde Inventario, puedes revisar y corregir fila por fila."
        )
        helper.setWordWrap(True)
        helper.setObjectName("analyticsLine")
        helper.setStyleSheet("padding: 2px 0; color: #5f6d78;")
        helper.setVisible(False)
        layout.addWidget(helper)

        self.initial_context_label = QLabel("")
        self.initial_context_label.setObjectName("analyticsLine")
        self.initial_context_label.setWordWrap(True)
        self.initial_context_label.setStyleSheet(
            "padding: 6px 10px; border-radius: 12px; background: #eef5fb; color: #4a6072; border: 1px solid #d1e1ee;"
        )
        self.initial_context_label.setVisible(False)
        layout.addWidget(self.initial_context_label)

        control_card = QFrame()
        control_card.setObjectName("infoSubcard")
        control_layout = QGridLayout()
        control_layout.setContentsMargins(14, 12, 14, 12)
        control_layout.setHorizontalSpacing(12)
        control_layout.setVerticalSpacing(10)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Escanea o captura SKU")
        self.sku_input.setClearButtonEnabled(True)
        self.sku_input.returnPressed.connect(self._handle_lookup_sku)
        self.lookup_button = QPushButton("Escanear")
        self.lookup_button.setObjectName("toolbarSecondaryButton")
        self.lookup_button.clicked.connect(self._handle_lookup_sku)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.sku_input, 1)
        search_row.addWidget(self.lookup_button)
        control_layout.addLayout(search_row, 0, 0, 1, 2)

        self.variant_title_label = QLabel("Sin SKU cargado.")
        self.variant_title_label.setObjectName("inventoryTitle")
        self.variant_meta_label = QLabel("Escanea una presentacion para cargar su stock actual.")
        self.variant_meta_label.setObjectName("inventoryMetaCard")
        self.variant_meta_label.setWordWrap(True)
        self.variant_stock_label = QLabel("Sistema: -")
        self.variant_stock_label.setObjectName("analyticsLine")
        self.variant_meta_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #eef5fb; color: #294f69; border: 1px solid #d1e1ee;"
        )
        self.variant_stock_label.setStyleSheet(
            "padding: 6px 10px; border-radius: 10px; background: #f5f9fc; color: #5a6b78; border: 1px solid #dbe6ef;"
        )

        variant_card = QFrame()
        variant_card.setObjectName("infoSubcard")
        variant_layout = QVBoxLayout()
        variant_layout.setContentsMargins(0, 0, 0, 0)
        variant_layout.setSpacing(6)
        variant_layout.addWidget(self.variant_title_label)
        variant_layout.addWidget(self.variant_meta_label)
        variant_layout.addWidget(self.variant_stock_label)
        variant_card.setLayout(variant_layout)

        manual_card = QFrame()
        manual_card.setObjectName("infoSubcard")
        manual_layout = QVBoxLayout()
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)
        manual_label = QLabel("Correccion manual")
        manual_label.setObjectName("inventoryFilterLabel")
        self.counted_spin = QSpinBox()
        self.counted_spin.setRange(0, 100000)
        self.counted_spin.setEnabled(False)
        self.counted_spin.setMinimumWidth(140)
        self.add_button = QPushButton("Aplicar contado manual")
        self.add_button.setObjectName("toolbarPrimaryButton")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._handle_add_to_batch)
        manual_hint = QLabel("Usa este ajuste si necesitas corregir una fila sin volver a escanear.")
        manual_hint.setObjectName("analyticsLine")
        manual_hint.setWordWrap(True)
        manual_hint.setStyleSheet("color: #6b7b88; padding: 2px 0;")
        manual_layout.addWidget(manual_label)
        manual_layout.addWidget(self.counted_spin)
        manual_layout.addWidget(self.add_button)
        manual_layout.addWidget(manual_hint)
        manual_layout.addStretch(1)
        manual_card.setLayout(manual_layout)

        control_layout.addWidget(variant_card, 1, 0)
        control_layout.addWidget(manual_card, 1, 1)
        control_layout.setColumnStretch(0, 3)
        control_layout.setColumnStretch(1, 1)
        control_card.setLayout(control_layout)
        layout.addWidget(control_card)

        self.batch_status_label = QLabel("")
        self.batch_status_label.setObjectName("analyticsLine")
        self.batch_status_label.setWordWrap(True)
        self.batch_status_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #eef5fb; color: #4f6475; border: 1px solid #d1e1ee;"
        )
        layout.addWidget(self.batch_status_label)

        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(5)
        self.batch_table.setHorizontalHeaderLabels(["SKU", "Producto", "Sistema", "Contado", "Diferencia"])
        self.batch_table.setObjectName("dataTable")
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setSelectionBehavior(self.batch_table.SelectionBehavior.SelectRows)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setMinimumHeight(340)
        self.batch_table.installEventFilter(self)
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)
        self.clear_batch_selection_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.batch_table)
        self.clear_batch_selection_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.clear_batch_selection_shortcut.activated.connect(self._clear_batch_selection)
        layout.addWidget(self.batch_table)

        self.batch_summary_label = QLabel("")
        self.batch_summary_label.setObjectName("analyticsLine")
        self.batch_summary_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #eef5fb; color: #4f6475; border: 1px solid #d1e1ee;"
        )
        layout.addWidget(self.batch_summary_label)

        footer_card = QFrame()
        footer_card.setObjectName("infoSubcard")
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(12)
        footer_form = QFormLayout()
        footer_form.setSpacing(8)
        self.reference_input = QLineEdit()
        self.reference_input.setText(self._reference_value)
        self.reference_input.setReadOnly(True)
        self.observation_input = QLineEdit()
        self.observation_input.setPlaceholderText("Conteo de piso, almacen o revision puntual")
        footer_form.addRow("Referencia", self.reference_input)
        footer_form.addRow("Observacion", self.observation_input)
        footer_layout.addLayout(footer_form, 1)

        actions_column = QVBoxLayout()
        actions_column.setSpacing(8)
        self.remove_button = QPushButton("Quitar fila")
        self.remove_button.setObjectName("toolbarGhostButton")
        self.remove_button.clicked.connect(self._handle_remove_selected_row)
        actions_column.addWidget(self.remove_button)
        actions_column.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Aplicar lote")
            ok_button.clicked.connect(self._handle_confirm)
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
            cancel_button.clicked.connect(self.reject)
        actions_column.addWidget(buttons)
        footer_layout.addLayout(actions_column)
        footer_card.setLayout(footer_layout)
        layout.addWidget(footer_card)

        self.setLayout(layout)
        self.sku_input.setFocus()

    def _handle_lookup_sku(self) -> None:
        sku = self.sku_input.text().strip()
        if not sku:
            self.variant_title_label.setText("Sin SKU cargado.")
            self.variant_meta_label.setText("Captura un SKU para buscar la presentacion.")
            self.variant_stock_label.setText("Sistema: -")
            self.counted_spin.setEnabled(False)
            self.add_button.setEnabled(False)
            self.sku_input.setFocus()
            return

        with get_session() as session:
            variant = load_inventory_count_variant_by_sku(session, sku)

        if variant is None:
            QMessageBox.information(self, "SKU no encontrado", f"No se encontro una presentacion para '{sku}'.")
            self._selected_variant = None
            self._refresh_selected_variant_card()
            self.sku_input.selectAll()
            self.sku_input.setFocus()
            return

        if self._scan_accumulation_enabled:
            self._selected_variant = variant
            self._rows = accumulate_inventory_count_scan(
                self._rows,
                variant=variant,
                step=1,
            )
            current_row = next(
                (row for row in self._rows if int(row.variante_id) == int(variant.variante_id)),
                None,
            )
            self._refresh_selected_variant_card()
            if current_row is not None:
                self.counted_spin.setValue(int(current_row.stock_contado))
            self.counted_spin.setEnabled(True)
            self.add_button.setEnabled(True)
            self._refresh_batch_table()
            self._clear_batch_selection()
            if current_row is not None:
                self.batch_status_label.setText(
                    f"Escaneo acumulado: {variant.sku} | contado {current_row.stock_contado} | sistema {current_row.stock_sistema} | delta {current_row.delta:+d}"
                )
            self.sku_input.clear()
            self.sku_input.setFocus()
            return

        self._selected_variant = variant
        self._refresh_selected_variant_card()
        self.counted_spin.setValue(int(variant.stock_actual))
        self.counted_spin.setEnabled(True)
        self.add_button.setEnabled(True)
        self.counted_spin.setFocus()
        self.counted_spin.selectAll()

    def _handle_add_to_batch(self) -> None:
        if self._selected_variant is None:
            return

        new_row = build_inventory_count_row(
            self._selected_variant,
            counted_stock=self.counted_spin.value(),
        )
        existed_before = any(int(row.variante_id) == int(new_row.variante_id) for row in self._rows)
        self._rows = upsert_inventory_count_row(self._rows, new_row)
        self._refresh_batch_table()
        self._clear_batch_selection()
        QMessageBox.information(
            self,
            "Lote actualizado",
            (
                f"SKU {new_row.sku} {'actualizado' if existed_before else 'agregado'} al lote.\n"
                f"Sistema: {new_row.stock_sistema}\n"
                f"Contado: {new_row.stock_contado}\n"
                f"Diferencia: {new_row.delta:+d}"
            ),
        )
        self.sku_input.clear()
        self._selected_variant = None
        self._refresh_selected_variant_card()
        self.counted_spin.setValue(0)
        self.counted_spin.setEnabled(False)
        self.add_button.setEnabled(False)
        self.sku_input.setFocus()

    def _handle_remove_selected_row(self) -> None:
        current_row = self.batch_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Sin fila", "Selecciona una fila del lote para quitarla.")
            return
        item = self.batch_table.item(current_row, 0)
        if item is None:
            return
        variante_id = item.data(Qt.ItemDataRole.UserRole)
        if variante_id is None:
            return
        self._rows = remove_inventory_count_row(self._rows, variante_id=int(variante_id))
        self._refresh_batch_table()
        self._clear_batch_selection()

    def _refresh_selected_variant_card(self) -> None:
        if self._selected_variant is None:
            self.variant_title_label.setText("Sin SKU cargado.")
            self.variant_meta_label.setText("Escanea una presentacion para cargar su stock actual.")
            self.variant_stock_label.setText("Sistema: -")
            return

        variant = self._selected_variant
        self.variant_title_label.setText(f"{variant.sku} | {variant.producto_nombre}")
        self.variant_meta_label.setText(
            f"Escuela {variant.escuela_nombre} | Talla {variant.talla} | Color {variant.color}"
        )
        self.variant_stock_label.setText(f"Sistema: {variant.stock_actual}")

    def _refresh_batch_table(self) -> None:
        batch_view = build_inventory_count_batch_view(self._rows)
        self.batch_table.setRowCount(len(batch_view.rows))
        for row_index, row in enumerate(batch_view.rows):
            self._apply_batch_table_row(row_index, row)
        self._refresh_batch_meta(batch_view)

    def _apply_batch_table_row(self, row_index: int, row) -> None:
        sku_item = QTableWidgetItem(str(row.values[0]))
        sku_item.setData(Qt.ItemDataRole.UserRole, row.variante_id)
        self.batch_table.setItem(row_index, 0, sku_item)
        self.batch_table.setItem(row_index, 1, QTableWidgetItem(str(row.values[1])))
        self.batch_table.setItem(row_index, 2, QTableWidgetItem(str(row.values[2])))
        counted_spin = self.batch_table.cellWidget(row_index, 3)
        if not isinstance(counted_spin, QSpinBox):
            counted_spin = QSpinBox()
            counted_spin.setRange(0, 100000)
            counted_spin.installEventFilter(self)
            counted_line_edit = counted_spin.lineEdit()
            if counted_line_edit is not None:
                counted_line_edit.installEventFilter(self)
            counted_spin.valueChanged.connect(
                lambda value, variante_id=row.variante_id: self._handle_batch_count_changed(
                    variante_id=int(variante_id),
                    counted_stock=int(value),
                )
            )
            self.batch_table.setCellWidget(row_index, 3, counted_spin)
        counted_spin.blockSignals(True)
        counted_spin.setValue(int(row.values[3]))
        counted_spin.blockSignals(False)
        self.batch_table.setItem(row_index, 4, QTableWidgetItem(str(row.values[4])))

    def _refresh_batch_meta(self, batch_view) -> None:
        self.batch_summary_label.setText(batch_view.summary_label)
        self.batch_status_label.setText(batch_view.status_label)
        if self._initial_context_label:
            self.initial_context_label.setText(
                f"Lote base: {self._initial_context_label}. Puedes ajustar el contado por fila o seguir agregando SKU."
            )
        elif self._scan_accumulation_enabled:
            self.initial_context_label.setText(
                "Modo escaneo acumulado: cada SKU suma 1 al contado. Usa el campo manual solo si necesitas corregir una fila."
            )
        else:
            self.initial_context_label.setText("Escanea SKU para construir o complementar el lote.")
        self.remove_button.setEnabled(bool(batch_view.rows))

    def _handle_batch_count_changed(self, *, variante_id: int, counted_stock: int) -> None:
        self._rows = update_inventory_count_row_counted_stock(
            self._rows,
            variante_id=int(variante_id),
            counted_stock=int(counted_stock),
        )
        batch_view = build_inventory_count_batch_view(self._rows)
        for row_index, row in enumerate(batch_view.rows):
            if int(row.variante_id) == int(variante_id):
                self._apply_batch_table_row(row_index, row)
                break
        self._refresh_batch_meta(batch_view)

    def _clear_batch_selection(self) -> None:
        current_focus = self.focusWidget()
        if self._is_batch_table_widget(current_focus):
            current_focus.clearFocus()
        for row_index in range(self.batch_table.rowCount()):
            counted_spin = self.batch_table.cellWidget(row_index, 3)
            if isinstance(counted_spin, QSpinBox):
                counted_spin.clearFocus()
                counted_line_edit = counted_spin.lineEdit()
                if counted_line_edit is not None:
                    counted_line_edit.deselect()
                    counted_line_edit.clearFocus()
        selection_model = self.batch_table.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()
            selection_model.clearCurrentIndex()
        self.batch_table.clearSelection()
        self.batch_table.setCurrentCell(-1, -1)
        self.batch_table.clearFocus()
        self.sku_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        QTimer.singleShot(0, lambda: self.sku_input.setFocus(Qt.FocusReason.ShortcutFocusReason))

    def _is_batch_table_widget(self, watched) -> bool:
        current = watched
        while current is not None:
            if current is self.batch_table or current is self.batch_table.viewport():
                return True
            parent_widget = getattr(current, "parentWidget", None)
            current = parent_widget() if callable(parent_widget) else None
        return False

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and event.key() == Qt.Key.Key_Escape:
            if self._is_batch_table_widget(watched):
                self._clear_batch_selection()
                return True
        return super().eventFilter(watched, event)

    def _handle_confirm(self) -> None:
        payload = build_inventory_count_payload(
            reference=self.reference_input.text(),
            observation=self.observation_input.text(),
            rows=self._rows,
        )
        changed_rows = list(payload["rows"])
        if not changed_rows:
            QMessageBox.information(self, "Sin diferencias", "No hay diferencias reales para aplicar.")
            return

        batch_view = build_inventory_count_batch_view(self._rows)
        reference = str(payload["reference"]).strip() or f"CONTEO-{uuid4().hex[:8].upper()}"
        confirmation_text = "\n".join(
            (
                f"Referencia: {reference}",
                *batch_view.confirmation_lines,
                "",
                "Solo se aplicaran filas con diferencia. ¿Deseas continuar?",
            )
        )
        answer = QMessageBox.question(
            self,
            "Confirmar conteo",
            confirmation_text,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        payload["reference"] = reference
        self._result = payload
        self.accept()

    def get_result(self) -> dict[str, object] | None:
        return self._result
