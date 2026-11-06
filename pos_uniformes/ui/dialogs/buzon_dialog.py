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
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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
#: A esta distancia del fondo (px) se considera que «está abajo»: lo nuevo lo
#: sigue. Más arriba, se respeta donde está leyendo. (Signal Desktop usa 15.)
UMBRAL_ABAJO = 24
#: Un mensaje con más renglones que esto sale recortado, con «Ver todo».
RENGLONES_VISIBLES = 30
#: Cuántos mensajes se traen de entrada, y cuántos más con «Ver mensajes anteriores».
TRAMO = 60
#: Una captura se manda a lo más de este tamaño (px del lado largo) y peso.
LADO_IMAGEN = 1600
PESO_IMAGEN = 1_500_000

# Los estados de lo que contesta a un comando (los del servicio, a la mano).
_RECIBIDO, _TERMINO_BIEN = "recibido", "ok"

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
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; border: none; }}
QScrollBar::handle:vertical {{ background: #c2c8cb; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #9aa3a8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
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
QToolButton#verTodo {{ background: transparent; color: #027eb5; border: none; font-size: 12px;
                      font-weight: 700; padding: 2px 0; }}
QLabel#nuevos {{ background: #d9fdd3; color: #1c6b4a; border-radius: 8px;
                padding: 4px 12px; font-size: 11px; font-weight: 700; }}
QPushButton#irAbajo {{ background: #ffffff; color: #54656f; border: 1px solid #d5dadd;
                      border-radius: 18px; font-size: 13px; font-weight: 700; padding: 0 14px; }}
QPushButton#irAbajo[nuevos="true"] {{ background: {_VERDE}; color: #ffffff; border: none; }}
QToolButton#borrar {{ background: transparent; color: #8696a0; border: none; font-size: 12px;
                     padding: 0 4px; }}
QToolButton#borrar:hover {{ color: #b3261e; }}
QLabel#cita {{ background: rgba(0, 0, 0, 0.06); color: #54656f; border-left: 3px solid {_VERDE};
              border-radius: 4px; padding: 4px 8px; font-size: 12px; }}
QPushButton#anteriores {{ background: #ffffff; color: #027eb5; border: none; border-radius: 12px;
                         padding: 6px 14px; font-size: 12px; font-weight: 700; }}
QFrame#adjuntos {{ background: #f0f2f5; border-top: 1px solid #e1e4e6; }}
QLabel#adjuntoTexto {{ color: #54656f; font-size: 12px; }}
QLineEdit#buscar {{ background: #ffffff; border: none; border-radius: 8px; padding: 6px 10px;
                   font-size: 13px; color: #111b21; }}
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


@dataclass(frozen=True)
class _Fila:
    """Un mensaje ya fuera de la sesión, con lo que la ventana necesita."""

    id: int
    de: str
    para: str | None
    texto: str
    creado: datetime | None
    responde_a: int | None = None
    estado: str | None = None
    borrado: bool = False
    adjunto: bool = False


@dataclass
class _Partes:
    """Lo de una burbuja que cambia sin repintarla: el estado del comando y la palomita."""

    estado: QLabel
    palomita: QLabel | None


def _previa(f: _Fila) -> str:
    """Un mensaje en un renglón, para citarlo."""
    from pos_uniformes.services import buzon_service as bz

    if f.borrado:
        return bz.TEXTO_BORRADO
    texto = " ".join(f.texto.split())
    return f"{bz.TEXTO_IMAGEN} {texto}".strip() if f.adjunto else texto


def _a_bytes(imagen: QImage) -> bytes:
    """La imagen lista para guardarse: no más grande ni más pesada de lo que hace falta.

    PNG si cabe (una captura con letras se lee nítida); si pesa, JPEG."""
    if max(imagen.width(), imagen.height()) > LADO_IMAGEN:
        imagen = imagen.scaled(
            LADO_IMAGEN, LADO_IMAGEN, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    datos = b""
    for formato, calidad in (("PNG", -1), ("JPEG", 85), ("JPEG", 60)):
        lienzo = imagen if formato == "PNG" else imagen.convertToFormat(QImage.Format.Format_RGB32)
        arreglo = QByteArray()
        salida = QBuffer(arreglo)
        salida.open(QIODevice.OpenModeFlag.WriteOnly)
        lienzo.save(salida, formato, calidad)
        salida.close()
        datos = bytes(arreglo)
        if len(datos) <= PESO_IMAGEN:
            break
    return datos


class _Miniatura(QLabel):
    """La imagen dentro de la burbuja: tocarla la abre completa."""

    tocada = pyqtSignal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self.tocada.emit()
        super().mouseReleaseEvent(event)


def _ver_imagen_completa(parent: QWidget, pix: QPixmap) -> None:
    """La imagen a su tamaño (con barras si no cabe), para copiarla o guardarla."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Imagen")
    ly = QVBoxLayout(dlg)
    area = QScrollArea()
    lienzo = QLabel()
    lienzo.setPixmap(pix)
    area.setWidget(lienzo)
    ly.addWidget(area, 1)
    botones = QHBoxLayout()
    copiar = QPushButton("📋 Copiar imagen")
    copiar.clicked.connect(lambda: QApplication.clipboard().setPixmap(pix))
    guardar = QPushButton("💾 Guardar…")

    def _guardar() -> None:
        ruta, _ = QFileDialog.getSaveFileName(dlg, "Guardar imagen", "captura.png", "PNG (*.png)")
        if ruta:
            pix.save(ruta, "PNG")

    guardar.clicked.connect(_guardar)
    cerrar = QPushButton("Cerrar")
    cerrar.clicked.connect(dlg.accept)
    botones.addWidget(copiar)
    botones.addWidget(guardar)
    botones.addStretch(1)
    botones.addWidget(cerrar)
    ly.addLayout(botones)
    dlg.resize(min(pix.width() + 60, 1200), min(pix.height() + 110, 820))
    dlg.exec()


def _confirmar_borrado(parent: QWidget) -> bool:
    return QMessageBox.question(
        parent, "Borrar mensaje",
        "¿Borrar este mensaje? Se quita en todas las PCs y no se puede deshacer.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    ) == QMessageBox.StandardButton.Yes


class _Escribir(QPlainTextEdit):
    """Enter manda; Shift+Enter hace otro renglón. Crece hasta 6 renglones.

    Pegar una captura (Win+Shift+S y Ctrl+V) no mete texto: avisa con
    `imagen_pegada` para que la ventana la deje lista."""

    enviar = pyqtSignal()
    imagen_pegada = pyqtSignal(object)

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802 — nombre de Qt
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 — nombre de Qt
        if source.hasImage():
            imagen = source.imageData()
            if isinstance(imagen, QPixmap):
                imagen = imagen.toImage()
            if isinstance(imagen, QImage) and not imagen.isNull():
                self.imagen_pegada.emit(imagen)
                return
        super().insertFromMimeData(source)

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


class _Conversacion(QScrollArea):
    """La conversación, con su botón flotante de «ir abajo» en la esquina."""

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.ir_abajo = QPushButton("↓", self)
        self.ir_abajo.setObjectName("irAbajo")
        self.ir_abajo.setFixedHeight(36)
        self.ir_abajo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ir_abajo.setToolTip("Ir al último mensaje")
        self.ir_abajo.hide()

    def acomodar_boton(self) -> None:
        self.ir_abajo.adjustSize()
        self.ir_abajo.move(
            self.width() - self.ir_abajo.width() - 26, self.height() - self.ir_abajo.height() - 14
        )
        self.ir_abajo.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        super().resizeEvent(event)
        self.acomodar_boton()


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
        guardar_nombre_local=...,
        identificador=...,
        confirmar_borrado=None,
        ver_imagen=None,
        tramo: int = TRAMO,
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
        if guardar_nombre_local is ...:
            from pos_uniformes.services.satellite_identity_service import set_satellite_name

            guardar_nombre_local = set_satellite_name
        self._guardar_nombre_local = guardar_nombre_local
        self._id_fijo = identificador
        self._ejecucion_terminada.connect(self._al_terminar_ejecucion)
        self._abierto: str = bz.GRUPO
        self._chats: list = []
        self._ultimo_pintado: tuple[str, int] | None = None
        # Lo que hace que se sienta como un chat de verdad (2026-11-06):
        self._pintado_hasta = 0            # id del último mensaje ya en pantalla
        self._dia_ultimo: str | None = None
        self._pegado = True                # está abajo: lo nuevo lo sigue
        self._nuevos_abajo = 0             # llegaron mientras leía arriba
        self._borradores: dict[str, str] = {}   # lo escrito a medias, por chat
        self._firma_lista: tuple | None = None
        self._boton_corriendo: QToolButton | None = None
        # El chat completo (2026-11-06): historia, palomitas, respuestas, imágenes, buscar, borrar.
        self._confirmar_borrado = confirmar_borrado or _confirmar_borrado
        self._ver_imagen = ver_imagen or _ver_imagen_completa
        self._tramo = max(1, int(tramo))
        self._cuantos = self._tramo         # cuántos mensajes del chat abierto se traen
        self._buscando = ""                 # texto que se busca en el chat abierto
        self._respondiendo: _Fila | None = None
        self._imagen_lista: bytes | None = None
        self._citas: dict[int, tuple[str, str]] = {}      # id → (de, un renglón)
        self._vistos: dict[str, int] = {}                 # quién leyó hasta dónde
        self._por_id: dict[int, _Partes] = {}
        self._estados: dict[int, tuple[str, str]] = {}    # comando → (estado, PC que lo corrió)
        self._pixmaps: dict[int, QPixmap | None] = {}
        self._anotado: dict[str, int] = {}                # lo ya marcado como leído, por chat
        self._ultimo_id = 0
        self._ancla: int | None = None      # distancia al final que se conserva al repintar
        self._ajustando = False

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
        cab_fila = QHBoxLayout(cabecera)
        cab_fila.setContentsMargins(16, 10, 10, 10)
        cab_fila.setSpacing(10)
        cab = QVBoxLayout()
        cab.setSpacing(0)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.subtitulo = QLabel()
        self.subtitulo.setStyleSheet("font-size: 12px; color: #667781;")
        cab.addWidget(self.titulo)
        cab.addWidget(self.subtitulo)
        cab_fila.addLayout(cab, 1)
        self.buscar = QLineEdit()
        self.buscar.setObjectName("buscar")
        self.buscar.setPlaceholderText("Buscar en este chat…")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setFixedWidth(240)
        self.buscar.setVisible(False)
        cab_fila.addWidget(self.buscar)
        self.buscar_btn = QPushButton("🔍 Buscar")
        self.buscar_btn.setObjectName("suave")
        self.buscar_btn.setToolTip("Buscar un mensaje en toda la historia de este chat")
        self.buscar_btn.clicked.connect(self._alternar_busqueda)
        cab_fila.addWidget(self.buscar_btn)
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
        self._scroll = _Conversacion()
        self._scroll.setWidget(self._mensajes)
        self.ir_abajo = self._scroll.ir_abajo
        self.ir_abajo.clicked.connect(self._bajar_al_final)
        barra_v = self._scroll.verticalScrollBar()
        barra_v.valueChanged.connect(self._al_mover_barra)
        barra_v.rangeChanged.connect(self._al_cambiar_rango)
        der.addWidget(self._scroll, 1)

        # La tira de «a qué contestas» y «qué imagen va», arriba del cuadro.
        adjuntos = QFrame()
        adjuntos.setObjectName("adjuntos")
        adj = QVBoxLayout(adjuntos)
        adj.setContentsMargins(14, 0, 14, 0)
        adj.setSpacing(0)
        self.respuesta_barra = QWidget()
        rly = QHBoxLayout(self.respuesta_barra)
        rly.setContentsMargins(0, 6, 0, 2)
        self.respuesta_label = QLabel()
        self.respuesta_label.setObjectName("adjuntoTexto")
        rly.addWidget(self.respuesta_label, 1)
        quitar_r = QPushButton("✕")
        quitar_r.setObjectName("suave")
        quitar_r.setToolTip("No contestar a ese mensaje")
        quitar_r.clicked.connect(self._quitar_respuesta)
        rly.addWidget(quitar_r)
        adj.addWidget(self.respuesta_barra)
        self.imagen_barra = QWidget()
        ily = QHBoxLayout(self.imagen_barra)
        ily.setContentsMargins(0, 6, 0, 2)
        self.imagen_mini = QLabel()
        ily.addWidget(self.imagen_mini)
        self.imagen_label = QLabel()
        self.imagen_label.setObjectName("adjuntoTexto")
        ily.addWidget(self.imagen_label, 1)
        quitar_i = QPushButton("✕")
        quitar_i.setObjectName("suave")
        quitar_i.setToolTip("No mandar la imagen")
        quitar_i.clicked.connect(self._quitar_imagen)
        ily.addWidget(quitar_i)
        adj.addWidget(self.imagen_barra)
        self.respuesta_barra.setVisible(False)
        self.imagen_barra.setVisible(False)
        der.addWidget(adjuntos)

        barra = QFrame()
        barra.setObjectName("barraEscribir")
        bly = QHBoxLayout(barra)
        bly.setContentsMargins(12, 8, 12, 8)
        bly.setSpacing(8)
        pegar = QPushButton("📋 Pegar")
        pegar.setObjectName("suave")
        pegar.setToolTip("Pegar lo que copiaste: texto de PowerShell o una captura de pantalla")
        pegar.clicked.connect(self._pegar)
        bly.addWidget(pegar, 0, Qt.AlignmentFlag.AlignBottom)
        imagen_btn = QPushButton("🖼 Imagen")
        imagen_btn.setObjectName("suave")
        imagen_btn.setToolTip("Mandar una imagen guardada en esta PC")
        imagen_btn.clicked.connect(self._escoger_imagen)
        bly.addWidget(imagen_btn, 0, Qt.AlignmentFlag.AlignBottom)
        self.editor = _Escribir()
        self.editor.enviar.connect(self.enviar)
        self.editor.imagen_pegada.connect(self.poner_imagen)
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
        # Buscar espera a que dejes de teclear: no una consulta por letra.
        self._buscar_timer = QTimer(self)
        self._buscar_timer.setSingleShot(True)
        self._buscar_timer.setInterval(300)
        self._buscar_timer.timeout.connect(lambda: self.buscar_texto(self.buscar.text()))
        self.buscar.textChanged.connect(lambda _t: self._buscar_timer.start())

        self._pintar_yo()
        self.refrescar()

    # ── Datos ───────────────────────────────────────────────────────────

    def refrescar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        try:
            with self._session_factory() as session:
                chats = bz.chats(session, yo=self._yo, leidos=self._leer_leidos())
                mensajes = bz.conversacion(
                    session, yo=self._yo, con=self._abierto,
                    limite=self._cuantos, buscar=self._buscando or None,
                )
                filas = [
                    _Fila(m.id, m.de, m.para, m.texto or "", m.created_at, m.responde_a,
                          m.estado, m.borrado_at is not None, bool(m.adjunto))
                    for m in mensajes
                ]
                hay_mas = bool(filas) and not self._buscando and bz.hay_anteriores(
                    session, yo=self._yo, con=self._abierto, antes_de=filas[0].id
                )
                self._vistos = bz.leido_por_otros(session, yo=self._yo, con=self._abierto)
                en_pantalla = {f.id for f in filas}
                citas = bz.resumenes(
                    session, {f.responde_a for f in filas if f.responde_a and f.responde_a not in en_pantalla}
                )
        except Exception:  # noqa: BLE001 — sin base, se dice y se sigue
            logger.exception("Buzón: no se pudo leer")
            self._avisar("Sin conexión con la PC principal. Se vuelve a intentar sola en unos segundos.")
            return
        for f in filas:
            citas[f.id] = (f.de, _previa(f))
        self._citas.update(citas)
        self._avisar("")
        self._pintar_lista(chats)
        self._pintar_conversacion(filas, hay_mas)

    def abrir_chat(self, clave: str) -> None:
        for i, chat in enumerate(self._chats):
            if chat.clave == clave:
                self.lista.setCurrentRow(i)
                return

    def enviar(self) -> None:
        from pos_uniformes.services import buzon_service as bz

        texto = self.editor.toPlainText()
        imagen = self._imagen_lista
        if not texto.strip() and not imagen:
            return
        para = None if self._abierto == bz.GRUPO else self._abierto
        try:
            with self._session_factory() as session:
                bz.enviar(
                    session, texto, de=self._yo, para=para, imagen=imagen,
                    responde_a=self._respondiendo.id if self._respondiendo else None,
                )
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
        self._borradores.pop(self._abierto, None)
        self._respondiendo = None
        self._imagen_lista = None
        self._pintar_adjuntos()
        if self._buscando:
            self._dejar_de_buscar()       # lo que mandé no saldría entre los resultados
        self._pegado = True      # lo que mando yo siempre se ve: baja aunque estuviera leyendo arriba
        self.refrescar()

    # ── Acciones ────────────────────────────────────────────────────────

    def _al_escoger_chat(self, fila: int) -> None:
        if 0 <= fila < len(self._chats) and self._chats[fila].clave != self._abierto:
            # Lo escrito a medias se queda en SU chat y vuelve al regresar.
            self._borradores[self._abierto] = self.editor.toPlainText()
            self._abierto = self._chats[fila].clave
            self._ultimo_pintado = None
            self._cuantos = self._tramo
            self._respondiendo = None
            self._imagen_lista = None
            self._pintar_adjuntos()
            self._dejar_de_buscar()
            self.editor.setPlainText(self._borradores.get(self._abierto, ""))
            self.editor.moveCursor(self.editor.textCursor().MoveOperation.End)
            self.refrescar()
            self.editor.setFocus()

    def _pegar(self) -> None:
        portapapeles = QApplication.clipboard()
        datos = portapapeles.mimeData()
        if datos is not None and datos.hasImage():
            self.poner_imagen(portapapeles.image())
        else:
            self.editor.insertPlainText(portapapeles.text())
        self.editor.setFocus()

    def _escoger_imagen(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Mandar una imagen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if ruta:
            self.poner_imagen(QImage(ruta))

    def poner_imagen(self, imagen) -> None:
        """Deja una imagen lista para mandarse con el siguiente Enter."""
        if imagen is None or imagen.isNull():
            self._avisar("Eso no es una imagen que se pueda mandar.")
            return
        self._imagen_lista = _a_bytes(imagen)
        self._pintar_adjuntos()
        self.editor.setFocus()

    def responder(self, fila: "_Fila") -> None:
        self._respondiendo = fila
        self._pintar_adjuntos()
        self.editor.setFocus()

    def _quitar_respuesta(self) -> None:
        self._respondiendo = None
        self._pintar_adjuntos()

    def _quitar_imagen(self) -> None:
        self._imagen_lista = None
        self._pintar_adjuntos()

    def _pintar_adjuntos(self) -> None:
        """La tira de arriba del cuadro: a qué contestas y qué imagen va."""
        r = self._respondiendo
        self.respuesta_barra.setVisible(r is not None)
        if r is not None:
            self.respuesta_label.setText(
                self.respuesta_label.fontMetrics().elidedText(
                    f"↩ Respondiendo a {r.de}: {_previa(r)}", Qt.TextElideMode.ElideRight, 520
                )
            )
        self.imagen_barra.setVisible(self._imagen_lista is not None)
        if self._imagen_lista is not None:
            pix = QPixmap()
            pix.loadFromData(self._imagen_lista)
            self.imagen_mini.setPixmap(pix.scaled(
                64, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
            self.imagen_label.setText(
                f"Imagen lista ({pix.width()}×{pix.height()}). Enter la manda; puedes escribir algo con ella."
            )

    # ── Buscar ──────────────────────────────────────────────────────────

    def _alternar_busqueda(self) -> None:
        if self.buscar.isVisible():
            self._dejar_de_buscar()
            self.refrescar()
        else:
            self.buscar.setVisible(True)
            self.buscar.setFocus()

    def _dejar_de_buscar(self) -> None:
        self._buscar_timer.stop()
        self._buscando = ""
        self.buscar.blockSignals(True)
        self.buscar.clear()
        self.buscar.blockSignals(False)
        self.buscar.setVisible(False)

    def buscar_texto(self, texto: str) -> None:
        """Enseña solo los mensajes de este chat que traen `texto` (de toda su historia)."""
        self._buscando = (texto or "").strip()
        self.refrescar()

    # ── Borrar ──────────────────────────────────────────────────────────

    def borrar_mensaje(self, mensaje_id: int) -> None:
        from pos_uniformes.services import buzon_service as bz

        if not self._confirmar_borrado(self):
            return
        try:
            with self._session_factory() as session:
                bz.borrar(session, mensaje_id, de=self._yo)
                session.commit()
        except bz.NoSePuede as exc:
            self._avisar(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo borrar")
            self._avisar("Sin conexión con la PC principal: no se borró.")
            return
        self._pixmaps.pop(mensaje_id, None)
        self.refrescar()

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
                limpio = bz.renombrar_esta_pc(
                    session, nuevo, viejo=viejo,
                    identificador=self._identificador() if self._id_fijo is ... else self._id_fijo,
                )
                session.commit()
        except bz.NoSePuede as exc:
            self._avisar(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo renombrar")
            self._avisar("Sin conexión con la PC principal: el nombre no se cambió.")
            return
        if self._guardar_nombre_local is not None:
            self._guardar_nombre_local(limpio)
        self._yo = limpio
        self._ultimo_pintado = None
        self._anotado.clear()
        self._avisar("")
        self._pintar_yo()
        self.refrescar()

    @staticmethod
    def _identificador() -> str | None:
        try:
            from pos_uniformes.services.satellite_identity_service import get_satellite_id

            return get_satellite_id()
        except Exception:  # noqa: BLE001
            return None

    # ── Pintar ──────────────────────────────────────────────────────────

    def _avisar(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.setVisible(bool(texto))

    def _pintar_yo(self) -> None:
        self.yo_label.setText(f"Esta PC es <b style='color:#111b21'>{self._yo}</b>")

    def _pintar_lista(self, chats) -> None:
        chats = list(chats)
        # Se repinta solo si algo cambió: rehacerla cada 5 s la hacía parpadear,
        # perdía el renglón bajo el ratón y regresaba la lista hasta arriba.
        firma = (self._yo, self._abierto, tuple(chats))
        if firma == self._firma_lista:
            return
        self._firma_lista = firma
        self._chats = chats
        donde = self.lista.verticalScrollBar().value()
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
        self.lista.verticalScrollBar().setValue(donde)
        actual = self._chats[fila_abierta] if self._chats else None
        if actual is not None:
            self._abierto = actual.clave
            self.titulo.setText(("👥 " if actual.es_grupo else "") + actual.nombre)
            self.subtitulo.setText(_estado(actual))
            self.subtitulo.setVisible(bool(_estado(actual)))

    def _pintar_conversacion(self, filas, hay_mas: bool = False) -> None:
        anterior = self._ultimo_pintado
        ultimo = filas[-1].id if filas else 0
        mismo_chat = anterior is not None and anterior[0] == self._abierto
        # Hasta dónde había leído ANTES de abrirlo: de ahí sale «N mensajes nuevos».
        leido_antes = (
            None if mismo_chat or self._buscando
            else int(self._leer_leidos().get(self._abierto, 0) or 0)
        )
        self._ultimo_id = 0 if self._buscando else ultimo
        # Leído es lo que se VIO: al abrir el chat, o si está abajo. Leyendo
        # arriba, lo que llega sigue pendiente hasta que baje.
        if self._ultimo_id and (self._pegado or not mismo_chat):
            self._marcar_leido(self._ultimo_id)
        firma = (
            self._abierto, ultimo, self._buscando, self._cuantos, hay_mas,
            tuple(f.id for f in filas if f.borrado),
        )
        if firma == anterior:
            self._pintar_palomitas()      # nada nuevo, pero alguien pudo haber leído
            return  # no se repinta (no se pierde lo seleccionado)
        self._ultimo_pintado = firma

        # Llegó algo al chat que ya está en pantalla: se AGREGA abajo. Antes se
        # borraba y se repintaba todo, y la barra se iba hasta arriba (Daniel,
        # 2026-11-06: «tengo que bajar manualmente para ver el nuevo mensaje»).
        if mismo_chat and anterior[2:] == firma[2:] and self._pintado_hasta:
            nuevas = [f for f in filas if f.id > self._pintado_hasta]
            if nuevas:
                self._ancla = None
                self._agregar(nuevas)
                self._pintar_palomitas()
                return
        # Mismo chat pero cambió lo de antes (se borró algo, se cargó más
        # historia): se repinta SIN moverle de donde está leyendo.
        self._pintar_todo(
            filas, leido_antes, hay_mas=hay_mas,
            conservar=mismo_chat and anterior[2] == firma[2],
        )
        self._pintar_palomitas()

    def _marcar_leido(self, hasta: int) -> None:
        if self._anotado.get(self._abierto, 0) >= hasta:
            return
        self._anotado[self._abierto] = hasta
        self._guardar_leido(self._abierto, hasta)
        self._apagar_globo()          # el chat abierto no tiene pendientes
        # Y a la base: de ahí salen las dos palomitas en la otra PC.
        from pos_uniformes.services import buzon_service as bz

        try:
            with self._session_factory() as session:
                bz.anotar_leido(session, lector=self._yo, chat=self._abierto, hasta_id=hasta)
                session.commit()
        except Exception:  # noqa: BLE001 — sin palomitas no se cae nada
            logger.exception("Buzón: no se pudo anotar lo leído")

    def _pintar_todo(self, filas, leido_antes: int | None, *, hay_mas: bool = False,
                     conservar: bool = False) -> None:
        barra = self._scroll.verticalScrollBar()
        desde_abajo = barra.maximum() - barra.value()
        estaba_abajo = self._pegado
        while self._mensajes_ly.count() > 1:     # el último es el resorte
            item = self._mensajes_ly.takeAt(0)
            viejo = item.widget()
            if viejo is not None:
                # Fuera de la pantalla YA: deleteLater solo lo borra cuando el
                # bucle de eventos llega a eso, y mientras se encimaba con lo nuevo.
                viejo.hide()
                viejo.setParent(None)
                viejo.deleteLater()
        self._pintado_hasta = 0
        self._dia_ultimo = None
        self._nuevos_abajo = 0
        self._por_id = {}
        self._estados = {}
        if conservar and not estaba_abajo:
            # Se queda a la misma distancia del final: lo que se agregó arriba
            # (historia más vieja) no le mueve lo que está leyendo.
            self._pegado = False
            self._ancla = desde_abajo
        else:
            self._pegado = True           # un chat recién abierto se ve desde el final
            self._ancla = None

        if self._buscando:
            n = len([f for f in filas if f.estado != _RECIBIDO])
            letrero = QLabel(
                f"Nada con «{self._buscando}» en este chat." if not n
                else f"{n} mensaje{'s' if n != 1 else ''} con «{self._buscando}»"
            )
            letrero.setObjectName("fecha")
            self._mensajes_ly.insertWidget(0, letrero, 0, Qt.AlignmentFlag.AlignHCenter)
        elif hay_mas:
            mas = QPushButton("▲ Ver mensajes anteriores")
            mas.setObjectName("anteriores")
            mas.setCursor(Qt.CursorShape.PointingHandCursor)
            mas.clicked.connect(self.cargar_anteriores)
            self._mensajes_ly.insertWidget(0, mas, 0, Qt.AlignmentFlag.AlignHCenter)
        elif not filas:
            vacio = QLabel(
                "Todavía no hay mensajes aquí.\nEscribe abajo y dale Enter para mandarlo."
            )
            vacio.setObjectName("fecha")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._mensajes_ly.insertWidget(0, vacio, 0, Qt.AlignmentFlag.AlignHCenter)
        if not filas:
            self._pintar_ir_abajo()
            return
        # La raya de «mensajes nuevos» va antes del primero que no había visto.
        # Si TODO es nuevo no se pone: no separa nada.
        sin_ver = [
            f.id for f in filas
            if leido_antes is not None and f.id > leido_antes and f.de != self._yo
            and f.estado != _RECIBIDO and not f.borrado
        ]
        raya_en = sin_ver[0] if sin_ver and sin_ver[0] != filas[0].id else None
        self._agregar(filas, raya_en=raya_en, cuantos_nuevos=len(sin_ver), recien_abierto=True)

    def cargar_anteriores(self) -> None:
        """Trae otro tramo de historia, sin mover lo que está leyendo."""
        self._cuantos += self._tramo
        self.refrescar()

    def _agregar(self, filas, *, raya_en: int | None = None, cuantos_nuevos: int = 0,
                 recien_abierto: bool = False) -> None:
        """Pone estas burbujas al final, sin tocar las que ya están."""
        posicion = self._mensajes_ly.count() - 1          # antes del resorte
        ajenos = 0
        con_estado: set[int] = set()
        for f in filas:
            self._pintado_hasta = max(self._pintado_hasta, f.id)
            if f.estado and f.responde_a:
                # Cómo le fue a un comando. «Recibido» no pisa a un resultado.
                if not (f.estado == _RECIBIDO and self._estados.get(f.responde_a, ("",))[0] not in ("", _RECIBIDO)):
                    self._estados[f.responde_a] = (f.estado, f.de)
                con_estado.add(f.responde_a)
            if f.estado == _RECIBIDO:
                continue      # no es un mensaje: es el «ejecutando…» de la burbuja del comando
            if f.id == raya_en:
                raya = QLabel(
                    "1 mensaje nuevo" if cuantos_nuevos == 1 else f"{cuantos_nuevos} mensajes nuevos"
                )
                raya.setObjectName("nuevos")
                self._mensajes_ly.insertWidget(posicion, raya, 0, Qt.AlignmentFlag.AlignHCenter)
                posicion += 1
            dia = _dia(f.creado)
            if dia != self._dia_ultimo:
                separador = QLabel(dia)
                separador.setObjectName("fecha")
                self._mensajes_ly.insertWidget(posicion, separador, 0, Qt.AlignmentFlag.AlignHCenter)
                posicion += 1
                self._dia_ultimo = dia
            self._mensajes_ly.insertWidget(posicion, self._burbuja(f))
            posicion += 1
            if f.de != self._yo and not f.borrado:
                ajenos += 1
        for mensaje_id in con_estado | set(self._estados):
            self._pintar_estado(mensaje_id)
        if not recien_abierto and not self._pegado:
            # Está leyendo arriba: no se le mueve nada; el botón le dice que llegó algo.
            self._nuevos_abajo += ajenos
        self._pintar_ir_abajo()
        if self._pegado:
            # Por si el layout ya acomodó (el cambio de rango es lo que baja de verdad).
            self._bajar.start()

    def _pintar_estado(self, mensaje_id: int) -> None:
        """«Ejecutando en Entrada…» / «Terminó bien» en la burbuja del comando."""
        partes = self._por_id.get(mensaje_id)
        estado = self._estados.get(mensaje_id)
        if partes is None or estado is None:
            return
        cual, quien = estado
        if cual == _RECIBIDO:
            texto, color = f"⏳ Ejecutando en {quien}…", "#8a6d00"
        elif cual == _TERMINO_BIEN:
            texto, color = f"✔ Corrió en {quien}: terminó bien", "#1c7c54"
        else:
            texto, color = f"⚠️ Corrió en {quien}: no terminó bien", "#b3261e"
        partes.estado.setText(texto)
        partes.estado.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color};")
        partes.estado.setVisible(True)

    def _pintar_palomitas(self) -> None:
        """✓ enviado · ✓✓ ya lo abrieron del otro lado."""
        hasta = max(self._vistos.values(), default=0)
        for mensaje_id, partes in self._por_id.items():
            if partes.palomita is None:
                continue
            leido = mensaje_id <= hasta
            partes.palomita.setText("✓✓" if leido else "✓")
            partes.palomita.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {'#34a7e0' if leido else '#8696a0'};"
            )
            quienes = sorted(q for q, h in self._vistos.items() if h >= mensaje_id)
            partes.palomita.setToolTip(
                ("Leído por " + ", ".join(quienes)) if quienes else "Enviado; todavía no lo abren"
            )

    def _apagar_globo(self) -> None:
        from dataclasses import replace

        for i, chat in enumerate(self._chats):
            if chat.clave == self._abierto and chat.no_leidos:
                self._chats[i] = replace(chat, no_leidos=0)
                renglon = self.lista.itemWidget(self.lista.item(i))
                if renglon is not None and renglon.globo is not None:
                    renglon.globo.hide()
                    renglon.cuando.setStyleSheet("font-size: 11px; color: #667781;")

    # ── La barra: seguir lo nuevo sin quitarle su lugar a quien lee ─────

    def _al_mover_barra(self, valor: int) -> None:
        if self._ajustando:
            return
        self._ancla = None                # la movió la persona: ya no hay nada que conservar
        barra = self._scroll.verticalScrollBar()
        self._pegado = valor >= barra.maximum() - UMBRAL_ABAJO
        if self._pegado:
            self._nuevos_abajo = 0
            if self._ultimo_id:
                self._marcar_leido(self._ultimo_id)     # ya bajó: ya los vio
        self._pintar_ir_abajo()

    def _al_cambiar_rango(self, _minimo: int, maximo: int) -> None:
        # El contenido creció (llegó un mensaje, se abrió un «Ver todo», cambió
        # el tamaño de la ventana). Si estaba abajo, sigue abajo; si no, se queda.
        # Bajar aquí y no con un timer: el máximo ya es el de verdad.
        barra = self._scroll.verticalScrollBar()
        if self._ancla is not None:
            self._ajustando = True
            try:
                barra.setValue(max(0, maximo - self._ancla))
            finally:
                self._ajustando = False
        elif self._pegado:
            barra.setValue(maximo)
        self._pintar_ir_abajo()

    def _pintar_ir_abajo(self) -> None:
        barra = self._scroll.verticalScrollBar()
        visible = not self._pegado and barra.maximum() > 0
        if visible:
            n = self._nuevos_abajo
            self.ir_abajo.setText("↓" if not n else (f"↓  {n} nuevo" if n == 1 else f"↓  {n} nuevos"))
            self.ir_abajo.setProperty("nuevos", "true" if n else "false")
            self.ir_abajo.style().unpolish(self.ir_abajo)
            self.ir_abajo.style().polish(self.ir_abajo)
            self._scroll.acomodar_boton()
        self.ir_abajo.setVisible(visible)

    def _bajar_al_final(self) -> None:
        barra = self._scroll.verticalScrollBar()
        self._ancla = None
        self._pegado = True
        self._nuevos_abajo = 0
        barra.setValue(barra.maximum())
        if self._ultimo_id:
            self._marcar_leido(self._ultimo_id)
        self._pintar_ir_abajo()

    # ── Una burbuja ─────────────────────────────────────────────────────

    def _pixmap(self, mensaje_id: int) -> QPixmap | None:
        if mensaje_id in self._pixmaps:
            return self._pixmaps[mensaje_id]
        from pos_uniformes.services import buzon_service as bz

        pix = None
        try:
            with self._session_factory() as session:
                datos = bz.imagen_de(session, mensaje_id)
            if datos:
                pix = QPixmap()
                if not pix.loadFromData(datos):
                    pix = None
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo traer la imagen")
            return None                   # sin guardar: se reintenta al repintar
        self._pixmaps[mensaje_id] = pix
        return pix

    def _burbuja(self, f: "_Fila") -> QWidget:
        from pos_uniformes.services import buzon_service as bz

        de, texto = f.de, f.texto
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

        estado = QLabel("")
        estado.setObjectName("estadoComando")
        estado.setVisible(False)
        palomita: QLabel | None = None

        if f.borrado:
            ido = QLabel(f"🚫 {bz.TEXTO_BORRADO}")
            ido.setObjectName("borrado")
            ido.setStyleSheet("font-size: 13px; font-style: italic; color: #8696a0;")
            bly.addWidget(ido)
            pie = QHBoxLayout()
            pie.addStretch(1)
            hora = QLabel(_hora(f.creado))
            hora.setStyleSheet("font-size: 11px; color: #667781;")
            pie.addWidget(hora)
            bly.addLayout(pie)
            self._por_id[f.id] = _Partes(estado, None)
            fly.addWidget(burbuja)
            if not mio:
                fly.addStretch(1)
            return fila

        # A qué contesta: el resultado va pegado a su comando.
        if f.responde_a:
            de_cita, previa = self._citas.get(f.responde_a, ("", "un mensaje anterior"))
            cita = QLabel()
            cita.setObjectName("cita")
            cita.setTextFormat(Qt.TextFormat.PlainText)
            cita.setText(cita.fontMetrics().elidedText(
                f"↩ {de_cita + ': ' if de_cita else ''}{previa}", Qt.TextElideMode.ElideRight, ANCHO_BURBUJA - 60
            ))
            bly.addWidget(cita)

        if f.adjunto:
            pix = self._pixmap(f.id)
            foto = _Miniatura()
            foto.setObjectName("foto")
            if pix is None:
                foto.setText("🖼 No se pudo cargar la imagen")
            else:
                foto.setPixmap(pix if pix.width() <= 340 and pix.height() <= 340 else pix.scaled(
                    340, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                ))
                foto.setCursor(Qt.CursorShape.PointingHandCursor)
                foto.setToolTip("Tocar para verla completa")
                foto.tocada.connect(lambda p=pix: self._ver_imagen(self, p))
            bly.addWidget(foto)

        if texto:
            # Lo que contesta PowerShell puede traer cientos de renglones: entero,
            # un solo mensaje ocupaba pantallas y no se podía ni llegar al siguiente.
            renglones = texto.splitlines()
            recortado = len(renglones) > RENGLONES_VISIBLES + 5
            corto = "\n".join(renglones[:RENGLONES_VISIBLES]) + "\n…" if recortado else texto
            cuerpo = QLabel(corto)
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
            largo = max((cuerpo.fontMetrics().horizontalAdvance(r) for r in renglones or [""]), default=0)
            cuerpo.setMinimumWidth(min(largo + 4, ANCHO_BURBUJA - 24))
            bly.addWidget(cuerpo)
            if recortado:
                ver = QToolButton()
                ver.setObjectName("verTodo")
                ver.setCursor(Qt.CursorShape.PointingHandCursor)
                abrir = f"▾ Ver todo ({len(renglones)} renglones)"
                ver.setText(abrir)

                def _alternar(_=False, c=cuerpo, b=ver) -> None:
                    completo = b.text() == abrir
                    c.setText(texto if completo else corto)
                    b.setText("▴ Ver menos" if completo else abrir)

                ver.clicked.connect(_alternar)
                bly.addWidget(ver, 0, Qt.AlignmentFlag.AlignLeft)

        bly.addWidget(estado)

        pie = QHBoxLayout()
        pie.setSpacing(2)
        if texto:
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
            correr.clicked.connect(
                lambda _=False, t=texto, d=de, b=correr, i=f.id: self.pedir_ejecucion(t, d, b, mensaje_id=i)
            )
            pie.addWidget(correr)
        contestar = QToolButton()
        contestar.setObjectName("copiar")
        contestar.setText("↩ Responder")
        contestar.setCursor(Qt.CursorShape.PointingHandCursor)
        contestar.clicked.connect(lambda _=False, m=f: self.responder(m))
        pie.addWidget(contestar)
        if mio:
            quitar = QToolButton()
            quitar.setObjectName("borrar")
            quitar.setText("🗑")
            quitar.setToolTip("Borrar este mensaje (en todas las PCs)")
            quitar.setCursor(Qt.CursorShape.PointingHandCursor)
            quitar.clicked.connect(lambda _=False, i=f.id: self.borrar_mensaje(i))
            pie.addWidget(quitar)
        pie.addStretch(1)
        hora = QLabel(_hora(f.creado))
        hora.setStyleSheet("font-size: 11px; color: #667781;")
        pie.addWidget(hora)
        if mio:
            palomita = QLabel("✓")
            palomita.setObjectName("palomita")
            pie.addWidget(palomita)
        bly.addLayout(pie)
        self._por_id[f.id] = _Partes(estado, palomita)

        fly.addWidget(burbuja)
        if not mio:
            fly.addStretch(1)
        return fila

    # ── Ejecutar ────────────────────────────────────────────────────────

    def pedir_ejecucion(self, texto: str, de: str, boton: QToolButton | None = None,
                        *, mensaje_id: int | None = None) -> None:
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
            self._boton_corriendo = boton
        self._avisar(f"Ejecutando… lo que salga se le manda a {de}.")
        if self._en_hilo:
            import threading

            threading.Thread(
                target=self._correr_y_contestar, args=(texto, de, mensaje_id),
                daemon=True, name="buzon-ejecutar",
            ).start()
        else:
            self._correr_y_contestar(texto, de, mensaje_id)

    def _correr_y_contestar(self, texto: str, de: str, mensaje_id: int | None = None) -> None:
        """Corre y manda el resultado. Va en su hilo: el kiosko no se congela.

        El resultado se manda DESDE AQUÍ y no desde la ventana: si alguien la
        cierra mientras corre, la respuesta igual llega. Y pase lo que pase
        algo llega: primero «recibido», al final el resultado o el error.
        En la primera prueba el botón se quedó en «Ejecutando…» y del otro lado
        no llegó nada; no se sabía ni si había arrancado (2026-10-15).

        Los dos van pegados al comando (`responde_a`): el «recibido» se ve como
        «⏳ Ejecutando en…» en la burbuja del comando, y el resultado lo cita."""
        from pos_uniformes.services import buzon_service as bz
        from pos_uniformes.services.buzon_ejecutar_service import Resultado, texto_de_resultado

        self._mandar_desde_hilo(
            f"⏳ Recibido en {self._yo}: ejecutando…", de, responde_a=mensaje_id, estado=bz.RECIBIDO
        )
        try:
            resultado = self._ejecutar(texto)
        except Exception as exc:  # noqa: BLE001 — un tropiezo también se reporta
            logger.exception("Buzón: falló la ejecución")
            resultado = Resultado("", None, 0.0, error=f"Falló antes de terminar: {exc}")
        mensaje = texto_de_resultado(resultado, pc=self._yo, maximo=bz.MAXIMO_CARACTERES)
        self._mandar_desde_hilo(
            mensaje, de, responde_a=mensaje_id, estado=bz.TERMINO_BIEN if resultado.ok else bz.FALLO
        )
        try:
            self._ejecucion_terminada.emit()
        except RuntimeError:  # la ventana ya se cerró
            pass

    def _mandar_desde_hilo(self, texto: str, para: str, *, responde_a: int | None = None,
                           estado: str | None = None) -> None:
        from pos_uniformes.services import buzon_service as bz

        try:
            with self._session_factory() as session:
                bz.enviar(session, texto, de=self._yo, para=para, responde_a=responde_a, estado=estado)
                session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Buzón: no se pudo mandar desde el hilo")

    def _al_terminar_ejecucion(self) -> None:
        self._avisar("")
        # Solo se devuelve el botón a su lugar: repintar todo movía la barra.
        boton, self._boton_corriendo = self._boton_corriendo, None
        if boton is not None:
            try:
                boton.setText("▶ Ejecutar")
                boton.setEnabled(True)
            except RuntimeError:      # la burbuja ya no existe (se cambió de chat)
                pass
        self.refrescar()

    @staticmethod
    def _copiar(texto: str, boton: QToolButton) -> None:
        QApplication.clipboard().setText(texto)
        boton.setText("✅ Copiado")


def abrir_buzon(parent: QWidget | None = None) -> None:
    BuzonDialog(parent).exec()
