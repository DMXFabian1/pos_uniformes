"""M2: del carrito del kiosko (o de la Libreta) a la entrada del motor.

El kiosko guarda sus renglones como dicts (`sku`, `precio`, `cantidad`,
`rebaja`, `precio_normal`, `promo_3pz`/`sports_uniform_role`, `categoria`…).
Aquí se traducen a `EntradaVenta` sin preguntarle nada a la base: quien llama
ya trae al cliente, a la compradora y las categorías.

Puntos finos:
- Con rebaja, `precio` ya es el rebajado (`rebaja_service.aplicar`): el
  precio de lista es `precio_normal`.
- Cada renglón lleva su `linea_uid` (D1). Si no lo trae (renglones de antes,
  reimpresiones) se le pone uno; si dos renglones traen el mismo (un dict
  copiado), el segundo recibe uno nuevo.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, MutableMapping, Sequence

from pos_uniformes.services.beneficios.contrato import (
    CERO,
    LIQUIDACION,
    MODALIDAD_DESCUENTO,
    MODALIDAD_MONEDERO,
    OFERTA,
    ORIGEN_KIOSKO_EN_LINEA,
    ORIGEN_KIOSKO_SIN_CONEXION,
    ClienteCtx,
    CompradoraCtx,
    EntradaVenta,
    LineaEntrada,
    Rebaja,
)

LLAVE_UID = "linea_uid"
_CENT = Decimal("0.01")


def _dinero(valor) -> Decimal:
    return Decimal(str(valor if valor not in (None, "") else 0)).quantize(_CENT)


def _pct(valor) -> Decimal | None:
    if valor in (None, ""):
        return None
    pct = Decimal(str(valor))
    return pct if pct > 0 else None


def es_promo_3pz(item: Mapping) -> bool:
    from pos_uniformes.services.fidelizacion import descuento_programa_service as dps

    return dps.es_promo_3pz(item)


def asegurar_uids(items: Sequence[MutableMapping]) -> None:
    """Cada renglón con su `linea_uid` único y en forma canónica."""
    vistos: set[str] = set()
    for it in items:
        uid = str(it.get(LLAVE_UID) or "").lower()
        try:
            valido = str(uuid.UUID(uid)) == uid
        except ValueError:
            valido = False
        if not valido or uid in vistos:
            uid = str(uuid.uuid4())
        it[LLAVE_UID] = uid
        vistos.add(uid)


def linea_desde_item(item: Mapping) -> LineaEntrada:
    tipo = str(item.get("rebaja") or "")
    precio = _dinero(item.get("precio"))
    rebaja = None
    precio_lista = precio
    if tipo in (OFERTA, LIQUIDACION):
        normal = item.get("precio_normal")
        precio_lista = _dinero(normal) if normal not in (None, "") else precio
        if precio > 0:
            rebaja = Rebaja(tipo=tipo, precio=precio)
    sku = str(item.get("sku") or "").strip() or None
    return LineaEntrada(
        linea_uid=str(item[LLAVE_UID]),
        sku=sku,
        cantidad=int(item.get("cantidad", 0) or 0),
        precio_lista=precio_lista,
        categoria=str(item.get("categoria") or ""),
        rebaja=rebaja,
        promo_3pz=es_promo_3pz(item),
        nombre=str(item.get("nombre") or ""),
        talla=str(item.get("talla") or ""),
    )


def cliente_ctx(cliente: Mapping | None, *, pct_mayoreo_fijo=None) -> ClienteCtx | None:
    """El cliente del kiosko (`self._cliente`) como lo necesita el motor."""
    if not cliente and not pct_mayoreo_fijo:
        return None
    cliente = cliente or {}
    pct_mayoreo = _pct(pct_mayoreo_fijo) or _pct(cliente.get("descuento_disponible"))
    return ClienteCtx(
        id=cliente.get("id"),
        programa_clave=(str(cliente["programa"]) if cliente.get("programa") else None),
        tasa_monedero=_pct(cliente.get("tasa")),
        pct_mayoreo=pct_mayoreo,
        activo=str(cliente.get("estado") or "activo") == "activo",
    )


def modalidad(cliente: Mapping | None, *, usar_descuento: bool, pct_mayoreo_fijo=None) -> str | None:
    """C4: la elección del Mayorista. Sin % de mayoreo no hay elección."""
    if _pct(pct_mayoreo_fijo):
        return MODALIDAD_DESCUENTO
    if not cliente or not _pct(cliente.get("descuento_disponible")):
        return None
    return MODALIDAD_DESCUENTO if usar_descuento else MODALIDAD_MONEDERO


def compradora_ctx(compradora: Any, *, descuento_empleada: bool) -> CompradoraCtx | None:
    """`EstadoCompradora` → contexto. Sin compradora con descuento es «otra
    persona» (R2): el motor lo entiende con `None`."""
    if not descuento_empleada or compradora is None:
        return None
    pct = Decimal(str(compradora.porcentaje))
    restante = compradora.restante
    return CompradoraCtx(
        codigo=str(compradora.codigo),
        pct_nivel=pct if compradora.tiene_nivel else None,
        restante_tope=(None if restante is None else Decimal(str(restante)).quantize(_CENT)),
    )


def entrada_desde_carrito(
    items: Sequence[MutableMapping],
    *,
    fecha_venta: datetime,
    en_linea: bool = True,
    cliente: Mapping | None = None,
    usar_descuento_programa: bool = False,
    pct_mayoreo_fijo=None,
    descuento_empleada: bool = False,
    compradora: Any = None,
    usar_saldo: bool = False,
    saldo_disponible=CERO,
    pago_tarjeta: bool = False,
    vendedora: str | None = None,
    origen_calculo: str | None = None,
) -> EntradaVenta:
    asegurar_uids(items)
    lineas = tuple(linea_desde_item(it) for it in items if int(it.get("cantidad", 0) or 0) > 0)
    disponible = _dinero(saldo_disponible) if usar_saldo else CERO
    return EntradaVenta(
        lineas=lineas,
        fecha_venta=fecha_venta,
        origen_calculo=origen_calculo or (ORIGEN_KIOSKO_EN_LINEA if en_linea else ORIGEN_KIOSKO_SIN_CONEXION),
        cliente=cliente_ctx(cliente, pct_mayoreo_fijo=pct_mayoreo_fijo),
        modalidad_mayorista=modalidad(
            cliente, usar_descuento=usar_descuento_programa, pct_mayoreo_fijo=pct_mayoreo_fijo
        ),
        descuento_empleada=bool(descuento_empleada),
        compradora=compradora_ctx(compradora, descuento_empleada=descuento_empleada),
        saldo_a_usar=disponible,
        saldo_disponible=disponible,
        pago_tarjeta=bool(pago_tarjeta),
        vendedora=(str(vendedora) if vendedora else None),
    )


# ─── De vuelta: lo que la Libreta guarda por renglón ─────────────────────


def detalle_por_renglon(items: Sequence[Mapping], calculo, *, pct_base=Decimal("5")) -> list[dict]:
    """Los renglones para la Libreta con lo que decidió el motor.

    El tope de empleada va por pieza (C8, C9): un renglón con piezas que
    consumen tope y piezas que no se parte en dos, cada uno con su
    `desc_empleada_pct` (el nivel o el base). Así lo que hoy se lee de
    `detalle` (el tope usado del mes) sigue cuadrando. Como antes (A3), una
    pieza que consume tope lleva el nivel aunque haya cobrado el mayoreo.
    Sin descuento de empleada los renglones van sin esa marca."""
    por_uid = {}
    for linea in calculo.lineas:
        for uid, _piezas in linea.lineas_origen:
            por_uid[uid] = linea
    salida: list[dict] = []
    usadas: dict[str, int] = {}
    for it in items:
        base = dict(it)
        base.pop("desc_empleada_pct", None)
        linea = por_uid.get(str(it.get(LLAVE_UID)))
        if linea is None or not calculo.descuento_empleada:
            salida.append(base)
            continue
        if linea.clasificacion_al_vender in (OFERTA, LIQUIDACION):
            salida.append({**base, "desc_empleada_pct": Decimal("0")})
            continue
        cantidad = int(it.get("cantidad", 0) or 0)
        if linea.consumo_tope > 0 and linea.precio_lista > 0:
            con_nivel = int(linea.consumo_tope / linea.precio_lista)
        else:
            con_nivel = linea.piezas_con_nivel
        # En una línea agrupada (Q6) las piezas con nivel se reparten en el
        # orden de sus líneas de origen.
        ya = usadas.get(linea.linea_uid, 0)
        nivel_aqui = max(0, min(cantidad, con_nivel - ya))
        usadas[linea.linea_uid] = ya + nivel_aqui
        if nivel_aqui:
            # El % que se cobró (el nivel, o el mayoreo si ganó: A3).
            salida.append({**base, "cantidad": nivel_aqui, "desc_empleada_pct": linea.descuento.pct})
        if cantidad - nivel_aqui:
            salida.append({**base, "cantidad": cantidad - nivel_aqui, "desc_empleada_pct": pct_base})
    return salida


def descuento_programa_a_guardar(pct, calculo) -> Decimal | None:
    """El % del Mayorista que se anota en la venta, o None si no se cobró.

    Con el motor manda lo que se COBRÓ: sin conexión el motor no aplica el
    mayoreo (C4), pero la venta se anotaba con `descuento_programa` y el
    servidor, al verlo, no abonaba Monedero. El cliente pagaba precio completo
    y se quedaba sin ninguno de los dos (revisión de deuda, 2026-11-12).
    Sin `calculo` (cálculo de respaldo) se queda el % de la pantalla."""
    if not pct:
        return None
    if calculo is not None and not getattr(calculo, "descuento_aplicado", False):
        return None
    return Decimal(str(pct))

