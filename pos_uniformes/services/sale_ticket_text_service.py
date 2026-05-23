"""Helpers puros para construir el texto de tickets de venta."""

from __future__ import annotations

import textwrap
from decimal import Decimal
import re

from pos_uniformes.services.sale_ticket_totals_service import resolve_sale_ticket_totals
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
from pos_uniformes.utils.date_format import format_display_datetime
from pos_uniformes.utils.product_name import build_ticket_product_name, sanitize_product_display_name

_IW = _W - 4


def _strike(text: str) -> str:
    """Aplica tachado Unicode (U+0336) a cada carácter."""
    return "".join(c + "̶" for c in text)


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

    lines: list[str] = []

    # — Encabezado —
    lines.append(business_name.center(_W))
    if business_address:
        lines.append(business_address.center(_W))
    if business_phone:
        lines.append(f"Tel: {business_phone}".center(_W))
    lines.append("Ticket de venta".center(_W))

    # — Datos —
    lines.append(tk_top())
    tk_field("Folio:", str(getattr(sale, "folio", "")), lines)
    tk_field("Fecha:", format_display_datetime(created_at), lines)
    if payment_method:
        tk_field("Pago:", payment_method, lines)

    # — Cliente —
    if cliente is not None:
        lines.append(tk_mid())
        tk_field("Cliente:", str(getattr(cliente, "nombre", "")), lines)
        tk_field("Codigo:", str(getattr(cliente, "codigo_cliente", "")), lines)

    # — Artículos —
    lines.append(tk_mid())
    lines.append(tk_center("ARTICULOS"))
    lines.append(tk_mid())
    first_detail = True
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        producto_obj = getattr(variante, "producto", None) if variante else None
        producto = (
            build_ticket_product_name(producto_obj)
            if producto_obj
            else str(getattr(detalle, "descripcion_snapshot", "") or "").strip()
        )
        sku = (
            getattr(variante, "sku", "")
            if variante
            else str(getattr(detalle, "sku_snapshot", "") or "").strip()
        )
        talla = str(getattr(variante, "talla", "") or "").strip() if variante else ""
        cantidad = getattr(detalle, "cantidad", "")
        precio_unitario = getattr(detalle, "precio_unitario", "")
        subtotal_linea = tk_fmt(getattr(detalle, "subtotal_linea", ""))

        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(str(producto), width=_IW) or [str(producto)]:
            lines.append(tk_line(dl))
        if talla:
            lines.append(tk_line(f"Talla: {talla}"))
        # Indicar precio promo si difiere del precio normal
        precio_normal = Decimal(str(getattr(variante, "precio_venta", 0))) if variante else None
        try:
            precio_unit_dec = Decimal(str(precio_unitario))
        except Exception:
            precio_unit_dec = None
        if precio_normal and precio_unit_dec and precio_normal > precio_unit_dec:
            # Línea tachada con precio normal
            meta_plain = f"{cantidad} x ${tk_fmt(precio_normal)}"
            sub_plain = f"${tk_fmt(precio_normal * int(cantidad))}"
            gap = _IW - len(meta_plain) - len(sub_plain)
            inner = _strike(meta_plain) + " " * max(1, gap) + _strike(sub_plain)
            # Pad usando ancho visual (len de texto plano, no del tachado)
            visual_len = len(meta_plain) + max(1, gap) + len(sub_plain)
            pad = " " * max(0, _IW - visual_len)
            lines.append(f"│ {inner}{pad} │")
            # Línea con precio promo
            tk_product_price(f"{cantidad} x ${tk_fmt(precio_unitario)} promo 3pz", f"${subtotal_linea}", lines)
        else:
            tk_product_price(f"{cantidad} x ${tk_fmt(precio_unitario)}", f"${subtotal_linea}", lines)

    # — Totales —
    ticket_totals = resolve_sale_ticket_totals(
        subtotal=getattr(sale, "subtotal", Decimal("0.00")),
        stored_discount_percent=getattr(sale, "descuento_porcentaje", Decimal("0.00")),
        stored_discount_amount=getattr(sale, "descuento_monto", Decimal("0.00")),
        total=getattr(sale, "total", Decimal("0.00")),
        rounding_adjustment=rounding_adjustment,
    )
    lines.append(tk_mid())
    lines.append(tk_row("Subtotal:", f"${ticket_totals.subtotal}"))
    try:
        has_discount = Decimal(str(ticket_totals.discount_amount)) > Decimal("0")
    except Exception:
        has_discount = False
    if has_discount:
        lines.append(tk_row(
            f"Descuento {ticket_totals.discount_percent}%:",
            f"-${ticket_totals.discount_amount}",
        ))
    if rounding_adjustment != Decimal("0.00"):
        lines.append(tk_row("Ajuste:", f"${tk_fmt(rounding_adjustment)}"))
    lines.append(tk_dbl())
    lines.append(tk_row("TOTAL A PAGAR:", f"${tk_fmt(ticket_totals.total)}"))
    lines.append(tk_bot())

    # — Notas —
    if ticket_notes:
        lines.append("")
        lines.append("Notas:")
        for note in ticket_notes:
            lines.extend(textwrap.wrap(f"  {note}", width=_W))

    # — Pie —
    lines.append("")
    lines.append(ticket_footer.center(_W))

    return "\n".join(lines)
