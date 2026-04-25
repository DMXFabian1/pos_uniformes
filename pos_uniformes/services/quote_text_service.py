"""Render HTML reutilizable para presupuestos."""

from __future__ import annotations

from decimal import Decimal
from html import escape as _esc

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime

DEFAULT_QUOTE_TERMS_LINES = (
    "1. Validez del Presupuesto",
    "1.1. Los precios son vigentes al momento de emision y pueden cambiar sin previo aviso.",
    "1.2. No garantizan disponibilidad del producto.",
    "1.3. El presupuesto es valido por 7 dias naturales, salvo indicacion contraria.",
    "",
    "2. Condiciones de Pago",
    "2.1. Los precios no aseguran reserva del producto.",
    "2.2. Se requiere confirmacion o anticipo para garantizar precio y disponibilidad.",
    "",
    "3. Promociones",
    "3.1. Por la alta demanda previa al inicio de clases, los padres que compren en julio de 2026 recibiran un descuento.",
    "Valido solo del 1 al 31 de julio, sujeto a disponibilidad.",
)


def build_quote_text(
    *,
    quote,
    business_name: str = "POS Uniformes",
    business_phone: str = "",
    business_address: str = "",
    ticket_footer: str = "",
) -> str:
    p: list[str] = []

    # — Encabezado —
    p.append(
        f'<p style="text-align:center; margin:2px 0;">'
        f'<b style="font-size:12pt;">{_esc(business_name or "POS Uniformes")}</b></p>'
    )
    if business_address:
        p.append(f'<p style="text-align:center; margin:1px 0; font-size:7pt;">{_esc(business_address)}</p>')
    if business_phone:
        p.append(f'<p style="text-align:center; margin:1px 0; font-size:7pt;">Tel: {_esc(business_phone)}</p>')
    p.append('<p style="text-align:center; margin:2px 0; font-size:7pt; color:#555555;">Presupuesto</p>')
    p.append('<hr/>')

    # — Datos del presupuesto —
    cliente_nombre = (
        quote.cliente_nombre
        or (quote.cliente.nombre if quote.cliente else "Mostrador / sin cliente")
    )
    phone_text = quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")

    p.append('<table width="100%" cellspacing="0" cellpadding="1">')
    p.append(f'<tr><td><b>Folio</b></td><td align="right">{_esc(str(quote.folio))}</td></tr>')
    p.append(f'<tr><td><b>Estado</b></td><td align="right">{_esc(str(quote.estado.value))}</td></tr>')
    p.append(f'<tr><td><b>Cliente</b></td><td align="right">{_esc(str(cliente_nombre))}</td></tr>')
    if phone_text:
        p.append(f'<tr><td><b>Teléfono</b></td><td align="right">{_esc(str(phone_text))}</td></tr>')
    if getattr(quote, "created_at", None) is not None:
        p.append(f'<tr><td><b>Fecha</b></td><td align="right">{_esc(format_display_datetime(quote.created_at))}</td></tr>')
    if quote.vigencia_hasta is not None:
        p.append(f'<tr><td><b>Vigencia</b></td><td align="right">{_esc(format_display_date(quote.vigencia_hasta))}</td></tr>')
    p.append('</table>')

    # — Piezas —
    p.append('<hr/>')
    p.append('<p style="margin:3px 0;"><b>PIEZAS</b></p>')
    p.append('<table width="100%" cellspacing="0" cellpadding="2">')
    for detail in quote.detalles:
        subtotal = Decimal(detail.subtotal_linea).quantize(Decimal("0.01"))
        unit_price = Decimal(detail.precio_unitario).quantize(Decimal("0.01"))
        descripcion = str(detail.descripcion_snapshot)
        sku = str(detail.sku_snapshot)
        cantidad = detail.cantidad
        p.append(
            f'<tr>'
            f'<td style="padding-bottom:0;">{_esc(descripcion)}</td>'
            f'<td align="right" style="padding-bottom:0; white-space:nowrap;"><b>${_esc(str(subtotal))}</b></td>'
            f'</tr>'
        )
        p.append(
            f'<tr>'
            f'<td colspan="2" style="font-size:7pt; color:#666666; padding-top:0;">'
            f'{_esc(sku)} &nbsp;·&nbsp; {_esc(str(cantidad))} × ${_esc(str(unit_price))}'
            f'</td>'
            f'</tr>'
        )
    p.append('</table>')

    # — Total —
    p.append('<hr/>')
    p.append('<table width="100%" cellspacing="0" cellpadding="3">')
    total_str = str(Decimal(quote.total).quantize(Decimal("0.01")))
    p.append(
        f'<tr>'
        f'<td><b style="font-size:10pt;">TOTAL ESTIMADO</b></td>'
        f'<td align="right"><b style="font-size:10pt;">${_esc(total_str)}</b></td>'
        f'</tr>'
    )
    p.append('</table>')

    # — Observaciones —
    if quote.observacion:
        p.append('<hr/>')
        p.append('<p style="margin:2px 0;"><b>Observaciones</b></p>')
        p.append(f'<p style="margin:1px 0; font-size:7pt;">{_esc(str(quote.observacion))}</p>')

    # — Términos y condiciones —
    p.append('<hr/>')
    p.append('<p style="margin:2px 0;"><b>Términos y condiciones</b></p>')
    for line in DEFAULT_QUOTE_TERMS_LINES:
        if not line:
            p.append('<p style="margin:1px 0;"></p>')
        else:
            p.append(f'<p style="margin:1px 0; font-size:7pt;">{_esc(line)}</p>')

    # — Pie —
    if ticket_footer:
        p.append('<hr/>')
        p.append(f'<p style="text-align:center; margin:3px 0; font-size:7pt;">{_esc(ticket_footer)}</p>')

    body = "\n".join(p)
    return (
        '<html><body style="font-family: Arial, sans-serif; font-size: 8pt; margin: 4px; padding: 0;">'
        f'{body}'
        '</body></html>'
    )
