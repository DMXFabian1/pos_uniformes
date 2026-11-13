"""Hojas 06 y 07 del export de Analítica, desde la Libreta (2026-11-12).

Daniel (2026-11-12): «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». El resumen del
archivo ya venía de la Libreta, pero «06_ventas» y «07_detalle_ventas» se
armaban con la tabla `venta` de la Caja antigua y llegaban vacías o con lo
de abril: el archivo contradecía la pantalla.

Ahora salen de `libreta_venta`, con los mismos nombres de hoja:

- **06_ventas**: una fila por operación de la Libreta del periodo (venta,
  apartado, abono…), con su tipo y si cuenta como operación
  (`libreta_service.cuenta_como_operacion`), para que quien lo abra pueda
  separar el dinero real de los apartados. Las anuladas no salen: se borran
  de la Libreta.
- **07_detalle_ventas**: una fila por línea de producto guardada en
  `detalle` (los abonos no traen prendas).

El export lo usa el dueño en el POS: incluye las operaciones privadas.
"""

from __future__ import annotations

from decimal import Decimal

_CENT = Decimal("0.01")


def _d(valor) -> Decimal:
    try:
        return Decimal(str(valor if valor is not None else 0)).quantize(_CENT)
    except Exception:  # noqa: BLE001 — dato raro: no tumba el export
        return Decimal("0.00")


def filas_ventas(rows) -> list[dict[str, object]]:
    """Hoja 06_ventas: una fila por operación de la Libreta (puro)."""
    from pos_uniformes.services.employee_sales_history_service import folio_de_operacion
    from pos_uniformes.services.libreta_service import cuenta_como_operacion

    filas: list[dict[str, object]] = []
    for row in rows or []:
        filas.append(
            {
                "operacion_id": row.id,
                "folio": folio_de_operacion(row),
                "tipo": str(getattr(row, "tipo", None) or "venta"),
                "cuenta_como_operacion": cuenta_como_operacion(row),
                "fecha": getattr(row, "created_at", None),
                "empleada_codigo": getattr(row, "employee_code", None),
                "empleada": getattr(row, "employee_name", None),
                "cliente_id": getattr(row, "cliente_id", None),
                "cliente": str(getattr(row, "cliente", None) or "").strip() or "Mostrador",
                "piezas": int(getattr(row, "piezas", 0) or 0),
                "monto_total": _d(getattr(row, "monto_total", None)),
                "monto_neto": _d(getattr(row, "monto_neto", None)),
                "monto_monedero": _d(getattr(row, "monto_monedero", None)),
                "pago_tarjeta": bool(getattr(row, "pago_tarjeta", False)),
                "privado": bool(getattr(row, "privado", False)),
                "compra_empleada": bool(getattr(row, "descuento_empleada", False)),
                "origen": getattr(row, "origen", None),
            }
        )
    return filas


def filas_detalle(rows) -> list[dict[str, object]]:
    """Hoja 07_detalle_ventas: una fila por línea de producto (puro)."""
    from pos_uniformes.services.employee_sales_history_service import folio_de_operacion

    filas: list[dict[str, object]] = []
    for row in rows or []:
        for linea in getattr(row, "detalle", None) or ():
            if not isinstance(linea, dict):
                continue
            cantidad = int(linea.get("cantidad") or 0)
            precio = _d(linea.get("precio"))
            subtotal = (
                _d(linea.get("subtotal")) if linea.get("subtotal") is not None else (precio * cantidad).quantize(_CENT)
            )
            filas.append(
                {
                    "operacion_id": row.id,
                    "folio": folio_de_operacion(row),
                    "tipo": str(getattr(row, "tipo", None) or "venta"),
                    "cliente": str(getattr(row, "cliente", None) or "").strip() or "Mostrador",
                    "sku": str(linea.get("sku") or "").strip() or None,
                    "producto": str(linea.get("nombre") or "").strip() or None,
                    "talla": str(linea.get("talla") or "").strip() or None,
                    "cantidad": cantidad,
                    "precio_unitario": precio,
                    "subtotal_linea": subtotal,
                }
            )
    return filas


def cargar(session, desde, hasta, *, cliente_id=None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """(06_ventas, 07_detalle_ventas) del periodo [desde, hasta), en orden de
    hora; con `cliente_id`, solo las de ese cliente."""
    from sqlalchemy import select

    from pos_uniformes.database.models import LibretaVenta

    stmt = (
        select(LibretaVenta)
        .where(LibretaVenta.created_at >= desde, LibretaVenta.created_at < hasta)
        .order_by(LibretaVenta.created_at.asc(), LibretaVenta.id.asc())
    )
    if cliente_id not in (None, ""):
        stmt = stmt.where(LibretaVenta.cliente_id == int(cliente_id))
    rows = list(session.scalars(stmt).all())
    return filas_ventas(rows), filas_detalle(rows)
