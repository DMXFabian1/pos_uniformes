"""Helpers visibles para el detalle modal de historial de caja en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SettingsCashHistoryBadgeView:
    text: str
    tone: str


@dataclass(frozen=True)
class SettingsCashHistoryDetailMovementRowView:
    values: tuple[object, ...]
    type_tone: str


@dataclass(frozen=True)
class SettingsCashHistoryDetailView:
    dialog_title: str
    title_label: str
    status_badge: SettingsCashHistoryBadgeView
    opening_rows: tuple[tuple[str, str], ...]
    opening_note: str
    opening_corrections: tuple[str, ...]
    flow_rows: tuple[tuple[str, str], ...]
    movement_rows: tuple[SettingsCashHistoryDetailMovementRowView, ...]
    closing_visible: bool
    closing_rows: tuple[tuple[str, str], ...]
    difference_badge: SettingsCashHistoryBadgeView | None
    closing_note: str


def build_settings_cash_history_detail_view(
    *,
    session_id: int,
    is_closed: bool,
    opened_at: str,
    opened_by: str,
    opening_amount: Decimal | str | int | float,
    opening_note: str,
    opening_corrections: list[str],
    reactivo_count: int,
    reactivo_total: Decimal | str | int | float,
    ingresos_count: int,
    ingresos_total: Decimal | str | int | float,
    retiros_count: int,
    retiros_total: Decimal | str | int | float,
    cash_sales_count: int,
    cash_sales_total: Decimal | str | int | float,
    cash_payments_count: int,
    cash_payments_total: Decimal | str | int | float,
    movement_rows: list[dict[str, object]],
    closed_at: str,
    closed_by: str,
    expected_amount: Decimal | str | int | float,
    declared_amount: Decimal | str | int | float,
    difference: Decimal | str | int | float,
    closing_note: str,
) -> SettingsCashHistoryDetailView:
    difference_decimal = Decimal(difference).quantize(Decimal("0.01"))
    if difference_decimal == Decimal("0.00"):
        difference_tone = "positive"
    elif difference_decimal > Decimal("0.00"):
        difference_tone = "warning"
    else:
        difference_tone = "danger"
    return SettingsCashHistoryDetailView(
        dialog_title=f"Detalle del corte #{session_id}",
        title_label=f"Corte #{session_id}",
        status_badge=SettingsCashHistoryBadgeView(
            text="Cerrada" if is_closed else "Abierta",
            tone="muted" if is_closed else "positive",
        ),
        opening_rows=(
            ("Fecha", opened_at),
            ("Usuario", opened_by),
            ("Reactivo inicial", f"${Decimal(opening_amount).quantize(Decimal('0.01'))}"),
        ),
        opening_note=opening_note,
        opening_corrections=tuple(opening_corrections),
        flow_rows=(
            ("Reactivos extra", f"{reactivo_count} | ${reactivo_total}"),
            ("Ingresos manuales", f"{ingresos_count} | ${ingresos_total}"),
            ("Retiros manuales", f"{retiros_count} | ${retiros_total}"),
            ("Ventas con efectivo", f"{cash_sales_count}"),
            ("Efectivo por ventas", f"${cash_sales_total}"),
            ("Abonos con efectivo", f"{cash_payments_count}"),
            ("Efectivo por abonos", f"${cash_payments_total}"),
        ),
        movement_rows=tuple(
            SettingsCashHistoryDetailMovementRowView(
                values=(
                    movement["fecha"],
                    movement["tipo"],
                    f"${movement['monto']}",
                    movement["usuario"],
                    movement["concepto"] or "-",
                ),
                type_tone=_movement_type_tone(str(movement["tipo"])),
            )
            for movement in movement_rows
        ),
        closing_visible=is_closed,
        closing_rows=(
            ("Fecha", closed_at),
            ("Usuario", closed_by),
            ("Esperado", f"${Decimal(expected_amount).quantize(Decimal('0.01'))}"),
            ("Contado", f"${Decimal(declared_amount).quantize(Decimal('0.01'))}"),
        ),
        difference_badge=(
            SettingsCashHistoryBadgeView(
                text=f"${difference_decimal}",
                tone=difference_tone,
            )
            if is_closed
            else None
        ),
        closing_note=closing_note,
    )


def _movement_type_tone(movement_type: str) -> str:
    return {
        "REACTIVO": "positive",
        "INGRESO": "warning",
        "RETIRO": "danger",
    }.get(movement_type, "muted")
