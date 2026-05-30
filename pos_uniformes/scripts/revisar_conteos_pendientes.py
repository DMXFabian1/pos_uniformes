"""Revisa (y opcionalmente descarta) conteos pendientes envenenados.

Contexto: hubo un bug donde `registrar_conteo` calculaba la diferencia contra
`stock_actual` (total) en vez de `stock_tienda`. Los conteos pendientes
(ajustado=False) registrados ANTES del fix tienen `stock_sistema` y `diferencia`
mal calculados. Si se confirman, descuadran el inventario.

Uso:
    # Solo reporte (no modifica nada):
    python -m pos_uniformes.scripts.revisar_conteos_pendientes

    # Descartar (marcar ajustado=True SIN aplicar el ajuste al stock):
    python -m pos_uniformes.scripts.revisar_conteos_pendientes --descartar

Descartar NO toca el stock: solo saca los conteos de la lista de pendientes
para que se puedan re-contar con el cálculo correcto.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import ConteoInventario, Variante


def main() -> None:
    descartar = "--descartar" in sys.argv

    with get_session() as session:
        conteos = list(session.scalars(
            select(ConteoInventario)
            .options(joinedload(ConteoInventario.variante))
            .where(ConteoInventario.ajustado.is_(False))
            .order_by(ConteoInventario.contado_at.desc())
        ).unique().all())

        if not conteos:
            print("No hay conteos pendientes. Nada que revisar.")
            return

        print(f"Conteos pendientes (ajustado=False): {len(conteos)}\n")
        print(f"{'ID':>5}  {'SKU':<12} {'sistema':>8} {'fisico':>7} {'dif':>6}  contado_por")
        print("-" * 70)
        for c in conteos:
            sku = c.variante.sku if c.variante else "?"
            print(
                f"{c.id:>5}  {sku:<12} {c.stock_sistema:>8} {c.stock_fisico:>7} "
                f"{c.diferencia:>+6}  {c.contado_por}"
            )

        if not descartar:
            print(
                "\nEsto es solo un reporte. Estos conteos pueden tener diferencias "
                "mal calculadas (bug previo)."
                "\nPara descartarlos (sin tocar el stock) y re-contar, corre de nuevo "
                "con:  --descartar"
            )
            return

        for c in conteos:
            c.ajustado = True
        session.commit()
        print(
            f"\n✓ {len(conteos)} conteos pendientes descartados (marcados como "
            "resueltos sin aplicar ajuste). El stock NO se modificó."
            "\nYa puedes re-contar con el cálculo corregido."
        )


if __name__ == "__main__":
    main()
