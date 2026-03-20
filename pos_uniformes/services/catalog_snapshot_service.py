"""Carga el snapshot base del listado de Catalogo."""

from __future__ import annotations

from pos_uniformes.ui.helpers.catalog_refresh_helper import build_catalog_snapshot_rows


def load_catalog_snapshot_rows(session) -> list[dict[str, object]]:
    return build_catalog_snapshot_rows(_execute_catalog_snapshot_query(session))


def _execute_catalog_snapshot_query(session) -> list[tuple[object, ...]]:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import (
        Apartado,
        ApartadoDetalle,
        Categoria,
        Escuela,
        EstadoApartado,
        ImportacionCatalogoFila,
        Marca,
        NivelEducativo,
        Producto,
        TipoPieza,
        TipoPrenda,
        Variante,
    )

    layaway_reserved_subquery = (
        select(
            ApartadoDetalle.variante_id.label("variante_id"),
            func.coalesce(func.sum(ApartadoDetalle.cantidad), 0).label("apartado_cantidad"),
        )
        .join(ApartadoDetalle.apartado)
        .where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
        .group_by(ApartadoDetalle.variante_id)
        .subquery()
    )

    return list(
        session.execute(
            select(
                Variante.id,
                Producto.id,
                Categoria.id,
                Marca.id,
                Escuela.id,
                Variante.sku,
                Categoria.nombre,
                Marca.nombre,
                Escuela.nombre,
                NivelEducativo.nombre,
                Producto.genero,
                TipoPrenda.nombre,
                TipoPieza.nombre,
                Producto.nombre,
                Producto.nombre_base,
                Producto.descripcion,
                Variante.nombre_legacy,
                Variante.origen_legacy,
                Variante.talla,
                Variante.color,
                Variante.precio_venta,
                Variante.costo_referencia,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Producto.activo,
                Variante.activo,
                func.coalesce(ImportacionCatalogoFila.producto_fallback, False),
            )
            .join(Variante.producto)
            .join(Producto.categoria)
            .join(Producto.marca)
            .outerjoin(Producto.escuela)
            .outerjoin(Producto.nivel_educativo)
            .outerjoin(Producto.tipo_prenda)
            .outerjoin(Producto.tipo_pieza)
            .outerjoin(ImportacionCatalogoFila, ImportacionCatalogoFila.variante_id == Variante.id)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
            .order_by(
                Categoria.nombre.asc(),
                Escuela.nombre.asc().nullslast(),
                Marca.nombre.asc(),
                Producto.nombre.asc(),
                Variante.sku.asc(),
            )
        ).all()
    )
