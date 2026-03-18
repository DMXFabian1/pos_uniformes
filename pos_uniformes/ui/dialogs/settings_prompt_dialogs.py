"""Prompts reutilizables para acciones de Configuracion."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.models import RolUsuario, TipoCliente
from pos_uniformes.services.client_service import ClientService


def _create_settings_prompt_dialog(
    parent: QWidget,
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


def _build_prompt_buttons(dialog: QDialog) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


def prompt_create_user_data(parent: QWidget) -> dict[str, object] | None:
    dialog, layout = _create_settings_prompt_dialog(
        parent,
        "Crear usuario",
        "Define username, nombre, rol y contrasena inicial.",
        width=480,
    )
    form = QFormLayout()
    username_input = QLineEdit()
    username_input.setPlaceholderText("ejemplo: cajero2")
    full_name_input = QLineEdit()
    full_name_input.setPlaceholderText("Nombre completo")
    role_combo = QComboBox()
    role_combo.addItem("ADMIN", RolUsuario.ADMIN)
    role_combo.addItem("CAJERO", RolUsuario.CAJERO)
    password_input = QLineEdit()
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setPlaceholderText("Contrasena inicial")
    form.addRow("Username", username_input)
    form.addRow("Nombre", full_name_input)
    form.addRow("Rol", role_combo)
    form.addRow("Contrasena", password_input)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "username": username_input.text().strip(),
        "nombre_completo": full_name_input.text().strip(),
        "rol": role_combo.currentData(),
        "password": password_input.text(),
    }


def prompt_edit_user_data(
    parent: QWidget,
    *,
    username: str,
    nombre_completo: str,
    current_role: RolUsuario,
) -> dict[str, object] | None:
    dialog, layout = _create_settings_prompt_dialog(
        parent,
        "Editar usuario",
        "Actualiza username, nombre y rol del usuario seleccionado.",
        width=480,
    )
    form = QFormLayout()
    username_input = QLineEdit()
    username_input.setText(username)
    full_name_input = QLineEdit()
    full_name_input.setText(nombre_completo)
    role_combo = QComboBox()
    role_combo.addItem("ADMIN", RolUsuario.ADMIN)
    role_combo.addItem("CAJERO", RolUsuario.CAJERO)
    role_combo.setCurrentIndex(0 if current_role == RolUsuario.ADMIN else 1)
    form.addRow("Username", username_input)
    form.addRow("Nombre", full_name_input)
    form.addRow("Rol", role_combo)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "username": username_input.text().strip(),
        "nombre_completo": full_name_input.text().strip(),
        "rol": role_combo.currentData(),
    }


def prompt_role_change(parent: QWidget, current_role: RolUsuario) -> RolUsuario | None:
    dialog, layout = _create_settings_prompt_dialog(parent, "Cambiar rol", width=360)
    form = QFormLayout()
    role_combo = QComboBox()
    role_combo.addItem("ADMIN", RolUsuario.ADMIN)
    role_combo.addItem("CAJERO", RolUsuario.CAJERO)
    role_combo.setCurrentIndex(0 if current_role == RolUsuario.ADMIN else 1)
    form.addRow("Nuevo rol", role_combo)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return role_combo.currentData()


def prompt_password_change(parent: QWidget) -> str | None:
    dialog, layout = _create_settings_prompt_dialog(parent, "Cambiar contrasena", width=420)
    form = QFormLayout()
    password_input = QLineEdit()
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setPlaceholderText("Nueva contrasena")
    confirm_input = QLineEdit()
    confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
    confirm_input.setPlaceholderText("Confirmar contrasena")
    form.addRow("Nueva", password_input)
    form.addRow("Confirmar", confirm_input)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    if password_input.text() != confirm_input.text():
        raise ValueError("La confirmacion de contrasena no coincide.")
    return password_input.text()


def prompt_supplier_data(
    parent: QWidget,
    *,
    title: str,
    helper_text: str,
    current_values: dict[str, str] | None = None,
) -> dict[str, str] | None:
    dialog, layout = _create_settings_prompt_dialog(parent, title, helper_text, width=520)
    form = QFormLayout()
    name_input = QLineEdit()
    phone_input = QLineEdit()
    email_input = QLineEdit()
    address_input = QTextEdit()
    address_input.setMinimumHeight(90)
    name_input.setPlaceholderText("Nombre comercial o razon social")
    phone_input.setPlaceholderText("Telefono")
    email_input.setPlaceholderText("correo@proveedor.com")
    address_input.setPlaceholderText("Direccion o notas de ubicacion")
    if current_values:
        name_input.setText(current_values.get("nombre", ""))
        phone_input.setText(current_values.get("telefono", ""))
        email_input.setText(current_values.get("email", ""))
        address_input.setPlainText(current_values.get("direccion", ""))
    form.addRow("Nombre", name_input)
    form.addRow("Telefono", phone_input)
    form.addRow("Correo", email_input)
    form.addRow("Direccion", address_input)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "nombre": name_input.text().strip(),
        "telefono": phone_input.text().strip(),
        "email": email_input.text().strip(),
        "direccion": address_input.toPlainText().strip(),
    }


def prompt_client_data(
    parent: QWidget,
    *,
    title: str,
    helper_text: str,
    current_values: dict[str, str] | None = None,
) -> dict[str, str] | None:
    dialog, layout = _create_settings_prompt_dialog(parent, title, helper_text, width=560)
    form = QFormLayout()
    name_input = QLineEdit()
    client_type_combo = QComboBox()
    client_type_combo.addItem("GENERAL", TipoCliente.GENERAL)
    client_type_combo.addItem("PROFESOR", TipoCliente.PROFESOR)
    client_type_combo.addItem("MAYORISTA", TipoCliente.MAYORISTA)
    discount_spin = QDoubleSpinBox()
    discount_spin.setRange(0.0, 100.0)
    discount_spin.setDecimals(2)
    discount_spin.setSuffix("%")
    discount_spin.setSingleStep(5.0)
    phone_input = QLineEdit()
    notes_input = QTextEdit()
    notes_input.setMinimumHeight(90)
    name_input.setPlaceholderText("Nombre completo o identificacion del cliente")
    phone_input.setPlaceholderText("Telefono")
    notes_input.setPlaceholderText("Notas internas o referencias")
    if current_values:
        name_input.setText(current_values.get("nombre", ""))
        initial_type = current_values.get("tipo_cliente", TipoCliente.GENERAL.value)
        type_index = client_type_combo.findData(TipoCliente(initial_type))
        client_type_combo.setCurrentIndex(type_index if type_index >= 0 else 0)
        discount_spin.setValue(float(current_values.get("descuento_preferente", "0") or 0))
        phone_input.setText(current_values.get("telefono", ""))
        notes_input.setPlainText(current_values.get("notas", ""))
    else:
        discount_spin.setValue(float(ClientService.default_discount_for_type(TipoCliente.GENERAL)))

    def _sync_discount_with_type() -> None:
        client_type = client_type_combo.currentData()
        if not isinstance(client_type, TipoCliente):
            return
        suggested = ClientService.default_discount_for_type(client_type)
        if client_type != TipoCliente.GENERAL:
            discount_spin.setValue(float(suggested))

    client_type_combo.currentIndexChanged.connect(_sync_discount_with_type)
    form.addRow("Nombre", name_input)
    form.addRow("Tipo cliente", client_type_combo)
    form.addRow("Desc. preferente", discount_spin)
    form.addRow("Telefono", phone_input)
    form.addRow("Notas", notes_input)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "nombre": name_input.text().strip(),
        "tipo_cliente": str((client_type_combo.currentData() or TipoCliente.GENERAL).value),
        "descuento_preferente": str(Decimal(str(discount_spin.value())).quantize(Decimal("0.01"))),
        "telefono": phone_input.text().strip(),
        "notas": notes_input.toPlainText().strip(),
    }


def prompt_client_whatsapp_data(parent: QWidget, client_name: str) -> tuple[str, str] | None:
    dialog, layout = _create_settings_prompt_dialog(
        parent,
        "Mensaje de WhatsApp",
        f"Prepara un mensaje para {client_name}. Se generara o reutilizara su credencial para que puedas adjuntarla por WhatsApp.",
        width=520,
    )
    form = QFormLayout()
    message_type_combo = QComboBox()
    message_type_combo.addItem("Promocion / descuento", "promotion")
    message_type_combo.addItem("Seguimiento general", "followup")
    message_type_combo.addItem("Saludo", "greeting")
    extra_message_input = QTextEdit()
    extra_message_input.setMinimumHeight(110)
    extra_message_input.setPlaceholderText("Texto extra opcional")
    form.addRow("Tipo", message_type_combo)
    form.addRow("Extra", extra_message_input)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return str(message_type_combo.currentData() or "followup"), extra_message_input.toPlainText().strip()
