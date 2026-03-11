"""Importa el catalogo legacy de SQLite a PostgreSQL."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import get_session
from pos_uniformes.importers.legacy_products_importer import LegacyProductsImporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Importa productos legacy SQLite hacia POS Uniformes.")
    parser.add_argument(
        "--sqlite-path",
        default="/Users/danielfabian/Downloads/productos.db",
        help="Ruta a la base SQLite legacy.",
    )
    parser.add_argument(
        "--report-dir",
        default="exports/imports",
        help="Directorio donde se guardara el resumen de importacion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    importer = LegacyProductsImporter(
        sqlite_path=Path(args.sqlite_path),
        report_dir=Path(args.report_dir),
    )
    with get_session() as session:
        summary = importer.run(session)

    print(f"Productos leidos: {summary.products_read}")
    print(f"Familias creadas: {summary.product_families_created}")
    print(f"Variantes creadas: {summary.variants_created}")
    print(f"Assets creados: {summary.assets_created}")
    print(f"Movimientos de stock: {summary.stock_movements_created}")
    print(f"SKU legacy maximo: {summary.max_legacy_sku}")
    print(f"Reporte: {summary.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
