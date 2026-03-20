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
    tone: str | None = None


@dataclass(frozen=True)
class LayawayPaymentLineView:
    values: tuple[object, ...]


@dataclass(frozen=True)
class LayawayDetailView:
    summary_label: str
    customer_label: str
    balance_label: str
    breakdown_label: str
    commitment_label: str
    due_badge: LayawayBadgeState
    notes_label: str
    detail_rows: tuple[LayawayDetailLineView, ...]
    payment_rows: tuple[LayawayPaymentLineView, ...]
    sale_ticket_enabled: bool
    whatsapp_enabled: bool


def _build_adjustment_detail_row(rounding_adjustment: Decimal) -> LayawayDetailLineView | None:
    if rounding_adjustment == Decimal("0.00"):
        return None
    return LayawayDetailLineView(
        values=(
            "",
            "Ajuste redondeo",
            "",
            "",
            rounding_adjustment,
        ),
        tone="warning",
    )


def build_empty_layaway_detail_view() -> LayawayDetailView:
    return LayawayDetailView(
        summary_label="Selecciona un apartado",
        customer_label="Sin detalle.",
        balance_label="",
        breakdown_label="",
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
        breakdown_label="",
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
    subtotal: Decimal | str | int | float,
    rounding_adjustment: Decimal | str | int | float,
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
    normalized_subtotal = Decimal(subtotal)
    normalized_adjustment = Decimal(rounding_adjustment)
    normalized_total = Decimal(total)
    balance_label = f"Total ${normalized_total} | Saldo ${Decimal(balance_due)}"
    breakdown_parts = [f"Subtotal ${normalized_subtotal}"]
    if normalized_adjustment != Decimal("0.00"):
        breakdown_parts.append(f"Ajuste ${normalized_adjustment}")
    breakdown_parts.append(f"Abonado ${Decimal(total_paid)}")
    detail_line_views = [
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
    ]
    adjustment_row = _build_adjustment_detail_row(normalized_adjustment)
    if adjustment_row is not None:
        detail_line_views.append(adjustment_row)
    return LayawayDetailView(
        summary_label=f"{folio} | {estado}",
        customer_label=" | ".join(part for part in customer_parts if part),
        balance_label=balance_label,
        breakdown_label=" | ".join(breakdown_parts),
        commitment_label=f"Vencimiento: {commitment_label}",
        due_badge=LayawayBadgeState(text=due_text, tone=due_tone),
        notes_label=notes_text or "Sin observaciones.",
        detail_rows=tuple(detail_line_views),
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
