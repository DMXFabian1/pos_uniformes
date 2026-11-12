"""Monedero de clientes: saldo de fidelización en MXN (cashback).

Única fuente de reglas del monedero: la UI del kiosko, la Libreta y la
administración del POS llaman aquí y nunca tocan saldos por su cuenta.

Cómo se lleva el dinero
-----------------------
- Libro de movimientos (`monedero_movimiento`): créditos en positivo
  (cashback, devolución de canje, ajuste a favor) y débitos en negativo
  (canje, reversa de cashback, expiración, ajuste en contra). Nada se edita
  ni se borra; se compensa con un movimiento nuevo.
- Cada crédito vence a los 12 meses de CALENDARIO de acreditado
  (`sumar_meses`): el 31 de marzo vence el 31 de marzo del año siguiente, y
  un 29 de febrero vence el 28 de febrero.
- Cada débito dice qué créditos consumió (`monedero_aplicacion`), primero los
  que vencen antes. Por eso el saldo disponible es exacto en cualquier
  momento: Σ (crédito − lo aplicado) de los créditos no vencidos.
- El saldo NO es un campo. La fila de `monedero` solo se bloquea
  (`SELECT … FOR UPDATE`) para que dos canjes no gasten el mismo peso.

Idempotencia: todo movimiento lleva una `idempotency_key` única derivada de
algo persistente (el `operacion_uuid` de la venta, el id del crédito que
vence, etc.). Repetir una operación devuelve el movimiento ya hecho.

Las funciones NO hacen commit: lo hace quien llama, para que la venta, el
canje y el cashback queden en la misma transacción.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from pos_uniformes.database.models import (
    Cliente,
    LibretaVenta,
    Membresia,
    Monedero,
    MonederoAplicacion,
    MonederoConfig,
    MonederoMovimiento,
    Programa,
    RolUsuario,
    Usuario,
)

logger = logging.getLogger(__name__)

_CENT = Decimal("0.01")
_CERO = Decimal("0.00")

MESES_VIGENCIA = 12

# Tipos de movimiento
CASHBACK = "cashback"
CANJE = "canje"
DEVOLUCION_CANJE = "devolucion_canje"
REVERSA_CASHBACK = "reversa_cashback"
EXPIRACION = "expiracion"
AJUSTE_ABONO = "ajuste_abono"
AJUSTE_CARGO = "ajuste_cargo"

TIPOS_CREDITO = (CASHBACK, DEVOLUCION_CANJE, AJUSTE_ABONO)
TIPOS_DEBITO = (CANJE, REVERSA_CASHBACK, EXPIRACION, AJUSTE_CARGO)

ETIQUETAS_TIPO = {
    CASHBACK: "Cashback",
    CANJE: "Pago con saldo",
    DEVOLUCION_CANJE: "Devolución de saldo",
    REVERSA_CASHBACK: "Reversa de cashback",
    EXPIRACION: "Vencimiento",
    AJUSTE_ABONO: "Ajuste a favor",
    AJUSTE_CARGO: "Ajuste en contra",
}

# Estados del monedero
ACTIVO = "activo"
BLOQUEADO = "bloqueado"
CERRADO = "cerrado"
ESTADOS = (ACTIVO, BLOQUEADO, CERRADO)

MENSAJE_SIN_CONEXION = "Para utilizar tu saldo, la terminal debe estar conectada al servidor."


# ─── Errores ─────────────────────────────────────────────────────────────


class MonederoError(Exception):
    """Algo que el monedero no permite; el mensaje es para la pantalla."""


class SaldoInsuficiente(MonederoError):
    pass


class MonederoNoActivo(MonederoError):
    pass


class CashbackYaGastado(MonederoError):
    """La reversa dejaría el saldo negativo: requiere un ajuste autorizado."""


class SinPermiso(PermissionError):
    pass


class OperacionConMonedero(MonederoError):
    """La venta movió el monedero: no se borra, se anula desde el POS."""


# ─── Reglas puras ────────────────────────────────────────────────────────


def _d(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else "0")).quantize(_CENT)


def sumar_meses(momento: datetime, meses: int) -> datetime:
    """Suma meses de calendario. Si el día no existe en el mes destino, cae en
    el último día de ese mes (31-mar + 1 mes = 30-abr; 29-feb + 12 = 28-feb)."""
    total = momento.month - 1 + int(meses)
    anio = momento.year + total // 12
    mes = total % 12 + 1
    dia = min(momento.day, calendar.monthrange(anio, mes)[1])
    return momento.replace(year=anio, month=mes, day=dia)


def vencimiento_de(acreditado: datetime) -> datetime:
    return sumar_meses(acreditado, MESES_VIGENCIA)


def importe_elegible(monto_total, monto_monedero=None) -> Decimal:
    """Lo que genera cashback: el total ya con descuentos y redondeo, menos lo
    pagado con el propio monedero. Nunca negativo."""
    elegible = _d(monto_total) - _d(monto_monedero)
    return elegible if elegible > _CERO else _CERO


def base_sin_comision_tarjeta(libreta_venta, base) -> tuple[Decimal, bool]:
    """Regla B (Daniel, 2026-11-12): si se pagó con tarjeta, el Monedero se
    gana sobre lo que deja la terminal. Lo pagado con saldo no pasa por la
    terminal, así que la comisión es solo sobre el resto. La misma cuenta
    que el motor (`base_monedero_con_comision`), para que el ticket y el
    abono digan lo mismo. Devuelve (base, si se le quitó comisión)."""
    base = _d(base)
    if not getattr(libreta_venta, "pago_tarjeta", False) or base <= 0:
        return base, False
    from pos_uniformes.services.beneficios.motor import base_monedero_con_comision
    from pos_uniformes.services.libreta_service import aplicar_comision_terminal

    pagado = importe_elegible(libreta_venta.monto_total, getattr(libreta_venta, "monto_monedero", None))
    if pagado <= 0:
        return base, False
    comision = max(pagado - aplicar_comision_terminal(pagado), _CERO)
    if comision <= 0:
        return base, False
    return base_monedero_con_comision(base, pagado, comision), True


def calcular_cashback(importe, tasa) -> Decimal:
    """Cashback = importe × tasa %, truncado al centavo (nunca se da de más)."""
    if tasa is None:
        return _CERO
    tasa = Decimal(str(tasa))
    importe = _d(importe)
    if tasa <= 0 or importe <= 0:
        return _CERO
    return (importe * tasa / Decimal("100")).quantize(_CENT, rounding=ROUND_DOWN)


def _al_medio_peso_hacia_arriba(monto: Decimal) -> Decimal:
    """Siguiente múltiplo de $0.50 (o el mismo si ya lo es)."""
    medios = (monto * 2).to_integral_value(rounding="ROUND_CEILING")
    return (medios / 2).quantize(_CENT)


def canje_ajustado(total, disponible, deseado=None) -> Decimal:
    """Cuánto saldo se puede usar en una venta.

    Nunca más que el saldo disponible, el total de la venta, ni lo que pidió
    la clienta. Y se ajusta para que lo que queda por cobrar en efectivo o
    tarjeta caiga en la regla de redondeo de la tienda (pesos o medios
    pesos): si el monedero pagara $37.42, la empleada tendría que cobrar
    centavos que la tienda no maneja."""
    total = _d(total)
    tope = min(_d(disponible), total)
    if deseado is not None:
        tope = min(tope, _d(deseado))
    if tope <= 0:
        return _CERO
    if tope >= total:
        return total
    resto = _al_medio_peso_hacia_arriba(total - tope)
    canje = (total - resto).quantize(_CENT)
    return canje if canje > 0 else _CERO


# ─── Configuración ───────────────────────────────────────────────────────


def config_vigente(session, momento: datetime | None = None) -> MonederoConfig | None:
    """La última configuración vigente en `momento` (habilitada o no)."""
    momento = momento or datetime.now(timezone.utc)
    return session.scalars(
        select(MonederoConfig)
        .where(MonederoConfig.vigente_desde <= momento)
        .order_by(MonederoConfig.vigente_desde.desc(), MonederoConfig.id.desc())
        .limit(1)
    ).first()


def tasa_vigente(session, momento: datetime | None = None) -> Decimal | None:
    """La tasa de cashback vigente, o None si no hay o está deshabilitado.

    Sin tasa configurada el cashback queda apagado: nunca se asume un %."""
    config = config_vigente(session, momento)
    if config is None or not config.habilitado:
        return None
    tasa = Decimal(str(config.tasa_cashback))
    return tasa if tasa > 0 else None


#: Estados en los que una membresía estuvo vigente en algún momento: la que
#: sigue activa y las que terminaron (con `hasta`). Las propuestas pendientes o
#: rechazadas nunca dieron programa.
_ESTADOS_QUE_FUERON_VIGENTES = ("activa", "reemplazada", "cancelada", "vencida")


def programa_en(session, cliente_id: int, momento: datetime | None = None) -> Programa | None:
    """El programa del que el cliente era miembro en `momento` (o None)."""
    momento = _ahora(momento)
    return session.scalars(
        select(Programa)
        .join(Membresia, Membresia.programa_id == Programa.id)
        .where(
            Membresia.cliente_id == int(cliente_id),
            Membresia.estado.in_(_ESTADOS_QUE_FUERON_VIGENTES),
            Membresia.desde.is_not(None),
            Membresia.desde <= momento,
            or_(Membresia.hasta.is_(None), Membresia.hasta > momento),
        )
        .order_by(Membresia.desde.desc(), Membresia.id.desc())
        .limit(1)
    ).first()


def tasa_para_cliente(session, cliente_id: int | None, momento: datetime | None = None) -> Decimal | None:
    """E5-A (2026-11-10): el % que va al Monedero es el del programa del
    cliente en `momento` (Club 5, Leal 10, Profesional 13, Mayorista 15).

    None si el Monedero está apagado (la configuración general sigue siendo
    el interruptor), si el cliente no tiene programa o si su programa da 0 %."""
    if cliente_id is None or tasa_vigente(session, momento) is None:
        return None
    programa = programa_en(session, cliente_id, momento)
    if programa is None:
        return None
    tasa = Decimal(str(programa.tasa_monedero or 0))
    return tasa if tasa > 0 else None


def descuento_disponible(session, cliente_id: int | None, momento: datetime | None = None) -> Decimal | None:
    """E5-A: el % que el cliente puede tomar como descuento en lugar de
    Monedero (solo programas con `permite_descuento`, hoy Mayorista). No
    depende del interruptor del Monedero: es su precio de mayoreo."""
    if cliente_id is None:
        return None
    programa = programa_en(session, cliente_id, momento)
    if programa is None or not programa.permite_descuento:
        return None
    tasa = Decimal(str(programa.tasa_monedero or 0))
    return tasa if tasa > 0 else None


def guardar_config(session, *, tasa, habilitado: bool, usuario_id: int, nota: str | None = None) -> MonederoConfig:
    """Agrega una configuración nueva (las anteriores se conservan: son la
    bitácora). Solo ADMIN. Aplica a ventas desde este momento."""
    _validar_admin(session, usuario_id)
    tasa = Decimal(str(tasa)).quantize(_CENT)
    if tasa < 0 or tasa > 100:
        raise MonederoError("La tasa de cashback debe estar entre 0 y 100 %.")
    if habilitado and tasa <= 0:
        raise MonederoError("Para habilitar el cashback hace falta una tasa mayor a 0 %.")
    config = MonederoConfig(
        tasa_cashback=tasa,
        habilitado=bool(habilitado),
        vigente_desde=datetime.now(timezone.utc),
        usuario_id=int(usuario_id),
        nota=(nota or "").strip()[:200] or None,
    )
    session.add(config)
    session.flush()
    return config


# ─── Permisos ────────────────────────────────────────────────────────────


def _validar_admin(session, usuario_id: int | None) -> Usuario:
    usuario = session.get(Usuario, int(usuario_id)) if usuario_id is not None else None
    if usuario is None or not usuario.activo or usuario.rol != RolUsuario.ADMIN:
        raise SinPermiso("Solo un administrador puede hacer esta operación del monedero.")
    return usuario


# ─── Monedero ────────────────────────────────────────────────────────────


def monedero_de_cliente(session, cliente_id: int, *, bloquear: bool = False) -> Monedero | None:
    stmt = select(Monedero).where(Monedero.cliente_id == int(cliente_id))
    if bloquear:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).first()


def _obtener_o_crear(session, cliente_id: int) -> Monedero:
    """El monedero del cliente, bloqueado; se crea la primera vez que gana
    cashback (no se asigna a todos los clientes de golpe)."""
    monedero = monedero_de_cliente(session, cliente_id, bloquear=True)
    if monedero is not None:
        return monedero
    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise MonederoError("El cliente no existe.")
    try:
        with session.begin_nested():
            session.add(Monedero(cliente_id=int(cliente_id), estado=ACTIVO))
            session.flush()
    except IntegrityError:
        # Otra terminal lo creó al mismo tiempo: se usa el suyo.
        pass
    monedero = monedero_de_cliente(session, cliente_id, bloquear=True)
    if monedero is None:  # pragma: no cover — no debería pasar
        raise MonederoError("No se pudo abrir el monedero del cliente.")
    return monedero


def _ahora(momento: datetime | None) -> datetime:
    momento = momento or datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento


def _con_zona(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class CreditoRestante:
    movimiento: MonederoMovimiento
    restante: Decimal

    @property
    def expira_at(self) -> datetime | None:
        return _con_zona(self.movimiento.expira_at)


def _creditos(session, monedero_id: int) -> list[CreditoRestante]:
    """Cada crédito con lo que le queda (monto − lo que ya consumieron)."""
    aplicado = (
        select(MonederoAplicacion.credito_id, func.coalesce(func.sum(MonederoAplicacion.monto), 0).label("aplicado"))
        .group_by(MonederoAplicacion.credito_id)
        .subquery()
    )
    filas = session.execute(
        select(MonederoMovimiento, func.coalesce(aplicado.c.aplicado, 0))
        .outerjoin(aplicado, aplicado.c.credito_id == MonederoMovimiento.id)
        .where(
            MonederoMovimiento.monedero_id == int(monedero_id),
            MonederoMovimiento.tipo.in_(TIPOS_CREDITO),
        )
        .order_by(MonederoMovimiento.expira_at.asc(), MonederoMovimiento.id.asc())
    ).all()
    return [CreditoRestante(mov, (_d(mov.monto) - _d(usado)).quantize(_CENT)) for mov, usado in filas]


@dataclass(frozen=True)
class SaldoMonedero:
    disponible: Decimal
    vencido_por_procesar: Decimal   # ya venció pero el proceso diario aún no lo asienta
    expirado: Decimal               # vencimientos ya asentados (histórico)
    proximo_vencimiento: datetime | None
    monto_proximo_vencimiento: Decimal


def saldo(session, monedero_id: int, momento: datetime | None = None) -> SaldoMonedero:
    momento = _ahora(momento)
    disponible = vencido = proximo_monto = _CERO
    proximo: datetime | None = None
    for credito in _creditos(session, monedero_id):
        if credito.restante <= 0:
            continue
        if credito.expira_at is not None and credito.expira_at <= momento:
            vencido += credito.restante
            continue
        disponible += credito.restante
        if credito.expira_at is not None and (proximo is None or credito.expira_at < proximo):
            proximo = credito.expira_at
            proximo_monto = credito.restante
        elif credito.expira_at is not None and credito.expira_at == proximo:
            proximo_monto += credito.restante
    expirado = -_d(
        session.scalar(
            select(func.coalesce(func.sum(MonederoMovimiento.monto), 0)).where(
                MonederoMovimiento.monedero_id == int(monedero_id),
                MonederoMovimiento.tipo == EXPIRACION,
            )
        )
    )
    return SaldoMonedero(
        disponible=disponible.quantize(_CENT),
        vencido_por_procesar=vencido.quantize(_CENT),
        expirado=expirado.quantize(_CENT),
        proximo_vencimiento=proximo,
        monto_proximo_vencimiento=proximo_monto.quantize(_CENT),
    )


@dataclass(frozen=True)
class ResumenCliente:
    cliente_id: int
    codigo: str
    nombre: str
    tiene_monedero: bool
    estado: str
    disponible: Decimal
    proximo_vencimiento: datetime | None
    monto_proximo_vencimiento: Decimal
    tasa: Decimal | None
    #: E5-A: % que puede tomar como descuento en vez de Monedero (Mayorista).
    descuento_disponible: Decimal | None = None
    #: Nombre del programa del cliente hoy («Maximoda Club»), para el ticket.
    programa: str | None = None

    @property
    def puede_canjear(self) -> bool:
        return self.tiene_monedero and self.estado == ACTIVO and self.disponible > 0


def resumen_cliente(session, cliente_id: int, momento: datetime | None = None) -> ResumenCliente:
    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise MonederoError("El cliente no existe.")
    monedero = monedero_de_cliente(session, cliente.id)
    tasa = tasa_para_cliente(session, cliente.id, momento)
    descuento = descuento_disponible(session, cliente.id, momento)
    prog = programa_en(session, cliente.id, momento)
    nombre_programa = prog.nombre if prog is not None else None
    if monedero is None:
        return ResumenCliente(cliente.id, cliente.codigo_cliente, cliente.nombre, False, ACTIVO, _CERO, None, _CERO,
                              tasa, descuento, nombre_programa)
    s = saldo(session, monedero.id, momento)
    return ResumenCliente(
        cliente.id,
        cliente.codigo_cliente,
        cliente.nombre,
        True,
        monedero.estado,
        s.disponible,
        s.proximo_vencimiento,
        s.monto_proximo_vencimiento,
        tasa,
        descuento,
        nombre_programa,
    )


# ─── Movimientos ─────────────────────────────────────────────────────────


def _por_llave(session, llave: str) -> MonederoMovimiento | None:
    return session.scalars(select(MonederoMovimiento).where(MonederoMovimiento.idempotency_key == llave)).first()


def _nuevo_movimiento(session, **campos) -> MonederoMovimiento:
    mov = MonederoMovimiento(**campos)
    session.add(mov)
    session.flush()
    return mov


def _aplicar(session, debito: MonederoMovimiento, monto: Decimal, creditos: list[CreditoRestante]) -> None:
    """Reparte `monto` del débito entre los créditos dados, en ese orden."""
    pendiente = _d(monto)
    for credito in creditos:
        if pendiente <= 0:
            break
        if credito.restante <= 0:
            continue
        toma = min(pendiente, credito.restante)
        session.add(MonederoAplicacion(debito_id=debito.id, credito_id=credito.movimiento.id, monto=toma))
        pendiente -= toma
    if pendiente > 0:
        raise SaldoInsuficiente("Saldo insuficiente en el monedero.")
    session.flush()


def _vigentes(session, monedero_id: int, momento: datetime) -> list[CreditoRestante]:
    """Créditos no vencidos con algo de saldo, los que vencen antes primero."""
    return [
        c for c in _creditos(session, monedero_id)
        if c.restante > 0 and (c.expira_at is None or c.expira_at > momento)
    ]


def acreditar_cashback(
    session,
    *,
    libreta_venta: LibretaVenta,
    momento: datetime | None = None,
) -> MonederoMovimiento | None:
    """Acredita el cashback de una venta confirmada de la Libreta.

    Devuelve el movimiento (el ya existente si se repite) o None si la venta
    no genera cashback: sin cliente, no es venta, cashback apagado en la
    fecha de la venta, cliente sin programa, eligió descuento de programa
    en vez de Monedero, llevó descuento de empleada, importe cero, o monedero
    bloqueado/cerrado. La tasa es la del programa del cliente cuando se HIZO
    la venta (no al sincronizar), y queda guardada en el movimiento."""
    if libreta_venta is None or libreta_venta.cliente_id is None:
        return None
    if str(libreta_venta.tipo) != "venta":
        return None
    if Decimal(str(getattr(libreta_venta, "descuento_programa", None) or 0)) > 0:
        return None  # E5-A: eligió descuento en vez de Monedero
    if getattr(libreta_venta, "descuento_empleada", False):
        # D1 (Daniel, 2026-11-11): con descuento de empleada no se gana
        # Monedero, igual que el Mayorista: o descuento o Monedero.
        return None
    llave = _llave_venta("cashback", libreta_venta)
    existente = _por_llave(session, llave)
    if existente is not None:
        return existente
    fecha_venta = _con_zona(libreta_venta.created_at) or _ahora(momento)
    tasa = tasa_para_cliente(session, libreta_venta.cliente_id, fecha_venta)
    if tasa is None:
        return None
    base = importe_elegible(libreta_venta.monto_total, getattr(libreta_venta, "monto_monedero", None))
    # E7: lo cobrado en Oferta o Liquidación no genera Monedero.
    from pos_uniformes.services.rebaja_service import importe_rebajado

    base = max(base - importe_rebajado(getattr(libreta_venta, "detalle", None) or []), _CERO)
    base, con_tarjeta = base_sin_comision_tarjeta(libreta_venta, base)
    monto = calcular_cashback(base, tasa)
    if monto <= 0:
        return None
    monedero = _obtener_o_crear(session, libreta_venta.cliente_id)
    if monedero.estado != ACTIVO:
        return None
    acreditado = _ahora(momento)
    return _nuevo_movimiento(
        session,
        monedero_id=monedero.id,
        tipo=CASHBACK,
        monto=monto,
        libreta_venta_id=libreta_venta.id,
        operacion_uuid=libreta_venta.operacion_uuid,
        idempotency_key=llave,
        tasa_snapshot=tasa,
        base_calculo=base,
        expira_at=vencimiento_de(acreditado),
        motivo=(
            f"Cashback {tasa}% sobre ${base:,.2f}"
            f"{' (pago con tarjeta)' if con_tarjeta else ''} (venta {_ref_venta(libreta_venta)})"
        ),
        employee_code=(libreta_venta.employee_code or None),
        origen=libreta_venta.origen,
        created_at=acreditado,
    )


def canjear(
    session,
    *,
    libreta_venta: LibretaVenta,
    monto,
    employee_code: str | None = None,
    momento: datetime | None = None,
) -> MonederoMovimiento:
    """Paga parte (o todo) de una venta con saldo. Bloquea el monedero, valida
    y asienta el débito en la misma transacción que la venta.

    Requiere conexión: esta función solo corre contra la base, nunca desde la
    cola offline."""
    if libreta_venta.cliente_id is None:
        raise MonederoError("Para usar saldo hay que identificar al cliente con su QR.")
    if str(libreta_venta.tipo) != "venta":
        raise MonederoError("El saldo solo se puede usar en ventas.")
    monto = _d(monto)
    if monto <= 0:
        raise MonederoError("El monto a usar debe ser mayor a cero.")
    if monto > _d(libreta_venta.monto_total):
        raise MonederoError("No se puede usar más saldo que el total de la venta.")
    llave = _llave_venta("canje", libreta_venta)
    existente = _por_llave(session, llave)
    if existente is not None:
        return existente
    monedero = monedero_de_cliente(session, libreta_venta.cliente_id, bloquear=True)
    if monedero is None:
        raise SaldoInsuficiente("El cliente todavía no tiene saldo en su monedero.")
    if monedero.estado != ACTIVO:
        raise MonederoNoActivo(f"El monedero está {monedero.estado}: no se puede usar el saldo.")
    momento = _ahora(momento)
    creditos = _vigentes(session, monedero.id, momento)
    disponible = sum((c.restante for c in creditos), _CERO)
    if monto > disponible:
        raise SaldoInsuficiente(f"Saldo insuficiente: disponible ${disponible:,.2f}.")
    debito = _nuevo_movimiento(
        session,
        monedero_id=monedero.id,
        tipo=CANJE,
        monto=-monto,
        libreta_venta_id=libreta_venta.id,
        operacion_uuid=libreta_venta.operacion_uuid,
        idempotency_key=llave,
        motivo=f"Pago con saldo (venta {_ref_venta(libreta_venta)})",
        employee_code=(employee_code or libreta_venta.employee_code or None),
        origen=libreta_venta.origen,
        created_at=momento,
    )
    _aplicar(session, debito, monto, creditos)
    return debito


def _llave_venta(prefijo: str, libreta_venta: LibretaVenta) -> str:
    if libreta_venta.operacion_uuid:
        return f"{prefijo}:{libreta_venta.operacion_uuid}"
    return f"{prefijo}:libreta:{libreta_venta.id}"


def _ref_venta(libreta_venta: LibretaVenta) -> str:
    return f"#{libreta_venta.id}" if libreta_venta.id is not None else (libreta_venta.operacion_uuid or "")


def movimientos_de_operacion(session, libreta_venta_id: int) -> list[MonederoMovimiento]:
    return list(
        session.scalars(
            select(MonederoMovimiento)
            .where(MonederoMovimiento.libreta_venta_id == int(libreta_venta_id))
            .order_by(MonederoMovimiento.id)
        ).all()
    )


def tiene_movimientos(session, libreta_venta_id: int) -> bool:
    return session.scalar(
        select(MonederoMovimiento.id).where(MonederoMovimiento.libreta_venta_id == int(libreta_venta_id)).limit(1)
    ) is not None


def _consumido_por(session, credito_id: int) -> dict[str, Decimal]:
    """Cuánto de un crédito consumió cada tipo de débito."""
    filas = session.execute(
        select(MonederoMovimiento.tipo, func.sum(MonederoAplicacion.monto))
        .join(MonederoMovimiento, MonederoMovimiento.id == MonederoAplicacion.debito_id)
        .where(MonederoAplicacion.credito_id == int(credito_id))
        .group_by(MonederoMovimiento.tipo)
    ).all()
    return {tipo: _d(total) for tipo, total in filas}


def _donde_quedo(session, credito: MonederoMovimiento, _nivel: int = 0) -> tuple[list[CreditoRestante], Decimal]:
    """Dónde está hoy el saldo de un crédito y cuánto se gastó de verdad.

    (Daniel, 2026-11-12) Si el cliente pagó con ese saldo y esa venta luego se
    anuló, el dinero regresó como una `devolucion_canje` nueva: el crédito
    original lo sigue viendo «gastado», pero el cliente lo tiene completo.
    Aquí se sigue ese dinero hasta la devolución (y, si también se usó y se
    devolvió, hasta la siguiente).

    Devuelve los créditos con lo que les queda (el original primero) y lo que
    se gastó sin regresar. Lo que venció o ya se revirtió no cuenta como
    gastado."""
    aplicaciones = session.execute(
        select(MonederoAplicacion, MonederoMovimiento.tipo)
        .join(MonederoMovimiento, MonederoMovimiento.id == MonederoAplicacion.debito_id)
        .where(MonederoAplicacion.credito_id == int(credito.id))
        .order_by(MonederoAplicacion.id)
    ).all()
    restante = (_d(credito.monto) - sum((_d(a.monto) for a, _t in aplicaciones), _CERO)).quantize(_CENT)
    creditos = [CreditoRestante(credito, restante)] if restante > 0 else []
    gastado = _CERO
    for aplic, tipo in aplicaciones:
        if tipo in (EXPIRACION, REVERSA_CASHBACK):
            continue
        devolucion = _por_llave(session, f"devolucion:{aplic.id}") if tipo == CANJE else None
        if devolucion is None or _nivel >= 20:
            gastado += _d(aplic.monto)
            continue
        mas, gastado_alla = _donde_quedo(session, devolucion, _nivel + 1)
        creditos.extend(mas)
        gastado += gastado_alla
    return creditos, gastado.quantize(_CENT)


@dataclass(frozen=True)
class ResultadoAnulacion:
    reversas: list[MonederoMovimiento]
    devoluciones: list[MonederoMovimiento]

    @property
    def cashback_revertido(self) -> Decimal:
        return -sum((_d(m.monto) for m in self.reversas), _CERO)

    @property
    def saldo_devuelto(self) -> Decimal:
        return sum((_d(m.monto) for m in self.devoluciones), _CERO)


def anular_operacion(
    session,
    libreta_venta: LibretaVenta,
    *,
    usuario_id: int,
    motivo: str,
    momento: datetime | None = None,
) -> ResultadoAnulacion:
    """Compensa todo lo que una venta hizo en el monedero, sin borrar nada.

    - Cashback otorgado → `reversa_cashback` por lo que quede de él. Si ya se
      gastó (aunque sea en parte), se detiene: no se crea deuda de monedero;
      hace falta un ajuste autorizado.
    - Saldo usado para pagar → `devolucion_canje` por cada crédito consumido,
      con el MISMO vencimiento que tenía ese crédito.

    Valida todo antes de escribir. Repetirla no duplica nada (llaves)."""
    _validar_admin(session, usuario_id)
    motivo = (motivo or "").strip()
    if not motivo:
        raise MonederoError("La anulación necesita un motivo.")
    momento = _ahora(momento)
    movimientos = movimientos_de_operacion(session, libreta_venta.id)
    if not movimientos:
        return ResultadoAnulacion([], [])
    monederos = {m.monedero_id for m in movimientos}
    for monedero_id in sorted(monederos):
        session.scalars(select(Monedero).where(Monedero.id == monedero_id).with_for_update()).first()

    # 1) Validar
    planes: list[tuple[MonederoMovimiento, list[CreditoRestante]]] = []
    for mov in movimientos:
        if mov.tipo != CASHBACK or _por_llave(session, f"reversa:{mov.id}") is not None:
            continue
        creditos, gastado = _donde_quedo(session, mov)
        if gastado > 0:
            raise CashbackYaGastado(
                f"El cliente ya usó ${gastado:,.2f} del cashback de esta venta. "
                "Revertirlo dejaría su saldo en negativo: haz primero un ajuste autorizado."
            )
        planes.append((mov, creditos))

    # 2) Escribir
    reversas: list[MonederoMovimiento] = []
    for mov, creditos in planes:
        restante = sum((c.restante for c in creditos), _CERO).quantize(_CENT)
        if restante <= 0:
            continue  # ya venció: no queda nada que revertir
        reversa = _nuevo_movimiento(
            session,
            monedero_id=mov.monedero_id,
            tipo=REVERSA_CASHBACK,
            monto=-restante,
            operacion_uuid=mov.operacion_uuid,
            movimiento_relacionado_id=mov.id,
            idempotency_key=f"reversa:{mov.id}",
            motivo=f"Reversa de cashback por anulación: {motivo}",
            usuario_id=int(usuario_id),
            created_at=momento,
        )
        _aplicar(session, reversa, restante, creditos)
        reversas.append(reversa)

    devoluciones: list[MonederoMovimiento] = []
    for mov in movimientos:
        if mov.tipo != CANJE:
            continue
        aplicaciones = session.scalars(
            select(MonederoAplicacion).where(MonederoAplicacion.debito_id == mov.id).order_by(MonederoAplicacion.id)
        ).all()
        for aplic in aplicaciones:
            llave = f"devolucion:{aplic.id}"
            if _por_llave(session, llave) is not None:
                continue
            credito_original = session.get(MonederoMovimiento, aplic.credito_id)
            devoluciones.append(
                _nuevo_movimiento(
                    session,
                    monedero_id=mov.monedero_id,
                    tipo=DEVOLUCION_CANJE,
                    monto=_d(aplic.monto),
                    operacion_uuid=mov.operacion_uuid,
                    movimiento_relacionado_id=mov.id,
                    idempotency_key=llave,
                    expira_at=credito_original.expira_at,
                    motivo=f"Devolución del saldo usado, por anulación: {motivo}",
                    usuario_id=int(usuario_id),
                    created_at=momento,
                )
            )
    return ResultadoAnulacion(reversas, devoluciones)


def soltar_operacion(session, libreta_venta_id: int) -> None:
    """Quita la liga de los movimientos a la Libreta para poder borrar la
    operación ya compensada. El movimiento conserva `operacion_uuid`.

    Es el único cambio que el trigger de la base permite sobre un movimiento."""
    for mov in movimientos_de_operacion(session, libreta_venta_id):
        mov.libreta_venta_id = None
    session.flush()


def procesar_vencimientos(session, momento: datetime | None = None) -> int:
    """Asienta como `expiracion` lo que quede de cada crédito vencido.

    Correrlo dos veces no duplica nada (llave `expira:<crédito>`). El saldo
    disponible ya excluye lo vencido aunque esto no haya corrido."""
    momento = _ahora(momento)
    monederos = session.scalars(
        select(MonederoMovimiento.monedero_id)
        .where(
            MonederoMovimiento.tipo.in_(TIPOS_CREDITO),
            MonederoMovimiento.expira_at <= momento,
        )
        .distinct()
    ).all()
    asentados = 0
    for monedero_id in monederos:
        session.scalars(select(Monedero).where(Monedero.id == monedero_id).with_for_update()).first()
        for credito in _creditos(session, monedero_id):
            if credito.restante <= 0 or credito.expira_at is None or credito.expira_at > momento:
                continue
            llave = f"expira:{credito.movimiento.id}"
            if _por_llave(session, llave) is not None:
                continue
            expiracion = _nuevo_movimiento(
                session,
                monedero_id=monedero_id,
                tipo=EXPIRACION,
                monto=-credito.restante,
                operacion_uuid=credito.movimiento.operacion_uuid,
                movimiento_relacionado_id=credito.movimiento.id,
                idempotency_key=llave,
                motivo=f"Venció el saldo acreditado el {_fecha_corta(credito.movimiento.created_at)}",
                created_at=momento,
            )
            _aplicar(session, expiracion, credito.restante, [credito])
            asentados += 1
    return asentados


def _fecha_corta(momento: datetime | None) -> str:
    if momento is None:
        return "?"
    local = _con_zona(momento).astimezone()
    return local.strftime("%d/%m/%Y")


def ajustar(
    session,
    *,
    cliente_id: int,
    monto,
    motivo: str,
    usuario_id: int,
    referencia: str | None = None,
    llave: str | None = None,
    momento: datetime | None = None,
) -> MonederoMovimiento:
    """Ajuste manual autorizado: positivo = a favor, negativo = en contra.

    Solo ADMIN y siempre con motivo. Un ajuste a favor vence a los 12 meses,
    como cualquier crédito. Uno en contra nunca deja el saldo negativo."""
    _validar_admin(session, usuario_id)
    motivo = (motivo or "").strip()
    if not motivo:
        raise MonederoError("El ajuste necesita un motivo.")
    monto = _d(monto)
    if monto == 0:
        raise MonederoError("El ajuste no puede ser de $0.00.")
    llave = llave or f"ajuste:{uuid.uuid4()}"
    existente = _por_llave(session, llave)
    if existente is not None:
        return existente
    momento = _ahora(momento)
    texto = motivo if not referencia else f"{motivo} (ref. {referencia.strip()})"
    if monto > 0:
        monedero = _obtener_o_crear(session, cliente_id)
        return _nuevo_movimiento(
            session,
            monedero_id=monedero.id,
            tipo=AJUSTE_ABONO,
            monto=monto,
            idempotency_key=llave,
            expira_at=vencimiento_de(momento),
            motivo=texto[:2000],
            usuario_id=int(usuario_id),
            created_at=momento,
        )
    monedero = monedero_de_cliente(session, cliente_id, bloquear=True)
    if monedero is None:
        raise SaldoInsuficiente("El cliente no tiene monedero.")
    creditos = _vigentes(session, monedero.id, momento)
    disponible = sum((c.restante for c in creditos), _CERO)
    if -monto > disponible:
        raise SaldoInsuficiente(f"El ajuste dejaría el saldo en negativo (disponible ${disponible:,.2f}).")
    debito = _nuevo_movimiento(
        session,
        monedero_id=monedero.id,
        tipo=AJUSTE_CARGO,
        monto=monto,
        idempotency_key=llave,
        motivo=texto[:2000],
        usuario_id=int(usuario_id),
        created_at=momento,
    )
    _aplicar(session, debito, -monto, creditos)
    return debito


def cambiar_estado(session, *, cliente_id: int, estado: str, motivo: str, usuario_id: int) -> Monedero:
    """Bloquea, desbloquea o cierra el monedero. Solo ADMIN, con motivo."""
    _validar_admin(session, usuario_id)
    if estado not in ESTADOS:
        raise MonederoError(f"Estado inválido: {estado}")
    motivo = (motivo or "").strip()
    if not motivo:
        raise MonederoError("El cambio de estado necesita un motivo.")
    monedero = _obtener_o_crear(session, cliente_id)
    monedero.estado = estado
    monedero.motivo_estado = motivo[:200]
    monedero.updated_at = datetime.now(timezone.utc)
    session.flush()
    return monedero


# ─── Consultas ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FilaHistorial:
    movimiento: MonederoMovimiento
    saldo_contable: Decimal   # suma acumulada del libro tras este movimiento

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS_TIPO.get(self.movimiento.tipo, self.movimiento.tipo)


def historial(session, monedero_id: int) -> list[FilaHistorial]:
    """Movimientos del más reciente al más viejo, con el saldo acumulado."""
    movimientos = session.scalars(
        select(MonederoMovimiento)
        .where(MonederoMovimiento.monedero_id == int(monedero_id))
        .order_by(MonederoMovimiento.created_at.asc(), MonederoMovimiento.id.asc())
    ).all()
    acumulado = _CERO
    filas: list[FilaHistorial] = []
    for mov in movimientos:
        acumulado = (acumulado + _d(mov.monto)).quantize(_CENT)
        filas.append(FilaHistorial(mov, acumulado))
    return list(reversed(filas))


def buscar_clientes(session, texto: str, limite: int = 50) -> list[Cliente]:
    """Clientes activos por código, nombre o teléfono (para consultar)."""
    texto = (texto or "").strip()
    stmt = select(Cliente).where(Cliente.activo.is_(True))
    if texto:
        patron = f"%{texto}%"
        stmt = stmt.where(
            Cliente.codigo_cliente.ilike(patron) | Cliente.nombre.ilike(patron) | Cliente.telefono.ilike(patron)
        )
    return list(session.scalars(stmt.order_by(Cliente.nombre).limit(limite)).all())


@dataclass(frozen=True)
class ReporteMonedero:
    desde: datetime
    hasta: datetime
    por_tipo: dict[str, Decimal]
    operaciones_por_tipo: dict[str, int]
    saldo_vigente_total: Decimal
    proximo_a_vencer: Decimal
    dias_proximo: int
    clientes_con_monedero: int
    ajustes: list[MonederoMovimiento]

    @property
    def cashback_generado(self) -> Decimal:
        return self.por_tipo.get(CASHBACK, _CERO)

    @property
    def saldo_utilizado(self) -> Decimal:
        return -self.por_tipo.get(CANJE, _CERO) - self.por_tipo.get(DEVOLUCION_CANJE, _CERO)

    @property
    def expirado(self) -> Decimal:
        return -self.por_tipo.get(EXPIRACION, _CERO)

    @property
    def reversiones(self) -> Decimal:
        return -self.por_tipo.get(REVERSA_CASHBACK, _CERO)


def reporte(session, desde: datetime, hasta: datetime, *, dias_proximo: int = 30, momento: datetime | None = None) -> ReporteMonedero:
    momento = _ahora(momento)
    filas = session.execute(
        select(MonederoMovimiento.tipo, func.sum(MonederoMovimiento.monto), func.count(MonederoMovimiento.id))
        .where(MonederoMovimiento.created_at >= desde, MonederoMovimiento.created_at < hasta)
        .group_by(MonederoMovimiento.tipo)
    ).all()
    por_tipo = {tipo: _d(total) for tipo, total, _n in filas}
    conteos = {tipo: int(n) for tipo, _total, n in filas}
    limite = momento + timedelta(days=dias_proximo)
    vigente = proximo = _CERO
    monederos = session.scalars(select(Monedero.id)).all()
    for monedero_id in monederos:
        for credito in _creditos(session, monedero_id):
            if credito.restante <= 0 or credito.expira_at is None or credito.expira_at <= momento:
                continue
            vigente += credito.restante
            if credito.expira_at <= limite:
                proximo += credito.restante
    ajustes = list(
        session.scalars(
            select(MonederoMovimiento)
            .where(
                MonederoMovimiento.tipo.in_((AJUSTE_ABONO, AJUSTE_CARGO)),
                MonederoMovimiento.created_at >= desde,
                MonederoMovimiento.created_at < hasta,
            )
            .order_by(MonederoMovimiento.created_at.desc())
        ).all()
    )
    return ReporteMonedero(
        desde=desde,
        hasta=hasta,
        por_tipo=por_tipo,
        operaciones_por_tipo=conteos,
        saldo_vigente_total=vigente.quantize(_CENT),
        proximo_a_vencer=proximo.quantize(_CENT),
        dias_proximo=dias_proximo,
        clientes_con_monedero=len(monederos),
        ajustes=ajustes,
    )


def acreditar_faltantes(session, *, dias: int = 30, momento: datetime | None = None) -> int:
    """Red de seguridad: acredita el cashback de ventas con cliente que se
    quedaron sin él (p. ej. falló al sincronizar). Idempotente por llave.
    Solo mira los últimos `dias` días."""
    momento = _ahora(momento)
    desde = momento - timedelta(days=dias)
    ventas = session.scalars(
        select(LibretaVenta).where(
            LibretaVenta.cliente_id.is_not(None),
            LibretaVenta.tipo == "venta",
            LibretaVenta.created_at >= desde,
        )
    ).all()
    acreditadas = 0
    for venta in ventas:
        if _por_llave(session, _llave_venta("cashback", venta)) is not None:
            continue
        try:
            with session.begin_nested():
                if acreditar_cashback(session, libreta_venta=venta, momento=momento) is not None:
                    acreditadas += 1
        except Exception:  # noqa: BLE001 — una venta mala no detiene a las demás
            logger.exception("Monedero: no se pudo acreditar el cashback de la venta %s", venta.id)
    return acreditadas
