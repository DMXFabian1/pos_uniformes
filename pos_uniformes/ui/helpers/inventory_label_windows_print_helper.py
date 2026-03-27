"""Impresion directa de etiquetas en Windows usando la API win32."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from PIL import Image, ImageWin


@dataclass(frozen=True)
class WindowsInventoryLabelPrinterResolution:
    printer_name: str
    available_printers: list[str]
    fallback_used: bool


def _require_windows() -> None:
    if not sys.platform.startswith("win"):
        raise RuntimeError("La impresion directa de etiquetas solo esta disponible en Windows.")


def _load_win32_modules():
    _require_windows()
    try:
        import win32print
        import win32ui
    except ImportError as exc:  # pragma: no cover - depende del entorno Windows
        raise RuntimeError(
            "Falta pywin32 en este entorno. Instala dependencias de Windows para imprimir etiquetas."
        ) from exc
    return win32print, win32ui


def list_windows_printer_names() -> list[str]:
    """Devuelve los nombres de impresoras visibles para Windows."""
    win32print, _win32ui = _load_win32_modules()
    printers = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    names = sorted({str(printer[2]).strip() for printer in printers if len(printer) > 2 and str(printer[2]).strip()})
    return names


def resolve_windows_inventory_label_printer(preferred_printer_name: str) -> WindowsInventoryLabelPrinterResolution:
    """Resuelve la impresora a usar priorizando la configurada y luego la predeterminada."""
    win32print, _win32ui = _load_win32_modules()
    preferred = str(preferred_printer_name or "").strip()
    available = list_windows_printer_names()
    if not available:
        raise ValueError("No hay impresoras disponibles en Windows para imprimir etiquetas.")

    if preferred and preferred in available:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=preferred,
            available_printers=available,
            fallback_used=False,
        )

    try:
        default_printer = str(win32print.GetDefaultPrinter() or "").strip()
    except Exception:
        default_printer = ""

    if default_printer and default_printer in available:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=default_printer,
            available_printers=available,
            fallback_used=bool(preferred),
        )

    return WindowsInventoryLabelPrinterResolution(
        printer_name=available[0],
        available_printers=available,
        fallback_used=bool(preferred),
    )


def print_inventory_label_via_windows(
    image_path: Path,
    *,
    sku: str,
    copies: int,
    preferred_printer_name: str,
) -> WindowsInventoryLabelPrinterResolution:
    """Imprime la etiqueta como bitmap monocromatico usando el spooler de Windows."""
    win32print, win32ui = _load_win32_modules()
    resolution = resolve_windows_inventory_label_printer(preferred_printer_name)

    hprinter = None
    hdc = None
    image = Image.open(image_path).convert("L").point(lambda value: 0 if value < 128 else 255, "1")
    label_width, label_height = image.size
    dib = ImageWin.Dib(image)
    job_name = f"Etiqueta {str(sku or '').strip() or 'inventario'}"

    try:
        hprinter = win32print.OpenPrinter(resolution.printer_name)
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(resolution.printer_name)
        hdc.StartDoc(job_name)
        for _copy_index in range(max(1, int(copies))):
            hdc.StartPage()
            dib.draw(hdc.GetHandleOutput(), (0, 0, label_width, label_height))
            hdc.EndPage()
        hdc.EndDoc()
        return resolution
    finally:
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass
        if hprinter is not None:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass
