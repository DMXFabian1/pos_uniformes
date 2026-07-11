"""Capa de vista de la cola de trabajos (para la GUI del despachador, Fase 2).

Pura y sin Qt: dado el estado de la cola, produce filas ya formateadas para la
tabla —etiquetas humanas por tipo, resumen del contenido, acciones disponibles—
de modo que el widget Qt solo pinte y conecte botones.

La etiqueta de estado depende del tipo: EN_PROCESO es "Imprimiendo" para un
ticket pero "Preparando" para un pedido; HECHO es "Impreso" vs "Listo".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc

_TIPO_LABEL = {
    TipoTrabajo.TICKET: "Ticket",
    TipoTrabajo.ETIQUETA: "Etiqueta",
    TipoTrabajo.CONTEO: "Conteo",
    TipoTrabajo.PEDIDO: "Pedido",
}

# Estados que se "atienden" (pedido) en vez de imprimirse.
_ATENDER = {TipoTrabajo.PEDIDO}


def tipo_label(tipo: TipoTrabajo) -> str:
    return _TIPO_LABEL.get(tipo, tipo.value.title())


def estado_label(estado: EstadoTrabajo, tipo: TipoTrabajo) -> str:
    atender = tipo in _ATENDER
    if estado == EstadoTrabajo.PENDIENTE:
        return "En espera"
    if estado == EstadoTrabajo.EN_PROCESO:
        return "Preparando" if atender else "Imprimiendo"
    if estado == EstadoTrabajo.HECHO:
        return "Listo" if atender else "Impreso"
    if estado == EstadoTrabajo.ERROR:
        return "Error"
    if estado == EstadoTrabajo.CANCELADO:
        return "Cancelado"
    return estado.value.title()


def resumen(trabajo: Trabajo) -> str:
    """Una línea corta que describe el contenido, para la columna 'Detalle'."""
    contenido = trabajo.contenido or {}
    if trabajo.tipo == TipoTrabajo.TICKET:
        texto = str(contenido.get("texto", ""))
        for linea in texto.splitlines():
            if linea.strip():
                return linea.strip()
        return "(ticket vacío)"
    if trabajo.tipo == TipoTrabajo.ETIQUETA:
        sku = contenido.get("sku") or ""
        copies = contenido.get("copies") or 1
        modo = contenido.get("paper_mode") or ""
        partes = [str(sku) if sku else "Etiqueta", f"{copies} copia(s)"]
        if modo:
            partes.append(str(modo))
        return " · ".join(partes)
    if trabajo.tipo == TipoTrabajo.CONTEO:
        titulo = str(contenido.get("titulo") or "Conteo")
        hojas = contenido.get("hojas")
        n = len(hojas) if isinstance(hojas, list) else 0
        return f"{titulo} · {n} hoja(s)"
    if trabajo.tipo == TipoTrabajo.PEDIDO:
        items = contenido.get("items")
        if isinstance(items, list):
            return f"{len(items)} artículo(s)"
        return "Pedido"
    return ", ".join(str(k) for k in contenido) or "—"


@dataclass(frozen=True)
class RowView:
    id: int
    tipo: TipoTrabajo
    estado: EstadoTrabajo
    tipo_texto: str
    estado_texto: str
    origen: str
    detalle: str
    error_msg: str | None
    puede_cancelar: bool
    puede_reintentar: bool
    puede_reimprimir: bool


def _to_row(trabajo: Trabajo) -> RowView:
    estado = trabajo.estado
    return RowView(
        id=trabajo.id,
        tipo=trabajo.tipo,
        estado=estado,
        tipo_texto=tipo_label(trabajo.tipo),
        estado_texto=estado_label(estado, trabajo.tipo),
        origen=trabajo.origen,
        detalle=resumen(trabajo),
        error_msg=trabajo.error_msg,
        puede_cancelar=estado == EstadoTrabajo.PENDIENTE,
        puede_reintentar=estado in (EstadoTrabajo.ERROR, EstadoTrabajo.CANCELADO),
        puede_reimprimir=estado == EstadoTrabajo.HECHO,
    )


def listar_para_vista(
    session: Session,
    *,
    estados: Iterable[EstadoTrabajo] | None = None,
    tipos: Iterable[TipoTrabajo] | None = None,
    origenes: Iterable[str] | None = None,
    limite: int | None = None,
) -> list[RowView]:
    """Filas listas para la tabla, en el mismo orden que procesa el despachador."""
    trabajos = svc.listar(
        session, estados=estados, tipos=tipos, origenes=origenes, limite=limite
    )
    return [_to_row(t) for t in trabajos]


def contar_por_estado(session: Session) -> dict[EstadoTrabajo, int]:
    """Cuántos trabajos hay en cada estado (para el encabezado del panel)."""
    conteo = {estado: 0 for estado in EstadoTrabajo}
    for trabajo in svc.listar(session):
        conteo[trabajo.estado] += 1
    return conteo
