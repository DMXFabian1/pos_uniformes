"""Listado visible de ventas recientes para la UI."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import desc, select

from pos_uniformes.database.models import Venta


@dataclass(frozen=True)
class RecentSaleRow:
    sale_id: int
    values: tuple[object, object, object, object, object, Decimal, object]


def list_recent_sale_rows(session, *, limit: int = 20) -> tuple[RecentSaleRow, ...]:
    sales = session.scalars(select(Venta).order_by(desc(Venta.created_at)).limit(limit)).all()
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
                    sale.created_at.strftime("%Y-%m-%d %H:%M") if sale.created_at else "",
                ),
            )
        )
    return tuple(rows)
