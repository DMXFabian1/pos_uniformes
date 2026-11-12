"""La tarjeta de su descuento en la Libreta de cada empleada (Daniel, 2026-11-12).

«Para que ellas vean qué tanto descuento se van a llevar.» En vez del renglón
de texto: con qué % compra este mes y cuánto le queda del tope, lo que se ha
ahorrado, su avance en comisiones hacia el siguiente nivel y la escalera de
niveles con el que ya alcanzó para el mes que entra.
"""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from pos_uniformes.services import incentivo_empleada_service as inc

CREMA = "#f4ede2"
TARJETA = "#fffdf9"
BORDE = "#e6dccd"
TINTA = "#2c2a27"
GRIS = "#8a7a68"
CAFE = "#73341c"
VINO = "#6b1f3a"
VERDE = "#2f5d3a"


def _etiqueta(texto: str, estilo: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"background: transparent; {estilo}")
    return lbl


def _barra(color: str, alto: int = 12) -> QProgressBar:
    barra = QProgressBar()
    barra.setRange(0, 1000)
    barra.setTextVisible(False)
    barra.setFixedHeight(alto)
    barra.setStyleSheet(
        f"QProgressBar {{ background: #efe6d8; border: none; border-radius: {alto // 2}px; }}"
        f"QProgressBar::chunk {{ background: {color}; border-radius: {alto // 2}px; }}"
    )
    return barra


def _dinero(valor) -> str:
    return f"${Decimal(str(valor)):,.2f}"


class NivelEmpleadaTarjeta(QFrame):
    """`mostrar(avance)` la llena; `mostrar(None)` la esconde."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("nivelEmpleada")
        self.setStyleSheet(
            f"QFrame#nivelEmpleada {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 16px; }}"
        )
        ly = QHBoxLayout(self)
        ly.setContentsMargins(18, 14, 18, 14)
        ly.setSpacing(22)

        # ── Hoy: su % grande ──
        hoy = QVBoxLayout()
        hoy.setSpacing(2)
        self.titulo = _etiqueta("", f"color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
        hoy.addWidget(self.titulo)
        self.pct = _etiqueta("", f"color: {VINO}; font-size: 40px; font-weight: 900;")
        hoy.addWidget(self.pct)
        self.detalle_pct = _etiqueta("", f"color: {TINTA}; font-size: 13px;")
        hoy.addWidget(self.detalle_pct)
        hoy.addStretch(1)
        ly.addLayout(hoy)

        # ── Su tope y lo ahorrado ──
        dinero = QVBoxLayout()
        dinero.setSpacing(6)
        self.quedan = _etiqueta("", f"color: {TINTA}; font-size: 15px; font-weight: 700;")
        dinero.addWidget(self.quedan)
        self.barra_tope = _barra(VINO)
        dinero.addWidget(self.barra_tope)
        self.detalle_tope = _etiqueta("", f"color: {GRIS}; font-size: 12px;")
        dinero.addWidget(self.detalle_tope)
        self.ahorro = QLabel("")
        self.ahorro.setStyleSheet(
            f"background: #eef2ea; color: {VERDE}; border-radius: 11px; padding: 5px 12px; font-size: 14px; font-weight: 800;"
        )
        fila_ahorro = QHBoxLayout()
        fila_ahorro.addWidget(self.ahorro)
        fila_ahorro.addStretch(1)
        dinero.addLayout(fila_ahorro)
        dinero.addStretch(1)
        ly.addLayout(dinero, 1)

        # ── El mes que entra: avance y escalera ──
        sigue = QVBoxLayout()
        sigue.setSpacing(6)
        self.avance = _etiqueta("", f"color: {TINTA}; font-size: 15px; font-weight: 700;")
        self.avance.setWordWrap(True)
        sigue.addWidget(self.avance)
        self.barra_avance = _barra(CAFE)
        sigue.addWidget(self.barra_avance)
        self.escalera = QWidget()
        self.escalera.setStyleSheet("background: transparent;")
        self._escalera_ly = QHBoxLayout(self.escalera)
        self._escalera_ly.setContentsMargins(0, 2, 0, 0)
        self._escalera_ly.setSpacing(6)
        sigue.addWidget(self.escalera)
        sigue.addStretch(1)
        ly.addLayout(sigue, 1)

        self.setVisible(False)

    def mostrar(self, av: inc.AvanceEmpleada | None) -> None:
        if av is None:
            self.setVisible(False)
            return
        mes = av.nombre_mes or "este mes"
        self.titulo.setText(f"TU DESCUENTO EN {mes.upper()}")
        self.pct.setText(inc.fmt_pct(av.pct_este_mes))
        if av.pct_este_mes > inc.TOPE_PCT_UNIFORME:
            self.detalle_pct.setText(f"en ropa · {inc.fmt_pct(inc.TOPE_PCT_UNIFORME)} en uniforme")
        elif av.pct_este_mes > inc.PCT_BASE:
            self.detalle_pct.setText("en lo que compres")
        else:
            self.detalle_pct.setText("el de todas")

        # Tope: solo cuenta si compra con nivel (arriba del base).
        con_nivel = av.pct_este_mes > inc.PCT_BASE
        if con_nivel and av.tope is not None and av.restante_este_mes is not None:
            self.quedan.setText(f"Te quedan {_dinero(av.restante_este_mes)} con tu {inc.fmt_pct(av.pct_este_mes)}")
            self.barra_tope.setValue(int(1000 * min(float(av.usado / av.tope), 1.0)) if av.tope else 0)
            self.detalle_tope.setText(
                f"Llevas {_dinero(av.usado)} de {_dinero(av.tope)}; lo que pase del tope va con {inc.fmt_pct(inc.PCT_BASE)}"
            )
            self.barra_tope.setVisible(True)
            self.detalle_tope.setVisible(True)
        elif con_nivel:
            self.quedan.setText(f"Sin tope: todo con tu {inc.fmt_pct(av.pct_este_mes)}")
            self.barra_tope.setVisible(False)
            self.detalle_tope.setVisible(False)
        else:
            self.quedan.setText(f"Compras con el {inc.fmt_pct(inc.PCT_BASE)} de siempre")
            self.barra_tope.setVisible(False)
            self.detalle_tope.setText("Vende más este mes y el que entra compras más barato")
            self.detalle_tope.setVisible(True)
        if av.ahorrado_mes > 0:
            self.ahorro.setText(f"💰 Te has ahorrado {_dinero(av.ahorrado_mes)} este mes")
        else:
            self.ahorro.setText("💰 Aún no compras este mes")

        siguiente_mes = av.nombre_mes_siguiente
        if av.siguiente is None:
            self.avance.setText(
                f"Vas en {av.comisiones_mes} comisiones: en {siguiente_mes} compras con el máximo, "
                f"{inc.fmt_pct(av.pct_mes_siguiente)} 🎉"
            )
        else:
            self.avance.setText(
                f"Vas en {av.comisiones_mes} comisiones: te faltan {av.faltan} para comprar con "
                f"{inc.fmt_pct(av.siguiente.porcentaje)} en {siguiente_mes}"
            )
        self.barra_avance.setValue(int(1000 * av.progreso))
        self._pintar_escalera(av)
        self.setVisible(True)

    def _pintar_escalera(self, av: inc.AvanceEmpleada) -> None:
        while self._escalera_ly.count():
            hijo = self._escalera_ly.takeAt(0).widget()
            if hijo is not None:
                hijo.setParent(None)
                hijo.deleteLater()
        self.peldanos: list[QLabel] = []
        for n in av.niveles:
            ganado = av.comisiones_mes >= n.comisiones_minimas
            actual = Decimal(str(n.porcentaje)) == Decimal(str(av.pct_mes_siguiente))
            if actual:
                fondo, color, borde = VINO, "#ffffff", VINO
            elif ganado:
                fondo, color, borde = "#f1e3e8", VINO, "#e0c3cd"
            else:
                fondo, color, borde = "#ffffff", GRIS, BORDE
            peldano = QLabel(f"{inc.fmt_pct(n.porcentaje)}\n{n.comisiones_minimas}+")
            peldano.setAlignment(Qt.AlignmentFlag.AlignCenter)
            peldano.setToolTip(f"{n.comisiones_minimas} comisiones o más en el mes → {inc.fmt_pct(n.porcentaje)} el siguiente")
            peldano.setStyleSheet(
                f"background: {fondo}; color: {color}; border: 1.5px solid {borde}; border-radius: 10px;"
                " padding: 3px 8px; font-size: 12px; font-weight: 800;"
            )
            self._escalera_ly.addWidget(peldano)
            self.peldanos.append(peldano)
        self._escalera_ly.addStretch(1)
