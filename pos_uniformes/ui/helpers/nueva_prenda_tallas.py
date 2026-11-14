"""La tabla de tallas de «Nueva prenda» (tanda 3 del alta, 2026-11-13).

    TALLA   PRECIO   DE DÓNDE                    LLEGAN
    ☑ 4     $245     como las demás              [ — ]   ← LLEGAN HOY (opcional)
    ☑ GD    $289     a mano   ¿$289? → [¿$295?]  [  ]
    ☐ EXG   $305     la tienen 1 de las 4 prendas de Pants Suelto   (gris)

Las tallas no se escriben: se marcan. Las que no trae el modelo salen en gris
con cuántas hermanas las tienen. El precio se edita; «de dónde» lo recalcula
el motor (`alta_prenda_service.completar`). Un precio vacío o en $0 se pone
en rojo; un precio más bajo que en las demás escuelas, en ámbar (deja
guardar); uno que no termina en 5 o 9 ofrece la sugerencia con un toque.

Aquí no hay reglas: la tabla enseña un `PlanPrenda` y avisa lo que se tocó.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import QRegularExpression, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIntValidator, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import nueva_prenda_service as nps
from pos_uniformes.services.talla_orden_service import clave_talla

ALTO_FILA = 32
#: Pausa tras la última tecla antes de pasar el precio al plan: así el botón
#: «Dar de alta» se enciende sin tener que dar Enter o Tab (un clic en un botón
#: apagado no le quita el foco al campo y nunca llegaría `editingFinished`).
REBOTE_PRECIO_MS = 300


def leer_precio(texto: str) -> Decimal | None:
    """«$245», «245.50», «» → Decimal o None."""
    limpio = str(texto or "").replace("$", "").replace(",", "").strip()
    if not limpio:
        return None
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def leer_cantidad(texto: str) -> int:
    try:
        return max(0, int(str(texto or "").strip() or 0))
    except ValueError:
        return 0


def texto_aviso(t) -> str:
    """El aviso ámbar, corto para la columna («más bajo que las demás ($295)»);
    el completo va en la sugerencia emergente."""
    if t.moda is not None and t.precio is not None and t.precio < t.moda:
        return f"más bajo que las demás (${t.moda:.0f})"
    return t.aviso


def texto_precio(precio: Decimal | None) -> str:
    if precio is None:
        return ""
    return f"{precio:.0f}" if precio == precio.to_integral_value() else f"{precio:.2f}"


def _repulir(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class FilaTalla:
    """Los widgets de una talla (marcada o posible)."""

    def __init__(self, tabla: "TablaTallas", talla: str) -> None:
        self.talla = talla
        self.marca = QCheckBox(talla)
        self.marca.setObjectName("npTalla")
        self.marca.setCursor(Qt.CursorShape.PointingHandCursor)
        self.precio = QLineEdit()
        self.precio.setObjectName("npPrecio")
        self.precio.setPlaceholderText("$")
        self.precio.setFixedWidth(92)
        self.precio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.precio.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\$?\d{0,5}(\.\d{0,2})?$")))
        self.donde = QLabel()
        self.donde.setObjectName("npDonde")
        self.donde.setWordWrap(True)
        self.sugerencia = QPushButton()
        self.sugerencia.setObjectName("npSugerencia")
        self.sugerencia.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sugerencia.hide()
        self.llegan = QLineEdit()
        self.llegan.setObjectName("npLlegan")
        self.llegan.setFixedWidth(78)
        self.llegan.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.llegan.setValidator(QIntValidator(0, 9999))
        self.llegan.setPlaceholderText("—")
        self.llegan.setToolTip("Cuántas llegan ahora (opcional). Entra como una entrada normal: se puede corregir.")

        self.rebote = QTimer(self.precio)
        self.rebote.setSingleShot(True)
        self.rebote.setInterval(REBOTE_PRECIO_MS)

        def pasar_precio() -> None:
            self.rebote.stop()
            tabla._al_editar_precio(self.talla, self.precio.text())

        self.marca.toggled.connect(lambda v: tabla._al_marcar(self.talla, v))
        self.precio.textEdited.connect(lambda _t: self.rebote.start())
        self.rebote.timeout.connect(pasar_precio)
        self.precio.editingFinished.connect(pasar_precio)
        self.sugerencia.clicked.connect(lambda: tabla.sugerencia_aceptada.emit(self.talla))
        self.llegan.editingFinished.connect(lambda: tabla._al_llegan(self.talla, leer_cantidad(self.llegan.text())))
        self._precio_mostrado = ""

    def widgets(self) -> list[QWidget]:
        return [self.marca, self.precio, self.donde, self.sugerencia, self.llegan]

    def mostrar(self, t, *, marcada: bool, cobertura: str = "") -> None:
        for w in (self.marca, self.precio, self.llegan):
            w.blockSignals(True)
        try:
            self.marca.setChecked(marcada)
            self.marca.setProperty("posible", "no" if marcada else "si")
            texto = texto_precio(t.precio)
            if not self.precio.hasFocus() or not marcada:
                self.precio.setText(texto)
            self._precio_mostrado = texto
            self.precio.setEnabled(marcada)
            self.llegan.setEnabled(marcada)
            self.llegan.setPlaceholderText("—" if marcada else "")
            cuantas = int(t.llegan or 0) if marcada else 0
            if not self.llegan.hasFocus() or not marcada:
                self.llegan.setText(str(cuantas) if cuantas else "")
        finally:
            for w in (self.marca, self.precio, self.llegan):
                w.blockSignals(False)

        if not marcada:
            self.donde.setText(cobertura or t.texto_cobertura or "no la trae el modelo")
            tono, estado = "", ""
        elif t.error:
            self.donde.setText(t.error)
            tono, estado = "danger", "error"
        elif t.aviso:
            self.donde.setText(texto_aviso(t))
            tono, estado = "warning", "aviso"
        else:
            self.donde.setText(t.origen_precio)
            tono, estado = "", ""
        self.donde.setToolTip("\n".join(x for x in (t.aviso if marcada else "", cobertura) if x))
        self.donde.setProperty("tono", tono)
        self.donde.setProperty("posible", "no" if marcada else "si")
        self.precio.setProperty("estado", estado)
        if marcada and t.sugerencia_5_9 is not None:
            self.sugerencia.setText(f"¿${t.sugerencia_5_9:.0f}?")
            self.sugerencia.setToolTip("Termina en 5 o 9, como los demás precios de la tienda. Toca para usarlo.")
            self.sugerencia.show()
        else:
            self.sugerencia.hide()
        for w in (self.marca, self.donde, self.precio):
            _repulir(w)


class TablaTallas(QFrame):
    """Enseña las tallas de un plan y avisa qué se tocó."""

    marcada = pyqtSignal(str, bool)
    precio_cambiado = pyqtSignal(str, object)  # talla, Decimal | None
    sugerencia_aceptada = pyqtSignal(str)
    llegan_cambiado = pyqtSignal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("npTallas")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(16, 10, 16, 8)
        caja.setSpacing(0)
        self.rejilla = QGridLayout()
        self.rejilla.setHorizontalSpacing(12)
        self.rejilla.setVerticalSpacing(0)
        self.rejilla.setColumnMinimumWidth(0, 110)
        self.rejilla.setColumnStretch(2, 1)
        caja.addLayout(self.rejilla)
        for col, titulo in enumerate(("TALLA", "PRECIO", "DE DÓNDE", "", "LLEGAN HOY")):
            etiqueta = QLabel(titulo)
            etiqueta.setObjectName("npColTitulo")
            if titulo in ("PRECIO", "LLEGAN HOY"):
                etiqueta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.rejilla.addWidget(etiqueta, 0, col)
        self.rejilla.setRowMinimumHeight(0, 28)
        self.filas: dict[str, FilaTalla] = {}
        self._orden: list[str] = []

    # ── Mostrar ───────────────────────────────────────────────────────────
    def mostrar(self, plan) -> None:
        marcadas = {t.talla: t for t in plan.tallas}
        posibles = {t.talla: t for t in plan.tallas_posibles if t.talla not in marcadas}
        orden = sorted([*marcadas, *posibles], key=clave_talla)
        if orden != self._orden:
            self._rehacer(orden)
        for talla in orden:
            fila = self.filas[talla]
            t = marcadas.get(talla) or posibles[talla]
            fila.mostrar(t, marcada=talla in marcadas,
                         cobertura=nps.texto_cobertura_talla(t, getattr(plan, "tipo_pieza", None)))

    def _rehacer(self, orden: list[str]) -> None:
        for fila in self.filas.values():
            for w in fila.widgets():
                self.rejilla.removeWidget(w)
                w.deleteLater()
        self.filas = {}
        for i, talla in enumerate(orden, start=1):
            fila = FilaTalla(self, talla)
            self.filas[talla] = fila
            self.rejilla.addWidget(fila.marca, i, 0)
            self.rejilla.addWidget(fila.precio, i, 1, Qt.AlignmentFlag.AlignRight)
            self.rejilla.addWidget(fila.donde, i, 2)
            self.rejilla.addWidget(fila.sugerencia, i, 3)
            self.rejilla.addWidget(fila.llegan, i, 4, Qt.AlignmentFlag.AlignRight)
            self.rejilla.setRowMinimumHeight(i, ALTO_FILA)
        self._orden = list(orden)

    # ── Lo que se tocó ────────────────────────────────────────────────────
    def _al_marcar(self, talla: str, valor: bool) -> None:
        self.marcada.emit(talla, bool(valor))

    def _al_editar_precio(self, talla: str, texto: str) -> None:
        fila = self.filas.get(talla)
        if fila is None or texto.strip() == fila._precio_mostrado:
            return
        fila._precio_mostrado = texto.strip()
        self.precio_cambiado.emit(talla, leer_precio(texto))

    def _al_llegan(self, talla: str, valor: int) -> None:
        self.llegan_cambiado.emit(talla, valor)


__all__ = ["TablaTallas", "leer_precio", "texto_precio"]
