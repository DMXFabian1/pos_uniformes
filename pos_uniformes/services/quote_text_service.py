"""Render textual reutilizable para presupuestos."""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime


def build_quote_text(
    *,
    quote,
    business_name: str = "POS Uniformes",
    business_phone: str = "",
    business_address: str = "",
    ticket_footer: str = "Gracias por tu preferencia.",
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
        lines.append(
            (
                f"- {detail.descripcion_snapshot} | {detail.sku_snapshot} | "
                f"{detail.cantidad} x {unit_price} = {subtotal}"
            )
        )

    lines.append("-" * 40)
    lines.append(f"Total estimado: {Decimal(quote.total).quantize(Decimal('0.01'))}")
    if quote.observacion:
        lines.append("Observaciones:")
        lines.append(str(quote.observacion))
    if ticket_footer:
        lines.append("")
        lines.append(ticket_footer)

    return "\n".join(lines).strip()
