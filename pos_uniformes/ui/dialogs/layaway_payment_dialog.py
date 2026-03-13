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
    QLineEdit,
    QTextEdit,
)

from pos_uniformes.services.layaway_payment_service import (
    LayawayPaymentInput,
    build_layaway_payment_input,
    resolve_layaway_payment_state,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_layaway_payment_dialog(window: "MainWindow") -> LayawayPaymentInput | None:
    dialog, layout = window._create_modal_dialog("Registrar abono", width=420)
    form = QFormLayout()
    amount_spin = QDoubleSpinBox()
    amount_spin.setRange(0.01, 999999.99)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    payment_combo = QComboBox()
    payment_combo.addItems(["Efectivo", "Transferencia", "Mixto"])
    cash_spin = QDoubleSpinBox()
    cash_spin.setRange(0.00, 999999.99)
    cash_spin.setDecimals(2)
    cash_spin.setPrefix("$")
    reference_input = QLineEdit()
    reference_input.setPlaceholderText("Referencia opcional")
    notes_input = QTextEdit()
    notes_input.setMaximumHeight(90)
    form.addRow("Monto", amount_spin)
    form.addRow("Metodo", payment_combo)
    form.addRow("Efectivo en caja", cash_spin)
    form.addRow("Referencia", reference_input)
    form.addRow("Observacion", notes_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)

    def sync_cash_spin() -> None:
        state = resolve_layaway_payment_state(
            payment_method=payment_combo.currentText(),
            amount=Decimal(str(amount_spin.value())),
            current_cash_amount=Decimal(str(cash_spin.value())),
        )
        cash_spin.blockSignals(True)
        cash_spin.setMaximum(float(state.cash_maximum))
        cash_spin.setValue(float(state.cash_amount))
        cash_spin.setEnabled(state.cash_enabled)
        cash_spin.blockSignals(False)

    payment_combo.currentTextChanged.connect(sync_cash_spin)
    amount_spin.valueChanged.connect(sync_cash_spin)
    sync_cash_spin()

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    return build_layaway_payment_input(
        amount=Decimal(str(amount_spin.value())),
        payment_method=payment_combo.currentText(),
        cash_amount=Decimal(str(cash_spin.value())),
        reference=reference_input.text(),
        notes=notes_input.toPlainText(),
    )
