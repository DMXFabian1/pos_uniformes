"""Helpers puros para construir el texto de tickets de venta."""

from __future__ import annotations

from decimal import Decimal
import re

from pos_uniformes.services.sale_ticket_totals_service import resolve_sale_ticket_totals


def _extract_payment_method(observacion: str) -> str:
    match = re.search(r"Metodo de pago:\s*([^|]+)", observacion)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_rounding_adjustment(observacion: str) -> Decimal:
    match = re.search(r"Ajuste redondeo:\s*([^|]+)", observacion)
    if not match:
        return Decimal("0.00")
    try:
        return Decimal(match.group(1).strip()).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _extract_ticket_notes(observacion: str) -> list[str]:
    cleaned_parts: list[str] = []
    for raw_part in observacion.split("|"):
        part = raw_part.strip()
        if not part:
            continue
        if part.startswith("Metodo de pago:"):
            continue
        if part.startswith("Descuento:"):
            continue
        if part.startswith("Lealtad "):
            continue
        if part.startswith("Promocion manual:"):
            continue
        if part == "Promocion manual autorizada con codigo":
            continue
        if part.startswith("Descuento aplicado:"):
            continue
        if part.startswith("Ajuste redondeo:"):
            continue
        if part.startswith("Beneficio aplicado:"):
            cleaned_parts.append(part.replace("Beneficio aplicado:", "Beneficio:", 1).strip())
            continue
        if part in {"Referencia: Sin referencia", "Referencia transferencia: Sin referencia"}:
            continue
        cleaned_parts.append(part)
    return cleaned_parts


def build_sale_ticket_text(
    *,
    sale: object,
    business_name: str,
    business_phone: str = "",
    business_address: str = "",
    ticket_footer: str = "Gracias por tu compra.",
    preferred_printer: str = "",
    ticket_copies: int = 1,
) -> str:
    cliente = getattr(sale, "cliente", None)
    created_at = getattr(sale, "created_at", None)
    observacion = getattr(sale, "observacion", "")
    payment_method = _extract_payment_method(observacion)
    rounding_adjustment = _extract_rounding_adjustment(observacion)
    ticket_notes = _extract_ticket_notes(observacion)
    detalles = getattr(sale, "detalles", []) or []

    lines = [
        business_name,
        "Ticket de venta",
        "",
        f"Folio: {getattr(sale, 'folio', '')}",
        f"Fecha: {created_at.strftime('%Y-%m-%d %H:%M') if created_at else ''}",
        "",
    ]

    if payment_method:
        lines.append(f"Forma de pago: {payment_method}")
        lines.append("")

    if cliente is not None:
        lines.extend(
            [
                f"Cliente: {getattr(cliente, 'nombre', '')}",
                f"Codigo cliente: {getattr(cliente, 'codigo_cliente', '')}",
            ]
        )
        lines.append("")

    if business_phone:
        lines.append(f"Telefono: {business_phone}")
    if business_address:
        lines.append(f"Direccion: {business_address}")

    lines.extend(["", "Articulos"])
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        producto = getattr(getattr(variante, "producto", None), "nombre", "") if variante else ""
        sku = getattr(variante, "sku", "") if variante else ""
        lines.append(
            f"- {producto} | {sku} | {getattr(detalle, 'cantidad', '')} x "
            f"{getattr(detalle, 'precio_unitario', '')} = {getattr(detalle, 'subtotal_linea', '')}"
        )

    ticket_totals = resolve_sale_ticket_totals(
        subtotal=getattr(sale, "subtotal", Decimal("0.00")),
        stored_discount_percent=getattr(sale, "descuento_porcentaje", Decimal("0.00")),
        stored_discount_amount=getattr(sale, "descuento_monto", Decimal("0.00")),
        total=getattr(sale, "total", Decimal("0.00")),
        rounding_adjustment=rounding_adjustment,
    )
    lines.extend(
        [
            "",
            f"Subtotal: {ticket_totals.subtotal}",
            f"Descuento aplicado: {ticket_totals.discount_percent}% (-{ticket_totals.discount_amount})",
        ]
    )
    if rounding_adjustment != Decimal("0.00"):
        lines.append(f"Ajuste: {rounding_adjustment}")
    lines.append(f"Total a pagar: {ticket_totals.total}")

    if ticket_notes:
        lines.extend(["", "Notas:"])
        for note in ticket_notes:
            lines.append(f"- {note}")

    lines.extend(["", ticket_footer])
    return "\n".join(lines)
