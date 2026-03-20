"""Dialogo reutilizable para registrar abonos de apartado."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QPushButton,
)

from pos_uniformes.ui.keypad_input_helper import (
    append_keypad_text,
    backspace_keypad_text,
    clear_keypad_text,
    install_keypad_shortcuts,
    parse_keypad_amount_text,
)
from pos_uniformes.services.sale_payment_validation_service import validate_cash_payment
from pos_uniformes.services.layaway_payment_service import (
    LayawayPaymentInput,
    build_layaway_payment_input,
    resolve_layaway_payment_state,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_layaway_payment_dialog(
    window: "MainWindow",
    *,
    title: str = "Registrar abono",
    helper_text: str | None = None,
    initial_amount: Decimal | str | int | float | None = None,
    fixed_amount: bool = False,
    default_reference: str = "",
    default_notes: str = "",
    accept_button_label: str = "OK",
) -> LayawayPaymentInput | None:
    dialog, layout = window._create_modal_dialog(title, helper_text, width=420)
    form = QFormLayout()
    normalized_initial_amount = Decimal(str(initial_amount or "0.01")).quantize(Decimal("0.01"))
    amount_spin = QDoubleSpinBox()
    amount_minimum = float(normalized_initial_amount if fixed_amount else Decimal("0.01"))
    amount_maximum = float(normalized_initial_amount if fixed_amount else Decimal("999999.99"))
    amount_spin.setRange(amount_minimum, amount_maximum)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    amount_spin.setValue(float(normalized_initial_amount))
    amount_spin.setEnabled(not fixed_amount)
    payment_combo = QComboBox()
    payment_combo.addItems(["Efectivo", "Transferencia", "Mixto"])
    cash_spin = QDoubleSpinBox()
    cash_spin.setRange(0.00, 999999.99)
    cash_spin.setDecimals(2)
    cash_spin.setPrefix("$")
    received_spin = QDoubleSpinBox()
    received_spin.setRange(0.00, 999999.99)
    received_spin.setDecimals(2)
    received_spin.setPrefix("$")
    change_value_label = QLabel("$0.00")
    change_value_label.setObjectName("cashierChangeValue")
    reference_input = QLineEdit()
    reference_input.setPlaceholderText("Referencia opcional")
    reference_input.setText(default_reference)
    notes_input = QTextEdit()
    notes_input.setMaximumHeight(90)
    notes_input.setPlainText(default_notes)
    keypad_target_label = QLabel("Calculadora activa: monto")
    keypad_target_label.setObjectName("analyticsLine")
    target_row = QHBoxLayout()
    target_amount_button = QPushButton("Capturar monto")
    target_cash_button = QPushButton("Capturar efectivo")
    target_received_button = QPushButton("Capturar recibido")
    target_row.addWidget(target_amount_button)
    target_row.addWidget(target_cash_button)
    target_row.addWidget(target_received_button)
    target_row.addStretch()
    form.addRow("Monto", amount_spin)
    form.addRow("Metodo", payment_combo)
    form.addRow("Efectivo en caja", cash_spin)
    form.addRow("Efectivo recibido", received_spin)
    form.addRow("Cambio", change_value_label)
    form.addRow("Referencia", reference_input)
    form.addRow("Observacion", notes_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_button is not None and accept_button_label:
        ok_button.setText(accept_button_label)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(keypad_target_label)
    layout.addLayout(target_row)
    quick_row = QHBoxLayout()
    keypad = QGridLayout()
    layout.addWidget(buttons)

    keypad_target = {"name": "received" if fixed_amount else "amount"}
    payment_method_state = {"value": payment_combo.currentText()}

    def current_target_spin() -> QDoubleSpinBox:
        if keypad_target["name"] == "received" and received_spin.isEnabled():
            return received_spin
        if keypad_target["name"] == "cash" and cash_spin.isEnabled():
            return cash_spin
        if amount_spin.isEnabled():
            return amount_spin
        if received_spin.isEnabled():
            return received_spin
        return cash_spin

    def refresh_keypad_target_state() -> None:
        target_name = keypad_target["name"]
        label_map = {
            "amount": "Calculadora activa: monto",
            "cash": "Calculadora activa: efectivo en caja",
            "received": "Calculadora activa: efectivo recibido",
        }
        keypad_target_label.setText(label_map.get(target_name, "Calculadora activa"))
        target_amount_button.setProperty("active", "true" if target_name == "amount" else "false")
        target_cash_button.setProperty("active", "true" if target_name == "cash" else "false")
        target_received_button.setProperty("active", "true" if target_name == "received" else "false")
        for button in (target_amount_button, target_cash_button, target_received_button):
            button.style().unpolish(button)
            button.style().polish(button)

    def set_keypad_target(name: str) -> None:
        previous_target = keypad_target["name"]
        fallback_order = {
            "amount": ("cash", "received"),
            "cash": ("received", "amount"),
            "received": ("cash", "amount"),
        }
        target_enabled = {
            "amount": amount_spin.isEnabled(),
            "cash": cash_spin.isEnabled(),
            "received": received_spin.isEnabled(),
        }
        if target_enabled.get(name, False):
            keypad_target["name"] = name
        else:
            for fallback_name in fallback_order.get(name, ()):
                if target_enabled.get(fallback_name, False):
                    keypad_target["name"] = fallback_name
                    break
        if keypad_target["name"] == "received" and previous_target != "received":
            received_spin.setValue(0.00)
        refresh_keypad_target_state()

    def update_target_value(raw_text: str) -> None:
        target = current_target_spin()
        parsed_value = parse_keypad_amount_text(raw_text)
        target.setValue(float(parsed_value))

    def current_target_keypad_text() -> str:
        target_value = current_target_spin().value()
        if target_value == 0:
            return "0.00"
        return f"{target_value:.2f}".rstrip("0").rstrip(".")

    def sync_cash_spin() -> None:
        previous_method = payment_method_state["value"]
        current_method = payment_combo.currentText()
        current_cash_amount = Decimal(str(cash_spin.value()))
        if current_method == "Mixto" and previous_method != "Mixto":
            current_cash_amount = Decimal("0.00")
        state = resolve_layaway_payment_state(
            payment_method=current_method,
            amount=Decimal(str(amount_spin.value())),
            current_cash_amount=current_cash_amount,
        )
        cash_spin.blockSignals(True)
        cash_spin.setMaximum(float(state.cash_maximum))
        cash_spin.setValue(float(state.cash_amount))
        cash_spin.setEnabled(state.cash_enabled)
        cash_spin.blockSignals(False)
        received_spin.blockSignals(True)
        if current_method == "Transferencia":
            received_spin.setValue(0.00)
            received_spin.setEnabled(False)
        else:
            reference_amount = state.cash_amount if current_method == "Mixto" else Decimal(str(amount_spin.value()))
            current_received = Decimal(str(received_spin.value()))
            if previous_method != current_method or current_received == Decimal("0.00"):
                current_received = reference_amount
            received_spin.setValue(float(current_received))
            received_spin.setEnabled(True)
        received_spin.blockSignals(False)
        update_change_label()
        payment_method_state["value"] = current_method
        if keypad_target["name"] == "cash" and not cash_spin.isEnabled():
            set_keypad_target("received")
        elif keypad_target["name"] == "received" and not received_spin.isEnabled():
            set_keypad_target("amount")
        sync_received_requirements()
        refresh_keypad_target_state()

    def update_change_label() -> None:
        current_method = payment_combo.currentText()
        if current_method == "Transferencia":
            change_value_label.setText("$0.00")
            return
        if current_method == "Efectivo":
            validation = validate_cash_payment(
                total=Decimal(str(amount_spin.value())),
                received=Decimal(str(received_spin.value())),
            )
            change_value_label.setText(f"${validation.change}")
            return
        cash_registered = Decimal(str(cash_spin.value()))
        cash_received = Decimal(str(received_spin.value()))
        change = cash_received - cash_registered
        if change < Decimal("0.00"):
            change = Decimal("0.00")
        change_value_label.setText(f"${change.quantize(Decimal('0.01'))}")

    def sync_received_requirements() -> None:
        current_method = payment_combo.currentText()
        if current_method == "Transferencia":
            update_change_label()
            return
        minimum_received = (
            Decimal(str(amount_spin.value()))
            if current_method == "Efectivo"
            else Decimal(str(cash_spin.value()))
        )
        current_received = Decimal(str(received_spin.value()))
        if current_received < minimum_received:
            received_spin.blockSignals(True)
            received_spin.setValue(float(minimum_received))
            received_spin.blockSignals(False)
        update_change_label()

    def append_keypad(value: str) -> None:
        update_target_value(append_keypad_text(current_target_keypad_text(), value))

    def clear_keypad() -> None:
        update_target_value(clear_keypad_text())

    def backspace_keypad() -> None:
        update_target_value(backspace_keypad_text(current_target_keypad_text()))

    for amount in (50, 100, 200, 500):
        button = QPushButton(f"${amount}")
        button.setObjectName("toolbarSecondaryButton")
        button.clicked.connect(
            lambda _checked=False, amt=amount: update_target_value(f"{amt:.2f}")
        )
        quick_row.addWidget(button)
    quick_row.addStretch()

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
        button.setMinimumHeight(38)
        button.clicked.connect(lambda _checked=False, value=key: append_keypad(value))
        keypad.addWidget(button, row, column)
    clear_button = QPushButton("Limpiar")
    clear_button.clicked.connect(clear_keypad)
    keypad.addWidget(clear_button, 4, 0, 1, 2)
    backspace_button = QPushButton("Borrar")
    backspace_button.clicked.connect(backspace_keypad)
    keypad.addWidget(backspace_button, 4, 2)

    layout.insertLayout(layout.count() - 1, quick_row)
    layout.insertLayout(layout.count() - 1, keypad)

    target_amount_button.clicked.connect(lambda: set_keypad_target("amount"))
    target_cash_button.clicked.connect(lambda: set_keypad_target("cash"))
    target_received_button.clicked.connect(lambda: set_keypad_target("received"))

    payment_combo.currentTextChanged.connect(sync_cash_spin)
    amount_spin.valueChanged.connect(sync_cash_spin)
    cash_spin.valueChanged.connect(sync_received_requirements)
    received_spin.valueChanged.connect(update_change_label)
    install_keypad_shortcuts(
        dialog=dialog,
        accept_button=buttons.button(QDialogButtonBox.StandardButton.Ok),
        reject_button=buttons.button(QDialogButtonBox.StandardButton.Cancel),
        append_value=append_keypad,
        clear_value=clear_keypad,
        backspace_value=backspace_keypad,
    )
    sync_cash_spin()
    refresh_keypad_target_state()

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    if payment_combo.currentText() == "Efectivo":
        validation = validate_cash_payment(
            total=Decimal(str(amount_spin.value())),
            received=Decimal(str(received_spin.value())),
        )
        if not validation.is_sufficient:
            QMessageBox.warning(window, "Cobro insuficiente", "El efectivo recibido debe cubrir el monto del abono.")
            return None
    if payment_combo.currentText() == "Mixto":
        cash_registered = Decimal(str(cash_spin.value()))
        cash_received = Decimal(str(received_spin.value()))
        if cash_received < cash_registered:
            QMessageBox.warning(
                window,
                "Cobro insuficiente",
                "El efectivo recibido debe cubrir al menos el efectivo registrado en caja.",
            )
            return None

    return build_layaway_payment_input(
        amount=Decimal(str(amount_spin.value())),
        payment_method=payment_combo.currentText(),
        cash_amount=Decimal(str(cash_spin.value())),
        reference=reference_input.text(),
        notes=notes_input.toPlainText(),
    )
