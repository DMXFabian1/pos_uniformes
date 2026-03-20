"""Acciones operativas de marketing en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.date_format import format_display_datetime


@dataclass(frozen=True)
class SettingsMarketingRecalculationResult:
    total: int
    changed: int


def recalculate_settings_loyalty_levels(session, *, admin_user_id: int) -> SettingsMarketingRecalculationResult:
    loyalty_service, usuario_model = _resolve_settings_marketing_recalc_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    summary = loyalty_service.recalculate_all_clients(
        session,
        actor_user=admin_user,
        reason="recalculo_manual_marketing",
    )
    return SettingsMarketingRecalculationResult(
        total=int(summary["total"]),
        changed=int(summary["changed"]),
    )


def load_settings_marketing_history_rows(session, *, limit: int = 120) -> list[dict[str, str]]:
    marketing_audit_service = _resolve_settings_marketing_history_dependencies()
    changes = marketing_audit_service.list_recent(session, limit=limit)
    return [
        {
            "created_at_label": format_display_datetime(change.created_at),
            "username": change.usuario.username if change.usuario is not None else "-",
            "role_label": change.rol_usuario or "-",
            "section_label": change.seccion.title(),
            "field_label": change.etiqueta_campo,
            "old_value": change.valor_anterior or "-",
            "new_value": change.valor_nuevo or "-",
        }
        for change in changes
    ]


def _resolve_settings_marketing_recalc_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.loyalty_service import LoyaltyService

    return LoyaltyService, Usuario


def _resolve_settings_marketing_history_dependencies():
    from pos_uniformes.services.marketing_audit_service import MarketingAuditService

    return MarketingAuditService
