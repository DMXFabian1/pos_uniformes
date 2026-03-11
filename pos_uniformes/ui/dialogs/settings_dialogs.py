"""Builders de dialogs para el modulo Configuracion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_users_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_users_table)
    layout.addWidget(close_buttons)
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_suppliers_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_suppliers_table)
    layout.addWidget(close_buttons)
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
    window.settings_clients_search_input.setPlaceholderText("Buscar por codigo, nombre, telefono, correo, direccion o notas")
    window.settings_create_client_button.setObjectName("toolbarPrimaryButton")
    window.settings_update_client_button.setObjectName("toolbarSecondaryButton")
    window.settings_toggle_client_button.setObjectName("toolbarGhostButton")
    window.settings_generate_client_qr_button.setObjectName("toolbarSecondaryButton")
    window.settings_client_whatsapp_button.setObjectName("toolbarGhostButton")
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

    window.settings_clients_table.setColumnCount(9)
    window.settings_clients_table.setHorizontalHeaderLabels(
        ["Codigo", "Cliente", "Telefono", "Correo", "Direccion", "Notas", "QR", "Estado", "Actualizado"]
    )
    window.settings_clients_table.setObjectName("dataTable")
    window.settings_clients_table.verticalHeader().setVisible(False)
    window.settings_clients_table.setSelectionBehavior(window.settings_clients_table.SelectionBehavior.SelectRows)
    window.settings_clients_table.setAlternatingRowColors(True)
    window.settings_clients_table.setMinimumHeight(340)
    window.settings_clients_table.horizontalHeader().setStretchLastSection(True)

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_clients_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_clients_table)
    layout.addWidget(close_buttons)
    return dialog


def build_whatsapp_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "WhatsApp y mensajes",
        "Administra plantillas para recordatorios de apartados y mensajes a clientes. Usa placeholders como {cliente}, {folio}, {saldo}, {vencimiento}, {fecha_compromiso} y {codigo_cliente}.",
        width=820,
    )
    window.settings_whatsapp_status_label.setObjectName("analyticsLine")
    whatsapp_box = QGroupBox("Plantillas WhatsApp")
    whatsapp_box.setObjectName("infoCard")
    whatsapp_form = QFormLayout()
    window.settings_whatsapp_layaway_reminder_input.setPlaceholderText(
        "Usa {cliente}, {folio}, {saldo}, {vencimiento}, {fecha_compromiso}"
    )
    window.settings_whatsapp_layaway_reminder_input.setMinimumHeight(70)
    window.settings_whatsapp_layaway_liquidated_input.setPlaceholderText(
        "Usa {cliente}, {folio}, {fecha_compromiso}"
    )
    window.settings_whatsapp_layaway_liquidated_input.setMinimumHeight(70)
    window.settings_whatsapp_client_promotion_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    window.settings_whatsapp_client_promotion_input.setMinimumHeight(70)
    window.settings_whatsapp_client_followup_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    window.settings_whatsapp_client_followup_input.setMinimumHeight(70)
    window.settings_whatsapp_client_greeting_input.setPlaceholderText("Usa {cliente}, {codigo_cliente}")
    window.settings_whatsapp_client_greeting_input.setMinimumHeight(70)
    whatsapp_form.addRow("Apartado recordatorio", window.settings_whatsapp_layaway_reminder_input)
    whatsapp_form.addRow("Apartado liquidado", window.settings_whatsapp_layaway_liquidated_input)
    whatsapp_form.addRow("Cliente promocion", window.settings_whatsapp_client_promotion_input)
    whatsapp_form.addRow("Cliente seguimiento", window.settings_whatsapp_client_followup_input)
    whatsapp_form.addRow("Cliente saludo", window.settings_whatsapp_client_greeting_input)
    whatsapp_box.setLayout(whatsapp_form)
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
    preview_actions.addWidget(QLabel("Mensaje"))
    preview_actions.addWidget(window.settings_whatsapp_preview_combo, 1)
    preview_actions.addWidget(window.settings_whatsapp_preview_button)
    preview_actions.addWidget(window.settings_whatsapp_reset_button)
    preview_layout.addLayout(preview_actions)
    preview_layout.addWidget(window.settings_whatsapp_preview_output)
    preview_box.setLayout(preview_layout)
    window.settings_whatsapp_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_whatsapp_save_button.clicked.connect(window._handle_save_whatsapp_settings)
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_whatsapp_status_label)
    layout.addWidget(whatsapp_box)
    layout.addWidget(preview_box)
    layout.addWidget(window.settings_whatsapp_save_button, 0, Qt.AlignmentFlag.AlignRight)
    layout.addWidget(close_buttons)
    return dialog


def build_business_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Negocio e impresion",
        "Actualiza los datos visibles del negocio, la informacion de transferencia y la impresion preferida del ticket.",
        width=760,
    )
    window.settings_business_status_label.setObjectName("analyticsLine")
    form_box = QGroupBox("Datos del negocio")
    form_box.setObjectName("infoCard")
    form = QFormLayout()
    window.settings_business_name_input.setPlaceholderText("Nombre comercial")
    window.settings_business_phone_input.setPlaceholderText("Telefono")
    window.settings_business_address_input.setPlaceholderText("Direccion visible en ticket")
    window.settings_business_address_input.setMinimumHeight(80)
    window.settings_business_footer_input.setPlaceholderText("Mensaje al pie del ticket")
    window.settings_business_footer_input.setMinimumHeight(80)
    window.settings_business_transfer_bank_input.setPlaceholderText("Banco destino")
    window.settings_business_transfer_beneficiary_input.setPlaceholderText("Nombre del beneficiario")
    window.settings_business_transfer_clabe_input.setPlaceholderText("CLABE o numero de cuenta")
    window.settings_business_transfer_instructions_input.setPlaceholderText("Indicaciones de pago por transferencia")
    window.settings_business_transfer_instructions_input.setMinimumHeight(80)
    window.settings_business_copies_spin.setRange(1, 5)
    window.settings_business_printer_combo.clear()
    window.settings_business_printer_combo.addItem("Preguntar siempre", "")
    for printer in QPrinterInfo.availablePrinters():
        window.settings_business_printer_combo.addItem(printer.printerName(), printer.printerName())
    form.addRow("Negocio", window.settings_business_name_input)
    form.addRow("Telefono", window.settings_business_phone_input)
    form.addRow("Direccion", window.settings_business_address_input)
    form.addRow("Pie ticket", window.settings_business_footer_input)
    form.addRow("Banco", window.settings_business_transfer_bank_input)
    form.addRow("Beneficiario", window.settings_business_transfer_beneficiary_input)
    form.addRow("CLABE", window.settings_business_transfer_clabe_input)
    form.addRow("Instrucciones pago", window.settings_business_transfer_instructions_input)
    form.addRow("Impresora", window.settings_business_printer_combo)
    form.addRow("Copias", window.settings_business_copies_spin)
    form_box.setLayout(form)
    window.settings_business_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_business_save_button.clicked.connect(window._handle_save_business_settings)
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_business_status_label)
    layout.addWidget(form_box)
    layout.addWidget(window.settings_business_save_button, 0, Qt.AlignmentFlag.AlignRight)
    layout.addWidget(close_buttons)
    return dialog


def build_backup_settings_dialog(window: "MainWindow") -> QDialog:
    dialog, layout = _create_settings_dialog(
        window,
        "Respaldo y restauracion",
        "Gestiona respaldos manuales y restauraciones controladas desde la interfaz.",
        width=980,
    )
    window.settings_backup_status_label.setObjectName("analyticsLine")
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
        "Los respaldos diarios siguen corriendo por script. Desde aqui puedes crear uno manual, revisar la carpeta y restaurar respaldos .dump."
    )
    backup_hint.setWordWrap(True)
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(backup_hint)
    layout.addWidget(window.settings_backup_status_label)
    layout.addWidget(window.settings_backup_location_label)
    layout.addLayout(backup_actions)
    layout.addWidget(window.settings_backup_table)
    layout.addWidget(close_buttons)
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
    window.settings_cash_history_from_input.setCalendarPopup(True)
    window.settings_cash_history_to_input.setCalendarPopup(True)
    window.settings_cash_history_from_input.setDisplayFormat("yyyy-MM-dd")
    window.settings_cash_history_to_input.setDisplayFormat("yyyy-MM-dd")
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_cash_history_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_cash_history_table)
    layout.addWidget(movements_box)
    layout.addWidget(close_buttons)
    return dialog
