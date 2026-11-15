"""Categorías que cuentan como uniforme escolar o como ropa normal.

Las usan los filtros de Catálogo e Inventario, las etiquetas y el
presupuesto guiado. Antes vivían en el helper del asistente viejo de la
prenda (`catalog_product_form_mode_helper`), que se retiró en la tanda 5
del alta (2026-11-15). Se comparan ya normalizadas (minúsculas).
"""

from __future__ import annotations

UNIFORM_CATEGORIES = {
    "uniformes",
    "uniforme",
    "basico",
    "básico",
    "deportivo",
    "oficial",
    "escolta",
    "accesorio",
}

REGULAR_CATEGORY_EXCLUSION_SET = {
    "ropa casual",
    "calzado",
    "accesorios",
    "temporada",
    "ropa interior",
    "pijamas",
    "deportivo casual",
}

__all__ = ["REGULAR_CATEGORY_EXCLUSION_SET", "UNIFORM_CATEGORIES"]
