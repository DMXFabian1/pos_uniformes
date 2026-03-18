"""Helpers visibles para clientes en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsClientRowView:
    client_id: int
    client_code: str
    values: tuple[object, ...]
    client_type_tone: str
    loyalty_level_tone: str
    discount_tone: str | None
    qr_tone: str
    card_tone: str
    status_tone: str


@dataclass(frozen=True)
class SettingsClientsView:
    status_label: str
    rows: tuple[SettingsClientRowView, ...]


def build_settings_clients_view(clients: list[dict[str, object]]) -> SettingsClientsView:
    return SettingsClientsView(
        status_label=f"Clientes registrados: {len(clients)}",
        rows=tuple(
            SettingsClientRowView(
                client_id=int(client["id"]),
                client_code=str(client["code"]),
                values=(
                    client["code"],
                    client["name"],
                    client["client_type"],
                    client["loyalty_level"],
                    client["discount_label"],
                    client["phone"],
                    client["notes"],
                    client["qr_label"],
                    client["card_label"],
                    client["active_label"],
                    client["updated_label"],
                ),
                client_type_tone=_client_type_tone(str(client["client_type"])),
                loyalty_level_tone=_loyalty_level_tone(str(client["loyalty_level"])),
                discount_tone="positive" if bool(client["has_discount"]) else None,
                qr_tone="positive" if str(client["qr_label"]) == "Listo" else "warning",
                card_tone="positive" if str(client["card_label"]) == "Lista" else "muted",
                status_tone="positive" if bool(client["active"]) else "muted",
            )
            for client in clients
        ),
    )


def build_settings_clients_error_view(error_message: str) -> SettingsClientsView:
    return SettingsClientsView(
        status_label=f"No se pudieron cargar clientes: {error_message}",
        rows=(),
    )


def _client_type_tone(client_type: str) -> str:
    return {
        "GENERAL": "muted",
        "PROFESOR": "positive",
        "MAYORISTA": "warning",
    }.get(client_type, "muted")


def _loyalty_level_tone(loyalty_level: str) -> str:
    return {
        "BASICO": "muted",
        "LEAL": "warning",
        "PROFESOR": "positive",
        "MAYORISTA": "warning",
    }.get(loyalty_level, "muted")
