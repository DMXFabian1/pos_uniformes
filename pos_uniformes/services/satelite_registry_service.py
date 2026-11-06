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


def es_de_desarrollo() -> bool:
    """Esta máquina no es pantalla de la tienda (`POS_UNIFORMES_SATELITE_DESARROLLO=1`).

    La Mac de Daniel corre el satélite contra la base de producción. Latía
    como un kiosko más, y cada vez que la cerraba el bot de la tienda avisaba
    que se había apagado, y al abrirla que «ya volvió» (2026-10-11). Sin
    latido, para el vigilante nunca estuvo prendida hoy y no hay noticia.
    """
    import os

    valor = os.getenv("POS_UNIFORMES_SATELITE_DESARROLLO")
    if valor is None:
        try:
            from pos_uniformes.utils.config import load_runtime_env_overrides

            valor = load_runtime_env_overrides().get("POS_UNIFORMES_SATELITE_DESARROLLO", "")
        except Exception:  # noqa: BLE001 — sin config, es una pantalla normal
            valor = ""
    return (valor or "").strip().lower() in {"1", "si", "sí", "true"}


def registrar(
    session: Session,
    identificador: str,
    nombre: str,
    *,
    ahora: datetime | None = None,
    imprime: str | None = None,
) -> Satelite:
    """Alta o actualización (upsert) del satélite + heartbeat. No hace commit.

    De paso publica qué sabe imprimir esta PC (`imprime`; por defecto lo que
    diga «Impresoras de esta PC»), para que otra la pueda elegir como destino.

    En una máquina de desarrollo no escribe nada: devuelve el registro que
    hubiera (o uno sin guardar) y no late."""
    momento = ahora or _ahora()
    sat = session.scalar(
        select(Satelite).where(Satelite.identificador == identificador)
    )
    if es_de_desarrollo():
        return sat or Satelite(identificador=identificador[:40], nombre=(nombre or "satelite")[:60])
    imprime = _lo_que_imprime_esta_pc() if imprime is None else imprime
    version = _mi_version()
    if sat is None:
        sat = Satelite(
            identificador=identificador[:40],
            nombre=(nombre or "satelite")[:60],
            ultimo_visto=momento,
            imprime=imprime,
            version=version,
        )
        session.add(sat)
    else:
        sat.imprime = imprime
        if version:
            sat.version = version
        if nombre and sat.nombre != nombre[:60]:
            _llevar_el_buzon(session, sat.nombre, nombre[:60])
            sat.nombre = nombre[:60]
        sat.ultimo_visto = momento
    session.flush()
    return sat


def _mi_version() -> str | None:
    """«2026.11.06+6ba73b01»: lo mismo que se publica para los kioskos."""
    try:
        from pos_uniformes.utils.app_metadata import sello_del_codigo

        return (sello_del_codigo() or "")[:40] or None
    except Exception:  # noqa: BLE001 — sin versión no se deja de latir
        return None


def version_legible(sello: str | None) -> str:
    """«6 nov · 6ba73b01» a partir de lo que publica cada PC; "" si no ha dicho."""
    import re

    m = re.match(r"^(\d{4})\.(\d{2})\.(\d{2})\+([0-9a-fA-F]{6,40})$", (sello or "").strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        return (sello or "").strip()
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{int(m.group(3))} {meses[int(m.group(2)) - 1]} · {m.group(4)}"


def _lo_que_imprime_esta_pc() -> str:
    try:
        from pos_uniformes.services.print_routing_cache_service import impresoras_de_esta_pc

        return ",".join(impresoras_de_esta_pc())[:120]
    except Exception:  # noqa: BLE001
        return ""


def otras_impresoras(session: Session, tipo: str, mi_identificador: str, *, ahora: datetime | None = None) -> list[dict]:
    """Las OTRAS PCs que imprimen `tipo` ("TICKET"…): [{identificador, nombre, online}].

    Primero las encendidas. Una apagada también sale (para que se vea que
    existe y por qué no se puede elegir), salvo que lleve más de una semana
    sin aparecer. Si la base aún no tiene la columna, no hay ninguna."""
    momento = ahora or _ahora()
    tipo = str(tipo).strip().upper()
    try:
        with session.begin_nested():
            sats = listar(session)
    except Exception:  # noqa: BLE001 — base sin migrar
        return []
    salida = []
    for sat in sats:
        if sat.identificador == mi_identificador:
            continue
        if tipo not in [t.strip().upper() for t in (sat.imprime or "").split(",")]:
            continue
        visto = sat.ultimo_visto
        if visto is None:
            continue
        if visto.tzinfo is None:
            visto = visto.replace(tzinfo=timezone.utc)
        if momento - visto > timedelta(days=7):
            continue
        salida.append({
            "identificador": sat.identificador,
            "nombre": sat.nombre,
            "online": esta_online(sat, ahora=momento),
        })
    salida.sort(key=lambda d: (not d["online"], d["nombre"].lower()))
    return salida


def _llevar_el_buzon(session: Session, viejo: str, nuevo: str) -> None:
    """La PC cambió de nombre: sus mensajes del buzón se van con ella.

    Aquí y no en cada pantalla que renombra: así da igual si se cambió desde
    el buzón, desde el menú admin o sin conexión — al siguiente latido queda
    todo alineado (2026-10-15). En su propio savepoint: una base sin la tabla
    del buzón no tumba el latido."""
    try:
        from sqlalchemy import update

        from pos_uniformes.database.models import BuzonMensaje

        with session.begin_nested():
            session.execute(update(BuzonMensaje).where(BuzonMensaje.de == viejo).values(de=nuevo))
            session.execute(update(BuzonMensaje).where(BuzonMensaje.para == viejo).values(para=nuevo))
    except Exception:  # noqa: BLE001
        pass


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
                "version": sat.version,
            }
        )
    return salida


def atrasadas(filas: list[dict], *, publicada: str | None) -> list[dict]:
    """Las PCs que ya dijeron su versión y no es la publicada (para avisar)."""
    publicada = (publicada or "").strip()
    if not publicada:
        return []
    return [f for f in filas if (f.get("version") or "").strip() and f["version"].strip() != publicada]


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
