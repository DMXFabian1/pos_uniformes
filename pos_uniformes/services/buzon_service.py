"""Buzón entre las PCs: mandar un texto de una pantalla a otra.

Existe para pasar comandos y respuestas entre la Mac, la PC principal y los
kioskos sin WhatsApp (Daniel, 2026-10-15). Se escribe en una PC, se lee y se
copia en otra. Va por la base porque todas las PCs ya hablan con ella, y porque
así Claude puede dejar un script desde la Mac y leer lo que le contesten.

No ejecuta nada: solo lleva texto. Quien lo recibe decide si lo copia y lo
corre (Daniel escogió eso sobre un botón «Ejecutar»).

Convención del repo: estas funciones mutan la Session pero NO hacen commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import BuzonMensaje

#: Lo que se ve en la ventana. Lo viejo sigue en la base, solo no estorba.
LIMITE = 60
#: Un mensaje es para leer y copiar, no para guardar un archivo entero.
MAXIMO_CARACTERES = 20_000


class NoSePuede(Exception):
    """Algo impide mandar el mensaje, dicho para enseñarlo en pantalla."""


def mi_nombre() -> str:
    """Cómo se firma esta PC: el nombre que tiene en el menú admin."""
    try:
        from pos_uniformes.services.satellite_identity_service import get_satellite_name

        nombre = (get_satellite_name() or "").strip()
        if nombre:
            return nombre[:60]
    except Exception:  # noqa: BLE001 — sin identidad, el nombre de la máquina
        pass
    import platform

    return (platform.node() or "PC")[:60]


def enviar(session: Session, texto: str, *, de: str, para: str | None = None) -> BuzonMensaje:
    """Deja un mensaje. `para` vacío = a todas las PCs."""
    # Lo que pegue Qt como separador de línea, como salto normal.
    texto = (texto or "").replace("\u2028", "\n").replace("\u2029", "\n").rstrip()
    if not texto.strip():
        raise NoSePuede("El mensaje está vacío.")
    if len(texto) > MAXIMO_CARACTERES:
        raise NoSePuede(
            f"Es muy largo ({len(texto):,} caracteres). El máximo es {MAXIMO_CARACTERES:,}."
        )
    mensaje = BuzonMensaje(
        de=(de or "PC").strip()[:60],
        para=((para or "").strip()[:60] or None),
        texto=texto,
    )
    session.add(mensaje)
    session.flush()
    return mensaje


def recientes(session: Session, *, yo: str | None = None, limite: int = LIMITE) -> list[BuzonMensaje]:
    """Los últimos mensajes que le tocan a `yo`, del más viejo al más nuevo.

    Le tocan los que son para todas, los que son para ella y los que ella
    mandó. Sin `yo`, todos."""
    stmt = select(BuzonMensaje)
    if yo:
        stmt = stmt.where(
            or_(BuzonMensaje.para.is_(None), BuzonMensaje.para == yo, BuzonMensaje.de == yo)
        )
    filas = list(session.scalars(stmt.order_by(BuzonMensaje.id.desc()).limit(limite)).all())
    filas.reverse()
    return filas


def destinos(session: Session, *, yo: str | None = None) -> list[str]:
    """A quién se le puede escribir: las PCs que se conocen, menos esta."""
    from pos_uniformes.database.models import Satelite

    nombres = {
        str(n).strip()
        for n in session.scalars(select(Satelite.nombre)).all()
        if n and str(n).strip()
    }
    # También quien ya escribió o a quien ya se le escribió (la PC principal,
    # la Mac, Claude): un chat que solo tiene lo que mandé yo también existe.
    nombres |= {
        str(n).strip() for n in session.scalars(select(BuzonMensaje.de).distinct()).all() if n
    }
    nombres |= {
        str(n).strip() for n in session.scalars(select(BuzonMensaje.para).distinct()).all() if n
    }
    nombres.discard(yo or "")
    return sorted(nombres, key=str.lower)


# ── Chats, como en WhatsApp ─────────────────────────────────────────────────

#: Clave del chat de grupo (los mensajes con `para` vacío).
GRUPO = "*"
NOMBRE_GRUPO = "Todas las PCs"


@dataclass(frozen=True)
class Chat:
    clave: str                       # GRUPO o el nombre de la otra PC
    nombre: str
    ultimo_texto: str = ""
    ultimo_de: str = ""
    ultimo_at: datetime | None = None
    ultimo_id: int = 0
    no_leidos: int = 0
    en_linea: bool | None = None     # None = no se sabe (Claude, la PC principal)
    visto: datetime | None = None

    @property
    def es_grupo(self) -> bool:
        return self.clave == GRUPO


def _de_la_conversacion(yo: str, con: str):
    if con == GRUPO:
        return BuzonMensaje.para.is_(None)
    return or_(
        and_(BuzonMensaje.de == yo, BuzonMensaje.para == con),
        and_(BuzonMensaje.de == con, BuzonMensaje.para == yo),
    )


def conversacion(session: Session, *, yo: str, con: str, limite: int = LIMITE) -> list[BuzonMensaje]:
    """Los mensajes entre `yo` y `con` (o los del grupo), del más viejo al más nuevo."""
    filas = list(session.scalars(
        select(BuzonMensaje).where(_de_la_conversacion(yo, con))
        .order_by(BuzonMensaje.id.desc()).limit(limite)
    ).all())
    filas.reverse()
    return filas


def _presencia(session: Session) -> dict[str, tuple[bool, datetime | None]]:
    try:
        from pos_uniformes.services.satelite_registry_service import listar_con_estado

        return {
            str(s["nombre"]).strip(): (bool(s["online"]), s.get("ultimo_visto"))
            for s in listar_con_estado(session)
        }
    except Exception:  # noqa: BLE001 — sin registro de pantallas, sin puntito
        return {}


def chats(session: Session, *, yo: str, leidos: dict[str, int] | None = None) -> list[Chat]:
    """La lista de la izquierda: el grupo arriba, luego por el mensaje más reciente.

    `leidos` = {clave: último id visto en esta PC}; lo de después cuenta como
    no leído, menos lo que mandó ella misma."""
    leidos = leidos or {}
    presencia = _presencia(session)
    claves = [GRUPO, *destinos(session, yo=yo)]
    salida: list[Chat] = []
    for clave in claves:
        filtro = _de_la_conversacion(yo, clave)
        ultimo = session.scalars(
            select(BuzonMensaje).where(filtro).order_by(BuzonMensaje.id.desc()).limit(1)
        ).first()
        visto_hasta = int(leidos.get(clave, 0))
        no_leidos = len(session.scalars(
            select(BuzonMensaje.id).where(
                filtro, BuzonMensaje.id > visto_hasta, BuzonMensaje.de != yo
            )
        ).all())
        en_linea, visto = presencia.get(clave, (None, None))
        salida.append(Chat(
            clave=clave,
            nombre=NOMBRE_GRUPO if clave == GRUPO else clave,
            ultimo_texto=(ultimo.texto if ultimo else ""),
            ultimo_de=(ultimo.de if ultimo else ""),
            ultimo_at=(ultimo.created_at if ultimo else None),
            ultimo_id=(ultimo.id if ultimo else 0),
            no_leidos=no_leidos,
            en_linea=en_linea,
            visto=visto,
        ))
    grupo, resto = salida[0], salida[1:]
    resto.sort(key=lambda c: (-(c.ultimo_id or 0), c.nombre.lower()))
    return [grupo, *resto]


# ── Lo leído, por PC ─────────────────────────────────────────────────────────
# Vive en un archivo de ESTA PC y no en la base: «leído» es de quien mira la
# pantalla, y así no hace falta otra columna ni otra migración.

_LEIDOS = "buzon_leidos.json"


def _ruta_leidos():
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / _LEIDOS


def leidos() -> dict[str, int]:
    import json

    try:
        datos = json.loads(_ruta_leidos().read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in datos.items()}
    except Exception:  # noqa: BLE001 — sin archivo: nada leído todavía
        return {}


def marcar_leido(clave: str, hasta_id: int) -> None:
    import json

    datos = leidos()
    if hasta_id <= datos.get(clave, 0):
        return
    datos[clave] = int(hasta_id)
    try:
        ruta = _ruta_leidos()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    except Exception:  # noqa: BLE001 — no recordar lo leído no vale un error
        pass


def parece_codigo(texto: str) -> bool:
    """Un comando o una salida de consola: va en letra de ancho fijo."""
    return "\n" in texto.strip() or any(c in texto for c in "$\\|{}")


def renombrar(session: Session, viejo: str, nuevo: str) -> int:
    """Una PC cambia de nombre: su historial se va con ella.

    Los mensajes guardan el nombre, así que sin esto «DESKTOP-AT4V4QO» y
    «Entrada» serían dos chats distintos. Devuelve cuántos mensajes tocó."""
    from sqlalchemy import update

    viejo, nuevo = (viejo or "").strip(), (nuevo or "").strip()[:60]
    if not viejo or not nuevo or viejo == nuevo:
        return 0
    a = session.execute(update(BuzonMensaje).where(BuzonMensaje.de == viejo).values(de=nuevo))
    b = session.execute(update(BuzonMensaje).where(BuzonMensaje.para == viejo).values(para=nuevo))
    try:
        from pos_uniformes.database.models import Satelite

        session.execute(update(Satelite).where(Satelite.nombre == viejo).values(nombre=nuevo))
    except Exception:  # noqa: BLE001 — sin registro de pantallas, solo el buzón
        pass
    session.flush()
    return int(a.rowcount or 0) + int(b.rowcount or 0)
