"""Helpers puros para construir el comprobante HTML de apartados."""

from __future__ import annotations

from decimal import Decimal
from html import escape as _esc

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICE,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import is_deportivo_playera_variant
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


def _fmt(value: object) -> str:
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except Exception:
        return str(value)


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

    p: list[str] = []

    # — Encabezado —
    p.append(
        f'<p style="text-align:center; margin:2px 0;">'
        f'<b style="font-size:12pt;">{_esc(business_name)}</b></p>'
    )
    if business_address:
        p.append(f'<p style="text-align:center; margin:1px 0; font-size:7pt;">{_esc(business_address)}</p>')
    if business_phone:
        p.append(f'<p style="text-align:center; margin:1px 0; font-size:7pt;">Tel: {_esc(business_phone)}</p>')
    p.append('<p style="text-align:center; margin:2px 0; font-size:7pt; color:#555555;">Comprobante de apartado</p>')
    p.append('<hr/>')

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

    p.append('<table width="100%" cellspacing="0" cellpadding="1">')
    p.append(f'<tr><td><b>Folio</b></td><td align="right">{_esc(str(getattr(layaway, "folio", "")))}</td></tr>')
    if fecha_str:
        p.append(f'<tr><td><b>Fecha</b></td><td align="right">{_esc(fecha_str)}</td></tr>')
    p.append(f'<tr><td><b>Cliente</b></td><td align="right">{_esc(cliente_nombre)}</td></tr>')
    p.append(f'<tr><td><b>Vencimiento</b></td><td align="right">{_esc(vencimiento_str)}</td></tr>')
    p.append('</table>')

    # — Productos —
    p.append('<hr/>')
    p.append('<p style="margin:3px 0;"><b>PRODUCTOS</b></p>')
    p.append('<table width="100%" cellspacing="0" cellpadding="2">')
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
        detail_parts = [part for part in (f"Talla {talla}" if talla else "", f"Color {color}" if color else "") if part]
        detail_str = " · ".join(detail_parts)
        subtotal_linea = getattr(detalle, "subtotal_linea", "")
        cantidad = getattr(detalle, "cantidad", "")
        precio_unitario = getattr(detalle, "precio_unitario", "")
        p.append(
            f'<tr>'
            f'<td style="padding-bottom:0;">{_esc(str(producto))}</td>'
            f'<td align="right" style="padding-bottom:0; white-space:nowrap;"><b>${_esc(_fmt(subtotal_linea))}</b></td>'
            f'</tr>'
        )
        meta = f"{_esc(str(cantidad))} × ${_esc(_fmt(precio_unitario))}"
        if detail_str:
            meta = f"{_esc(detail_str)} &nbsp;·&nbsp; {meta}"
        p.append(
            f'<tr>'
            f'<td colspan="2" style="font-size:7pt; color:#666666; padding-top:0;">{meta}</td>'
            f'</tr>'
        )
    p.append('</table>')

    # — Totales / Saldos —
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    total_abonado = getattr(layaway, "total_abonado", "")
    saldo_pendiente = getattr(layaway, "saldo_pendiente", "")
    try:
        adjustment = Decimal(str(total)) - Decimal(str(subtotal))
    except Exception:
        adjustment = None

    p.append('<hr/>')
    p.append('<table width="100%" cellspacing="0" cellpadding="1">')
    p.append(f'<tr><td>Total</td><td align="right">${_esc(_fmt(total))}</td></tr>')
    if adjustment not in {None, Decimal("0.00"), 0}:
        p.append(f'<tr><td>Ajuste</td><td align="right">${_esc(_fmt(adjustment))}</td></tr>')
    p.append(f'<tr><td>Abonado</td><td align="right">${_esc(_fmt(total_abonado))}</td></tr>')
    p.append('</table>')
    p.append('<hr/>')
    p.append('<table width="100%" cellspacing="0" cellpadding="3">')
    p.append(
        f'<tr>'
        f'<td><b style="font-size:10pt;">SALDO PENDIENTE</b></td>'
        f'<td align="right"><b style="font-size:10pt;">${_esc(_fmt(saldo_pendiente))}</b></td>'
        f'</tr>'
    )
    p.append('</table>')

    # — Abonos —
    if abonos:
        p.append('<hr/>')
        p.append('<p style="margin:2px 0;"><b>Abonos registrados</b></p>')
        p.append('<table width="100%" cellspacing="0" cellpadding="1">')
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
                right = f"{right} · {_esc(referencia)}"
            p.append(
                f'<tr>'
                f'<td style="font-size:7pt; color:#555555;">{_esc(label)}</td>'
                f'<td align="right" style="font-size:7pt; color:#555555;">{right}</td>'
                f'</tr>'
            )
        p.append('</table>')

    # — Notas —
    observacion = _clean_customer_layaway_note(getattr(layaway, "observacion", ""))
    if observacion:
        p.append('<hr/>')
        p.append('<p style="margin:2px 0;"><b>Notas</b></p>')
        p.append(f'<p style="margin:1px 0; font-size:7pt;">{_esc(observacion)}</p>')

    # — Pie —
    p.append('<hr/>')
    p.append('<p style="text-align:center; margin:2px 0; font-size:7pt;">Por favor conserve su comprobante.</p>')
    p.append(f'<p style="text-align:center; margin:3px 0; font-size:7pt;">{_esc(ticket_footer)}</p>')

    body = "\n".join(p)
    return (
        '<html><body style="font-family: Arial, sans-serif; font-size: 8pt; margin: 4px; padding: 0;">'
        f'{body}'
        '</body></html>'
    )


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
