"""Helpers visibles para el listado reciente de Apartados."""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.database.models import EstadoApartado


def build_layaway_history_rows(
    *,
    layaway_snapshots: list[dict[str, object]],
    search_text: str,
    state_filter: str,
    due_filter: str,
) -> list[dict[str, object]]:
    normalized_search = search_text.strip().lower()
    rows: list[dict[str, object]] = []
    for snapshot in layaway_snapshots:
        state_value = str(snapshot["estado"])
        if state_filter and state_value != state_filter:
            continue
        if due_filter and str(snapshot["due_bucket"]) != due_filter:
            continue
        searchable = str(snapshot["searchable"]).lower()
        if normalized_search and normalized_search not in searchable:
            continue
        rows.append(
            {
                "id": int(snapshot["id"]),
                "folio": str(snapshot["folio"]),
                "cliente": str(snapshot["cliente"]),
                "estado": state_value,
                "total": Decimal(snapshot["total"]),
                "abonado": Decimal(snapshot["abonado"]),
                "saldo": Decimal(snapshot["saldo"]),
                "due_text": str(snapshot["due_text"]),
                "due_tone": str(snapshot["due_tone"]),
                "status_tone": _layaway_status_tone(state_value),
            }
        )
    return rows


def _layaway_status_tone(state_value: str) -> str:
    return {
        EstadoApartado.ACTIVO.value: "warning",
        EstadoApartado.LIQUIDADO.value: "positive",
        EstadoApartado.ENTREGADO.value: "muted",
        EstadoApartado.CANCELADO.value: "danger",
    }.get(state_value, "muted")
