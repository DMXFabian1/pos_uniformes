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
    BodegaCaja,
    BodegaContenido,
    ConteoInventario,
    ConteoJornada,
    DemandaNoAtendida,
    LibretaVenta,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_jornada_service import DUENO_CODE

SEMANAS_OBJETIVO = 4          # Daniel: "4 semanas, igual para todas" (2026-09-13)
SEMANAS_A_LA_MANO = 2         # cuánto conviene tener colgado antes de ir a las cajas por más
VENTANA_MAX_DIAS = 84         # no mirar ventas de hace más de 12 semanas: la temporada cambia
MIN_DIAS_OBSERVADOS = 7       # con menos de una semana, "sin datos" en vez de "no se mueve"
TIPOS_SALIDA = ("venta", "apartado")  # lo que se lleva piezas del piso

URGENTE = "URGENTE"
PEDIR = "PEDIR"
SURTIR = "SURTIR"             # no hace falta pedir: hay en cajas, hay que pasarlo al piso
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
    conto: int                      # a la mano (lo colgado, lo que la empleada ve)
    en_cajas: int                   # guardado en cajas de bodega, esté la caja donde esté
    cajas: tuple                    # (("A-12", 8), ("A-3", 4)) para enseñar de dónde
    surtir: int                     # cuántas pasar de las cajas al piso
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

    @property
    def total(self) -> int:
        return self.conto + self.en_cajas


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

    @property
    def piezas_a_surtir(self) -> int:
        return sum(l.surtir for l in self.lineas)

    @property
    def tallas_a_surtir(self) -> int:
        return sum(1 for l in self.lineas if l.surtir > 0)


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


def _en_cajas(session: Session, variante_ids: list[int]) -> dict[int, tuple[int, tuple]]:
    """{variante_id: (total, (("A-12", 8), ...))} de lo guardado en cajas de
    bodega. Da igual si la caja está en el almacén o bajo el rack: lo que no
    está colgado no lo ve la empleada al contar."""
    if not variante_ids:
        return {}
    filas = session.execute(
        select(BodegaContenido.variante_id, BodegaCaja.codigo, BodegaContenido.cantidad)
        .join(BodegaCaja, BodegaCaja.id == BodegaContenido.caja_id)
        .where(BodegaContenido.variante_id.in_(variante_ids), BodegaContenido.cantidad > 0)
        .order_by(BodegaContenido.cantidad.desc(), BodegaCaja.codigo)
    ).all()
    por_vid: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for vid, codigo, cantidad in filas:
        por_vid[int(vid)].append((str(codigo), int(cantidad)))
    return {vid: (sum(c for _, c in cajas), tuple(cajas)) for vid, cajas in por_vid.items()}


def _suma_desde(eventos: list[tuple[date, int]], desde: date) -> int:
    return sum(p for f, p in eventos if f >= desde)


def _ellas_sugieren(notas: str | None) -> int | None:
    m = _PEDIDO_EN_NOTAS.search(notas or "")
    return int(m.group(1)) if m else None


# --- la cuenta ---------------------------------------------------------------------

@dataclass(frozen=True)
class Sugerencia:
    sugerido: int            # cuántas pedir al maquilador
    surtir: int              # cuántas pasar de las cajas al piso
    ritmo_semana: float
    semanas_cubiertas: float | None   # con el total (a la mano + cajas)
    estado: str


def sugerir(*, conto: int, vendidas: int, dias_observados: int, pidieron: int, en_cajas: int = 0, semanas: int = SEMANAS_OBJETIVO) -> Sugerencia:
    """Qué hacer con una talla: pedir, surtir del almacén, o nada.

    - La demanda no atendida cuenta como venta perdida: entra al ritmo, porque
      si hubiera habido pieza se habría vendido.
    - Se pide contra el TOTAL (a la mano + en cajas): lo guardado también es
      inventario. Se surte cuando a la mano no alcanza para `SEMANAS_A_LA_MANO`
      y en cajas sí hay.
    """
    dias = max(1, dias_observados)
    ritmo = (vendidas + pidieron) / (dias / 7)
    total = conto + en_cajas
    cubiertas = (total / ritmo) if ritmo > 0 else None
    sugerido = max(0, math.ceil(ritmo * semanas - total)) if ritmo > 0 else 0
    if en_cajas > 0 and ritmo > 0:
        surtir = min(en_cajas, max(0, math.ceil(ritmo * SEMANAS_A_LA_MANO) - conto))
    elif en_cajas > 0 and conto <= 0:
        surtir = min(en_cajas, 1)   # sin ritmo pero nada colgado: que al menos se vea
    else:
        surtir = 0
    if total <= 0 and (vendidas > 0 or pidieron > 0):
        estado = URGENTE
    elif sugerido > 0:
        estado = PEDIR
    elif surtir > 0:
        estado = SURTIR
    elif ritmo == 0:
        estado = SIN_DATOS if dias_observados < MIN_DIAS_OBSERVADOS else NO_SE_MUEVE
    else:
        estado = BIEN
    return Sugerencia(sugerido, surtir, round(ritmo, 2), (round(cubiertas, 1) if cubiertas is not None else None), estado)


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
    cajas = _en_cajas(session, variante_ids)

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
        en_cajas, detalle_cajas = cajas.get(variante.id, (0, ()))
        sug = sugerir(conto=conteo.stock_fisico, vendidas=vendidas, dias_observados=dias, pidieron=pidieron_n, en_cajas=en_cajas)

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
            en_cajas=en_cajas,
            cajas=detalle_cajas,
            surtir=sug.surtir,
            anterior=int(anterior.stock_fisico) if anterior else None,
            anterior_at=anterior_at,
            vendidas=vendidas,
            dias_observados=dias,
            ritmo_semana=sug.ritmo_semana,
            semanas_cubiertas=sug.semanas_cubiertas,
            pidieron=pidieron_n,
            ellas_sugieren=_ellas_sugieren(conteo.notas),
            sugerido=sug.sugerido,
            estado=sug.estado,
            pedido_anterior=int(pedido_ant.pedido) if pedido_ant else None,
            pedido_anterior_at=pedido_ant_at,
            vendidas_desde_pedido=vendidas_desde_pedido,
            pedido=conteo.pedido,
        ))
    return Revision(jornada.id, jornada.titulo, jornada.empleada_nombre or jornada.empleada_code, hoy, lineas)


def guardar_pedidos(session: Session, jornada: ConteoJornada, pedidos: dict[int, int | None], *, decidido_por: str, hoy: date | None = None) -> int:
    """Guarda lo que Daniel decidió por talla (`{conteo_id: piezas}`) y lo que
    se le sugirió en ese momento. `None` o vacío borra la decisión. Solo el dueño."""
    if (decidido_por or "").strip().upper() != DUENO_CODE:
        raise PermissionError("Solo el dueño decide el pedido.")
    sugeridos = {l.conteo_id: l.sugerido for l in revisar(session, jornada, hoy=hoy).lineas}
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


# --- la historia de una escuela (o prenda básica) --------------------------------

@dataclass(frozen=True)
class TallaEscuela:
    variante_id: int
    talla: str
    color: str
    vendidas: int
    pidieron: int
    a_la_mano: int
    en_cajas: int
    pedido_total: int      # lo que Daniel ha pedido de esta talla (últimas 12 semanas)


@dataclass(frozen=True)
class PrendaEscuela:
    producto: str
    tipo_pieza: str
    vendidas: int
    pidieron: int
    a_la_mano: int
    en_cajas: int
    pedido_total: int
    tallas: list[TallaEscuela]     # de la que más vende a la que menos


@dataclass(frozen=True)
class HistoriaEscuela:
    titulo: str
    hoy: date
    semanas: list[SemanaHistorica]
    prendas: list[PrendaEscuela]   # de la que más vende a la que menos
    vendidas_total: int
    pidieron_total: int
    pedido_total: int

    @property
    def prendas_del_80(self) -> int:
        """Cuántas prendas hacen el 80 % de lo vendido: dónde está el negocio."""
        if self.vendidas_total <= 0:
            return 0
        acumulado = 0
        for i, p in enumerate(self.prendas, start=1):
            acumulado += p.vendidas
            if acumulado >= 0.8 * self.vendidas_total:
                return i
        return len(self.prendas)


def historia_de_escuela(session: Session, escuela_id: int | None, tipo_pieza: str = "", *, hoy: date | None = None, semanas: int = SEMANAS_HISTORIA) -> HistoriaEscuela:
    """Cómo se ha vendido una escuela (o una prenda de básicos): piezas por
    semana y, por prenda y talla, vendidas, pidieron-y-no-había, lo que hay
    y lo que se ha pedido. Para ver qué se pide más y qué menos."""
    from pos_uniformes.services.conteo_jornada_service import alcance

    hoy = hoy or date.today()
    grupos = alcance(session, escuela_id, tipo_pieza)
    if escuela_id is None:
        titulo = f"Básicos · {tipo_pieza}" if tipo_pieza else "Básicos"
    else:
        from pos_uniformes.database.models import Escuela

        e = session.get(Escuela, escuela_id)
        titulo = e.nombre if e is not None else f"Escuela {escuela_id}"

    inicio = _lunes(hoy) - timedelta(weeks=semanas - 1)
    ventas = _ventas_por_sku(session, inicio)
    pidieron = _pidieron_por_sku(session, inicio)
    variante_ids = [v.variante_id for g in grupos for v in g["variantes"]]
    cajas = _en_cajas(session, variante_ids)
    pedidos: dict[int, int] = defaultdict(int)
    if variante_ids:
        desde_dt = datetime.combine(inicio, datetime.min.time())
        for vid, pedido in session.execute(
            select(ConteoInventario.variante_id, ConteoInventario.pedido).where(
                ConteoInventario.variante_id.in_(variante_ids),
                ConteoInventario.pedido.is_not(None),
                ConteoInventario.pedido_decidido_at >= desde_dt,
            )
        ).all():
            pedidos[int(vid)] += int(pedido or 0)

    por_semana: dict[date, list[int]] = {inicio + timedelta(weeks=i): [0, 0] for i in range(semanas)}
    prendas: list[PrendaEscuela] = []
    for g in grupos:
        tallas: list[TallaEscuela] = []
        for v in g["variantes"]:
            sku = str(v.sku or "")
            vend = sum(p for f, p in ventas.get(sku, []) if f >= inicio)
            pid = sum(p for f, p in pidieron.get(sku, []) if f >= inicio)
            for f, p in ventas.get(sku, []):
                k = _lunes(f)
                if k in por_semana:
                    por_semana[k][0] += p
            for f, p in pidieron.get(sku, []):
                k = _lunes(f)
                if k in por_semana:
                    por_semana[k][1] += p
            en_cajas = cajas.get(v.variante_id, (0, ()))[0]
            tallas.append(TallaEscuela(
                variante_id=v.variante_id, talla=str(v.talla or ""), color=str(v.color or ""),
                # A la mano = total − lo que está en cajas (cualquier caja, tenga o
                # no ubicación), igual que en el resto de Revisar.
                vendidas=vend, pidieron=pid, a_la_mano=max(0, int(getattr(v, "stock_actual", 0) or 0) - en_cajas), en_cajas=en_cajas,
                pedido_total=pedidos.get(v.variante_id, 0),
            ))
        tallas.sort(key=lambda t: (-t.vendidas, -t.pidieron, t.talla))
        prendas.append(PrendaEscuela(
            producto=str(g.get("producto_nombre") or ""), tipo_pieza=str(g.get("tipo_pieza") or ""),
            vendidas=sum(t.vendidas for t in tallas), pidieron=sum(t.pidieron for t in tallas),
            a_la_mano=sum(t.a_la_mano for t in tallas), en_cajas=sum(t.en_cajas for t in tallas),
            pedido_total=sum(t.pedido_total for t in tallas), tallas=tallas,
        ))
    prendas.sort(key=lambda p: (-p.vendidas, -p.pidieron, p.producto))
    return HistoriaEscuela(
        titulo=titulo, hoy=hoy,
        semanas=[SemanaHistorica(k, v, q) for k, (v, q) in sorted(por_semana.items())],
        prendas=prendas,
        vendidas_total=sum(p.vendidas for p in prendas),
        pidieron_total=sum(p.pidieron for p in prendas),
        pedido_total=sum(p.pedido_total for p in prendas),
    )


# --- el comparativo con el conteo anterior --------------------------------------

@dataclass(frozen=True)
class LineaComparativo:
    variante_id: int
    producto: str
    talla: str
    color: str
    antes: int | None        # el conteo anterior de esa talla (None = primer conteo)
    antes_at: date | None
    ahora: int
    vendidas: int            # entre los dos conteos, según la Libreta
    pidieron: int

    @property
    def cambio(self) -> int | None:
        return None if self.antes is None else self.ahora - self.antes

    @property
    def sin_explicar(self) -> int | None:
        """antes − vendidas − ahora. Positivo = piezas que faltan sin venta que
        lo explique (merma, venta sin registrar); negativo = sobran (llegó
        mercancía que no se anotó)."""
        return None if self.antes is None else self.antes - self.vendidas - self.ahora


@dataclass(frozen=True)
class Comparativo:
    titulo: str
    quien: str
    fecha: date | None            # cuándo se terminó esta jornada
    lineas: list[LineaComparativo]   # de lo que más se movió a lo que menos

    @property
    def con_anterior(self) -> list[LineaComparativo]:
        return [l for l in self.lineas if l.antes is not None]

    @property
    def antes_total(self) -> int:
        return sum(l.antes for l in self.con_anterior)

    @property
    def ahora_total(self) -> int:
        return sum(l.ahora for l in self.lineas)

    @property
    def vendidas_total(self) -> int:
        return sum(l.vendidas for l in self.lineas)

    @property
    def faltan(self) -> int:
        return sum(l.sin_explicar for l in self.con_anterior if l.sin_explicar and l.sin_explicar > 0)

    @property
    def sobran(self) -> int:
        return -sum(l.sin_explicar for l in self.con_anterior if l.sin_explicar and l.sin_explicar < 0)

    @property
    def anterior_at(self) -> date | None:
        fechas = [l.antes_at for l in self.con_anterior if l.antes_at]
        return max(fechas) if fechas else None


def comparativo_de_jornada(session: Session, jornada: ConteoJornada, *, hoy: date | None = None) -> Comparativo:
    """Este conteo contra el anterior de cada talla: cuánto había, cuánto hay,
    cuánto se vendió en medio y cuánto no se explica. Daniel (2026-09-14):
    "ver cómo estuvo de diferente, qué se movió más y cuánto"."""
    r = revisar(session, jornada, hoy=hoy)
    lineas = [
        LineaComparativo(
            variante_id=l.variante_id, producto=l.producto, talla=l.talla, color=l.color,
            antes=l.anterior, antes_at=l.anterior_at, ahora=l.conto, vendidas=l.vendidas, pidieron=l.pidieron,
        )
        for l in r.lineas
    ]
    lineas.sort(key=lambda l: (-(abs(l.cambio) if l.cambio is not None else -1), -l.vendidas, l.producto, l.talla))
    fecha = _fecha(jornada.terminada_at) if jornada.terminada_at else None
    return Comparativo(titulo=r.titulo, quien=r.quien, fecha=fecha, lineas=lineas)
