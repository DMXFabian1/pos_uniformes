"""Búsqueda de texto de la pestaña Inventario (puro)."""

from __future__ import annotations

from typing import Callable, Iterable, Mapping


def combinar_hits_meili(
    filas: Iterable[Mapping[str, object]],
    skus_hits: set[str],
    coincide_local: Callable[[Mapping[str, object]], bool],
) -> list[Mapping[str, object]]:
    """Filas que deja la búsqueda cuando Meilisearch respondió.

    Meilisearch indexa solo variantes activas de productos activos
    (`meilisearch_service`), así que con texto las INACTIVAS desaparecían y el
    chip «Inactivas» / el filtro Estado «Inactivas» daban 0. Las activas salen
    de Meili (con typos y sinónimos); las inactivas, de la búsqueda local.

    Límite conocido: una variante activa de un PRODUCTO inactivo tampoco está
    en Meili y el snapshot no trae `producto_activo`, así que esa no se
    recupera aquí.
    """
    return [
        fila
        for fila in filas
        if str(fila.get("sku", "")) in skus_hits
        or (not bool(fila.get("variante_activa", True)) and coincide_local(fila))
    ]
