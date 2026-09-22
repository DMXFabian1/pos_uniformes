"""Revisa (y opcionalmente sube a cero) las tallas con existencia en negativo.

Una talla en negativo no es un misterio: es la tienda diciendo *"vendí más de
lo que tú creías que había"*. Físicamente nadie tiene −3 calcetas. El número
quedó mal porque esa talla nunca se contó, o se contó hace mucho.

Subirlas a cero **no arregla el inventario** — solo deja de mentir hacia abajo.
Lo que de verdad arregla es contar, y por eso el reporte sale ordenado como
lista de trabajo: lo más rojo primero.

Uso:
    # Solo reporte (no modifica nada):
    python -m pos_uniformes.scripts.revisar_stock_negativo

    # Subir a cero, dejando un ajuste trazable por cada una:
    python -m pos_uniformes.scripts.revisar_stock_negativo --aplicar

Los conjuntos (Pants 3pz, Chamarra) no se tocan a mano: su existencia es la de
sus piezas, así que se vuelven a calcular con `conjunto_service`.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    ConjuntoComponente,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    Variante,
)
from pos_uniformes.services import conjunto_service
from pos_uniformes.services.inventario_service import InventarioService

#: Quién firma los ajustes de esta reconciliación.
FIRMA = "RECONCILIACION"


def _dias_desde(momento) -> str:
    if momento is None:
        return "sin movimientos"
    dias = (datetime.now(timezone.utc) - momento).days
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    return f"hace {dias} días"


def _ultimo_movimiento(session, variante_id: int):
    return session.execute(
        select(MovimientoInventario.created_at, MovimientoInventario.tipo_movimiento)
        .where(MovimientoInventario.variante_id == variante_id)
        .order_by(desc(MovimientoInventario.created_at))
        .limit(1)
    ).first()


def listar_negativas(session) -> list[Variante]:
    """Las tallas vivas cuya existencia quedó por debajo de cero, la peor primero."""
    return list(
            session.scalars(
                select(Variante)
                .options(joinedload(Variante.producto).joinedload(Producto.escuela))
                .join(Producto, Producto.id == Variante.producto_id)
                .where(
                    Variante.activo.is_(True),
                    Producto.activo.is_(True),
                    Variante.stock_actual < 0,
                )
                .order_by(Variante.stock_actual)
            ).unique().all()
    )


def ids_de_conjuntos(session) -> set[int]:
    """Productos que son conjuntos: su existencia se recalcula, no se ajusta."""
    return {int(pid) for pid in session.scalars(select(ConjuntoComponente.conjunto_id)).all()}


def reconciliar(session) -> tuple[int, int]:
    """Sube a cero lo que está en rojo y recalcula los conjuntos.

    Devuelve `(tallas ajustadas, conjuntos recalculados)`. Cada ajuste deja su
    movimiento, firmado, para poder auditarlo después."""
    conjuntos = ids_de_conjuntos(session)
    ajustadas = 0
    recalculadas = 0
    for v in listar_negativas(session):
        if v.producto_id in conjuntos:
            recalculadas += conjunto_service.sincronizar_conjunto(
                session, v.producto_id, creado_por=FIRMA
            )
            continue
        InventarioService.registrar_movimiento(
            session=session,
            variante=v,
            tipo_movimiento=TipoMovimientoInventario.AJUSTE_ENTRADA,
            cantidad=-v.stock_actual,
            referencia=FIRMA,
            observacion=(
                "Reconciliación: estaba en negativo porque se vendió más de lo "
                "que el sistema creía. Queda en cero hasta que se cuente."
            ),
            creado_por=FIRMA,
        )
        ajustadas += 1
    return ajustadas, recalculadas


def main() -> None:
    aplicar = "--aplicar" in sys.argv

    with get_session() as session:
        variantes = listar_negativas(session)

        if not variantes:
            print("Ninguna talla está en negativo. El número no miente hacia abajo.")
            return

        conjuntos = ids_de_conjuntos(session)

        en_rojo = sum(v.stock_actual for v in variantes)
        print(f"Tallas en negativo: {len(variantes)}   piezas en rojo: {en_rojo}\n")
        print(f"{'stock':>6}  {'talla':<10} {'prenda':<42} {'escuela':<20} último movimiento")
        print("-" * 110)

        de_conjunto = []
        for v in variantes:
            producto = v.producto
            escuela = producto.escuela.nombre if producto.escuela else "general"
            ultimo = _ultimo_movimiento(session, v.id)
            cuando = _dias_desde(ultimo[0]) if ultimo else "sin movimientos"
            marca = " (conjunto)" if producto.id in conjuntos else ""
            print(
                f"{v.stock_actual:>6}  {v.talla:<10} "
                f"{((producto.nombre_base or producto.nombre) + marca)[:42]:<42} "
                f"{escuela[:20]:<20} {cuando}"
            )
            if producto.id in conjuntos:
                de_conjunto.append(v)

        print()
        if de_conjunto:
            print(
                f"{len(de_conjunto)} de ellas son conjuntos: su existencia es la de sus "
                "piezas, así que se recalculan, no se ajustan."
            )

        if not aplicar:
            print("\nSolo reporte. Para subirlas a cero: --aplicar")
            print("Y para arreglarlas de verdad: contarlas. Empieza por las de arriba.")
            return

        ajustadas, recalculadas = reconciliar(session)
        session.commit()
        print(f"\nListo: {ajustadas} tallas subidas a cero, {recalculadas} conjuntos recalculados.")
        print("Cada una dejó su movimiento de ajuste, así que se puede auditar después.")


if __name__ == "__main__":
    main()
