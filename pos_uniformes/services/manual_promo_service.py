"""Autorizacion por codigo y auditoria de promociones manuales en caja."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AutorizacionPromocionManual,
    Cliente,
    ConfiguracionNegocio,
    Usuario,
    Venta,
)
from pos_uniformes.services.auth_service import AuthService

DEFAULT_PROMO_AUTHORIZATION_CODE = "PROMO2026"


@dataclass(frozen=True)
class PromoAuthorizationSummary:
    total_hoy: int
    recientes: list[AutorizacionPromocionManual]


class ManualPromoService:
    """Gestiona codigo de autorizacion y trazabilidad de promociones manuales."""

    @staticmethod
    def _money(value: Decimal | str | int | float) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))

    @classmethod
    def _ensure_code_hash(cls, config: ConfiguracionNegocio) -> str:
        if config.promo_authorization_code_hash:
            return config.promo_authorization_code_hash
        config.promo_authorization_code_hash = AuthService.hash_password(DEFAULT_PROMO_AUTHORIZATION_CODE)
        return config.promo_authorization_code_hash

    @classmethod
    def get_or_create_code_hash(cls, session: Session) -> str:
        config = session.scalar(select(ConfiguracionNegocio).limit(1))
        if config is None:
            config = ConfiguracionNegocio(nombre_negocio="POS Uniformes")
            session.add(config)
            session.flush()
        code_hash = cls._ensure_code_hash(config)
        session.add(config)
        session.flush()
        return code_hash

    @classmethod
    def update_authorization_code(cls, session: Session, config: ConfiguracionNegocio, raw_code: str | None) -> None:
        normalized = (raw_code or "").strip()
        if not normalized:
            return
        if len(normalized) < 4:
            raise ValueError("El codigo de autorizacion debe tener al menos 4 caracteres.")
        config.promo_authorization_code_hash = AuthService.hash_password(normalized)

    @classmethod
    def verify_authorization_code(cls, session: Session, code: str) -> bool:
        normalized = (code or "").strip()
        if not normalized:
            return False
        stored_hash = cls.get_or_create_code_hash(session)
        return AuthService.verify_password(normalized, stored_hash)

    @classmethod
    def log_authorized_promo(
        cls,
        session: Session,
        *,
        venta: Venta,
        actor_user: Usuario,
        cliente: Cliente | None,
        loyalty_percent: Decimal | str | int | float,
        promo_percent: Decimal | str | int | float,
        applied_percent: Decimal | str | int | float,
        applied_source: str,
        note: str | None = None,
    ) -> AutorizacionPromocionManual:
        entry = AutorizacionPromocionManual(
            venta=venta,
            usuario=actor_user,
            cliente=cliente,
            rol_usuario=actor_user.rol.value if getattr(actor_user, "rol", None) else None,
            folio_venta=venta.folio,
            porcentaje_lealtad=cls._money(loyalty_percent),
            porcentaje_promocion=cls._money(promo_percent),
            porcentaje_aplicado=cls._money(applied_percent),
            origen_aplicado=applied_source.strip() or "SIN_DESCUENTO",
            observacion=note.strip() if note else None,
        )
        session.add(entry)
        session.flush()
        return entry

    @classmethod
    def list_recent(cls, session: Session, *, limit: int = 5) -> list[AutorizacionPromocionManual]:
        query = (
            select(AutorizacionPromocionManual)
            .order_by(AutorizacionPromocionManual.created_at.desc(), AutorizacionPromocionManual.id.desc())
            .limit(limit)
        )
        return list(session.scalars(query).all())

    @classmethod
    def summarize_today(cls, session: Session, *, limit: int = 4) -> PromoAuthorizationSummary:
        today_start = datetime.combine(date.today(), time.min)
        total_hoy = session.scalar(
            select(func.count(AutorizacionPromocionManual.id)).where(
                AutorizacionPromocionManual.created_at >= today_start
            )
        ) or 0
        recientes = list(
            session.scalars(
                select(AutorizacionPromocionManual)
                .where(AutorizacionPromocionManual.created_at >= today_start)
                .order_by(AutorizacionPromocionManual.created_at.desc(), AutorizacionPromocionManual.id.desc())
                .limit(limit)
            ).all()
        )
        return PromoAuthorizationSummary(total_hoy=int(total_hoy), recientes=recientes)
