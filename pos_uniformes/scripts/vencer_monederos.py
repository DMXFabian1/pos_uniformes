"""Proceso diario del monedero de clientes.

Lo corre la tarea «POS Monederos» cada noche (ver postactualizacion.py):

1. Asienta como `expiracion` el saldo de cada crédito que ya cumplió sus 12
   meses. El saldo disponible ya lo excluye desde su fecha aunque esto no
   haya corrido; esto lo deja en el libro para reportes e historial.
2. Red de seguridad: acredita el cashback de ventas con cliente de los
   últimos 30 días que se quedaron sin él (p. ej. falló al sincronizar).

Las dos cosas son idempotentes: correrlo dos veces no duplica nada.

    python -m pos_uniformes.scripts.vencer_monederos
    python -m pos_uniformes.scripts.vencer_monederos --solo-revisar
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger("vencer_monederos")


def correr(session, *, aplicar: bool = True) -> tuple[int, int]:
    from pos_uniformes.services import monedero_service as mon

    try:
        vencidos = mon.procesar_vencimientos(session)
        acreditados = mon.acreditar_faltantes(session, dias=30)
        if aplicar:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    return vencidos, acreditados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--solo-revisar", action="store_true", help="Calcula pero no guarda nada.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from pos_uniformes.database.connection import get_session

    try:
        with get_session() as session:
            vencidos, acreditados = correr(session, aplicar=not args.solo_revisar)
    except Exception:  # noqa: BLE001
        logger.exception("Monederos: el proceso diario falló")
        return 1
    modo = "revisión (sin guardar)" if args.solo_revisar else "aplicado"
    logger.info("Monederos %s: %s vencimientos asentados, %s cashback repuestos", modo, vencidos, acreditados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
