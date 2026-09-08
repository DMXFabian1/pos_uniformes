"""Afluencia vs ventas por hora.

Junta lo que contó el DVR (`afluencia_hora`, sumando todas las cámaras) con las
operaciones de la Libreta (ventas y apartados) en la misma hora local, y saca
la conversión: de cada 100 que entran, cuántos compran.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from pos_uniformes.database.models import AfluenciaHora, LibretaVenta

TIPOS_QUE_CUENTAN_COMO_VENTA = ("venta", "apartado")


@dataclass(frozen=True)
class FilaAfluencia:
    hora: datetime  # inicio de hora, local naive
    entradas: int
    salidas: int
    pasan: int
    ventas: int

    @property
    def conversion(self) -> float | None:
        """Porcentaje ventas/entradas; None si no entró nadie."""
        if self.entradas <= 0:
            return None
        return round(100.0 * self.ventas / self.entradas, 1)


def _hora_local(momento: datetime) -> datetime:
    if momento.tzinfo is not None:
        momento = momento.astimezone().replace(tzinfo=None)
    return momento.replace(minute=0, second=0, microsecond=0)


def combinar(afluencia: list, ventas_por_hora: dict[datetime, int]) -> list[FilaAfluencia]:
    """Lógica pura: suma cámaras por hora y pega las ventas. Ordenado por hora."""
    por_hora: dict[datetime, dict[str, int]] = {}
    for fila in afluencia:
        hora = _hora_local(fila.hora)
        acc = por_hora.setdefault(hora, {"entradas": 0, "salidas": 0, "pasan": 0})
        acc["entradas"] += int(fila.entradas or 0)
        acc["salidas"] += int(fila.salidas or 0)
        acc["pasan"] += int(fila.pasan or 0)
    for hora in ventas_por_hora:
        por_hora.setdefault(hora, {"entradas": 0, "salidas": 0, "pasan": 0})
    return [
        FilaAfluencia(
            hora=hora,
            entradas=v["entradas"],
            salidas=v["salidas"],
            pasan=v["pasan"],
            ventas=int(ventas_por_hora.get(hora, 0)),
        )
        for hora, v in sorted(por_hora.items())
    ]


def ventas_por_hora(session, *, desde: datetime, hasta: datetime) -> dict[datetime, int]:
    stmt = select(LibretaVenta.created_at).where(
        LibretaVenta.created_at >= desde,
        LibretaVenta.created_at <= hasta,
        LibretaVenta.tipo.in_(TIPOS_QUE_CUENTAN_COMO_VENTA),
    )
    conteo: dict[datetime, int] = {}
    for (created_at,) in session.execute(stmt):
        hora = _hora_local(created_at)
        conteo[hora] = conteo.get(hora, 0) + 1
    return conteo


def listar_afluencia(session, *, desde: datetime, hasta: datetime) -> list[AfluenciaHora]:
    stmt = (
        select(AfluenciaHora)
        .where(AfluenciaHora.hora >= desde, AfluenciaHora.hora <= hasta)
        .order_by(AfluenciaHora.hora)
    )
    return list(session.scalars(stmt).all())


def resumen_afluencia(session, *, desde: datetime, hasta: datetime) -> list[FilaAfluencia]:
    return combinar(
        listar_afluencia(session, desde=desde, hasta=hasta),
        ventas_por_hora(session, desde=desde, hasta=hasta),
    )


def totales(filas: list[FilaAfluencia]) -> FilaAfluencia | None:
    if not filas:
        return None
    return FilaAfluencia(
        hora=filas[0].hora,
        entradas=sum(f.entradas for f in filas),
        salidas=sum(f.salidas for f in filas),
        pasan=sum(f.pasan for f in filas),
        ventas=sum(f.ventas for f in filas),
    )
