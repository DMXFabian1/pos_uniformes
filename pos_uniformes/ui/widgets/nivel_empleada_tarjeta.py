"""La tarjeta de su descuento en la Libreta de cada empleada (Daniel, 2026-11-12).

«Para que ellas vean qué tanto descuento se van a llevar.» Dos partes que no
se confunden:

- ESTE MES: con qué % compra hoy, cuánto le queda del tope y lo que se ha
  ahorrado.
- PARA EL MES QUE ENTRA: una sola pista con los niveles marcados y dónde va
  ella («Tú · 124»), y en palabras qué le falta.

Primera versión (mismo día) tenía una barra y una escalera de cajitas por
separado, y la cajita encendida era la del mes que entra: con 20 % hoy y 5 %
encendido parecía que había bajado. «Hay que mejorar esta vista.»
"""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QBoxLayout, QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from pos_uniformes.services import incentivo_empleada_service as inc

TARJETA = "#fffdf9"
BORDE = "#e6dccd"
TINTA = "#2c2a27"
GRIS = "#8a7a68"
CAFE = "#73341c"
VINO = "#6b1f3a"
VERDE = "#2f5d3a"
PISTA = "#efe6d8"

_NBSP = " "


def pct(valor) -> str:
    """«15 %» sin que el % se vaya solo al siguiente renglón."""
    return inc.fmt_pct(valor).replace(" ", _NBSP)


def _dinero(valor) -> str:
    return f"${Decimal(str(valor)):,.2f}"


def _etiqueta(texto: str, estilo: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"background: transparent; {estilo}")
    return lbl


def _encabezado(texto: str) -> QLabel:
    return _etiqueta(texto, f"color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 1.5px;")


def frase_mes_siguiente(av: inc.AvanceEmpleada) -> str:
    """Qué le toca el mes que entra y qué le falta, en palabras."""
    mes = av.nombre_mes_siguiente
    va = pct(av.pct_mes_siguiente)
    if av.siguiente is None:
        return f"Con {av.comisiones_mes} comisiones ya tienes el máximo: en {mes} compras con {va} 🎉"
    frase = (
        f"Con {av.comisiones_mes} comisiones vas para <b>{va}</b>. "
        f"Te faltan <b>{av.faltan}</b> para <b>{pct(av.siguiente.porcentaje)}</b>."
    )
    if av.pct_mes_siguiente < av.pct_este_mes:
        # Hoy compra con más de lo que lleva para el mes que entra: que sepa
        # cuánto necesita para no bajar.
        mantener = next(
            (n for n in av.niveles if Decimal(str(n.porcentaje)) == Decimal(str(av.pct_este_mes))), None
        )
        if mantener is not None and mantener.comisiones_minimas > av.siguiente.comisiones_minimas:
            frase += f" Para seguir con {pct(av.pct_este_mes)} necesitas {mantener.comisiones_minimas}."
    return frase


class PistaNiveles(QWidget):
    """La pista de comisiones con los niveles y la marca «Tú»."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.comisiones = 0
        self.niveles: tuple[inc.Nivel, ...] = ()
        self.setMinimumHeight(96)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, comisiones: int, niveles) -> None:
        self.comisiones = max(int(comisiones), 0)
        self.niveles = tuple(sorted(niveles, key=lambda n: n.comisiones_minimas))
        self.update()

    def tope_escala(self) -> float:
        ultimo = self.niveles[-1].comisiones_minimas if self.niveles else 100
        return float(max(ultimo * 1.12, self.comisiones * 1.04, 1))

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        margen = 30
        ancho = self.width() - 2 * margen
        escala = self.tope_escala()

        def x(v: float) -> float:
            return margen + ancho * min(v, escala) / escala

        y_pista, alto_pista = 30, 10
        # Pista y lo que lleva.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(PISTA))
        p.drawRoundedRect(QRectF(margen, y_pista, ancho, alto_pista), 5, 5)
        p.setBrush(QColor(CAFE))
        p.drawRoundedRect(QRectF(margen, y_pista, max(x(self.comisiones) - margen, alto_pista), alto_pista), 5, 5)

        fuerte = QFont(self.font())
        fuerte.setPixelSize(14)
        fuerte.setBold(True)
        chica = QFont(self.font())
        chica.setPixelSize(12)
        for n in self.niveles:
            cx = x(n.comisiones_minimas)
            alcanzado = self.comisiones >= n.comisiones_minimas
            # El punto del nivel.
            p.setPen(QPen(QColor(VINO if alcanzado else "#cdbfae"), 2))
            p.setBrush(QColor(VINO if alcanzado else "#ffffff"))
            p.drawEllipse(QRectF(cx - 7, y_pista + alto_pista / 2 - 7, 14, 14))
            # Arriba el %, abajo cuántas comisiones.
            p.setFont(fuerte)
            p.setPen(QColor(VINO if alcanzado else GRIS))
            p.drawText(QRectF(cx - 40, 2, 80, 20), Qt.AlignmentFlag.AlignCenter, inc.fmt_pct(n.porcentaje))
            p.setFont(chica)
            p.setPen(QColor(GRIS))
            p.drawText(QRectF(cx - 40, y_pista + 16, 80, 16), Qt.AlignmentFlag.AlignCenter, str(n.comisiones_minimas))

        # Ella: un punto grande en la pista y su etiqueta abajo.
        cx = x(self.comisiones)
        p.setPen(QPen(QColor("#ffffff"), 3))
        p.setBrush(QColor(CAFE))
        p.drawEllipse(QRectF(cx - 10, y_pista + alto_pista / 2 - 10, 20, 20))
        texto = f"Tú · {self.comisiones}"
        p.setFont(fuerte)
        ancho_txt = p.fontMetrics().horizontalAdvance(texto) + 20
        izq = min(max(cx - ancho_txt / 2, 0), self.width() - ancho_txt)
        caja = QRectF(izq, y_pista + 36, ancho_txt, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CAFE))
        p.drawRoundedRect(caja, 13, 13)
        p.setPen(QColor("#ffffff"))
        p.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
        p.end()


class NivelEmpleadaTarjeta(QFrame):
    """`mostrar(avance)` la llena; `mostrar(None)` la esconde."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("nivelEmpleada")
        self.setStyleSheet(
            f"QFrame#nivelEmpleada {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 16px; }}"
        )
        ly = QHBoxLayout(self)
        ly.setContentsMargins(20, 16, 20, 16)
        ly.setSpacing(0)

        # ── Este mes ──
        hoy = QVBoxLayout()
        hoy.setSpacing(4)
        self.titulo = _encabezado("")
        hoy.addWidget(self.titulo)
        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.pct = _etiqueta("", f"color: {VINO}; font-size: 44px; font-weight: 900;")
        fila.addWidget(self.pct)
        self.detalle_pct = _etiqueta("", f"color: {TINTA}; font-size: 14px; font-weight: 600;")
        fila.addWidget(self.detalle_pct, 0, Qt.AlignmentFlag.AlignVCenter)
        fila.addStretch(1)
        hoy.addLayout(fila)
        self.quedan = _etiqueta("", f"color: {TINTA}; font-size: 15px; font-weight: 700;")
        hoy.addWidget(self.quedan)
        self.barra_tope = QProgressBar()
        self.barra_tope.setRange(0, 1000)
        self.barra_tope.setTextVisible(False)
        self.barra_tope.setFixedHeight(8)
        self.barra_tope.setStyleSheet(
            f"QProgressBar {{ background: {PISTA}; border: none; border-radius: 4px; }}"
            f"QProgressBar::chunk {{ background: {VINO}; border-radius: 4px; }}"
        )
        hoy.addWidget(self.barra_tope)
        self.detalle_tope = _etiqueta("", f"color: {GRIS}; font-size: 12px;")
        self.detalle_tope.setWordWrap(True)
        hoy.addWidget(self.detalle_tope)
        self.ahorro = QLabel("")
        self.ahorro.setStyleSheet(
            f"background: #eef2ea; color: {VERDE}; border-radius: 11px; padding: 5px 12px; font-size: 14px; font-weight: 800;"
        )
        fila_ahorro = QHBoxLayout()
        fila_ahorro.setContentsMargins(0, 4, 0, 0)
        fila_ahorro.addWidget(self.ahorro)
        fila_ahorro.addStretch(1)
        hoy.addLayout(fila_ahorro)
        hoy.addStretch(1)
        ly.addLayout(hoy, 5)

        self._separador = QFrame()
        self._separador.setFixedWidth(1)
        self._separador.setStyleSheet(f"background: {BORDE};")
        ly.addSpacing(22)
        ly.addWidget(self._separador)
        ly.addSpacing(22)

        # ── El mes que entra ──
        sigue = QVBoxLayout()
        sigue.setSpacing(6)
        self.titulo_sigue = _encabezado("")
        sigue.addWidget(self.titulo_sigue)
        self.avance = _etiqueta("", f"color: {TINTA}; font-size: 15px;")
        self.avance.setWordWrap(True)
        self.avance.setTextFormat(Qt.TextFormat.RichText)
        sigue.addWidget(self.avance)
        self.pista = PistaNiveles()
        sigue.addWidget(self.pista)
        sigue.addStretch(1)
        ly.addLayout(sigue, 7)

        self._ly = ly
        self.setVisible(False)

    def set_vertical(self, vertical: bool) -> None:
        """Este mes arriba y el mes que entra abajo (en la columna angosta de
        la Libreta agrupada)."""
        self._ly.setDirection(QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight)
        if vertical:
            self._separador.setMinimumWidth(0)
            self._separador.setMaximumWidth(16777215)
            self._separador.setFixedHeight(1)
            self._ly.setSpacing(0)
        else:
            self._separador.setMinimumHeight(0)
            self._separador.setMaximumHeight(16777215)
            self._separador.setFixedWidth(1)
        self.pista.setMinimumWidth(260 if vertical else 320)
        self._vertical = vertical

    def mostrar(self, av: inc.AvanceEmpleada | None) -> None:
        if av is None:
            self.setVisible(False)
            return
        mes = (av.nombre_mes or "este mes").upper()
        # En la Libreta agrupada cada recuadro dice qué es: «MI PAGO», «MIS
        # DESCANSOS»… y este, «MI DESCUENTO».
        self.titulo.setText(f"🏷  MI DESCUENTO · {mes}" if getattr(self, "_vertical", False) else f"ESTE MES · {mes}")
        self.titulo_sigue.setText(f"PARA {av.nombre_mes_siguiente.upper()}")
        self.pct.setText(pct(av.pct_este_mes))
        if av.pct_este_mes > inc.TOPE_PCT_UNIFORME:
            self.detalle_pct.setText(f"de descuento en ropa\n{pct(inc.TOPE_PCT_UNIFORME)} en uniforme")
        elif av.pct_este_mes > inc.PCT_BASE:
            self.detalle_pct.setText("de descuento\nen lo que compres")
        else:
            self.detalle_pct.setText("de descuento\n(el de todas)")

        con_nivel = av.pct_este_mes > inc.PCT_BASE
        if con_nivel and av.tope and av.restante_este_mes is not None:
            self.quedan.setText(f"Te quedan {_dinero(av.restante_este_mes)} para comprar con tu {pct(av.pct_este_mes)}")
            self.barra_tope.setValue(int(1000 * min(float(av.usado / av.tope), 1.0)))
            self.barra_tope.setVisible(True)
            self.detalle_tope.setText(
                f"Llevas {_dinero(av.usado)} de {_dinero(av.tope)}. Lo que pase de ahí va con {pct(inc.PCT_BASE)}."
            )
        elif con_nivel:
            self.quedan.setText(f"Todo lo que compres va con tu {pct(av.pct_este_mes)}")
            self.barra_tope.setVisible(False)
            self.detalle_tope.setText("")
        else:
            self.quedan.setText("Vende más este mes y el que entra")
            self.barra_tope.setVisible(False)
            self.detalle_tope.setText("compras más barato.")
        self.detalle_tope.setVisible(bool(self.detalle_tope.text()))
        if av.ahorrado_mes > 0:
            self.ahorro.setText(f"💰 Te has ahorrado {_dinero(av.ahorrado_mes)} este mes")
        else:
            self.ahorro.setText("💰 Aún no compras este mes")

        self.avance.setText(frase_mes_siguiente(av))
        self.pista.poner(av.comisiones_mes, av.niveles)
        self.setVisible(True)
