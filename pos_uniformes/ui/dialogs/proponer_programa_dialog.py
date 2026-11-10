"""E4-C: la empleada propone a un cliente para Profesional o Mayorista.

Solo junta el programa y el motivo; quien llama guarda la propuesta. Nunca
muestra ni promete porcentajes: lo decide el dueño.
"""

from __future__ import annotations

from html import escape

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from pos_uniformes.services.fidelizacion.membresia_service import MOTIVO_PROPUESTA_MINIMO
from pos_uniformes.ui.styles import kiosko_clientes_styles

PROGRAMAS = (
    ("PROFESIONAL", "Maximoda Profesional", "Docentes y profesionales que compran seguido."),
    ("MAYORISTA", "Maximoda Mayorista", "Negocios o instituciones que compran por volumen."),
)


class ProponerProgramaDialog(QDialog):
    def __init__(self, parent=None, *, nombre_cliente: str) -> None:
        super().__init__(parent)
        kiosko_clientes_styles.aplicar(self)
        self.setWindowTitle("Proponer programa")
        self.setMinimumWidth(520)
        self.resultado: tuple[str, str] | None = None

        ly = QVBoxLayout(self)
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(10)
        titulo = QLabel("Proponer programa")
        titulo.setObjectName("kcTitulo")
        ly.addWidget(titulo)
        para = QLabel(f"Para <b>{escape(nombre_cliente)}</b>. Lo aprueba el dueño.")
        para.setObjectName("kcSubtitulo")
        ly.addWidget(para)
        ly.addSpacing(4)

        self.opciones: dict[str, QRadioButton] = {}
        for clave, nombre, ayuda in PROGRAMAS:
            radio = QRadioButton(f"★ {nombre}\n{ayuda}")
            radio.setObjectName("kcOpcion")
            radio.toggled.connect(self._validar)
            self.opciones[clave] = radio
            ly.addWidget(radio)

        ly.addSpacing(4)
        pregunta = QLabel("¿POR QUÉ? (LO LEE EL DUEÑO PARA DECIDIR)")
        pregunta.setObjectName("kcSeccion")
        ly.addWidget(pregunta)
        self.motivo_input = QPlainTextEdit()
        self.motivo_input.setPlaceholderText("Ej.: maestra de la Benito Juárez, compra para su grupo")
        self.motivo_input.setFixedHeight(96)
        self.motivo_input.textChanged.connect(self._validar)
        ly.addWidget(self.motivo_input)

        self.aviso = QLabel("")
        self.aviso.setObjectName("kcAviso")
        ly.addWidget(self.aviso)
        nota = QLabel("Queda pendiente hasta que el dueño la apruebe. Si en 7 días no hay respuesta, caduca.")
        nota.setObjectName("kcNota")
        nota.setWordWrap(True)
        ly.addWidget(nota)

        botones = QHBoxLayout()
        botones.addStretch()
        self.cancelar_button = QPushButton("Cancelar")
        self.cancelar_button.setObjectName("kcFantasma")
        self.cancelar_button.setAutoDefault(False)
        self.cancelar_button.clicked.connect(self.reject)
        self.enviar_button = QPushButton("Enviar propuesta")
        self.enviar_button.setObjectName("kcPrimario")
        self.enviar_button.setAutoDefault(False)
        self.enviar_button.clicked.connect(self._enviar)
        botones.addWidget(self.cancelar_button)
        botones.addWidget(self.enviar_button)
        ly.addLayout(botones)
        self._validar()

    def _clave(self) -> str | None:
        for clave, radio in self.opciones.items():
            if radio.isChecked():
                return clave
        return None

    def _validar(self) -> None:
        motivo = self.motivo_input.toPlainText().strip()
        falta = MOTIVO_PROPUESTA_MINIMO - len(motivo)
        if self._clave() is None:
            self.aviso.setText("Elige un programa.")
        elif falta > 0:
            self.aviso.setText(f"Escribe el motivo (faltan {falta} caracteres).")
        else:
            self.aviso.setText("")
        self.enviar_button.setEnabled(self._clave() is not None and falta <= 0)

    def _enviar(self) -> None:
        clave = self._clave()
        motivo = self.motivo_input.toPlainText().strip()
        if clave is None or len(motivo) < MOTIVO_PROPUESTA_MINIMO:
            return
        self.resultado = (clave, motivo)
        self.accept()
