"""Dialogos reutilizables para presentaciones del catalogo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
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
                excluding_variant_id=int(initial["variante_id"]) if initial else None,
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
    elif default_product_id is not None:
        window._set_combo_value(producto_combo, default_product_id)
        sku_hint.setText("Completa talla y color para sugerir un SKU.")
    else:
        sku_hint.setText("Completa producto, talla y color para sugerir un SKU.")

    form.addRow("Producto", producto_combo)
    form.addRow("SKU", sku_input)
    form.addRow("", sku_hint)
    form.addRow("Talla", talla_combo)
    form.addRow("Color", color_combo)
    form.addRow("Precio venta", precio_input)
    form.addRow("Costo referencia", costo_input)
    if include_stock:
        form.addRow("Stock inicial", stock_spin)

    producto_combo.currentIndexChanged.connect(lambda _: refresh_sku_suggestion())
    talla_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
    color_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
    sku_input.textEdited.connect(mark_manual_override)
    if not initial:
        refresh_sku_suggestion()

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addLayout(form)
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
