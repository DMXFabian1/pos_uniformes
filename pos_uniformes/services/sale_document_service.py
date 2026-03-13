"""Carga y validaciones para documentos operativos de ventas y apartados."""

from __future__ import annotations

from sqlalchemy import select

from pos_uniformes.database.models import EstadoApartado, Venta
from pos_uniformes.services.apartado_service import ApartadoService


def load_sale_for_ticket(session, sale_id: int):
    sale = session.get(Venta, sale_id)
    if sale is None:
        raise ValueError("Venta no encontrada.")
    _ = [(detalle.variante.sku if detalle.variante else "") for detalle in sale.detalles]
    _ = sale.cliente.codigo_cliente if sale.cliente is not None else ""
    return sale


def load_layaway_for_receipt(session, layaway_id: int):
    layaway = ApartadoService.obtener_apartado(session, layaway_id)
    if layaway is None:
        raise ValueError("Apartado no encontrado.")
    _ = [detalle.variante.sku if detalle.variante else "" for detalle in layaway.detalles]
    _ = [abono.usuario.username if abono.usuario else "" for abono in layaway.abonos]
    return layaway


def load_sale_for_layaway_ticket(session, layaway_id: int):
    layaway = ApartadoService.obtener_apartado(session, layaway_id)
    if layaway is None:
        raise ValueError("Apartado no encontrado.")
    if layaway.estado != EstadoApartado.ENTREGADO:
        raise ValueError("El ticket de venta solo esta disponible para apartados entregados.")
    sale = session.scalar(select(Venta).where(Venta.folio == f"ENT-{layaway.folio}"))
    if sale is None:
        raise ValueError("No se encontro la venta generada para este apartado.")
    _ = [detalle.variante.sku if detalle.variante else "" for detalle in sale.detalles]
    _ = sale.cliente.codigo_cliente if sale.cliente is not None else ""
    return sale
