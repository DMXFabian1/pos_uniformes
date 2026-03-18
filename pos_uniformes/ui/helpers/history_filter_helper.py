"""Helpers visibles para filtros de Historial."""

from __future__ import annotations

from pos_uniformes.database.models import TipoCambioCatalogo, TipoMovimientoInventario


def build_history_type_options(source_filter: str) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = [("Todos", "")]
    if source_filter in {"", "inventory"}:
        options.extend(
            (f"Inv. {movement_type.value}", f"inventory:{movement_type.value}")
            for movement_type in TipoMovimientoInventario
        )
    if source_filter in {"", "catalog"}:
        options.extend(
            (f"Cat. {change_type.value}", f"catalog:{change_type.value}")
            for change_type in TipoCambioCatalogo
        )
    return tuple(options)
