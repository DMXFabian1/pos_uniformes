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
    """Nombre corto para tickets: nombre_base + escuela (sin tipo prenda/pieza).

    Si nombre_base ya contiene el nombre de la escuela, lo elimina para
    evitar duplicación (ej: 'Pants 2pz Deportivo Práxedis Guerrero - Práxedis Guerrero').
    También elimina 'Ad hoc' / 'Ad Hoc'.
    """
    nombre_base = str(getattr(producto, "nombre_base", "") or "").strip()
    if not nombre_base:
        return sanitize_product_display_name(getattr(producto, "nombre", ""))
    escuela = getattr(producto, "escuela", None)
    escuela_nombre = str(getattr(escuela, "nombre", "") or "").strip() if escuela else ""
    # Limpiar Ad hoc
    cleaned = re.sub(r"\bAd\s+hoc\b", "", nombre_base, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if escuela_nombre:
        # Quitar escuela si ya está en nombre_base
        cleaned = re.sub(re.escape(escuela_nombre), "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return f"{cleaned} - {escuela_nombre}" if cleaned else escuela_nombre
    return cleaned or nombre_base
