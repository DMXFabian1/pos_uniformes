"""Helpers puros para construir el comprobante de texto de apartados."""

from __future__ import annotations

import textwrap
from decimal import Decimal

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICE,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
)
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_CHAR_WIDTH as _W,
    tk_bot,
    tk_center,
    tk_dbl,
    tk_field,
    tk_fmt,
    tk_line,
    tk_mid,
    tk_product_price,
    tk_row,
    tk_top,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import is_deportivo_playera_variant
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name

_IW = _W - 4


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
    lines.append(business_name.center(_W))
    if business_address:
        lines.append(business_address.center(_W))
    if business_phone:
        lines.append(f"Tel: {business_phone}".center(_W))
    lines.append("Comprobante de apartado".center(_W))

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

    lines.append(tk_top())
    tk_field("Folio:", str(getattr(layaway, "folio", "")), lines)
    if fecha_str:
        tk_field("Fecha:", fecha_str, lines)
    tk_field("Cliente:", cliente_nombre, lines)
    tk_field("Vencimiento:", vencimiento_str, lines)

    # — Productos —
    lines.append(tk_mid())
    lines.append(tk_center("PRODUCTOS"))
    lines.append(tk_mid())
    first_detail = True
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

        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(str(producto), width=_IW) or [str(producto)]:
            lines.append(tk_line(dl))
        meta = f"{cantidad} x ${tk_fmt(precio_unitario)}"
        if detail_str:
            meta = f"{detail_str} | {meta}"
        tk_product_price(meta, f"${tk_fmt(subtotal_linea)}", lines)

    # — Totales / Saldos —
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    total_abonado = getattr(layaway, "total_abonado", "")
    saldo_pendiente = getattr(layaway, "saldo_pendiente", "")
    try:
        adjustment = Decimal(str(total)) - Decimal(str(subtotal))
    except Exception:
        adjustment = None

    lines.append(tk_mid())
    lines.append(tk_row("Total:", f"${tk_fmt(total)}"))
    if adjustment not in {None, Decimal("0.00"), 0}:
        lines.append(tk_row("Ajuste:", f"${tk_fmt(adjustment)}"))
    lines.append(tk_row("Abonado:", f"${tk_fmt(total_abonado)}"))
    lines.append(tk_dbl())
    lines.append(tk_row("SALDO PENDIENTE:", f"${tk_fmt(saldo_pendiente)}"))
    lines.append(tk_bot())

    # — Abonos —
    if abonos:
        lines.append("")
        lines.append("Abonos registrados".center(_W))
        lines.append("─" * _W)
        for abono in abonos:
            fecha_abono = (
                format_display_datetime(abono.created_at)
                if getattr(abono, "created_at", None)
                else ""
            )
            monto_abono = tk_fmt(getattr(abono, "monto", ""))
            referencia = str(getattr(abono, "referencia", "") or "").strip()
            label = fecha_abono or "—"
            right = f"${monto_abono}"
            if referencia and referencia.casefold() != "sin referencia":
                right = f"{right} {referencia}"
            gap = _W - len(label) - len(right)
            lines.append(f"{label}{' ' * max(1, gap)}{right}")

    # — Notas —
    observacion = _clean_customer_layaway_note(getattr(layaway, "observacion", ""))
    if observacion:
        lines.append("")
        lines.append("Notas:")
        lines.extend(textwrap.wrap(observacion, width=_W))

    # — Pie —
    lines.append("")
    lines.append("Conserve su comprobante.".center(_W))
    lines.append(ticket_footer.center(_W))

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


def _is_three_piece_playera_detail(detalle, variante) -> bool:
    try:
        unit_price = Decimal(getattr(detalle, "precio_unitario", "0.00")).quantize(Decimal("0.01"))
    except Exception:
        return False
    return unit_price == THREE_PIECE_PLAYERA_PRICE and is_deportivo_playera_variant(variante)
