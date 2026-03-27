"""Runner listo para tarea programada de respaldos automaticos."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services.backup_service import (  # noqa: E402
    automatic_backup_status_path,
    run_automatic_backup,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un respaldo automatico de PostgreSQL y actualiza el estado visible para Configuracion."
    )
    parser.add_argument(
        "--output-dir",
        default="backups/database",
        help="Directorio donde se guardara el respaldo. Default: backups/database",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "custom"),
        default="custom",
        help="Formato del respaldo. 'custom' genera .dump y es el recomendado para tarea programada.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=14,
        help="Cantidad de dias que se conservaran respaldos del mismo formato. Default: 14",
    )
    parser.add_argument(
        "--external-dir",
        default=None,
        help=(
            "Carpeta opcional para copiar el respaldo a una segunda ubicacion. "
            "Si se omite, se usa POS_UNIFORMES_BACKUP_EXTERNAL_DIR cuando exista."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    external_dir = Path(args.external_dir).expanduser().resolve() if args.external_dir else None
    try:
        backup_file, deleted_files, status = run_automatic_backup(
            output_dir=output_dir,
            dump_format=args.format,
            retention_days=args.retention_days,
            external_dir=external_dir,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Fallo respaldo automatico: {exc}", file=sys.stderr)
        print(
            f"Estado actualizado en: {automatic_backup_status_path(output_dir)}",
            file=sys.stderr,
        )
        return 1

    print(f"Respaldo automatico generado: {backup_file}")
    print(f"Estado actualizado en: {automatic_backup_status_path(output_dir)}")
    if status.external_copy_dir is None:
        print("Copia externa: no configurada.")
    elif status.external_last_error:
        print(f"Copia externa con advertencia: {status.external_last_error}", file=sys.stderr)
    elif status.external_last_backup_path is not None:
        print(f"Copia externa actualizada: {status.external_last_backup_path}")
    if deleted_files:
        print("Respaldos eliminados por rotacion:")
        for deleted_file in deleted_files:
            print(f"- {deleted_file}")
    else:
        print("Rotacion: no se eliminaron respaldos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
