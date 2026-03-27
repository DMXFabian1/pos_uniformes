"""Dialogo V1 para conteo fisico rapido por SKU."""

from __future__ import annotations

from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
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
    build_inventory_count_payload,
    build_inventory_count_row,
    load_inventory_count_variant_by_sku,
    upsert_inventory_count_row,
    remove_inventory_count_row,
)
from pos_uniformes.ui.helpers.inventory_count_view_helper import build_inventory_count_batch_view


def prompt_inventory_count_data(parent=None) -> dict[str, object] | None:
    dialog = InventoryCountDialog(parent=parent)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dialog.get_result()


class InventoryCountDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_variant: InventoryCountVariantView | None = None
        self._rows: list[InventoryCountRow] = []
        self._result: dict[str, object] | None = None
        self.setWindowTitle("Conteo fisico")
        self.setModal(True)
        self.resize(860, 680)
        self._build_ui()
        self._refresh_selected_variant_card()
        self._refresh_batch_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        helper = QLabel(
            "Modo rapido por SKU. Captura diferencias puntuales y revisa el lote antes de aplicarlo."
        )
        helper.setWordWrap(True)
        helper.setObjectName("subtleLine")
        layout.addWidget(helper)

        search_card = QFrame()
        search_card.setObjectName("infoSubcard")
        search_layout = QVBoxLayout()
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(8)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Escanea o captura SKU")
        self.sku_input.setClearButtonEnabled(True)
        self.sku_input.returnPressed.connect(self._handle_lookup_sku)
        self.lookup_button = QPushButton("Buscar")
        self.lookup_button.setObjectName("toolbarSecondaryButton")
        self.lookup_button.clicked.connect(self._handle_lookup_sku)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.sku_input, 1)
        search_row.addWidget(self.lookup_button)
        search_layout.addLayout(search_row)

        self.variant_title_label = QLabel("Sin SKU cargado.")
        self.variant_title_label.setObjectName("inventoryTitle")
        self.variant_meta_label = QLabel("Escanea una presentacion para cargar su stock actual.")
        self.variant_meta_label.setObjectName("inventoryMetaCard")
        self.variant_meta_label.setWordWrap(True)
        self.variant_stock_label = QLabel("Sistema: -")
        self.variant_stock_label.setObjectName("analyticsLine")

        search_layout.addWidget(self.variant_title_label)
        search_layout.addWidget(self.variant_meta_label)
        search_layout.addWidget(self.variant_stock_label)
        search_card.setLayout(search_layout)
        layout.addWidget(search_card)

        counted_card = QFrame()
        counted_card.setObjectName("infoSubcard")
        counted_layout = QHBoxLayout()
        counted_layout.setContentsMargins(12, 10, 12, 10)
        counted_layout.setSpacing(8)
        counted_form = QFormLayout()
        counted_form.setSpacing(8)
        self.counted_spin = QSpinBox()
        self.counted_spin.setRange(0, 100000)
        self.counted_spin.setEnabled(False)
        counted_form.addRow("Contado", self.counted_spin)
        counted_layout.addLayout(counted_form)
        self.add_button = QPushButton("Agregar al lote")
        self.add_button.setObjectName("toolbarPrimaryButton")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._handle_add_to_batch)
        counted_layout.addWidget(self.add_button)
        counted_layout.addStretch()
        counted_card.setLayout(counted_layout)
        layout.addWidget(counted_card)

        self.batch_status_label = QLabel("")
        self.batch_status_label.setObjectName("subtleLine")
        layout.addWidget(self.batch_status_label)

        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(5)
        self.batch_table.setHorizontalHeaderLabels(["SKU", "Producto", "Sistema", "Contado", "Diferencia"])
        self.batch_table.setObjectName("dataTable")
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setSelectionBehavior(self.batch_table.SelectionBehavior.SelectRows)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setMinimumHeight(260)
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)
        layout.addWidget(self.batch_table)

        self.batch_summary_label = QLabel("")
        self.batch_summary_label.setObjectName("analyticsLine")
        layout.addWidget(self.batch_summary_label)

        footer_form = QFormLayout()
        footer_form.setSpacing(8)
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("CONTEO-0001")
        self.observation_input = QLineEdit()
        self.observation_input.setPlaceholderText("Conteo de piso, almacen o revision puntual")
        footer_form.addRow("Referencia", self.reference_input)
        footer_form.addRow("Observacion", self.observation_input)
        layout.addLayout(footer_form)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.remove_button = QPushButton("Quitar fila")
        self.remove_button.setObjectName("toolbarGhostButton")
        self.remove_button.clicked.connect(self._handle_remove_selected_row)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addStretch()

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
        buttons_row.addWidget(buttons)
        layout.addLayout(buttons_row)

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
            for column_index, value in enumerate(row.values):
                item = QTableWidgetItem(str(value))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.variante_id)
                self.batch_table.setItem(row_index, column_index, item)

        self.batch_summary_label.setText(batch_view.summary_label)
        self.batch_status_label.setText(batch_view.status_label)
        self.remove_button.setEnabled(bool(batch_view.rows))

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
