"""Reproductor de grabaciones del DVR alrededor de un momento ("Ver momento").

Se abre desde la Libreta con la fecha/hora de un movimiento y reproduce la
grabación de la cámara desde un minuto antes hasta dos minutos después. No se
guarda nada: el DVR entrega el clip por RTSP (`cam/playback`) y QMediaPlayer lo
trata como un archivo (duración conocida, se puede adelantar y pausar).

Mismas reglas de acceso que el visor en vivo: sin PIN solo cámaras de entrada;
"Ver todas (PIN)" habilita el resto (CAJA, mostradores, vestidor).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.dvr_settings_cache_service import CanalDVR, DVRSettings, load_dvr_settings
from pos_uniformes.ui.dialogs.camera_wall_dialog import (
    PlayerFactory,
    _default_pin_prompt,
    _default_player_factory,
    _default_video_widget_factory,
)

ANTES = timedelta(minutes=1)
DESPUES = timedelta(minutes=2)
SALTO = timedelta(minutes=1)
CANAL_PREFERIDO = "CAJA"

_BTN_STYLE = (
    "QPushButton { background: #3a3a3a; color: #f4ede2; border-radius: 6px; padding: 6px 12px; }"
    "QPushButton:hover { background: #505050; }"
    "QPushButton:disabled { color: #777; }"
)


class CameraPlaybackDialog(QDialog):
    def __init__(
        self,
        momento: datetime,
        parent: QWidget | None = None,
        *,
        titulo: str = "",
        canal_preferido: str = CANAL_PREFERIDO,
        admin: bool = False,
        settings_loader: Callable[[], DVRSettings] = load_dvr_settings,
        player_factory: PlayerFactory | None = None,
        video_factory: Callable[[], QWidget] | None = None,
        pin_prompt: Callable[[QWidget], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.momento = momento.replace(microsecond=0)
        self._canal_preferido = canal_preferido
        self._settings_loader = settings_loader
        self._pin_prompt = pin_prompt or _default_pin_prompt
        # `admin=True` cuando quien abre ya se identificó como dueño (gafete
        # VEND-1 en la Libreta): no tiene sentido pedirle el PIN otra vez.
        self._admin = bool(admin)
        self._inicio = self.momento - ANTES
        self._fin = self.momento + DESPUES
        self.url: str | None = None
        self._settings = DVRSettings()

        self.setWindowTitle("Ver momento")
        self.setModal(False)
        self.setStyleSheet("QDialog { background: #1c1c1c; } QLabel { color: #f4ede2; }")

        self.title_label = QLabel(titulo or "Ver momento")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.momento_label = QLabel(self.momento.strftime("%d/%m/%Y %H:%M:%S"))
        self.momento_label.setStyleSheet("color: #d7c9a8; font-size: 13px;")
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(160)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self.admin_button = QPushButton("Ver todas (PIN)")
        self.admin_button.clicked.connect(self._toggle_admin)
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.close)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addSpacing(10)
        header.addWidget(self.momento_label)
        header.addStretch()
        header.addWidget(QLabel("Cámara:"))
        header.addWidget(self.camera_combo)
        header.addWidget(self.admin_button)
        header.addWidget(self.close_button)

        self.video = (video_factory or _default_video_widget_factory)()
        self.video.setMinimumSize(480, 270)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.player = (player_factory or _default_player_factory)()
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)

        self.message_label = QLabel()
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #d7c9a8; font-size: 15px; padding: 30px;")
        self.message_label.setVisible(False)

        self.play_button = QPushButton("⏸ Pausa")
        self.play_button.clicked.connect(self._toggle_play)
        self.earlier_button = QPushButton("◀ 1 min antes")
        self.earlier_button.clicked.connect(lambda: self._desplazar(-SALTO))
        self.later_button = QPushButton("1 min después ▶")
        self.later_button.clicked.connect(lambda: self._desplazar(SALTO))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderReleased.connect(self._on_seek)
        self.time_label = QLabel("--:--:--")
        self.time_label.setStyleSheet("color: #d7c9a8; font-family: monospace;")
        self.status_label = QLabel("Cargando grabación…")
        self.status_label.setStyleSheet("color: #d7c9a8; font-size: 12px;")

        controls = QHBoxLayout()
        controls.addWidget(self.earlier_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.later_button)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)
        for b in (self.admin_button, self.close_button, self.play_button, self.earlier_button, self.later_button):
            b.setMinimumHeight(34)
            b.setStyleSheet(_BTN_STYLE)

        outer = QVBoxLayout()
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        outer.addLayout(header)
        outer.addWidget(self.message_label)
        outer.addWidget(self.video, 1)
        outer.addLayout(controls)
        outer.addWidget(self.status_label)
        self.setLayout(outer)

        screen = self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(int(avail.width() * 0.6), int(avail.height() * 0.7))

        self._rebuild_cameras()

    # -- API pública ---------------------------------------------------------
    def es_admin(self) -> bool:
        return self._admin

    def canal_actual(self) -> CanalDVR | None:
        return self.camera_combo.currentData()

    def ventana(self) -> tuple[datetime, datetime]:
        return self._inicio, self._fin

    # -- cámaras -------------------------------------------------------------
    def _rebuild_cameras(self) -> None:
        self._settings = self._settings_loader()
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        if not self._settings.configurado():
            self.camera_combo.blockSignals(False)
            self._show_message(
                "Las cámaras no están configuradas en este equipo.\n"
                "Administración (Ctrl+Shift+A) → pestaña Cámaras."
            )
            return
        canales = self._settings.canales_visibles(self._admin)
        for c in canales:
            self.camera_combo.addItem(c.nombre, c)
        preferido = self._settings.canal_por_nombre(self._canal_preferido, self._admin)
        if preferido is not None:
            self.camera_combo.setCurrentIndex(canales.index(preferido))
        self.camera_combo.blockSignals(False)
        self.admin_button.setText("Solo entradas" if self._admin else "Ver todas (PIN)")
        if not canales:
            self._show_message(
                "No hay cámaras de entrada configuradas."
                if not self._admin
                else "El DVR no tiene canales configurados."
            )
            return
        self.message_label.setVisible(False)
        self.video.setVisible(True)
        self._cargar()

    def _on_camera_changed(self, _idx: int) -> None:
        self._cargar()

    def _toggle_admin(self) -> None:
        if self._admin:
            self._admin = False
            self._rebuild_cameras()
            return
        if self._pin_prompt(self):
            self._admin = True
            self._rebuild_cameras()
        else:
            QMessageBox.warning(self, "PIN incorrecto", "PIN incorrecto.")

    # -- reproducción --------------------------------------------------------
    def _cargar(self) -> None:
        canal = self.canal_actual()
        if canal is None:
            return
        self.url = self._settings.playback_url(canal.canal, self._inicio, self._fin)
        self.status_label.setText(
            f"Grabación {self._inicio.strftime('%H:%M:%S')} → {self._fin.strftime('%H:%M:%S')} · cargando…"
        )
        self.slider.setRange(0, 0)
        self.player.setSource(QUrl(self.url))
        self.player.play()
        self.play_button.setText("⏸ Pausa")

    def _desplazar(self, delta: timedelta) -> None:
        self._inicio += delta
        self._fin += delta
        self._cargar()

    def _toggle_play(self) -> None:
        estado = getattr(self.player, "playbackState", lambda: None)()
        nombre = getattr(estado, "name", str(estado))
        if nombre == "PlayingState":
            self.player.pause()
            self.play_button.setText("▶ Reproducir")
        else:
            self.player.play()
            self.play_button.setText("⏸ Pausa")

    def _on_seek(self) -> None:
        self.player.setPosition(int(self.slider.value()))

    def _on_duration(self, dur_ms: int) -> None:
        self.slider.setRange(0, int(dur_ms or 0))

    def _on_position(self, pos_ms: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(int(pos_ms or 0))
        actual = self._inicio + timedelta(milliseconds=int(pos_ms or 0))
        self.time_label.setText(actual.strftime("%H:%M:%S"))

    def _on_status(self, status) -> None:
        nombre = getattr(status, "name", str(status))
        if nombre in ("BufferedMedia", "BufferingMedia", "LoadedMedia"):
            self.status_label.setText(
                f"Grabación {self._inicio.strftime('%H:%M:%S')} → {self._fin.strftime('%H:%M:%S')}"
            )
        elif nombre == "EndOfMedia":
            self.status_label.setText("Fin del clip. Usa '1 min después' para seguir.")
            self.play_button.setText("▶ Reproducir")
        elif nombre == "InvalidMedia":
            self.status_label.setText("El DVR no tiene grabación en ese rango (o no responde).")

    def _on_error(self, *_args) -> None:
        self.status_label.setText("No se pudo cargar la grabación del DVR.")

    def _show_message(self, texto: str) -> None:
        self.message_label.setText(texto)
        self.message_label.setVisible(True)
        self.video.setVisible(False)

    # -- eventos Qt ----------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:  # noqa: BLE001
            pass
        self._admin = False
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        if event.key() == Qt.Key.Key_Space:
            self._toggle_play()
            return
        super().keyPressEvent(event)
