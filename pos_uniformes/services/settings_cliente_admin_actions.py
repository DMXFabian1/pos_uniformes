"""Acciones de Configuración > Clientes sobre el modelo nuevo (E1-C1).

Sustituyen, para la pantalla del ADMIN, a `create_settings_client`,
`update_settings_client` y `toggle_settings_client`, que quedan sin uso y se
retiran en la etapa R. Ninguna toca nivel, descuento ni el enum viejo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pos_uniformes.database.models import Cliente, ClienteTipo
from pos_uniformes.services.clientes import admin_service, identidad_service
from pos_uniformes.services.settings_client_action_service import SettingsClientActionResult


def tipos_para_combo(session) -> list[tuple[str, str]]:
    return [(str(t.clave), str(t.nombre)) for t in identidad_service.tipos_activos(session)]


def cargar_ficha(session, *, client_id: int) -> dict[str, str]:
    cliente = session.get(Cliente, int(client_id))
    if cliente is None:
        raise ValueError("No se encontro el cliente seleccionado.")
    tipo = session.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    return {
        "nombre": str(cliente.nombre),
        "telefono": str(cliente.telefono or ""),
        "tipo_clave": str(tipo.clave) if tipo is not None else "",
        "notas": str(cliente.notas or ""),
        "activo": "1" if cliente.activo else "0",
        "archivado": "1" if cliente.archivado_en is not None else "0",
    }


def crear_cliente(
    session,
    *,
    admin_user_id: int,
    datos: dict[str, str],
    render_card: Callable[[object], tuple[Path | None, str | None]] | None = None,
) -> SettingsClientActionResult:
    """Alta del ADMIN. El teléfono es obligatorio (10 dígitos,
    `TelefonoInvalidoError`) y único: si ya es de otra ficha, no se crea
    (`CoincidenciasPorConfirmarError`). Daniel, 2026-11-10."""
    admin_service.exigir_admin(session, admin_user_id)
    cliente = identidad_service.dar_de_alta(
        session,
        nombre=datos.get("nombre", ""),
        telefono=datos.get("telefono"),
        origen=identidad_service.ORIGEN_POS_ADMIN,
        tipo_clave=datos.get("tipo_clave") or identidad_service.TIPO_GENERAL,
        notas=datos.get("notas"),
        usuario_id=int(admin_user_id),
        exigir_telefono_valido=True,
        revisar_duplicados=True,
    )
    card_path, card_error = render_card(cliente) if render_card is not None else (None, None)
    return SettingsClientActionResult(
        client_name=str(cliente.nombre),
        client_code=str(cliente.codigo_cliente),
        card_path=card_path,
        card_error=card_error,
    )


def editar_cliente(
    session,
    *,
    admin_user_id: int,
    client_id: int,
    datos: dict[str, str],
) -> SettingsClientActionResult:
    """Identidad y tipo, cada uno con su evento. Sin cambios, sin eventos."""
    cliente = admin_service.editar_identidad(
        session,
        cliente_id=client_id,
        usuario_id=admin_user_id,
        nombre=datos.get("nombre", ""),
        telefono=datos.get("telefono"),
        notas=datos.get("notas"),
    )
    clave = (datos.get("tipo_clave") or "").strip()
    if clave:
        cliente = admin_service.cambiar_tipo(session, cliente_id=client_id, usuario_id=admin_user_id, clave=clave)
    return SettingsClientActionResult(client_name=str(cliente.nombre), client_code=str(cliente.codigo_cliente))


def alternar_estado(session, *, admin_user_id: int, client_id: int, motivo: str) -> SettingsClientActionResult:
    cliente = session.get(Cliente, int(client_id))
    if cliente is None:
        raise ValueError("No se encontro el cliente seleccionado.")
    cliente = admin_service.cambiar_estado(
        session, cliente_id=client_id, usuario_id=admin_user_id, activo=not bool(cliente.activo), motivo=motivo
    )
    return SettingsClientActionResult(
        client_name=str(cliente.nombre),
        client_code=str(cliente.codigo_cliente),
        status_text="activado" if bool(cliente.activo) else "desactivado",
    )
