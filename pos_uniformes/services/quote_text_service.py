"""Render textual reutilizable para presupuestos."""

from __future__ import annotations

import textwrap
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime

_W = 38

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
    "Contamos con sistema de apartado, con solo un 25% del valor total, asegure sus uniformes, ahorre y obtenga las tallas que necesita sin complicaciones :)",
)


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
    lines.append(_center(business_name or "POS Uniformes"))
    if business_address:
        lines.append(_center(business_address))
    if business_phone:
        lines.append(_center(f"Tel: {business_phone}"))
    lines.append(_center("Presupuesto"))
    lines.append(_sep())
    lines.append(_center("ESTE NO ES UN COMPROBANTE"))
    lines.append(_center("FISCAL NI DE COMPRA"))
    lines.append(_center("Precios solo de referencia"))
    lines.append(_sep())

    # — Datos —
    cliente_nombre = (
        quote.cliente_nombre
        or (quote.cliente.nombre if quote.cliente else "Mostrador / sin cliente")
    )
    phone_text = quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")

    lines.append(_row("Folio:", str(quote.folio)))
    lines.append(_row("Estado:", str(quote.estado.value)))
    lines.append(_row("Cliente:", str(cliente_nombre)))
    if phone_text:
        lines.append(_row("Telefono:", str(phone_text)))
    if getattr(quote, "created_at", None) is not None:
        lines.append(_row("Fecha:", format_display_datetime(quote.created_at)))
    if quote.vigencia_hasta is not None:
        lines.append(_row("Vigencia:", format_display_date(quote.vigencia_hasta)))

    # — Piezas —
    lines.append(_sep())
    lines.append("PIEZAS")
    lines.append(_sep())
    for detail in quote.detalles:
        subtotal = _fmt(detail.subtotal_linea)
        unit_price = _fmt(detail.precio_unitario)
        talla = str(detail.talla_snapshot or "").strip()
        lines.append("")
        lines.append(str(detail.descripcion_snapshot))
        if talla and talla != "-":
            lines.append(f"Talla: {talla}")
        lines.append(_row(
            f"{detail.sku_snapshot} | {detail.cantidad} x ${unit_price}",
            f"${subtotal}",
        ))

    # — Total —
    lines.append("")
    lines.append(_sep())
    lines.append(_row("TOTAL ESTIMADO:", f"${_fmt(quote.total)}"))
    lines.append(_sep())

    # — Observaciones —
    if quote.observacion:
        lines.append("Observaciones:")
        lines.append(str(quote.observacion))
        lines.append("")

    # — Términos —
    lines.append("Terminos y condiciones")
    lines.append(_sep())
    for term_line in DEFAULT_QUOTE_TERMS_LINES:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])

    # — Pie —
    if ticket_footer:
        lines.append("")
        lines.append(_center(ticket_footer))

    return "\n".join(lines)
