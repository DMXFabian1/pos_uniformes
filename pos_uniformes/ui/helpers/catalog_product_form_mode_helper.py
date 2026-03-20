"""Estado visible del formulario de producto para uniforme escolar o ropa normal."""

from __future__ import annotations

from dataclasses import dataclass


UNIFORM_CATEGORIES = {
    "uniformes",
    "basico",
    "básico",
    "deportivo",
    "oficial",
    "escolta",
    "accesorio",
}

REGULAR_CATEGORY_SUGGESTIONS = (
    "Ropa casual",
    "Calzado",
    "Accesorios",
    "Temporada",
    "Ropa interior",
    "Pijamas",
    "Deportivo casual",
)

REGULAR_GARMENT_SUGGESTIONS = (
    "Casual",
    "Formal",
    "Deportivo casual",
    "Temporada",
    "Interior",
    "Descanso",
    "Accesorios",
    "Calzado",
)

REGULAR_PIECE_SUGGESTIONS = (
    "Playera",
    "Camisa",
    "Blusa",
    "Sudadera",
    "Chamarra",
    "Pantalon",
    "Jeans",
    "Short",
    "Falda",
    "Vestido",
    "Tenis",
    "Zapato",
    "Bota",
    "Sandalia",
    "Bolsa",
    "Mochila",
    "Gorra",
    "Cinturon",
)

REGULAR_ATTRIBUTE_SUGGESTIONS = (
    "Basico",
    "Liso",
    "Estampado",
    "Mezclilla",
    "Afelpado",
    "Termico",
    "Impermeable",
    "Casual",
    "Formal",
    "Deportivo",
    "Ligero",
    "Invierno",
    "Verano",
)

REGULAR_LOCATION_SUGGESTIONS = (
    "Piso de venta",
    "Rack central",
    "Muro",
    "Area de calzado",
    "Area de accesorios",
    "Bodega ropa normal",
)


@dataclass(frozen=True)
class CatalogProductFormModeView:
    mode_key: str
    mode_label: str
    category_locked: bool
    locked_category_label: str
    base_hint: str
    context_hint: str
    school_label: str
    garment_label: str
    piece_label: str
    attribute_label: str
    level_label: str
    shield_label: str
    location_label: str
    school_enabled: bool
    level_enabled: bool
    shield_enabled: bool
    context_template_enabled: bool
    base_templates_visible: bool
    context_templates_visible: bool
    presentation_templates_visible: bool
    school_field_visible: bool
    level_field_visible: bool
    shield_field_visible: bool
    exclude_uniform_category_options: bool
    exclude_uniform_garment_options: bool
    template_context_hint: str
    review_context_empty_label: str


def detect_catalog_product_form_mode(product_initial: dict[str, object] | None) -> str:
    if not product_initial:
        return "uniform"

    category_name = _normalize_text(product_initial.get("categoria_nombre"))
    if category_name in UNIFORM_CATEGORIES:
        return "uniform"

    for key in ("escuela", "nivel_educativo", "escudo"):
        if _normalize_text(product_initial.get(key)):
            return "uniform"

    return "regular"


def build_catalog_product_form_mode_view(mode_key: str) -> CatalogProductFormModeView:
    if mode_key == "regular":
        return CatalogProductFormModeView(
            mode_key="regular",
            mode_label="Ropa normal",
            category_locked=False,
            locked_category_label="Categoria editable",
            base_hint=(
                "Empieza por categoria, marca y nombre base. Para ropa normal la categoria se elige manualmente."
            ),
            context_hint=(
                "Define el contexto comercial de la prenda. Aqui decides linea, pieza, atributo, genero y ubicacion."
            ),
            school_label="Escuela",
            garment_label="Linea / estilo",
            piece_label="Prenda / pieza",
            attribute_label="Detalle",
            level_label="Nivel educativo",
            shield_label="Escudo",
            location_label="Ubicacion / rack",
            school_enabled=False,
            level_enabled=False,
            shield_enabled=False,
            context_template_enabled=False,
            base_templates_visible=False,
            context_templates_visible=False,
            presentation_templates_visible=False,
            school_field_visible=False,
            level_field_visible=False,
            shield_field_visible=False,
            exclude_uniform_category_options=True,
            exclude_uniform_garment_options=True,
            template_context_hint="Las plantillas de contexto escolar no aplican para ropa normal.",
            review_context_empty_label="Sin contexto adicional de ropa normal",
        )

    return CatalogProductFormModeView(
        mode_key="uniform",
        mode_label="Uniforme escolar",
        category_locked=True,
        locked_category_label="Uniformes",
        base_hint=(
            "Empieza por plantilla, marca y nombre base. La categoria se maneja internamente como Uniformes."
        ),
        context_hint=(
            "Define el contexto escolar del producto. Aqui decides tipo de uniforme, nivel, pieza y detalles."
        ),
        school_label="Escuela",
        garment_label="Tipo de uniforme",
        piece_label="Tipo pieza",
        attribute_label="Atributo",
        level_label="Nivel educativo",
        shield_label="Escudo",
        location_label="Ubicacion",
        school_enabled=True,
        level_enabled=True,
        shield_enabled=True,
        context_template_enabled=True,
        base_templates_visible=True,
        context_templates_visible=True,
        presentation_templates_visible=True,
        school_field_visible=True,
        level_field_visible=True,
        shield_field_visible=True,
        exclude_uniform_category_options=False,
        exclude_uniform_garment_options=False,
        template_context_hint="Selecciona una plantilla de contexto para sugerir nivel, prenda y escudo.",
        review_context_empty_label="Sin contexto escolar adicional",
    )


def _normalize_text(raw_value: object) -> str:
    if raw_value is None:
        return ""
    return str(raw_value).strip().lower()
