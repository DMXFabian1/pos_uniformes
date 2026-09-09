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


def periodo_del_corte(session, corte) -> tuple[datetime | None, datetime]:
    """(desde, hasta) del corte; reconstruye el de los cortes viejos."""
    from pos_uniformes.database.models import LibretaCorte

    hasta = corte.hasta or corte.created_at
    desde = corte.desde
    if desde is None and corte.hasta is None:
        anterior = session.scalars(
            select(LibretaCorte)
            .where(LibretaCorte.created_at < corte.created_at)
            .order_by(LibretaCorte.created_at.desc())
            .limit(1)
        ).first()
        if anterior is not None:
            desde = anterior.hasta or anterior.created_at
    return desde, hasta


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
    if corte.hasta is None:
        return None
    return (_d(corte.monto_final) - _d(corte.monto_esperado)).quantize(_CENT)


def retirado(corte) -> Decimal:
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
