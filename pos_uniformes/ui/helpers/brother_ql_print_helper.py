"""Impresion directa a Brother QL via protocolo raster (sin driver Windows).

Usa la libreria brother_ql para enviar imagenes directamente por USB.
Mas confiable que win32print para etiquetas die-cut como DK-1221.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


BROTHER_QL_MODEL = "QL-800"
BROTHER_QL_LABEL_23x23 = "23x23"
# USB vendor:product para QL-800
BROTHER_QL_USB_ID = "usb://0x04f9:0x209b"


def is_brother_ql_available() -> bool:
    """Verifica si brother_ql esta instalado."""
    try:
        import brother_ql  # noqa: F401
        return True
    except ImportError:
        return False


def _discover_usb_printer() -> str:
    """Busca la impresora Brother QL conectada por USB.

    Devuelve el URI (usb://...) o el default si no puede descubrir.
    """
    try:
        from brother_ql.backends.helpers import discover
        printers = discover(backend_identifier="pyusb")
        if printers:
            return printers[0]["instance"]
    except Exception:
        pass
    return BROTHER_QL_USB_ID


def print_dk1221_via_brother_ql(
    image_path: Path,
    *,
    copies: int = 1,
    label_type: str = BROTHER_QL_LABEL_23x23,
) -> None:
    """Imprime una etiqueta die-cut DK-1221 (23x23mm) directamente via USB.

    Envia N copias en una sola llamada. El auto-cutter de la QL-800
    corta entre cada etiqueta usando el sensor de gap.
    """
    from brother_ql import BrotherQLRaster
    from brother_ql.conversion import convert
    from brother_ql.backends.helpers import send

    printer_uri = _discover_usb_printer()
    img = Image.open(image_path)

    # brother_ql espera 202x202 para 23x23 die-cut
    if img.size != (202, 202):
        img = img.resize((202, 202), Image.LANCZOS)

    # Convertir a instrucciones raster
    qlr = BrotherQLRaster(BROTHER_QL_MODEL)
    qlr.exception_on_warning = True

    for _ in range(max(1, copies)):
        convert(
            qlr=qlr,
            images=[img],
            label=label_type,
            cut=True,
            dither=False,
            compress=False,
            red=False,
            dpi_600=False,
            hq=True,
            rotate="auto",
        )

    # Enviar todo de golpe
    send(
        instructions=qlr.data,
        printer_identifier=printer_uri,
        backend_identifier="pyusb",
        blocking=True,
    )
