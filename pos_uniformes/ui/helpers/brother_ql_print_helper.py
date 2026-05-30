"""Impresion de etiquetas die-cut DK-1221 en Brother QL-800.

Estrategia: brother_ql genera las instrucciones raster nativas de la
impresora (incluido el comando de auto-corte entre etiquetas) y esos
bytes se envian al spooler de Windows en modo RAW.

Ventajas sobre win32print + GDI/DEVMODE:
  - brother_ql conoce el formato exacto de DK-1221 (no hay que pelear
    con el paper size del driver).
  - El modo RAW del spooler entrega los bytes sin tocarlos, asi que no
    interviene el GDI ni el DEVMODE (que es fragil con drivers Brother).
  - No necesita libusb/pyusb: usa el puerto del driver Brother ya
    instalado en Windows.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


BROTHER_QL_MODEL = "QL-800"
BROTHER_QL_LABEL_23x23 = "23x23"  # DK-1221 die-cut (area imprimible 202x202)


def is_brother_ql_available() -> bool:
    """Verifica si brother_ql esta instalado."""
    try:
        import brother_ql  # noqa: F401
        return True
    except ImportError:
        return False


def build_dk1221_raster(image_path: Path, *, copies: int = 1) -> bytes:
    """Genera las instrucciones raster para N copias de una etiqueta DK-1221.

    El raster incluye el comando de auto-corte (cut=True) por lo que la
    QL-800 corta entre cada etiqueta automaticamente.
    """
    from brother_ql.raster import BrotherQLRaster
    from brother_ql.conversion import convert

    img = Image.open(image_path)
    # brother_ql aplica su propio umbral; convertir a escala de grises
    if img.mode not in ("L", "RGB"):
        img = img.convert("L")
    # El area imprimible de la etiqueta 23x23 es 202x202 px
    if img.size != (202, 202):
        img = img.resize((202, 202), Image.LANCZOS)

    images = [img] * max(1, int(copies))

    qlr = BrotherQLRaster(BROTHER_QL_MODEL)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=images,
        label=BROTHER_QL_LABEL_23x23,
        rotate="auto",
        threshold=70.0,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=True,
    )
    return instructions


def send_raw_to_spooler(printer_name: str, data: bytes, job_name: str = "Etiqueta DK-1221") -> None:
    """Envia bytes crudos al spooler de Windows en modo RAW.

    El modo RAW entrega los bytes directamente al puerto de la impresora
    sin procesarlos por GDI. Requiere el nombre EXACTO de la cola de
    impresion instalada (no el modelo).
    """
    import win32print

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, (job_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def print_dk1221_via_brother_ql(
    image_path: Path,
    *,
    printer_name: str,
    copies: int = 1,
) -> None:
    """Imprime N etiquetas DK-1221 generando raster con brother_ql y
    enviandolo por el spooler RAW de Windows.

    Lanza excepcion si algo falla (el caller decide el fallback).
    """
    data = build_dk1221_raster(image_path, copies=copies)
    send_raw_to_spooler(printer_name, data)
