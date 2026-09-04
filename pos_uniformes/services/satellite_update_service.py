"""Buscar y aplicar actualizaciones del satélite desde la PC principal.

Un exe no puede sobreescribirse mientras corre, así que "aplicar" =
cerrar la app y relanzarla a través del lanzador (lanzador_satelite.bat),
que copia la versión nueva desde \\<servidor>\pos_updates y la abre.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_SHARE_NAME = "pos_updates"
_BUNDLE_DIR = "PresupuestosSatelite"
_LAUNCHER = "lanzador_satelite.bat"


def _share_dir() -> Path | None:
    from pos_uniformes.utils.config import server_db_host

    host = server_db_host()
    if not host:
        return None
    return Path(rf"\\{host}\{_SHARE_NAME}")


def version_local() -> str:
    from pos_uniformes.utils.app_metadata import app_version

    return str(app_version()).strip()


def version_remota() -> str | None:
    """VERSION.txt publicado por la build en la PC principal (o None si el
    share no está disponible)."""
    share = _share_dir()
    if share is None:
        return None
    try:
        version_file = share / _BUNDLE_DIR / "VERSION.txt"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
    return None


def estado_actualizacion() -> tuple[str, str | None, bool]:
    """(version_local, version_remota, hay_actualizacion)."""
    local = version_local()
    remota = version_remota()
    return local, remota, bool(remota) and remota != local


def lanzar_actualizador() -> bool:
    """Abre el lanzador (que actualizará y reabrirá la app). El caller debe
    cerrar la app inmediatamente después para soltar los archivos."""
    candidatos = [Path(r"C:\PresupuestosSatelite") / _LAUNCHER]
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidatos.append(Path(localappdata) / "PresupuestosSatelite" / _LAUNCHER)
    share = _share_dir()
    if share is not None:
        candidatos.append(share / _LAUNCHER)
    for bat in candidatos:
        try:
            if bat.exists():
                subprocess.Popen(
                    ["cmd", "/c", "start", "", str(bat)], close_fds=True
                )
                return True
        except OSError:
            continue
    return False
