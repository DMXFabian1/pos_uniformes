"""Acciones operativas de marketing en Configuracion.

2026-11-12: se retiró «Recalcular niveles» («el nivel viejo retíralo»,
Daniel). Ya no hay revisión del nivel viejo de los clientes.
"""

from __future__ import annotations

from pos_uniformes.utils.date_format import format_display_datetime


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


def _resolve_settings_marketing_history_dependencies():
    from pos_uniformes.services.marketing_audit_service import MarketingAuditService

    return MarketingAuditService
