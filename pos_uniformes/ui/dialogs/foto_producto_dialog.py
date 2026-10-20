"""La foto del modelo, desde la webcam o desde un archivo.

Daniel la toma con la prenda en la mano (2026-10-20): se abre la cámara, se
ve en vivo, «Tomar foto», y queda. Sin cámara, «Elegir archivo…» hace lo
mismo con una foto del celular copiada a la PC. El recorte y la compresión los
hace `producto_foto_service`; aquí solo se captura.

Las fábricas de cámara se inyectan para poder probar la ventana sin hardware.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_ESTILO = """
QDialog { background: #f4ede2; }
QLabel { color: #2c2a27; background: transparent; }
QLabel#vista { background: #1d1a17; border-radius: 12px; }
QPushButton { background: #f8f2e9; color: #73341c; font-weight: 700; border: 1px solid #ddd0c0;
              border-radius: 10px; min-height: 40px; padding: 0 16px; }
QPushButton#primario { background: #a84f2d; color: #ffffff; border: none; }
QPushButton:disabled { color: #b5aa9c; }
QPushButton#primario:disabled { background: #d9c7bb; color: #f8f2e9; }
"""


class _Camara:
    """La webcam de esta PC, envuelta para que la ventana no sepa de Qt Multimedia."""

    def __init__(self, video_widget: QWidget) -> None:
        from PyQt6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices

        dispositivos = QMediaDevices.videoInputs()
        if not dispositivos:
            raise RuntimeError("Esta PC no tiene cámara.")
        self.camara = QCamera(dispositivos[0])
        self.sesion = QMediaCaptureSession()
        self.captura = QImageCapture(self.camara)
        self.sesion.setCamera(self.camara)
        self.sesion.setImageCapture(self.captura)
        self.sesion.setVideoOutput(video_widget)
        self.nombre = dispositivos[0].description()

    def iniciar(self) -> None:
        self.camara.start()

    def detener(self) -> None:
        try:
            self.camara.stop()
        except Exception:  # noqa: BLE001
            pass

    def tomar(self, al_capturar) -> None:
        """`al_capturar(QImage)` cuando llegue la foto."""
        self.captura.imageCaptured.connect(lambda _id, imagen: al_capturar(imagen))
        self.captura.capture()


def _video_widget() -> QWidget:
    from PyQt6.QtMultimediaWidgets import QVideoWidget

    return QVideoWidget()


def imagen_a_bytes(imagen: QImage) -> bytes:
    """JPEG de calidad alta; el servicio lo recorta y lo achica después."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagen.save(buffer, "JPEG", 92)
    return bytes(buffer.data())


class FotoProductoDialog(QDialog):
    """Devuelve con `self.cambio = True` si la foto cambió."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        producto_id: int,
        titulo: str = "",
        session_factory=None,
        camara_factory=_Camara,
        video_factory=_video_widget,
        con_camara: bool = True,
    ) -> None:
        super().__init__(parent)
        if session_factory is None:
            from pos_uniformes.database.connection import get_session

            session_factory = get_session
        self._session_factory = session_factory
        self._producto_id = int(producto_id)
        self._camara = None
        self.cambio = False

        self.setWindowTitle("Foto del modelo")
        self.setStyleSheet(_ESTILO)
        self.resize(760, 640)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 16, 18, 14)
        raiz.setSpacing(10)
        encabezado = QLabel(f"📷 {titulo or 'Foto del modelo'}")
        encabezado.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        raiz.addWidget(encabezado)
        self.pista = QLabel("Acomoda la prenda, que se vea completa, y toma la foto. Se recorta sola.")
        self.pista.setWordWrap(True)
        self.pista.setStyleSheet("font-size: 12px; color: #8a8177;")
        raiz.addWidget(self.pista)

        fila = QHBoxLayout()
        self.vista = QLabel("Sin cámara")
        self.vista.setObjectName("vista")
        self.vista.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vista.setStyleSheet("color: #d8d0c4;")
        self.vista.setMinimumSize(420, 420)
        self._video = None
        if con_camara:
            try:
                self._video = video_factory()
                self._camara = camara_factory(self._video)
                self._video.setMinimumSize(420, 420)
                fila.addWidget(self._video, 3)
                self.pista.setText(f"Cámara: {self._camara.nombre}. Acomoda la prenda y toma la foto; se recorta sola.")
            except Exception as exc:  # noqa: BLE001 — sin cámara, con archivo
                logger.info("Sin cámara: %s", exc)
                self._camara = None
                self._video = None
        if self._video is None:
            fila.addWidget(self.vista, 3)
        self.actual = QLabel("Sin foto")
        self.actual.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.actual.setStyleSheet("background: #ffffff; border: 1px solid #ddd0c0; border-radius: 12px; color: #8a8177;")
        self.actual.setFixedSize(240, 320)
        fila.addWidget(self.actual, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addLayout(fila, 1)

        self.estado = QLabel("")
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet("font-size: 12px; color: #a33b25; font-weight: 600;")
        raiz.addWidget(self.estado)

        botones = QHBoxLayout()
        self.tomar_btn = QPushButton("📷 Tomar foto")
        self.tomar_btn.setObjectName("primario")
        self.tomar_btn.setEnabled(self._camara is not None)
        self.tomar_btn.clicked.connect(self._tomar)
        botones.addWidget(self.tomar_btn)
        self.archivo_btn = QPushButton("📁 Elegir archivo…")
        self.archivo_btn.clicked.connect(self._elegir_archivo)
        botones.addWidget(self.archivo_btn)
        self.quitar_btn = QPushButton("Quitar foto")
        self.quitar_btn.clicked.connect(self._quitar)
        botones.addWidget(self.quitar_btn)
        botones.addStretch(1)
        cerrar = QPushButton("Listo")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        raiz.addLayout(botones)

        self._pintar_actual()
        if self._camara is not None:
            self._camara.iniciar()

    # ── Captura ─────────────────────────────────────────────────────────

    def _tomar(self) -> None:
        if self._camara is None:
            return
        self.tomar_btn.setEnabled(False)
        self._camara.tomar(self._capturada)

    def _capturada(self, imagen: QImage) -> None:
        self.tomar_btn.setEnabled(True)
        if imagen is None or imagen.isNull():
            self._avisar("La cámara no entregó la foto. Intenta otra vez.")
            return
        self.guardar(imagen_a_bytes(imagen))

    def _elegir_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Foto del modelo", "", "Imágenes (*.jpg *.jpeg *.png *.webp *.heic)")
        if not ruta:
            return
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        except OSError as exc:
            self._avisar(f"No se pudo leer el archivo: {exc}")
            return
        self.guardar(datos)

    def guardar(self, datos: bytes) -> None:
        from pos_uniformes.services import producto_foto_service as fotos

        try:
            with self._session_factory() as session:
                fotos.guardar(session, self._producto_id, datos)
                session.commit()
        except fotos.NoSePuede as exc:
            self._avisar(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Foto: no se pudo guardar")
            self._avisar("No se pudo guardar la foto. Revisa la conexión.")
            return
        self.cambio = True
        self._avisar("")
        self._pintar_actual()

    def _quitar(self) -> None:
        from pos_uniformes.services import producto_foto_service as fotos

        try:
            with self._session_factory() as session:
                fotos.quitar(session, self._producto_id)
                session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Foto: no se pudo quitar")
            self._avisar("No se pudo quitar la foto.")
            return
        self.cambio = True
        self._pintar_actual()

    # ── Pintar ──────────────────────────────────────────────────────────

    def _pintar_actual(self) -> None:
        from pos_uniformes.services import producto_foto_service as fotos

        try:
            with self._session_factory() as session:
                datos = fotos.miniatura(session, self._producto_id)
        except Exception:  # noqa: BLE001
            datos = None
        if not datos:
            self.actual.setPixmap(QPixmap())
            self.actual.setText("Sin foto")
            self.quitar_btn.setEnabled(False)
            return
        pixmap = QPixmap()
        pixmap.loadFromData(datos)
        self.actual.setText("")
        self.actual.setPixmap(pixmap.scaled(
            self.actual.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        self.quitar_btn.setEnabled(True)

    def _avisar(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.setVisible(bool(texto))

    def closeEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        if self._camara is not None:
            self._camara.detener()
        super().closeEvent(event)

    def done(self, r: int) -> None:  # noqa: D102 — accept/reject también apagan la cámara
        if self._camara is not None:
            self._camara.detener()
        super().done(r)


def abrir_foto_producto(parent, *, producto_id: int, titulo: str = "") -> bool:
    """True si la foto cambió."""
    d = FotoProductoDialog(parent, producto_id=producto_id, titulo=titulo)
    d.exec()
    return d.cambio
