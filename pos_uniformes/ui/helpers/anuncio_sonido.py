"""Hacer sonar un aviso, sin que el sonido pueda estropear el aviso.

La regla entera de este archivo: **si algo falla, el aviso se ve igual y en
silencio**. Un kiosko sin bocinas, sin códec o con el archivo mal escrito tiene
que seguir enseñando el recado — un aviso que no sale porque no pudo sonar
sería peor que no haber puesto sonido nunca.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: El reproductor se guarda vivo: si se lo lleva el recolector de basura a
#: media reproducción, el sonido se corta solo (clásico de QtMultimedia).
_vivo: list = []


def reproducir(nombre: str | None) -> bool:
    """Suena ese sonido de `assets/sonidos`. True si se mandó a sonar."""
    if not nombre:
        return False
    try:
        from pos_uniformes.services import sonidos_service as sn

        ruta = sn.buscar(nombre)
    except Exception:  # noqa: BLE001
        logger.exception("Aviso: no se pudo buscar el sonido %r", nombre)
        return False
    if ruta is None:
        logger.info("Aviso: no tengo el sonido %r; sale mudo.", nombre)
        return False

    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

        player = QMediaPlayer()
        salida = QAudioOutput()
        player.setAudioOutput(salida)
        salida.setVolume(1.0)
        player.setSource(QUrl.fromLocalFile(str(ruta)))
        player.play()
        _vivo.append((player, salida))
        # No se guardan para siempre: con dos avisos seguidos basta y sobra.
        del _vivo[:-3]
        return True
    except Exception:  # noqa: BLE001 — sin audio el aviso sale igual
        logger.exception("Aviso: no se pudo reproducir %s", ruta)
        return False
