"""Las fotos de los modelos en el disco de ESTE kiosko.

La cuadrícula de Ropa lee las miniaturas de aquí, nunca de la base: así pinta
en milisegundos y funciona sin red (Daniel, 2026-10-20: «lo que más me importa
es que no se haga lento»). Lo que hay que saber:

- Cada archivo se llama por su `hash`: si el hash del catálogo coincide con el
  archivo, ya está; si no, se baja. Una foto nueva es un hash nuevo.
- `sincronizar` corre en el MISMO hilo de fondo que baja el catálogo, después
  de guardarlo: baja solo lo que falta y borra lo que ya nadie usa.
- La mediana (para la ficha) se baja la primera vez que se abre esa ficha y
  se queda; son pocas y grandes, no vale la pena bajarlas todas.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

logger = logging.getLogger(__name__)

_CARPETA = "fotos"


def carpeta() -> Path:
    return satellite_data_dir() / "data" / _CARPETA


def ruta_miniatura(hash_: str) -> Path | None:
    """La miniatura en disco, o None si no está (todavía)."""
    if not hash_:
        return None
    ruta = carpeta() / f"{hash_}.jpg"
    return ruta if ruta.exists() else None


def ruta_mediana(hash_: str) -> Path | None:
    if not hash_:
        return None
    ruta = carpeta() / f"{hash_}.m.jpg"
    return ruta if ruta.exists() else None


def _escribir(ruta: Path, datos: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_bytes(datos)
    tmp.replace(ruta)


def sincronizar(session, snapshot_rows: list[dict]) -> int:
    """Baja las miniaturas que faltan y borra las que sobran. Devuelve cuántas bajó.

    `snapshot_rows` es el catálogo recién bajado: de ahí salen los hashes que
    deben existir. Una que no se pueda bajar no detiene a las demás."""
    from pos_uniformes.services import producto_foto_service as fotos

    esperados: dict[str, int] = {}
    for row in snapshot_rows:
        h = str(row.get("foto_hash") or "")
        if h:
            esperados.setdefault(h, int(row.get("producto_id") or 0))
    bajadas = 0
    for h, producto_id in esperados.items():
        if ruta_miniatura(h) is not None or not producto_id:
            continue
        try:
            datos = fotos.miniatura(session, producto_id)
            if datos:
                _escribir(carpeta() / f"{h}.jpg", datos)
                bajadas += 1
        except Exception:  # noqa: BLE001 — la siguiente foto sí puede bajar
            logger.warning("No se pudo bajar la foto de %s", producto_id, exc_info=True)
    try:
        for archivo in carpeta().glob("*.jpg"):
            h = archivo.name.split(".")[0]
            if h not in esperados:
                archivo.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 — limpiar es lo de menos
        pass
    return bajadas


def asegurar_mediana(session, producto_id: int, hash_: str) -> Path | None:
    """La mediana en disco; si no está, la baja ahora (una sola vez)."""
    ruta = ruta_mediana(hash_)
    if ruta is not None:
        return ruta
    if not hash_ or session is None:
        return None
    try:
        from pos_uniformes.services import producto_foto_service as fotos

        datos = fotos.mediana(session, producto_id)
        if not datos:
            return None
        destino = carpeta() / f"{hash_}.m.jpg"
        _escribir(destino, datos)
        return destino
    except Exception:  # noqa: BLE001 — sin red, la ficha sale con la miniatura
        logger.debug("No se pudo bajar la mediana de %s", producto_id, exc_info=True)
        return None
