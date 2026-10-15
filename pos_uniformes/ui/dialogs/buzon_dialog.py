"""Ventana del buzón: un chat entre las PCs de la tienda, como WhatsApp.

Para pasar comandos y respuestas sin WhatsApp (Daniel, 2026-10-15). La primera
versión era una lista con un «Para:» que nadie entendía: se mandaba el script en
vez de su resultado, y desde la PC equivocada. Ahora es como el WhatsApp que ya
saben usar: los chats a la izquierda, la conversación a la derecha, y lo que
escribes va al chat que tienes abierto.

Cada mensaje trae «Copiar»: el comando se pega tal cual en PowerShell, y lo que
conteste PowerShell se pega aquí de regreso. Nada se ejecuta solo.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

#: Cada cuánto se buscan mensajes nuevos con la ventana abierta.
REFRESCO_MS = 5_000
#: Ancho máximo de una burbuja: más ancho y se lee como documento, no como chat.
ANCHO_BURBUJA = 560

_VERDE = "#00a884"
_ESTILO = f"""
QDialog {{ background: #f0f2f5; }}
QLabel {{ color: #111b21; background: transparent; }}
QListWidget {{ background: #ffffff; border: none; outline: none; }}
QListWidget::item {{ border-bottom: 1px solid #f0f2f5; }}
QListWidget::item:selected {{ background: #f0f2f5; }}
QListWidget::item:hover {{ background: #f5f6f6; }}
QFrame#cabecera {{ background: #f0f2f5; border-bottom: 1px solid #e1e4e6; }}
QScrollArea {{ background: #efeae2; border: none; }}
QScrollArea > QWidget > QWidget {{ background: #efeae2; }}
QFrame#mia {{ background: #d9fdd3; border-radius: 10px; }}
QFrame#otra {{ background: #ffffff; border-radius: 10px; }}
QLabel#fecha {{ background: #ffffff; color: #54656f; border-radius: 8px;
               padding: 4px 10px; font-size: 11px; }}
QFrame#barraEscribir {{ background: #f0f2f5; }}
QPlainTextEdit#escribir {{ background: #ffffff; color: #111b21; border: none;
                          border-radius: 10px; padding: 6px 10px; font-size: 14px; }}
QPushButton#enviar {{ background: {_VERDE}; color: #ffffff; border: none; border-radius: 22px;
                     font-size: 18px; font-weight: 700; }}
QPushButton#suave {{ background: transparent; color: #54656f; border: none; font-size: 13px;
                    padding: 4px 8px; }}
QPushButton#suave:hover {{ color: {_VERDE}; }}
QToolButton#copiar {{ background: transparent; color: #027eb5; border: none; font-size: 12px;
                     padding: 0 2px; }}
QToolButton#ejecutar {{ background: transparent; color: {_VERDE}; border: none; font-size: 12px;
                       font-weight: 700; padding: 0 6px; }}
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


def _local(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    try:
        return momento.astimezone()
    except Exception:  # noqa: BLE001
        return momento


def _hora(momento: datetime | None) -> str:
    m = _local(momento)
    return m.strftime("%H:%M") if m else ""


def _dia(momento: datetime | None, hoy: date | None = None) -> str:
    """«Hoy», «Ayer» o la fecha, como los separadores de WhatsApp."""
    m = _local(momento)
    if m is None:
        return ""
    hoy = hoy or date.today()
    if m.date() == hoy:
        return "Hoy"
    if m.date() == hoy - timedelta(days=1):
        return "Ayer"
    dias = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    return f"{dias[m.weekday()]} {m:%d/%m}"


def _cuando_en_lista(momento: datetime | None) -> str:
    m = _local(momento)
    if m is None:
        return ""
    return _hora(m) if m.date() == date.today() else _dia(m)


def _estado(chat) -> str:
    if chat.es_grupo:
        return "Lo que se manda aquí lo ven todas las PCs"
    if chat.en_linea:
        return "en línea"
    if chat.visto is not None:
        return f"últ. vez {_dia(chat.visto).lower()} a las {_hora(chat.visto)}"
    return ""


class _Escribir(QPlainTextEdit):
    """Enter manda; Shift+Enter hace otro renglón. Crece hasta 6 renglones."""

    enviar = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("escribir")
        self.setPlaceholderText("Escribe un mensaje o pega lo que salió en pantalla")
        self.textChanged.connect(self._ajustar_alto)
        self._ajustar_alto()

    def keyPressEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # A mano: Qt mete un «separador de línea» (U+2028) y no un
                # salto, y ese carácter rompe el comando al pegarlo en PowerShell.
                self.insertPlainText("\n")
            else:
                self.enviar.emit()
            return
        super().keyPressEvent(event)

    def _ajustar_alto(self) -> None:
        total = max(self.document().blockCount(), 1)
        renglones = min(total, 6)
        self.setFixedHeight(self.fontMetrics().lineSpacing() * renglones + 22)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if total > 6 else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )


class _ItemChat(QWidget):
    """Un renglón de la lista: nombre, último mensaje, hora y no leídos."""

    def __init__(self, chat, yo: str) -> None:
        super().__init__()
        ly = QHBoxLayout(self)
        ly.setContentsMargins(14, 10, 14, 10)
        ly.setSpacing(10)

        avatar = QLabel("👥" if chat.es_grupo else (chat.nombre[:1].upper() or "?"))
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background: #dfe5e7; color: #54656f; border-radius: 21px;"
            "font-size: 17px; font-weight: 700;"
        )
        ly.addWidget(avatar)

        columna = QVBoxLayout()
        columna.setSpacing(2)
        arriba = QHBoxLayout()
        punto = ""
        if chat.en_linea is True:
            punto = f"<span style='color:{_VERDE}'>●</span> "
        elif chat.en_linea is False:
            punto = "<span style='color:#c4c9cc'>●</span> "
        self.nombre = QLabel(f"{punto}<b>{chat.nombre}</b>")
        self.nombre.setStyleSheet("font-size: 14px;")
        arriba.addWidget(self.nombre, 1)
        self.cuando = QLabel(_cuando_en_lista(chat.ultimo_at))
        self.cuando.setStyleSheet(
            f"font-size: 11px; color: {_VERDE if chat.no_leidos else '#667781'};"
        )
        arriba.addWidget(self.cuando)
        columna.addLayout(arriba)

        abajo = QHBoxLayout()
        vista = " ".join((chat.ultimo_texto or "").split())
        if vista and chat.ultimo_de == yo:
            vista = f"Tú: {vista}"
        elif vista and chat.es_grupo:
            vista = f"{chat.ultimo_de}: {vista}"
        previa = QLabel()
        previa.setStyleSheet("font-size: 12px; color: #667781;")
        previa.setText(previa.fontMetrics().elidedText(
            vista or "Sin mensajes todavía", Qt.TextElideMode.ElideRight, 200
        ))
        abajo.addWidget(previa, 1)
        self.globo: QLabel | None = None
        if chat.no_leidos:
            self.globo = QLabel(str(chat.no_leidos))
            self.globo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.globo.setMinimumWidth(20)
            self.globo.setStyleSheet(
                f"background: {_VERDE}; color: #ffffff; border-radius: 10px;"
                "font-size: 11px; font-weight: 700; padding: 1px 6px;"
            )
            abajo.addWidget(self.globo)
        columna.addLayout(abajo)
        ly.addLayout(columna, 1)


class _ConfirmarEjecucion(QDialog):
    """Antes de correr: el comando completo a la vista y el PIN de admin."""

    def __init__(self, parent: QWidget, texto: str, de: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ejecutar en esta PC")
        self.setMinimumWidth(560)
        ly = QVBoxLayout(self)
        aviso = QLabel(
            f"<b>{de}</b> pide correr esto en esta PC. Revísalo: lo que salga "
            f"se le manda de regreso."
        )
        aviso.setWordWrap(True)
        ly.addWidget(aviso)
        vista = QPlainTextEdit(texto)
        vista.setReadOnly(True)
        vista.setFont(_mono())
        vista.setMinimumHeight(160)
        ly.addWidget(vista)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin.setPlaceholderText("PIN de administrador")
        self.pin.returnPressed.connect(self.accept)
        ly.addWidget(self.pin)
        self.pin.setFocus()
        botones = QDialogButtonBox()
        botones.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        botones.addButton("▶ Ejecutar en esta PC", QDialogButtonBox.ButtonRole.AcceptRole)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        ly.addWidget(botones)


def _pin_correcto(pin: str) -> bool:
    from pos_uniformes.ui.dialogs.satellite_admin_dialog import _ADMIN_PIN

    return (pin or "").strip() == _ADMIN_PIN


def _confirmar_con_pin(parent: QWidget, texto: str, de: str) -> bool | None:
    """True = adelante; False = PIN equivocado; None = se arrepintió."""
    dlg = _ConfirmarEjecucion(parent, texto, de)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return _pin_correcto(dlg.pin.text())


class BuzonDialog(QDialog):
    """El chat. Los parámetros con nombre son para las pruebas."""

    #: Terminó de correr un comando (desde el hilo que lo corrió).
    _ejecucion_terminada = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory=None,
        yo: str | None = None,
        leer_leidos=None,
        guardar_leido=None,
        confirmar=None,
        ejecutar=None,
        en_hilo: bool = True,
    ) -> None:
        super().__init__(parent)
        from pos_uniformes.services import buzon_service as bz

        if session_factory is None:
            from pos_uniformes.database.connection import get_session

            session_factory = get_session
        self._session_factory = session_factory
        self._yo = yo or bz.mi_nombre()
        self._leer_leidos = leer_leidos or bz.leidos
        self._guardar_leido = guardar_leido or bz.marcar_leido
        self._confirmar = confirmar or _confirmar_con_pin
        if ejecutar is None:
            from pos_uniformes.services.buzon_ejecutar_service import ejecutar
        self._ejecutar = ejecutar
        self._en_hilo = en_hilo
        self._ejecucion_terminada.connect(self._al_terminar_ejecucion)
        self._abierto: str = bz.GRUPO
        self._chats: list = []
        self._ultimo_pintado: tuple[str, int] | None = None

        self.setWindowTitle("Buzón entre PCs")
        self.setStyleSheet(_ESTILO)
        self.resize(1000, 700)

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        raiz.addWidget(divisor)

        # ── Izquierda: quién soy y la lista de chats ──
        izquierda = QWidget()
        # Con selector: sin él, el blanco se hereda a cada etiqueta de la lista
        # y el renglón escogido salía con recuadros blancos encima.
        izquierda.setObjectName("panelChats")
        izquierda.setStyleSheet("QWidget#panelChats { background: #ffffff; }")
        izq = QVBoxLayout(izquierda)
        izq.setContentsMargins(0, 0, 0, 0)
        izq.setSpacing(0)
        yo_barra = QFrame()
        yo_barra.setObjectName("cabecera")
        yo_ly = QHBoxLayout(yo_barra)
        yo_ly.setContentsMargins(14, 12, 10, 12)
        self.yo_label = QLabel()
        self.yo_label.setStyleSheet("font-size: 13px; color: #54656f;")
        yo_ly.addWidget(self.yo_label, 1)
        cambiar = QPushButton("✏️ Cambiar")
        cambiar.setObjectName("suave")
        cambiar.setToolTip("Cambiar cómo aparece esta PC en el chat")
        cambiar.clicked.connect(self._pedir_nombre)
        yo_ly.addWidget(cambiar)
        izq.addWidget(yo_barra)
        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._al_escoger_chat)
        izq.addWidget(self.lista, 1)
        divisor.addWidget(izquierda)

        # ── Derecha: la conversación ──
        derecha = QWidget()
        der = QVBoxLayout(derecha)
        der.setContentsMargins(0, 0, 0, 0)
        der.setSpacing(0)
        cabecera = QFrame()
        cabecera.setObjectName("cabecera")
        cab = QVBoxLayout(cabecera)
        cab.setContentsMargins(16, 10, 16, 10)
        cab.setSpacing(0)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.subtitulo = QLabel()
        self.subtitulo.setStyleSheet("font-size: 12px; color: #667781;")
        cab.addWidget(self.titulo)
        cab.addWidget(self.subtitulo)
        der.addWidget(cabecera)

        self.estado = QLabel("")
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet(
            "background: #fff3c4; color: #7a5b00; padding: 8px 14px; font-size: 12px;"
        )
        self.estado.setVisible(False)
        der.addWidget(self.estado)

        self._mensajes = QWidget()
        self._mensajes_ly = QVBoxLayout(self._mensajes)
        self._mensajes_ly.setContentsMargins(40, 12, 40, 12)
        self._mensajes_ly.setSpacing(4)
        self._mensajes_ly.addStretch()
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._mensajes)
        der.addWidget(self._scroll, 1)

        barra = QFrame()
        barra.setObjectName("barraEscribir")
        bly = QHBoxLayout(barra)
        bly.setContentsMargins(12, 8, 12, 8)
        bly.setSpacing(8)
        pegar = QPushButton("📋 Pegar")
        pegar.setObjectName("suave")
        pegar.setToolTip("Pegar lo que copiaste (por ejemplo, lo que salió en PowerShell)")
        pegar.clicked.connect(self._pegar)
        bly.addWidget(pegar, 0, Qt.AlignmentFlag.AlignBottom)
        self.editor = _Escribir()
        self.editor.enviar.connect(self.enviar)
        bly.addWidget(self.editor, 1)
        self.enviar_btn = QPushButton("➤")
        self.enviar_btn.setObjectName("enviar")
        self.enviar_btn.setFixedSize(QSize(44, 44))
        self.enviar_btn.setToolTip("Enviar (Enter). Shift+Enter hace otro renglón.")
        self.enviar_btn.clicked.connect(self.enviar)
        bly.addWidget(self.enviar_btn, 0, Qt.AlignmentFlag.AlignBottom)
        der.addWidget(barra)

        divisor.addWidget(derecha)
        divisor.setSizes([320, 680])

        # Hijos de la ventana: mueren con ella (un singleShot suelto puede
        # disparar con la ventana ya borrada).
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESCO_MS)
        self._timer.timeout.connect(self.refrescar)
        self._timer.start()
        self._bajar = QTimer(self)
        self._bajar.setSingleShot(True)
        self._bajar.setInterval(0)
        self._bajar.timeout.connect(self._bajar_al_final)

        self._pintar_yo()
        self.refrescar()

    # ── Datos ───────────────────────────────────────────────────────────

    def refrescar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        try:
            with self._session_factory() as session:
                chats = bz.chats(session, yo=self._yo, leidos=self._leer_leidos())
                mensajes = bz.conversacion(session, yo=self._yo, con=self._abierto)
                filas = [(m.id, m.de, m.para, m.texto, m.created_at) for m in mensajes]
        except Exception:  # noqa: BLE001 — sin base, se dice y se sigue
            logger.exception("Buzón: no se pudo leer")
            self._avisar("Sin conexión con la PC principal. Se vuelve a intentar sola en unos segundos.")
            return
        self._avisar("")
        self._pintar_lista(chats)
        self._pintar_conversacion(filas)

    def abrir_chat(self, clave: str) -> None:
        for i, chat in enumerate(self._chats):
            if chat.clave == clave:
                self.lista.setCurrentRow(i)
                return

    def enviar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        texto = self.editor.toPlainText()
        if not texto.strip():
            return
        para = None if self._abierto == bz.GRUPO else self._abierto
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
            self._avisar("Sin conexión con la PC principal: no se mandó. Tu mensaje sigue escrito abajo.")
            return
        self.editor.clear()
        self.refrescar()

    # ── Acciones ────────────────────────────────────────────────────────

    def _al_escoger_chat(self, fila: int) -> None:
        if 0 <= fila < len(self._chats) and self._chats[fila].clave != self._abierto:
            self._abierto = self._chats[fila].clave
            self._ultimo_pintado = None
            self.refrescar()
            self.editor.setFocus()

    def _pegar(self) -> None:
        self.editor.insertPlainText(QApplication.clipboard().text())
        self.editor.setFocus()

    def _pedir_nombre(self) -> None:
        nuevo, ok = QInputDialog.getText(
            self, "Nombre de esta PC",
            "¿Cómo se llama esta PC en el chat? (por ejemplo: Entrada, Caja, PC principal)",
            text=self._yo,
        )
        if ok and nuevo.strip() and nuevo.strip() != self._yo:
            self.renombrar(nuevo.strip())

    def renombrar(self, nuevo: str) -> None:
        """Cambia el nombre de esta PC y se lleva su historial al nombre nuevo."""
        from pos_uniformes.services import buzon_service as bz

        viejo = self._yo
        try:
            with self._session_factory() as session:
                bz.renombrar(session, viejo, nuevo)
                session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo renombrar")
            self._avisar("Sin conexión con la PC principal: el nombre no se cambió.")
            return
        try:
            from pos_uniformes.services.satellite_identity_service import set_satellite_name

            set_satellite_name(nuevo)
        except Exception:  # noqa: BLE001 — sin identidad local, solo el buzón
            pass
        self._yo = nuevo
        self._ultimo_pintado = None
        self._pintar_yo()
        self.refrescar()

    # ── Pintar ──────────────────────────────────────────────────────────

    def _avisar(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.setVisible(bool(texto))

    def _pintar_yo(self) -> None:
        self.yo_label.setText(f"Esta PC es <b style='color:#111b21'>{self._yo}</b>")

    def _pintar_lista(self, chats) -> None:
        self._chats = list(chats)
        self.lista.blockSignals(True)
        for i in range(self.lista.count()):
            viejo = self.lista.itemWidget(self.lista.item(i))
            if viejo is not None:
                viejo.hide()
        self.lista.clear()
        fila_abierta = 0
        for i, chat in enumerate(self._chats):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 66))
            self.lista.addItem(item)
            self.lista.setItemWidget(item, _ItemChat(chat, self._yo))
            if chat.clave == self._abierto:
                fila_abierta = i
        self.lista.setCurrentRow(fila_abierta)
        self.lista.blockSignals(False)
        actual = self._chats[fila_abierta] if self._chats else None
        if actual is not None:
            self._abierto = actual.clave
            self.titulo.setText(("👥 " if actual.es_grupo else "") + actual.nombre)
            self.subtitulo.setText(_estado(actual))
            self.subtitulo.setVisible(bool(_estado(actual)))

    def _pintar_conversacion(self, filas) -> None:
        ultimo = filas[-1][0] if filas else 0
        if ultimo:
            self._guardar_leido(self._abierto, ultimo)
            self._apagar_globo()          # el chat abierto no tiene pendientes
        firma = (self._abierto, ultimo)
        if firma == self._ultimo_pintado:
            return  # nada nuevo: no se repinta (no se pierde lo seleccionado)
        self._ultimo_pintado = firma

        while self._mensajes_ly.count() > 1:     # el último es el resorte
            item = self._mensajes_ly.takeAt(0)
            viejo = item.widget()
            if viejo is not None:
                # Fuera de la pantalla YA: deleteLater solo lo borra cuando el
                # bucle de eventos llega a eso, y mientras se encimaba con lo nuevo.
                viejo.hide()
                viejo.setParent(None)
                viejo.deleteLater()

        if not filas:
            vacio = QLabel(
                "Todavía no hay mensajes aquí.\nEscribe abajo y dale Enter para mandarlo."
            )
            vacio.setObjectName("fecha")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._mensajes_ly.insertWidget(0, vacio, 0, Qt.AlignmentFlag.AlignHCenter)
            return
        posicion = 0
        dia_anterior = None
        for _id, de, _para, texto, creado in filas:
            dia = _dia(creado)
            if dia != dia_anterior:
                separador = QLabel(dia)
                separador.setObjectName("fecha")
                self._mensajes_ly.insertWidget(posicion, separador, 0, Qt.AlignmentFlag.AlignHCenter)
                posicion += 1
                dia_anterior = dia
            self._mensajes_ly.insertWidget(posicion, self._burbuja(de, texto, creado))
            posicion += 1
        # Después de que el layout acomode las burbujas, si no el máximo es viejo.
        self._bajar.start()

    def _apagar_globo(self) -> None:
        from dataclasses import replace

        for i, chat in enumerate(self._chats):
            if chat.clave == self._abierto and chat.no_leidos:
                self._chats[i] = replace(chat, no_leidos=0)
                renglon = self.lista.itemWidget(self.lista.item(i))
                if renglon is not None and renglon.globo is not None:
                    renglon.globo.hide()
                    renglon.cuando.setStyleSheet("font-size: 11px; color: #667781;")

    def _bajar_al_final(self) -> None:
        barra = self._scroll.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _burbuja(self, de: str, texto: str, creado) -> QWidget:
        from pos_uniformes.services import buzon_service as bz

        mio = de == self._yo
        fila = QWidget()
        fly = QHBoxLayout(fila)
        fly.setContentsMargins(0, 2, 0, 2)
        if mio:
            fly.addStretch(1)

        burbuja = QFrame()
        burbuja.setObjectName("mia" if mio else "otra")
        burbuja.setMaximumWidth(ANCHO_BURBUJA)
        bly = QVBoxLayout(burbuja)
        bly.setContentsMargins(10, 6, 10, 4)
        bly.setSpacing(2)
        if not mio and self._abierto == bz.GRUPO:
            quien = QLabel(de)
            quien.setStyleSheet("font-size: 12px; font-weight: 700; color: #1f7aec;")
            bly.addWidget(quien)

        cuerpo = QLabel(texto)
        cuerpo.setObjectName("cuerpo")
        cuerpo.setTextFormat(Qt.TextFormat.PlainText)
        cuerpo.setWordWrap(True)
        cuerpo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if bz.parece_codigo(texto):
            cuerpo.setFont(_mono())
        else:
            # Con setFont y no con hoja de estilo: el ancho de abajo se mide
            # con esta letra, y la de la hoja aún no aplica a esta altura.
            letra = cuerpo.font()
            letra.setPixelSize(14)
            cuerpo.setFont(letra)
        # Con wordWrap, QLabel se encoge al mínimo y parte hasta lo que cabía.
        # Se le pide el ancho de su renglón más largo, sin pasar del de la burbuja.
        largo = max((cuerpo.fontMetrics().horizontalAdvance(r) for r in texto.splitlines() or [""]), default=0)
        cuerpo.setMinimumWidth(min(largo + 4, ANCHO_BURBUJA - 24))
        bly.addWidget(cuerpo)

        pie = QHBoxLayout()
        copiar = QToolButton()
        copiar.setObjectName("copiar")
        copiar.setText("📋 Copiar")
        copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        copiar.clicked.connect(lambda _=False, t=texto, b=copiar: self._copiar(t, b))
        pie.addWidget(copiar)
        from pos_uniformes.services.buzon_ejecutar_service import puede_ejecutarse

        # Solo en un comando: «dale Ejecutar al de abajo» no se corre.
        if not mio and puede_ejecutarse(de) and bz.parece_codigo(texto):
            correr = QToolButton()
            correr.setObjectName("ejecutar")
            correr.setText("▶ Ejecutar")
            correr.setToolTip("Correr esto en esta PC y mandar de regreso lo que salga")
            correr.setCursor(Qt.CursorShape.PointingHandCursor)
            correr.clicked.connect(lambda _=False, t=texto, d=de, b=correr: self.pedir_ejecucion(t, d, b))
            pie.addWidget(correr)
        pie.addStretch(1)
        hora = QLabel(_hora(creado))
        hora.setStyleSheet("font-size: 11px; color: #667781;")
        pie.addWidget(hora)
        bly.addLayout(pie)

        fly.addWidget(burbuja)
        if not mio:
            fly.addStretch(1)
        return fila

    # ── Ejecutar ────────────────────────────────────────────────────────

    def pedir_ejecucion(self, texto: str, de: str, boton: QToolButton | None = None) -> None:
        """Confirma con PIN y corre el comando; lo que sale regresa a `de`."""
        respuesta = self._confirmar(self, texto, de)
        if respuesta is None:
            return
        if not respuesta:
            self._avisar("PIN incorrecto: no se ejecutó nada.")
            return
        if boton is not None:
            boton.setText("⏳ Ejecutando…")
            boton.setEnabled(False)
        self._avisar(f"Ejecutando… lo que salga se le manda a {de}.")
        if self._en_hilo:
            import threading

            threading.Thread(
                target=self._correr_y_contestar, args=(texto, de), daemon=True, name="buzon-ejecutar"
            ).start()
        else:
            self._correr_y_contestar(texto, de)

    def _correr_y_contestar(self, texto: str, de: str) -> None:
        """Corre y manda el resultado. Va en su hilo: el kiosko no se congela.

        El resultado se manda DESDE AQUÍ y no desde la ventana: si alguien la
        cierra mientras corre, la respuesta igual llega."""
        from pos_uniformes.services import buzon_service as bz
        from pos_uniformes.services.buzon_ejecutar_service import texto_de_resultado

        resultado = self._ejecutar(texto)
        mensaje = texto_de_resultado(resultado, pc=self._yo, maximo=bz.MAXIMO_CARACTERES)
        try:
            with self._session_factory() as session:
                bz.enviar(session, mensaje, de=self._yo, para=de)
                session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo mandar el resultado")
        try:
            self._ejecucion_terminada.emit()
        except RuntimeError:  # la ventana ya se cerró
            pass

    def _al_terminar_ejecucion(self) -> None:
        self._avisar("")
        self._ultimo_pintado = None
        self.refrescar()

    @staticmethod
    def _copiar(texto: str, boton: QToolButton) -> None:
        QApplication.clipboard().setText(texto)
        boton.setText("✅ Copiado")


def abrir_buzon(parent: QWidget | None = None) -> None:
    BuzonDialog(parent).exec()
