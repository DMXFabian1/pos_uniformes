"""Render textual reutilizable para presupuestos."""

from __future__ import annotations

import textwrap
from decimal import Decimal

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
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime

_IW = _W - 4

DEFAULT_QUOTE_TERMS_LINES = (
    "1. Validez del Presupuesto",
    "Los precios son vigentes al momento de emision y pueden cambiar sin previo aviso. No garantizan disponibilidad del producto. Valido por 7 dias naturales salvo indicacion contraria.",
    "",
    "2. Condiciones de Pago",
    "Este ticket no asegura reserva del producto. Se requiere confirmacion o anticipo para garantizar precio y disponibilidad.",
    "",
    "3. Promociones",
    "Por la alta demanda previa al inicio de clases, los padres que compren en julio de 2026 recibiran un descuento al registrarse en Maximoda. Valido solo del 1 al 31 de julio, sujeto a disponibilidad.",
    "",
    "Contamos con sistema de apartado, con solo un 25% del valor total, asegure sus uniformes, ahorre y obtenga las tallas que necesita sin complicaciones.",
)


def build_quote_text(
    *,
    quote,
    business_name: str = "POS Uniformes",
    business_phone: str = "",
    business_address: str = "",
    ticket_footer: str = "",
) -> str:
    lines: list[str] = []

    # — Encabezado —
    lines.append((business_name or "POS Uniformes").center(_W))
    if business_address:
        lines.append(business_address.center(_W))
    if business_phone:
        lines.append(f"Tel: {business_phone}".center(_W))
    lines.append("Presupuesto".center(_W))
    lines.append("")
    lines.append("ESTE NO ES UN COMPROBANTE".center(_W))
    lines.append("FISCAL NI DE COMPRA".center(_W))
    lines.append("Precios solo de referencia".center(_W))

    # — Datos —
    cliente_nombre = (
        quote.cliente_nombre
        or (quote.cliente.nombre if quote.cliente else "Mostrador / sin cliente")
    )
    phone_text = quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")

    lines.append(tk_top())
    tk_field("Folio:", str(quote.folio), lines)
    tk_field("Estado:", str(quote.estado.value), lines)
    tk_field("Cliente:", str(cliente_nombre), lines)
    if phone_text:
        tk_field("Telefono:", str(phone_text), lines)
    if getattr(quote, "created_at", None) is not None:
        tk_field("Fecha:", format_display_datetime(quote.created_at), lines)
    if quote.vigencia_hasta is not None:
        tk_field("Vigencia:", format_display_date(quote.vigencia_hasta), lines)

    # — Piezas —
    lines.append(tk_mid())
    lines.append(tk_center("PIEZAS"))
    lines.append(tk_mid())
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    sorted_detalles = sorted(
        quote.detalles,
        key=lambda d: _tariff_product_sort_key(
            d.variante.producto.tipo_pieza.nombre
            if d.variante and d.variante.producto and d.variante.producto.tipo_pieza
            else ""
        ),
    )
    first_detail = True
    for detail in sorted_detalles:
        subtotal = tk_fmt(detail.subtotal_linea)
        unit_price = tk_fmt(detail.precio_unitario)
        talla = str(detail.talla_snapshot or "").strip()
        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(str(detail.descripcion_snapshot), width=_IW) or [str(detail.descripcion_snapshot)]:
            lines.append(tk_line(dl))
        if talla and talla != "-":
            lines.append(tk_line(f"Talla: {talla}"))
        tk_product_price(f"{detail.cantidad} x ${unit_price}", f"${subtotal}", lines)

    # — Total —
    lines.append(tk_dbl())
    lines.append(tk_row("PRESUPUESTO ESTIMADO:", f"${tk_fmt(quote.total)}"))
    lines.append(tk_bot())

    # — Observaciones —
    if quote.observacion:
        lines.append("")
        lines.append("Observaciones:")
        lines.extend(textwrap.wrap(str(quote.observacion), width=_W))

    # — Términos —
    lines.append("")
    lines.append("Terminos y condiciones")
    lines.append("─" * _W)
    all_terms = list(DEFAULT_QUOTE_TERMS_LINES)
    promo_line = all_terms.pop() if all_terms else ""
    for term_line in all_terms:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])
    if promo_line:
        lines.append("")
        lines.append("─" * _W)
        for wrapped in textwrap.wrap(promo_line, width=_W):
            lines.append(wrapped.center(_W))

    # — Pie —
    if ticket_footer:
        lines.append("")
        lines.append(ticket_footer.center(_W))

    return "\n".join(lines)
