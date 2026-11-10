#!/usr/bin/env python3
"""Genera el plan para que una escuela tenga el mismo uniforme que otra (SOLO LECTURA).

Compara la escuela ORIGEN con la DESTINO (que ya debe existir) y escribe un
plan para aplicar_alta.py:
  - ALTAS: productos del origen que el destino no tiene (mismos precios por talla,
    color cambiado según las reglas, color cambiado también en el nombre).
  - EDITAR: productos que el destino ya tiene pero con otro color o nombre.
  - LIGAR: piezas del uniforme del origen (incluidas las generales, sin escuela)
    que faltan en el uniforme del destino, con su grupo y orden.

Uso (desde la raíz del repo):
    python .claude/skills/alta-productos/scripts/copiar_escuela.py \
        --origen "Ignacio Allende" --destino "Ignacio Allende (Jaral)" \
        --colores Rojo=Azul --color-de "Pants Suelto=Gris" --excluir Boina \
        --salida /tmp/plan_jaral.json [--env-file ...]

  --colores ORIGEN=DESTINO     cambio general de color (repetible)
  --color-de PATRÓN=COLOR      color fijo para productos cuyo nombre o tipo de pieza
                               contiene PATRÓN (repetible; gana sobre --colores)
  --excluir PATRÓN             no copiar esos productos (repetible)

Los productos se emparejan por tipo de pieza + nombre sin escuela y sin color.
No crea la escuela destino: si no existe, se da de alta en el POS primero.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import _comun


def norm(valor: str | None) -> str:
    valor = unicodedata.normalize("NFKD", (valor or "").strip().lower())
    return " ".join("".join(c for c in valor if not unicodedata.combining(c)).split())


def pares(valores: list[str], opcion: str) -> list[tuple[str, str]]:
    salida = []
    for v in valores:
        if "=" not in v:
            raise SystemExit(f"ERROR: {opcion} espera PATRÓN=VALOR, llegó «{v}».")
        a, b = v.split("=", 1)
        salida.append((a.strip(), b.strip()))
    return salida


SQL_PRODUCTOS = """
SELECT p.id, p.nombre, p.nombre_base, p.genero, p.escudo, p.ubicacion,
       c.nombre categoria, m.nombre marca, tpr.nombre prenda, tpi.nombre pieza,
       ne.nombre nivel, a.nombre atributo
FROM producto p
JOIN escuela e ON e.id = p.escuela_id
JOIN categoria c ON c.id = p.categoria_id
JOIN marca m ON m.id = p.marca_id
LEFT JOIN tipo_prenda tpr ON tpr.id = p.tipo_prenda_id
LEFT JOIN tipo_pieza tpi ON tpi.id = p.tipo_pieza_id
LEFT JOIN nivel_educativo ne ON ne.id = p.nivel_educativo_id
LEFT JOIN atributo_producto a ON a.id = p.atributo_id
WHERE e.nombre = :escuela AND p.activo
ORDER BY p.id
"""
SQL_VARIANTES = """
SELECT talla, color, precio_venta, costo_referencia FROM variante
WHERE producto_id = :pid AND activo ORDER BY id
"""
SQL_UNIFORME = """
SELECT up.producto_id, up.grupo, up.orden, up.obligatoria, p.nombre, p.escuela_id
FROM uniforme u JOIN escuela e ON e.id = u.escuela_id
JOIN uniforme_pieza up ON up.uniforme_id = u.id AND up.activo
JOIN producto p ON p.id = up.producto_id
WHERE e.nombre = :escuela ORDER BY up.orden, up.id
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", required=True)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--colores", action="append", default=[])
    ap.add_argument("--color-de", action="append", default=[])
    ap.add_argument("--excluir", action="append", default=[])
    ap.add_argument("--salida", type=Path, required=True, help="JSON del plan (fuera del repo)")
    _comun.agregar_argumentos_db(ap)
    args = ap.parse_args()

    mapa_colores = {norm(a): b for a, b in pares(args.colores, "--colores")}
    color_de = [(norm(a), b) for a, b in pares(args.color_de, "--color-de")]
    excluir = [norm(x) for x in args.excluir]

    from sqlalchemy import text

    engine = _comun.motor(args, solo_lectura=True)
    with engine.connect() as conn:
        escuelas = {r[0] for r in conn.execute(text("SELECT nombre FROM escuela"))}
        for nombre in (args.origen, args.destino):
            if nombre not in escuelas:
                parecidas = [e for e in escuelas if norm(nombre.split("(")[0]) in norm(e)][:6]
                raise SystemExit(f"ERROR: la escuela «{nombre}» no existe (nombre exacto). Parecidas: {parecidas}")

        colores_bd = sorted(
            {r[0] for r in conn.execute(text("SELECT DISTINCT color FROM variante")) if r[0] and r[0] != "Sin color"},
            key=len, reverse=True,
        )

        def cargar(escuela: str) -> list[dict]:
            productos = []
            for r in conn.execute(text(SQL_PRODUCTOS), {"escuela": escuela}).mappings():
                p = dict(r)
                p["variantes"] = [dict(v) for v in conn.execute(text(SQL_VARIANTES), {"pid": p["id"]}).mappings()]
                cuenta = Counter(v["color"] for v in p["variantes"])
                p["color"] = cuenta.most_common(1)[0][0] if cuenta else "Sin color"
                base = p["nombre_base"] or p["nombre"]
                p["base"] = base[: -len(escuela)].strip() if base.endswith(escuela) else base
                sin_color = p["base"]
                for c in colores_bd:
                    sin_color = re.sub(rf"\b{re.escape(c)}\b", "", sin_color, flags=re.IGNORECASE)
                p["clave"] = f"{norm(p['pieza'])}|{norm(sin_color)}"
                productos.append(p)
            return productos

        origen, destino = cargar(args.origen), cargar(args.destino)
        uni_origen = [dict(r) for r in conn.execute(text(SQL_UNIFORME), {"escuela": args.origen}).mappings()]
        uni_destino = {r["producto_id"] for r in conn.execute(text(SQL_UNIFORME), {"escuela": args.destino}).mappings()}

    def coincide(p: dict, patron: str) -> bool:
        return patron in norm(p["base"]) or patron == norm(p["pieza"])

    def color_objetivo(p: dict) -> str:
        for patron, color in color_de:
            if coincide(p, patron):
                return color
        return mapa_colores.get(norm(p["color"]), p["color"])

    def nombre_objetivo(p: dict, nuevo: str) -> str:
        if nuevo == p["color"] or p["color"] == "Sin color":
            return p["base"]
        return re.sub(rf"\b{re.escape(p['color'])}\b", nuevo, p["base"], flags=re.IGNORECASE)

    por_clave_destino = {p["clave"]: p for p in destino}
    pieza_origen = {u["producto_id"]: u for u in uni_origen}
    plan_editar, plan_altas, plan_ligar = [], [], []
    excluidos, avisos = [], []
    destino_de_origen: dict[int, int | None] = {}

    print(f"\nOrigen «{args.origen}»: {len(origen)} productos · Destino «{args.destino}»: {len(destino)} productos\n")
    for p in origen:
        if any(coincide(p, x) for x in excluir):
            excluidos.append(p["nombre"])
            continue
        color = color_objetivo(p)
        nombre = nombre_objetivo(p, color)
        d = por_clave_destino.get(p["clave"])
        if d:
            destino_de_origen[p["id"]] = d["id"]
            cambio: dict = {}
            if norm(d["color"]) != norm(color):
                cambio["color"] = color
            if norm(d["base"]) != norm(nombre):
                cambio["nombre"] = nombre
            faltan = {v["talla"] for v in p["variantes"]} - {v["talla"] for v in d["variantes"]}
            if faltan:
                avisos.append(f"«{d['nombre']}» no tiene las tallas {sorted(faltan)} del origen (no se agregan solas)")
            if cambio:
                plan_editar.append({"producto": d["nombre"], "producto_id": d["id"], **cambio})
                print(f"EDITAR  «{d['nombre']}»: " + ", ".join(
                    f"{k} {d['color'] if k == 'color' else d['base']} → {v}" for k, v in cambio.items()))
            else:
                print(f"YA ESTÁ «{d['nombre']}»")
            continue
        destino_de_origen[p["id"]] = None
        spec = {
            "producto": {
                "nombre": nombre, "categoria": p["categoria"], "marca": p["marca"], "escuela": args.destino,
                "tipo_prenda": p["prenda"], "tipo_pieza": p["pieza"], "nivel_educativo": p["nivel"],
                "atributo": p["atributo"], "genero": p["genero"], "escudo": p["escudo"], "ubicacion": p["ubicacion"],
            },
            "color": color,
            "variantes": [
                {"talla": v["talla"], "precio": float(v["precio_venta"]),
                 **({"costo": float(v["costo_referencia"])} if v["costo_referencia"] is not None else {})}
                for v in p["variantes"]
            ],
        }
        if p["id"] in pieza_origen:
            u = pieza_origen[p["id"]]
            spec["uniforme"] = {"grupo": u["grupo"], "orden": u["orden"], "obligatoria": u["obligatoria"]}
        plan_altas.append(spec)
        escalera = " ".join(f"{v['talla']}:{float(v['precio_venta']):.0f}" for v in p["variantes"])
        print(f"ALTA    «{nombre} {args.destino}» · {color} · {len(p['variantes'])} tallas · {escalera}")

    for u in uni_origen:
        if u["escuela_id"] is None:                       # pieza general (sin escuela)
            if u["producto_id"] not in uni_destino:
                plan_ligar.append({"producto": u["nombre"], "producto_id": u["producto_id"],
                                   "grupo": u["grupo"], "orden": u["orden"], "obligatoria": u["obligatoria"]})
                print(f"LIGAR   «{u['nombre']}» (general) · {u['grupo']} · orden {u['orden']}")
            continue
        dest_id = destino_de_origen.get(u["producto_id"])
        if dest_id and dest_id not in uni_destino:
            d = next(x for x in destino if x["id"] == dest_id)
            plan_ligar.append({"producto": d["nombre"], "producto_id": dest_id,
                               "grupo": u["grupo"], "orden": u["orden"], "obligatoria": u["obligatoria"]})
            print(f"LIGAR   «{d['nombre']}» · {u['grupo']} · orden {u['orden']}")

    sobran = [d["nombre"] for d in destino if d["id"] not in destino_de_origen.values()]
    if excluidos:
        print(f"\nExcluidos: {excluidos}")
    if sobran:
        print(f"Solo en el destino (no se tocan): {sobran}")
    for a in avisos:
        print(f"⚠ {a}")

    plan: list[dict] = []
    if plan_editar:
        plan.append({"editar": plan_editar})
    plan.extend(plan_altas)
    if plan_ligar:
        plan.append({"escuela": args.destino, "ligar_al_uniforme": plan_ligar})
    args.salida.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nPlan: {len(plan_altas)} altas · {len(plan_editar)} ediciones · {len(plan_ligar)} piezas a ligar → {args.salida}")
    print("Siguiente: aplicar_alta.py <plan> (ensayo) y, con el OK de Daniel, --aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
