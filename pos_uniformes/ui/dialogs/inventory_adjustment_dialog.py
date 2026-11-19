"""Diálogo viejo de Inventario: corregir la existencia de una presentación.

Salió tal cual de `MainWindow._prompt_inventory_adjustment_data` (2026-11-19).
La ventana sigue teniendo ese método y solo delega aquí, pasando lo que el
diálogo necesita.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)
from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Variante
from pos_uniformes.utils.product_name import sanitize_product_display_name


def prompt_inventory_adjustment_data(
    *,
    create_modal_dialog: Callable[..., tuple[QDialog, QVBoxLayout]],
    set_combo_value: Callable[[QComboBox, object], None],
    prefill_variant_id: Callable[[], int | None],
) -> dict[str, object] | None:
    with get_session() as session:
        variantes = [
            (
                variante.id,
                variante.sku,
                sanitize_product_display_name(variante.producto.nombre),
                variante.stock_actual,
            )
            for variante in session.scalars(
                select(Variante).where(Variante.activo.is_(True)).order_by(Variante.sku)
            ).all()
        ]

    if not variantes:
        raise ValueError("No hay presentaciones activas disponibles para ajustar.")

    dialog, layout = create_modal_dialog(
        "Ajuste manual de inventario",
        "Captura el stock final deseado. El sistema calcula automaticamente la diferencia contra el stock actual.",
    )
    form = QFormLayout()
    presentacion_combo = QComboBox()
    stock_map: dict[int, int] = {}
    for variante_id, sku, producto_nombre, stock_actual in variantes:
        stock_map[int(variante_id)] = int(stock_actual)
        presentacion_combo.addItem(
            f"{sku} | {producto_nombre} | stock {stock_actual}",
            variante_id,
        )
    set_combo_value(presentacion_combo, prefill_variant_id())
    stock_actual_label = QLabel()
    stock_actual_label.setObjectName("analyticsLine")
    stock_final_spin = QSpinBox()
    stock_final_spin.setRange(0, 100000)
    stock_final_spin.setAccelerated(True)
    diferencia_label = QLabel()
    diferencia_label.setObjectName("subtleLine")
    referencia_input = QLineEdit()
    referencia_input.setPlaceholderText("AJUSTE-0001")
    observacion_input = QTextEdit()
    observacion_input.setFixedHeight(90)
    observacion_input.setPlaceholderText("Motivo del ajuste")

    def refresh_adjustment_labels() -> None:
        variante_id = presentacion_combo.currentData()
        current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
        stock_actual_label.setText(f"Stock actual: {current_stock}")
        stock_final_spin.blockSignals(True)
        stock_final_spin.setValue(current_stock)
        stock_final_spin.blockSignals(False)
        diferencia_label.setText("Sin cambios pendientes.")

    def refresh_difference_label() -> None:
        variante_id = presentacion_combo.currentData()
        current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
        target_stock = stock_final_spin.value()
        delta = target_stock - current_stock
        if delta == 0:
            diferencia_label.setText("Sin cambios pendientes.")
        elif delta > 0:
            diferencia_label.setText(f"Se agregaran {delta} unidades para dejar stock en {target_stock}.")
        else:
            diferencia_label.setText(f"Se descontaran {abs(delta)} unidades para dejar stock en {target_stock}.")

    presentacion_combo.currentIndexChanged.connect(lambda _: refresh_adjustment_labels())
    stock_final_spin.valueChanged.connect(lambda _: refresh_difference_label())
    refresh_adjustment_labels()

    form.addRow("Presentacion", presentacion_combo)
    form.addRow("Stock actual", stock_actual_label)
    form.addRow("Stock final", stock_final_spin)
    form.addRow("Impacto", diferencia_label)
    form.addRow("Referencia", referencia_input)
    form.addRow("Observacion", observacion_input)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    variante_id = presentacion_combo.currentData()
    current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
    target_stock = stock_final_spin.value()
    return {
        "variante_id": variante_id,
        "cantidad": target_stock - current_stock,
        "stock_actual": current_stock,
        "stock_final": target_stock,
        "referencia": referencia_input.text().strip(),
        "observacion": observacion_input.toPlainText().strip(),
    }
