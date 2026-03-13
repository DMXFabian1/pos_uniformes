"""Verifica conexion y version de esquema antes de abrir POS Uniformes."""

from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.preflight import DatabasePreflightError, assert_database_ready


def main() -> int:
    try:
        status = assert_database_ready()
    except DatabasePreflightError as exc:
        print("PRECHECK FAILED")
        print(exc)
        return 1

    print("PRECHECK OK")
    print(f"Revision actual: {', '.join(status.current_heads)}")
    print(f"Revision esperada: {', '.join(status.expected_heads)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
