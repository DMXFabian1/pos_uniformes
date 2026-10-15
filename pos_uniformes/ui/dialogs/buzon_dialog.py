"""Ventana del buzón: un chat de texto entre las PCs de la tienda.

Para pasar comandos y respuestas sin WhatsApp (Daniel, 2026-10-15). Cada
mensaje trae su botón «Copiar»: el comando se pega tal cual en PowerShell, y lo
que conteste PowerShell se pega aquí de regreso. No ejecuta nada.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

#: Cada cuánto se buscan mensajes nuevos con la ventana abierta.
REFRESCO_MS = 10_000
#: Renglones que se ven de un mensaje antes de que tenga su propio scroll.
RENGLONES_VISIBLES = 14

TODAS = "Todas las PCs"

_ESTILO = """
QDialog { background: #f4ede2; }
QLabel { color: #2c2a27; background: transparent; }
QFrame#tarjeta { background: #ffffff; border: 1px solid #ddd0c0; border-radius: 12px; }
QFrame#tarjetaMia { background: #fbf3e6; border: 1px solid #e3c9a8; border-radius: 12px; }
QPlainTextEdit { background: #fffdf9; color: #2c2a27; border: 1px solid #e8dccd;
                 border-radius: 8px; padding: 6px; }
QComboBox { background: #ffffff; color: #2c2a27; border: 1px solid #ddd0c0;
            border-radius: 8px; min-height: 34px; padding: 0 10px; }
QPushButton { background: #f8f2e9; color: #73341c; font-weight: 700;
              border: 1px solid #ddd0c0; border-radius: 10px; min-height: 34px; padding: 0 14px; }
QPushButton#enviar { background: #a84f2d; color: #ffffff; border: none; }
QScrollArea { background: #f4ede2; border: none; }
QScrollArea > QWidget > QWidget { background: #f4ede2; }
"""


def _mono() -> QFont:
    """Letra de ancho fijo de verdad: las tablas de PowerShell se leen en columnas.

    `systemFont(FixedFont)` en la Mac devuelve una proporcional y las columnas
    salían chuecas; se busca una monoespaciada por nombre, como en el ticket."""
    try:
        from pos_uniformes.services.ticket_imagen_service import _fuente_mono

        fuente = QFont(_fuente_mono())
    except Exception:  # noqa: BLE001
        fuente = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    fuente.setPointSize(10)
    return fuente


class BuzonDialog(QDialog):
    """El chat. `session_factory` y `yo` se pueden cambiar para las pruebas."""

    def __init__(self, parent: QWidget | None = None, *, session_factory=None, yo: str | None = None) -> None:
        super().__init__(parent)
        from pos_uniformes.services import buzon_service as bz

        if session_factory is None:
            from pos_uniformes.database.connection import get_session

            session_factory = get_session
        self._session_factory = session_factory
        self._yo = yo or bz.mi_nombre()
        self._ultimo_id: int | None = None

        self.setWindowTitle("Buzón entre PCs")
        self.setStyleSheet(_ESTILO)
        self.resize(760, 720)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(18, 16, 18, 14)
        ly.setSpacing(10)

        titulo = QLabel("💬 Buzón entre PCs")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(titulo)
        pista = QLabel(
            f"Esta PC firma como <b>{self._yo}</b>. Escribe o pega un texto y mándalo; "
            "en la otra PC se copia con un toque. Nada se ejecuta solo."
        )
        pista.setWordWrap(True)
        pista.setStyleSheet("font-size: 12px; color: #8a8177;")
        ly.addWidget(pista)

        self.estado = QLabel("")
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet("font-size: 12px; color: #a33b25; font-weight: 600;")
        self.estado.setVisible(False)
        ly.addWidget(self.estado)

        self._lista = QWidget()
        self._lista_ly = QVBoxLayout(self._lista)
        self._lista_ly.setContentsMargins(0, 0, 6, 0)
        self._lista_ly.setSpacing(10)
        self._lista_ly.addStretch()
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._lista)
        ly.addWidget(self._scroll, 1)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Para:"))
        self.destino = QComboBox()
        self.destino.addItem(TODAS)
        fila.addWidget(self.destino, 1)
        self.actualizar_btn = QPushButton("Actualizar")
        self.actualizar_btn.clicked.connect(self.refrescar)
        fila.addWidget(self.actualizar_btn)
        ly.addLayout(fila)

        self.editor = QPlainTextEdit()
        self.editor.setFont(_mono())
        self.editor.setPlaceholderText("Escribe o pega aquí (un comando, lo que salió en pantalla…)")
        self.editor.setFixedHeight(120)
        ly.addWidget(self.editor)

        abajo = QHBoxLayout()
        abajo.addStretch()
        self.enviar_btn = QPushButton("Enviar")
        self.enviar_btn.setObjectName("enviar")
        self.enviar_btn.clicked.connect(self.enviar)
        abajo.addWidget(self.enviar_btn)
        ly.addLayout(abajo)

        # Hijo de la ventana: muere con ella (un singleShot suelto puede
        # disparar con la ventana ya borrada).
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESCO_MS)
        self._timer.timeout.connect(self.refrescar)
        self._timer.start()
        self._bajar = QTimer(self)
        self._bajar.setSingleShot(True)
        self._bajar.setInterval(0)
        self._bajar.timeout.connect(self._bajar_al_final)

        self.refrescar()

    # ── Datos ───────────────────────────────────────────────────────────

    def refrescar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        try:
            with self._session_factory() as session:
                mensajes = bz.recientes(session, yo=self._yo)
                destinos = bz.destinos(session, yo=self._yo)
                filas = [(m.id, m.de, m.para, m.texto, m.created_at) for m in mensajes]
        except Exception:  # noqa: BLE001 — sin base, se dice y se sigue
            logger.exception("Buzón: no se pudo leer")
            self._avisar("Sin conexión con la PC principal: no se pudieron leer los mensajes.")
            return
        self._avisar("")
        self._poner_destinos(destinos)
        ultimo = filas[-1][0] if filas else None
        if ultimo == self._ultimo_id and self._lista_ly.count() > 1:
            return  # nada nuevo: no se repinta (no se pierde lo que se seleccionó)
        self._ultimo_id = ultimo
        self._pintar(filas)

    def enviar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        texto = self.editor.toPlainText()
        para = self.destino.currentText()
        para = None if para == TODAS else para
        try:
            with self._session_factory() as session:
                bz.enviar(session, texto, de=self._yo, para=para)
                session.commit()
        except bz.NoSePuede as exc:
            self._avisar(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo enviar")
            # Lo escrito se queda en el cuadro: no se pierde por un tropiezo de red.
            self._avisar("Sin conexión con la PC principal: no se mandó. Tu texto sigue ahí.")
            return
        self.editor.clear()
        self.refrescar()

    # ── Pintar ──────────────────────────────────────────────────────────

    def _avisar(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.setVisible(bool(texto))

    def _poner_destinos(self, destinos: list[str]) -> None:
        actual = self.destino.currentText()
        nuevos = [TODAS, *destinos]
        if [self.destino.itemText(i) for i in range(self.destino.count())] == nuevos:
            return
        self.destino.blockSignals(True)
        self.destino.clear()
        self.destino.addItems(nuevos)
        indice = self.destino.findText(actual)
        self.destino.setCurrentIndex(max(indice, 0))
        self.destino.blockSignals(False)

    def _pintar(self, filas) -> None:
        while self._lista_ly.count() > 1:     # el último es el resorte
            item = self._lista_ly.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not filas:
            vacio = QLabel("Todavía no hay mensajes.")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vacio.setStyleSheet("color: #8a8177; padding: 30px;")
            self._lista_ly.insertWidget(0, vacio)
            return
        for i, (_id, de, para, texto, creado) in enumerate(filas):
            self._lista_ly.insertWidget(i, self._tarjeta(de, para, texto, creado))
        # Después de que el layout acomode las tarjetas, si no el máximo es viejo.
        self._bajar.start()

    def _bajar_al_final(self) -> None:
        barra = self._scroll.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _tarjeta(self, de: str, para: str | None, texto: str, creado) -> QFrame:
        mio = de == self._yo
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaMia" if mio else "tarjeta")
        ly = QVBoxLayout(tarjeta)
        ly.setContentsMargins(12, 10, 12, 10)
        ly.setSpacing(6)

        arriba = QHBoxLayout()
        cuando = ""
        try:
            cuando = creado.astimezone().strftime("%d/%m %H:%M") if creado is not None else ""
        except Exception:  # noqa: BLE001
            cuando = ""
        quien = QLabel(f"<b>{'Tú' if mio else de}</b> → {para or 'todas'}  ·  {cuando}")
        quien.setStyleSheet("font-size: 12px; color: #73341c;")
        arriba.addWidget(quien, 1)
        copiar = QPushButton("📋 Copiar")
        copiar.clicked.connect(lambda _=False, t=texto, b=copiar: self._copiar(t, b))
        arriba.addWidget(copiar)
        ly.addLayout(arriba)

        cuerpo = QPlainTextEdit()
        cuerpo.setReadOnly(True)
        cuerpo.setFont(_mono())
        cuerpo.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        cuerpo.setPlainText(texto)
        renglones = min(max(texto.count("\n") + 1, 1), RENGLONES_VISIBLES)
        # Renglones + el aire del cuadro (márgenes del documento, relleno y
        # borde). Corto, y aparece la barra aunque el texto quepa.
        margen = int(cuerpo.document().documentMargin() * 2) + 16
        alto = cuerpo.fontMetrics().lineSpacing() * renglones + margen
        cuerpo.setFixedHeight(alto)
        if texto.count("\n") + 1 <= RENGLONES_VISIBLES:
            cuerpo.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ly.addWidget(cuerpo)
        return tarjeta

    @staticmethod
    def _copiar(texto: str, boton: QPushButton) -> None:
        QApplication.clipboard().setText(texto)
        boton.setText("✅ Copiado")


def abrir_buzon(parent: QWidget | None = None) -> None:
    BuzonDialog(parent).exec()
