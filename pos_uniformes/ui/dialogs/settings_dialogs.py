"""Builders de dialogs para el modulo Configuracion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.date_field_helper import configure_friendly_date_edit

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def _create_settings_dialog(
    parent: "MainWindow",
    title: str,
    helper_text: str | None = None,
    width: int = 460,
) -> tuple[QDialog, QVBoxLayout]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(width)
    layout = QVBoxLayout()
    layout.setSpacing(12)
    if helper_text:
        helper = QLabel(helper_text)
        helper.setWordWrap(True)
        helper.setObjectName("subtleLine")
        layout.addWidget(helper)
    dialog.setLayout(layout)
    return dialog, layout


def build_users_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Usuarios y acceso",
        "Administra usuarios del POS. Aqui puedes crear cuentas, activar o desactivar, cambiar rol y actualizar contrasenas.",
        width=920,
    )
    window.settings_users_status_label.setObjectName("analyticsLine")
    actions = QHBoxLayout()
    window.settings_create_user_button.setObjectName("toolbarPrimaryButton")
    window.settings_edit_user_button.setObjectName("toolbarSecondaryButton")
    window.settings_toggle_user_button.setObjectName("toolbarSecondaryButton")
    window.settings_change_role_button.setObjectName("toolbarSecondaryButton")
    window.settings_change_password_button.setObjectName("toolbarGhostButton")
    window.settings_create_user_button.clicked.connect(window._handle_create_user)
    window.settings_edit_user_button.clicked.connect(window._handle_edit_user)
    window.settings_toggle_user_button.clicked.connect(window._handle_toggle_user)
    window.settings_change_role_button.clicked.connect(window._handle_change_user_role)
    window.settings_change_password_button.clicked.connect(window._handle_change_user_password)
    actions.addWidget(window.settings_create_user_button)
    actions.addWidget(window.settings_edit_user_button)
    actions.addWidget(window.settings_toggle_user_button)
    actions.addWidget(window.settings_change_role_button)
    actions.addWidget(window.settings_change_password_button)
    actions.addStretch()

    window.settings_users_table.setColumnCount(5)
    window.settings_users_table.setHorizontalHeaderLabels(
        ["Username", "Nombre", "Rol", "Estado", "Actualizado"]
    )
    window.settings_users_table.setObjectName("dataTable")
    window.settings_users_table.verticalHeader().setVisible(False)
    window.settings_users_table.setSelectionBehavior(window.settings_users_table.SelectionBehavior.SelectRows)
    window.settings_users_table.setAlternatingRowColors(True)
    window.settings_users_table.setMinimumHeight(320)
    window.settings_users_table.horizontalHeader().setStretchLastSection(True)
    window.settings_users_table.itemDoubleClicked.connect(window._handle_edit_user)

    layout.addWidget(window.settings_users_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_users_table, 1)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_suppliers_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Proveedores",
        "Administra proveedores para compras y reposicion. Puedes crear, editar y activar o desactivar proveedores.",
        width=980,
    )
    window.settings_suppliers_status_label.setObjectName("analyticsLine")
    actions = QHBoxLayout()
    window.settings_suppliers_search_input.setPlaceholderText("Buscar por nombre, telefono, correo o direccion")
    window.settings_create_supplier_button.setObjectName("toolbarPrimaryButton")
    window.settings_update_supplier_button.setObjectName("toolbarSecondaryButton")
    window.settings_toggle_supplier_button.setObjectName("toolbarGhostButton")
    window.settings_suppliers_search_input.textChanged.connect(window._refresh_settings_suppliers)
    window.settings_create_supplier_button.clicked.connect(window._handle_create_supplier)
    window.settings_update_supplier_button.clicked.connect(window._handle_update_supplier)
    window.settings_toggle_supplier_button.clicked.connect(window._handle_toggle_supplier)
    actions.addWidget(QLabel("Buscar"))
    actions.addWidget(window.settings_suppliers_search_input, 1)
    actions.addWidget(window.settings_create_supplier_button)
    actions.addWidget(window.settings_update_supplier_button)
    actions.addWidget(window.settings_toggle_supplier_button)

    window.settings_suppliers_table.setColumnCount(6)
    window.settings_suppliers_table.setHorizontalHeaderLabels(
        ["Proveedor", "Telefono", "Correo", "Direccion", "Estado", "Actualizado"]
    )
    window.settings_suppliers_table.setObjectName("dataTable")
    window.settings_suppliers_table.verticalHeader().setVisible(False)
    window.settings_suppliers_table.setSelectionBehavior(
        window.settings_suppliers_table.SelectionBehavior.SelectRows
    )
    window.settings_suppliers_table.setAlternatingRowColors(True)
    window.settings_suppliers_table.setMinimumHeight(320)
    window.settings_suppliers_table.horizontalHeader().setStretchLastSection(True)

    layout.addWidget(window.settings_suppliers_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_suppliers_table)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_clients_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Clientes",
        "Administra clientes para futuras ventas, apartados y programas de fidelizacion.",
        width=1040,
    )
    window.settings_clients_status_label.setObjectName("analyticsLine")
    actions = QHBoxLayout()
    window.settings_clients_search_input.setPlaceholderText("Buscar por codigo, nombre, telefono, tipo, nivel o notas")
    window.settings_create_client_button.setObjectName("toolbarPrimaryButton")
    window.settings_update_client_button.setObjectName("toolbarSecondaryButton")
    window.settings_toggle_client_button.setObjectName("toolbarGhostButton")
    window.settings_generate_client_qr_button.setObjectName("toolbarSecondaryButton")
    window.settings_client_whatsapp_button.setObjectName("toolbarGhostButton")
    window.settings_client_whatsapp_button.setText("WhatsApp + credencial")
    window.settings_clients_search_input.textChanged.connect(window._refresh_settings_clients)
    window.settings_create_client_button.clicked.connect(window._handle_create_client)
    window.settings_update_client_button.clicked.connect(window._handle_update_client)
    window.settings_toggle_client_button.clicked.connect(window._handle_toggle_client)
    window.settings_generate_client_qr_button.clicked.connect(window._handle_generate_client_qr)
    window.settings_client_whatsapp_button.clicked.connect(window._handle_open_client_whatsapp)
    actions.addWidget(QLabel("Buscar"))
    actions.addWidget(window.settings_clients_search_input, 1)
    actions.addWidget(window.settings_create_client_button)
    actions.addWidget(window.settings_update_client_button)
    actions.addWidget(window.settings_toggle_client_button)
    actions.addWidget(window.settings_generate_client_qr_button)
    actions.addWidget(window.settings_client_whatsapp_button)

    window.settings_clients_table.setColumnCount(11)
    window.settings_clients_table.setHorizontalHeaderLabels(
        ["Codigo", "Cliente", "Tipo", "Nivel", "Desc.", "Telefono", "Notas", "QR", "Credencial", "Estado", "Actualizado"]
    )
    window.settings_clients_table.setObjectName("dataTable")
    window.settings_clients_table.verticalHeader().setVisible(False)
    window.settings_clients_table.setSelectionBehavior(window.settings_clients_table.SelectionBehavior.SelectRows)
    window.settings_clients_table.setAlternatingRowColors(True)
    window.settings_clients_table.setMinimumHeight(340)
    window.settings_clients_table.horizontalHeader().setStretchLastSection(True)

    layout.addWidget(window.settings_clients_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_clients_table)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_employees_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Empleadas",
        "Administra codigos EMP y nombres visibles del equipo comercial para resolver responsable por escaneo en Caja.",
        width=1240,
    )
    window.settings_employees_status_label.setObjectName("analyticsLine")
    actions = QHBoxLayout()
    window.settings_employees_search_input.setPlaceholderText("Buscar por codigo o nombre")
    window.settings_employees_activity_filter_combo.clear()
    window.settings_employees_activity_filter_combo.addItems(
        ["Todas", "Activa hoy", "Activa 7d", "Sin actividad"]
    )
    window.settings_employees_activity_filter_combo.setObjectName("toolbarSecondaryButton")
    window.settings_create_employee_button.setObjectName("toolbarPrimaryButton")
    window.settings_update_employee_button.setObjectName("toolbarSecondaryButton")
    window.settings_toggle_employee_button.setObjectName("toolbarGhostButton")
    window.settings_set_employee_pin_button.setObjectName("toolbarSecondaryButton")
    window.settings_generate_employee_qr_button.setObjectName("toolbarSecondaryButton")
    window.settings_generate_employee_card_button.setObjectName("toolbarGhostButton")
    window.settings_employees_search_input.textChanged.connect(window._refresh_settings_employees)
    window.settings_employees_activity_filter_combo.currentTextChanged.connect(window._refresh_settings_employees)
    window.settings_create_employee_button.clicked.connect(window._handle_create_employee)
    window.settings_update_employee_button.clicked.connect(window._handle_update_employee)
    window.settings_toggle_employee_button.clicked.connect(window._handle_toggle_employee)
    window.settings_set_employee_pin_button.clicked.connect(window._handle_set_employee_pin)
    window.settings_generate_employee_qr_button.clicked.connect(window._handle_generate_employee_qr)
    window.settings_generate_employee_card_button.clicked.connect(window._handle_generate_employee_card)
    window.settings_open_employee_ranking_button.setObjectName("toolbarSecondaryButton")
    window.settings_open_employee_ranking_button.clicked.connect(window._open_employee_ranking_dialog)
    actions.addWidget(QLabel("Buscar"))
    actions.addWidget(window.settings_employees_search_input, 1)
    actions.addWidget(QLabel("Actividad"))
    actions.addWidget(window.settings_employees_activity_filter_combo)
    actions.addWidget(window.settings_create_employee_button)
    actions.addWidget(window.settings_update_employee_button)
    actions.addWidget(window.settings_toggle_employee_button)
    actions.addWidget(window.settings_set_employee_pin_button)
    actions.addWidget(window.settings_generate_employee_qr_button)
    actions.addWidget(window.settings_generate_employee_card_button)
    actions.addWidget(window.settings_open_employee_ranking_button)

    window.settings_employees_table.setColumnCount(9)
    window.settings_employees_table.setHorizontalHeaderLabels(
        ["Codigo", "Nombre completo", "Visible", "Actividad", "PIN", "QR", "Credencial", "Estado", "Actualizado"]
    )
    window.settings_employees_table.setObjectName("dataTable")
    window.settings_employees_table.verticalHeader().setVisible(False)
    window.settings_employees_table.setSelectionBehavior(window.settings_employees_table.SelectionBehavior.SelectRows)
    window.settings_employees_table.setAlternatingRowColors(True)
    window.settings_employees_table.setMinimumHeight(320)
    window.settings_employees_table.horizontalHeader().setStretchLastSection(True)
    window.settings_employees_table.itemDoubleClicked.connect(window._handle_update_employee)
    window.settings_employees_table.itemSelectionChanged.connect(window._refresh_settings_employee_detail)

    detail_box = QGroupBox("Detalle de empleada")
    detail_box.setObjectName("infoCard")
    detail_layout = QVBoxLayout()
    detail_layout.setSpacing(8)
    window.settings_employee_detail_name_label.setObjectName("dashboardSummaryTitle")
    window.settings_employee_detail_meta_label.setObjectName("inventoryMetaCard")
    window.settings_employee_detail_assets_label.setObjectName("inventoryMetaCardAlt")
    window.settings_employee_detail_today_label.setObjectName("inventoryMetaCard")
    window.settings_employee_detail_last_sale_label.setObjectName("inventoryMetaCardAlt")
    window.settings_employee_activity_status_label.setObjectName("subtleLine")
    window.settings_employee_toggle_amounts_button.setObjectName("toolbarGhostButton")
    window.settings_employee_period_combo.clear()
    window.settings_employee_period_combo.addItems(["Hoy", "7 dias", "30 dias"])
    window.settings_employee_period_combo.setObjectName("toolbarSecondaryButton")
    window.settings_employee_period_combo.currentTextChanged.connect(window._refresh_settings_employee_detail)
    window.settings_employee_toggle_amounts_button.clicked.connect(window._handle_toggle_settings_employee_amounts)
    for label in (
        window.settings_employee_detail_name_label,
        window.settings_employee_detail_meta_label,
        window.settings_employee_detail_assets_label,
        window.settings_employee_detail_today_label,
        window.settings_employee_detail_last_sale_label,
        window.settings_employee_activity_status_label,
    ):
        label.setWordWrap(True)
    window.settings_employee_activity_table.setColumnCount(4)
    window.settings_employee_activity_table.setHorizontalHeaderLabels(["Dia", "Piezas", "Tickets", "Monto"])
    window.settings_employee_activity_table.setObjectName("dataTable")
    window.settings_employee_activity_table.verticalHeader().setVisible(False)
    window.settings_employee_activity_table.setSelectionBehavior(
        window.settings_employee_activity_table.SelectionBehavior.SelectRows
    )
    window.settings_employee_activity_table.setEditTriggers(
        window.settings_employee_activity_table.EditTrigger.NoEditTriggers
    )
    window.settings_employee_activity_table.setAlternatingRowColors(True)
    window.settings_employee_activity_table.setMinimumHeight(240)
    window.settings_employee_activity_table.horizontalHeader().setStretchLastSection(True)
    window.settings_employee_activity_table.itemDoubleClicked.connect(window._open_settings_employee_day_sales_dialog)
    activity_header = QHBoxLayout()
    activity_header.setSpacing(8)
    activity_header.addWidget(window.settings_employee_activity_status_label, 1)
    activity_header.addWidget(QLabel("Periodo"))
    activity_header.addWidget(window.settings_employee_period_combo)
    activity_header.addWidget(window.settings_employee_toggle_amounts_button)
    detail_layout.addWidget(window.settings_employee_detail_name_label)
    detail_layout.addWidget(window.settings_employee_detail_meta_label)
    detail_layout.addWidget(window.settings_employee_detail_assets_label)
    detail_layout.addWidget(window.settings_employee_detail_today_label)
    detail_layout.addWidget(window.settings_employee_detail_last_sale_label)
    detail_layout.addLayout(activity_header)
    detail_layout.addWidget(window.settings_employee_activity_table, 1)
    detail_box.setLayout(detail_layout)

    content_layout = QHBoxLayout()
    content_layout.setSpacing(12)
    content_layout.addWidget(window.settings_employees_table, 3)
    content_layout.addWidget(detail_box, 2)

    layout.addWidget(window.settings_employees_status_label)
    layout.addLayout(actions)
    layout.addLayout(content_layout)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_employee_day_sales_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Tickets del dia",
        "Consulta los tickets confirmados acreditados a la empleada en la fecha seleccionada.",
        width=860,
    )
    window.settings_employee_day_sales_status_label.setObjectName("subtleLine")
    window.settings_employee_view_ticket_button.setObjectName("toolbarSecondaryButton")
    window.settings_employee_view_ticket_button.clicked.connect(window._handle_view_settings_employee_day_sale_ticket)
    window.settings_employee_day_sales_table.setColumnCount(5)
    window.settings_employee_day_sales_table.setHorizontalHeaderLabels(
        ["Hora", "Folio", "Cliente", "Piezas", "Total"]
    )
    window.settings_employee_day_sales_table.setObjectName("dataTable")
    window.settings_employee_day_sales_table.verticalHeader().setVisible(False)
    window.settings_employee_day_sales_table.setSelectionBehavior(
        window.settings_employee_day_sales_table.SelectionBehavior.SelectRows
    )
    window.settings_employee_day_sales_table.setAlternatingRowColors(True)
    window.settings_employee_day_sales_table.setEditTriggers(
        window.settings_employee_day_sales_table.EditTrigger.NoEditTriggers
    )
    window.settings_employee_day_sales_table.horizontalHeader().setStretchLastSection(True)
    window.settings_employee_day_sales_table.itemDoubleClicked.connect(
        window._handle_view_settings_employee_day_sale_ticket
    )
    window.settings_employee_day_sales_table.itemSelectionChanged.connect(
        window._refresh_settings_employee_day_sale_actions
    )

    actions = QHBoxLayout()
    actions.addWidget(window.settings_employee_day_sales_status_label, 1)
    actions.addWidget(window.settings_employee_view_ticket_button)

    layout.addLayout(actions)
    layout.addWidget(window.settings_employee_day_sales_table, 1)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_employee_sale_detail_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Detalle de ticket",
        "Consulta los productos incluidos en el ticket seleccionado.",
        width=980,
    )
    window.settings_employee_sale_detail_status_label.setObjectName("subtleLine")
    window.settings_employee_sale_detail_table.setColumnCount(5)
    window.settings_employee_sale_detail_table.setHorizontalHeaderLabels(
        ["SKU", "Producto", "Cantidad", "Precio", "Subtotal"]
    )
    window.settings_employee_sale_detail_table.setObjectName("dataTable")
    window.settings_employee_sale_detail_table.verticalHeader().setVisible(False)
    window.settings_employee_sale_detail_table.setSelectionBehavior(
        window.settings_employee_sale_detail_table.SelectionBehavior.SelectRows
    )
    window.settings_employee_sale_detail_table.setAlternatingRowColors(True)
    window.settings_employee_sale_detail_table.setEditTriggers(
        window.settings_employee_sale_detail_table.EditTrigger.NoEditTriggers
    )
    window.settings_employee_sale_detail_table.horizontalHeader().setStretchLastSection(True)

    layout.addWidget(window.settings_employee_sale_detail_status_label)
    layout.addWidget(window.settings_employee_sale_detail_table, 1)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_whatsapp_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "WhatsApp y mensajes",
        "Configura mensajes reutilizables para apartados y seguimiento a clientes. Ajusta el texto, revisa una vista previa y guarda solo cuando te guste el resultado.",
        width=980,
    )
    window.settings_whatsapp_status_label.setObjectName("analyticsLine")
    quick_reference = QLabel(
        "Placeholders disponibles: {cliente}, {folio}, {saldo}, {vencimiento}, "
        "{fecha_compromiso} y {codigo_cliente}."
    )
    quick_reference.setObjectName("subtleLine")
    quick_reference.setWordWrap(True)
    placeholder_hint = QLabel(
        "Toca un placeholder para insertarlo en la plantilla activa o en la que tengas seleccionada en la vista previa."
    )
    placeholder_hint.setObjectName("catalogSectionHint")
    placeholder_hint.setWordWrap(True)
    placeholder_actions = QHBoxLayout()
    placeholder_actions.setSpacing(8)
    whatsapp_box = QGroupBox("Plantillas WhatsApp")
    whatsapp_box.setObjectName("infoCard")
    whatsapp_grid = QGridLayout()
    whatsapp_grid.setHorizontalSpacing(12)
    whatsapp_grid.setVerticalSpacing(12)

    def _build_template_card(
        title: str,
        hint: str,
        placeholder: str,
        editor: QWidget,
    ) -> QWidget:
        card = QWidget()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("catalogSectionTitle")
        hint_label = QLabel(hint)
        hint_label.setObjectName("catalogSectionHint")
        hint_label.setWordWrap(True)

        if hasattr(editor, "setPlaceholderText"):
            editor.setPlaceholderText(placeholder)
        if hasattr(editor, "setMinimumHeight"):
            editor.setMinimumHeight(92)

        card_layout.addWidget(title_label)
        card_layout.addWidget(hint_label)
        card_layout.addWidget(editor)
        return card

    template_editors: dict[str, QTextEdit] = {
        "layaway_reminder": window.settings_whatsapp_layaway_reminder_input,
        "layaway_liquidated": window.settings_whatsapp_layaway_liquidated_input,
        "client_promotion": window.settings_whatsapp_client_promotion_input,
        "client_followup": window.settings_whatsapp_client_followup_input,
        "client_greeting": window.settings_whatsapp_client_greeting_input,
    }

    def _resolve_active_editor() -> QTextEdit:
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, QTextEdit) and focus_widget in template_editors.values():
            return focus_widget
        template_key = str(window.settings_whatsapp_preview_combo.currentData() or "layaway_reminder")
        return template_editors.get(template_key, window.settings_whatsapp_layaway_reminder_input)

    def _insert_placeholder(token: str) -> None:
        editor = _resolve_active_editor()
        editor.insertPlainText(token)
        editor.setFocus()

    for token in (
        "{cliente}",
        "{folio}",
        "{saldo}",
        "{vencimiento}",
        "{fecha_compromiso}",
        "{codigo_cliente}",
    ):
        button = QPushButton(token)
        button.setObjectName("chipButton")
        button.clicked.connect(lambda _checked=False, value=token: _insert_placeholder(value))
        placeholder_actions.addWidget(button)
    placeholder_actions.addStretch()

    window.settings_whatsapp_layaway_reminder_input.setPlaceholderText(
        "Usa {cliente}, {folio}, {saldo}, {vencimiento}, {fecha_compromiso}"
    )
    window.settings_whatsapp_layaway_liquidated_input.setPlaceholderText(
        "Usa {cliente}, {folio}, {fecha_compromiso}"
    )
    window.settings_whatsapp_client_promotion_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    window.settings_whatsapp_client_followup_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    window.settings_whatsapp_client_greeting_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    whatsapp_grid.addWidget(
        _build_template_card(
            "Apartado recordatorio",
            "Usalo para recordar saldo, vencimiento o fecha compromiso.",
            "Hola {cliente}, te recordamos tu apartado {folio}...",
            window.settings_whatsapp_layaway_reminder_input,
        ),
        0,
        0,
    )
    whatsapp_grid.addWidget(
        _build_template_card(
            "Apartado liquidado",
            "Confirmacion breve cuando el apartado ya esta listo o pagado.",
            "Hola {cliente}, tu apartado {folio} ya esta liquidado...",
            window.settings_whatsapp_layaway_liquidated_input,
        ),
        0,
        1,
    )
    whatsapp_grid.addWidget(
        _build_template_card(
            "Cliente promocion",
            "Mensaje corto para campaña, descuento o invitacion a volver.",
            "Hola {cliente}, queremos compartirte una promocion...",
            window.settings_whatsapp_client_promotion_input,
        ),
        1,
        0,
    )
    whatsapp_grid.addWidget(
        _build_template_card(
            "Cliente seguimiento",
            "Seguimiento amable para retomar conversacion o resolver dudas.",
            "Hola {cliente}, te escribimos para dar seguimiento...",
            window.settings_whatsapp_client_followup_input,
        ),
        1,
        1,
    )
    whatsapp_grid.addWidget(
        _build_template_card(
            "Cliente saludo",
            "Saludo corto de bienvenida o continuidad de contacto.",
            "Hola {cliente}, gracias por seguir en contacto...",
            window.settings_whatsapp_client_greeting_input,
        ),
        2,
        0,
        1,
        2,
    )
    whatsapp_box.setLayout(whatsapp_grid)
    preview_box = QGroupBox("Vista previa")
    preview_box.setObjectName("infoCard")
    preview_layout = QVBoxLayout()
    preview_actions = QHBoxLayout()
    window.settings_whatsapp_preview_combo.clear()
    window.settings_whatsapp_preview_combo.addItem("Apartado recordatorio", "layaway_reminder")
    window.settings_whatsapp_preview_combo.addItem("Apartado liquidado", "layaway_liquidated")
    window.settings_whatsapp_preview_combo.addItem("Cliente promocion", "client_promotion")
    window.settings_whatsapp_preview_combo.addItem("Cliente seguimiento", "client_followup")
    window.settings_whatsapp_preview_combo.addItem("Cliente saludo", "client_greeting")
    window.settings_whatsapp_preview_button.setObjectName("toolbarSecondaryButton")
    window.settings_whatsapp_reset_button.setObjectName("toolbarGhostButton")
    window.settings_whatsapp_preview_button.clicked.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_reset_button.clicked.connect(window._handle_reset_whatsapp_templates)
    window.settings_whatsapp_preview_combo.currentIndexChanged.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_preview_output.setReadOnly(True)
    window.settings_whatsapp_preview_output.setMinimumHeight(140)
    preview_hint = QLabel(
        "Elige una plantilla para revisar como se veria con datos reales antes de guardarla."
    )
    preview_hint.setObjectName("templatePreviewLabel")
    preview_hint.setWordWrap(True)
    preview_actions.addWidget(window.settings_whatsapp_preview_combo, 1)
    preview_actions.addWidget(window.settings_whatsapp_preview_button)
    preview_actions.addWidget(window.settings_whatsapp_reset_button)
    window.settings_whatsapp_layaway_reminder_input.textChanged.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_layaway_liquidated_input.textChanged.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_client_promotion_input.textChanged.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_client_followup_input.textChanged.connect(window._refresh_whatsapp_preview)
    window.settings_whatsapp_client_greeting_input.textChanged.connect(window._refresh_whatsapp_preview)
    preview_layout.addWidget(preview_hint)
    preview_layout.addLayout(preview_actions)
    preview_layout.addWidget(window.settings_whatsapp_preview_output)
    preview_box.setLayout(preview_layout)
    window.settings_whatsapp_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_whatsapp_save_button.clicked.connect(window._handle_save_whatsapp_settings)

    # --- Scroll area for all content ---
    content_widget = QWidget()
    content_layout = QVBoxLayout()
    content_layout.setSpacing(12)
    content_layout.addWidget(quick_reference)
    content_layout.addWidget(placeholder_hint)
    content_layout.addLayout(placeholder_actions)
    content_layout.addWidget(window.settings_whatsapp_status_label)
    content_layout.addWidget(whatsapp_box)
    content_layout.addWidget(preview_box)
    content_layout.addStretch()
    content_widget.setLayout(content_layout)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(content_widget)

    layout.addWidget(scroll, 1)
    actions = QHBoxLayout()
    actions.addStretch()
    actions.addWidget(window.settings_whatsapp_save_button)
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    actions.addWidget(close_btn)
    layout.addLayout(actions)
    return dialog


def _build_print_routing_box(dialog: QDialog) -> QGroupBox:
    """Toggle 'imprimir local' vs 'enviar al satélite' para esta PC.

    Es un ajuste POR MÁQUINA (cache local), independiente de la config del
    negocio. En modo satélite, tickets/etiquetas/conteo se encolan para que los
    imprima la PC satélite.
    """
    from pos_uniformes.services.print_routing_cache_service import (
        MODO_LOCAL,
        MODO_SATELITE,
        load_print_routing,
        save_print_routing,
    )

    box = QGroupBox("Modo de impresión de esta PC")
    box.setObjectName("infoCard")
    box_layout = QVBoxLayout()
    box_layout.setSpacing(8)

    hint = QLabel(
        "Local: imprime en las impresoras conectadas a esta PC.\n"
        "Enviar al satélite: encola tickets, etiquetas y conteos para que los "
        "imprima la PC satélite."
    )
    hint.setWordWrap(True)
    hint.setObjectName("subtleLine")

    current_modo, current_origen = load_print_routing()
    radio_local = QRadioButton("Imprimir local (esta PC tiene las impresoras)")
    radio_sat = QRadioButton("Enviar al satélite")
    (radio_sat if current_modo == MODO_SATELITE else radio_local).setChecked(True)

    origen_row = QHBoxLayout()
    origen_label = QLabel("Nombre de esta PC (origen):")
    origen_edit = QLineEdit(current_origen)
    origen_edit.setPlaceholderText("principal / kiosko")
    origen_row.addWidget(origen_label)
    origen_row.addWidget(origen_edit, 1)

    save_btn = QPushButton("Guardar modo de impresión")
    save_btn.setObjectName("toolbarPrimaryButton")

    def _handle_save() -> None:
        modo = MODO_SATELITE if radio_sat.isChecked() else MODO_LOCAL
        origen = origen_edit.text().strip() or "principal"
        try:
            save_print_routing(modo, origen)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        etiqueta = "enviar al satélite" if modo == MODO_SATELITE else "imprimir local"
        QMessageBox.information(dialog, "Guardado", f"Esta PC ahora va a: {etiqueta}.")

    save_btn.clicked.connect(_handle_save)

    box_layout.addWidget(hint)
    box_layout.addWidget(radio_local)
    box_layout.addWidget(radio_sat)
    box_layout.addLayout(origen_row)
    box_layout.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignLeft)
    box.setLayout(box_layout)
    return box


def build_business_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Negocio e impresion",
        "Actualiza los datos visibles del negocio, la informacion de transferencia y la impresion preferida del ticket.",
        width=920,
    )
    window.settings_business_status_label.setObjectName("analyticsLine")
    window.settings_business_name_input.setPlaceholderText("Nombre comercial")
    window.settings_business_name_input.setMinimumHeight(34)
    window.settings_business_logo_input.setPlaceholderText("Ruta del logo para credenciales")
    window.settings_business_logo_input.setReadOnly(True)
    window.settings_business_logo_preview_label.setFixedSize(220, 120)
    window.settings_business_logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.settings_business_logo_preview_label.setObjectName("infoCard")
    window.settings_business_phone_input.setPlaceholderText("Telefono de contacto")
    window.settings_business_phone_input.setMinimumHeight(34)
    window.settings_business_address_input.setPlaceholderText("Direccion visible en ticket")
    window.settings_business_address_input.setMinimumHeight(70)
    window.settings_business_footer_input.setPlaceholderText("Mensaje al pie del ticket")
    window.settings_business_footer_input.setMinimumHeight(70)
    window.settings_business_transfer_bank_input.setPlaceholderText("Banco destino")
    window.settings_business_transfer_bank_input.setMinimumHeight(34)
    window.settings_business_transfer_beneficiary_input.setPlaceholderText("Nombre del beneficiario")
    window.settings_business_transfer_beneficiary_input.setMinimumHeight(34)
    window.settings_business_transfer_clabe_input.setPlaceholderText("CLABE o numero de cuenta")
    window.settings_business_transfer_clabe_input.setMinimumHeight(34)
    window.settings_business_transfer_instructions_input.setPlaceholderText("Indicaciones de pago por transferencia")
    window.settings_business_transfer_instructions_input.setMinimumHeight(70)
    window.settings_business_promo_code_input.setPlaceholderText("Deja vacio para conservar el codigo actual")
    window.settings_business_promo_code_input.setEchoMode(QLineEdit.EchoMode.Password)
    window.settings_business_promo_code_input.setMinimumHeight(34)
    window.settings_business_copies_spin.setRange(1, 5)
    window.settings_business_printer_combo.clear()
    window.settings_business_printer_combo.addItem("Preguntar siempre", "")
    window.settings_business_ticket_printer_combo.clear()
    window.settings_business_ticket_printer_combo.addItem("Preguntar siempre", "")
    for printer in QPrinterInfo.availablePrinters():
        window.settings_business_printer_combo.addItem(printer.printerName(), printer.printerName())
        window.settings_business_ticket_printer_combo.addItem(printer.printerName(), printer.printerName())
    window.settings_business_logo_pick_button.clicked.connect(window._handle_select_business_logo)
    window.settings_business_logo_clear_button.clicked.connect(window._handle_clear_business_logo)

    def _labeled(label_text: str, widget) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #555;")
        vbox.addWidget(lbl)
        vbox.addWidget(widget)
        return vbox

    # --- Identidad visible ---
    identity_box = QGroupBox("Identidad visible")
    identity_box.setObjectName("infoCard")
    identity_layout = QVBoxLayout()
    identity_layout.setSpacing(10)
    identity_layout.addLayout(_labeled("Nombre del negocio", window.settings_business_name_input))
    identity_layout.addLayout(_labeled("Telefono", window.settings_business_phone_input))
    identity_layout.addLayout(_labeled("Direccion", window.settings_business_address_input))
    identity_layout.addLayout(_labeled("Pie de ticket", window.settings_business_footer_input))
    identity_box.setLayout(identity_layout)

    # --- Logo ---
    logo_box = QGroupBox("Logo credencial")
    logo_box.setObjectName("infoCard")
    logo_box_layout = QVBoxLayout()
    logo_box_layout.setSpacing(10)
    logo_hint = QLabel("Se usa en credenciales de cliente y staff. Si no hay logo, se muestra el nombre del negocio.")
    logo_hint.setWordWrap(True)
    logo_hint.setObjectName("subtleLine")
    logo_row = QHBoxLayout()
    logo_row.addWidget(window.settings_business_logo_input, 1)
    logo_row.addWidget(window.settings_business_logo_pick_button)
    logo_row.addWidget(window.settings_business_logo_clear_button)
    logo_box_layout.addWidget(logo_hint)
    logo_box_layout.addLayout(logo_row)
    logo_box_layout.addWidget(window.settings_business_logo_preview_label, 0, Qt.AlignmentFlag.AlignLeft)
    logo_box_layout.addStretch(1)
    logo_box.setLayout(logo_box_layout)

    # --- Transferencia ---
    transfer_box = QGroupBox("Datos de transferencia")
    transfer_box.setObjectName("infoCard")
    transfer_layout = QVBoxLayout()
    transfer_layout.setSpacing(10)
    transfer_layout.addLayout(_labeled("Banco", window.settings_business_transfer_bank_input))
    transfer_layout.addLayout(_labeled("Beneficiario", window.settings_business_transfer_beneficiary_input))
    transfer_layout.addLayout(_labeled("CLABE", window.settings_business_transfer_clabe_input))
    transfer_layout.addLayout(_labeled("Instrucciones de pago", window.settings_business_transfer_instructions_input))
    transfer_box.setLayout(transfer_layout)

    # --- Ticket e impresion ---
    print_box = QGroupBox("Ticket e impresion")
    print_box.setObjectName("infoCard")
    print_layout = QVBoxLayout()
    print_layout.setSpacing(10)
    print_layout.addLayout(_labeled("Codigo promo manual", window.settings_business_promo_code_input))
    print_layout.addLayout(_labeled("Impresora etiquetas", window.settings_business_printer_combo))
    print_layout.addLayout(_labeled("Impresora tickets", window.settings_business_ticket_printer_combo))
    print_layout.addLayout(_labeled("Copias por ticket", window.settings_business_copies_spin))
    print_box.setLayout(print_layout)

    # --- Modo de impresion (ajuste por maquina) ---
    routing_box = _build_print_routing_box(dialog)

    # --- Grid layout ---
    top_row = QHBoxLayout()
    top_row.setSpacing(14)
    top_row.addWidget(identity_box, 3)
    top_row.addWidget(logo_box, 2)

    bottom_row = QHBoxLayout()
    bottom_row.setSpacing(14)
    bottom_row.addWidget(transfer_box, 3)
    bottom_row.addWidget(print_box, 2)

    content_widget = QWidget()
    content_layout = QVBoxLayout()
    content_layout.setSpacing(14)
    content_layout.addLayout(top_row)
    content_layout.addLayout(bottom_row)
    content_layout.addWidget(routing_box)
    content_layout.addStretch()
    content_widget.setLayout(content_layout)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(content_widget)

    window.settings_business_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_business_demo_button.setObjectName("toolbarSecondaryButton")
    window.settings_business_save_button.clicked.connect(window._handle_save_business_settings)
    window.settings_business_demo_button.clicked.connect(window._handle_preview_business_card)

    layout.addWidget(window.settings_business_status_label)
    layout.addWidget(scroll, 1)
    actions = QHBoxLayout()
    actions.addWidget(window.settings_business_demo_button)
    actions.addWidget(window.settings_business_save_button)
    actions.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    actions.addWidget(close_btn)
    layout.addLayout(actions)
    return dialog


def build_marketing_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Marketing y promociones",
        "Configura reglas automaticas de lealtad, descuentos por nivel y recalculo masivo de clientes.",
        width=720,
    )
    window.settings_marketing_status_label.setObjectName("analyticsLine")
    rules_box = QGroupBox("Reglas de lealtad")
    rules_box.setObjectName("infoCard")
    rules_form = QFormLayout()
    for money_spin in (
        window.settings_marketing_leal_spend_spin,
        window.settings_marketing_leal_purchase_sum_spin,
        window.settings_marketing_discount_basico_spin,
        window.settings_marketing_discount_leal_spin,
        window.settings_marketing_discount_profesor_spin,
        window.settings_marketing_discount_mayorista_spin,
    ):
        money_spin.setRange(0.0, 999999.99)
        money_spin.setDecimals(2)
        money_spin.setSingleStep(5.0)
    for percent_spin in (
        window.settings_marketing_discount_basico_spin,
        window.settings_marketing_discount_leal_spin,
        window.settings_marketing_discount_profesor_spin,
        window.settings_marketing_discount_mayorista_spin,
    ):
        percent_spin.setSuffix("%")
        percent_spin.setRange(0.0, 100.0)
    window.settings_marketing_leal_spend_spin.setPrefix("$")
    window.settings_marketing_leal_purchase_sum_spin.setPrefix("$")
    window.settings_marketing_review_days_spin.setRange(30, 1095)
    window.settings_marketing_review_days_spin.setSingleStep(30)
    window.settings_marketing_leal_purchase_count_spin.setRange(1, 50)
    rules_form.addRow("Ventana evaluacion (dias)", window.settings_marketing_review_days_spin)
    rules_form.addRow("Monto para subir a LEAL", window.settings_marketing_leal_spend_spin)
    rules_form.addRow("Compras minimas para LEAL", window.settings_marketing_leal_purchase_count_spin)
    rules_form.addRow("Monto acumulado por frecuencia", window.settings_marketing_leal_purchase_sum_spin)
    rules_box.setLayout(rules_form)

    discounts_box = QGroupBox("Descuentos por nivel")
    discounts_box.setObjectName("infoCard")
    discounts_form = QFormLayout()
    discounts_form.addRow("BASICO", window.settings_marketing_discount_basico_spin)
    discounts_form.addRow("LEAL", window.settings_marketing_discount_leal_spin)
    discounts_form.addRow("PROFESOR", window.settings_marketing_discount_profesor_spin)
    discounts_form.addRow("MAYORISTA", window.settings_marketing_discount_mayorista_spin)
    discounts_box.setLayout(discounts_form)

    note = QLabel(
        "PROFESOR y MAYORISTA siguen siendo niveles asignados manualmente. "
        "Las reglas automaticas solo aplican a la transicion BASICO <-> LEAL."
    )
    note.setWordWrap(True)
    note.setObjectName("subtleLine")
    summary_box = QGroupBox("Resumen actual")
    summary_box.setObjectName("infoCard")
    summary_layout = QVBoxLayout()
    window.settings_marketing_summary_label.setWordWrap(True)
    window.settings_marketing_summary_label.setObjectName("subtleLine")
    summary_layout.addWidget(window.settings_marketing_summary_label)
    summary_box.setLayout(summary_layout)

    window.settings_marketing_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_marketing_recalculate_button.setObjectName("toolbarSecondaryButton")
    window.settings_marketing_history_button.setObjectName("toolbarGhostButton")
    window.settings_marketing_save_button.clicked.connect(window._handle_save_marketing_settings)
    window.settings_marketing_recalculate_button.clicked.connect(window._handle_recalculate_loyalty_levels)
    window.settings_marketing_history_button.clicked.connect(window._handle_open_marketing_history)

    actions = QHBoxLayout()
    actions.addWidget(window.settings_marketing_history_button)
    actions.addWidget(window.settings_marketing_recalculate_button)
    actions.addWidget(window.settings_marketing_save_button)
    actions.addStretch()

    layout.addWidget(window.settings_marketing_status_label)
    layout.addWidget(rules_box)
    layout.addWidget(discounts_box)
    layout.addWidget(summary_box)
    layout.addWidget(note)
    layout.addLayout(actions)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_backup_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Respaldo y restauracion",
        "Gestiona respaldos manuales y restauraciones controladas desde la interfaz.",
        width=980,
    )
    window.settings_backup_status_label.setObjectName("analyticsLine")
    window.settings_backup_automatic_status_label.setObjectName("analyticsLine")
    window.settings_backup_automatic_detail_label.setObjectName("subtleLine")
    window.settings_backup_automatic_detail_label.setWordWrap(True)
    window.settings_backup_location_label.setObjectName("subtleLine")
    window.settings_backup_location_label.setWordWrap(True)
    window.settings_backup_format_combo.clear()
    window.settings_backup_format_combo.addItem("SQL (.sql)", "plain")
    window.settings_backup_format_combo.addItem("Restaurable (.dump)", "custom")
    window.settings_create_backup_button.setObjectName("toolbarPrimaryButton")
    window.settings_refresh_backups_button.setObjectName("toolbarSecondaryButton")
    window.settings_open_backups_button.setObjectName("toolbarGhostButton")
    window.settings_restore_backup_button.setObjectName("cashierDangerButton")
    window.settings_create_backup_button.clicked.connect(window._handle_create_backup)
    window.settings_refresh_backups_button.clicked.connect(window._refresh_settings_backups)
    window.settings_open_backups_button.clicked.connect(window._handle_open_backup_folder)
    window.settings_restore_backup_button.clicked.connect(window._handle_restore_backup)

    backup_hint = QLabel(
        "Los respaldos automaticos deben correr por tarea externa usando scripts/run_scheduled_backup.py. Desde aqui puedes crear uno manual, revisar la carpeta y restaurar respaldos .dump."
    )
    backup_hint.setWordWrap(True)
    automatic_box = QGroupBox("Estado del respaldo automatico")
    automatic_box.setObjectName("infoCard")
    automatic_layout = QVBoxLayout()
    automatic_layout.setSpacing(6)
    automatic_layout.addWidget(window.settings_backup_automatic_status_label)
    automatic_layout.addWidget(window.settings_backup_automatic_detail_label)
    automatic_box.setLayout(automatic_layout)
    backup_actions = QHBoxLayout()
    backup_actions.addWidget(QLabel("Formato"))
    backup_actions.addWidget(window.settings_backup_format_combo)
    backup_actions.addWidget(window.settings_create_backup_button)
    backup_actions.addWidget(window.settings_refresh_backups_button)
    backup_actions.addWidget(window.settings_open_backups_button)
    backup_actions.addWidget(window.settings_restore_backup_button)
    backup_actions.addStretch()

    window.settings_backup_table.setColumnCount(5)
    window.settings_backup_table.setHorizontalHeaderLabels(
        ["Archivo", "Formato", "Fecha", "Tamano", "Restaurable"]
    )
    window.settings_backup_table.setObjectName("dataTable")
    window.settings_backup_table.verticalHeader().setVisible(False)
    window.settings_backup_table.setSelectionBehavior(window.settings_backup_table.SelectionBehavior.SelectRows)
    window.settings_backup_table.setAlternatingRowColors(True)
    window.settings_backup_table.setMinimumHeight(280)
    window.settings_backup_table.horizontalHeader().setStretchLastSection(True)

    layout.addWidget(backup_hint)
    layout.addWidget(automatic_box)
    layout.addWidget(window.settings_backup_status_label)
    layout.addWidget(window.settings_backup_location_label)
    layout.addLayout(backup_actions)
    layout.addWidget(window.settings_backup_table)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_cash_history_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Historial de cortes de caja",
        "Consulta aperturas y cierres de caja, montos esperados, diferencias y responsables.",
        width=1100,
    )
    window.settings_cash_history_status_label.setObjectName("analyticsLine")
    actions = QHBoxLayout()
    window.settings_cash_history_state_combo.clear()
    window.settings_cash_history_state_combo.addItem("Todas", "todas")
    window.settings_cash_history_state_combo.addItem("Abiertas", "abiertas")
    window.settings_cash_history_state_combo.addItem("Cerradas", "cerradas")
    configure_friendly_date_edit(window.settings_cash_history_from_input)
    configure_friendly_date_edit(window.settings_cash_history_to_input)
    window.settings_cash_history_refresh_button.setObjectName("toolbarPrimaryButton")
    window.settings_cash_history_detail_button.setObjectName("toolbarSecondaryButton")
    window.settings_cash_history_state_combo.currentIndexChanged.connect(window._refresh_settings_cash_history)
    window.settings_cash_history_from_input.dateChanged.connect(window._refresh_settings_cash_history)
    window.settings_cash_history_to_input.dateChanged.connect(window._refresh_settings_cash_history)
    window.settings_cash_history_refresh_button.clicked.connect(window._refresh_settings_cash_history)
    window.settings_cash_history_detail_button.clicked.connect(window._handle_view_cash_history_detail)
    actions.addWidget(QLabel("Estado"))
    actions.addWidget(window.settings_cash_history_state_combo)
    actions.addWidget(QLabel("Desde"))
    actions.addWidget(window.settings_cash_history_from_input)
    actions.addWidget(QLabel("Hasta"))
    actions.addWidget(window.settings_cash_history_to_input)
    actions.addWidget(window.settings_cash_history_refresh_button)
    actions.addWidget(window.settings_cash_history_detail_button)
    actions.addStretch()

    window.settings_cash_history_table.setColumnCount(10)
    window.settings_cash_history_table.setHorizontalHeaderLabels(
        [
            "Id",
            "Estado",
            "Apertura",
            "Abierta por",
            "Reactivo inicial",
            "Cierre",
            "Cerrada por",
            "Esperado",
            "Contado",
            "Diferencia",
        ]
    )
    window.settings_cash_history_table.setObjectName("dataTable")
    window.settings_cash_history_table.verticalHeader().setVisible(False)
    window.settings_cash_history_table.setSelectionBehavior(
        window.settings_cash_history_table.SelectionBehavior.SelectRows
    )
    window.settings_cash_history_table.setAlternatingRowColors(True)
    window.settings_cash_history_table.setMinimumHeight(320)
    window.settings_cash_history_table.horizontalHeader().setStretchLastSection(True)
    window.settings_cash_history_table.itemDoubleClicked.connect(window._handle_view_cash_history_detail)
    window.settings_cash_history_table.itemSelectionChanged.connect(window._refresh_permissions)
    window.settings_cash_history_table.itemSelectionChanged.connect(window._refresh_selected_cash_history_movements)

    movements_box = QGroupBox("Movimientos de la sesion seleccionada")
    movements_box.setObjectName("infoCard")
    movements_layout = QVBoxLayout()
    window.settings_cash_history_movements_label.setObjectName("subtleLine")
    window.settings_cash_history_table.setMinimumHeight(240)
    window.settings_cash_history_movements_table.setColumnCount(5)
    window.settings_cash_history_movements_table.setHorizontalHeaderLabels(
        ["Fecha", "Tipo", "Monto", "Usuario", "Concepto"]
    )
    window.settings_cash_history_movements_table.setObjectName("dataTable")
    window.settings_cash_history_movements_table.verticalHeader().setVisible(False)
    window.settings_cash_history_movements_table.setSelectionBehavior(
        window.settings_cash_history_movements_table.SelectionBehavior.SelectRows
    )
    window.settings_cash_history_movements_table.setAlternatingRowColors(True)
    window.settings_cash_history_movements_table.setMinimumHeight(180)
    window.settings_cash_history_movements_table.horizontalHeader().setStretchLastSection(True)
    movements_layout.addWidget(window.settings_cash_history_movements_label)
    movements_layout.addWidget(window.settings_cash_history_movements_table)
    movements_box.setLayout(movements_layout)

    layout.addWidget(window.settings_cash_history_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_cash_history_table)
    layout.addWidget(movements_box)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_catalog_sync_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Consistencia de catálogo",
        "Compara el catálogo SQLite (Windows) contra PostgreSQL y detecta productos nuevos, "
        "exclusivos de Postgres y precios distintos.",
        width=1060,
    )

    window.settings_catalog_sync_status_label.setObjectName("analyticsLine")

    window.settings_catalog_sync_filter_combo.clear()
    window.settings_catalog_sync_filter_combo.addItem("Todos", "todos")
    window.settings_catalog_sync_filter_combo.addItem("Solo en catálogo (SQLite)", "solo_sqlite")
    window.settings_catalog_sync_filter_combo.addItem("Solo en Postgres", "solo_postgres")
    window.settings_catalog_sync_filter_combo.addItem("Precio distinto", "precio_distinto")

    window.settings_catalog_sync_verify_button.setObjectName("toolbarPrimaryButton")
    window.settings_catalog_sync_path_button.setObjectName("toolbarGhostButton")
    window.settings_catalog_sync_verify_button.clicked.connect(window._handle_catalog_sync_verify)
    window.settings_catalog_sync_path_button.clicked.connect(window._handle_catalog_sync_change_path)
    window.settings_catalog_sync_filter_combo.currentIndexChanged.connect(
        window._apply_catalog_sync_filter
    )

    path_row = QHBoxLayout()
    path_row.addWidget(QLabel("Catálogo SQLite:"))
    path_row.addWidget(window.settings_catalog_sync_path_label, stretch=1)
    path_row.addWidget(window.settings_catalog_sync_path_button)

    actions_row = QHBoxLayout()
    actions_row.addWidget(window.settings_catalog_sync_verify_button)
    actions_row.addWidget(QLabel("Filtrar:"))
    actions_row.addWidget(window.settings_catalog_sync_filter_combo)
    actions_row.addStretch()

    window.settings_catalog_sync_table.setColumnCount(5)
    window.settings_catalog_sync_table.setHorizontalHeaderLabels(
        ["Tipo", "SKU", "Nombre", "$ Catálogo", "$ Postgres"]
    )
    window.settings_catalog_sync_table.setObjectName("dataTable")
    window.settings_catalog_sync_table.verticalHeader().setVisible(False)
    window.settings_catalog_sync_table.setSelectionBehavior(
        window.settings_catalog_sync_table.SelectionBehavior.SelectRows
    )
    window.settings_catalog_sync_table.setAlternatingRowColors(True)
    window.settings_catalog_sync_table.setMinimumHeight(340)
    window.settings_catalog_sync_table.horizontalHeader().setStretchLastSection(True)
    window.settings_catalog_sync_table.setEditTriggers(
        window.settings_catalog_sync_table.EditTrigger.NoEditTriggers
    )


    layout.addLayout(path_row)
    layout.addLayout(actions_row)
    layout.addWidget(window.settings_catalog_sync_status_label)
    layout.addWidget(window.settings_catalog_sync_table)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog


def build_employee_ranking_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Ranking de empleadas",
        "Ventas confirmadas acreditadas por escaneo QR de empleada. Solo aparecen quienes tienen ventas en el periodo.",
        width=780,
    )
    toolbar = QHBoxLayout()
    window.settings_employee_ranking_period_combo.clear()
    window.settings_employee_ranking_period_combo.addItems(["Hoy", "7 dias", "Este mes"])
    window.settings_employee_ranking_period_combo.setObjectName("toolbarSecondaryButton")
    window.settings_employee_ranking_period_combo.currentTextChanged.connect(window._refresh_employee_ranking)
    window.settings_employee_ranking_toggle_amounts_button.setObjectName("toolbarGhostButton")
    window.settings_employee_ranking_toggle_amounts_button.clicked.connect(
        window._handle_toggle_employee_ranking_amounts
    )
    toolbar.addWidget(QLabel("Periodo"))
    toolbar.addWidget(window.settings_employee_ranking_period_combo)
    toolbar.addStretch()
    toolbar.addWidget(window.settings_employee_ranking_toggle_amounts_button)

    window.settings_employee_ranking_status_label.setObjectName("analyticsLine")

    window.settings_employee_ranking_table.setColumnCount(6)
    window.settings_employee_ranking_table.setHorizontalHeaderLabels(
        ["#", "Empleada", "Tickets", "Piezas", "Monto", "Ultima venta"]
    )
    window.settings_employee_ranking_table.setObjectName("dataTable")
    window.settings_employee_ranking_table.verticalHeader().setVisible(False)
    window.settings_employee_ranking_table.setSelectionBehavior(
        window.settings_employee_ranking_table.SelectionBehavior.SelectRows
    )
    window.settings_employee_ranking_table.setEditTriggers(
        window.settings_employee_ranking_table.EditTrigger.NoEditTriggers
    )
    window.settings_employee_ranking_table.setAlternatingRowColors(True)
    window.settings_employee_ranking_table.setMinimumHeight(280)
    header = window.settings_employee_ranking_table.horizontalHeader()
    from PyQt6.QtWidgets import QHeaderView
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    layout.addLayout(toolbar)
    layout.addWidget(window.settings_employee_ranking_status_label)
    layout.addWidget(window.settings_employee_ranking_table, 1)
    footer = QHBoxLayout()
    footer.addStretch()
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("toolbarGhostButton")
    close_btn.clicked.connect(dialog.reject)
    footer.addWidget(close_btn)
    layout.addLayout(footer)
    return dialog
