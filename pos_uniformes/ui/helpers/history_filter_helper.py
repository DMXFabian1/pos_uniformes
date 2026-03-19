"""Helpers visibles para filtros de Historial."""

from __future__ import annotations

INVENTORY_HISTORY_TYPES = (
    "ENTRADA_COMPRA",
    "SALIDA_VENTA",
    "AJUSTE_ENTRADA",
    "AJUSTE_SALIDA",
    "CANCELACION_VENTA",
    "APARTADO_RESERVA",
    "APARTADO_LIBERACION",
)

CATALOG_HISTORY_TYPES = (
    "CREACION",
    "ACTUALIZACION",
    "ESTADO",
    "ELIMINACION",
)


def build_history_type_options(source_filter: str) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = [("Todos", "")]
    if source_filter in {"", "inventory"}:
        options.extend(
            (f"Inv. {movement_type}", f"inventory:{movement_type}")
            for movement_type in INVENTORY_HISTORY_TYPES
        )
    if source_filter in {"", "catalog"}:
        options.extend(
            (f"Cat. {change_type}", f"catalog:{change_type}")
            for change_type in CATALOG_HISTORY_TYPES
        )
    return tuple(options)
