"""Helpers visibles para el resumen del listado de inventario."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class InventoryCounterState:
    text: str
    tone: str


@dataclass(frozen=True)
class InventorySummaryView:
    results_summary: str
    out_counter: InventoryCounterState
    low_counter: InventoryCounterState
    qr_pending_counter: InventoryCounterState
    inactive_counter: InventoryCounterState


def build_inventory_summary_view(
    *,
    total_rows: int,
    visible_rows: list[dict[str, object]],
    active_filter_labels: list[str],
) -> InventorySummaryView:
    total_stock = sum(int(row["stock_actual"]) for row in visible_rows)
    reserved_count = sum(1 for row in visible_rows if int(row["apartado_cantidad"]) > 0)
    fallback_count = sum(1 for row in visible_rows if bool(row.get("fallback_importacion")))
    count_out = sum(1 for row in visible_rows if int(row["stock_actual"]) == 0)
    count_low = sum(1 for row in visible_rows if 0 < int(row["stock_actual"]) <= 3)
    count_missing_qr = sum(1 for row in visible_rows if not bool(row.get("qr_exists")))
    count_inactive = sum(1 for row in visible_rows if not bool(row.get("variante_activa")))
    return InventorySummaryView(
        results_summary=(
            f"{len(visible_rows)}/{total_rows} resultados | stock {total_stock} | "
            f"ap. {reserved_count} | fallbacks {fallback_count}"
        ),
        out_counter=InventoryCounterState(
            text=f"Agotados: {count_out}",
            tone="danger" if count_out else "positive",
        ),
        low_counter=InventoryCounterState(
            text=f"Bajo stock: {count_low}",
            tone="warning" if count_low else "positive",
        ),
        qr_pending_counter=InventoryCounterState(
            text=f"Sin QR: {count_missing_qr}",
            tone="warning" if count_missing_qr else "positive",
        ),
        inactive_counter=InventoryCounterState(
            text=f"Inactivas: {count_inactive}",
            tone="muted" if count_inactive else "positive",
        ),
    )
