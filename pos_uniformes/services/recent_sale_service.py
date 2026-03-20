"""Listado visible de ventas recientes para la UI."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_datetime


@dataclass(frozen=True)
class RecentSaleRow:
    sale_id: int
    values: tuple[object, object, object, object, object, Decimal, object]


def list_recent_sale_rows(session, *, limit: int = 20) -> tuple[RecentSaleRow, ...]:
    desc, select, venta_model = _resolve_recent_sale_dependencies()
    sales = session.scalars(select(venta_model).order_by(desc(venta_model.created_at)).limit(limit)).all()
    rows: list[RecentSaleRow] = []
    for sale in sales:
        rows.append(
            RecentSaleRow(
                sale_id=int(sale.id),
                values=(
                    sale.id,
                    sale.folio,
                    sale.cliente.nombre if sale.cliente is not None else "Mostrador",
                    sale.usuario.username if sale.usuario else "",
                    sale.estado.value,
                    Decimal(sale.total),
                    format_display_datetime(sale.created_at),
                ),
            )
        )
    return tuple(rows)


def _resolve_recent_sale_dependencies():
    from sqlalchemy import desc, select

    from pos_uniformes.database.models import Venta

    return desc, select, Venta
