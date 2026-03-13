"""Auditoria de cambios en reglas y descuentos de marketing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioMarketingConfiguracion, Usuario


@dataclass(frozen=True)
class MarketingAuditField:
    field_key: str
    section: str
    label: str
    previous_value: object | None
    new_value: object | None


class MarketingAuditService:
    """Registra y consulta cambios administrativos en Marketing y promociones."""

    @staticmethod
    def _stringify(value: object | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return format(value, ".2f")
        return str(value)

    @classmethod
    def log_field_changes(
        cls,
        session: Session,
        *,
        actor_user: Usuario,
        fields: list[MarketingAuditField],
    ) -> list[CambioMarketingConfiguracion]:
        changes: list[CambioMarketingConfiguracion] = []
        for field in fields:
            previous_value = cls._stringify(field.previous_value)
            new_value = cls._stringify(field.new_value)
            if previous_value == new_value:
                continue
            change = CambioMarketingConfiguracion(
                usuario=actor_user,
                rol_usuario=actor_user.rol.value if actor_user.rol is not None else None,
                seccion=field.section,
                campo=field.field_key,
                etiqueta_campo=field.label,
                valor_anterior=previous_value,
                valor_nuevo=new_value,
            )
            session.add(change)
            changes.append(change)
        return changes

    @staticmethod
    def list_recent(session: Session, *, limit: int = 100) -> list[CambioMarketingConfiguracion]:
        statement = (
            select(CambioMarketingConfiguracion)
            .order_by(CambioMarketingConfiguracion.created_at.desc(), CambioMarketingConfiguracion.id.desc())
            .limit(max(1, int(limit)))
        )
        return session.scalars(statement).all()
