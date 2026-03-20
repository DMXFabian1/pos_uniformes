"""Servicios para guardar y reanudar el armado de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QuoteEditorLineSnapshot:
    sku: str
    description: str
    quantity: int
    unit_price: object
    school_name: str
    education_level_name: str


@dataclass(frozen=True)
class QuoteEditorSnapshot:
    quote_id: int
    folio: str
    customer_id: int | None
    customer_name: str
    customer_phone: str
    validity_at: datetime | None
    notes_text: str
    status_label: str
    detail_rows: tuple[QuoteEditorLineSnapshot, ...]


@dataclass(frozen=True)
class QuoteSavePayload:
    quote_id: int | None
    folio: str
    customer_id: int | None
    validity_at: datetime | None
    notes_text: str
    items: tuple[object, ...]
    target_state: object


@dataclass(frozen=True)
class QuoteSaveResult:
    quote_id: int
    folio: str
    status_label: str
    action_key: str


def load_quote_editor_snapshot(session, *, quote_id: int) -> QuoteEditorSnapshot:
    presupuesto_service = _resolve_quote_editor_dependencies()[2]
    quote = presupuesto_service.obtener_presupuesto(session, quote_id)
    if quote is None:
        raise ValueError("No se encontro el presupuesto seleccionado.")
    if _state_value(quote.estado) != "BORRADOR":
        raise ValueError("Solo se pueden reanudar presupuestos en borrador.")

    return QuoteEditorSnapshot(
        quote_id=int(quote.id),
        folio=str(quote.folio),
        customer_id=int(quote.cliente_id) if quote.cliente_id is not None else None,
        customer_name=str(quote.cliente_nombre or (quote.cliente.nombre if quote.cliente else "")),
        customer_phone=str(quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")),
        validity_at=quote.vigencia_hasta,
        notes_text=str(quote.observacion or ""),
        status_label=str(quote.estado.value),
        detail_rows=tuple(
            QuoteEditorLineSnapshot(
                sku=str(detail.sku_snapshot),
                description=str(detail.descripcion_snapshot),
                quantity=int(detail.cantidad),
                unit_price=detail.precio_unitario,
                school_name=_detail_school_name(detail),
                education_level_name=_detail_education_level_name(detail),
            )
            for detail in quote.detalles
        ),
    )


def save_quote_from_editor(session, *, user_id: int, payload: QuoteSavePayload) -> QuoteSaveResult:
    usuario_model, cliente_model, presupuesto_service = _resolve_quote_editor_dependencies()
    usuario = session.get(usuario_model, user_id)
    if usuario is None:
        raise ValueError("Usuario no encontrado.")

    cliente = session.get(cliente_model, payload.customer_id) if payload.customer_id is not None else None
    items = list(payload.items)

    if payload.quote_id is None:
        quote = presupuesto_service.crear_presupuesto(
            session=session,
            usuario=usuario,
            folio=payload.folio,
            items=items,
            cliente=cliente,
            cliente_nombre=cliente.nombre if cliente is not None else None,
            cliente_telefono=cliente.telefono if cliente is not None else None,
            vigencia_hasta=payload.validity_at,
            observacion=payload.notes_text,
            estado=payload.target_state,
        )
        action_key = "save_quote_draft" if _state_value(payload.target_state) == "BORRADOR" else "save_quote"
    else:
        quote = presupuesto_service.obtener_presupuesto(session, payload.quote_id)
        if quote is None:
            raise ValueError("No se encontro el presupuesto a actualizar.")
        quote = presupuesto_service.actualizar_presupuesto(
            session=session,
            presupuesto=quote,
            usuario=usuario,
            folio=payload.folio,
            items=items,
            cliente=cliente,
            cliente_nombre=cliente.nombre if cliente is not None else None,
            cliente_telefono=cliente.telefono if cliente is not None else None,
            vigencia_hasta=payload.validity_at,
            observacion=payload.notes_text,
            estado=payload.target_state,
        )
        action_key = "update_quote_draft" if _state_value(payload.target_state) == "BORRADOR" else "emit_quote"

    session.flush()
    return QuoteSaveResult(
        quote_id=int(quote.id),
        folio=str(quote.folio),
        status_label=str(quote.estado.value),
        action_key=action_key,
    )


def _resolve_quote_editor_dependencies():
    from pos_uniformes.database.models import Cliente, Usuario
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return Usuario, Cliente, PresupuestoService


def _state_value(state: object) -> str:
    return str(getattr(state, "value", state)).strip().upper()


def _detail_school_name(detail: object) -> str:
    variant = getattr(detail, "variante", None)
    product = getattr(variant, "producto", None)
    school = getattr(product, "escuela", None)
    school_name = getattr(school, "nombre", None)
    return str(school_name or "General")


def _detail_education_level_name(detail: object) -> str:
    variant = getattr(detail, "variante", None)
    product = getattr(variant, "producto", None)
    level = getattr(product, "nivel_educativo", None)
    level_name = getattr(level, "nombre", None)
    return str(level_name or "Sin nivel")
