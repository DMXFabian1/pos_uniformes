"""Dialogo V1/V2 para conteo fisico con escaneo uno a uno."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.inventory_count_service import (
    InventoryCountRow,
    InventoryCountVariantView,
    accumulate_inventory_count_scan,
    build_inventory_count_payload,
    build_inventory_count_row,
    get_inventory_count_apply_error,
    load_inventory_count_variant_by_sku,
    remove_inventory_count_row,
    update_inventory_count_row_counted_stock,
    upsert_inventory_count_row,
)
from pos_uniformes.ui.helpers.inventory_count_view_helper import (
    build_inventory_count_batch_view,
    build_inventory_count_confirm_text,
)


def prompt_inventory_count_data(
    parent=None,
    *,
    initial_rows: list[InventoryCountRow] | None = None,
    initial_context_label: str | None = None,
    print_labels_callback: Callable[[list[int]], None] | None = None,
) -> dict[str, object] | None:
    dialog = InventoryCountDialog(
        parent=parent,
        initial_rows=initial_rows,
        initial_context_label=initial_context_label,
        print_labels_callback=print_labels_callback,
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
        print_labels_callback: Callable[[list[int]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected_variant: InventoryCountVariantView | None = None
        self._rows: list[InventoryCountRow] = list(initial_rows or [])
        self._initial_context_label = str(initial_context_label or "").strip()
        self._scan_accumulation_enabled = True
        self._result: dict[str, object] | None = None
        self._reference_value = f"CONTEO-{uuid4().hex[:8].upper()}"
        self._print_labels_callback = print_labels_callback
        self._scan_feedback_reset_timer = QTimer(self)
        self._scan_feedback_reset_timer.setSingleShot(True)
        self._scan_feedback_reset_timer.setInterval(1200)
        self._scan_feedback_reset_timer.timeout.connect(self._reset_scan_feedback)
        self._add_to_system_mode = False
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
            "Conteo libre por SKU. Escanea sin detenerte: la tabla ira armando una piscina de datos con solo los productos capturados."
        )
        helper.setWordWrap(True)
        helper.setObjectName("analyticsLine")
        helper.setStyleSheet("padding: 2px 0; color: #5f6d78;")
        layout.addWidget(helper)

        mode_card = QFrame()
        mode_card.setObjectName("infoSubcard")
        mode_card.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; }")
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(14, 10, 14, 10)
        mode_layout.setSpacing(16)
        mode_label = QLabel("Modo:")
        mode_label.setObjectName("inventoryFilterLabel")
        self._radio_conteo = QRadioButton("Conteo fisico")
        self._radio_conteo.setChecked(True)
        self._radio_ingreso = QRadioButton("Agregar mercancia")
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._radio_conteo, 0)
        self._mode_group.addButton(self._radio_ingreso, 1)
        self._mode_hint = QLabel("Reemplaza el stock con lo que cuentes fisicamente.")
        self._mode_hint.setObjectName("analyticsLine")
        self._mode_hint.setStyleSheet("color: #5f6d78;")
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self._radio_conteo)
        mode_layout.addWidget(self._radio_ingreso)
        mode_layout.addSpacing(8)
        mode_layout.addWidget(self._mode_hint, 1)
        mode_card.setLayout(mode_layout)
        layout.addWidget(mode_card)

        scan_header_card = QFrame()
        scan_header_card.setObjectName("infoSubcard")
        scan_header_card.setStyleSheet(
            "QFrame#infoSubcard { border: 1px solid #d9e5ef; }"
            "QLineEdit#inventoryCountScanInput {"
            "  min-height: 58px;"
            "  padding: 0 18px;"
            "  border-radius: 18px;"
            "  border: 2px solid #d5c9b9;"
            "  background: #fffdf8;"
            "  font-size: 22px;"
            "  font-weight: 600;"
            "  color: #2f2a24;"
            "}"
            "QLineEdit#inventoryCountScanInput:focus {"
            "  border: 2px solid #c45425;"
            "  background: #fffdf9;"
            "}"
        )
        scan_header_layout = QVBoxLayout()
        scan_header_layout.setContentsMargins(16, 14, 16, 14)
        scan_header_layout.setSpacing(10)

        scan_header_row = QHBoxLayout()
        scan_header_row.setSpacing(10)
        self.scan_title_label = QLabel("Escaneando...")
        self.scan_title_label.setObjectName("inventoryTitle")
        self.scan_title_label.setStyleSheet("font-size: 30px; font-weight: 800; color: #224863;")
        self.scan_state_badge = QLabel()
        self.scan_state_badge.setObjectName("analyticsLine")
        self.scan_state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scan_header_row.addWidget(self.scan_title_label)
        scan_header_row.addStretch(1)
        scan_header_row.addWidget(self.scan_state_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.scan_hint_label = QLabel("Cada lectura suma una pieza y mantiene el foco en este campo.")
        self.scan_hint_label.setObjectName("analyticsLine")
        self.scan_hint_label.setWordWrap(True)
        self.scan_hint_label.setStyleSheet("color: #5f6d78; padding: 0 2px;")

        self.sku_input = QLineEdit()
        self.sku_input.setObjectName("inventoryCountScanInput")
        self.sku_input.setPlaceholderText("Escanea pieza por pieza")
        self.sku_input.setClearButtonEnabled(True)
        self.sku_input.setMinimumHeight(58)
        self.sku_input.installEventFilter(self)

        scan_header_layout.addLayout(scan_header_row)
        scan_header_layout.addWidget(self.scan_hint_label)
        scan_header_layout.addWidget(self.sku_input)
        scan_header_card.setLayout(scan_header_layout)
        layout.addWidget(scan_header_card)

        self.initial_context_label = QLabel("")
        self.initial_context_label.setObjectName("analyticsLine")
        self.initial_context_label.setWordWrap(True)
        self.initial_context_label.setStyleSheet(
            "padding: 6px 10px; border-radius: 12px; background: #eef5fb; color: #4a6072; border: 1px solid #d1e1ee;"
        )
        self.initial_context_label.setVisible(True)
        layout.addWidget(self.initial_context_label)

        control_card = QFrame()
        control_card.setObjectName("infoSubcard")
        control_layout = QGridLayout()
        control_layout.setContentsMargins(14, 12, 14, 12)
        control_layout.setHorizontalSpacing(12)
        control_layout.setVerticalSpacing(10)

        self.lookup_button = QPushButton("Sumar 1")
        self.lookup_button.setObjectName("toolbarSecondaryButton")
        self.lookup_button.setAutoDefault(False)
        self.lookup_button.setDefault(False)
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
        manual_label = QLabel("Correccion puntual")
        manual_label.setObjectName("inventoryFilterLabel")
        self.counted_spin = QSpinBox()
        self.counted_spin.setRange(0, 100000)
        self.counted_spin.setEnabled(False)
        self.counted_spin.setMinimumWidth(140)
        self.counted_spin.installEventFilter(self)
        self.add_button = QPushButton("Aplicar contado manual")
        self.add_button.setObjectName("toolbarPrimaryButton")
        self.add_button.setAutoDefault(False)
        self.add_button.setDefault(False)
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
        self.print_labels_button = QPushButton("Imprimir etiquetas")
        self.print_labels_button.setObjectName("toolbarSecondaryButton")
        self.print_labels_button.clicked.connect(self._handle_print_labels)
        self.decrement_button = QPushButton("Restar 1")
        self.decrement_button.setObjectName("toolbarGhostButton")
        self.decrement_button.clicked.connect(self._handle_decrement_selected_row_count)
        self.remove_button = QPushButton("Quitar fila")
        self.remove_button.setObjectName("toolbarGhostButton")
        self.remove_button.clicked.connect(self._handle_remove_selected_row)
        actions_column.addWidget(self.print_labels_button)
        actions_column.addWidget(self.decrement_button)
        actions_column.addWidget(self.remove_button)
        actions_column.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Aplicar lote")
            ok_button.setAutoDefault(False)
            ok_button.setDefault(False)
            ok_button.clicked.connect(self._handle_confirm)
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
            cancel_button.setAutoDefault(False)
            cancel_button.setDefault(False)
            cancel_button.clicked.connect(self.reject)
        actions_column.addWidget(buttons)
        footer_layout.addLayout(actions_column)
        footer_card.setLayout(footer_layout)
        layout.addWidget(footer_card)

        content_widget = QWidget()
        content_widget.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.setLayout(outer)

        self.batch_table.itemSelectionChanged.connect(self._refresh_batch_action_state)
        self._mode_group.idToggled.connect(self._handle_mode_changed)
        self._reset_scan_feedback()
        self.sku_input.setFocus()

    def _handle_mode_changed(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        new_mode_is_add = button_id == 1
        if new_mode_is_add == self._add_to_system_mode:
            return
        if self._rows:
            answer = QMessageBox.question(
                self,
                "Cambiar modo",
                "Cambiar de modo borrara las filas ya capturadas porque los valores no son compatibles.\n\n¿Deseas continuar?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._mode_group.blockSignals(True)
                self._radio_conteo.setChecked(not self._add_to_system_mode)
                self._radio_ingreso.setChecked(self._add_to_system_mode)
                self._mode_group.blockSignals(False)
                return
            self._rows = []
            self._refresh_batch_table()
            self._clear_batch_selection()
            self._selected_variant = None
            self._refresh_selected_variant_card()
        self._add_to_system_mode = new_mode_is_add
        if self._add_to_system_mode:
            self._mode_hint.setText("Suma las piezas escaneadas al stock actual del sistema.")
        else:
            self._mode_hint.setText("Reemplaza el stock con lo que cuentes fisicamente.")

    def _handle_lookup_sku(self) -> None:
        sku = self.sku_input.text().strip()
        if not sku:
            self.variant_title_label.setText("Sin SKU cargado.")
            self.variant_meta_label.setText("Escanea una pieza para empezar a llenar la tabla.")
            self.variant_stock_label.setText("Sistema: -")
            self.counted_spin.setEnabled(False)
            self.add_button.setEnabled(False)
            self._set_scan_feedback("Esperando lectura", tone="idle")
            self.sku_input.setFocus()
            return

        with get_session() as session:
            variant = load_inventory_count_variant_by_sku(session, sku)

        if variant is None:
            self._set_scan_feedback("SKU no encontrado", tone="warning", sticky=True)
            QMessageBox.information(self, "SKU no encontrado", f"No se encontro una presentacion para '{sku}'.")
            self._selected_variant = None
            self._refresh_selected_variant_card()
            self.sku_input.selectAll()
            self.sku_input.setFocus()
            return

        self._selected_variant = variant
        self._rows = accumulate_inventory_count_scan(
            self._rows,
            variant=variant,
            step=1,
            add_to_system=self._add_to_system_mode,
        )
        current_row = next(
            (row for row in self._rows if int(row.variante_id) == int(variant.variante_id)),
            None,
        )
        self._refresh_selected_variant_card()
        if current_row is not None:
            spin_min = int(current_row.stock_sistema) if self._add_to_system_mode else 0
            self.counted_spin.setMinimum(spin_min)
            self.counted_spin.setValue(int(current_row.stock_contado))
        self.counted_spin.setEnabled(True)
        self.add_button.setEnabled(True)
        self._refresh_batch_table()
        self._clear_batch_selection()
        if current_row is not None:
            mode_label = "Ingreso de mercancia" if self._add_to_system_mode else "Conteo uno a uno"
            self.batch_status_label.setText(
                f"{mode_label}: {variant.sku} | contado {current_row.stock_contado} | sistema {current_row.stock_sistema} | delta {current_row.delta:+d}"
            )
            self._set_scan_feedback(f"{variant.sku} sumado", tone="success")
        self.sku_input.clear()
        self.sku_input.setFocus()

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
        self.batch_status_label.setText(
            (
                f"Ajuste puntual: {new_row.sku} {'actualizado' if existed_before else 'agregado'} al lote | "
                f"contado {new_row.stock_contado} | sistema {new_row.stock_sistema} | delta {new_row.delta:+d}"
            )
        )
        self.sku_input.clear()
        self._selected_variant = None
        self._refresh_selected_variant_card()
        self.counted_spin.setMinimum(0)
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
            self.variant_meta_label.setText("Escanea una pieza para cargar su stock actual.")
            self.variant_stock_label.setText("Sistema: -")
            return

        variant = self._selected_variant
        self.variant_title_label.setText(f"Ultima lectura: {variant.sku} | {variant.producto_nombre}")
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
            spin_min = int(row.values[2]) if self._add_to_system_mode else 0
            counted_spin.setRange(spin_min, 100000)
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
        self.initial_context_label.setText(
            "Modo libre: la tabla solo muestra SKU escaneados. Revisa diferencias hasta el final."
        )
        self.initial_context_label.setVisible(bool(self.initial_context_label.text().strip()))
        self._refresh_batch_action_state()

    def _refresh_batch_action_state(self) -> None:
        has_rows = bool(self._rows)
        has_selection = self.batch_table.currentRow() >= 0
        self.print_labels_button.setEnabled(has_rows and self._print_labels_callback is not None)
        self.remove_button.setEnabled(has_rows and has_selection)
        self.decrement_button.setEnabled(has_rows and has_selection)

    def _selected_batch_variant_ids(self) -> list[int]:
        selection_model = self.batch_table.selectionModel()
        if selection_model is None:
            return []
        variant_ids: list[int] = []
        seen: set[int] = set()
        for model_index in selection_model.selectedRows():
            item = self.batch_table.item(model_index.row(), 0)
            if item is None:
                continue
            raw_variant_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                variant_id = int(raw_variant_id)
            except (TypeError, ValueError):
                continue
            if variant_id in seen:
                continue
            seen.add(variant_id)
            variant_ids.append(variant_id)
        return variant_ids

    def _handle_print_labels(self) -> None:
        if self._print_labels_callback is None:
            return
        selected_variant_ids = self._selected_batch_variant_ids()
        variant_ids = selected_variant_ids or [int(row.variante_id) for row in self._rows]
        if not variant_ids:
            QMessageBox.information(
                self,
                "Sin lecturas",
                "Escanea al menos una pieza antes de abrir la impresion de etiquetas.",
            )
            return
        self._print_labels_callback(variant_ids)
        self.sku_input.setFocus()

    def _handle_decrement_selected_row_count(self) -> None:
        current_row = self.batch_table.currentRow()
        if current_row < 0 or current_row >= len(self._rows):
            QMessageBox.information(self, "Sin fila", "Selecciona una fila del lote para restar una pieza.")
            return
        selected = self._rows[current_row]
        min_stock = int(selected.stock_sistema) if self._add_to_system_mode else 0
        new_counted_stock = max(min_stock, int(selected.stock_contado) - 1)
        self._rows = update_inventory_count_row_counted_stock(
            self._rows,
            variante_id=int(selected.variante_id),
            counted_stock=new_counted_stock,
        )
        self._refresh_batch_table()
        if 0 <= current_row < self.batch_table.rowCount():
            self.batch_table.selectRow(current_row)
        self.batch_status_label.setText(
            f"Correccion rapida: {selected.sku} quedo en contado {new_counted_stock} | sistema {selected.stock_sistema} | delta {new_counted_stock - int(selected.stock_sistema):+d}"
        )

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
        self._refresh_batch_action_state()
        self.sku_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        QTimer.singleShot(0, lambda: self.sku_input.setFocus(Qt.FocusReason.ShortcutFocusReason))

    def _reset_scan_feedback(self) -> None:
        self._set_scan_feedback("Listo para leer", tone="idle", sticky=True)

    def _set_scan_feedback(self, text: str, *, tone: str, sticky: bool = False) -> None:
        tone_styles = {
            "idle": "background: #eef5fb; color: #456176; border: 1px solid #d1e1ee;",
            "success": "background: #e6f6ec; color: #1f6a3b; border: 1px solid #b7e0c4;",
            "warning": "background: #fff4df; color: #8a5a0a; border: 1px solid #efd4a0;",
        }
        self.scan_state_badge.setText(text.strip() or "Listo para leer")
        self.scan_state_badge.setStyleSheet(
            "padding: 6px 12px; border-radius: 12px; font-weight: 700; "
            + tone_styles.get(tone, tone_styles["idle"])
        )
        if sticky:
            self._scan_feedback_reset_timer.stop()
            return
        self._scan_feedback_reset_timer.start()

    def _is_batch_table_widget(self, watched) -> bool:
        current = watched
        while current is not None:
            if current is self.batch_table or current is self.batch_table.viewport():
                return True
            parent_widget = getattr(current, "parentWidget", None)
            current = parent_widget() if callable(parent_widget) else None
        return False

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() == QEvent.Type.Wheel:
            target = watched
            while target is not None:
                if isinstance(target, QSpinBox):
                    return True
                target = target.parent() if callable(getattr(target, "parent", None)) else None
        if watched is self.sku_input and event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._handle_lookup_sku()
            return True
        if watched is self.sku_input and event.type() == QEvent.Type.ShortcutOverride and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            event.accept()
            return True
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and event.key() == Qt.Key.Key_Escape:
            if self._is_batch_table_widget(watched):
                self._clear_batch_selection()
                return True
        return super().eventFilter(watched, event)

    def _handle_confirm(self) -> None:
        apply_error = get_inventory_count_apply_error(self._rows)
        if apply_error is not None:
            QMessageBox.information(self, "No se puede aplicar", apply_error)
            return

        payload = build_inventory_count_payload(
            reference=self.reference_input.text(),
            observation=self.observation_input.text(),
            rows=self._rows,
        )
        reference = str(payload["reference"]).strip() or f"CONTEO-{uuid4().hex[:8].upper()}"
        mode_label = "Ingreso de mercancia" if self._add_to_system_mode else "Conteo fisico"
        batch_view = build_inventory_count_batch_view(self._rows)
        confirmation_text = build_inventory_count_confirm_text(
            batch_view, mode_label=mode_label, reference=reference
        )
        answer = QMessageBox.question(self, "Confirmar conteo", confirmation_text)
        if answer != QMessageBox.StandardButton.Yes:
            return

        payload["reference"] = reference
        self._result = payload
        self.accept()

    def get_result(self) -> dict[str, object] | None:
        return self._result
