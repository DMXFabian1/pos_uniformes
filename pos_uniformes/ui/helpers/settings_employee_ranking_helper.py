"""Vista de tabla para el ranking de empleadas en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_datetime


@dataclass(frozen=True)
class EmployeeRankingRowView:
    values: tuple[str, ...]
    is_top: bool


@dataclass(frozen=True)
class EmployeeRankingView:
    status_label: str
    rows: tuple[EmployeeRankingRowView, ...]
    total_tickets: int
    total_pieces: int
    total_amount: Decimal


def build_employee_ranking_view(
    rows: tuple | list,
    *,
    period_label: str = "",
    amounts_visible: bool = True,
) -> EmployeeRankingView:
    total_tickets = sum(int(getattr(r, "tickets", 0)) for r in rows)
    total_pieces = sum(int(getattr(r, "pieces", 0)) for r in rows)
    total_amount = sum(
        (Decimal(str(getattr(r, "amount", "0") or "0")) for r in rows),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    if not rows:
        period_suffix = f" — {period_label}" if period_label else ""
        return EmployeeRankingView(
            status_label=f"Sin ventas acreditadas{period_suffix}.",
            rows=(),
            total_tickets=0,
            total_pieces=0,
            total_amount=Decimal("0.00"),
        )

    amount_str = f"${total_amount:,.2f}" if amounts_visible else "---"
    n = len(rows)
    period_suffix = f" | {period_label}" if period_label else ""
    status_label = (
        f"{n} empleada{'s' if n != 1 else ''}{period_suffix} · "
        f"{total_tickets} ticket{'s' if total_tickets != 1 else ''} · "
        f"{total_pieces} pieza{'s' if total_pieces != 1 else ''} · "
        f"{amount_str}"
    )

    row_views: list[EmployeeRankingRowView] = []
    for r in rows:
        last_sale_at = getattr(r, "last_sale_at", None)
        last_label = format_display_datetime(last_sale_at) if last_sale_at else "—"
        amount_cell = (
            f"${Decimal(str(getattr(r, 'amount', '0') or '0')):,.2f}"
            if amounts_visible
            else "---"
        )
        row_views.append(
            EmployeeRankingRowView(
                values=(
                    str(getattr(r, "rank", "")),
                    str(getattr(r, "display_name", "") or getattr(r, "employee_code", "")),
                    str(getattr(r, "tickets", 0)),
                    str(getattr(r, "pieces", 0)),
                    amount_cell,
                    last_label,
                ),
                is_top=int(getattr(r, "rank", 0)) == 1,
            )
        )
    return EmployeeRankingView(
        status_label=status_label,
        rows=tuple(row_views),
        total_tickets=total_tickets,
        total_pieces=total_pieces,
        total_amount=total_amount,
    )
