"""Snapshots de historial de caja para listado y detalle."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashSessionHistoryAmounts:
    expected_amount: Decimal | None
    declared_amount: Decimal | None
    difference_amount: Decimal | None


def build_cash_session_history_amounts(cash_session, *, summary) -> CashSessionHistoryAmounts:
    is_closed = getattr(cash_session, "cerrada_at", None) is not None
    if not is_closed:
        return CashSessionHistoryAmounts(
            expected_amount=None,
            declared_amount=None,
            difference_amount=None,
        )

    expected_amount = Decimal(getattr(summary, "esperado_en_caja", 0) or 0).quantize(Decimal("0.01"))
    raw_declared_amount = getattr(cash_session, "monto_cierre_declarado", None)
    if raw_declared_amount is None:
        return CashSessionHistoryAmounts(
            expected_amount=expected_amount,
            declared_amount=None,
            difference_amount=None,
        )

    declared_amount = Decimal(raw_declared_amount).quantize(Decimal("0.01"))
    difference_amount = (declared_amount - expected_amount).quantize(Decimal("0.01"))
    return CashSessionHistoryAmounts(
        expected_amount=expected_amount,
        declared_amount=declared_amount,
        difference_amount=difference_amount,
    )
