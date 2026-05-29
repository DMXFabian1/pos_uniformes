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


def is_virtual_windows_printer(printer_name: str) -> bool:
    """Detecta impresoras virtuales que no sirven para la etiqueta fisica."""
    normalized = str(printer_name or "").strip().casefold()
    virtual_markers = (
        "microsoft print to pdf",
        "onenote",
        "xps",
        "fax",
        "pdf",
    )
    return any(marker in normalized for marker in virtual_markers)


def _physical_windows_printer_names(printer_names: list[str]) -> list[str]:
    return [name for name in printer_names if not is_virtual_windows_printer(name)]


def resolve_windows_inventory_label_printer(preferred_printer_name: str) -> WindowsInventoryLabelPrinterResolution:
    """Resuelve la impresora a usar evitando impresoras virtuales como PDF."""
    win32print, _win32ui = _load_win32_modules()
    preferred = str(preferred_printer_name or "").strip()
    available = list_windows_printer_names()
    if not available:
        raise ValueError("No hay impresoras disponibles en Windows para imprimir etiquetas.")
    physical_printers = _physical_windows_printer_names(available)

    if preferred and preferred in available and is_virtual_windows_printer(preferred):
        raise ValueError(
            f'La impresora configurada "{preferred}" es virtual y no sirve para imprimir etiquetas fisicas.'
        )

    if preferred and preferred in physical_printers:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=preferred,
            available_printers=available,
            fallback_used=False,
        )

    brother_exact = next((name for name in physical_printers if name.casefold() == "brother ql-800"), "")
    if brother_exact:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=brother_exact,
            available_printers=available,
            fallback_used=bool(preferred and preferred != brother_exact),
        )

    brother_family = next((name for name in physical_printers if "brother" in name.casefold()), "")
    if brother_family:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=brother_family,
            available_printers=available,
            fallback_used=bool(preferred and preferred != brother_family),
        )

    try:
        default_printer = str(win32print.GetDefaultPrinter() or "").strip()
    except Exception:
        default_printer = ""

    if default_printer and default_printer in physical_printers:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=default_printer,
            available_printers=available,
            fallback_used=bool(preferred),
        )

    if len(physical_printers) == 1:
        return WindowsInventoryLabelPrinterResolution(
            printer_name=physical_printers[0],
            available_printers=available,
            fallback_used=bool(preferred),
        )

    if not physical_printers:
        raise ValueError(
            "Windows solo detecta impresoras virtuales. Instala o conecta la impresora real de etiquetas."
        )

    return WindowsInventoryLabelPrinterResolution(
        printer_name=physical_printers[0],
        available_printers=available,
        fallback_used=bool(preferred),
    )


def _query_printer_dpi(win32ui, printer_name: str) -> tuple[int, int]:
    """Devuelve (dpi_x, dpi_y) reales del driver. Fallback 203 (QL-800 estandar)."""
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        dpi_x = hdc.GetDeviceCaps(88) or 0  # LOGPIXELSX
        dpi_y = hdc.GetDeviceCaps(90) or 0  # LOGPIXELSY
        hdc.DeleteDC()
        return (dpi_x or 203, dpi_y or 203)
    except Exception:
        return (203, 203)


# ── Paper configuration builders ──────────────────────────────────────────────


def _find_continuous_roll_paper_id(win32print, printer_name: str, target_width_mm10: int) -> int | None:
    """Busca el ID de rollo continuo (257-264) cuyo ancho coincide con el ancho del rollo actual."""
    try:
        paper_ids = win32print.DeviceCapabilities(printer_name, '', 2)   # DC_PAPERS
        paper_sizes = win32print.DeviceCapabilities(printer_name, '', 3)  # DC_PAPERSIZE
        if not paper_ids or not paper_sizes:
            return None
        candidates = []
        for pid, sz in zip(paper_ids, paper_sizes):
            w = sz['x'] if isinstance(sz, dict) else sz[0]
            h = sz['y'] if isinstance(sz, dict) else sz[1]
            if 257 <= pid <= 264:
                candidates.append((pid, w, h))
        if not candidates:
            return None
        return min(candidates, key=lambda x: abs(x[1] - target_width_mm10))[0]
    except Exception:
        return None


def _find_die_cut_paper_id(win32print, printer_name: str, target_w_mm10: int, target_h_mm10: int) -> int | None:
    """Busca el ID de papel die-cut cuyo tamaño coincide con las dimensiones objetivo.

    El driver de la Brother QL registra un paper ID para cada tipo de etiqueta
    die-cut soportada. Excluimos los IDs de rollo continuo (257-264).
    """
    try:
        paper_ids = win32print.DeviceCapabilities(printer_name, '', 2)   # DC_PAPERS
        paper_sizes = win32print.DeviceCapabilities(printer_name, '', 3)  # DC_PAPERSIZE
        if not paper_ids or not paper_sizes:
            return None
        candidates = []
        for pid, sz in zip(paper_ids, paper_sizes):
            w = sz['x'] if isinstance(sz, dict) else sz[0]
            h = sz['y'] if isinstance(sz, dict) else sz[1]
            if pid < 257 or pid > 264:
                candidates.append((pid, w, h))
        if not candidates:
            return None
        best = min(candidates, key=lambda x: abs(x[1] - target_w_mm10) + abs(x[2] - target_h_mm10))
        if abs(best[1] - target_w_mm10) <= 50 and abs(best[2] - target_h_mm10) <= 50:
            return best[0]
        return None
    except Exception:
        return None


def _build_continuous_devmode(win32print, win32ui, printer_name: str, hprinter, label_width_px: int, label_height_px: int):
    """Devuelve un DEVMODE configurado para rollo continuo con el largo exacto de la imagen."""
    try:
        dpi_x, dpi_y = _query_printer_dpi(win32ui, printer_name)
        height_mm10 = max(1, int(round((label_height_px / dpi_y) * 254)))
        width_mm10 = max(1, int(round((label_width_px / dpi_x) * 254)))

        props = win32print.GetPrinter(hprinter, 2)
        devmode = props.get("pDevMode")
        if devmode is None:
            return None

        continuous_id = _find_continuous_roll_paper_id(win32print, printer_name, width_mm10)
        if continuous_id is not None:
            devmode.PaperSize = continuous_id
            devmode.PaperLength = height_mm10
            devmode.Fields = (getattr(devmode, "Fields", 0) or 0) | 0x2 | 0x4  # PAPERSIZE | PAPERLENGTH
        else:
            devmode.PaperSize = 256  # DMPAPER_USER
            devmode.PaperLength = height_mm10
            devmode.PaperWidth = width_mm10
            devmode.Fields = (getattr(devmode, "Fields", 0) or 0) | 0x2 | 0x4 | 0x8

        win32print.DocumentProperties(
            0, hprinter, printer_name, devmode, devmode,
            win32print.DM_IN_BUFFER | win32print.DM_OUT_BUFFER,
        )
        return devmode
    except Exception:
        return None


def _build_die_cut_devmode(win32print, win32ui, printer_name: str, hprinter, label_width_px: int, label_height_px: int):
    """Devuelve un DEVMODE configurado para etiqueta die-cut.

    Busca el paper ID del driver Brother que coincide con el tamaño de la etiqueta.
    El sensor de gap de la QL-800 detecta los bordes de cada etiqueta die-cut
    y el auto-cutter corta automáticamente entre cada una.
    """
    try:
        dpi_x, dpi_y = _query_printer_dpi(win32ui, printer_name)
        width_mm10 = max(1, int(round((label_width_px / dpi_x) * 254)))
        height_mm10 = max(1, int(round((label_height_px / dpi_y) * 254)))

        props = win32print.GetPrinter(hprinter, 2)
        devmode = props.get("pDevMode")
        if devmode is None:
            return None

        die_cut_id = _find_die_cut_paper_id(win32print, printer_name, width_mm10, height_mm10)
        if die_cut_id is not None:
            devmode.PaperSize = die_cut_id
            devmode.Fields = (getattr(devmode, "Fields", 0) or 0) | 0x2
        else:
            devmode.PaperSize = 256  # DMPAPER_USER
            devmode.PaperWidth = width_mm10
            devmode.PaperLength = height_mm10
            devmode.Fields = (getattr(devmode, "Fields", 0) or 0) | 0x2 | 0x4 | 0x8

        win32print.DocumentProperties(
            0, hprinter, printer_name, devmode, devmode,
            win32print.DM_IN_BUFFER | win32print.DM_OUT_BUFFER,
        )
        return devmode
    except Exception:
        return None


# ── Job senders ───────────────────────────────────────────────────────────────


def _configure_devmode(win32print, win32ui, printer_name, hprinter, label_width, label_height, paper_mode):
    """Selecciona y aplica el DEVMODE correcto segun paper_mode."""
    if paper_mode == "die_cut":
        return _build_die_cut_devmode(win32print, win32ui, printer_name, hprinter, label_width, label_height)
    if paper_mode == "continuous":
        return _build_continuous_devmode(win32print, win32ui, printer_name, hprinter, label_width, label_height)
    return None


def _send_single_label_job(
    win32print,
    win32ui,
    printer_name: str,
    dib: "ImageWin.Dib",
    label_width: int,
    label_height: int,
    job_name: str,
    configure_paper: bool = False,
    paper_mode: str = "continuous",
) -> None:
    """Envia UN job con UNA pagina. Usado para rollo continuo (un job por corte)."""
    hprinter = None
    hdc = None
    original_devmode = None
    try:
        hprinter = win32print.OpenPrinter(printer_name)

        if configure_paper:
            try:
                original_devmode = win32print.GetPrinter(hprinter, 8).get("pDevMode")
            except Exception:
                pass
            devmode = _configure_devmode(
                win32print, win32ui, printer_name, hprinter, label_width, label_height, paper_mode
            )
            if devmode is not None:
                try:
                    win32print.SetPrinter(hprinter, 8, {"pDevMode": devmode}, 0)
                except Exception:
                    pass

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc(job_name)
        hdc.StartPage()
        dib.draw(hdc.GetHandleOutput(), (0, 0, label_width, label_height))
        hdc.EndPage()
        hdc.EndDoc()
    finally:
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass
        if original_devmode is not None and hprinter is not None:
            try:
                win32print.SetPrinter(hprinter, 8, {"pDevMode": original_devmode}, 0)
            except Exception:
                pass
        if hprinter is not None:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass


def _send_multi_page_job(
    win32print,
    win32ui,
    printer_name: str,
    dib: "ImageWin.Dib",
    label_width: int,
    label_height: int,
    job_name: str,
    copies: int,
    paper_mode: str = "standard",
) -> None:
    """Envia UN job con N paginas. Usado para die-cut (el sensor de gap corta solo)
    y para modo standard (sin corte entre copias)."""
    hprinter = None
    hdc = None
    original_devmode = None
    try:
        hprinter = win32print.OpenPrinter(printer_name)

        if paper_mode != "standard":
            try:
                original_devmode = win32print.GetPrinter(hprinter, 8).get("pDevMode")
            except Exception:
                pass
            devmode = _configure_devmode(
                win32print, win32ui, printer_name, hprinter, label_width, label_height, paper_mode
            )
            if devmode is not None:
                try:
                    win32print.SetPrinter(hprinter, 8, {"pDevMode": devmode}, 0)
                except Exception:
                    pass

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc(job_name)
        for _ in range(copies):
            hdc.StartPage()
            dib.draw(hdc.GetHandleOutput(), (0, 0, label_width, label_height))
            hdc.EndPage()
        hdc.EndDoc()
    finally:
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass
        if original_devmode is not None and hprinter is not None:
            try:
                win32print.SetPrinter(hprinter, 8, {"pDevMode": original_devmode}, 0)
            except Exception:
                pass
        if hprinter is not None:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass


# ── Public API ────────────────────────────────────────────────────────────────


def print_inventory_label_via_windows(
    image_path: Path,
    *,
    sku: str,
    copies: int,
    preferred_printer_name: str,
    paper_mode: str = "standard",
) -> WindowsInventoryLabelPrinterResolution:
    """Imprime la etiqueta como bitmap monocromatico usando el spooler de Windows.

    paper_mode controla el comportamiento completo:
      - "standard": un job, N paginas, sin config de papel.
      - "continuous": N jobs separados (uno por copia), config rollo continuo,
        fuerza corte entre cada etiqueta.
      - "die_cut": un job, N paginas, config die-cut. El sensor de gap de la
        QL-800 detecta cada etiqueta y el auto-cutter corta entre cada una.
    """
    win32print, win32ui = _load_win32_modules()
    resolution = resolve_windows_inventory_label_printer(preferred_printer_name)

    image = Image.open(image_path).convert("L").point(lambda value: 0 if value < 128 else 255, "1")
    label_width, label_height = image.size
    dib = ImageWin.Dib(image)
    job_name = f"Etiqueta {str(sku or '').strip() or 'inventario'}"
    total_copies = max(1, int(copies))

    if paper_mode == "continuous":
        # Rollo continuo: un job por copia para forzar corte
        for _ in range(total_copies):
            _send_single_label_job(
                win32print, win32ui, resolution.printer_name,
                dib, label_width, label_height, job_name,
                configure_paper=True, paper_mode="continuous",
            )
    else:
        # Die-cut y standard: un solo job, multiples paginas
        _send_multi_page_job(
            win32print, win32ui, resolution.printer_name,
            dib, label_width, label_height, job_name,
            copies=total_copies, paper_mode=paper_mode,
        )

    return resolution
