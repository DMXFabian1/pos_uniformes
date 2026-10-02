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


# ── Limpieza del registro ────────────────────────────────────────────────────

#: Una pantalla que lleva más de un mes sin latir ya no es una pantalla de la
#: tienda: es una Mac donde se probó el kiosko una tarde, o un equipo retirado.
#: Un mes es amplio a propósito — un kiosko descompuesto que vuelve de
#: reparación en tres semanas no debería desaparecer de la lista mientras tanto.
DIAS_PARA_RETIRAR = 30


def listar_viejos(
    session: Session, *, dias: int = DIAS_PARA_RETIRAR, ahora: datetime | None = None
) -> list[Satelite]:
    """Los satélites que no laten desde hace `dias`. Los que nunca latieron van también."""
    corte = (ahora or _ahora()) - timedelta(days=dias)
    viejos = []
    for sat in listar(session):
        visto = sat.ultimo_visto
        if visto is None:
            viejos.append(sat)
            continue
        if visto.tzinfo is None:  # por si el motor devolvió naive (SQLite)
            visto = visto.replace(tzinfo=timezone.utc)
        if visto < corte:
            viejos.append(sat)
    return viejos


def retirar_viejos(
    session: Session, *, dias: int = DIAS_PARA_RETIRAR, ahora: datetime | None = None
) -> list[str]:
    """Borra los registros viejos. Devuelve los nombres que quitó. No hace commit.

    **Borrar aquí es seguro porque el registro se cura solo**: cualquier pantalla
    que siga viva se vuelve a registrar sola en su siguiente latido, que es al
    minuto. Lo único que se pierde es el nombre que se le haya puesto a mano, y
    solo de una pantalla que lleva un mes sin aparecer.

    Importa tenerlo limpio porque un aviso espera a que **todas** las pantallas
    lo acusen: una fantasma en la lista es una que nunca va a contestar. (Eso ya
    está cubierto aparte — `anuncio_service` solo cuenta las vistas en 7 días —
    pero una lista con equipos que no existen tampoco se puede leer de un
    vistazo, y leerla de un vistazo es para lo que está.)
    """
    viejos = listar_viejos(session, dias=dias, ahora=ahora)
    nombres = [s.nombre or s.identificador for s in viejos]
    for sat in viejos:
        session.delete(sat)
    if viejos:
        session.flush()
    return nombres
