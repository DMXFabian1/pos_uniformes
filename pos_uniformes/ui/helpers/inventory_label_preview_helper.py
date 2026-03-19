"""Estado visible para preview e impresion de etiquetas de inventario."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.label_generator import LabelRenderResult


@dataclass(frozen=True)
class InventoryLabelPreviewView:
    preview_text: str
    summary_text: str
    print_enabled: bool


def build_inventory_label_mode_hint(mode: str) -> str:
    normalized_mode = "split" if str(mode).strip().lower() == "split" else "standard"
    if normalized_mode == "split":
        return "Split acomoda 4 etiquetas por hoja y calcula automaticamente cuantas hojas hacen falta."
    return "Normal imprime una etiqueta por pieza y es el formato recomendado para impresion directa."


def build_error_inventory_label_preview_view(error_message: str) -> InventoryLabelPreviewView:
    return InventoryLabelPreviewView(
        preview_text="No se pudo generar la etiqueta",
        summary_text=f"No se pudo preparar la vista previa.\nDetalle: {error_message}",
        print_enabled=False,
    )


def build_inventory_label_preview_view(result: LabelRenderResult) -> InventoryLabelPreviewView:
    mode_label = "Split" if result.mode == "split" else "Normal"
    if result.mode == "split":
        summary_text = (
            f"Modo seleccionado: {mode_label}\n"
            f"Piezas solicitadas: {result.requested_copies}\n"
            f"Hojas a imprimir: {result.effective_copies}\n"
            f"Archivo generado: {result.image_path.name}"
        )
    else:
        summary_text = (
            f"Modo seleccionado: {mode_label}\n"
            f"Copias a imprimir: {result.effective_copies}\n"
            f"Archivo generado: {result.image_path.name}"
        )
    return InventoryLabelPreviewView(
        preview_text="Sin vista previa",
        summary_text=summary_text,
        print_enabled=True,
    )


def build_inventory_label_print_confirmation(
    *,
    sku: str,
    result: LabelRenderResult,
) -> str:
    return (
        f"Se envio la etiqueta de '{sku}' a impresion.\n\n"
        f"Modo: {'Split' if result.mode == 'split' else 'Normal'}\n"
        f"Piezas solicitadas: {result.requested_copies}\n"
        f"Copias/hojas impresas: {result.effective_copies}"
    )
