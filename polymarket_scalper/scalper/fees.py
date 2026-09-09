"""Modelo de comisiones de Polymarket.

Solo el taker paga. fee = shares * rate * p * (1 - p). El maker no paga nada.
La tasa real viene en `feeSchedule.rate` del mercado (Gamma). Si el mercado
tiene feesEnabled=False (geopolítica) la tasa es 0.
"""
from __future__ import annotations

from typing import Any


def taker_fee(shares: float, price: float, rate: float) -> float:
    """Comisión en USD por operar `shares` a `price` como taker."""
    if shares <= 0 or rate <= 0:
        return 0.0
    p = min(max(price, 0.0), 1.0)
    return round(shares * rate * p * (1.0 - p), 5)


def fee_rate_from_market(market: dict[str, Any], default_rate: float) -> float:
    """Extrae la tasa de fee de un objeto market de Gamma."""
    if market.get("feesEnabled") is False:
        return 0.0
    sched = market.get("feeSchedule")
    if isinstance(sched, dict) and sched.get("rate") is not None:
        try:
            return float(sched["rate"])
        except (TypeError, ValueError):
            pass
    return float(default_rate)
