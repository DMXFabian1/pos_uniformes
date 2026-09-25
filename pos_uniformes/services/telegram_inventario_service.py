"""Las respuestas de inventario del bot: prenda, contar, escuela y faltas.

El bot sabía de dinero y de gente, no de lo que hay en el estante — había que
abrir el POS para la pregunta más común de todas, "¿cuánto cuesta y cuántas
hay?" (Daniel, 2026-09-25).

Aquí no se calcula nada: se le pregunta a los mismos servicios que usan el
kiosko, el panel y el mapa, y se acomoda para una pantalla de celular. Si una
cifra no cuadra con su pantalla, el error está en el servicio de origen.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Escuela
from pos_uniformes.utils.text_normalization import normalize_text_unicode

#: Cuántos renglones caben sin que el mensaje se vuelva un muro.
TOPE = 8

#: Hacia atrás para "lo que pidieron y no había".
DIAS_FALTAS = 7


def _parecido(texto: str, candidato: str) -> bool:
    return normalize_text_unicode(texto) in normalize_text_unicode(candidato)


# ------------------------------------------------------------------ /prenda

def prenda(session: Session, texto: str) -> str:
    """Precio y existencia por talla. La pregunta de todos los días."""
    from pos_uniformes.scripts.cambiar_precio import buscar_prendas, tallas_de

    texto = (texto or "").strip()
    if not texto:
        return "¿Cuál prenda? Por ejemplo:\n/prenda playera justo sierra"

    encontradas = buscar_prendas(session, texto)
    if not encontradas:
        # El nombre completo no siempre es el que uno diría: probar por partes.
        todas = buscar_prendas(session, "")
        encontradas = [
            p for p in todas
            if all(_parecido(t, str(p.nombre_base or p.nombre)) for t in texto.split())
        ]
    if not encontradas:
        return f"No encontré nada que diga «{texto}»."
    if len(encontradas) > 1:
        nombres = "\n".join(f"· {p.nombre_base or p.nombre}" for p in encontradas[:TOPE])
        mas = f"\n… y {len(encontradas) - TOPE} más" if len(encontradas) > TOPE else ""
        return f"«{texto}» empata con {len(encontradas)}:\n{nombres}{mas}\n\nDime cuál con más palabras."

    p = encontradas[0]
    escuela = session.get(Escuela, p.escuela_id).nombre if p.escuela_id else "general"
    variantes = tallas_de(session, p, None)
    if not variantes:
        return f"{p.nombre_base}\n{escuela}\n\nNo tiene tallas activas."

    precios = sorted({float(v.precio_venta) for v in variantes})
    precio = (
        f"${precios[0]:,.2f}" if len(precios) == 1
        else f"${precios[0]:,.2f} a ${precios[-1]:,.2f}"
    )
    # Mismo orden de tallas que en todas partes (CH, MD, GD, EXG…), no el
    # alfabético; y agrupadas por color, como están en el estante.
    from pos_uniformes.services.conteo_service import _talla_sort_key

    por_color: dict[str, list] = {}
    for v in variantes:
        c = str(v.color or "").strip()
        c = "" if c.lower() in ("sin color", "unico", "único") else c
        por_color.setdefault(c, []).append(v)

    lineas = [f"{p.nombre_base}", f"{escuela} · {precio}", ""]
    for color in sorted(por_color, key=lambda c: (c == "", normalize_text_unicode(c))):
        if len(por_color) > 1:
            lineas.append(f"— {color or 'sin color'} —")
        for v in sorted(por_color[color], key=_talla_sort_key):
            stock = int(v.stock_actual)
            marca = "⚠️" if stock < 0 else ("—" if stock == 0 else f"{stock}")
            lineas.append(f"{str(v.talla)}: {marca}")
    hay = sum(max(0, int(v.stock_actual)) for v in variantes)
    lineas.append("")
    lineas.append(f"En total: {hay} piezas")
    return "\n".join(lineas)


# ------------------------------------------------------------------ /contar

def contar(session: Session) -> str:
    """Lo que toca contar, lo más urgente primero. El mismo orden del kiosko."""
    from pos_uniformes.services import conteo_jornada_service as jn

    filas = jn.lo_que_toca(session, limite=TOPE)
    if not filas:
        return "No hay nada pendiente de contar. ✅"
    lineas = ["Lo que toca contar:", ""]
    for f in filas:
        punto = {"rojo": "🔴", "ambar": "🟠"}.get(f.salud, "·")
        lineas.append(f"{punto} {f.titulo}\n   {f.motivo}")
    return "\n".join(lineas)


# ----------------------------------------------------------------- /escuela

def escuela(session: Session, texto: str) -> str:
    """Cómo va una escuela: contada, surtida, vendida y sentida."""
    from pos_uniformes.services import escuela_estado_service as ee

    texto = (texto or "").strip()
    if not texto:
        return "¿Cuál escuela? Por ejemplo:\n/escuela conalep"

    activas = session.scalars(select(Escuela).where(Escuela.activo.is_(True))).all()
    encontradas = [e for e in activas if _parecido(texto, str(e.nombre))]
    if not encontradas:
        return f"No encontré ninguna escuela que diga «{texto}»."
    if len(encontradas) > 1:
        nombres = "\n".join(f"· {e.nombre}" for e in encontradas[:TOPE])
        return f"«{texto}» empata con {len(encontradas)}:\n{nombres}\n\nDime cuál con más palabras."

    est = ee.estado_de(session, int(encontradas[0].id))
    punto = {"rojo": "🔴", "ambar": "🟠", "verde": "🟢"}.get(est.salud, "·")
    lineas = [
        f"{punto} {est.nombre}",
        est.titular,
        "",
        f"Contada: {est.pct_al_dia}% ({est.al_dia} de {est.tallas} tallas)",
        f"En tienda: {est.piezas_en_tienda} piezas · {est.agotadas} tallas agotadas",
        f"Vendido (30 d): {est.vendido_piezas} piezas",
    ]
    if est.pedido:
        lineas.append(f"Por pedir: {len(est.pedido)} tallas")
    if est.faltas_sentidas:
        top = est.faltas_sentidas[0]
        lineas.append(f"Pidieron y no había: {len(est.faltas_sentidas)} (la más, {top.prenda} {top.talla})")
    if est.quien_en_proceso:
        lineas.append(f"Contando ahora: {est.quien_en_proceso}")
    lineas.append("")
    lineas.append(f"Se contó {est.ultimo_conteo.texto()}")
    return "\n".join(lineas)


# ------------------------------------------------------------------ /faltas

def faltas(session: Session, dias: int = DIAS_FALTAS, *, hoy: date | None = None) -> str:
    """Lo que se tocó estando agotado: la lista de qué pedir."""
    from pos_uniformes.services import demanda_service

    hasta_dia = hoy or date.today()
    hasta = datetime.combine(hasta_dia, time.max, tzinfo=timezone.utc)
    desde = datetime.combine(hasta_dia - timedelta(days=int(dias)), time.min, tzinfo=timezone.utc)

    filas = demanda_service.listar(session, desde, hasta)
    agrupadas = demanda_service.por_producto_talla(filas)
    if not agrupadas:
        return f"Nadie pidió algo que no hubiera en los últimos {dias} días. ✅"

    lineas = [f"Pidieron y no había ({dias} días):", ""]
    for f in agrupadas[:TOPE]:
        veces = "una vez" if f.veces == 1 else f"{f.veces} veces"
        urgente = " 🔴" if f.urgente else ""
        lineas.append(f"· {f.clave} — {veces}{urgente}")
    if len(agrupadas) > TOPE:
        lineas.append(f"… y {len(agrupadas) - TOPE} más")
    return "\n".join(lineas)
