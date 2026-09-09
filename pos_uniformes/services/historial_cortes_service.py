"""Historial de cortes (solo dueño): listar por mes y reconstruir el ticket.

Un corte guardado (`libreta_corte`) trae su periodo (`desde`/`hasta`), así
que las operaciones, los pagos y los retiros de ese periodo se vuelven a
consultar y el ticket sale igual al original. Los cortes viejos (antes del
corte por periodo, 2026-09-08) no tienen `desde`/`hasta`: se toma el corte
anterior como inicio y `created_at` como fin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

_CENT = Decimal("0.01")
FORMATO_DUENO = "dueno"
FORMATO_ENCARGADO = "encargado"
_QUIEN_ENCARGADO = {"ENC-1", "AUTO"}


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENT)


def listar_cortes_mes(session, desde: date, hasta: date) -> list:
    """Cortes con fecha en [desde, hasta], el más reciente primero."""
    from pos_uniformes.database.models import LibretaCorte

    stmt = (
        select(LibretaCorte)
        .where(LibretaCorte.fecha >= desde, LibretaCorte.fecha <= hasta)
        .order_by(LibretaCorte.fecha.desc(), LibretaCorte.id.desc())
    )
    return list(session.scalars(stmt).all())


def es_legacy(corte) -> bool:
    """Corte de antes del corte por periodo (2026-09-08): era el total DEL DÍA
    ("HOY"), sin reactivo ni esperado. La migración le puso `hasta = created_at`
    pero no tiene `desde`."""
    return getattr(corte, "desde", None) is None


def periodo_del_corte(session, corte) -> tuple[datetime | None, datetime]:
    """(desde, hasta) del corte. Los viejos cubren su día: de las 00:00 a la
    hora en que se hicieron (nunca 90 días atrás ni "desde el anterior")."""
    hasta = corte.hasta or corte.created_at
    if not es_legacy(corte):
        return corte.desde, hasta
    local = hasta.astimezone() if getattr(hasta, "tzinfo", None) else hasta
    inicio_dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio_dia, hasta


@dataclass(frozen=True)
class DatosReimpresion:
    por_empleada: list
    pagos: list
    retiros: list
    venta_efectivo: Decimal


def datos_para_reimprimir(session, corte) -> DatosReimpresion:
    """Vuelve a consultar lo del periodo del corte para armar el ticket."""
    from pos_uniformes.services.corte_caja_service import (
        operaciones_del_periodo,
        pagos_registrados_del_periodo,
        resumir_periodo,
    )
    from pos_uniformes.services.libreta_service import resumir_por_empleada

    desde, hasta = periodo_del_corte(session, corte)
    rows = operaciones_del_periodo(session, desde, hasta)
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        retiros = retiros_del_periodo(session, desde, hasta)
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        retiros = []
    return DatosReimpresion(
        por_empleada=resumir_por_empleada(rows),
        pagos=pagos_registrados_del_periodo(session, desde, hasta),
        retiros=retiros,
        venta_efectivo=resumir_periodo(rows).efectivo,
    )


def formato_original(corte) -> str:
    """El encargado y la tarea automática imprimen el ticket simple."""
    return FORMATO_ENCARGADO if str(corte.creado_por or "").upper() in _QUIEN_ENCARGADO else FORMATO_DUENO


def diferencia_corte(corte) -> Decimal | None:
    """Sobró (+) / faltó (−) contra lo esperado. None en cortes viejos sin esperado."""
    if corte.hasta is None or es_legacy(corte):
        return None  # los viejos no guardaron esperado
    return (_d(corte.monto_final) - _d(corte.monto_esperado)).quantize(_CENT)


def es_del_dueno(corte) -> bool:
    return str(corte.creado_por or "").upper() == "VEND-1"


def retirado(corte) -> Decimal:
    if es_legacy(corte):
        return Decimal("0.00")  # eran totales del día, no retiros
    return (_d(corte.monto_final) - _d(corte.reactivo_final)).quantize(_CENT)


@dataclass(frozen=True)
class TotalesCortes:
    cortes: int
    en_caja: Decimal
    retirado: Decimal
    pagos: Decimal
    otros_retiros: Decimal


def totales_cortes(cortes: list) -> TotalesCortes:
    return TotalesCortes(
        cortes=len(cortes),
        en_caja=sum((_d(c.monto_final) for c in cortes), Decimal("0.00")),
        retirado=sum((retirado(c) for c in cortes), Decimal("0.00")),
        pagos=sum((_d(c.retiros_pagos) for c in cortes), Decimal("0.00")),
        otros_retiros=sum((_d(c.otros_retiros) for c in cortes), Decimal("0.00")),
    )
