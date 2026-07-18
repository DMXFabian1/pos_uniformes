"""Reduce imágenes de anuncios antes de embeberlas en la DB.

Las imágenes viajan por la misma conexión que ya usa el satélite, así que
conviene bajarlas de tamaño: se reescalan a un lado máximo y se recodifican a
JPEG. Usa Pillow (ya es dependencia del proyecto para etiquetas). Sin Qt, para
que sea testeable y reusable desde cualquier capa.
"""

from __future__ import annotations

import io
from pathlib import Path

_MAX_LADO_DEFAULT = 1600  # px del lado más largo — suficiente para pantallas de kiosko
_CALIDAD_DEFAULT = 85


def preparar_imagen(
    origen: str | Path | bytes,
    *,
    max_lado: int = _MAX_LADO_DEFAULT,
    calidad: int = _CALIDAD_DEFAULT,
) -> tuple[bytes, str]:
    """Devuelve (bytes_jpeg, mime) de la imagen reducida.

    `origen` puede ser una ruta o bytes. Reescala si el lado más largo supera
    `max_lado` (mantiene proporción; nunca agranda), aplana transparencia sobre
    blanco y recodifica a JPEG. Lanza ValueError si no se puede leer la imagen.
    """
    from PIL import Image, ImageOps

    try:
        if isinstance(origen, (bytes, bytearray)):
            img = Image.open(io.BytesIO(bytes(origen)))
        else:
            img = Image.open(Path(origen))
        # Respeta la orientación EXIF (fotos de celular) antes de descartar metadata.
        img = ImageOps.exif_transpose(img)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo abrir la imagen: {exc}") from exc

    # Aplana alpha/paleta sobre fondo blanco para poder guardar en JPEG.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[-1])
        img = fondo
    elif img.mode != "RGB":
        img = img.convert("RGB")

    ancho, alto = img.size
    lado_mayor = max(ancho, alto)
    if lado_mayor > max_lado:
        factor = max_lado / float(lado_mayor)
        nuevo = (max(1, int(ancho * factor)), max(1, int(alto * factor)))
        img = img.resize(nuevo, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=calidad, optimize=True)
    return buffer.getvalue(), "image/jpeg"
