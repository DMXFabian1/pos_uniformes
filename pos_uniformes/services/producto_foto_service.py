"""La foto del modelo: se sube una vez, se guarda en dos tamaños, viaja por hash.

Para la cuadrícula de Ropa del kiosko y, después, los uniformes (Daniel,
2026-10-20). Lo que cuida este módulo es que una foto nunca haga lento nada:

- Al subir se recorta y comprime AQUÍ, una sola vez: miniatura de ~400 px
  (~25 KB) y mediana de ~1000 px. El original (6 MB de celular) no se guarda.
- El catálogo que baja a los kioskos lleva solo el `hash`; los bytes se piden
  aparte, por producto, cuando hacen falta (`foto_local_cache_service`).

Convención del repo: mutan la Session pero NO hacen commit.
"""

from __future__ import annotations

import hashlib
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Producto, ProductoFoto

#: Lado largo de cada tamaño. La miniatura a 400 se ve nítida en una tarjeta
#: de 250 px aun en pantallas densas; la mediana llena la ficha.
LADO_MINIATURA = 400
LADO_MEDIANA = 1000
#: Proporción de la tarjeta (ancho:alto), como las tiendas de ropa en línea.
PROPORCION = (3, 4)
CALIDAD_MINIATURA = 82
CALIDAD_MEDIANA = 85
#: Un archivo más grande que esto no es una foto de producto.
MAXIMO_BYTES = 25 * 1024 * 1024


class NoSePuede(Exception):
    """Algo impide guardar la foto, dicho para enseñarlo en pantalla."""


def _abrir(datos: bytes):
    from PIL import Image, ImageOps

    if not datos:
        raise NoSePuede("No llegó ninguna imagen.")
    if len(datos) > MAXIMO_BYTES:
        raise NoSePuede("La imagen es demasiado grande (más de 25 MB).")
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise NoSePuede("Ese archivo no es una imagen que se pueda leer.") from exc
    # La orientación del celular viene en EXIF: sin esto la foto sale acostada.
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def recortar_a_proporcion(img, proporcion: tuple[int, int] = PROPORCION):
    """Recorta al centro para que todas las tarjetas midan igual."""
    pw, ph = proporcion
    ancho, alto = img.size
    objetivo = pw / ph
    actual = ancho / alto
    if abs(actual - objetivo) < 0.01:
        return img
    if actual > objetivo:          # demasiado ancha: se recortan los lados
        nuevo_ancho = int(round(alto * objetivo))
        x0 = (ancho - nuevo_ancho) // 2
        return img.crop((x0, 0, x0 + nuevo_ancho, alto))
    nuevo_alto = int(round(ancho / objetivo))   # demasiado alta: arriba y abajo
    y0 = (alto - nuevo_alto) // 2
    return img.crop((0, y0, ancho, y0 + nuevo_alto))


def _a_tamano(img, lado_largo: int, calidad: int) -> tuple[bytes, int, int]:
    from PIL import Image

    copia = img.copy()
    copia.thumbnail((lado_largo, lado_largo), Image.Resampling.LANCZOS)
    salida = io.BytesIO()
    copia.save(salida, format="JPEG", quality=calidad, optimize=True, progressive=True)
    return salida.getvalue(), copia.size[0], copia.size[1]


def preparar(datos: bytes) -> tuple[bytes, bytes, int, int, str]:
    """(miniatura, mediana, ancho, alto, hash) a partir de cualquier imagen. Puro."""
    img = recortar_a_proporcion(_abrir(datos))
    miniatura, _, _ = _a_tamano(img, LADO_MINIATURA, CALIDAD_MINIATURA)
    mediana, ancho, alto = _a_tamano(img, LADO_MEDIANA, CALIDAD_MEDIANA)
    return miniatura, mediana, ancho, alto, hashlib.md5(miniatura).hexdigest()


def guardar(session: Session, producto_id: int, datos: bytes) -> ProductoFoto:
    """Pone (o reemplaza) la foto del modelo."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise NoSePuede("Ese producto ya no existe.")
    miniatura, mediana, ancho, alto, hash_ = preparar(datos)
    foto = session.get(ProductoFoto, producto.id)
    if foto is None:
        foto = ProductoFoto(producto_id=producto.id, hash=hash_, miniatura=miniatura, mediana=mediana, ancho=ancho, alto=alto)
        session.add(foto)
    else:
        foto.hash, foto.miniatura, foto.mediana, foto.ancho, foto.alto = hash_, miniatura, mediana, ancho, alto
    session.flush()
    _avisar_catalogo()
    return foto


def quitar(session: Session, producto_id: int) -> bool:
    foto = session.get(ProductoFoto, int(producto_id))
    if foto is None:
        return False
    session.delete(foto)
    session.flush()
    _avisar_catalogo()
    return True


def miniatura(session: Session, producto_id: int) -> bytes | None:
    return session.scalar(select(ProductoFoto.miniatura).where(ProductoFoto.producto_id == int(producto_id)))


def mediana(session: Session, producto_id: int) -> bytes | None:
    return session.scalar(select(ProductoFoto.mediana).where(ProductoFoto.producto_id == int(producto_id)))


def hash_de(session: Session, producto_id: int) -> str:
    return str(session.scalar(select(ProductoFoto.hash).where(ProductoFoto.producto_id == int(producto_id))) or "")


def hashes(session: Session) -> dict[int, str]:
    """{producto_id: hash} de todas las fotos. Ligero: sin bytes."""
    return {int(pid): str(h) for pid, h in session.execute(select(ProductoFoto.producto_id, ProductoFoto.hash)).all()}


def _avisar_catalogo() -> None:
    """La foto cambia el catálogo que ven los kioskos (el hash va en él)."""
    try:
        from pos_uniformes.services.meilisearch_service import notify_catalog_changed

        notify_catalog_changed()
    except Exception:  # noqa: BLE001 — sin búsqueda, la foto se guardó igual
        pass
