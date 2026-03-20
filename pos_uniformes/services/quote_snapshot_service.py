"""Carga el snapshot base del listado de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_date, format_display_datetime


@dataclass(frozen=True)
class QuoteSnapshotRow:
    quote_id: int
    folio: str
    customer_label: str
    estado: str
    total: Decimal
    username: str
    validity_label: str
    created_at_label: str
    searchable: str


def load_quote_snapshot_rows(session, *, limit: int = 200) -> tuple[QuoteSnapshotRow, ...]:
    presupuesto_service = _resolve_quote_snapshot_dependencies()
    quotes = presupuesto_service.listar_presupuestos(session, limit=limit)
    return tuple(
        QuoteSnapshotRow(
            quote_id=int(quote.id),
            folio=str(quote.folio),
            customer_label=str(
                quote.cliente_nombre
                or (quote.cliente.nombre if quote.cliente else "Mostrador / sin cliente")
            ),
            estado=str(quote.estado.value),
            total=Decimal(quote.total),
            username=str(quote.usuario.username if quote.usuario else ""),
            validity_label=format_display_date(quote.vigencia_hasta, empty="Sin vigencia"),
            created_at_label=format_display_datetime(quote.created_at),
            searchable=" ".join(
                [
                    quote.folio,
                    quote.cliente_nombre or "",
                    quote.cliente_telefono or "",
                    " ".join(detalle.sku_snapshot for detalle in quote.detalles),
                ]
            ),
        )
        for quote in quotes
    )


def build_quote_history_input_rows(rows: list[QuoteSnapshotRow] | tuple[QuoteSnapshotRow, ...]) -> list[dict[str, object]]:
    return [
        {
            "id": row.quote_id,
            "folio": row.folio,
            "cliente": row.customer_label,
            "estado": row.estado,
            "total": row.total,
            "usuario": row.username,
            "vigencia": row.validity_label,
            "fecha": row.created_at_label,
            "searchable": row.searchable,
        }
        for row in rows
    ]


def _resolve_quote_snapshot_dependencies():
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return PresupuestoService
