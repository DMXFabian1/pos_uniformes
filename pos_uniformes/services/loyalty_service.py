"""Reglas de lealtad y metadata visual para clientes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Cliente, EstadoVenta, NivelLealtad, RolUsuario, TipoCliente, Usuario, Venta
from pos_uniformes.services.business_settings_service import BusinessSettingsService


@dataclass(frozen=True)
class LoyaltyVisualSpec:
    level: NivelLealtad
    label: str
    primary_color: str
    secondary_color: str


@dataclass(frozen=True)
class LoyaltyProgramRules:
    review_window_days: int
    leal_spend_threshold: Decimal
    leal_purchase_count_threshold: int
    leal_purchase_sum_threshold: Decimal
    discount_basico: Decimal
    discount_leal: Decimal
    discount_profesor: Decimal
    discount_mayorista: Decimal


class LoyaltyService:
    """Centraliza reglas de nivel inicial y estilo visual de lealtad."""

    _VISUAL_SPECS = {
        NivelLealtad.BASICO: LoyaltyVisualSpec(
            level=NivelLealtad.BASICO,
            label="Basico",
            primary_color="#3A3A3A",
            secondary_color="#E6E1DB",
        ),
        NivelLealtad.LEAL: LoyaltyVisualSpec(
            level=NivelLealtad.LEAL,
            label="Leal",
            primary_color="#C65A1E",
            secondary_color="#F3E1D5",
        ),
        NivelLealtad.PROFESOR: LoyaltyVisualSpec(
            level=NivelLealtad.PROFESOR,
            label="Profesor",
            primary_color="#1F3A44",
            secondary_color="#D7E3E7",
        ),
        NivelLealtad.MAYORISTA: LoyaltyVisualSpec(
            level=NivelLealtad.MAYORISTA,
            label="Mayorista",
            primary_color="#C2A24A",
            secondary_color="#F2E9C9",
        ),
    }

    @staticmethod
    def coerce_level(level: NivelLealtad | str | None) -> NivelLealtad:
        if isinstance(level, NivelLealtad):
            return level
        if isinstance(level, str) and level.strip():
            return NivelLealtad(level.strip().upper())
        return NivelLealtad.BASICO

    @classmethod
    def visual_spec(cls, level: NivelLealtad | str | None) -> LoyaltyVisualSpec:
        normalized = cls.coerce_level(level)
        return cls._VISUAL_SPECS.get(normalized, cls._VISUAL_SPECS[NivelLealtad.BASICO])

    @classmethod
    def default_level_for_client_type(cls, tipo_cliente: TipoCliente | str | None) -> NivelLealtad:
        normalized_type = tipo_cliente
        if isinstance(tipo_cliente, str) and tipo_cliente.strip():
            normalized_type = TipoCliente(tipo_cliente.strip().upper())
        return {
            TipoCliente.GENERAL: NivelLealtad.BASICO,
            TipoCliente.PROFESOR: NivelLealtad.PROFESOR,
            TipoCliente.MAYORISTA: NivelLealtad.MAYORISTA,
        }.get(normalized_type, NivelLealtad.BASICO)

    @classmethod
    def _load_program_rules(cls, session: Session) -> LoyaltyProgramRules:
        config = BusinessSettingsService.get_or_create(session)
        return LoyaltyProgramRules(
            review_window_days=int(config.loyalty_review_window_days or 365),
            leal_spend_threshold=Decimal(str(config.leal_spend_threshold or Decimal("3000.00"))).quantize(Decimal("0.01")),
            leal_purchase_count_threshold=int(config.leal_purchase_count_threshold or 3),
            leal_purchase_sum_threshold=Decimal(str(config.leal_purchase_sum_threshold or Decimal("2000.00"))).quantize(Decimal("0.01")),
            discount_basico=Decimal(str(config.discount_basico or Decimal("5.00"))).quantize(Decimal("0.01")),
            discount_leal=Decimal(str(config.discount_leal or Decimal("10.00"))).quantize(Decimal("0.01")),
            discount_profesor=Decimal(str(config.discount_profesor or Decimal("15.00"))).quantize(Decimal("0.01")),
            discount_mayorista=Decimal(str(config.discount_mayorista or Decimal("20.00"))).quantize(Decimal("0.01")),
        )

    @classmethod
    def discount_for_level(cls, level: NivelLealtad | str | None, session: Session | None = None) -> Decimal:
        normalized = cls.coerce_level(level)
        if session is not None:
            rules = cls._load_program_rules(session)
        else:
            with get_session() as local_session:
                rules = cls._load_program_rules(local_session)
        mapping = {
            NivelLealtad.BASICO: rules.discount_basico,
            NivelLealtad.LEAL: rules.discount_leal,
            NivelLealtad.PROFESOR: rules.discount_profesor,
            NivelLealtad.MAYORISTA: rules.discount_mayorista,
        }
        return mapping.get(normalized, rules.discount_basico).quantize(Decimal("0.01"))

    @classmethod
    def evaluate_auto_level(
        cls,
        session: Session,
        client: Cliente,
        *,
        reference_time: datetime | None = None,
    ) -> NivelLealtad:
        if client.id is None:
            return cls.coerce_level(client.nivel_lealtad)
        if client.tipo_cliente in {TipoCliente.PROFESOR, TipoCliente.MAYORISTA}:
            return cls.default_level_for_client_type(client.tipo_cliente)
        if client.nivel_lealtad in {NivelLealtad.PROFESOR, NivelLealtad.MAYORISTA}:
            return cls.coerce_level(client.nivel_lealtad)

        rules = cls._load_program_rules(session)
        review_time = reference_time or datetime.now()
        period_start = review_time - timedelta(days=rules.review_window_days)
        statement = (
            select(
                func.count(Venta.id),
                func.coalesce(func.sum(Venta.total), Decimal("0.00")),
            )
            .where(
                Venta.cliente_id == int(client.id),
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.confirmada_at.is_not(None),
                Venta.confirmada_at >= period_start,
                Venta.confirmada_at <= review_time,
            )
        )
        purchase_count, purchase_total = session.execute(statement).one()
        count_value = int(purchase_count or 0)
        total_value = Decimal(str(purchase_total or Decimal("0.00"))).quantize(Decimal("0.01"))
        if total_value >= rules.leal_spend_threshold:
            return NivelLealtad.LEAL
        if (
            count_value >= rules.leal_purchase_count_threshold
            and total_value >= rules.leal_purchase_sum_threshold
        ):
            return NivelLealtad.LEAL
        return NivelLealtad.BASICO

    @classmethod
    def refresh_client_level_from_sales(
        cls,
        session: Session,
        client: Cliente | None,
        *,
        actor_user: Usuario,
        reason: str,
        reference_time: datetime | None = None,
    ) -> Cliente | None:
        if client is None:
            return None
        normalized_level = cls.evaluate_auto_level(session, client, reference_time=reference_time)
        cls.assign_level(
            client,
            level=normalized_level,
            actor_user=actor_user,
            reason=reason,
            session=session,
        )
        session.add(client)
        return client

    @classmethod
    def recalculate_all_clients(
        cls,
        session: Session,
        *,
        actor_user: Usuario,
        reason: str,
    ) -> dict[str, int]:
        clients = session.scalars(select(Cliente)).all()
        changed = 0
        total = 0
        for client in clients:
            total += 1
            previous_level = client.nivel_lealtad
            previous_discount = Decimal(str(client.descuento_preferente or Decimal("0.00"))).quantize(Decimal("0.01"))
            cls.refresh_client_level_from_sales(session, client, actor_user=actor_user, reason=reason)
            if client.nivel_lealtad != previous_level or Decimal(str(client.descuento_preferente)) != previous_discount:
                changed += 1
        return {"total": total, "changed": changed}

    @classmethod
    def resolve_initial_level(
        cls,
        actor_role: RolUsuario | str,
        requested_level: NivelLealtad | str | None = None,
    ) -> NivelLealtad:
        normalized_role = actor_role if isinstance(actor_role, RolUsuario) else RolUsuario(str(actor_role).upper())
        if normalized_role == RolUsuario.ADMIN:
            return cls.coerce_level(requested_level)
        return NivelLealtad.BASICO

    @classmethod
    def assign_level(
        cls,
        client: Cliente,
        *,
        level: NivelLealtad | str | None,
        actor_user: Usuario,
        reason: str,
        session: Session | None = None,
    ) -> Cliente:
        normalized_level = cls.coerce_level(level)
        client.nivel_lealtad = normalized_level
        client.descuento_preferente = cls.discount_for_level(normalized_level, session=session)
        client.nivel_asignado_por_user_id = actor_user.id
        client.nivel_asignado_por_rol = actor_user.rol.value
        client.nivel_asignacion_motivo = reason.strip() or "ajuste_nivel"
        return client
