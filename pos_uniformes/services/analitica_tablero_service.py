"""La pestaña Analítica del POS, toda desde la Libreta (2026-11-07).

Daniel: «mejoremos la pestaña de analítica» → «hazlo completo». La mitad de la
pestaña leía `venta`/`venta_detalle`, que quedaron en 8 registros de abril:
ingreso, tickets, métodos de pago, top clientes… todo salía casi en cero. Lo
que de verdad se vende está en la Libreta del kiosko; de ahí sale todo esto.

Reglas de la casa que se respetan:
- **Solo dinero real**: «Cobrado» = efectivo + lo que LLEGA por la terminal
  (tras el 4.5%), de ventas y abonos. El valor de los apartados no se suma.
- **La cifra oficial por defecto**: el cobrado lleva los ajustes del dueño en
  sus cortes (`ajustes_en_rango`); lo real solo con Ctrl+Shift+R.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

_CENT = Decimal("0.01")

# Periodos (la clave viaja en el combo)
HOY, SEMANA, MES, TREINTA, MANUAL = "hoy", "semana", "mes", "30d", "manual"
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

#: «Se va a acabar»: lo que con su ritmo de venta no llega a estas semanas.
SEMANAS_DE_ALERTA = 2.0
#: Con menos piezas vendidas en la ventana, no hay ritmo que creerle.
VENDIDAS_MINIMAS = 2
#: Cuántos días se miran para sacar el ritmo de venta.
DIAS_DE_RITMO = 30


# ─── Periodos ───────────────────────────────────────────────────────────────

def rango(clave: str, ancla: date, manual: tuple[date, date] | None = None) -> tuple[date, date]:
    """(primer día, último día) del periodo que contiene a `ancla`."""
    if clave == HOY:
        return ancla, ancla
    if clave == SEMANA:
        lunes = ancla - timedelta(days=ancla.weekday())
        return lunes, lunes + timedelta(days=6)
    if clave == MES:
        inicio = ancla.replace(day=1)
        siguiente = (inicio + timedelta(days=32)).replace(day=1)
        return inicio, siguiente - timedelta(days=1)
    if clave == TREINTA:
        return ancla - timedelta(days=29), ancla
    desde, hasta = manual or (ancla, ancla)
    return min(desde, hasta), max(desde, hasta)


def mover(clave: str, ancla: date, pasos: int) -> date:
    """La misma clase de periodo, `pasos` hacia atrás (−) o adelante (+)."""
    if clave == HOY:
        return ancla + timedelta(days=pasos)
    if clave == SEMANA:
        return ancla + timedelta(weeks=pasos)
    if clave == MES:
        y, m = ancla.year, ancla.month + pasos
        while m < 1:
            y, m = y - 1, m + 12
        while m > 12:
            y, m = y + 1, m - 12
        return date(y, m, 1)
    return ancla + timedelta(days=30 * pasos)


def anterior(desde: date, hasta: date, clave: str) -> tuple[date, date]:
    """El periodo con el que se compara: el mismo tamaño, justo antes."""
    if clave == MES:
        fin = desde - timedelta(days=1)
        return fin.replace(day=1), fin
    largo = (hasta - desde).days + 1
    return desde - timedelta(days=largo), desde - timedelta(days=1)


def nombre_comparacion(clave: str) -> str:
    return {HOY: "ayer", SEMANA: "la semana pasada", MES: "el mes pasado",
            TREINTA: "los 30 días anteriores"}.get(clave, "el periodo anterior")


def texto_periodo(clave: str, desde: date, hasta: date, hoy: date | None = None) -> str:
    hoy = hoy or date.today()
    if clave == HOY:
        prefijo = "Hoy, " if desde == hoy else ("Ayer, " if desde == hoy - timedelta(days=1) else "")
        return f"{prefijo}{_DIAS[desde.weekday()]} {desde.day} de {_MESES[desde.month - 1]}"
    if clave == MES:
        return f"{_MESES[desde.month - 1].capitalize()} {desde.year}"
    if desde.month == hasta.month:
        return f"{desde.day} al {hasta.day} de {_MESES[hasta.month - 1]}"
    return f"{desde.day} de {_MESES[desde.month - 1]} al {hasta.day} de {_MESES[hasta.month - 1]}"


def limites(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Del inicio del primer día al final del último, en hora local con zona."""
    return (datetime.combine(desde, time.min).astimezone(),
            datetime.combine(hasta, time.max).astimezone())


# ─── Las cifras ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Cifras:
    cobrado: Decimal = Decimal("0.00")      # efectivo + lo que llega por terminal (ventas y abonos)
    efectivo: Decimal = Decimal("0.00")
    tarjeta_neto: Decimal = Decimal("0.00")
    operaciones: int = 0                    # ventas + apartados + abonos
    ventas: int = 0                         # para el ticket promedio
    importe_ventas: Decimal = Decimal("0.00")
    piezas: int = 0

    @property
    def ticket_promedio(self) -> Decimal:
        if not self.ventas:
            return Decimal("0.00")
        return (self.importe_ventas / self.ventas).quantize(_CENT)


def cifras(rows: list, *, ajuste: Decimal = Decimal("0.00")) -> Cifras:
    """Las cuatro cifras de un periodo, a partir de sus operaciones (puro).

    `ajuste`: lo que el dueño cambió en sus cortes del periodo (cifra oficial);
    se aplica al efectivo, que es donde lo aplica él."""
    from pos_uniformes.services.corte_caja_service import resumir_periodo

    rows = [x for x in rows if str(getattr(x, "tipo", "")) in ("venta", "apartado", "abono")]
    r = resumir_periodo(rows)
    efectivo = (r.efectivo + Decimal(ajuste or 0)).quantize(_CENT)
    ventas = [x for x in rows if str(getattr(x, "tipo", "")) == "venta"]
    importe = sum((Decimal(str(x.monto_total or 0)) for x in ventas), Decimal("0.00"))
    piezas = sum(int(x.piezas or 0) for x in rows if str(getattr(x, "tipo", "")) in ("venta", "apartado"))
    return Cifras(
        cobrado=(efectivo + r.tarjeta_neto).quantize(_CENT),
        efectivo=efectivo,
        tarjeta_neto=r.tarjeta_neto,
        operaciones=len(rows),
        ventas=len(ventas),
        importe_ventas=importe.quantize(_CENT),
        piezas=piezas,
    )


def cambio(ahora, antes) -> tuple[str, str]:
    """(«↑ 12 %», tono) contra el periodo anterior. Tono: sube / baja / igual / nuevo."""
    ahora, antes = Decimal(str(ahora or 0)), Decimal(str(antes or 0))
    if antes == 0:
        return ("nuevo", "nuevo") if ahora > 0 else ("—", "igual")
    pct = ((ahora - antes) / antes * 100).quantize(Decimal("1"))
    if pct > 0:
        return f"↑ {pct} %", "sube"
    if pct < 0:
        return f"↓ {abs(pct)} %", "baja"
    return "= igual", "igual"


@dataclass(frozen=True)
class Dia:
    dia: date
    cobrado: Decimal
    piezas: int


def cobrado_por_dia(rows: list, desde: date, hasta: date) -> list[Dia]:
    """Un renglón por día del periodo, aunque no haya habido nada (puro)."""
    from pos_uniformes.services.corte_caja_service import resumir_periodo

    por_dia: dict[date, list] = defaultdict(list)
    for x in rows:
        momento = x.created_at.astimezone() if x.created_at.tzinfo else x.created_at
        por_dia[momento.date()].append(x)
    salida = []
    d = desde
    while d <= hasta:
        r = resumir_periodo(por_dia.get(d, []))
        piezas = sum(int(x.piezas or 0) for x in por_dia.get(d, []) if str(x.tipo) in ("venta", "apartado"))
        salida.append(Dia(d, (r.efectivo + r.tarjeta_neto).quantize(_CENT), piezas))
        d += timedelta(days=1)
    return salida


# ─── Se va a acabar ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PorAcabarse:
    sku: str
    nombre: str
    talla: str
    escuela: str
    vendidas: int                 # en los últimos DIAS_DE_RITMO días
    existencia: int
    semanas: float | None         # cuánto alcanza con ese ritmo; 0 = ya no hay

    @property
    def texto_semanas(self) -> str:
        if self.existencia <= 0:
            return "ya no hay"
        if self.semanas is None:
            return "—"
        dias = self.semanas * 7
        return f"{dias:.0f} días" if dias < 14 else f"{self.semanas:.1f} sem"


def por_acabarse(vendidas_por_sku: dict[str, int], existencias: dict[str, dict], *,
                 dias: int = DIAS_DE_RITMO, tope: int = 15) -> list[PorAcabarse]:
    """Lo que se vende y no va a alcanzar (puro).

    `existencias`: {sku: {stock, nombre, talla, escuela}}. Primero lo que ya
    no hay, luego lo que menos alcanza."""
    semanas_ventana = dias / 7
    salida = []
    for sku, vendidas in vendidas_por_sku.items():
        if vendidas < VENDIDAS_MINIMAS or sku not in existencias:
            continue
        e = existencias[sku]
        stock = int(e.get("stock") or 0)
        ritmo = vendidas / semanas_ventana
        semanas = (stock / ritmo) if ritmo > 0 and stock > 0 else 0.0
        if stock > 0 and semanas >= SEMANAS_DE_ALERTA:
            continue
        salida.append(PorAcabarse(sku, e.get("nombre", sku), e.get("talla", ""), e.get("escuela", ""),
                                  vendidas, stock, round(semanas, 2)))
    salida.sort(key=lambda p: (p.existencia > 0, p.semanas or 0, -p.vendidas))
    return salida[:tope]


def cargar_por_acabarse(session, *, hoy: date | None = None) -> list[PorAcabarse]:
    from sqlalchemy import select

    from pos_uniformes.database.models import Escuela, Producto, Variante
    from pos_uniformes.services.libreta_service import listar_operaciones
    from pos_uniformes.services.analitica_libreta_service import desglosar

    hoy = hoy or date.today()
    desde, hasta = limites(hoy - timedelta(days=DIAS_DE_RITMO - 1), hoy)
    filas = desglosar(listar_operaciones(session, desde=desde, hasta=hasta, employee_code=None))
    vendidas: dict[str, int] = defaultdict(int)
    for f in filas:
        if f.sku and f.sku != "SIN-CODIGO":
            vendidas[f.sku] += int(f.cantidad)
    if not vendidas:
        return []
    existencias = {}
    consulta = (
        select(Variante.sku, Variante.stock_actual, Variante.talla, Producto.nombre, Escuela.nombre)
        .join(Producto, Producto.id == Variante.producto_id)
        .outerjoin(Escuela, Escuela.id == Producto.escuela_id)
        .where(Variante.sku.in_(list(vendidas)), Variante.activo.is_(True))
    )
    for sku, stock, talla, nombre, escuela in session.execute(consulta):
        existencias[sku] = {"stock": stock, "talla": talla, "nombre": nombre, "escuela": escuela or ""}
    return por_acabarse(dict(vendidas), existencias)


# ─── Todo junto ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tablero:
    clave: str
    desde: date
    hasta: date
    ahora: Cifras
    antes: Cifras
    dias: tuple[Dia, ...] = ()
    filas: tuple = ()                       # FilaVenta del periodo, para los cortes por escuela/prenda/…
    acabarse: tuple[PorAcabarse, ...] = ()
    afluencia: object | None = None         # FilaAfluencia total, si hay cámaras
    real: bool = False
    ajuste: Decimal = Decimal("0.00")
    a_medias: bool = False                  # el periodo no ha terminado: se comparan los mismos días
    hasta_la_hora: bool = False             # hoy: contra ayer hasta esta misma hora
    hoy: date | None = None


def cargar(session, clave: str, ancla: date, *, manual: tuple[date, date] | None = None,
           real: bool = False, hoy: date | None = None, ahora: datetime | None = None) -> Tablero:
    from pos_uniformes.services.analitica_libreta_service import filas_de_periodo
    from pos_uniformes.services.corte_caja_service import ajustes_en_rango
    from pos_uniformes.services.libreta_service import listar_operaciones

    hoy = hoy or date.today()
    desde, hasta = rango(clave, ancla, manual)
    a_desde, a_hasta = anterior(desde, hasta, clave)
    # Un periodo que no ha terminado se compara con los MISMOS días del
    # anterior: el sábado, lunes–sábado contra lunes–sábado, no contra la
    # semana pasada completa (que siempre «ganaría»).
    a_medias = desde <= hoy < hasta
    if a_medias:
        a_hasta = min(a_hasta, a_desde + (hoy - desde))
    ini, fin = limites(desde, hasta)
    a_ini, a_fin = limites(a_desde, a_hasta)
    hasta_la_hora = clave == HOY and desde == hoy
    if hasta_la_hora:
        # Hoy a las 11 contra ayer completo siempre «baja»: se compara con
        # ayer hasta esta misma hora.
        momento = (ahora or datetime.now()).astimezone()
        a_fin = datetime.combine(a_desde, momento.timetz())
        a_medias = True
    rows = listar_operaciones(session, desde=ini, hasta=fin, employee_code=None)
    rows_antes = listar_operaciones(session, desde=a_ini, hasta=a_fin, employee_code=None)
    ajuste = Decimal("0.00") if real else ajustes_en_rango(session, ini, fin)
    ajuste_antes = Decimal("0.00") if real else ajustes_en_rango(session, a_ini, a_fin)
    try:
        acabarse = tuple(cargar_por_acabarse(session, hoy=hoy))
    except Exception:  # noqa: BLE001 — sin esto, lo demás se ve igual
        session.rollback()
        acabarse = ()
    try:
        from pos_uniformes.services.afluencia_service import resumen_afluencia, totales

        afl = totales(resumen_afluencia(session, desde=ini.replace(tzinfo=None), hasta=fin.replace(tzinfo=None)))
    except Exception:  # noqa: BLE001 — sin cámaras no hay afluencia
        session.rollback()
        afl = None
    return Tablero(
        clave=clave, desde=desde, hasta=hasta,
        ahora=cifras(rows, ajuste=ajuste), antes=cifras(rows_antes, ajuste=ajuste_antes),
        dias=tuple(cobrado_por_dia(rows, desde, hasta)) if (hasta - desde).days >= 1 else (),
        filas=tuple(filas_de_periodo(session, ini, fin)),
        acabarse=acabarse, afluencia=afl, real=real, ajuste=ajuste, a_medias=a_medias, hoy=hoy,
        hasta_la_hora=hasta_la_hora,
    )
