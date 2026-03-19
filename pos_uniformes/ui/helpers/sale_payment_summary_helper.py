"""Resumen visible del metodo de cobro en Caja."""

from __future__ import annotations


def build_sale_payment_tooltip(payment_method: str) -> str:
    normalized = (payment_method or "").strip() or "Efectivo"
    if normalized == "Transferencia":
        return "El cobro abrira una ventana con los datos bancarios y la referencia de transferencia."
    if normalized == "Mixto":
        return "El cobro abrira una ventana para capturar transferencia, efectivo y cambio."
    return "El cobro se completara en una ventana aparte para efectivo."
