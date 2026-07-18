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

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Anuncio

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
    activos = list(session.scalars(stmt).all())
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
            }
        )
    return filas
