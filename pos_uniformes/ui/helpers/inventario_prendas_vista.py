"""Lista «Por prenda» de Inventario (tanda 4, 2026-11-13).

Un `QTreeView` con un modelo propio (sin un `QStandardItem` por celda ni un
widget por celda): cada prenda + color es una fila con su escalera de tallas,
y al desplegarla salen sus tallas como filas hijas. Las cuentas salen de
`inventario_prenda_service` (puro); aquí solo se pinta.

- La escalera la dibuja `DelegadoPrendas` en la columna «Tallas»: fichas
  compactas «4·3  6·0  8·5», la talla en tenue y el número con su tono (rojo
  negativo, ámbar quedan pocas, gris cero o desactivada). Si no caben, termina
  en «…» y el aviso al pasar el mouse las dice todas.
- El ▸ / ▾ lo pinta el delegado en la primera columna; tocarlo despliega sin
  elegir la prenda. El doble clic también despliega.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import QAbstractItemModel, QEvent, QModelIndex, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPalette
from PyQt6.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeView

from pos_uniformes.services.inventario_prenda_service import (
    COLUMNAS_PRENDA,
    GrupoPrenda,
    texto_contada_grupo,
    texto_rango_precio,
)
from pos_uniformes.ui.helpers.inventario_tabla_helper import ALTO_FILA
from pos_uniformes.ui.helpers.inventory_table_row_helper import (
    COLUMNA_DONDE,
    COLUMNA_PRECIO,
    COLUMNA_SKU,
    COLUMNA_STOCK,
    INVENTORY_TABLE_HEADERS,
    InventoryTableRowView,
    build_inventory_table_row_view,
)
from pos_uniformes.ui.styles.inventario_styles import COLOR_CIFRA, COLOR_FILA_APAGADA, TENUE, TEXTO, VINO

COL_PRENDA, COL_TALLAS, COL_HAY, COL_DONDE, COL_PRECIO, COL_CONTADA = range(len(COLUMNAS_PRENDA))

#: La talla (fila hija) de esta celda: su `variante_id`; en la fila de prenda, None.
ROL_VARIANTE = Qt.ItemDataRole.UserRole
#: Índice de la prenda en el modelo (en las dos clases de fila).
ROL_GRUPO = Qt.ItemDataRole.UserRole + 1

#: Ancho que toca el ▸ en la primera columna (y sangría de las tallas).
ANCHO_FLECHA = 26
#: La fila de prenda lleva dos renglones: el nombre y, debajo, el color.
ALTO_PRENDA = 46
#: Anchos fijos de las columnas cortas; Prenda y Tallas se reparten el resto.
ANCHOS_FIJOS = {2: 46, 3: 108, 4: 108, 5: 86}
#: Parte del resto que se lleva «Prenda» (la escalera, lo demás).
PARTE_PRENDA = 0.46
_COLUMNA_TALLA = INVENTORY_TABLE_HEADERS.index("Talla")
_COLUMNA_CONTADA = INVENTORY_TABLE_HEADERS.index("Contada")
#: Fondo neutro de cada ficha de la escalera (el color va solo en el número).
FONDO_FICHA = QColor("#f5efe7")
#: Las tallas de una prenda elegida van con un vino aún más suave: también cuentan.
FONDO_TALLA_DE_PRENDA_ELEGIDA = QColor("#faf2f5")
_SIN_PADRE = 0


class ModeloPrendas(QAbstractItemModel):
    """Dos niveles: prendas (id interno 0) y sus tallas (id = índice de la prenda + 1)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.grupos: list[GrupoPrenda] = []
        self.ahora = datetime.now(tz=timezone.utc)
        self._vistas_talla: dict[object, InventoryTableRowView] = {}

    def poner(self, grupos, *, ahora: datetime | None = None) -> None:
        self.beginResetModel()
        self.grupos = list(grupos)
        self.ahora = ahora or datetime.now(tz=timezone.utc)
        self._vistas_talla = {}
        self.endResetModel()

    def vista_talla(self, fila) -> InventoryTableRowView:
        """Los textos de una talla desplegada: los MISMOS de «Por talla» (se
        arman solo al desplegarla y se guardan hasta el siguiente refresco)."""
        llave = fila.get("variante_id")
        vista = self._vistas_talla.get(llave)
        if vista is None:
            vista = build_inventory_table_row_view(dict(fila))
            self._vistas_talla[llave] = vista
        return vista

    # ── Estructura ───────────────────────────────────────────────────────

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        if not parent.isValid():
            if 0 <= row < len(self.grupos) and 0 <= column < len(COLUMNAS_PRENDA):
                return self.createIndex(row, column, _SIN_PADRE)
            return QModelIndex()
        if parent.internalId() != _SIN_PADRE:
            return QModelIndex()
        grupo = parent.row()
        if 0 <= grupo < len(self.grupos) and 0 <= row < self.grupos[grupo].tallas:
            return self.createIndex(row, column, grupo + 1)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid() or index.internalId() == _SIN_PADRE:
            return QModelIndex()
        return self.createIndex(index.internalId() - 1, 0, _SIN_PADRE)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        if not parent.isValid():
            return len(self.grupos)
        if parent.internalId() == _SIN_PADRE and parent.column() == 0:
            return self.grupos[parent.row()].tallas
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return len(COLUMNAS_PRENDA)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(COLUMNAS_PRENDA):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return COLUMNAS_PRENDA[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if section == COL_HAY:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    # ── Lo que va en cada celda ──────────────────────────────────────────

    def es_prenda(self, index: QModelIndex) -> bool:
        return index.isValid() and index.internalId() == _SIN_PADRE

    def grupo_de(self, index: QModelIndex) -> GrupoPrenda | None:
        if not index.isValid():
            return None
        fila = index.row() if index.internalId() == _SIN_PADRE else index.internalId() - 1
        return self.grupos[fila] if 0 <= fila < len(self.grupos) else None

    def fila_de(self, index: QModelIndex):
        """La fila del snapshot de una talla (fila hija); None en la de prenda."""
        if not index.isValid() or index.internalId() == _SIN_PADRE:
            return None
        grupo = self.grupos[index.internalId() - 1]
        return grupo.filas[index.row()] if 0 <= index.row() < grupo.tallas else None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.internalId() == _SIN_PADRE:
            return self._dato_prenda(self.grupos[index.row()], index.row(), index.column(), role)
        grupo_indice = index.internalId() - 1
        return self._dato_talla(self.grupos[grupo_indice], grupo_indice, index.row(), index.column(), role)

    def _dato_prenda(self, grupo: GrupoPrenda, fila: int, columna: int, role: int):
        if role == ROL_GRUPO:
            return fila
        if role == Qt.ItemDataRole.DisplayRole:
            if columna == COL_PRENDA:
                return f"{grupo.prenda} · {grupo.color}" if grupo.color else grupo.prenda
            if columna == COL_TALLAS:
                return grupo.texto_escalera
            if columna == COL_HAY:
                return grupo.texto_hay
            # La fila de prenda tiene dos renglones: «Bodega 16» / «Piso 2» y
            # «$175–$289» / «Oferta» caben sin recortarse a 1366 px.
            if columna == COL_DONDE:
                return grupo.texto_donde.replace(" · ", "\n")
            if columna == COL_PRECIO:
                rango = texto_rango_precio(grupo.precio_min, grupo.precio_max)
                return f"{rango}\n{grupo.rebaja}" if grupo.rebaja else rango
            if columna == COL_CONTADA:
                return texto_contada_grupo(grupo, ahora=self.ahora)
        elif role == Qt.ItemDataRole.ToolTipRole:
            if columna == COL_PRENDA:
                nombre = f"{grupo.prenda} · {grupo.color}" if grupo.color else grupo.prenda
                return f"{nombre}\n{grupo.tallas} {'talla' if grupo.tallas == 1 else 'tallas'}. Toca ▸ para verlas una por una."
            if columna == COL_TALLAS:
                return f"Tallas (talla·hay): {grupo.texto_escalera}"
            if columna == COL_HAY:
                if grupo.es_conjunto:
                    return "Conjunto: su número sale de sus piezas y no suma al total"
                return "Piezas de todas sus tallas (un negativo no resta)"
            if columna == COL_PRECIO:
                return grupo.aviso_precio
            if columna == COL_CONTADA:
                return "La talla contada hace más tiempo"
        elif role == Qt.ItemDataRole.ForegroundRole:
            if columna == COL_HAY and grupo.es_conjunto:
                return QColor(TENUE)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if columna == COL_HAY:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.FontRole:
            if columna in (COL_PRENDA, COL_HAY):
                fuente = QFont()
                fuente.setBold(True)
                return fuente
        return None

    def _dato_talla(self, grupo: GrupoPrenda, grupo_indice: int, fila_indice: int, columna: int, role: int):
        fila = grupo.filas[fila_indice]
        if role == ROL_VARIANTE:
            return fila.get("variante_id")
        if role == ROL_GRUPO:
            return grupo_indice
        vista = self.vista_talla(fila)
        apagada = vista.row_tone == "muted"
        de_tabla = {
            COL_PRENDA: COLUMNA_SKU,
            COL_TALLAS: _COLUMNA_TALLA,
            COL_HAY: COLUMNA_STOCK,
            COL_DONDE: COLUMNA_DONDE,
            COL_PRECIO: COLUMNA_PRECIO,
            COL_CONTADA: _COLUMNA_CONTADA,
        }[columna]
        if role == Qt.ItemDataRole.DisplayRole:
            valor = vista.values[de_tabla]
            if columna == COL_TALLAS:
                talla = str(valor or "").strip()
                return f"Talla {talla}" if talla else "Sin talla"
            return "" if valor is None else str(valor)
        if role == Qt.ItemDataRole.ForegroundRole:
            if apagada:
                return QColor(COLOR_FILA_APAGADA)
            if columna == COL_PRENDA:
                return QColor(TENUE)
            if columna == COL_HAY:
                color = COLOR_CIFRA.get(vista.stock_tone or "")
                return QColor(color) if color else None
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            for col, aviso in vista.cell_tooltips:
                if col == de_tabla:
                    return aviso
            return vista.tooltip
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if columna == COL_HAY:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return None
        if role == Qt.ItemDataRole.FontRole:
            if columna in (COL_HAY, COL_TALLAS):
                fuente = QFont()
                fuente.setBold(True)
                return fuente
        return None


# ── Pintar ───────────────────────────────────────────────────────────────


class DelegadoPrendas(QStyledItemDelegate):
    """Pinta la escalera, el ▸/▾ y la sangría de las tallas; el resto, como
    `DelegadoConTono`: una fila elegida conserva el color de su número."""

    def __init__(self, vista: "VistaPrendas") -> None:
        super().__init__(vista)
        self.vista = vista

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 - API de Qt
        tam = super().sizeHint(option, index)
        return QSize(tam.width(), ALTO_PRENDA if index.model().es_prenda(index) else ALTO_FILA)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        modelo = index.model()
        es_prenda = modelo.es_prenda(index)
        columna = index.column()
        opcion = QStyleOptionViewItem(option)
        self.initStyleOption(opcion, index)
        # La letra conserva su tono al elegir la fila (sin esto el número rojo se pinta negro).
        color = index.data(Qt.ItemDataRole.ForegroundRole)
        brocha = QBrush(color) if color is not None else QBrush(QColor(TEXTO))
        for grupo in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            opcion.palette.setBrush(grupo, QPalette.ColorRole.HighlightedText, brocha)
        seleccion = self.vista.selectionModel()
        if (
            not es_prenda
            and not seleccion.isSelected(index)
            and seleccion.isRowSelected(index.parent().row(), QModelIndex())
        ):
            painter.fillRect(opcion.rect, FONDO_TALLA_DE_PRENDA_ELEGIDA)
        dibujo_propio = columna == COL_PRENDA or (es_prenda and columna == COL_TALLAS)
        if not dibujo_propio:
            estilo = opcion.widget.style() if opcion.widget else None
            if estilo is not None:
                estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opcion, painter, opcion.widget)
            return
        texto = opcion.text
        opcion.text = ""
        estilo = opcion.widget.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opcion, painter, opcion.widget)
        rect = estilo.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opcion, opcion.widget)
        painter.save()
        try:
            if columna == COL_PRENDA:
                self._pintar_primera(painter, opcion, rect, index, texto, es_prenda)
            else:
                self._pintar_escalera(painter, opcion, rect, modelo.grupo_de(index))
        finally:
            painter.restore()

    def _pintar_primera(self, painter: QPainter, opcion, rect: QRect, index: QModelIndex, texto: str, es_prenda: bool) -> None:
        fuente = QFont(opcion.font)
        if es_prenda:
            abierta = self.vista.isExpanded(index)
            flecha = QRect(rect.left(), rect.top(), ANCHO_FLECHA - 6, rect.height())
            painter.setPen(QColor(VINO))
            fuente_flecha = QFont(fuente)
            fuente_flecha.setPixelSize(16)
            painter.setFont(fuente_flecha)
            painter.drawText(flecha, int(Qt.AlignmentFlag.AlignCenter), "▾" if abierta else "▸")
            grupo = index.model().grupo_de(index)
            area = rect.adjusted(ANCHO_FLECHA, 0, 0, 0)
            # Dos renglones: el nombre en negritas y, debajo, el color en tenue.
            negrita = QFont(fuente)
            negrita.setBold(True)
            chica = QFont(fuente)
            chica.setPixelSize(12)
            chica.setBold(False)
            m_nombre, m_color = QFontMetrics(negrita), QFontMetrics(chica)
            alto = m_nombre.height() + m_color.height()
            arriba = area.top() + (area.height() - alto) // 2
            nombre = grupo.prenda if grupo else texto
            painter.setFont(negrita)
            painter.setPen(QColor(TEXTO))
            painter.drawText(QRect(area.left(), arriba, area.width(), m_nombre.height()),
                             int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                             m_nombre.elidedText(nombre, Qt.TextElideMode.ElideRight, area.width()))
            color = (grupo.color if grupo else "") or "Sin color"
            painter.setFont(chica)
            painter.setPen(QColor(TENUE))
            painter.drawText(QRect(area.left(), arriba + m_nombre.height(), area.width(), m_color.height()),
                             int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                             m_color.elidedText(color, Qt.TextElideMode.ElideRight, area.width()))
            return
        # Talla: sangría bajo la flecha y el código en tenue.
        area = rect.adjusted(ANCHO_FLECHA, 0, 0, 0)
        color = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setFont(fuente)
        painter.setPen(color if isinstance(color, QColor) else QColor(TENUE))
        painter.drawText(area, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         QFontMetrics(fuente).elidedText(texto, Qt.TextElideMode.ElideRight, area.width()))

    def _pintar_escalera(self, painter: QPainter, opcion, rect: QRect, grupo: GrupoPrenda | None) -> None:
        if grupo is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fuente_talla = QFont(opcion.font)
        fuente_talla.setPixelSize(11)
        fuente_cifra = QFont(opcion.font)
        fuente_cifra.setPixelSize(13)
        fuente_cifra.setBold(True)
        m_talla = QFontMetrics(fuente_talla)
        m_cifra = QFontMetrics(fuente_cifra)
        alto = 22
        y = rect.top() + (rect.height() - alto) // 2
        x = rect.left()
        derecha = rect.right()
        puntos = m_cifra.horizontalAdvance("…") + 6
        fichas = grupo.escalera
        for posicion, talla in enumerate(fichas):
            etiqueta = f"{talla.talla or '—'}·"
            ancho = 6 + m_talla.horizontalAdvance(etiqueta) + m_cifra.horizontalAdvance(talla.cifra) + 6
            ultima = posicion == len(fichas) - 1
            if x + ancho > derecha - (0 if ultima else puntos):
                painter.setFont(fuente_cifra)
                painter.setPen(QColor(TENUE))
                painter.drawText(QRect(x, rect.top(), puntos + 4, rect.height()),
                                 int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), "…")
                return
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(FONDO_FICHA)
            painter.drawRoundedRect(QRect(x, y, ancho, alto), 8, 8)
            painter.setFont(fuente_talla)
            painter.setPen(QColor(COLOR_FILA_APAGADA if not talla.activa else TENUE))
            ancho_etiqueta = m_talla.horizontalAdvance(etiqueta)
            painter.drawText(QRect(x + 6, y, ancho_etiqueta, alto), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), etiqueta)
            painter.setFont(fuente_cifra)
            painter.setPen(QColor(COLOR_CIFRA.get(talla.tono) or TEXTO))
            painter.drawText(QRect(x + 6 + ancho_etiqueta, y, ancho, alto),
                             int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), talla.cifra)
            x += ancho + 4


class VistaPrendas(QTreeView):
    """El árbol de prendas. Tocar el ▸ despliega sin elegir; doble clic en una
    prenda la despliega y en una talla avisa `talla_doble_clic`."""

    talla_doble_clic = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("invPrendas")
        self.modelo = ModeloPrendas(self)
        self.setModel(self.modelo)
        self.setItemDelegate(DelegadoPrendas(self))
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        # Las prendas (dos renglones) son más altas que sus tallas.
        self.setUniformRowHeights(False)
        self.setExpandsOnDoubleClick(False)
        self.setAllColumnsShowFocus(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(120)
        self.setMouseTracking(True)
        encabezado = self.header()
        encabezado.setHighlightSections(False)
        encabezado.setSectionsClickable(True)
        encabezado.setStretchLastSection(False)
        encabezado.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for columna in range(len(COLUMNAS_PRENDA)):
            encabezado.setSectionResizeMode(columna, QHeaderView.ResizeMode.Fixed)
        self._acomodar_columnas()
        self.doubleClicked.connect(self._doble_clic)

    def _acomodar_columnas(self) -> None:
        """Las columnas cortas tienen ancho fijo; Prenda y la escalera se
        reparten lo que queda (sin barra horizontal a 1366 px)."""
        encabezado = self.header()
        for columna, ancho in ANCHOS_FIJOS.items():
            encabezado.resizeSection(columna, ancho)
        resto = max(240, self.viewport().width() - sum(ANCHOS_FIJOS.values()))
        prenda = int(resto * PARTE_PRENDA)
        encabezado.resizeSection(COL_PRENDA, prenda)
        encabezado.resizeSection(COL_TALLAS, resto - prenda)

    def viewportEvent(self, event) -> bool:  # noqa: N802 - API de Qt
        # El viewport cambia de ancho también cuando sale o se va la barra vertical.
        if event.type() == QEvent.Type.Resize:
            self._acomodar_columnas()
        return super().viewportEvent(event)

    # ── Desplegar ────────────────────────────────────────────────────────

    def alternar(self, index: QModelIndex) -> None:
        indice = self.modelo.index(index.row(), 0) if self.modelo.es_prenda(index) else QModelIndex()
        if indice.isValid():
            self.setExpanded(indice, not self.isExpanded(indice))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - API de Qt
        index = self.indexAt(event.position().toPoint())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.modelo.es_prenda(index)
            and index.column() == COL_PRENDA
            and event.position().toPoint().x() - self.visualRect(index).left() < ANCHO_FLECHA
        ):
            self.alternar(index)
            event.accept()
            return
        super().mousePressEvent(event)

    def _doble_clic(self, index: QModelIndex) -> None:
        if self.modelo.es_prenda(index):
            self.alternar(index)
            return
        variante = index.data(ROL_VARIANTE)
        if variante is not None:
            self.talla_doble_clic.emit(variante)

    def llaves_desplegadas(self) -> set:
        return {
            grupo.llave
            for fila, grupo in enumerate(self.modelo.grupos)
            if self.isExpanded(self.modelo.index(fila, 0))
        }

    def desplegar(self, llaves) -> None:
        for fila, grupo in enumerate(self.modelo.grupos):
            if grupo.llave in llaves:
                self.setExpanded(self.modelo.index(fila, 0), True)

    # ── Qué hay elegido ──────────────────────────────────────────────────

    def variantes_elegidas(self) -> list:
        """Tallas elegidas: una prenda elegida cuenta todas sus tallas. Sin repetir, en orden."""
        vistas: set = set()
        ids: list = []
        filas = sorted(
            self.selectionModel().selectedRows(0),
            key=lambda i: (i.internalId() - 1 if i.internalId() else i.row(), -1 if not i.internalId() else i.row()),
        )
        for index in filas:
            if self.modelo.es_prenda(index):
                candidatos = self.modelo.grupos[index.row()].variante_ids
            else:
                candidatos = (index.data(ROL_VARIANTE),)
            for variante in candidatos:
                if variante is not None and variante not in vistas:
                    vistas.add(variante)
                    ids.append(variante)
        return ids

    def llaves_elegidas(self) -> set:
        return {self.modelo.grupos[i.row()].llave for i in self.selectionModel().selectedRows(0) if self.modelo.es_prenda(i)}

    def indice_de_talla(self, variante_id: object) -> QModelIndex:
        for fila, grupo in enumerate(self.modelo.grupos):
            if variante_id in grupo.variante_ids:
                return self.modelo.index(grupo.variante_ids.index(variante_id), 0, self.modelo.index(fila, 0))
        return QModelIndex()

    def indice_de_prenda(self, llave) -> QModelIndex:
        for fila, grupo in enumerate(self.modelo.grupos):
            if grupo.llave == llave:
                return self.modelo.index(fila, 0)
        return QModelIndex()
