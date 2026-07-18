"""Identidad local de cada satélite: id estable + nombre editable.

Cada satélite necesita identificarse ante los demás para poder dirigirle
anuncios ("mostrar solo en Entrada y Caja 2"). Se guarda en un archivo local
que sobrevive reinicios:
- `id`: identificador estable (UUID corto) generado una sola vez por máquina.
- `nombre`: etiqueta legible que el usuario puede cambiar (default = hostname).

Sin Qt ni DB: solo archivo local, para que sea testeable y lo use tanto el
arranque como el menú admin.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import uuid
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_FILENAME = "satellite_identity.json"
_DATA_SUBDIR = "data"


def _path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _FILENAME


def _load() -> dict:
    path = _path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _hostname() -> str:
    try:
        return socket.gethostname() or "satelite"
    except Exception:  # noqa: BLE001
        return "satelite"


def get_satellite_id() -> str:
    """Id estable de esta máquina. Lo crea la primera vez y lo persiste."""
    data = _load()
    sid = data.get("id")
    if not sid:
        sid = uuid.uuid4().hex[:12]
        data["id"] = sid
        _save(data)
    return sid


def get_satellite_name() -> str:
    """Nombre legible de este satélite (default: nombre de la PC)."""
    data = _load()
    nombre = (data.get("nombre") or "").strip()
    return nombre or _hostname()


def set_satellite_name(nombre: str) -> str:
    """Cambia el nombre de este satélite. Devuelve el nombre efectivo guardado."""
    data = _load()
    limpio = (nombre or "").strip()[:60]
    if limpio:
        data["nombre"] = limpio
    else:
        data.pop("nombre", None)  # vuelve al default (hostname)
    # Asegura que el id exista aunque solo se cambie el nombre.
    if not data.get("id"):
        data["id"] = uuid.uuid4().hex[:12]
    _save(data)
    return get_satellite_name()
