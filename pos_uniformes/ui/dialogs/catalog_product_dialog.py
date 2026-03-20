"""Dialogo reutilizable para alta/edicion de productos de catalogo."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
import unicodedata

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Usuario,
)
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.helpers.catalog_form_payload_helper import (
    build_catalog_product_dialog_payload,
    validate_catalog_product_presentations_step,
    validate_catalog_product_submission,
)
from pos_uniformes.ui.helpers.catalog_product_form_mode_helper import (
    REGULAR_ATTRIBUTE_SUGGESTIONS,
    REGULAR_CATEGORY_SUGGESTIONS,
    REGULAR_GARMENT_SUGGESTIONS,
    REGULAR_LOCATION_SUGGESTIONS,
    REGULAR_PIECE_SUGGESTIONS,
    UNIFORM_CATEGORIES,
    build_catalog_product_form_mode_view,
    detect_catalog_product_form_mode,
)
from pos_uniformes.ui.helpers.catalog_product_form_summary_helper import (
    build_catalog_capture_summary_html,
    build_catalog_product_display_name_preview,
    build_catalog_review_details_html,
    build_catalog_variant_examples_preview,
)
from pos_uniformes.utils.product_templates import (
    build_price_blocks,
    build_product_template_preview,
    build_step_template_preview,
    load_legacy_config_choices,
    load_legacy_product_templates,
    load_step_product_templates,
    merge_choice_lists,
    product_template_defaults,
    suggest_presentation_template,
    suggest_price_capture_mode,
    step_template_defaults,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_catalog_product_dialog(
    window: "MainWindow",
    *,
    initial: dict[str, object] | None = None,
    picker_button_class,
    product_templates: list[dict[str, str]],
    common_sizes: list[str],
    common_colors: list[str],
    default_variant_size: str,
    default_variant_color: str,
) -> dict[str, object] | None:
    with get_session() as session:
        categorias = [
            (categoria.id, categoria.nombre)
            for categoria in session.scalars(
                select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)
            ).all()
        ]
        marcas = [
            (marca.id, marca.nombre)
            for marca in session.scalars(
                select(Marca).where(Marca.activo.is_(True)).order_by(Marca.nombre)
            ).all()
        ]
        escuelas = [
            escuela.nombre
            for escuela in session.scalars(
                select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)
            ).all()
        ]
        tipos_prenda = [
            tipo.nombre
            for tipo in session.scalars(
                select(TipoPrenda).where(TipoPrenda.activo.is_(True)).order_by(TipoPrenda.nombre)
            ).all()
        ]
        tipos_pieza = [
            tipo.nombre
            for tipo in session.scalars(
                select(TipoPieza).where(TipoPieza.activo.is_(True)).order_by(TipoPieza.nombre)
            ).all()
        ]
        atributos = [
            atributo.nombre
            for atributo in session.scalars(
                select(AtributoProducto).where(AtributoProducto.activo.is_(True)).order_by(AtributoProducto.nombre)
            ).all()
        ]
        niveles = [
            nivel.nombre
            for nivel in session.scalars(
                select(NivelEducativo).where(NivelEducativo.activo.is_(True)).order_by(NivelEducativo.nombre)
            ).all()
        ]
        product_initial = None
        if initial is not None:
            producto = session.get(Producto, int(initial["producto_id"]))
            if producto is not None:
                product_initial = {
                    "categoria_id": producto.categoria_id,
                    "categoria_nombre": producto.categoria.nombre if producto.categoria else "",
                    "marca_id": producto.marca_id,
                    "nombre_base": producto.nombre_base,
                    "descripcion": producto.descripcion or "",
                    "escuela": producto.escuela.nombre if producto.escuela else "",
                    "tipo_prenda": producto.tipo_prenda.nombre if producto.tipo_prenda else "",
                    "tipo_pieza": producto.tipo_pieza.nombre if producto.tipo_pieza else "",
                    "atributo": producto.atributo.nombre if producto.atributo else "",
                    "nivel_educativo": producto.nivel_educativo.nombre if producto.nivel_educativo else "",
                    "genero": producto.genero or "",
                    "escudo": producto.escudo or "",
                    "ubicacion": producto.ubicacion or "",
                }

    if not categorias or not marcas:
        raise ValueError("Primero necesitas al menos una categoria y una marca activas.")

    legacy_choices = load_legacy_config_choices()
    escuelas = merge_choice_lists(escuelas)
    tipos_uniforme = ["Deportivo", "Oficial", "Basico", "Escolta", "Accesorio"]
    tipos_prenda = merge_choice_lists(tipos_prenda, legacy_choices.get("TIPOS_PRENDA", []), tipos_uniforme)
    tipos_pieza = merge_choice_lists(tipos_pieza, legacy_choices.get("TIPOS_PIEZA", []))
    atributos = merge_choice_lists(atributos, legacy_choices.get("ATRIBUTOS", []))
    niveles = merge_choice_lists(niveles, legacy_choices.get("NIVELES_EDUCATIVOS", []))
    generos_disponibles = merge_choice_lists(legacy_choices.get("GENEROS", []))
    escudos_disponibles = merge_choice_lists(legacy_choices.get("ESCUDOS", []))
    ubicaciones_disponibles = merge_choice_lists(legacy_choices.get("UBICACIONES", []))
    regular_category_suggestions = merge_choice_lists(list(REGULAR_CATEGORY_SUGGESTIONS))
    regular_garment_suggestions = merge_choice_lists(tipos_prenda, list(REGULAR_GARMENT_SUGGESTIONS))
    regular_piece_suggestions = merge_choice_lists(tipos_pieza, list(REGULAR_PIECE_SUGGESTIONS))
    regular_attribute_suggestions = merge_choice_lists(atributos, list(REGULAR_ATTRIBUTE_SUGGESTIONS))
    regular_location_suggestions = merge_choice_lists(ubicaciones_disponibles, list(REGULAR_LOCATION_SUGGESTIONS))

    dialog, layout = window._create_modal_dialog(
        "Producto",
        "Captura los datos base del producto. Esta accion no altera inventario por si sola.",
        width=1040,
        expand_to_screen=True,
    )
    legacy_templates = load_legacy_product_templates()
    template_entries: list[dict[str, object]] = [
        {
            "source": "builtin",
            "label": str(template["label"]),
            "category": str(template["category"]),
            "name": str(template["name"]),
            "description": str(template["description"]),
        }
        for template in product_templates
    ]
    template_entries.extend(legacy_templates)
    base_step_templates = load_step_product_templates("base")
    context_step_templates = load_step_product_templates("context")
    presentation_step_templates = load_step_product_templates("presentation")
    template_combo = QComboBox()
    template_combo.addItem("Selecciona una plantilla", None)
    for template_entry in template_entries:
        template_combo.addItem(str(template_entry["label"]), template_entry)
    base_template_combo = QComboBox()
    base_template_combo.addItem("Selecciona plantilla base", None)
    for template_entry in base_step_templates:
        base_template_combo.addItem(str(template_entry["label"]), template_entry)
    context_template_combo = QComboBox()
    context_template_combo.addItem("Selecciona plantilla de contexto", None)
    for template_entry in context_step_templates:
        context_template_combo.addItem(str(template_entry["label"]), template_entry)
    presentation_template_combo = QComboBox()
    presentation_template_combo.addItem("Selecciona plantilla de presentaciones", None)
    for template_entry in presentation_step_templates:
        presentation_template_combo.addItem(str(template_entry["label"]), template_entry)
    product_mode_combo = QComboBox()
    product_mode_combo.addItem("Uniforme escolar", "uniform")
    product_mode_combo.addItem("Ropa normal", "regular")
    categoria_combo = QComboBox()
    categoria_combo.addItem("Selecciona categoria", None)
    for categoria_id, categoria_nombre in categorias:
        categoria_combo.addItem(categoria_nombre, categoria_id)
    marca_combo = QComboBox()
    marca_combo.addItem("Selecciona marca", None)
    for marca_id, marca_nombre in marcas:
        marca_combo.addItem(marca_nombre, marca_id)
    add_category_button = QPushButton("+")
    add_brand_button = QPushButton("+")
    add_category_button.setObjectName("iconButton")
    add_brand_button.setObjectName("iconButton")
    add_category_button.setToolTip("Crear una categoria nueva sin salir de esta ventana.")
    add_brand_button.setToolTip("Crear una marca nueva sin salir de esta ventana.")
    uniform_category_label = QLabel("Uniformes")
    uniform_category_label.setObjectName("readOnlyField")
    category_mode_label = QLabel("Categoria")
    category_mode_label.setObjectName("inventoryFilterLabel")
    product_mode_label = QLabel("Modo de captura")
    product_mode_label.setObjectName("inventoryFilterLabel")
    category_field_stack = QStackedWidget()
    regular_category_row = QWidget()
    regular_category_layout = QHBoxLayout()
    regular_category_layout.setContentsMargins(0, 0, 0, 0)
    regular_category_layout.setSpacing(10)
    regular_category_layout.addWidget(categoria_combo, 1)
    regular_category_layout.addWidget(add_category_button)
    regular_category_row.setLayout(regular_category_layout)
    category_field_stack.addWidget(uniform_category_label)
    category_field_stack.addWidget(regular_category_row)
    nombre_input = QLineEdit()
    descripcion_input = QTextEdit()
    descripcion_input.setFixedHeight(90)
    escuela_combo = QComboBox()
    escuela_combo.setEditable(True)
    escuela_combo.addItem("")
    escuela_combo.addItems(escuelas)
    tipo_prenda_combo = QComboBox()
    tipo_prenda_combo.setEditable(True)
    tipo_prenda_combo.addItem("")
    tipo_prenda_combo.addItems(tipos_prenda)
    tipo_pieza_combo = QComboBox()
    tipo_pieza_combo.setEditable(True)
    tipo_pieza_combo.addItem("")
    tipo_pieza_combo.addItems(tipos_pieza)
    atributo_combo = QComboBox()
    atributo_combo.setEditable(True)
    atributo_combo.addItem("")
    atributo_combo.addItems(atributos)
    nivel_combo = QComboBox()
    nivel_combo.setEditable(True)
    nivel_combo.addItem("")
    nivel_combo.addItems(niveles)
    genero_input = QComboBox()
    genero_input.setEditable(True)
    genero_input.addItem("")
    genero_input.addItems(generos_disponibles)
    escudo_input = QComboBox()
    escudo_input.setEditable(True)
    escudo_input.addItem("")
    escudo_input.addItems(escudos_disponibles)
    ubicacion_input = QComboBox()
    ubicacion_input.setEditable(True)
    ubicacion_input.addItem("")
    ubicacion_input.addItems(ubicaciones_disponibles)
    variant_sizes_button = picker_button_class(
        "Tallas: ninguna",
        title="Seleccionar tallas",
        helper_text="Marca varias tallas sin que el selector se cierre a cada clic. Puedes filtrar, elegir varias y aplicar al final.",
        columns=5,
        presets=[
            ("Basicas", ["2", "4", "6", "8", "10", "12", "14", "16"]),
            ("Pants", ["16", "CH", "MD", "GD", "EXG"]),
            ("Mallas", ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"]),
            ("Pares", lambda values: [value for value in values if value.isdigit() and int(value) % 2 == 0]),
            ("Todas", lambda values: list(values)),
            ("Ninguna", []),
        ],
    )
    variant_colors_button = picker_button_class(
        "Colores: ninguno",
        title="Seleccionar colores",
        helper_text="Marca uno o varios colores para generar las presentaciones en lote. Si no eliges color, se usara Sin color.",
        columns=4,
        presets=[
            ("Todos", lambda values: [value for value in values if value != default_variant_color]),
            ("Ninguno", []),
        ],
    )
    variant_price_input = QLineEdit()
    variant_price_input.setPlaceholderText("Ej. 199.00")
    variant_cost_input = QLineEdit()
    variant_cost_input.setPlaceholderText("Opcional")
    variant_stock_spin = QSpinBox()
    variant_stock_spin.setRange(0, 10000)
    variant_sizes_summary = QLabel("Sin tallas seleccionadas.")
    variant_colors_summary = QLabel("Sin colores seleccionados.")
    variant_count_summary = QLabel("Si eliges tallas y colores, al guardar podremos crear presentaciones por lote.")
    price_mode_combo = QComboBox()
    price_mode_combo.addItem("Precio unico", "single")
    price_mode_combo.addItem("Precio por bloques", "blocks")
    price_mode_combo.addItem("Precio manual por talla", "manual")
    configure_prices_button = QPushButton("Configurar precios")
    price_mode_hint = QLabel("Captura un solo precio para todas las tallas o usa bloques si manejas escalones.")
    price_mode_hint.setWordWrap(True)
    price_mode_hint.setObjectName("subtleLine")
    price_strategy_summary = QLabel("Todavia no hay estructura de precios definida.")
    price_strategy_summary.setWordWrap(True)
    price_strategy_summary.setObjectName("subtleLine")
    variant_sizes_summary.setObjectName("subtleLine")
    variant_colors_summary.setObjectName("subtleLine")
    variant_count_summary.setObjectName("subtleLine")
    auto_name_checkbox = QCheckBox("Auto")
    auto_name_checkbox.setChecked(initial is None)
    generate_name_button = QPushButton("Generar")
    final_name_preview = QLabel("Nombre final pendiente.")
    final_name_preview.setWordWrap(True)
    final_name_preview.setObjectName("subtleLine")
    live_name_card = QFrame()
    live_name_card.setObjectName("infoCard")
    live_name_card_layout = QVBoxLayout()
    live_name_card_layout.setContentsMargins(16, 14, 16, 14)
    live_name_card_layout.setSpacing(4)
    live_name_caption = QLabel("Nombre del producto")
    live_name_caption.setObjectName("liveNameCaption")
    live_name_title = QLabel("Nombre en construccion")
    live_name_title.setWordWrap(True)
    live_name_title.setObjectName("liveNameValue")
    live_name_hint = QLabel("Se construye conforme avanzas en base, contexto y presentaciones.")
    live_name_hint.setWordWrap(True)
    live_name_hint.setObjectName("liveNameHint")
    live_name_card_layout.addWidget(live_name_caption)
    live_name_card_layout.addWidget(live_name_title)
    live_name_card_layout.addWidget(live_name_hint)
    live_name_card.setLayout(live_name_card_layout)
    capture_summary_card = QFrame()
    capture_summary_card.setObjectName("infoCard")
    capture_summary_layout = QVBoxLayout()
    capture_summary_layout.setContentsMargins(12, 10, 12, 10)
    capture_summary_layout.setSpacing(4)
    capture_summary_label = QLabel("Completa los datos para ver un resumen en vivo.")
    capture_summary_label.setWordWrap(True)
    capture_summary_label.setTextFormat(Qt.TextFormat.RichText)
    capture_summary_label.setObjectName("templatePreviewLabel")
    capture_summary_layout.addWidget(capture_summary_label)
    capture_summary_card.setLayout(capture_summary_layout)
    apply_template_button = QPushButton("Aplicar")
    apply_template_button.setEnabled(False)
    apply_template_button.setToolTip(
        "Aplica los valores visibles de la plantilla al producto base para que revises el resultado antes de guardar."
    )
    apply_base_template_button = QPushButton("Aplicar base")
    apply_base_template_button.setEnabled(False)
    base_template_preview = QLabel("Selecciona una plantilla base para sugerir familia, pieza y descripcion.")
    base_template_preview.setWordWrap(True)
    base_template_preview.setTextFormat(Qt.TextFormat.RichText)
    base_template_preview.setObjectName("templatePreviewLabel")
    apply_context_template_button = QPushButton("Aplicar contexto")
    apply_context_template_button.setEnabled(False)
    context_template_preview = QLabel("Selecciona una plantilla de contexto para sugerir nivel, prenda y escudo.")
    context_template_preview.setWordWrap(True)
    context_template_preview.setTextFormat(Qt.TextFormat.RichText)
    context_template_preview.setObjectName("templatePreviewLabel")
    context_inheritance_hint = QLabel("La herencia desde plantilla base aparecera aqui cuando aplique.")
    context_inheritance_hint.setWordWrap(True)
    context_inheritance_hint.setObjectName("subtleLine")
    apply_presentation_template_button = QPushButton("Aplicar presentaciones")
    apply_presentation_template_button.setEnabled(False)
    presentation_template_preview = QLabel("Selecciona una plantilla de presentaciones para sugerir tallas y colores.")
    presentation_template_preview.setWordWrap(True)
    presentation_template_preview.setTextFormat(Qt.TextFormat.RichText)
    presentation_template_preview.setObjectName("templatePreviewLabel")
    presentation_template_hint = QLabel("Aun no hay una sugerencia automatica para este paso.")
    presentation_template_hint.setWordWrap(True)
    presentation_template_hint.setObjectName("subtleLine")
    template_preview_card = QFrame()
    template_preview_card.setObjectName("infoCard")
    template_preview_layout = QVBoxLayout()
    template_preview_layout.setContentsMargins(12, 10, 12, 10)
    template_preview_layout.setSpacing(4)
    template_preview = QLabel("Selecciona una plantilla para revisar su resumen antes de aplicarla.")
    template_preview.setWordWrap(True)
    template_preview.setTextFormat(Qt.TextFormat.RichText)
    template_preview.setObjectName("templatePreviewLabel")
    template_preview_layout.addWidget(template_preview)
    template_preview_card.setLayout(template_preview_layout)
    template_preview_card.setMinimumHeight(132)
    template_preview_card.setMaximumHeight(180)
    base_template_preview_card = QFrame()
    base_template_preview_card.setObjectName("infoCard")
    base_template_preview_card_layout = QVBoxLayout()
    base_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
    base_template_preview_card_layout.setSpacing(4)
    base_template_preview_card_layout.addWidget(base_template_preview)
    base_template_preview_card.setLayout(base_template_preview_card_layout)
    base_template_preview_card.setMaximumHeight(132)
    context_template_preview_card = QFrame()
    context_template_preview_card.setObjectName("infoCard")
    context_template_preview_card_layout = QVBoxLayout()
    context_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
    context_template_preview_card_layout.setSpacing(4)
    context_template_preview_card_layout.addWidget(context_template_preview)
    context_template_preview_card_layout.addWidget(context_inheritance_hint)
    context_template_preview_card.setLayout(context_template_preview_card_layout)
    context_template_preview_card.setMaximumHeight(132)
    presentation_template_preview_card = QFrame()
    presentation_template_preview_card.setObjectName("infoCard")
    presentation_template_preview_card_layout = QVBoxLayout()
    presentation_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
    presentation_template_preview_card_layout.setSpacing(4)
    presentation_template_preview_card_layout.addWidget(presentation_template_preview)
    presentation_template_preview_card_layout.addWidget(presentation_template_hint)
    presentation_template_preview_card.setLayout(presentation_template_preview_card_layout)
    presentation_template_preview_card.setMaximumHeight(148)
    school_label_widget = QLabel("Escuela")
    garment_label_widget = QLabel("Tipo de uniforme")
    piece_label_widget = QLabel("Tipo pieza")
    attribute_label_widget = QLabel("Atributo")
    level_label_widget = QLabel("Nivel educativo")
    shield_label_widget = QLabel("Escudo")
    location_label_widget = QLabel("Ubicacion")
    all_category_items = list(categorias)
    all_garment_choices = list(tipos_prenda)
    all_piece_choices = list(tipos_pieza)
    all_attribute_choices = list(atributos)
    all_location_choices = list(ubicaciones_disponibles)

    def unique_values(values: list[str]) -> list[str]:
        return [value for value in dict.fromkeys(values) if value]

    def normalize_values(raw_values: object) -> list[str]:
        if not isinstance(raw_values, list):
            return []
        normalized: list[str] = []
        for raw_value in raw_values:
            value = str(raw_value or "").strip()
            if value:
                normalized.append(value)
        return unique_values(normalized)

    def preview_values(values: list[str], *, max_items: int = 6) -> str:
        if not values:
            return "ninguno"
        if len(values) <= max_items:
            return ", ".join(values)
        return f"{', '.join(values[:max_items])} ... (+{len(values) - max_items})"

    def normalize_lookup_text(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
        return "".join(char for char in decomposed if not unicodedata.combining(char))

    def is_placeholder_brand(value: str) -> bool:
        return normalize_lookup_text(value) in {"", "sin marca", "selecciona marca"}

    def select_combo_text(combo: QComboBox, text: str) -> bool:
        normalized_target = normalize_lookup_text(text)
        if not normalized_target:
            return False
        for index in range(combo.count()):
            if normalize_lookup_text(combo.itemText(index)) == normalized_target:
                combo.setCurrentIndex(index)
                return True
        return False

    def set_editable_combo_text(combo: QComboBox, text: str) -> None:
        normalized_text = text.strip()
        if not normalized_text:
            return
        if not select_combo_text(combo, normalized_text):
            combo.setEditText(normalized_text)

    def current_base_template_defaults() -> dict[str, object]:
        template_entry = base_template_combo.currentData()
        if isinstance(template_entry, dict):
            return step_template_defaults("base", template_entry)
        return {}

    def current_template_text(widget: QComboBox) -> str:
        current_entry = widget.currentData()
        if isinstance(current_entry, dict):
            return str(current_entry.get("label") or "").strip()
        return widget.currentText().strip()

    def reset_template_selections(*, keep_global: bool) -> None:
        if not keep_global and template_combo.currentIndex() != 0:
            template_combo.blockSignals(True)
            template_combo.setCurrentIndex(0)
            template_combo.blockSignals(False)
            update_template_preview()
        if base_template_combo.currentIndex() != 0:
            base_template_combo.blockSignals(True)
            base_template_combo.setCurrentIndex(0)
            base_template_combo.blockSignals(False)
            update_base_template_preview()
        if context_template_combo.currentIndex() != 0:
            context_template_combo.blockSignals(True)
            context_template_combo.setCurrentIndex(0)
            context_template_combo.blockSignals(False)
            update_context_template_preview()
        if presentation_template_combo.currentIndex() != 0:
            presentation_template_combo.blockSignals(True)
            presentation_template_combo.setCurrentIndex(0)
            presentation_template_combo.blockSignals(False)
            update_presentation_template_preview()

    def refresh_mode_specific_combo_options(*, clear_uniform_only_fields: bool) -> None:
        mode_view = current_product_mode_view()

        current_category_data = categoria_combo.currentData()
        current_category_text = categoria_combo.currentText().strip()
        categoria_combo.blockSignals(True)
        categoria_combo.clear()
        categoria_combo.addItem("Selecciona categoria", None)
        visible_categories = (
            all_category_items
            if not mode_view.exclude_uniform_category_options
            else [
                (category_id, category_name)
                for category_id, category_name in all_category_items
                if normalize_lookup_text(category_name) not in UNIFORM_CATEGORIES
            ]
        )
        for category_id, category_name in visible_categories:
            categoria_combo.addItem(category_name, category_id)
        if mode_view.exclude_uniform_category_options:
            existing_category_names = {
                normalize_lookup_text(categoria_combo.itemText(index))
                for index in range(categoria_combo.count())
            }
            for suggestion in regular_category_suggestions:
                if normalize_lookup_text(suggestion) not in existing_category_names:
                    categoria_combo.addItem(suggestion, None)
        if mode_view.category_locked:
            ensure_uniform_category()
        elif current_category_data is not None and categoria_combo.findData(current_category_data) >= 0:
            categoria_combo.setCurrentIndex(categoria_combo.findData(current_category_data))
        elif (
            current_category_text
            and not clear_uniform_only_fields
            and normalize_lookup_text(current_category_text) not in UNIFORM_CATEGORIES
                ):
            select_combo_text(categoria_combo, current_category_text)
        categoria_combo.setEditable(not mode_view.category_locked)
        if categoria_combo.isEditable() and categoria_combo.lineEdit() is not None:
            categoria_combo.lineEdit().setPlaceholderText("Selecciona o escribe una categoria")
        categoria_combo.blockSignals(False)

        current_garment_text = tipo_prenda_combo.currentText().strip()
        visible_garments = (
            all_garment_choices
            if not mode_view.exclude_uniform_garment_options
            else [option for option in regular_garment_suggestions if normalize_lookup_text(option) not in UNIFORM_CATEGORIES]
        )
        tipo_prenda_combo.blockSignals(True)
        tipo_prenda_combo.clear()
        tipo_prenda_combo.addItem("")
        tipo_prenda_combo.addItems(visible_garments)
        if current_garment_text:
            normalized_garment = normalize_lookup_text(current_garment_text)
            if not clear_uniform_only_fields or normalized_garment not in UNIFORM_CATEGORIES:
                set_editable_combo_text(tipo_prenda_combo, current_garment_text)
        tipo_prenda_combo.blockSignals(False)

        current_piece_text = tipo_pieza_combo.currentText().strip()
        visible_pieces = all_piece_choices if not mode_view.exclude_uniform_garment_options else regular_piece_suggestions
        tipo_pieza_combo.blockSignals(True)
        tipo_pieza_combo.clear()
        tipo_pieza_combo.addItem("")
        tipo_pieza_combo.addItems(visible_pieces)
        if current_piece_text:
            set_editable_combo_text(tipo_pieza_combo, current_piece_text)
        tipo_pieza_combo.blockSignals(False)

        current_attribute_text = atributo_combo.currentText().strip()
        visible_attributes = all_attribute_choices if not mode_view.exclude_uniform_garment_options else regular_attribute_suggestions
        atributo_combo.blockSignals(True)
        atributo_combo.clear()
        atributo_combo.addItem("")
        atributo_combo.addItems(visible_attributes)
        if current_attribute_text:
            set_editable_combo_text(atributo_combo, current_attribute_text)
        atributo_combo.blockSignals(False)

        current_location_text = ubicacion_input.currentText().strip()
        visible_locations = all_location_choices if not mode_view.exclude_uniform_garment_options else regular_location_suggestions
        ubicacion_input.blockSignals(True)
        ubicacion_input.clear()
        ubicacion_input.addItem("")
        ubicacion_input.addItems(visible_locations)
        if current_location_text:
            set_editable_combo_text(ubicacion_input, current_location_text)
        ubicacion_input.blockSignals(False)

    def merged_context_defaults(template_entry: dict[str, object]) -> dict[str, object]:
        resolved = dict(step_template_defaults("context", template_entry))
        base_defaults = current_base_template_defaults()
        for key in ("garment_type", "piece_type", "attribute", "gender"):
            if not str(resolved.get(key) or "").strip():
                inherited_value = str(base_defaults.get(key) or "").strip()
                if inherited_value:
                    resolved[key] = inherited_value
        return resolved

    current_product_mode = {"key": detect_catalog_product_form_mode(product_initial)}

    def current_product_mode_view():
        return build_catalog_product_form_mode_view(current_product_mode["key"])

    def is_uniform_product_mode() -> bool:
        return current_product_mode["key"] == "uniform"

    def update_context_inheritance_hint() -> None:
        if not current_product_mode_view().context_template_enabled:
            context_inheritance_hint.setText("La herencia escolar no aplica para ropa normal.")
            return
        template_entry = context_template_combo.currentData()
        if not isinstance(template_entry, dict):
            context_inheritance_hint.setText("La herencia desde plantilla base aparecera aqui cuando aplique.")
            return
        base_defaults = current_base_template_defaults()
        inherited_parts: list[str] = []
        for key, label in (("piece_type", "pieza"), ("attribute", "atributo"), ("gender", "genero")):
            context_value = str(template_entry.get(key) or "").strip()
            base_value = str(base_defaults.get(key) or "").strip()
            if not context_value and base_value:
                inherited_parts.append(f"{label}: {base_value}")
        if inherited_parts:
            context_inheritance_hint.setText(
                f"Si aplicas este contexto, heredara desde la plantilla base: {' | '.join(inherited_parts)}."
            )
        else:
            context_inheritance_hint.setText(
                "Este contexto ya trae sus propios datos clave o no necesita herencia adicional."
            )

    def ensure_uniform_category() -> bool:
        if select_combo_text(categoria_combo, "Uniformes"):
            return True
        if window.current_role != RolUsuario.ADMIN:
            return False
        try:
            with get_session() as session:
                user = session.get(Usuario, window.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                categoria = CatalogService.crear_categoria(
                    session,
                    user,
                    "Uniformes",
                    descripcion="Creada desde plantilla: Uniformes.",
                )
                session.commit()
                categoria_id = int(categoria.id)
        except Exception:
            return False
        categoria_combo.addItem("Uniformes", categoria_id)
        categoria_combo.setCurrentIndex(categoria_combo.count() - 1)
        return True

    def apply_product_mode_view(*, clear_uniform_only_fields: bool = False) -> None:
        mode_view = current_product_mode_view()
        refresh_mode_specific_combo_options(clear_uniform_only_fields=clear_uniform_only_fields)
        category_field_stack.setCurrentIndex(0 if mode_view.category_locked else 1)
        if mode_view.category_locked:
            uniform_category_label.setText(mode_view.locked_category_label)
            ensure_uniform_category()
            add_category_button.setEnabled(False)
        else:
            if clear_uniform_only_fields and categoria_combo.currentText().strip() == "Uniformes":
                categoria_combo.setCurrentIndex(0)
            add_category_button.setEnabled(True)
        template_hint.setText(mode_view.base_hint)
        context_hint.setText(mode_view.context_hint)
        school_label_widget.setText(mode_view.school_label)
        garment_label_widget.setText(mode_view.garment_label)
        piece_label_widget.setText(mode_view.piece_label)
        attribute_label_widget.setText(mode_view.attribute_label)
        level_label_widget.setText(mode_view.level_label)
        shield_label_widget.setText(mode_view.shield_label)
        location_label_widget.setText(mode_view.location_label)
        base_templates_panel.setVisible(mode_view.base_templates_visible)
        context_template_panel.setVisible(mode_view.context_templates_visible)
        presentation_template_label_widget.setVisible(mode_view.presentation_templates_visible)
        presentation_template_preview_card.setVisible(mode_view.presentation_templates_visible)
        presentation_template_combo.setVisible(mode_view.presentation_templates_visible)
        apply_presentation_template_button.setVisible(mode_view.presentation_templates_visible)
        school_label_widget.setVisible(mode_view.school_field_visible)
        escuela_combo.setVisible(mode_view.school_field_visible)
        level_label_widget.setVisible(mode_view.level_field_visible)
        nivel_combo.setVisible(mode_view.level_field_visible)
        shield_label_widget.setVisible(mode_view.shield_field_visible)
        escudo_input.setVisible(mode_view.shield_field_visible)
        escuela_combo.setEnabled(mode_view.school_enabled)
        nivel_combo.setEnabled(mode_view.level_enabled)
        escudo_input.setEnabled(mode_view.shield_enabled)
        context_template_combo.setEnabled(mode_view.context_template_enabled)
        apply_context_template_button.setEnabled(
            mode_view.context_template_enabled and isinstance(context_template_combo.currentData(), dict)
        )
        if clear_uniform_only_fields:
            reset_template_selections(keep_global=False)
            if not mode_view.school_enabled:
                escuela_combo.setCurrentIndex(0)
                if escuela_combo.isEditable():
                    escuela_combo.setEditText("")
            if not mode_view.level_enabled:
                nivel_combo.setCurrentIndex(0)
                if nivel_combo.isEditable():
                    nivel_combo.setEditText("")
            if not mode_view.shield_enabled:
                escudo_input.setCurrentIndex(0)
                if escudo_input.isEditable():
                    escudo_input.setEditText("")
        update_context_template_preview()

    def build_suggested_base_name() -> str:
        base_template_entry = base_template_combo.currentData()
        if isinstance(base_template_entry, dict):
            base_template_label = str(base_template_entry.get("label") or "").strip()
            if base_template_label:
                return base_template_label

        template_entry = template_combo.currentData()
        template_name = str(template_entry.get("name") or "").strip() if isinstance(template_entry, dict) else ""
        piece_type = tipo_pieza_combo.currentText().strip()
        garment_type = tipo_prenda_combo.currentText().strip()
        brand = marca_combo.currentText().strip() if marca_combo.currentData() is not None else ""
        if is_placeholder_brand(brand):
            brand = ""
        attribute = atributo_combo.currentText().strip()
        gender = gender_abbreviation(genero_input.currentText()) if genero_input.currentIndex() > 0 else ""
        parts: list[str] = []
        if piece_type:
            parts.append(piece_type)
        elif template_name:
            parts.append(template_name)
        descriptor = attribute or garment_descriptor(piece_type or template_name, garment_type)
        for candidate in (descriptor, brand, gender):
            if candidate and candidate.casefold() not in {part.casefold() for part in parts}:
                parts.append(candidate)
        return " ".join(part for part in parts if part).strip()

    def build_display_name_preview(base_name: str) -> str:
        return build_catalog_product_display_name_preview(
            base_name=base_name,
            context_values=(
                escuela_combo.currentText().strip(),
                tipo_prenda_combo.currentText().strip(),
                tipo_pieza_combo.currentText().strip(),
            ),
        )

    def update_final_name_preview() -> None:
        preview_text = build_display_name_preview(nombre_input.text().strip())
        final_name_preview.setText(
            preview_text
            if preview_text != "Nombre final pendiente."
            else "El nombre completo aparecera arriba en cuanto haya base suficiente."
        )
        live_name_title.setText(
            preview_text if preview_text != "Nombre final pendiente." else "Nombre en construccion"
        )

    def selected_sizes_for_pricing() -> list[str]:
        selected_sizes = variant_sizes_button.selected_labels()
        return selected_sizes or [default_variant_size]

    def current_price_block_definitions() -> list[dict[str, object]]:
        return build_price_blocks(
            {
                "garment_type": tipo_prenda_combo.currentText(),
                "piece_type": tipo_pieza_combo.currentText(),
                "education_level": nivel_combo.currentText(),
                "gender": genero_input.currentText(),
            },
            selected_sizes_for_pricing(),
        )

    def build_price_assignment() -> tuple[dict[str, str], list[str], str]:
        normalized_sizes = selected_sizes_for_pricing()
        mode = str(price_mode_combo.currentData() or "single")
        price_map: dict[str, str] = {}
        missing: list[str] = []
        if mode == "single":
            price_text = variant_price_input.text().strip()
            if not price_text:
                missing.append("precio unico")
            else:
                for size in normalized_sizes:
                    price_map[size] = price_text
            return price_map, missing, f"Precio unico: {price_text or '-'}"
        if mode == "blocks":
            block_values = price_value_store["blocks"]
            assert isinstance(block_values, dict)
            summary_parts: list[str] = []
            for block in current_price_block_definitions():
                block_key = str(block["key"])
                block_label = str(block["label"])
                block_sizes = [str(value) for value in block.get("sizes", [])]
                price_text = str(block_values.get(block_key) or "").strip()
                if not price_text:
                    missing.append(block_label)
                else:
                    for size in block_sizes:
                        price_map[size] = price_text
                summary_parts.append(f"{block_label} ({preview_values(block_sizes, max_items=8)}): {price_text or '-'}")
            return price_map, missing, " | ".join(summary_parts) if summary_parts else "Sin bloques disponibles."
        manual_values = price_value_store["manual"]
        assert isinstance(manual_values, dict)
        summary_parts: list[str] = []
        for size in normalized_sizes:
            price_text = str(manual_values.get(size) or "").strip()
            if not price_text:
                missing.append(size)
            else:
                price_map[size] = price_text
            summary_parts.append(f"{size}: {price_text or '-'}")
        return price_map, missing, " | ".join(summary_parts) if summary_parts else "Sin precios por talla."

    def update_price_inputs_ui() -> None:
        mode = str(price_mode_combo.currentData() or "single")
        if mode == "single":
            configure_prices_button.setText("Capturar precio")
            price_mode_hint.setText("Usa un solo precio para todas las presentaciones y configuralo desde el popup.")
        elif mode == "blocks":
            configure_prices_button.setText("Configurar bloques")
            price_mode_hint.setText(
                "Captura un precio por bloque de tallas desde el popup. Es ideal cuando infantil, numericas o letras cambian de precio."
            )
        else:
            configure_prices_button.setText("Configurar por talla")
            price_mode_hint.setText(
                "Define un precio por talla desde el popup solo cuando haya muchas excepciones."
            )
        price_map, missing_prices, strategy_summary = build_price_assignment()
        missing_label = (
            f"Faltan precios en: {', '.join(missing_prices)}."
            if missing_prices
            else f"Precios listos para {len(price_map)} talla(s)."
        )
        price_strategy_summary.setText(f"{strategy_summary}\n{missing_label}")

    def sync_price_mode_suggestion(*, force: bool = False) -> None:
        suggested_mode = suggest_price_capture_mode(
            {
                "garment_type": tipo_prenda_combo.currentText(),
                "piece_type": tipo_pieza_combo.currentText(),
                "education_level": nivel_combo.currentText(),
                "gender": genero_input.currentText(),
            },
            selected_sizes_for_pricing(),
        )
        if force or not price_mode_state["manual_override"]:
            target_index = price_mode_combo.findData(suggested_mode)
            if target_index >= 0 and price_mode_combo.currentIndex() != target_index:
                price_mode_combo.blockSignals(True)
                price_mode_combo.setCurrentIndex(target_index)
                price_mode_combo.blockSignals(False)
        update_price_inputs_ui()

    def update_capture_summary() -> None:
        final_name = build_display_name_preview(nombre_input.text().strip())
        selected_sizes = variant_sizes_button.selected_labels()
        selected_colors = variant_colors_button.selected_labels()
        total_sizes = max(1, len(selected_sizes))
        total_colors = max(1, len(selected_colors))
        total_variants = total_sizes * total_colors
        price_map, missing_prices, price_summary = build_price_assignment()
        stock_text = str(variant_stock_spin.value())
        sku_summary = window._format_sku_preview(total_variants)
        notes: list[str] = []
        if not nombre_input.text().strip():
            notes.append("Define el nombre base para evitar guardar un producto incompleto.")
        if not selected_sizes:
            notes.append("Sin tallas elegidas: se usara Unitalla si creas el lote.")
        if not selected_colors:
            notes.append("Sin colores elegidos: se usara Sin color si creas el lote.")
        if missing_prices:
            notes.append(
                "Todavia faltan precios para poder crear presentaciones sin correcciones: "
                + ", ".join(missing_prices)
                + "."
            )
        price_strategy_summary.setText(
            f"{price_summary}\n"
            + (
                f"Faltan precios en: {', '.join(missing_prices)}."
                if missing_prices
                else f"Precios listos para {len(price_map)} talla(s)."
            )
        )
        capture_summary_label.setText(
            build_catalog_capture_summary_html(
                final_name=final_name,
                total_variants=total_variants,
                sku_summary=sku_summary,
                variant_examples=build_catalog_variant_examples_preview(
                    sizes=selected_sizes,
                    colors=selected_colors,
                    default_size=default_variant_size,
                    default_color=default_variant_color,
                ),
                price_summary=price_summary,
                stock_text=stock_text,
                notes=notes,
            )
        )

    def update_variant_summary() -> None:
        selected_sizes = variant_sizes_button.selected_labels()
        selected_colors = variant_colors_button.selected_labels()
        variant_sizes_summary.setText(
            f"Tallas elegidas: {preview_values(selected_sizes)}"
            if selected_sizes
            else "Tallas elegidas: ninguna. Si el producto no maneja talla, usaremos Unitalla."
        )
        variant_colors_summary.setText(
            f"Colores elegidos: {preview_values(selected_colors, max_items=5)}"
            if selected_colors
            else "Colores elegidos: ninguno. Si el producto no maneja color, usaremos Sin color."
        )
        total_sizes = max(1, len(selected_sizes))
        total_colors = max(1, len(selected_colors))
        total_variants = total_sizes * total_colors
        variant_count_summary.setText(
            f"Presentaciones previstas: {total_variants}. Se generaran despues de guardar el producto base."
        )
        update_capture_summary()

    auto_name_enabled = {"value": bool(initial is None)}
    last_auto_name = {"value": ""}
    presentation_template_state = {"suggested_label": ""}
    price_mode_state = {"manual_override": False}
    price_value_store: dict[str, dict[str, str] | str] = {"single": "", "blocks": {}, "manual": {}}

    def gender_abbreviation(raw_value: str) -> str:
        mapping = {
            "hombre": "H",
            "mujer": "M",
            "unisex": "U",
            "nino": "N",
            "niño": "N",
            "nina": "N",
            "niña": "N",
        }
        return mapping.get(raw_value.strip().casefold(), raw_value.strip())

    def looks_feminine_piece(raw_value: str) -> bool:
        normalized = normalize_lookup_text(raw_value)
        feminine_terms = ("chamarra", "playera", "blusa", "falda", "malla", "sudadera", "camisa")
        return any(term in normalized for term in feminine_terms)

    def garment_descriptor(piece_value: str, garment_value: str) -> str:
        normalized = normalize_lookup_text(garment_value)
        if not normalized:
            return ""
        if normalized == "deportivo":
            return "deportiva" if looks_feminine_piece(piece_value) else "deportivo"
        if normalized == "basico":
            return "basica" if looks_feminine_piece(piece_value) else "basico"
        if normalized == "accesorio":
            return "escolar"
        return garment_value.strip()

    def sync_name_suggestion(*, force: bool = False) -> None:
        suggested_name = build_suggested_base_name()
        previous_auto = last_auto_name["value"]
        last_auto_name["value"] = suggested_name
        if force or auto_name_enabled["value"] or nombre_input.text().strip() == previous_auto:
            if suggested_name:
                nombre_input.setText(suggested_name)
        update_final_name_preview()

    def handle_name_manual_edit(value: str) -> None:
        normalized_value = value.strip()
        auto_name_enabled["value"] = auto_name_checkbox.isChecked() and normalized_value == last_auto_name["value"]
        if normalized_value and normalized_value != last_auto_name["value"]:
            auto_name_checkbox.setChecked(False)
            auto_name_enabled["value"] = False
        update_final_name_preview()
        update_capture_summary()

    def sync_variant_options(template_entry: dict[str, object] | None, *, apply_defaults: bool) -> None:
        suggested_sizes = normalize_values(template_entry.get("tallas")) if template_entry else []
        suggested_colors = normalize_values(template_entry.get("colores")) if template_entry else []
        available_sizes = merge_choice_lists(
            suggested_sizes,
            legacy_choices.get("TALLAS", []),
            common_sizes,
            [default_variant_size],
        )
        available_colors = merge_choice_lists(
            suggested_colors,
            legacy_choices.get("COLORES", []),
            common_colors,
            [default_variant_color],
        )
        variant_sizes_button.set_items([(value, value) for value in available_sizes])
        variant_colors_button.set_items([(value, value) for value in available_colors])
        if apply_defaults:
            variant_sizes_button.set_selected_values(suggested_sizes)
            variant_colors_button.set_selected_values(suggested_colors)
        update_variant_summary()

    def presentation_template_index_by_label(label: str) -> int:
        normalized = normalize_lookup_text(label)
        if not normalized:
            return -1
        for index in range(presentation_template_combo.count()):
            if normalize_lookup_text(presentation_template_combo.itemText(index)) == normalized:
                return index
        return -1

    def update_presentation_template_suggestion() -> None:
        suggested_label = suggest_presentation_template(
            {
                "garment_type": tipo_prenda_combo.currentText(),
                "piece_type": tipo_pieza_combo.currentText(),
                "education_level": nivel_combo.currentText(),
                "gender": genero_input.currentText(),
            }
        ) or ""
        previous_label = presentation_template_state["suggested_label"]
        current_entry = presentation_template_combo.currentData()
        current_label = str(current_entry.get("label") or "").strip() if isinstance(current_entry, dict) else ""
        if suggested_label:
            presentation_template_hint.setText(
                f"Sugerida por el contexto actual: {suggested_label}. Puedes aplicarla o cambiarla."
            )
        else:
            presentation_template_hint.setText("Aun no hay una sugerencia automatica para este paso.")
        should_sync_selection = not current_label or current_label == previous_label
        presentation_template_state["suggested_label"] = suggested_label
        if should_sync_selection:
            target_index = presentation_template_index_by_label(suggested_label) if suggested_label else 0
            if presentation_template_combo.currentIndex() != target_index:
                presentation_template_combo.blockSignals(True)
                presentation_template_combo.setCurrentIndex(target_index)
                presentation_template_combo.blockSignals(False)
                update_presentation_template_preview()
        sync_price_mode_suggestion()

    sync_variant_options(None, apply_defaults=False)

    def create_inline_category() -> None:
        if window.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(dialog, "Sin permisos", "Solo ADMIN puede crear categorias.")
            return
        name = window._prompt_text_value("Nueva categoria", "Categoria", "Nueva categoria")
        if name is None or not name:
            return
        try:
            with get_session() as session:
                user = session.get(Usuario, window.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                categoria = CatalogService.crear_categoria(session, user, name)
                session.commit()
                categoria_id = int(categoria.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Categoria fallida", str(exc))
            return
        categoria_combo.addItem(name, categoria_id)
        categoria_combo.setCurrentIndex(categoria_combo.count() - 1)

    def create_inline_brand() -> None:
        if window.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(dialog, "Sin permisos", "Solo ADMIN puede crear marcas.")
            return
        name = window._prompt_text_value("Nueva marca", "Marca", "Nueva marca")
        if name is None or not name:
            return
        try:
            with get_session() as session:
                user = session.get(Usuario, window.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                marca = CatalogService.crear_marca(session, user, name)
                session.commit()
                marca_id = int(marca.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Marca fallida", str(exc))
            return
        marca_combo.addItem(name, marca_id)
        marca_combo.setCurrentIndex(marca_combo.count() - 1)

    add_category_button.clicked.connect(create_inline_category)
    add_brand_button.clicked.connect(create_inline_brand)

    def update_template_preview() -> None:
        template_entry = template_combo.currentData()
        if not isinstance(template_entry, dict):
            apply_template_button.setEnabled(False)
            template_preview.setText("Selecciona una plantilla para revisar su resumen antes de aplicarla.")
            sync_variant_options(None, apply_defaults=False)
            return
        apply_template_button.setEnabled(True)
        template_preview.setText(build_product_template_preview(template_entry))
        sync_variant_options(template_entry, apply_defaults=False)

    def apply_selected_template() -> None:
        template_entry = template_combo.currentData()
        if not isinstance(template_entry, dict):
            return
        defaults = product_template_defaults(template_entry)
        category_name = defaults["category"]
        if category_name:
            if is_uniform_product_mode():
                ensure_uniform_category()
            else:
                select_combo_text(categoria_combo, category_name)
        brand_name = defaults["brand"]
        if brand_name and not is_placeholder_brand(brand_name):
            select_combo_text(marca_combo, brand_name)
        if defaults["name"]:
            nombre_input.setText(defaults["name"])
        if defaults["description"]:
            descripcion_input.setPlainText(defaults["description"])
        if defaults["school"]:
            set_editable_combo_text(escuela_combo, defaults["school"])
        if defaults["garment_type"]:
            set_editable_combo_text(tipo_prenda_combo, defaults["garment_type"])
        if defaults["piece_type"]:
            set_editable_combo_text(tipo_pieza_combo, defaults["piece_type"])
        if defaults["attribute"]:
            set_editable_combo_text(atributo_combo, defaults["attribute"])
        if defaults["education_level"]:
            set_editable_combo_text(nivel_combo, defaults["education_level"])
        if defaults["gender"]:
            set_editable_combo_text(genero_input, defaults["gender"])
        if defaults["shield"]:
            set_editable_combo_text(escudo_input, defaults["shield"])
        if defaults["location"]:
            set_editable_combo_text(ubicacion_input, defaults["location"])
        if str(template_entry.get("precio") or "").strip():
            variant_price_input.setText(str(template_entry.get("precio") or "").strip())
            price_mode_state["manual_override"] = False
            target_index = price_mode_combo.findData("single")
            if target_index >= 0:
                price_mode_combo.setCurrentIndex(target_index)
        sync_variant_options(template_entry, apply_defaults=True)
        sync_price_mode_suggestion(force=bool(template_entry.get("precio")))
        if auto_name_checkbox.isChecked():
            sync_name_suggestion(force=True)

    def update_base_template_preview() -> None:
        template_entry = base_template_combo.currentData()
        if not isinstance(template_entry, dict):
            apply_base_template_button.setEnabled(False)
            base_template_preview.setText("Selecciona una plantilla base para sugerir familia, pieza y descripcion.")
            update_context_inheritance_hint()
            return
        apply_base_template_button.setEnabled(True)
        base_template_preview.setText(build_step_template_preview("base", template_entry))
        update_context_inheritance_hint()

    def apply_base_step_template() -> None:
        template_entry = base_template_combo.currentData()
        if not isinstance(template_entry, dict):
            return
        defaults = step_template_defaults("base", template_entry)
        if is_uniform_product_mode():
            ensure_uniform_category()
        if defaults.get("garment_type"):
            set_editable_combo_text(tipo_prenda_combo, str(defaults["garment_type"]))
        if defaults.get("piece_type"):
            set_editable_combo_text(tipo_pieza_combo, str(defaults["piece_type"]))
        if defaults.get("attribute"):
            set_editable_combo_text(atributo_combo, str(defaults["attribute"]))
        if defaults.get("gender"):
            set_editable_combo_text(genero_input, str(defaults["gender"]))
        if defaults.get("description"):
            descripcion_input.setPlainText(str(defaults["description"]))
        if auto_name_checkbox.isChecked():
            sync_name_suggestion(force=True)
        elif defaults.get("name") and not nombre_input.text().strip():
            nombre_input.setText(str(defaults["name"]))
            update_final_name_preview()
            update_capture_summary()
        update_review_details()

    def update_context_template_preview() -> None:
        template_entry = context_template_combo.currentData()
        mode_view = current_product_mode_view()
        if not mode_view.context_template_enabled or not isinstance(template_entry, dict):
            apply_context_template_button.setEnabled(False)
            context_template_preview.setText(mode_view.template_context_hint)
            update_context_inheritance_hint()
            return
        apply_context_template_button.setEnabled(True)
        context_template_preview.setText(build_step_template_preview("context", template_entry))
        update_context_inheritance_hint()

    def apply_context_step_template() -> None:
        template_entry = context_template_combo.currentData()
        if not isinstance(template_entry, dict):
            return
        defaults = merged_context_defaults(template_entry)
        if is_uniform_product_mode():
            ensure_uniform_category()
        if defaults.get("garment_type"):
            set_editable_combo_text(tipo_prenda_combo, str(defaults["garment_type"]))
        if defaults.get("piece_type"):
            set_editable_combo_text(tipo_pieza_combo, str(defaults["piece_type"]))
        if defaults.get("attribute"):
            set_editable_combo_text(atributo_combo, str(defaults["attribute"]))
        if defaults.get("education_level"):
            set_editable_combo_text(nivel_combo, str(defaults["education_level"]))
        if defaults.get("gender"):
            set_editable_combo_text(genero_input, str(defaults["gender"]))
        if defaults.get("shield"):
            set_editable_combo_text(escudo_input, str(defaults["shield"]))
        if defaults.get("location"):
            set_editable_combo_text(ubicacion_input, str(defaults["location"]))
        if auto_name_checkbox.isChecked():
            sync_name_suggestion(force=True)
        update_capture_summary()
        update_review_details()
        update_context_inheritance_hint()

    def update_presentation_template_preview() -> None:
        template_entry = presentation_template_combo.currentData()
        if not isinstance(template_entry, dict):
            apply_presentation_template_button.setEnabled(False)
            presentation_template_preview.setText("Selecciona una plantilla de presentaciones para sugerir tallas y colores.")
            return
        apply_presentation_template_button.setEnabled(True)
        presentation_template_preview.setText(build_step_template_preview("presentation", template_entry))

    def apply_presentation_step_template() -> None:
        template_entry = presentation_template_combo.currentData()
        if not isinstance(template_entry, dict):
            return
        defaults = step_template_defaults("presentation", template_entry)
        variant_sizes_button.set_selected_values(list(defaults.get("sizes", [])))
        variant_colors_button.set_selected_values(list(defaults.get("colors", [])))
        if defaults.get("price"):
            variant_price_input.setText(str(defaults["price"]))
            price_mode_state["manual_override"] = False
            target_index = price_mode_combo.findData("single")
            if target_index >= 0:
                price_mode_combo.setCurrentIndex(target_index)
        if defaults.get("stock"):
            variant_stock_spin.setValue(int(defaults["stock"]))
        sync_price_mode_suggestion(force=not bool(defaults.get("price")))
        update_capture_summary()
        update_review_details()

    def open_price_configuration_dialog() -> None:
        mode = str(price_mode_combo.currentData() or "single")
        temp_single_price = variant_price_input.text().strip()
        temp_blocks = dict(price_value_store["blocks"]) if isinstance(price_value_store["blocks"], dict) else {}
        temp_manual = dict(price_value_store["manual"]) if isinstance(price_value_store["manual"], dict) else {}

        pricing_dialog, pricing_layout = window._create_modal_dialog(
            "Configurar precios",
            "Captura la estructura de precios sin saturar el formulario principal.",
            width=640,
        )
        context_label = QLabel(
            f"Modo actual: {price_mode_combo.currentText()} | Tallas: {preview_values(selected_sizes_for_pricing(), max_items=10)}"
        )
        context_label.setWordWrap(True)
        context_label.setObjectName("subtleLine")
        pricing_layout.addWidget(context_label)

        if mode == "single":
            editor_form = QFormLayout()
            single_input = QLineEdit(temp_single_price)
            single_input.setPlaceholderText("Ej. 199.00")
            helper_label = QLabel("Este precio se aplicara a todas las tallas seleccionadas.")
            helper_label.setWordWrap(True)
            helper_label.setObjectName("subtleLine")
            editor_form.addRow("Precio unico", single_input)
            editor_form.addRow("", helper_label)
            pricing_layout.addLayout(editor_form)
        else:
            editor_scroll = QScrollArea()
            editor_scroll.setWidgetResizable(True)
            editor_container = QWidget()
            editor_container_layout = QVBoxLayout()
            editor_container_layout.setContentsMargins(0, 0, 0, 0)
            editor_container_layout.setSpacing(8)
            editor_inputs: dict[str, QLineEdit] = {}
            if mode == "blocks":
                for block in current_price_block_definitions():
                    block_key = str(block["key"])
                    block_label = str(block["label"])
                    block_sizes = [str(value) for value in block.get("sizes", [])]
                    row_box = QFrame()
                    row_box.setObjectName("infoCard")
                    row_layout = QVBoxLayout()
                    row_layout.setContentsMargins(10, 10, 10, 10)
                    row_layout.setSpacing(4)
                    title_label = QLabel(block_label)
                    title_label.setObjectName("tableSectionTitle")
                    price_input = QLineEdit(str(temp_blocks.get(block_key) or ""))
                    price_input.setPlaceholderText("Ej. 199.00")
                    sizes_label = QLabel(f"Tallas: {preview_values(block_sizes, max_items=10)}")
                    sizes_label.setWordWrap(True)
                    sizes_label.setObjectName("subtleLine")
                    row_layout.addWidget(title_label)
                    row_layout.addWidget(price_input)
                    row_layout.addWidget(sizes_label)
                    row_box.setLayout(row_layout)
                    editor_container_layout.addWidget(row_box)
                    editor_inputs[block_key] = price_input
            else:
                for size in selected_sizes_for_pricing():
                    row_box = QFrame()
                    row_box.setObjectName("infoCard")
                    row_layout = QVBoxLayout()
                    row_layout.setContentsMargins(10, 10, 10, 10)
                    row_layout.setSpacing(4)
                    title_label = QLabel(f"Talla {size}")
                    title_label.setObjectName("tableSectionTitle")
                    price_input = QLineEdit(str(temp_manual.get(size) or ""))
                    price_input.setPlaceholderText("Ej. 199.00")
                    row_layout.addWidget(title_label)
                    row_layout.addWidget(price_input)
                    row_box.setLayout(row_layout)
                    editor_container_layout.addWidget(row_box)
                    editor_inputs[size] = price_input
            editor_container_layout.addStretch(1)
            editor_container.setLayout(editor_container_layout)
            editor_scroll.setWidget(editor_container)
            pricing_layout.addWidget(editor_scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(pricing_dialog.accept)
        buttons.rejected.connect(pricing_dialog.reject)
        pricing_layout.addWidget(buttons)
        if pricing_dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        if mode == "single":
            variant_price_input.setText(single_input.text().strip())
        elif mode == "blocks":
            price_value_store["blocks"] = {key: input_widget.text().strip() for key, input_widget in editor_inputs.items()}
        else:
            price_value_store["manual"] = {key: input_widget.text().strip() for key, input_widget in editor_inputs.items()}
        update_capture_summary()
        update_review_details()

    template_combo.currentIndexChanged.connect(lambda _: update_template_preview())
    apply_template_button.clicked.connect(apply_selected_template)
    base_template_combo.currentIndexChanged.connect(lambda _: update_base_template_preview())
    apply_base_template_button.clicked.connect(apply_base_step_template)
    context_template_combo.currentIndexChanged.connect(lambda _: update_context_template_preview())
    apply_context_template_button.clicked.connect(apply_context_step_template)
    presentation_template_combo.currentIndexChanged.connect(lambda _: update_presentation_template_preview())
    apply_presentation_template_button.clicked.connect(apply_presentation_step_template)
    variant_sizes_button.selectionChanged.connect(lambda: (update_variant_summary(), sync_price_mode_suggestion()))
    variant_colors_button.selectionChanged.connect(update_variant_summary)
    auto_name_checkbox.toggled.connect(
        lambda checked: (auto_name_enabled.__setitem__("value", bool(checked)), sync_name_suggestion(force=bool(checked)))
    )
    generate_name_button.clicked.connect(lambda: sync_name_suggestion(force=True))
    nombre_input.textEdited.connect(handle_name_manual_edit)
    marca_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
    tipo_pieza_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
    atributo_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
    genero_input.currentTextChanged.connect(lambda _: sync_name_suggestion())
    escuela_combo.currentTextChanged.connect(lambda _: (update_final_name_preview(), update_capture_summary()))
    tipo_prenda_combo.currentTextChanged.connect(
        lambda _: (update_final_name_preview(), update_capture_summary(), update_presentation_template_suggestion(), sync_price_mode_suggestion())
    )
    tipo_pieza_combo.currentTextChanged.connect(
        lambda _: (update_final_name_preview(), update_capture_summary(), update_presentation_template_suggestion(), sync_price_mode_suggestion())
    )
    nivel_combo.currentTextChanged.connect(lambda _: (update_presentation_template_suggestion(), sync_price_mode_suggestion()))
    genero_input.currentTextChanged.connect(lambda _: (update_presentation_template_suggestion(), sync_price_mode_suggestion()))
    price_mode_combo.currentIndexChanged.connect(
        lambda _: (
            price_mode_state.__setitem__("manual_override", True),
            update_price_inputs_ui(),
            update_capture_summary(),
        )
    )
    configure_prices_button.clicked.connect(open_price_configuration_dialog)
    variant_price_input.textChanged.connect(lambda _: update_capture_summary())
    variant_stock_spin.valueChanged.connect(lambda _: update_capture_summary())

    if product_initial:
        window._set_combo_value(categoria_combo, product_initial["categoria_id"])
        window._set_combo_value(marca_combo, product_initial["marca_id"])
        nombre_input.setText(str(product_initial["nombre_base"]))
        descripcion_input.setPlainText(str(product_initial["descripcion"]))
        set_editable_combo_text(escuela_combo, str(product_initial["escuela"]))
        set_editable_combo_text(tipo_prenda_combo, str(product_initial["tipo_prenda"]))
        set_editable_combo_text(tipo_pieza_combo, str(product_initial["tipo_pieza"]))
        set_editable_combo_text(atributo_combo, str(product_initial["atributo"]))
        set_editable_combo_text(nivel_combo, str(product_initial["nivel_educativo"]))
        set_editable_combo_text(genero_input, str(product_initial["genero"]))
        set_editable_combo_text(escudo_input, str(product_initial["escudo"]))
        set_editable_combo_text(ubicacion_input, str(product_initial["ubicacion"]))
        auto_name_checkbox.setChecked(False)
        auto_name_enabled["value"] = False

    sync_name_suggestion(force=bool(initial is None and not nombre_input.text().strip()))
    update_final_name_preview()
    update_capture_summary()
    update_context_inheritance_hint()
    update_presentation_template_suggestion()
    sync_price_mode_suggestion(force=True)

    template_row = QHBoxLayout()
    template_row.setSpacing(10)
    template_row.addWidget(template_combo, 1)
    template_row.addWidget(apply_template_button)
    base_template_row = QHBoxLayout()
    base_template_row.setSpacing(10)
    base_template_row.addWidget(base_template_combo, 1)
    base_template_row.addWidget(apply_base_template_button)
    context_template_row = QHBoxLayout()
    context_template_row.setSpacing(10)
    context_template_row.addWidget(context_template_combo, 1)
    context_template_row.addWidget(apply_context_template_button)
    presentation_template_row = QHBoxLayout()
    presentation_template_row.setSpacing(10)
    presentation_template_row.addWidget(presentation_template_combo, 1)
    presentation_template_row.addWidget(apply_presentation_template_button)
    presentation_template_label_widget = QLabel("Plantilla present.")
    marca_row = QHBoxLayout()
    marca_row.setSpacing(10)
    marca_row.addWidget(marca_combo)
    marca_row.addWidget(add_brand_button)
    name_row = QHBoxLayout()
    name_row.setSpacing(10)
    name_row.addWidget(nombre_input, 1)
    name_row.addWidget(auto_name_checkbox)
    name_row.addWidget(generate_name_button)
    template_box = QGroupBox("Paso 1 · Base")
    template_box.setObjectName("infoCard")
    template_box_layout = QVBoxLayout()
    template_box_layout.setContentsMargins(16, 18, 16, 16)
    template_box_layout.setSpacing(14)
    template_hint = QLabel("Empieza por plantilla, marca y nombre base. La categoria se maneja internamente como Uniformes.")
    template_hint.setWordWrap(True)
    template_hint.setObjectName("subtleLine")
    base_templates_panel = QFrame()
    base_templates_panel.setObjectName("infoCard")
    base_templates_layout = QFormLayout()
    base_templates_layout.setContentsMargins(14, 14, 14, 14)
    base_templates_layout.setSpacing(10)
    base_templates_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    base_templates_layout.addRow("Plantilla global", template_row)
    base_templates_layout.addRow("Vista global", template_preview_card)
    base_templates_layout.addRow("Plantilla base", base_template_row)
    base_templates_layout.addRow("Resumen base", base_template_preview_card)
    base_templates_panel.setLayout(base_templates_layout)
    base_fields_panel = QFrame()
    base_fields_panel.setObjectName("infoCard")
    base_fields_layout = QGridLayout()
    base_fields_layout.setContentsMargins(14, 14, 14, 14)
    base_fields_layout.setHorizontalSpacing(12)
    base_fields_layout.setVerticalSpacing(10)
    base_fields_layout.addWidget(product_mode_label, 0, 0)
    base_fields_layout.addWidget(product_mode_combo, 0, 1)
    base_fields_layout.addWidget(category_mode_label, 0, 2)
    base_fields_layout.addWidget(category_field_stack, 0, 3)
    base_fields_layout.addWidget(QLabel("Marca"), 1, 0)
    base_fields_layout.addLayout(marca_row, 1, 1, 1, 3)
    base_fields_layout.addWidget(QLabel("Nombre base"), 2, 0)
    base_fields_layout.addLayout(name_row, 2, 1, 1, 3)
    base_fields_layout.addWidget(QLabel("Descripcion"), 3, 0)
    base_fields_layout.addWidget(descripcion_input, 3, 1, 1, 3)
    base_fields_layout.addWidget(final_name_preview, 4, 0, 1, 4)
    base_fields_layout.setColumnStretch(1, 3)
    base_fields_layout.setColumnStretch(3, 3)
    base_fields_panel.setLayout(base_fields_layout)
    base_content_row = QHBoxLayout()
    base_content_row.setSpacing(14)
    base_content_row.addWidget(base_templates_panel, 5)
    base_content_row.addWidget(base_fields_panel, 6)
    template_box_layout.addWidget(template_hint)
    template_box_layout.addLayout(base_content_row)
    template_box_layout.addStretch(1)
    template_box.setLayout(template_box_layout)

    context_box = QGroupBox("Paso 2 · Contexto")
    context_box.setObjectName("infoCard")
    context_layout = QVBoxLayout()
    context_layout.setContentsMargins(16, 18, 16, 16)
    context_layout.setSpacing(14)
    context_hint = QLabel("Define el contexto escolar del producto. Aqui decides tipo de uniforme, nivel, pieza y detalles.")
    context_hint.setWordWrap(True)
    context_hint.setObjectName("subtleLine")
    context_template_panel = QFrame()
    context_template_panel.setObjectName("infoCard")
    context_template_layout = QFormLayout()
    context_template_layout.setContentsMargins(14, 14, 14, 14)
    context_template_layout.setSpacing(10)
    context_template_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    context_template_layout.addRow("Plantilla contexto", context_template_row)
    context_template_layout.addRow("Resumen contexto", context_template_preview_card)
    context_template_panel.setLayout(context_template_layout)
    context_fields_panel = QFrame()
    context_fields_panel.setObjectName("infoCard")
    context_fields_layout = QGridLayout()
    context_fields_layout.setContentsMargins(14, 14, 14, 14)
    context_fields_layout.setHorizontalSpacing(12)
    context_fields_layout.setVerticalSpacing(10)
    context_fields_layout.addWidget(school_label_widget, 0, 0)
    context_fields_layout.addWidget(escuela_combo, 0, 1, 1, 3)
    context_fields_layout.addWidget(garment_label_widget, 1, 0)
    context_fields_layout.addWidget(tipo_prenda_combo, 1, 1)
    context_fields_layout.addWidget(piece_label_widget, 1, 2)
    context_fields_layout.addWidget(tipo_pieza_combo, 1, 3)
    context_fields_layout.addWidget(attribute_label_widget, 2, 0)
    context_fields_layout.addWidget(atributo_combo, 2, 1)
    context_fields_layout.addWidget(level_label_widget, 2, 2)
    context_fields_layout.addWidget(nivel_combo, 2, 3)
    context_fields_layout.addWidget(QLabel("Genero"), 3, 0)
    context_fields_layout.addWidget(genero_input, 3, 1)
    context_fields_layout.addWidget(shield_label_widget, 3, 2)
    context_fields_layout.addWidget(escudo_input, 3, 3)
    context_fields_layout.addWidget(location_label_widget, 4, 0)
    context_fields_layout.addWidget(ubicacion_input, 4, 1)
    context_fields_layout.setColumnStretch(1, 3)
    context_fields_layout.setColumnStretch(3, 3)
    context_fields_panel.setLayout(context_fields_layout)
    context_content_row = QHBoxLayout()
    context_content_row.setSpacing(14)
    context_content_row.addWidget(context_template_panel, 4)
    context_content_row.addWidget(context_fields_panel, 7)
    context_layout.addWidget(context_hint)
    context_layout.addLayout(context_content_row)
    context_layout.addStretch(1)
    context_box.setLayout(context_layout)

    variants_box = QGroupBox("Paso 3 · Presentaciones")
    variants_box.setObjectName("infoCard")
    variants_layout = QGridLayout()
    variants_layout.setContentsMargins(16, 18, 16, 16)
    variants_layout.setHorizontalSpacing(12)
    variants_layout.setVerticalSpacing(10)
    variants_hint = QLabel("Define tallas, colores y precio. Aqui decides si el producto creara presentaciones por lote despues de guardar.")
    variants_hint.setWordWrap(True)
    variants_hint.setObjectName("subtleLine")
    variants_layout.addWidget(variants_hint, 0, 0, 1, 4)
    variants_layout.addWidget(presentation_template_label_widget, 1, 0)
    variants_layout.addLayout(presentation_template_row, 1, 1, 1, 3)
    variants_layout.addWidget(presentation_template_preview_card, 2, 0, 1, 4)
    variants_layout.addWidget(QLabel("Tallas"), 3, 0)
    variants_layout.addWidget(variant_sizes_button, 3, 1)
    variants_layout.addWidget(QLabel("Colores"), 3, 2)
    variants_layout.addWidget(variant_colors_button, 3, 3)
    variants_layout.addWidget(variant_sizes_summary, 4, 0, 1, 2)
    variants_layout.addWidget(variant_colors_summary, 4, 2, 1, 2)
    variants_layout.addWidget(QLabel("Modo precio"), 5, 0)
    variants_layout.addWidget(price_mode_combo, 5, 1, 1, 2)
    variants_layout.addWidget(configure_prices_button, 5, 3)
    variants_layout.addWidget(price_mode_hint, 6, 0, 1, 4)
    variants_layout.addWidget(price_strategy_summary, 7, 0, 1, 4)
    variants_layout.addWidget(QLabel("Costo ref."), 8, 0)
    variants_layout.addWidget(variant_cost_input, 8, 1)
    variants_layout.addWidget(QLabel("Stock inicial"), 8, 2)
    variants_layout.addWidget(variant_stock_spin, 8, 3)
    variants_layout.addWidget(variant_count_summary, 9, 0, 1, 4)
    variants_box.setLayout(variants_layout)

    review_box = QGroupBox("Paso 4 · Revisar")
    review_box.setObjectName("infoCard")
    review_layout = QVBoxLayout()
    review_layout.setContentsMargins(16, 18, 16, 16)
    review_layout.setSpacing(10)
    review_hint = QLabel("Revisa el resumen final. Si algo no cuadra, vuelve al paso correspondiente antes de guardar.")
    review_hint.setWordWrap(True)
    review_hint.setObjectName("subtleLine")
    review_details_label = QLabel("Aun no hay suficiente informacion para revisar.")
    review_details_label.setWordWrap(True)
    review_details_label.setTextFormat(Qt.TextFormat.RichText)
    review_details_label.setObjectName("templatePreviewLabel")
    review_layout.addWidget(review_hint)
    review_layout.addWidget(review_details_label)
    review_layout.addStretch(1)
    review_box.setLayout(review_layout)

    def update_review_details() -> None:
        mode_view = current_product_mode_view()
        selected_sizes = variant_sizes_button.selected_labels()
        selected_colors = variant_colors_button.selected_labels()
        _, missing_prices, price_summary = build_price_assignment()
        total_variants = max(1, len(selected_sizes) or 1) * max(1, len(selected_colors) or 1)
        sku_summary = window._format_sku_preview(total_variants)
        review_notes: list[str] = []
        validation_feedback = validate_catalog_product_submission(
            build_catalog_product_dialog_payload(
                mode_key=current_product_mode["key"],
                category_id=categoria_combo.currentData(),
                category_name=categoria_combo.currentText(),
                brand_id=marca_combo.currentData(),
                base_name=nombre_input.text(),
                school=escuela_combo.currentText(),
                garment_type=tipo_prenda_combo.currentText(),
                piece_type=tipo_pieza_combo.currentText(),
                attribute=atributo_combo.currentText(),
                education_level=nivel_combo.currentText(),
                gender=genero_input.currentText(),
                shield=escudo_input.currentText(),
                location=ubicacion_input.currentText(),
                description=descripcion_input.toPlainText(),
                sizes=selected_sizes,
                colors=selected_colors,
                variant_price=variant_price_input.text(),
                price_mode=str(price_mode_combo.currentData() or "single"),
                prices_by_size=build_price_assignment()[0],
                price_summary=price_summary,
                variant_cost=variant_cost_input.text(),
                initial_stock=variant_stock_spin.value(),
            )
        )
        if validation_feedback is not None:
            review_notes.append(validation_feedback)
        if missing_prices:
            review_notes.append("Hay precios pendientes en: " + ", ".join(missing_prices) + ".")
        category_label_text = (
            mode_view.locked_category_label if mode_view.category_locked else (categoria_combo.currentText().strip() or "-")
        )
        context_values = (
            escuela_combo.currentText().strip() if mode_view.school_enabled else "",
            tipo_prenda_combo.currentText().strip(),
            tipo_pieza_combo.currentText().strip(),
            atributo_combo.currentText().strip(),
            nivel_combo.currentText().strip() if mode_view.level_enabled else "",
            escudo_input.currentText().strip() if mode_view.shield_enabled else "",
            ubicacion_input.currentText().strip(),
        )
        review_details_label.setText(
            build_catalog_review_details_html(
                product_name=build_display_name_preview(nombre_input.text().strip()),
                category_label=category_label_text,
                brand_label=marca_combo.currentText().strip() or "-",
                context_values=context_values,
                context_empty_label=mode_view.review_context_empty_label,
                sizes_preview=preview_values(selected_sizes),
                colors_preview=preview_values(selected_colors, max_items=5),
                sku_summary=sku_summary,
                price_summary=price_summary,
                stock_value=variant_stock_spin.value(),
                review_notes=review_notes,
            )
        )

    window._set_combo_value(product_mode_combo, current_product_mode["key"])
    apply_product_mode_view(clear_uniform_only_fields=False)
    if is_uniform_product_mode():
        ensure_uniform_category()
    update_final_name_preview()
    update_capture_summary()
    update_context_inheritance_hint()
    update_presentation_template_suggestion()
    sync_price_mode_suggestion(force=True)
    product_mode_combo.currentIndexChanged.connect(
        lambda _: (
            current_product_mode.__setitem__("key", str(product_mode_combo.currentData() or "uniform")),
            apply_product_mode_view(clear_uniform_only_fields=True),
            update_final_name_preview(),
            update_capture_summary(),
            update_review_details(),
        )
    )

    step_stack = QStackedWidget()
    step_titles = ["1 Base", "2 Contexto", "3 Presentaciones", "4 Revisar"]
    for box in (template_box, context_box, variants_box, review_box):
        page = QWidget()
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(box)
        page.setLayout(page_layout)
        step_stack.addWidget(page)

    summary_box = QGroupBox("Resumen")
    summary_box.setObjectName("infoCard")
    summary_box.setMinimumWidth(300)
    summary_box.setMaximumWidth(360)
    summary_layout = QVBoxLayout()
    summary_layout.setContentsMargins(16, 18, 16, 16)
    summary_layout.setSpacing(10)
    summary_hint = QLabel("Este panel se actualiza en tiempo real mientras avanzas por los pasos.")
    summary_hint.setWordWrap(True)
    summary_hint.setObjectName("subtleLine")
    summary_layout.addWidget(summary_hint)
    summary_layout.addWidget(capture_summary_card)
    summary_layout.addStretch(1)
    summary_box.setLayout(summary_layout)

    step_buttons: list[QPushButton] = []
    stepper_row = QHBoxLayout()
    stepper_row.setSpacing(8)
    current_step = {"index": 0}

    def validate_step(step_index: int) -> bool:
        if step_index == 0:
            feedback = validate_catalog_product_submission(
                build_catalog_product_dialog_payload(
                    mode_key=current_product_mode["key"],
                    category_id=categoria_combo.currentData(),
                    category_name=categoria_combo.currentText(),
                    brand_id=marca_combo.currentData(),
                    base_name=nombre_input.text(),
                    school=escuela_combo.currentText(),
                    garment_type=tipo_prenda_combo.currentText(),
                    piece_type=tipo_pieza_combo.currentText(),
                    attribute=atributo_combo.currentText(),
                    education_level=nivel_combo.currentText(),
                    gender=genero_input.currentText(),
                    shield=escudo_input.currentText(),
                    location=ubicacion_input.currentText(),
                    description=descripcion_input.toPlainText(),
                    sizes=variant_sizes_button.selected_labels(),
                    colors=variant_colors_button.selected_labels(),
                    variant_price=variant_price_input.text(),
                    price_mode=str(price_mode_combo.currentData() or "single"),
                    prices_by_size=build_price_assignment()[0],
                    price_summary=build_price_assignment()[2],
                    variant_cost=variant_cost_input.text(),
                    initial_stock=variant_stock_spin.value(),
                )
            )
            if feedback is not None:
                QMessageBox.warning(dialog, "Paso 1 incompleto", feedback)
                return False
        if step_index == 2:
            has_variant_intent = bool(variant_sizes_button.selected_labels() or variant_colors_button.selected_labels())
            _, missing_prices, _ = build_price_assignment()
            feedback = validate_catalog_product_presentations_step(
                has_variant_intent=has_variant_intent,
                missing_prices=missing_prices,
            )
            if feedback is not None:
                QMessageBox.warning(dialog, "Paso 3 incompleto", feedback)
                return False
        return True

    def refresh_step_ui() -> None:
        for index, button in enumerate(step_buttons):
            is_active = index == current_step["index"]
            button.setProperty("active", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        previous_button.setEnabled(current_step["index"] > 0)
        next_button.setVisible(current_step["index"] < len(step_titles) - 1)
        save_button.setVisible(current_step["index"] == len(step_titles) - 1)
        step_stack.setCurrentIndex(current_step["index"])
        update_review_details()

    def go_to_step(target_index: int) -> None:
        if target_index > current_step["index"] and not validate_step(current_step["index"]):
            return
        current_step["index"] = max(0, min(target_index, len(step_titles) - 1))
        refresh_step_ui()

    for index, title in enumerate(step_titles):
        button = QPushButton(title)
        button.setObjectName("stepButton")
        button.clicked.connect(lambda _checked=False, target=index: go_to_step(target))
        step_buttons.append(button)
        stepper_row.addWidget(button)
    stepper_row.addStretch(1)

    main_content_row = QHBoxLayout()
    main_content_row.setSpacing(14)
    main_content_row.addWidget(step_stack, 7)
    main_content_row.addWidget(summary_box, 4)

    navigation_row = QHBoxLayout()
    navigation_row.setSpacing(10)
    previous_button = QPushButton("Anterior")
    next_button = QPushButton("Siguiente")
    save_button = QPushButton("Guardar")
    cancel_button = QPushButton("Cancelar")
    previous_button.clicked.connect(lambda: go_to_step(current_step["index"] - 1))
    next_button.clicked.connect(lambda: go_to_step(current_step["index"] + 1))
    save_button.clicked.connect(lambda: dialog.accept() if validate_step(0) and validate_step(2) else None)
    cancel_button.clicked.connect(dialog.reject)
    navigation_row.addWidget(previous_button)
    navigation_row.addWidget(next_button)
    navigation_row.addStretch(1)
    navigation_row.addWidget(cancel_button)
    navigation_row.addWidget(save_button)

    refresh_step_ui()
    layout.addWidget(live_name_card)
    layout.addLayout(stepper_row)
    layout.addLayout(main_content_row)
    layout.addLayout(navigation_row)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    prices_by_size, _, price_summary = build_price_assignment()
    return build_catalog_product_dialog_payload(
        mode_key=current_product_mode["key"],
        category_id=categoria_combo.currentData(),
        category_name=categoria_combo.currentText(),
        brand_id=marca_combo.currentData(),
        base_name=nombre_input.text(),
        school=escuela_combo.currentText(),
        garment_type=tipo_prenda_combo.currentText(),
        piece_type=tipo_pieza_combo.currentText(),
        attribute=atributo_combo.currentText(),
        education_level=nivel_combo.currentText(),
        gender=genero_input.currentText(),
        shield=escudo_input.currentText(),
        location=ubicacion_input.currentText(),
        description=descripcion_input.toPlainText(),
        sizes=variant_sizes_button.selected_labels(),
        colors=variant_colors_button.selected_labels(),
        variant_price=variant_price_input.text(),
        price_mode=str(price_mode_combo.currentData() or "single"),
        prices_by_size=prices_by_size,
        price_summary=price_summary,
        variant_cost=variant_cost_input.text(),
        initial_stock=variant_stock_spin.value(),
    )
