"""Tipos de escocés como catálogo del programa, no como PDF (2026-11-07).

Daniel: «hay que mejorar la visualización y funciones dentro de tipos de
escocés». El PDF de dos hojas se veía chiquito, no se podía buscar ni
acercarse a una tela, y para decirle a alguien cuál era había que leer el
código en la hoja.

Ahora (Ctrl+Shift+E en kiosko y POS):
- Las 37 telas en una cuadrícula, con chips por familia (Marinos, Rojos…) y
  un buscador: «12», «verde», «stewart», «gales».
- Al tocar una: la muestra grande a la derecha con su código, nombre,
  familia y tartán oficial (si tiene), las otras de su familia para
  comparar, ‹ › para recorrerlas; tocar la foto (o doble clic / Enter en
  la cuadrícula) la abre a pantalla completa.
- 📋 Copiar código y 🖨 Imprimir ficha (código, foto y nombre en una hoja).
- «📄 Hoja completa» abre el PDF de antes, para imprimir el resumen.

Los datos salen de `assets/catalogos/escoces/escoces.json` y sus fotos (los
prepara `scripts/preparar_catalogo_escoces.py`).
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.dialogs.visor_consulta_dialog import _ABIERTAS, _Visor

VINO = "#6b1f3a"
VERDE = "#2f7d4f"
GRIS = "#7a6f63"

CARPETA = Path(__file__).resolve().parents[2] / "assets" / "catalogos" / "escoces"

_ESTILO = f"""
QWidget#cuerpoEscoces {{ background: #f6f0e6; }}
QLineEdit#buscaEscoces {{
    font-size: 15px; padding: 9px 12px; border-radius: 10px;
    border: 1px solid #ddd0c0; background: white; color: #2c2a27;
}}
QLineEdit#buscaEscoces:focus {{ border-color: {VINO}; }}
QPushButton#chipFamilia {{
    font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 14px;
    background: #fbf7f1; color: #5a4636; border: 1px solid #ddd0c0; min-height: 0px;
}}
QPushButton#chipFamilia:hover {{ background: #f1e6d6; }}
QPushButton#chipFamilia:checked {{ background: {VINO}; color: white; border-color: {VINO}; }}
QListWidget#rejillaEscoces {{
    background: transparent; border: none; outline: none;
}}
QListWidget#rejillaEscoces::item {{
    background: white; border: 1px solid #e6dccd; border-radius: 12px;
    color: #2c2a27; padding: 4px; margin: 3px;
}}
QListWidget#rejillaEscoces::item:hover {{ border-color: #c9b59c; }}
QListWidget#rejillaEscoces::item:selected {{
    background: #f7e9ee; border: 2px solid {VINO}; color: #2c2a27;
}}
QFrame#fichaEscoces {{
    background: white; border: 1px solid #e6dccd; border-radius: 16px;
}}
QFrame#fichaEscoces QLabel {{ background: transparent; border: none; }}
QLabel#codigoEscoces {{ font-size: 34px; font-weight: 800; color: {VINO}; }}
QLabel#nombreEscoces {{ font-size: 18px; font-weight: 700; color: #2c2a27; }}
QLabel#familiaEscoces {{ font-size: 13px; color: {GRIS}; }}
QLabel#tartanEscoces {{ font-size: 14px; font-weight: 700; color: {VERDE}; }}
QLabel#vacioEscoces {{ font-size: 15px; color: {GRIS}; }}
QFrame#fichaEscoces QPushButton {{
    font-size: 13px; font-weight: 700; padding: 8px 12px; border-radius: 10px;
    background: #fbf7f1; color: #73341c; border: 1px solid #ddd0c0; min-height: 0px;
}}
QFrame#fichaEscoces QPushButton:hover {{ background: #f1e6d6; }}
QFrame#fichaEscoces QPushButton:disabled {{ color: #c4b8a8; }}
"""


@dataclass(frozen=True)
class Tela:
    codigo: str
    familia: str
    nombre: str
    tartan: str
    foto: Path

    @property
    def numero(self) -> int:
        try:
            return int(self.codigo.split("-")[-1])
        except ValueError:
            return 0


def cargar_telas(carpeta: Path = CARPETA) -> list[Tela]:
    datos = json.loads((carpeta / "escoces.json").read_text(encoding="utf-8"))
    return [
        Tela(t["codigo"], t.get("familia", ""), t.get("nombre", ""), t.get("tartan", ""), carpeta / t["foto"])
        for t in datos.get("telas", [])
    ]


def hay_catalogo(carpeta: Path = CARPETA) -> bool:
    return (carpeta / "escoces.json").is_file()


def _plano(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn"
    )


def filtrar(telas: list[Tela], texto: str = "", familia: str = "") -> list[Tela]:
    """«12» o «esc-12» = esa tela; si no, cada palabra tiene que estar en el
    código, el nombre, la familia o el tartán (sin acentos ni mayúsculas)."""
    quedan = [t for t in telas if not familia or t.familia == familia]
    buscado = _plano(texto).strip()
    if not buscado:
        return quedan
    numero = buscado.replace("esc", "").replace("-", "").strip()
    if numero.isdigit():
        return [t for t in quedan if t.numero == int(numero)]
    palabras = buscado.split()
    return [
        t for t in quedan
        if all(p in _plano(f"{t.codigo} {t.nombre} {t.familia} {t.tartan}") for p in palabras)
    ]


def familias(telas: list[Tela]) -> list[tuple[str, int]]:
    vistas: dict[str, int] = {}
    for t in telas:
        vistas[t.familia] = vistas.get(t.familia, 0) + 1
    return list(vistas.items())


class _Ampliada(QDialog):
    """La tela a casi toda la pantalla, para ver el dibujo de cerca."""

    def __init__(self, tela: Tela, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{tela.codigo} · {tela.nombre}")
        self.setStyleSheet("QDialog { background: #1d1a17; } QLabel { color: white; }")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(16, 12, 16, 16)
        titulo = QLabel(f"<b style='font-size:20px'>{tela.codigo}</b>&nbsp;&nbsp;"
                        f"<span style='font-size:16px'>{tela.nombre}</span>"
                        "<span style='color:#aaa'>&nbsp;&nbsp;·&nbsp;&nbsp;toca o Esc para cerrar</span>")
        caja.addWidget(titulo)
        pantalla = (parent.screen() if parent else None) or QApplication.primaryScreen()
        lado = 900
        if pantalla is not None:
            area = pantalla.availableGeometry()
            lado = int(min(area.width(), area.height()) * 0.82)
        foto = QLabel()
        foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = QPixmap(str(tela.foto))
        if not px.isNull():
            foto.setPixmap(px.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        caja.addWidget(foto, 1)
        QShortcut(QKeySequence("Esc"), self, activated=self.close)

    def mousePressEvent(self, _evento) -> None:  # noqa: N802
        self.close()


class VisorEscoces(_Visor):
    clave = "escoces"

    def __init__(self, parent: QWidget | None = None, carpeta: Path = CARPETA) -> None:
        super().__init__("🧵 Tipos de escocés", parent)
        self.carpeta = Path(carpeta)
        self.telas = cargar_telas(self.carpeta)
        self.familia = ""
        self.actual: Tela | None = None
        self.detalle.setText(f"{len(self.telas)} telas")
        self._iconos: dict[str, QIcon] = {}

        pdf = self.carpeta.parent / "Tipos_de_Escoces.pdf"
        if pdf.is_file():
            self.boton("📄 Hoja completa", lambda: self._abrir_pdf(pdf))

        cuerpo = QWidget(objectName="cuerpoEscoces")
        cuerpo.setStyleSheet(_ESTILO)
        fila = QHBoxLayout(cuerpo)
        fila.setContentsMargins(18, 16, 18, 18)
        fila.setSpacing(18)
        self.cuerpo.addWidget(cuerpo)

        # ── Izquierda: buscar, familias, cuadrícula ──────────────────────
        izquierda = QVBoxLayout()
        izquierda.setSpacing(10)
        self.busca = QLineEdit(objectName="buscaEscoces")
        self.busca.setPlaceholderText("Buscar: número, color o nombre  (12 · verde · stewart · gales)")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._refrescar)
        izquierda.addWidget(self.busca)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chips: dict[str, QPushButton] = {}
        for familia, cuantas in [("", len(self.telas))] + familias(self.telas):
            chip = QPushButton(f"{familia or 'Todas'}  {cuantas}", objectName="chipFamilia")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, f=familia: self._elegir_familia(f))
            chips.addWidget(chip)
            self.chips[familia] = chip
        chips.addStretch(1)
        izquierda.addLayout(chips)

        self.rejilla = QListWidget(objectName="rejillaEscoces")
        self.rejilla.setViewMode(QListWidget.ViewMode.IconMode)
        self.rejilla.setIconSize(QSize(136, 136))
        self.rejilla.setGridSize(QSize(190, 226))
        self.rejilla.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.rejilla.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.rejilla.setMovement(QListWidget.Movement.Static)
        self.rejilla.setUniformItemSizes(True)
        self.rejilla.setWordWrap(True)
        self.rejilla.setSpacing(4)
        self.rejilla.currentItemChanged.connect(self._al_elegir)
        self.rejilla.itemActivated.connect(lambda _i: self.ver_en_grande())
        izquierda.addWidget(self.rejilla, 1)
        self.vacio = QLabel("", objectName="vacioEscoces")
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio.hide()
        izquierda.addWidget(self.vacio, 1)
        fila.addLayout(izquierda, 1)

        # ── Derecha: la ficha de la tela elegida ─────────────────────────
        ficha = self.ficha = QFrame(objectName="fichaEscoces")
        ficha.setFixedWidth(420)
        caja = QVBoxLayout(ficha)
        caja.setContentsMargins(20, 20, 20, 18)
        caja.setSpacing(6)
        self.foto = QLabel()
        self.foto.setFixedSize(380, 380)
        self.foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.foto.setToolTip("Ver en grande")
        self.foto.mousePressEvent = lambda _e: self.ver_en_grande()  # type: ignore[assignment]
        caja.addWidget(self.foto, 0, Qt.AlignmentFlag.AlignHCenter)
        pista = QLabel("Toca la foto para verla en grande", objectName="familiaEscoces")
        pista.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        caja.addWidget(pista)
        caja.addSpacing(4)
        self.codigo = QLabel("", objectName="codigoEscoces")
        self.nombre = QLabel("", objectName="nombreEscoces")
        self.nombre.setWordWrap(True)
        self.familia_lbl = QLabel("", objectName="familiaEscoces")
        self.tartan = QLabel("", objectName="tartanEscoces")
        self.tartan.setWordWrap(True)
        for w in (self.codigo, self.nombre, self.familia_lbl, self.tartan):
            caja.addWidget(w)
        caja.addSpacing(8)
        # Las parecidas: las otras de su familia, para comparar de un toque.
        self.parecidas_lbl = QLabel("", objectName="familiaEscoces")
        caja.addWidget(self.parecidas_lbl)
        self.parecidas = QHBoxLayout()
        self.parecidas.setSpacing(6)
        caja.addLayout(self.parecidas)
        caja.addStretch(1)

        navegar = QHBoxLayout()
        self.anterior = QPushButton("‹ Anterior")
        self.siguiente = QPushButton("Siguiente ›")
        self.anterior.clicked.connect(lambda: self._mover(-1))
        self.siguiente.clicked.connect(lambda: self._mover(1))
        navegar.addWidget(self.anterior)
        navegar.addWidget(self.siguiente)
        caja.addLayout(navegar)
        acciones = QHBoxLayout()
        self.copiar = QPushButton("📋 Copiar código")
        self.copiar.clicked.connect(self.copiar_codigo)
        imprimir = QPushButton("🖨 Imprimir ficha")
        imprimir.clicked.connect(self.imprimir_ficha)
        for b in (self.copiar, imprimir):
            acciones.addWidget(b)
        caja.addLayout(acciones)
        fila.addWidget(ficha)

        self._reloj_copiado = QTimer(self)
        self._reloj_copiado.setSingleShot(True)
        self._reloj_copiado.timeout.connect(lambda: self.copiar.setText("📋 Copiar código"))

        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.busca.setFocus)
        QShortcut(QKeySequence("Ctrl+C"), self.rejilla, activated=self.copiar_codigo)

        self.chips[""].setChecked(True)
        self._refrescar()
        self.busca.setFocus()

    # ── datos → pantalla ─────────────────────────────────────────────────
    def _icono(self, tela: Tela) -> QIcon:
        if tela.codigo not in self._iconos:
            px = QPixmap(str(tela.foto))
            if not px.isNull():
                px = px.scaled(272, 272, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
            self._iconos[tela.codigo] = QIcon(px)
        return self._iconos[tela.codigo]

    def visibles(self) -> list[Tela]:
        return filtrar(self.telas, self.busca.text(), self.familia)

    def _refrescar(self) -> None:
        elegida = self.actual.codigo if self.actual else None
        telas = self.visibles()
        self.rejilla.blockSignals(True)
        self.rejilla.clear()
        for t in telas:
            item = QListWidgetItem(self._icono(t), f"{t.codigo}\n{t.nombre}")
            item.setData(Qt.ItemDataRole.UserRole, t.codigo)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            # Alto fijo para tres renglones: con el alto que calcula Qt, un
            # nombre largo se cortaba con «…» («azul-blanco … oscuro»).
            item.setSizeHint(QSize(180, 218))
            item.setToolTip(f"{t.codigo} · {t.nombre}" + (f" · {t.tartan}" if t.tartan else ""))
            self.rejilla.addItem(item)
        self.rejilla.blockSignals(False)
        self.rejilla.setVisible(bool(telas))
        self.vacio.setVisible(not telas)
        self.ficha.setVisible(bool(telas))
        if not telas:
            self.vacio.setText(f"No hay telas con «{self.busca.text().strip()}»"
                               + (f" en {self.familia}" if self.familia else "") + ".")
        codigos = [t.codigo for t in telas]
        fila = codigos.index(elegida) if elegida in codigos else 0
        if telas:
            self.rejilla.setCurrentRow(fila)
            self._mostrar(telas[fila])
        self._botones_navegar()

    def _elegir_familia(self, familia: str) -> None:
        self.familia = familia
        for f, chip in self.chips.items():
            chip.setChecked(f == familia)
        self._refrescar()

    def _al_elegir(self, item, _anterior=None) -> None:
        if item is None:
            return
        codigo = item.data(Qt.ItemDataRole.UserRole)
        tela = next((t for t in self.telas if t.codigo == codigo), None)
        if tela is not None:
            self._mostrar(tela)
        self._botones_navegar()

    def _mostrar(self, tela: Tela) -> None:
        self.actual = tela
        px = QPixmap(str(tela.foto))
        if not px.isNull():
            self.foto.setPixmap(px.scaled(380, 380, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation))
        self.codigo.setText(tela.codigo)
        self.nombre.setText(tela.nombre)
        self.familia_lbl.setText(f"Familia: {tela.familia}")
        self.tartan.setText(f"Tartán: {tela.tartan}" if tela.tartan else "")
        self.tartan.setVisible(bool(tela.tartan))
        self._poner_parecidas(tela)

    def _poner_parecidas(self, tela: Tela) -> None:
        while self.parecidas.count():
            w = self.parecidas.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        otras = [t for t in self.telas if t.familia == tela.familia and t.codigo != tela.codigo][:6]
        self.parecidas_lbl.setText(f"Otras {tela.familia.lower()}:" if otras else "")
        for t in otras:
            b = QPushButton()
            b.setFixedSize(54, 54)
            b.setIcon(self._icono(t))
            b.setIconSize(QSize(48, 48))
            b.setToolTip(f"{t.codigo} · {t.nombre}")
            b.setStyleSheet("QPushButton { padding: 0px; border-radius: 8px; background: white; }")
            b.clicked.connect(lambda _=False, c=t.codigo: self.ir_a(c))
            self.parecidas.addWidget(b)
        self.parecidas.addStretch(1)

    def ir_a(self, codigo: str) -> None:
        """Elige esa tela; si el filtro la esconde, se quita el filtro."""
        for fila in range(self.rejilla.count()):
            if self.rejilla.item(fila).data(Qt.ItemDataRole.UserRole) == codigo:
                self.rejilla.setCurrentRow(fila)
                return
        self.actual = next((t for t in self.telas if t.codigo == codigo), self.actual)
        self.busca.blockSignals(True)
        self.busca.clear()
        self.busca.blockSignals(False)
        self._elegir_familia("")

    def _botones_navegar(self) -> None:
        fila, total = self.rejilla.currentRow(), self.rejilla.count()
        self.anterior.setEnabled(fila > 0)
        self.siguiente.setEnabled(0 <= fila < total - 1)

    def _mover(self, paso: int) -> None:
        fila = self.rejilla.currentRow() + paso
        if 0 <= fila < self.rejilla.count():
            self.rejilla.setCurrentRow(fila)

    # ── acciones ─────────────────────────────────────────────────────────
    def copiar_codigo(self) -> None:
        if self.actual is None:
            return
        QApplication.clipboard().setText(self.actual.codigo)
        self.copiar.setText(f"✓ {self.actual.codigo} copiado")
        self._reloj_copiado.start(1600)

    def ver_en_grande(self) -> None:
        if self.actual is not None:
            _Ampliada(self.actual, self).exec()

    def pintar_ficha(self, pintor: QPainter, ancho: int, alto: int) -> None:
        """La ficha en una hoja: código grande, la muestra y su nombre."""
        tela = self.actual
        if tela is None:
            return
        margen = int(ancho * 0.07)
        y = margen
        fuente = QFont()
        fuente.setBold(True)
        fuente.setPixelSize(int(ancho * 0.11))
        pintor.setFont(fuente)
        pintor.setPen(QColor(VINO))
        alto_codigo = int(ancho * 0.14)
        pintor.drawText(margen, y, ancho - 2 * margen, alto_codigo, Qt.AlignmentFlag.AlignCenter, tela.codigo)
        y += alto_codigo + int(ancho * 0.02)
        lado = min(ancho - 2 * margen, int(alto * 0.55))
        px = QPixmap(str(tela.foto))
        if not px.isNull():
            px = px.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
            pintor.drawPixmap((ancho - lado) // 2, y, px, 0, 0, lado, lado)
        y += lado + int(ancho * 0.04)
        fuente.setPixelSize(int(ancho * 0.06))
        pintor.setFont(fuente)
        pintor.setPen(QColor("#2c2a27"))
        pintor.drawText(margen, y, ancho - 2 * margen, int(ancho * 0.16),
                        Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, tela.nombre)
        y += int(ancho * 0.17)
        if tela.tartan:
            fuente.setPixelSize(int(ancho * 0.045))
            pintor.setFont(fuente)
            pintor.setPen(QColor(VERDE))
            pintor.drawText(margen, y, ancho - 2 * margen, int(ancho * 0.08), Qt.AlignmentFlag.AlignHCenter,
                            f"Tartán: {tela.tartan}")

    def imprimir_ficha(self) -> None:
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        if self.actual is None:
            return
        impresora = QPrinter(QPrinter.PrinterMode.HighResolution)
        if QPrintDialog(impresora, self).exec() != QDialog.DialogCode.Accepted:
            return
        pintor = QPainter(impresora)
        try:
            area = impresora.pageLayout().paintRectPixels(impresora.resolution())
            self.pintar_ficha(pintor, area.width(), area.height())
        finally:
            pintor.end()

    def _abrir_pdf(self, pdf: Path) -> None:
        from pos_uniformes.ui.dialogs.visor_consulta_dialog import mostrar_pdf

        mostrar_pdf(pdf, "🧵 Tipos de escocés — hoja completa", self)


def mostrar_escoces(parent: QWidget | None = None, carpeta: Path = CARPETA) -> VisorEscoces:
    ya = _ABIERTAS.get(VisorEscoces.clave)
    if ya is not None:
        ya.traer_al_frente()
        return ya
    visor = VisorEscoces(parent, carpeta)
    _ABIERTAS[VisorEscoces.clave] = visor
    visor.show()
    return visor
