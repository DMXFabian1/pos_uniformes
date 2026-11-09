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


# ─── Ranking sobre la Libreta (fuente vigente) ───────────────────────────

LIBRETA_RANKING_HEADERS = (
    "#", "Empleada", "Puntos", "Piezas", "Operaciones",
    "Importe ventas", "Apartados", "Importe apartados",
)
LIBRETA_ABONOS_HEADERS = ("Empleada", "Abonos cobrados", "Importe abonos")


@dataclass(frozen=True)
class LibretaRankingView:
    status_label: str
    rows: tuple[EmployeeRankingRowView, ...]
    abonos_rows: tuple[tuple[str, ...], ...]


def _dinero(valor, visible: bool) -> str:
    return f"${Decimal(str(valor or 0)):,.2f}" if visible else "---"


def build_libreta_ranking_view(
    filas,
    *,
    period_label: str = "",
    amounts_visible: bool = True,
) -> LibretaRankingView:
    """Tabla principal (ordenada por puntos) y tabla aparte de abonos.

    Los abonos NO entran en operaciones ni en el importe de los apartados:
    van solos, a nombre de quien los cobró."""
    filas = list(filas or [])
    period_suffix = f" | {period_label}" if period_label else ""
    con_venta = [f for f in filas if f.operaciones or f.puntos]
    if not filas:
        return LibretaRankingView(
            status_label=f"Sin operaciones en la Libreta{period_suffix.replace(' | ', ' — ')}.",
            rows=(),
            abonos_rows=(),
        )
    puntos = sum(f.puntos for f in filas)
    piezas = sum(f.piezas for f in filas)
    operaciones = sum(f.operaciones for f in filas)
    importe = sum((f.importe_ventas for f in filas), Decimal("0.00"))
    n = len(con_venta)
    status_label = (
        f"{n} empleada{'s' if n != 1 else ''}{period_suffix} · "
        f"{puntos} punto{'s' if puntos != 1 else ''} · "
        f"{piezas} pieza{'s' if piezas != 1 else ''} · "
        f"{operaciones} operaci{'ones' if operaciones != 1 else 'ón'} · "
        f"ventas {_dinero(importe, amounts_visible)}"
    )
    rows = tuple(
        EmployeeRankingRowView(
            values=(
                str(f.posicion),
                f.nombre or f.employee_code,
                str(f.puntos),
                str(f.piezas),
                str(f.operaciones),
                _dinero(f.importe_ventas, amounts_visible),
                str(f.apartados),
                _dinero(f.importe_apartados, amounts_visible),
            ),
            is_top=f.posicion == 1 and f.puntos > 0,
        )
        for f in con_venta
    )
    abonos_rows = tuple(
        (f.nombre or f.employee_code, str(f.abonos), _dinero(f.importe_abonos, amounts_visible))
        for f in sorted((f for f in filas if f.abonos), key=lambda f: (-f.importe_abonos, f.employee_code))
    )
    return LibretaRankingView(status_label=status_label, rows=rows, abonos_rows=abonos_rows)
