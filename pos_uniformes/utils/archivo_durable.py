"""Escritura durable de archivos de datos del kiosko (C1 · H-M2, 2026-11-08).

`path.write_text(...)` + `replace` es atómico ante un error de Python, pero NO
ante un apagón: el sistema puede no haber bajado los bytes al disco y, al
volver la luz, el archivo queda vacío o truncado. Aquí:

1. se escribe a un temporal en la MISMA carpeta;
2. `flush` + `os.fsync` del temporal (los bytes llegan al disco);
3. `os.replace` atómico sobre el destino;
4. `fsync` de la carpeta, donde la plataforma lo permite (POSIX). En Windows
   no se puede abrir una carpeta para `fsync`; NTFS registra el renombrado
   en su bitácora, que es lo más que se puede pedir sin APIs nativas.

Si algo falla antes del reemplazo, el destino queda como estaba y el temporal
se limpia. El error sube a quien llamó.
"""

from __future__ import annotations

import os
from pathlib import Path


def sincronizar_carpeta(carpeta: Path) -> None:
    """`fsync` de la carpeta (para que el renombrado sobreviva un apagón).
    No hace nada en Windows ni si la plataforma no lo permite."""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(carpeta), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def escribir_atomico(path: Path, texto: str, *, temporal: Path | None = None) -> None:
    """Escribe `texto` en `path` de forma atómica y durable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(temporal) if temporal is not None else path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(texto)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    sincronizar_carpeta(path.parent)
