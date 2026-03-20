"""Dialogo reutilizable para crear apartados."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.layaway_pricing_service import (
    build_layaway_pricing,
    resolve_layaway_client_discount_percent,
    resolve_layaway_min_deposit,
    resolve_layaway_unit_price,
)
from pos_uniformes.ui.helpers.date_field_helper import configure_friendly_date_edit
from pos_uniformes.utils.product_name import sanitize_product_display_name

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def build_create_layaway_dialog(
    window: "MainWindow",
    *,
    initial_items: list[dict[str, object]] | None = None,
    selected_catalog_row: dict[str, object] | None = None,
) -> dict[str, object] | None:
    dialog, layout = window._create_modal_dialog(
        "Nuevo apartado",
        "Agrega una o varias presentaciones y registra el anticipo inicial del apartado.",
        width=760,
    )
    form = QFormLayout()
    client_selector = QComboBox()
    client_selector.addItem("Manual / sin cliente", None)
    customer_input = QLineEdit()
    customer_input.setPlaceholderText("Nombre del cliente")
    phone_input = QLineEdit()
    phone_input.setPlaceholderText("Telefono")
    last_autofill = {"nombre": "", "telefono": ""}
    try:
        with get_session() as session:
            for client in [item for item in ClientService.list_clients(session) if item.activo]:
                client_selector.addItem(
                    f"{client.codigo_cliente} · {client.nombre}",
                    {
                        "id": int(client.id),
                        "nombre": client.nombre,
                        "telefono": client.telefono or "",
                    },
                )
    except Exception:
        pass

    def sync_selected_client() -> None:
        nonlocal last_autofill
        selected_client = client_selector.currentData()
        if isinstance(selected_client, dict):
            nombre = str(selected_client.get("nombre", "")).strip()
            telefono = str(selected_client.get("telefono", "")).strip()
            customer_input.setText(nombre)
            phone_input.setText(telefono)
            last_autofill = {"nombre": nombre, "telefono": telefono}
            return
        if customer_input.text().strip() == last_autofill["nombre"]:
            customer_input.clear()
        if phone_input.text().strip() == last_autofill["telefono"]:
            phone_input.clear()
        last_autofill = {"nombre": "", "telefono": ""}

    form.addRow("Cliente guardado", client_selector)
    form.addRow("Cliente", customer_input)
    form.addRow("Telefono", phone_input)

    items: list[dict[str, object]] = [
        {
            "sku": str(item["sku"]),
            "producto_nombre": str(item["producto_nombre"]),
            "cantidad": int(item["cantidad"]),
            "precio_unitario": Decimal(item["precio_unitario"]),
            "precio_base": Decimal(item.get("precio_base", item["precio_unitario"])),
        }
        for item in (initial_items or [])
    ]
    sku_input = QLineEdit()
    sku_input.setPlaceholderText("SKU")
    if selected_catalog_row is not None:
        sku_input.setText(str(selected_catalog_row["sku"]))
    qty_spin = QSpinBox()
    qty_spin.setRange(1, 100)
    add_item_button = QPushButton("Agregar presentacion")
    remove_item_button = QPushButton("Quitar seleccionada")
    items_table = QTableWidget()
    items_table.setColumnCount(5)
    items_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
    items_table.setObjectName("dataTable")
    items_table.verticalHeader().setVisible(False)
    items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    items_table.setAlternatingRowColors(True)
    total_label = QLabel("Total estimado: $0.00")
    total_label.setObjectName("analyticsLine")
    subtotal_label = QLabel("Subtotal estimado: $0.00")
    subtotal_label.setObjectName("analyticsLine")
    minimum_deposit_label = QLabel("Anticipo minimo (20%): $0.00")
    minimum_deposit_label.setObjectName("analyticsLine")

    def current_selected_client_id() -> int | None:
        selected_client = client_selector.currentData()
        if not isinstance(selected_client, dict):
            return None
        try:
            return int(selected_client["id"])
        except (KeyError, TypeError, ValueError):
            return None

    def current_client_discount_percent() -> Decimal:
        client_id = current_selected_client_id()
        if client_id is None:
            return Decimal("0.00")
        try:
            with get_session() as session:
                return resolve_layaway_client_discount_percent(
                    session,
                    selected_client_id=client_id,
                )
        except Exception:
            return Decimal("0.00")

    def reprice_items_for_selected_client() -> Decimal:
        discount_percent = current_client_discount_percent()
        for item in items:
            item["precio_unitario"] = resolve_layaway_unit_price(
                Decimal(item["precio_base"]),
                discount_percent=discount_percent,
            )
        return discount_percent

    def refresh_items_table() -> None:
        subtotal = Decimal("0.00")
        items_table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            line_subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
            subtotal += line_subtotal
            values = [
                item["sku"],
                item["producto_nombre"],
                item["cantidad"],
                item["precio_unitario"],
                line_subtotal,
            ]
            for column_index, value in enumerate(values):
                items_table.setItem(row_index, column_index, _table_item(value))
        items_table.resizeColumnsToContents()
        pricing = build_layaway_pricing(subtotal)
        subtotal_label.setText(f"Subtotal estimado: ${pricing.subtotal}")
        if pricing.rounding_adjustment != Decimal("0.00"):
            total_label.setText(
                f"Total estimado: ${pricing.total} | Ajuste: ${pricing.rounding_adjustment}"
            )
        else:
            total_label.setText(f"Total estimado: ${pricing.total}")
        minimum_deposit = resolve_layaway_min_deposit(pricing.total)
        minimum_deposit_label.setText(f"Anticipo minimo (20%): ${minimum_deposit}")
        deposit_spin.setMinimum(float(minimum_deposit))
        if deposit_spin.value() < float(minimum_deposit):
            deposit_spin.setValue(float(minimum_deposit))

    def handle_add_item() -> None:
        sku = sku_input.text().strip().upper()
        cantidad = qty_spin.value()
        if not sku:
            QMessageBox.warning(dialog, "SKU requerido", "Captura o escanea un SKU para agregarlo.")
            return
        try:
            with get_session() as session:
                variante = ApartadoService.obtener_variante_por_sku(session, sku)
                if variante is None:
                    raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")
                InventarioService.validar_stock_disponible(variante, cantidad)
                producto_nombre = sanitize_product_display_name(variante.producto.nombre)
                base_price = Decimal(variante.precio_venta)
                discount_percent = current_client_discount_percent()
                precio_unitario = resolve_layaway_unit_price(
                    base_price,
                    discount_percent=discount_percent,
                )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "Stock insuficiente" in message:
                message = f"No hay stock suficiente para reservar {cantidad} pieza(s) de '{sku}'."
            QMessageBox.warning(dialog, "No se pudo agregar", message)
            return

        existing = next((item for item in items if str(item["sku"]) == sku), None)
        if existing is not None:
            nueva_cantidad = int(existing["cantidad"]) + cantidad
            try:
                with get_session() as session:
                    variante = ApartadoService.obtener_variante_por_sku(session, sku)
                    if variante is None:
                        raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")
                    InventarioService.validar_stock_disponible(variante, nueva_cantidad)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if "Stock insuficiente" in message:
                    message = f"No hay stock suficiente para dejar {nueva_cantidad} pieza(s) de '{sku}' en el apartado."
                QMessageBox.warning(dialog, "Stock insuficiente", message)
                return
            existing["cantidad"] = nueva_cantidad
        else:
            items.append(
                {
                    "sku": sku,
                    "producto_nombre": producto_nombre,
                    "cantidad": cantidad,
                    "precio_base": base_price,
                    "precio_unitario": precio_unitario,
                }
            )

        sku_input.clear()
        qty_spin.setValue(1)
        refresh_items_table()

    def handle_remove_item() -> None:
        row_index = items_table.currentRow()
        if row_index < 0 or row_index >= len(items):
            return
        items.pop(row_index)
        refresh_items_table()

    def handle_selected_client_changed() -> None:
        sync_selected_client()
        reprice_items_for_selected_client()
        refresh_items_table()

    def set_due_date_from_offset(days: int) -> None:
        target_date = date.today() + timedelta(days=days)
        due_input.setDate(QDate(target_date.year, target_date.month, target_date.day))

    add_item_button.clicked.connect(handle_add_item)
    remove_item_button.clicked.connect(handle_remove_item)
    sku_input.returnPressed.connect(handle_add_item)
    client_selector.currentIndexChanged.connect(handle_selected_client_changed)

    line_row = QHBoxLayout()
    line_row.setSpacing(8)
    line_row.addWidget(QLabel("SKU"))
    line_row.addWidget(sku_input, 1)
    line_row.addWidget(QLabel("Cantidad"))
    line_row.addWidget(qty_spin)
    line_row.addWidget(add_item_button)
    line_row.addWidget(remove_item_button)

    due_input = QDateEdit()
    due_date = date.today() + timedelta(days=15)
    configure_friendly_date_edit(
        due_input,
        initial_date=QDate(due_date.year, due_date.month, due_date.day),
    )
    due_quick_row = QHBoxLayout()
    due_quick_row.setSpacing(6)
    due_plus_15_button = QPushButton("+15 dias")
    due_plus_30_button = QPushButton("+30 dias")
    due_plus_60_button = QPushButton("+60 dias")
    due_quick_row.addWidget(due_plus_15_button)
    due_quick_row.addWidget(due_plus_30_button)
    due_quick_row.addWidget(due_plus_60_button)
    due_quick_row.addStretch()
    due_plus_15_button.clicked.connect(lambda: set_due_date_from_offset(15))
    due_plus_30_button.clicked.connect(lambda: set_due_date_from_offset(30))
    due_plus_60_button.clicked.connect(lambda: set_due_date_from_offset(60))
    deposit_spin = QDoubleSpinBox()
    deposit_spin.setRange(0.01, 999999.99)
    deposit_spin.setDecimals(2)
    deposit_spin.setPrefix("$")
    deposit_spin.setValue(0.01)
    notes_input = QTextEdit()
    notes_input.setMaximumHeight(90)
    form.addRow("Anticipo", deposit_spin)
    form.addRow("Fecha de vencimiento", due_input)
    form.addRow("", due_quick_row)
    form.addRow("Observacion", notes_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addLayout(line_row)
    layout.addWidget(items_table)
    layout.addWidget(subtotal_label)
    layout.addWidget(total_label)
    layout.addWidget(minimum_deposit_label)
    layout.addWidget(buttons)
    refresh_items_table()
    sku_input.setFocus()
    sku_input.selectAll()
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    if not items:
        QMessageBox.warning(window, "Sin presentaciones", "Agrega al menos una presentacion al apartado.")
        return None
    return {
        "cliente_id": (
            int(client_selector.currentData()["id"])
            if isinstance(client_selector.currentData(), dict)
            else None
        ),
        "cliente_nombre": customer_input.text().strip(),
        "cliente_telefono": phone_input.text().strip(),
        "items": [
            ApartadoItemInput(
                sku=str(item["sku"]),
                cantidad=int(item["cantidad"]),
            )
            for item in items
        ],
        "anticipo": Decimal(str(deposit_spin.value())),
        "fecha_compromiso": due_input.date().toPyDate().isoformat(),
        "observacion": notes_input.toPlainText().strip(),
    }
