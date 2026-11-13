"""Cara nueva de la pestaña Inventario (tanda 3): tarjetas, ficha y «⋯».

`InventarioPantalla` es el coordinador propio de la pestaña: la vista lo
crea (`build_inventory_tab`) y `main_window.py` solo le avisa en tres
puntos (filas filtradas, fin del refresco y ficha nueva). Las reglas viven
en servicios puros: `inventario_tarjetas_service` (qué cae en cada tarjeta,
«Para atender») e `inventario_vista_service` (orden, escaneo, textos, topes).

Las acciones llaman a los manejadores de siempre de la ventana por nombre
(`getattr(window, nombre)()`), así ninguna función vieja queda
inalcanzable y las pruebas pueden cambiarlos por dobles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Mapping

from PyQt6.QtCore import QEvent, QItemSelection, QItemSelectionModel, QModelIndex, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from pos_uniformes.services.inventario_donde_service import texto_donde_completo
from pos_uniformes.ui.helpers.history_filter_state_helper import build_history_clear_filter_state
from pos_uniformes.services.inventario_existencia_service import es_fila_virtual
from pos_uniformes.services.inventario_precio_service import LLAVE_PRECIO, LLAVE_TIPO, precio_efectivo
from pos_uniformes.services.inventario_prenda_service import (
    COLUMNAS_PRENDA,
    GrupoPrenda,
    PaginaPrendas,
    agrupar_por_prenda,
    filas_en_orden,
    indice_de_variante,
    ordenar_grupos,
    paginar_prendas,
    resumen_prendas,
    siguiente_orden_prenda,
    texto_paginacion_prendas,
)
from pos_uniformes.services.rebaja_service import ETIQUETAS as ETIQUETAS_REBAJA, fmt_corto
from pos_uniformes.services.inventario_tarjetas_service import (
    AVISO_TARJETAS,
    EN_NEGATIVO,
    INFO_TARJETAS,
    QUEDAN_POCAS,
    SE_ACABO,
    TARJETAS,
    ConteoTarjetas,
    contar_tarjetas,
    en_tarjeta,
    filtrar_por_tarjeta,
    motivo_para_atender,
    para_atender,
)
from pos_uniformes.services.inventario_vista_service import (
    BLOQUEAR,
    CONFIRMAR,
    NADA,
    UMBRAL_CONFIRMAR_ETIQUETAS,
    buscar_sku_exacto,
    confirmacion_coincide,
    contar_activos,
    decidir_impresion_lote,
    ordenar_por_columna,
    resumir_lote,
    siguiente_orden,
    texto_contada_corto,
    texto_paginacion,
    texto_talla_color,
)
from pos_uniformes.ui.helpers.catalog_pagination_helper import CatalogPaginationView
from pos_uniformes.ui.helpers.inventario_combo_rotulo import RotuloCombos
from pos_uniformes.ui.helpers.inventario_prendas_vista import VistaPrendas
from pos_uniformes.ui.helpers.inventory_table_row_helper import INVENTORY_TABLE_HEADERS
from pos_uniformes.ui.styles.inventario_styles import sombra

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow

#: El aviso de la búsqueda cortada viene pegado al resumen (`_with_notice`).
_SEPARADOR_AVISO = " · ⚠ "

#: Las dos vistas de la lista (segmento [Por talla | Por prenda]).
POR_TALLA = "talla"
POR_PRENDA = "prenda"
AVISO_POR_TALLA = "Una fila por cada talla"
AVISO_POR_PRENDA = "Cada prenda y color en una fila con su escalera de tallas (talla·hay). Toca ▸ para ver sus tallas."


def _repulir(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _etiqueta(texto: str, nombre: str, *, envolver: bool = False) -> QLabel:
    label = QLabel(texto)
    label.setObjectName(nombre)
    label.setWordWrap(envolver)
    return label


class MarcaFoco(QObject):
    """Pone `foco="si"` en el marco mientras su campo tiene el foco (la hoja
    lo pinta con borde vino), como `cliBuscar:focus` en Clientes."""

    def __init__(self, marco: QWidget, campo: QWidget) -> None:
        super().__init__(marco)
        self.marco = marco
        marco.setProperty("foco", "no")
        campo.installEventFilter(self)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:  # noqa: N802 - API de Qt
        if evento.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            valor = "si" if evento.type() == QEvent.Type.FocusIn else "no"
            if self.marco.property("foco") != valor:
                self.marco.setProperty("foco", valor)
                _repulir(self.marco)
        return False


# ── Tarjeta que filtra ───────────────────────────────────────────────────


class TarjetaFiltro(QFrame):
    """Cifra grande con su criterio; tocarla filtra y la deja marcada."""

    tocada = pyqtSignal(str)

    def __init__(self, llave: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        info = INFO_TARJETAS[llave]
        self.llave = llave
        self.setObjectName("invTarjeta")
        self.setProperty("tono", info.tono)
        self.setProperty("prendida", "no")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{AVISO_TARJETAS[llave]}\nTócala para ver solo esas; otra vez para quitar el filtro.")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        self.titulo = _etiqueta(info.titulo.upper(), "invTarjetaTitulo")
        self.valor = _etiqueta("0", "invTarjetaValor")
        self.valor.setProperty("tono", info.tono)
        self.nota = _etiqueta(info.criterio, "invTarjetaNota", envolver=True)
        layout.addWidget(self.titulo)
        layout.addWidget(self.valor)
        layout.addWidget(self.nota)
        sombra(self)

    def mostrar(self, cantidad: int, *, prendida: bool) -> None:
        self.valor.setText(f"{cantidad:,}")
        valor = "si" if prendida else "no"
        if self.property("prendida") != valor:
            self.setProperty("prendida", valor)
            _repulir(self)

    def esta_prendida(self) -> bool:
        return self.property("prendida") == "si"

    def mousePressEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self.tocada.emit(self.llave)
        super().mousePressEvent(event)


# ── Ficha derecha ────────────────────────────────────────────────────────


class EtiquetaRecortada(QLabel):
    """Un renglón que, si no cabe, termina en «…» y enseña el texto completo
    al pasar el mouse (en vez de cortarse en seco)."""

    def __init__(self, texto: str, nombre: str) -> None:
        super().__init__()
        self.setObjectName(nombre)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(1)
        self._completo = ""
        self.poner(texto)

    def poner(self, texto: str) -> None:
        self._completo = texto
        self.setToolTip(texto)
        self._recortar()

    def completo(self) -> str:
        return self._completo

    def _recortar(self) -> None:
        ancho = max(1, self.contentsRect().width())
        self.setText(self.fontMetrics().elidedText(self._completo, Qt.TextElideMode.ElideRight, ancho))

    def resizeEvent(self, event) -> None:  # noqa: N802 - API de Qt
        super().resizeEvent(event)
        self._recortar()

    def changeEvent(self, event) -> None:  # noqa: N802 - API de Qt
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._recortar()


class FilaAtender(QFrame):
    """Un renglón tocable de «Para atender». Arriba la prenda (con «…» si es
    larga); abajo la talla, el color y por qué urge, que nunca se pierden."""

    tocada = pyqtSignal(object)

    def __init__(
        self, variante_id: object, prenda: str, talla_color: str, motivo: str, tono: str, aviso: str = ""
    ) -> None:
        super().__init__()
        self.variante_id = variante_id
        self.setObjectName("invAtender")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(1)
        self.titulo = EtiquetaRecortada(prenda, "invAtenderTitulo")
        if aviso:
            self.titulo.setToolTip(f"{prenda}\n{aviso}")
            self.setToolTip(aviso)
        layout.addWidget(self.titulo)
        abajo = QHBoxLayout()
        abajo.setSpacing(0)
        self.talla = _etiqueta(f"{talla_color} · " if talla_color else "", "invAtenderTalla")
        self.motivo = _etiqueta(motivo, "invAtenderMotivo")
        self.motivo.setProperty("tono", tono)
        abajo.addWidget(self.talla)
        abajo.addWidget(self.motivo)
        abajo.addStretch(1)
        layout.addLayout(abajo)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self.tocada.emit(self.variante_id)
        super().mousePressEvent(event)



VACIA, TALLA, LOTE = 0, 1, 2


class _PilaFicha(QStackedWidget):
    """Las tres caras de la ficha. No pide alto según su ancho: si lo pidiera,
    los textos que se envuelven harían crecer la pestaña entera y saldría un
    segundo scroll. El alto lo pone la lista de la izquierda."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - API de Qt
        return False


class FichaInventario(QFrame):
    """Tarjeta blanca de la derecha con sus tres estados: vacía, una talla, varias."""

    ANCHO = 420

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("invFicha")
        self.setFixedWidth(self.ANCHO)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sombra(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(0)
        self.paginas = _PilaFicha()
        self.paginas.setObjectName("invFichaPaginas")
        # La ficha no empuja la página: su alto lo pone la lista de la izquierda.
        # (Con «Ignored» su mínimo no cuenta y la pestaña no se desplaza entera.)
        self.paginas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.paginas)
        # Cada cara va en su propio scroll sin marco: si un nombre de dos
        # renglones no cabe a 768 px, se desplaza SOLO la ficha y nada se aplasta.
        self.scrolls: list[QScrollArea] = []
        for pagina in (self._pagina_vacia(), self._pagina_talla(), self._pagina_lote()):
            self.paginas.addWidget(self._desplazable(pagina))

    def _desplazable(self, pagina: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setObjectName("invFichaScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.viewport().setObjectName("invFichaVista")
        area.viewport().setAutoFillBackground(False)
        area.setWidget(pagina)
        self.scrolls.append(area)
        return area

    # Vacía: instrucción y «Para atender»
    def _pagina_vacia(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("invFichaPagina")
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.vacio = _etiqueta(
            "🔎  Elige una talla\nTócala en la lista o escanea su etiqueta.",
            "invVacio",
            envolver=True,
        )
        layout.addWidget(self.vacio)
        layout.addSpacing(4)
        layout.addWidget(_etiqueta("PARA ATENDER", "invSeccion"))
        self.atender_nota = _etiqueta("", "invFichaLinea", envolver=True)
        layout.addWidget(self.atender_nota)
        self.atender_caja = QVBoxLayout()
        self.atender_caja.setSpacing(0)
        layout.addLayout(self.atender_caja)
        layout.addStretch(1)
        self.atender_botones: list[FilaAtender] = []
        self.atender_ids: list[object] = []
        return pagina

    # Una talla
    def _pagina_talla(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("invFichaPagina")
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        # El estado («Se acabó», «Desactivada») sube al renglón del título:
        # así no le quita alto a la tarjeta vino.
        encabezado = QHBoxLayout()
        encabezado.setSpacing(6)
        encabezado.addWidget(_etiqueta("TALLA ELEGIDA", "invSeccion"))
        encabezado.addSpacing(4)
        self.chip_estado = _etiqueta("", "invChip")
        self.chip_apagada = _etiqueta("Desactivada", "invChip")
        self.chip_apagada.setToolTip("Desactivada: no se vende ni sale en el kiosko")
        self.chip_apagada.setProperty("tono", "muted")
        encabezado.addWidget(self.chip_estado, 0, Qt.AlignmentFlag.AlignVCenter)
        encabezado.addWidget(self.chip_apagada, 0, Qt.AlignmentFlag.AlignVCenter)
        encabezado.addStretch(1)
        self.mas = QToolButton()
        self.mas.setObjectName("invFichaMas")
        self.mas.setText("⋯")
        self.mas.setToolTip("Más para esta talla: editar la prenda, foto, desactivar…")
        self.mas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        encabezado.addWidget(self.mas)
        layout.addLayout(encabezado)

        total = QFrame()
        total.setObjectName("invFichaTotal")
        # Nunca se encoge: si falta alto, se desplaza la ficha, no se cortan las cifras.
        total.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sombra(total, fuerte=True)
        caja = QVBoxLayout(total)
        caja.setContentsMargins(18, 14, 18, 14)
        caja.setSpacing(2)
        self.nombre = _etiqueta("", "invFichaNombre", envolver=True)
        self.sub = _etiqueta("", "invFichaSub", envolver=True)
        caja.addWidget(self.nombre)
        caja.addWidget(self.sub)
        caja.addSpacing(8)
        datos = QHBoxLayout()
        datos.setSpacing(18)
        self.hay, self.hay_nota = self._dato(datos, "HAY")
        self.precio, self.precio_nota = self._dato(datos, "PRECIO")
        datos.addStretch(1)
        caja.addLayout(datos)
        self.total = total
        layout.addWidget(total)

        # «Etiqueta: valor» en un renglón cada uno (antes eran dos por dato).
        lineas = QGridLayout()
        lineas.setHorizontalSpacing(12)
        lineas.setVerticalSpacing(6)
        lineas.setColumnStretch(1, 1)
        self.donde = self._linea(lineas, 0, "DÓNDE")
        self.contada = self._linea(lineas, 1, "CONTADA")
        self.movimiento = self._linea(lineas, 2, "ÚLTIMO MOV.")
        self.movimiento.setToolTip("Último movimiento de esta talla")
        layout.addLayout(lineas)

        self.acciones = QGridLayout()
        self.acciones.setHorizontalSpacing(8)
        self.acciones.setVerticalSpacing(8)
        layout.addSpacing(2)
        layout.addLayout(self.acciones)
        layout.addStretch(1)
        return pagina

    def _dato(self, fila: QHBoxLayout, titulo: str) -> tuple[QLabel, QLabel]:
        columna = QVBoxLayout()
        columna.setSpacing(0)
        columna.addWidget(_etiqueta(titulo, "invFichaDatoTitulo"))
        valor = _etiqueta("", "invFichaDatoValor")
        # La cifra grande guarda su alto completo pase lo que pase.
        valor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        nota = _etiqueta("", "invFichaDatoNota")
        columna.addWidget(valor)
        columna.addWidget(nota)
        fila.addLayout(columna)
        return valor, nota

    def _linea(self, rejilla: QGridLayout, renglon: int, titulo: str) -> QLabel:
        etiqueta = _etiqueta(titulo, "invFichaEtiqueta")
        rejilla.addWidget(etiqueta, renglon, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        valor = _etiqueta("", "invFichaLinea", envolver=True)
        rejilla.addWidget(valor, renglon, 1, Qt.AlignmentFlag.AlignTop)
        return valor

    # Varias tallas
    def _pagina_lote(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("invFichaPagina")
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_etiqueta("VARIAS TALLAS", "invSeccion"))
        total = QFrame()
        total.setObjectName("invFichaTotal")
        sombra(total, fuerte=True)
        caja = QVBoxLayout(total)
        caja.setContentsMargins(18, 16, 18, 16)
        caja.setSpacing(2)
        caja.addWidget(_etiqueta("ELEGISTE", "invFichaDatoTitulo"))
        self.lote_total = _etiqueta("", "invFichaNombre", envolver=True)
        caja.addWidget(self.lote_total)
        self.lote_nota = _etiqueta("Con Ctrl/Cmd + clic sumas o quitas tallas; con Shift, un rango.", "invFichaSub", envolver=True)
        caja.addWidget(self.lote_nota)
        layout.addWidget(total)
        self.lote_acciones = QVBoxLayout()
        self.lote_acciones.setSpacing(8)
        layout.addLayout(self.lote_acciones)
        layout.addStretch(1)
        return pagina

    def estado(self) -> int:
        return self.paginas.currentIndex()


def boton_accion(texto: str, aviso: str = "") -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName("invAccion")
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    if aviso:
        boton.setToolTip(aviso)
    return boton


# ── Coordinador de la pestaña ────────────────────────────────────────────


class InventarioPantalla(QObject):
    """Estado y acciones de la cara nueva. La ventana solo le avisa."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.tarjeta: str | None = None
        self.orden: tuple[str | None, bool] = (None, False)
        self.conteo = ConteoTarjetas(0, 0, 0, 0)
        self.filas_base: list = []
        self._ultimo_mov: tuple[str, str] = ("", "")
        self._sku_escaneado = ""
        self._seleccionando = False
        self.tarjetas: dict[str, TarjetaFiltro] = {}
        # Tanda 4: vista «Por prenda». La vista elegida se recuerda mientras
        # la ventana esté abierta (la sesión); no se guarda en disco.
        self.vista = POR_TALLA
        self.orden_prenda: tuple[str | None, bool] = (None, False)
        self.grupos: list[GrupoPrenda] = []
        self.pagina_prendas: PaginaPrendas | None = None
        #: Lo último elegido en el árbol (prendas por llave y tallas sueltas),
        #: para volver a marcarlo tras un refresco.
        self._eleccion_arbol: tuple[set, list] = (set(), [])
        self._espejando = False
        self.prendas = VistaPrendas()
        self.prendas.selectionModel().selectionChanged.connect(lambda *_: self._al_elegir_en_arbol())
        self.prendas.header().sectionClicked.connect(self.tocar_encabezado_prenda)
        self.prendas.talla_doble_clic.connect(lambda _: self._llamar("_handle_inventory_table_double_click"))
        soltar = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.prendas)
        soltar.setContext(Qt.ShortcutContext.WidgetShortcut)
        soltar.activated.connect(self.quitar_seleccion)
        self.ficha = FichaInventario()
        self.subtitulo = _etiqueta("", "invSub")
        self.aviso_busqueda = _etiqueta("", "invSub")
        self.aviso_busqueda.setVisible(False)
        self.paginas = _etiqueta("", "invPaginas")
        self.mas_filtros = QToolButton()
        self.mas_filtros.setObjectName("invMasFiltros")
        self.mas_filtros.setCheckable(True)
        self.mas_filtros.setText("Más filtros")
        self.rotulos = RotuloCombos(self)
        self.mas_filtros_panel = QFrame()
        self.mas_filtros_panel.setObjectName("invMasFiltrosPanel")
        self.mas_filtros_panel.setVisible(False)
        self.mas_filtros.toggled.connect(self.mas_filtros_panel.setVisible)
        for llave in TARJETAS:
            tarjeta = TarjetaFiltro(llave)
            tarjeta.tocada.connect(self.tocar_tarjeta)
            self.tarjetas[llave] = tarjeta
        self._armar_acciones_ficha()

    # ── Avisos de la ventana ─────────────────────────────────────────────

    def ahora(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def preparar_filas(self, filas: list) -> list:
        """Filas ya filtradas por la ventana → cuenta tarjetas, filtra por la tocada y ordena."""
        ahora = self.ahora()
        self.filas_base = filas
        self.conteo = contar_tarjetas(filas, ahora=ahora)
        visibles = filtrar_por_tarjeta(filas, self.tarjeta, ahora=ahora)
        if self.por_prenda():
            # Se agrupa lo que pasó filtros y tarjeta; las filas quedan prenda tras prenda.
            columna, descendente = self.orden_prenda
            self.grupos = ordenar_grupos(agrupar_por_prenda(visibles), columna, descendente=descendente)
            return filas_en_orden(self.grupos)
        self.grupos = []
        columna, descendente = self.orden
        return ordenar_por_columna(visibles, columna, descendente=descendente)

    def por_prenda(self) -> bool:
        return self.vista == POR_PRENDA

    def paginar(self, pagina: int, tamano: int, variante_id: object = None) -> CatalogPaginationView:
        """«Por prenda»: la página cuenta prendas y lleva todas sus tallas.

        Devuelve lo mismo que `build_catalog_pagination_view` para que la
        ventana llene la tabla (escondida) con las tallas de la página: la
        tabla sigue siendo de donde leen la selección todos los manejadores.
        """
        resultado = paginar_prendas(self.grupos, pagina, tamano, variante_id=variante_id)
        self.pagina_prendas = resultado
        filas = filas_en_orden(resultado.grupos)
        return CatalogPaginationView(
            page_rows=filas,
            current_page_index=resultado.pagina,
            total_pages=resultado.paginas,
            total_rows=resultado.total,
            start_row_number=resultado.inicio,
            end_row_number=resultado.fin,
            page_label=texto_paginacion_prendas(resultado),
            previous_enabled=resultado.pagina > 0,
            next_enabled=resultado.pagina < resultado.paginas - 1,
        )

    def al_refrescar(self) -> None:
        """Fin de `_refresh_inventory_table`: encabezado, tarjetas, filtros, páginas y ficha."""
        w = self.window
        resumen = w.inventory_results_label.text()
        principal, _, aviso = resumen.partition(_SEPARADOR_AVISO)
        self.subtitulo.setText(resumen_prendas(self.grupos) if self.por_prenda() else principal)
        self.aviso_busqueda.setText(f"⚠ {aviso}" if aviso else "")
        self.aviso_busqueda.setVisible(bool(aviso))
        for llave, tarjeta in self.tarjetas.items():
            tarjeta.mostrar(self.conteo.de(llave), prendida=self.tarjeta == llave)
        self._refrescar_filtros()
        if self.por_prenda():
            pagina = self.pagina_prendas or paginar_prendas(self.grupos, 0, _tamano_pagina())
            self.paginas.setText(texto_paginacion_prendas(pagina))
            varias = len(self.grupos) > _tamano_pagina()
        else:
            self.paginas.setText(texto_paginacion(len(w.inventory_filtered_rows), w.inventory_page_index, _tamano_pagina()))
            varias = len(w.inventory_filtered_rows) > _tamano_pagina()
        # Con una sola página las flechas no sirven: no se enseñan.
        w.inventory_previous_page_button.setVisible(varias)
        w.inventory_next_page_button.setVisible(varias)
        self._marcar_orden()
        if self.por_prenda():
            self._llenar_arbol()
        if not self._seleccionando:
            self._seleccionar_si_es_codigo()
        self.actualizar_ficha()

    def al_cambiar_ficha(self, vista) -> None:
        """Fin de `_apply_inventory_overview_view`: guarda el último movimiento y redibuja."""
        self._ultimo_mov = (str(getattr(vista, "overview_label", "") or ""), str(getattr(vista, "last_movement_label", "") or ""))
        self.actualizar_ficha()

    # ── Tarjetas, orden y filtros ────────────────────────────────────────

    def tocar_tarjeta(self, llave: str) -> None:
        self.tarjeta = None if self.tarjeta == llave else llave
        self.window._handle_inventory_filters_changed_reset_page()

    def quitar_tarjeta(self) -> None:
        self.tarjeta = None

    def tocar_encabezado(self, columna: int) -> None:
        if not 0 <= columna < len(INVENTORY_TABLE_HEADERS):
            return
        self.orden = siguiente_orden(self.orden, INVENTORY_TABLE_HEADERS[columna])
        self.window._handle_inventory_filters_changed_reset_page()

    def _marcar_orden(self) -> None:
        encabezado = self.window.inventory_table.horizontalHeader()
        columna, descendente = self.orden
        if columna is None:
            encabezado.setSortIndicatorShown(False)
            return
        encabezado.setSortIndicatorShown(True)
        encabezado.setSortIndicator(
            INVENTORY_TABLE_HEADERS.index(columna),
            Qt.SortOrder.DescendingOrder if descendente else Qt.SortOrder.AscendingOrder,
        )

    def filtros_de_mas(self) -> list[object]:
        w = self.window
        return [
            w.inventory_brand_filter_combo.has_selection(),
            w.inventory_type_filter_combo.has_selection(),
            w.inventory_use_filter_combo.currentData(),
            w.inventory_status_filter_combo.currentData(),
            w.inventory_stock_filter_combo.currentData(),
            w.inventory_precio_filter_combo.currentData(),
            w.inventory_conteo_filter_combo.currentData(),
            w.inventory_precio_text_input.text().strip(),
        ]

    def hay_filtro(self) -> bool:
        return bool(self.tarjeta) or bool(self.window._inventory_active_filter_tokens())

    def _refrescar_filtros(self) -> None:
        n = contar_activos(self.filtros_de_mas())
        self.mas_filtros.setText(f"Más filtros ({n})" if n else "Más filtros")
        self.window.inventory_clear_filters_button.setVisible(self.hay_filtro())

    # ── Escaneo y selección ──────────────────────────────────────────────

    def _seleccionar_si_es_codigo(self) -> None:
        texto = self.window.inventory_search_input.text().strip()
        if not texto or texto == self._sku_escaneado:
            if not texto:
                self._sku_escaneado = ""
            return
        # Se busca antes de la tarjeta: si el código no cae en la tarjeta prendida,
        # `seleccionar` la apaga y elige la talla de todos modos.
        variante_id = buscar_sku_exacto(self.filas_base, texto)
        if variante_id is None:
            return
        self._sku_escaneado = texto
        self.seleccionar(variante_id)

    def seleccionar(self, variante_id: object) -> None:
        """Lleva la tabla a la página de esa talla y la elige (desde «Para atender» o un escaneo)."""
        w = self.window
        if self._seleccionando:
            return
        self._seleccionando = True
        try:
            indice = _indice(w.inventory_filtered_rows, variante_id)
            if indice is None and self.tarjeta:
                self.tarjeta = None
                w._handle_inventory_filters_changed()
                indice = _indice(w.inventory_filtered_rows, variante_id)
            if indice is None:
                return
            if self.por_prenda():
                # La talla se ve desplegada dentro de su prenda, en la página de esa prenda.
                self._eleccion_arbol = (set(), [variante_id])
                indice = indice_de_variante(self.grupos, variante_id) or 0
            w.inventory_page_index = indice // _tamano_pagina()
            w._set_combo_value(w.inventory_variant_combo, variante_id)
            w._handle_inventory_filters_changed()
            w._sync_inventory_table_selection(variante_id)
            fila_tabla = w.inventory_table.currentRow()
            if fila_tabla >= 0:
                w.inventory_table.scrollTo(
                    w.inventory_table.model().index(fila_tabla, 0),
                    w.inventory_table.ScrollHint.PositionAtCenter,
                )
            if self.por_prenda():
                self._eleccion_arbol = (set(), [variante_id])
                self._marcar_en_arbol()
        finally:
            self._seleccionando = False
        self.actualizar_ficha()

    def variante_actual(self) -> object | None:
        w = self.window
        elegidas = w._selected_inventory_variant_ids()
        if len(elegidas) > 1:
            return None
        actual = w.inventory_variant_combo.currentData()
        if actual:
            return actual
        return elegidas[0] if elegidas else None

    def fila_de(self, variante_id: object) -> Mapping[str, object] | None:
        for fila in self.window.inventory_filtered_rows:
            if fila.get("variante_id") == variante_id:
                return fila
        return None

    # ── Vista «Por prenda» (tanda 4) ─────────────────────────────────────

    def cambiar_vista(self, vista: str) -> None:
        """[Por talla | Por prenda]: cambia la lista y refresca desde la primera página.

        La talla elegida se conserva: en «Por prenda» se ve desplegada dentro
        de su prenda.
        """
        if vista not in (POR_TALLA, POR_PRENDA) or vista == self.vista:
            self._marcar_segmento()
            return
        w = self.window
        self.vista = vista
        actual = w.inventory_variant_combo.currentData()
        self._eleccion_arbol = (set(), [actual] if actual else [])
        self._marcar_segmento()
        w.inventory_page_index = 0
        w._handle_inventory_filters_changed()

    def _marcar_segmento(self) -> None:
        segmento = getattr(self, "segmento", None)
        if segmento:
            segmento[0].setChecked(not self.por_prenda())
            segmento[1].setChecked(self.por_prenda())
        pila = getattr(self, "pila_lista", None)
        if pila is not None:
            pila.setCurrentWidget(self.prendas if self.por_prenda() else self.window.inventory_table)

    def tocar_encabezado_prenda(self, columna: int) -> None:
        if not 0 <= columna < len(COLUMNAS_PRENDA):
            return
        self.orden_prenda = siguiente_orden_prenda(self.orden_prenda, COLUMNAS_PRENDA[columna])
        self.window._handle_inventory_filters_changed_reset_page()

    def _llenar_arbol(self) -> None:
        """Pone en el árbol las prendas de la página y vuelve a marcar lo elegido."""
        arbol = self.prendas
        desplegadas = arbol.llaves_desplegadas()
        pagina = self.pagina_prendas.grupos if self.pagina_prendas else ()
        self._espejando = True
        try:
            arbol.modelo.poner(pagina, ahora=self.ahora())
            arbol.desplegar(desplegadas)
        finally:
            self._espejando = False
        encabezado = arbol.header()
        columna, descendente = self.orden_prenda
        encabezado.setSortIndicatorShown(columna is not None)
        if columna is not None:
            encabezado.setSortIndicator(
                COLUMNAS_PRENDA.index(columna),
                Qt.SortOrder.DescendingOrder if descendente else Qt.SortOrder.AscendingOrder,
            )
        self._marcar_en_arbol()

    def _marcar_en_arbol(self) -> None:
        """Marca en el árbol lo último elegido ahí; si ya no está, lo que tenga la tabla.

        Una talla suelta se ve desplegada dentro de su prenda. Si lo marcado no
        coincide con la tabla (p. ej. una prenda entera tras un refresco), se
        copia a la tabla para que los manejadores vean lo mismo.
        """
        arbol = self.prendas
        llaves, ids = self._eleccion_arbol
        indices = [arbol.indice_de_prenda(llave) for llave in llaves]
        indices += [arbol.indice_de_talla(vid) for vid in ids]
        indices = [i for i in indices if i.isValid()]
        if not indices:
            indices = [arbol.indice_de_talla(vid) for vid in self.window._selected_inventory_variant_ids()]
            indices = [i for i in indices if i.isValid()]
        seleccion = QItemSelection()
        ultima = arbol.modelo.columnCount() - 1
        for indice in indices:
            padre = indice.parent()
            if padre.isValid():
                arbol.setExpanded(padre, True)
            seleccion.select(indice, indice.sibling(indice.row(), ultima))
        self._espejando = True
        try:
            modelo_sel = arbol.selectionModel()
            modelo_sel.select(seleccion, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            modelo_sel.setCurrentIndex(indices[0] if indices else QModelIndex(), QItemSelectionModel.SelectionFlag.NoUpdate)
        finally:
            self._espejando = False
        if indices:
            arbol.scrollTo(indices[0], arbol.ScrollHint.EnsureVisible)
            elegidas = arbol.variantes_elegidas()
            if set(elegidas) != set(self.window._selected_inventory_variant_ids()):
                self._espejar_a_tabla(elegidas, self._actual_del_arbol())

    def _actual_del_arbol(self) -> object | None:
        arbol = self.prendas
        actual = arbol.currentIndex()
        if actual.isValid():
            if arbol.modelo.es_prenda(actual):
                grupo = arbol.modelo.grupo_de(actual)
                return grupo.variante_ids[0] if grupo and grupo.variante_ids else None
            return arbol.modelo.data(actual.sibling(actual.row(), 0), Qt.ItemDataRole.UserRole)
        elegidas = arbol.variantes_elegidas()
        return elegidas[0] if elegidas else None

    def _al_elegir_en_arbol(self) -> None:
        if self._espejando:
            return
        arbol = self.prendas
        tallas_sueltas = [
            arbol.modelo.data(i, Qt.ItemDataRole.UserRole)
            for i in arbol.selectionModel().selectedRows(0)
            if not arbol.modelo.es_prenda(i)
        ]
        self._eleccion_arbol = (arbol.llaves_elegidas(), tallas_sueltas)
        self._espejar_a_tabla(arbol.variantes_elegidas(), self._actual_del_arbol())

    def _espejar_a_tabla(self, ids: list, actual: object | None) -> None:
        """Copia lo elegido en el árbol a la tabla escondida (con las tallas de la
        página): de ahí leen la ficha, la impresión y los ajustes de siempre."""
        w = self.window
        tabla = w.inventory_table
        modelo = tabla.model()
        renglones = {w._inventory_table_variant_id_at_row(r): r for r in range(tabla.rowCount())}
        seleccion = QItemSelection()
        ultima = max(0, tabla.columnCount() - 1)
        for variante in ids:
            renglon = renglones.get(variante)
            if renglon is not None:
                seleccion.select(modelo.index(renglon, 0), modelo.index(renglon, ultima))
        if actual not in renglones:
            actual = ids[0] if ids else None
        tabla.blockSignals(True)
        try:
            tabla.selectionModel().select(seleccion, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            renglon = renglones.get(actual)
            tabla.selectionModel().setCurrentIndex(
                modelo.index(renglon, 0) if renglon is not None else QModelIndex(),
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
        finally:
            tabla.blockSignals(False)
        combo = w.inventory_variant_combo
        if len(ids) == 1:
            # Una talla: la ficha de siempre (último movimiento incluido).
            w._set_combo_value(combo, ids[0])
        else:
            combo.blockSignals(True)
            try:
                if actual is None:
                    combo.setCurrentIndex(-1)
                else:
                    w._set_combo_value(combo, actual)
            finally:
                combo.blockSignals(False)
        self.actualizar_ficha()

    def quitar_seleccion(self) -> None:
        """«Quitar selección» (ficha o Esc) en cualquiera de las dos vistas."""
        self._eleccion_arbol = (set(), [])
        self._espejando = True
        try:
            self.prendas.selectionModel().clearSelection()
        finally:
            self._espejando = False
        self._llamar("_clear_inventory_table_selection")
        self.actualizar_ficha()

    # ── Ficha ────────────────────────────────────────────────────────────

    def actualizar_ficha(self) -> None:
        w = self.window
        elegidas = w._selected_inventory_variant_ids()
        if len(elegidas) > 1:
            self._mostrar_lote(elegidas)
            return
        variante_id = self.variante_actual()
        fila = self.fila_de(variante_id) if variante_id else None
        if fila is None:
            self._mostrar_vacia()
            return
        self._mostrar_talla(fila)

    def _mostrar_vacia(self) -> None:
        ficha = self.ficha
        urgentes = para_atender(self.filas_base)
        ids = [fila.get("variante_id") for fila in urgentes]
        if ids != ficha.atender_ids:
            for fila_vieja in ficha.atender_botones:
                ficha.atender_caja.removeWidget(fila_vieja)
                fila_vieja.hide()
                fila_vieja.setParent(None)
                fila_vieja.deleteLater()
            ficha.atender_botones = []
            ficha.atender_ids = ids
            for fila in urgentes:
                nueva = FilaAtender(
                    fila.get("variante_id"),
                    str(fila.get("producto_nombre_base") or fila.get("producto_nombre") or ""),
                    texto_talla_color(fila),
                    motivo_para_atender(fila),
                    "danger" if int(fila.get("stock_actual") or 0) < 0 else "muted",
                    f"Código {fila.get('sku', '')}",
                )
                nueva.tocada.connect(self.seleccionar)
                ficha.atender_caja.addWidget(nueva)
                ficha.atender_botones.append(nueva)
        if urgentes:
            ficha.atender_nota.setText("Lo más urgente de lo que estás viendo. Toca una para abrir su ficha.")
        else:
            ficha.atender_nota.setText("Nada en negativo ni agotado en lo que estás viendo.")
        ficha.paginas.setCurrentIndex(VACIA)

    def _mostrar_talla(self, fila: Mapping[str, object]) -> None:
        ficha = self.ficha
        stock = int(fila.get("stock_actual") or 0)
        virtual = es_fila_virtual(fila)
        ficha.nombre.setText(str(fila.get("producto_nombre_base") or fila.get("producto_nombre") or ""))
        ficha.sub.setText(f"{texto_talla_color(fila)} · {fila.get('sku', '')}")
        ficha.hay.setText(f"−{abs(stock)}" if stock < 0 else str(stock))
        ficha.hay_nota.setText("conjunto: sale de sus piezas" if virtual else ("pieza" if stock == 1 else "piezas"))
        precio = precio_efectivo(fila)
        ficha.precio.setText(fmt_corto(precio) if precio not in (None, "") else "—")
        ficha.precio_nota.setText(_nota_precio(fila))
        tono, texto = _estado_existencia(fila, self.ahora())
        ficha.chip_estado.setText(texto)
        ficha.chip_estado.setProperty("tono", tono)
        ficha.chip_estado.setVisible(bool(texto))
        _repulir(ficha.chip_estado)
        ficha.chip_apagada.setVisible(not bool(fila.get("variante_activa", True)))
        ficha.donde.setText(
            texto_donde_completo(
                stock, int(fila.get("stock_bodega") or 0), int(fila.get("stock_piso") or 0), conjunto=virtual
            )
        )
        ficha.contada.setText(texto_contada_corto(fila, ahora=self.ahora()))
        sku, movimiento = self._ultimo_mov
        if sku == str(fila.get("sku", "")) and movimiento:
            ficha.movimiento.setText(movimiento.replace("Último movimiento: ", ""))
        else:
            ficha.movimiento.setText("—")
        self._habilitar_acciones()
        ficha.paginas.setCurrentIndex(TALLA)

    def _mostrar_lote(self, elegidas: list) -> None:
        ids = set(elegidas)
        filas = [f for f in self.window.inventory_filtered_rows if f.get("variante_id") in ids]
        resumen = resumir_lote(filas) if filas else resumir_lote({"stock_actual": 0} for _ in elegidas)
        self.ficha.lote_total.setText(resumen.texto)
        self.boton_lote_etiquetas.setText(
            f"🏷  Imprimir {len(elegidas):,} {'etiqueta' if len(elegidas) == 1 else 'etiquetas'}"
        )
        self._habilitar_acciones()
        self.ficha.paginas.setCurrentIndex(LOTE)

    def _habilitar_acciones(self) -> None:
        w = self.window
        admin = w.inventory_more_button.isEnabled()
        for boton in (
            self.boton_corregir,
            self.boton_editar,
            self.boton_lote_existencias,
            self.boton_lote_precio,
        ):
            boton.setEnabled(admin)
        self.boton_lote_etiquetas.setEnabled(w.inventory_print_label_button.isEnabled())
        self.boton_movimientos.setEnabled(admin and _indice_pestana(w, "Historial inventarios") is not None)

    def _armar_acciones_ficha(self) -> None:
        w = self.window
        ficha = self.ficha
        self.boton_corregir = boton_accion("🧮  Corregir existencia", "Corregir a mano cuántas hay, con su motivo")
        self.boton_corregir.clicked.connect(lambda: self._llamar("_handle_inventory_adjustment"))
        w.inventory_print_label_button.setObjectName("invAccion")
        w.inventory_print_label_button.setText("🏷  Imprimir etiqueta")
        self.boton_editar = boton_accion("✏️  Editar", "Cambiar código, talla, color o precio de esta talla")
        self.boton_editar.clicked.connect(lambda: self._llamar("_handle_update_variant"))
        self.boton_movimientos = boton_accion("📜  Ver movimientos", "Abre Historial inventarios con esta talla")
        self.boton_movimientos.clicked.connect(self.ver_movimientos)
        ficha.acciones.addWidget(self.boton_corregir, 0, 0)
        ficha.acciones.addWidget(w.inventory_print_label_button, 0, 1)
        ficha.acciones.addWidget(self.boton_editar, 1, 0)
        ficha.acciones.addWidget(self.boton_movimientos, 1, 1)

        menu = QMenu(ficha.mas)
        menu.setObjectName("invMenu")
        _accion(menu, "✏️  Editar la prenda", lambda: self._llamar("_handle_update_product"))
        _accion(menu, "📷  Foto del modelo", lambda: self._llamar("_handle_product_photo"))
        _accion(menu, "⧉  Duplicar esta talla", lambda: self._llamar("_handle_duplicate_variant"))
        _accion(menu, "📦  Registrar entrada", lambda: self._llamar("_handle_purchase"))
        menu.addSeparator()
        # El texto y el permiso salen de los botones de siempre (dicen «Activar…» si ya está apagada).
        self.accion_talla = _accion(menu, w.toggle_variant_button.text(), lambda: self._llamar("_handle_toggle_variant"))
        self.accion_prenda = _accion(menu, w.toggle_product_button.text(), lambda: self._llamar("_handle_toggle_product"))
        menu.aboutToShow.connect(self._sincronizar_desactivar)
        ficha.mas.setMenu(menu)
        self.menu_ficha = menu

        self.boton_lote_etiquetas = boton_accion("🏷  Imprimir etiquetas", "Imprime la etiqueta de cada talla elegida")
        self.boton_lote_etiquetas.clicked.connect(self.imprimir_elegidas)
        self.boton_lote_existencias = boton_accion(
            "🧮  Corregir existencias en lote", "Corregir cuántas hay de varias tallas a la vez"
        )
        self.boton_lote_existencias.clicked.connect(lambda: self._llamar("_handle_inventory_bulk_adjustment"))
        self.boton_lote_precio = boton_accion("💲  Cambiar precio", "Cambiar el precio de las tallas elegidas")
        self.boton_lote_precio.clicked.connect(lambda: self._llamar("_handle_inventory_bulk_price_update"))
        self.boton_lote_quitar = boton_accion("✕  Quitar la selección")
        self.boton_lote_quitar.clicked.connect(self.quitar_seleccion)
        for boton in (
            self.boton_lote_etiquetas,
            self.boton_lote_existencias,
            self.boton_lote_precio,
            self.boton_lote_quitar,
        ):
            ficha.lote_acciones.addWidget(boton)

    def _sincronizar_desactivar(self) -> None:
        w = self.window
        self.accion_talla.setText(w.toggle_variant_button.text())
        self.accion_talla.setEnabled(w.toggle_variant_button.isEnabled())
        self.accion_prenda.setText(w.toggle_product_button.text())
        self.accion_prenda.setEnabled(w.toggle_product_button.isEnabled())

    def _llamar(self, nombre: str) -> None:
        getattr(self.window, nombre)()

    # ── Acciones con su cuidado ──────────────────────────────────────────

    def ver_movimientos(self) -> None:
        w = self.window
        fila = self.fila_de(self.variante_actual())
        indice = _indice_pestana(w, "Historial inventarios")
        if fila is None or indice is None:
            return
        # Filtros de Historial limpios (como su «Quitar filtros»), con solo el código:
        # un rango «Hoy» o un tipo «Ajuste» olvidados no deben esconder la historia.
        limpio = build_history_clear_filter_state(w.history_from_input.minimumDate().toPyDate())
        widgets = (w.history_source_combo, w.history_entity_combo, w.history_type_combo,
                   w.history_from_input, w.history_to_input, w.history_sku_input)
        for widget in widgets:
            widget.blockSignals(True)
        try:
            w.history_source_combo.setCurrentIndex(limpio.source_index)
            w.history_entity_combo.setCurrentIndex(limpio.entity_index)
            w.history_type_combo.setCurrentIndex(limpio.type_index)
            w.history_from_input.setDate(limpio.from_date)
            w.history_to_input.setDate(limpio.to_date)
            w.history_sku_input.setText(str(fila.get("sku", "")))
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        w._handle_history_filter()
        w.tabs.setCurrentIndex(indice)

    def imprimir_elegidas(self) -> None:
        cantidad = len(self.window._selected_inventory_variant_ids())
        if self._puede_imprimir(cantidad, todo_lo_filtrado=False):
            self._llamar("_handle_inventory_print_label")

    def imprimir_filtrado(self) -> None:
        cantidad = len(self.window.inventory_filtered_rows)
        if self._puede_imprimir(cantidad, todo_lo_filtrado=True):
            self._llamar("_handle_inventory_print_visible_labels")

    def _puede_imprimir(self, cantidad: int, *, todo_lo_filtrado: bool) -> bool:
        decision = decidir_impresion_lote(cantidad, hay_filtro=self.hay_filtro(), todo_lo_filtrado=todo_lo_filtrado)
        if decision == NADA:
            return True  # el manejador de siempre dice que no hay nada elegido
        if decision == BLOQUEAR:
            QMessageBox.information(
                self.window,
                "Pon un filtro primero",
                "Sin ningún filtro serían las etiquetas de todo el inventario. "
                "Elige una escuela, prenda o tarjeta y vuelve a intentarlo.",
            )
            return False
        if decision == CONFIRMAR:
            respuesta = QMessageBox.question(
                self.window,
                "Muchas etiquetas",
                f"Vas a preparar {cantidad:,} etiquetas (más de {UMBRAL_CONFIRMAR_ETIQUETAS}). ¿Seguimos?",
            )
            return respuesta == QMessageBox.StandardButton.Yes
        return True

    def eliminar(self, que: str) -> None:
        """«Eliminar» con confirmación fuerte: hay que escribir el nombre (o el código de la talla).

        El manejador de siempre borra la fila ACTUAL de la tabla, así que la
        confirmación se pide sobre esa misma fila y nunca se le llama sin ella.
        """
        w = self.window
        manejador = "_handle_delete_product" if que == "prenda" else "_handle_delete_variant"
        titulo = "Eliminar toda la prenda" if que == "prenda" else "Eliminar esta talla"
        if len(w._selected_inventory_variant_ids()) > 1:
            QMessageBox.information(w, titulo, "Elige una sola talla para eliminar.")
            return
        objetivo = w._inventory_table_variant_id_at_row(w.inventory_table.currentRow())
        if objetivo is None:
            QMessageBox.information(w, titulo, "Elige primero la talla en la lista.")
            return
        fila = self.fila_de(objetivo) or w._selected_catalog_row()
        if fila is None:
            QMessageBox.information(w, titulo, "Elige primero la talla en la lista.")
            return
        if que == "prenda":
            esperado = str(fila.get("producto_nombre_base") or fila.get("producto_nombre") or "")
            texto = (
                f"Esto borra para siempre «{esperado}» con todas sus tallas.\n"
                "Si solo quieres que no se venda, mejor desactívala.\n\n"
                "Para confirmar, escribe el nombre de la prenda:"
            )
        else:
            esperado = str(fila.get("sku") or "")
            texto = (
                f"Esto borra para siempre la talla {fila.get('talla', '')} de «{fila.get('producto_nombre_base') or fila.get('producto_nombre', '')}».\n"
                "Si solo quieres que no se venda, mejor desactívala.\n\n"
                f"Para confirmar, escribe su código ({esperado}):"
            )
        escrito, aceptado = QInputDialog.getText(self.window, titulo, texto)
        if not aceptado:
            return
        if not confirmacion_coincide(escrito, esperado):
            QMessageBox.information(self.window, titulo, "No coincide con lo escrito; no se borró nada.")
            return
        self._llamar(manejador)


# ── Menú «⋯» del encabezado ──────────────────────────────────────────────


def _accion(menu: QMenu, texto: str, alHacer: Callable[[], object], aviso: str = ""):
    accion = menu.addAction(texto)
    if aviso:
        accion.setToolTip(aviso)
    accion.triggered.connect(lambda _=False: alHacer())
    return accion


def _submenu(menu: QMenu, titulo: str) -> QMenu:
    sub = menu.addMenu(titulo)
    sub.setObjectName("invMenu")
    sub.setToolTipsVisible(True)
    return sub


def _accion_peligro(menu: QMenu, texto: str, alHacer: Callable[[], object], aviso: str) -> QWidgetAction:
    """Renglón en rojo al final del menú (QMenu no colorea acciones sueltas)."""
    accion = QWidgetAction(menu)
    accion.setText(texto)
    accion.setToolTip(aviso)
    boton = QPushButton(texto)
    boton.setObjectName("invMenuPeligro")
    boton.setToolTip(aviso)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    boton.setStyleSheet(
        "QPushButton#invMenuPeligro { background: transparent; color: #b3261e; border: none; border-radius: 8px;"
        " text-align: left; padding: 9px 22px 9px 14px; font-size: 14px; font-weight: 700; }"
        "QPushButton#invMenuPeligro:hover { background: #fef0ee; }"
    )

    def hacer() -> None:
        menu.close()
        alHacer()

    boton.clicked.connect(hacer)
    accion.setDefaultWidget(boton)
    accion.triggered.connect(lambda _=False: alHacer())
    menu.addAction(accion)
    return accion


def armar_menu_mas(window: "MainWindow", pantalla: InventarioPantalla) -> QMenu:
    """Todo lo de los menús viejos Nuevo/Editar/Existencias/Etiquetas/Más, agrupado."""

    def llamar(nombre: str) -> Callable[[], object]:
        return lambda: getattr(window, nombre)()

    def disparar(nombre: str) -> Callable[[], object]:
        return lambda: getattr(window, nombre).trigger()

    menu = QMenu(window.inventory_more_button)
    menu.setObjectName("invMenu")
    menu.setToolTipsVisible(True)
    _accion(menu, "➕  Agregar talla o color", llamar("_handle_create_variant"),
            "Agregar una talla o color (con su precio) a una prenda que ya existe")
    _accion(menu, "⧉  Duplicar la talla elegida", llamar("_handle_duplicate_variant"),
            "Usar la talla elegida como base para crear otra")
    _accion(menu, "✏️  Editar la talla elegida", llamar("_handle_update_variant"),
            "Cambiar código, talla, color o precio de la talla elegida")
    _accion(menu, "✏️  Editar la prenda elegida", llamar("_handle_update_product"),
            "Cambiar nombre, escuela, marca o tipo de la prenda elegida")
    _accion(menu, "📷  Foto del modelo", llamar("_handle_product_photo"),
            "Tomar con la webcam (o elegir archivo) la foto que sale en el kiosko")
    menu.addSeparator()

    existencias = _submenu(menu, "📦  Existencias")
    _accion(existencias, "Registrar entrada", llamar("_handle_purchase"), "Sumar la mercancía que llegó del proveedor")
    _accion(existencias, "Corregir existencia", llamar("_handle_inventory_adjustment"),
            "Corregir a mano cuántas hay de una talla, con su motivo")
    _accion(existencias, "Ajuste en lote", llamar("_handle_inventory_bulk_adjustment"),
            "Corregir la existencia de varias tallas a la vez")
    _accion(existencias, "Conteo físico", llamar("_handle_inventory_count"),
            "Contar las piezas y corregir las diferencias contra lo que dice el sistema")

    precios = _submenu(menu, "💲  Precios")
    _accion(precios, "Precios en lote", llamar("_handle_inventory_bulk_price_update"),
            "Cambiar el precio de varias tallas a la vez")
    _accion(precios, "Ofertas y liquidación…", llamar("_handle_open_rebajas"),
            "Poner prendas en Oferta o Liquidación: no se les suma ningún otro descuento")

    etiquetas = _submenu(menu, "🏷  Etiquetas")
    _accion(etiquetas, "Imprimir las elegidas", pantalla.imprimir_elegidas,
            "Imprimir la etiqueta de las tallas elegidas en la lista")
    _accion(etiquetas, "Imprimir todo lo filtrado", pantalla.imprimir_filtrado,
            f"Todas las tallas que quedan con los filtros puestos (más de {UMBRAL_CONFIRMAR_ETIQUETAS} pide confirmar)")

    poco = _submenu(menu, "🗂  Poco usado")
    _accion(poco, "Categoría nueva", llamar("_handle_create_category"), "Crear una categoría (p. ej. Uniformes, Accesorios)")
    _accion(poco, "Marca nueva", llamar("_handle_create_brand"), "Crear una marca (p. ej. Fertoni, Ykan)")
    poco.addSeparator()
    _accion(poco, "Calendario de conteos", disparar("conteo_calendario_action"), "Qué escuela toca contar cada día")
    _accion(poco, "Mercancía por nombrar", disparar("por_nombrar_action"), "Lo que llegó sin nombre todavía")
    poco.addSeparator()
    _accion(poco, "Generar QR de la selección", llamar("_handle_generate_all_qr"),
            "Guarda el QR de las tallas elegidas (la etiqueta ya lo hace sola)")
    _accion(poco, "Generar los QR que faltan", llamar("_handle_generate_missing_qr"),
            "Guarda el QR de las tallas activas que aún no lo tienen en esta computadora")
    _accion(poco, "Regenerar todos los QR", llamar("_handle_regenerate_all_qr"),
            "Vuelve a crear el QR de todas las tallas activas (reemplaza los guardados)")

    menu.addSeparator()
    _accion_peligro(menu, "🗑  Eliminar la talla elegida…", lambda: pantalla.eliminar("talla"),
                    "Borrar para siempre la talla elegida (solo si nunca se movió). Pide escribir su código.")
    _accion_peligro(menu, "🗑  Eliminar toda la prenda…", lambda: pantalla.eliminar("prenda"),
                    "Borrar para siempre la prenda y todas sus tallas (solo si nunca se movió). Pide escribir su nombre.")
    return menu


# ── Utilidades ───────────────────────────────────────────────────────────


def _tamano_pagina() -> int:
    from pos_uniformes.ui import main_window

    return int(main_window.INVENTORY_PAGE_SIZE)


def _indice(filas, variante_id: object) -> int | None:
    for indice, fila in enumerate(filas):
        if fila.get("variante_id") == variante_id:
            return indice
    return None


def _indice_pestana(window, titulo: str) -> int | None:
    tabs = getattr(window, "tabs", None)
    if tabs is None:
        return None
    for indice in range(tabs.count()):
        if tabs.tabText(indice).strip() == titulo:
            return indice if tabs.isTabVisible(indice) else None
    return None


def _nota_precio(fila: Mapping[str, object]) -> str:
    """«Oferta · antes $289» con rebaja vigente; si no, «precio de venta»."""
    tipo = fila.get(LLAVE_TIPO)
    normal = fila.get("precio_venta")
    if tipo and fila.get(LLAVE_PRECIO) is not None and normal not in (None, ""):
        return f"{ETIQUETAS_REBAJA.get(str(tipo), str(tipo))} · antes {fmt_corto(normal)}"
    return "precio de venta"


def _estado_existencia(fila: Mapping[str, object], ahora: datetime) -> tuple[str, str]:
    for llave in (EN_NEGATIVO, SE_ACABO, QUEDAN_POCAS):
        if en_tarjeta(fila, llave, ahora=ahora):
            info = INFO_TARJETAS[llave]
            return info.tono, info.titulo
    return "", ""
