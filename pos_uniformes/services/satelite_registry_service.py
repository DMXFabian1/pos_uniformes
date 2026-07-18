"""Registro y presencia de satélites (tabla `satelite`).

Cada satélite se autoregistra y late (`registrar`) cada minuto; el punto de
control (Mac / satélite-servidor / PWA) lista quiénes están encendidos con
`listar` + `esta_online`.

Convención del repo: estas funciones mutan la Session pero NO hacen commit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Satelite

# Margen para considerar "encendido": si latió hace más de esto, se da por
# apagado. 150 s = 2.5 min → tolera un heartbeat perdido (late cada 60 s).
UMBRAL_ONLINE_SEG = 150


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def registrar(
    session: Session,
    identificador: str,
    nombre: str,
    *,
    ahora: datetime | None = None,
) -> Satelite:
    """Alta o actualización (upsert) del satélite + heartbeat. No hace commit."""
    momento = ahora or _ahora()
    sat = session.scalar(
        select(Satelite).where(Satelite.identificador == identificador)
    )
    if sat is None:
        sat = Satelite(
            identificador=identificador[:40],
            nombre=(nombre or "satelite")[:60],
            ultimo_visto=momento,
        )
        session.add(sat)
    else:
        if nombre:
            sat.nombre = nombre[:60]
        sat.ultimo_visto = momento
    session.flush()
    return sat


def listar(session: Session) -> list[Satelite]:
    """Todos los satélites conocidos, ordenados por nombre."""
    stmt = select(Satelite).order_by(Satelite.nombre.asc(), Satelite.id.asc())
    return list(session.scalars(stmt).all())


def esta_online(
    sat: Satelite,
    *,
    umbral_seg: int = UMBRAL_ONLINE_SEG,
    ahora: datetime | None = None,
) -> bool:
    """True si el satélite latió dentro del margen (está encendido)."""
    if sat.ultimo_visto is None:
        return False
    momento = ahora or _ahora()
    visto = sat.ultimo_visto
    if visto.tzinfo is None:  # por si el motor devolvió naive (SQLite)
        visto = visto.replace(tzinfo=timezone.utc)
    return momento - visto <= timedelta(seconds=umbral_seg)


def listar_con_estado(
    session: Session,
    *,
    umbral_seg: int = UMBRAL_ONLINE_SEG,
    ahora: datetime | None = None,
) -> list[dict]:
    """Lista lista para UI: [{identificador, nombre, online, ultimo_visto}]."""
    momento = ahora or _ahora()
    salida: list[dict] = []
    for sat in listar(session):
        salida.append(
            {
                "identificador": sat.identificador,
                "nombre": sat.nombre,
                "online": esta_online(sat, umbral_seg=umbral_seg, ahora=momento),
                "ultimo_visto": sat.ultimo_visto,
            }
        )
    return salida
