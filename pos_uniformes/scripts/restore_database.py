"""Restaura un respaldo .dump de PostgreSQL para POS Uniformes."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services.backup_service import restore_backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restaura un respaldo .dump sobre la base PostgreSQL de POS Uniformes.")
    parser.add_argument("backup_file", help="Ruta al archivo .dump que se quiere restaurar.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backup_file = Path(args.backup_file).expanduser().resolve()
    restore_backup(backup_file)
    print(f"Respaldo restaurado: {backup_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
