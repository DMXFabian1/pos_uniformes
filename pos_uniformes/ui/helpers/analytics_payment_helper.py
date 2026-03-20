"""Tabla visible de metodos de pago en Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AnalyticsPaymentRowView:
    values: tuple[str, int, Decimal]
    sales_tone: str
    amount_tone: str
    row_tone: str | None


def build_analytics_payment_rows(sales: list[object]) -> tuple[AnalyticsPaymentRowView, ...]:
    payment_buckets: dict[str, dict[str, Decimal | int]] = {
        "Efectivo": {"count": 0, "amount": Decimal("0.00")},
        "Tarjeta": {"count": 0, "amount": Decimal("0.00")},
        "Transferencia": {"count": 0, "amount": Decimal("0.00")},
        "Mixto": {"count": 0, "amount": Decimal("0.00")},
    }
    for sale in sales:
        note = sale.observacion or ""
        method = "Efectivo"
        for candidate in payment_buckets:
            if f"Metodo de pago: {candidate}" in note:
                method = candidate
                break
        payment_buckets[method]["count"] = int(payment_buckets[method]["count"]) + 1
        payment_buckets[method]["amount"] = Decimal(payment_buckets[method]["amount"]) + Decimal(sale.total)

    visible_rows = [
        (method, int(data["count"]), Decimal(data["amount"]))
        for method, data in payment_buckets.items()
        if int(data["count"]) > 0 or Decimal(data["amount"]) > Decimal("0.00")
    ]
    return tuple(
        AnalyticsPaymentRowView(
            values=row,
            sales_tone="positive" if row_index == 0 else "warning" if row[1] > 1 else "muted",
            amount_tone="positive" if row_index == 0 else "warning" if row[2] > Decimal("0.00") else "muted",
            row_tone="positive" if row_index == 0 else None,
        )
        for row_index, row in enumerate(
            sorted(visible_rows, key=lambda item: (item[2], item[1]), reverse=True)
        )
    )
