#!/usr/bin/env python3
"""Análisis de ventas de la tienda (SOLO LECTURA).

Lee la Libreta (`libreta_venta`, donde viven las ventas reales desde 2026;
`venta`/`venta_detalle` quedaron casi vacías) con los MISMOS servicios que la
pestaña Analítica del POS, para que las cifras cuadren:
  - `analitica_libreta_service.filas_de_periodo`: una fila por prenda vendida,
    con escuela, pieza, nivel, talla, empleada.
  - `analitica_tablero_service.cifras` + `corte_caja_service.ajustes_en_rango`:
    el «cobrado» oficial (efectivo + lo que llega por terminal, con los ajustes
    del dueño en sus cortes).

Uso (desde la raíz del repo):
    python .claude/skills/analisis-ventas/scripts/analizar_ventas.py \
        [--desde 2026-10-01 --hasta 2026-10-31 | --dias 30] \
        [--escuela "Ignacio Allende"] [--secciones resumen,escuelas,...] \
        [--top 15] [--sin-movimiento 120] [--env-file /ruta/pos_uniformes.env]

Secciones (por defecto todas):
  resumen     cobrado, importe, tickets, piezas, ticket promedio; contra el
              periodo anterior y contra las mismas fechas del año pasado
  escuelas    ranking por importe, con cambio contra el año pasado
  prendas     por tipo de pieza
  productos   productos más vendidos (y los que más cayeron contra el año pasado)
  tallas      curva de tallas (% de piezas) — base para pedir al proveedor
  reabasto    lo que se vende y no alcanza: semanas de existencia al ritmo actual
  margen      importe contra costo de referencia (costo ACTUAL del catálogo)
  muerto      existencia sin una sola venta en N días, y lo que vale
  horarios    ventas por día de la semana y por hora
  empleadas   piezas e importe por empleada
  faltantes   demanda no atendida (búsquedas vacías, tallas agotadas)
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "alta-productos" / "scripts"))
import _comun  # noqa: E402  (conexión, --env-file, raíz del repo en sys.path)

SECCIONES = ("resumen", "escuelas", "prendas", "productos", "tallas", "reabasto",
             "margen", "muerto", "horarios", "empleadas", "faltantes")
DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


# ─── Formato ────────────────────────────────────────────────────────────────

def pesos(v) -> str:
    return f"${Decimal(str(v or 0)):,.0f}"


def pct(ahora, antes) -> str:
    ahora, antes = Decimal(str(ahora or 0)), Decimal(str(antes or 0))
    if antes == 0:
        return "nuevo" if ahora > 0 else "—"
    p = (ahora - antes) / antes * 100
    return f"{'+' if p >= 0 else ''}{p:.0f}%"


def titulo(t: str) -> None:
    print(f"\n## {t}")


def tabla(encabezados: list[str], filas: list[list], alinear_izq: int = 1) -> None:
    """Tabla markdown compacta: se lee bien en terminal y se pega tal cual."""
    if not filas:
        print("(sin datos)")
        return
    print("| " + " | ".join(encabezados) + " |")
    print("|" + "|".join(":--" if i < alinear_izq else "--:" for i in range(len(encabezados))) + "|")
    for f in filas:
        print("| " + " | ".join(str(x) for x in f) + " |")


def un_anio_antes(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


# ─── Agregados puros ────────────────────────────────────────────────────────

def agrupar(filas, clave) -> dict[str, list]:
    """{clave: [piezas, importe]}"""
    acc: dict[str, list] = defaultdict(lambda: [0, Decimal("0")])
    for f in filas:
        k = clave(f) or "(sin dato)"
        acc[k][0] += f.cantidad
        acc[k][1] += f.importe
    return acc


def ordenar(acc: dict, top: int | None = None) -> list[tuple[str, int, Decimal]]:
    salida = sorted(((k, v[0], v[1]) for k, v in acc.items()), key=lambda x: (-x[2], -x[1]))
    return salida[:top] if top else salida


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", type=date.fromisoformat)
    ap.add_argument("--hasta", type=date.fromisoformat)
    ap.add_argument("--dias", type=int, default=30, help="si no hay --desde: los últimos N días (def. 30)")
    ap.add_argument("--escuela", help="filtra a una escuela (nombre exacto o parte)")
    ap.add_argument("--secciones", default=",".join(SECCIONES))
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--sin-movimiento", type=int, default=120, help="días sin venta para 'muerto' (def. 120)")
    _comun.agregar_argumentos_db(ap)
    args = ap.parse_args()

    hasta = args.hasta or date.today()
    desde = args.desde or hasta - timedelta(days=args.dias - 1)
    if desde > hasta:
        raise SystemExit("ERROR: --desde es posterior a --hasta.")
    largo = (hasta - desde).days + 1
    a_desde, a_hasta = desde - timedelta(days=largo), desde - timedelta(days=1)
    y_desde, y_hasta = un_anio_antes(desde), un_anio_antes(hasta)
    pedidas = [s.strip() for s in args.secciones.split(",") if s.strip()]
    malas = [s for s in pedidas if s not in SECCIONES]
    if malas:
        raise SystemExit(f"ERROR: secciones desconocidas {malas}. Válidas: {', '.join(SECCIONES)}")

    engine = _comun.motor(args, solo_lectura=True)

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from pos_uniformes.database.models import Escuela, Producto, Variante
    from pos_uniformes.services import analitica_tablero_service as tablero
    from pos_uniformes.services.analitica_libreta_service import filas_de_periodo
    from pos_uniformes.services.libreta_service import listar_operaciones

    def filtro_escuela(filas):
        if not args.escuela:
            return filas
        patron = args.escuela.lower()
        return [f for f in filas if patron in (f.escuela or "").lower()]

    with Session(engine) as session:
        def cargar(d0: date, d1: date):
            ini, fin = tablero.limites(d0, d1)
            return filtro_escuela(filas_de_periodo(session, ini, fin))

        def cifras_oficiales(d0: date, d1: date):
            from pos_uniformes.services.corte_caja_service import ajustes_en_rango

            ini, fin = tablero.limites(d0, d1)
            rows = listar_operaciones(session, desde=ini, hasta=fin, employee_code=None)
            try:
                ajuste = ajustes_en_rango(session, ini, fin)
            except Exception:  # noqa: BLE001 — sin cortes, la cifra real
                session.rollback()
                ajuste = Decimal("0")
            return tablero.cifras(rows, ajuste=ajuste)

        filas = cargar(desde, hasta)
        filas_ant = cargar(a_desde, a_hasta)
        filas_y = cargar(y_desde, y_hasta)

        # Primer y último registro de la Libreta: dice qué comparaciones valen.
        from sqlalchemy import func

        from pos_uniformes.database.models import LibretaVenta

        primero, ultimo = session.execute(
            select(func.min(LibretaVenta.created_at), func.max(LibretaVenta.created_at))
        ).one()

        print(f"\n# Ventas {desde:%d-%b-%Y} → {hasta:%d-%b-%Y} ({largo} días)"
              + (f" · escuela ~ «{args.escuela}»" if args.escuela else ""))
        print(f"Libreta con datos del {primero:%d-%b-%Y} al {ultimo:%d-%b-%Y %H:%M}."
              if primero else "La Libreta está vacía.")
        hay_anio = bool(primero) and primero.date() <= y_desde
        if not hay_anio:
            print("Sin datos del año pasado para estas fechas: no se muestran comparaciones anuales.")

        def cols(base: list[str]) -> list[str]:
            return base + (["Año pasado", "Cambio"] if hay_anio else [])

        def fila(base: list, anual: list) -> list:
            return base + (anual if hay_anio else [])

        def piezas(fs):
            return sum(f.cantidad for f in fs)

        def importe(fs):
            return sum((f.importe for f in fs), Decimal("0"))

        # ── resumen
        if "resumen" in pedidas:
            titulo("Resumen")
            if args.escuela:
                print("(con filtro de escuela solo cuentan prendas; el cobrado es de toda la tienda y no se muestra)")
                tabla(cols(["", "Periodo", "Anterior", "Cambio"]), [
                    fila(["Importe prendas", pesos(importe(filas)), pesos(importe(filas_ant)),
                          pct(importe(filas), importe(filas_ant))],
                         [pesos(importe(filas_y)), pct(importe(filas), importe(filas_y))]),
                    fila(["Piezas", piezas(filas), piezas(filas_ant), pct(piezas(filas), piezas(filas_ant))],
                         [piezas(filas_y), pct(piezas(filas), piezas(filas_y))]),
                ])
            else:
                c, ca, cy = (cifras_oficiales(desde, hasta), cifras_oficiales(a_desde, a_hasta),
                             cifras_oficiales(y_desde, y_hasta))
                renglones = [
                    ("Cobrado (oficial)", "cobrado", pesos),
                    ("Efectivo", "efectivo", pesos),
                    ("Terminal (neto)", "tarjeta_neto", pesos),
                    ("Tickets de venta", "ventas", str),
                    ("Ticket promedio", "ticket_promedio", pesos),
                    ("Piezas", "piezas", str),
                ]
                tabla(cols(["", "Periodo", "Anterior", "Cambio"]), [
                    fila([n, fmt(getattr(c, a)), fmt(getattr(ca, a)), pct(getattr(c, a), getattr(ca, a))],
                         [fmt(getattr(cy, a)), pct(getattr(c, a), getattr(cy, a))])
                    for n, a, fmt in renglones
                ])
                if c.cobrado:
                    print(f"Terminal: {c.tarjeta_neto / c.cobrado * 100:.0f}% de lo cobrado.")
            print(f"«Anterior» = {a_desde:%d-%b} → {a_hasta:%d-%b}"
                  + (f"; «Año pasado» = {y_desde:%d-%b-%Y} → {y_hasta:%d-%b-%Y}." if hay_anio else ".")
                  + " Ojo con la temporada: contra el regreso a clases casi todo «baja».")

        # ── escuelas
        if "escuelas" in pedidas:
            titulo("Escuelas (por importe)")
            ahora = agrupar(filas, lambda f: f.escuela or "(general / sin escuela)")
            antes = agrupar(filas_y, lambda f: f.escuela or "(general / sin escuela)")
            total = importe(filas) or Decimal("1")
            tabla(cols(["Escuela", "Piezas", "Importe", "% del total"]), [
                fila([k, p, pesos(i), f"{i / total * 100:.0f}%"],
                     [pesos(antes.get(k, [0, 0])[1]), pct(i, antes.get(k, [0, 0])[1])])
                for k, p, i in ordenar(ahora, args.top)
            ])
            if hay_anio:
                caidas = sorted(
                    ((k, v[1], ahora.get(k, [0, Decimal("0")])[1]) for k, v in antes.items() if v[1] >= 1000),
                    key=lambda x: (x[2] - x[1]),
                )[:5]
                caidas = [c for c in caidas if c[2] < c[1]]
                if caidas:
                    print("\nLas que más bajaron contra el año pasado:")
                    for k, antes_i, ahora_i in caidas:
                        print(f"- {k}: {pesos(antes_i)} → {pesos(ahora_i)} ({pct(ahora_i, antes_i)})")

        # ── prendas
        if "prendas" in pedidas:
            titulo("Prendas (tipo de pieza)")
            ahora = agrupar(filas, lambda f: f.tipo_pieza)
            antes = agrupar(filas_y, lambda f: f.tipo_pieza)
            tabla(cols(["Pieza", "Piezas", "Importe", "Precio prom."]), [
                fila([k, p, pesos(i), pesos(i / p if p else 0)],
                     [pesos(antes.get(k, [0, 0])[1]), pct(i, antes.get(k, [0, 0])[1])])
                for k, p, i in ordenar(ahora, args.top)
            ])
            sin = sum(f.cantidad for f in filas if not f.tipo_pieza)
            if sin:
                print(f"«(sin dato)»: {sin} piezas vendidas sin SKU del catálogo (SIN-CODIGO o SKU que ya no existe).")

        # ── productos
        if "productos" in pedidas:
            titulo("Productos más vendidos")
            ahora = agrupar(filas, lambda f: f.nombre)
            tabla(["Producto", "Piezas", "Importe"], [[k, p, pesos(i)] for k, p, i in ordenar(ahora, args.top)])

        # ── tallas
        if "tallas" in pedidas:
            titulo("Curva de tallas (% de piezas por tipo de pieza)")
            por_pieza: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for f in filas:
                por_pieza[f.tipo_pieza or "(sin pieza)"][f.talla or "?"] += f.cantidad
            principales = sorted(por_pieza.items(), key=lambda kv: -sum(kv[1].values()))[:6]
            for pieza, tallas in principales:
                total = sum(tallas.values())
                curva = sorted(tallas.items(), key=lambda kv: -kv[1])
                print(f"- **{pieza}** ({total} pzs): " + " · ".join(f"{t} {n / total * 100:.0f}%" for t, n in curva[:10]))

        # ── reabasto / muerto: existencias actuales
        if {"reabasto", "muerto", "margen"} & set(pedidas):
            consulta = (
                select(Variante.sku, Variante.talla, Variante.stock_actual, Variante.precio_venta,
                       Variante.costo_referencia, Producto.nombre, Escuela.nombre)
                .join(Producto, Producto.id == Variante.producto_id)
                .outerjoin(Escuela, Escuela.id == Producto.escuela_id)
                .where(Variante.activo.is_(True), Producto.activo.is_(True))
            )
            existencias = {
                sku: {"talla": t, "stock": int(s or 0), "precio": p, "costo": c, "nombre": n, "escuela": e or ""}
                for sku, t, s, p, c, n, e in session.execute(consulta)
            }
            if args.escuela:
                patron = args.escuela.lower()
                existencias = {k: v for k, v in existencias.items() if patron in v["escuela"].lower()}

        if "reabasto" in pedidas:
            titulo(f"Reabasto: no alcanza para 4 semanas al ritmo de los últimos {largo} días")
            vendidas: dict[str, int] = defaultdict(int)
            for f in filas:
                vendidas[f.sku] += f.cantidad
            semanas_periodo = largo / 7
            alerta = []
            for sku, n in vendidas.items():
                e = existencias.get(sku)
                if not e or n < 2:
                    continue
                ritmo = n / semanas_periodo
                semanas = e["stock"] / ritmo if ritmo else 99
                if semanas < 4:
                    alerta.append((semanas, sku, e, n, ritmo))
            alerta.sort(key=lambda x: (x[0], -x[3]))
            tabla(["Producto", "Talla", "Vendidas", "Por semana", "Existencia", "Alcanza"], [
                [e["nombre"], e["talla"], n, f"{r:.1f}", e["stock"],
                 "NEGATIVA" if e["stock"] < 0 else ("ya no hay" if e["stock"] == 0 else f"{s:.1f} sem")]
                for s, sku, e, n, r in alerta[: args.top * 2]
            ])
            if len(alerta) > args.top * 2:
                print(f"… y {len(alerta) - args.top * 2} más.")
            negativas = sum(1 for a in alerta if a[2]["stock"] < 0)
            if negativas:
                print(f"\n{negativas} de {len(alerta)} tienen existencia NEGATIVA: se vendió sin entrada registrada. "
                      "Ahí el número no dice cuánto hay; primero hay que contar (conteo o entrada de mercancía).")

        if "margen" in pedidas:
            titulo("Margen bruto (contra el costo de referencia ACTUAL)")
            con_costo = [(f, existencias[f.sku]["costo"]) for f in filas
                         if f.sku in existencias and existencias[f.sku]["costo"]]
            imp_total = importe(filas)
            imp_cc = sum((f.importe for f, _ in con_costo), Decimal("0"))
            cobertura = imp_cc / imp_total * 100 if imp_total else 0
            print(f"Cobertura: {cobertura:.0f}% del importe tiene costo capturado.")
            if cobertura < 30:
                print("⚠ Con tan poco costo capturado el margen no representa a la tienda: se muestra solo como muestra. "
                      "Para mejorarlo: registrar costos (skill registro-costos-proveedor) y pasarlos a costo_referencia.")
            acc: dict[str, list] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
            for f, costo in con_costo:
                acc[f.tipo_pieza or "(sin pieza)"][0] += f.importe
                acc[f.tipo_pieza or "(sin pieza)"][1] += Decimal(str(costo)) * f.cantidad
            filas_m = sorted(acc.items(), key=lambda kv: -(kv[1][0] - kv[1][1]))[: args.top]
            tabla(["Pieza", "Importe", "Costo", "Utilidad", "Margen"], [
                [k, pesos(i), pesos(c), pesos(i - c), f"{(i - c) / i * 100:.0f}%" if i else "—"]
                for k, (i, c) in filas_m
            ])
            bajos = sorted(((f.nombre, f.talla, f.precio, Decimal(str(c))) for f, c in con_costo
                            if f.precio and (f.precio - Decimal(str(c))) / f.precio < Decimal("0.25")),
                           key=lambda x: (x[2] - x[3]) / x[2])
            vistos, unicos = set(), []
            for b in bajos:
                if (b[0], b[1]) not in vistos:
                    vistos.add((b[0], b[1]))
                    unicos.append(b)
            if unicos:
                print("\nVendidos con margen menor a 25 %:")
                for n, t, p, c in unicos[:10]:
                    print(f"- {n} {t}: precio {pesos(p)}, costo {pesos(c)} ({(p - c) / p * 100:.0f}%)")

        if "muerto" in pedidas:
            n = args.sin_movimiento
            titulo(f"Inventario sin una venta en {n} días")
            ini, fin = tablero.limites(hasta - timedelta(days=n - 1), hasta)
            vendidos_ventana = {f.sku for f in filtro_escuela(filas_de_periodo(session, ini, fin))}
            if primero and primero.date() > hasta - timedelta(days=n - 1):
                print(f"⚠ La Libreta empieza el {primero:%d-%b-%Y}: la ventana real es más corta que {n} días.")
            muertos = [(k, e) for k, e in existencias.items() if e["stock"] > 0 and k not in vendidos_ventana]
            valor_p = sum((Decimal(str(e["precio"] or 0)) * e["stock"] for _, e in muertos), Decimal("0"))
            valor_c = sum((Decimal(str(e["costo"] or 0)) * e["stock"] for _, e in muertos), Decimal("0"))
            print(f"{len(muertos)} tallas con existencia · {sum(e['stock'] for _, e in muertos)} piezas · "
                  f"{pesos(valor_p)} a precio de venta · {pesos(valor_c)} a costo (donde hay costo).")
            por_escuela: dict[str, list] = defaultdict(lambda: [0, Decimal("0")])
            for _, e in muertos:
                por_escuela[e["escuela"] or "(general)"][0] += e["stock"]
                por_escuela[e["escuela"] or "(general)"][1] += Decimal(str(e["precio"] or 0)) * e["stock"]
            tabla(["Escuela", "Piezas paradas", "Valor a precio"], [
                [k, v[0], pesos(v[1])] for k, v in sorted(por_escuela.items(), key=lambda kv: -kv[1][1])[: args.top]
            ])

        if "horarios" in pedidas:
            titulo("¿Cuándo se vende?")
            dia = agrupar(filas, lambda f: f"{f.momento.weekday()}")
            semanas_dia = {d: 0 for d in range(7)}
            dd = desde
            while dd <= hasta:
                semanas_dia[dd.weekday()] += 1
                dd += timedelta(days=1)
            tabla(["Día", "Piezas", "Importe", "Promedio por día"], [
                [DIAS[int(k)], v[0], pesos(v[1]), pesos(v[1] / (semanas_dia[int(k)] or 1))]
                for k, v in sorted(dia.items())
            ])
            hora = agrupar(filas, lambda f: f"{f.momento.hour:02d}")
            total = importe(filas) or Decimal("1")
            print("\nPor hora: " + " · ".join(f"{k}h {v[1] / total * 100:.0f}%" for k, v in sorted(hora.items())))

        if "empleadas" in pedidas:
            titulo("Por empleada")
            emp = agrupar(filas, lambda f: f.employee_name or f.employee_code)
            tabla(["Empleada", "Piezas", "Importe"], [[k, p, pesos(i)] for k, p, i in ordenar(emp)])

        if "faltantes" in pedidas:
            titulo("Demanda no atendida")
            try:
                from pos_uniformes.services import demanda_service

                ini, fin = tablero.limites(desde, hasta)
                faltas = demanda_service.listar(session, ini, fin)
                print(f"{len(faltas)} registros en el periodo.")
                tabla(["Talla agotada que pidieron", "Veces", "Piezas"],
                      [[g.clave, g.veces, g.piezas] for g in demanda_service.por_producto_talla(faltas)[: args.top]])
                print()
                repetidas = [g for g in demanda_service.por_texto(faltas) if g.veces >= 2]
                if repetidas:
                    tabla(["Búsqueda sin resultado (2+ veces)", "Veces"],
                          [[g.clave, g.veces] for g in repetidas[: args.top]])
                else:
                    print("Ninguna búsqueda sin resultado se repitió (las de una vez suelen ser errores de dedo).")
            except Exception as exc:  # noqa: BLE001 — tabla nueva: puede no existir en la base
                session.rollback()
                print(f"(no disponible en esta base: {type(exc).__name__})")

        session.rollback()  # solo lectura: nada que guardar
    return 0


if __name__ == "__main__":
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        raise SystemExit(main())
    except ProgrammingError as exc:
        print(f"\nERROR: la base no coincide con el código de esta rama ({type(exc.orig).__name__}). "
              "Probablemente le faltan migraciones. Usar la caja (--env-file, ver CLAUDE.md) o una copia migrada.")
        raise SystemExit(1)
    except OperationalError as exc:
        print(f"\nERROR: no se pudo conectar a la base ({str(exc.orig).splitlines()[0][:150]}).")
        raise SystemExit(1)
