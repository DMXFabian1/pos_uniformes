"""Helpers puros para construir el comprobante de texto de apartados."""

from __future__ import annotations

import textwrap
from decimal import Decimal

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICE,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import is_deportivo_playera_variant
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name

_W = 38


def _fmt(value: object) -> str:
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except Exception:
        return str(value)


def _sep() -> str:
    return "─" * _W


def _center(text: str) -> str:
    return text.center(_W)


def _row(label: str, value: str) -> str:
    gap = _W - len(label) - len(value)
    return f"{label}{' ' * max(1, gap)}{value}"


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
    detalles = getattr(layaway, "detalles", []) or []
    abonos = getattr(layaway, "abonos", []) or []

    lines: list[str] = []

    # — Encabezado —
    lines.append(_center(business_name))
    if business_address:
        lines.extend(textwrap.wrap(business_address, width=_W))
    if business_phone:
        lines.append(_center(f"Tel: {business_phone}"))
    lines.append(_sep())
    lines.append(_center("Comprobante de apartado"))
    lines.append(_sep())

    # — Datos del apartado —
    fecha_str = (
        format_display_datetime(layaway.created_at)
        if getattr(layaway, "created_at", None)
        else ""
    )
    vencimiento_str = (
        format_display_date(layaway.fecha_compromiso)
        if getattr(layaway, "fecha_compromiso", None)
        else "Sin fecha"
    )
    cliente_nombre = str(getattr(layaway, "cliente_nombre", "") or "Mostrador")

    lines.append(_row("Folio:", str(getattr(layaway, "folio", ""))))
    if fecha_str:
        lines.append(_row("Fecha:", fecha_str))
    if len("Cliente:" + cliente_nombre) + 1 > _W:
        lines.append("Cliente:")
        lines.extend(textwrap.wrap(cliente_nombre, width=_W))
    else:
        lines.append(_row("Cliente:", cliente_nombre))
    lines.append(_row("Vencimiento:", vencimiento_str))
    lines.append(_sep())

    # — Productos —
    lines.append("PRODUCTOS")
    lines.append(_sep())
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        producto = (
            sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", ""))
            if variante
            else ""
        )
        if variante is not None and _is_three_piece_playera_detail(detalle, variante):
            school_name = str(
                getattr(getattr(getattr(variante, "producto", None), "escuela", None), "nombre", "") or ""
            ).strip()
            label = (
                f"{THREE_PIECE_PLAYERA_PRICING_LABEL} - {school_name}"
                if school_name
                else THREE_PIECE_PLAYERA_PRICING_LABEL
            )
            producto = f"{producto} ({label})"
        talla = str(getattr(variante, "talla", "") or "").strip()
        color = str(getattr(variante, "color", "") or "").strip()
        detail_parts = [part for part in (f"T:{talla}" if talla else "", f"C:{color}" if color else "") if part]
        detail_str = " ".join(detail_parts)

        subtotal_linea = getattr(detalle, "subtotal_linea", "")
        cantidad = getattr(detalle, "cantidad", "")
        precio_unitario = getattr(detalle, "precio_unitario", "")

        lines.append("")
        lines.extend(textwrap.wrap(str(producto), width=_W) or [str(producto)])
        meta = f"{cantidad} x ${_fmt(precio_unitario)}"
        if detail_str:
            meta = f"{detail_str} | {meta}"
        row_line = _row(meta, f"${_fmt(subtotal_linea)}")
        if len(row_line) > _W:
            lines.append(meta)
            lines.append(f"${_fmt(subtotal_linea)}".rjust(_W))
        else:
            lines.append(row_line)
    lines.append("")
    lines.append(_sep())

    # — Totales / Saldos —
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    total_abonado = getattr(layaway, "total_abonado", "")
    saldo_pendiente = getattr(layaway, "saldo_pendiente", "")
    try:
        adjustment = Decimal(str(total)) - Decimal(str(subtotal))
    except Exception:
        adjustment = None

    lines.append(_row("Total:", f"${_fmt(total)}"))
    if adjustment not in {None, Decimal("0.00"), 0}:
        lines.append(_row("Ajuste:", f"${_fmt(adjustment)}"))
    lines.append(_row("Abonado:", f"${_fmt(total_abonado)}"))
    lines.append(_sep())
    lines.append(_row("SALDO PENDIENTE:", f"${_fmt(saldo_pendiente)}"))
    lines.append(_sep())

    # — Abonos —
    if abonos:
        lines.append("Abonos registrados")
        lines.append(_sep())
        for abono in abonos:
            fecha_abono = (
                format_display_datetime(abono.created_at)
                if getattr(abono, "created_at", None)
                else ""
            )
            monto_abono = _fmt(getattr(abono, "monto", ""))
            referencia = str(getattr(abono, "referencia", "") or "").strip()
            label = fecha_abono or "—"
            right = f"${monto_abono}"
            if referencia and referencia.casefold() != "sin referencia":
                right = f"{right} {referencia}"
            lines.append(_row(label, right))
        lines.append(_sep())

    # — Notas —
    observacion = _clean_customer_layaway_note(getattr(layaway, "observacion", ""))
    if observacion:
        lines.append("Notas:")
        lines.extend(textwrap.wrap(observacion, width=_W))
        lines.append(_sep())

    # — Pie —
    lines.append(_center("Conserve su comprobante."))
    lines.append(_center(ticket_footer))

    return "\n".join(lines)


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
