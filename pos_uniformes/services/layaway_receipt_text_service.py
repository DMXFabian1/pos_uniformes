"""Helpers puros para construir el comprobante textual de apartados."""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICE,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import is_deportivo_playera_variant
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
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    try:
        adjustment = total - subtotal
    except Exception:
        adjustment = None
    lines.extend(
        [
            "",
            f"Total: {_format_amount(getattr(layaway, 'total', ''))}",
        ]
    )
    if adjustment not in {None, 0}:
        lines.append(f"Ajuste: {_format_amount(adjustment)}")
    lines.extend(
        [
            f"Abonado: {_format_amount(getattr(layaway, 'total_abonado', ''))}",
            f"Saldo pendiente: {_format_amount(getattr(layaway, 'saldo_pendiente', ''))}",
        ]
    )
    if abonos:
        lines.extend(["", "Abonos:"])
        for abono in abonos:
            lines.append(_format_layaway_payment_line(abono))
    observacion = _clean_customer_layaway_note(getattr(layaway, "observacion", ""))
    if observacion:
        lines.extend(["", f"Notas: {observacion}"])
    lines.extend(["", "Por favor conserve su comprobante.", ticket_footer])
    return "\n".join(lines)


def _format_layaway_product_line(detalle, variante) -> str:
    producto = (
        sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", ""))
        if variante
        else ""
    )
    if variante is not None and _is_three_piece_playera_detail(detalle, variante):
        school_name = str(getattr(getattr(getattr(variante, "producto", None), "escuela", None), "nombre", "") or "").strip()
        label = f"{THREE_PIECE_PLAYERA_PRICING_LABEL} - {school_name}" if school_name else THREE_PIECE_PLAYERA_PRICING_LABEL
        producto = f"{producto} ({label})"
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


def _is_three_piece_playera_detail(detalle, variante) -> bool:
    try:
        unit_price = Decimal(getattr(detalle, "precio_unitario", "0.00")).quantize(Decimal("0.01"))
    except Exception:
        return False
    return unit_price == THREE_PIECE_PLAYERA_PRICE and is_deportivo_playera_variant(variante)
