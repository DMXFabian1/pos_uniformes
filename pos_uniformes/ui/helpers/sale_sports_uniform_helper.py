"""Subflujo de Caja para pants deportivos que pueden llevar playera."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import unicodedata

from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import Producto, Variante
from pos_uniformes.services.sports_uniform_size_service import (
    build_sports_uniform_size_guidance,
    build_sports_uniform_size_hint,
)
from pos_uniformes.services.venta_service import VentaService

_TWO_PIECE_PATTERNS = ("2pz", "2 pz", "2 piezas", "dos piezas", "conjunto 2", "set 2")
_SPORT_PATTERNS = ("deportivo", "deporte")
_PLAYERA_PATTERNS = ("playera", "camiseta", "jersey", "camisa deportiva")


@dataclass(frozen=True)
class SaleSportsUniformResolution:
    variants: tuple[object, ...]
    composed_as_three_pieces: bool = False
    selected_playera_sku: str = ""
    size_hint: str = ""


def resolve_sale_scan_variants(
    parent: QWidget | None,
    session,
    scanned_variant,
    *,
    variant_loader: Callable | None = None,
    playera_candidates_loader: Callable | None = None,
) -> SaleSportsUniformResolution | None:
    """Resuelve si un pants deportivo 2pz debe completarse con playera."""

    if not is_deportivo_two_piece_variant(scanned_variant):
        return SaleSportsUniformResolution(variants=(scanned_variant,))

    reply = QMessageBox.question(
        parent,
        "Uniforme deportivo",
        "Este pants 2 piezas puede llevar playera. ¿Tambien lleva playera?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return SaleSportsUniformResolution(variants=(scanned_variant,))

    typed_sku, accepted = QInputDialog.getText(
        parent,
        "Playera deportiva",
        (
            "Escanea o captura el SKU de la playera.\n"
            "Si lo dejas vacio, podras elegir una de la misma escuela."
        ),
    )
    if not accepted:
        return None

    load_variant = variant_loader or VentaService.obtener_variante_por_sku
    if typed_sku.strip():
        playera_variant = load_variant(session, typed_sku.strip().upper())
        if playera_variant is None:
            raise ValueError(f"El SKU '{typed_sku.strip().upper()}' no existe o esta inactivo.")
    else:
        load_candidates = playera_candidates_loader or load_same_school_playera_candidates
        playera_candidates = list(load_candidates(session, scanned_variant))
        if not playera_candidates:
            raise ValueError("No hay playeras deportivas disponibles para la misma escuela.")
        playera_variant = _prompt_playera_selection(parent, scanned_variant, playera_candidates)
        if playera_variant is None:
            return None

    validate_sports_playera_match(scanned_variant, playera_variant)
    return SaleSportsUniformResolution(
        variants=(scanned_variant, playera_variant),
        composed_as_three_pieces=True,
        selected_playera_sku=str(getattr(playera_variant, "sku", "") or ""),
        size_hint=build_sports_uniform_size_hint(
            getattr(scanned_variant, "talla", ""),
            getattr(playera_variant, "talla", ""),
        ),
    )


def build_sports_uniform_prototype_note(base_variant, playera_variant) -> str:
    return (
        "Maqueta prueba deportivo 3pz: "
        f"{getattr(base_variant, 'sku', '')} + {getattr(playera_variant, 'sku', '')}. "
        f"{build_sports_uniform_size_hint(getattr(base_variant, 'talla', ''), getattr(playera_variant, 'talla', ''))} "
        "Regla provisional; validar equivalencia de tallas despues."
    )


def attach_sports_uniform_trace_to_cart_lines(
    line_items: list[dict[str, object]],
    *,
    trace_note: str,
) -> None:
    for line_item in line_items:
        line_item["internal_trace_note"] = trace_note
        line_item["internal_trace_scope"] = "SPORTS_UNIFORM_PROTOTYPE"


def collect_internal_sale_cart_notes(
    sale_cart: list[dict[str, object]],
    *,
    scope: str | None = None,
) -> list[str]:
    unique_notes: list[str] = []
    seen: set[str] = set()
    for line_item in sale_cart:
        if scope is not None and str(line_item.get("internal_trace_scope") or "") != scope:
            continue
        note = str(line_item.get("internal_trace_note") or "").strip()
        if not note or note in seen:
            continue
        seen.add(note)
        unique_notes.append(note)
    return unique_notes


def is_deportivo_two_piece_variant(variante) -> bool:
    searchable = _variant_searchable_text(variante)
    return _contains_any(searchable, _SPORT_PATTERNS) and _contains_any(searchable, _TWO_PIECE_PATTERNS)


def is_deportivo_playera_variant(variante) -> bool:
    searchable = _variant_searchable_text(variante)
    return _contains_any(searchable, _SPORT_PATTERNS) and _contains_any(searchable, _PLAYERA_PATTERNS)


def validate_sports_playera_match(base_variant, playera_variant) -> None:
    if not is_deportivo_playera_variant(playera_variant):
        raise ValueError("La prenda seleccionada no es una playera deportiva valida.")
    if not belongs_to_same_school(base_variant, playera_variant):
        raise ValueError("La playera debe pertenecer a la misma escuela que el pants 2 piezas.")


def belongs_to_same_school(first_variant, second_variant) -> bool:
    first_product = getattr(first_variant, "producto", None)
    second_product = getattr(second_variant, "producto", None)
    first_school_id = getattr(first_product, "escuela_id", None)
    second_school_id = getattr(second_product, "escuela_id", None)
    if first_school_id is not None and second_school_id is not None:
        return first_school_id == second_school_id

    first_school_name = _normalize_text(getattr(getattr(first_product, "escuela", None), "nombre", ""))
    second_school_name = _normalize_text(getattr(getattr(second_product, "escuela", None), "nombre", ""))
    if first_school_name or second_school_name:
        return first_school_name == second_school_name
    return True


def load_same_school_playera_candidates(session, scanned_variant) -> list[object]:
    product = getattr(scanned_variant, "producto", None)
    school_id = getattr(product, "escuela_id", None)

    statement = (
        select(Variante)
        .join(Variante.producto)
        .options(
            joinedload(Variante.producto).joinedload(Producto.escuela),
            joinedload(Variante.producto).joinedload(Producto.tipo_prenda),
            joinedload(Variante.producto).joinedload(Producto.tipo_pieza),
        )
        .where(Variante.activo.is_(True), Producto.activo.is_(True))
    )
    if school_id is not None:
        statement = statement.where(Producto.escuela_id == school_id)

    variants = list(session.scalars(statement))
    filtered = [
        candidate
        for candidate in variants
        if is_deportivo_playera_variant(candidate) and belongs_to_same_school(scanned_variant, candidate)
    ]
    filtered.sort(key=lambda candidate: _playera_candidate_sort_key(scanned_variant, candidate))
    return filtered


def _prompt_playera_selection(parent: QWidget | None, base_variant, playera_candidates: list[object]) -> object | None:
    option_map = {
        _format_playera_option_label(candidate, base_variant=base_variant): candidate
        for candidate in playera_candidates
    }
    labels = list(option_map)
    selected_label, accepted = QInputDialog.getItem(
        parent,
        "Seleccionar playera",
        "Elige la playera deportiva de la misma escuela. [Exacta], [Sugerida] y [Atipica] son referencias de maqueta.",
        labels,
        0,
        False,
    )
    if not accepted:
        return None
    return option_map.get(selected_label)


def _format_playera_option_label(variante, *, base_variant=None) -> str:
    product = getattr(variante, "producto", None)
    school_name = str(getattr(getattr(product, "escuela", None), "nombre", "") or "").strip()
    school_segment = f" | {school_name}" if school_name else ""
    recommendation_label = ""
    if base_variant is not None:
        guidance = build_sports_uniform_size_guidance(
            getattr(base_variant, "talla", ""),
            getattr(variante, "talla", ""),
        )
        if guidance.match_level == "exacta":
            recommendation_label = " [Exacta]"
        elif guidance.match_level == "sugerida":
            recommendation_label = " [Sugerida]"
        elif guidance.match_level == "atipica":
            recommendation_label = " [Atipica]"
    return (
        f"{getattr(variante, 'sku', '')} | "
        f"{getattr(variante, 'talla', '-') or '-'} | "
        f"{getattr(variante, 'color', '-') or '-'} | "
        f"{getattr(product, 'nombre', '-') or '-'}"
        f"{school_segment}"
        f"{recommendation_label}"
    )


def _playera_candidate_sort_key(base_variant, playera_variant) -> tuple[object, ...]:
    guidance = build_sports_uniform_size_guidance(
        getattr(base_variant, "talla", ""),
        getattr(playera_variant, "talla", ""),
    )
    priority_by_level = {
        "exacta": 0,
        "sugerida": 1,
        "sin_referencia": 2,
        "atipica": 3,
    }
    return (
        priority_by_level.get(guidance.match_level, 9),
        str(getattr(playera_variant, "talla", "") or "").upper(),
        str(getattr(playera_variant, "sku", "") or "").upper(),
    )


def _variant_searchable_text(variante) -> str:
    product = getattr(variante, "producto", None)
    return " ".join(
        [
            _normalize_text(getattr(variante, "sku", "")),
            _normalize_text(getattr(variante, "talla", "")),
            _normalize_text(getattr(variante, "color", "")),
            _normalize_text(getattr(product, "nombre", "")),
            _normalize_text(getattr(product, "nombre_base", "")),
            _normalize_text(getattr(product, "descripcion", "")),
            _normalize_text(getattr(getattr(product, "tipo_prenda", None), "nombre", "")),
            _normalize_text(getattr(getattr(product, "tipo_pieza", None), "nombre", "")),
        ]
    )


def _normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)
