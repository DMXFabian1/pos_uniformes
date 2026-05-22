"""Helpers para cargar y describir plantillas de producto."""

from __future__ import annotations

from html import escape
from pathlib import Path
import json

LEGACY_PRODUCT_TEMPLATES_PATH = (
    Path(__file__).resolve().parents[2] / "Gestor_de_Inventarios" / "plantillas_productos.json"
)
LEGACY_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "Gestor_de_Inventarios" / "src" / "core" / "config" / "config.json"
)

_OMIT_LABELS = {
    "tipo_prenda": "tipo de prenda",
    "tipo_pieza": "tipo de pieza",
    "marca": "marca",
    "atributo": "atributo",
    "genero": "genero",
    "nivel_educativo": "nivel educativo",
    "escuela": "escuela",
    "ubicacion": "ubicacion",
    "escudo": "escudo",
    "colores": "colores",
}

BASE_STEP_TEMPLATES: list[dict[str, object]] = [
    # Deportivos — nombre: [Pieza] Deportiva/o [Escuela]
    {"label": "Playera deportiva", "name": "Playera Deportiva", "piece_type": "Playera", "garment_type": "Deportivo", "description": "Playera deportiva escolar. Color por escuela."},
    {"label": "Chamarra deportiva", "name": "Chamarra Deportiva", "piece_type": "Chamarra", "garment_type": "Deportivo", "description": "Chamarra deportiva escolar. Color por escuela."},
    {"label": "Pants 2pz deportivo", "name": "Pants 2pz Deportivo", "piece_type": "Pants 2pz", "garment_type": "Deportivo", "description": "Conjunto deportivo de dos piezas."},
    {"label": "Pants 3pz deportivo", "name": "Pants 3pz Deportivo", "piece_type": "Pants 3pz", "garment_type": "Deportivo", "description": "Conjunto deportivo de tres piezas."},
    # Básicos — nombre: [Pieza] [Atributo] [Color]
    {"label": "Pants 2pz liso", "name": "Pants 2pz Liso", "piece_type": "Pants 2pz", "attribute": "Liso", "garment_type": "Basico", "description": "Conjunto basico de dos piezas liso."},
    {"label": "Pants 2pz punto", "name": "Pants 2pz Punto", "piece_type": "Pants 2pz", "attribute": "Punto", "garment_type": "Basico", "description": "Conjunto basico de dos piezas punto."},
    {"label": "Pants suelto liso", "name": "Pants Suelto Liso", "piece_type": "Pants Suelto", "attribute": "Liso", "garment_type": "Basico", "description": "Pants suelto liso para uniforme basico."},
    {"label": "Pants suelto punto", "name": "Pants Suelto Punto", "piece_type": "Pants Suelto", "attribute": "Punto", "garment_type": "Basico", "description": "Pants suelto punto para uniforme basico."},
    # Oficiales — nombre: [Pieza] [Atributo] [Género]
    {"label": "Suéter botones M", "name": "Suéter Botones M", "piece_type": "Suéter", "attribute": "Botones", "gender": "Mujer", "garment_type": "Oficial", "description": "Suéter escolar con botones mujer."},
    {"label": "Suéter cuello V H", "name": "Suéter Cuello V H", "piece_type": "Suéter", "attribute": "Cuello V", "gender": "Hombre", "garment_type": "Oficial", "description": "Suéter escolar cuello V hombre."},
    {"label": "Chaleco oficial", "name": "Chaleco", "piece_type": "Chaleco", "gender": "Unisex", "garment_type": "Oficial", "description": "Chaleco escolar oficial."},
    {"label": "Pantalón vestir", "name": "Pantalón Vestir", "piece_type": "Pantalón", "attribute": "Vestir", "garment_type": "Oficial", "description": "Pantalón escolar de vestir."},
    {"label": "Falda cuatro tablas", "name": "Falda Cuatro tablas", "piece_type": "Falda", "attribute": "Cuatro tablas", "gender": "Mujer", "garment_type": "Oficial", "description": "Falda escolar cuatro tablas."},
    {"label": "Falda escocés", "name": "Falda Escoces", "piece_type": "Falda", "attribute": "Escoces", "gender": "Mujer", "garment_type": "Oficial", "description": "Falda escolar escocés."},
    {"label": "Malla escolar", "name": "Malla", "piece_type": "Malla", "gender": "Mujer", "garment_type": "Oficial", "description": "Malla escolar."},
    {"label": "Jumper", "name": "Jumper", "piece_type": "Jumper", "gender": "Mujer", "garment_type": "Basico", "description": "Jumper escolar."},
    {"label": "Camisa manga corta", "name": "Camisa Manga Corta", "piece_type": "Camisa", "attribute": "Manga corta", "garment_type": "Oficial", "description": "Camisa escolar de manga corta."},
    {"label": "Camisa manga larga", "name": "Camisa Manga Larga", "piece_type": "Camisa", "attribute": "Manga larga", "garment_type": "Oficial", "description": "Camisa escolar de manga larga."},
    {"label": "Camisa cuello olan", "name": "Camisa Cuello olan", "piece_type": "Camisa", "attribute": "Cuello olan", "gender": "Mujer", "garment_type": "Oficial", "description": "Camisa escolar cuello olan."},
    # Accesorios — nombre: [Pieza] [Tipo]
    {"label": "Boina escolta", "name": "Boina Escolta", "piece_type": "Boina", "garment_type": "Escolta", "description": "Boina para uniforme de escolta."},
    {"label": "Corbatín", "name": "Corbatín", "piece_type": "Corbatín", "garment_type": "Accesorio", "description": "Corbatín escolar."},
    {"label": "Moño", "name": "Moño", "piece_type": "Moño", "garment_type": "Accesorio", "description": "Moño escolar."},
    {"label": "Bata manga corta", "name": "Bata Manga Corta", "piece_type": "Bata", "attribute": "Manga corta", "garment_type": "Accesorio", "description": "Bata escolar manga corta."},
    {"label": "Bata manga larga", "name": "Bata Manga Larga", "piece_type": "Bata", "attribute": "Manga larga", "garment_type": "Accesorio", "description": "Bata escolar manga larga."},
]

CONTEXT_STEP_TEMPLATES: list[dict[str, object]] = [
    # Deportivo por nivel — siempre Con Escudo
    {"label": "Preescolar deportivo", "garment_type": "Deportivo", "education_level": "Preescolar", "shield": "Con Escudo"},
    {"label": "Primaria deportivo", "garment_type": "Deportivo", "education_level": "Primaria", "shield": "Con Escudo"},
    {"label": "Secundaria deportivo", "garment_type": "Deportivo", "education_level": "Secundaria", "shield": "Con Escudo"},
    {"label": "Bachillerato deportivo", "garment_type": "Deportivo", "education_level": "Bachillerato", "shield": "Con Escudo"},
    # Oficial por nivel + género — siempre Con Escudo
    {"label": "Primaria oficial mujer", "garment_type": "Oficial", "education_level": "Primaria", "gender": "Mujer", "shield": "Con Escudo"},
    {"label": "Primaria oficial hombre", "garment_type": "Oficial", "education_level": "Primaria", "gender": "Hombre", "shield": "Con Escudo"},
    {"label": "Secundaria oficial mujer", "garment_type": "Oficial", "education_level": "Secundaria", "gender": "Mujer", "shield": "Con Escudo"},
    {"label": "Secundaria oficial hombre", "garment_type": "Oficial", "education_level": "Secundaria", "gender": "Hombre", "shield": "Con Escudo"},
    {"label": "Preescolar oficial", "garment_type": "Oficial", "education_level": "Preescolar"},
    # Oficial por pieza (sin nivel fijo)
    {"label": "Suéter botones mujer", "garment_type": "Oficial", "piece_type": "Suéter", "attribute": "Botones", "gender": "Mujer", "shield": "Con Escudo"},
    {"label": "Suéter cuello V hombre", "garment_type": "Oficial", "piece_type": "Suéter", "attribute": "Cuello V", "gender": "Hombre", "shield": "Con Escudo"},
    {"label": "Chaleco oficial", "garment_type": "Oficial", "piece_type": "Chaleco", "shield": "Con Escudo"},
    {"label": "Playera polo oficial", "garment_type": "Oficial", "piece_type": "Playera", "attribute": "Polo", "shield": "Con Escudo"},
    {"label": "Camisa cuello olan", "garment_type": "Oficial", "piece_type": "Camisa", "attribute": "Cuello olan", "education_level": "Preescolar"},
    # Básico — sin nivel, sin escudo
    {"label": "Básico general", "garment_type": "Basico"},
    {"label": "Básico pantalón vestir", "garment_type": "Basico", "piece_type": "Pantalón", "attribute": "Vestir"},
    {"label": "Básico falda", "garment_type": "Basico", "piece_type": "Falda"},
    {"label": "Básico pants liso", "garment_type": "Basico", "piece_type": "Pants 2pz", "attribute": "Liso"},
    {"label": "Básico pants punto", "garment_type": "Basico", "piece_type": "Pants 2pz", "attribute": "Punto"},
    {"label": "Básico chamarra", "garment_type": "Basico", "piece_type": "Chamarra"},
    {"label": "Básico suéter mujer", "garment_type": "Basico", "piece_type": "Suéter", "attribute": "Botones", "gender": "Mujer"},
    {"label": "Básico suéter hombre", "garment_type": "Basico", "piece_type": "Suéter", "attribute": "Cuello V", "gender": "Hombre"},
    {"label": "Básico jumper", "garment_type": "Basico", "piece_type": "Jumper", "gender": "Mujer"},
    {"label": "Básico camisa", "garment_type": "Basico", "piece_type": "Camisa", "attribute": "Manga Corta"},
    # Accesorios
    {"label": "Malla escolar", "garment_type": "Accesorio", "piece_type": "Malla", "attribute": "Escolar"},
    {"label": "Accesorio escolar", "garment_type": "Accesorio", "attribute": "Escolar"},
    # Escolta
    {"label": "Escolta", "garment_type": "Escolta", "shield": "Con Escudo"},
]

PRESENTATION_STEP_TEMPLATES: list[dict[str, object]] = [
    # Deportivo por nivel — colores varían por escuela, iniciar con paleta común
    {"label": "Preescolar deportiva", "sizes": ["2", "4", "6", "8", "10"], "colors": ["Azul Marino", "Rojo", "Verde", "Vino", "Blanco"]},
    {"label": "Primaria deportiva", "sizes": ["4", "6", "8", "10", "12", "14", "16", "18", "CH", "MD", "GD", "EXG"], "colors": ["Azul Marino", "Rojo", "Verde", "Vino", "Blanco"]},
    {"label": "Secundaria deportiva", "sizes": ["10", "12", "14", "16", "18", "CH", "MD", "GD", "EXG"], "colors": ["Azul Marino", "Rojo", "Verde", "Vino", "Blanco"]},
    {"label": "Bachillerato deportiva", "sizes": ["12", "14", "16", "CH", "MD", "GD", "EXG"], "colors": ["Azul Marino", "Rojo", "Verde", "Vino", "Blanco"]},
    # Oficial — separado por género (tallas numéricas difieren)
    {"label": "Oficial mujer", "sizes": ["4", "6", "8", "10", "12", "14", "16", "18", "28", "30", "32", "34", "36", "38", "40", "42", "44"], "colors": ["Azul Marino", "Rojo", "Vino", "Blanco", "Negro"]},
    {"label": "Oficial hombre", "sizes": ["4", "6", "8", "10", "12", "14", "16", "18", "30", "32", "34", "36", "38", "40", "42", "44"], "colors": ["Azul Marino", "Rojo", "Vino", "Blanco", "Negro"]},
    # Básico — infantil (solo numeración chica) y mixto (infantil + adulto)
    {"label": "Básico infantil", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16"], "colors": ["Azul Marino", "Blanco", "Rojo", "Vino", "Gris", "Verde", "Azul Rey", "Negro"]},
    {"label": "Básico mixto", "sizes": ["4", "6", "8", "10", "12", "14", "16", "18", "28", "30", "32", "34", "36", "38", "40", "42", "44"], "colors": ["Azul Marino", "Blanco", "Negro", "Rojo", "Verde", "Vino", "Gris"]},
    # Malla — rangos especiales
    {"label": "Malla escolar", "sizes": ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"], "colors": ["Rojo", "Beige", "Vino", "Azul Marino", "Negro", "Verde", "Blanco"]},
    # Accesorios — unitalla o sin color
    {"label": "Unitalla accesorio", "sizes": ["Uni"], "colors": ["Sin color"]},
]


def load_legacy_product_templates(path: Path | None = None) -> list[dict[str, object]]:
    """Carga las plantillas del sistema legacy y las normaliza para el formulario nuevo."""

    template_path = (path or LEGACY_PRODUCT_TEMPLATES_PATH).expanduser().resolve()
    if not template_path.exists():
        return []

    try:
        raw_data = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    templates: list[dict[str, object]] = []
    for raw_template in raw_data.get("plantillas", []):
        if not isinstance(raw_template, dict):
            continue
        template_name = str(raw_template.get("nombre_plantilla") or "").strip()
        if not template_name:
            continue
        schools = _clean_string_list(raw_template.get("escuelas"))
        sizes = _clean_string_list(raw_template.get("tallas"))
        colors = _clean_string_list(raw_template.get("colores"))
        omit_values = {
            str(key): bool(value)
            for key, value in (raw_template.get("omitir") or {}).items()
        }
        templates.append(
            {
                "source": "legacy",
                "label": f"Legacy | {template_name}",
                "name": template_name,
                "tipo_prenda": str(raw_template.get("tipo_prenda") or "").strip(),
                "tipo_pieza": str(raw_template.get("tipo_pieza") or "").strip(),
                "marca": str(raw_template.get("marca") or "").strip(),
                "atributo": str(raw_template.get("atributo") or "").strip(),
                "genero": str(raw_template.get("genero") or "").strip(),
                "nivel_educativo": str(raw_template.get("nivel_educativo") or "").strip(),
                "ubicacion": str(raw_template.get("ubicacion") or "").strip(),
                "escudo": str(raw_template.get("escudo") or "").strip(),
                "precio": str(raw_template.get("precio") or "").strip(),
                "escuelas": schools,
                "tallas": sizes,
                "colores": colors,
                "omitir": omit_values,
            }
        )
    return templates


def load_step_product_templates(step: str) -> list[dict[str, object]]:
    normalized_step = step.strip().lower()
    if normalized_step == "base":
        return [dict(item) for item in BASE_STEP_TEMPLATES]
    if normalized_step == "context":
        return [dict(item) for item in CONTEXT_STEP_TEMPLATES]
    if normalized_step == "presentation":
        return [dict(item) for item in PRESENTATION_STEP_TEMPLATES]
    return []


def build_step_template_preview(step: str, template_entry: dict[str, object]) -> str:
    normalized_step = step.strip().lower()
    if normalized_step == "base":
        parts = [
            str(template_entry.get("garment_type") or "").strip(),
            str(template_entry.get("piece_type") or "").strip(),
            str(template_entry.get("attribute") or "").strip(),
            str(template_entry.get("gender") or "").strip(),
        ]
        parts = [part for part in parts if part]
        return (
            f"<div><b>{escape(str(template_entry.get('label') or '-'))}</b></div>"
            f"<div>{escape(' · '.join(parts) if parts else str(template_entry.get('name') or '-'))}</div>"
            f"<div style='color:#6f665f;'>{escape(str(template_entry.get('description') or ''))}</div>"
        )
    if normalized_step == "context":
        parts = [
            str(template_entry.get("education_level") or "").strip(),
            str(template_entry.get("garment_type") or "").strip(),
            str(template_entry.get("piece_type") or "").strip(),
            str(template_entry.get("attribute") or "").strip(),
            str(template_entry.get("gender") or "").strip(),
            str(template_entry.get("shield") or "").strip(),
        ]
        parts = [part for part in parts if part]
        return (
            f"<div><b>{escape(str(template_entry.get('label') or '-'))}</b></div>"
            f"<div>{escape(' · '.join(parts) if parts else 'Sin contexto sugerido')}</div>"
            "<div style='color:#6f665f;'>Aplica solo campos de contexto.</div>"
        )
    if normalized_step == "presentation":
        sizes = _clean_string_list(template_entry.get("sizes"))
        colors = _clean_string_list(template_entry.get("colors"))
        return (
            f"<div><b>{escape(str(template_entry.get('label') or '-'))}</b></div>"
            f"<div>{escape(f'{len(sizes)} tallas · {len(colors)} colores')}</div>"
            f"<div style='color:#6f665f;'><b>Tallas:</b> {escape(_format_list_preview(sizes))}</div>"
            f"<div style='color:#6f665f;'><b>Colores:</b> {escape(_format_list_preview(colors, max_items=5))}</div>"
        )
    return "<div>Sin vista previa.</div>"


def step_template_defaults(step: str, template_entry: dict[str, object]) -> dict[str, object]:
    normalized_step = step.strip().lower()
    if normalized_step == "base":
        return {
            "name": str(template_entry.get("name") or "").strip(),
            "garment_type": str(template_entry.get("garment_type") or "").strip(),
            "piece_type": str(template_entry.get("piece_type") or "").strip(),
            "attribute": str(template_entry.get("attribute") or "").strip(),
            "gender": str(template_entry.get("gender") or "").strip(),
            "description": str(template_entry.get("description") or "").strip(),
        }
    if normalized_step == "context":
        return {
            "garment_type": str(template_entry.get("garment_type") or "").strip(),
            "piece_type": str(template_entry.get("piece_type") or "").strip(),
            "attribute": str(template_entry.get("attribute") or "").strip(),
            "education_level": str(template_entry.get("education_level") or "").strip(),
            "gender": str(template_entry.get("gender") or "").strip(),
            "shield": str(template_entry.get("shield") or "").strip(),
            "location": str(template_entry.get("location") or "").strip(),
        }
    if normalized_step == "presentation":
        return {
            "sizes": _clean_string_list(template_entry.get("sizes")),
            "colors": _clean_string_list(template_entry.get("colors")),
            "price": str(template_entry.get("price") or "").strip(),
            "stock": int(template_entry.get("stock") or 0),
        }
    return {}


def suggest_presentation_template(criteria: dict[str, str]) -> str | None:
    garment_type = str(criteria.get("garment_type") or "").strip().casefold()
    piece_type = str(criteria.get("piece_type") or "").strip().casefold()
    education_level = str(criteria.get("education_level") or "").strip().casefold()
    gender = str(criteria.get("gender") or "").strip().casefold()

    if garment_type == "accesorio" or piece_type == "accesorio":
        return "Unitalla accesorio"
    if piece_type == "malla":
        return "Malla escolar"
    if garment_type == "deportivo":
        if education_level == "preescolar":
            return "Preescolar deportiva"
        if education_level == "secundaria":
            return "Secundaria deportiva"
        if education_level == "bachillerato":
            return "Bachillerato deportiva"
        return "Primaria deportiva"
    if garment_type == "oficial":
        if gender == "hombre":
            return "Oficial hombre"
        if gender == "mujer":
            return "Oficial mujer"
    if garment_type == "basico":
        if education_level in {"secundaria", "bachillerato"}:
            return "Básico mixto"
        return "Básico infantil"
    return None


def build_price_blocks(criteria: dict[str, str], sizes: list[str]) -> list[dict[str, object]]:
    normalized_sizes = [str(size or "").strip() for size in sizes if str(size or "").strip()]
    if not normalized_sizes:
        return [{"key": "unitalla", "label": "Unitalla", "sizes": ["Unitalla"]}]

    grouped_sizes: dict[str, list[str]] = {}
    ordered_labels: list[str] = []
    for size in normalized_sizes:
        block = _classify_price_block(criteria, size)
        key = str(block["key"])
        if key not in grouped_sizes:
            grouped_sizes[key] = []
            ordered_labels.append(key)
        grouped_sizes[key].append(size)

    label_map = {
        "preescolar": "Preescolar",
        "infantil": "Infantil",
        "numericas": "Numericas",
        "letras": "Letras",
        "malla": "Malla",
        "unitalla": "Unitalla",
        "especiales": "Especiales",
    }
    return [
        {
            "key": key,
            "label": label_map.get(key, str(key).title()),
            "sizes": grouped_sizes[key],
        }
        for key in ordered_labels
    ]


def suggest_price_capture_mode(criteria: dict[str, str], sizes: list[str]) -> str:
    blocks = build_price_blocks(criteria, sizes)
    return "blocks" if len(blocks) > 1 else "single"


def _classify_price_block(criteria: dict[str, str], size: str) -> dict[str, str]:
    garment_type = _normalize_token(str(criteria.get("garment_type") or ""))
    piece_type = _normalize_token(str(criteria.get("piece_type") or ""))
    education_level = _normalize_token(str(criteria.get("education_level") or ""))
    normalized_size = _normalize_token(size)

    if normalized_size in {"uni", "unitalla", "sin talla"}:
        return {"key": "unitalla"}
    if any(token in normalized_size for token in ("dama", "ch-md", "gd-exg")):
        return {"key": "malla"}
    if "-" in normalized_size:
        return {"key": "malla"}
    if normalized_size in {"ch", "md", "gd", "xg", "exg", "xxg", "xxxg"}:
        return {"key": "letras"}
    if normalized_size.isdigit():
        numeric_size = int(normalized_size)
        if garment_type == "deportivo" and education_level == "preescolar" and numeric_size <= 8:
            return {"key": "preescolar"}
        if numeric_size <= 16:
            return {"key": "infantil"}
        if numeric_size >= 28:
            return {"key": "numericas"}

    if piece_type == "malla":
        return {"key": "malla"}
    if garment_type == "accesorio" or piece_type == "accesorio":
        return {"key": "unitalla"}
    return {"key": "especiales"}


def _normalize_token(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def load_legacy_config_choices(path: Path | None = None) -> dict[str, list[str]]:
    """Carga las listas configurables del sistema legacy para reutilizarlas como sugerencias."""

    config_path = (path or LEGACY_CONFIG_PATH).expanduser().resolve()
    if not config_path.exists():
        return {}

    try:
        raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    keys = [
        "TALLAS",
        "COLORES",
        "GENEROS",
        "MARCAS",
        "NIVELES_EDUCATIVOS",
        "TIPOS_PRENDA",
        "TIPOS_PIEZA",
        "ATRIBUTOS",
        "UBICACIONES",
        "ESCUDOS",
    ]
    return {
        key: _clean_string_list(raw_data.get(key))
        for key in keys
        if _clean_string_list(raw_data.get(key))
    }


def merge_choice_lists(*groups: list[str]) -> list[str]:
    """Une listas sin duplicados, conservando el orden de aparición."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw_value in group:
            value = str(raw_value or "").strip()
            normalized = value.casefold()
            if not value or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(value)
    return merged


def build_product_template_preview(template_entry: dict[str, object]) -> str:
    """Genera un resumen compacto en HTML de la plantilla seleccionada."""

    source = str(template_entry.get("source") or "builtin")
    if source == "legacy":
        schools = _clean_string_list(template_entry.get("escuelas"))
        sizes = _clean_string_list(template_entry.get("tallas"))
        colors = _clean_string_list(template_entry.get("colores"))
        school_preview = _format_list_preview(schools, max_items=3)
        size_preview = _format_list_preview(sizes)
        color_preview = _format_list_preview(colors, max_items=5)
        omitted = [
            label
            for key, label in _OMIT_LABELS.items()
            if bool((_omitir := template_entry.get("omitir")) and isinstance(_omitir, dict) and _omitir.get(key))
        ]
        title = f"Legacy | {str(template_entry.get('name') or '').strip() or '-'}"
        primary_parts = [
            str(template_entry.get("tipo_prenda") or "").strip() or "-",
            str(template_entry.get("tipo_pieza") or "").strip() or "-",
            str(template_entry.get("atributo") or "").strip() or "-",
        ]
        secondary_parts = [
            f"{len(sizes)} talla{'s' if len(sizes) != 1 else ''}" if sizes else "sin tallas",
            f"{len(colors)} color{'es' if len(colors) != 1 else ''}" if colors else "sin colores",
            (
                f"{len(schools)} escuela{'s' if len(schools) != 1 else ''}"
                if schools
                else "sin escuela fija"
            ),
        ]
        context_parts = []
        if str(template_entry.get("nivel_educativo") or "").strip():
            context_parts.append(str(template_entry.get("nivel_educativo") or "").strip())
        if str(template_entry.get("genero") or "").strip():
            context_parts.append(str(template_entry.get("genero") or "").strip())
        if str(template_entry.get("escudo") or "").strip():
            context_parts.append(str(template_entry.get("escudo") or "").strip())
        if str(template_entry.get("ubicacion") or "").strip():
            context_parts.append(str(template_entry.get("ubicacion") or "").strip())
        if str(template_entry.get("precio") or "").strip():
            context_parts.append(f"${str(template_entry.get('precio') or '').strip()}")
        if str(template_entry.get("marca") or "").strip():
            context_parts.append(str(template_entry.get("marca") or "").strip())
        note_parts = []
        if omitted:
            note_parts.append(f"Omitidos: {', '.join(omitted)}")
        if len(schools) > 1:
            note_parts.append(
                "Incluye varias escuelas; aqui solo se usan como referencia visual antes del alta por lote."
            )
        if sizes or colors:
            note_parts.append(
                "Revisa tallas y colores antes de aplicar para evitar cambios manuales despues."
            )
        return (
            f"<div><b>{escape(title)}</b></div>"
            f"<div>{escape(' · '.join(primary_parts))}</div>"
            f"<div>{escape(' · '.join(secondary_parts + context_parts[:2]))}</div>"
            f"<div style='margin-top:4px; color:#6f665f;'><b>Escuelas:</b> {escape(school_preview)}</div>"
            f"<div style='color:#6f665f;'><b>Tallas:</b> {escape(size_preview)}</div>"
            f"<div style='color:#6f665f;'><b>Colores:</b> {escape(color_preview)}</div>"
            f"<div style='color:#6f665f;'>{escape(' · '.join(context_parts[2:])) if len(context_parts) > 2 else '&nbsp;'}</div>"
            f"<div style='margin-top:4px; color:#7e3a22;'>{escape(' | '.join(note_parts)) if note_parts else 'Lista para revisar y aplicar.'}</div>"
        )

    title = str(template_entry.get("label") or "").strip() or "-"
    category = str(template_entry.get("category") or "").strip() or "-"
    name = str(template_entry.get("name") or "").strip() or "-"
    description = str(template_entry.get("description") or "").strip() or "-"
    return (
        f"<div><b>{escape(title)}</b></div>"
        f"<div>{escape(category)} · {escape(name)}</div>"
        f"<div style='color:#6f665f;'>{escape(description)}</div>"
        "<div style='color:#7e3a22;'>Plantilla sugerida para arrancar rapido y ajustar a mano.</div>"
    )


def product_template_defaults(template_entry: dict[str, object]) -> dict[str, str]:
    """Mapea una plantilla a los campos editables del producto base."""

    source = str(template_entry.get("source") or "builtin")
    if source == "legacy":
        schools = _clean_string_list(template_entry.get("escuelas"))
        return {
            "category": "",
            "name": str(template_entry.get("name") or "").strip(),
            "description": "",
            "brand": str(template_entry.get("marca") or "").strip(),
            "school": schools[0] if len(schools) == 1 else "",
            "garment_type": str(template_entry.get("tipo_prenda") or "").strip(),
            "piece_type": str(template_entry.get("tipo_pieza") or "").strip(),
            "attribute": str(template_entry.get("atributo") or "").strip(),
            "education_level": str(template_entry.get("nivel_educativo") or "").strip(),
            "gender": str(template_entry.get("genero") or "").strip(),
            "shield": str(template_entry.get("escudo") or "").strip(),
            "location": str(template_entry.get("ubicacion") or "").strip(),
        }

    return {
        "category": str(template_entry.get("category") or "").strip(),
        "name": str(template_entry.get("name") or "").strip(),
        "description": str(template_entry.get("description") or "").strip(),
        "brand": "",
        "school": "",
        "garment_type": "",
        "piece_type": "",
        "attribute": "",
        "education_level": "",
        "gender": "",
        "shield": "",
        "location": "",
    }


def _clean_string_list(raw_values: object) -> list[str]:
    if not isinstance(raw_values, list):
        return []
    cleaned: list[str] = []
    for value in raw_values:
        text = str(value or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _format_list_preview(values: list[str], *, max_items: int = 6) -> str:
    if not values:
        return "-"
    preview = ", ".join(values[:max_items])
    if len(values) <= max_items:
        return preview
    return f"{preview} ... (+{len(values) - max_items})"
