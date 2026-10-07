"""Impresión de tickets/hojas en ESC/POS crudo (spooler RAW de Windows).

Manda los bytes directo a la impresora térmica, sin pasar por el driver ni por
QPrinter. Así se evita el problema del tamaño de página (la 1ª hoja salía ancha
y recortada): la impresora imprime a su ancho nativo y corta donde le decimos.

`build_escpos_bytes` es puro y testeable; `print_ticket_escpos` toca el spooler
(solo Windows, reusa pywin32 igual que la impresión de etiquetas).
"""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

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


def _corte(s: "EscPosSettings") -> bytes:
    """Avanzar y cortar, dejando que la IMPRESORA calcule cuánto avanzar.

    `GS V 0` corta donde está el papel, así que había que adelantarlo a mano
    con renglones en blanco (`feed_lines`, 3). Pero la cuchilla no está a la
    altura del cabezal: está ~1.5 cm más arriba. Tres renglones no alcanzan,
    y eso explicaba DOS cosas que parecían distintas (Daniel, 2026-10-07):
    el «¡Feliz Halloween!» —que es el último renglón— salía partido a la
    mitad, y lo que quedaba del ticket aparecía encabezando el siguiente,
    con su hueco en blanco delante.

    `GS V 65 n` avanza hasta la posición de corte —la de ESTA impresora, que
    ella sí conoce— más `n` puntos, y corta. Nada se corta a media frase, y en
    las impresoras que saben retroceder el papel, el siguiente ticket arranca
    pegado al cabezal en vez de nacer con 1.5 cm en blanco.
    """
    if not getattr(s, "corte_calculado", True):
        return (("\n" * s.feed_lines).encode("ascii", errors="ignore")
                + (_CUT_FULL if s.full_cut else _CUT_PARTIAL))
    n = max(0, min(255, int(getattr(s, "puntos_tras_corte", 0))))
    return bytes([_GS, ord("V"), 65 if s.full_cut else 66, n])


def _codepage_cmd(n: int) -> bytes:
    """ESC t n -> selecciona la tabla de códigos (n=2 suele ser CP850)."""
    return bytes([_ESC, ord("t"), max(0, min(255, int(n)))])


#: Ancho del papel en puntos. 80 mm a 203 dpi = 576; es el valor de casi todas
#: las térmicas de 80 mm, y solo se usa para centrar la imagen.
PUNTOS_POR_LINEA = 576

_ALINEAR_CENTRO = bytes([_ESC, ord("a"), 1])
_ALINEAR_IZQ = bytes([_ESC, ord("a"), 0])


def raster_de_imagen(ruta) -> bytes:
    """Convierte un PNG a los bytes de `GS v 0` (imagen de puntos).

    La térmica no sabe de PNG: recibe un mapa de bits, un bit por punto, 1 =
    quema. Se manda en filas de `ancho/8` bytes, con el bit más significativo a
    la izquierda.

    El ancho se redondea hacia arriba al múltiplo de 8 porque la unidad del
    comando es el byte: una imagen de 240 puntos ocupa 30 bytes por fila, pero
    una de 243 ocuparía 31 y los 5 puntos de más tienen que ir en blanco, no
    con basura.
    """
    from PIL import Image

    img = Image.open(ruta).convert("L")
    # Umbral duro, sin grises: la impresora decide quemar o no quemar, y un gris
    # se convierte en un tramado sucio.
    img = img.point(lambda v: 0 if v < 128 else 255, mode="1")
    ancho, alto = img.size
    bytes_por_fila = (ancho + 7) // 8
    pixeles = img.load()

    datos = bytearray()
    for y in range(alto):
        fila = bytearray(bytes_por_fila)
        for x in range(ancho):
            if not pixeles[x, y]:          # 0 = negro = quemar
                fila[x // 8] |= 0x80 >> (x % 8)
        datos += fila

    cabecera = bytes(
        [_GS, ord("v"), ord("0"), 0,
         bytes_por_fila & 0xFF, (bytes_por_fila >> 8) & 0xFF,
         alto & 0xFF, (alto >> 8) & 0xFF]
    )
    return cabecera + bytes(datos)


def _trozos_con_imagenes(text: str, s: EscPosSettings) -> bytes:
    """Codifica el texto y cambia cada marcador de imagen por sus puntos.

    El ticket viaja como una cadena por toda la cola de impresión, así que la
    imagen no puede ir dentro: va un marcador en su propio renglón y aquí se
    sustituye. Si el dibujo no se puede cargar, se omite y el ticket sale igual
    — un adorno nunca detiene un ticket.
    """
    from pos_uniformes.services.temporada_service import (
        ANCHO_PAPEL_TEXTO,
        MARCADOR_INICIO,
        imagen_para_marcador,
        partir_marcador,
    )

    salida = bytearray()
    for i, parte in enumerate(text.split(MARCADOR_INICIO)):
        # `i` y no «¿ya escribí algo?»: eso último daba falso cuando el
        # marcador abría el texto, y entonces el ticket salía con
        # «logo|MAXIMODA]]» escrito tal cual. Pasó al subir el logo al
        # encabezado, que es justo el primer renglón (2026-10-07).
        if i and "]]" in parte:
            cuerpo, _, resto = parte.partition("]]")
            nombre, respaldo = partir_marcador(cuerpo)
            ruta = imagen_para_marcador(nombre)
            puesto = False
            if ruta is not None:
                try:
                    salida += _ALINEAR_CENTRO + raster_de_imagen(ruta) + _ALINEAR_IZQ
                    puesto = True
                except Exception:  # noqa: BLE001 — sin dibujo, el ticket sigue
                    pass
            if not puesto and respaldo:
                # El logo no se pudo poner: el nombre de la tienda escrito es
                # mejor que un encabezado en blanco.
                salida += respaldo.center(ANCHO_PAPEL_TEXTO).encode(
                    s.encoding, errors="replace"
                )
            parte = resto
        salida += parte.encode(s.encoding, errors="replace")
    return bytes(salida)


def build_escpos_bytes(text: str, settings: EscPosSettings | None = None) -> bytes:
    """Arma el stream ESC/POS: init + codepage + texto + avance + corte."""
    s = settings or EscPosSettings()
    cuerpo = text if text.endswith("\n") else text + "\n"
    encoded = _trozos_con_imagenes(cuerpo, s)
    return _INIT + _codepage_cmd(s.codepage) + encoded + _corte(s)


def build_escpos_imagen(texto: str, settings: EscPosSettings | None = None) -> bytes:
    """El ticket ENTERO como una sola imagen de puntos, centrada y con corte.

    No va una letra de texto: el papel es un mapa de bits de 576 puntos, que es
    justo el ancho real del cabezal. Así no hay reescalado en ninguna parte de
    la cadena (era lo que apolillaba el logo), las cajas salen con línea de
    verdad y el codepage deja de importar — una imagen no tiene codificación.
    """
    import io

    from pos_uniformes.services.ticket_imagen_service import render_ticket_png

    s = settings or EscPosSettings()
    png = render_ticket_png(texto)
    raster = raster_de_imagen(io.BytesIO(png))
    return _INIT + _ALINEAR_CENTRO + raster + _ALINEAR_IZQ + _corte(s)


def _send_raw_windows(printer_name: str, data: bytes, copies: int) -> bool:
    """Windows: spooler RAW vía pywin32 (igual que la impresión de etiquetas)."""
    import win32print

    handle = win32print.OpenPrinter(printer_name)
    try:
        for _ in range(max(1, copies)):
            win32print.StartDocPrinter(handle, 1, ("Hoja de conteo", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, data)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    return True


def _send_raw_cups(printer_name: str, data: bytes, copies: int) -> bool:
    """macOS/Linux: CUPS raw vía `lp -o raw` (bypassa el driver)."""
    for _ in range(max(1, copies)):
        proc = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw"],
            input=data,
            capture_output=True,
        )
        if proc.returncode != 0:
            detalle = proc.stderr.decode(errors="replace").strip() or "lp falló"
            raise RuntimeError(detalle)
    return True


def print_ticket_imagen_escpos(printer_name: str, text: str, *, copies: int = 1) -> bool:
    """Imprime el ticket dibujado. False si no se pudo (el llamador cae al de siempre)."""
    if not printer_name:
        return False
    try:
        datos = build_escpos_imagen(text)
    except Exception:  # noqa: BLE001 — sin dibujo, el ticket sale por el camino viejo
        logger.exception("ESC/POS: no se pudo dibujar el ticket")
        return False
    if sys.platform.startswith("win"):
        return _send_raw_windows(printer_name, datos, copies)
    return _send_raw_cups(printer_name, datos, copies)


def print_ticket_escpos(printer_name: str, text: str, *, copies: int = 1) -> bool:
    """Envía el ticket como datos RAW a la impresora. True si se mandó.

    Windows usa el spooler RAW (pywin32); macOS/Linux usan CUPS (`lp -o raw`).
    Lanza si el envío falla, para que el llamador caiga al camino QPrinter.
    """
    settings = load_escpos_settings()
    data = build_escpos_bytes(text, settings)

    if sys.platform.startswith("win"):
        return _send_raw_windows(printer_name, data, copies)
    return _send_raw_cups(printer_name, data, copies)
