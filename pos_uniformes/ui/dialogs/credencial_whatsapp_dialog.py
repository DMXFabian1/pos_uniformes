"""Kiosko: «Credencial lista» después de registrar a un cliente nuevo.

Enseña la credencial y deja un solo botón: «Enviar por WhatsApp». Ese botón
copia la imagen, abre WhatsApp Web en el chat del cliente con el mensaje ya
escrito y se cierra. La empleada pega (Ctrl+V) y da Enviar.

WhatsApp Web, no la app de escritorio, y en su propia ventana como el mapa
(Daniel, 2026-11-10): ver `abrir_whatsapp_web` en `ui/helpers/abrir_consultas.py`.
La parte de datos está en `services/clientes/credencial_whatsapp_service.py`.
"""

from __future__ import annotations

from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.services.clientes.credencial_whatsapp_service import EnvioCredencial
from pos_uniformes.ui.styles import kiosko_clientes_styles

SIN_WHATSAPP = "No se pudo abrir WhatsApp Web en esta PC. La credencial ya quedó copiada."


def copiar_imagen(envio: EnvioCredencial) -> bool:
    imagen = QImage(str(envio.imagen))
    if imagen.isNull():
        return False
    QGuiApplication.clipboard().setImage(imagen)
    return True


def _abrir_por_omision(url: str, parent: QWidget | None) -> bool:
    from pos_uniformes.ui.helpers.abrir_consultas import abrir_whatsapp_web

    return abrir_whatsapp_web(url, parent)


class CredencialWhatsappDialog(QDialog):
    def __init__(self, parent: QWidget | None, envio: EnvioCredencial, *, abrir=None, proponer=None) -> None:
        super().__init__(parent)
        kiosko_clientes_styles.aplicar(self)
        self.setWindowTitle("Credencial lista")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._envio = envio
        #: `abrir(url, parent) -> bool`; inyectable para las pruebas.
        self._abrir = abrir or _abrir_por_omision
        self.enviado = False

        ly = QVBoxLayout(self)
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(12)
        titulo = QLabel("¡Cliente registrado!")
        titulo.setObjectName("kcTitulo")
        ly.addWidget(titulo)
        subtitulo = QLabel(
            f"<b>{escape(envio.nombre)}</b> · {escape(envio.codigo)}. Mándale su credencial por WhatsApp: "
            "se abre su chat con el mensaje escrito, tú pegas la credencial (Ctrl+V) y das Enviar."
        )
        subtitulo.setObjectName("kcSubtitulo")
        subtitulo.setWordWrap(True)
        ly.addWidget(subtitulo)
        if envio.programa:
            self.programa_label = QLabel(f"★ Ya es miembro de {escape(envio.programa)}")
            self.programa_label.setObjectName("kcAviso")
            ly.addWidget(self.programa_label)

        self.vista = QLabel()
        self.vista.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(str(envio.imagen))
        if not pix.isNull():
            self.vista.setPixmap(pix.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation))
        else:
            self.vista.setText("No se pudo mostrar la credencial.")
            self.vista.setObjectName("kcVacio")
        ly.addWidget(self.vista, 1)

        self.paso_label = QLabel("")
        self.paso_label.setObjectName("kcNota")
        self.paso_label.setWordWrap(True)
        self.paso_label.setVisible(False)
        ly.addWidget(self.paso_label)

        botones = QHBoxLayout()
        #: `proponer() -> bool`: abre «Proponer programa» para este cliente.
        self._proponer = proponer
        self.proponer_button = QPushButton("Proponer programa…")
        self.proponer_button.setObjectName("kcSecundario")
        self.proponer_button.setAutoDefault(False)
        self.proponer_button.setVisible(proponer is not None)
        self.proponer_button.clicked.connect(self._on_proponer)
        botones.addWidget(self.proponer_button)
        self.ahora_no_button = QPushButton("Ahora no")
        self.ahora_no_button.setObjectName("kcFantasma")
        self.ahora_no_button.setAutoDefault(False)
        self.ahora_no_button.clicked.connect(self.reject)
        self.enviar_button = QPushButton("Enviar por WhatsApp")
        self.enviar_button.setObjectName("kcPrimario")
        self.enviar_button.setAutoDefault(True)
        self.enviar_button.setDefault(True)
        self.enviar_button.clicked.connect(self._enviar)
        botones.addStretch()
        botones.addWidget(self.ahora_no_button)
        botones.addWidget(self.enviar_button)
        ly.addLayout(botones)

    def _on_proponer(self) -> None:
        if self._proponer is not None and self._proponer():
            self.proponer_button.setText("✓ Propuesta enviada")
            self.proponer_button.setEnabled(False)

    def _enviar(self) -> None:
        copiada = copiar_imagen(self._envio)
        # La ventana de WhatsApp es del kiosko, no de este diálogo: sigue
        # abierta después de cerrarlo.
        abierto = bool(self._abrir(self._envio.url_web, self.parentWidget()))
        self.enviado = abierto
        if abierto and copiada:
            self.accept()
            return
        if abierto:
            self.paso_label.setText(
                "Ya está abierto el chat con el mensaje, pero no se pudo copiar la imagen. "
                f"La credencial está en {self._envio.imagen}."
            )
        else:
            self.paso_label.setText(SIN_WHATSAPP if copiada else f"No se pudo abrir WhatsApp Web. La credencial está en {self._envio.imagen}.")
        self.paso_label.setVisible(True)
