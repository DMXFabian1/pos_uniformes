"""E7: prendas en Oferta o Liquidación (Daniel, 2026-11-11).

«Para que no se sumen descuentos.»

- Oferta: rebaja con último día (ese día termina sola y la prenda vuelve a
  su precio normal) o sin fecha, hasta que el dueño la quite (2026-11-11:
  el Pants 2pz Liso Azul Marino/Azul Rey a $175, regular $250/$265).
- Liquidación: sin fecha, hasta que se acabe. El ticket dice «sin cambios ni
  devoluciones».
- El precio normal de la variante (`precio_venta`) no se toca: la rebaja
  guarda su propio precio. Si el precio normal llega a quedar igual o abajo
  del rebajado, gana el normal (nunca se cobra de más).
- Una prenda rebajada no lleva ningún otro descuento (5 % o nivel de
  empleada, precio de mayoreo) ni genera Monedero: el precio rebajado ya es
  el beneficio.

En el carrito la marca viaja en el propio renglón (`LLAVE`) junto con el
precio normal, y se guarda así en el detalle de la Libreta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping, Sequence

from pos_uniformes.services.fidelizacion.descuento_programa_service import LLAVE_REBAJA

_CENT = Decimal("0.01")
_PESO = Decimal("1")
_CERO = Decimal("0")

OFERTA = "oferta"
LIQUIDACION = "liquidacion"
TIPOS = (OFERTA, LIQUIDACION)
ETIQUETAS = {OFERTA: "Oferta", LIQUIDACION: "Liquidación"}

#: Llaves del renglón: el tipo de rebaja y el precio normal.
LLAVE = LLAVE_REBAJA
LLAVE_ANTES = "precio_normal"

#: Dos renglones para el ticket (cada uno cabe en el papel).
LEYENDA_LIQUIDACION = ("Prendas en LIQUIDACIÓN:", "sin cambios ni devoluciones.")


class RebajaInvalida(ValueError):
    """El texto se le muestra tal cual al dueño."""


@dataclass(frozen=True)
class RebajaVigente:
    sku: str
    tipo: str
    precio: Decimal
    precio_antes: Decimal
    hasta: date | None

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS.get(self.tipo, self.tipo)


# ─── Reglas puras ───────────────────────────────────────────────────────


def es_vigente(activa: bool, hasta: date | None, hoy: date) -> bool:
    return bool(activa) and (hasta is None or hoy <= hasta)


def precio_por_porcentaje(precio_normal, porcentaje) -> Decimal:
    """Precio con el % de rebaja, redondeado al peso."""
    precio_normal = Decimal(str(precio_normal))
    pct = Decimal(str(porcentaje))
    if pct <= 0 or pct >= 100:
        raise RebajaInvalida("La rebaja debe ser de más de 0 y menos de 100 %.")
    return (precio_normal * (Decimal("100") - pct) / Decimal("100")).quantize(_PESO, rounding=ROUND_HALF_UP).quantize(_CENT)


def validar(tipo: str, precio, precio_normal, hasta: date | None, hoy: date, *, sku: str = "") -> Decimal:
    """Revisa una rebaja; devuelve el precio limpio."""
    if tipo not in TIPOS:
        raise RebajaInvalida("Elige Oferta o Liquidación.")
    precio = Decimal(str(precio)).quantize(_CENT)
    normal = Decimal(str(precio_normal)).quantize(_CENT)
    donde = f" ({sku})" if sku else ""
    if precio <= 0:
        raise RebajaInvalida(f"El precio rebajado debe ser mayor a $0{donde}.")
    if precio >= normal:
        raise RebajaInvalida(f"El precio rebajado ${precio:,.2f} no es menor que el normal ${normal:,.2f}{donde}.")
    if tipo == OFERTA and hasta is not None and hasta < hoy:
        raise RebajaInvalida("El último día de la oferta ya pasó.")
    return precio


def es_rebajado(item: Mapping) -> bool:
    return str(item.get(LLAVE) or "") in TIPOS


def aplicar(item: dict, rebaja: RebajaVigente) -> dict:
    """Pone el precio rebajado y la marca en el renglón del carrito."""
    item["precio"] = rebaja.precio
    item[LLAVE] = rebaja.tipo
    item[LLAVE_ANTES] = rebaja.precio_antes
    return item


def marca_para_libreta(item: Mapping) -> dict:
    if not es_rebajado(item):
        return {}
    return {LLAVE: str(item[LLAVE]), LLAVE_ANTES: str(item.get(LLAVE_ANTES) or "")}


def importe_rebajado(lineas: Iterable[Mapping]) -> Decimal:
    """Lo cobrado en prendas rebajadas (no genera Monedero)."""
    total = _CERO
    for line in lineas:
        if es_rebajado(line):
            total += Decimal(str(line.get("precio", 0) or 0)) * int(line.get("cantidad", 0) or 0)
    return total.quantize(_CENT)


def texto_renglon(item: Mapping) -> str:
    """«OFERTA · antes $450.00» para el carrito y el ticket."""
    if not es_rebajado(item):
        return ""
    antes = item.get(LLAVE_ANTES)
    texto = ETIQUETAS[str(item[LLAVE])].upper()
    if antes not in (None, ""):
        texto += f" · antes ${Decimal(str(antes)):,.2f}"
    return texto


TACHADO = "\u0336"


def tachar(texto: str) -> str:
    """Tachado para el ticket (cada carácter con U+0336)."""
    return "".join(c + TACHADO for c in texto)


def largo_visible(texto: str) -> int:
    return len(texto.replace(TACHADO, ""))


def fmt_corto(valor) -> str:
    """$250 si es entero, $250.50 si trae centavos."""
    v = Decimal(str(valor))
    return f"${v:,.0f}" if v == v.to_integral_value() else f"${v:,.2f}"


def ahorro(item: Mapping) -> Decimal:
    """Lo que se ahorra el cliente en ese renglón por la rebaja."""
    if not es_rebajado(item) or item.get(LLAVE_ANTES) in (None, ""):
        return _CERO
    dif = Decimal(str(item[LLAVE_ANTES])) - Decimal(str(item.get("precio", 0) or 0))
    return max(dif * int(item.get("cantidad", 0) or 0), _CERO).quantize(_CENT)


def ahorro_total(items: Iterable[Mapping]) -> Decimal:
    return sum((ahorro(it) for it in items), _CERO).quantize(_CENT)


def renglon_marca(item: Mapping, ancho: int) -> str:
    """El renglón de arriba del precio: solo la marca («OFERTA»).

    Lo que se ahorra va sumado al final del ticket (`texto_ahorro_total`),
    no prenda por prenda (Daniel, 2026-11-11)."""
    if not es_rebajado(item):
        return ""
    return ETIQUETAS[str(item[LLAVE])].upper()[:ancho]


def precio_unitario_ticket(item: Mapping, precio_fmt: str) -> str:
    """«$2̶5̶0̶ $175.00»: el precio de antes tachado junto al de hoy, como en
    las tiendas grandes. Sin rebaja, el precio de siempre."""
    if not es_rebajado(item) or item.get(LLAVE_ANTES) in (None, ""):
        return precio_fmt
    return f"{tachar(fmt_corto(item[LLAVE_ANTES]))} {precio_fmt}"


def texto_ahorro_total(items: Iterable[Mapping]) -> str:
    """«¡Hoy ahorraste $75 en ofertas!» (vacío si no hubo ahorro)."""
    total = ahorro_total(items)
    if total <= 0:
        return ""
    return f"¡Hoy ahorraste {fmt_corto(total)} en ofertas!"


def hay_liquidacion(items: Iterable[Mapping]) -> bool:
    return any(str(it.get(LLAVE) or "") == LIQUIDACION for it in items)


# ─── Con la base ────────────────────────────────────────────────────────


def vigentes_por_sku(session, *, hoy: date | None = None) -> dict[str, RebajaVigente]:
    from sqlalchemy import or_, select

    from pos_uniformes.database.models import RebajaProducto, Variante

    hoy = hoy or date.today()
    filas = session.execute(
        select(RebajaProducto, Variante.sku, Variante.precio_venta)
        .join(Variante, Variante.id == RebajaProducto.variante_id)
        .where(RebajaProducto.activa.is_(True), or_(RebajaProducto.hasta.is_(None), RebajaProducto.hasta >= hoy))
    ).all()
    resultado: dict[str, RebajaVigente] = {}
    for r, sku, precio_venta in filas:
        normal = Decimal(str(precio_venta))
        if Decimal(str(r.precio)) >= normal:
            continue  # el precio normal ya es igual o menor: gana el normal
        resultado[str(sku).upper()] = RebajaVigente(
            sku=str(sku).upper(), tipo=r.tipo, precio=Decimal(str(r.precio)), precio_antes=normal, hasta=r.hasta
        )
    return resultado


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def quitar(session, variante_ids: Iterable[int]) -> int:
    """Termina las rebajas activas de esas variantes. Devuelve cuántas."""
    from sqlalchemy import select

    from pos_uniformes.database.models import RebajaProducto

    ids = [int(v) for v in variante_ids]
    if not ids:
        return 0
    filas = session.scalars(
        select(RebajaProducto).where(RebajaProducto.variante_id.in_(ids), RebajaProducto.activa.is_(True))
    ).all()
    for r in filas:
        r.activa = False
        r.terminada_at = _ahora()
    session.flush()
    return len(filas)


def terminar_vencidas(session, *, hoy: date | None = None) -> int:
    from sqlalchemy import select

    from pos_uniformes.database.models import RebajaProducto

    hoy = hoy or date.today()
    filas = session.scalars(
        select(RebajaProducto).where(RebajaProducto.activa.is_(True), RebajaProducto.hasta.is_not(None), RebajaProducto.hasta < hoy)
    ).all()
    for r in filas:
        r.activa = False
        r.terminada_at = _ahora()
    session.flush()
    return len(filas)


def marcar(
    session,
    variante_ids: Sequence[int],
    *,
    tipo: str,
    precio=None,
    porcentaje=None,
    hasta: date | None = None,
    usuario_id: int | None = None,
    hoy: date | None = None,
) -> list:
    """Pone en Oferta o Liquidación esas variantes, con un precio fijo o un %.

    Si alguna ya estaba rebajada, la de antes se termina. Valida todas antes
    de cambiar nada."""
    from sqlalchemy import select

    from pos_uniformes.database.models import RebajaProducto, Variante

    hoy = hoy or date.today()
    if (precio is None) == (porcentaje is None):
        raise RebajaInvalida("Pon un precio o un porcentaje de rebaja.")
    if tipo == LIQUIDACION:
        hasta = None
    variantes = session.scalars(select(Variante).where(Variante.id.in_([int(v) for v in variante_ids]))).all()
    if not variantes:
        raise RebajaInvalida("Elige al menos una prenda.")
    nuevas = []
    for v in variantes:
        normal = Decimal(str(v.precio_venta))
        p = precio_por_porcentaje(normal, porcentaje) if porcentaje is not None else precio
        nuevas.append((v, normal, validar(tipo, p, normal, hasta, hoy, sku=str(v.sku))))
    quitar(session, [v.id for v, _n, _p in nuevas])
    creadas = []
    for v, normal, p in nuevas:
        r = RebajaProducto(
            variante_id=v.id, tipo=tipo, precio=p, precio_antes=normal, hasta=hasta, activa=True, usuario_id=usuario_id
        )
        session.add(r)
        creadas.append(r)
    session.flush()
    return creadas


@dataclass(frozen=True)
class FilaRebaja:
    variante_id: int
    sku: str
    nombre: str
    talla: str
    color: str
    tipo: str
    precio: Decimal
    precio_normal: Decimal
    hasta: date | None

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS.get(self.tipo, self.tipo)

    @property
    def descuento_pct(self) -> Decimal:
        if self.precio_normal <= 0:
            return _CERO
        return ((self.precio_normal - self.precio) * Decimal("100") / self.precio_normal).quantize(Decimal("1"))


def listar(session, *, hoy: date | None = None) -> list[FilaRebaja]:
    """Lo que está rebajado hoy (las ofertas vencidas se terminan antes)."""
    from sqlalchemy import select

    from pos_uniformes.database.models import Producto, RebajaProducto, Variante

    hoy = hoy or date.today()
    terminar_vencidas(session, hoy=hoy)
    filas = session.execute(
        select(RebajaProducto, Variante, Producto)
        .join(Variante, Variante.id == RebajaProducto.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(RebajaProducto.activa.is_(True))
        .order_by(RebajaProducto.tipo, Producto.nombre_base, Variante.talla)
    ).all()
    return [
        FilaRebaja(
            variante_id=v.id, sku=str(v.sku), nombre=str(p.nombre_base or p.nombre), talla=str(v.talla),
            color=str(v.color), tipo=r.tipo, precio=Decimal(str(r.precio)),
            precio_normal=Decimal(str(v.precio_venta)), hasta=r.hasta,
        )
        for r, v, p in filas
    ]


@dataclass(frozen=True)
class PrendaParaRebajar:
    variante_id: int
    sku: str
    nombre: str
    talla: str
    color: str
    precio: Decimal


def buscar_prendas(session, texto: str, limite: int = 200) -> list[PrendaParaRebajar]:
    """Por SKU exacto o por nombre (todas sus tallas)."""
    from sqlalchemy import func, or_, select

    from pos_uniformes.database.models import Producto, Variante

    texto = " ".join(str(texto or "").split())
    if not texto:
        return []
    patron = f"%{texto.lower()}%"
    filas = session.execute(
        select(Variante, Producto)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(
            Variante.activo.is_(True),
            Producto.activo.is_(True),
            or_(func.upper(Variante.sku) == texto.upper(), func.lower(Producto.nombre).like(patron)),
        )
        .order_by(Producto.nombre, Variante.talla, Variante.color)
        .limit(limite)
    ).all()
    return [
        PrendaParaRebajar(v.id, str(v.sku), str(p.nombre_base or p.nombre), str(v.talla), str(v.color), Decimal(str(v.precio_venta)))
        for v, p in filas
    ]
