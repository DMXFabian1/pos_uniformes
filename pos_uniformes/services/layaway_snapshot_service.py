"""Carga el snapshot base del listado de Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class LayawaySnapshotRow:
    layaway_id: int
    folio: str
    customer_label: str
    estado: str
    total: Decimal
    paid: Decimal
    balance: Decimal
    due_bucket: str
    due_text: str
    due_tone: str
    searchable: str


def load_layaway_snapshot_rows(
    session,
    *,
    today: date,
    classify_due,
) -> tuple[LayawaySnapshotRow, ...]:
    apartado_service, estado_apartado = _resolve_layaway_dependencies()
    layaways = apartado_service.listar_apartados(session)
    week_limit = today + timedelta(days=7)
    rows: list[LayawaySnapshotRow] = []
    for layaway in layaways:
        searchable = " ".join(
            [
                layaway.folio,
                layaway.cliente.codigo_cliente if layaway.cliente is not None else "",
                layaway.cliente_nombre,
                layaway.cliente_telefono or "",
            ]
        ).lower()
        due_date = layaway.fecha_compromiso.date() if layaway.fecha_compromiso else None
        due_bucket = "none"
        state_value = str(getattr(layaway.estado, "value", layaway.estado))
        closed_states = {
            str(getattr(estado_apartado.ENTREGADO, "value", estado_apartado.ENTREGADO)),
            str(getattr(estado_apartado.CANCELADO, "value", estado_apartado.CANCELADO)),
        }
        if due_date is not None and state_value not in closed_states:
            if due_date < today:
                due_bucket = "overdue"
            elif due_date == today:
                due_bucket = "today"
            elif due_date <= week_limit:
                due_bucket = "week"
        due_text, due_tone = classify_due(layaway.fecha_compromiso, layaway.estado)
        rows.append(
            LayawaySnapshotRow(
                layaway_id=int(layaway.id),
                folio=str(layaway.folio),
                customer_label=(
                    f"{layaway.cliente.codigo_cliente} · {layaway.cliente_nombre}"
                    if layaway.cliente is not None
                    else f"Manual · {layaway.cliente_nombre}"
                ),
                estado=state_value,
                total=Decimal(layaway.total),
                paid=Decimal(layaway.total_abonado),
                balance=Decimal(layaway.saldo_pendiente),
                due_bucket=due_bucket,
                due_text=str(due_text),
                due_tone=str(due_tone),
                searchable=searchable,
            )
        )
    return tuple(rows)


def build_layaway_history_input_rows(rows: list[LayawaySnapshotRow] | tuple[LayawaySnapshotRow, ...]) -> list[dict[str, object]]:
    return [
        {
            "id": row.layaway_id,
            "folio": row.folio,
            "cliente": row.customer_label,
            "estado": row.estado,
            "total": row.total,
            "abonado": row.paid,
            "saldo": row.balance,
            "due_bucket": row.due_bucket,
            "due_text": row.due_text,
            "due_tone": row.due_tone,
            "searchable": row.searchable,
        }
        for row in rows
    ]
def _resolve_layaway_dependencies():
    from pos_uniformes.database.models import EstadoApartado
    from pos_uniformes.services.apartado_service import ApartadoService

    return ApartadoService, EstadoApartado
