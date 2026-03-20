"""Helpers puros para snapshot y filas visibles del listado de Catalogo."""

from __future__ import annotations

from pos_uniformes.utils.product_name import sanitize_product_display_name


def build_catalog_snapshot_rows(rows: list[tuple[object, ...]]) -> list[dict[str, object]]:
    return [
        {
            "variante_id": row[0],
            "producto_id": row[1],
            "categoria_id": row[2],
            "marca_id": row[3],
            "escuela_id": row[4],
            "sku": row[5],
            "categoria_nombre": row[6],
            "marca_nombre": row[7],
            "escuela_nombre": row[8] or "General",
            "nivel_educativo_nombre": row[9] or "Sin nivel",
            "producto_genero": row[10] or "",
            "tipo_prenda_nombre": row[11] or "-",
            "tipo_pieza_nombre": row[12] or "-",
            "producto_nombre": sanitize_product_display_name(row[13]),
            "producto_nombre_base": row[14],
            "producto_descripcion": row[15],
            "nombre_legacy": row[16],
            "origen_legacy": bool(row[17]),
            "talla": row[18],
            "color": row[19],
            "precio_venta": row[20],
            "costo_referencia": row[21],
            "stock_actual": row[22],
            "apartado_cantidad": row[23],
            "producto_activo": row[24],
            "variante_activo": row[25],
            "producto_estado": "ACTIVO" if row[24] else "INACTIVO",
            "variante_estado": "ACTIVA" if row[25] else "INACTIVA",
            "origen_etiqueta": "LEGACY" if row[17] else "NUEVO",
            "fallback_importacion": bool(row[26]),
            "fallback_text": "fallback" if bool(row[26]) else "",
        }
        for row in rows
    ]


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
