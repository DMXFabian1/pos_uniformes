"""Carga el snapshot del detalle seleccionado en Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class LayawayDetailLineSnapshot:
    sku: str
    product_name: str
    quantity: object
    unit_price: object
    subtotal: object


@dataclass(frozen=True)
class LayawayPaymentLineSnapshot:
    created_at_label: str
    amount: object
    reference: str
    username: str


@dataclass(frozen=True)
class LayawayDetailSnapshot:
    folio: str
    estado: str
    customer_code: str
    customer_name: str
    customer_phone: str
    subtotal: Decimal
    rounding_adjustment: Decimal
    total: Decimal
    total_paid: Decimal
    balance_due: Decimal
    commitment_label: str
    due_text: str
    due_tone: str
    notes_text: str
    detail_rows: tuple[LayawayDetailLineSnapshot, ...]
    payment_rows: tuple[LayawayPaymentLineSnapshot, ...]
    sale_ticket_enabled: bool
    whatsapp_enabled: bool


def load_layaway_detail_snapshot(
    session,
    *,
    layaway_id: int,
    current_role,
    classify_due,
) -> LayawayDetailSnapshot:
    apartado_service, estado_apartado, rol_usuario = _resolve_layaway_detail_dependencies()
    layaway = apartado_service.obtener_apartado(session, layaway_id)
    if layaway is None:
        raise ValueError("Apartado no encontrado.")

    due_text, due_tone = classify_due(layaway.fecha_compromiso, layaway.estado)
    can_manage_layaways = current_role in {rol_usuario.ADMIN, rol_usuario.CAJERO}
    return LayawayDetailSnapshot(
        folio=str(layaway.folio),
        estado=str(layaway.estado.value),
        customer_code=layaway.cliente.codigo_cliente if layaway.cliente is not None else "Manual",
        customer_name=str(layaway.cliente_nombre),
        customer_phone=str(layaway.cliente_telefono or ""),
        subtotal=Decimal(layaway.subtotal),
        rounding_adjustment=(Decimal(layaway.total) - Decimal(layaway.subtotal)).quantize(Decimal("0.01")),
        total=Decimal(layaway.total),
        total_paid=Decimal(layaway.total_abonado),
        balance_due=Decimal(layaway.saldo_pendiente),
        commitment_label=format_display_date(layaway.fecha_compromiso, empty="Sin fecha"),
        due_text=str(due_text),
        due_tone=str(due_tone),
        notes_text=str(layaway.observacion or "Sin observaciones."),
        detail_rows=tuple(
            LayawayDetailLineSnapshot(
                sku=str(detalle.variante.sku),
                product_name=sanitize_product_display_name(detalle.variante.producto.nombre),
                quantity=detalle.cantidad,
                unit_price=detalle.precio_unitario,
                subtotal=detalle.subtotal_linea,
            )
            for detalle in layaway.detalles
        ),
        payment_rows=tuple(
            LayawayPaymentLineSnapshot(
                created_at_label=format_display_datetime(abono.created_at),
                amount=abono.monto,
                reference=str(abono.referencia or ""),
                username=str(abono.usuario.username),
            )
            for abono in layaway.abonos
        ),
        sale_ticket_enabled=can_manage_layaways and layaway.estado == estado_apartado.ENTREGADO,
        whatsapp_enabled=can_manage_layaways and bool((layaway.cliente_telefono or "").strip()),
    )


def _resolve_layaway_detail_dependencies():
    from pos_uniformes.database.models import EstadoApartado, RolUsuario
    from pos_uniformes.services.apartado_service import ApartadoService

    return ApartadoService, EstadoApartado, RolUsuario
