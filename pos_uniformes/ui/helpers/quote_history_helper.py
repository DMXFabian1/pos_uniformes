"""Helpers visibles para el listado reciente de Presupuestos."""

from __future__ import annotations

from decimal import Decimal


def build_quote_history_rows(
    *,
    quote_snapshots: list[dict[str, object]],
    search_text: str,
    state_filter: str,
) -> list[dict[str, object]]:
    normalized_search = search_text.strip().lower()
    rows: list[dict[str, object]] = []
    for snapshot in quote_snapshots:
        state_value = str(snapshot["estado"])
        if state_filter and state_value != state_filter:
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
                "usuario": str(snapshot["usuario"]),
                "vigencia": str(snapshot["vigencia"]),
                "fecha": str(snapshot["fecha"]),
                "status_tone": _quote_status_tone(state_value),
            }
        )
    return rows


def _quote_status_tone(state_value: str) -> str:
    return {
        "EMITIDO": "positive",
        "BORRADOR": "warning",
        "CANCELADO": "danger",
        "CONVERTIDO": "muted",
    }.get(state_value, "muted")
