"""Helpers puros para construir el texto de tickets de venta."""

from __future__ import annotations

from decimal import Decimal
import re

from pos_uniformes.services.sale_ticket_totals_service import resolve_sale_ticket_totals
from pos_uniformes.utils.date_format import format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name

_W = 38  # ancho en caracteres para papel de 80 mm a 8 pt bold


def _sep(char: str = "─") -> str:
    return char * _W


def _center(text: str) -> str:
    return text.center(_W)


def _row(label: str, value: str) -> str:
    gap = _W - len(label) - len(value)
    return f"{label}{' ' * max(1, gap)}{value}"


def _fmt(value: object) -> str:
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except Exception:
        return str(value)


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
        if part.startswith("Interno:"):
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

    lines: list[str] = []

    # — Encabezado —
    lines.append(_center(business_name))
    if business_address:
        lines.append(_center(business_address))
    if business_phone:
        lines.append(_center(f"Tel: {business_phone}"))
    lines.append(_center("Ticket de venta"))
    lines.append(_sep())

    # — Folio / Fecha / Pago —
    lines.append(_row("Folio:", str(getattr(sale, "folio", ""))))
    lines.append(_row("Fecha:", format_display_datetime(created_at)))
    if payment_method:
        lines.append(_row("Pago:", payment_method))

    # — Cliente —
    if cliente is not None:
        lines.append(_sep())
        lines.append(_row("Cliente:", str(getattr(cliente, "nombre", ""))))
        lines.append(_row("Codigo:", str(getattr(cliente, "codigo_cliente", ""))))

    # — Artículos —
    lines.append(_sep())
    lines.append("ARTICULOS")
    lines.append(_sep())
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        producto = (
            sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", ""))
            if variante
            else str(getattr(detalle, "descripcion_snapshot", "") or "").strip()
        )
        sku = (
            getattr(variante, "sku", "")
            if variante
            else str(getattr(detalle, "sku_snapshot", "") or "").strip()
        )
        talla = str(getattr(variante, "talla", "") or "").strip() if variante else ""
        cantidad = getattr(detalle, "cantidad", "")
        precio_unitario = getattr(detalle, "precio_unitario", "")
        subtotal_linea = _fmt(getattr(detalle, "subtotal_linea", ""))

        lines.append("")
        lines.append(str(producto))
        meta = f"{sku}"
        if talla:
            meta += f" | Talla {talla}"
        meta += f" | {cantidad} x ${_fmt(precio_unitario)}"
        lines.append(_row(meta, f"${subtotal_linea}"))

    # — Totales —
    ticket_totals = resolve_sale_ticket_totals(
        subtotal=getattr(sale, "subtotal", Decimal("0.00")),
        stored_discount_percent=getattr(sale, "descuento_porcentaje", Decimal("0.00")),
        stored_discount_amount=getattr(sale, "descuento_monto", Decimal("0.00")),
        total=getattr(sale, "total", Decimal("0.00")),
        rounding_adjustment=rounding_adjustment,
    )
    lines.append("")
    lines.append(_sep())
    lines.append(_row("Subtotal:", f"${ticket_totals.subtotal}"))
    try:
        has_discount = Decimal(str(ticket_totals.discount_amount)) > Decimal("0")
    except Exception:
        has_discount = False
    if has_discount:
        lines.append(_row(
            f"Descuento {ticket_totals.discount_percent}%:",
            f"-${ticket_totals.discount_amount}",
        ))
    if rounding_adjustment != Decimal("0.00"):
        lines.append(_row("Ajuste:", f"${_fmt(rounding_adjustment)}"))
    lines.append(_sep())
    lines.append(_row("TOTAL A PAGAR:", f"${_fmt(ticket_totals.total)}"))
    lines.append(_sep())

    # — Notas —
    if ticket_notes:
        lines.append("Notas:")
        for note in ticket_notes:
            lines.append(f"  {note}")
        lines.append("")

    # — Pie —
    lines.append(_center(ticket_footer))

    return "\n".join(lines)
