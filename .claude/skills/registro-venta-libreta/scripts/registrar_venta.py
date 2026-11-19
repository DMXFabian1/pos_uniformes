"""Registra en la Libreta una o varias ventas que no se capturaron en su momento.

Ensayo por defecto (todo en UNA transacción que se deshace); guarda solo con --aplicar.
Usa `libreta_service.registrar_operacion`, igual que la Libreta: calcula las comisiones
(1 por pieza, 2 en los de 3pz) y descuenta el stock (`libreta:N`).

Plan (JSON):
{
  "ventas": [
    {
      "empleada": "VEND-4",                 # código, o parte del nombre ("Stayce")
      "cuando": "2026-11-17 17:50",         # opcional; hora de la tienda. Sin esto: ahora
      "tarjeta": false,                     # opcional; default efectivo
      "cliente": null,                      # opcional; texto libre
      "descontar_stock": true,              # opcional; false = la venta no toca existencias
      "items": [
        {"sku": "SKU000190", "cantidad": 11, "precio": 80},   # precio opcional: el de lista
        {"sku": "SIN-CODIGO", "nombre": "mono", "cantidad": 1, "precio": 60}
      ]
    }
  ]
}

Uso (desde la raíz del repo):
  "$PY" .claude/skills/registro-venta-libreta/scripts/registrar_venta.py plan.json [--aplicar] [--env-file …]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "alta-productos" / "scripts"))
import _comun  # noqa: E402

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

ZONA = ZoneInfo("America/Mexico_City")
ORIGEN = "manual-claude"
CENT = Decimal("0.01")


def falla(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def resolver_empleada(s, valor: str) -> tuple[str, str]:
    valor = str(valor or "").strip()
    if not valor:
        falla("una venta no trae «empleada».")
    filas = s.execute(text("""select codigo, nombre_completo, activo from empleada
        where upper(codigo) = upper(:v) or nombre_completo ilike :like order by activo desc"""),
        {"v": valor, "like": f"%{valor}%"}).fetchall()
    exacta = [f for f in filas if f[0].upper() == valor.upper()]
    filas = exacta or filas
    if not filas:
        falla(f"no hay empleada «{valor}» (ver buscar.py --empleadas).")
    if len(filas) > 1:
        falla(f"«{valor}» es ambiguo: {', '.join(f'{c} {n}' for c, n, _ in filas)}.")
    codigo, nombre, activo = filas[0]
    if not activo:
        print(f"   ⚠ {codigo} {nombre} está INACTIVA.")
    return codigo, nombre


def resolver_cuando(valor) -> datetime | None:
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(str(valor))
    except ValueError:
        falla(f"«cuando» inválido: {valor!r} (formato AAAA-MM-DD HH:MM).")
    momento = momento if momento.tzinfo else momento.replace(tzinfo=ZONA)
    if momento > datetime.now(ZONA):
        falla(f"«cuando» está en el futuro: {momento}.")
    return momento


def resolver_items(s, items: list[dict]) -> list[dict]:
    if not items:
        falla("una venta no trae items.")
    salida = []
    for it in items:
        sku = str(it.get("sku") or "").strip().upper() or "SIN-CODIGO"
        cantidad = int(it.get("cantidad") or 0)
        if cantidad <= 0:
            falla(f"cantidad inválida en {it}.")
        if sku == "SIN-CODIGO":
            if not it.get("nombre") or it.get("precio") in (None, ""):
                falla(f"un renglón SIN-CODIGO necesita «nombre» y «precio»: {it}.")
            salida.append({"sku": sku, "nombre": str(it["nombre"]), "talla": str(it.get("talla") or ""),
                           "cantidad": cantidad, "precio": str(Decimal(str(it["precio"])).quantize(CENT)),
                           "_lista": None})
            continue
        fila = s.execute(text("""select p.nombre, v.talla, v.precio_venta, v.activo from variante v
            join producto p on p.id = v.producto_id where upper(v.sku) = :sku"""), {"sku": sku}).fetchone()
        if fila is None:
            falla(f"no existe el SKU {sku} (buscar.py --producto …, o darlo de alta con alta-productos).")
        nombre, talla, lista, activo = fila
        if not activo:
            print(f"   ⚠ {sku} {nombre} está INACTIVO.")
        precio = Decimal(str(it["precio"])) if it.get("precio") not in (None, "") else Decimal(lista)
        salida.append({"sku": sku, "nombre": nombre, "talla": talla, "cantidad": cantidad,
                       "precio": str(precio.quantize(CENT)), "_lista": Decimal(lista)})
    return salida


def stock(s, skus) -> dict:
    skus = sorted({k for k in skus if k != "SIN-CODIGO"})
    if not skus:
        return {}
    return dict(s.execute(text("select sku, stock_actual from variante where sku = any(:k)"), {"k": skus}).fetchall())


def corte_de(s, momento: datetime | None, tarjeta: bool) -> str:
    abierto = "PERIODO ABIERTO: " + ("con tarjeta, el cajón no cambia" if tarjeta
                                     else "sube lo que debe haber en el cajón (el dinero debe estar ahí)")
    if momento is None:
        return abierto
    fila = s.execute(text("""select id, hasta from libreta_corte
        where (desde is null or desde < :t) and hasta >= :t order by hasta limit 1"""), {"t": momento}).fetchone()
    if fila is None:
        return abierto
    return f"corte #{fila[0]} (cerrado el {fila[1].astimezone(ZONA):%d-%b %H:%M}): el cajón no se mueve"


def ultimo_pago(s, codigo: str):
    return s.execute(text("select max(created_at) from empleada_pago where employee_code = :c"), {"c": codigo}).scalar()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--aplicar", action="store_true", help="Guardar (sin esto: ensayo)")
    _comun.agregar_argumentos_db(ap)
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    ventas = plan.get("ventas") or []
    if not ventas:
        falla("el plan no trae «ventas».")

    e = _comun.motor(a)
    from pos_uniformes.services import libreta_service
    from pos_uniformes.services.corte_caja_service import estado_caja

    with Session(e) as s:
        preparadas = []
        for i, v in enumerate(ventas, 1):
            codigo, nombre = resolver_empleada(s, v.get("empleada"))
            preparadas.append((i, v, codigo, nombre, resolver_cuando(v.get("cuando")), resolver_items(s, v.get("items"))))

        todos_skus = [it["sku"] for *_, items in preparadas for it in items]
        stock_antes = stock(s, todos_skus)
        cajon_antes = estado_caja(s).esperado
        gran_total = Decimal("0.00")
        gran_comisiones = 0

        for i, v, codigo, nombre, cuando, items in preparadas:
            total = sum((Decimal(it["precio"]) * it["cantidad"] for it in items), Decimal("0.00")).quantize(CENT)
            limpios = [{k: val for k, val in it.items() if not k.startswith("_")} for it in items]
            if v.get("descontar_stock", True):
                entry = libreta_service.registrar_operacion(
                    s, employee_code=codigo, employee_name=nombre, tipo="venta", items=limpios,
                    monto_total=total, origen=ORIGEN, created_at=cuando,
                    pago_tarjeta=bool(v.get("tarjeta", False)), cliente=v.get("cliente") or None)
            else:
                original = libreta_service.descontar_stock
                libreta_service.descontar_stock = lambda *_a, **_k: 0
                try:
                    entry = libreta_service.registrar_operacion(
                        s, employee_code=codigo, employee_name=nombre, tipo="venta", items=limpios,
                        monto_total=total, origen=ORIGEN, created_at=cuando,
                        pago_tarjeta=bool(v.get("tarjeta", False)), cliente=v.get("cliente") or None)
                finally:
                    libreta_service.descontar_stock = original
            s.flush()
            momento = (entry.created_at or datetime.now(ZONA)).astimezone(ZONA)
            gran_total += total
            gran_comisiones += int(entry.comisiones or 0)
            pago = "TARJETA" if entry.pago_tarjeta else "efectivo"
            print(f"\n[{i}] Libreta #{entry.id} · {momento:%a %d-%b-%Y %H:%M} · {codigo} {nombre}")
            for it in items:
                lista = it["_lista"]
                nota = f"  (lista ${lista})" if lista is not None and Decimal(it["precio"]) != lista else ""
                print(f"    {it['cantidad']:>3} × {it['sku']:10} {it['nombre']} · {it['talla']} @ ${it['precio']}{nota}")
            print(f"    Total ${total} {pago} · {entry.piezas} piezas · {entry.comisiones} comisiones")
            print(f"    Cae en: {corte_de(s, cuando, bool(entry.pago_tarjeta))}")
            pagado = ultimo_pago(s, codigo)
            if pagado is not None and momento < pagado:
                print(f"    ⚠ {nombre} ya cobró el {pagado.astimezone(ZONA):%d-%b %H:%M}: estas comisiones NO entran en ningún pago.")
            elif pagado is not None:
                print(f"    Comisiones: entran en su próximo pago (último pago {pagado.astimezone(ZONA):%d-%b %H:%M}).")
            if not v.get("descontar_stock", True):
                print("    Stock: no se toca (descontar_stock=false)")

        stock_despues = stock(s, todos_skus)
        cajon_despues = estado_caja(s).esperado
        print(f"\nTotal: ${gran_total} · {gran_comisiones} comisiones · {len(preparadas)} venta(s)")
        print(f"Cajón abierto (esperado): ${cajon_antes} → ${cajon_despues}")
        for sku in sorted(stock_antes):
            antes, despues = stock_antes[sku], stock_despues.get(sku)
            neg = "  ⚠ NEGATIVA: capturar la entrada de mercancía" if despues is not None and despues < 0 else ""
            print(f"Stock {sku}: {antes} → {despues}{neg}")

        if a.aplicar:
            s.commit()
            print("\nGUARDADO")
        else:
            s.rollback()
            print("\nENSAYO: no se guardó nada (los # de Libreta de arriba se gastan; es normal)")


if __name__ == "__main__":
    main()
