"""Helpers visibles para el listado reciente de Presupuestos."""

from __future__ import annotations

from datetime import datetime, timezone
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
        is_expired = _is_quote_expired(state_value, snapshot.get("vigencia_raw"))
        display_state = "VENCIDO" if is_expired else state_value
        if state_filter and display_state != state_filter:
            continue
        searchable = str(snapshot["searchable"]).lower()
        if normalized_search and normalized_search not in searchable:
            continue
        rows.append(
            {
                "id": int(snapshot["id"]),
                "folio": str(snapshot["folio"]),
                "cliente": str(snapshot["cliente"]),
                "estado": display_state,
                "total": Decimal(snapshot["total"]),
                "usuario": str(snapshot["usuario"]),
                "vigencia": str(snapshot["vigencia"]),
                "fecha": str(snapshot["fecha"]),
                "status_tone": _quote_status_tone(display_state),
            }
        )
    return rows


def _quote_status_tone(state_value: str) -> str:
    return {
        "EMITIDO": "positive",
        "BORRADOR": "warning",
        "CANCELADO": "danger",
        "CONVERTIDO": "muted",
        "VENCIDO": "danger",
    }.get(state_value, "muted")


def _is_quote_expired(state_value: str, vigencia_raw: object) -> bool:
    if state_value != "EMITIDO" or vigencia_raw is None:
        return False
    try:
        dt = vigencia_raw if isinstance(vigencia_raw, datetime) else datetime.fromisoformat(str(vigencia_raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < datetime.now(tz=timezone.utc)
    except Exception:
        return False
