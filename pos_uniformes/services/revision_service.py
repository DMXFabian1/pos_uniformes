"""Revisar un conteo = decidir qué pedir.

Para cada talla contada en una jornada junta lo que el sistema sabe:

- cuántas hay (lo que contaron);
- cuántas se vendieron desde el conteo anterior (Libreta, por SKU);
- a qué ritmo se van (piezas por semana) y para cuántas semanas alcanza;
- cuántas veces la pidieron y no había (demanda no atendida);
- lo que la empleada anotó en la hoja ("Pedido: N");
- lo que Daniel pidió la última vez y qué pasó después.

Con eso sugiere un pedido para cubrir `SEMANAS_OBJETIVO` semanas y guarda la
decisión de Daniel en el propio renglón del conteo. Esa decisión es lo que la
siguiente revisión usa para aprender.

Todo se calcula en Python sobre pocas filas (una escuela) para que funcione
igual en Postgres y en el SQLite de los tests.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    ConteoInventario,
    ConteoJornada,
    DemandaNoAtendida,
    LibretaVenta,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_jornada_service import DUENO_CODE

SEMANAS_OBJETIVO = 4          # Daniel: "4 semanas, igual para todas" (2026-09-13)
VENTANA_MAX_DIAS = 84         # no mirar ventas de hace más de 12 semanas: la temporada cambia
MIN_DIAS_OBSERVADOS = 7       # con menos de una semana, "sin datos" en vez de "no se mueve"
TIPOS_SALIDA = ("venta", "apartado")  # lo que se lleva piezas del piso

URGENTE = "URGENTE"
PEDIR = "PEDIR"
BIEN = "BIEN"
NO_SE_MUEVE = "NO_SE_MUEVE"
SIN_DATOS = "SIN_DATOS"

_PEDIDO_EN_NOTAS = re.compile(r"Pedido:\s*(\d+)")


@dataclass(frozen=True)
class LineaRevision:
    conteo_id: int
    variante_id: int
    producto: str
    talla: str
    color: str
    conto: int
    anterior: int | None            # último conteo previo a esta jornada
    anterior_at: date | None
    vendidas: int                   # desde el conteo anterior (o desde que hay Libreta)
    dias_observados: int
    ritmo_semana: float
    semanas_cubiertas: float | None  # None cuando no se mueve
    pidieron: int                   # piezas que pidieron y no había
    ellas_sugieren: int | None      # "Pedido: N" en la hoja
    sugerido: int
    estado: str
    pedido_anterior: int | None
    pedido_anterior_at: date | None
    vendidas_desde_pedido: int | None
    pedido: int | None              # lo ya decidido en esta jornada

    @property
    def urgente(self) -> bool:
        return self.estado == URGENTE


@dataclass(frozen=True)
class Revision:
    jornada_id: int
    titulo: str
    quien: str
    hoy: date
    lineas: list[LineaRevision]

    @property
    def piezas_sugeridas(self) -> int:
        return sum(l.sugerido for l in self.lineas)

    @property
    def tallas_a_pedir(self) -> int:
        return sum(1 for l in self.lineas if l.sugerido > 0)

    @property
    def urgentes(self) -> int:
        return sum(1 for l in self.lineas if l.urgente)

    @property
    def piezas_pedidas(self) -> int:
        return sum(l.pedido or 0 for l in self.lineas)


# --- fechas ------------------------------------------------------------------------

def _fecha(momento: datetime | None) -> date | None:
    if momento is None:
        return None
    # SQLite devuelve naive (hora local); Postgres, con zona.
    return momento.astimezone().date() if momento.tzinfo else momento.date()


# --- lecturas ----------------------------------------------------------------------

def _ventas_por_sku(session: Session, desde: date) -> dict[str, list[tuple[date, int]]]:
    """(fecha, piezas) por SKU en la Libreta desde `desde`. Un pase por las
    ventas del periodo; el detalle es JSON y se abre en Python."""
    inicio = datetime.combine(desde, datetime.min.time())
    filas = session.execute(
        select(LibretaVenta.created_at, LibretaVenta.detalle)
        .where(LibretaVenta.tipo.in_(TIPOS_SALIDA), LibretaVenta.created_at >= inicio)
    ).all()
    por_sku: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for creado, detalle in filas:
        fecha = _fecha(creado)
        for linea in detalle or []:
            sku = str(linea.get("sku") or "").strip()
            if not sku:
                continue
            try:
                piezas = int(linea.get("cantidad") or 0)
            except (TypeError, ValueError):
                continue
            if piezas > 0 and fecha is not None:
                por_sku[sku].append((fecha, piezas))
    return por_sku


def _primera_venta(session: Session) -> date | None:
    return _fecha(session.scalar(select(func.min(LibretaVenta.created_at))))


def _pidieron_por_sku(session: Session, desde: date) -> dict[str, list[tuple[date, int]]]:
    inicio = datetime.combine(desde, datetime.min.time())
    filas = session.execute(
        select(DemandaNoAtendida.sku, DemandaNoAtendida.created_at, DemandaNoAtendida.piezas)
        .where(DemandaNoAtendida.tipo == "talla_agotada", DemandaNoAtendida.created_at >= inicio)
    ).all()
    out: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for sku, creado, piezas in filas:
        fecha = _fecha(creado)
        if sku and fecha is not None:
            out[str(sku)].append((fecha, int(piezas or 1)))
    return out


def _suma_desde(eventos: list[tuple[date, int]], desde: date) -> int:
    return sum(p for f, p in eventos if f >= desde)


def _ellas_sugieren(notas: str | None) -> int | None:
    m = _PEDIDO_EN_NOTAS.search(notas or "")
    return int(m.group(1)) if m else None


# --- la cuenta ---------------------------------------------------------------------

def sugerir(*, conto: int, vendidas: int, dias_observados: int, pidieron: int, semanas: int = SEMANAS_OBJETIVO) -> tuple[int, float, float | None, str]:
    """Devuelve (sugerido, ritmo_semana, semanas_cubiertas, estado).

    La demanda no atendida cuenta como venta perdida: entra al ritmo, porque si
    hubiera habido pieza se habría vendido.
    """
    dias = max(1, dias_observados)
    ritmo = (vendidas + pidieron) / (dias / 7)
    cubiertas = (conto / ritmo) if ritmo > 0 else None
    sugerido = max(0, math.ceil(ritmo * semanas - conto)) if ritmo > 0 else 0
    if conto <= 0 and (vendidas > 0 or pidieron > 0):
        estado = URGENTE
    elif sugerido > 0:
        estado = PEDIR
    elif ritmo == 0:
        estado = SIN_DATOS if dias_observados < MIN_DIAS_OBSERVADOS else NO_SE_MUEVE
    else:
        estado = BIEN
    return sugerido, round(ritmo, 2), (round(cubiertas, 1) if cubiertas is not None else None), estado


def revisar(session: Session, jornada: ConteoJornada, *, hoy: date | None = None) -> Revision:
    """Todo lo que Daniel necesita ver por talla para decidir el pedido."""
    hoy = hoy or date.today()
    filas = session.execute(
        select(ConteoInventario, Variante, Producto.nombre)
        .join(Variante, Variante.id == ConteoInventario.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(ConteoInventario.jornada_id == jornada.id)
        .order_by(Producto.nombre, ConteoInventario.id)
    ).all()
    if not filas:
        return Revision(jornada.id, jornada.titulo, jornada.empleada_nombre or jornada.empleada_code, hoy, [])

    variante_ids = [c.variante_id for c, _, _ in filas]
    # Conteos previos de estas tallas (no de esta jornada), del más reciente al más viejo.
    previos: dict[int, list[ConteoInventario]] = defaultdict(list)
    for c in session.scalars(
        select(ConteoInventario)
        .where(
            ConteoInventario.variante_id.in_(variante_ids),
            or_(ConteoInventario.jornada_id.is_(None), ConteoInventario.jornada_id != jornada.id),
        )
        .order_by(ConteoInventario.contado_at.desc(), ConteoInventario.id.desc())
    ).all():
        previos[c.variante_id].append(c)

    piso = hoy - timedelta(days=VENTANA_MAX_DIAS)
    primera_venta = _primera_venta(session)
    ventas = _ventas_por_sku(session, piso)
    pidieron = _pidieron_por_sku(session, piso)

    lineas: list[LineaRevision] = []
    for conteo, variante, producto in filas:
        fecha_conteo = _fecha(conteo.contado_at) or hoy
        anteriores = [p for p in previos.get(variante.id, []) if (_fecha(p.contado_at) or hoy) <= fecha_conteo]
        anterior = anteriores[0] if anteriores else None
        anterior_at = _fecha(anterior.contado_at) if anterior else None

        # Ventana observada: desde el conteo anterior, pero nunca antes de que
        # exista la Libreta ni más atrás que la ventana máxima.
        candidatos = [piso]
        if anterior_at:
            candidatos.append(anterior_at)
        if primera_venta:
            candidatos.append(primera_venta)
        desde = max(candidatos)
        dias = max(0, (hoy - desde).days)
        if primera_venta is None:
            dias = 0

        sku = variante.sku or ""
        vendidas = _suma_desde(ventas.get(sku, []), desde)
        pidieron_n = _suma_desde(pidieron.get(sku, []), desde)
        sugerido, ritmo, cubiertas, estado = sugerir(conto=conteo.stock_fisico, vendidas=vendidas, dias_observados=dias, pidieron=pidieron_n)

        con_pedido = [p for p in anteriores if p.pedido is not None]
        pedido_ant = con_pedido[0] if con_pedido else None
        pedido_ant_at = _fecha(pedido_ant.pedido_decidido_at or pedido_ant.contado_at) if pedido_ant else None
        vendidas_desde_pedido = _suma_desde(ventas.get(sku, []), pedido_ant_at) if pedido_ant_at else None

        lineas.append(LineaRevision(
            conteo_id=conteo.id,
            variante_id=variante.id,
            producto=str(producto),
            talla=str(variante.talla or ""),
            color=str(variante.color or ""),
            conto=int(conteo.stock_fisico),
            anterior=int(anterior.stock_fisico) if anterior else None,
            anterior_at=anterior_at,
            vendidas=vendidas,
            dias_observados=dias,
            ritmo_semana=ritmo,
            semanas_cubiertas=cubiertas,
            pidieron=pidieron_n,
            ellas_sugieren=_ellas_sugieren(conteo.notas),
            sugerido=sugerido,
            estado=estado,
            pedido_anterior=int(pedido_ant.pedido) if pedido_ant else None,
            pedido_anterior_at=pedido_ant_at,
            vendidas_desde_pedido=vendidas_desde_pedido,
            pedido=conteo.pedido,
        ))
    return Revision(jornada.id, jornada.titulo, jornada.empleada_nombre or jornada.empleada_code, hoy, lineas)


def guardar_pedidos(session: Session, jornada: ConteoJornada, pedidos: dict[int, int | None], *, decidido_por: str) -> int:
    """Guarda lo que Daniel decidió por talla (`{conteo_id: piezas}`) y lo que
    se le sugirió en ese momento. `None` o vacío borra la decisión. Solo el dueño."""
    if (decidido_por or "").strip().upper() != DUENO_CODE:
        raise PermissionError("Solo el dueño decide el pedido.")
    sugeridos = {l.conteo_id: l.sugerido for l in revisar(session, jornada).lineas}
    conteos = {
        c.id: c
        for c in session.scalars(
            select(ConteoInventario).where(ConteoInventario.jornada_id == jornada.id, ConteoInventario.id.in_(list(pedidos)))
        ).all()
    }
    guardados = 0
    for conteo_id, piezas in pedidos.items():
        c = conteos.get(conteo_id)
        if c is None:
            continue
        if piezas is None or piezas == "":
            c.pedido = None
            c.pedido_sugerido = None
            c.pedido_decidido_at = None
        else:
            c.pedido = max(0, int(piezas))
            c.pedido_sugerido = sugeridos.get(conteo_id)
            c.pedido_decidido_at = func.now()
            guardados += 1
        session.add(c)
    session.flush()
    return guardados


# --- la hoja de pedido ---------------------------------------------------------------

def _agrupar_pedido(revision: Revision) -> list[tuple[str, list[tuple[str, str, int]]]]:
    """[(prenda, [(talla, color, piezas), ...])] con lo que Daniel decidió (> 0),
    en el orden de la revisión."""
    from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

    grupos: dict[str, list[tuple[str, str, int]]] = {}
    for l in revision.lineas:
        if not l.pedido or l.pedido <= 0:
            continue
        nombre = nombre_para_hoja(l.producto, revision.titulo)
        grupos.setdefault(nombre, []).append((l.talla, l.color, int(l.pedido)))
    return list(grupos.items())


def texto_pedido(revision: Revision) -> str:
    """El pedido como mensaje: para Telegram o para copiarlo al WhatsApp del
    maquilador. Una prenda por bloque, tallas con su cantidad."""
    grupos = _agrupar_pedido(revision)
    fecha = revision.hoy.strftime("%d/%m/%Y")
    if not grupos:
        return f"Pedido {revision.titulo} · {fecha}\n(sin piezas)"
    partes = [f"Pedido {revision.titulo} · {fecha}"]
    total = 0
    colores = len({c for _, tallas in grupos for _, c, _ in tallas}) > 1
    for prenda, tallas in grupos:
        partes.append("")
        partes.append(prenda)
        for talla, color, piezas in tallas:
            etiqueta = f"{talla} {color}".strip() if colores else talla
            partes.append(f"  {etiqueta or 'Uni'}: {piezas}")
            total += piezas
    partes.append("")
    partes.append(f"Total: {total} piezas")
    return "\n".join(partes)


def html_pedido(revision: Revision) -> str:
    """La misma hoja, para imprimir en carta (QTextDocument: atributos HTML,
    no CSS de tablas)."""
    import html as _html

    grupos = _agrupar_pedido(revision)
    fecha = revision.hoy.strftime("%d/%m/%Y")
    total = sum(p for _, tallas in grupos for _, _, p in tallas)
    partes = [
        "<html><body style='font-family: Arial, sans-serif; color: #1a1a1a;'>",
        f"<h2 style='color:#6f331d; margin-bottom:2px;'>Pedido · {_html.escape(revision.titulo)}</h2>",
        f"<p style='margin-top:0; color:#555;'>{fecha} · {total} piezas · contó {_html.escape(revision.quien)}</p>",
    ]
    if not grupos:
        partes.append("<p>(sin piezas)</p>")
    for prenda, tallas in grupos:
        partes.append(f"<h3 style='color:#6f331d; margin:14px 0 4px 0;'>{_html.escape(prenda)}</h3>")
        partes.append("<table cellpadding='5' cellspacing='0' border='1' bordercolor='#d9c7b8' width='60%'>")
        partes.append("<tr bgcolor='#f5ebe0'><th align='left'>Talla</th><th align='left'>Color</th><th align='right'>Piezas</th></tr>")
        for i, (talla, color, piezas) in enumerate(tallas):
            fondo = " bgcolor='#faf7f3'" if i % 2 else ""
            partes.append(f"<tr{fondo}><td>{_html.escape(talla or 'Uni')}</td><td>{_html.escape(color)}</td><td align='right'><b>{piezas}</b></td></tr>")
        partes.append("</table>")
    partes.append("</body></html>")
    return "\n".join(partes)


# --- la historia de una talla ------------------------------------------------------

SEMANAS_HISTORIA = 12


@dataclass(frozen=True)
class ConteoHistorico:
    fecha: date
    conto: int
    quien: str
    pedido: int | None
    sugerido: int | None
    vendidas_despues: int | None   # hasta el siguiente conteo (o hasta hoy); None si no hay Libreta


@dataclass(frozen=True)
class SemanaHistorica:
    inicio: date          # lunes
    vendidas: int
    pidieron: int

    @property
    def etiqueta(self) -> str:
        return self.inicio.strftime("%d/%m")


@dataclass(frozen=True)
class Historia:
    variante_id: int
    producto: str
    talla: str
    color: str
    hoy: date
    conteos: list[ConteoHistorico]        # del más reciente al más viejo
    semanas: list[SemanaHistorica]         # de la más vieja a la actual
    pedido_total: int                      # todo lo que Daniel ha pedido de esta talla
    vendidas_total: int                    # en las semanas mostradas

    @property
    def maximo_semana(self) -> int:
        return max((s.vendidas + s.pidieron for s in self.semanas), default=0)


def _lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())


def historia_de_talla(session: Session, variante_id: int, *, hoy: date | None = None, semanas: int = SEMANAS_HISTORIA) -> Historia:
    """Cómo ha evolucionado una talla: conteos con lo que se pidió y lo que se
    vendió después, y ventas por semana (con lo que pidieron y no había)."""
    hoy = hoy or date.today()
    variante = session.get(Variante, variante_id)
    if variante is None:
        raise ValueError(f"No existe la variante {variante_id}")
    producto = session.get(Producto, variante.producto_id)

    inicio = _lunes(hoy) - timedelta(weeks=semanas - 1)
    hay_libreta = _primera_venta(session) is not None
    ventas = _ventas_por_sku(session, min(inicio, hoy - timedelta(days=365))).get(variante.sku or "", [])
    pidieron = _pidieron_por_sku(session, inicio).get(variante.sku or "", [])

    por_semana: dict[date, list[int]] = {inicio + timedelta(weeks=i): [0, 0] for i in range(semanas)}
    for f, p in ventas:
        k = _lunes(f)
        if k in por_semana:
            por_semana[k][0] += p
    for f, p in pidieron:
        k = _lunes(f)
        if k in por_semana:
            por_semana[k][1] += p
    semanas_out = [SemanaHistorica(k, v, q) for k, (v, q) in sorted(por_semana.items())]

    filas = list(session.scalars(
        select(ConteoInventario)
        .where(ConteoInventario.variante_id == variante_id)
        .order_by(ConteoInventario.contado_at.desc(), ConteoInventario.id.desc())
    ).all())
    conteos: list[ConteoHistorico] = []
    siguiente: date | None = None   # fecha del conteo posterior (vamos del más nuevo al más viejo)
    for c in filas:
        fecha = _fecha(c.contado_at) or hoy
        if hay_libreta:
            tope = siguiente or (hoy + timedelta(days=1))
            vendidas_despues = sum(p for f, p in ventas if fecha <= f < tope)
        else:
            vendidas_despues = None
        conteos.append(ConteoHistorico(
            fecha=fecha, conto=int(c.stock_fisico), quien=str(c.contado_por or ""),
            pedido=c.pedido, sugerido=c.pedido_sugerido, vendidas_despues=vendidas_despues,
        ))
        siguiente = fecha
    return Historia(
        variante_id=variante_id,
        producto=str(producto.nombre if producto else ""),
        talla=str(variante.talla or ""),
        color=str(variante.color or ""),
        hoy=hoy,
        conteos=conteos,
        semanas=semanas_out,
        pedido_total=sum(c.pedido or 0 for c in conteos),
        vendidas_total=sum(s.vendidas for s in semanas_out),
    )
