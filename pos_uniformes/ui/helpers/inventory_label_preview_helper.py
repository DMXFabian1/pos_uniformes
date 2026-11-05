"""Estado visible para preview e impresion de etiquetas de inventario."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.label_generator import LabelRenderResult

#: Cómo se llama cada tamaño en pantalla: (nombre, medida). Antes eran
#: «Normal / Split / Label», nombres de cuando se programó, que no decían qué
#: etiqueta salía (Daniel, 2026-11-05).
NOMBRES_DE_MODO: dict[str, tuple[str, str]] = {
    "dk1221": ("Cuadrada", "23 × 23 mm"),
    "standard": ("Grande", "29 × 90 mm"),
    "split": ("Tira de 4", "4 por hoja"),
    "continuous": ("Rollo continuo", "29 mm"),
}


def nombre_de_modo(mode: str) -> str:
    return NOMBRES_DE_MODO.get(str(mode).strip().lower(), NOMBRES_DE_MODO["standard"])[0]


@dataclass(frozen=True)
class InventoryLabelPreviewView:
    preview_text: str
    summary_text: str
    print_enabled: bool


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def build_inventory_label_mode_hint(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized == "split":
        return "Tira de 4: acomoda 4 etiquetas por hoja y calcula sola cuántas hojas hacen falta."
    if normalized == "continuous":
        return "Rollo continuo: cada etiqueta va como trabajo aparte para que la impresora corte entre una y otra."
    if normalized == "dk1221":
        return "Cuadrada de 23 mm: el QR, la talla o el precio y el nombre. Una etiqueta por pieza, con corte automático."
    return "Grande de 29 × 90 mm: una etiqueta por pieza, con la escuela o la marca arriba, el nombre grande y el SKU."


def build_error_inventory_label_preview_view(error_message: str) -> InventoryLabelPreviewView:
    return InventoryLabelPreviewView(
        preview_text="No se pudo generar la etiqueta",
        summary_text=f"No se pudo preparar la vista previa.\nDetalle: {error_message}",
        print_enabled=False,
    )


def build_inventory_label_preview_view(result: LabelRenderResult) -> InventoryLabelPreviewView:
    """Qué va a salir, dicho en una línea y sin el nombre del archivo."""
    if result.mode == "split":
        summary_text = (
            f"{_plural(result.requested_copies, 'pieza', 'piezas')} en "
            f"{_plural(result.effective_copies, 'hoja', 'hojas')} de 4 etiquetas"
        )
    elif result.mode == "continuous":
        summary_text = f"{_plural(result.effective_copies, 'etiqueta', 'etiquetas')} en rollo continuo, con corte entre cada una"
    elif result.mode == "dk1221":
        summary_text = f"{_plural(result.effective_copies, 'etiqueta cuadrada', 'etiquetas cuadradas')} de 23 mm, con corte entre cada una"
    else:
        summary_text = f"{_plural(result.effective_copies, 'etiqueta grande', 'etiquetas grandes')} de 29 × 90 mm"
    return InventoryLabelPreviewView(
        preview_text="Sin vista previa",
        summary_text=summary_text,
        print_enabled=True,
    )


def texto_boton_imprimir(result: LabelRenderResult | None) -> str:
    """El botón dice lo que va a pasar: «Imprimir 20 etiquetas»."""
    if result is None:
        return "Imprimir etiqueta"
    if result.mode == "split":
        return f"Imprimir {_plural(result.effective_copies, 'hoja', 'hojas')}"
    return f"Imprimir {_plural(result.effective_copies, 'etiqueta', 'etiquetas')}"


def build_inventory_label_print_confirmation(
    *,
    sku: str,
    result: LabelRenderResult,
) -> str:
    return (
        f"Se envio la etiqueta de '{sku}' a impresion.\n\n"
        f"Modo: {nombre_de_modo(result.mode)}\n"
        f"Piezas solicitadas: {result.requested_copies}\n"
        f"Copias/hojas impresas: {result.effective_copies}"
    )
