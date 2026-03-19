"""Tabla visible de metodos de pago en Analytics."""

from __future__ import annotations

from decimal import Decimal


def build_analytics_payment_rows(sales: list[object]) -> tuple[tuple[str, int, Decimal], ...]:
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

    return tuple(
        (method, int(data["count"]), Decimal(data["amount"]))
        for method, data in payment_buckets.items()
        if int(data["count"]) > 0 or Decimal(data["amount"]) > Decimal("0.00")
    )
