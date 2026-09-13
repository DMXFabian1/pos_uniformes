"""Dibujar las líneas de conteo encima del cuadro de cada cámara.

Se abre desde afluencia\\dibujar_lineas.bat (que antes toma un cuadro fresco
de cada cámara con --calibrar). Daniel da un clic donde empieza la línea y otro
donde termina, dice de qué lado queda la tienda y guarda. El contador que
corre oculto ve que afluencia.json cambió y toma la línea nueva solo.

Corre con el Python del POS (tiene PyQt6); no toca el DVR ni el modelo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "afluencia.json"
CUADROS = AQUI / "calibracion" / "cuadros"

LADOS = (("arriba", "Arriba"), ("abajo", "Abajo"), ("izquierda", "Izquierda"), ("derecha", "Derecha"))
CAFE = "#6f331d"
CREMA = "#f5ebe0"
RADIO_AGARRE = 14  # px alrededor de un extremo para arrastrarlo


def sombra_dentro(x1: float, y1: float, x2: float, y2: float, lado: str) -> list[tuple[float, float]]:
    """Polígono (coordenadas 0..1) del lado de la tienda: la mitad del cuadro
    que queda del lado `lado` respecto a la línea, para pintarla en pantalla."""
    esquinas = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ref = {"abajo": (mx, my + 0.1), "arriba": (mx, my - 0.1), "izquierda": (mx - 0.1, my), "derecha": (mx + 0.1, my)}[lado]

    def cruz(x: float, y: float) -> float:
        return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)

    signo = 1 if cruz(*ref) >= 0 else -1
    # Recorte de Sutherland–Hodgman del cuadro contra la recta.
    dentro = lambda p: cruz(*p) * signo >= 0  # noqa: E731
    salida: list[tuple[float, float]] = []
    for i, p in enumerate(esquinas):
        q = esquinas[(i + 1) % 4]
        if dentro(p):
            salida.append(p)
        if dentro(p) != dentro(q):
            cp, cq = cruz(*p), cruz(*q)
            t = cp / (cp - cq)
            salida.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return salida


class Lienzo(QWidget):
    """El cuadro de la cámara con la línea encima; se dibuja con dos clics."""

    def __init__(self, al_cambiar) -> None:
        super().__init__()
        self.pix: QPixmap | None = None
        self.puntos: list[tuple[float, float]] = []
        self.lado = "abajo"
        self.arrastrando: int | None = None
        self.al_cambiar = al_cambiar
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)

    # --- geometría entre widget e imagen ---------------------------------------
    def _rect_imagen(self) -> QRectF:
        if self.pix is None:
            return QRectF(0, 0, self.width(), self.height())
        escala = min(self.width() / self.pix.width(), self.height() / self.pix.height())
        w, h = self.pix.width() * escala, self.pix.height() * escala
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _a_norm(self, p: QPointF) -> tuple[float, float]:
        r = self._rect_imagen()
        x = min(1.0, max(0.0, (p.x() - r.x()) / r.width()))
        y = min(1.0, max(0.0, (p.y() - r.y()) / r.height()))
        return round(x, 3), round(y, 3)

    def _a_widget(self, xy: tuple[float, float]) -> QPointF:
        r = self._rect_imagen()
        return QPointF(r.x() + xy[0] * r.width(), r.y() + xy[1] * r.height())

    # --- estado ------------------------------------------------------------------
    def cargar(self, pix: QPixmap | None, linea: list[float] | None, lado: str) -> None:
        self.pix = pix
        self.puntos = [(linea[0], linea[1]), (linea[2], linea[3])] if linea else []
        self.lado = lado
        self.arrastrando = None
        self.update()

    def linea(self) -> list[float] | None:
        if len(self.puntos) != 2 or self.puntos[0] == self.puntos[1]:
            return None
        (x1, y1), (x2, y2) = self.puntos
        return [x1, y1, x2, y2]

    def poner_lado(self, lado: str) -> None:
        self.lado = lado
        self.update()

    # --- ratón -------------------------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self.pix is None or e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position()
        for i, p in enumerate(self.puntos):
            if (self._a_widget(p) - pos).manhattanLength() <= RADIO_AGARRE:
                self.arrastrando = i
                return
        if len(self.puntos) >= 2:
            self.puntos = []
        self.puntos.append(self._a_norm(pos))
        self.arrastrando = len(self.puntos) - 1
        self.update()
        self.al_cambiar()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self.arrastrando is None:
            return
        self.puntos[self.arrastrando] = self._a_norm(e.position())
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self.arrastrando is not None:
            self.arrastrando = None
            self.al_cambiar()

    # --- pintura -----------------------------------------------------------------
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#2b2b2b"))
        if self.pix is None:
            p.setPen(QColor("white"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin cuadro de esta cámara.\nCierra y vuelve a abrir dibujar_lineas.bat con el DVR prendido.")
            return
        r = self._rect_imagen()
        p.drawPixmap(r.toRect(), self.pix)
        linea = self.linea()
        if linea:
            poligono = QPolygonF([self._a_widget(xy) for xy in sombra_dentro(*linea, self.lado)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(60, 200, 90, 70)))
            p.drawPolygon(poligono)
            a, b = self._a_widget(self.puntos[0]), self._a_widget(self.puntos[1])
            p.setPen(QPen(QColor("#e53935"), 5))
            p.drawLine(a, b)
        for i, xy in enumerate(self.puntos):
            c = self._a_widget(xy)
            p.setPen(QPen(QColor("white"), 2))
            p.setBrush(QBrush(QColor("#e53935")))
            p.drawEllipse(c, 8, 8)
            p.setPen(QColor("white"))
            p.drawText(QRectF(c.x() + 10, c.y() - 22, 60, 20), Qt.AlignmentFlag.AlignLeft, "inicio" if i == 0 else "fin")


class VentanaLineas(QMainWindow):
    def __init__(self, config: Path = CONFIG, cuadros: Path = CUADROS) -> None:
        super().__init__()
        self.setWindowTitle("Líneas de afluencia")
        self.config = config
        self.cuadros = cuadros
        self.cfg = json.loads(config.read_text(encoding="utf-8"))
        self.camaras = [c for c in self.cfg["camaras"] if c.get("modo", "linea") == "linea"]
        self.actual: dict | None = None

        self.lista = QListWidget()
        self.lista.setFixedWidth(180)
        for cam in self.camaras:
            self.lista.addItem(cam["nombre"])
        self.lista.currentRowChanged.connect(self._elegir)

        self.lienzo = Lienzo(self._linea_cambio)

        self.ayuda = QLabel("1 · Clic donde EMPIEZA la línea   2 · Clic donde TERMINA   3 · Di de qué lado queda la tienda   4 · Guardar")
        self.ayuda.setWordWrap(True)
        self.estado = QLabel("")

        lados = QHBoxLayout()
        lados.addWidget(QLabel("La parte VERDE es la tienda. Queda:"))
        self.grupo = QButtonGroup(self)
        self.radios: dict[str, QRadioButton] = {}
        for clave, texto in LADOS:
            rb = QRadioButton(texto)
            self.radios[clave] = rb
            self.grupo.addButton(rb)
            lados.addWidget(rb)
            rb.toggled.connect(lambda on, k=clave: on and self._lado_cambio(k))
        lados.addStretch()
        self.guardar = QPushButton("Guardar")
        self.guardar.setMinimumHeight(40)
        self.guardar.clicked.connect(self._guardar)
        lados.addWidget(self.guardar)

        derecha = QVBoxLayout()
        derecha.addWidget(self.ayuda)
        derecha.addWidget(self.lienzo, 1)
        derecha.addLayout(lados)
        derecha.addWidget(self.estado)

        raiz = QHBoxLayout()
        raiz.addWidget(self.lista)
        raiz.addLayout(derecha, 1)
        w = QWidget()
        w.setLayout(raiz)
        self.setCentralWidget(w)
        self.setStyleSheet(
            f"QMainWindow, QWidget {{ background: {CREMA}; color: {CAFE}; font-size: 14px; }}"
            f"QListWidget {{ background: white; font-size: 16px; }}"
            f"QListWidget::item:selected {{ background: {CAFE}; color: white; }}"
            f"QPushButton {{ background: {CAFE}; color: white; font-weight: bold; padding: 6px 18px; border-radius: 6px; }}"
            f"QPushButton:disabled {{ background: #b9a89b; }}"
        )
        self.resize(1180, 760)
        if self.camaras:
            self.lista.setCurrentRow(0)

    def _elegir(self, fila: int) -> None:
        if fila < 0:
            return
        self.actual = self.camaras[fila]
        ruta = self.cuadros / f"{self.actual['nombre']}.jpg"
        pix = QPixmap(str(ruta)) if ruta.exists() else None
        lado = self.actual.get("lado_dentro", "abajo")
        self.lienzo.cargar(pix, self.actual.get("linea"), lado)
        self.radios[lado].setChecked(True)
        self._linea_cambio()

    def _linea_cambio(self) -> None:
        linea = self.lienzo.linea()
        if self.actual is not None and linea:
            self.actual["linea"] = linea
        a_medias = len(self.lienzo.puntos) == 1  # con un solo clic no hay línea que guardar
        self.guardar.setEnabled(not a_medias and all(c.get("linea") and c["linea"][:2] != c["linea"][2:] for c in self.camaras))
        if linea:
            self.estado.setText(f"{self.actual['nombre']}: de ({linea[0]}, {linea[1]}) a ({linea[2]}, {linea[3]}) · tienda {self.lienzo.lado}. Sin guardar.")
        else:
            self.estado.setText("Falta el segundo clic.")

    def _lado_cambio(self, lado: str) -> None:
        if self.actual is not None:
            self.actual["lado_dentro"] = lado
        self.lienzo.poner_lado(lado)
        self._linea_cambio()

    def _guardar(self) -> None:
        self.config.write_text(json.dumps(self.cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.estado.setText("Guardado. El contador toma las líneas nuevas en unos segundos, no hay que reiniciar nada.")
        QMessageBox.information(self, "Líneas guardadas", "Listo. El contador ya cuenta con las líneas nuevas.")


def main() -> int:
    app = QApplication(sys.argv)
    if not CONFIG.exists():
        QMessageBox.critical(None, "Falta afluencia.json", "Primero corre afluencia\\instalar_afluencia.bat")
        return 1
    v = VentanaLineas()
    v.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
