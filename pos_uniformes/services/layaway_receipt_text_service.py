"""Helpers puros para construir el comprobante textual de apartados."""

from __future__ import annotations

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


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

    lines = [
        business_name,
        business_phone,
        business_address,
        "",
        f"Comprobante de apartado: {getattr(layaway, 'folio', '')}",
        f"Estado: {getattr(getattr(layaway, 'estado', None), 'value', '')}",
        f"Cliente: {getattr(layaway, 'cliente_nombre', '')}",
        (
            f"Codigo cliente: {getattr(cliente, 'codigo_cliente', '')}"
            if cliente is not None
            else "Codigo cliente: Manual / sin cliente"
        ),
        f"Telefono: {getattr(layaway, 'cliente_telefono', '') or 'Sin telefono'}",
        (
            f"Fecha: {format_display_datetime(layaway.created_at)}"
            if getattr(layaway, 'created_at', None)
            else "Fecha: "
        ),
        (
            "Vencimiento: "
            + (
                format_display_date(layaway.fecha_compromiso)
                if getattr(layaway, "fecha_compromiso", None)
                else "Sin fecha"
            )
        ),
        "",
        "Presentaciones:",
    ]
    for detalle in detalles:
        variante = getattr(detalle, "variante", None)
        producto = (
            sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", ""))
            if variante
            else ""
        )
        sku = getattr(variante, "sku", "") if variante else ""
        lines.append(
            f"- {producto} | {sku} | {getattr(detalle, 'cantidad', '')} x "
            f"{getattr(detalle, 'precio_unitario', '')} = {getattr(detalle, 'subtotal_linea', '')}"
        )
    lines.extend(
        [
            "",
            f"Total: {getattr(layaway, 'total', '')}",
            f"Abonado: {getattr(layaway, 'total_abonado', '')}",
            f"Saldo pendiente: {getattr(layaway, 'saldo_pendiente', '')}",
        ]
    )
    if abonos:
        lines.extend(["", "Abonos:"])
        for abono in abonos:
            usuario = getattr(abono, "usuario", None)
            lines.append(
                f"- {format_display_datetime(abono.created_at) if getattr(abono, 'created_at', None) else ''} | "
                f"{getattr(abono, 'monto', '')} | {getattr(abono, 'referencia', '') or 'Sin referencia'} | "
                f"{getattr(usuario, 'username', '')}"
            )
    observacion = getattr(layaway, "observacion", "")
    subtotal = getattr(layaway, "subtotal", "")
    total = getattr(layaway, "total", "")
    if observacion:
        lines.extend(["", f"Notas: {observacion}"])
    try:
        adjustment = total - subtotal
    except Exception:
        adjustment = None
    if adjustment not in {None, 0}:
        lines.extend(["", f"Ajuste: {adjustment}"])
    lines.extend(["", ticket_footer, f"Copias configuradas: {ticket_copies}"])
    lines.append(f"Impresora preferida: {preferred_printer or 'Preguntar siempre'}")
    return "\n".join(lines)
