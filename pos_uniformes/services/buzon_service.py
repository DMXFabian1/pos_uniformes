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

from pos_uniformes.database.models import BuzonAdjunto, BuzonLeido, BuzonMensaje

#: Lo que se ve en la ventana. Lo viejo sigue en la base, solo no estorba.
LIMITE = 60
#: Un mensaje es para leer y copiar, no para guardar un archivo entero.
MAXIMO_CARACTERES = 20_000
#: Una captura de pantalla cabe de sobra; un video o un respaldo, no.
MAXIMO_IMAGEN = 3_000_000

#: Lo que contesta a un comando dice cómo le fue (`BuzonMensaje.estado`).
RECIBIDO, TERMINO_BIEN, FALLO = "recibido", "ok", "error"
#: Lo que se enseña de un mensaje que ya no tiene texto.
TEXTO_BORRADO = "Se borró este mensaje"
TEXTO_IMAGEN = "📷 Imagen"


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


def enviar(
    session: Session, texto: str, *, de: str, para: str | None = None,
    responde_a: int | None = None, estado: str | None = None, imagen: bytes | None = None,
) -> BuzonMensaje:
    """Deja un mensaje. `para` vacío = a todas las PCs.

    `responde_a` lo pega al mensaje que contesta; `estado` dice cómo le fue a
    un comando; `imagen` son los bytes de una captura (PNG o JPEG)."""
    # Lo que pegue Qt como separador de línea, como salto normal.
    texto = (texto or "").replace("\u2028", "\n").replace("\u2029", "\n").rstrip()
    if not texto.strip() and not imagen:
        raise NoSePuede("El mensaje está vacío.")
    if imagen and len(imagen) > MAXIMO_IMAGEN:
        raise NoSePuede(
            f"La imagen pesa mucho ({len(imagen) / 1_000_000:.1f} MB). El máximo es "
            f"{MAXIMO_IMAGEN / 1_000_000:.0f} MB."
        )
    if len(texto) > MAXIMO_CARACTERES:
        raise NoSePuede(
            f"Es muy largo ({len(texto):,} caracteres). El máximo es {MAXIMO_CARACTERES:,}."
        )
    mensaje = BuzonMensaje(
        de=(de or "PC").strip()[:60],
        para=((para or "").strip()[:60] or None),
        texto=texto,
        responde_a=responde_a,
        estado=estado,
        adjunto=bool(imagen),
    )
    session.add(mensaje)
    session.flush()
    if imagen:
        session.add(BuzonAdjunto(mensaje_id=mensaje.id, datos=imagen))
        session.flush()
    return mensaje


def imagen_de(session: Session, mensaje_id: int) -> bytes | None:
    return session.scalars(
        select(BuzonAdjunto.datos).where(BuzonAdjunto.mensaje_id == mensaje_id)
    ).first()


def borrar(session: Session, mensaje_id: int, *, de: str) -> bool:
    """Borra un mensaje PROPIO. El renglón queda —el chat no brinca y lo que
    le contestaron sigue teniendo de qué colgarse— pero sin texto ni imagen."""
    from sqlalchemy import delete, func

    mensaje = session.get(BuzonMensaje, mensaje_id)
    if mensaje is None or mensaje.borrado_at is not None:
        return False
    if mensaje.de != de:
        raise NoSePuede("Solo se puede borrar lo que mandó esta PC.")
    session.execute(delete(BuzonAdjunto).where(BuzonAdjunto.mensaje_id == mensaje_id))
    mensaje.texto = ""
    mensaje.adjunto = False
    mensaje.borrado_at = func.now()
    session.flush()
    return True


def vista_previa(mensaje: BuzonMensaje | None) -> str:
    """Lo que se lee de un mensaje en un renglón: en la lista y en las citas."""
    if mensaje is None:
        return ""
    if mensaje.borrado_at is not None:
        return TEXTO_BORRADO
    texto = " ".join((mensaje.texto or "").split())
    if mensaje.adjunto:
        return f"{TEXTO_IMAGEN} {texto}".strip()
    return texto


def resumenes(session: Session, ids) -> dict[int, tuple[str, str]]:
    """{id: (de, vista previa)} de los mensajes citados que no están en pantalla."""
    ids = [int(i) for i in ids if i]
    if not ids:
        return {}
    filas = session.scalars(select(BuzonMensaje).where(BuzonMensaje.id.in_(ids))).all()
    return {m.id: (m.de, vista_previa(m)) for m in filas}


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


def conversacion(
    session: Session, *, yo: str, con: str, limite: int = LIMITE, buscar: str | None = None,
) -> list[BuzonMensaje]:
    """Los mensajes entre `yo` y `con` (o los del grupo), del más viejo al más nuevo.

    Con `buscar`, solo los que traen ese texto (sin distinguir mayúsculas), de
    toda la historia del chat y no solo de lo que está en pantalla."""
    stmt = select(BuzonMensaje).where(_de_la_conversacion(yo, con))
    buscar = (buscar or "").strip()
    if buscar:
        patron = buscar.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            BuzonMensaje.borrado_at.is_(None),
            BuzonMensaje.estado.is_distinct_from(RECIBIDO),
            BuzonMensaje.texto.ilike(f"%{patron}%", escape="\\"),
        )
    filas = list(session.scalars(stmt.order_by(BuzonMensaje.id.desc()).limit(limite)).all())
    filas.reverse()
    return filas


def hay_anteriores(session: Session, *, yo: str, con: str, antes_de: int) -> bool:
    """¿Queda historia más vieja que `antes_de` en este chat?"""
    return session.scalars(
        select(BuzonMensaje.id).where(_de_la_conversacion(yo, con), BuzonMensaje.id < antes_de).limit(1)
    ).first() is not None


# ── Las palomitas: hasta dónde leyó cada quien ───────────────────────────────

def anotar_leido(session: Session, *, lector: str, chat: str, hasta_id: int) -> None:
    """Esta PC ya vio el chat `chat` hasta `hasta_id`. Nunca retrocede."""
    fila = session.get(BuzonLeido, (lector, chat))
    if fila is None:
        session.add(BuzonLeido(lector=lector, chat=chat, hasta_id=int(hasta_id)))
    elif int(hasta_id) > int(fila.hasta_id or 0):
        fila.hasta_id = int(hasta_id)
    session.flush()


def leido_por_otros(session: Session, *, yo: str, con: str) -> dict[str, int]:
    """{quién: hasta qué id leyó} de lo que YO mandé a este chat.

    En un chat privado es la otra PC; en el grupo, cada una de las demás."""
    if con == GRUPO:
        filas = session.scalars(
            select(BuzonLeido).where(BuzonLeido.chat == GRUPO, BuzonLeido.lector != yo)
        ).all()
    else:
        filas = session.scalars(
            select(BuzonLeido).where(BuzonLeido.lector == con, BuzonLeido.chat == yo)
        ).all()
    return {f.lector: int(f.hasta_id or 0) for f in filas}


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
        # «Recibido: ejecutando…» no es un mensaje para leer: es el estado de un comando.
        de_leer = BuzonMensaje.estado.is_distinct_from(RECIBIDO)
        ultimo = session.scalars(
            select(BuzonMensaje).where(filtro, de_leer).order_by(BuzonMensaje.id.desc()).limit(1)
        ).first()
        visto_hasta = int(leidos.get(clave, 0))
        no_leidos = len(session.scalars(
            select(BuzonMensaje.id).where(
                filtro, de_leer, BuzonMensaje.borrado_at.is_(None),
                BuzonMensaje.id > visto_hasta, BuzonMensaje.de != yo,
            )
        ).all())
        en_linea, visto = presencia.get(clave, (None, None))
        salida.append(Chat(
            clave=clave,
            nombre=NOMBRE_GRUPO if clave == GRUPO else clave,
            ultimo_texto=vista_previa(ultimo),
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
    # Lo leído también se muda: si no, las palomitas se quedarían con el nombre viejo.
    from sqlalchemy import delete

    for columna in (BuzonLeido.lector, BuzonLeido.chat):
        try:
            with session.begin_nested():
                session.execute(update(BuzonLeido).where(columna == viejo).values({columna.key: nuevo}))
        except Exception:  # noqa: BLE001 — ya había renglón con el nombre nuevo: el viejo sobra
            session.execute(delete(BuzonLeido).where(columna == viejo))
    session.flush()
    return int(a.rowcount or 0) + int(b.rowcount or 0)


def no_leidos_total(session: Session, *, yo: str, leidos: dict[str, int] | None = None) -> int:
    """Cuántos mensajes le esperan a esta PC en todos sus chats (para el aviso)."""
    return sum(c.no_leidos for c in chats(session, yo=yo, leidos=leidos))


# ── Nombre de esta PC ────────────────────────────────────────────────────────

#: Nombres que no puede tomar una PC: son de otro, o son el grupo.
RESERVADOS = ("Claude", NOMBRE_GRUPO, GRUPO, "Todas")


def validar_nombre(session: Session, nuevo: str, *, identificador: str | None = None) -> str:
    """El nombre limpio, o `NoSePuede` con el porqué.

    Dos PCs con el mismo nombre juntarían sus chats, y una que se llamara
    «Claude» mandaría mensajes que se ofrecen para Ejecutar en las demás."""
    limpio = " ".join((nuevo or "").split())
    if not limpio:
        raise NoSePuede("Escribe un nombre.")
    if len(limpio) > 60:
        raise NoSePuede("Es muy largo: máximo 60 letras.")
    if limpio.casefold() in {r.casefold() for r in RESERVADOS}:
        raise NoSePuede(f"«{limpio}» está reservado. Escoge otro.")
    try:
        from pos_uniformes.database.models import Satelite

        otras = session.scalars(select(Satelite)).all()
        for sat in otras:
            if sat.identificador != identificador and (sat.nombre or "").casefold() == limpio.casefold():
                raise NoSePuede(f"Ya hay otra PC que se llama «{sat.nombre}».")
    except NoSePuede:
        raise
    except Exception:  # noqa: BLE001 — sin registro de pantallas no hay con qué comparar
        pass
    return limpio


def renombrar_esta_pc(session: Session, nuevo: str, *, viejo: str, identificador: str | None) -> str:
    """Valida, se lleva el historial y deja el registro al día. No hace commit.

    El nombre local (el archivo de la PC) lo cambia quien llama, DESPUÉS del
    commit: si la base falla, la PC no queda con un nombre que nadie conoce."""
    from sqlalchemy import update

    limpio = validar_nombre(session, nuevo, identificador=identificador)
    renombrar(session, viejo, limpio)
    if identificador:
        # Por identificador, nunca por nombre: el nombre viejo podía repetirse.
        try:
            from pos_uniformes.database.models import Satelite

            with session.begin_nested():
                session.execute(
                    update(Satelite).where(Satelite.identificador == identificador).values(nombre=limpio)
                )
        except Exception:  # noqa: BLE001 — sin registro de pantallas, solo el buzón
            pass
    return limpio
