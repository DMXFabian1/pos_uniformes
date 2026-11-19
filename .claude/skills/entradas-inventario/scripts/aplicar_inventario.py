"""Entradas de mercancía y conteos de un plan JSON, con los servicios del POS.

Tres modos:
  (nada)       VISTA PREVIA en solo lectura: resuelve cada renglón, valida y calcula cómo
               quedaría cada talla. No abre ninguna transacción de escritura. Es la que se
               le enseña a Daniel antes del OK.
  --aplicar    Todo en UNA transacción: si algo falla, no se guarda nada. Imprime el
               resultado real (incluidos los conjuntos recalculados) y guarda.
  --ensayo     Igual que --aplicar pero deshace al final. Solo contra una base LOCAL (o una
               copia de la caja); contra la caja hace falta además --ensayo-en-caja.

Qué usa del POS (lo mismo que la PC y el celular, con su bitácora):
  - entrada CON proveedor → `CompraService` (compra + detalle; sube `costo_referencia`), firma
    el usuario ADMIN. Como «Registrar entrada» de Inventario y `importar_nota_compra.py`.
  - entrada SIN proveedor → `bodega_movil_service.llego_mercancia`, como «Llegó mercancía» del
    celular (firma Daniel, sale en «Llegadas recientes»; lo que va `a_caja` entra a una caja).
  - conteo → `conteo_service.registrar_conteo` + `confirmar_ajustes_lote`, como el conteo del
    POS: mide SOLO la tienda (sin cajas), deja el renglón de conteo y la fecha de último conteo,
    y recalcula los conjuntos de la pieza.
  - "recalcular_conjuntos": "todos" → `conjunto_service.sincronizar_todo`.

Plan (JSON):
{
  "quien": "VEND-1",                         # opcional; las llegadas del celular solo las firma el dueño
  "entradas": [
    {"proveedor": "Tejidos Romanos", "documento": "ROMANOS-1234-2026-11-19", "observacion": "remisión 1234",
     "items": [{"sku": "SKU000159", "cantidad": 24, "costo": 18.5}]},          # costo de la remisión
    {"referencia": "maquilador",                                               # sin proveedor = «Llegó mercancía»
     "items": [{"sku": "SKU005703", "cantidad": 30, "a_caja": 0}]}             # a_caja / "caja": "A-012" opcionales
  ],
  "conteo": {
    "contado": "2026-11-19 18:30",            # hora REAL en que Daniel contó
    "incluye_entradas": true,                 # ¿contó DESPUÉS de acomodar lo que llegó en este plan?
    "items": [{"sku": "SKU005234", "hay": 7, "notas": "repisa de accesorios"}]   # hay = en TIENDA
  },
  "recalcular_conjuntos": "todos",            # opcional: corrige los conjuntos desfasados (la vista previa los lista)
  "nota": "texto libre, no se usa"
}
Cada renglón se identifica con "sku", "variante_id" o "buscar" (+ "talla", "escuela").
"costo": "actual" usa el costo guardado de esa talla. Un CONJUNTO (Pants 3pz, Chamarra con receta) no
entra ni se cuenta: van sus piezas, y el conjunto se recalcula solo. Una clave que no se conoce es ERROR.

Uso (desde la raíz del repo):
  "$PY" .claude/skills/entradas-inventario/scripts/aplicar_inventario.py plan.json [--env-file …] [--aplicar | --ensayo]
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _inventario as inv  # noqa: E402
from _inventario import _comun  # noqa: E402

from sqlalchemy import text  # noqa: E402

LOCALES = {"localhost", "127.0.0.1", "::1", None, ""}
MARGEN_BAJO = Decimal("0.40")      # igual que registro-costos-proveedor
DIAS_REPETIDA = 3                  # una llegada igual en estos días = probable doble captura


def falla(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def _entero(valor, donde: str, *, minimo: int) -> int:
    if isinstance(valor, bool) or not (isinstance(valor, int) or (isinstance(valor, str) and valor.strip().lstrip("-").isdigit())):
        falla(f"{donde}: {valor!r} no es un número entero.")
    n = int(valor)
    if n < minimo:
        falla(f"{donde}: debe ser ≥ {minimo} (vino {n}).")
    return n


IDENT = {"sku", "variante_id", "buscar", "talla", "escuela", "nombre"}
CLAVES_ENTRADA = {"proveedor", "documento", "observacion", "referencia", "caja", "items"}
CLAVES_ITEM_ENTRADA = IDENT | {"cantidad", "costo", "a_caja", "repetir"}
CLAVES_CONTEO = {"contado", "incluye_entradas", "items"}
CLAVES_ITEM_CONTEO = IDENT | {"hay", "notas", "sistema", "en_cajas"}


def _claves(obj: dict, validas: set[str], donde: str) -> None:
    """Una clave mal escrita («Proveedor») no debe cambiar en silencio lo que se hace."""
    raras = set(obj) - validas
    if raras:
        falla(f"{donde}: claves que no conozco: {', '.join(sorted(raras))} (válidas: {', '.join(sorted(validas))}).")


def piezas_de(c, f: dict) -> str:
    filas = c.execute(text("""select distinct pz.nombre from conjunto_componente k
        join producto pz on pz.id = k.componente_id where k.conjunto_id = :p and k.cantidad > 0 order by 1"""),
                      {"p": f["producto_id"]}).fetchall()
    return " + ".join(r[0] for r in filas) or "ver su receta"


# ── 1. Leer y validar el plan (solo lectura) ────────────────────────────────

def preparar(c, plan: dict) -> dict:
    if not isinstance(plan, dict):
        falla("el plan debe ser un objeto JSON.")
    desconocidas = set(plan) - {"quien", "entradas", "conteo", "recalcular_conjuntos", "nota"}
    if desconocidas:
        falla(f"claves que no conozco en el plan: {', '.join(sorted(desconocidas))}.")
    quien = str(plan.get("quien") or inv.DUENO).strip().upper()
    emp = c.execute(text("select codigo, nombre_completo, activo from empleada where upper(codigo) = :c"),
                    {"c": quien}).fetchone()
    if emp is None:
        falla(f"no existe la empleada {quien}.")
    nombre_quien = emp[1]

    entradas = []
    for gi, g in enumerate(plan.get("entradas") or [], 1):
        donde = f"entrada {gi}"
        if not isinstance(g, dict):
            falla(f"{donde}: debe ser un objeto.")
        _claves(g, CLAVES_ENTRADA, donde)
        items_raw = g.get("items") or []
        if not items_raw:
            falla(f"{donde}: no trae items.")
        proveedor = (g.get("proveedor") or "").strip()
        if not proveedor and (g.get("documento") or any(isinstance(i, dict) and "costo" in i for i in items_raw)):
            falla(f"{donde}: trae «documento» o «costo» pero no «proveedor»: ¿es una compra? Pon el proveedor.")
        grupo = {"n": gi, "tipo": "compra" if proveedor else "llegada", "items": [],
                 "observacion": (g.get("observacion") or "").strip() or None}
        if proveedor:
            provs = c.execute(text("select id, nombre, activo from proveedor")).fetchall()
            match = [p for p in provs if inv.sin_acentos(p[1]) == inv.sin_acentos(proveedor)]
            if not match:
                falla(f"{donde}: no hay proveedor «{proveedor}». Hay: {', '.join(p[1] for p in provs)}.")
            grupo["proveedor_id"], grupo["proveedor"] = match[0][0], match[0][1]
            doc = (g.get("documento") or "").strip()
            if not doc:
                falla(f"{donde}: una compra necesita «documento» (p. ej. ROMANOS-1234-2026-11-19).")
            if len(doc) > 40:
                falla(f"{donde}: «documento» pasa de 40 caracteres.")
            if c.execute(text("select 1 from compra where upper(numero_documento) = upper(:d)"), {"d": doc}).first():
                falla(f"{donde}: la compra «{doc}» YA está registrada (¿doble captura?).")
            grupo["documento"] = doc
        else:
            if quien != inv.DUENO:
                falla(f"{donde}: una llegada sin proveedor la firma el dueño ({inv.DUENO}), como en el celular.")
            # Igual que llego_mercancia (`referencia or "maquilador"`), para que la revisión de repetidas compare lo mismo.
            grupo["referencia"] = ((g.get("referencia") or "").strip() or "maquilador")[:60]
            caja = (g.get("caja") or "").strip()
            grupo["caja_id"] = None
            if caja:
                fila = c.execute(text("select id from bodega_caja where upper(codigo) = upper(:c)"), {"c": caja}).first()
                if not fila:
                    falla(f"{donde}: no existe la caja «{caja}».")
                grupo["caja_id"], grupo["caja"] = fila[0], caja.upper()
        vistos = set()
        for ii, it in enumerate(items_raw, 1):
            d = f"{donde}, renglón {ii}"
            if not isinstance(it, dict):
                falla(f"{d}: debe ser un objeto.")
            _claves(it, CLAVES_ITEM_ENTRADA, d)
            f = inv.resolver(c, it, d)
            if f["id"] in vistos:
                falla(f"{d}: {f['sku']} se repite en la misma entrada; súmalo en un renglón.")
            vistos.add(f["id"])
            if f["es_conjunto"]:
                # Su entrada se reparte por la receta (una Chamarra RESTA un Pants Suelto) y eso ni la
                # vista previa ni el conteo ni la revisión de repetidas lo pueden seguir bien.
                falla(f"{d}: {inv.nombre_talla(f)} es un conjunto: da entrada a sus PIEZAS "
                      f"({piezas_de(c, f)}); el conjunto se recalcula solo.")
            cant = _entero(it.get("cantidad"), f"{d} «cantidad»", minimo=1)
            item = {"fila": f, "cantidad": cant, "a_caja": 0, "costo": None, "repetir": bool(it.get("repetir"))}
            if grupo["tipo"] == "compra":
                costo = it.get("costo")
                if costo == "actual":
                    costo = f["costo_referencia"]
                    if costo is None:
                        falla(f"{d}: {f['sku']} no tiene costo guardado; pon el de la remisión.")
                try:
                    item["costo"] = Decimal(str(costo)).quantize(Decimal("0.01"))
                except (InvalidOperation, ValueError):
                    falla(f"{d}: falta «costo» (el de la remisión) o vino inválido: {costo!r}.")
                if item["costo"] < 0:
                    falla(f"{d}: costo negativo.")
                if it.get("a_caja"):
                    falla(f"{d}: «a_caja» solo aplica a llegadas sin proveedor (como en el celular).")
            else:
                item["a_caja"] = _entero(it.get("a_caja") or 0, f"{d} «a_caja»", minimo=0)
                if item["a_caja"] > cant:
                    falla(f"{d}: no se puede guardar en caja más de lo que llegó.")
                en_cajas = int(f["bodega"]) + int(f["piso"])
                if item["a_caja"] and int(f["stock_actual"]) + cant < en_cajas + item["a_caja"]:
                    # BodegaService.ingresar_producto exige cajas ≤ total, medido ANTES del conteo.
                    falla(f"{d}: {f['sku']} está en {inv.cifra(f['stock_actual'])} con {en_cajas} en cajas: aunque lleguen "
                          f"{cant}, el total no alcanza para guardar {item['a_caja']} en caja. Deja «a_caja» en 0, "
                          "aplica primero el conteo de esa talla y guarda en caja en otro plan.")
                if not item["repetir"]:
                    rep = c.execute(text("""select created_at from movimiento_inventario
                        where variante_id = :v and tipo_movimiento = 'ENTRADA_COMPRA' and cantidad = :n
                          and coalesce(referencia,'') = :r and created_at > now() - make_interval(days => :d)
                        order by created_at desc limit 1"""),
                                    {"v": f["id"], "n": cant, "r": grupo["referencia"], "d": DIAS_REPETIDA}).first()
                    if rep:
                        falla(f"{d}: ya entraron {cant} de {f['sku']} con referencia «{grupo['referencia']}» el "
                              f"{rep[0].astimezone(inv.ZONA):%d-%b %H:%M}. Si de verdad es otra llegada, pon \"repetir\": true.")
            grupo["items"].append(item)
        entradas.append(grupo)

    conteo = None
    if plan.get("conteo"):
        cp = plan["conteo"]
        if not isinstance(cp, dict):
            falla("«conteo» debe ser un objeto.")
        _claves(cp, CLAVES_CONTEO, "conteo")
        contado = inv.parse_cuando(cp.get("contado"))
        incluye = cp.get("incluye_entradas")
        if incluye is None and plan.get("entradas"):
            falla("conteo: di si contaste antes o después de acomodar lo que llegó («incluye_entradas»: true/false).")
        if incluye is not None and not isinstance(incluye, bool):
            falla("conteo: «incluye_entradas» va true o false.")
        conteo = {"contado": contado, "incluye_entradas": True if incluye is None else incluye, "items": [],
                  "omitidos": []}
        vistos = set()
        for ii, it in enumerate(cp.get("items") or [], 1):
            d = f"conteo, renglón {ii}"
            if not isinstance(it, dict):
                falla(f"{d}: debe ser un objeto.")
            _claves(it, CLAVES_ITEM_CONTEO, d)
            if it.get("hay") is None:
                conteo["omitidos"].append(it.get("sku") or it.get("buscar") or str(ii))
                continue
            f = inv.resolver(c, it, d)
            if f["id"] in vistos:
                falla(f"{d}: {f['sku']} se repite en el conteo.")
            vistos.add(f["id"])
            if f["es_conjunto"]:
                falla(f"{d}: {inv.nombre_talla(f)} es un conjunto; su número sale de sus piezas: cuenta las piezas.")
            hay = _entero(it.get("hay"), f"{d} «hay»", minimo=0)
            otro = c.execute(text("""select contado_at, contado_por from conteo_inventario
                where variante_id = :v and contado_at > :t order by contado_at desc limit 1"""),
                             {"v": f["id"], "t": contado}).first()
            if otro:
                falla(f"{d}: {f['sku']} ya tiene un conteo MÁS NUEVO ({otro[0].astimezone(inv.ZONA):%d-%b %H:%M}, "
                      f"{otro[1]}). Si es este mismo conteo ya aplicado, no lo repitas.")
            caja = c.execute(text("""select tipo, created_at from bodega_movimiento
                where variante_id = :v and created_at > :t order by created_at limit 1"""),
                             {"v": f["id"], "t": contado}).first()
            if caja:
                # «desde» suma movimientos del TOTAL; lo que entra o sale de una caja cambia la tienda
                # sin que el total lo diga (o al revés), y la cuenta quedaría chueca.
                falla(f"{d}: {f['sku']} tuvo movimiento de cajas ({caja[0]}, {caja[1].astimezone(inv.ZONA):%d-%b %H:%M}) "
                      "después de la hora del conteo: vuelve a contar esa talla.")
            pendientes = c.execute(text("""select id, contado_at, diferencia, jornada_id from conteo_inventario
                where variante_id = :v and not ajustado and contado_at <= :t order by contado_at"""),
                                   {"v": f["id"], "t": contado}).fetchall()
            if "sistema" in it and it["sistema"] is not None and int(it["sistema"]) != f["stock_actual"]:
                print(f"   (nota: {f['sku']} estaba en {it['sistema']} en la plantilla y ahora está en {f['stock_actual']})")
            conteo["items"].append({"fila": f, "hay": hay, "notas": (it.get("notas") or "").strip(),
                                    "viejos": [tuple(x) for x in pendientes]})
        if not conteo["items"]:
            conteo = None if not conteo["omitidos"] else conteo

    recalc = plan.get("recalcular_conjuntos") or False
    if recalc not in (False, "todos"):
        falla("«recalcular_conjuntos» solo acepta \"todos\" (los de las piezas tocadas se recalculan solos).")
    if not entradas and not (conteo and conteo["items"]) and not recalc:
        falla("el plan no trae nada que hacer.")
    return {"quien": quien, "nombre_quien": nombre_quien, "entradas": entradas, "conteo": conteo,
            "recalcular": recalc}


def movido_desde(c, variante_id: int, desde) -> int:
    return int(c.execute(text("""select coalesce(sum(cantidad), 0) from movimiento_inventario
        where variante_id = :v and created_at > :t"""), {"v": variante_id, "t": desde}).scalar() or 0)


def conjuntos_desfasados(c) -> list[tuple[str, str, int, int]]:
    """(sku, nombre, dice, sus piezas dan) de cada talla de conjunto que no cuadra. Solo lee."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from pos_uniformes.database.models import Variante
    from pos_uniformes.services import conjunto_service as cs

    out = []
    with Session(bind=c) as s:
        for prod in cs.conjuntos_activos(s):
            receta = cs.receta_de(s, prod.id)
            for v in s.scalars(select(Variante).where(Variante.producto_id == prod.id, Variante.activo.is_(True))):
                debe = cs.stock_derivado(s, v, receta)
                if debe is not None and debe != int(v.stock_actual):
                    out.append((v.sku, f"{prod.nombre} {v.talla}", int(v.stock_actual), int(debe)))
    return sorted(out, key=lambda x: x[1])


# ── 2. Vista previa ─────────────────────────────────────────────────────────

def vista_previa(c, p: dict) -> list[str]:
    avisos: list[str] = []
    por_var: dict[int, dict] = {}

    def reg(f):
        return por_var.setdefault(f["id"], {"fila": f, "entra": 0, "a_caja": 0, "conteo": None})

    for g in p["entradas"]:
        if g["tipo"] == "compra":
            print(f"\n▸ Entrada {g['n']}: compra a {g['proveedor']} · {g['documento']}")
        else:
            caja = f" · a caja {g.get('caja') or 'nueva'}" if any(i["a_caja"] for i in g["items"]) else ""
            print(f"\n▸ Entrada {g['n']}: llegó mercancía (como el celular) · ref. «{g['referencia']}»{caja}")
        total = Decimal(0)
        for it in g["items"]:
            f = it["fila"]
            r = reg(f)
            r["entra"] += it["cantidad"]
            r["a_caja"] += it["a_caja"]
            extra = ""
            if it["costo"] is not None:
                total += it["costo"] * it["cantidad"]
                extra = f" · costo ${it['costo']}"
                precio = Decimal(str(f["precio_venta"] or 0))
                if precio > 0:
                    margen = (precio - it["costo"]) / precio
                    extra += f" (margen {margen:.0%} contra ${precio:.0f})"
                    if margen < MARGEN_BAJO:
                        avisos.append(f"{f['sku']} {inv.nombre_talla(f)}: margen {margen:.0%}, bajo (candidato a subir precio, no se aplica nada).")
                ref = f["costo_referencia"]
                if ref is not None and ref > 0 and abs(it["costo"] - ref) / ref > Decimal("0.30"):
                    avisos.append(f"{f['sku']}: el costo cambia de ${ref} a ${it['costo']} (más de 30 %).")
            if it["a_caja"]:
                extra += f" · {it['a_caja']} a caja"
            print(f"   +{it['cantidad']:<4} {f['sku']}  {inv.nombre_talla(f)}{extra}")
        if g["tipo"] == "compra":
            print(f"   Total de la compra: ${total:,.2f}")

    cont = p["conteo"]
    if cont and cont["items"]:
        print(f"\n▸ Conteo de las {cont['contado']:%H:%M} del {cont['contado']:%d-%b} "
              f"({'después' if cont['incluye_entradas'] else 'antes'} de acomodar lo que llegó)")
        for it in cont["items"]:
            f = it["fila"]
            r = reg(f)
            r["conteo"] = it
            it["desde"] = movido_desde(c, f["id"], cont["contado"])
    if cont and cont["omitidos"]:
        print(f"   ({len(cont['omitidos'])} renglones sin «hay»: se omiten)")

    print(f"\n{'SKU':<10} {'antes':>6} {'entra':>6} {'contó':>6} {'queda':>6}  talla")
    for r in por_var.values():
        f = r["fila"]
        antes = int(f["stock_actual"])
        cajas = int(f["bodega"]) + int(f["piso"])
        if r["conteo"]:
            it = r["conteo"]
            obj = inv.objetivo_tienda(it["hay"], it["desde"], r["entra"] - r["a_caja"], cont["incluye_entradas"])
            queda = obj + cajas + r["a_caja"]
            nota = f"  (desde el conteo se movieron {it['desde']:+d})" if it["desde"] else ""
            if obj < 0:
                avisos.append(f"{f['sku']}: con lo vendido desde el conteo la tienda quedaría en {obj}; ¿la hora del conteo es correcta?")
            if antes >= 0 and abs(queda - (antes + r["entra"])) >= 10:   # en negativo, brincar es lo esperado
                avisos.append(f"{f['sku']} {inv.nombre_talla(f)}: el conteo mueve {queda - antes - r['entra']:+d} piezas; confírmalo.")
            contado = str(it["hay"]) + (f"+{cajas}c" if cajas else "")
            for vid_viejo, cuando, dif, jornada in it["viejos"]:
                avisos.append(f"{f['sku']}: tiene un conteo viejo sin aplicar ({cuando.astimezone(inv.ZONA):%d-%b}, "
                              f"diferencia {dif:+d}{', jornada ' + str(jornada) if jornada else ''}). Al aplicar queda "
                              "marcado como superado por este, para que nadie lo aplique después encima.")
            print(f"{f['sku']:<10} {inv.cifra(antes):>6} {('+' + str(r['entra'])) if r['entra'] else '':>6} {contado:>6} {inv.cifra(queda):>6}  {inv.nombre_talla(f)}{nota}")
        else:
            queda = antes + r["entra"]
            print(f"{f['sku']:<10} {inv.cifra(antes):>6} {('+' + str(r['entra'])):>6} {'':>6} {inv.cifra(queda):>6}  {inv.nombre_talla(f)}")
            if antes < 0:
                avisos.append(f"{f['sku']} {inv.nombre_talla(f)} estaba en {inv.cifra(antes)}: queda en {inv.cifra(queda)}. "
                              "Ese número no es real (se vendió sin contar): agrega un conteo de esa talla.")
    if cont and cont["items"]:
        print("   («contó» = lo suelto en tienda; +Nc = lo que hay DENTRO de cajas, en almacén o en el piso, que el conteo no toca)")
    if p["recalcular"]:
        desf = conjuntos_desfasados(c)
        bajan = [d for d in desf if d[3] < d[2]]
        print(f"\n▸ Recalcular conjuntos desfasados de sus piezas: {len(desf)} talla(s), {len(bajan)} BAJAN")
        for sku, nombre, actual, debe in desf:
            print(f"   {sku:<10} {inv.cifra(actual):>5} → {inv.cifra(debe):<5} {nombre}{'   ↓ baja' if debe < actual else ''}")
        if bajan:
            avisos.append(f"{len(bajan)} conjunto(s) BAJAN al recalcular: el kiosko dejará de ofrecer lo que sus piezas no alcanzan a armar.")
    for a in avisos:
        print(f"⚠ {a}")
    return avisos


# ── 3. Aplicar con los servicios del POS ────────────────────────────────────

def aplicar(session, p: dict) -> dict:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import (
        ConteoInventario, MovimientoInventario, Proveedor, RolUsuario, Usuario, Variante,
    )
    from pos_uniformes.services import bodega_movil_service as bm
    from pos_uniformes.services import conjunto_service as cs
    from pos_uniformes.services.compra_service import CompraItemInput, CompraService
    from pos_uniformes.services.conteo_service import confirmar_ajustes_lote, registrar_conteo

    max_mov = int(session.scalar(select(func.coalesce(func.max(MovimientoInventario.id), 0))))
    tocadas = {it["fila"]["id"] for g in p["entradas"] for it in g["items"]}
    cont = p["conteo"]
    items_conteo = cont["items"] if cont else []
    tocadas |= {it["fila"]["id"] for it in items_conteo}
    # Candado sobre las tallas tocadas ANTES de leer nada: una venta de la caja en este momento espera,
    # y lo que se lee es lo último (populate_existing), no una copia vieja del identity map.
    bloqueadas = session.scalars(select(Variante).where(Variante.id.in_(tocadas)).order_by(Variante.id)
                                 .with_for_update().execution_options(populate_existing=True)).all()
    antes = {v.id: int(v.stock_actual) for v in bloqueadas}

    # Lo movido desde el conteo se mide ANTES de las entradas de este plan.
    for it in items_conteo:
        it["desde"] = int(session.scalar(select(func.coalesce(func.sum(MovimientoInventario.cantidad), 0)).where(
            MovimientoInventario.variante_id == it["fila"]["id"],
            MovimientoInventario.created_at > cont["contado"])) or 0)

    for g in p["entradas"]:
        if g["tipo"] == "compra":
            admin = session.scalar(select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True))
                                   .order_by(Usuario.id).limit(1))
            if admin is None:
                raise RuntimeError("No hay usuario ADMIN activo para firmar la compra.")
            compra = CompraService.crear_borrador(
                session, session.get(Proveedor, g["proveedor_id"]), admin, g["documento"],
                [CompraItemInput(it["fila"]["id"], it["cantidad"], it["costo"]) for it in g["items"]],
                observacion=g["observacion"],
            )
            CompraService.confirmar_compra(session, compra)
        else:
            bm.llego_mercancia(
                session, items=[{"variante_id": it["fila"]["id"], "cantidad": it["cantidad"], "a_caja": it["a_caja"]}
                                for it in g["items"]],
                quien_code=p["quien"], quien=p["nombre_quien"], caja_id=g["caja_id"],
                caja_nueva=g["caja_id"] is None, referencia=g["referencia"],
            )
        session.flush()

    if items_conteo:
        entra_tienda: dict[int, int] = {}
        for g in p["entradas"]:
            for it in g["items"]:
                entra_tienda[it["fila"]["id"]] = entra_tienda.get(it["fila"]["id"], 0) + it["cantidad"] - it["a_caja"]
        ids = []
        firma = f"{p['nombre_quien']} ({p['quien']})"
        for it in items_conteo:
            vid = it["fila"]["id"]
            obj = inv.objetivo_tienda(it["hay"], it["desde"], entra_tienda.get(vid, 0), cont["incluye_entradas"])
            nota = (f"Con Claude: contó {it['hay']} a las {cont['contado']:%H:%M} del {cont['contado']:%d-%b}"
                    + (f"; {it['desde']:+d} desde entonces" if it["desde"] else "")
                    + (f". {it['notas']}" if it["notas"] else ""))
            conteo = registrar_conteo(session, vid, stock_fisico=obj, contado_por=firma, notas=nota[:500])
            session.flush()
            ids.append(conteo.id)
        ajustados, omitidos = confirmar_ajustes_lote(session, ids, p["quien"])
        session.flush()
        # Los conteos viejos sin aplicar de esas tallas quedan superados: aplicarlos después en el
        # POS sumaría su diferencia vieja encima de este conteo.
        superados = 0
        for it, nuevo_id in zip(items_conteo, ids):
            for vid_viejo, *_ in it["viejos"]:
                viejo = session.get(ConteoInventario, vid_viejo)
                if viejo is not None and not viejo.ajustado:
                    viejo.ajustado = True
                    viejo.notas = ((viejo.notas or "") + f" [superado por el conteo {nuevo_id}]").strip()
                    superados += 1
        if superados:
            session.flush()
            print(f"Conteos viejos sin aplicar marcados como superados: {superados}.")
        print(f"\nConteo: {ajustados} talla(s) ajustadas, {omitidos} ya cuadraban.")

    if p["recalcular"] == "todos":
        n = cs.sincronizar_todo(session, creado_por=p["quien"])
        session.flush()
        print(f"Conjuntos recalculados: {n} talla(s).")

    # Resultado real: cada talla tocada y cada conjunto que se movió por arrastre.
    movs = session.execute(
        select(MovimientoInventario.variante_id, func.sum(MovimientoInventario.cantidad), func.count())
        .where(MovimientoInventario.id > max_mov).group_by(MovimientoInventario.variante_id)
    ).all()
    cambios = {int(v): (int(s), int(n)) for v, s, n in movs}
    print(f"\n{'SKU':<10} {'antes':>6} {'ahora':>6}  talla")
    for v in session.scalars(select(Variante).where(Variante.id.in_(set(cambios) | tocadas)).order_by(Variante.id)):
        a = antes.get(v.id, int(v.stock_actual) - cambios.get(v.id, (0, 0))[0])
        marca = "" if v.id in tocadas else "   (conjunto o pieza, por arrastre)"
        print(f"{v.sku:<10} {inv.cifra(a):>6} {inv.cifra(v.stock_actual):>6}  {v.producto.nombre} {v.talla}{marca}")
    return {"movimientos": sum(n for _, n in cambios.values()), "tallas": len(cambios)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    _comun.agregar_argumentos_db(ap)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--aplicar", action="store_true", help="guardar (una transacción)")
    modo.add_argument("--ensayo", action="store_true", help="hacerlo de verdad y deshacerlo (base local)")
    ap.add_argument("--ensayo-en-caja", action="store_true", help="permitir --ensayo contra la caja (pedir OK antes)")
    args = ap.parse_args()

    try:
        plan = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        falla(f"no pude leer el plan: {exc}")

    escribe = args.aplicar or args.ensayo
    engine = _comun.motor(args, solo_lectura=not escribe)
    import os

    host = engine.url.host or engine.url.query.get("host") or os.environ.get("PGHOST")
    if args.ensayo and host not in LOCALES and not args.ensayo_en_caja:
        falla("--ensayo contra la caja también la bloquea un momento: úsalo contra una copia local, "
              "o agrega --ensayo-en-caja con el OK de Daniel. La vista previa (sin flags) no escribe nada.")

    with engine.connect() as c:
        p = preparar(c, plan)
        avisos = vista_previa(c, p)
        c.rollback()
    if not escribe:
        print("\nVISTA PREVIA: no se cambió nada. Con el OK de Daniel: el mismo comando con --aplicar.")
        return 0

    from sqlalchemy.orm import Session

    print("\n── " + ("APLICANDO" if args.aplicar else "ENSAYO (se deshace al final)") + " ──")
    with Session(engine) as session:
        try:
            with engine.connect() as c:          # se vuelve a validar con lo de este momento
                p = preparar(c, plan)
                c.rollback()
            res = aplicar(session, p)
            if args.aplicar:
                session.commit()
                print(f"\n✓ Guardado: {res['movimientos']} movimiento(s) en {res['tallas']} talla(s).")
            else:
                session.rollback()
                print(f"\nEnsayo: {res['movimientos']} movimiento(s) en {res['tallas']} talla(s); se deshizo todo.")
        except BaseException:
            session.rollback()
            print("\n✗ Falló: no se guardó nada.")
            raise
    if avisos and args.aplicar:
        print(f"({len(avisos)} aviso(s) de la vista previa; ver arriba.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
