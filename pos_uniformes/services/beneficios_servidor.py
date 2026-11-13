"""M2 (T3): el servidor vuelve a calcular la venta con los datos de la base.

El kiosko manda su fotografía (entrada + cálculo). Aquí se reconstruye la
entrada, se refresca lo que el kiosko pudo tener viejo (el programa y la tasa
del cliente, su saldo y el nivel y tope de quien compra) y se calcula otra vez
con el mismo motor.

- En la venta con saldo (en línea, antes de imprimir) una diferencia en lo que
  se cobra detiene el cobro: la empleada ve el importe nuevo (T3).
- En la venta que sube de la cola el cliente ya pagó: la diferencia se queda
  anotada en la fotografía y la venta nunca se pierde.

Los precios y las rebajas se toman como los vio el kiosko: son lo que el
cliente vio en el ticket.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from pos_uniformes.services.beneficios.contrato import (
    ORIGEN_KIOSKO_SIN_CONEXION,
    ORIGEN_SERVIDOR,
    ClienteCtx,
    CompradoraCtx,
    EntradaVenta,
    LineaEntrada,
    Pago,
    Rebaja,
    ReglasCtx,
)
from pos_uniformes.services.beneficios.fotografia import _plano
from pos_uniformes.services.beneficios.motor import calcular

#: Lo que, si cambia, cambia lo que paga el cliente.
CAMPOS_DEL_COBRO = ("total", "saldo_usado", "por_cobrar")
#: Lo que se compara y se anota. El Monedero (2026-11-12) se anota pero no
#: frena el cobro: el abono sale de la base del motor y conviene ver cuándo
#: el kiosko prometió otra cosa (otra tasa, otro programa).
CAMPOS_DEL_MONEDERO = ("monedero.base", "monedero.abono")
CAMPOS_COMPARADOS = (
    *CAMPOS_DEL_COBRO, "descuento_total", "neto_tienda", "consumo_tope_total", *CAMPOS_DEL_MONEDERO,
)


class CalculoCambio(ValueError):
    """El servidor calculó otro cobro: no se cobra con el importe viejo."""

    def __init__(self, diferencias: dict):
        self.diferencias = diferencias
        partes = []
        etiquetas = {"total": "Total", "saldo_usado": "Saldo a usar", "por_cobrar": "Por cobrar"}
        for campo in CAMPOS_DEL_COBRO:
            if campo in diferencias:
                antes, ahora = diferencias[campo]
                partes.append(f"{etiquetas[campo]}: ${Decimal(antes):,.2f} → ${Decimal(ahora):,.2f}")
        super().__init__(
            "El cobro cambió al revisarlo con el servidor (cambió el saldo, el programa del "
            "cliente o el tope de quien compra).\n\n" + "\n".join(partes)
            + "\n\nRevisa el total en pantalla y vuelve a cobrar."
        )


# ─── De la fotografía a la entrada ───────────────────────────────────────


def _d(valor) -> Decimal | None:
    return None if valor in (None, "") else Decimal(str(valor))


def entrada_desde_plano(d: dict) -> EntradaVenta:
    lineas = tuple(
        LineaEntrada(
            linea_uid=str(l["linea_uid"]),
            sku=l.get("sku"),
            cantidad=int(l["cantidad"]),
            precio_lista=Decimal(str(l["precio_lista"])),
            categoria=str(l.get("categoria") or ""),
            rebaja=(Rebaja(tipo=l["rebaja"]["tipo"], precio=Decimal(str(l["rebaja"]["precio"]))) if l.get("rebaja") else None),
            promo_3pz=bool(l.get("promo_3pz")),
            nombre=str(l.get("nombre") or ""),
            talla=str(l.get("talla") or ""),
        )
        for l in d["lineas"]
    )
    c = d.get("cliente")
    cliente = None
    if c:
        cliente = ClienteCtx(
            id=c.get("id"),
            programa_clave=c.get("programa_clave"),
            tasa_monedero=_d(c.get("tasa_monedero")),
            pct_mayoreo=_d(c.get("pct_mayoreo")),
            activo=bool(c.get("activo", True)),
        )
    k = d.get("compradora")
    compradora = None
    if k:
        compradora = CompradoraCtx(
            codigo=str(k["codigo"]), pct_nivel=_d(k.get("pct_nivel")), restante_tope=_d(k.get("restante_tope"))
        )
    r = d.get("reglas") or {}
    reglas = ReglasCtx(
        version=str(r.get("version", ReglasCtx.version)),
        pct_base_empleada=Decimal(str(r.get("pct_base_empleada", ReglasCtx.pct_base_empleada))),
        tope_pct_uniforme=Decimal(str(r.get("tope_pct_uniforme", ReglasCtx.tope_pct_uniforme))),
        categorias_no_uniforme=frozenset(r.get("categorias_no_uniforme") or ReglasCtx().categorias_no_uniforme),
        pct_comision_tarjeta=Decimal(str(r.get("pct_comision_tarjeta", ReglasCtx.pct_comision_tarjeta))),
        pct_otra_persona=Decimal(str(r.get("pct_otra_persona", ReglasCtx.pct_otra_persona))),
    )
    return EntradaVenta(
        lineas=lineas,
        fecha_venta=datetime.fromisoformat(d["fecha_venta"]),
        origen_calculo=str(d.get("origen_calculo")),
        cliente=cliente,
        modalidad_mayorista=d.get("modalidad_mayorista"),
        descuento_empleada=bool(d.get("descuento_empleada")),
        compradora=compradora,
        saldo_a_usar=Decimal(str(d.get("saldo_a_usar", "0.00"))),
        saldo_disponible=Decimal(str(d.get("saldo_disponible", "0.00"))),
        pago_tarjeta=bool(d.get("pago_tarjeta")),
        pagos=tuple(Pago(p["medio"], Decimal(str(p["importe"]))) for p in d.get("pagos") or ()),
        vendedora=d.get("vendedora"),
        reglas=reglas,
    )


# ─── Refrescar con la base ───────────────────────────────────────────────


def _fecha_local(fecha: datetime):
    return (fecha.astimezone() if fecha.tzinfo else fecha).date()


def refrescar(session, entrada: EntradaVenta, *, cliente_id: int | None = None) -> EntradaVenta:
    """La misma venta con lo que dice la base hoy del cliente y de quien compra."""
    from pos_uniformes.services import incentivo_empleada_service as inc
    from pos_uniformes.services import monedero_service as mon

    sin_conexion = entrada.origen_calculo == ORIGEN_KIOSKO_SIN_CONEXION
    cambios: dict = {"origen_calculo": entrada.origen_calculo if sin_conexion else ORIGEN_SERVIDOR}
    fecha = entrada.fecha_venta
    cid = cliente_id if cliente_id is not None else (entrada.cliente.id if entrada.cliente else None)
    if entrada.cliente is not None and cid is not None:
        monedero = mon.monedero_de_cliente(session, int(cid))
        activo = monedero is None or monedero.estado == mon.ACTIVO
        pct_mayoreo = mon.descuento_disponible(session, int(cid), fecha)
        cambios["cliente"] = replace(
            entrada.cliente,
            id=int(cid),
            tasa_monedero=mon.tasa_para_cliente(session, int(cid), fecha),
            pct_mayoreo=pct_mayoreo,
            activo=activo,
        )
        if not pct_mayoreo and entrada.modalidad_mayorista is not None:
            # En la base ya no es Mayorista: no hay nada que elegir.
            cambios["modalidad_mayorista"] = None
        if entrada.saldo_a_usar > 0 and monedero is not None:
            disponible = mon.saldo(session, monedero.id, fecha).disponible
            cambios["saldo_disponible"] = max(Decimal(str(disponible)), Decimal("0.00")).quantize(Decimal("0.01"))
    if entrada.compradora is not None:
        estado = inc.estado_compradora(session, entrada.compradora.codigo, hoy=_fecha_local(fecha))
        cambios["compradora"] = CompradoraCtx(
            codigo=estado.codigo,
            pct_nivel=estado.porcentaje if estado.tiene_nivel else None,
            restante_tope=estado.restante,
        )
    return replace(entrada, **cambios)


def _valor(plano: dict, campo: str) -> str:
    """El valor de `campo` («monedero.abono» entra al dict anidado). Sin
    Monedero (bloqueado o sin programa) cuenta como $0.00."""
    valor = plano
    for parte in campo.split("."):
        valor = valor.get(parte) if isinstance(valor, dict) else None
    return "0.00" if valor is None else str(valor)


def diferencias(kiosko: dict, servidor) -> dict:
    """{campo: (kiosko, servidor)} de lo que no coincide."""
    plano = _plano(servidor)
    salida = {}
    for campo in CAMPOS_COMPARADOS:
        antes, ahora = _valor(kiosko, campo), _valor(plano, campo)
        if Decimal(antes) != Decimal(ahora):
            salida[campo] = (antes, ahora)
    return salida


def recalcular(session, foto: dict, *, cliente_id: int | None = None):
    """(fotografía con la parte del servidor, diferencias en el cobro)."""
    entrada = refrescar(session, entrada_desde_plano(foto["entrada"]), cliente_id=cliente_id)
    calculo = calcular(entrada)
    dif = diferencias(foto["calculo"], calculo)
    nueva = dict(foto)
    nueva["servidor"] = {
        "entrada": _plano(entrada),
        "calculo": _plano(calculo),
        "diferencias": {k: list(v) for k, v in dif.items()},
    }
    return nueva, {k: v for k, v in dif.items() if k in CAMPOS_DEL_COBRO}
