"""Reglas puras para enlazar clientes escaneados en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class ScannedClientDecision:
    action: str


@dataclass(frozen=True)
class ScannedClientFeedback:
    message: str
    tone: str
    auto_clear_ms: int


def decide_scanned_client_action(
    *,
    current_client_id: int | str | None,
    scanned_client_id: int | str,
    has_sale_cart: bool,
) -> ScannedClientDecision:
    normalized_current = None if current_client_id in {None, ""} else int(current_client_id)
    normalized_scanned = int(scanned_client_id)

    if normalized_current == normalized_scanned:
        return ScannedClientDecision(action="already_linked")
    if normalized_current is not None and has_sale_cart:
        return ScannedClientDecision(action="confirm_replace")
    return ScannedClientDecision(action="apply")


def build_replace_client_confirmation(
    *,
    current_label: str,
    scanned_client_code: str,
    scanned_client_name: str,
) -> str:
    normalized_current = current_label.strip() or "Cliente actual"
    return (
        f"Ya hay un cliente enlazado: {normalized_current}\n\n"
        f"Se escaneo el QR de {scanned_client_code} · {scanned_client_name}.\n"
        "Cambiar el cliente actual puede modificar el descuento aplicado.\n\n"
        "Deseas reemplazarlo?"
    )


def build_scanned_client_kept_feedback() -> str:
    return "QR de cliente detectado, pero se conservo el cliente actual."


def build_client_already_linked_feedback(client_code: str) -> str:
    return f"Cliente {client_code} ya estaba enlazado."


def build_client_linked_feedback(
    *,
    client_code: str,
    client_name: str,
    discount_label: str,
) -> str:
    return (
        f"Cliente enlazado: {client_code} · {client_name}. "
        f"Descuento vigente: {discount_label}."
    )


def build_scanned_client_applied_feedback(
    *,
    client_code: str,
    client_name: str,
    discount_percent: Decimal | str | int | float,
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> ScannedClientFeedback:
    normalized_discount = Decimal(str(discount_percent or 0)).quantize(Decimal("0.01"))
    discount_label = format_discount_label(normalized_discount) if normalized_discount > Decimal("0.00") else "0%"
    return ScannedClientFeedback(
        message=build_client_linked_feedback(
            client_code=client_code,
            client_name=client_name,
            discount_label=discount_label,
        ),
        tone="positive",
        auto_clear_ms=2200,
    )
