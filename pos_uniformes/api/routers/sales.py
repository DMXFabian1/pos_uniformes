"""Endpoints de ventas y tickets de la empleada para la API movil."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.sales import (
    ResumenVentasHoy,
    TicketListItem,
    TicketOut,
    VentaDetalleOut,
)
from pos_uniformes.api.services.token_service import TokenPayload
from pos_uniformes.database.models import EstadoVenta, Venta, VentaDetalle

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


def _confirmed_sales_base(employee_id: int):
    """Stmt base: ventas confirmadas de la empleada."""
    return (
        select(Venta)
        .where(
            Venta.seller_employee_id == employee_id,
            Venta.estado == EstadoVenta.CONFIRMADA,
        )
    )


@router.get("/today", response_model=ResumenVentasHoy)
def sales_today(
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> ResumenVentasHoy:
    """
    Resumen de ventas confirmadas del dia actual atribuidas a la empleada.
    Dia definido en UTC — ajustar si se requiere zona horaria local en el futuro.
    """
    _empleada, payload = auth
    today = date.today()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    ventas = db.scalars(
        _confirmed_sales_base(payload.employee_id)
        .where(Venta.confirmada_at >= start)
        .options(selectinload(Venta.detalles))
    ).all()

    monto_total = sum((v.total for v in ventas), Decimal("0.00"))
    total_tickets = len(ventas)
    total_lineas = sum(sum(d.cantidad for d in v.detalles) for v in ventas)

    return ResumenVentasHoy(
        total_ventas=total_lineas,
        total_tickets=total_tickets,
        monto_total=monto_total,
        fecha=today.isoformat(),
    )


@router.get("", response_model=list[TicketListItem])
def list_sales(
    desde: date | None = Query(default=None, description="Fecha inicio (YYYY-MM-DD)"),
    hasta: date | None = Query(default=None, description="Fecha fin (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> list[TicketListItem]:
    """
    Ventas confirmadas de la empleada filtradas por periodo.
    Sin filtros devuelve las ultimas 30.
    """
    _empleada, payload = auth
    stmt = _confirmed_sales_base(payload.employee_id)

    if desde:
        stmt = stmt.where(
            Venta.confirmada_at >= datetime(desde.year, desde.month, desde.day, tzinfo=timezone.utc)
        )
    if hasta:
        stmt = stmt.where(
            Venta.confirmada_at < datetime(hasta.year, hasta.month, hasta.day + 1, tzinfo=timezone.utc)
        )

    stmt = stmt.order_by(Venta.confirmada_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ventas = db.scalars(stmt).all()

    return [
        TicketListItem(
            id=v.id,
            folio=v.folio,
            estado=v.estado.value,
            cliente_nombre=None,  # Se carga en detalle para no hacer join en lista
            total=v.total,
            confirmada_at=v.confirmada_at,
            created_at=v.created_at,
        )
        for v in ventas
    ]


@router.get("/{venta_id}", response_model=TicketOut)
def get_ticket(
    venta_id: int,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> TicketOut:
    """Detalle completo de un ticket de venta de la empleada."""
    _empleada, payload = auth
    venta = db.scalar(
        select(Venta)
        .where(Venta.id == venta_id, Venta.seller_employee_id == payload.employee_id)
        .options(
            selectinload(Venta.detalles),
            selectinload(Venta.cliente),
        )
    )
    if venta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ticket_no_encontrado", "message": "Ticket no encontrado."}},
        )

    return TicketOut(
        id=venta.id,
        folio=venta.folio,
        estado=venta.estado.value,
        cliente_nombre=venta.cliente.nombre if venta.cliente else None,
        subtotal=venta.subtotal,
        descuento_monto=venta.descuento_monto,
        total=venta.total,
        confirmada_at=venta.confirmada_at,
        created_at=venta.created_at,
        lineas=[
            VentaDetalleOut(
                id=d.id,
                sku_snapshot=d.sku_snapshot,
                descripcion_snapshot=d.descripcion_snapshot,
                cantidad=d.cantidad,
                precio_unitario=d.precio_unitario,
                subtotal_linea=d.subtotal_linea,
            )
            for d in venta.detalles
        ],
    )
