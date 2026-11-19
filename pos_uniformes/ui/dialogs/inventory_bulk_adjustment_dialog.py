"""Diálogo viejo de Inventario: ajuste de stock en lote (preview por fila con avisos).

Salió tal cual de `MainWindow._prompt_inventory_bulk_adjustment_data` (2026-11-19).
La ventana sigue teniendo ese método y solo delega aquí, pasando lo que el
diálogo necesita.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.tabla_lote_helper import (
    TableSpinTabNavigator as _TableSpinTabNavigator,
    build_bulk_selection_label as _build_bulk_selection_label,
    set_table_badge_style as _set_table_badge_style,
    table_item as _table_item,
)


def prompt_inventory_bulk_adjustment_data(
    *,
    selected_ids: list[int],
    filtered_rows: list[dict[str, object]],
    create_modal_dialog: Callable[..., tuple[QDialog, QVBoxLayout]],
    generate_reference: Callable[..., str],
) -> dict[str, object] | None:
    filtered_rows = list(filtered_rows)
    if not selected_ids and not filtered_rows:
        raise ValueError("No hay presentaciones disponibles para ajuste masivo.")

    source_options: list[tuple[str, str, list[dict[str, object]]]] = []
    if selected_ids:
        selected_rows = [row for row in filtered_rows if int(row["variante_id"]) in set(selected_ids)]
        source_options.append(
            (_build_bulk_selection_label(selected_ids, selected_rows), "SELECCION", selected_rows)
        )
    if filtered_rows:
        source_options.append(
            (f"Resultados filtrados ({len(filtered_rows)})", "FILTRADO", filtered_rows)
        )

    dialog, layout = create_modal_dialog(
        "Ajuste masivo de stock",
        "Aplica ajustes por lote sobre varias presentaciones. Cada fila genera su movimiento auditado.",
        width=980,
    )
    layout.setSpacing(8)
    header_grid = QGridLayout()
    header_grid.setHorizontalSpacing(8)
    header_grid.setVerticalSpacing(6)
    source_combo = QComboBox()
    source_payloads: dict[str, list[dict[str, object]]] = {}
    for label, code, rows in source_options:
        source_combo.addItem(label, code)
        source_payloads[code] = rows
    mode_combo = QComboBox()
    mode_combo.addItem("Stock final", "STOCK_FINAL")
    mode_combo.addItem("Diferencia (+/-)", "DELTA")
    reference_input = QLineEdit()
    reference_input.setText(generate_reference())
    reference_input.setReadOnly(True)
    reference_input.setObjectName("inventoryFilterInput")
    motive_input = QLineEdit()
    motive_input.setPlaceholderText("Conteo general / correccion de lote")
    note_input = QLineEdit()
    note_input.setPlaceholderText("Observación adicional")
    source_label = QLabel("Fuente")
    mode_label = QLabel("Tipo")
    reference_label = QLabel("Referencia")
    motive_label = QLabel("Motivo")
    note_label = QLabel("Observación")
    for label in (source_label, mode_label, reference_label, motive_label, note_label):
        label.setObjectName("inventoryFilterLabel")
    header_grid.addWidget(source_label, 0, 0)
    header_grid.addWidget(source_combo, 0, 1)
    header_grid.addWidget(mode_label, 0, 2)
    header_grid.addWidget(mode_combo, 0, 3)
    header_grid.addWidget(reference_label, 1, 0)
    header_grid.addWidget(reference_input, 1, 1)
    header_grid.addWidget(motive_label, 1, 2)
    header_grid.addWidget(motive_input, 1, 3)
    header_grid.addWidget(note_label, 2, 0)
    header_grid.addWidget(note_input, 2, 1, 1, 3)
    header_grid.setColumnStretch(1, 1)
    header_grid.setColumnStretch(3, 1)

    quick_actions_row = QHBoxLayout()
    quick_actions_row.setSpacing(6)
    quick_value_spin = QSpinBox()
    quick_value_spin.setRange(-100000, 100000)
    quick_value_spin.setAccelerated(True)
    quick_apply_all_button = QPushButton("Aplicar a todas")
    quick_apply_selected_button = QPushButton("Aplicar a seleccionadas")
    quick_reset_button = QPushButton("Restablecer")
    for button in (quick_apply_all_button, quick_apply_selected_button, quick_reset_button):
        button.setObjectName("secondaryButton")
    quick_apply_all_button.setStyleSheet("font-weight: 700;")
    quick_apply_selected_button.setStyleSheet("font-weight: 700;")
    quick_label = QLabel("Valor rapido")
    quick_label.setObjectName("inventoryFilterLabel")
    quick_actions_row.addWidget(quick_label)
    quick_actions_row.addWidget(quick_value_spin)
    quick_actions_row.addWidget(quick_apply_all_button)
    quick_actions_row.addWidget(quick_apply_selected_button)
    quick_actions_row.addWidget(quick_reset_button)
    quick_actions_row.addStretch()

    table = QTableWidget()
    table.setObjectName("dataTable")
    table.setColumnCount(10)
    table.setHorizontalHeaderLabels(
        ["SKU", "Producto", "Talla", "Color", "Stock", "Apartado", "Entrada", "Resultado", "Estado", "Mensaje"]
    )
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setMinimumHeight(380)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

    summary_label = QLabel("Sin filas cargadas.")
    summary_label.setObjectName("subtleLine")
    summary_label.setStyleSheet(
        "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
        "color: #50606c; font-weight: 600;"
    )
    status_banner_label = QLabel("Carga un lote para validar resultados.")
    status_banner_label.setObjectName("subtleLine")
    status_banner_label.setStyleSheet(
        "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
        "color: #5f6d78; font-weight: 700;"
    )

    def set_banner_style(tone: str) -> None:
        palette = {
            "positive": ("#e5f2eb", "#245241", "#bfdccd"),
            "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
            "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
            "neutral": ("#f3f7fa", "#5f6d78", "#d7e2ea"),
        }
        background, foreground, border = palette.get(tone, palette["neutral"])
        status_banner_label.setStyleSheet(
            f"padding: 8px 10px; border-radius: 12px; background: {background}; "
            f"border: 1px solid {border}; color: {foreground}; font-weight: 700;"
        )

    def current_source_rows() -> list[dict[str, object]]:
        return source_payloads.get(str(source_combo.currentData() or ""), [])

    def refresh_summary() -> None:
        rows = current_source_rows()
        valid_rows = 0
        error_rows = 0
        warning_rows = 0
        unchanged_rows = 0
        plus_units = 0
        minus_units = 0
        for row_index in range(len(rows)):
            state_item = table.item(row_index, 8)
            result_item = table.item(row_index, 7)
            if state_item is None or result_item is None:
                continue
            state_text = state_item.text()
            delta_value = int(result_item.data(Qt.ItemDataRole.UserRole) or 0)
            if state_text == "OK":
                valid_rows += 1
                if delta_value > 0:
                    plus_units += delta_value
                elif delta_value < 0:
                    minus_units += abs(delta_value)
            elif state_text == "WARNING":
                warning_rows += 1
                if delta_value > 0:
                    plus_units += delta_value
                elif delta_value < 0:
                    minus_units += abs(delta_value)
            elif state_text == "ERROR":
                error_rows += 1
            elif state_text == "SIN CAMBIOS":
                unchanged_rows += 1
        summary_label.setText(
            f"Filas: {len(rows)} | OK: {valid_rows} | Warning: {warning_rows} | "
            f"Sin cambios: {unchanged_rows} | Error: {error_rows} | "
            f"Unidades +: {plus_units} | Unidades -: {minus_units}"
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(error_rows == 0 and (valid_rows > 0 or warning_rows > 0))
        if error_rows > 0:
            status_banner_label.setText(
                "Hay filas con error. Corrige los valores capturados antes de aplicar el lote."
            )
            set_banner_style("danger")
        elif warning_rows > 0:
            status_banner_label.setText(
                "Hay advertencias. El lote se puede aplicar, pero revisa las filas resaltadas."
            )
            set_banner_style("warning")
        elif valid_rows == 0:
            status_banner_label.setText("No hay cambios efectivos para aplicar en este lote.")
            set_banner_style("neutral")
        else:
            status_banner_label.setText("Lote listo para aplicar.")
            set_banner_style("positive")

    def update_preview() -> None:
        rows = current_source_rows()
        mode = str(mode_combo.currentData() or "STOCK_FINAL")
        table.setRowCount(len(rows))
        quick_value_spin.setRange(0, 100000) if mode == "STOCK_FINAL" else quick_value_spin.setRange(-100000, 100000)
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(
                [
                    row["sku"],
                    row["producto_nombre_base"],
                    row["talla"],
                    row["color"],
                    row["stock_actual"],
                    row["apartado_cantidad"],
                ]
            ):
                item = _table_item(value)
                table.setItem(row_index, column_index, item)
            spin = table.cellWidget(row_index, 6)
            if not isinstance(spin, QSpinBox):
                spin = QSpinBox()
                spin.setRange(-100000, 100000)
                spin.valueChanged.connect(lambda _value, idx=row_index: _recalc_bulk_row(idx))
                table.setCellWidget(row_index, 6, spin)
            spin.blockSignals(True)
            spin.setRange(0, 100000) if mode == "STOCK_FINAL" else spin.setRange(-100000, 100000)
            spin.setValue(int(row["stock_actual"]) if mode == "STOCK_FINAL" else 0)
            spin.blockSignals(False)
            recalc_row(row_index)
        tab_navigator.set_inputs(
            [
                spin
                for row_index in range(table.rowCount())
                if isinstance((spin := table.cellWidget(row_index, 6)), QSpinBox)
            ]
        )
        refresh_summary()
        table.resizeColumnsToContents()

    def recalc_row(row_index: int) -> None:
        rows = current_source_rows()
        if row_index >= len(rows):
            return
        row = rows[row_index]
        mode = str(mode_combo.currentData() or "STOCK_FINAL")
        spin = table.cellWidget(row_index, 6)
        if not isinstance(spin, QSpinBox):
            return
        captured_value = spin.value()
        stock_actual = int(row["stock_actual"])
        apartado = int(row["apartado_cantidad"])
        delta = captured_value - stock_actual if mode == "STOCK_FINAL" else captured_value
        stock_final = captured_value if mode == "STOCK_FINAL" else stock_actual + captured_value
        estado = "OK"
        mensaje = "Ajuste listo."
        tone = "positive"
        if stock_final < 0:
            estado = "ERROR"
            mensaje = f"El stock final seria {stock_final}. No se permite stock negativo."
            tone = "danger"
        elif stock_final < apartado:
            estado = "ERROR"
            mensaje = f"El stock final ({stock_final}) queda por debajo del apartado comprometido ({apartado})."
            tone = "danger"
        elif delta == 0:
            estado = "SIN CAMBIOS"
            mensaje = "El valor capturado no cambia el stock actual."
            tone = "muted"
        elif apartado > 0 and stock_final == apartado:
            estado = "WARNING"
            mensaje = "El stock final queda exactamente igual al comprometido por apartados."
            tone = "warning"
        elif not bool(row["variante_activa"]):
            estado = "WARNING"
            mensaje = "La presentacion esta inactiva; el ajuste se puede aplicar, pero conviene revisarla."
            tone = "warning"
        elif abs(delta) >= max(10, stock_actual * 2) and stock_actual > 0:
            estado = "WARNING"
            mensaje = f"El ajuste cambia {abs(delta)} unidades. Revisa que el lote sea correcto."
            tone = "warning"
        result_item = _table_item(stock_final)
        result_item.setData(Qt.ItemDataRole.UserRole, delta)
        state_item = _table_item(estado)
        message_item = _table_item(mensaje)
        _set_table_badge_style(state_item, tone)
        if estado == "ERROR":
            _set_table_badge_style(message_item, "danger")
        elif estado == "SIN CAMBIOS":
            _set_table_badge_style(message_item, "muted")
        elif estado == "WARNING":
            _set_table_badge_style(message_item, "warning")
        table.setItem(row_index, 7, result_item)
        table.setItem(row_index, 8, state_item)
        table.setItem(row_index, 9, message_item)

    def _recalc_bulk_row(row_index: int) -> None:
        recalc_row(row_index)
        refresh_summary()

    def _apply_quick_value(selected_only: bool) -> None:
        target_rows = (
            sorted({index.row() for index in table.selectionModel().selectedRows()})
            if selected_only
            else list(range(table.rowCount()))
        )
        if selected_only and not target_rows:
            QMessageBox.information(dialog, "Sin seleccion", "Selecciona al menos una fila del preview.")
            return
        value = quick_value_spin.value()
        for row_index in target_rows:
            spin = table.cellWidget(row_index, 6)
            if isinstance(spin, QSpinBox):
                spin.setValue(value)

    def _reset_quick_values() -> None:
        update_preview()

    source_combo.currentIndexChanged.connect(lambda _: update_preview())
    mode_combo.currentIndexChanged.connect(lambda _: update_preview())
    quick_apply_all_button.clicked.connect(lambda: _apply_quick_value(False))
    quick_apply_selected_button.clicked.connect(lambda: _apply_quick_value(True))
    quick_reset_button.clicked.connect(_reset_quick_values)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText("Aplicar lote")
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    tab_navigator = _TableSpinTabNavigator(
        anchor_before=quick_reset_button,
        anchor_after=cancel_button or ok_button,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(header_grid)
    layout.addWidget(status_banner_label)
    layout.addLayout(quick_actions_row)
    layout.addWidget(summary_label)
    layout.addWidget(table)
    layout.addWidget(buttons)
    update_preview()
    if ok_button is not None and cancel_button is not None:
        QWidget.setTabOrder(cancel_button, ok_button)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    rows = current_source_rows()
    items: list[dict[str, int]] = []
    mode = str(mode_combo.currentData() or "STOCK_FINAL")
    for row_index, row in enumerate(rows):
        spin = table.cellWidget(row_index, 6)
        state_item = table.item(row_index, 8)
        if not isinstance(spin, QSpinBox) or state_item is None:
            continue
        items.append(
            {
                "variante_id": int(row["variante_id"]),
                "valor": int(spin.value()),
                "estado": 1 if state_item.text() == "OK" else 0,
            }
        )

    return {
        "tipo_fuente": str(source_combo.currentData() or "SELECCION"),
        "tipo_ajuste": mode,
        "referencia": reference_input.text().strip(),
        "motivo": motive_input.text().strip(),
        "observacion": note_input.text().strip(),
        "items": items,
    }
