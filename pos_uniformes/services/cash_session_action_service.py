"""Acciones operativas de apertura, movimiento y corte de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashSessionGateSnapshot:
    has_active_session: bool
    active_session_id: int | None
    requires_cut: bool
    opened_by: str
    opened_at_label: str
    opening_amount: Decimal


@dataclass(frozen=True)
class CashMovementTargetSnapshot:
    target_total: Decimal | None


@dataclass(frozen=True)
class CashCutPromptSnapshot:
    opened_at_label: str
    opening_amount: Decimal
    reactivo_count: int
    reactivo_total: Decimal
    ingresos_count: int
    ingresos_total: Decimal
    retiros_count: int
    retiros_total: Decimal
    cash_sales_count: int
    cash_sales_total: Decimal
    cash_payments_count: int
    cash_payments_total: Decimal
    expected_amount: Decimal


@dataclass(frozen=True)
class CashOpeningCorrectionResult:
    previous_amount: Decimal
    new_amount: Decimal


@dataclass(frozen=True)
class CashCloseResult:
    expected_amount: Decimal
    counted_amount: Decimal
    difference: Decimal


def load_cash_session_gate_snapshot(session, *, user_id: int, is_stale_session) -> CashSessionGateSnapshot:
    caja_service, usuario_model, _, _ = _resolve_cash_session_action_dependencies()
    active_session = caja_service.obtener_sesion_activa(session)
    if active_session is not None:
        return CashSessionGateSnapshot(
            has_active_session=True,
            active_session_id=int(active_session.id),
            requires_cut=bool(is_stale_session(active_session)),
            opened_by=(
                active_session.abierta_por.nombre_completo
                if active_session.abierta_por is not None
                else "otro usuario"
            ),
            opened_at_label=(
                active_session.abierta_at.strftime("%Y-%m-%d %H:%M")
                if active_session.abierta_at is not None
                else "sin fecha"
            ),
            opening_amount=Decimal(active_session.monto_apertura).quantize(Decimal("0.01")),
        )
    user = session.get(usuario_model, user_id)
    if user is None:
        raise ValueError("No se encontro el usuario autenticado.")
    return CashSessionGateSnapshot(
        has_active_session=False,
        active_session_id=None,
        requires_cut=False,
        opened_by="",
        opened_at_label="",
        opening_amount=Decimal("0.00"),
    )


def load_cash_opening_suggested_amount(session) -> Decimal | None:
    caja_service, _, _, _ = _resolve_cash_session_action_dependencies()
    return caja_service.obtener_ultimo_reactivo_sugerido(session)


def open_cash_session_action(
    session,
    *,
    user_id: int,
    opening_amount: Decimal,
    opening_note: object,
) -> int:
    caja_service, usuario_model, _, _ = _resolve_cash_session_action_dependencies()
    user = session.get(usuario_model, user_id)
    if user is None:
        raise ValueError("No se encontro el usuario autenticado.")
    cash_session = caja_service.abrir_sesion(
        session=session,
        usuario=user,
        monto_apertura=opening_amount,
        observacion=_normalize_optional_text(opening_note),
    )
    session.commit()
    return int(cash_session.id)


def load_cash_movement_target_snapshot(session, *, active_cash_session_id: int | None, movement_type) -> CashMovementTargetSnapshot:
    caja_service, _, sesion_caja_model, tipo_movimiento_caja = _resolve_cash_session_action_dependencies()
    target_total: Decimal | None = None
    if movement_type == tipo_movimiento_caja.REACTIVO and active_cash_session_id is not None:
        cash_session = session.get(sesion_caja_model, active_cash_session_id)
        if cash_session is not None:
            resumen = caja_service.resumir_sesion(session, cash_session)
            target_total = (
                Decimal(cash_session.monto_apertura).quantize(Decimal("0.01")) + resumen.reactivo_total
            ).quantize(Decimal("0.01"))
    return CashMovementTargetSnapshot(target_total=target_total)


def register_cash_movement_action(
    session,
    *,
    active_cash_session_id: int,
    user_id: int,
    movement_type,
    amount: Decimal,
    concept: object,
) -> None:
    caja_service, usuario_model, sesion_caja_model, _ = _resolve_cash_session_action_dependencies()
    cash_session = session.get(sesion_caja_model, active_cash_session_id)
    user = session.get(usuario_model, user_id)
    if cash_session is None or user is None:
        raise ValueError("No se pudo cargar la caja activa o el usuario.")
    caja_service.registrar_movimiento(
        session=session,
        cash_session=cash_session,
        usuario=user,
        tipo=movement_type,
        monto=amount,
        concepto=_normalize_optional_text(concept),
    )
    session.commit()


def load_cash_opening_amount(session, *, active_cash_session_id: int | None) -> Decimal:
    _, _, sesion_caja_model, _ = _resolve_cash_session_action_dependencies()
    if active_cash_session_id is None:
        return Decimal("0.00")
    cash_session = session.get(sesion_caja_model, active_cash_session_id)
    if cash_session is None:
        return Decimal("0.00")
    return Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))


def correct_cash_opening_action(
    session,
    *,
    active_cash_session_id: int,
    user_id: int,
    new_amount: Decimal,
    note: object,
) -> CashOpeningCorrectionResult:
    caja_service, usuario_model, sesion_caja_model, _ = _resolve_cash_session_action_dependencies()
    cash_session = session.get(sesion_caja_model, active_cash_session_id)
    user = session.get(usuario_model, user_id)
    if cash_session is None or user is None:
        raise ValueError("No se pudo cargar la caja activa o el usuario.")
    previous_amount = Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))
    caja_service.corregir_apertura(
        session=session,
        cash_session=cash_session,
        usuario=user,
        nuevo_monto_apertura=new_amount,
        observacion=_normalize_optional_text(note),
    )
    session.commit()
    return CashOpeningCorrectionResult(
        previous_amount=previous_amount,
        new_amount=Decimal(new_amount).quantize(Decimal("0.01")),
    )


def load_cash_cut_prompt_snapshot(session, *, active_cash_session_id: int) -> CashCutPromptSnapshot:
    caja_service, _, sesion_caja_model, _ = _resolve_cash_session_action_dependencies()
    cash_session = session.get(sesion_caja_model, active_cash_session_id)
    if cash_session is None:
        raise ValueError("No se encontro la caja activa.")
    resumen = caja_service.resumir_sesion(session, cash_session)
    return CashCutPromptSnapshot(
        opened_at_label=cash_session.abierta_at.strftime("%Y-%m-%d %H:%M") if cash_session.abierta_at else "",
        opening_amount=Decimal(cash_session.monto_apertura).quantize(Decimal("0.01")),
        reactivo_count=int(resumen.reactivo_count),
        reactivo_total=Decimal(resumen.reactivo_total).quantize(Decimal("0.01")),
        ingresos_count=int(resumen.ingresos_count),
        ingresos_total=Decimal(resumen.ingresos_total).quantize(Decimal("0.01")),
        retiros_count=int(resumen.retiros_count),
        retiros_total=Decimal(resumen.retiros_total).quantize(Decimal("0.01")),
        cash_sales_count=int(resumen.ventas_efectivo_count),
        cash_sales_total=Decimal(resumen.efectivo_ventas).quantize(Decimal("0.01")),
        cash_payments_count=int(resumen.abonos_efectivo_count),
        cash_payments_total=Decimal(resumen.efectivo_abonos).quantize(Decimal("0.01")),
        expected_amount=Decimal(resumen.esperado_en_caja).quantize(Decimal("0.01")),
    )


def close_cash_session_action(
    session,
    *,
    active_cash_session_id: int,
    user_id: int,
    counted_amount: Decimal,
    closing_note: object,
) -> CashCloseResult:
    caja_service, usuario_model, sesion_caja_model, _ = _resolve_cash_session_action_dependencies()
    cash_session = session.get(sesion_caja_model, active_cash_session_id)
    user = session.get(usuario_model, user_id)
    if cash_session is None or user is None:
        raise ValueError("No se pudo cargar la caja o el usuario.")
    closed_session = caja_service.cerrar_sesion(
        session=session,
        cash_session=cash_session,
        usuario=user,
        monto_contado=counted_amount,
        observacion=_normalize_optional_text(closing_note),
    )
    session.commit()
    return CashCloseResult(
        expected_amount=Decimal(closed_session.monto_esperado_cierre).quantize(Decimal("0.01")),
        counted_amount=Decimal(closed_session.monto_cierre_declarado).quantize(Decimal("0.01")),
        difference=Decimal(closed_session.diferencia_cierre).quantize(Decimal("0.01")),
    )


def _resolve_cash_session_action_dependencies():
    from pos_uniformes.database.models import SesionCaja, TipoMovimientoCaja, Usuario
    from pos_uniformes.services.caja_service import CajaService

    return CajaService, Usuario, SesionCaja, TipoMovimientoCaja


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
