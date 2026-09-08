"""Visor de cámaras del DVR dentro del kiosko (Ctrl+Shift+C / botón "Cámaras").

Reproduce los canales RTSP del DVR con QtMultimedia (ffmpeg viene dentro de
PyQt6, no hay dependencias nuevas). Reglas:

  - Abre en modo *empleada*: solo las cámaras marcadas como entrada.
  - "Ver todas" pide el PIN de administrador y muestra todos los canales.
  - Al cerrar la ventana vuelve a modo empleada (el PIN no queda "pegado").
  - Doble clic en una cámara la amplía sola con el stream principal; Esc regresa.
  - Si un stream falla, muestra "Sin señal" y reintenta cada pocos segundos.

Los reproductores se detienen al ocultar/cerrar para no gastar red ni CPU.
"""

from __future__ import annotations

import math
from typing import Callable

from PyQt6.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.dvr_settings_cache_service import CanalDVR, DVRSettings, load_dvr_settings

_RETRY_MS = 5000
PlayerFactory = Callable[[], object]


def _default_player_factory():
    from PyQt6.QtMultimedia import QMediaPlayer

    return QMediaPlayer()


def _default_video_widget_factory() -> QWidget:
    from PyQt6.QtMultimediaWidgets import QVideoWidget

    return QVideoWidget()


def _default_pin_prompt(parent: QWidget) -> bool:
    from pos_uniformes.ui.dialogs.satellite_admin_dialog import _prompt_pin

    return _prompt_pin(parent)


class CameraTile(QFrame):
    """Una cámara: video + nombre + estado. Reintenta sola si se cae el stream."""

    ampliar = pyqtSignal(int)

    def __init__(
        self,
        canal: CanalDVR,
        player_factory: PlayerFactory,
        video_factory: Callable[[], QWidget],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.canal = canal
        self.url: str | None = None
        self._activo = False
        self.setObjectName("cameraTile")
        self.setStyleSheet(
            "#cameraTile { background: #111; border: 1px solid #333; border-radius: 6px; }"
            "QLabel { color: #f4ede2; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.video = video_factory()
        self.video.setMinimumSize(240, 135)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.player = player_factory()
        self.player.setVideoOutput(self.video)

        self.name_label = QLabel(canal.nombre)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 14px; padding: 2px 6px;")
        self.status_label = QLabel("Conectando…")
        self.status_label.setStyleSheet("color: #d7c9a8; font-size: 12px; padding: 2px 6px;")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(self.status_label)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addWidget(self.video, 1)
        self.setLayout(layout)

        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_status)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(_RETRY_MS)
        self._retry.timeout.connect(self._reconnect)

    # -- ciclo de vida -------------------------------------------------------
    def start(self, url: str) -> None:
        self.url = url
        self._activo = True
        self.status_label.setText("Conectando…")
        self.player.setSource(QUrl(url))
        self.player.play()

    def stop(self) -> None:
        self._activo = False
        self._retry.stop()
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:  # noqa: BLE001
            pass

    def _reconnect(self) -> None:
        if self._activo and self.url:
            self.start(self.url)

    # -- señales del reproductor -------------------------------------------
    def _on_error(self, *_args) -> None:
        if not self._activo:
            return
        self.status_label.setText("Sin señal · reintentando")
        self._retry.start()

    def _on_status(self, status) -> None:
        nombre = getattr(status, "name", str(status))
        if nombre in ("BufferedMedia", "BufferingMedia"):
            self.status_label.setText("En vivo")
        elif nombre in ("InvalidMedia", "EndOfMedia", "NoMedia") and self._activo:
            self.status_label.setText("Sin señal · reintentando")
            self._retry.start()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        self.ampliar.emit(self.canal.canal)
        super().mouseDoubleClickEvent(event)


class CameraWallDialog(QDialog):
    """Mosaico de cámaras. No modal: convive con el kiosko."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_loader: Callable[[], DVRSettings] = load_dvr_settings,
        player_factory: PlayerFactory | None = None,
        video_factory: Callable[[], QWidget] | None = None,
        pin_prompt: Callable[[QWidget], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_loader = settings_loader
        self._player_factory = player_factory or _default_player_factory
        self._video_factory = video_factory or _default_video_widget_factory
        self._pin_prompt = pin_prompt or _default_pin_prompt
        self._admin = False
        self._ampliado: int | None = None
        self._tiles: list[CameraTile] = []

        self.setWindowTitle("Cámaras")
        self.setModal(False)
        self.setStyleSheet("QDialog { background: #1c1c1c; }")

        self.title_label = QLabel("Cámaras")
        self.title_label.setStyleSheet("color: #f4ede2; font-size: 20px; font-weight: 700;")
        self.mode_label = QLabel()
        self.mode_label.setStyleSheet("color: #d7c9a8; font-size: 13px;")
        self.admin_button = QPushButton()
        self.admin_button.clicked.connect(self._toggle_admin)
        self.back_button = QPushButton("← Volver al mosaico")
        self.back_button.clicked.connect(self._volver_al_mosaico)
        self.back_button.setVisible(False)
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.close)
        for b in (self.admin_button, self.back_button, self.close_button):
            b.setMinimumHeight(36)
            b.setStyleSheet(
                "QPushButton { background: #3a3a3a; color: #f4ede2; border-radius: 6px; padding: 6px 14px; }"
                "QPushButton:hover { background: #505050; }"
            )

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addSpacing(12)
        header.addWidget(self.mode_label)
        header.addStretch()
        header.addWidget(self.back_button)
        header.addWidget(self.admin_button)
        header.addWidget(self.close_button)

        self.message_label = QLabel()
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #d7c9a8; font-size: 16px; padding: 40px;")
        self.message_label.setVisible(False)

        self.grid_host = QWidget()
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.grid_host.setLayout(self.grid)

        outer = QVBoxLayout()
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        outer.addLayout(header)
        outer.addWidget(self.message_label)
        outer.addWidget(self.grid_host, 1)
        self.setLayout(outer)
        self._refresh_header()

        screen = self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(int(avail.width() * 0.75), int(avail.height() * 0.8))

    # -- API pública ---------------------------------------------------------
    def es_admin(self) -> bool:
        return self._admin

    def set_admin(self, admin: bool) -> None:
        self._admin = bool(admin)
        self._ampliado = None
        self._refresh_header()
        if self.isVisible():
            self._rebuild()

    def tiles_activos(self) -> list[tuple[int, str]]:
        """(canal, url) de cada cámara reproduciéndose. Útil en tests."""
        return [(t.canal.canal, t.url or "") for t in self._tiles]

    # -- construcción --------------------------------------------------------
    def _refresh_header(self) -> None:
        if self._admin:
            self.mode_label.setText("Administrador · todas las cámaras")
            self.admin_button.setText("Solo entradas")
        else:
            self.mode_label.setText("Cámaras de entrada")
            self.admin_button.setText("Ver todas (PIN)")
        self.back_button.setVisible(self._ampliado is not None)

    def _clear_tiles(self) -> None:
        for tile in self._tiles:
            tile.stop()
            self.grid.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        self._tiles = []

    def _rebuild(self) -> None:
        self._clear_tiles()
        settings = self._settings_loader()
        if not settings.configurado():
            self._show_message(
                "Las cámaras no están configuradas en este equipo.\n"
                "Administración (Ctrl+Shift+A) → pestaña Cámaras."
            )
            return
        canales = settings.canales_visibles(self._admin)
        if self._ampliado is not None:
            canales = [c for c in canales if c.canal == self._ampliado]
            if not canales:
                self._ampliado = None
                canales = settings.canales_visibles(self._admin)
        if not canales:
            self._show_message(
                "No hay cámaras de entrada configuradas."
                if not self._admin
                else "El DVR no tiene canales configurados. Usa 'Detectar canales' en Administración."
            )
            return
        self.message_label.setVisible(False)
        self.grid_host.setVisible(True)
        ampliada = self._ampliado is not None
        cols = 1 if ampliada else max(1, math.ceil(math.sqrt(len(canales))))
        for idx, canal in enumerate(canales):
            tile = CameraTile(canal, self._player_factory, self._video_factory, self.grid_host)
            tile.ampliar.connect(self._ampliar)
            self.grid.addWidget(tile, idx // cols, idx % cols)
            tile.start(settings.rtsp_url(canal.canal, substream=not ampliada))
            self._tiles.append(tile)
        self._refresh_header()

    def _show_message(self, texto: str) -> None:
        self.message_label.setText(texto)
        self.message_label.setVisible(True)
        self.grid_host.setVisible(False)
        self._refresh_header()

    # -- acciones ------------------------------------------------------------
    def _toggle_admin(self) -> None:
        if self._admin:
            self.set_admin(False)
            return
        if self._pin_prompt(self):
            self.set_admin(True)
        else:
            QMessageBox.warning(self, "PIN incorrecto", "PIN incorrecto.")

    def _ampliar(self, canal: int) -> None:
        self._ampliado = canal
        self._rebuild()

    def _volver_al_mosaico(self) -> None:
        self._ampliado = None
        self._rebuild()

    # -- eventos Qt ----------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._rebuild()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._clear_tiles()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._clear_tiles()
        # Al cerrar, el modo admin se olvida: la siguiente apertura vuelve a
        # pedir PIN. Evita dejar el vestidor a la vista en el mostrador.
        self._admin = False
        self._ampliado = None
        self._refresh_header()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self._ampliado is not None:
                self._volver_al_mosaico()
                return
            self.close()
            return
        super().keyPressEvent(event)
