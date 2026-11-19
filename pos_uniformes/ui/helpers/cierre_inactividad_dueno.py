"""La sesión del dueño se cierra sola tras 5 minutos sin tocar el kiosko
(Daniel, 2026-11-19).

El filtro global de teclas del kiosko (`_KioskKeyFilter`) llama a
`notar_actividad()` con cada tecla, clic o toque: eso reinicia el QTimer. Si
vence, y la Libreta o Conteos están abiertas como dueño, se cierran. Las
sesiones de las empleadas no se tocan.

La regla (¿ya pasaron los minutos?) es `pin_dueno_service.debe_cerrar_sesion`.

Al cerrar también se cierran (Cancelar) los diálogos modales que el dueño dejó
abiertos sobre el kiosko —historial de cortes, pagos, equipo, calendario…—:
si no, el que llegue seguiría operando como dueño aunque la sesión de abajo ya
se haya cerrado. Como el filtro es global, teclear dentro de un diálogo
también cuenta como actividad: solo se cierra lo que lleva 5 min sin tocarse.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Callable

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QDialog

from pos_uniformes.services.pin_dueno_service import MINUTOS_INACTIVIDAD, debe_cerrar_sesion

logger = logging.getLogger(__name__)

AVISO_CIERRE = "Se cerró la sesión del dueño por inactividad."


#: Tope de vueltas al cerrar diálogos encimados (por si uno se reabre solo).
_MAX_DIALOGOS = 20


def _cuelga_de(widget, ventana) -> bool:
    """¿`widget` es la ventana o cuelga de ella (padre, abuelo…)? `isAncestorOf`
    no sirve: un diálogo es otra ventana."""
    w = widget
    while w is not None:
        if w is ventana:
            return True
        try:
            w = w.parent()
        except Exception:  # noqa: BLE001
            return False
    return False


def cerrar_dialogos_abiertos(ventana) -> int:
    """Cierra (como Cancelar) los modales abiertos encima de la ventana del
    kiosko, del más nuevo al más viejo. Devuelve cuántos cerró."""
    app = QApplication.instance()
    if app is None:
        return 0
    cerrados = 0
    for _ in range(_MAX_DIALOGOS):
        modal = app.activeModalWidget()
        if modal is None or not _cuelga_de(modal, ventana):
            break
        try:
            if isinstance(modal, QDialog):
                modal.reject()
            else:
                modal.close()
        except Exception:  # noqa: BLE001 — que uno no deje los demás abiertos
            logger.exception("Inactividad: no se pudo cerrar un diálogo del dueño")
            break
        if app.activeModalWidget() is modal:  # no se dejó cerrar
            break
        cerrados += 1
    return cerrados


def _hay_sesion_de_dueno(ventana) -> bool:
    try:
        if getattr(ventana, "_libreta_is_owner", False):
            return True
        es_dueno = getattr(ventana, "_conteos_es_dueno", None)
        return bool(callable(es_dueno) and es_dueno())
    except Exception:  # noqa: BLE001
        return False


def cerrar_sesiones_de_dueno(ventana) -> bool:
    """Cierra la Libreta y/o Conteos si están abiertas como dueño, con los
    diálogos que quedaron abiertos encima. True si cerró algo."""
    if _hay_sesion_de_dueno(ventana):
        try:
            cerrar_dialogos_abiertos(ventana)
        except Exception:  # noqa: BLE001
            logger.exception("Inactividad: no se pudieron cerrar los diálogos del dueño")
    cerro = False
    try:
        if getattr(ventana, "_libreta_is_owner", False):
            ventana._libreta_logout()
            cerro = True
    except Exception:  # noqa: BLE001 — que una falla no deje la otra abierta
        logger.exception("Inactividad: no se pudo cerrar la Libreta del dueño")
    try:
        es_dueno = getattr(ventana, "_conteos_es_dueno", None)
        if callable(es_dueno) and es_dueno():
            ventana._conteos_logout()
            cerro = True
    except Exception:  # noqa: BLE001
        logger.exception("Inactividad: no se pudo cerrar Conteos del dueño")
    if cerro:
        try:
            ventana._set_status(AVISO_CIERRE)
        except Exception:  # noqa: BLE001
            pass
    return cerro


class CierreInactividadDueno(QObject):
    """QTimer de un disparo que se reinicia con cada actividad."""

    def __init__(
        self,
        ventana,
        *,
        minutos: float = MINUTOS_INACTIVIDAD,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(ventana if isinstance(ventana, QObject) else None)
        self._ventana = ventana
        self._minutos = float(minutos)
        self._reloj = reloj
        self._ultimo_toque = reloj()
        self._intervalo_ms = int(self._minutos * 60_000)
        self.timer = QTimer(self)
        # El tipo por omisión (Coarse) en intervalos largos redondea al
        # segundo y puede vencer medio segundo ANTES: revisar() vería 299.6 s,
        # no cerraría y esperaría otros 5 min completos.
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.setInterval(self._intervalo_ms)
        self.timer.timeout.connect(self.revisar)
        self.timer.start()

    @property
    def ultimo_toque(self) -> float:
        return self._ultimo_toque

    def notar_actividad(self) -> None:
        self._ultimo_toque = self._reloj()
        self.timer.start(self._intervalo_ms)  # reinicia la cuenta completa

    def revisar(self) -> bool:
        """Al vencer el timer. True si cerró alguna sesión de dueño."""
        ahora = self._reloj()
        if not debe_cerrar_sesion(self._ultimo_toque, ahora, self._minutos):
            # Venció antes de tiempo o hubo actividad que el timer no vio:
            # se rearma SOLO por lo que falta, no por otros 5 minutos.
            faltan = self._minutos * 60 - (ahora - self._ultimo_toque)
            self.timer.start(max(1, math.ceil(faltan * 1000)))
            return False
        return cerrar_sesiones_de_dueno(self._ventana)
