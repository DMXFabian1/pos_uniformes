"""Reconstruye la trazabilidad formal de la importacion legacy ya aplicada."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys

from sqlalchemy import func, select

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AtributoProducto,
    Escuela,
    ImportacionCatalogo,
    ImportacionCatalogoFila,
    ImportacionCatalogoIncidencia,
    Marca,
    MovimientoInventario,
    NivelEducativo,
    Producto,
    ProductoAsset,
    TipoPieza,
    TipoPrenda,
    Variante,
)
from pos_uniformes.utils.legacy_paths import detect_legacy_sqlite_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_source_path = detect_legacy_sqlite_path()
    parser = argparse.ArgumentParser(
        description="Reconstruye la trazabilidad formal de una importacion legacy ya aplicada.",
    )
    parser.add_argument(
        "--legacy-source-path",
        default=str(default_source_path),
        help=(
            "Ruta que se registrara como fuente original del catalogo legacy. "
            "Si no se indica, se intenta detectar en la carpeta actual, "
            "en data/productos.db, en Gestor_de_Inventarios/data/productos.db "
            "o en Downloads/productos.db."
        ),
    )
    return parser.parse_args(argv)


def _latest_import_report() -> str | None:
    base_dir = Path(__file__).resolve().parents[1] / "exports" / "imports"
    candidates = sorted(base_dir.glob("*/legacy_catalog_import_summary.json"))
    if not candidates:
        return None
    return str(candidates[-1])


def main() -> None:
    args = parse_args()
    legacy_source_path = Path(args.legacy_source_path).expanduser()

    with get_session() as session:
        existing_batch = session.scalar(select(ImportacionCatalogo.id).limit(1))
        if existing_batch is not None:
            raise SystemExit("Ya existe trazabilidad de importacion registrada en esta base.")

        legacy_variants = session.scalars(
            select(Variante).where(Variante.origen_legacy.is_(True)).order_by(Variante.sku)
        ).all()
        if not legacy_variants:
            raise SystemExit("No hay variantes legacy para reconstruir la trazabilidad.")

        assets_created = session.scalar(
            select(func.count(ProductoAsset.id))
            .join(ProductoAsset.variante)
            .where(Variante.origen_legacy.is_(True))
        ) or 0
        stock_movements_created = session.scalar(
            select(func.count(MovimientoInventario.id))
            .join(MovimientoInventario.variante)
            .where(Variante.origen_legacy.is_(True), MovimientoInventario.referencia == "LEGACY-IMPORT")
        ) or 0
        max_legacy_sku = 0
        families_created = len({int(variante.producto_id) for variante in legacy_variants})
        report_path = _latest_import_report()

        batch = ImportacionCatalogo(
            fuente_nombre=legacy_source_path.name,
            fuente_ruta=str(legacy_source_path),
            reporte_ruta=report_path,
            filas_leidas=len(legacy_variants),
            familias_creadas=families_created,
            variantes_creadas=len(legacy_variants),
            assets_creados=int(assets_created),
            movimientos_stock_creados=int(stock_movements_created),
            observaciones="Trazabilidad reconstruida despues de una importacion legacy previa.",
        )
        session.add(batch)
        session.flush()
        batch_id = int(batch.id)

        family_conflicts: dict[tuple[str, ...], list[dict[str, object]]] = {}
        fallback_count = 0

        for variante in legacy_variants:
            producto = variante.producto
            parsed_sku = 0
            normalized_sku = (variante.sku or "").strip().upper()
            if normalized_sku.startswith("SKU") and normalized_sku[3:].isdigit():
                parsed_sku = int(normalized_sku[3:])
            max_legacy_sku = max(max_legacy_sku, parsed_sku)

            row = ImportacionCatalogoFila(
                importacion=batch,
                legacy_sku=variante.sku,
                legacy_nombre=variante.nombre_legacy or producto.nombre,
                legacy_nombre_base=producto.nombre_base,
                legacy_talla=variante.talla,
                legacy_color=variante.color,
                legacy_precio=variante.precio_venta,
                legacy_inventario=variante.stock_actual,
                legacy_last_modified=variante.legacy_last_modified,
                producto_id=producto.id,
                variante_id=variante.id,
                producto_fallback=False,
                clave_familia=" | ".join(
                    [
                        producto.nombre_base or "-",
                        producto.marca.nombre if producto.marca else "-",
                        producto.escuela.nombre if producto.escuela else "-",
                        producto.tipo_prenda.nombre if producto.tipo_prenda else "-",
                        producto.tipo_pieza.nombre if producto.tipo_pieza else "-",
                        producto.nivel_educativo.nombre if producto.nivel_educativo else "-",
                        producto.atributo.nombre if producto.atributo else "-",
                        producto.genero or "-",
                    ]
                ),
            )
            session.add(row)

            conflict_key = (
                producto.nombre_base,
                producto.marca.nombre if producto.marca else "",
                producto.escuela.nombre if producto.escuela else "",
                producto.tipo_prenda.nombre if producto.tipo_prenda else "",
                producto.tipo_pieza.nombre if producto.tipo_pieza else "",
                producto.nivel_educativo.nombre if producto.nivel_educativo else "",
                producto.atributo.nombre if producto.atributo else "",
                producto.genero or "",
                variante.talla,
                variante.color,
            )
            family_conflicts.setdefault(conflict_key, []).append(
                {
                    "sku": variante.sku,
                    "producto_id": int(producto.id),
                    "producto_nombre": producto.nombre,
                    "variante_id": int(variante.id),
                }
            )

        session.flush()

        for conflict_key, rows in family_conflicts.items():
            if len(rows) <= 1:
                continue
            fallback_count += len(rows) - 1
            issue = ImportacionCatalogoIncidencia(
                importacion=batch,
                severidad="WARNING",
                tipo="DUPLICATE_VARIANT_FALLBACK",
                descripcion=(
                    "Se detectaron SKUs legacy con la misma combinacion semantica de familia+talla+color; "
                    "se conservaron separandolos en productos fallback."
                ),
                detalle_json=json.dumps(
                    {
                        "conflict_key": list(conflict_key),
                        "rows": rows,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
            )
            session.add(issue)

            primary_sku = rows[0]["sku"]
            for item in rows[1:]:
                mapped_row = session.scalar(
                    select(ImportacionCatalogoFila).where(
                        ImportacionCatalogoFila.importacion_id == batch.id,
                        ImportacionCatalogoFila.legacy_sku == item["sku"],
                    )
                )
                if mapped_row is not None:
                    mapped_row.producto_fallback = True
                    session.add(mapped_row)

        batch.duplicados_fallback = fallback_count
        batch.max_sku_legacy = max_legacy_sku
        batch.finished_at = max(
            (variante.legacy_last_modified for variante in legacy_variants if variante.legacy_last_modified is not None),
            default=None,
        )
        session.add(batch)
        session.commit()

    print(f"Trazabilidad backfill lista. Batch={batch_id} filas={len(legacy_variants)} duplicados_fallback={fallback_count}")


if __name__ == "__main__":
    main()
