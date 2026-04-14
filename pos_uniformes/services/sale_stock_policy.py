"""Politica temporal del bloqueo por stock en ventas."""

from __future__ import annotations

TEMPORARY_SALE_STOCK_GUARD_ENABLED = False


def sale_stock_guard_enabled() -> bool:
    """Control central para reactivar el bloqueo cuando vuelva a ser deseado."""
    return TEMPORARY_SALE_STOCK_GUARD_ENABLED


def allow_negative_sale_stock() -> bool:
    return not sale_stock_guard_enabled()
