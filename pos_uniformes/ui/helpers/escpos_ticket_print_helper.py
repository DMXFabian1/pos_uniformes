"""Impresión de tickets/hojas en ESC/POS crudo (spooler RAW de Windows).

Manda los bytes directo a la impresora térmica, sin pasar por el driver ni por
QPrinter. Así se evita el problema del tamaño de página (la 1ª hoja salía ancha
y recortada): la impresora imprime a su ancho nativo y corta donde le decimos.

`build_escpos_bytes` es puro y testeable; `print_ticket_escpos` toca el spooler
(solo Windows, reusa pywin32 igual que la impresión de etiquetas).
"""

from __future__ import annotations

from pos_uniformes.services.escpos_settings_cache_service import (
    EscPosSettings,
    load_escpos_settings,
)

# Comandos ESC/POS
_ESC = 0x1B
_GS = 0x1D
_INIT = bytes([_ESC, ord("@")])                 # ESC @  -> reset
_CUT_FULL = bytes([_GS, ord("V"), 0])           # GS V 0 -> corte total
_CUT_PARTIAL = bytes([_GS, ord("V"), 1])        # GS V 1 -> corte parcial


def _codepage_cmd(n: int) -> bytes:
    """ESC t n -> selecciona la tabla de códigos (n=2 suele ser CP850)."""
    return bytes([_ESC, ord("t"), max(0, min(255, int(n)))])


def build_escpos_bytes(text: str, settings: EscPosSettings | None = None) -> bytes:
    """Arma el stream ESC/POS: init + codepage + texto + avance + corte."""
    s = settings or EscPosSettings()
    cuerpo = text if text.endswith("\n") else text + "\n"
    encoded = cuerpo.encode(s.encoding, errors="replace")
    feed = ("\n" * s.feed_lines).encode(s.encoding, errors="replace")
    corte = _CUT_FULL if s.full_cut else _CUT_PARTIAL
    return _INIT + _codepage_cmd(s.codepage) + encoded + feed + corte


def print_ticket_escpos(printer_name: str, text: str, *, copies: int = 1) -> bool:
    """Envía el ticket como datos RAW a la impresora. True si se mandó.

    Solo Windows (usa pywin32). Lanza si falta pywin32 o el spooler falla, para
    que el llamador pueda caer al camino QPrinter.
    """
    import win32print  # pywin32 (igual que la impresión de etiquetas)

    settings = load_escpos_settings()
    data = build_escpos_bytes(text, settings)

    handle = win32print.OpenPrinter(printer_name)
    try:
        for _ in range(max(1, copies)):
            job = win32print.StartDocPrinter(handle, 1, ("Hoja de conteo", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, data)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    return True
