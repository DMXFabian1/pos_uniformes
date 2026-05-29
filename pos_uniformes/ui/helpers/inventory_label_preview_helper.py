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
    normalized = str(mode).strip().lower()
    if normalized == "split":
        return "Split acomoda 4 etiquetas por hoja y calcula automaticamente cuantas hojas hacen falta."
    if normalized == "continuous":
        return "Continua envia cada etiqueta como trabajo independiente para que la impresora de rollo corte automaticamente entre cada una."
    if normalized == "dk1221":
        return "Label genera una etiqueta cuadrada (23x23mm) con el codigo QR y nombre del producto. Una etiqueta por pieza, corte automatico."
    return "Normal imprime una etiqueta por pieza y es el formato recomendado para impresion directa."


def build_error_inventory_label_preview_view(error_message: str) -> InventoryLabelPreviewView:
    return InventoryLabelPreviewView(
        preview_text="No se pudo generar la etiqueta",
        summary_text=f"No se pudo preparar la vista previa.\nDetalle: {error_message}",
        print_enabled=False,
    )


def build_inventory_label_preview_view(result: LabelRenderResult) -> InventoryLabelPreviewView:
    if result.mode == "split":
        mode_label = "Split"
        summary_text = (
            f"Modo seleccionado: {mode_label}\n"
            f"Piezas solicitadas: {result.requested_copies}\n"
            f"Hojas a imprimir: {result.effective_copies}\n"
            f"Archivo generado: {result.image_path.name}"
        )
    elif result.mode == "continuous":
        mode_label = "Continua"
        summary_text = (
            f"Modo seleccionado: {mode_label}\n"
            f"Etiquetas a imprimir: {result.effective_copies} (una por trabajo)\n"
            f"Archivo generado: {result.image_path.name}"
        )
    elif result.mode == "dk1221":
        mode_label = "Label"
        summary_text = (
            f"Modo seleccionado: {mode_label} (23x23mm)\n"
            f"Etiquetas a imprimir: {result.effective_copies} (una por trabajo)\n"
            f"Archivo generado: {result.image_path.name}"
        )
    else:
        mode_label = "Normal"
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
    if result.mode == "split":
        mode_label = "Split"
    elif result.mode == "continuous":
        mode_label = "Continua"
    elif result.mode == "dk1221":
        mode_label = "Label"
    else:
        mode_label = "Normal"
    return (
        f"Se envio la etiqueta de '{sku}' a impresion.\n\n"
        f"Modo: {mode_label}\n"
        f"Piezas solicitadas: {result.requested_copies}\n"
        f"Copias/hojas impresas: {result.effective_copies}"
    )
