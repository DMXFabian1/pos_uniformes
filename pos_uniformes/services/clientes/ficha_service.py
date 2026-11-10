"""Ficha de un cliente para el ADMIN (E1-C3). Solo lectura.

Junta lo que ya existe: identidad, Libreta, ventas, apartados y eventos. No
escribe nada ni recalcula nada. Los registros privados de la Libreta se
cuentan pero no se listan. No hay totales acumulados: cada fila muestra su
propio importe y nada más.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Apartado, Cliente, ClienteEvento, ClienteTipo, LibretaVenta, Usuario, Venta
from pos_uniformes.services.clientes import admin_service

LIMITE_FILAS = 200


@dataclass(frozen=True)
class FilaHistorial:
    fecha: datetime | None
    columnas: tuple[str, ...]


@dataclass(frozen=True)
class FichaCliente:
    id: int
    codigo: str
    nombre: str
    telefono: str
    tipo: str
    origen: str
    alta: datetime | None
    activo: bool
    archivado_en: datetime | None
    archivado_motivo: str
    notas: str
    libreta: list[FilaHistorial] = field(default_factory=list)
    libreta_privadas: int = 0
    ventas: list[FilaHistorial] = field(default_factory=list)
    apartados: list[FilaHistorial] = field(default_factory=list)
    eventos: list[FilaHistorial] = field(default_factory=list)


def _dinero(valor) -> str:
    return f"${Decimal(valor or 0).quantize(Decimal('0.01'))}"


def _enum(valor) -> str:
    return str(getattr(valor, "value", valor) or "")


def _resumen_detalle(detalle) -> str:
    if not isinstance(detalle, dict):
        return ""
    if "cambios" in detalle:
        return "Cambio: " + ", ".join(sorted(detalle["cambios"]))
    partes = []
    for clave in ("motivo", "antes", "despues", "tipo", "origen"):
        if detalle.get(clave) not in (None, ""):
            partes.append(f"{clave}: {detalle[clave]}")
    return "; ".join(partes)


def cargar_ficha(session: Session, *, cliente_id: int, usuario_id: int) -> FichaCliente:
    admin_service.exigir_admin(session, usuario_id)
    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise ValueError("No se encontró el cliente.")
    tipo = session.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    cid = int(cliente.id)

    libreta = [
        FilaHistorial(
            fecha=r.created_at,
            columnas=(str(r.tipo or ""), str(r.piezas or 0), str(r.employee_name or r.employee_code or ""), _dinero(r.monto_total)),
        )
        for r in session.scalars(
            select(LibretaVenta)
            .where(LibretaVenta.cliente_id == cid, LibretaVenta.privado.is_(False))
            .order_by(LibretaVenta.created_at.desc(), LibretaVenta.id.desc())
            .limit(LIMITE_FILAS)
        )
    ]
    privadas = int(
        session.scalar(
            select(func.count(LibretaVenta.id)).where(LibretaVenta.cliente_id == cid, LibretaVenta.privado.is_(True))
        )
        or 0
    )
    ventas = [
        FilaHistorial(
            fecha=v.confirmada_at or v.created_at,
            columnas=(str(v.folio), _enum(v.estado), _dinero(v.total)),
        )
        for v in session.scalars(
            select(Venta).where(Venta.cliente_id == cid).order_by(Venta.created_at.desc(), Venta.id.desc()).limit(LIMITE_FILAS)
        )
    ]
    apartados = [
        FilaHistorial(
            fecha=a.created_at,
            columnas=(str(a.folio), _enum(a.estado), _dinero(a.total), _dinero(a.saldo_pendiente)),
        )
        for a in session.scalars(
            select(Apartado)
            .where(Apartado.cliente_id == cid)
            .order_by(Apartado.created_at.desc(), Apartado.id.desc())
            .limit(LIMITE_FILAS)
        )
    ]
    eventos = [
        FilaHistorial(
            fecha=e.created_at,
            columnas=(str(e.tipo), str(e.origen or ""), str(nombre or e.employee_code or ""), _resumen_detalle(e.detalle)),
        )
        for e, nombre in session.execute(
            select(ClienteEvento, Usuario.username)
            .outerjoin(Usuario, Usuario.id == ClienteEvento.usuario_id)
            .where(ClienteEvento.cliente_id == cid)
            .order_by(ClienteEvento.id.desc())
            .limit(LIMITE_FILAS)
        ).all()
    ]
    return FichaCliente(
        id=cid,
        codigo=str(cliente.codigo_cliente),
        nombre=str(cliente.nombre),
        telefono=cliente.telefono or "",
        tipo=str(tipo.nombre) if tipo is not None else "",
        origen=cliente.origen_alta or "",
        alta=cliente.cliente_desde,
        activo=bool(cliente.activo),
        archivado_en=cliente.archivado_en,
        archivado_motivo=cliente.archivado_motivo or "",
        notas=cliente.notas or "",
        libreta=libreta,
        libreta_privadas=privadas,
        ventas=ventas,
        apartados=apartados,
        eventos=eventos,
    )
