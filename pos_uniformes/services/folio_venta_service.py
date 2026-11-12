"""Folio de la venta: el QR del ticket para encontrar una venta después.

Daniel (2026-11-12): «el QR era para identificar ventas, así si necesito
hacer un cambio o rastrear una venta».

La venta ya tiene una identidad única desde que se cobra: su
`operacion_uuid` (la misma en cada reintento, aunque la venta suba después
desde la cola sin conexión). El folio es esa identidad:

- En el QR va completa: `VTA` + los 32 dígitos hexadecimales en mayúsculas.
  Solo letras y números, sin guiones ni dos puntos: el lector con teclado
  en español cambia `-` por `'` (ya pasó con el QR del cliente).
- Escrito en el papel va corto: los primeros 8 dígitos, `3F9A-12BC`, para
  buscarlo a mano si el QR se borró.

El dibujo del QR se genera al imprimir con el mismo marcador que el logo
(`[[IMG:qr_VTA…|Folio: …]]`), así que todas las impresoras lo entienden y
la que no sabe poner dibujos escribe el folio.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

PREFIJO = "VTA"
PREFIJO_MARCADOR = "qr_"
_RE_CODIGO = re.compile(r"VTA([0-9A-F]{32})")
_RE_CORTO = re.compile(r"([0-9A-F]{4})-?([0-9A-F]{4})")


def _hex(operacion_uuid) -> str:
    return uuid.UUID(str(operacion_uuid)).hex.upper()


def codigo_qr(operacion_uuid) -> str:
    """Lo que lleva el QR: `VTA` + 32 hex en mayúsculas."""
    return PREFIJO + _hex(operacion_uuid)


def folio_corto(operacion_uuid) -> str:
    """El folio escrito en el ticket: `3F9A-12BC`."""
    h = _hex(operacion_uuid)
    return f"{h[:4]}-{h[4:8]}"


def marcador_qr(operacion_uuid) -> str:
    """El renglón del ticket que pide el dibujo del QR (con el folio escrito
    de respaldo para la impresora que no sabe poner dibujos)."""
    from pos_uniformes.services.temporada_service import MARCADOR_FIN, MARCADOR_INICIO, SEPARADOR_RESPALDO

    return (
        f"{MARCADOR_INICIO}{PREFIJO_MARCADOR}{codigo_qr(operacion_uuid)}"
        f"{SEPARADOR_RESPALDO}Folio: {folio_corto(operacion_uuid)}{MARCADOR_FIN}"
    )


def _limpio(raw: str) -> str:
    # Lo que llega del lector: mayúsculas, sin espacios ni lo que el teclado
    # en español mete en lugar del guion.
    return re.sub(r"[\s'\-–]", "", str(raw or "")).upper()


def uuid_de_codigo(raw: str) -> str | None:
    """El `operacion_uuid` de un QR de venta escaneado, o None si no es uno."""
    m = _RE_CODIGO.fullmatch(_limpio(raw))
    return str(uuid.UUID(m.group(1))) if m else None


def es_folio_corto(raw: str) -> bool:
    """`3F9A-12BC` tecleado (con el guion: sin él se confundiría con un SKU
    de puros números)."""
    return bool(re.fullmatch(r"[0-9A-F]{4}[-'][0-9A-F]{4}", str(raw or "").strip().upper()))


def es_folio(raw: str) -> bool:
    """¿Lo escaneado o tecleado es el folio de una venta (QR o corto)?"""
    return uuid_de_codigo(raw) is not None or es_folio_corto(raw)


def buscar_venta(session, raw: str):
    """La venta (LibretaVenta) de un QR escaneado o de un folio corto escrito.

    None si no existe (o si aún no sube desde la cola sin conexión). Con un
    folio corto que le quedara a más de una venta, la más reciente."""
    from sqlalchemy import String, cast, select

    from pos_uniformes.database.models import LibretaVenta

    completo = uuid_de_codigo(raw)
    if completo:
        return session.scalars(
            select(LibretaVenta).where(LibretaVenta.operacion_uuid == completo)
        ).first()
    m = _RE_CORTO.fullmatch(str(raw or "").strip().upper().replace("'", "-"))
    if not m:
        return None
    prefijo = (m.group(1) + m.group(2)).lower()
    return session.scalars(
        select(LibretaVenta)
        .where(cast(LibretaVenta.operacion_uuid, String).like(f"{prefijo}%"))
        .order_by(LibretaVenta.created_at.desc())
    ).first()


def carpeta_qrs() -> Path:
    import tempfile

    carpeta = Path(tempfile.gettempdir()) / "pos_uniformes_qr_ticket"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


#: Fuentes en negritas para el recuadro, la de la tienda (Windows) primero.
_FUENTES = (
    "C:/Windows/Fonts/consolab.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
#: Ancho del recuadro: cabe en los 552 útiles del papel (576 menos márgenes).
ANCHO_RECUADRO = 540


def _fuente(tamano: int):
    from PIL import ImageFont

    for ruta in _FUENTES:
        if Path(ruta).exists():
            try:
                return ImageFont.truetype(ruta, size=tamano)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default(size=tamano)


def _fuente_que_quepa(draw, texto: str, tamano: int, ancho: int):
    while tamano > 12:
        f = _fuente(tamano)
        if draw.textlength(texto, font=f) <= ancho:
            return f
        tamano -= 2
    return _fuente(tamano)


def _dibujar_recuadro(codigo: str, destino: Path) -> None:
    """El QR dentro de un recuadro redondeado, con el folio grande al lado
    (Daniel, 2026-11-12: «ponerlo en un recuadro o algo»). Blanco y negro
    puro, que es lo que la térmica imprime limpio."""
    import qrcode
    from PIL import Image, ImageDraw
    from qrcode.constants import ERROR_CORRECT_M

    # 7 puntos por módulo: unos 3 cm en la térmica, de sobra para cualquier lector.
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=7, border=2)
    qr.add_data(codigo)
    qr.make(fit=True)
    dibujo = qr.make_image(fill_color="black", back_color="white").convert("L")

    aire, trazo = 16, 4
    alto = dibujo.height + 2 * aire
    lienzo = Image.new("L", (ANCHO_RECUADRO, alto), 255)
    draw = ImageDraw.Draw(lienzo)
    draw.rounded_rectangle((trazo // 2, trazo // 2, ANCHO_RECUADRO - 1 - trazo // 2, alto - 1 - trazo // 2),
                           radius=22, outline=0, width=trazo)
    lienzo.paste(dibujo, (aire, aire))

    # A la derecha: qué es, el folio en grande y para qué sirve.
    x = aire + dibujo.width + 10
    ancho = ANCHO_RECUADRO - x - aire - 4
    folio = folio_corto(uuid.UUID(codigo[len(PREFIJO):]))
    f_titulo = _fuente_que_quepa(draw, "FOLIO DE VENTA", 24, ancho)
    f_folio = _fuente_que_quepa(draw, folio, 46, ancho)
    f_nota = _fuente_que_quepa(draw, "cambios y aclaraciones", 20, ancho)
    renglones = [
        ("FOLIO DE VENTA", f_titulo, 10),
        (folio, f_folio, 14),
        (None, None, 14),                       # rayita
        ("Escanéalo para", f_nota, 4),
        ("cambios y aclaraciones", f_nota, 0),
    ]
    altos = [(f.getbbox(t)[3] if t else trazo // 2) for t, f, _ in renglones]
    total = sum(altos) + sum(sep for *_, sep in renglones)
    y = (alto - total) // 2
    for (texto, fuente, sep), h in zip(renglones, altos):
        if texto is None:
            draw.line((x, y, x + ancho, y), fill=0, width=2)
        else:
            draw.text((x + (ancho - draw.textlength(texto, font=fuente)) / 2, y), texto, font=fuente, fill=0)
        y += h + sep
    temporal = destino.with_suffix(".tmp.png")
    lienzo.point(lambda v: 255 if v > 140 else 0).convert("1").save(temporal)
    temporal.replace(destino)


def png_para_marcador(nombre: str) -> Path | None:
    """El PNG del QR enmarcado para el marcador `qr_VTA…` (se genera la
    primera vez). None si el nombre no es de un QR de venta."""
    if not nombre.startswith(PREFIJO_MARCADOR):
        return None
    codigo = nombre[len(PREFIJO_MARCADOR):]
    if not _RE_CODIGO.fullmatch(codigo):
        return None
    ruta = carpeta_qrs() / f"{codigo}_recuadro.png"
    if not ruta.exists():
        _dibujar_recuadro(codigo, ruta)
    return ruta
