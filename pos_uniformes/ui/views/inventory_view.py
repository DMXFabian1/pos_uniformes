"""Vista principal de la pestaña Inventario (tanda 3, «Cara nueva»)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from pos_uniformes.ui.helpers.flow_layout import FlowLayout
from pos_uniformes.ui.helpers.inventario_pantalla import (
    TEXTO_PROXIMAMENTE,
    InventarioPantalla,
    armar_menu_mas,
)
from pos_uniformes.ui.helpers.inventario_tabla_helper import ALTO_FILA
from pos_uniformes.ui.helpers.inventory_help_texts import AYUDA_IMPRIMIR_ETIQUETA
from pos_uniformes.ui.helpers.inventory_table_row_helper import INVENTORY_TABLE_HEADERS
from pos_uniformes.ui.helpers.inventory_toggle_helper import etiqueta_boton_prenda, etiqueta_boton_talla
from pos_uniformes.ui.styles.inventario_styles import build_inventario_stylesheet, sombra

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_inventory_tab(window: "MainWindow") -> QWidget:
    """Cara nueva (tanda 3): a la izquierda se trabaja, a la derecha la ficha.

    Arriba, en todo el ancho: título con lo que estás viendo, el buscador
    grande, «＋ Nueva prenda» y «⋯». Debajo, a la izquierda, las cuatro
    tarjetas que filtran, los filtros y la lista; a la derecha, la ficha.
    Un solo scroll: la pestaña es su propio QScrollArea (la ventana no la
    vuelve a envolver) y a 1366×768 cabe sin desplazarse; solo la lista
    desplaza sus filas.
    """
    pantalla = InventarioPantalla(window)
    window.inventario_pantalla = pantalla

    scroll = QScrollArea()
    scroll.setObjectName("invScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    raiz = _RaizInventario()
    raiz.setObjectName("invRaiz")
    raiz.setStyleSheet(build_inventario_stylesheet())
    layout = QVBoxLayout(raiz)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(12)

    _preparar_botones_viejos(window)
    layout.addLayout(_encabezado(window, pantalla))

    cuerpo = QHBoxLayout()
    cuerpo.setSpacing(14)
    izquierda = QVBoxLayout()
    izquierda.setSpacing(10)
    tarjetas = QHBoxLayout()
    tarjetas.setSpacing(10)
    for tarjeta in pantalla.tarjetas.values():
        tarjetas.addWidget(tarjeta)
    izquierda.addLayout(tarjetas)
    _filtros(window, pantalla, izquierda)
    izquierda.addWidget(_tabla(window, pantalla), 1)
    cuerpo.addLayout(izquierda, 1)
    cuerpo.addWidget(pantalla.ficha)
    layout.addLayout(cuerpo, 1)

    window.inventory_variant_combo.currentIndexChanged.connect(window._refresh_inventory_selection_panel)
    scroll.setWidget(raiz)
    return scroll


class _RaizInventario(QWidget):
    """Raíz de la pestaña. No pide alto según su ancho: así el scroll de la
    pestaña solo aparece si no caben los MÍNIMOS (lista de 120 px), no los
    tamaños preferidos; lo normal es que solo la lista desplace sus filas."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - API de Qt
        return False

    def heightForWidth(self, _ancho: int) -> int:  # noqa: N802 - QScrollArea la consulta directo
        return -1


def _preparar_botones_viejos(window: "MainWindow") -> None:
    """Los botones de antes siguen vivos (permisos y pruebas los usan), pero no
    van en ningún layout: sus funciones están en «⋯» y en la ficha."""
    window.catalog_selection_label.setObjectName("analyticsLine")
    window.inventory_permission_label.setObjectName("catalogSectionHint")
    for widget in (
        window.catalog_selection_label,
        window.inventory_edit_button,
        window.inventory_stock_button,
        window.inventory_labels_button,
        window.inventory_bulk_adjust_button,
        window.inventory_bulk_price_button,
        window.inventory_pagination_label,
        window.inventory_results_label,
        window.inventory_negative_counter,
        window.inventory_out_counter,
        window.inventory_low_counter,
        window.inventory_inactive_counter,
        window.inventory_overview_label,
        window.inventory_product_label,
        window.inventory_status_badge,
        window.inventory_stock_badge,
        window.inventory_stock_hint_label,
        window.inventory_meta_label,
        window.inventory_last_movement_label,
        window.toggle_product_button,
        window.toggle_variant_button,
    ):
        widget.setVisible(False)
    window.toggle_product_button.setText(etiqueta_boton_prenda(True))
    window.toggle_variant_button.setText(etiqueta_boton_talla(True))
    window.delete_product_button.setText("Eliminar prenda")
    window.delete_variant_button.setText("Eliminar talla")
    window.purchase_button.setText("Registrar entrada")
    window.inventory_count_button.setText("Conteo físico")
    window.inventory_adjust_button.setText("Corregir existencia")
    window.inventory_bulk_adjust_button.setText("Ajuste en lote")
    window.inventory_bulk_price_button.setText("Precios en lote")
    window.inventory_generate_all_qr_button.setText("Generar QR de la selección")
    window.toggle_product_button.clicked.connect(window._handle_toggle_product)
    window.toggle_variant_button.clicked.connect(window._handle_toggle_variant)
    window.delete_product_button.clicked.connect(window._handle_delete_product)
    window.delete_variant_button.clicked.connect(window._handle_delete_variant)
    window.purchase_button.clicked.connect(window._handle_purchase)
    window.inventory_count_button.clicked.connect(window._handle_inventory_count)
    window.inventory_adjust_button.clicked.connect(window._handle_inventory_adjustment)
    window.inventory_bulk_adjust_button.clicked.connect(window._handle_inventory_bulk_adjustment)
    window.inventory_bulk_price_button.clicked.connect(window._handle_inventory_bulk_price_update)
    window.inventory_generate_all_qr_button.clicked.connect(window._handle_generate_all_qr)
    window.inventory_print_label_button.clicked.connect(window._handle_inventory_print_label)
    window.inventory_print_label_button.setToolTip(AYUDA_IMPRIMIR_ETIQUETA)


def _encabezado(window: "MainWindow", pantalla: InventarioPantalla) -> QHBoxLayout:
    fila = QHBoxLayout()
    fila.setSpacing(12)
    titulos = QVBoxLayout()
    titulos.setSpacing(0)
    titulo = QLabel("Inventario")
    titulo.setObjectName("invTitulo")
    titulos.addWidget(titulo)
    titulos.addWidget(pantalla.subtitulo)
    fila.addLayout(titulos)
    fila.addSpacing(8)

    busqueda = QVBoxLayout()
    busqueda.setSpacing(2)
    barra = QFrame()
    barra.setObjectName("invBuscador")
    sombra(barra)
    caja = QHBoxLayout(barra)
    caja.setContentsMargins(16, 2, 10, 2)
    caja.setSpacing(8)
    icono = QLabel("⌕")
    icono.setObjectName("invBuscadorIcono")
    caja.addWidget(icono)
    entrada = window.inventory_search_input
    entrada.setObjectName("invBuscar")
    entrada.setPlaceholderText("Busca o escanea: prenda, escuela, talla, color o código")
    entrada.setClearButtonEnabled(True)
    caja.addWidget(entrada, 1)
    busqueda.addWidget(barra)
    busqueda.addWidget(pantalla.aviso_busqueda)
    fila.addLayout(busqueda, 1)
    entrada.textChanged.connect(lambda _: window._schedule_inventory_filter_refresh_reset_page())
    entrada.returnPressed.connect(window._handle_inventory_filters_changed_reset_page)

    nueva = window.inventory_new_button
    nueva.setObjectName("invNueva")
    nueva.setText("＋ Nueva prenda")
    nueva.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    nueva.setCursor(Qt.CursorShape.PointingHandCursor)
    nueva.clicked.connect(lambda: window._handle_create_product())
    fila.addWidget(nueva)

    mas = window.inventory_more_button
    mas.setObjectName("invMas")
    mas.setText("⋯")
    mas.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    mas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    mas.setMenu(armar_menu_mas(window, pantalla))
    fila.addWidget(mas)
    return fila


def _filtros(window: "MainWindow", pantalla: InventarioPantalla, layout: QVBoxLayout) -> None:
    """A la vista: Escuela, Prenda, Talla y Color. Lo demás, en «Más filtros (n)»."""
    window.inventory_category_filter_combo.hide()
    fila = QHBoxLayout()
    fila.setSpacing(8)
    for filtro in (
        window.inventory_school_filter_combo,
        window.inventory_piece_filter_combo,
        window.inventory_size_filter_combo,
        window.inventory_color_filter_combo,
    ):
        filtro.setObjectName("invFiltro")
        fila.addWidget(filtro)
    fila.addWidget(pantalla.mas_filtros)
    quitar = window.inventory_clear_filters_button
    quitar.setObjectName("invQuitar")
    quitar.setText("Quitar filtros")
    quitar.setCursor(Qt.CursorShape.PointingHandCursor)
    quitar.setVisible(False)
    # La tarjeta tocada se apaga ANTES de que la ventana limpie y refresque.
    quitar.clicked.connect(pantalla.quitar_tarjeta)
    quitar.clicked.connect(window._handle_clear_inventory_filters)
    fila.addWidget(quitar)
    fila.addStretch(1)
    layout.addLayout(fila)

    _llenar_combos(window)
    panel = pantalla.mas_filtros_panel
    panel_layout = FlowLayout(margin=10, h_spacing=8, v_spacing=8)
    for filtro in (window.inventory_brand_filter_combo, window.inventory_type_filter_combo):
        filtro.setObjectName("invFiltroMas")
        panel_layout.addWidget(filtro)
    for combo in (
        window.inventory_use_filter_combo,
        window.inventory_status_filter_combo,
        window.inventory_stock_filter_combo,
        window.inventory_precio_filter_combo,
        window.inventory_conteo_filter_combo,
    ):
        combo.setObjectName("invCombo")
        panel_layout.addWidget(combo)
    window.inventory_precio_text_input.setObjectName("invPrecioExacto")
    window.inventory_precio_text_input.setPlaceholderText("Precio exacto $")
    window.inventory_precio_text_input.setFixedWidth(130)
    panel_layout.addWidget(window.inventory_precio_text_input)
    panel.setLayout(panel_layout)
    layout.addWidget(panel)

    window.inventory_active_filters_wrap.setObjectName("invChips")
    window.inventory_active_filters_wrap.setVisible(False)
    window.inventory_active_filters_flow_layout = FlowLayout(
        window.inventory_active_filters_wrap, margin=0, h_spacing=6, v_spacing=6
    )
    window.inventory_active_filters_wrap.setLayout(window.inventory_active_filters_flow_layout)
    layout.addWidget(window.inventory_active_filters_wrap)

    cambio = window._handle_inventory_filters_changed_reset_page
    for filtro in (
        window.inventory_category_filter_combo,
        window.inventory_brand_filter_combo,
        window.inventory_school_filter_combo,
        window.inventory_type_filter_combo,
        window.inventory_piece_filter_combo,
        window.inventory_size_filter_combo,
        window.inventory_color_filter_combo,
    ):
        filtro.selectionChanged.connect(cambio)
    for combo in (
        window.inventory_use_filter_combo,
        window.inventory_status_filter_combo,
        window.inventory_stock_filter_combo,
        window.inventory_conteo_filter_combo,
        window.inventory_precio_filter_combo,
    ):
        combo.currentIndexChanged.connect(lambda _: cambio())
    window.inventory_precio_text_input.textChanged.connect(
        lambda _: window._schedule_inventory_filter_refresh_reset_page()
    )


def _llenar_combos(window: "MainWindow") -> None:
    opciones = (
        (
            window.inventory_use_filter_combo,
            (("Ropa: toda", ""), ("Uniforme escolar", "school_only"), ("Ropa normal", "general_only")),
        ),
        (
            window.inventory_status_filter_combo,
            (("Estado: todas", ""), ("Activas", "active"), ("Desactivadas", "inactive")),
        ),
        (
            window.inventory_stock_filter_combo,
            (
                ("Hay: todas", ""),
                ("En negativo", "negative"),
                ("Agotadas", "zero"),
                ("Quedan pocas", "low"),
                ("Sí hay", "available"),
                ("Bajo el mínimo", "below_min"),
            ),
        ),
        (
            window.inventory_precio_filter_combo,
            (
                ("Precio: todos", ""),
                ("Hasta $99", "under_100"),
                ("$100 – $199", "100_199"),
                ("$200 – $499", "200_499"),
                ("$500+", "500_plus"),
            ),
        ),
        (
            window.inventory_conteo_filter_combo,
            (
                ("Contada: todas", ""),
                ("Nunca contada", "never"),
                ("Hace 0 a 3 días", "recent"),
                ("Hace 8 días o más", "stale"),
            ),
        ),
    )
    for combo, items in opciones:
        combo.clear()
        for texto, dato in items:
            combo.addItem(texto, dato)


def _tabla(window: "MainWindow", pantalla: InventarioPantalla) -> QFrame:
    tabla = window.inventory_table
    tabla.setColumnCount(len(INVENTORY_TABLE_HEADERS))
    tabla.setHorizontalHeaderLabels(list(INVENTORY_TABLE_HEADERS))
    # «Hay» va a la derecha, igual que sus números.
    tabla.horizontalHeaderItem(INVENTORY_TABLE_HEADERS.index("Hay")).setTextAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    tabla.setObjectName("invTabla")
    tabla.verticalHeader().setVisible(False)
    tabla.verticalHeader().setDefaultSectionSize(ALTO_FILA)
    tabla.setShowGrid(False)
    tabla.setAlternatingRowColors(False)
    tabla.setFrameShape(QFrame.Shape.NoFrame)
    tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabla.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    tabla.setMinimumHeight(120)
    encabezado = tabla.horizontalHeader()
    encabezado.setHighlightSections(False)
    encabezado.setSectionsClickable(True)
    encabezado.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for columna, titulo in enumerate(INVENTORY_TABLE_HEADERS):
        encabezado.setSectionResizeMode(
            columna,
            QHeaderView.ResizeMode.Stretch if titulo == "Prenda" else QHeaderView.ResizeMode.ResizeToContents,
        )
    encabezado.setStretchLastSection(False)
    encabezado.sectionClicked.connect(pantalla.tocar_encabezado)
    tabla.setToolTip(
        "Toca el encabezado para ordenar. Ctrl/Cmd + clic para elegir varias; Shift para un rango; Esc para soltar."
    )
    tabla.itemSelectionChanged.connect(window._handle_inventory_table_selection)
    tabla.itemSelectionChanged.connect(pantalla.actualizar_ficha)
    tabla.currentCellChanged.connect(lambda *_: window._handle_inventory_table_selection())
    tabla.itemDoubleClicked.connect(window._handle_inventory_table_double_click)
    tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tabla.customContextMenuRequested.connect(window._show_inventory_context_menu)
    soltar = QShortcut(QKeySequence(Qt.Key.Key_Escape), tabla)
    soltar.setContext(Qt.ShortcutContext.WidgetShortcut)
    soltar.activated.connect(window._clear_inventory_table_selection)

    tarjeta = QFrame()
    tarjeta.setObjectName("invTablaCard")
    sombra(tarjeta)
    caja = QVBoxLayout(tarjeta)
    caja.setContentsMargins(10, 8, 10, 8)
    caja.setSpacing(6)
    caja.addWidget(tabla, 1)

    pie = QHBoxLayout()
    pie.setSpacing(6)
    # Segmento de vistas: «Por prenda» llega en la tanda 4. Se apaga, no se
    # esconde (norma del POS), y dice por qué al pasar el mouse.
    por_talla = QPushButton("Por talla")
    por_talla.setObjectName("invSegmento")
    por_talla.setProperty("lado", "izq")
    por_talla.setCheckable(True)
    por_talla.setChecked(True)
    por_talla.setToolTip("Una fila por cada talla")
    por_prenda = QPushButton("Por prenda")
    por_prenda.setObjectName("invSegmento")
    por_prenda.setProperty("lado", "der")
    por_prenda.setEnabled(False)
    por_prenda.setToolTip(TEXTO_PROXIMAMENTE)
    pantalla.segmento = (por_talla, por_prenda)
    pie.addWidget(por_talla)
    pie.addWidget(por_prenda)
    pie.addStretch(1)
    pie.addWidget(pantalla.paginas)
    anterior = window.inventory_previous_page_button
    siguiente = window.inventory_next_page_button
    for boton, texto, aviso in ((anterior, "◀", "Página anterior"), (siguiente, "▶", "Página siguiente")):
        boton.setObjectName("invFlecha")
        boton.setText(texto)
        boton.setToolTip(aviso)
        pie.addWidget(boton)
    anterior.clicked.connect(window._handle_inventory_previous_page)
    siguiente.clicked.connect(window._handle_inventory_next_page)
    caja.addLayout(pie)
    return tarjeta
