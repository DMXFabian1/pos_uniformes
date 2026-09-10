"""Corte de caja por periodo con reactivo (fondo). Distinto de caja_service.py
(sesiones y movimientos de caja del POS principal).

Reglas (Daniel, 2026-09-08):
- El cajón siempre tiene un fondo ("reactivo"). Efectivo esperado =
  reactivo + ventas en efectivo + abonos en efectivo del periodo
  - pagos a empleadas - otros retiros.
- El corte es por MOMENTO: cubre desde el corte anterior hasta ahora. Lo que
  se venda después queda para el siguiente corte, aunque sea el mismo día.
- Al cerrar se captura lo contado y cuánto se queda como reactivo (por
  defecto el mismo fondo). Solo el dueño (VEND-1) y el encargado (ENC-1) lo hacen.

La lógica de sumas es pura; lo que lleva `session` toca la base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

_CENT = Decimal("0.01")
_SIN_CORTE_DIAS = 90
DUENO_CODE = "VEND-1"  # Daniel: su cifra es la oficial; el real solo lo ve él  # sin corte previo: periodo abierto hacia atrás


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENT)


@dataclass(frozen=True)
class ParametrosCaja:
    reactivo_actual: Decimal = Decimal("0.00")
    sueldo_base: Decimal = Decimal("0.00")
    tarifa_comision: Decimal = Decimal("0.00")
    descuento_falta: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class ResumenPeriodo:
    operaciones: int
    piezas: int
    ventas: Decimal          # cobrado en ventas (efectivo + tarjeta)
    abonos: Decimal          # cobrado en abonos (efectivo + tarjeta)
    apartados: Decimal       # comprometido, no es dinero recibido
    tarjeta: Decimal         # lo que entró por terminal (no está en el cajón)
    efectivo: Decimal        # ventas + abonos pagados en efectivo


@dataclass(frozen=True)
class EstadoCaja:
    desde: datetime | None
    hasta: datetime
    reactivo: Decimal
    resumen: ResumenPeriodo
    pagos: Decimal           # pagos a empleadas registrados en el periodo
    otros_retiros: Decimal = Decimal("0.00")   # capturado a mano al cerrar (dueño)
    retiros: Decimal = Decimal("0.00")         # apuntados con motivo (caja_retiro)

    @property
    def total_retiros(self) -> Decimal:
        return (self.retiros + self.otros_retiros).quantize(_CENT)

    @property
    def esperado(self) -> Decimal:
        return (self.reactivo + self.resumen.efectivo - self.pagos - self.total_retiros).quantize(_CENT)


# ─── Lógica pura ─────────────────────────────────────────────────────────

def resumir_periodo(rows: list) -> ResumenPeriodo:
    """Suma las operaciones de la Libreta de un periodo (mismas reglas que
    el corte por día: tarjeta no está en caja, apartado no es dinero)."""
    operaciones = piezas = 0
    ventas = abonos = apartados = tarjeta = efectivo = Decimal("0.00")
    for row in rows:
        operaciones += 1
        piezas += int(row.piezas or 0)
        monto = _d(row.monto_total)
        tipo = str(row.tipo)
        con_tarjeta = bool(getattr(row, "pago_tarjeta", False))
        if tipo == "apartado":
            apartados += monto
            continue
        if tipo == "abono":
            abonos += monto
        else:
            ventas += monto
        if con_tarjeta:
            tarjeta += monto
        else:
            efectivo += monto
    return ResumenPeriodo(
        operaciones=operaciones,
        piezas=piezas,
        ventas=ventas.quantize(_CENT),
        abonos=abonos.quantize(_CENT),
        apartados=apartados.quantize(_CENT),
        tarjeta=tarjeta.quantize(_CENT),
        efectivo=efectivo.quantize(_CENT),
    )


def diferencia(contado: Decimal, esperado: Decimal) -> Decimal:
    """Positivo = sobra, negativo = falta."""
    return (_d(contado) - _d(esperado)).quantize(_CENT)


# ─── Acceso a datos ──────────────────────────────────────────────────────

def cargar_parametros(session) -> ParametrosCaja:
    from pos_uniformes.database.models import CajaParametros

    fila = session.get(CajaParametros, 1)
    if fila is None:
        return ParametrosCaja()
    return ParametrosCaja(
        reactivo_actual=_d(fila.reactivo_actual),
        sueldo_base=_d(fila.sueldo_base),
        tarifa_comision=_d(fila.tarifa_comision),
        descuento_falta=_d(fila.descuento_falta),
    )


def guardar_parametros(session, **campos) -> ParametrosCaja:
    """Actualiza solo los campos dados (reactivo_actual, sueldo_base, ...)."""
    from pos_uniformes.database.models import CajaParametros

    fila = session.get(CajaParametros, 1)
    if fila is None:
        fila = CajaParametros(id=1)
        session.add(fila)
    permitidos = {"reactivo_actual", "sueldo_base", "tarifa_comision", "descuento_falta"}
    for nombre, valor in campos.items():
        if nombre not in permitidos:
            raise ValueError(f"parámetro desconocido: {nombre}")
        setattr(fila, nombre, _d(valor))
    session.commit()
    return cargar_parametros(session)


def ultimo_corte(session):
    from pos_uniformes.database.models import LibretaCorte

    return session.scalars(
        select(LibretaCorte).order_by(LibretaCorte.created_at.desc()).limit(1)
    ).first()


def inicio_periodo(session) -> datetime | None:
    """Momento del corte anterior; None si nunca se ha hecho corte."""
    corte = ultimo_corte(session)
    if corte is None:
        return None
    return corte.hasta or corte.created_at


def operaciones_del_periodo(session, desde: datetime | None, hasta: datetime) -> list:
    from pos_uniformes.database.models import LibretaVenta

    if desde is None:
        desde = hasta - timedelta(days=_SIN_CORTE_DIAS)
    stmt = (
        select(LibretaVenta)
        .where(LibretaVenta.created_at > desde, LibretaVenta.created_at <= hasta)
        .order_by(LibretaVenta.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def pagos_del_periodo(session, desde: datetime | None, hasta: datetime) -> Decimal:
    from pos_uniformes.database.models import EmpleadaPago

    stmt = select(func.coalesce(func.sum(EmpleadaPago.total), 0)).where(EmpleadaPago.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(EmpleadaPago.created_at > desde)
    return _d(session.scalar(stmt))


def pagos_registrados_del_periodo(session, desde: datetime | None, hasta: datetime) -> list:
    """Filas EmpleadaPago del periodo (para desglosarlas en el ticket)."""
    from pos_uniformes.database.models import EmpleadaPago

    stmt = select(EmpleadaPago).where(EmpleadaPago.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(EmpleadaPago.created_at > desde)
    return list(session.scalars(stmt.order_by(EmpleadaPago.id)).all())


def estado_caja(session, ahora: datetime | None = None, otros_retiros=Decimal("0.00")) -> EstadoCaja:
    """Lo que debería haber en el cajón ahora mismo."""
    ahora = ahora or datetime.now().astimezone()
    desde = inicio_periodo(session)
    params = cargar_parametros(session)
    rows = operaciones_del_periodo(session, desde, ahora)
    try:
        from pos_uniformes.services.retiros_service import total_retiros

        retiros = total_retiros(session, desde, ahora)
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        retiros = Decimal("0.00")
    return EstadoCaja(
        desde=desde,
        hasta=ahora,
        reactivo=params.reactivo_actual,
        resumen=resumir_periodo(rows),
        pagos=pagos_del_periodo(session, desde, ahora),
        otros_retiros=_d(otros_retiros),
        retiros=retiros,
    )


def cerrar_corte(
    session,
    *,
    contado,
    creado_por: str,
    reactivo_final=None,
    otros_retiros=Decimal("0.00"),
    nota: str | None = None,
    ahora: datetime | None = None,
):
    """Cierra el periodo: guarda el corte y deja `reactivo_final` como fondo
    del siguiente. `contado` es el efectivo real en el cajón."""
    from pos_uniformes.database.models import LibretaCorte

    ahora = ahora or datetime.now().astimezone()
    estado = estado_caja(session, ahora, otros_retiros=otros_retiros)
    contado = _d(contado)
    reactivo_final = estado.reactivo if reactivo_final is None else _d(reactivo_final)
    if reactivo_final < 0 or contado < 0:
        raise ValueError("El contado y el reactivo no pueden ser negativos.")
    if reactivo_final > contado:
        raise ValueError("El reactivo que se queda no puede ser mayor a lo contado.")
    local = ahora.astimezone() if ahora.tzinfo else ahora
    # Regla de Daniel (2026-09-09): su cifra final es la oficial (ticket,
    # encargado y PWA solo ven `monto_final`); el real calculado se guarda en
    # `monto_esperado` y SOLO lo ve él (historial, Telegram) como "ajuste".
    corte = LibretaCorte(
        fecha=local.date(),
        periodo_label=_etiqueta_periodo(estado.desde, ahora),
        monto_final=contado,
        operaciones=estado.resumen.operaciones,
        piezas=estado.resumen.piezas,
        nota=(nota or "").strip()[:200] or None,
        creado_por=str(creado_por or "").strip().upper()[:40],
        desde=estado.desde,
        hasta=ahora,
        reactivo_inicial=estado.reactivo,
        monto_esperado=estado.esperado,
        retiros_pagos=estado.pagos,
        otros_retiros=estado.total_retiros,
        reactivo_final=reactivo_final,
    )
    session.add(corte)
    guardar_parametros(session, reactivo_actual=reactivo_final)  # hace commit
    _avisar_corte(session, corte, estado)
    return corte


def _avisar_corte(session, corte, estado: EstadoCaja) -> None:
    """Alerta al celular de Daniel (cola que manda el bot). Nunca rompe el corte."""
    try:
        from pos_uniformes.services.alertas_service import encolar, texto_alerta_corte

        pagos = pagos_registrados_del_periodo(session, estado.desde, estado.hasta)
        encolar(session, texto_alerta_corte(corte, estado.resumen.efectivo, pagos=pagos))
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("Corte guardado, pero la alerta no se encoló: %s", exc)
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass


def ajustes_en_rango(session, desde, hasta) -> Decimal:
    """Cuánto cambió el dueño sus cortes en este rango (negativo = sacó dinero).

    Su cifra es la oficial (2026-09-09): la Libreta también la respeta, así
    que el efectivo mostrado se corrige con esta suma. El modo real la ignora.
    """
    from pos_uniformes.database.models import LibretaCorte

    try:
        stmt = select(
            func.coalesce(func.sum(LibretaCorte.monto_final - LibretaCorte.monto_esperado), 0)
        ).where(
            LibretaCorte.creado_por == DUENO_CODE,
            LibretaCorte.hasta.is_not(None),
            LibretaCorte.monto_esperado > 0,
        )
        if desde is not None:
            stmt = stmt.where(LibretaCorte.hasta >= desde)
        if hasta is not None:
            stmt = stmt.where(LibretaCorte.hasta <= hasta)
        return _d(session.scalar(stmt))
    except Exception:  # noqa: BLE001 — base sin las columnas nuevas
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return Decimal("0.00")


def _etiqueta_periodo(desde: datetime | None, hasta: datetime) -> str:
    h = (hasta.astimezone() if hasta.tzinfo else hasta).strftime("%d/%m %H:%M")
    if desde is None:
        return f"hasta {h}"
    d = (desde.astimezone() if desde.tzinfo else desde).strftime("%d/%m %H:%M")
    return f"{d} → {h}"


# ─── Corte automático del encargado ──────────────────────────────────────

@dataclass(frozen=True)
class CorteAutomatico:
    corte: object            # LibretaCorte guardado
    estado: EstadoCaja       # estado con el que se cerró (ya incluye los pagos)
    pagos: list              # EmpleadaPago registrados en este corte


def pagos_que_tocan_hoy(session, hoy=None) -> list:
    """Empleadas cuyo pago cae hoy o ya se pasó y que no han cobrado hoy."""
    from datetime import date as _date

    from pos_uniformes.services.calendario_empleadas_service import cargar_horario
    from pos_uniformes.services.nomina_service import avisos_de_pago

    hoy = hoy or _date.today()
    pendientes = []
    for a in avisos_de_pago(session, hoy, dias=0):
        if a.dias_para_pago is None or a.dias_para_pago > 0:
            continue
        if cargar_horario(session, a.employee_code).fecha_ultimo_pago == hoy:
            continue  # ya cobró hoy
        pendientes.append(a)
    return pendientes


@dataclass(frozen=True)
class DatosTicketEncargado:
    """Lo que lleva el ticket del encargado, ya SIN los movimientos privados.

    Ese papel se queda en la tienda y lo lee el encargado, así que nunca
    incluye lo que el dueño marcó como privado: ni el dinero de tarjeta, ni
    las piezas, ni las comisiones de esas ventas."""

    por_empleada: list
    tarjeta: Decimal
    tarjeta_ops: int
    retiros: list


def datos_ticket_encargado(session, desde: datetime | None, hasta: datetime) -> DatosTicketEncargado:
    from pos_uniformes.services.libreta_service import resumir_por_empleada, sin_privados

    rows = operaciones_del_periodo(session, desde, hasta)
    # Las comisiones y las piezas van completas: la empleada cobra lo que
    # trabajó. Lo que desaparece es el DINERO de los cobros privados.
    visibles = sin_privados(rows)
    tarjeta = sum(
        (
            _d(r.monto_total)
            for r in visibles
            if str(r.tipo) in ("venta", "abono") and bool(getattr(r, "pago_tarjeta", False))
        ),
        Decimal("0.00"),
    )
    ops = sum(
        1
        for r in visibles
        if str(r.tipo) in ("venta", "abono") and bool(getattr(r, "pago_tarjeta", False))
    )
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        retiros = retiros_del_periodo(session, desde, hasta)
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        retiros = []
    return DatosTicketEncargado(
        por_empleada=resumir_por_empleada(rows), tarjeta=tarjeta, tarjeta_ops=ops, retiros=retiros
    )


def cerrar_corte_automatico(
    session, *, creado_por: str, ahora: datetime | None = None, nota: str | None = None,
    retirar: Decimal | None = None,
) -> CorteAutomatico:
    """Corte de un botón (encargado): registra los pagos que tocan hoy, cierra
    con el esperado como cifra final y deja el mismo fondo. Nadie cuenta ni
    captura nada; el ticket dice cuánto se vendió, a quién pagar y cuánto
    se retira.

    `retirar` (solo Daniel, desde el celular) fija cuánto sale del cajón: el
    corte cierra en fondo + esa cifra y el resto se queda. El real calculado
    igual queda guardado en `monto_esperado`, que solo ve él."""
    from pos_uniformes.services.nomina_service import registrar_pago_con_monto

    ahora = ahora or datetime.now().astimezone()
    hoy = (ahora.astimezone() if ahora.tzinfo else ahora).date()
    pagos = []
    for aviso in pagos_que_tocan_hoy(session, hoy):
        # Fechados EXACTAMENTE a la hora del corte: así caen dentro del
        # periodo que se cierra (<= hasta) aunque `ahora` venga del caller.
        pagos.append(registrar_pago_con_monto(session, aviso.employee_code, creado_por=creado_por, fecha=hoy, momento=ahora))
    estado = estado_caja(session, ahora)
    # Si los pagos superaron la venta, el fondo baja (no hay de dónde más
    # sacar); si no, se queda igual y el resto se retira.
    fondo = min(estado.reactivo, max(estado.esperado, Decimal("0.00")))
    contado = max(estado.esperado, Decimal("0.00"))
    if retirar is not None:
        fondo = estado.reactivo
        contado = (fondo + _d(retirar)).quantize(_CENT)
    corte = cerrar_corte(
        session,
        contado=contado,
        creado_por=creado_por,
        reactivo_final=fondo,
        nota=nota,
        ahora=ahora,
    )
    return CorteAutomatico(corte=corte, estado=estado, pagos=pagos)
