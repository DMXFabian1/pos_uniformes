"""Descuenta del stock las ventas de la Libreta que se hicieron ANTES de que
la venta descontara sola (2026-09-14). Una sola vez.

Regla: a cada talla se le restan las ventas posteriores a su último conteo
(si nunca se contó, todas las de la Libreta). Lo que ya está descontado
(referencia libreta:N) se salta. Sin --aplicar solo enseña qué haría.

Uso:  python -m pos_uniformes.scripts.descontar_ventas_pasadas [--aplicar]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import LibretaVenta, MovimientoInventario, TipoMovimientoInventario, Variante
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.libreta_service import TIPOS_QUE_DESCUENTAN


def _aware(m: datetime | None) -> datetime | None:
    if m is None:
        return None
    return m if m.tzinfo else m.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="sin esto solo enseña")
    args = parser.parse_args(argv)

    with get_session() as session:
        ventas = list(session.scalars(
            select(LibretaVenta).where(LibretaVenta.tipo.in_(TIPOS_QUE_DESCUENTAN)).order_by(LibretaVenta.id)
        ).all())
        ya = set(session.execute(
            select(MovimientoInventario.referencia, MovimientoInventario.variante_id)
            .where(MovimientoInventario.referencia.like("libreta:%"))
        ).all())
        por_sku = {v.sku: v for v in session.scalars(select(Variante)).all() if v.sku}
        plan: list[tuple[LibretaVenta, Variante, int]] = []
        saltadas_por_conteo = 0
        sin_sku = 0
        for e in ventas:
            for linea in e.detalle or []:
                sku = str(linea.get("sku") or "").strip()
                cantidad = int(linea.get("cantidad") or 0)
                v = por_sku.get(sku)
                if not sku or cantidad <= 0 or v is None:
                    sin_sku += 1
                    continue
                if (f"libreta:{e.id}", v.id) in ya:
                    continue
                ultimo = _aware(v.ultimo_conteo_at)
                if ultimo is not None and _aware(e.created_at) <= ultimo:
                    saltadas_por_conteo += 1   # ese conteo ya la vio
                    continue
                plan.append((e, v, cantidad))

        piezas = sum(c for _, _, c in plan)
        tallas = {v.id for _, v, _ in plan}
        negativos = defaultdict(int)
        for _, v, c in plan:
            negativos[v.id] += c
        quedan_negativas = sum(1 for vid, c in negativos.items() if session.get(Variante, vid).stock_actual - c < 0)
        print(f"Ventas de la Libreta: {len(ventas)} · renglones a descontar: {len(plan)} ({piezas} piezas en {len(tallas)} tallas)")
        print(f"Saltados: {saltadas_por_conteo} porque un conteo posterior ya los vio · {sin_sku} sin talla en el catálogo")
        print(f"Tallas que quedarían en negativo (hay que recontarlas): {quedan_negativas}")
        if not args.aplicar:
            print("\nSolo fue un vistazo. Con --aplicar se descuenta de verdad.")
            return 0
        hechas = 0
        for e, v, cantidad in plan:
            tipo = TipoMovimientoInventario.SALIDA_VENTA if e.tipo == "venta" else TipoMovimientoInventario.APARTADO_RESERVA
            InventarioService.registrar_movimiento(
                session, v, tipo, -cantidad, referencia=f"libreta:{e.id}",
                observacion=f"{e.tipo} del {e.created_at:%d/%m} descontada al arrancar (2026-09-14)",
                creado_por="descontar_ventas_pasadas", allow_negative_stock=True,
            )
            hechas += 1
        session.commit()
        print(f"Listo: {hechas} renglones descontados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
