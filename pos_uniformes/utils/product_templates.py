"""Helpers para cargar y describir plantillas de producto."""

from __future__ import annotations

from html import escape
from pathlib import Path
import json

LEGACY_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "Gestor_de_Inventarios" / "src" / "core" / "config" / "config.json"
)


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
    # Deportivo — precios por nivel, escalera común
    {"label": "Preescolar playera", "sizes": ["2", "4", "6", "8", "10"], "prices": {"2": "199", "4": "199", "6": "199", "8": "199", "10": "199"}},
    {"label": "Preescolar chamarra", "sizes": ["2", "4", "6", "8", "10"], "prices": {"2": "315", "4": "315", "6": "315", "8": "315", "10": "315"}},
    {"label": "Preescolar pants 2pz", "sizes": ["2", "4", "6", "8", "10"], "prices": {"2": "485", "4": "485", "6": "485", "8": "485", "10": "485"}},
    {"label": "Preescolar pants 3pz", "sizes": ["2", "4", "6", "8", "10"], "prices": {"2": "585", "4": "585", "6": "585", "8": "585", "10": "585"}},
    {"label": "Primaria playera", "sizes": ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"], "prices": {"4": "199", "6": "199", "8": "199", "10": "199", "12": "209", "14": "209", "16": "209", "CH": "219", "MD": "225", "GD": "235"}},
    {"label": "Primaria chamarra", "sizes": ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"], "prices": {"4": "335", "6": "335", "8": "335", "10": "335", "12": "335", "14": "335", "16": "335", "CH": "335", "MD": "335", "GD": "335"}},
    {"label": "Primaria pants 2pz", "sizes": ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"], "prices": {"4": "485", "6": "485", "8": "485", "10": "485", "12": "485", "14": "495", "16": "495", "CH": "585", "MD": "585", "GD": "595"}},
    {"label": "Primaria pants 3pz", "sizes": ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"], "prices": {"4": "585", "6": "585", "8": "585", "10": "585", "12": "585", "14": "595", "16": "595", "CH": "685", "MD": "685", "GD": "695"}},
    {"label": "Secundaria deportiva", "sizes": ["10", "12", "14", "16", "CH", "MD", "GD", "EXG"], "prices": {"10": "229", "12": "229", "14": "229", "16": "229", "CH": "239", "MD": "239", "GD": "239", "EXG": "239"}},
    {"label": "Bachillerato deportiva", "sizes": ["12", "14", "16", "CH", "MD", "GD", "EXG"], "prices": {"12": "385", "14": "385", "16": "385", "CH": "385", "MD": "385", "GD": "385", "EXG": "385"}},
    # Oficial — suéteres, chalecos, camisas
    {"label": "Suéter botones / cuello V (preescolar-primaria)", "sizes": ["4", "6", "8", "10"], "prices": {"4": "290", "6": "290", "8": "290", "10": "290"}},
    {"label": "Suéter botones / cuello V (completo)", "sizes": ["4", "6", "8", "10", "12", "14", "16", "28", "30", "32", "34", "36", "38", "40", "42"], "prices": {"4": "289", "6": "289", "8": "289", "10": "299", "12": "299", "14": "299", "16": "299", "28": "309", "30": "309", "32": "309", "34": "309", "36": "315", "38": "315", "40": "315", "42": "315"}},
    {"label": "Chaleco oficial", "sizes": ["4", "6", "8", "10", "12", "14", "16", "28", "30", "32", "34", "36", "38", "40", "42", "44", "46"], "prices": {"4": "229", "6": "229", "8": "229", "10": "239", "12": "239", "14": "239", "16": "239", "28": "259", "30": "259", "32": "259", "34": "259", "36": "269", "38": "269", "40": "269", "42": "269", "44": "269", "46": "269"}},
    # Básico — pants, chamarras, faldas, jumpers, camisas
    {"label": "Pants 2pz liso", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "CH", "MD", "GD", "EXG"], "prices": {"2": "250", "4": "250", "6": "250", "8": "250", "10": "265", "12": "265", "14": "265", "16": "265", "28": "315", "CH": "315", "MD": "325", "GD": "335", "EXG": "345"}},
    {"label": "Pants 2pz punto", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "CH", "MD", "GD", "EXG"], "prices": {"2": "475", "4": "475", "6": "475", "8": "475", "10": "495", "12": "495", "14": "495", "16": "495", "28": "525", "CH": "525", "MD": "535", "GD": "545", "EXG": "555"}},
    {"label": "Pants suelto liso", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "CH", "MD", "GD", "EXG"], "prices": {"2": "165", "4": "165", "6": "165", "8": "165", "10": "180", "12": "180", "14": "180", "16": "180", "28": "205", "CH": "205", "MD": "215", "GD": "225", "EXG": "235"}},
    {"label": "Chamarra liso", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "CH", "MD", "GD", "EXG"], "prices": {"2": "175", "4": "175", "6": "175", "8": "175", "10": "225", "12": "225", "14": "225", "16": "225", "28": "235", "CH": "235", "MD": "235", "GD": "235", "EXG": "235"}},
    {"label": "Chamarra punto", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "CH", "MD", "GD", "EXG"], "prices": {"2": "275", "4": "275", "6": "275", "8": "275", "10": "295", "12": "295", "14": "295", "16": "295", "28": "385", "CH": "385", "MD": "395", "GD": "405", "EXG": "415"}},
    {"label": "Pantalón vestir", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "18", "20", "28", "30", "32", "34", "36", "38", "40"], "prices": {"2": "235", "4": "235", "6": "235", "8": "235", "10": "245", "12": "245", "14": "255", "16": "255", "18": "265", "20": "265", "28": "275", "30": "275", "32": "285", "34": "285", "36": "295", "38": "295", "40": "295"}},
    {"label": "Falda tableada / cuatro tablas", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "30", "32", "34", "36", "38", "40", "42"], "prices": {"2": "195", "4": "195", "6": "195", "8": "195", "10": "195", "12": "195", "14": "195", "16": "205", "28": "205", "30": "205", "32": "215", "34": "215", "36": "225", "38": "225", "40": "235", "42": "235"}},
    {"label": "Jumper", "sizes": ["2", "4", "6", "8", "10", "12", "14", "16", "28", "30", "32", "34", "36", "38"], "prices": {"2": "249", "4": "249", "6": "249", "8": "249", "10": "269", "12": "269", "14": "269", "16": "289", "28": "289", "30": "309", "32": "309", "34": "319", "36": "329", "38": "329"}},
    {"label": "Camisa manga corta", "sizes": ["4", "6", "8", "10", "12", "14", "16", "28", "30", "32", "34", "36", "38", "40", "42"], "prices": {"4": "89", "6": "89", "8": "89", "10": "99", "12": "99", "14": "99", "16": "99", "28": "115", "30": "115", "32": "135", "34": "135", "36": "145", "38": "145", "40": "165", "42": "165"}},
    # Malla — rangos especiales
    {"label": "Malla escolar", "sizes": ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"], "prices": {"0-0": "109", "0-2": "109", "3-5": "109", "6-8": "109", "9-12": "129", "13-18": "139", "CH-MD": "139", "GD-EXG": "139", "Dama": "139"}},
    # Accesorios
    {"label": "Unitalla accesorio", "sizes": ["Uni"], "prices": {"Uni": "70"}},
]



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
        prices = template_entry.get("prices") or {}
        unique_prices = sorted(set(str(v) for v in prices.values() if v)) if isinstance(prices, dict) else []
        price_preview = ", ".join(f"${p}" for p in unique_prices[:6])
        if len(unique_prices) > 6:
            price_preview += f" ... (+{len(unique_prices) - 6})"
        return (
            f"<div><b>{escape(str(template_entry.get('label') or '-'))}</b></div>"
            f"<div>{escape(f'{len(sizes)} tallas · {len(unique_prices)} precios distintos')}</div>"
            f"<div style='color:#6f665f;'><b>Tallas:</b> {escape(_format_list_preview(sizes))}</div>"
            f"<div style='color:#6f665f;'><b>Precios:</b> {escape(price_preview or '-')}</div>"
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
        raw_prices = template_entry.get("prices")
        prices: dict[str, str] = {}
        if isinstance(raw_prices, dict):
            prices = {str(k): str(v) for k, v in raw_prices.items() if v}
        return {
            "sizes": _clean_string_list(template_entry.get("sizes")),
            "prices": prices,
            "stock": int(template_entry.get("stock") or 0),
        }
    return {}


def suggest_presentation_template(criteria: dict[str, str]) -> str | None:
    garment_type = str(criteria.get("garment_type") or "").strip().casefold()
    piece_type = str(criteria.get("piece_type") or "").strip().casefold()
    attribute = str(criteria.get("attribute") or "").strip().casefold()
    education_level = str(criteria.get("education_level") or "").strip().casefold()

    if garment_type == "accesorio" or piece_type == "accesorio":
        return "Unitalla accesorio"
    if piece_type == "malla":
        return "Malla escolar"
    if garment_type == "deportivo":
        level = education_level or "primaria"
        piece = _match_deportivo_piece(piece_type)
        if level == "preescolar":
            return f"Preescolar {piece}"
        if level == "secundaria":
            return "Secundaria deportiva"
        if level == "bachillerato":
            return "Bachillerato deportiva"
        return f"Primaria {piece}"
    if garment_type == "oficial":
        if piece_type in ("suéter", "sueter"):
            return "Suéter botones / cuello V (preescolar-primaria)"
        if piece_type == "chaleco":
            return "Chaleco oficial"
        return None
    if garment_type == "basico":
        if piece_type == "pantalón" and attribute == "vestir":
            return "Pantalón vestir"
        if piece_type == "falda":
            return "Falda tableada / cuatro tablas"
        if piece_type == "jumper":
            return "Jumper"
        if piece_type == "camisa":
            return "Camisa manga corta"
        if piece_type in ("pants 2pz",):
            return "Pants 2pz liso" if attribute in ("liso", "") else "Pants 2pz punto"
        if piece_type == "pants suelto":
            return "Pants suelto liso"
        if piece_type == "chamarra":
            return "Chamarra liso" if attribute in ("liso", "") else "Chamarra punto"
        return None
    return None


def _match_deportivo_piece(piece_type: str) -> str:
    if piece_type in ("chamarra",):
        return "chamarra"
    if piece_type in ("pants 2pz",):
        return "pants 2pz"
    if piece_type in ("pants 3pz",):
        return "pants 3pz"
    return "playera"


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
