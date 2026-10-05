"""Los sonidos que puede hacer un aviso al salir en las pantallas.

Viven como archivos en `assets/sonidos/` y viajan dentro de la app del
satélite, así que no hace falta mandarlos por la red cada vez ni guardarlos en
la base: el kiosko ya los trae.

La regla que ordena todo esto: **el sonido nunca puede impedir que el aviso se
vea**. Si el archivo no está, si el nombre está mal escrito o si el kiosko no
trae el códec, el aviso sale igual y en silencio.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

#: Lo que se intenta reproducir. El .wav es el que siempre funciona.
EXTENSIONES = (".wav", ".mp3", ".ogg")


def carpeta() -> Path:
    """Dónde viven los sonidos.

    Mismo camino que los dibujos de temporada: dentro del .exe del satélite el
    árbol del paquete queda bajo _MEIPASS y `__file__` cae ahí solo."""
    return Path(__file__).resolve().parents[1] / "assets" / "sonidos"


def clave(nombre: str) -> str:
    """«Risa del Payaso.wav» → «risadelpayaso»: así se escribe sin acentos ni
    espacios, que es lo que no se puede teclear cómodo en el celular."""
    base = Path(str(nombre or "")).stem
    plano = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    return "".join(c for c in plano.lower() if c.isalnum())


def disponibles() -> list[tuple[str, Path]]:
    """[(clave, ruta)] de los sonidos que hay, en orden alfabético."""
    try:
        archivos = [
            p for p in carpeta().iterdir()
            if p.is_file() and p.suffix.lower() in EXTENSIONES
        ]
    except Exception:  # noqa: BLE001 — sin carpeta, no hay sonidos y ya
        return []
    return sorted(((clave(p.name), p) for p in archivos), key=lambda t: t[0])


def nombres() -> list[str]:
    """Solo las claves, para enseñarlas en Telegram."""
    return [c for c, _ in disponibles()]


def buscar(nombre: str) -> Path | None:
    """La ruta del sonido que se pidió, o None si no está."""
    pedido = clave(nombre)
    if not pedido:
        return None
    for c, ruta in disponibles():
        if c == pedido:
            return ruta
    return None


def existe(nombre: str) -> bool:
    return buscar(nombre) is not None
