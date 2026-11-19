"""El diálogo del PIN del dueño en el kiosko (Daniel, 2026-11-19).

Toda puerta del kiosko que deja actuar como dueño (Libreta, Conteos, precio
especial, cambios fuera de plazo, pagos del Calendario) pide su PIN con:

    if not pedir_pin_dueno(self, en_linea=not self.offline_mode, motivo="..."):
        return

La regla (base o copia local, intentos, mensajes) vive en
`services/pin_dueno_service.py`; aquí solo se pregunta.

En pruebas se parchea `pedir_pin_dueno` de ESTE módulo (las puertas lo leen
al momento de llamar), así ninguna prueba abre un diálogo de verdad.
"""

from __future__ import annotations

import time
from typing import Callable

from PyQt6.QtCore import QRegularExpression, Qt, QTimer
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import pin_dueno_service as pin_svc

TITULO = "PIN del dueño"

#: Los intentos fallidos cuentan entre un diálogo y otro: cerrar y volver a
#: abrir no reinicia el bloqueo.
CONTROL_INTENTOS = pin_svc.ControlIntentos()

_ESTILO = (
    "QDialog { background: #fdf8f3; }"
    "QLabel { color: #3d2e22; background: transparent; }"
    "QLabel#pinTitulo { font-size: 19px; font-weight: 800; color: #73341c; }"
    "QLabel#pinMotivo { font-size: 14px; }"
    "QLabel#pinAviso { font-size: 14px; font-weight: 700; color: #a3281b; }"
    "QLineEdit { background: #ffffff; color: #73341c;"
    "  border: 2px solid #a84f2d; border-radius: 12px;"
    "  min-height: 56px; padding: 0 14px; font-size: 26px; font-weight: 800; }"
    "QPushButton#pinAceptar { background: #87492c; color: #ffffff; border: none;"
    "  border-radius: 12px; min-height: 52px; font-size: 17px; font-weight: 800; }"
    "QPushButton#pinCancelar { background: #ffffff; color: #3d2e22;"
    "  border: 1.5px solid #ddd0c0; border-radius: 12px; min-height: 52px; font-size: 17px; }"
)


def en_linea_de(widget: QWidget | None) -> bool:
    """¿La ventana del kiosko que contiene a `widget` está en línea?
    Sube por los padres buscando `offline_mode`; sin dato, se asume en línea
    (el servicio cae solo a la copia local si la base no responde)."""
    w = widget
    while w is not None:
        if hasattr(w, "offline_mode"):
            try:
                return not bool(w.offline_mode)
            except Exception:  # noqa: BLE001
                return True
        try:
            w = w.parent()
        except Exception:  # noqa: BLE001
            return True
    return True


class PinDuenoDialog(QDialog):
    """Modal: el motivo, el PIN (oculto), teclado táctil sin punto, Aceptar/Cancelar.

    `autorizado` queda en True solo si el PIN se confirmó. Los parámetros con
    nombre son para las pruebas."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        en_linea: bool,
        motivo: str,
        verificar: Callable[..., pin_svc.ResultadoPin] | None = None,
        control: pin_svc.ControlIntentos | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._en_linea = bool(en_linea)
        self._verificar = verificar or pin_svc.verificar_pin_dueno
        self._control = control if control is not None else CONTROL_INTENTOS
        self._reloj = reloj
        self.autorizado = False
        self.setWindowTitle(TITULO)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(_ESTILO)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(10)

        titulo = QLabel("🔒 " + TITULO)
        titulo.setObjectName("pinTitulo")
        ly.addWidget(titulo)
        self.motivo_label = QLabel(motivo or "Escribe tu PIN para continuar.")
        self.motivo_label.setObjectName("pinMotivo")
        self.motivo_label.setWordWrap(True)
        ly.addWidget(self.motivo_label)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setMaxLength(8)
        self.pin_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,8}"), self.pin_input))
        self.pin_input.setPlaceholderText("PIN")
        self.pin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_input.returnPressed.connect(self._aceptar)
        ly.addWidget(self.pin_input)

        self.aviso_label = QLabel("")
        self.aviso_label.setObjectName("pinAviso")
        self.aviso_label.setWordWrap(True)
        self.aviso_label.setVisible(False)
        ly.addWidget(self.aviso_label)

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        ly.addLayout(QuickSaleWidget._teclado_numerico(self.pin_input, con_punto=False))

        botones = QHBoxLayout()
        botones.setSpacing(10)
        self.cancelar_button = QPushButton("Cancelar")
        self.cancelar_button.setObjectName("pinCancelar")
        self.cancelar_button.setAutoDefault(False)
        self.cancelar_button.clicked.connect(self.reject)
        self.aceptar_button = QPushButton("Aceptar")
        self.aceptar_button.setObjectName("pinAceptar")
        self.aceptar_button.setAutoDefault(False)
        self.aceptar_button.clicked.connect(self._aceptar)
        botones.addWidget(self.cancelar_button, 1)
        botones.addWidget(self.aceptar_button, 1)
        ly.addLayout(botones)

        QTimer.singleShot(0, self.pin_input.setFocus)

    def _avisar(self, texto: str) -> None:
        self.aviso_label.setText(texto)
        self.aviso_label.setVisible(True)
        self.pin_input.setFocus()

    def _aceptar(self) -> None:
        faltan = self._control.segundos_restantes(self._reloj())
        if faltan:
            self.pin_input.clear()
            self._avisar(f"Demasiados intentos. Espera {faltan} segundos.")
            return
        pin = self.pin_input.text()
        self.pin_input.clear()
        if not pin.strip():
            self._avisar("Escribe tu PIN.")
            return
        resultado = self._verificar(pin, en_linea=self._en_linea)
        if resultado.estado == pin_svc.OK:
            self._control.registrar_exito()
            self.autorizado = True
            self.accept()
            return
        if resultado.estado == pin_svc.INCORRECTO:
            bloqueo = self._control.registrar_fallo(self._reloj())
            if bloqueo:
                self._avisar(f"PIN incorrecto. Demasiados intentos: espera {bloqueo} segundos.")
            else:
                self._avisar("PIN incorrecto. Inténtalo otra vez.")
            return
        # sin_pin / sin_datos: no hay con qué validar; reintentar no sirve.
        QMessageBox.warning(self, TITULO, resultado.mensaje)
        self.reject()


#: Plataformas de Qt sin pantalla (pruebas, revisiones de arranque): ahí nadie
#: puede teclear el PIN y el diálogo esperaría para siempre.
_SIN_PANTALLA = {"offscreen", "minimal"}


def _hay_pantalla() -> bool:
    from PyQt6.QtGui import QGuiApplication

    try:
        return QGuiApplication.platformName() not in _SIN_PANTALLA
    except Exception:  # noqa: BLE001
        return True


def pedir_pin_dueno(parent: QWidget | None, *, en_linea: bool, motivo: str) -> bool:
    """True solo si el dueño escribió su PIN correcto. Cancelar, Esc o cerrar → False.

    Sin pantalla no se abre nada y se niega: lo seguro, y así una prueba que
    olvide parchear el PIN falla en vez de colgarse, aunque cargue Qt tarde."""
    if not _hay_pantalla():
        return False
    dlg = PinDuenoDialog(parent, en_linea=en_linea, motivo=motivo)
    try:
        dlg.exec()
        return bool(dlg.autorizado)
    finally:
        dlg.deleteLater()
