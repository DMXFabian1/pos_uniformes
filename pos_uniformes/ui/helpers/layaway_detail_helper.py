"""Helpers visibles para el detalle seleccionado en Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LayawayBadgeState:
    text: str
    tone: str


@dataclass(frozen=True)
class LayawayDetailLineView:
    values: tuple[object, ...]


@dataclass(frozen=True)
class LayawayPaymentLineView:
    values: tuple[object, ...]


@dataclass(frozen=True)
class LayawayDetailView:
    summary_label: str
    customer_label: str
    balance_label: str
    commitment_label: str
    due_badge: LayawayBadgeState
    notes_label: str
    detail_rows: tuple[LayawayDetailLineView, ...]
    payment_rows: tuple[LayawayPaymentLineView, ...]
    sale_ticket_enabled: bool
    whatsapp_enabled: bool


def build_empty_layaway_detail_view() -> LayawayDetailView:
    return LayawayDetailView(
        summary_label="Selecciona un apartado",
        customer_label="Sin detalle.",
        balance_label="",
        commitment_label="",
        due_badge=LayawayBadgeState(text="Sin detalle", tone="neutral"),
        notes_label="",
        detail_rows=(),
        payment_rows=(),
        sale_ticket_enabled=False,
        whatsapp_enabled=False,
    )


def build_error_layaway_detail_view(error_message: str) -> LayawayDetailView:
    return LayawayDetailView(
        summary_label="No se pudo cargar el apartado",
        customer_label=error_message,
        balance_label="",
        commitment_label="",
        due_badge=LayawayBadgeState(text="Sin detalle", tone="neutral"),
        notes_label="",
        detail_rows=(),
        payment_rows=(),
        sale_ticket_enabled=False,
        whatsapp_enabled=False,
    )


def build_layaway_detail_view(
    *,
    folio: str,
    estado: str,
    customer_code: str,
    customer_name: str,
    customer_phone: str,
    total: Decimal | str | int | float,
    total_paid: Decimal | str | int | float,
    balance_due: Decimal | str | int | float,
    commitment_label: str,
    due_text: str,
    due_tone: str,
    notes_text: str,
    detail_rows: list[dict[str, object]],
    payment_rows: list[dict[str, object]],
    sale_ticket_enabled: bool,
    whatsapp_enabled: bool,
) -> LayawayDetailView:
    customer_parts = [customer_code, customer_name, customer_phone or "Sin telefono"]
    return LayawayDetailView(
        summary_label=f"{folio} | {estado}",
        customer_label=" | ".join(part for part in customer_parts if part),
        balance_label=(
            f"Total ${Decimal(total)} | Abonado ${Decimal(total_paid)} | Saldo ${Decimal(balance_due)}"
        ),
        commitment_label=f"Compromiso: {commitment_label}",
        due_badge=LayawayBadgeState(text=due_text, tone=due_tone),
        notes_label=notes_text or "Sin observaciones.",
        detail_rows=tuple(
            LayawayDetailLineView(
                values=(
                    row["sku"],
                    row["product_name"],
                    row["quantity"],
                    row["unit_price"],
                    row["subtotal"],
                )
            )
            for row in detail_rows
        ),
        payment_rows=tuple(
            LayawayPaymentLineView(
                values=(
                    row["created_at"],
                    row["amount"],
                    row["reference"],
                    row["username"],
                )
            )
            for row in payment_rows
        ),
        sale_ticket_enabled=sale_ticket_enabled,
        whatsapp_enabled=whatsapp_enabled,
    )
