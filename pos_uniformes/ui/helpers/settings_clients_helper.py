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


# 2026-11-12: se quitó `build_settings_clients_view`, la lista vieja con
# columnas Nivel y Desc. (sin uso desde E1-C3). Mostraba el nivel viejo, que
# se retiró («el nivel viejo retíralo», Daniel).


def build_settings_clients_error_view(error_message: str) -> SettingsClientsView:
    return SettingsClientsView(
        status_label=f"No se pudieron cargar clientes: {error_message}",
        rows=(),
    )


# -- E1-C3: lista del ADMIN sobre el modelo nuevo -------------------------------
# Sin columnas de Nivel ni Desc. (D5). La columna 1 conserva el id del cliente
# para la seleccion, como antes.

CLIENTES_ADMIN_COLUMNAS = (
    "Codigo",
    "Cliente",
    "Tipo",
    "Telefono",
    "Origen",
    "Alta",
    "QR",
    "Credencial",
    "Estado",
    "Programa",  # E4-D: antes de Notas, para no mover las columnas de E1-C
    "Notas",
)
COLUMNA_QR = 6
COLUMNA_CREDENCIAL = 7
COLUMNA_ESTADO = 8


@dataclass(frozen=True)
class ClienteAdminRowView:
    client_id: int
    client_code: str
    values: tuple[str, ...]
    qr_tone: str
    card_tone: str
    status_tone: str


@dataclass(frozen=True)
class ClientesAdminView:
    status_label: str
    rows: tuple[ClienteAdminRowView, ...]


def build_clientes_admin_view(clients: list[dict[str, object]], *, estado_label: str = "") -> ClientesAdminView:
    sufijo = f" ({estado_label.lower()})" if estado_label else ""
    return ClientesAdminView(
        status_label=f"Clientes{sufijo}: {len(clients)}",
        rows=tuple(
            ClienteAdminRowView(
                client_id=int(c["id"]),
                client_code=str(c["code"]),
                values=(
                    str(c["code"]),
                    str(c["name"]),
                    str(c["tipo"] or "Sin tipo"),
                    str(c["phone"]),
                    str(c["origen"]),
                    str(c["alta"]),
                    str(c["qr_label"]),
                    str(c["card_label"]),
                    str(c["status_label"]),
                    str(c.get("programa") or ""),
                    str(c["notes"]),
                ),
                qr_tone="positive" if str(c["qr_label"]) == "Listo" else "warning",
                card_tone="positive" if str(c["card_label"]) == "Lista" else "muted",
                status_tone="positive" if str(c["status_label"]) == "ACTIVO" else "muted",
            )
            for c in clients
        ),
    )
