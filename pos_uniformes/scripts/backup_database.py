"""Respaldo manual o programado de PostgreSQL para POS Uniformes."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services.backup_service import create_backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera un respaldo de la base PostgreSQL de POS Uniformes.")
    parser.add_argument(
        "--output-dir",
        default="backups/database",
        help="Directorio donde se guardara el respaldo. Default: backups/database",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "custom"),
        default="plain",
        help="Formato del respaldo. 'plain' genera .sql, 'custom' genera .dump",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Cantidad de dias que se conservaran respaldos del mismo formato. Default: 7",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    backup_file, deleted_files = create_backup(
        output_dir=output_dir,
        dump_format=args.format,
        retention_days=args.retention_days,
    )
    print(f"Respaldo generado: {backup_file}")
    if deleted_files:
        print("Respaldos eliminados por rotacion:")
        for deleted_file in deleted_files:
            print(f"- {deleted_file}")
    else:
        print("Rotacion: no se eliminaron respaldos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
