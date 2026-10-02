"""Servicio de anuncios/cartelera que se difunden a los satélites.

A diferencia de la cola de trabajos (una máquina reclama y consume cada
trabajo), un anuncio es *broadcast*: todos los satélites leen los que están
`activo=True` y los muestran. Se crea desde el menú admin del propio satélite y
se replica al resto por la DB central; el trigger `anuncio_notify` avisa por
LISTEN/NOTIFY para que la cartelera se refresque al instante.

Convención del repo: estas funciones mutan la Session pero NO hacen commit; el
llamador controla la transacción. Solo se hace flush donde se necesita el id.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Anuncio, AnuncioVisto

# Tope defensivo del tamaño de imagen embebida (ya reducida antes de llegar aquí).
MAX_IMAGEN_BYTES = 4 * 1024 * 1024  # 4 MB


def _limpiar(texto: str | None) -> str | None:
    """Normaliza texto: recorta espacios y trata el vacío como None."""
    if texto is None:
        return None
    t = texto.strip()
    return t or None


def _normalizar_destinos(destinos) -> list[str] | None:
    """Lista de identificadores destino, o None si va a TODOS.

    Acepta lista/tupla/set; recorta vacíos y duplica-nada. Lista vacía → None.
    """
    if not destinos:
        return None
    limpios = [str(d).strip() for d in destinos if str(d).strip()]
    # Quita duplicados conservando orden.
    vistos: list[str] = []
    for d in limpios:
        if d not in vistos:
            vistos.append(d)
    return vistos or None


def _aware(momento: datetime | None) -> datetime | None:
    """Normaliza a UTC: SQLite devuelve naive y comparar mezclado reventaría."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento


def vence_en(horas: float) -> datetime:
    """Momento de vencimiento a N horas de ahora, para quien crea el anuncio."""
    return datetime.now(timezone.utc) + timedelta(hours=horas)


def vigente(anuncio: Anuncio, ahora: datetime | None = None) -> bool:
    """¿Todavía toca mostrarlo? Sin `expira_en` vive hasta que se quite.

    La vigencia se resuelve en Python, no en SQL, para que valga igual con el
    SQLite de los tests y con Postgres, y porque los anuncios activos son
    siempre un puño.
    """
    expira = _aware(anuncio.expira_en)
    if expira is None:
        return True
    return expira > (_aware(ahora) or datetime.now(timezone.utc))


def visible_para(anuncio: Anuncio, identificador: str | None) -> bool:
    """¿Este satélite debe mostrar el anuncio? Sin destinos = todos."""
    destinos = anuncio.destinos
    if not destinos:
        return True
    if not identificador:
        return False
    return identificador in destinos


def crear_anuncio(
    session: Session,
    *,
    titulo: str | None = None,
    mensaje: str | None = None,
    imagen: bytes | None = None,
    imagen_mime: str | None = None,
    destinos=None,
    duracion_seg: int = 8,
    prioridad: int = 0,
    expira_en: datetime | None = None,
    pide_acuse: bool = False,
    creado_por: str = "satelite",
) -> Anuncio:
    """Crea un anuncio activo. Requiere al menos texto o imagen.

    `destinos`: lista de identificadores de satélite; None/vacía = todos.
    La imagen debe venir ya reducida (JPEG/PNG); se rechaza si excede el tope.
    Devuelve el Anuncio con id asignado (flush). No hace commit.
    """
    titulo = _limpiar(titulo)
    mensaje = _limpiar(mensaje)
    if not titulo and not mensaje and not imagen:
        raise ValueError("El anuncio necesita al menos un título, mensaje o imagen.")
    if imagen is not None and len(imagen) > MAX_IMAGEN_BYTES:
        raise ValueError(
            f"La imagen pesa {len(imagen)} bytes; el máximo es {MAX_IMAGEN_BYTES}."
        )
    if imagen is None:
        imagen_mime = None
    anuncio = Anuncio(
        titulo=titulo,
        mensaje=mensaje,
        imagen=imagen,
        imagen_mime=imagen_mime,
        destinos=_normalizar_destinos(destinos),
        activo=True,
        duracion_seg=max(1, int(duracion_seg)),
        prioridad=int(prioridad),
        expira_en=expira_en,
        pide_acuse=bool(pide_acuse),
        creado_por=(creado_por or "satelite")[:60],
    )
    session.add(anuncio)
    session.flush()  # asigna id
    return anuncio


def listar_activos(session: Session, *, para: str | None = None) -> list[Anuncio]:
    """Anuncios activos, en el orden en que rota la cartelera.

    Prioridad más alta primero; a igual prioridad, el más viejo primero (orden
    estable para que la rotación no salte al agregar/quitar).

    Si `para` (identificador de satélite) se pasa, filtra a los dirigidos a ese
    satélite (o a todos). Sin `para`, devuelve todos los activos (para el admin).
    """
    stmt = (
        select(Anuncio)
        .where(Anuncio.activo.is_(True))
        .order_by(Anuncio.prioridad.desc(), Anuncio.creado_en.asc(), Anuncio.id.asc())
    )
    ahora = datetime.now(timezone.utc)
    activos = [a for a in session.scalars(stmt).all() if vigente(a, ahora)]
    if para is None:
        return activos
    return [a for a in activos if visible_para(a, para)]


def listar_todos(session: Session, *, limite: int = 200) -> list[Anuncio]:
    """Todos los anuncios (para el panel admin), más reciente primero."""
    stmt = select(Anuncio).order_by(Anuncio.creado_en.desc(), Anuncio.id.desc()).limit(limite)
    return list(session.scalars(stmt).all())


def obtener(session: Session, anuncio_id: int) -> Anuncio | None:
    return session.get(Anuncio, anuncio_id)


def desactivar(session: Session, anuncio_id: int) -> Anuncio | None:
    """Quita un anuncio de la cartelera (activo=False). No hace commit."""
    anuncio = session.get(Anuncio, anuncio_id)
    if anuncio is None:
        return None
    anuncio.activo = False
    session.flush()
    return anuncio


def desactivar_todos(session: Session) -> int:
    """Apaga todos los anuncios activos de una. Devuelve cuántos apagó."""
    stmt = update(Anuncio).where(Anuncio.activo.is_(True)).values(activo=False)
    resultado = session.execute(stmt)
    return int(resultado.rowcount or 0)


def notificar(session: Session, accion: str, anuncio_id: int) -> None:
    """Emite un NOTIFY manual al canal 'anuncio' (respaldo del trigger).

    El trigger de la DB ya notifica en INSERT/UPDATE, así que normalmente no hace
    falta; se expone para forzar un aviso sin escribir. Best-effort: en motores
    sin pg_notify (SQLite de tests) no hace nada.
    """
    payload = f'{{"accion": "{accion}", "id": {int(anuncio_id)}}}'
    try:
        from sqlalchemy import text

        session.execute(text("SELECT pg_notify('anuncio', :p)"), {"p": payload})
    except Exception:  # noqa: BLE001 — motor sin NOTIFY o sin conexión: ignorar
        pass


def to_cache_dict(anuncio: Anuncio) -> dict:
    """Representa un anuncio para el cache local (sin los bytes de imagen).

    Los bytes se guardan aparte como archivo; aquí solo va la metadata + el mime
    para reconstruir el nombre del archivo de imagen.
    """
    return {
        "id": anuncio.id,
        "titulo": anuncio.titulo,
        "mensaje": anuncio.mensaje,
        "imagen_mime": anuncio.imagen_mime,
        "tiene_imagen": anuncio.imagen is not None,
        "duracion_seg": anuncio.duracion_seg,
        "prioridad": anuncio.prioridad,
        "pide_acuse": bool(anuncio.pide_acuse),
        "creado_en": (_aware(anuncio.creado_en) or datetime.now(timezone.utc)).isoformat(),
    }


def cache_payload(anuncios: Sequence[Anuncio]) -> list[dict]:
    """Metadata de varios anuncios para persistir en el cache local."""
    return [to_cache_dict(a) for a in anuncios]


def filas_para_cache(session: Session, *, para: str | None = None) -> list[dict]:
    """Anuncios activos CON bytes de imagen, listos para `save_anuncios_cache`.

    Se usa desde el hilo de fondo del watchdog: baja los anuncios de la DB y los
    escribe al cache local para que la cartelera funcione aun sin conexión.
    `para` (identificador de este satélite) filtra a los que le corresponden.
    """
    filas: list[dict] = []
    for a in listar_activos(session, para=para):
        filas.append(
            {
                "id": a.id,
                "titulo": a.titulo,
                "mensaje": a.mensaje,
                "imagen_mime": a.imagen_mime,
                "imagen_bytes": a.imagen,
                "duracion_seg": a.duracion_seg,
                "prioridad": a.prioridad,
                "pide_acuse": bool(a.pide_acuse),
                "creado_en": (_aware(a.creado_en) or datetime.now(timezone.utc)).isoformat(),
            }
        )
    return filas


# ── Acuse de recibo ──────────────────────────────────────────────────────────


def marcar_visto(
    session: Session,
    anuncio_id: int,
    *,
    satelite: str = "",
    satelite_nombre: str | None = None,
    empleada: str | None = None,
) -> AnuncioVisto | None:
    """Registra que en esta pantalla alguien tocó «Enterada». No hace commit.

    Idempotente por pantalla: el segundo toque devuelve la fila de la primera
    vez sin agregar renglones ni mover la hora. Lo que vale es cuándo se vio
    por primera vez, y así tocar dos veces no manda dos avisos a Daniel.

    Devuelve None si el anuncio no existe.
    """
    anuncio = session.get(Anuncio, int(anuncio_id))
    if anuncio is None:
        return None
    satelite = (str(satelite or "").strip())[:80]
    previo = session.scalar(
        select(AnuncioVisto).where(
            AnuncioVisto.anuncio_id == anuncio.id, AnuncioVisto.satelite == satelite
        )
    )
    if previo is not None:
        return previo
    visto = AnuncioVisto(
        anuncio_id=anuncio.id,
        satelite=satelite,
        satelite_nombre=(_limpiar(satelite_nombre) or None),
        empleada=(_limpiar(empleada) or None),
    )
    session.add(visto)
    session.flush()
    return visto


def ya_visto_en(session: Session, anuncio_id: int, satelite: str = "") -> bool:
    """¿Esta pantalla ya acusó este anuncio?"""
    return (
        session.scalar(
            select(AnuncioVisto).where(
                AnuncioVisto.anuncio_id == int(anuncio_id),
                AnuncioVisto.satelite == (str(satelite or "").strip())[:80],
            )
        )
        is not None
    )


def quien_vio(session: Session, anuncio_id: int) -> list[AnuncioVisto]:
    """Los acuses de un anuncio, el primero que contestó primero."""
    stmt = (
        select(AnuncioVisto)
        .where(AnuncioVisto.anuncio_id == int(anuncio_id))
        .order_by(AnuncioVisto.visto_en.asc(), AnuncioVisto.id.asc())
    )
    return list(session.scalars(stmt).all())


# ── Darle más vida a uno que ya está puesto ──────────────────────────────────


def alargar(session: Session, anuncio_id: int, horas: float) -> Anuncio | None:
    """Le suma horas al vencimiento. No hace commit.

    Cuenta desde *ahora*, no desde el vencimiento viejo: si ya venció o le
    faltan minutos, «+3 h» tiene que querer decir tres horas más de hoy, no
    tres horas desde un momento que ya pasó.
    """
    anuncio = session.get(Anuncio, int(anuncio_id))
    if anuncio is None:
        return None
    ahora = datetime.now(timezone.utc)
    base = _aware(anuncio.expira_en)
    if base is None or base < ahora:
        base = ahora
    anuncio.expira_en = base + timedelta(hours=float(horas))
    session.flush()
    return anuncio


def reponer(session: Session, anuncio_id: int, *, horas: float = 12.0) -> Anuncio | None:
    """Vuelve a poner el mismo aviso como nuevo, para que lo acusen otra vez.

    Crea una copia con id nuevo y apaga el original en vez de revivirlo. Es a
    propósito: cada kiosko recuerda qué ids ya acusó para no estorbar dos veces
    con lo mismo, así que revivir el original no haría que nadie lo volviera a
    ver. Con id nuevo, todas las pantallas lo preguntan de cero — y los acuses
    de la vuelta anterior quedan guardados como lo que fueron.
    """
    viejo = session.get(Anuncio, int(anuncio_id))
    if viejo is None:
        return None
    nuevo = Anuncio(
        titulo=viejo.titulo,
        mensaje=viejo.mensaje,
        imagen=viejo.imagen,
        imagen_mime=viejo.imagen_mime,
        destinos=list(viejo.destinos) if viejo.destinos else None,
        activo=True,
        duracion_seg=viejo.duracion_seg,
        prioridad=viejo.prioridad,
        pide_acuse=viejo.pide_acuse,
        expira_en=vence_en(horas),
        creado_por=viejo.creado_por,
    )
    session.add(nuevo)
    viejo.activo = False
    session.flush()
    return nuevo


# ── Cuando ya lo vieron, el aviso terminó ────────────────────────────────────


def pantallas_esperadas(session: Session, anuncio: Anuncio) -> list[str]:
    """Identificadores de los satélites que deberían acusar este anuncio.

    Con `destinos`, son esos. Sin destinos, son todos los satélites conocidos.
    Lista vacía = no se pudo averiguar, y entonces no se cierra nada: más vale
    un aviso de más que uno que se apagó sin que nadie lo viera.
    """
    if anuncio.destinos:
        return [str(d) for d in anuncio.destinos]
    try:
        from pos_uniformes.services import satelite_registry_service as rsvc

        return [str(s["identificador"]) for s in rsvc.listar_con_estado(session)]
    except Exception:  # noqa: BLE001
        return []


def cerrar_si_ya_lo_vieron(session: Session, anuncio_id: int) -> tuple[bool, int]:
    """Apaga el aviso si ya lo acusaron todas las pantallas. (cerrado, faltan).

    Daniel (02/10): "una vez que ponen enterada, debería de ya no salir de
    nuevo, solo que me avise que ya se enteraron y ya". Un aviso es un recado,
    no un cartel: cuando llegó a quien tenía que llegar, su trabajo terminó.
    Lo que sí se queda puesto es el cartel (`/cartel`), que para eso existe.

    No hace commit.
    """
    anuncio = session.get(Anuncio, int(anuncio_id))
    if anuncio is None or not anuncio.activo:
        return False, 0
    esperadas = pantallas_esperadas(session, anuncio)
    if not esperadas:
        return False, 0
    vistas = {str(v.satelite) for v in quien_vio(session, anuncio.id) if v.satelite}
    faltan = [p for p in esperadas if p not in vistas]
    if faltan:
        return False, len(faltan)
    anuncio.activo = False
    session.flush()
    return True, 0
