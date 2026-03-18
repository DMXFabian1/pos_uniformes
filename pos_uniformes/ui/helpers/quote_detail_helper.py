"""Helpers visibles para el detalle seleccionado en Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteDetailLineView:
    sku: str
    description: str
    quantity: int
    unit_price: Decimal | str | int | float
    subtotal: Decimal | str | int | float


@dataclass(frozen=True)
class QuoteDetailView:
    customer_label: str
    meta_label: str
    notes_label: str
    detail_rows: list[QuoteDetailLineView]


def build_empty_quote_detail_view() -> QuoteDetailView:
    return QuoteDetailView(
        customer_label="Sin detalle.",
        meta_label="",
        notes_label="",
        detail_rows=[],
    )


def build_error_quote_detail_view(error_message: str) -> QuoteDetailView:
    return QuoteDetailView(
        customer_label="No se pudo cargar el presupuesto",
        meta_label=error_message,
        notes_label="",
        detail_rows=[],
    )


def build_quote_detail_view(
    *,
    folio: str,
    client_name: str,
    status_label: str,
    phone_text: str,
    total: Decimal | str | int | float,
    validity_label: str,
    user_label: str,
    notes_text: str,
    detail_rows: list[dict[str, object]],
) -> QuoteDetailView:
    total_decimal = Decimal(total).quantize(Decimal("0.01"))
    return QuoteDetailView(
        customer_label=f"{folio} | {client_name}",
        meta_label=" | ".join(
            [
                f"Estado {status_label}",
                f"Telefono {phone_text}",
                f"Total ${total_decimal}",
                f"Vigencia {validity_label}",
                f"Usuario {user_label}",
            ]
        ),
        notes_label=notes_text or "Sin observaciones.",
        detail_rows=[
            QuoteDetailLineView(
                sku=str(row["sku"]),
                description=str(row["description"]),
                quantity=int(row["quantity"]),
                unit_price=row["unit_price"],
                subtotal=row["subtotal"],
            )
            for row in detail_rows
        ],
    )
