"""Helpers puros para listado y acciones del satelite de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteSatelliteActionState:
    resume_enabled: bool
    emit_enabled: bool
    cancel_enabled: bool
    whatsapp_enabled: bool
    print_enabled: bool


def build_quote_satellite_rows(
    *,
    quote_snapshots: list[dict[str, object]],
    search_text: str,
    state_filter: str,
) -> list[dict[str, object]]:
    normalized_search = search_text.strip().lower()
    compact_search = _normalize_search_token(search_text)
    rows: list[dict[str, object]] = []
    for snapshot in quote_snapshots:
        state_value = str(snapshot["estado"])
        if state_filter and state_value != state_filter:
            continue
        searchable = str(snapshot["searchable"]).lower()
        compact_searchable = _normalize_search_token(searchable)
        if normalized_search and normalized_search not in searchable and compact_search not in compact_searchable:
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
                "status_tone": _status_tone(state_value),
            }
        )
    return rows


def build_quote_satellite_action_state(
    *,
    can_operate: bool,
    has_selection: bool,
    selected_state: str,
    has_phone: bool,
) -> QuoteSatelliteActionState:
    normalized_state = selected_state.strip().upper()
    is_draft = normalized_state == "BORRADOR"
    is_active = normalized_state in {"BORRADOR", "EMITIDO"}
    return QuoteSatelliteActionState(
        resume_enabled=can_operate and has_selection and is_draft,
        emit_enabled=can_operate and has_selection and is_draft,
        cancel_enabled=can_operate and has_selection and is_active,
        whatsapp_enabled=has_selection and is_active and has_phone,
        print_enabled=has_selection and is_active,
    )


def _normalize_search_token(value: str) -> str:
    return "".join(character.lower() for character in str(value) if character.isalnum())


def _status_tone(state_value: str) -> str:
    return {
        "EMITIDO": "positive",
        "BORRADOR": "warning",
        "CANCELADO": "danger",
        "CONVERTIDO": "muted",
    }.get(state_value, "muted")
