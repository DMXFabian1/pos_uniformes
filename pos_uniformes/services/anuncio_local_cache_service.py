"""Cache local de anuncios para que la cartelera funcione sin conexión.

Guarda los anuncios activos (metadata JSON + imágenes como archivos) en
`data/anuncios/`. Así, si el satélite arranca o queda con la PC principal
apagada (p.ej. de 9 a 11), la cartelera sigue mostrando lo último difundido en
vez de quedarse en blanco.

El display lee `imagen_path` (ruta a archivo local) — no maneja bytes ni DB.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_DATA_SUBDIR = "data"
_ANUNCIOS_DIR = "anuncios"
_INDEX_FILENAME = "index.json"

_EXT_POR_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _dir() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _ANUNCIOS_DIR


def _index_path() -> Path:
    return _dir() / _INDEX_FILENAME


def _ext_para(mime: str | None) -> str:
    return _EXT_POR_MIME.get((mime or "").lower(), ".img")


def save_anuncios_cache(anuncios: list[dict]) -> None:
    """Persiste los anuncios activos en disco (metadata + imágenes).

    Cada dict acepta: id, titulo, mensaje, imagen_mime, imagen_bytes (bytes|None),
    duracion_seg, prioridad. Sobreescribe el cache anterior y borra las imágenes
    de anuncios que ya no están activos.
    """
    carpeta = _dir()
    carpeta.mkdir(parents=True, exist_ok=True)

    vigentes: set[str] = set()
    entradas: list[dict] = []
    for a in anuncios:
        anuncio_id = a.get("id")
        if anuncio_id is None:
            continue
        imagen_archivo = None
        imagen_bytes = a.get("imagen_bytes")
        if imagen_bytes:
            imagen_archivo = f"{anuncio_id}{_ext_para(a.get('imagen_mime'))}"
            _atomic_write_bytes(carpeta / imagen_archivo, imagen_bytes)
            vigentes.add(imagen_archivo)
        entradas.append(
            {
                "id": anuncio_id,
                "titulo": a.get("titulo"),
                "mensaje": a.get("mensaje"),
                "imagen_archivo": imagen_archivo,
                "duracion_seg": int(a.get("duracion_seg") or 8),
                "prioridad": int(a.get("prioridad") or 0),
            }
        )

    _atomic_write_text(
        _index_path(),
        json.dumps({"anuncios": entradas}, ensure_ascii=False),
    )
    _limpiar_imagenes_huerfanas(carpeta, vigentes)


def load_anuncios_cache() -> list[dict]:
    """Lee los anuncios cacheados. Devuelve [] si no hay o está corrupto.

    Cada dict incluye `imagen_path` (ruta absoluta str al archivo local, o None).
    """
    path = _index_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entradas = payload.get("anuncios")
        if not isinstance(entradas, list):
            return []
    except Exception:  # noqa: BLE001
        return []

    carpeta = _dir()
    salida: list[dict] = []
    for e in entradas:
        archivo = e.get("imagen_archivo")
        imagen_path = None
        if archivo:
            ruta = carpeta / archivo
            if ruta.exists():
                imagen_path = str(ruta)
        salida.append(
            {
                "id": e.get("id"),
                "titulo": e.get("titulo"),
                "mensaje": e.get("mensaje"),
                "imagen_path": imagen_path,
                "duracion_seg": int(e.get("duracion_seg") or 8),
                "prioridad": int(e.get("prioridad") or 0),
            }
        )
    return salida


def clear_anuncios_cache() -> None:
    """Borra todo el cache de anuncios (index + imágenes)."""
    carpeta = _dir()
    if not carpeta.exists():
        return
    for hijo in carpeta.iterdir():
        try:
            hijo.unlink()
        except OSError:
            pass


def _limpiar_imagenes_huerfanas(carpeta: Path, vigentes: set[str]) -> None:
    """Borra archivos de imagen que ya no corresponden a un anuncio activo."""
    for hijo in carpeta.iterdir():
        if hijo.name == _INDEX_FILENAME or not hijo.is_file():
            continue
        if hijo.name not in vigentes:
            try:
                hijo.unlink()
            except OSError:
                pass


def _atomic_write_text(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except BaseException:
        _rm(tmp)
        raise


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        _rm(tmp)
        raise


def _rm(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
