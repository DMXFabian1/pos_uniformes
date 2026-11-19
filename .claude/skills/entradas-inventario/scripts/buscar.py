"""Buscar tallas para armar un plan: SKU, existencia por partes, costo y precio. SOLO LECTURA.

Uso (desde la raíz del repo):
  "$PY" .claude/skills/entradas-inventario/scripts/buscar.py "golpe blanco" [--escuela X] [--talla CH] [--env-file …]
  "$PY" .claude/skills/entradas-inventario/scripts/buscar.py --sku SKU005703 [--movimientos 10]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _inventario as inv  # noqa: E402
from _inventario import _comun  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _comun.agregar_argumentos_db(ap)
    ap.add_argument("texto", nargs="*", help="palabras del nombre, color o escuela (sin importar acentos)")
    ap.add_argument("--sku")
    ap.add_argument("--escuela")
    ap.add_argument("--talla")
    ap.add_argument("--inactivas", action="store_true", help="incluir tallas o productos dados de baja")
    ap.add_argument("--movimientos", type=int, default=0, help="últimos N movimientos de cada talla encontrada")
    ap.add_argument("--limite", type=int, default=40)
    args = ap.parse_args()
    if not args.texto and not args.sku:
        ap.error("da un texto o --sku")

    engine = _comun.motor(args, solo_lectura=True)
    with engine.connect() as c:
        if args.sku:
            res = inv.filas(c, "upper(v.sku) = upper(:s)", {"s": args.sku.strip()})
        else:
            res = inv.buscar_texto(c, " ".join(args.texto), escuela=args.escuela, talla=args.talla,
                                   solo_activas=not args.inactivas, limite=args.limite + 1)
        if not res:
            print("Sin resultados.")
            return 1
        print(f"{'SKU':<10} {'total':>5} {'suelto':>6} {'c.alm':>5} {'c.piso':>6}  {'costo':>7} {'precio':>7}  prenda")
        for f in res[: args.limite]:
            costo = f"{f['costo_referencia']:.0f}" if f["costo_referencia"] is not None else "—"
            marcas = (" [conjunto: su número sale de sus piezas]" if f["es_conjunto"] else "") + ("" if f["activo"] else " [INACTIVA]")
            print(f"{f['sku']:<10} {inv.cifra(f['stock_actual']):>5} {inv.cifra(f['tienda']):>6} {f['bodega']:>5} {f['piso']:>6}"
                  f"  {costo:>7} {f['precio_venta']:>7.0f}  {inv.nombre_talla(f)}{marcas}")
            if args.movimientos:
                movs = c.execute(inv.text("""select created_at, tipo_movimiento, cantidad, stock_posterior,
                        coalesce(referencia,''), coalesce(creado_por,'') from movimiento_inventario
                        where variante_id = :v order by created_at desc, id desc limit :n"""),
                                 {"v": f["id"], "n": args.movimientos}).fetchall()
                for cuando, tipo, cant, post, ref, quien in movs:
                    print(f"      {cuando.astimezone(inv.ZONA):%d-%b %H:%M} {tipo:<17} {cant:+4d} → {inv.cifra(post):>4}  {ref[:24]} {quien[:20]}")
        print("(suelto = en tienda fuera de cajas, lo que mide el conteo; c.alm / c.piso = dentro de cajas del almacén / del piso)")
        if len(res) > args.limite:
            print(f"… hay más; afina la búsqueda (--escuela, --talla).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
