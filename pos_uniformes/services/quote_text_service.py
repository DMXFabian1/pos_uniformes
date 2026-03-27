"""Render textual reutilizable para presupuestos."""

from __future__ import annotations

from decimal import Decimal
from textwrap import wrap

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime

QUOTE_TERMS_WRAP_WIDTH = 38

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
    lines = [
        business_name or "POS Uniformes",
        "Presupuesto",
        "=" * 40,
        f"Folio: {quote.folio}",
        f"Estado: {quote.estado.value}",
        f"Cliente: {quote.cliente_nombre or (quote.cliente.nombre if quote.cliente else 'Mostrador / sin cliente')}",
    ]

    phone_text = quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")
    if phone_text:
        lines.append(f"Telefono: {phone_text}")
    if getattr(quote, "created_at", None) is not None:
        lines.append(f"Fecha: {format_display_datetime(quote.created_at)}")
    if quote.vigencia_hasta is not None:
        lines.append(f"Vigencia: {format_display_date(quote.vigencia_hasta)}")
    if business_phone:
        lines.append(f"Negocio tel: {business_phone}")
    if business_address:
        lines.append(f"Direccion: {business_address}")

    lines.append("-" * 40)
    lines.append("Piezas")
    for detail in quote.detalles:
        subtotal = Decimal(detail.subtotal_linea).quantize(Decimal("0.01"))
        unit_price = Decimal(detail.precio_unitario).quantize(Decimal("0.01"))
        lines.append(str(detail.descripcion_snapshot))
        lines.append(
            f"{detail.sku_snapshot} | {detail.cantidad} x {unit_price} = {subtotal}"
        )
        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    lines.append("-" * 40)
    lines.append(f"Total estimado: {Decimal(quote.total).quantize(Decimal('0.01'))}")
    if quote.observacion:
        lines.append("Observaciones:")
        lines.append(str(quote.observacion))
    lines.append("")
    lines.append("Terminos y condiciones")
    lines.extend(_build_wrapped_quote_terms_lines())
    if ticket_footer:
        lines.append("")
        lines.append(ticket_footer)

    return "\n".join(lines).strip()


def _build_wrapped_quote_terms_lines() -> list[str]:
    wrapped_lines: list[str] = []
    for raw_line in DEFAULT_QUOTE_TERMS_LINES:
        if not raw_line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(wrap(raw_line, width=QUOTE_TERMS_WRAP_WIDTH, break_long_words=False))
    return wrapped_lines
