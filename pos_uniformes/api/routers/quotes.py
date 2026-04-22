"""Endpoints de presupuestos moviles para la API."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.quotes import (
    LineaOut,
    PresupuestoCreateRequest,
    PresupuestoListItem,
    PresupuestoOut,
    PresupuestoUpdateRequest,
)
from pos_uniformes.api.services.token_service import TokenPayload
from pos_uniformes.database.models import (
    Cliente,
    Empleada,
    EstadoPresupuesto,
    Presupuesto,
    PresupuestoDetalle,
    RolUsuario,
    Usuario,
    Variante,
)

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


def _generate_folio() -> str:
    """Genera folio compatible con el formato del POS: PRE-YYYYMMDD-HHMMSS-XXXX."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:4].upper()
    return f"PRE-{ts}-{suffix}"


def _resolve_service_user(db: Session) -> Usuario:
    """
    Resuelve un usuario tecnico de servicio para la operacion API.
    Usa el primer CAJERO activo disponible, igual que el satelite desktop.
    """
    user = db.scalar(
        select(Usuario)
        .where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.CAJERO)
        .order_by(Usuario.id.asc())
    )
    if user is None:
        user = db.scalar(
            select(Usuario)
            .where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.ADMIN)
            .order_by(Usuario.id.asc())
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "sin_usuario_servicio", "message": "No hay usuarios activos para operar la API."}},
        )
    return user


def _build_lines(db: Session, lineas: list) -> tuple[list[PresupuestoDetalle], Decimal]:
    """Construye lineas de detalle y calcula el total."""
    if not lineas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "sin_lineas", "message": "El presupuesto debe tener al menos una linea."}},
        )

    total = Decimal("0.00")
    detalles: list[PresupuestoDetalle] = []
    skus_vistos: set[str] = set()

    for linea in lineas:
        sku = linea.sku.strip().upper()
        if sku in skus_vistos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "sku_duplicado", "message": f"SKU duplicado en el presupuesto: {sku}."}},
            )
        skus_vistos.add(sku)

        variante = db.scalar(
            select(Variante).where(Variante.sku == sku, Variante.activo.is_(True))
        )
        if variante is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "sku_no_encontrado", "message": f"No se encontro variante activa con SKU '{sku}'."}},
            )

        precio = Decimal(str(linea.precio_unitario)).quantize(Decimal("0.01"))
        subtotal_linea = (precio * linea.cantidad).quantize(Decimal("0.01"))
        total += subtotal_linea

        detalles.append(
            PresupuestoDetalle(
                variante_id=variante.id,
                sku_snapshot=variante.sku,
                descripcion_snapshot=f"{variante.producto.nombre} {variante.talla} {variante.color}".strip()
                if variante.producto
                else variante.sku,
                talla_snapshot=variante.talla,
                color_snapshot=variante.color,
                precio_unitario=precio,
                cantidad=linea.cantidad,
                subtotal_linea=subtotal_linea,
            )
        )

    return detalles, total


def _to_presupuesto_out(p: Presupuesto) -> PresupuestoOut:
    return PresupuestoOut(
        id=p.id,
        folio=p.folio,
        estado=p.estado.value,
        seller_employee_id=p.seller_employee_id,
        cliente_id=p.cliente_id,
        cliente_nombre=p.cliente_nombre,
        subtotal=p.subtotal,
        total=p.total,
        observacion=p.observacion,
        lineas=[
            LineaOut(
                id=d.id,
                sku_snapshot=d.sku_snapshot,
                descripcion_snapshot=d.descripcion_snapshot,
                talla_snapshot=d.talla_snapshot,
                color_snapshot=d.color_snapshot,
                precio_unitario=d.precio_unitario,
                cantidad=d.cantidad,
                subtotal_linea=d.subtotal_linea,
            )
            for d in p.detalles
        ],
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _load_presupuesto(db: Session, presupuesto_id: int) -> Presupuesto:
    p = db.scalar(
        select(Presupuesto)
        .where(Presupuesto.id == presupuesto_id)
        .options(selectinload(Presupuesto.detalles))
    )
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "presupuesto_no_encontrado", "message": "Presupuesto no encontrado."}},
        )
    return p


def _assert_owner(p: Presupuesto, payload: TokenPayload) -> None:
    """Verifica que el presupuesto pertenece a la empleada autenticada."""
    if p.seller_employee_id != payload.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "no_autorizado", "message": "Este presupuesto pertenece a otra empleada."}},
        )


def _assert_borrador(p: Presupuesto) -> None:
    if p.estado != EstadoPresupuesto.BORRADOR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "estado_invalido", "message": "Solo se pueden editar presupuestos en borrador."}},
        )


@router.get("", response_model=list[PresupuestoListItem])
def list_my_quotes(
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> list[PresupuestoListItem]:
    """Lista borradores activos de la empleada en sesion."""
    _empleada, payload = auth
    presupuestos = db.scalars(
        select(Presupuesto)
        .where(
            Presupuesto.seller_employee_id == payload.employee_id,
            Presupuesto.estado == EstadoPresupuesto.BORRADOR,
        )
        .options(selectinload(Presupuesto.detalles))
        .order_by(Presupuesto.created_at.desc())
    ).all()

    return [
        PresupuestoListItem(
            id=p.id,
            folio=p.folio,
            estado=p.estado.value,
            cliente_nombre=p.cliente_nombre,
            total=p.total,
            total_lineas=len(p.detalles),
            created_at=p.created_at,
        )
        for p in presupuestos
    ]


@router.post("", response_model=PresupuestoOut, status_code=status.HTTP_201_CREATED)
def create_quote(
    body: PresupuestoCreateRequest,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> PresupuestoOut:
    """Crea un borrador de presupuesto ligado a la empleada en sesion."""
    _empleada, payload = auth
    service_user = _resolve_service_user(db)

    cliente_nombre = body.cliente_nombre
    if body.cliente_id:
        cliente = db.scalar(select(Cliente).where(Cliente.id == body.cliente_id))
        if cliente is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "cliente_no_encontrado", "message": "Cliente no encontrado."}},
            )
        cliente_nombre = cliente_nombre or cliente.nombre

    detalles, total = _build_lines(db, body.lineas) if body.lineas else ([], Decimal("0.00"))

    p = Presupuesto(
        usuario_id=service_user.id,
        seller_employee_id=payload.employee_id,
        cliente_id=body.cliente_id,
        cliente_nombre=cliente_nombre,
        folio=_generate_folio(),
        estado=EstadoPresupuesto.BORRADOR,
        subtotal=total,
        total=total,
        observacion=body.observacion,
    )
    p.detalles = detalles
    db.add(p)
    db.flush()
    db.refresh(p)
    return _to_presupuesto_out(p)


@router.get("/{presupuesto_id}", response_model=PresupuestoOut)
def get_quote(
    presupuesto_id: int,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> PresupuestoOut:
    """Detalle de un presupuesto de la empleada."""
    _empleada, payload = auth
    p = _load_presupuesto(db, presupuesto_id)
    _assert_owner(p, payload)
    return _to_presupuesto_out(p)


@router.put("/{presupuesto_id}", response_model=PresupuestoOut)
def update_quote(
    presupuesto_id: int,
    body: PresupuestoUpdateRequest,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> PresupuestoOut:
    """Reemplaza las lineas y datos de un borrador de la empleada."""
    _empleada, payload = auth
    p = _load_presupuesto(db, presupuesto_id)
    _assert_owner(p, payload)
    _assert_borrador(p)

    cliente_nombre = body.cliente_nombre
    if body.cliente_id:
        cliente = db.scalar(select(Cliente).where(Cliente.id == body.cliente_id))
        if cliente is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "cliente_no_encontrado", "message": "Cliente no encontrado."}},
            )
        cliente_nombre = cliente_nombre or cliente.nombre

    detalles, total = _build_lines(db, body.lineas)

    p.cliente_id = body.cliente_id
    p.cliente_nombre = cliente_nombre
    p.observacion = body.observacion
    p.subtotal = total
    p.total = total
    p.detalles.clear()
    for d in detalles:
        d.presupuesto_id = p.id
    p.detalles.extend(detalles)
    db.add(p)
    db.flush()
    db.refresh(p)
    return _to_presupuesto_out(p)


@router.post("/{presupuesto_id}/ready", response_model=PresupuestoOut)
def mark_ready(
    presupuesto_id: int,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> PresupuestoOut:
    """
    Marca el presupuesto como EMITIDO (listo para pasar a caja).
    La empleada no puede editarlo despues de esto.
    """
    _empleada, payload = auth
    p = _load_presupuesto(db, presupuesto_id)
    _assert_owner(p, payload)
    _assert_borrador(p)

    if not p.detalles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "sin_lineas", "message": "No se puede emitir un presupuesto sin lineas."}},
        )

    p.estado = EstadoPresupuesto.EMITIDO
    p.emitido_at = datetime.now(timezone.utc)
    db.add(p)
    db.flush()
    db.refresh(p)
    return _to_presupuesto_out(p)


@router.delete("/{presupuesto_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_quote(
    presupuesto_id: int,
    db: Session = Depends(get_db),
    auth=Depends(get_current_employee),
) -> None:
    """Cancela un borrador de presupuesto de la empleada."""
    _empleada, payload = auth
    p = _load_presupuesto(db, presupuesto_id)
    _assert_owner(p, payload)
    _assert_borrador(p)

    p.estado = EstadoPresupuesto.CANCELADO
    p.cancelado_at = datetime.now(timezone.utc)
    db.add(p)
