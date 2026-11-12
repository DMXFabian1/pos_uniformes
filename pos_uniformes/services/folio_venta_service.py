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


def png_para_marcador(nombre: str) -> Path | None:
    """El PNG del QR para el marcador `qr_VTA…` (se genera la primera vez).
    None si el nombre no es de un QR de venta."""
    if not nombre.startswith(PREFIJO_MARCADOR):
        return None
    codigo = nombre[len(PREFIJO_MARCADOR):]
    if not _RE_CODIGO.fullmatch(codigo):
        return None
    ruta = carpeta_qrs() / f"{codigo}.png"
    if not ruta.exists():
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        # 7 puntos por módulo: unos 3 cm en la térmica de 576 puntos, de
        # sobra para cualquier lector, y en blanco y negro puro (sin grises).
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=7, border=3)
        qr.add_data(codigo)
        qr.make(fit=True)
        temporal = ruta.with_suffix(".tmp.png")
        qr.make_image(fill_color="black", back_color="white").convert("1").save(temporal)
        temporal.replace(ruta)
    return ruta
