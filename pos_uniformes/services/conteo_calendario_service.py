"""Calendario de conteos periódicos por escuela (Fase 0, sin UI).

Motor del recordatorio: para cada escuela con productos, calcula cuándo toca el
próximo conteo (último conteo + días de vigencia) y si ya está vencida. Se apoya
en lo que ya existe: `config_conteo_escuela.dias_vigencia` y el `ultimo_conteo`
(máxima fecha de conteo) que devuelve `obtener_estado_conteo_escuela`.

El ciclo se reinicia solo: al registrar un conteo, `ultimo_conteo` avanza y la
próxima fecha se recorre sola.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Escuela
from pos_uniformes.services.conteo_service import obtener_estado_conteo_escuela


@dataclass(frozen=True)
class EstadoCalendarioConteo:
    escuela_id: int
    escuela_nombre: str
    dias_vigencia: int
    total_variantes: int
    ultimo_conteo: datetime | None       # última fecha de conteo (None = nunca)
    proxima_fecha: date | None           # día en que vuelve a tocar (None si nunca contada)
    vencida: bool                        # True = ya toca contar
    dias_para_vencer: int | None         # >0 faltan; <=0 vencida; None si nunca contada
    nunca_contada: bool


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _estado_desde(estado, ahora: datetime) -> EstadoCalendarioConteo:
    base = dict(
        escuela_id=estado.escuela_id,
        escuela_nombre=estado.escuela_nombre,
        dias_vigencia=estado.dias_vigencia,
        total_variantes=estado.total_variantes,
    )
    ultimo = estado.ultimo_conteo
    if ultimo is None:
        # Nunca se ha contado: si tiene piezas, ya toca.
        return EstadoCalendarioConteo(
            **base,
            ultimo_conteo=None,
            proxima_fecha=None,
            vencida=estado.total_variantes > 0,
            dias_para_vencer=None,
            nunca_contada=True,
        )

    # Normalizar a aware para restar contra `ahora` (UTC).
    if ultimo.tzinfo is None:
        ultimo = ultimo.replace(tzinfo=timezone.utc)
    proxima = ultimo + timedelta(days=estado.dias_vigencia)
    return EstadoCalendarioConteo(
        **base,
        ultimo_conteo=ultimo,
        proxima_fecha=proxima.date(),
        vencida=ahora >= proxima,
        dias_para_vencer=(proxima - ahora).days,
        nunca_contada=False,
    )


def obtener_calendario_conteo(
    session: Session,
    *,
    ahora: datetime | None = None,
    solo_con_productos: bool = True,
) -> list[EstadoCalendarioConteo]:
    """Estado de conteo de todas las escuelas activas, para el calendario.

    Ordenado por urgencia: primero las que llevan más tiempo vencidas / nunca
    contadas, luego las que están por vencer. `ahora` es inyectable para tests.
    """
    ahora = ahora or _ahora_utc()
    escuelas = session.scalars(
        select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)
    ).all()

    resultado: list[EstadoCalendarioConteo] = []
    for escuela in escuelas:
        estado = obtener_estado_conteo_escuela(session, escuela.id)
        if solo_con_productos and estado.total_variantes == 0:
            continue
        resultado.append(_estado_desde(estado, ahora))

    # Orden: vencidas/nunca contadas primero (más urgente = menor dias_para_vencer);
    # las nunca contadas van al frente. Empate por nombre.
    def _clave(e: EstadoCalendarioConteo):
        if e.nunca_contada:
            urgencia = float("-inf")
        else:
            urgencia = e.dias_para_vencer if e.dias_para_vencer is not None else 0
        return (0 if e.vencida else 1, urgencia, e.escuela_nombre)

    resultado.sort(key=_clave)
    return resultado


def escuelas_con_conteo_vencido(
    session: Session, *, ahora: datetime | None = None
) -> list[EstadoCalendarioConteo]:
    """Solo las escuelas que ya requieren conteo (vencidas o nunca contadas)."""
    return [e for e in obtener_calendario_conteo(session, ahora=ahora) if e.vencida]


def agrupar_calendario_por_dia(
    estados: list[EstadoCalendarioConteo], anio: int, mes: int
) -> dict[int, list[EstadoCalendarioConteo]]:
    """Agrupa por día-del-mes las escuelas cuya próxima fecha cae en (anio, mes).

    Para pintar el calendario visual. Las escuelas sin próxima fecha (nunca
    contadas) no entran aquí; se muestran aparte como vencidas.
    """
    por_dia: dict[int, list[EstadoCalendarioConteo]] = {}
    for estado in estados:
        p = estado.proxima_fecha
        if p is not None and p.year == anio and p.month == mes:
            por_dia.setdefault(p.day, []).append(estado)
    return por_dia
