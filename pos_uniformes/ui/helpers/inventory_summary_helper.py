"""Helpers visibles para el resumen del listado de inventario."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.inventario_existencia_service import contar_existencias

# Meilisearch devuelve como máximo esto en la pestaña Inventario. No se sube:
# cada hit trae ~25 campos y una búsqueda amplia (p. ej. «pants») con 5000
# hits pesaría varios MB por tecla; mejor avisar y que se afine la búsqueda.
INVENTORY_SEARCH_LIMIT = 500


def build_search_cut_notice(hits_count: int | None, *, limit: int = INVENTORY_SEARCH_LIMIT) -> str:
    """Aviso cuando la búsqueda llegó al tope y pudo quedarse corta."""
    if hits_count is None or hits_count < limit:
        return ""
    return f"Mostrando los primeros {limit}; afina la búsqueda"


@dataclass(frozen=True)
class InventoryCounterState:
    text: str
    tone: str


@dataclass(frozen=True)
class InventorySummaryView:
    results_summary: str
    negative_counter: InventoryCounterState
    out_counter: InventoryCounterState
    low_counter: InventoryCounterState
    inactive_counter: InventoryCounterState


def build_inventory_summary_view(
    *,
    total_rows: int,
    visible_rows: list[dict[str, object]],
    active_filter_labels: list[str],
    search_hits_count: int | None = None,
) -> InventorySummaryView:
    conteo = contar_existencias(visible_rows)
    total_stock = conteo.piezas  # sin conjuntos: ya están contados en sus piezas
    count_negative = conteo.negativos
    count_out = conteo.agotados
    count_low = conteo.bajos
    count_inactive = sum(1 for row in visible_rows if not bool(row.get("variante_activa")))
    return InventorySummaryView(
        results_summary=_with_notice(
            build_results_summary(len(visible_rows), total_rows, total_stock),
            build_search_cut_notice(search_hits_count),
        ),
        negative_counter=InventoryCounterState(
            text=f"En negativo: {count_negative}",
            tone="danger" if count_negative else "positive",
        ),
        out_counter=InventoryCounterState(
            text=f"Agotadas: {count_out}",
            tone="danger" if count_out else "positive",
        ),
        low_counter=InventoryCounterState(
            text=f"Quedan pocas: {count_low}",
            tone="warning" if count_low else "positive",
        ),
        inactive_counter=InventoryCounterState(
            text=f"Inactivas: {count_inactive}",
            tone="muted" if count_inactive else "positive",
        ),
    )


def build_results_summary(visibles: int, total: int, piezas: int) -> str:
    """El pie en palabras de la tienda: «214 de 5,153 tallas · 18,420 piezas».

    Las piezas no cuentan los conjuntos (ya están contados en sus piezas)."""
    tallas = f"{visibles:,} de {total:,} tallas" if visibles != total else f"{total:,} {_plural(total, 'talla', 'tallas')}"
    return f"{tallas} · {piezas:,} {_plural(piezas, 'pieza', 'piezas')}"


def _plural(n: int, uno: str, varios: str) -> str:
    return uno if n == 1 else varios


def _with_notice(summary: str, notice: str) -> str:
    return f"{summary} · ⚠ {notice}" if notice else summary
