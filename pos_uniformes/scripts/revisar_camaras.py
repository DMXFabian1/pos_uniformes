"""Imprime la revisión del contador de personas (lo mismo que `/camaras` en el bot).

    python -m pos_uniformes.scripts.revisar_camaras [dias]
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import camaras_revision_service as rev

    argv = sys.argv[1:] if argv is None else argv
    dias = int(argv[0]) if argv else 7
    with get_session() as session:
        print(rev.texto(rev.revisar(session, dias=dias)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
