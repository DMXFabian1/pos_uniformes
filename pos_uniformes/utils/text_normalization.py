"""Normalización de texto reutilizable en filtros y búsquedas."""

from __future__ import annotations

import unicodedata


def normalize_text(raw_value: object) -> str:
    """Lowercase + strip, None-safe. Para comparaciones simples sin acentos."""
    if raw_value is None:
        return ""
    return str(raw_value).strip().lower()


def normalize_text_unicode(value: object) -> str:
    """Lowercase + strip + elimina diacríticos (NFKD). Para búsqueda con acentos."""
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
