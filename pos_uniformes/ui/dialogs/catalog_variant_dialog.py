"""Dialogos reutilizables para presentaciones del catalogo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QVBoxLayout,
)
from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.helpers.catalog_form_payload_helper import (
    build_catalog_batch_variant_dialog_payload,
    build_catalog_variant_dialog_payload,
    validate_catalog_variant_submission,
)
from pos_uniformes.utils.product_templates import load_legacy_config_choices, merge_choice_lists

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_catalog_variant_dialog(
    window: "MainWindow",
    *,
    initial: dict[str, object] | None = None,
    prefill: dict[str, object] | None = None,
    include_stock: bool = False,
    default_product_id: int | None = None,
    common_sizes: list[str],
    common_colors: list[str],
    default_variant_size: str,
    default_variant_color: str,
) -> dict[str, object] | None:
    legacy_choices = load_legacy_config_choices()
    with get_session() as session:
        productos = [
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "nombre_base": producto.nombre_base,
                "marca": producto.marca.nombre,
                "escuela": producto.escuela.nombre if producto.escuela else "",
                "tipo_prenda": producto.tipo_prenda.nombre if producto.tipo_prenda else "",
                "tipo_pieza": producto.tipo_pieza.nombre if producto.tipo_pieza else "",
            }
            for producto in session.scalars(
                select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre)
            ).all()
        ]

    if not productos:
        raise ValueError("Primero necesitas al menos un producto activo.")

    dialog, layout = window._create_modal_dialog(
        "Presentacion",
        "Cada presentacion representa una combinacion vendible de producto, talla y color con su propio SKU, precio y stock.",
    )
    form = QFormLayout()
    producto_combo = QComboBox()
    product_map = {producto["id"]: producto for producto in productos}
    for producto in productos:
        context = " | ".join(
            part for part in (producto["escuela"], producto["tipo_prenda"], producto["tipo_pieza"]) if part
        )
        if context:
            producto_combo.addItem(f"{producto['nombre_base']} | {context} | {producto['marca']}", producto["id"])
        else:
            producto_combo.addItem(f"{producto['nombre_base']} | {producto['marca']}", producto["id"])
    sku_input = QLineEdit()
    sku_input.setPlaceholderText("Se genera automaticamente si lo dejas vacio")
    talla_combo = QComboBox()
    talla_combo.setEditable(True)
    talla_combo.addItems(merge_choice_lists(legacy_choices.get("TALLAS", []), common_sizes, [default_variant_size]))
    if talla_combo.lineEdit() is not None:
        talla_combo.lineEdit().setPlaceholderText("Selecciona o escribe una talla")
    color_combo = QComboBox()
    color_combo.setEditable(True)
    color_combo.addItems(merge_choice_lists(legacy_choices.get("COLORES", []), common_colors, [default_variant_color]))
    if color_combo.lineEdit() is not None:
        color_combo.lineEdit().setPlaceholderText("Selecciona o escribe un color")
    precio_input = QLineEdit()
    costo_input = QLineEdit()
    stock_spin = QSpinBox()
    stock_spin.setRange(0, 10000)
    sku_hint = QLabel()
    sku_hint.setObjectName("subtleLine")
    auto_sku_enabled = {"value": True}
    last_auto_sku = {"value": ""}

    def refresh_sku_suggestion() -> None:
        producto_id = producto_combo.currentData()
        talla = talla_combo.currentText().strip()
        color = color_combo.currentText().strip()
        producto_info = product_map.get(producto_id)
        if producto_info is None or not talla or not color:
            sku_hint.setText("Completa producto, talla y color para sugerir un SKU.")
            return

        class _FakeMarca:
            def __init__(self, nombre: str) -> None:
                self.nombre = nombre

        class _FakeProducto:
            def __init__(self, nombre: str, marca_nombre: str) -> None:
                self.nombre = nombre
                self.marca = _FakeMarca(marca_nombre)

        fake_producto = _FakeProducto(producto_info["nombre_base"], producto_info["marca"])
        with get_session() as session:
            suggested = CatalogService.generar_sku_sugerido(
                session=session,
                producto=fake_producto,  # type: ignore[arg-type]
                talla=talla,
                color=color,
                excluding_variant_id=int(initial["variante_id"]) if (initial and initial.get("variante_id")) else None,
            )
        previous_auto = last_auto_sku["value"]
        last_auto_sku["value"] = suggested
        sku_hint.setText(f"SKU sugerido: {suggested}")
        if auto_sku_enabled["value"] or sku_input.text().strip().upper() == previous_auto:
            auto_sku_enabled["value"] = True
            sku_input.setText(suggested)

    def mark_manual_override(value: str) -> None:
        auto_sku_enabled["value"] = value.strip().upper() == last_auto_sku["value"]

    if initial:
        window._set_combo_value(producto_combo, initial["producto_id"])
        sku_input.setText(str(initial["sku"]))
        last_auto_sku["value"] = str(initial["sku"]).strip().upper()
        talla_text = str(initial["talla"])
        talla_index = talla_combo.findText(talla_text)
        if talla_index >= 0:
            talla_combo.setCurrentIndex(talla_index)
        else:
            talla_combo.setEditText(talla_text)
        color_text = str(initial["color"])
        color_index = color_combo.findText(color_text)
        if color_index >= 0:
            color_combo.setCurrentIndex(color_index)
        else:
            color_combo.setEditText(color_text)
        precio_input.setText(str(initial["precio_venta"]))
        costo_input.setText("" if initial["costo_referencia"] is None else str(initial["costo_referencia"]))
        sku_hint.setText(f"SKU actual: {initial['sku']}")
    elif prefill:
        window._set_combo_value(producto_combo, prefill["producto_id"])
        producto_combo.setEnabled(False)
        color_text = str(prefill["color"])
        color_index = color_combo.findText(color_text)
        if color_index >= 0:
            color_combo.setCurrentIndex(color_index)
        else:
            color_combo.setEditText(color_text)
        precio_input.setText(str(prefill["precio_venta"]))
        costo_input.setText("" if prefill.get("costo_referencia") is None else str(prefill["costo_referencia"]))
        sku_input.setReadOnly(True)
        sku_hint.setText("Elige la nueva talla para generar el SKU.")
    elif default_product_id is not None:
        window._set_combo_value(producto_combo, default_product_id)
        sku_hint.setText("Completa talla y color para sugerir un SKU.")
    else:
        sku_hint.setText("Completa producto, talla y color para sugerir un SKU.")

    _section_title_style = "font-size: 13px; font-weight: 700; color: #6B4226; padding: 2px 0;"
    _field_style = (
        "QLineEdit, QComboBox, QSpinBox { padding: 6px 10px; font-size: 13px;"
        " border: 1px solid #d5c9b9; border-radius: 6px; background: #fffaf2; }"
        "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #87492c; }"
    )
    dialog.setStyleSheet(dialog.styleSheet() + _field_style)

    # ── Sección 1: Producto ──
    product_box = QGroupBox("Producto")
    product_box.setStyleSheet("QGroupBox { font-weight: 700; color: #6B4226; }")
    product_form = QFormLayout()
    product_form.setSpacing(8)
    product_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    product_form.addRow("Producto base", producto_combo)
    product_box.setLayout(product_form)

    # ── Sección 2: Identificación ──
    id_box = QGroupBox("Identificacion")
    id_box.setStyleSheet("QGroupBox { font-weight: 700; color: #6B4226; }")
    id_form = QFormLayout()
    id_form.setSpacing(8)
    id_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    id_form.addRow("SKU", sku_input)
    sku_hint.setStyleSheet("font-size: 11px; color: #8a7a6a; padding-left: 4px;")
    id_form.addRow("", sku_hint)

    # Talla y Color en la misma fila
    size_color_row = QHBoxLayout()
    size_color_row.setSpacing(12)
    talla_label = QLabel("Talla")
    talla_label.setStyleSheet("font-size: 13px; color: #3a2a1a;")
    color_label = QLabel("Color")
    color_label.setStyleSheet("font-size: 13px; color: #3a2a1a;")
    talla_combo.setMinimumWidth(120)
    color_combo.setMinimumWidth(140)
    size_color_row.addWidget(talla_label)
    size_color_row.addWidget(talla_combo, 1)
    size_color_row.addSpacing(8)
    size_color_row.addWidget(color_label)
    size_color_row.addWidget(color_combo, 1)
    id_form.addRow(size_color_row)
    id_box.setLayout(id_form)

    # ── Sección 3: Precios ──
    price_box = QGroupBox("Precios")
    price_box.setStyleSheet("QGroupBox { font-weight: 700; color: #6B4226; }")
    price_form = QFormLayout()
    price_form.setSpacing(8)
    price_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    precio_input.setPlaceholderText("0.00")
    costo_input.setPlaceholderText("Opcional")
    price_row = QHBoxLayout()
    price_row.setSpacing(12)
    pv_label = QLabel("Precio venta")
    pv_label.setStyleSheet("font-size: 13px; color: #3a2a1a;")
    cr_label = QLabel("Costo ref.")
    cr_label.setStyleSheet("font-size: 13px; color: #3a2a1a;")
    price_row.addWidget(pv_label)
    price_row.addWidget(precio_input, 1)
    price_row.addSpacing(8)
    price_row.addWidget(cr_label)
    price_row.addWidget(costo_input, 1)
    price_form.addRow(price_row)
    price_box.setLayout(price_form)

    # ── Sección 4: Stock ──
    stock_minimo_spin = QSpinBox()
    stock_minimo_spin.setRange(1, 10000)
    stock_minimo_enabled = QCheckBox("Definir mínimo")
    if initial:
        existing_min = initial.get("stock_minimo")
        if existing_min is not None:
            stock_minimo_enabled.setChecked(True)
            stock_minimo_spin.setValue(int(existing_min))
        else:
            stock_minimo_enabled.setChecked(False)
            stock_minimo_spin.setValue(1)
    else:
        stock_minimo_enabled.setChecked(False)
        stock_minimo_spin.setValue(1)
    stock_minimo_spin.setEnabled(stock_minimo_enabled.isChecked())

    def _on_minimo_toggled(checked: bool) -> None:
        stock_minimo_spin.setEnabled(checked)

    stock_minimo_enabled.toggled.connect(_on_minimo_toggled)

    stock_box = QGroupBox("Stock")
    stock_box.setStyleSheet("QGroupBox { font-weight: 700; color: #6B4226; }")
    stock_form = QFormLayout()
    stock_form.setSpacing(8)
    stock_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    if include_stock:
        stock_form.addRow("Stock inicial", stock_spin)
    else:
        stock_min_row = QHBoxLayout()
        stock_min_row.setSpacing(8)
        stock_min_row.addWidget(stock_minimo_enabled)
        stock_min_row.addWidget(stock_minimo_spin)
        stock_min_row.addStretch()
        stock_form.addRow(stock_min_row)
    stock_box.setLayout(stock_form)

    producto_combo.currentIndexChanged.connect(lambda _: refresh_sku_suggestion())
    talla_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
    color_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
    sku_input.textEdited.connect(mark_manual_override)
    if not initial:
        refresh_sku_suggestion()

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(product_box)
    layout.addWidget(id_box)
    layout.addWidget(price_box)
    layout.addWidget(stock_box)
    layout.addStretch()
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    payload = build_catalog_variant_dialog_payload(
        product_id=producto_combo.currentData(),
        sku=sku_input.text(),
        size=talla_combo.currentText(),
        color=color_combo.currentText(),
        price=precio_input.text(),
        cost=costo_input.text(),
        initial_stock=stock_spin.value(),
    )
    validation = validate_catalog_variant_submission(payload, require_stock=include_stock)
    if validation is not None:
        raise ValueError(validation)
    if not include_stock:
        payload["stock_minimo"] = stock_minimo_spin.value() if stock_minimo_enabled.isChecked() else None
    return payload


def build_catalog_batch_variant_dialog(
    window: "MainWindow",
    *,
    sizes: list[str],
    colors: list[str],
    initial_price: str = "",
    pricing_mode: str = "single",
    prices_by_size: dict[str, str] | None = None,
    price_summary: str = "",
    initial_cost: str = "",
    initial_stock: int = 0,
    default_variant_size: str,
    default_variant_color: str,
) -> dict[str, object] | None:
    normalized_sizes = [value for value in sizes if str(value).strip()] or [default_variant_size]
    normalized_colors = [value for value in colors if str(value).strip()] or [default_variant_color]
    total_variants = len(normalized_sizes) * len(normalized_colors)

    dialog, layout = window._create_modal_dialog(
        "Presentaciones por lote",
        "Confirma las tallas, colores y estructura de precio para crear las presentaciones del producto en una sola operacion.",
        width=720,
    )
    form = QFormLayout()
    sizes_label = QLabel(", ".join(normalized_sizes))
    sizes_label.setWordWrap(True)
    sizes_label.setObjectName("subtleLine")
    colors_label = QLabel(", ".join(normalized_colors))
    colors_label.setWordWrap(True)
    colors_label.setObjectName("subtleLine")
    summary_label = QLabel(f"Se crearan {total_variants} presentaciones.")
    summary_label.setObjectName("subtleLine")
    sku_summary_label = QLabel(window._format_sku_preview(total_variants))
    sku_summary_label.setWordWrap(True)
    sku_summary_label.setObjectName("subtleLine")
    pricing_map = {
        str(size).strip(): str(price).strip()
        for size, price in (prices_by_size or {}).items()
        if str(size).strip() and str(price).strip()
    }
    effective_price_summary = price_summary.strip() or (initial_price.strip() if initial_price.strip() else "-")
    price_label = QLabel(effective_price_summary)
    price_label.setWordWrap(True)
    price_label.setObjectName("subtleLine")
    price_mode_label = QLabel(
        {
            "single": "Precio unico",
            "blocks": "Precio por bloques",
            "manual": "Precio manual por talla",
        }.get(pricing_mode, "Precio unico")
    )
    price_mode_label.setObjectName("subtleLine")
    cost_input = QLineEdit()
    cost_input.setPlaceholderText("Opcional")
    cost_input.setText(initial_cost)
    stock_spin = QSpinBox()
    stock_spin.setRange(0, 10000)
    stock_spin.setValue(initial_stock)
    form.addRow("Tallas", sizes_label)
    form.addRow("Colores", colors_label)
    form.addRow("", summary_label)
    form.addRow("SKU previstos", sku_summary_label)
    form.addRow("Modo precio", price_mode_label)
    form.addRow("Precio venta", price_label)
    form.addRow("Costo ref.", cost_input)
    form.addRow("Stock inicial", stock_spin)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    return build_catalog_batch_variant_dialog_payload(
        sizes=normalized_sizes,
        colors=normalized_colors,
        initial_price=initial_price,
        pricing_mode=pricing_mode,
        prices_by_size=pricing_map,
        price_summary=effective_price_summary,
        initial_cost=cost_input.text(),
        initial_stock=stock_spin.value(),
    )
