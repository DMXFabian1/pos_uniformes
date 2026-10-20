"""La Ropa del kiosko como en una tienda en línea: fichas arriba, cuadrícula con fotos.

Daniel (2026-10-20): *«más visual o intuitivo… como Adidas o Nike… que no se haga
lento»*. Lo que se copia de esas tiendas: la foto manda (3:4), debajo solo
nombre, marca·color y precio; los filtros son fichas que se prenden y apagan,
no pasos numerados. Lo que no: carruseles ni animaciones.

Rápido a propósito:
- Las fotos se leen del disco del kiosko (`foto_local_cache_service`), nunca
  de la base, y pasan por `QPixmapCache` con un tope fijo de memoria.
- Se pinta por páginas de `POR_PAGINA` tarjetas: con 300 modelos no se crean
  300 widgets.
- Sin foto, la tarjeta enseña la inicial sobre un fondo neutro; nunca espera.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPixmapCache
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

POR_PAGINA = 24
COLUMNAS = 4
ANCHO_TARJETA = 228
ALTO_FOTO = 300           # 3:4 sobre 228 de ancho (menos márgenes)
#: Tope de memoria para miniaturas ya decodificadas (en KB). 64 MB ≈ 600 fotos.
TOPE_CACHE_KB = 64 * 1024

_ESTILO = """
QFrame#ropaTarjeta { background: #ffffff; border: 1px solid #e8dccd; border-radius: 14px; }
QFrame#ropaTarjeta[elegida="true"] { border: 2px solid #a84f2d; }
QLabel#ropaFoto { background: #f4ede2; border-radius: 10px; color: #b5aa9c; font-size: 48px; font-weight: 800; }
QLabel#ropaTitulo { color: #2c2a27; font-size: 14px; font-weight: 700; }
QLabel#ropaSub { color: #8a8177; font-size: 12px; }
QLabel#ropaPrecio { color: #73341c; font-size: 15px; font-weight: 800; }
QPushButton#ficha { background: #ffffff; color: #2c2a27; border: 1px solid #ddd0c0; border-radius: 17px;
                    min-height: 34px; padding: 0 14px; font-size: 13px; font-weight: 600; }
QPushButton#ficha:checked { background: #a84f2d; color: #ffffff; border-color: #a84f2d; }
QPushButton#ficha:disabled { color: #c4b9ab; }
QLabel#ropaGrupo { color: #8a8177; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QPushButton#ropaPagina { background: #f8f2e9; color: #73341c; border: 1px solid #ddd0c0; border-radius: 10px;
                         min-height: 34px; padding: 0 14px; font-weight: 700; }
"""

QPixmapCache.setCacheLimit(TOPE_CACHE_KB)


def pixmap_de_miniatura(foto_hash: str, ancho: int, alto: int) -> QPixmap | None:
    """La miniatura escalada, de la caché de memoria o del disco. None si no hay."""
    if not foto_hash:
        return None
    clave = f"ropa:{foto_hash}:{ancho}x{alto}"
    cached = QPixmapCache.find(clave)
    if cached is not None and not cached.isNull():
        return cached
    from pos_uniformes.services.foto_local_cache_service import ruta_miniatura

    ruta = ruta_miniatura(foto_hash)
    if ruta is None:
        return None
    pixmap = QPixmap(str(ruta))
    if pixmap.isNull():
        return None
    escalada = pixmap.scaled(ancho, alto, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
    QPixmapCache.insert(clave, escalada)
    return escalada


class _Tarjeta(QFrame):
    """Una tarjeta: foto, nombre, marca·color, precio. Toda es un botón."""

    tocada = pyqtSignal(str)

    def __init__(self, card, *, elegida: bool) -> None:
        super().__init__()
        self.setObjectName("ropaTarjeta")
        self.setProperty("elegida", "true" if elegida else "false")
        self.setFixedWidth(ANCHO_TARJETA)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key = card.key
        ly = QVBoxLayout(self)
        ly.setContentsMargins(10, 10, 10, 10)
        ly.setSpacing(4)
        foto = QLabel()
        foto.setObjectName("ropaFoto")
        foto.setFixedSize(ANCHO_TARJETA - 20, ALTO_FOTO - 40)
        foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = pixmap_de_miniatura(card.foto_hash, foto.width(), foto.height())
        if pixmap is not None:
            foto.setPixmap(pixmap)
        else:
            foto.setText((card.title[:1] or "?").upper())
        ly.addWidget(foto)
        titulo = QLabel(card.title)
        titulo.setObjectName("ropaTitulo")
        titulo.setWordWrap(True)
        ly.addWidget(titulo)
        sub = QLabel(card.subtitle)
        sub.setObjectName("ropaSub")
        sub.setWordWrap(True)
        ly.addWidget(sub)
        precio = QLabel(card.price_label)
        precio.setObjectName("ropaPrecio")
        ly.addWidget(precio)

    def mousePressEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self.tocada.emit(self._key)
        super().mousePressEvent(event)


class RopaGridWidget(QWidget):
    """Fichas + cuadrícula. La ventana le pasa el `view` del guiado y escucha sus señales."""

    genero_elegido = pyqtSignal(str)
    seccion_elegida = pyqtSignal(str)
    prenda_elegida = pyqtSignal(str)
    modelo_elegido = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO)
        self._pagina = 0
        self._cards: tuple = ()
        self._elegida = ""
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(10)
        self._filas: dict[str, QHBoxLayout] = {}
        for clave, titulo in (("genero", "PARA QUIÉN"), ("seccion", "SECCIÓN"), ("prenda", "PRENDA")):
            etiqueta = QLabel(titulo)
            etiqueta.setObjectName("ropaGrupo")
            raiz.addWidget(etiqueta)
            fila = QHBoxLayout()
            fila.setSpacing(8)
            fila.addStretch(1)
            raiz.addLayout(fila)
            self._filas[clave] = fila
        self.resumen = QLabel("")
        self.resumen.setObjectName("ropaSub")
        raiz.addWidget(self.resumen)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        raiz.addWidget(self._grid_host)
        pager = QHBoxLayout()
        self.anterior_btn = QPushButton("‹ Anteriores")
        self.anterior_btn.setObjectName("ropaPagina")
        self.anterior_btn.clicked.connect(lambda: self._cambiar_pagina(-1))
        self.pagina_label = QLabel("")
        self.pagina_label.setObjectName("ropaSub")
        self.siguiente_btn = QPushButton("Siguientes ›")
        self.siguiente_btn.setObjectName("ropaPagina")
        self.siguiente_btn.clicked.connect(lambda: self._cambiar_pagina(1))
        pager.addWidget(self.anterior_btn)
        pager.addWidget(self.pagina_label)
        pager.addStretch(1)
        pager.addWidget(self.siguiente_btn)
        self._pager = QWidget()
        self._pager.setLayout(pager)
        raiz.addWidget(self._pager)
        self.tarjetas: dict[str, _Tarjeta] = {}

    # ── Entrada ─────────────────────────────────────────────────────────

    def aplicar(self, view, *, genero: str, seccion: str, prenda: str) -> None:
        """Repinta fichas y cuadrícula con lo que calculó el guiado."""
        self._fichas("genero", view.gender_options, genero, self.genero_elegido)
        self._fichas("seccion", view.bucket_options, seccion or "TODOS", self.seccion_elegida)
        self._fichas("prenda", (self._todas_las_prendas(view.piece_options),) + tuple(view.piece_options),
                     prenda or "", self.prenda_elegida)
        if self._cards != view.product_cards:
            self._pagina = 0
        self._cards = tuple(view.product_cards)
        self._elegida = view.selected_product_key
        n = len(self._cards)
        self.resumen.setText(
            f"{n} modelo{'s' if n != 1 else ''}" + (f" · {view.path_label}" if view.path_label else "")
            if n else (view.empty_label or "No hay ropa con esos filtros.")
        )
        self._pintar_pagina()

    @staticmethod
    def _todas_las_prendas(piece_options):
        from pos_uniformes.ui.helpers.quote_guided_catalog_helper import GuidedCatalogOption

        total = sum(o.count for o in piece_options)
        return GuidedCatalogOption(key="", label="Todas", count=total, enabled=total > 0)

    def _fichas(self, clave: str, options, elegida: str, senal) -> None:
        fila = self._filas[clave]
        while fila.count() > 1:                      # el último es el resorte
            item = fila.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        for i, opcion in enumerate(options):
            boton = QPushButton(f"{opcion.label} ({opcion.count})" if opcion.count else opcion.label)
            boton.setObjectName("ficha")
            boton.setCheckable(True)
            boton.setChecked(opcion.key == elegida)
            boton.setEnabled(bool(opcion.enabled) or opcion.key == elegida)
            boton.clicked.connect(lambda _=False, k=opcion.key, s=senal: s.emit(k))
            fila.insertWidget(i, boton)

    # ── Cuadrícula ──────────────────────────────────────────────────────

    def _cambiar_pagina(self, paso: int) -> None:
        paginas = max(1, (len(self._cards) + POR_PAGINA - 1) // POR_PAGINA)
        self._pagina = max(0, min(paginas - 1, self._pagina + paso))
        self._pintar_pagina()

    def _pintar_pagina(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.tarjetas = {}
        paginas = max(1, (len(self._cards) + POR_PAGINA - 1) // POR_PAGINA)
        inicio = self._pagina * POR_PAGINA
        columnas = self._columnas()
        for i, card in enumerate(self._cards[inicio:inicio + POR_PAGINA]):
            tarjeta = _Tarjeta(card, elegida=(card.key == self._elegida))
            tarjeta.tocada.connect(self.modelo_elegido)
            self._grid.addWidget(tarjeta, i // columnas, i % columnas)
            self.tarjetas[card.key] = tarjeta
        self._columnas_pintadas = columnas
        self._pager.setVisible(paginas > 1)
        self.pagina_label.setText(f"Página {self._pagina + 1} de {paginas}")
        self.anterior_btn.setEnabled(self._pagina > 0)
        self.siguiente_btn.setEnabled(self._pagina < paginas - 1)

    def _columnas(self) -> int:
        """Las que quepan en el ancho que hay: 4 en una pantalla grande, 3 o 2 en una chica."""
        ancho = self.width() if self.width() > 100 else COLUMNAS * (ANCHO_TARJETA + 12)
        return max(2, min(COLUMNAS, ancho // (ANCHO_TARJETA + 12)))

    def resizeEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        super().resizeEvent(event)
        if self._cards and getattr(self, "_columnas_pintadas", None) not in (None, self._columnas()):
            self._pintar_pagina()

    def sizeHint(self) -> QSize:  # noqa: N802 — nombre de Qt
        return QSize(2 * (ANCHO_TARJETA + 12), 400)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — nombre de Qt
        return QSize(2 * (ANCHO_TARJETA + 12), 200)
