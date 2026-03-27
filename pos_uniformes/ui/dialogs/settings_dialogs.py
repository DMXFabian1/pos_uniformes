"""Builders de dialogs para el modulo Configuracion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(quick_reference)
    layout.addWidget(placeholder_hint)
    layout.addLayout(placeholder_actions)
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
        width=920,
    )
    window.settings_business_status_label.setObjectName("analyticsLine")
    form_box = QGroupBox("Datos del negocio")
    form_box.setObjectName("infoCard")
    form_layout = QVBoxLayout()
    form_layout.setSpacing(12)
    window.settings_business_name_input.setPlaceholderText("Nombre comercial")
    window.settings_business_logo_input.setPlaceholderText("Ruta del logo para credenciales")
    window.settings_business_logo_input.setReadOnly(True)
    window.settings_business_logo_preview_label.setFixedSize(220, 120)
    window.settings_business_logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.settings_business_logo_preview_label.setObjectName("infoCard")
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
    window.settings_business_promo_code_input.setPlaceholderText("Deja vacio para conservar el codigo actual")
    window.settings_business_promo_code_input.setEchoMode(QLineEdit.EchoMode.Password)
    window.settings_business_copies_spin.setRange(1, 5)
    window.settings_business_printer_combo.clear()
    window.settings_business_printer_combo.addItem("Preguntar siempre", "")
    for printer in QPrinterInfo.availablePrinters():
        window.settings_business_printer_combo.addItem(printer.printerName(), printer.printerName())
    logo_row = QHBoxLayout()
    logo_row.addWidget(window.settings_business_logo_input)
    logo_row.addWidget(window.settings_business_logo_pick_button)
    logo_row.addWidget(window.settings_business_logo_clear_button)
    logo_widget = QWidget()
    logo_widget.setLayout(logo_row)
    logo_preview_box = QVBoxLayout()
    logo_preview_box.setSpacing(8)
    logo_preview_box.addWidget(logo_widget)
    logo_preview_box.addWidget(window.settings_business_logo_preview_label, 0, Qt.AlignmentFlag.AlignLeft)
    logo_preview_widget = QWidget()
    logo_preview_widget.setLayout(logo_preview_box)
    window.settings_business_logo_pick_button.clicked.connect(window._handle_select_business_logo)
    window.settings_business_logo_clear_button.clicked.connect(window._handle_clear_business_logo)

    identity_box = QGroupBox("Identidad visible")
    identity_box.setObjectName("infoCard")
    identity_form = QFormLayout()
    identity_form.setSpacing(10)
    identity_form.addRow("Negocio", window.settings_business_name_input)
    identity_form.addRow("Telefono", window.settings_business_phone_input)
    identity_form.addRow("Direccion", window.settings_business_address_input)
    identity_form.addRow("Pie ticket", window.settings_business_footer_input)
    identity_box.setLayout(identity_form)

    logo_box = QGroupBox("Logo credencial")
    logo_box.setObjectName("infoCard")
    logo_box_layout = QVBoxLayout()
    logo_box_layout.setSpacing(10)
    logo_hint = QLabel("Este logo se usa para credenciales y vistas relacionadas. Si no hay logo, el sistema seguira funcionando.")
    logo_hint.setWordWrap(True)
    logo_hint.setObjectName("subtleLine")
    logo_box_layout.addWidget(logo_hint)
    logo_box_layout.addWidget(logo_preview_widget)
    logo_box_layout.addStretch(1)
    logo_box.setLayout(logo_box_layout)

    transfer_box = QGroupBox("Transferencia")
    transfer_box.setObjectName("infoCard")
    transfer_form = QFormLayout()
    transfer_form.setSpacing(10)
    transfer_form.addRow("Banco", window.settings_business_transfer_bank_input)
    transfer_form.addRow("Beneficiario", window.settings_business_transfer_beneficiary_input)
    transfer_form.addRow("CLABE", window.settings_business_transfer_clabe_input)
    transfer_form.addRow("Instrucciones pago", window.settings_business_transfer_instructions_input)
    transfer_box.setLayout(transfer_form)

    print_box = QGroupBox("Ticket e impresion")
    print_box.setObjectName("infoCard")
    print_form = QFormLayout()
    print_form.setSpacing(10)
    print_form.addRow("Codigo promo manual", window.settings_business_promo_code_input)
    print_form.addRow("Impresora", window.settings_business_printer_combo)
    print_form.addRow("Copias", window.settings_business_copies_spin)
    print_box.setLayout(print_form)

    top_row = QHBoxLayout()
    top_row.setSpacing(12)
    top_row.addWidget(identity_box, 3)
    top_row.addWidget(logo_box, 2)

    bottom_row = QHBoxLayout()
    bottom_row.setSpacing(12)
    bottom_row.addWidget(transfer_box, 3)
    bottom_row.addWidget(print_box, 2)

    form_layout.addLayout(top_row)
    form_layout.addLayout(bottom_row)
    form_box.setLayout(form_layout)

    window.settings_business_save_button.setObjectName("toolbarPrimaryButton")
    window.settings_business_demo_button.setObjectName("toolbarSecondaryButton")
    window.settings_business_save_button.clicked.connect(window._handle_save_business_settings)
    window.settings_business_demo_button.clicked.connect(window._handle_preview_business_card)
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_business_status_label)
    layout.addWidget(form_box)
    actions = QHBoxLayout()
    actions.addWidget(window.settings_business_demo_button)
    actions.addWidget(window.settings_business_save_button)
    actions.addStretch()
    layout.addLayout(actions)
    layout.addWidget(close_buttons)
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_marketing_status_label)
    layout.addWidget(rules_box)
    layout.addWidget(discounts_box)
    layout.addWidget(summary_box)
    layout.addWidget(note)
    layout.addLayout(actions)
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(backup_hint)
    layout.addWidget(automatic_box)
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

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)
    close_buttons.accepted.connect(dialog.accept)
    layout.addWidget(window.settings_cash_history_status_label)
    layout.addLayout(actions)
    layout.addWidget(window.settings_cash_history_table)
    layout.addWidget(movements_box)
    layout.addWidget(close_buttons)
    return dialog
