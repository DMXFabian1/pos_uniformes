"""Prompts reutilizables para operaciones de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.models import TipoMovimientoCaja


@dataclass(frozen=True)
class CashCutSummaryView:
    opened_at_label: str
    opening_amount: Decimal
    reactivo_count: int
    reactivo_total: Decimal
    ingresos_count: int
    ingresos_total: Decimal
    retiros_count: int
    retiros_total: Decimal
    cash_sales_count: int
    cash_sales_total: Decimal
    cash_payments_count: int
    cash_payments_total: Decimal
    expected_amount: Decimal
    suggested_next_reactivo: Decimal


def build_cash_cut_summary_lines(summary_view: CashCutSummaryView) -> list[str]:
    lines = [
        f"Apertura: {summary_view.opened_at_label}",
        f"Reactivo inicial: ${summary_view.opening_amount}",
    ]
    has_extra_cash_movements = any(
        (
            summary_view.reactivo_count,
            summary_view.ingresos_count,
            summary_view.retiros_count,
            summary_view.cash_sales_count,
            summary_view.cash_payments_count,
            summary_view.reactivo_total,
            summary_view.ingresos_total,
            summary_view.retiros_total,
            summary_view.cash_sales_total,
            summary_view.cash_payments_total,
        )
    )
    if has_extra_cash_movements:
        lines.extend(
            [
                f"Reactivos extra: {summary_view.reactivo_count} | ${summary_view.reactivo_total}",
                f"Ingresos manuales: {summary_view.ingresos_count} | ${summary_view.ingresos_total}",
                f"Retiros manuales: {summary_view.retiros_count} | ${summary_view.retiros_total}",
                f"Ventas con efectivo: {summary_view.cash_sales_count}",
                f"Efectivo por ventas: ${summary_view.cash_sales_total}",
                f"Abonos con efectivo: {summary_view.cash_payments_count}",
                f"Efectivo por abonos: ${summary_view.cash_payments_total}",
            ]
        )
    lines.append(f"Esperado en caja: ${summary_view.expected_amount}")
    return lines


def _create_cash_prompt_dialog(
    parent: QWidget,
    title: str,
    helper_text: str | None = None,
    width: int = 420,
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


def prompt_open_cash_session(
    parent: QWidget,
    *,
    suggested_amount: Decimal | None,
) -> dict[str, object] | None:
    dialog, layout = _create_cash_prompt_dialog(
        parent,
        "Apertura de caja",
        "Antes de operar, confirma cuanto reactivo inicial hay actualmente en caja.",
        width=420,
    )
    amount_spin = QDoubleSpinBox()
    amount_spin.setRange(0.0, 999999.99)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    amount_spin.setSingleStep(50.0)
    if suggested_amount is not None:
        amount_spin.setValue(float(suggested_amount))
    note_input = QTextEdit()
    note_input.setPlaceholderText("Observacion opcional")
    note_input.setMaximumHeight(90)
    reuse_button = QPushButton("Usar ultimo reactivo")
    reuse_button.setObjectName("toolbarSecondaryButton")
    reuse_button.setEnabled(suggested_amount is not None)
    reuse_hint = QLabel(
        f"Ultimo reactivo sugerido: ${suggested_amount}" if suggested_amount is not None else "No hay un reactivo anterior registrado."
    )
    reuse_hint.setObjectName("subtleLine")
    reuse_hint.setWordWrap(True)
    if suggested_amount is not None:
        reuse_button.clicked.connect(lambda: amount_spin.setValue(float(suggested_amount)))
    form = QFormLayout()
    form.addRow("Reactivo inicial", amount_spin)
    form.addRow("", reuse_button)
    form.addRow("Observacion", note_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Abrir caja")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(reuse_hint)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "monto_apertura": Decimal(str(amount_spin.value())).quantize(Decimal("0.01")),
        "observacion": note_input.toPlainText().strip(),
    }


def prompt_cash_movement_data(
    parent: QWidget,
    *,
    movement_type: TipoMovimientoCaja,
    target_total: Decimal | None,
) -> dict[str, object] | None:
    labels = {
        TipoMovimientoCaja.REACTIVO: (
            "Ajustar reactivo",
            "Captura el total actual de reactivo en caja. El sistema calculara la diferencia automaticamente.",
        ),
        TipoMovimientoCaja.INGRESO: ("Ingreso", "Registra una entrada manual de efectivo a la caja actual."),
        TipoMovimientoCaja.RETIRO: ("Retiro", "Registra una salida manual de efectivo de la caja actual."),
    }
    title, helper = labels[movement_type]
    dialog, layout = _create_cash_prompt_dialog(parent, title, helper, width=420)
    amount_spin = QDoubleSpinBox()
    amount_spin.setRange(0.00, 999999.99)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    amount_spin.setSingleStep(50.0)
    concept_input = QTextEdit()
    concept_input.setPlaceholderText("Concepto u observacion")
    concept_input.setMaximumHeight(90)
    form = QFormLayout()
    delta_label = QLabel("")
    delta_label.setObjectName("cashierChangeValue")
    if movement_type == TipoMovimientoCaja.REACTIVO:
        if target_total is not None:
            amount_spin.setValue(float(target_total))
        current_label = QLabel(
            f"Reactivo actual registrado: ${target_total}" if target_total is not None else "No se pudo calcular el reactivo actual."
        )
        current_label.setObjectName("subtleLine")
        current_label.setWordWrap(True)

        def update_delta() -> None:
            current_total = target_total or Decimal("0.00")
            delta = (Decimal(str(amount_spin.value())).quantize(Decimal("0.01")) - current_total).quantize(Decimal("0.01"))
            sign = "+" if delta >= Decimal("0.00") else ""
            delta_label.setText(f"Diferencia a registrar: {sign}${delta}")

        amount_spin.valueChanged.connect(update_delta)
        form.addRow(current_label)
        form.addRow("Total actual", amount_spin)
        form.addRow("Diferencia", delta_label)
        update_delta()
    else:
        form.addRow("Monto", amount_spin)
    form.addRow("Concepto", concept_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(f"Registrar {title.lower()}")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    amount = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
    if movement_type == TipoMovimientoCaja.REACTIVO:
        current_total = target_total or Decimal("0.00")
        amount = (amount - current_total).quantize(Decimal("0.01"))
        if amount == Decimal("0.00"):
            QMessageBox.information(dialog, "Sin cambios", "El total actual coincide con el reactivo ya registrado.")
            return None
    return {
        "monto": amount,
        "total_objetivo": Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
        if movement_type == TipoMovimientoCaja.REACTIVO
        else None,
        "concepto": concept_input.toPlainText().strip(),
    }


def prompt_admin_cash_cut_data(parent: QWidget) -> dict[str, object] | None:
    dialog, layout = _create_cash_prompt_dialog(
        parent,
        "Corte administrativo",
        "Registra una salida administrativa real de efectivo. Este movimiento impacta el esperado del cierre como cualquier retiro.",
        width=430,
    )
    amount_spin = QDoubleSpinBox()
    amount_spin.setRange(0.00, 999999.99)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    amount_spin.setSingleStep(50.0)
    note_input = QTextEdit()
    note_input.setPlaceholderText("Nota opcional para identificar el corte administrativo")
    note_input.setMaximumHeight(90)
    concept_label = QLabel("Concepto fijo: Corte administrativo")
    concept_label.setObjectName("subtleLine")
    concept_label.setWordWrap(True)
    form = QFormLayout()
    form.addRow("Monto", amount_spin)
    form.addRow("Nota", note_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText("Registrar corte")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(concept_label)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    amount = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
    if amount <= Decimal("0.00"):
        QMessageBox.information(dialog, "Monto invalido", "Captura un monto mayor a cero para registrar el corte.")
        return None
    note = note_input.toPlainText().strip()
    concept = "Corte administrativo"
    if note:
        concept = f"{concept} | {note}"
    return {
        "monto": amount,
        "concepto": concept,
        "nota": note,
    }


def prompt_cash_opening_correction(
    parent: QWidget,
    *,
    current_amount: Decimal,
) -> dict[str, object] | None:
    dialog, layout = _create_cash_prompt_dialog(
        parent,
        "Corregir apertura",
        "Actualiza el reactivo inicial de la caja abierta. Usa esto solo si la apertura se registro con un monto incorrecto.",
        width=430,
    )
    amount_spin = QDoubleSpinBox()
    amount_spin.setRange(0.00, 999999.99)
    amount_spin.setDecimals(2)
    amount_spin.setPrefix("$")
    amount_spin.setSingleStep(50.0)
    amount_spin.setValue(float(current_amount))
    difference_label = QLabel("")
    difference_label.setObjectName("cashierChangeValue")
    current_label = QLabel(f"Reactivo inicial registrado: ${current_amount}")
    current_label.setObjectName("subtleLine")
    current_label.setWordWrap(True)
    reason_input = QTextEdit()
    reason_input.setPlaceholderText("Motivo o aclaracion de la correccion")
    reason_input.setMaximumHeight(90)

    def update_difference() -> None:
        nuevo = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
        delta = (nuevo - current_amount).quantize(Decimal("0.01"))
        sign = "+" if delta >= Decimal("0.00") else ""
        difference_label.setText(f"Cambio sobre apertura: {sign}${delta}")

    amount_spin.valueChanged.connect(update_difference)
    update_difference()
    form = QFormLayout()
    form.addRow(current_label)
    form.addRow("Nuevo reactivo inicial", amount_spin)
    form.addRow("Diferencia", difference_label)
    form.addRow("Motivo", reason_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar correccion")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    nuevo_monto = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
    if nuevo_monto == current_amount:
        QMessageBox.information(dialog, "Sin cambios", "El reactivo inicial ya tiene ese valor.")
        return None
    return {
        "monto_anterior": current_amount,
        "nuevo_monto": nuevo_monto,
        "motivo": reason_input.toPlainText().strip(),
    }


def prompt_cash_cut_data(
    parent: QWidget,
    *,
    summary_view: CashCutSummaryView,
) -> dict[str, object] | None:
    dialog, layout = _create_cash_prompt_dialog(
        parent,
        "Corte de caja",
        "Revisa el efectivo esperado y captura el monto contado para cerrar la caja.",
        width=520,
    )
    info = QLabel(
        "\n".join(build_cash_cut_summary_lines(summary_view))
    )
    info.setWordWrap(True)
    info.setObjectName("inventoryMetaCard")
    counted_spin = QDoubleSpinBox()
    counted_spin.setRange(0.0, 999999.99)
    counted_spin.setDecimals(2)
    counted_spin.setPrefix("$")
    counted_spin.setSingleStep(50.0)
    counted_spin.setValue(float(summary_view.expected_amount))
    difference_label = QLabel("$0.00")
    difference_label.setObjectName("cashierChangeValue")
    next_reactivo_spin = QDoubleSpinBox()
    next_reactivo_spin.setRange(0.0, 999999.99)
    next_reactivo_spin.setDecimals(2)
    next_reactivo_spin.setPrefix("$")
    next_reactivo_spin.setSingleStep(50.0)
    next_reactivo_spin.setValue(float(summary_view.suggested_next_reactivo))
    note_input = QTextEdit()
    note_input.setPlaceholderText("Observaciones del corte")
    note_input.setMaximumHeight(90)

    def update_difference() -> None:
        counted = Decimal(str(counted_spin.value())).quantize(Decimal("0.01"))
        difference = (counted - summary_view.expected_amount).quantize(Decimal("0.01"))
        difference_label.setText(f"${difference}")
        next_reactivo_spin.setValue(float(counted))

    counted_spin.valueChanged.connect(update_difference)
    form = QFormLayout()
    form.addRow("Monto contado", counted_spin)
    form.addRow("Diferencia", difference_label)
    form.addRow("Reactivo nueva sesion", next_reactivo_spin)
    form.addRow("Observacion", note_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Cerrar y reabrir caja")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(info)
    layout.addLayout(form)
    layout.addWidget(buttons)
    update_difference()
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "monto_contado": Decimal(str(counted_spin.value())).quantize(Decimal("0.01")),
        "next_reactivo": Decimal(str(next_reactivo_spin.value())).quantize(Decimal("0.01")),
        "observacion": note_input.toPlainText().strip(),
    }
