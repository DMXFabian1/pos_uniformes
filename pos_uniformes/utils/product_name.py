"""Utilidades para normalizar nombres visibles de productos."""

from __future__ import annotations

import re

_LEGACY_DUPLICATE_SUFFIX_PATTERN = re.compile(r"\s+#\d+$")


def sanitize_product_display_name(value: object | None) -> str:
    """Oculta sufijos legacy tipo ``#4`` que no forman parte del nombre real."""

    if value is None:
        return ""

    segments = []
    for raw_segment in str(value).split("|"):
        segment = " ".join(raw_segment.strip().split())
        if not segment:
            continue
        cleaned = _LEGACY_DUPLICATE_SUFFIX_PATTERN.sub("", segment).strip()
        if cleaned:
            segments.append(cleaned)
    return " | ".join(segments)


def build_ticket_product_name(producto: object) -> str:
    """Nombre corto para tickets: nombre_base + escuela (sin tipo prenda/pieza)."""
    nombre_base = str(getattr(producto, "nombre_base", "") or "").strip()
    if not nombre_base:
        return sanitize_product_display_name(getattr(producto, "nombre", ""))
    escuela = getattr(producto, "escuela", None)
    escuela_nombre = str(getattr(escuela, "nombre", "") or "").strip() if escuela else ""
    if escuela_nombre:
        return f"{nombre_base} - {escuela_nombre}"
    return nombre_base
