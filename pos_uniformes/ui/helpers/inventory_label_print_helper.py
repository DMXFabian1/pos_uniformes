"""Helpers para preparar impresion de etiquetas de inventario."""

from __future__ import annotations

from dataclasses import dataclass

LABEL_PRINT_DPI = 300.0
MM_PER_INCH = 25.4


@dataclass(frozen=True)
class InventoryLabelPrintLayout:
    width_mm: float
    height_mm: float
    orientation: str


def pixels_to_mm(pixels: int, *, dpi: float = LABEL_PRINT_DPI) -> float:
    """Convierte pixeles a milimetros usando el DPI de impresion esperado."""
    normalized_pixels = max(1, int(pixels))
    normalized_dpi = float(dpi) if dpi and dpi > 0 else LABEL_PRINT_DPI
    return round((normalized_pixels * MM_PER_INCH) / normalized_dpi, 2)


def build_inventory_label_print_layout(
    width_px: int,
    height_px: int,
    *,
    dpi: float = LABEL_PRINT_DPI,
) -> InventoryLabelPrintLayout:
    """Calcula tamano fisico y orientacion para una etiqueta renderizada."""
    normalized_width = max(1, int(width_px))
    normalized_height = max(1, int(height_px))
    orientation = "landscape" if normalized_width >= normalized_height else "portrait"
    return InventoryLabelPrintLayout(
        width_mm=pixels_to_mm(normalized_width, dpi=dpi),
        height_mm=pixels_to_mm(normalized_height, dpi=dpi),
        orientation=orientation,
    )
