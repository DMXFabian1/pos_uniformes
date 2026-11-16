"""El resumen de lo que «Aplicar» le hace al inventario (tanda 2, 2026-11-15).

Para cada talla de una jornada dice lo que de verdad pasa al corregir:

- **el sistema decía** (`stock_sistema`): lo que el sistema tenía en tienda
  cuando contaron; ya está guardado en el renglón del conteo.
- **contó** y la **diferencia** (contó − el sistema decía), también guardadas.
- **vendidas desde** el conteo: piezas que salieron por la Libreta después de
  `contado_at`, con el mismo reparto de conjuntos que usa `revision_service`
  (un Pants 3pz vendido también es un 2pz y una playera). Ventas y apartados
  suman; un «cambio» suma lo que se lleva y resta lo que regresa. Una venta
  que el dueño borró ya no está en la Libreta (y su stock regresó), así que no
  cuenta.
- **tienda hoy**: `stock_actual − lo que hay en cajas`. `stock_actual` incluye
  lo guardado en cajas (`BodegaContenido`, ver `bodega_service.stock_disponible_tienda`);
  el conteo es solo de tienda.
- **queda hoy**: lo que el sistema dirá en tienda después de corregir. Aplicar
  hace `stock_actual += diferencia` (`conteo_service.confirmar_ajustes_lote`),
  así que es `tienda hoy + diferencia` mientras la talla no se ha ajustado; ya
  ajustada, es la tienda de hoy.
- **ajuste posterior**: la fecha del primer `AJUSTE_ENTRADA`/`AJUSTE_SALIDA`
  de esa talla después del conteo que no sea el de este mismo renglón
  (`CONTEO-<id>`): otro conteo aplicado o un ajuste a mano. Esas tallas
  recibirían la diferencia otra vez. Los ajustes que hace sola la venta
  (`libreta:N`, p. ej. el pants suelto que deja una chamarra, o una operación
  borrada) y el stock calculado de un conjunto (`derivado:`) no cuentan: son
  movimientos que la diferencia ya respeta.

Y el total: tallas a corregir, piezas que entran y que salen, el valor a
precio de venta, lo vendido desde el conteo y cuántas tallas tuvieron otro
ajuste. Solo lee; no cambia la regla de aplicar ni la de sugerir.

Pocas consultas: los renglones de la jornada, las cajas, la Libreta desde el
conteo más viejo y los ajustes desde ahí (más el reparto de conjuntos de
`revision_service`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    BodegaContenido,
    ConteoInventario,
    ConteoJornada,
    LibretaVenta,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    Variante,
)

TIPOS_QUE_SACAN = ("venta", "apartado")   # como revision_service.TIPOS_SALIDA
TIPO_CAMBIO = "cambio"                    # cambio_service.TIPO: regresa una, se lleva otra
TIPOS_AJUSTE = (TipoMovimientoInventario.AJUSTE_ENTRADA, TipoMovimientoInventario.AJUSTE_SALIDA)
# Ajustes que no son «otro ajuste»: los hace sola la venta (libreta:N, libreta:N:borrada)
# o el stock calculado de un conjunto (conjunto_service.PREFIJO_DERIVADO).
PREFIJOS_AUTOMATICOS = ("libreta:", "derivado:")


def referencia_de(conteo_id: int) -> str:
    """La referencia con que `confirmar_ajustes_lote` firma el ajuste de un renglón."""
    return f"CONTEO-{int(conteo_id)}"


@dataclass(frozen=True)
class TallaResumen:
    conteo_id: int
    variante_id: int
    producto: str
    talla: str
    stock_sistema: int              # lo que el sistema decía en tienda al contar
    conto: int                      # stock_fisico
    diferencia: int                 # conto − stock_sistema (la que Aplicar suma)
    ajustado: bool
    vendidas_desde: int             # piezas que salieron después del conteo
    tienda_hoy: int                 # stock_actual − en cajas
    queda_hoy: int                  # lo que dirá el sistema en tienda al corregir
    precio_venta: Decimal | None    # None si la talla no tiene precio
    ajuste_posterior: datetime | None   # el primer ajuste ajeno después del conteo

    @property
    def por_corregir(self) -> bool:
        """Aplicar todavía la mueve (mismo criterio que `aplicar_jornada`)."""
        return not self.ajustado and self.diferencia != 0

    @property
    def valor(self) -> Decimal | None:
        """La diferencia a precio de venta; None sin precio."""
        if self.precio_venta is None:
            return None
        return self.precio_venta * self.diferencia


@dataclass(frozen=True)
class ResumenAjuste:
    jornada_id: int
    tallas: tuple[TallaResumen, ...]
    tallas_a_corregir: int
    entran: int                     # piezas que suben (sobraban)
    salen: int                      # piezas que bajan (faltaban)
    valor: Decimal                  # entran − salen a precio de venta (sin las que no tienen precio)
    tallas_sin_precio: int          # a corregir y sin precio: no entran al valor
    vendidas_desde: int
    tallas_con_ajuste_posterior: int

    @property
    def a_corregir(self) -> tuple[TallaResumen, ...]:
        return tuple(t for t in self.tallas if t.por_corregir)

    @property
    def con_ajuste_posterior(self) -> tuple[TallaResumen, ...]:
        return tuple(t for t in self.tallas if t.ajuste_posterior is not None)

    @property
    def a_corregir_con_ajuste_posterior(self) -> tuple[TallaResumen, ...]:
        """Las que recibirían la diferencia otra vez si se aplica hoy."""
        return tuple(t for t in self.tallas if t.por_corregir and t.ajuste_posterior is not None)

    @property
    def piezas_netas(self) -> int:
        return self.entran - self.salen


# --- la cuenta (pura) ---------------------------------------------------------------

def _precio(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        precio = Decimal(str(valor))
    except Exception:  # noqa: BLE001 — un precio raro es «sin precio»
        return None
    return precio if precio > 0 else None


def queda_hoy(*, tienda_hoy: int, diferencia: int, ajustado: bool) -> int:
    """Lo que dirá el sistema en tienda después de corregir (como hace Aplicar)."""
    return int(tienda_hoy) if ajustado else int(tienda_hoy) + int(diferencia)


def resumir(tallas, *, jornada_id: int = 0) -> ResumenAjuste:
    """El total del ajuste a partir de las tallas (sin base)."""
    tallas = tuple(tallas)
    corregir = [t for t in tallas if t.por_corregir]
    entran = sum(t.diferencia for t in corregir if t.diferencia > 0)
    salen = -sum(t.diferencia for t in corregir if t.diferencia < 0)
    valor = sum((t.valor for t in corregir if t.valor is not None), Decimal("0"))
    return ResumenAjuste(
        jornada_id=jornada_id,
        tallas=tallas,
        tallas_a_corregir=len(corregir),
        entran=entran,
        salen=salen,
        valor=valor,
        tallas_sin_precio=sum(1 for t in corregir if t.precio_venta is None),
        vendidas_desde=sum(t.vendidas_desde for t in tallas),
        tallas_con_ajuste_posterior=sum(1 for t in tallas if t.ajuste_posterior is not None),
    )


# --- fechas -------------------------------------------------------------------------

def _utc(momento: datetime | None) -> datetime | None:
    """Sin zona = UTC (SQLite guarda el `now()` en UTC pelón; Postgres trae zona)."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


# --- lecturas -----------------------------------------------------------------------

def _en_cajas_por_variante(session: Session, variante_ids: list[int]) -> dict[int, int]:
    filas = session.execute(
        select(BodegaContenido.variante_id, func.coalesce(func.sum(BodegaContenido.cantidad), 0))
        .where(BodegaContenido.variante_id.in_(variante_ids))
        .group_by(BodegaContenido.variante_id)
    ).all()
    return {int(vid): int(n) for vid, n in filas}


def _salidas_libreta(session: Session, desde: datetime) -> dict[str, list[tuple[datetime, int]]]:
    """(momento, piezas) por SKU en la Libreta desde `desde`: + lo que sale, − lo
    que regresa en un cambio. Los conjuntos reparten a sus piezas (misma regla
    que `revision_service._ventas_por_sku`)."""
    from pos_uniformes.services.cambio_service import ENTRA
    from pos_uniformes.services.revision_service import _piezas_de_conjuntos

    filas = session.execute(
        select(LibretaVenta.created_at, LibretaVenta.tipo, LibretaVenta.detalle)
        .where(LibretaVenta.tipo.in_(TIPOS_QUE_SACAN + (TIPO_CAMBIO,)), LibretaVenta.created_at >= desde)
    ).all()
    por_sku: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for creado, tipo, detalle in filas:
        momento = _utc(creado)
        if momento is None:
            continue
        for linea in detalle or []:
            sku = str(linea.get("sku") or "").strip()
            if not sku:
                continue
            try:
                piezas = int(linea.get("cantidad") or 0)
            except (TypeError, ValueError):
                continue
            if piezas <= 0:
                continue
            if tipo == TIPO_CAMBIO and linea.get("cambio") == ENTRA:
                piezas = -piezas
            por_sku[sku].append((momento, piezas))
    for sku_conjunto, piezas_sku in _piezas_de_conjuntos(session, list(por_sku)).items():
        for evento in list(por_sku[sku_conjunto]):
            for sku_pieza in piezas_sku:
                por_sku[sku_pieza].append(evento)
    return por_sku


def _ajustes_desde(session: Session, variante_ids: list[int], desde: datetime) -> dict[int, list[tuple[datetime, str]]]:
    """(momento, referencia) de cada AJUSTE_ENTRADA/SALIDA de esas tallas desde `desde`,
    sin los automáticos de la venta y de los conjuntos."""
    filas = session.execute(
        select(MovimientoInventario.variante_id, MovimientoInventario.created_at, MovimientoInventario.referencia)
        .where(
            MovimientoInventario.variante_id.in_(variante_ids),
            MovimientoInventario.tipo_movimiento.in_(TIPOS_AJUSTE),
            MovimientoInventario.created_at >= desde,
        )
    ).all()
    out: dict[int, list[tuple[datetime, str]]] = defaultdict(list)
    for vid, creado, referencia in filas:
        ref = str(referencia or "")
        if ref.startswith(PREFIJOS_AUTOMATICOS):
            continue
        momento = _utc(creado)
        if momento is not None:
            out[int(vid)].append((momento, ref))
    return out


def resumen_de_jornada(session: Session, jornada: ConteoJornada) -> ResumenAjuste:
    """Por talla y en total, lo que Aplicar le haría hoy al inventario."""
    filas = session.execute(
        select(ConteoInventario, Variante, Producto.nombre)
        .join(Variante, Variante.id == ConteoInventario.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(ConteoInventario.jornada_id == jornada.id)
        .order_by(Producto.nombre, ConteoInventario.id)
    ).all()
    if not filas:
        return resumir((), jornada_id=jornada.id)

    variante_ids = sorted({int(v.id) for _c, v, _p in filas})
    contados_raw = [c.contado_at for c, _v, _p in filas if c.contado_at is not None]
    desde_raw = min(contados_raw, key=_utc) if contados_raw else None
    cajas = _en_cajas_por_variante(session, variante_ids)
    salidas = _salidas_libreta(session, desde_raw) if desde_raw is not None else {}
    ajustes = _ajustes_desde(session, variante_ids, desde_raw) if desde_raw is not None else {}

    tallas: list[TallaResumen] = []
    for conteo, variante, producto in filas:
        contado = _utc(conteo.contado_at)
        sku = str(variante.sku or "")
        vendidas = sum(p for m, p in salidas.get(sku, []) if contado is not None and m > contado)
        propia = referencia_de(conteo.id)
        posteriores = sorted(
            m for m, ref in ajustes.get(int(variante.id), [])
            if contado is not None and m > contado and ref != propia
        )
        tienda = int(variante.stock_actual or 0) - cajas.get(int(variante.id), 0)
        diferencia = int(conteo.diferencia)
        ajustado = bool(conteo.ajustado)
        tallas.append(TallaResumen(
            conteo_id=int(conteo.id),
            variante_id=int(variante.id),
            producto=str(producto),
            talla=str(variante.talla or ""),
            stock_sistema=int(conteo.stock_sistema),
            conto=int(conteo.stock_fisico),
            diferencia=diferencia,
            ajustado=ajustado,
            vendidas_desde=max(0, vendidas),
            tienda_hoy=tienda,
            queda_hoy=queda_hoy(tienda_hoy=tienda, diferencia=diferencia, ajustado=ajustado),
            precio_venta=_precio(variante.precio_venta),
            ajuste_posterior=posteriores[0] if posteriores else None,
        ))
    return resumir(tallas, jornada_id=jornada.id)
