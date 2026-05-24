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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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
from pos_uniformes.services.sale_cart_update_service import add_sale_cart_variants
from pos_uniformes.services.sports_uniform_pricing_service import build_three_piece_playera_price_override
from pos_uniformes.ui.helpers.date_field_helper import configure_friendly_date_edit
from pos_uniformes.ui.helpers.quote_sports_uniform_helper import build_three_piece_quote_description
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    resolve_sale_scan_variants,
    restore_sports_uniform_playera_price_if_needed,
)
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
    dialog = QDialog(window)
    dialog.setWindowTitle("Nuevo apartado")
    dialog.setModal(True)
    dialog.setMinimumWidth(760)
    dialog.setMinimumHeight(600)

    outer_layout = QVBoxLayout()
    outer_layout.setSpacing(8)

    helper = QLabel("Escanea o busca un cliente, agrega presentaciones y registra el anticipo.")
    helper.setWordWrap(True)
    helper.setObjectName("subtleLine")
    outer_layout.addWidget(helper)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll_content = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(12)
    scroll_content.setLayout(layout)
    scroll.setWidget(scroll_content)

    # ── Estado del cliente seleccionado ──
    selected_client_state: dict[str, object] = {"id": None, "nombre": "", "telefono": ""}

    # ── Seccion 1: Cliente ──
    client_box = QGroupBox("1. Cliente")
    client_box.setObjectName("infoCard")
    client_inner = QVBoxLayout()
    client_inner.setSpacing(8)

    # Fila de escaneo QR
    client_qr_input = QLineEdit()
    client_qr_input.setPlaceholderText("Escanea QR de cliente o escribe codigo (ej. CLI-000012)")
    client_qr_input.setEchoMode(QLineEdit.EchoMode.Password)

    # Fila de busqueda por nombre
    client_search_input = QLineEdit()
    client_search_input.setPlaceholderText("Buscar por nombre o telefono...")

    client_search_results = QComboBox()
    client_search_results.setVisible(False)

    # Boton crear nuevo
    create_client_btn = QPushButton("+ Nuevo cliente")

    search_row = QHBoxLayout()
    search_row.setSpacing(8)
    search_row.addWidget(client_search_input, 1)
    search_row.addWidget(create_client_btn)

    # Info del cliente seleccionado
    client_info_label = QLabel("Ningun cliente seleccionado")
    client_info_label.setObjectName("analyticsLine")
    client_info_label.setWordWrap(True)
    clear_client_btn = QPushButton("Quitar cliente")
    clear_client_btn.setVisible(False)

    info_row = QHBoxLayout()
    info_row.addWidget(client_info_label, 1)
    info_row.addWidget(clear_client_btn)

    def _set_client(client_id: int, nombre: str, telefono: str) -> None:
        selected_client_state["id"] = client_id
        selected_client_state["nombre"] = nombre
        selected_client_state["telefono"] = telefono
        tel_display = telefono if telefono else "sin telefono"
        client_info_label.setText(f"✓ {nombre}  ·  {tel_display}")
        client_info_label.setStyleSheet("color: green; font-weight: bold;")
        clear_client_btn.setVisible(True)
        # Re-price items for new client
        reprice_items_for_selected_client()
        refresh_items_table()

    def _clear_client() -> None:
        selected_client_state["id"] = None
        selected_client_state["nombre"] = ""
        selected_client_state["telefono"] = ""
        client_info_label.setText("Ningun cliente seleccionado")
        client_info_label.setStyleSheet("")
        clear_client_btn.setVisible(False)
        reprice_items_for_selected_client()
        refresh_items_table()

    def handle_client_qr() -> None:
        raw = client_qr_input.text().strip()
        client_qr_input.clear()
        if not raw:
            return
        try:
            with get_session() as session:
                # Try by codigo_cliente first
                clients = ClientService.list_clients(session, search_text=raw)
                active = [c for c in clients if c.activo]
                if len(active) == 1:
                    c = active[0]
                    _set_client(int(c.id), c.nombre, c.telefono or "")
                    return
                elif len(active) > 1:
                    # Multiple matches — pick exact code match
                    exact = [c for c in active if (c.codigo_cliente or "").strip().upper() == raw.upper()]
                    if exact:
                        c = exact[0]
                        _set_client(int(c.id), c.nombre, c.telefono or "")
                        return
                QMessageBox.warning(dialog, "Cliente no encontrado", f"No se encontro un cliente activo con '{raw}'.")
        except Exception as exc:
            QMessageBox.warning(dialog, "Error", str(exc))

    def handle_client_search() -> None:
        query = client_search_input.text().strip()
        if not query:
            client_search_results.clear()
            client_search_results.setVisible(False)
            return
        try:
            with get_session() as session:
                clients = ClientService.list_clients(session, search_text=query)
                active = [c for c in clients if c.activo]
            client_search_results.clear()
            if not active:
                client_search_results.addItem("Sin resultados", None)
                client_search_results.setVisible(True)
                return
            for c in active[:20]:
                tel = f" · {c.telefono}" if c.telefono else ""
                client_search_results.addItem(
                    f"{c.codigo_cliente} · {c.nombre}{tel}",
                    {"id": int(c.id), "nombre": c.nombre, "telefono": c.telefono or ""},
                )
            client_search_results.setVisible(True)
        except Exception:
            pass

    def handle_search_result_selected() -> None:
        data = client_search_results.currentData()
        if isinstance(data, dict):
            _set_client(int(data["id"]), str(data["nombre"]), str(data.get("telefono", "")))
            client_search_results.setVisible(False)
            client_search_input.clear()

    def handle_create_client() -> None:
        from pos_uniformes.ui.dialogs.settings_prompt_dialogs import prompt_client_data
        from pos_uniformes.ui.helpers.settings_client_helper import create_settings_client
        data = prompt_client_data(
            dialog,
            title="Crear cliente",
            helper_text="Captura los datos base del cliente para el apartado.",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                result = create_settings_client(
                    session,
                    admin_user_id=window.user_id,
                    payload=data,
                    render_card=window._render_client_card_safe,
                )
                session.commit()
                # Find the newly created client
                all_clients = ClientService.list_clients(session)
                new_client = next(
                    (c for c in all_clients if c.nombre == data.get("nombre", "").strip()),
                    None,
                )
                if new_client:
                    _set_client(int(new_client.id), new_client.nombre, new_client.telefono or "")
                    QMessageBox.information(dialog, "Cliente creado", f"Cliente '{new_client.nombre}' creado y seleccionado.")
                    return
        except Exception as exc:
            QMessageBox.critical(dialog, "Error", str(exc))
            return
        QMessageBox.information(dialog, "Cliente creado", "Cliente creado. Buscalo para seleccionarlo.")

    client_qr_input.returnPressed.connect(handle_client_qr)
    client_search_input.returnPressed.connect(handle_client_search)
    client_search_results.activated.connect(handle_search_result_selected)
    clear_client_btn.clicked.connect(_clear_client)
    create_client_btn.clicked.connect(handle_create_client)

    client_inner.addWidget(client_qr_input)
    client_inner.addLayout(search_row)
    client_inner.addWidget(client_search_results)
    client_inner.addLayout(info_row)
    client_box.setLayout(client_inner)

    # ── Seccion 2: Productos ──
    products_box = QGroupBox("2. Presentaciones")
    products_box.setObjectName("infoCard")
    products_layout = QVBoxLayout()
    products_layout.setSpacing(8)

    items: list[dict[str, object]] = [
        {
            "sku": str(item["sku"]),
            "producto_nombre": str(item["producto_nombre"]),
            "cantidad": int(item["cantidad"]),
            "precio_unitario": Decimal(item["precio_unitario"]),
            "precio_base": Decimal(item.get("precio_base", item["precio_unitario"])),
            "pricing_rule_key": str(item.get("pricing_rule_key", "") or ""),
            "pricing_rule_label": str(item.get("pricing_rule_label", "") or ""),
            "internal_trace_note": str(item.get("internal_trace_note", "") or ""),
            "internal_trace_scope": str(item.get("internal_trace_scope", "") or ""),
            "sports_uniform_base_sku": str(item.get("sports_uniform_base_sku", "") or ""),
            "sports_uniform_playera_sku": str(item.get("sports_uniform_playera_sku", "") or ""),
            "sports_uniform_role": str(item.get("sports_uniform_role", "") or ""),
        }
        for item in (initial_items or [])
    ]
    for item in items:
        if str(item.get("pricing_rule_label", "") or "").strip() and "conjunto deportivo 3pz" not in str(
            item.get("producto_nombre", "")
        ).casefold():
            school_name = ""
            trace_note = str(item.get("internal_trace_note", "") or "")
            if "misma escuela" not in trace_note.casefold():
                school_name = ""
            item["producto_nombre"] = build_three_piece_quote_description(
                str(item.get("producto_nombre", "") or ""),
                school_name=school_name,
            )

    sku_input = QLineEdit()
    sku_input.setPlaceholderText("Escanea o escribe un SKU")
    if selected_catalog_row is not None:
        sku_input.setText(str(selected_catalog_row["sku"]))
    qty_spin = QSpinBox()
    qty_spin.setRange(1, 100)
    add_item_button = QPushButton("Agregar")
    remove_item_button = QPushButton("Quitar seleccionada")

    scan_row = QHBoxLayout()
    scan_row.setSpacing(8)
    scan_row.addWidget(QLabel("SKU"))
    scan_row.addWidget(sku_input, 1)
    scan_row.addWidget(QLabel("Cant."))
    scan_row.addWidget(qty_spin)
    scan_row.addWidget(add_item_button)
    scan_row.addWidget(remove_item_button)

    items_table = QTableWidget()
    items_table.setColumnCount(5)
    items_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
    items_table.setObjectName("dataTable")
    items_table.verticalHeader().setVisible(False)
    items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    items_table.setAlternatingRowColors(True)

    subtotal_label = QLabel("Subtotal estimado: $0.00")
    subtotal_label.setObjectName("analyticsLine")
    total_label = QLabel("Presupuesto estimado: $0.00")
    total_label.setObjectName("analyticsLine")
    minimum_deposit_label = QLabel("Anticipo minimo (20%): $0.00")
    minimum_deposit_label.setObjectName("analyticsLine")

    products_layout.addLayout(scan_row)
    products_layout.addWidget(items_table)
    products_layout.addWidget(subtotal_label)
    products_layout.addWidget(total_label)
    products_layout.addWidget(minimum_deposit_label)
    products_box.setLayout(products_layout)

    # ── Seccion 3: Detalles del apartado ──
    details_box = QGroupBox("3. Detalles del apartado")
    details_box.setObjectName("infoCard")
    details_form = QFormLayout()
    details_form.setSpacing(8)

    deposit_spin = QDoubleSpinBox()
    deposit_spin.setRange(0.01, 999999.99)
    deposit_spin.setDecimals(2)
    deposit_spin.setPrefix("$")
    deposit_spin.setValue(0.01)

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

    def set_due_date_from_offset(days: int) -> None:
        target_date = date.today() + timedelta(days=days)
        due_input.setDate(QDate(target_date.year, target_date.month, target_date.day))

    due_plus_15_button.clicked.connect(lambda: set_due_date_from_offset(15))
    due_plus_30_button.clicked.connect(lambda: set_due_date_from_offset(30))
    due_plus_60_button.clicked.connect(lambda: set_due_date_from_offset(60))

    notes_input = QTextEdit()
    notes_input.setMaximumHeight(70)

    employee_qr_input = QLineEdit()
    employee_qr_input.setPlaceholderText("Escanea QR de empleada (opcional)")
    employee_qr_input.setEchoMode(QLineEdit.EchoMode.Password)
    employee_name_label = QLabel("—")
    employee_state: dict[str, str | None] = {"code": None, "display_name": None}

    def resolve_employee_qr() -> None:
        raw = employee_qr_input.text().strip()
        if not raw:
            employee_state["code"] = None
            employee_state["display_name"] = None
            employee_name_label.setText("—")
            return
        try:
            from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
            with get_session() as _session:
                emp = EmployeeIdentityService.resolve_employee_by_qr_code(_session, raw)
            if emp is None:
                employee_state["code"] = None
                employee_state["display_name"] = None
                employee_name_label.setText("QR no reconocido")
            else:
                employee_state["code"] = str(emp.codigo)
                display = EmployeeIdentityService.build_visible_employee_name(str(emp.nombre_completo or emp.codigo))
                employee_state["display_name"] = display
                employee_name_label.setText(display)
        except Exception:  # noqa: BLE001
            employee_state["code"] = None
            employee_state["display_name"] = None
            employee_name_label.setText("Error al verificar QR")
        employee_qr_input.clear()

    employee_qr_input.returnPressed.connect(resolve_employee_qr)
    emp_row = QHBoxLayout()
    emp_row.addWidget(employee_qr_input, 1)
    emp_row.addWidget(employee_name_label)

    details_form.addRow("Anticipo", deposit_spin)
    details_form.addRow("Vencimiento", due_input)
    details_form.addRow("", due_quick_row)
    details_form.addRow("Observacion", notes_input)
    details_form.addRow("Empleada", emp_row)
    details_box.setLayout(details_form)

    # ── Logica ──
    def current_selected_client_id() -> int | None:
        cid = selected_client_state.get("id")
        if cid is None:
            return None
        try:
            return int(cid)
        except (TypeError, ValueError):
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
            if str(item.get("pricing_rule_key", "") or "").strip():
                continue
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
                f"Presupuesto estimado: ${pricing.total} | Ajuste: ${pricing.rounding_adjustment}"
            )
        else:
            total_label.setText(f"Presupuesto estimado: ${pricing.total}")
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
                resolution = resolve_sale_scan_variants(
                    dialog,
                    session,
                    variante,
                    variant_loader=ApartadoService.obtener_variante_por_sku,
                )
                if resolution is None:
                    return
                base_price_by_sku = {
                    str(getattr(variant, "sku", "") or "").strip().upper(): Decimal(str(getattr(variant, "precio_venta", 0)))
                    for variant in resolution.variants
                }
                updated_lines = add_sale_cart_variants(
                    items,
                    variants=list(resolution.variants),
                    quantity=cantidad,
                    stock_validator=InventarioService.validar_stock_disponible,
                    line_overrides_by_sku=(
                        {
                            str(getattr(resolution.variants[1], "sku", "") or "").strip().upper(): (
                                build_three_piece_playera_price_override(resolution.variants[1])
                            )
                        }
                        if resolution.composed_as_three_pieces and len(resolution.variants) >= 2
                        else None
                    ),
                )
                for line_item in updated_lines:
                    current_sku = str(line_item.get("sku") or "").strip().upper()
                    current_variant = next(
                        (variant for variant in resolution.variants if str(getattr(variant, "sku", "") or "").strip().upper() == current_sku),
                        None,
                    )
                    if current_variant is None:
                        continue
                    product = getattr(current_variant, "producto", None)
                    school_name = str(getattr(getattr(product, "escuela", None), "nombre", "") or "General")
                    base_name = sanitize_product_display_name(getattr(product, "nombre", ""))
                    line_item["precio_base"] = base_price_by_sku[current_sku]
                    line_item["producto_nombre"] = (
                        build_three_piece_quote_description(base_name, school_name=school_name)
                        if str(line_item.get("pricing_rule_label") or "").strip()
                        else base_name
                    )
                    if resolution.composed_as_three_pieces and len(resolution.variants) >= 2:
                        base_variant, playera_variant = resolution.variants[0], resolution.variants[1]
                        base_sku = str(getattr(base_variant, "sku", "") or "").strip().upper()
                        playera_sku = str(getattr(playera_variant, "sku", "") or "").strip().upper()
                        line_item["internal_trace_scope"] = "SPORTS_UNIFORM_PROTOTYPE"
                        line_item["sports_uniform_base_sku"] = base_sku
                        line_item["sports_uniform_playera_sku"] = playera_sku
                        line_item["sports_uniform_role"] = "base" if current_sku == base_sku else "playera"
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "Stock insuficiente" in message:
                message = f"No hay stock suficiente para reservar {cantidad} pieza(s) de '{sku}'."
            QMessageBox.warning(dialog, "No se pudo agregar", message)
            return

        sku_input.clear()
        qty_spin.setValue(1)
        refresh_items_table()

    def handle_remove_item() -> None:
        row_index = items_table.currentRow()
        if row_index < 0 or row_index >= len(items):
            return
        removed_line_item = dict(items[row_index])
        items.pop(row_index)
        restore_message = restore_sports_uniform_playera_price_if_needed(
            items,
            removed_line_item=removed_line_item,
        )
        if restore_message:
            with get_session() as session:
                playera_sku = str(removed_line_item.get("sports_uniform_playera_sku") or "").strip().upper()
                for item in items:
                    if str(item.get("sku") or "").strip().upper() != playera_sku:
                        continue
                    variante = ApartadoService.obtener_variante_por_sku(session, playera_sku)
                    if variante is None:
                        continue
                    item["producto_nombre"] = sanitize_product_display_name(variante.producto.nombre)
            QMessageBox.information(dialog, "Precio restaurado", restore_message)
        refresh_items_table()

    add_item_button.clicked.connect(handle_add_item)
    remove_item_button.clicked.connect(handle_remove_item)
    sku_input.returnPressed.connect(handle_add_item)

    # ── Botones finales ──
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    # ── Layout final con scroll ──
    layout.addWidget(client_box)
    layout.addWidget(products_box)
    layout.addWidget(details_box)
    layout.addStretch()

    outer_layout.addWidget(scroll, 1)
    outer_layout.addWidget(buttons)
    dialog.setLayout(outer_layout)

    refresh_items_table()
    client_qr_input.setFocus()

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    if current_selected_client_id() is None:
        QMessageBox.warning(window, "Cliente requerido", "Selecciona un cliente antes de crear el apartado.")
        return None

    if not items:
        QMessageBox.warning(window, "Sin presentaciones", "Agrega al menos una presentacion al apartado.")
        return None

    return {
        "cliente_id": current_selected_client_id(),
        "cliente_nombre": str(selected_client_state.get("nombre", "")),
        "cliente_telefono": str(selected_client_state.get("telefono", "")),
        "items": [
            ApartadoItemInput(
                sku=str(item["sku"]),
                cantidad=int(item["cantidad"]),
                precio_unitario=Decimal(item["precio_unitario"]),
                pricing_rule_key=str(item.get("pricing_rule_key", "") or ""),
                pricing_rule_label=str(item.get("pricing_rule_label", "") or ""),
            )
            for item in items
        ],
        "anticipo": Decimal(str(deposit_spin.value())),
        "fecha_compromiso": due_input.date().toPyDate().isoformat(),
        "observacion": notes_input.toPlainText().strip(),
        "seller_employee_code": employee_state["code"],
        "seller_employee_display_name": employee_state["display_name"],
    }
