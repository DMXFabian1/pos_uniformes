"""Impresión de etiquetas SIN interfaz, para el despachador del satélite.

Espeja el camino Windows de `QuoteSatelliteWindow._print_satellite_label` pero
sin diálogos ni QMessageBox: el despachador corre en background y no puede abrir
ventanas. Resuelve la impresora de etiquetas según el modo (config local del
menú admin) y manda la imagen al helper de Windows.

Solo Windows: es donde está físicamente conectada la impresora del satélite.
En otros SO lanza (el despachador marcará el trabajo como ERROR, visible en la
GUI de la cola).
"""

from __future__ import annotations

import sys
from pathlib import Path


def print_label_image_headless(
    image_path: Path,
    *,
    sku: str,
    copies: int,
    paper_mode: str,
) -> None:
    """Imprime una etiqueta desde imagen en la impresora del satélite. Lanza si falla."""
    if not sys.platform.startswith("win"):
        raise RuntimeError(
            "La impresión de etiquetas del satélite solo está disponible en Windows."
        )

    from pos_uniformes.services.label_printer_settings_cache_service import (
        load_label_printer_settings,
        resolve_label_printer_for_mode,
    )
    from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
        print_inventory_label_via_windows,
    )

    normal_printer, label_printer = load_label_printer_settings()
    preferred_printer = resolve_label_printer_for_mode(
        paper_mode, normal_printer=normal_printer, label_printer=label_printer
    )
    print_inventory_label_via_windows(
        image_path,
        sku=sku,
        copies=copies,
        preferred_printer_name=preferred_printer,
        paper_mode=paper_mode,
    )
