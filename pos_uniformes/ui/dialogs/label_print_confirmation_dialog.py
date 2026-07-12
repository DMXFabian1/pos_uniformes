"""Confirmación de impresión de etiquetas tras agregar piezas desde búsqueda.

Espejo del flujo de caja (_show_label_print_confirmation): checkboxes por SKU
(marcados por default), botones Todas/Ninguna y Enter = imprimir. La lógica
de armado de entradas es pura para poder testearla sin abrir el diálogo.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Tipos de etiqueta ofrecidos y su paper_mode (define la impresora):
# Normal/Split → impresora de rollo continuo; Label → troquelada DK-1221.
_LABEL_TYPE_OPTIONS = [
    ("Normal", "standard"),
    ("Split", "split"),
    ("Label (troquelada)", "dk1221"),
]


def build_label_entries(
    skus: list[str],
    find_row_by_sku: Callable[[str], dict | None],
) -> list[tuple[str, str]]:
    """(sku, texto del checkbox) por cada SKU agregado, sin duplicados."""
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_sku in skus:
        sku = str(raw_sku or "").strip().upper()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        row = find_row_by_sku(sku)
        if row is None:
            entries.append((sku, sku))
            continue
        name = str(row.get("producto_nombre_base") or row.get("producto_nombre") or "").strip()
        size = str(row.get("talla") or "").strip()
        parts = [sku]
        if name:
            parts.append(name)
        if size and size != "-":
            parts.append(f"T:{size}")
        entries.append((sku, " · ".join(parts)))
    return entries


def open_label_print_confirmation(
    parent: QWidget | None,
    entries: list[tuple[str, str]],
) -> tuple[list[str], str]:
    """Muestra la confirmación y devuelve (SKUs seleccionados, tipo de etiqueta).

    El tipo (paper_mode) elegido decide la impresora. ([], "standard") = nada.
    """
    if not entries:
        return [], "standard"

    dialog = QDialog(parent)
    dialog.setWindowTitle("Imprimir etiquetas")
    dialog.setMinimumWidth(420)
    layout = QVBoxLayout()

    count = len(entries)
    header = QLabel(
        f"Se agregaron {count} producto{'s' if count != 1 else ''} desde búsqueda."
    )
    hint = QLabel("Selecciona las etiquetas que quieres imprimir:")
    layout.addWidget(header)
    layout.addWidget(hint)

    checkboxes: list[tuple[str, QCheckBox]] = []
    for sku, label in entries:
        checkbox = QCheckBox(label)
        checkbox.setChecked(True)
        layout.addWidget(checkbox)
        checkboxes.append((sku, checkbox))

    select_row = QHBoxLayout()
    all_btn = QPushButton("Todas")
    none_btn = QPushButton("Ninguna")
    all_btn.clicked.connect(lambda checked=False: [cb.setChecked(True) for _s, cb in checkboxes])
    none_btn.clicked.connect(lambda checked=False: [cb.setChecked(False) for _s, cb in checkboxes])
    select_row.addWidget(all_btn)
    select_row.addWidget(none_btn)
    select_row.addStretch()
    layout.addLayout(select_row)

    # Tipo de etiqueta (define la impresora que se usa).
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel("Tipo de etiqueta:"))
    mode_combo = QComboBox()
    for texto, valor in _LABEL_TYPE_OPTIONS:
        mode_combo.addItem(texto, valor)
    mode_row.addWidget(mode_combo, 1)
    layout.addLayout(mode_row)

    action_row = QHBoxLayout()
    skip_btn = QPushButton("No imprimir")
    skip_btn.setObjectName("ghostButton")
    print_btn = QPushButton("Imprimir seleccionadas")
    print_btn.setObjectName("primaryButton")
    print_btn.setDefault(True)  # Enter imprime
    skip_btn.clicked.connect(dialog.reject)
    print_btn.clicked.connect(dialog.accept)
    action_row.addStretch()
    action_row.addWidget(skip_btn)
    action_row.addWidget(print_btn)
    layout.addLayout(action_row)

    dialog.setLayout(layout)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return [], "standard"
    selected = [sku for sku, checkbox in checkboxes if checkbox.isChecked()]
    mode = str(mode_combo.currentData() or "standard")
    return selected, mode
