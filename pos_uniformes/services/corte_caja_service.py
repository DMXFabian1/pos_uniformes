"""Corte de caja por periodo con reactivo (fondo). Distinto de caja_service.py
(sesiones y movimientos de caja del POS principal).

Reglas (Daniel, 2026-09-08):
- El cajón siempre tiene un fondo ("reactivo"). Efectivo esperado =
  reactivo + ventas en efectivo + abonos en efectivo del periodo
  - pagos a empleadas - otros retiros.
- El corte es por MOMENTO: cubre desde el corte anterior hasta ahora. Lo que
  se venda después queda para el siguiente corte, aunque sea el mismo día.
- Al cerrar se captura lo contado y cuánto se queda como reactivo (por
  defecto el mismo fondo). Solo Daniel (VEND-1) y su papá (ENC-1) lo hacen.

La lógica de sumas es pura; lo que lleva `session` toca la base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

_CENT = Decimal("0.01")
_SIN_CORTE_DIAS = 90  # sin corte previo: periodo abierto hacia atrás


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
    otros_retiros: Decimal = Decimal("0.00")

    @property
    def esperado(self) -> Decimal:
        return (self.reactivo + self.resumen.efectivo - self.pagos - self.otros_retiros).quantize(_CENT)


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


def estado_caja(session, ahora: datetime | None = None, otros_retiros=Decimal("0.00")) -> EstadoCaja:
    """Lo que debería haber en el cajón ahora mismo."""
    ahora = ahora or datetime.now().astimezone()
    desde = inicio_periodo(session)
    params = cargar_parametros(session)
    rows = operaciones_del_periodo(session, desde, ahora)
    return EstadoCaja(
        desde=desde,
        hasta=ahora,
        reactivo=params.reactivo_actual,
        resumen=resumir_periodo(rows),
        pagos=pagos_del_periodo(session, desde, ahora),
        otros_retiros=_d(otros_retiros),
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
        otros_retiros=_d(otros_retiros),
        reactivo_final=reactivo_final,
    )
    session.add(corte)
    guardar_parametros(session, reactivo_actual=reactivo_final)  # hace commit
    return corte


def _etiqueta_periodo(desde: datetime | None, hasta: datetime) -> str:
    h = (hasta.astimezone() if hasta.tzinfo else hasta).strftime("%d/%m %H:%M")
    if desde is None:
        return f"hasta {h}"
    d = (desde.astimezone() if desde.tzinfo else desde).strftime("%d/%m %H:%M")
    return f"{d} → {h}"
