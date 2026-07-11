"""Servicio de la cola de trabajos que el POS/kiosko envían al satélite.

Fase 0 del despachador: solo la capa de datos, sin UI ni impresión.

Modelo mental:
  - El emisor (principal/kiosko) llama a `encolar(...)` -> INSERT de un Trabajo PENDIENTE.
  - El despachador del satélite llama a `reclamar_siguiente(...)` para tomar el
    siguiente PENDIENTE de forma atómica (pasa a EN_PROCESO), lo imprime/atiende,
    y luego llama a `marcar_hecho(...)` o `marcar_error(...)`.
  - La GUI usa `listar(...)`, `reordenar(...)`, `cancelar(...)` y `reintentar(...)`.

Convención del repo: estas funciones mutan la Session pero NO hacen commit;
el llamador controla la transacción. Solo se hace flush donde se necesita el id.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo, Trabajo

# Estados desde los que tiene sentido reintentar un trabajo.
_REINTENTABLES = {EstadoTrabajo.ERROR, EstadoTrabajo.CANCELADO}


def encolar(
    session: Session,
    tipo: TipoTrabajo,
    contenido: dict,
    *,
    origen: str = "principal",
    creado_por: str = "SYSTEM",
    prioridad: int = 0,
) -> Trabajo:
    """Crea un trabajo PENDIENTE y lo deja en la cola. Hace flush para asignar id."""
    if not isinstance(tipo, TipoTrabajo):
        raise TypeError(f"tipo debe ser TipoTrabajo, no {type(tipo)!r}")
    if not isinstance(contenido, dict):
        raise TypeError("contenido debe ser un dict serializable a JSON")

    trabajo = Trabajo(
        tipo=tipo,
        estado=EstadoTrabajo.PENDIENTE,
        contenido=contenido,
        origen=(origen or "principal").strip() or "principal",
        creado_por=(creado_por or "SYSTEM").strip() or "SYSTEM",
        prioridad=prioridad,
    )
    session.add(trabajo)
    session.flush()
    return trabajo


def obtener(session: Session, trabajo_id: int) -> Trabajo | None:
    """Devuelve un trabajo por id, o None si no existe."""
    return session.get(Trabajo, trabajo_id)


# ---------------------------------------------------------------------------
# Emisores de alto nivel (POS / kiosko)
#
# Encapsulan el esquema de `contenido` de cada tipo, para que el emisor y el
# despachador no lo dupliquen. La clave de un ticket es siempre "texto".
# ---------------------------------------------------------------------------

def enviar_ticket(
    session: Session,
    texto: str,
    *,
    origen: str = "principal",
    creado_por: str = "SYSTEM",
) -> Trabajo:
    """Encola un ticket (texto ya renderizado a 80mm) para imprimir en el satélite."""
    if not texto or not texto.strip():
        raise ValueError("El texto del ticket está vacío.")
    return encolar(
        session,
        TipoTrabajo.TICKET,
        {"texto": texto},
        origen=origen,
        creado_por=creado_por,
    )


def enviar_tickets(
    session: Session,
    textos: Sequence[str],
    *,
    origen: str = "principal",
    creado_por: str = "SYSTEM",
) -> list[Trabajo]:
    """Encola varios tickets de una venta/apartado en orden. Ignora los vacíos."""
    creados: list[Trabajo] = []
    for texto in textos:
        if texto and texto.strip():
            creados.append(
                enviar_ticket(session, texto, origen=origen, creado_por=creado_por)
            )
    return creados


def texto_de_ticket(trabajo: Trabajo) -> str:
    """Extrae el texto imprimible del payload de un trabajo TICKET."""
    if trabajo.tipo != TipoTrabajo.TICKET:
        raise ValueError(f"El trabajo id={trabajo.id} no es un TICKET.")
    texto = (trabajo.contenido or {}).get("texto", "")
    if not texto:
        raise ValueError(f"El trabajo TICKET id={trabajo.id} no trae texto.")
    return texto


def listar(
    session: Session,
    *,
    estados: Iterable[EstadoTrabajo] | None = None,
    tipos: Iterable[TipoTrabajo] | None = None,
    origenes: Iterable[str] | None = None,
    limite: int | None = None,
) -> list[Trabajo]:
    """Lista trabajos ordenados por (prioridad, created_at, id).

    Todos los filtros son opcionales y se combinan con AND. Un iterable vacío
    filtra a cero resultados (no se ignora), para que la GUI pueda expresar
    "ninguno de estos estados" sin ambigüedad.
    """
    stmt = select(Trabajo)
    if estados is not None:
        stmt = stmt.where(Trabajo.estado.in_(list(estados)))
    if tipos is not None:
        stmt = stmt.where(Trabajo.tipo.in_(list(tipos)))
    if origenes is not None:
        stmt = stmt.where(Trabajo.origen.in_(list(origenes)))
    stmt = stmt.order_by(Trabajo.prioridad, Trabajo.created_at, Trabajo.id)
    if limite is not None:
        stmt = stmt.limit(limite)
    return list(session.scalars(stmt))


def siguiente_pendiente(
    session: Session,
    *,
    tipos: Iterable[TipoTrabajo] | None = None,
) -> Trabajo | None:
    """Devuelve el siguiente trabajo PENDIENTE sin cambiar su estado (peek)."""
    stmt = (
        select(Trabajo)
        .where(Trabajo.estado == EstadoTrabajo.PENDIENTE)
        .order_by(Trabajo.prioridad, Trabajo.created_at, Trabajo.id)
        .limit(1)
    )
    if tipos is not None:
        stmt = stmt.where(Trabajo.tipo.in_(list(tipos)))
    return session.scalars(stmt).first()


def reclamar_siguiente(
    session: Session,
    *,
    tipos: Iterable[TipoTrabajo] | None = None,
) -> Trabajo | None:
    """Toma atómicamente el siguiente PENDIENTE y lo pasa a EN_PROCESO.

    Usa FOR UPDATE SKIP LOCKED para que varios despachadores (o hilos) no tomen
    el mismo trabajo. En SQLite (tests) el lock se ignora sin error.
    Devuelve el trabajo reclamado, o None si no hay pendientes.
    """
    stmt = (
        select(Trabajo)
        .where(Trabajo.estado == EstadoTrabajo.PENDIENTE)
        .order_by(Trabajo.prioridad, Trabajo.created_at, Trabajo.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if tipos is not None:
        stmt = stmt.where(Trabajo.tipo.in_(list(tipos)))
    trabajo = session.scalars(stmt).first()
    if trabajo is None:
        return None
    trabajo.estado = EstadoTrabajo.EN_PROCESO
    session.flush()
    return trabajo


def marcar_hecho(session: Session, trabajo_id: int) -> Trabajo:
    """Marca el trabajo como HECHO y sella procesado_en."""
    return _finalizar(session, trabajo_id, EstadoTrabajo.HECHO, error_msg=None)


def marcar_error(session: Session, trabajo_id: int, mensaje: str) -> Trabajo:
    """Marca el trabajo como ERROR guardando el mensaje y sella procesado_en."""
    return _finalizar(session, trabajo_id, EstadoTrabajo.ERROR, error_msg=mensaje)


def cancelar(session: Session, trabajo_id: int) -> Trabajo:
    """Cancela un trabajo. No se puede cancelar uno ya HECHO."""
    trabajo = _requerir(session, trabajo_id)
    if trabajo.estado == EstadoTrabajo.HECHO:
        raise ValueError(f"El trabajo id={trabajo_id} ya está HECHO; no se puede cancelar.")
    trabajo.estado = EstadoTrabajo.CANCELADO
    session.flush()
    return trabajo


def reintentar(session: Session, trabajo_id: int) -> Trabajo:
    """Vuelve a poner en PENDIENTE un trabajo en ERROR o CANCELADO."""
    trabajo = _requerir(session, trabajo_id)
    if trabajo.estado not in _REINTENTABLES:
        raise ValueError(
            f"Solo se puede reintentar un trabajo en {sorted(e.value for e in _REINTENTABLES)}; "
            f"id={trabajo_id} está en {trabajo.estado.value}."
        )
    trabajo.estado = EstadoTrabajo.PENDIENTE
    trabajo.error_msg = None
    trabajo.procesado_en = None
    session.flush()
    return trabajo


def reimprimir(session: Session, trabajo_id: int) -> Trabajo:
    """Encola una copia nueva (PENDIENTE) de un trabajo, sea cual sea su estado.

    A diferencia de `reintentar` (que resetea el mismo trabajo, solo desde
    ERROR/CANCELADO), esto CLONA: el original queda como está (p.ej. HECHO) y
    se crea un trabajo nuevo con el mismo contenido. Ideal para "reimprimir".
    """
    original = _requerir(session, trabajo_id)
    return encolar(
        session,
        original.tipo,
        dict(original.contenido or {}),
        origen=original.origen,
        creado_por=original.creado_por,
    )


def reordenar(session: Session, orden_ids: Sequence[int]) -> list[Trabajo]:
    """Reasigna `prioridad` a los trabajos dados según su posición en la lista.

    El primer id recibe prioridad 0, el segundo 1, etc. Los trabajos no listados
    conservan su prioridad. Lanza si algún id no existe.
    """
    resultado: list[Trabajo] = []
    for posicion, trabajo_id in enumerate(orden_ids):
        trabajo = _requerir(session, trabajo_id)
        trabajo.prioridad = posicion
        resultado.append(trabajo)
    session.flush()
    return resultado


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _requerir(session: Session, trabajo_id: int) -> Trabajo:
    trabajo = session.get(Trabajo, trabajo_id)
    if trabajo is None:
        raise ValueError(f"Trabajo id={trabajo_id} no encontrado.")
    return trabajo


def _finalizar(
    session: Session,
    trabajo_id: int,
    estado: EstadoTrabajo,
    *,
    error_msg: str | None,
) -> Trabajo:
    trabajo = _requerir(session, trabajo_id)
    trabajo.estado = estado
    trabajo.error_msg = error_msg
    trabajo.procesado_en = func.now()
    session.flush()
    return trabajo
