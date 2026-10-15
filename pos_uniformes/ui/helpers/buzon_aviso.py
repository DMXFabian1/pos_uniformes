"""Aviso de mensajes nuevos del buzón, en la esquina de la ventana.

Con el buzón cerrado no había forma de enterarse de que llegó algo: había que
entrar al menú admin a ver (Daniel, 2026-10-15). Esto es una pastilla verde
—«💬 2 mensajes nuevos»— abajo a la derecha que aparece sola y abre el buzón
al tocarla. Sin mensajes, no se ve.

La consulta va en un hilo: un kiosko sin red no se congela por preguntar.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QWidget

logger = logging.getLogger(__name__)

#: Cada cuánto se pregunta si hay algo nuevo.
INTERVALO_MS = 20_000
#: Distancia a la orilla de la ventana.
MARGEN = 18


class BuzonAviso(QPushButton):
    """La pastilla. `contar` y `abrir` se cambian en las pruebas."""

    _contado = pyqtSignal(int)

    def __init__(
        self,
        ventana: QWidget,
        *,
        contar=None,
        abrir=None,
        intervalo_ms: int = INTERVALO_MS,
        en_hilo: bool = True,
    ) -> None:
        super().__init__(ventana)
        self._ventana = ventana
        self._contar = contar or _contar_no_leidos
        self._abrir = abrir or _abrir_buzon
        self._en_hilo = en_hilo
        # Con nombre propio, para que la hoja de estilo de la ventana no le
        # gane. Y el radio a la mitad del alto exacto: si lo pasa, Qt lo
        # ignora y la pastilla sale cuadrada.
        self.setObjectName("buzonAviso")
        self.setStyleSheet(
            "QPushButton#buzonAviso { background: #00a884; color: #ffffff; border: none;"
            " border-radius: 20px; min-height: 40px; padding: 0 18px; font-size: 14px; font-weight: 700; }"
            "QPushButton#buzonAviso:hover { background: #008f72; }"
        )
        self.setToolTip("Abrir el buzón entre PCs")
        self.hide()
        self.clicked.connect(self._al_tocar)
        self._contado.connect(self.pintar)
        ventana.installEventFilter(self)

        # Hijos de la pastilla: mueren con ella.
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.revisar)
        self._timer.start()
        self._primera = QTimer(self)
        self._primera.setSingleShot(True)
        self._primera.setInterval(3_000)
        self._primera.timeout.connect(self.revisar)
        self._primera.start()

    def revisar(self) -> None:
        if not self._en_hilo:
            self._contar_y_avisar()
            return
        import threading

        threading.Thread(target=self._contar_y_avisar, daemon=True, name="buzon-aviso").start()

    def _contar_y_avisar(self) -> None:
        try:
            n = int(self._contar() or 0)
        except Exception:  # noqa: BLE001 — sin base no se avisa nada, y ya
            logger.debug("Buzón: no se pudo contar", exc_info=True)
            return
        try:
            self._contado.emit(n)
        except RuntimeError:  # la ventana ya se cerró
            pass

    def pintar(self, n: int) -> None:
        if n <= 0:
            self.hide()
            return
        self.setText(f"💬 {n} mensaje{'s' if n != 1 else ''} nuevo{'s' if n != 1 else ''}")
        self.adjustSize()
        self._colocar()
        self.show()
        self.raise_()

    def _colocar(self) -> None:
        ancho, alto = self._ventana.width(), self._ventana.height()
        self.move(ancho - self.width() - MARGEN, alto - self.height() - MARGEN)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 — nombre de Qt
        if obj is self._ventana and event.type() == QEvent.Type.Resize:
            self._colocar()
        return False

    def _al_tocar(self) -> None:
        self.hide()
        self._abrir(self._ventana)
        self.revisar()          # lo que se leyó ya no cuenta


def _contar_no_leidos() -> int:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import buzon_service as bz

    try:
        from pos_uniformes.services.satellite_startup_service import probe_database_host

        if not probe_database_host(0.5):
            return 0
    except Exception:  # noqa: BLE001
        pass
    with get_session() as session:
        return bz.no_leidos_total(session, yo=bz.mi_nombre(), leidos=bz.leidos())


def _abrir_buzon(ventana: QWidget) -> None:
    from pos_uniformes.ui.dialogs.buzon_dialog import abrir_buzon

    abrir_buzon(ventana)
