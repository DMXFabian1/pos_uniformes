"""Diálogo viejo de Inventario: registrar entrada de mercancía de un proveedor.

Salió tal cual de `MainWindow._prompt_purchase_data` (2026-11-19).
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
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)
from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Proveedor, Variante
from pos_uniformes.utils.product_name import sanitize_product_display_name


def prompt_purchase_data(
    *,
    create_modal_dialog: Callable[..., tuple[QDialog, QVBoxLayout]],
    set_combo_value: Callable[[QComboBox, object], None],
    prefill_variant_id: Callable[[], int | None],
) -> dict[str, object] | None:
    with get_session() as session:
        proveedores = [
            (proveedor.id, proveedor.nombre)
            for proveedor in session.scalars(
                select(Proveedor).where(Proveedor.activo.is_(True)).order_by(Proveedor.nombre)
            ).all()
        ]
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

    if not proveedores or not variantes:
        raise ValueError("Necesitas al menos un proveedor activo y una presentacion activa.")

    dialog, layout = create_modal_dialog(
        "Registrar entrada",
        "Usa esta ventana para ingresar nueva mercancia de una presentacion existente.",
    )
    form = QFormLayout()
    proveedor_combo = QComboBox()
    for proveedor_id, proveedor_nombre in proveedores:
        proveedor_combo.addItem(proveedor_nombre, proveedor_id)
    presentacion_combo = QComboBox()
    for variante_id, sku, producto_nombre, stock_actual in variantes:
        presentacion_combo.addItem(
            f"{sku} | {producto_nombre} | stock {stock_actual}",
            variante_id,
        )
    set_combo_value(presentacion_combo, prefill_variant_id())
    cantidad_spin = QSpinBox()
    cantidad_spin.setRange(1, 1000)
    costo_input = QLineEdit()
    costo_input.setPlaceholderText("550.00")
    documento_input = QLineEdit()
    documento_input.setPlaceholderText("COMP-0001")
    form.addRow("Proveedor", proveedor_combo)
    form.addRow("Presentacion", presentacion_combo)
    form.addRow("Cantidad", cantidad_spin)
    form.addRow("Costo unitario", costo_input)
    form.addRow("Documento", documento_input)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "proveedor_id": proveedor_combo.currentData(),
        "variante_id": presentacion_combo.currentData(),
        "cantidad": cantidad_spin.value(),
        "costo": costo_input.text().strip(),
        "documento": documento_input.text().strip(),
    }
