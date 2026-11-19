"""Lo que hace falta saber ANTES de armar el plan de una venta manual. Solo lectura.

  --producto "boina vino"   variantes cuyo nombre o SKU tienen TODAS las palabras
                            (SKU, nombre, talla, precio de lista, existencia)
  --empleadas               códigos y nombres de las empleadas activas, con su último pago
  --dia 2026-11-17          el corte que cubre ese día, su primera y última operación,
                            y una hora sugerida para registrar dentro del corte ya cerrado

Uso (desde la raíz del repo):
  "$PY" .claude/skills/registro-venta-libreta/scripts/buscar.py --producto "boina vino" \
      --producto golpe --empleadas --dia 2026-11-17 [--env-file …]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "alta-productos" / "scripts"))
import _comun  # noqa: E402

from sqlalchemy import text  # noqa: E402

ZONA = "America/Mexico_City"


def buscar_productos(c, consulta: str, limite: int) -> None:
    palabras = [p for p in consulta.split() if p]
    filtros = " and ".join(
        f"(p.nombre ilike :p{i} or v.sku ilike :p{i} or v.color ilike :p{i})" for i in range(len(palabras))
    )
    params = {f"p{i}": f"%{p}%" for i, p in enumerate(palabras)}
    filas = c.execute(text(f"""
        select v.sku, p.nombre, v.talla, v.precio_venta, v.stock_actual, v.activo
        from variante v join producto p on p.id = v.producto_id
        where {filtros or 'true'}
        order by v.activo desc, p.nombre, v.talla
        limit :lim"""), {**params, "lim": limite}).fetchall()
    print(f"\n== Producto «{consulta}»: {len(filas)}{' (recortado)' if len(filas) == limite else ''}")
    if not filas:
        print("   (nada: revisar el nombre, o darlo de alta con la skill alta-productos)")
    for sku, nombre, talla, precio, stock, activo in filas:
        marca = "" if activo else "  [INACTIVO]"
        neg = "  ⚠ NEGATIVA" if stock is not None and stock < 0 else ""
        print(f"   {sku:10} {nombre} · {talla} · ${precio} · existencia {stock}{neg}{marca}")


def empleadas(c) -> None:
    print("\n== Empleadas activas (código · nombre · último pago)")
    for codigo, nombre, ultimo in c.execute(text(f"""
        select e.codigo, e.nombre_completo,
               (select max(p.created_at) from empleada_pago p where p.employee_code = e.codigo)
                   at time zone '{ZONA}'
        from empleada e where e.activo order by e.codigo""")):
        print(f"   {codigo:8} {nombre:28} {ultimo:%Y-%m-%d %H:%M}" if ultimo else f"   {codigo:8} {nombre:28} (sin pagos)")


def dia(c, d: date) -> None:
    ini = datetime.combine(d, datetime.min.time())
    fin = ini + timedelta(days=1)
    print(f"\n== Día {d:%a %d-%b-%Y}")
    ops = c.execute(text(f"""
        select min(created_at at time zone '{ZONA}'), max(created_at at time zone '{ZONA}'), count(*)
        from libreta_venta
        where created_at at time zone '{ZONA}' >= :ini and created_at at time zone '{ZONA}' < :fin"""),
        {"ini": ini, "fin": fin}).fetchone()
    print(f"   Operaciones: {ops[2]}" + (f" (de {ops[0]:%H:%M} a {ops[1]:%H:%M})" if ops[2] else ""))
    cortes = c.execute(text(f"""
        select id, desde at time zone '{ZONA}', hasta at time zone '{ZONA}', monto_esperado, monto_final
        from libreta_corte
        where hasta is not null and hasta at time zone '{ZONA}' >= :ini
          and coalesce(desde at time zone '{ZONA}', :ini) < :fin
        order by hasta"""), {"ini": ini, "fin": fin}).fetchall()
    if not cortes:
        print("   Ningún corte cerrado cubre este día: una venta con esta fecha cae en el PERIODO ABIERTO")
        print("   y sube lo que debe haber en el cajón (correcto solo si el dinero está en el cajón).")
        return
    for cid, desde, hasta, esperado, final in cortes:
        print(f"   Corte #{cid}: {desde:%d-%b %H:%M} → {hasta:%d-%b %H:%M}  (esperado ${esperado}, oficial ${final})")
    ultimo = cortes[-1]
    if ops[2] and ops[1] < ultimo[2]:
        sugerida = min(ops[1] + timedelta(minutes=1), ultimo[2] - timedelta(minutes=1)).replace(second=0, microsecond=0)
        if sugerida <= ops[1]:
            sugerida = ops[1] + timedelta(seconds=1)
        print(f"   Hora sugerida: {sugerida:%Y-%m-%d %H:%M:%S} (después de la última operación del día y "
              f"antes del cierre del corte #{ultimo[0]}: el cajón no se mueve)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _comun.agregar_argumentos_db(ap)
    ap.add_argument("--producto", action="append", default=[], help="Palabras a buscar (se puede repetir)")
    ap.add_argument("--empleadas", action="store_true")
    ap.add_argument("--dia", type=date.fromisoformat, help="AAAA-MM-DD")
    ap.add_argument("--limite", type=int, default=25)
    a = ap.parse_args()
    if not (a.producto or a.empleadas or a.dia):
        ap.error("Pedir al menos --producto, --empleadas o --dia.")
    e = _comun.motor(a, solo_lectura=True)
    with e.connect() as c:
        for consulta in a.producto:
            buscar_productos(c, consulta, a.limite)
        if a.empleadas:
            empleadas(c)
        if a.dia:
            dia(c, a.dia)


if __name__ == "__main__":
    main()
