"""Helpers puros para snapshot y filas visibles del listado de Catalogo."""

from __future__ import annotations

from pos_uniformes.services.search_filter_service import (
    CATALOG_SEARCH_ALIAS_MAP,
    CATALOG_SEARCH_GENERAL_FIELDS,
    attach_row_search_cache,
)
from pos_uniformes.utils.product_name import sanitize_product_display_name


def build_catalog_snapshot_rows(rows: list[tuple[object, ...]]) -> list[dict[str, object]]:
    return [
        attach_row_search_cache(
            {
                "variante_id": normalized_row["variante_id"],
                "producto_id": normalized_row["producto_id"],
                "categoria_id": normalized_row["categoria_id"],
                "marca_id": normalized_row["marca_id"],
                "escuela_id": normalized_row["escuela_id"],
                "sku": normalized_row["sku"],
                "categoria_nombre": normalized_row["categoria_nombre"],
                "marca_nombre": normalized_row["marca_nombre"],
                "escuela_nombre": normalized_row["escuela_nombre"] or "General",
                "nivel_educativo_nombre": normalized_row["nivel_educativo_nombre"] or "Sin nivel",
                "producto_genero": normalized_row["producto_genero"] or "",
                "tipo_prenda_nombre": normalized_row["tipo_prenda_nombre"] or "-",
                "tipo_pieza_nombre": normalized_row["tipo_pieza_nombre"] or "-",
                "producto_nombre": sanitize_product_display_name(normalized_row["producto_nombre"]),
                "producto_nombre_base": normalized_row["producto_nombre_base"],
                "producto_descripcion": normalized_row["producto_descripcion"],
                "nombre_legacy": normalized_row["nombre_legacy"],
                "origen_legacy": bool(normalized_row["origen_legacy"]),
                "talla": normalized_row["talla"],
                "color": normalized_row["color"],
                "precio_venta": normalized_row["precio_venta"],
                "costo_referencia": normalized_row["costo_referencia"],
                "stock_actual": normalized_row["stock_actual"],
                "apartado_cantidad": normalized_row["apartado_cantidad"],
                "producto_activo": normalized_row["producto_activo"],
                "variante_activo": normalized_row["variante_activo"],
                "producto_estado": "ACTIVO" if normalized_row["producto_activo"] else "INACTIVO",
                "variante_estado": "ACTIVA" if normalized_row["variante_activo"] else "INACTIVA",
                "origen_etiqueta": "LEGACY" if normalized_row["origen_legacy"] else "NUEVO",
                "fallback_importacion": bool(normalized_row["fallback_importacion"]),
                "fallback_text": "fallback" if bool(normalized_row["fallback_importacion"]) else "",
            },
            alias_map=CATALOG_SEARCH_ALIAS_MAP,
            general_fields=CATALOG_SEARCH_GENERAL_FIELDS,
        )
        for normalized_row in (_normalize_catalog_snapshot_row(row) for row in rows)
    ]


def _normalize_catalog_snapshot_row(row: tuple[object, ...]) -> dict[str, object]:
    if len(row) == 27:
        return {
            "variante_id": row[0],
            "producto_id": row[1],
            "categoria_id": row[2],
            "marca_id": row[3],
            "escuela_id": row[4],
            "sku": row[5],
            "categoria_nombre": row[6],
            "marca_nombre": row[7],
            "escuela_nombre": row[8],
            "nivel_educativo_nombre": row[9],
            "producto_genero": row[10],
            "tipo_prenda_nombre": row[11],
            "tipo_pieza_nombre": row[12],
            "producto_nombre": row[13],
            "producto_nombre_base": row[14],
            "producto_descripcion": row[15],
            "nombre_legacy": row[16],
            "origen_legacy": row[17],
            "talla": row[18],
            "color": row[19],
            "precio_venta": row[20],
            "costo_referencia": row[21],
            "stock_actual": row[22],
            "apartado_cantidad": row[23],
            "producto_activo": row[24],
            "variante_activo": row[25],
            "fallback_importacion": row[26],
        }
    if len(row) == 25:
        return {
            "variante_id": row[0],
            "producto_id": row[1],
            "categoria_id": row[2],
            "marca_id": row[3],
            "escuela_id": row[4],
            "sku": row[5],
            "categoria_nombre": row[6],
            "marca_nombre": row[7],
            "escuela_nombre": row[8],
            "nivel_educativo_nombre": None,
            "producto_genero": None,
            "tipo_prenda_nombre": row[9],
            "tipo_pieza_nombre": row[10],
            "producto_nombre": row[11],
            "producto_nombre_base": row[12],
            "producto_descripcion": row[13],
            "nombre_legacy": row[14],
            "origen_legacy": row[15],
            "talla": row[16],
            "color": row[17],
            "precio_venta": row[18],
            "costo_referencia": row[19],
            "stock_actual": row[20],
            "apartado_cantidad": row[21],
            "producto_activo": row[22],
            "variante_activo": row[23],
            "fallback_importacion": row[24],
        }
    raise ValueError(f"Formato de snapshot de catalogo no soportado: {len(row)} columnas")


def build_catalog_table_values(visible_rows: list[dict[str, object]]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            row["sku"],
            row["escuela_nombre"],
            row["tipo_prenda_nombre"],
            row["tipo_pieza_nombre"],
            row["marca_nombre"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            row["precio_venta"],
            row["stock_actual"],
            row["apartado_cantidad"],
            row["variante_estado"],
        )
        for row in visible_rows
    )
