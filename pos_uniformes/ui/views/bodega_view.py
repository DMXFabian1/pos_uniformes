"""Vista principal de la pestaña Bodega — cajas, búsqueda, detalle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select as sa_select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    CATEGORIA_CAJA_LABELS,
    BodegaCaja,
    BodegaUbicacion,
    CategoriaCaja,
    EstadoCaja,
    Variante,
)
from pos_uniformes.services.bodega_service import BodegaService

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow

CATEGORIA_COLORS: dict[str, str] = {
    "A": "#2e7d32",
    "B": "#1565c0",
    "C": "#e65100",
    "D": "#616161",
}

# ── Estilos compartidos ───────────────────────────────────────────────────────

_TABLE_STYLE = """
    QTableWidget {
        border: 1px solid #D5CEC9;
        border-radius: 6px;
        gridline-color: #EDE8E5;
        background: white;
        alternate-background-color: #FAF7F5;
        selection-background-color: #FDEAE2;
        selection-color: #2C1810;
        font-size: 12px;
        outline: 0;
    }
    QTableWidget::item { padding: 5px 8px; }
    QHeaderView::section {
        background: #F0EBE6;
        border: none;
        border-bottom: 2px solid #C9B9AE;
        border-right: 1px solid #DDD7D3;
        padding: 6px 8px;
        font-weight: bold;
        font-size: 11px;
        color: #4A3728;
    }
    QHeaderView::section:last-of-type { border-right: none; }
    QScrollBar:vertical { width: 8px; background: #F5F2F0; border-radius: 4px; }
    QScrollBar::handle:vertical { background: #C9B9AE; border-radius: 4px; min-height: 20px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

_GROUPBOX_STYLE = """
    QGroupBox {
        font-weight: bold;
        font-size: 12px;
        color: #4A3728;
        border: 1px solid #D5CEC9;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 4px;
        background: white;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        background: white;
    }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #B03A2E;
        border: none;
        border-radius: 6px;
        padding: 6px 18px;
        font-size: 12px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover { background: #992D23; }
    QPushButton:pressed { background: #7D2218; }
    QPushButton:disabled { background: #D5C5C2; color: #A08880; }
"""

_BTN_SUCCESS = """
    QPushButton {
        background: #1E6B3A;
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover { background: #185830; }
    QPushButton:pressed { background: #124524; }
    QPushButton:disabled { background: #C5D5CA; color: #8AAA95; }
"""

_BTN_DANGER = """
    QPushButton {
        background: white;
        border: 1.5px solid #C0392B;
        border-radius: 6px;
        padding: 5px 14px;
        font-size: 12px;
        color: #C0392B;
        font-weight: bold;
    }
    QPushButton:hover { background: #FDEDEB; }
    QPushButton:pressed { background: #FADBD8; }
    QPushButton:disabled { border-color: #D5C5C2; color: #C5A5A2; }
"""

_BTN_SECONDARY = """
    QPushButton {
        background: #F0EBE6;
        border: 1px solid #C9B9AE;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        color: #4A3728;
    }
    QPushButton:hover { background: #E8DFD8; }
    QPushButton:pressed { background: #DDD4CC; }
    QPushButton:disabled { background: #F5F2F0; color: #B0A098; border-color: #DDD; }
"""

_BTN_OUTLINE = """
    QPushButton {
        background: white;
        border: 1px solid #C9B9AE;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        color: #5A4A3F;
    }
    QPushButton:hover { background: #F8F5F2; }
    QPushButton:pressed { background: #F0EBE6; }
    QPushButton:disabled { background: #F5F2F0; color: #B0A098; border-color: #DDD; }
"""

_SEARCH_INPUT_STYLE = """
    QLineEdit {
        border: 1.5px solid #C9B9AE;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 13px;
        background: white;
        color: #2C1810;
    }
    QLineEdit:focus { border-color: #B03A2E; }
    QLineEdit:hover:!focus { border-color: #A99088; }
"""

_COMBO_STYLE = """
    QComboBox {
        border: 1px solid #C9B9AE;
        border-radius: 5px;
        padding: 4px 8px;
        background: white;
        font-size: 12px;
        color: #333;
        min-width: 80px;
    }
    QComboBox:focus { border-color: #B03A2E; }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        border: 1px solid #C9B9AE;
        selection-background-color: #FDEAE2;
        selection-color: #2C1810;
    }
"""


def build_bodega_tab(window: "MainWindow") -> QWidget:
    return BodegaWidget(window)


class BodegaWidget(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.window = window
        self._selected_caja_id: int | None = None
        self._categoria_filter: CategoriaCaja | None = None
        self._init_ui()
        self._refresh_cajas()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # ─── Top bar: búsqueda + acciones ────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto, SKU, talla o caja...")
        self.search_input.setStyleSheet(_SEARCH_INPUT_STYLE)
        self.search_input.setFixedHeight(36)
        self.search_input.returnPressed.connect(self._on_search)
        top_bar.addWidget(self.search_input, 3)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setFixedHeight(36)
        self.btn_buscar.setStyleSheet(_BTN_SECONDARY)
        self.btn_buscar.setToolTip("Busca dónde está un producto, talla o SKU dentro de las cajas")
        self.btn_buscar.clicked.connect(self._on_search)
        top_bar.addWidget(self.btn_buscar)

        self.btn_nueva_caja = QPushButton("+ Nueva Caja")
        self.btn_nueva_caja.setFixedHeight(36)
        self.btn_nueva_caja.setStyleSheet(_BTN_PRIMARY)
        self.btn_nueva_caja.setToolTip("Crea una caja nueva eligiendo su categoría de rotación (A/B/C/D)")
        self.btn_nueva_caja.clicked.connect(self._on_nueva_caja)
        top_bar.addWidget(self.btn_nueva_caja)

        self.btn_ubicaciones = QPushButton("Ubicaciones")
        self.btn_ubicaciones.setFixedHeight(36)
        self.btn_ubicaciones.setStyleSheet(_BTN_OUTLINE)
        self.btn_ubicaciones.setToolTip("Administra los racks y niveles donde se colocan las cajas")
        self.btn_ubicaciones.clicked.connect(self._on_gestionar_ubicaciones)
        top_bar.addWidget(self.btn_ubicaciones)

        main_layout.addLayout(top_bar)

        # ─── Category chips ──────────────────────────────────────────────
        cat_bar = QHBoxLayout()
        cat_bar.setSpacing(6)
        self._cat_buttons: dict[str | None, QPushButton] = {}
        for key, label in [
            (None, "Todas"),
            ("A", "A — Alta rotación"),
            ("B", "B — Excedentes escuelas"),
            ("C", "C — Temporada"),
            ("D", "D — Descatalogado"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key is None)
            btn.setFixedHeight(28)
            color = CATEGORIA_COLORS.get(key, "#555555")
            btn.setStyleSheet(
                f"QPushButton {{ border: 1.5px solid {color}; border-radius: 14px; "
                f"padding: 2px 12px; color: {color}; background: white; "
                f"font-size: 11px; font-weight: 500; }}"
                f"QPushButton:checked {{ background: {color}; color: white; }}"
                f"QPushButton:hover:!checked {{ background: {color}22; }}"
            )
            btn.clicked.connect(lambda checked, k=key: self._on_cat_filter(k))
            cat_bar.addWidget(btn)
            self._cat_buttons[key] = btn
        cat_bar.addStretch()

        self.resumen_label = QLabel("")
        self.resumen_label.setStyleSheet("font-size: 11px; color: #7A6055; font-style: italic;")
        cat_bar.addWidget(self.resumen_label)
        main_layout.addLayout(cat_bar)

        # ─── Splitter: lista cajas | detalle ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: lista de cajas
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        # Filtros
        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        lbl_estado = QLabel("Estado:")
        lbl_estado.setStyleSheet("font-size: 12px; color: #5A4A3F;")
        self.filtro_estado = QComboBox()
        self.filtro_estado.addItems(["Todas", "ACTIVA", "VACIA", "CERRADA"])
        self.filtro_estado.setStyleSheet(_COMBO_STYLE)
        self.filtro_estado.currentIndexChanged.connect(self._refresh_cajas)
        filtros.addWidget(lbl_estado)
        filtros.addWidget(self.filtro_estado)

        lbl_ub = QLabel("Ubicación:")
        lbl_ub.setStyleSheet("font-size: 12px; color: #5A4A3F;")
        self.filtro_ubicacion = QComboBox()
        self.filtro_ubicacion.addItem("Todas", None)
        self.filtro_ubicacion.setStyleSheet(_COMBO_STYLE)
        self.filtro_ubicacion.currentIndexChanged.connect(self._refresh_cajas)
        filtros.addWidget(lbl_ub)
        filtros.addWidget(self.filtro_ubicacion)
        filtros.addStretch()
        left_layout.addLayout(filtros)

        # Tabla de cajas
        self.tabla_cajas = QTableWidget()
        self.tabla_cajas.setColumnCount(6)
        self.tabla_cajas.setHorizontalHeaderLabels([
            "Código", "Categoría", "Ubicación", "Estado", "Contenido", "Última actividad",
        ])
        self.tabla_cajas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_cajas.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_cajas.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_cajas.setAlternatingRowColors(True)
        self.tabla_cajas.setStyleSheet(_TABLE_STYLE)
        self.tabla_cajas.horizontalHeader().setStretchLastSection(True)
        self.tabla_cajas.verticalHeader().setVisible(False)
        self.tabla_cajas.setShowGrid(False)
        self.tabla_cajas.itemSelectionChanged.connect(self._on_caja_selected)
        left_layout.addWidget(self.tabla_cajas)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # Panel derecho: detalle de caja
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        # Tarjeta de info de la caja seleccionada
        self._detalle_card = QFrame()
        self._detalle_card.setFrameShape(QFrame.Shape.StyledPanel)
        self._detalle_card.setStyleSheet("""
            QFrame {
                background: #FEF9F7;
                border: 1px solid #E0D5CE;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(2)

        self.detalle_header = QLabel("Selecciona una caja")
        self.detalle_header.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #2C1810; "
            "border: none; background: transparent;"
        )
        card_layout.addWidget(self.detalle_header)

        self.detalle_ubicacion_label = QLabel("")
        self.detalle_ubicacion_label.setStyleSheet(
            "font-size: 12px; color: #7A6055; border: none; background: transparent;"
        )
        card_layout.addWidget(self.detalle_ubicacion_label)

        self.detalle_categoria_label = QLabel("")
        self.detalle_categoria_label.setStyleSheet(
            "font-size: 12px; border: none; background: transparent;"
        )
        card_layout.addWidget(self.detalle_categoria_label)

        self._detalle_card.setLayout(card_layout)
        right_layout.addWidget(self._detalle_card)

        # Acciones de caja
        acciones_caja = QHBoxLayout()
        acciones_caja.setSpacing(6)

        self.btn_agregar = QPushButton("+ Agregar producto")
        self.btn_agregar.setToolTip("Escanea o busca productos para ingresar piezas a esta caja")
        self.btn_agregar.setStyleSheet(_BTN_SUCCESS)
        self.btn_agregar.clicked.connect(self._on_agregar_producto)
        self.btn_agregar.setEnabled(False)
        acciones_caja.addWidget(self.btn_agregar)

        self.btn_retirar = QPushButton("− Retirar")
        self.btn_retirar.setToolTip("Saca piezas de esta caja para llevarlas a tienda")
        self.btn_retirar.setStyleSheet(_BTN_DANGER)
        self.btn_retirar.clicked.connect(self._on_retirar_producto)
        self.btn_retirar.setEnabled(False)
        acciones_caja.addWidget(self.btn_retirar)

        self.btn_mover = QPushButton("Mover caja")
        self.btn_mover.setToolTip("Cambia la ubicación física de esta caja a otro rack o nivel")
        self.btn_mover.setStyleSheet(_BTN_SECONDARY)
        self.btn_mover.clicked.connect(self._on_mover_caja)
        self.btn_mover.setEnabled(False)
        acciones_caja.addWidget(self.btn_mover)

        self.btn_reclasificar = QPushButton("Reclasificar")
        self.btn_reclasificar.setToolTip("Cambia la categoría de rotación (A/B/C/D) de esta caja")
        self.btn_reclasificar.setStyleSheet(_BTN_SECONDARY)
        self.btn_reclasificar.clicked.connect(self._on_reclasificar)
        self.btn_reclasificar.setEnabled(False)
        acciones_caja.addWidget(self.btn_reclasificar)

        self.btn_etiqueta = QPushButton("Imprimir etiqueta")
        self.btn_etiqueta.setToolTip("Genera una hoja tamaño carta con QR, contenido y tallas para pegar a la caja")
        self.btn_etiqueta.setStyleSheet(_BTN_OUTLINE)
        self.btn_etiqueta.clicked.connect(self._on_imprimir_etiqueta)
        self.btn_etiqueta.setEnabled(False)
        acciones_caja.addWidget(self.btn_etiqueta)

        acciones_caja.addStretch()
        right_layout.addLayout(acciones_caja)

        # Contenido de caja
        contenido_group = QGroupBox("Contenido")
        contenido_group.setStyleSheet(_GROUPBOX_STYLE)
        contenido_layout = QVBoxLayout()
        contenido_layout.setContentsMargins(8, 8, 8, 8)
        contenido_layout.setSpacing(6)

        self.contenido_text = QLabel("")
        self.contenido_text.setWordWrap(True)
        self.contenido_text.setStyleSheet("font-size: 12px; padding: 2px 4px; color: #333;")
        self.contenido_text.setTextFormat(Qt.TextFormat.RichText)
        contenido_layout.addWidget(self.contenido_text)

        self.tabla_contenido = QTableWidget()
        self.tabla_contenido.setColumnCount(5)
        self.tabla_contenido.setHorizontalHeaderLabels(["Producto", "Talla", "Color", "Cantidad", "SKU"])
        self.tabla_contenido.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_contenido.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_contenido.setAlternatingRowColors(True)
        self.tabla_contenido.setStyleSheet(_TABLE_STYLE)
        self.tabla_contenido.verticalHeader().setVisible(False)
        self.tabla_contenido.setShowGrid(False)
        self.tabla_contenido.horizontalHeader().setStretchLastSection(True)
        contenido_layout.addWidget(self.tabla_contenido)
        contenido_group.setLayout(contenido_layout)
        right_layout.addWidget(contenido_group)

        # Historial
        historial_group = QGroupBox("Últimos movimientos")
        historial_group.setStyleSheet(_GROUPBOX_STYLE)
        historial_layout = QVBoxLayout()
        historial_layout.setContentsMargins(8, 8, 8, 8)

        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(5)
        self.tabla_historial.setHorizontalHeaderLabels(["Fecha", "Tipo", "Producto", "Cantidad", "Usuario"])
        self.tabla_historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_historial.setAlternatingRowColors(True)
        self.tabla_historial.setStyleSheet(_TABLE_STYLE)
        self.tabla_historial.verticalHeader().setVisible(False)
        self.tabla_historial.setShowGrid(False)
        self.tabla_historial.horizontalHeader().setStretchLastSection(True)
        historial_layout.addWidget(self.tabla_historial)
        historial_group.setLayout(historial_layout)
        right_layout.addWidget(historial_group)

        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

        # ─── Resultados de búsqueda (oculto inicialmente) ────────────────
        self.search_results_group = QGroupBox("Resultados de búsqueda")
        self.search_results_group.setStyleSheet(_GROUPBOX_STYLE)
        search_layout = QVBoxLayout()
        search_layout.setContentsMargins(10, 8, 10, 10)
        search_top = QHBoxLayout()
        self.search_results_text = QLabel("")
        self.search_results_text.setWordWrap(True)
        self.search_results_text.setTextFormat(Qt.TextFormat.RichText)
        self.search_results_text.setStyleSheet("font-size: 12px; padding: 4px;")
        search_top.addWidget(self.search_results_text, 1)
        btn_cerrar_busqueda = QPushButton("✕")
        btn_cerrar_busqueda.setFixedSize(28, 28)
        btn_cerrar_busqueda.setStyleSheet(
            "QPushButton { border: none; font-size: 15px; font-weight: bold; color: #888; "
            "background: transparent; border-radius: 14px; }"
            "QPushButton:hover { background: #F0EBE6; color: #555; }"
        )
        btn_cerrar_busqueda.setToolTip("Cerrar resultados")
        btn_cerrar_busqueda.clicked.connect(self._close_search_results)
        search_top.addWidget(btn_cerrar_busqueda, 0, Qt.AlignmentFlag.AlignTop)
        search_layout.addLayout(search_top)
        self.search_results_group.setLayout(search_layout)
        self.search_results_group.setVisible(False)
        main_layout.addWidget(self.search_results_group)

        self.setLayout(main_layout)

    # ─── Category filter ─────────────────────────────────────────────────

    def _on_cat_filter(self, cat_key: str | None) -> None:
        for k, btn in self._cat_buttons.items():
            btn.setChecked(k == cat_key)
        self._categoria_filter = CategoriaCaja(cat_key) if cat_key else None
        self._refresh_cajas()

    # ─── Data loading ────────────────────────────────────────────────────

    def _refresh_cajas(self) -> None:
        with get_session() as session:
            estado_text = self.filtro_estado.currentText()
            estado = EstadoCaja(estado_text) if estado_text != "Todas" else None

            ub_data = self.filtro_ubicacion.currentData()
            ubicacion_id = int(ub_data) if ub_data is not None else None

            cajas = BodegaService.listar_cajas(
                session,
                estado=estado,
                ubicacion_id=ubicacion_id,
                categoria=self._categoria_filter,
            )

            self.tabla_cajas.setRowCount(len(cajas))
            for row, caja in enumerate(cajas):
                # Código
                item_codigo = QTableWidgetItem(caja.codigo)
                item_codigo.setData(Qt.ItemDataRole.UserRole, caja.id)
                self.tabla_cajas.setItem(row, 0, item_codigo)

                # Categoría (colored badge)
                cat_label = CATEGORIA_CAJA_LABELS.get(caja.categoria, caja.categoria)
                item_cat = QTableWidgetItem(f"{caja.categoria} — {cat_label}")
                color = CATEGORIA_COLORS.get(caja.categoria, "#333")
                item_cat.setForeground(QColor(color))
                self.tabla_cajas.setItem(row, 1, item_cat)

                # Ubicación
                ub_str = caja.ubicacion.codigo if caja.ubicacion else "—"
                self.tabla_cajas.setItem(row, 2, QTableWidgetItem(ub_str))

                # Estado
                self.tabla_cajas.setItem(row, 3, QTableWidgetItem(caja.estado))

                # Contenido — desglose de tallas
                desglose = BodegaService.desglose_contenido_caja(session, caja.id)
                if desglose:
                    parts = []
                    for grupo in desglose:
                        tallas = " ".join(
                            f"{t['talla']}({t['cantidad']})" for t in grupo["tallas"]
                        )
                        parts.append(f"{grupo['producto']}: {tallas}")
                    contenido_str = " | ".join(parts)
                else:
                    contenido_str = "Vacía"
                self.tabla_cajas.setItem(row, 4, QTableWidgetItem(contenido_str))

                # Última actividad
                self.tabla_cajas.setItem(row, 5, QTableWidgetItem(
                    caja.updated_at.strftime("%d/%m %H:%M") if caja.updated_at else "—"
                ))

            self._refresh_filtro_ubicaciones(session)
            self._refresh_resumen(session)

    def _refresh_resumen(self, session) -> None:
        resumen = BodegaService.resumen_por_categoria(session)
        parts = []
        for r in resumen:
            parts.append(f"{r['categoria']}: {r['cajas']} cajas, {r['prendas']} prendas")
        self.resumen_label.setText("  ·  ".join(parts) if parts else "Sin cajas")

    def _refresh_filtro_ubicaciones(self, session) -> None:
        current = self.filtro_ubicacion.currentData()
        self.filtro_ubicacion.blockSignals(True)
        self.filtro_ubicacion.clear()
        self.filtro_ubicacion.addItem("Todas", None)
        ubicaciones = BodegaService.listar_ubicaciones(session)
        for ub in ubicaciones:
            self.filtro_ubicacion.addItem(ub.codigo, ub.id)
        if current is not None:
            idx = self.filtro_ubicacion.findData(current)
            if idx >= 0:
                self.filtro_ubicacion.setCurrentIndex(idx)
        self.filtro_ubicacion.blockSignals(False)

    def _on_caja_selected(self) -> None:
        rows = self.tabla_cajas.selectedItems()
        if not rows:
            self._selected_caja_id = None
            self._set_detalle_enabled(False)
            self.detalle_header.setText("Selecciona una caja")
            self.detalle_ubicacion_label.setText("")
            self.detalle_categoria_label.setText("")
            self.contenido_text.setText("")
            self.tabla_contenido.setRowCount(0)
            self.tabla_historial.setRowCount(0)
            return

        row = self.tabla_cajas.currentRow()
        item = self.tabla_cajas.item(row, 0)
        if not item:
            return
        caja_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_caja_id = caja_id
        self._set_detalle_enabled(True)
        self._load_caja_detalle(caja_id)

    def _set_detalle_enabled(self, enabled: bool) -> None:
        self.btn_agregar.setEnabled(enabled)
        self.btn_retirar.setEnabled(enabled)
        self.btn_mover.setEnabled(enabled)
        self.btn_reclasificar.setEnabled(enabled)
        self.btn_etiqueta.setEnabled(enabled)

    def _load_caja_detalle(self, caja_id: int) -> None:
        with get_session() as session:
            caja = BodegaService.obtener_caja_detalle(session, caja_id)
            if not caja:
                return

            cat_label = CATEGORIA_CAJA_LABELS.get(caja.categoria, caja.categoria)
            color = CATEGORIA_COLORS.get(caja.categoria, "#333")
            self.detalle_header.setText(f"Caja {caja.codigo}  [{caja.estado}]")
            ub_text = f"Ubicación: {caja.ubicacion.codigo}" if caja.ubicacion else "Sin ubicación asignada"
            self.detalle_ubicacion_label.setText(ub_text)
            self.detalle_categoria_label.setText(
                f'<span style="color:{color}; font-weight:bold;">{caja.categoria} — {cat_label}</span>'
            )
            self.detalle_categoria_label.setTextFormat(Qt.TextFormat.RichText)

            # Desglose por producto
            desglose = BodegaService.desglose_contenido_caja(session, caja_id)
            if desglose:
                html_parts = []
                for grupo in desglose:
                    tallas = " &nbsp; ".join(
                        f"<b>{t['talla']}</b>({t['cantidad']})" for t in grupo["tallas"]
                    )
                    html_parts.append(f"<b>{grupo['producto']}</b> ({grupo['total']} pz): {tallas}")
                self.contenido_text.setText("<br>".join(html_parts))
            else:
                self.contenido_text.setText("<i>Sin contenido</i>")

            # Tabla detallada
            contenido = caja.contenido or []
            self.tabla_contenido.setRowCount(len(contenido))
            for row, c in enumerate(contenido):
                prod_item = QTableWidgetItem(c.variante.producto.nombre)
                prod_item.setData(Qt.ItemDataRole.UserRole, c.variante_id)
                self.tabla_contenido.setItem(row, 0, prod_item)
                self.tabla_contenido.setItem(row, 1, QTableWidgetItem(c.variante.talla or ""))
                self.tabla_contenido.setItem(row, 2, QTableWidgetItem(c.variante.color or ""))
                cant_item = QTableWidgetItem(str(c.cantidad))
                cant_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_contenido.setItem(row, 3, cant_item)
                self.tabla_contenido.setItem(row, 4, QTableWidgetItem(c.variante.sku or ""))

            # Historial
            movimientos = BodegaService.historial_caja(session, caja_id, limit=20)
            self.tabla_historial.setRowCount(len(movimientos))
            for row, mov in enumerate(movimientos):
                self.tabla_historial.setItem(row, 0, QTableWidgetItem(
                    mov.created_at.strftime("%d/%m %H:%M")
                ))
                self.tabla_historial.setItem(row, 1, QTableWidgetItem(mov.tipo))
                prod_text = ""
                if mov.variante:
                    prod_text = f"{mov.variante.producto.nombre} {mov.variante.talla}"
                self.tabla_historial.setItem(row, 2, QTableWidgetItem(prod_text))
                cant_text = str(mov.cantidad) if mov.cantidad else "—"
                self.tabla_historial.setItem(row, 3, QTableWidgetItem(cant_text))
                self.tabla_historial.setItem(row, 4, QTableWidgetItem(mov.creado_por))

    # ─── Búsqueda ────────────────────────────────────────────────────────

    def _close_search_results(self) -> None:
        self.search_results_group.setVisible(False)
        self.search_input.clear()

    def _on_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.search_results_group.setVisible(False)
            return

        with get_session() as session:
            resultados = BodegaService.buscar_por_texto_agrupado(session, query)

        if not resultados:
            self.search_results_text.setText("<i>Sin resultados</i>")
            self.search_results_group.setVisible(True)
            return

        html_parts = []
        for grupo in resultados:
            html_parts.append(f'<b style="font-size:13px">{grupo["producto"]}</b>')
            for v in grupo["variantes"]:
                cajas_str = ", ".join(
                    f'{c["caja_codigo"]}({c["cantidad"]})'
                    for c in v["cajas"]
                )
                html_parts.append(
                    f'&nbsp;&nbsp;{v["talla"]} {v["color"]} — '
                    f'Bodega: <b>{v["en_bodega"]}</b> · '
                    f'Tienda: <b>{v["en_tienda"]}</b> · '
                    f'Total: {v["stock_actual"]} · '
                    f'Cajas: {cajas_str}'
                )
            html_parts.append("")

        self.search_results_text.setText("<br>".join(html_parts))
        self.search_results_group.setVisible(True)

    # ─── Acciones ────────────────────────────────────────────────────────

    def _on_nueva_caja(self) -> None:
        dialog = NuevaCajaDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_cajas()

    def _on_gestionar_ubicaciones(self) -> None:
        from pos_uniformes.ui.dialogs.bodega_ubicaciones_dialog import BodegaUbicacionesDialog
        dialog = BodegaUbicacionesDialog(self)
        dialog.exec()
        self._refresh_cajas()

    def _on_agregar_producto(self) -> None:
        if not self._selected_caja_id:
            return
        from pos_uniformes.ui.dialogs.bodega_ingreso_dialog import BodegaIngresoDialog
        dialog = BodegaIngresoDialog(self, self._selected_caja_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_retirar_producto(self) -> None:
        if not self._selected_caja_id:
            return
        row = self.tabla_contenido.currentRow()
        if row < 0:
            QMessageBox.information(self, "Retirar", "Selecciona un producto de la tabla de contenido.")
            return

        sku_item = self.tabla_contenido.item(row, 4)
        cant_item = self.tabla_contenido.item(row, 3)
        if not sku_item or not cant_item:
            return
        sku = sku_item.text() or ""
        try:
            cant_actual = int(cant_item.text())
        except (ValueError, TypeError):
            cant_actual = 1

        # Obtener variante_id de UserRole (más fiable que buscar por SKU)
        variante_id_item = self.tabla_contenido.item(row, 0)
        variante_id = variante_id_item.data(Qt.ItemDataRole.UserRole) if variante_id_item else None

        display_name = sku or (variante_id_item.text() if variante_id_item else "producto")
        dialog = RetirarDialog(self, display_name, cant_actual)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cantidad = dialog.cantidad()
            with get_session() as session:
                # Buscar por variante_id si está disponible, sino fallback a SKU
                variante = None
                if variante_id:
                    variante = session.get(Variante, variante_id)
                elif sku:
                    variante = session.scalar(
                        sa_select(Variante).where(Variante.sku == sku)
                    )
                if variante:
                    try:
                        BodegaService.retirar_producto(
                            session, self._selected_caja_id, variante.id, cantidad,
                            creado_por=self._get_usuario_actual(),
                        )
                        session.commit()
                    except ValueError as e:
                        session.rollback()
                        QMessageBox.warning(self, "Error", str(e))
                        return
                else:
                    QMessageBox.warning(self, "Error", "No se encontró la variante.")
                    return
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_mover_caja(self) -> None:
        if not self._selected_caja_id:
            return
        dialog = MoverCajaDialog(self, self._selected_caja_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_reclasificar(self) -> None:
        if not self._selected_caja_id:
            return
        dialog = ReclasificarDialog(self, self._selected_caja_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_imprimir_etiqueta(self) -> None:
        if not self._selected_caja_id:
            return
        from pos_uniformes.services.bodega_label_service import print_caja_label
        with get_session() as session:
            try:
                print_caja_label(session, self._selected_caja_id)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo generar la etiqueta:\n{e}")

    def _get_usuario_actual(self) -> str:
        if hasattr(self.window, "current_user") and self.window.current_user:
            return self.window.current_user.nombre
        return "ADMIN"


# ═══════════════════════════════════════════════════════════════════════════════
# DIÁLOGOS INTEGRADOS
# ═══════════════════════════════════════════════════════════════════════════════


class NuevaCajaDialog(QDialog):
    def __init__(self, parent: BodegaWidget):
        super().__init__(parent)
        self.setWindowTitle("Nueva Caja")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        self.categoria_combo = QComboBox()
        for cat in CategoriaCaja:
            color = CATEGORIA_COLORS[cat.value]
            label = f"{cat.value} — {CATEGORIA_CAJA_LABELS[cat.value]}"
            self.categoria_combo.addItem(label, cat)
        layout.addRow("Categoría:", self.categoria_combo)

        self.ubicacion_combo = QComboBox()
        self.ubicacion_combo.addItem("Sin asignar", None)
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session)
            for ub in ubicaciones:
                self.ubicacion_combo.addItem(ub.codigo, ub.id)
        layout.addRow("Ubicación:", self.ubicacion_combo)

        self.notas_input = QLineEdit()
        layout.addRow("Notas:", self.notas_input)

        self.preview_label = QLabel("")
        self.preview_label.setStyleSheet("font-size: 11px; color: #555;")
        layout.addRow("", self.preview_label)
        self.categoria_combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def _update_preview(self) -> None:
        cat: CategoriaCaja = self.categoria_combo.currentData()
        if not cat:
            return
        with get_session() as session:
            codigo = BodegaService._siguiente_codigo(session, cat)
        self.preview_label.setText(f"Se creará con código: {codigo}")

    def _on_accept(self) -> None:
        cat: CategoriaCaja = self.categoria_combo.currentData()
        ubicacion_id = self.ubicacion_combo.currentData()
        notas = self.notas_input.text().strip() or None

        with get_session() as session:
            try:
                BodegaService.crear_caja(session, cat, ubicacion_id, notas)
                session.commit()
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return
        self.accept()


class ReclasificarDialog(QDialog):
    def __init__(self, parent: BodegaWidget, caja_id: int):
        super().__init__(parent)
        self._caja_id = caja_id
        self._parent_widget = parent
        self.setWindowTitle("Reclasificar Caja")
        self.setMinimumWidth(350)

        layout = QFormLayout()

        self.categoria_combo = QComboBox()
        for cat in CategoriaCaja:
            label = f"{cat.value} — {CATEGORIA_CAJA_LABELS[cat.value]}"
            self.categoria_combo.addItem(label, cat)
        layout.addRow("Nueva categoría:", self.categoria_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def _on_accept(self) -> None:
        cat: CategoriaCaja = self.categoria_combo.currentData()
        with get_session() as session:
            try:
                BodegaService.reclasificar_caja(
                    session, self._caja_id, cat,
                    creado_por=self._parent_widget._get_usuario_actual(),
                )
                session.commit()
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return
        self.accept()


class RetirarDialog(QDialog):
    def __init__(self, parent: QWidget, sku: str, max_cantidad: int):
        super().__init__(parent)
        self.setWindowTitle(f"Retirar — {sku}")

        layout = QFormLayout()
        self._spin = QSpinBox()
        self._spin.setMinimum(1)
        self._spin.setMaximum(max_cantidad)
        self._spin.setValue(1)
        layout.addRow("Cantidad a retirar:", self._spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def cantidad(self) -> int:
        return self._spin.value()


class MoverCajaDialog(QDialog):
    def __init__(self, parent: BodegaWidget, caja_id: int):
        super().__init__(parent)
        self._caja_id = caja_id
        self._parent_widget = parent
        self.setWindowTitle("Mover Caja")

        layout = QFormLayout()
        self.ubicacion_combo = QComboBox()
        self.ubicacion_combo.addItem("Sin asignar", None)
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session)
            for ub in ubicaciones:
                self.ubicacion_combo.addItem(ub.codigo, ub.id)
        layout.addRow("Nueva ubicación:", self.ubicacion_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def _on_accept(self) -> None:
        nueva_ub = self.ubicacion_combo.currentData()
        with get_session() as session:
            try:
                BodegaService.mover_caja(
                    session, self._caja_id, nueva_ub,
                    creado_por=self._parent_widget._get_usuario_actual(),
                )
                session.commit()
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return
        self.accept()
