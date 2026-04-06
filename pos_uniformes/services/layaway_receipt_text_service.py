"""Helpers puros para construir el comprobante textual de apartados."""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


def build_layaway_receipt_text(
    *,
    layaway: object,
    business_name: str,
    business_phone: str = "",
    business_address: str = "",
    ticket_footer: str = "Gracias por tu preferencia.",
    preferred_printer: str = "",
    ticket_copies: int = 1,
) -> str:
    cliente = getattr(layaway, "cliente", None)
    detalles = getattr(layaway, "detalles", []) or []
    abonos = getattr(layaway, "abonos", []) or []

    lines = [business_name]
    if business_address.strip():
        lines.append(business_address)
    lines.extend(
        [
            "",
            "Comprobante de apartado",
            f"Folio: {getattr(layaway, 'folio', '')}",
            (
                f"Fecha: {format_display_datetime(layaway.created_at)}"
                if getattr(layaway, "created_at", None)
                else "Fecha: "
            ),
            f"Cliente: {getattr(layaway, 'cliente_nombre', '') or 'Mostrador'}",
            (
                "Vencimiento: "
                + (
                    format_display_date(layaway.fecha_compromiso)
                    if getattr(layaway, "fecha_compromiso", None)
                    else "Sin fecha"
                )
            ),
            "",
            "Productos",
        ]
    )
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        lines.append(_format_layaway_product_line(detalle, variante))
    lines.extend(
        [
            "",
            f"Total: {_format_amount(getattr(layaway, 'total', ''))}",
            f"Abonado: {_format_amount(getattr(layaway, 'total_abonado', ''))}",
            f"Saldo pendiente: {_format_amount(getattr(layaway, 'saldo_pendiente', ''))}",
        ]
    )
    if abonos:
        lines.extend(["", "Abonos:"])
        for abono in abonos:
            lines.append(_format_layaway_payment_line(abono))
    observacion = _clean_customer_layaway_note(getattr(layaway, "observacion", ""))
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    if observacion:
        lines.extend(["", f"Notas: {observacion}"])
    try:
        adjustment = total - subtotal
    except Exception:
        adjustment = None
    if adjustment not in {None, 0}:
        lines.extend(["", f"Ajuste: {_format_amount(adjustment)}"])
    lines.extend(["", ticket_footer])
    return "\n".join(lines)


def _format_layaway_product_line(detalle, variante) -> str:
    producto = (
        sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", ""))
        if variante
        else ""
    )
    talla = str(getattr(variante, "talla", "") or "").strip()
    color = str(getattr(variante, "color", "") or "").strip()
    detail_parts = [part for part in (f"Talla {talla}" if talla else "", f"Color {color}" if color else "") if part]
    detail_suffix = f" | {' | '.join(detail_parts)}" if detail_parts else ""
    return (
        f"- {producto}{detail_suffix} | "
        f"{getattr(detalle, 'cantidad', '')} x {_format_amount(getattr(detalle, 'precio_unitario', ''))} = "
        f"{_format_amount(getattr(detalle, 'subtotal_linea', ''))}"
    )


def _format_layaway_payment_line(abono) -> str:
    parts = [
        format_display_datetime(abono.created_at) if getattr(abono, "created_at", None) else "",
        _format_amount(getattr(abono, "monto", "")),
    ]
    reference = str(getattr(abono, "referencia", "") or "").strip()
    if reference and reference.casefold() != "sin referencia":
        parts.append(reference)
    return f"- {' | '.join(part for part in parts if part)}"


def _clean_customer_layaway_note(note: object) -> str:
    parts: list[str] = []
    for raw_part in str(note or "").split("|"):
        part = raw_part.strip()
        if not part:
            continue
        lowered = part.casefold()
        if lowered in {
            "creado desde caja.",
            "creado desde caja",
            "manual / sin cliente",
        }:
            continue
        if "ambiente de pruebas" in lowered:
            continue
        if lowered.startswith("interno:"):
            continue
        parts.append(part)
    return " | ".join(parts)


def _format_amount(value: object) -> str:
    try:
        return str(Decimal(value).quantize(Decimal("0.01")))
    except Exception:
        return str(value)
