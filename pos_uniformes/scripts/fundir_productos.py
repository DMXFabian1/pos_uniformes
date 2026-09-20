"""Funde dos productos que son la misma prenda (nombre repetido, tallas
partidas en dos fichas). Las tallas del que se va pasan al que se queda con
sus SKUs intactos (las etiquetas impresas siguen sirviendo); si una talla ya
existe en el destino, su existencia se suma a la del destino con un
movimiento de inventario y la talla repetida queda inactiva bajo el origen
(talla+color son únicos por producto), con su SKU para la historia. El producto vacío
queda inactivo con la nota "fundido en #N".

Uso:  python -m pos_uniformes.scripts.fundir_productos --de 426 --en 394 [--aplicar]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, TipoMovimientoInventario, Variante


def planear(session, *, de: int, en: int) -> dict:
    origen, destino = session.get(Producto, de), session.get(Producto, en)
    if origen is None or destino is None:
        raise SystemExit("No existe alguno de los dos productos.")
    if origen.id == destino.id:
        raise SystemExit("Son el mismo producto.")
    existentes = {(v.talla, v.color): v for v in session.scalars(select(Variante).where(Variante.producto_id == destino.id)).all()}
    mover, sumar = [], []
    for v in session.scalars(select(Variante).where(Variante.producto_id == origen.id).order_by(Variante.id)).all():
        clave = (v.talla, v.color)
        (sumar if clave in existentes else mover).append((v, existentes.get(clave)))
    return {"origen": origen, "destino": destino, "mover": mover, "sumar": sumar}


def aplicar(session, plan: dict, *, quien: str = "fundir_productos") -> None:
    from pos_uniformes.services.inventario_service import InventarioService

    origen, destino = plan["origen"], plan["destino"]
    for v, _ in plan["mover"]:
        v.producto_id = destino.id
        session.add(v)
    for v, existente in plan["sumar"]:
        if int(v.stock_actual) != 0:
            InventarioService.registrar_movimiento(
                session, existente, TipoMovimientoInventario.AJUSTE_ENTRADA if v.stock_actual > 0 else TipoMovimientoInventario.AJUSTE_SALIDA,
                int(v.stock_actual), referencia=f"fundido:{origen.id}", observacion=f"Existencia de {v.sku} ({origen.nombre}) al fundirse", creado_por=quien,
                allow_negative_stock=True,
            )
            InventarioService.registrar_movimiento(
                session, v, TipoMovimientoInventario.AJUSTE_SALIDA if v.stock_actual > 0 else TipoMovimientoInventario.AJUSTE_ENTRADA,
                -int(v.stock_actual), referencia=f"fundido:{destino.id}", observacion=f"Pasa a {existente.sku} ({destino.nombre}) al fundirse", creado_por=quien,
                allow_negative_stock=True,
            )
        # No puede vivir bajo el destino (talla+color únicos por producto):
        # se queda bajo el origen inactivo, inactiva, con su SKU para la historia.
        v.activo = False
        session.add(v)
    origen.activo = False
    origen.descripcion = f"{(origen.descripcion or '').strip()} [fundido en #{destino.id}]".strip()
    session.add(origen)
    session.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--de", type=int, required=True, help="el que desaparece")
    parser.add_argument("--en", type=int, required=True, help="el que se queda")
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)
    with get_session() as session:
        plan = planear(session, de=args.de, en=args.en)
        o, d = plan["origen"], plan["destino"]
        print(f"#{o.id} {o.nombre!r} → #{d.id} {d.nombre!r}")
        for v, _ in plan["mover"]:
            print(f"  pasa  {v.sku} talla {v.talla} {v.color} stock={v.stock_actual}")
        for v, ex in plan["sumar"]:
            print(f"  talla repetida {v.talla} {v.color}: {v.sku} (stock {v.stock_actual}) queda inactiva; su existencia pasa a {ex.sku} (stock {ex.stock_actual})")
        if not args.aplicar:
            print("\nSolo fue un vistazo. Con --aplicar se funden de verdad.")
            return 0
        aplicar(session, plan)
        session.commit()
        print(f"\nListo: #{o.id} inactivo, sus tallas bajo #{d.id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
