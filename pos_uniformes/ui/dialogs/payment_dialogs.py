"""Dialogs de cobro para caja."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import QRegularExpression, Qt
from PyQt6.QtGui import QKeySequence, QRegularExpressionValidator, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from pos_uniformes.ui.keypad_input_helper import (
    append_keypad_text,
    backspace_keypad_text,
    clear_keypad_text,
    install_keypad_shortcuts,
    parse_keypad_amount_text,
)
from pos_uniformes.services.sale_payment_note_service import (
    build_cash_payment_details,
    build_mixed_payment_details,
    build_transfer_payment_details,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_cash_payment_dialog(window: "MainWindow", total: Decimal):
    dialog, layout = window._create_modal_dialog(
        "Cobro en efectivo",
        "Captura el efectivo recibido. Puedes usar el teclado numerico o los montos rapidos.",
        width=420,
    )
    total_label = QLabel(f"Total a cobrar: ${total}")
    total_label.setObjectName("inventoryTitle")
    received_label = QLabel("$0.00")
    received_label.setObjectName("cashierTotalValue")
    change_label = QLabel("$0.00")
    change_label.setObjectName("cashierChangeValue")
    status_label = QLabel("Captura el monto recibido.")
    status_label.setObjectName("analyticsLine")
    keypad_display = QLineEdit("0.00")
    keypad_display.setReadOnly(True)
    keypad_display.setObjectName("readOnlyField")
    reference_input = QLineEdit()
    reference_input.setPlaceholderText("Referencia opcional")

    def parse_received() -> Decimal:
        return parse_keypad_amount_text(keypad_display.text())

    def update_cash_labels() -> None:
        received = parse_received()
        change = received - total
        if change < Decimal("0.00"):
            change = Decimal("0.00")
            status_label.setText("Falta efectivo para cubrir el total.")
            status_label.setProperty("tone", "warning")
        else:
            status_label.setText("Monto suficiente para cobrar.")
            status_label.setProperty("tone", "positive")
        status_label.style().unpolish(status_label)
        status_label.style().polish(status_label)
        received_label.setText(f"${received}")
        change_label.setText(f"${change}")

    def append_keypad(value: str) -> None:
        keypad_display.setText(append_keypad_text(keypad_display.text(), value))
        update_cash_labels()

    def clear_keypad() -> None:
        keypad_display.setText(clear_keypad_text())
        update_cash_labels()

    def backspace_keypad() -> None:
        keypad_display.setText(backspace_keypad_text(keypad_display.text()))
        update_cash_labels()

    summary_grid = QGridLayout()
    summary_grid.addWidget(QLabel("Recibido"), 0, 0)
    summary_grid.addWidget(received_label, 0, 1)
    summary_grid.addWidget(QLabel("Cambio"), 1, 0)
    summary_grid.addWidget(change_label, 1, 1)

    quick_row = QHBoxLayout()
    for amount in (100, 200, 500, 1000):
        button = QPushButton(f"${amount}")
        button.setObjectName("toolbarSecondaryButton")
        button.clicked.connect(
            lambda _checked=False, amt=amount: (
                keypad_display.setText(f"{amt:.2f}"),
                update_cash_labels(),
            )
        )
        quick_row.addWidget(button)
    quick_row.addStretch()

    keypad = QGridLayout()
    keys = [
        ("7", 0, 0),
        ("8", 0, 1),
        ("9", 0, 2),
        ("4", 1, 0),
        ("5", 1, 1),
        ("6", 1, 2),
        ("1", 2, 0),
        ("2", 2, 1),
        ("3", 2, 2),
        ("0", 3, 0),
        ("00", 3, 1),
        (".", 3, 2),
    ]
    for key, row, column in keys:
        button = QPushButton(key)
        button.setMinimumHeight(42)
        button.clicked.connect(lambda _checked=False, value=key: append_keypad(value))
        keypad.addWidget(button, row, column)
    clear_button = QPushButton("Limpiar")
    clear_button.clicked.connect(clear_keypad)
    keypad.addWidget(clear_button, 4, 0, 1, 2)
    backspace_button = QPushButton("Borrar")
    backspace_button.clicked.connect(backspace_keypad)
    keypad.addWidget(backspace_button, 4, 2)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    install_keypad_shortcuts(
        dialog=dialog,
        accept_button=buttons.button(QDialogButtonBox.StandardButton.Ok),
        reject_button=buttons.button(QDialogButtonBox.StandardButton.Cancel),
        append_value=append_keypad,
        clear_value=clear_keypad,
        backspace_value=backspace_keypad,
    )

    layout.addWidget(total_label)
    layout.addWidget(keypad_display)
    layout.addLayout(summary_grid)
    layout.addWidget(status_label)
    layout.addLayout(quick_row)
    layout.addLayout(keypad)
    layout.addWidget(QLabel("Referencia"))
    layout.addWidget(reference_input)
    layout.addWidget(buttons)
    update_cash_labels()

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    received = parse_received()
    if received < total:
        QMessageBox.warning(window, "Pago insuficiente", "El monto recibido debe cubrir el total de la venta.")
        return None
    change = (received - total).quantize(Decimal("0.01"))
    return build_cash_payment_details(
        received=received,
        change=change,
        reference=reference_input.text(),
    )


def build_transfer_payment_dialog(window: "MainWindow", total: Decimal, business):
    if not business.transfer_clabe and not business.transfer_instructions:
        QMessageBox.warning(
            window,
            "Transferencia no configurada",
            "Configura CLABE o instrucciones de transferencia en Configuracion > Negocio e impresion.",
        )
        return None

    dialog, layout = window._create_modal_dialog(
        "Cobro por transferencia",
        "Muestra los datos de pago al cliente y confirma cuando la transferencia este registrada.",
        width=520,
    )
    info_lines = [
        f"Negocio: {business.business_name}",
        f"Banco: {business.transfer_bank or 'No configurado'}",
        f"Beneficiario: {business.transfer_beneficiary or 'No configurado'}",
        f"CLABE: {business.transfer_clabe or 'No configurada'}",
        f"Total a transferir: ${total}",
    ]
    info_label = QLabel("\n".join(info_lines))
    info_label.setWordWrap(True)
    info_label.setObjectName("inventoryMetaCard")
    instructions_label = QLabel(str(business.transfer_instructions or "Sin instrucciones adicionales."))
    instructions_label.setWordWrap(True)
    instructions_label.setObjectName("inventoryMetaCardAlt")
    reference_input = QLineEdit()
    reference_input.setPlaceholderText("Folio o referencia de transferencia")
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar pago")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout.addWidget(info_label)
    layout.addWidget(QLabel("Indicaciones"))
    layout.addWidget(instructions_label)
    layout.addWidget(QLabel("Referencia"))
    layout.addWidget(reference_input)
    layout.addWidget(buttons)

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    return build_transfer_payment_details(reference_input.text())


def build_mixed_payment_dialog(window: "MainWindow", total: Decimal, business):
    dialog, layout = window._create_modal_dialog(
        "Cobro mixto",
        "Registra cuanto entra por transferencia y cuanto efectivo recibes. El sistema calcula el cambio.",
        width=520,
    )
    total_label = QLabel(f"Total a cobrar: ${total}")
    total_label.setObjectName("inventoryTitle")
    transfer_info = QLabel(
        "\n".join(
            [
                f"Banco: {business.transfer_bank or 'No configurado'}",
                f"Beneficiario: {business.transfer_beneficiary or 'No configurado'}",
                f"CLABE: {business.transfer_clabe or 'No configurada'}",
            ]
        )
    )
    transfer_info.setWordWrap(True)
    transfer_info.setObjectName("inventoryMetaCard")
    amount_validator = QRegularExpressionValidator(QRegularExpression(r"^\d{0,6}([.,]\d{0,2})?$"))
    transfer_input = QLineEdit("0.00")
    transfer_input.setValidator(amount_validator)
    transfer_input.setPlaceholderText("0.00")
    transfer_input.setAlignment(Qt.AlignmentFlag.AlignRight)
    transfer_input.setClearButtonEnabled(True)
    cash_received_input = QLineEdit("0.00")
    cash_received_input.setValidator(amount_validator)
    cash_received_input.setPlaceholderText("0.00")
    cash_received_input.setAlignment(Qt.AlignmentFlag.AlignRight)
    cash_received_input.setClearButtonEnabled(True)
    remaining_label = QLabel("$0.00")
    remaining_label.setObjectName("cashierMetaLabel")
    change_label = QLabel("$0.00")
    change_label.setObjectName("cashierChangeValue")
    keyboard_hint = QLabel("Usa Tab para cambiar de campo. Enter confirma y Esc cancela.")
    keyboard_hint.setObjectName("analyticsLine")
    reference_input = QLineEdit()
    reference_input.setPlaceholderText("Referencia transferencia opcional")

    def parse_transfer_amount() -> Decimal:
        return parse_keypad_amount_text(transfer_input.text())

    def parse_cash_received() -> Decimal:
        return parse_keypad_amount_text(cash_received_input.text())

    def normalize_amount_input(input_field: QLineEdit) -> None:
        input_field.setText(f"{parse_keypad_amount_text(input_field.text()):.2f}")

    def update_mixed_labels() -> None:
        transfer_amount = parse_transfer_amount()
        cash_received = parse_cash_received()
        remaining_cash = total - transfer_amount
        if remaining_cash < Decimal("0.00"):
            remaining_cash = Decimal("0.00")
        change = cash_received - remaining_cash
        if change < Decimal("0.00"):
            change = Decimal("0.00")
        remaining_label.setText(f"${remaining_cash}")
        change_label.setText(f"${change}")

    transfer_input.textChanged.connect(update_mixed_labels)
    transfer_input.editingFinished.connect(lambda: normalize_amount_input(transfer_input))
    cash_received_input.textChanged.connect(update_mixed_labels)
    cash_received_input.editingFinished.connect(lambda: normalize_amount_input(cash_received_input))

    form = QFormLayout()
    form.addRow("Transferencia", transfer_input)
    form.addRow("Efectivo recibido", cash_received_input)
    form.addRow("Efectivo a cubrir", remaining_label)
    form.addRow("Cambio", change_label)
    form.addRow("Referencia", reference_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar pago")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    submit_shortcuts: list[QShortcut] = []

    def register_submit_shortcut(sequence: QKeySequence | str, callback) -> None:
        shortcut = QShortcut(QKeySequence(sequence), dialog)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        submit_shortcuts.append(shortcut)

    register_submit_shortcut(QKeySequence(Qt.Key.Key_Return), buttons.button(QDialogButtonBox.StandardButton.Ok).click)
    register_submit_shortcut(QKeySequence(Qt.Key.Key_Enter), buttons.button(QDialogButtonBox.StandardButton.Ok).click)
    register_submit_shortcut("Escape", buttons.button(QDialogButtonBox.StandardButton.Cancel).click)
    dialog._mixed_payment_shortcuts = submit_shortcuts  # type: ignore[attr-defined]

    layout.addWidget(total_label)
    layout.addWidget(transfer_info)
    layout.addWidget(keyboard_hint)
    layout.addLayout(form)
    layout.addWidget(buttons)
    update_mixed_labels()
    cash_received_input.setFocus()
    cash_received_input.selectAll()

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    transfer_amount = parse_transfer_amount()
    cash_received = parse_cash_received()
    cash_due = total - transfer_amount
    if cash_due < Decimal("0.00"):
        cash_due = Decimal("0.00")
    if transfer_amount + cash_received < total:
        QMessageBox.warning(window, "Pago insuficiente", "La suma de transferencia y efectivo debe cubrir el total.")
        return None
    change = (cash_received - cash_due).quantize(Decimal("0.01"))
    if change < Decimal("0.00"):
        change = Decimal("0.00")
    return build_mixed_payment_details(
        transfer_amount=transfer_amount,
        cash_received=cash_received,
        change=change,
        reference=reference_input.text(),
    )
