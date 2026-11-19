"""Diálogo viejo de Inventario: precio en lote (preview por fila con avisos).

Salió tal cual de `MainWindow._prompt_inventory_bulk_price_data` (2026-11-19).
La ventana sigue teniendo ese método y solo delega aquí, pasando lo que el
diálogo necesita.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.tabla_lote_helper import (
    TableSpinTabNavigator as _TableSpinTabNavigator,
    set_table_badge_style as _set_table_badge_style,
    table_item as _table_item,
)


def prompt_inventory_bulk_price_data(
    *,
    selected_ids: list[int],
    filtered_rows: list[dict[str, object]],
    create_modal_dialog: Callable[..., tuple[QDialog, QVBoxLayout]],
    generate_reference: Callable[..., str],
) -> dict[str, object] | None:
    filtered_rows = list(filtered_rows)
    if not selected_ids and not filtered_rows:
        raise ValueError("No hay presentaciones disponibles para cambio masivo de precio.")

    source_options: list[tuple[str, str, list[dict[str, object]]]] = []
    if selected_ids:
        selected_rows = [row for row in filtered_rows if int(row["variante_id"]) in set(selected_ids)]
        source_options.append((f"Filas seleccionadas ({len(selected_rows)})", "SELECCION", selected_rows))
    if filtered_rows:
        source_options.append((f"Resultados filtrados ({len(filtered_rows)})", "FILTRADO", filtered_rows))

    dialog, layout = create_modal_dialog(
        "Precio masivo",
        "Actualiza precios por lote con preview y auditoria. Cada fila deja rastro en historial de catalogo.",
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
    mode_combo.addItem("Fijar precio", "SET")
    mode_combo.addItem("Aumentar monto", "INCREASE_AMOUNT")
    mode_combo.addItem("Disminuir monto", "DECREASE_AMOUNT")
    mode_combo.addItem("Aumentar %", "INCREASE_PERCENT")
    mode_combo.addItem("Disminuir %", "DECREASE_PERCENT")

    reference_input = QLineEdit()
    reference_input.setText(generate_reference(prefix="PRL"))
    reference_input.setReadOnly(True)
    reference_input.setObjectName("inventoryFilterInput")
    motive_input = QLineEdit()
    motive_input.setPlaceholderText("Ajuste de lista / temporada / correccion comercial")
    note_input = QLineEdit()
    note_input.setPlaceholderText("Observación adicional")
    for label_text, row_index, column_index in (
        ("Fuente", 0, 0),
        ("Operacion", 0, 2),
        ("Referencia", 1, 0),
        ("Motivo", 1, 2),
        ("Observacion", 2, 0),
    ):
        label = QLabel(label_text)
        label.setObjectName("inventoryFilterLabel")
        header_grid.addWidget(label, row_index, column_index)
    header_grid.addWidget(source_combo, 0, 1)
    header_grid.addWidget(mode_combo, 0, 3)
    header_grid.addWidget(reference_input, 1, 1)
    header_grid.addWidget(motive_input, 1, 3)
    header_grid.addWidget(note_input, 2, 1, 1, 3)
    header_grid.setColumnStretch(1, 1)
    header_grid.setColumnStretch(3, 1)

    operation_hint_label = QLabel()
    operation_hint_label.setObjectName("subtleLine")
    operation_hint_label.setStyleSheet("padding: 4px 2px; color: #5f6d78;")

    quick_actions_row = QHBoxLayout()
    quick_actions_row.setSpacing(6)
    quick_label = QLabel("Valor rapido")
    quick_label.setObjectName("inventoryFilterLabel")
    quick_value_spin = QDoubleSpinBox()
    quick_value_spin.setDecimals(2)
    quick_value_spin.setSingleStep(1.0)
    quick_value_spin.setRange(0.00, 100000.00)
    quick_value_spin.setObjectName("inventoryFilterInput")
    quick_apply_all_button = QPushButton("Aplicar a todas")
    quick_apply_selected_button = QPushButton("Aplicar a seleccionadas")
    quick_reset_button = QPushButton("Restablecer")
    for button in (quick_apply_all_button, quick_apply_selected_button, quick_reset_button):
        button.setObjectName("secondaryButton")
    quick_apply_all_button.setStyleSheet("font-weight: 700;")
    quick_apply_selected_button.setStyleSheet("font-weight: 700;")
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
        ["SKU", "Producto", "Talla", "Color", "Actual", "Entrada", "Nuevo", "Delta", "Estado", "Mensaje"]
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

    def format_money(value: Decimal) -> str:
        return f"${value.quantize(Decimal('0.01'))}"

    def current_source_rows() -> list[dict[str, object]]:
        return source_payloads.get(str(source_combo.currentData() or ""), [])

    def current_mode() -> str:
        return str(mode_combo.currentData() or "SET")

    def update_operation_hint() -> None:
        hint_map = {
            "SET": "Captura el precio final deseado por fila.",
            "INCREASE_AMOUNT": "Captura cuanto quieres aumentar en dinero a cada presentacion.",
            "DECREASE_AMOUNT": "Captura cuanto quieres descontar en dinero a cada presentacion.",
            "INCREASE_PERCENT": "Captura el porcentaje de aumento por fila.",
            "DECREASE_PERCENT": "Captura el porcentaje de descuento por fila.",
        }
        operation_hint_label.setText(hint_map.get(current_mode(), "Define la operacion comercial a aplicar."))
        quick_value_spin.setSuffix("%" if current_mode().endswith("PERCENT") else "")
        quick_value_spin.setSingleStep(1.0 if current_mode().endswith("PERCENT") else 5.0)

    def refresh_summary() -> None:
        rows = current_source_rows()
        ok_rows = 0
        warning_rows = 0
        unchanged_rows = 0
        error_rows = 0
        increased_rows = 0
        decreased_rows = 0
        for row_index in range(len(rows)):
            state_item = table.item(row_index, 8)
            delta_item = table.item(row_index, 7)
            if state_item is None or delta_item is None:
                continue
            state_text = state_item.text()
            delta_text = str(delta_item.data(Qt.ItemDataRole.UserRole) or "0.00")
            delta_value = Decimal(delta_text).quantize(Decimal("0.01"))
            if state_text == "OK":
                ok_rows += 1
            elif state_text == "WARNING":
                warning_rows += 1
            elif state_text == "ERROR":
                error_rows += 1
            elif state_text == "SIN CAMBIOS":
                unchanged_rows += 1
            if delta_value > Decimal("0.00"):
                increased_rows += 1
            elif delta_value < Decimal("0.00"):
                decreased_rows += 1

        summary_label.setText(
            f"Filas: {len(rows)} | OK: {ok_rows} | Warning: {warning_rows} | "
            f"Sin cambios: {unchanged_rows} | Error: {error_rows} | "
            f"Suben: {increased_rows} | Bajan: {decreased_rows}"
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(error_rows == 0 and (ok_rows > 0 or warning_rows > 0))
        if error_rows > 0:
            status_banner_label.setText(
                "Hay filas con error. Corrige los valores capturados antes de aplicar el lote."
            )
            set_banner_style("danger")
        elif warning_rows > 0:
            status_banner_label.setText(
                "Hay advertencias. El lote se puede aplicar, pero conviene revisar las filas marcadas."
            )
            set_banner_style("warning")
        elif ok_rows == 0:
            status_banner_label.setText("No hay cambios efectivos de precio para aplicar en este lote.")
            set_banner_style("neutral")
        else:
            status_banner_label.setText("Lote de precio listo para aplicar.")
            set_banner_style("positive")

    def recalc_row(row_index: int) -> None:
        rows = current_source_rows()
        if row_index >= len(rows):
            return
        row = rows[row_index]
        spin = table.cellWidget(row_index, 5)
        if not isinstance(spin, QDoubleSpinBox):
            return

        price_actual = Decimal(str(row["precio_venta"])).quantize(Decimal("0.01"))
        captured_value = Decimal(str(spin.value())).quantize(Decimal("0.01"))
        mode = current_mode()
        if mode == "SET":
            new_price = captured_value
            delta_value = (new_price - price_actual).quantize(Decimal("0.01"))
        elif mode == "INCREASE_AMOUNT":
            delta_value = captured_value
            new_price = (price_actual + captured_value).quantize(Decimal("0.01"))
        elif mode == "DECREASE_AMOUNT":
            delta_value = (captured_value * Decimal("-1")).quantize(Decimal("0.01"))
            new_price = (price_actual - captured_value).quantize(Decimal("0.01"))
        elif mode == "INCREASE_PERCENT":
            delta_value = (price_actual * captured_value / Decimal("100.00")).quantize(Decimal("0.01"))
            new_price = (price_actual + delta_value).quantize(Decimal("0.01"))
        else:
            delta_value = ((price_actual * captured_value / Decimal("100.00")) * Decimal("-1")).quantize(Decimal("0.01"))
            new_price = (price_actual + delta_value).quantize(Decimal("0.01"))

        estado = "OK"
        mensaje = "Cambio listo."
        tone = "positive"
        costo_referencia = row.get("costo_referencia")
        if new_price < Decimal("0.00"):
            estado = "ERROR"
            mensaje = f"El precio final seria {format_money(new_price)}. No se permiten precios negativos."
            tone = "danger"
        elif new_price == price_actual:
            estado = "SIN CAMBIOS"
            mensaje = "La operacion no cambia el precio actual."
            tone = "muted"
        elif new_price == Decimal("0.00"):
            estado = "WARNING"
            mensaje = "El precio final queda en $0.00. Verifica si realmente es correcto."
            tone = "warning"
        elif costo_referencia is not None and new_price < Decimal(str(costo_referencia)).quantize(Decimal("0.01")):
            estado = "WARNING"
            mensaje = f"El precio queda por debajo del costo de referencia {format_money(Decimal(str(costo_referencia)))}."
            tone = "warning"
        elif not bool(row["variante_activa"]):
            estado = "WARNING"
            mensaje = "La presentacion esta inactiva; el cambio se puede aplicar, pero conviene revisarla."
            tone = "warning"
        elif price_actual > Decimal("0.00") and abs(delta_value) >= max(Decimal("50.00"), price_actual * Decimal("0.50")):
            estado = "WARNING"
            mensaje = f"El cambio mueve {format_money(abs(delta_value))} respecto al precio actual."
            tone = "warning"

        new_item = _table_item(format_money(new_price))
        new_item.setData(Qt.ItemDataRole.UserRole, str(new_price))
        delta_prefix = "+" if delta_value > Decimal("0.00") else ""
        delta_item = _table_item(f"{delta_prefix}{format_money(delta_value)}")
        delta_item.setData(Qt.ItemDataRole.UserRole, str(delta_value))
        state_item = _table_item(estado)
        message_item = _table_item(mensaje)
        if delta_value > Decimal("0.00"):
            _set_table_badge_style(delta_item, "positive")
        elif delta_value < Decimal("0.00"):
            _set_table_badge_style(delta_item, "warning")
        else:
            _set_table_badge_style(delta_item, "muted")
        _set_table_badge_style(state_item, tone)
        if estado == "ERROR":
            _set_table_badge_style(message_item, "danger")
        elif estado == "WARNING":
            _set_table_badge_style(message_item, "warning")
        elif estado == "SIN CAMBIOS":
            _set_table_badge_style(message_item, "muted")
        table.setItem(row_index, 6, new_item)
        table.setItem(row_index, 7, delta_item)
        table.setItem(row_index, 8, state_item)
        table.setItem(row_index, 9, message_item)

    def _recalc_price_row(row_index: int) -> None:
        recalc_row(row_index)
        refresh_summary()

    def update_preview() -> None:
        rows = current_source_rows()
        mode = current_mode()
        table.setRowCount(len(rows))
        update_operation_hint()
        quick_value_spin.setRange(0.00, 100000.00)
        for row_index, row in enumerate(rows):
            base_values = [
                row["sku"],
                row["producto_nombre_base"],
                row["talla"],
                row["color"],
                format_money(Decimal(str(row["precio_venta"]))),
            ]
            for column_index, value in enumerate(base_values):
                table.setItem(row_index, column_index, _table_item(value))
            spin = table.cellWidget(row_index, 5)
            if not isinstance(spin, QDoubleSpinBox):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(0.00, 100000.00)
                spin.setSingleStep(1.0)
                spin.valueChanged.connect(lambda _value, idx=row_index: _recalc_price_row(idx))
                table.setCellWidget(row_index, 5, spin)
            spin.blockSignals(True)
            spin.setSuffix("%" if mode.endswith("PERCENT") else "")
            spin.setSingleStep(1.0 if mode.endswith("PERCENT") else 5.0)
            spin.setValue(float(Decimal(str(row["precio_venta"])).quantize(Decimal("0.01"))) if mode == "SET" else 0.0)
            spin.blockSignals(False)
            recalc_row(row_index)
        tab_navigator.set_inputs(
            [
                spin
                for row_index in range(table.rowCount())
                if isinstance((spin := table.cellWidget(row_index, 5)), QDoubleSpinBox)
            ]
        )
        refresh_summary()
        table.resizeColumnsToContents()

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
            spin = table.cellWidget(row_index, 5)
            if isinstance(spin, QDoubleSpinBox):
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
    layout.addWidget(operation_hint_label)
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
    items: list[dict[str, object]] = []
    for row_index, row in enumerate(rows):
        state_item = table.item(row_index, 8)
        new_item = table.item(row_index, 6)
        if state_item is None or new_item is None:
            continue
        items.append(
            {
                "variante_id": int(row["variante_id"]),
                "precio_nuevo": str(new_item.data(Qt.ItemDataRole.UserRole) or "0.00"),
                "estado": state_item.text(),
            }
        )

    return {
        "tipo_fuente": str(source_combo.currentData() or "SELECCION"),
        "tipo_operacion": current_mode(),
        "referencia": reference_input.text().strip(),
        "motivo": motive_input.text().strip(),
        "observacion": note_input.text().strip(),
        "items": items,
    }
