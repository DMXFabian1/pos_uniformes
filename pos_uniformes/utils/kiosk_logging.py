"""Log persistente del kiosko (A2/A3 · C1, 2026-11-08).

El kiosko se empaqueta con `console=False`: no hay stdout/stderr
(`sys.stderr is None`) y, sin esto, `logger.error(...)` no llegaba a ningún
lado. Aquí se agrega a la raíz un `RotatingFileHandler` en

    <datos del satélite>/logs/kiosko.log   (1 MB × 5 respaldos)

No depende de la consola. Llamarlo varias veces no duplica el handler. El
modo `--servidor-impresion` tiene su propio archivo y no usa esto.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "kiosko.log"
MAX_BYTES = 1024 * 1024
BACKUPS = 5
_MARCA = "_pos_uniformes_kiosko_log"


def ruta_log(base: Path | None = None) -> Path:
    if base is None:
        from pos_uniformes.utils.config import satellite_data_dir

        base = satellite_data_dir()
    return Path(base) / "logs" / LOG_FILENAME


def configurar_log_kiosko(base: Path | None = None, *, nivel: int = logging.INFO) -> Path | None:
    """Instala (una sola vez) el log rotativo del kiosko. Devuelve la ruta,
    o None si no se pudo (el kiosko sigue funcionando igual)."""
    raiz = logging.getLogger()
    for h in raiz.handlers:
        if getattr(h, _MARCA, False):
            return Path(h.baseFilename)
    try:
        destino = ruta_log(base)
        destino.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(destino, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    except Exception:  # noqa: BLE001 — sin log, el kiosko igual arranca
        return None
    handler.setLevel(nivel)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s")
    )
    setattr(handler, _MARCA, True)
    raiz.addHandler(handler)
    if raiz.level == logging.NOTSET or raiz.level > nivel:
        raiz.setLevel(nivel)
    raiz.info("Log del kiosko activo en %s (consola: %s)", destino, sys.stderr is not None)
    return destino
