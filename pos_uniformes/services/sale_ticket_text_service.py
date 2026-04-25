"""Helpers puros para construir el HTML de tickets de venta."""

from __future__ import annotations

from decimal import Decimal
from html import escape as _esc
import re

from pos_uniformes.services.sale_ticket_totals_service import resolve_sale_ticket_totals
from pos_uniformes.utils.date_format import format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


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


def _fmt(value: object) -> str:
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except Exception:
        return str(value)


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
    p.append('<p style="text-align:center; margin:2px 0; font-size:7pt; color:#555555;">Ticket de venta</p>')
    p.append('<hr/>')

    # — Folio / Fecha / Pago —
    p.append('<table width="100%" cellspacing="0" cellpadding="1">')
    p.append(f'<tr><td><b>Folio</b></td><td align="right">{_esc(str(getattr(sale, "folio", "")))}</td></tr>')
    p.append(f'<tr><td><b>Fecha</b></td><td align="right">{_esc(format_display_datetime(created_at))}</td></tr>')
    if payment_method:
        p.append(f'<tr><td><b>Pago</b></td><td align="right">{_esc(payment_method)}</td></tr>')
    p.append('</table>')

    # — Cliente —
    if cliente is not None:
        p.append('<hr/>')
        p.append('<table width="100%" cellspacing="0" cellpadding="1">')
        p.append(
            f'<tr><td><b>Cliente</b></td>'
            f'<td align="right">{_esc(str(getattr(cliente, "nombre", "")))}</td></tr>'
        )
        p.append(
            f'<tr><td><b>Código</b></td>'
            f'<td align="right">{_esc(str(getattr(cliente, "codigo_cliente", "")))}</td></tr>'
        )
        p.append('</table>')

    # — Artículos —
    p.append('<hr/>')
    p.append('<p style="margin:3px 0;"><b>ARTÍCULOS</b></p>')
    p.append('<table width="100%" cellspacing="0" cellpadding="2">')
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
        cantidad = getattr(detalle, "cantidad", "")
        precio_unitario = getattr(detalle, "precio_unitario", "")
        subtotal_linea = getattr(detalle, "subtotal_linea", "")
        talla = str(getattr(variante, "talla", "") or "").strip() if variante else ""
        color = str(getattr(variante, "color", "") or "").strip() if variante else ""
        meta_parts = [str(sku)]
        if talla:
            meta_parts.append(f"Talla {talla}")
        if color:
            meta_parts.append(color)
        meta_parts.append(f"{cantidad} × ${_fmt(precio_unitario)}")
        meta_str = " &nbsp;·&nbsp; ".join(_esc(part) for part in meta_parts)
        p.append(
            f'<tr>'
            f'<td style="padding-bottom:0;">{_esc(str(producto))}</td>'
            f'<td align="right" style="padding-bottom:0; white-space:nowrap;"><b>${_esc(_fmt(subtotal_linea))}</b></td>'
            f'</tr>'
        )
        p.append(
            f'<tr>'
            f'<td colspan="2" style="font-size:7pt; color:#666666; padding-top:0;">{meta_str}</td>'
            f'</tr>'
        )
    p.append('</table>')

    # — Subtotal / Descuento —
    ticket_totals = resolve_sale_ticket_totals(
        subtotal=getattr(sale, "subtotal", Decimal("0.00")),
        stored_discount_percent=getattr(sale, "descuento_porcentaje", Decimal("0.00")),
        stored_discount_amount=getattr(sale, "descuento_monto", Decimal("0.00")),
        total=getattr(sale, "total", Decimal("0.00")),
        rounding_adjustment=rounding_adjustment,
    )
    p.append('<hr/>')
    p.append('<table width="100%" cellspacing="0" cellpadding="1">')
    p.append(f'<tr><td>Subtotal</td><td align="right">${_esc(str(ticket_totals.subtotal))}</td></tr>')
    try:
        has_discount = Decimal(str(ticket_totals.discount_amount)) > Decimal("0")
    except Exception:
        has_discount = False
    if has_discount:
        p.append(
            f'<tr><td>Descuento {_esc(str(ticket_totals.discount_percent))}%</td>'
            f'<td align="right">-${_esc(str(ticket_totals.discount_amount))}</td></tr>'
        )
    if rounding_adjustment != Decimal("0.00"):
        p.append(f'<tr><td>Ajuste</td><td align="right">${_esc(str(rounding_adjustment))}</td></tr>')
    p.append('</table>')

    # — Total —
    p.append('<hr/>')
    p.append('<table width="100%" cellspacing="0" cellpadding="3">')
    p.append(
        f'<tr>'
        f'<td><b style="font-size:10pt;">TOTAL A PAGAR</b></td>'
        f'<td align="right"><b style="font-size:10pt;">${_esc(_fmt(ticket_totals.total))}</b></td>'
        f'</tr>'
    )
    p.append('</table>')

    # — Notas —
    if ticket_notes:
        p.append('<hr/>')
        p.append('<p style="margin:2px 0;"><b>Notas</b></p>')
        for note in ticket_notes:
            p.append(f'<p style="margin:1px 0; font-size:7pt;">• {_esc(note)}</p>')

    # — Pie —
    p.append('<hr/>')
    p.append(f'<p style="text-align:center; margin:3px 0; font-size:7pt;">{_esc(ticket_footer)}</p>')

    body = "\n".join(p)
    return (
        '<html><body style="font-family: Arial, sans-serif; font-size: 8pt; margin: 4px; padding: 0;">'
        f'{body}'
        '</body></html>'
    )
