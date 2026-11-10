"""E4-D: lo que ve y hace el ADMIN en el POS.

- La pestaña «Fidelización» de la ficha: programa actual, propuesta pendiente
  e historial. Las acciones (aprobar, rechazar, inscribir, cambiar, sacar)
  son las de `membresia_service`, que ya exigen ADMIN y motivo.
- La ventana «Programas»: listar con sus miembros y editar nombre,
  descripción y estado. No se borran programas: solo se pausan o cierran.

La vigencia queda en «sin vencimiento» (P-E4-3) y no se edita aquí: no hay
todavía nada que venza una membresía, y ponerla dejaría una fecha que nadie
cumple.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Empleada, Membresia, MembresiaEvento, Programa
from pos_uniformes.services.fidelizacion import membresia_service as ms

ESTADOS_EDITABLES = ("activo", "pausado", "cerrado")
ESTADO_ETIQUETAS = {"borrador": "Borrador", "activo": "Activo", "pausado": "Pausado", "cerrado": "Cerrado"}
EVENTO_ETIQUETAS = {
    ms.EV_ALTA: "Alta",
    ms.EV_PROPUESTA: "Propuesta",
    ms.EV_APROBACION: "Aprobada",
    ms.EV_RECHAZO: "Rechazada",
    ms.EV_EXPIRACION: "Caducó sin respuesta",
    ms.EV_REEMPLAZO: "Reemplazada por otro programa",
    ms.EV_CAMBIO_PROGRAMA: "Cambio de programa",
    ms.EV_CANCELACION: "Sacado del programa",
}
INGRESO_ETIQUETAS = {ms.DIRECTO_EMPLEADA: "La empleada inscribe", ms.APROBACION_DUENO: "Lo aprueba el dueño"}


# -- pestaña Fidelización -----------------------------------------------------------


@dataclass(frozen=True)
class Pendiente:
    membresia_id: int
    programa: str
    propuesta_por: str
    motivo: str
    fecha: datetime | None


@dataclass(frozen=True)
class FilaHistorialPrograma:
    fecha: datetime | None
    evento: str
    programa: str
    quien: str
    motivo: str


@dataclass(frozen=True)
class PanelPrograma:
    cliente_id: int
    actual: str | None
    actual_clave: str | None
    actual_desde: datetime | None
    pendiente: Pendiente | None
    historial: tuple[FilaHistorialPrograma, ...]
    #: (clave, nombre) de los programas activos a los que se puede inscribir o cambiar.
    destinos: tuple[tuple[str, str], ...]


def _nombre_empleada(session: Session, code: str | None) -> str:
    if not code:
        return ""
    e = session.scalar(select(Empleada).where(func.upper(Empleada.codigo) == str(code).upper()))
    return e.nombre_completo if e is not None else str(code)


def cargar_panel(session: Session, *, cliente_id: int, usuario_id: int) -> PanelPrograma:
    ms._admin(session, usuario_id)
    estado = ms.estado_de_cliente(session, int(cliente_id))
    pendiente = None
    if estado.pendiente is not None:
        p = estado.pendiente
        pendiente = Pendiente(
            membresia_id=int(p.id),
            programa=p.programa.nombre,
            propuesta_por=_nombre_empleada(session, p.propuesta_por_employee_code) or "ADMIN",
            motivo=p.motivo_propuesta or "",
            fecha=p.created_at,
        )
    historial = []
    for membresia, evento in ms.historial(session, int(cliente_id)):
        quien = evento.quien or _nombre_empleada(session, evento.employee_code)
        historial.append(FilaHistorialPrograma(
            fecha=evento.created_at,
            evento=EVENTO_ETIQUETAS.get(evento.tipo, evento.tipo),
            programa=membresia.programa.nombre,
            quien=quien or "",
            motivo=evento.motivo or (membresia.motivo_propuesta if evento.tipo == ms.EV_PROPUESTA else "") or "",
        ))
    actual_clave = estado.activa.programa.clave if estado.activa else None
    destinos = tuple((p.clave, p.nombre) for p in ms.programas_activos(session) if p.clave != actual_clave)
    return PanelPrograma(
        cliente_id=int(cliente_id),
        actual=estado.activa.programa.nombre if estado.activa else None,
        actual_clave=actual_clave,
        actual_desde=estado.activa.desde if estado.activa else None,
        pendiente=pendiente,
        historial=tuple(historial),
        destinos=destinos,
    )


# -- ventana Programas ---------------------------------------------------------------


@dataclass(frozen=True)
class FilaPrograma:
    clave: str
    nombre: str
    descripcion: str
    estado: str
    ingreso: str
    tipo_sugerido: str
    vigencia: str
    miembros: int
    pendientes: int


def listar_programas(session: Session, *, usuario_id: int) -> list[FilaPrograma]:
    ms._admin(session, usuario_id)
    conteos: dict[tuple[int, str], int] = {
        (int(pid), estado): int(n)
        for pid, estado, n in session.execute(
            select(Membresia.programa_id, Membresia.estado, func.count(Membresia.id))
            .where(Membresia.estado.in_((ms.ACTIVA, ms.PENDIENTE)))
            .group_by(Membresia.programa_id, Membresia.estado)
        ).all()
    }
    filas = []
    for p in session.scalars(select(Programa).order_by(Programa.orden, Programa.id)):
        filas.append(FilaPrograma(
            clave=p.clave,
            nombre=p.nombre,
            descripcion=p.descripcion or "",
            estado=ESTADO_ETIQUETAS.get(p.estado, p.estado),
            ingreso=INGRESO_ETIQUETAS.get(p.ingreso_modo, p.ingreso_modo),
            tipo_sugerido={"DOCENTE": "Docente", "MAYORISTA": "Mayorista"}.get(p.tipo_sugerido_clave or "", "—"),
            vigencia="Sin vencimiento" if p.vigencia_dias is None else f"{p.vigencia_dias} días",
            miembros=conteos.get((int(p.id), ms.ACTIVA), 0),
            pendientes=conteos.get((int(p.id), ms.PENDIENTE), 0),
        ))
    return filas


def editar_programa(session: Session, *, usuario_id: int, clave: str, nombre: str, descripcion: str,
                    estado: str) -> Programa:
    """Nombre, descripción y estado. Pausar o cerrar solo detiene las altas y
    aprobaciones nuevas: quien ya es miembro lo sigue siendo."""
    ms._admin(session, usuario_id)
    programa = ms.programa_por_clave(session, clave)
    if programa is None:
        raise ms.NoSePuede("No encontré ese programa.")
    nombre = (nombre or "").strip()
    if len(nombre) < 3:
        raise ms.NoSePuede("El nombre debe tener al menos 3 caracteres.")
    if len(nombre) > 80:
        raise ms.NoSePuede("El nombre no puede pasar de 80 caracteres.")
    estado = (estado or "").strip().lower()
    if estado not in ESTADOS_EDITABLES:
        raise ms.NoSePuede("El estado debe ser activo, pausado o cerrado.")
    duplicado = session.scalar(select(Programa).where(func.lower(Programa.nombre) == nombre.lower(), Programa.id != programa.id))
    if duplicado is not None:
        raise ms.NoSePuede(f"Ya hay un programa que se llama {duplicado.nombre}.")
    programa.nombre = nombre
    programa.descripcion = (descripcion or "").strip() or None
    programa.estado = estado
    session.add(programa)
    session.flush()
    return programa
