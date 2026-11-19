"""Tallas en negativo (y conjuntos desfasados): la lista de qué contar. SOLO LECTURA.

Un negativo es la tienda diciendo «vendí más de lo que creías que había»: nadie tiene −3
corbatines. Se arregla CONTANDO, no subiendo a cero. Sale agrupado por escuela y prenda,
lo más rojo primero, con lo que hay en cajas de bodega (el conteo mide solo la tienda),
cuánto se vendió en 30 días y cuándo se contó por última vez.

Los conjuntos (Pants 3pz, Chamarra con receta) no se cuentan: su número sale de sus piezas.
Con --desfasados se listan las tallas de conjuntos cuyo número NO coincide con el de sus
piezas (se corrigen con "recalcular_conjuntos": "todos" en el plan de aplicar_inventario.py).

Uso (desde la raíz del repo):
  "$PY" .claude/skills/entradas-inventario/scripts/negativos.py --env-file "<env de la caja>" \
      [--escuela UVEG] [--buscar corbatin] [--plantilla <scratchpad>/conteo.json] [--desfasados] [--reconciliados]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _inventario as inv  # noqa: E402
from _inventario import _comun  # noqa: E402


def _cuando(dt) -> str:
    if dt is None:
        return "nunca"
    dias = (datetime.now(inv.ZONA) - dt).days
    return "hoy" if dias <= 0 else ("ayer" if dias == 1 else f"hace {dias} d")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _comun.agregar_argumentos_db(ap)
    ap.add_argument("--escuela", help="solo esta escuela (parte del nombre; «general» = sin escuela)")
    ap.add_argument("--buscar", help="solo prendas cuyo nombre lleve estas palabras")
    ap.add_argument("--plantilla", help="escribe un plan de conteo con «hay»: null por talla, para llenar")
    ap.add_argument("--desfasados", action="store_true", help="también conjuntos cuyo número no cuadra con sus piezas")
    ap.add_argument("--reconciliados", action="store_true",
                    help="también las tallas que el script viejo subió a 0 (RECONCILIACION) y nadie ha contado")
    args = ap.parse_args()

    engine = _comun.motor(args, solo_lectura=True)
    with engine.connect() as c:
        where = ["v.activo and p.activo", "v.stock_actual < 0"]
        params: dict = {}
        if args.escuela:
            if inv.sin_acentos(args.escuela) in {"general", "basicos", "sin escuela"}:
                where.append("p.escuela_id is null")
            else:
                where.append("translate(lower(coalesce(e.nombre,'')), 'áéíóúüñ', 'aeiouun') like :esc")
                params["esc"] = f"%{inv.sin_acentos(args.escuela)}%"
        if args.buscar:
            for i, w in enumerate(inv.sin_acentos(args.buscar).split()):
                where.append(f"translate(lower(p.nombre || ' ' || coalesce(v.color,'')), 'áéíóúüñ', 'aeiouun') like :b{i}")
                params[f"b{i}"] = f"%{w}%"
        negativas = inv.filas(c, " and ".join(where), params)

        piezas = [f for f in negativas if not f["es_conjunto"]]
        conjuntos = [f for f in negativas if f["es_conjunto"]]
        print(f"\nTallas en negativo: {len(piezas)} (−{sum(-f['stock_actual'] for f in piezas)} piezas)"
              + (f" · y {len(conjuntos)} de conjuntos, que se corrigen solos al contar sus piezas" if conjuntos else ""))

        grupos: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for f in piezas:
            grupos[f["escuela"] or "(general)"][f["producto"]].append(f)
        orden_esc = sorted(grupos, key=lambda e: sum(x["stock_actual"] for p in grupos[e].values() for x in p))
        for esc in orden_esc:
            prendas = grupos[esc]
            total = sum(x["stock_actual"] for p in prendas.values() for x in p)
            print(f"\n■ {esc}  ({sum(len(p) for p in prendas.values())} tallas, {inv.cifra(total)})")
            for prod in sorted(prendas, key=lambda p: sum(x["stock_actual"] for x in prendas[p])):
                tallas = prendas[prod]
                print(f"  {prod}")
                for f in sorted(tallas, key=lambda x: x["stock_actual"]):
                    extra = []
                    if f["bodega"]:
                        extra.append(f"en cajas del almacén {f['bodega']}")
                    if f["piso"]:
                        extra.append(f"en cajas en el piso {f['piso']}")
                    extra.append(f"vendió {f['vendidas_30d']} en 30 d")
                    extra.append(f"contada {_cuando(f['ultimo_conteo_at'])}")
                    print(f"    {f['talla']:<9} {inv.cifra(f['stock_actual']):>5}  {f['sku']}  · {' · '.join(extra)}")

        if args.reconciliados:
            ceros = c.execute(inv.text("""
                select v.sku, p.nombre, v.talla, coalesce(e.nombre,'') from variante v
                join producto p on p.id = v.producto_id left join escuela e on e.id = p.escuela_id
                where v.activo and p.activo and v.stock_actual = 0
                  and exists (select 1 from movimiento_inventario m where m.variante_id = v.id and m.referencia = 'RECONCILIACION')
                  and (v.ultimo_conteo_at is null or v.ultimo_conteo_at < (
                       select max(m.created_at) from movimiento_inventario m
                       where m.variante_id = v.id and m.referencia = 'RECONCILIACION'))
                order by 4, 2, 3""")).fetchall()
            print(f"\nEn 0 por la reconciliación de septiembre y sin contar desde entonces: {len(ceros)}")
            for sku, prod, talla, esc in ceros[:60]:
                print(f"    {sku}  {prod} {talla} · {esc or 'general'}")
            if len(ceros) > 60:
                print(f"    … y {len(ceros) - 60} más")

    if args.desfasados:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from pos_uniformes.database.models import Variante
        from pos_uniformes.services import conjunto_service as cs

        with Session(engine) as s:
            desf = []
            for p in cs.conjuntos_activos(s):
                receta = cs.receta_de(s, p.id)
                for v in s.scalars(select(Variante).where(Variante.producto_id == p.id, Variante.activo.is_(True))):
                    d = cs.stock_derivado(s, v, receta)
                    if d is not None and d != int(v.stock_actual):
                        desf.append((p.nombre, v.talla, int(v.stock_actual), d))
            s.rollback()
        print(f"\nConjuntos desfasados de sus piezas: {len(desf)} tallas"
              + (" (el kiosko vende con el número del conjunto)" if desf else ""))
        for nombre, talla, actual, debe in sorted(desf):
            print(f"    {nombre} {talla}: dice {inv.cifra(actual)}, sus piezas dan {debe}{'   ↓ bajaría' if debe < actual else ''}")

    if args.plantilla:
        plan = {
            "conteo": {
                "contado": "AAAA-MM-DD HH:MM (la hora en que se contó)",
                "incluye_entradas": None,
                "items": [{"sku": f["sku"], "nombre": inv.nombre_talla(f), "sistema": f["stock_actual"],
                           "en_cajas": f["bodega"] + f["piso"], "hay": None} for f in piezas],
            }
        }
        Path(args.plantilla).expanduser().write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nPlantilla de conteo: {args.plantilla} ({len(piezas)} tallas). «hay» = lo suelto en tienda, SIN"
              " lo que está dentro de cajas (del almacén o en el piso). Si en el mismo plan entra mercancía,"
              " llena «incluye_entradas».")
    print("\nSolo lectura: no se cambió nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
