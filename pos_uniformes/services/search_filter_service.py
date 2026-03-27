"""Helpers puros para filtros de texto en tablas."""

from __future__ import annotations

import shlex
import unicodedata

SEARCH_GENERAL_BLOB_KEY = "_search_general_blob"
SEARCH_ALIAS_BLOBS_KEY = "_search_alias_blobs"

CATALOG_SEARCH_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "sku": ("sku",),
    "escuela": ("escuela_nombre",),
    "tipo": ("tipo_prenda_nombre",),
    "pieza": ("tipo_pieza_nombre",),
    "producto": ("producto_nombre_base", "producto_nombre"),
    "legacy": ("nombre_legacy",),
    "talla": ("talla",),
    "color": ("color",),
    "marca": ("marca_nombre",),
    "categoria": ("categoria_nombre",),
    "origen": ("origen_etiqueta",),
    "estado": ("producto_estado", "variante_estado"),
    "fallback": ("fallback_text",),
}

CATALOG_SEARCH_GENERAL_FIELDS: tuple[str, ...] = (
    "sku",
    "categoria_nombre",
    "marca_nombre",
    "escuela_nombre",
    "tipo_prenda_nombre",
    "tipo_pieza_nombre",
    "producto_nombre",
    "producto_nombre_base",
    "producto_descripcion",
    "nombre_legacy",
    "talla",
    "color",
    "origen_etiqueta",
    "producto_estado",
    "variante_estado",
    "fallback_text",
)

INVENTORY_SEARCH_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "sku": ("sku",),
    "escuela": ("escuela_nombre",),
    "tipo": ("tipo_prenda_nombre",),
    "pieza": ("tipo_pieza_nombre",),
    "producto": ("producto_nombre_base", "producto_nombre"),
    "legacy": ("nombre_legacy",),
    "talla": ("talla",),
    "color": ("color",),
    "marca": ("marca_nombre",),
    "categoria": ("categoria_nombre",),
    "origen": ("origen_etiqueta",),
    "estado": ("variante_estado",),
    "fallback": ("fallback_text",),
}

INVENTORY_SEARCH_GENERAL_FIELDS: tuple[str, ...] = (
    "sku",
    "categoria_nombre",
    "marca_nombre",
    "escuela_nombre",
    "tipo_prenda_nombre",
    "tipo_pieza_nombre",
    "producto_nombre",
    "producto_nombre_base",
    "nombre_legacy",
    "talla",
    "color",
    "origen_etiqueta",
    "variante_estado",
    "fallback_text",
)


def _normalize_search_fragment(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def build_row_search_cache(
    row: dict[str, object],
    *,
    alias_map: dict[str, tuple[str, ...]],
    general_fields: tuple[str, ...],
) -> dict[str, object]:
    general_blob = " ".join(_normalize_search_fragment(row.get(field, "")) for field in general_fields)
    alias_blobs = {
        alias: tuple(_normalize_search_fragment(row.get(field, "")) for field in fields)
        for alias, fields in alias_map.items()
    }
    return {
        SEARCH_GENERAL_BLOB_KEY: general_blob,
        SEARCH_ALIAS_BLOBS_KEY: alias_blobs,
    }


def attach_row_search_cache(
    row: dict[str, object],
    *,
    alias_map: dict[str, tuple[str, ...]],
    general_fields: tuple[str, ...],
) -> dict[str, object]:
    row.update(
        build_row_search_cache(
            row,
            alias_map=alias_map,
            general_fields=general_fields,
        )
    )
    return row


def tokenize_search_text(search_text: str) -> list[str]:
    normalized = search_text.strip()
    if not normalized:
        return []
    try:
        return [_normalize_search_fragment(term) for term in shlex.split(normalized) if term.strip()]
    except ValueError:
        return [_normalize_search_fragment(term) for term in normalized.split() if term.strip()]


def compile_search_terms(search_text: str) -> tuple[str, ...]:
    return tuple(tokenize_search_text(search_text))


def row_matches_search(
    row: dict[str, object],
    *,
    search_text: str,
    alias_map: dict[str, tuple[str, ...]],
    general_fields: tuple[str, ...],
    search_terms: tuple[str, ...] | None = None,
) -> bool:
    terms = search_terms if search_terms is not None else compile_search_terms(search_text)
    if not terms:
        return True

    general_haystack = str(row.get(SEARCH_GENERAL_BLOB_KEY, ""))
    if not general_haystack:
        general_haystack = " ".join(_normalize_search_fragment(row.get(field, "")) for field in general_fields)
    alias_blobs = row.get(SEARCH_ALIAS_BLOBS_KEY)
    normalized_alias_blobs = alias_blobs if isinstance(alias_blobs, dict) else {}

    for term in terms:
        if ":" not in term:
            if term not in general_haystack:
                return False
            continue

        alias, raw_value = term.split(":", 1)
        fields = alias_map.get(alias.strip())
        value = raw_value.strip().strip("\"'")
        if not fields or not value:
            if term not in general_haystack:
                return False
            continue
        cached_alias_values = normalized_alias_blobs.get(alias.strip())
        if cached_alias_values is not None:
            if any(value in cached_value for cached_value in cached_alias_values):
                continue
            return False
        if not any(value in _normalize_search_fragment(row.get(field, "")) for field in fields):
            return False
    return True
