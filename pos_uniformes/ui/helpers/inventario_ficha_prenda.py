"""«La prenda» en la ficha de Inventario: su escalera de tallas y lo que le falta (tanda 4 del alta).

Bajo la tarjeta vino de la ficha, solo para ADMIN:

    LA PRENDA                         ＋ Otro color   ✏️ Corregir prenda
    [4] [6] [8] [10] [12] [14] [16] [CH] [MD] [GD]  [EXG ＋ $305]
    ＋ Otra talla ▾
    En gris: tallas que hay de Pants Suelto en otras escuelas…

Las tallas que ya tiene van en blanco (la elegida, en vino suave); las que
tienen sus hermanas y esta no, en gris con su precio sugerido. Un toque abre
la confirmación corta (`TallaNuevaDialog`). «＋ Otra talla» (un enlace en su
renglón, no un chip: no se confunde con las sugeridas) ofrece la lista
oficial. «✏️ Corregir prenda» es el único lápiz de la ficha: «Editar talla»
y «📝 Más datos» (marca, tipo, escuela…; tanda 5, reemplaza al editor viejo) van sin él. «Agregar talla o color» y «Duplicar talla» viven aquí, ya con la
prenda elegida (antes, en el «⋯» de arriba, con una lista de 580 prendas).

Aquí solo hay pantalla y cableado: la escalera la arma
`alta_ficha_service.leer_ficha` y las altas, el motor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services.alta_ficha_service import FichaPrenda
from pos_uniformes.ui.styles.inventario_styles import BORDE, CAFE, FUENTE, TENUE, VINO, VINO_SUAVE

if TYPE_CHECKING:  # pragma: no cover
    from pos_uniformes.ui.main_window import MainWindow

GRIS = "#8a8177"
GRIS_FONDO = "#f6f2ec"

ESTILO = f"""
QFrame#invPrenda, QWidget#invPrendaRejilla {{ background: transparent; font-family: {FUENTE}; }}
QLabel#invPrendaTitulo {{ font-size: 11px; font-weight: 800; color: {VINO}; letter-spacing: 1.5px; }}
QPushButton#invPrendaEnlace {{
    background: transparent; color: {VINO}; border: none; font-size: 13px; font-weight: 700; padding: 2px 4px;
}}
QPushButton#invPrendaEnlace:hover {{ text-decoration: underline; }}
QPushButton#invPrendaEnlace:disabled {{ color: #b4aba0; }}
QLabel#invPrendaTalla {{
    background: #ffffff; color: {CAFE}; border: 1px solid {BORDE}; border-radius: 10px;
    padding: 3px 9px; font-size: 13px; font-weight: 700;
}}
QLabel#invPrendaTalla[actual="si"] {{ background: {VINO_SUAVE}; color: {VINO}; border-color: #d9b6c4; }}
QPushButton#invPrendaFalta {{
    background: {GRIS_FONDO}; color: {GRIS}; border: 1px dashed #c9bcad; border-radius: 10px;
    padding: 3px 9px; font-size: 13px; font-weight: 700;
}}
QPushButton#invPrendaFalta:hover {{ background: {VINO_SUAVE}; color: {VINO}; border-color: #d9b6c4; }}
QToolButton#invPrendaOtra {{
    background: transparent; color: {VINO}; border: none; font-size: 13px; font-weight: 700; padding: 2px 4px;
}}
QToolButton#invPrendaOtra::menu-indicator {{ image: none; width: 0; }}
QToolButton#invPrendaOtra:hover {{ text-decoration: underline; }}
QToolButton#invPrendaOtra:disabled {{ color: #b4aba0; }}
QLabel#invPrendaNota {{ font-size: 12px; color: {TENUE}; }}
"""


class Flujo(QLayout):
    """Pone los widgets en renglones, como texto (Qt no trae uno)."""

    def __init__(self, parent: QWidget | None = None, *, espacio: int = 6) -> None:
        super().__init__(parent)
        self._items = []
        self._espacio = espacio
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802 - API de Qt
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i):  # noqa: N802 - API de Qt
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):  # noqa: N802 - API de Qt
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802 - API de Qt
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - API de Qt
        return True

    def heightForWidth(self, ancho: int) -> int:  # noqa: N802 - API de Qt
        return self._acomodar(QRect(0, 0, ancho, 0), probar=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - API de Qt
        super().setGeometry(rect)
        self._acomodar(rect, probar=False)

    def sizeHint(self) -> QSize:  # noqa: N802 - API de Qt
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - API de Qt
        tam = QSize()
        for item in self._items:
            tam = tam.expandedTo(item.minimumSize())
        return tam

    def _acomodar(self, rect: QRect, *, probar: bool) -> int:
        x, y, alto_renglon = rect.x(), rect.y(), 0
        for item in self._items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            tam = item.sizeHint()
            if x + tam.width() > rect.right() + 1 and alto_renglon > 0:
                x = rect.x()
                y += alto_renglon + self._espacio
                alto_renglon = 0
            if not probar:
                item.setGeometry(QRect(QPoint(x, y), tam))
            x += tam.width() + self._espacio
            alto_renglon = max(alto_renglon, tam.height())
        return y + alto_renglon - rect.y()


def _boton(nombre: str, texto: str, aviso: str = "") -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName(nombre)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    boton.setAutoDefault(False)
    if aviso:
        boton.setToolTip(aviso)
    return boton


class SeccionPrenda(QFrame):
    """La escalera de la prenda con sus tallas en gris. Avisa lo que se toca."""

    talla_tocada = pyqtSignal(str)
    otra_talla = pyqtSignal(str)
    otro_color = pyqtSignal()
    corregir = pyqtSignal()
    datos = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("invPrenda")
        self.setStyleSheet(ESTILO)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.ficha: FichaPrenda | None = None
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 2, 0, 2)
        caja.setSpacing(6)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(4)
        titulo = QLabel("LA PRENDA")
        titulo.setObjectName("invPrendaTitulo")
        cabeza.addWidget(titulo)
        cabeza.addStretch(1)
        self.boton_color = _boton("invPrendaEnlace", "＋ Otro color",
                                  "Copia todas las tallas, con sus precios, en un color nuevo")
        self.boton_corregir = _boton("invPrendaEnlace", "✏️ Corregir prenda",
                                     "Cambiar el nombre o el color de todas las tallas a la vez")
        # Tanda 5: «Más datos» reemplaza al editor viejo de la prenda (marca, tipo, escuela…).
        self.boton_datos = _boton("invPrendaEnlace", "📝 Más datos",
                                  "Marca, categoría, tipo, pieza, escuela, género, escudo, costo…")
        self.boton_color.clicked.connect(self.otro_color.emit)
        self.boton_corregir.clicked.connect(self.corregir.emit)
        self.boton_datos.clicked.connect(self.datos.emit)
        cabeza.addWidget(self.boton_color)
        cabeza.addWidget(self.boton_corregir)
        caja.addLayout(cabeza)
        self.rejilla = QWidget()
        self.rejilla.setObjectName("invPrendaRejilla")
        self.rejilla.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.flujo = Flujo(self.rejilla)
        caja.addWidget(self.rejilla)
        self.boton_otra = QToolButton()
        self.boton_otra.setObjectName("invPrendaOtra")
        self.boton_otra.setText("＋ Otra talla")
        self.boton_otra.setToolTip("Una talla de la lista oficial que ni sus hermanas tienen")
        self.boton_otra.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_otra.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_otra = QMenu(self.boton_otra)
        self.menu_otra.setObjectName("invMenu")
        self.boton_otra.setMenu(self.menu_otra)
        # «📝 Más datos» abajo a la derecha: en la cabeza no cabe a 1366×768.
        pie = QHBoxLayout()
        pie.setSpacing(4)
        pie.addWidget(self.boton_otra, 0, Qt.AlignmentFlag.AlignLeft)
        pie.addStretch(1)
        pie.addWidget(self.boton_datos)
        caja.addLayout(pie)
        self.nota = QLabel()
        self.nota.setObjectName("invPrendaNota")
        self.nota.setWordWrap(True)
        caja.addWidget(self.nota)
        self.chips_tallas: dict[str, QLabel] = {}
        self.chips_faltan: dict[str, QPushButton] = {}
        self.setVisible(False)

    def mostrar(self, ficha: FichaPrenda | None, talla_actual: str | None = None) -> None:
        self.ficha = ficha
        if ficha is None:
            self.setVisible(False)
            return
        while self.flujo.count():
            item = self.flujo.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self.chips_tallas, self.chips_faltan = {}, {}
        for t in ficha.tallas:
            chip = QLabel(t.talla)
            chip.setObjectName("invPrendaTalla")
            chip.setProperty("actual", "si" if t.talla == talla_actual else "no")
            chip.setToolTip(f"Talla {t.talla} · ${t.precio:,.0f}" + (
                f" · {', '.join(t.colores)}" if len(ficha.colores) > 1 else ""))
            self.flujo.addWidget(chip)
            self.chips_tallas[t.talla] = chip
        for f in ficha.faltan:
            boton = _boton("invPrendaFalta", f.texto_chip,
                           f"{f.texto_cobertura(ficha.tipo_pieza)}. Toca para agregarla a esta prenda.")
            boton.clicked.connect(lambda _=False, talla=f.talla: self.talla_tocada.emit(talla))
            self.flujo.addWidget(boton)
            self.chips_faltan[f.talla] = boton
        self.menu_otra.clear()
        for talla in ficha.otras_tallas:
            accion = self.menu_otra.addAction(talla)
            accion.triggered.connect(lambda _=False, t=talla: self.otra_talla.emit(t))
        self.boton_otra.setVisible(bool(ficha.otras_tallas))
        self.nota.setText(ficha.texto_hermanas)
        self.nota.setVisible(bool(ficha.texto_hermanas))
        for w in (self.boton_color, self.boton_corregir, self.boton_otra, *self.chips_faltan.values()):
            w.setEnabled(ficha.activa)
        self.boton_datos.setEnabled(True)  # los datos de una prenda apagada también se corrigen
        self.rejilla.updateGeometry()
        self.setVisible(True)


# ── Acciones (cableado con la ventana) ─────────────────────────────────────

def _es_admin(window) -> bool:
    return getattr(window, "current_role", None) == RolUsuario.ADMIN


def _sin_permiso(window) -> bool:
    if _es_admin(window):
        return False
    QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede cambiar el catálogo.")
    return True


def _abrir(window, dialogo: QDialog) -> object | None:
    """Abre la ventanita; si guardó, refresca Inventario. Devuelve el resultado."""
    if dialogo.exec() != QDialog.DialogCode.Accepted or getattr(dialogo, "resultado", None) is None:
        return None
    resultado = dialogo.resultado
    refrescar = getattr(window, "refresh_all", None)
    if callable(refrescar):
        refrescar()
    return resultado


def _elegir_creada(window, resultado) -> None:
    productos = getattr(resultado, "productos", ()) or ()
    pantalla = getattr(window, "inventario_pantalla", None)
    if pantalla is not None and productos and productos[0].tallas:
        pantalla.seleccionar(productos[0].tallas[0].variante_id)


def agregar_talla(window, session_factory: Callable, producto_id: int, talla: str, nota: str = "") -> object | None:
    if _sin_permiso(window):
        return None
    from pos_uniformes.ui.dialogs.ficha_prenda_dialogs import TallaNuevaDialog

    dialogo = TallaNuevaDialog(window, session_factory=session_factory, usuario_id=int(window.user_id),
                               producto_id=producto_id, talla=talla, nota_hermanas=nota)
    resultado = _abrir(window, dialogo)
    if resultado is not None:
        _elegir_creada(window, resultado)
    return resultado


def agregar_color(window, session_factory: Callable, producto_id: int) -> object | None:
    if _sin_permiso(window):
        return None
    from pos_uniformes.ui.dialogs.ficha_prenda_dialogs import OtroColorDialog

    dialogo = OtroColorDialog(window, session_factory=session_factory, usuario_id=int(window.user_id),
                              producto_id=producto_id)
    resultado = _abrir(window, dialogo)
    if resultado is not None:
        _elegir_creada(window, resultado)
    return resultado


def corregir_prenda(window, session_factory: Callable, producto_id: int) -> object | None:
    if _sin_permiso(window):
        return None
    from pos_uniformes.ui.dialogs.ficha_prenda_dialogs import CorregirPrendaDialog

    dialogo = CorregirPrendaDialog(window, session_factory=session_factory, usuario_id=int(window.user_id),
                                   producto_id=producto_id)
    return _abrir(window, dialogo)


def editar_datos(window, session_factory: Callable, producto_id: int) -> object | None:
    """«📝 Más datos»: el reemplazo del editor viejo de la prenda (tanda 5)."""
    if _sin_permiso(window):
        return None
    from pos_uniformes.ui.dialogs.datos_prenda_dialog import DatosPrendaDialog

    dialogo = DatosPrendaDialog(window, session_factory=session_factory, usuario_id=int(window.user_id),
                                producto_id=producto_id)
    return _abrir(window, dialogo)


#: Lo que dice el «⋯» de arriba cuando no hay prenda elegida.
TEXTO_ELIGE_PRENDA = (
    "Elige en la lista una talla de la prenda. En su ficha, bajo «LA PRENDA», están las tallas que le "
    "faltan, «＋ Otra talla», «＋ Otro color», «✏️ Corregir prenda» y «📝 Más datos»."
)


__all__ = [
    "Flujo",
    "SeccionPrenda",
    "TEXTO_ELIGE_PRENDA",
    "agregar_color",
    "agregar_talla",
    "corregir_prenda",
    "editar_datos",
]
