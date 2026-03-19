"""Helpers puros para construir el comprobante textual de apartados."""

from __future__ import annotations

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
            f"Fecha: {layaway.created_at.strftime('%Y-%m-%d %H:%M')}"
            if getattr(layaway, 'created_at', None)
            else "Fecha: "
        ),
        (
            "Compromiso: "
            + (
                layaway.fecha_compromiso.strftime("%Y-%m-%d")
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
                f"- {abono.created_at.strftime('%Y-%m-%d %H:%M') if getattr(abono, 'created_at', None) else ''} | "
                f"{getattr(abono, 'monto', '')} | {getattr(abono, 'referencia', '') or 'Sin referencia'} | "
                f"{getattr(usuario, 'username', '')}"
            )
    observacion = getattr(layaway, "observacion", "")
    if observacion:
        lines.extend(["", f"Notas: {observacion}"])
    lines.extend(["", ticket_footer, f"Copias configuradas: {ticket_copies}"])
    lines.append(f"Impresora preferida: {preferred_printer or 'Preguntar siempre'}")
    return "\n".join(lines)
