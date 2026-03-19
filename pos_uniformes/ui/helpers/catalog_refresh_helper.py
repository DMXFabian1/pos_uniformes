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
            "tipo_prenda_nombre": row[9] or "-",
            "tipo_pieza_nombre": row[10] or "-",
            "producto_nombre": sanitize_product_display_name(row[11]),
            "producto_nombre_base": row[12],
            "producto_descripcion": row[13],
            "nombre_legacy": row[14],
            "origen_legacy": bool(row[15]),
            "talla": row[16],
            "color": row[17],
            "precio_venta": row[18],
            "costo_referencia": row[19],
            "stock_actual": row[20],
            "apartado_cantidad": row[21],
            "producto_activo": row[22],
            "variante_activo": row[23],
            "producto_estado": "ACTIVO" if row[22] else "INACTIVO",
            "variante_estado": "ACTIVA" if row[23] else "INACTIVA",
            "origen_etiqueta": "LEGACY" if row[15] else "NUEVO",
            "fallback_importacion": bool(row[24]),
            "fallback_text": "fallback" if bool(row[24]) else "",
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
