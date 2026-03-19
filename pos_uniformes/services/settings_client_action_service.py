"""Mutaciones y snapshots operativos para clientes en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SettingsClientPromptSnapshot:
    name: str
    client_type: str
    discount_label: str
    phone: str
    notes: str


@dataclass(frozen=True)
class SettingsClientActionResult:
    client_name: str
    client_code: str | None = None
    status_text: str | None = None
    card_path: Path | None = None
    card_error: str | None = None


def load_settings_client_prompt_snapshot(session, *, client_id: int) -> SettingsClientPromptSnapshot:
    cliente_model = _resolve_settings_client_model()
    client = session.get(cliente_model, client_id)
    if client is None:
        raise ValueError("No se encontro el cliente seleccionado.")
    return SettingsClientPromptSnapshot(
        name=str(client.nombre),
        client_type=str(client.tipo_cliente.value),
        discount_label=str(Decimal(client.descuento_preferente).quantize(Decimal("0.01"))),
        phone=str(client.telefono or ""),
        notes=str(client.notas or ""),
    )


def create_settings_client(
    session,
    *,
    admin_user_id: int,
    payload: dict[str, object],
    render_card: Callable[[object], tuple[Path | None, str | None]] | None = None,
) -> SettingsClientActionResult:
    client_service, usuario_model, tipo_cliente_enum = _resolve_settings_client_create_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    client = client_service.create_client(
        session=session,
        admin_user=admin_user,
        nombre=str(payload["nombre"]),
        tipo_cliente=tipo_cliente_enum(str(payload["tipo_cliente"])),
        descuento_preferente=Decimal(str(payload["descuento_preferente"])),
        telefono=str(payload["telefono"]),
        notas=str(payload["notas"]),
    )
    session.flush()
    card_path, card_error = render_card(client) if render_card is not None else (None, None)
    return SettingsClientActionResult(
        client_name=str(client.nombre),
        client_code=str(client.codigo_cliente),
        card_path=card_path,
        card_error=card_error,
    )


def update_settings_client(
    session,
    *,
    admin_user_id: int,
    client_id: int,
    payload: dict[str, object],
    render_card: Callable[[object], tuple[Path | None, str | None]] | None = None,
) -> SettingsClientActionResult:
    client_service, usuario_model, cliente_model, tipo_cliente_enum = _resolve_settings_client_update_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    client = session.get(cliente_model, client_id)
    if admin_user is None or client is None:
        raise ValueError("No se pudo cargar el cliente seleccionado.")
    updated_client = client_service.update_client(
        session=session,
        admin_user=admin_user,
        client=client,
        nombre=str(payload["nombre"]),
        tipo_cliente=tipo_cliente_enum(str(payload["tipo_cliente"])),
        descuento_preferente=Decimal(str(payload["descuento_preferente"])),
        telefono=str(payload["telefono"]),
        notas=str(payload["notas"]),
    )
    session.flush()
    card_path, card_error = render_card(updated_client) if render_card is not None else (None, None)
    return SettingsClientActionResult(
        client_name=str(updated_client.nombre),
        client_code=str(updated_client.codigo_cliente),
        card_path=card_path,
        card_error=card_error,
    )


def toggle_settings_client(session, *, admin_user_id: int, client_id: int) -> SettingsClientActionResult:
    client_service, usuario_model, cliente_model = _resolve_settings_client_toggle_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    client = session.get(cliente_model, client_id)
    if admin_user is None or client is None:
        raise ValueError("No se pudo cargar el cliente seleccionado.")
    updated_client = client_service.toggle_active(session, admin_user, client)
    return SettingsClientActionResult(
        client_name=str(updated_client.nombre),
        client_code=str(updated_client.codigo_cliente),
        status_text="activado" if bool(updated_client.activo) else "desactivado",
    )


def generate_settings_client_qr(session, *, client_id: int) -> SettingsClientActionResult:
    cliente_model, qr_generator = _resolve_settings_client_qr_dependencies()
    client = session.get(cliente_model, client_id)
    if client is None:
        raise ValueError("No se encontro el cliente seleccionado.")
    path = qr_generator.generate_for_client(client)
    return SettingsClientActionResult(
        client_name=str(client.nombre),
        client_code=str(client.codigo_cliente),
        card_path=Path(str(path)),
    )


def _resolve_settings_client_model():
    from pos_uniformes.database.models import Cliente

    return Cliente


def _resolve_settings_client_create_dependencies():
    from pos_uniformes.database.models import TipoCliente, Usuario
    from pos_uniformes.services.client_service import ClientService

    return ClientService, Usuario, TipoCliente


def _resolve_settings_client_update_dependencies():
    from pos_uniformes.database.models import Cliente, TipoCliente, Usuario
    from pos_uniformes.services.client_service import ClientService

    return ClientService, Usuario, Cliente, TipoCliente


def _resolve_settings_client_toggle_dependencies():
    from pos_uniformes.database.models import Cliente, Usuario
    from pos_uniformes.services.client_service import ClientService

    return ClientService, Usuario, Cliente


def _resolve_settings_client_qr_dependencies():
    from pos_uniformes.database.models import Cliente
    from pos_uniformes.utils.qr_generator import QrGenerator

    return Cliente, QrGenerator
