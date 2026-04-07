"""Helpers para generacion masiva de QR en inventario."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pos_uniformes.utils.qr_generator import QrGenerator


@dataclass(frozen=True)
class InventoryBulkQrProgress:
    current: int
    total: int
    sku: str
    message: str


class InventoryBulkQrCancelled(Exception):
    """Se levanta cuando el usuario cancela la generacion masiva."""


def build_inventory_bulk_qr_progress(*, current: int, total: int, sku: str) -> InventoryBulkQrProgress:
    normalized_sku = str(sku or "").strip().upper() or "SIN SKU"
    return InventoryBulkQrProgress(
        current=current,
        total=total,
        sku=normalized_sku,
        message=f"Generando etiqueta {current} de {total}: {normalized_sku}",
    )


def generate_inventory_bulk_qr(
    variantes: list[object],
    *,
    on_progress: Callable[[InventoryBulkQrProgress], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> list[Path]:
    paths: list[Path] = []
    total = len(variantes)
    for index, variante in enumerate(variantes, start=1):
        if is_cancelled is not None and is_cancelled():
            raise InventoryBulkQrCancelled()
        progress = build_inventory_bulk_qr_progress(
            current=index,
            total=total,
            sku=str(getattr(variante, "sku", "") or ""),
        )
        if on_progress is not None:
            on_progress(progress)
        if is_cancelled is not None and is_cancelled():
            raise InventoryBulkQrCancelled()
        paths.append(QrGenerator.generate_for_variant(variante))
    return paths
