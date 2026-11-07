"""Escribir un archivo de estado sin que pueda quedar a medias (2026-11-07).

Auditoría del bot, #33: el offset, la lista de mensajes, la conexión y la
memoria del vigilante se escribían con `write_text`. Un apagón o un antivirus
a media escritura dejaba el JSON roto; con el offset roto el bot volvía a
ejecutar los toques del último lote. Aquí se escribe a un temporal junto al
archivo y se reemplaza de un golpe (`os.replace` es atómico en Windows y Mac).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def escribir_texto(ruta: Path | str, texto: str) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(ruta))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def escribir_json(ruta: Path | str, datos, **kwargs) -> None:
    escribir_texto(ruta, json.dumps(datos, **kwargs))
