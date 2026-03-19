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
