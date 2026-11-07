"""El mapa de escuelas, desde cualquier PC (2026-11-07).

Daniel (10/10): «añadir el mapa de escuelas al satélite». El mapa vive en
`mapas_escuelas/` del repo; el kiosko lo trae dentro del ejecutable (ver el
spec del satélite). Al abrirlo se copia a una carpeta temporal junto con un
`estados_pos.js` calculado en ese momento, así los anillos de conteo son los
de ahora y no los del día que se generó el mapa ni los de la última vez que
alguien regeneró el Panel en la principal.

Sin conexión el mapa abre igual, con el estado que trae dentro (y él mismo
avisa «sin actualizar»)."""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

NOMBRE = "mapa_escuelas_san_felipe.html"


def ubicar_mapa() -> Path | None:
    """El HTML del mapa: dentro del ejecutable o en el repo."""
    candidatos = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidatos.append(Path(meipass) / "mapas_escuelas" / NOMBRE)
    candidatos.append(Path(__file__).resolve().parents[2] / "mapas_escuelas" / NOMBRE)
    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return None


def preparar(destino: Path | None = None, *, estados=None, calcular=None) -> Path | None:
    """Copia el mapa a `destino` con su `estados_pos.js` y devuelve la ruta del HTML.

    `estados`: los de `escuela_estado_service.estados_de_todas`; si no vienen se
    calculan con `calcular()` (por defecto, contra la base). Si eso falla se
    borra el `estados_pos.js` viejo para que el mapa no presuma un estado que
    no es de hoy."""
    origen = ubicar_mapa()
    if origen is None:
        return None
    destino = Path(destino or Path(tempfile.gettempdir()) / "pos_mapa_escuelas")
    destino.mkdir(parents=True, exist_ok=True)
    html = destino / NOMBRE
    shutil.copyfile(origen, html)

    from pos_uniformes.services import escuela_estado_service as svc

    js = destino / "estados_pos.js"
    try:
        if estados is None:
            estados = (calcular or _calcular)()
        svc.escribir_estados_para_mapa(estados, js)
    except Exception:  # noqa: BLE001 — sin base el mapa abre con lo que trae dentro
        logger.warning("Mapa de escuelas: no se pudo calcular el estado de los conteos", exc_info=True)
        js.unlink(missing_ok=True)
    return html


def _calcular() -> dict:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import escuela_estado_service as svc

    with get_session() as session:
        return svc.estados_de_todas(session)
