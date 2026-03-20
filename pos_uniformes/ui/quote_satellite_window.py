"""Ventana satelite para gestion dedicada de Presupuestos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, QSize, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Cliente, EstadoPresupuesto, RolUsuario, Usuario
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.presupuesto_service import PresupuestoItemInput, PresupuestoService
from pos_uniformes.services.quote_action_service import cancel_quote, emit_quote
from pos_uniformes.services.quote_detail_service import load_quote_detail_snapshot
from pos_uniformes.services.quote_document_view_service import build_quote_document_view
from pos_uniformes.services.quote_editor_service import QuoteSavePayload, load_quote_editor_snapshot, save_quote_from_editor
from pos_uniformes.services.quote_kiosk_lookup_service import QuoteKioskLookupSnapshot, load_quote_kiosk_lookup_snapshot
from pos_uniformes.services.quote_snapshot_service import build_quote_history_input_rows, load_quote_snapshot_rows
from pos_uniformes.services.quote_whatsapp_service import build_quote_whatsapp_view
from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog
from pos_uniformes.ui.helpers.date_field_helper import configure_friendly_date_edit
from pos_uniformes.ui.helpers.printable_document_flow_helper import open_printable_document_flow
from pos_uniformes.ui.helpers.quote_cart_view_helper import build_quote_cart_view
from pos_uniformes.ui.helpers.quote_detail_helper import (
    build_empty_quote_detail_view,
    build_error_quote_detail_view,
    build_quote_detail_view,
)
from pos_uniformes.ui.helpers.quote_feedback_helper import build_quote_guard_feedback
from pos_uniformes.ui.helpers.quote_catalog_browser_helper import (
    build_quote_catalog_browser,
    build_quote_catalog_school_options,
)
from pos_uniformes.ui.helpers.quote_guided_catalog_helper import build_guided_catalog_view
from pos_uniformes.ui.helpers.quote_kiosk_lookup_helper import (
    build_empty_quote_kiosk_lookup_view,
    build_error_quote_kiosk_lookup_view,
    build_quote_kiosk_lookup_view,
    build_quote_kiosk_recent_scan_rows,
    push_quote_kiosk_recent_scan,
)
from pos_uniformes.ui.helpers.quote_satellite_filter_helper import (
    build_quote_satellite_action_state,
    build_quote_satellite_rows,
)
from pos_uniformes.ui.helpers.quote_summary_helper import build_quote_summary_view
from pos_uniformes.ui.helpers.quote_table_row_helper import build_quote_table_row_views


class QuoteSatelliteWindow(QMainWindow):
    def __init__(self, user_id: int) -> None:
        super().__init__()
        self.user_id = user_id
        self.current_username = ""
        self.current_full_name = ""
        self.current_role = RolUsuario.CAJERO
        self.quote_editing_id: int | None = None
        self.quote_cart: list[dict[str, object]] = []
        self.quote_rows: list[dict[str, object]] = []
        self.selected_quote_state = ""
        self.selected_quote_phone = ""
        self.lookup_snapshot: QuoteKioskLookupSnapshot | None = None
        self.lookup_history: list[QuoteKioskLookupSnapshot] = []
        self.catalog_snapshot_rows: list[dict[str, object]] = []

        self._build_widgets()
        self._apply_icons()
        self._apply_styles()
        self._build_ui()
        self._bind_events()
        self._load_operator_context()
        self._reset_quote_form()
        self._apply_lookup_view(build_empty_quote_kiosk_lookup_view())
        self._apply_catalog_detail(None)
        self._apply_guided_detail(None)
        self._refresh_recent_lookup_table()
        self.refresh_all()
        QTimer.singleShot(0, self.kiosk_scan_input.setFocus)

    def _build_widgets(self) -> None:
        self.operator_label = QLabel("Sin operador")
        self.status_label = QLabel("Listo.")
        self.refresh_button = QPushButton("Refrescar")
        self.page_stack = QStackedWidget()
        self.nav_button_group = QButtonGroup(self)
        self.nav_kiosk_button = QPushButton("Kiosko")
        self.nav_catalog_button = QPushButton("Catalogo")
        self.nav_guided_button = QPushButton("Presupuesto guiado")
        self.nav_quote_button = QPushButton("Presupuesto")
        self.nav_search_button = QPushButton("Buscar")
        self.nav_share_button = QPushButton("Compartir")
        self.sidebar_total_label = QLabel("$0.00")
        self.sidebar_summary_label = QLabel("Sin piezas en el presupuesto actual.")
        self.kiosk_open_quote_button = QPushButton("Ver presupuesto")
        self.kiosk_open_search_button = QPushButton("Abrir catalogo")
        self.kiosk_budget_total_label = QLabel("$0.00")
        self.kiosk_budget_summary_label = QLabel("Sin piezas en el presupuesto actual.")
        self.catalog_school_combo = QComboBox()
        self.catalog_include_general_combo = QComboBox()
        self.catalog_search_input = QLineEdit()
        self.catalog_qty_spin = QSpinBox()
        self.catalog_refresh_button = QPushButton("Refrescar")
        self.catalog_add_button = QPushButton("Agregar al presupuesto")
        self.catalog_status_label = QLabel("Sin catalogo cargado.")
        self.catalog_table = QTableWidget()
        self.catalog_visual_icon_label = QLabel()
        self.catalog_detail_title_label = QLabel("Sin seleccion.")
        self.catalog_detail_meta_label = QLabel("")
        self.catalog_detail_notes_label = QLabel("")
        self.catalog_level_combo = QComboBox()
        self.guided_mode = "school"
        self.guided_selected_level = ""
        self.guided_selected_school = ""
        self.guided_selected_gender = "TODOS"
        self.guided_selected_sku = ""
        self.guided_status_label = QLabel("Empieza eligiendo una ruta.")
        self.guided_path_label = QLabel("Uniformes > sin nivel > sin escuela > Todos")
        self.guided_empty_label = QLabel("Selecciona una ruta para comenzar.")
        self.guided_qty_spin = QSpinBox()
        self.guided_add_button = QPushButton("Agregar al presupuesto")
        self.guided_visual_icon_label = QLabel()
        self.guided_detail_title_label = QLabel("Sin seleccion.")
        self.guided_detail_meta_label = QLabel("")
        self.guided_detail_notes_label = QLabel("")
        self.guided_mode_buttons: dict[str, QPushButton] = {}
        self.guided_level_buttons: dict[str, QPushButton] = {}
        self.guided_school_buttons: dict[str, QPushButton] = {}
        self.guided_gender_buttons: dict[str, QPushButton] = {}
        self.guided_product_buttons: dict[str, QPushButton] = {}

        self.kiosk_scan_input = QLineEdit()
        self.kiosk_qty_spin = QSpinBox()
        self.kiosk_lookup_button = QPushButton("Consultar")
        self.kiosk_add_button = QPushButton("Agregar al presupuesto")
        self.kiosk_lookup_sku_label = QLabel("")
        self.kiosk_lookup_product_label = QLabel("")
        self.kiosk_lookup_price_label = QLabel("$0.00")
        self.kiosk_lookup_status_label = QLabel("")
        self.kiosk_lookup_detail_label = QLabel("")
        self.kiosk_lookup_context_label = QLabel("")
        self.kiosk_lookup_notes_label = QLabel("")
        self.kiosk_visual_icon_label = QLabel()
        self.kiosk_recent_table = QTableWidget()

        self.quote_folio_input = QLabel()
        self.quote_client_combo = QComboBox()
        self.quote_create_client_button = QPushButton("Nuevo cliente")
        self.quote_school_scope_combo = QComboBox()
        self.quote_validity_input = QDateEdit()
        self.quote_note_input = QTextEdit()
        self.quote_draft_button = QPushButton("Guardar borrador")
        self.quote_emit_button = QPushButton("Emitir")
        self.quote_remove_button = QPushButton("Quitar linea")
        self.quote_clear_button = QPushButton("Vaciar")
        self.quote_cart_table = QTableWidget()
        self.quote_total_label = QLabel("$0.00")
        self.quote_summary_label = QLabel("Presupuesto vacio.")
        self.quote_school_summary_label = QLabel("Sin escuelas activas.")

        self.quote_search_input = QLineEdit()
        self.quote_state_combo = QComboBox()
        self.quote_refresh_button = QPushButton("Refrescar")
        self.quote_resume_button = QPushButton("Reanudar")
        self.quote_emit_selected_button = QPushButton("Emitir seleccionado")
        self.quote_open_share_button = QPushButton("Compartir")
        self.quote_whatsapp_button = QPushButton("WhatsApp")
        self.quote_print_button = QPushButton("Imprimir")
        self.quote_cancel_button = QPushButton("Cancelar")
        self.quote_status_label = QLabel("Sin presupuestos cargados.")
        self.quote_table = QTableWidget()
        self.quote_customer_label = QLabel("Sin detalle.")
        self.quote_meta_label = QLabel("")
        self.quote_notes_label = QLabel("")
        self.quote_detail_table = QTableWidget()
        self.share_status_label = QLabel("Selecciona un presupuesto desde Buscar.")
        self.share_customer_label = QLabel("Sin detalle.")
        self.share_meta_label = QLabel("")
        self.share_notes_label = QLabel("")
        self.share_detail_table = QTableWidget()
        self.share_back_search_button = QPushButton("Ir a buscar")
        self.share_refresh_button = QPushButton("Recargar detalle")

    def _apply_icons(self) -> None:
        nav_icons = {
            self.nav_kiosk_button: _icon_from_asset("kiosk_icons/kiosk_scan.svg"),
            self.nav_catalog_button: _icon_from_asset("kiosk_icons/catalog_grid.svg"),
            self.nav_guided_button: _icon_from_asset("kiosk_icons/quote_stack.svg"),
            self.nav_quote_button: _icon_from_asset("kiosk_icons/quote_stack.svg"),
            self.nav_search_button: _icon_from_asset("kiosk_icons/search_quote.svg"),
            self.nav_share_button: _icon_from_asset("kiosk_icons/share_send.svg"),
        }
        for button, icon in nav_icons.items():
            button.setIcon(icon)
            button.setIconSize(QSize(20, 20))

        self.kiosk_lookup_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.kiosk_lookup_button.setIconSize(QSize(18, 18))
        self.kiosk_add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.kiosk_add_button.setIconSize(QSize(18, 18))
        self.catalog_add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.catalog_add_button.setIconSize(QSize(18, 18))
        self.guided_add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.guided_add_button.setIconSize(QSize(18, 18))
        self.quote_open_share_button.setIcon(_icon_from_asset("kiosk_icons/share_send.svg"))
        self.quote_open_share_button.setIconSize(QSize(18, 18))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4efe7;
                color: #1f1c19;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #d7cbbb;
                border-radius: 16px;
                margin-top: 12px;
                padding-top: 12px;
                background: #fbf8f2;
                font-weight: 700;
            }
            QGroupBox::title {
                left: 12px;
                padding: 0 6px;
                color: #87492c;
            }
            QFrame#satHeaderCard, QFrame#satTotalsCard {
                background: #fbf8f2;
                border: 1px solid #d7cbbb;
                border-radius: 18px;
            }
            QFrame#satSidebarCard {
                background: #fbf8f2;
                border: 1px solid #d7cbbb;
                border-radius: 22px;
            }
            QLabel#satTitle {
                font-size: 20px;
                font-weight: 800;
                color: #87492c;
            }
            QLabel#satMeta {
                color: #675f56;
                font-size: 12px;
            }
            QLabel#satStatus {
                color: #675f56;
                font-weight: 700;
            }
            QLabel#satTotal {
                font-size: 28px;
                font-weight: 900;
                color: #87492c;
            }
            QLabel#satSummary {
                color: #4f4a44;
                background: #f2ece3;
                border-radius: 12px;
                padding: 10px 12px;
            }
            QLabel#satSidebarTitle {
                font-size: 15px;
                font-weight: 900;
                color: #87492c;
            }
            QLabel#satSidebarTotal {
                font-size: 28px;
                font-weight: 900;
                color: #87492c;
            }
            QLabel#satSidebarSummary {
                color: #5e574f;
                background: #f1ebe2;
                border-radius: 12px;
                padding: 10px 12px;
            }
            QLabel#satKioskSku {
                font-size: 26px;
                font-weight: 900;
                color: #2f2a24;
            }
            QLabel#satKioskProduct {
                font-size: 22px;
                font-weight: 800;
                color: #87492c;
            }
            QLabel#satKioskPrice {
                font-size: 48px;
                font-weight: 900;
                color: #87492c;
            }
            QLabel#satKioskBadge {
                color: #2f2a24;
                background: #e8dfd3;
                border-radius: 12px;
                padding: 8px 12px;
                font-weight: 800;
            }
            QLabel#satKioskBody {
                color: #5e574f;
                background: #f1ebe2;
                border-radius: 12px;
                padding: 10px 12px;
            }
            QLabel#satDetailTitle {
                font-size: 16px;
                font-weight: 800;
                color: #2f2a24;
            }
            QLabel#satDetailMeta {
                color: #5e574f;
                background: #f1ebe2;
                border-radius: 12px;
                padding: 10px 12px;
            }
            QLabel#satDetailNotes {
                color: #5e574f;
                background: #efe5d8;
                border-radius: 12px;
                padding: 10px 12px;
            }
            QLabel#guidedStepTitle {
                font-size: 16px;
                font-weight: 900;
                color: #87492c;
            }
            QLabel#guidedStepHint {
                color: #675f56;
                font-size: 13px;
            }
            QLabel#guidedPath {
                color: #5e574f;
                background: #f1ebe2;
                border-radius: 12px;
                padding: 10px 12px;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QDateEdit, QComboBox, QSpinBox {
                background: #fffaf2;
                border: 1px solid #d5c9b9;
                border-radius: 12px;
                padding: 8px 10px;
                color: #1f1c19;
            }
            QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 2px solid #c76b39;
            }
            QPushButton {
                border-radius: 12px;
                padding: 9px 14px;
                font-weight: 800;
            }
            QPushButton#primaryButton {
                background: #87492c;
                color: #f9f4ea;
            }
            QPushButton#secondaryButton {
                background: #efe4d5;
                color: #2f2a24;
            }
            QPushButton#ghostButton {
                background: #f8f1e7;
                color: #6d6155;
            }
            QPushButton#dangerButton {
                background: #b65246;
                color: #fbf8f2;
            }
            QPushButton#navButton {
                background: #f8f1e7;
                color: #6d6155;
                text-align: left;
                padding: 14px 16px;
                font-size: 15px;
            }
            QPushButton#navButton:checked {
                background: #87492c;
                color: #f9f4ea;
            }
            QPushButton#guidedChoiceButton, QPushButton#guidedProductButton {
                background: #fffaf2;
                color: #2f2a24;
                border: 1px solid #d5c9b9;
                text-align: left;
                padding: 10px 12px;
            }
            QPushButton#guidedChoiceButton:checked, QPushButton#guidedProductButton:checked {
                background: #87492c;
                color: #fbf8f2;
                border: 1px solid #87492c;
            }
            QPushButton:disabled {
                background: #e8dfd3;
                color: #a39a90;
            }
            QTableWidget {
                background: #fffaf2;
                alternate-background-color: #f5eee5;
                border: 1px solid #d5c9b9;
                border-radius: 12px;
                gridline-color: #e7dccf;
                color: #2f2a24;
                selection-background-color: #dfb48f;
                selection-color: #1f1c19;
            }
            QTableWidget::item {
                color: #2f2a24;
            }
            QTableWidget::item:selected {
                color: #1f1c19;
            }
            QHeaderView::section {
                background: #efe4d5;
                color: #5d4c3f;
                border: none;
                border-bottom: 1px solid #d5c9b9;
                padding: 8px;
                font-weight: 800;
            }
            """
        )

    def _build_ui(self) -> None:
        self.setWindowTitle("Kiosko de Presupuestos")
        self.resize(1560, 980)

        header_card = QFrame()
        header_card.setObjectName("satHeaderCard")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("Kiosko")
        title.setObjectName("satTitle")
        self.operator_label.setObjectName("satMeta")
        self.status_label.setObjectName("satStatus")
        title_layout.addWidget(title)
        title_layout.addWidget(self.operator_label)
        header_layout.addLayout(title_layout, 1)
        header_layout.addWidget(self.status_label, 1, Qt.AlignmentFlag.AlignRight)
        self.refresh_button.setObjectName("secondaryButton")
        header_layout.addWidget(self.refresh_button)
        header_card.setLayout(header_layout)

        content = QWidget()
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._build_sidebar())
        content_layout.addWidget(self._build_page_stack(), 1)
        content.setLayout(content_layout)

        root = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)
        root_layout.addWidget(header_card)
        root_layout.addWidget(content, 1)
        root.setLayout(root_layout)
        self.setCentralWidget(root)
        self._set_page("kiosk")

    def _build_sidebar(self) -> QWidget:
        card = QFrame()
        card.setObjectName("satSidebarCard")
        card.setFixedWidth(232)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(8)

        for button in (
            self.nav_kiosk_button,
            self.nav_catalog_button,
            self.nav_guided_button,
            self.nav_quote_button,
            self.nav_search_button,
            self.nav_share_button,
        ):
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            self.nav_button_group.addButton(button)
            layout.addWidget(button)

        budget_card = QFrame()
        budget_card.setObjectName("satTotalsCard")
        budget_layout = QVBoxLayout()
        budget_layout.setContentsMargins(14, 14, 14, 14)
        budget_layout.setSpacing(6)
        budget_title = QLabel("Tu presupuesto")
        budget_title.setObjectName("satSidebarTitle")
        self.sidebar_total_label.setObjectName("satSidebarTotal")
        self.sidebar_summary_label.setObjectName("satSidebarSummary")
        self.sidebar_summary_label.setWordWrap(True)
        budget_layout.addWidget(budget_title)
        budget_layout.addWidget(self.sidebar_total_label)
        budget_layout.addWidget(self.sidebar_summary_label)
        budget_card.setLayout(budget_layout)

        layout.addWidget(budget_card)
        layout.addStretch()
        card.setLayout(layout)
        return card

    def _build_page_stack(self) -> QWidget:
        self.page_stack.addWidget(self._build_kiosk_page())
        self.page_stack.addWidget(self._build_catalog_page())
        self.page_stack.addWidget(self._build_guided_page())
        self.page_stack.addWidget(self._build_quote_page())
        self.page_stack.addWidget(self._build_search_page())
        self.page_stack.addWidget(self._build_share_page())
        return self.page_stack

    def _build_kiosk_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_kiosk_panel(), 1)
        page.setLayout(layout)
        return page

    def _build_quote_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._build_editor_panel(), 1)
        page.setLayout(layout)
        return page

    def _build_catalog_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        browser_box = QGroupBox("Catalogo para cotizar")
        browser_layout = QVBoxLayout()
        browser_layout.setSpacing(10)
        self.catalog_status_label.setObjectName("satStatus")
        self.catalog_search_input.setPlaceholderText("Buscar por SKU, producto, talla, color o tipo")
        self.catalog_search_input.setClearButtonEnabled(True)
        self.catalog_qty_spin.setRange(1, 100)
        self.catalog_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.catalog_qty_spin.setValue(1)
        self.catalog_refresh_button.setObjectName("ghostButton")
        self.catalog_add_button.setObjectName("secondaryButton")
        self.catalog_level_combo.addItem("Todos los niveles", "")
        self.catalog_include_general_combo.addItem("Escuela + extras generales", "include_general")
        self.catalog_include_general_combo.addItem("Solo escuela", "school_only")
        self.catalog_include_general_combo.addItem("Solo generales", "general_only")
        self.catalog_school_combo.addItem("Todas las escuelas", "")

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.catalog_level_combo)
        filters.addWidget(self.catalog_school_combo)
        filters.addWidget(self.catalog_include_general_combo)
        filters.addWidget(self.catalog_search_input, 1)
        filters.addWidget(QLabel("Cantidad"))
        filters.addWidget(self.catalog_qty_spin)
        filters.addWidget(self.catalog_add_button)
        filters.addWidget(self.catalog_refresh_button)

        self.catalog_table.setColumnCount(8)
        self.catalog_table.setHorizontalHeaderLabels(
            ["SKU", "Nivel", "Escuela", "Producto", "Prenda", "Talla", "Color", "Precio"]
        )
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSelectionBehavior(self.catalog_table.SelectionBehavior.SelectRows)
        self.catalog_table.setMinimumHeight(360)

        browser_layout.addWidget(self.catalog_status_label)
        browser_layout.addLayout(filters)
        browser_layout.addWidget(self.catalog_table)
        browser_box.setLayout(browser_layout)

        detail_box = QGroupBox("Detalle del catalogo")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(8)
        detail_header = QHBoxLayout()
        detail_header.setSpacing(12)
        self.catalog_visual_icon_label.setFixedSize(84, 84)
        detail_header.addWidget(self.catalog_visual_icon_label, 0, Qt.AlignmentFlag.AlignTop)
        detail_text_layout = QVBoxLayout()
        self.catalog_detail_title_label.setObjectName("satDetailTitle")
        self.catalog_detail_meta_label.setObjectName("satDetailMeta")
        self.catalog_detail_meta_label.setWordWrap(True)
        self.catalog_detail_notes_label.setObjectName("satDetailNotes")
        self.catalog_detail_notes_label.setWordWrap(True)
        detail_text_layout.addWidget(self.catalog_detail_title_label)
        detail_text_layout.addWidget(self.catalog_detail_meta_label)
        detail_header.addLayout(detail_text_layout, 1)
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.catalog_detail_notes_label)
        detail_box.setLayout(detail_layout)

        layout.addWidget(browser_box, 1)
        layout.addWidget(detail_box)
        page.setLayout(layout)
        return page

    def _build_search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._build_history_panel(), 1)
        page.setLayout(layout)
        return page

    def _build_guided_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        intro_box = QGroupBox("Presupuesto guiado")
        intro_layout = QVBoxLayout()
        intro_layout.setSpacing(6)
        intro_title = QLabel("Cotiza por pasos")
        intro_title.setObjectName("guidedStepTitle")
        intro_hint = QLabel("Elige nivel, escuela y tipo de uniforme.")
        intro_hint.setObjectName("guidedStepHint")
        intro_hint.setWordWrap(True)
        self.guided_status_label.setObjectName("satStatus")
        self.guided_path_label.setObjectName("guidedPath")
        intro_layout.addWidget(intro_title)
        intro_layout.addWidget(intro_hint)
        intro_layout.addWidget(self.guided_status_label)
        intro_layout.addWidget(self.guided_path_label)
        intro_box.setLayout(intro_layout)

        steps_box = QGroupBox("Ruta")
        steps_layout = QVBoxLayout()
        steps_layout.setSpacing(10)

        mode_title = QLabel("1. Elige una ruta")
        mode_title.setObjectName("guidedStepTitle")
        mode_hint = QLabel("Uniformes por escuela o piezas generales.")
        mode_hint.setObjectName("guidedStepHint")
        mode_hint.setWordWrap(True)
        self.guided_mode_row = QHBoxLayout()
        self.guided_mode_row.setSpacing(8)
        steps_layout.addWidget(mode_title)
        steps_layout.addWidget(mode_hint)
        steps_layout.addLayout(self.guided_mode_row)

        self.guided_level_section = QWidget()
        level_layout = QVBoxLayout()
        level_layout.setContentsMargins(0, 0, 0, 0)
        level_layout.setSpacing(8)
        level_title = QLabel("2. Elige nivel")
        level_title.setObjectName("guidedStepTitle")
        level_hint = QLabel("Solo niveles disponibles.")
        level_hint.setObjectName("guidedStepHint")
        self.guided_level_grid = QGridLayout()
        self.guided_level_grid.setHorizontalSpacing(10)
        self.guided_level_grid.setVerticalSpacing(10)
        level_layout.addWidget(level_title)
        level_layout.addWidget(level_hint)
        level_layout.addLayout(self.guided_level_grid)
        self.guided_level_section.setLayout(level_layout)
        steps_layout.addWidget(self.guided_level_section)

        self.guided_school_section = QWidget()
        school_layout = QVBoxLayout()
        school_layout.setContentsMargins(0, 0, 0, 0)
        school_layout.setSpacing(8)
        school_title = QLabel("3. Elige escuela")
        school_title.setObjectName("guidedStepTitle")
        school_hint = QLabel("Escuelas del nivel elegido.")
        school_hint.setObjectName("guidedStepHint")
        school_hint.setWordWrap(True)
        school_scroll = QScrollArea()
        school_scroll.setWidgetResizable(True)
        school_scroll.setFrameShape(QFrame.Shape.NoFrame)
        school_scroll.setMinimumHeight(160)
        school_scroll.setMaximumHeight(220)
        self.guided_school_container = QWidget()
        self.guided_school_grid = QGridLayout()
        self.guided_school_grid.setContentsMargins(0, 0, 0, 0)
        self.guided_school_grid.setHorizontalSpacing(10)
        self.guided_school_grid.setVerticalSpacing(10)
        self.guided_school_container.setLayout(self.guided_school_grid)
        school_scroll.setWidget(self.guided_school_container)
        school_layout.addWidget(school_title)
        school_layout.addWidget(school_hint)
        school_layout.addWidget(school_scroll)
        self.guided_school_section.setLayout(school_layout)
        steps_layout.addWidget(self.guided_school_section, 1)

        self.guided_gender_section = QWidget()
        gender_section_layout = QVBoxLayout()
        gender_section_layout.setContentsMargins(0, 0, 0, 0)
        gender_section_layout.setSpacing(8)
        gender_title = QLabel("4. Elige tipo de uniforme")
        gender_title.setObjectName("guidedStepTitle")
        gender_hint = QLabel("Elige la linea mas cercana a lo que buscan.")
        gender_hint.setObjectName("guidedStepHint")
        gender_hint.setWordWrap(True)
        self.guided_gender_row = QHBoxLayout()
        self.guided_gender_row.setSpacing(8)
        gender_section_layout.addWidget(gender_title)
        gender_section_layout.addWidget(gender_hint)
        gender_section_layout.addLayout(self.guided_gender_row)
        self.guided_gender_section.setLayout(gender_section_layout)
        steps_layout.addWidget(self.guided_gender_section)

        self.guided_products_section = QWidget()
        products_section_layout = QVBoxLayout()
        products_section_layout.setContentsMargins(0, 0, 0, 0)
        products_section_layout.setSpacing(8)
        products_title = QLabel("5. Productos sugeridos")
        products_title.setObjectName("guidedStepTitle")
        products_hint = QLabel("Toca una tarjeta para agregarla.")
        products_hint.setObjectName("guidedStepHint")
        products_hint.setWordWrap(True)
        self.guided_empty_label.setObjectName("guidedPath")
        self.guided_product_scroll = QScrollArea()
        self.guided_product_scroll.setWidgetResizable(True)
        self.guided_product_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.guided_product_scroll.setMinimumHeight(220)
        self.guided_product_container = QWidget()
        self.guided_product_grid = QGridLayout()
        self.guided_product_grid.setContentsMargins(0, 0, 0, 0)
        self.guided_product_grid.setHorizontalSpacing(12)
        self.guided_product_grid.setVerticalSpacing(12)
        self.guided_product_container.setLayout(self.guided_product_grid)
        self.guided_product_scroll.setWidget(self.guided_product_container)
        products_section_layout.addWidget(products_title)
        products_section_layout.addWidget(products_hint)
        products_section_layout.addWidget(self.guided_empty_label)
        products_section_layout.addWidget(self.guided_product_scroll, 1)
        self.guided_products_section.setLayout(products_section_layout)
        steps_layout.addWidget(self.guided_products_section, 1)
        steps_box.setLayout(steps_layout)

        detail_box = QGroupBox("Producto seleccionado")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(8)
        detail_header = QHBoxLayout()
        detail_header.setSpacing(10)
        self.guided_visual_icon_label.setFixedSize(84, 84)
        detail_header.addWidget(self.guided_visual_icon_label, 0, Qt.AlignmentFlag.AlignTop)
        detail_text_layout = QVBoxLayout()
        self.guided_detail_title_label.setObjectName("satDetailTitle")
        self.guided_detail_meta_label.setObjectName("satDetailMeta")
        self.guided_detail_meta_label.setWordWrap(True)
        self.guided_detail_notes_label.setObjectName("satDetailNotes")
        self.guided_detail_notes_label.setWordWrap(True)
        detail_text_layout.addWidget(self.guided_detail_title_label)
        detail_text_layout.addWidget(self.guided_detail_meta_label)
        detail_header.addLayout(detail_text_layout, 1)
        detail_actions = QHBoxLayout()
        detail_actions.setSpacing(8)
        self.guided_qty_spin.setRange(1, 100)
        self.guided_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.guided_qty_spin.setValue(1)
        self.guided_add_button.setObjectName("primaryButton")
        detail_actions.addStretch()
        detail_actions.addWidget(QLabel("Cantidad"))
        detail_actions.addWidget(self.guided_qty_spin)
        detail_actions.addWidget(self.guided_add_button)
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.guided_detail_notes_label)
        detail_layout.addLayout(detail_actions)
        detail_box.setLayout(detail_layout)

        layout.addWidget(intro_box)
        layout.addWidget(steps_box, 1)
        layout.addWidget(detail_box)
        content.setLayout(layout)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        page.setLayout(page_layout)
        return page

    def _build_share_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        action_card = QGroupBox("Compartir o imprimir")
        action_layout = QVBoxLayout()
        action_layout.setSpacing(10)
        self.share_status_label.setObjectName("satStatus")
        self.share_back_search_button.setObjectName("ghostButton")
        self.share_refresh_button.setObjectName("secondaryButton")
        self.quote_whatsapp_button.setObjectName("secondaryButton")
        self.quote_print_button.setObjectName("primaryButton")
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self.share_back_search_button)
        button_row.addWidget(self.share_refresh_button)
        button_row.addStretch()
        button_row.addWidget(self.quote_whatsapp_button)
        button_row.addWidget(self.quote_print_button)
        action_layout.addWidget(self.share_status_label)
        action_layout.addLayout(button_row)
        action_card.setLayout(action_layout)

        detail_card = QGroupBox("Detalle listo para salida")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(8)
        self.share_customer_label.setObjectName("satDetailTitle")
        self.share_meta_label.setObjectName("satDetailMeta")
        self.share_meta_label.setWordWrap(True)
        self.share_notes_label.setObjectName("satDetailNotes")
        self.share_notes_label.setWordWrap(True)
        self.share_detail_table.setColumnCount(5)
        self.share_detail_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
        self.share_detail_table.verticalHeader().setVisible(False)
        self.share_detail_table.setAlternatingRowColors(True)
        self.share_detail_table.setSelectionBehavior(self.share_detail_table.SelectionBehavior.SelectRows)
        detail_layout.addWidget(self.share_customer_label)
        detail_layout.addWidget(self.share_meta_label)
        detail_layout.addWidget(self.share_notes_label)
        detail_layout.addWidget(self.share_detail_table)
        detail_card.setLayout(detail_layout)

        layout.addWidget(action_card)
        layout.addWidget(detail_card, 1)
        page.setLayout(layout)
        return page

    def _build_kiosk_panel(self) -> QWidget:
        panel = QGroupBox("Escaneo rapido")
        layout = QHBoxLayout()
        layout.setSpacing(16)

        left = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        self.kiosk_scan_input.setPlaceholderText("Escanea o captura el SKU")
        self.kiosk_scan_input.setClearButtonEnabled(True)
        self.kiosk_qty_spin.setRange(1, 100)
        self.kiosk_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.kiosk_qty_spin.setValue(1)
        self.kiosk_lookup_button.setObjectName("primaryButton")
        self.kiosk_add_button.setObjectName("secondaryButton")
        self.kiosk_open_quote_button.setObjectName("secondaryButton")
        self.kiosk_open_search_button.setObjectName("ghostButton")

        scan_row = QHBoxLayout()
        scan_row.setSpacing(8)
        scan_row.addWidget(self.kiosk_scan_input, 1)
        scan_row.addWidget(QLabel("Cantidad"))
        scan_row.addWidget(self.kiosk_qty_spin)
        scan_row.addWidget(self.kiosk_lookup_button)
        scan_row.addWidget(self.kiosk_add_button)

        self.kiosk_lookup_sku_label.setObjectName("satKioskSku")
        self.kiosk_lookup_product_label.setObjectName("satKioskProduct")
        self.kiosk_lookup_price_label.setObjectName("satKioskPrice")
        self.kiosk_lookup_status_label.setObjectName("satKioskBadge")
        self.kiosk_lookup_detail_label.setObjectName("satKioskBody")
        self.kiosk_lookup_context_label.setObjectName("satKioskBody")
        self.kiosk_lookup_notes_label.setObjectName("satKioskBody")
        self.kiosk_visual_icon_label.setFixedSize(132, 132)
        self.kiosk_lookup_product_label.setWordWrap(True)
        self.kiosk_lookup_detail_label.setWordWrap(True)
        self.kiosk_lookup_context_label.setWordWrap(True)
        self.kiosk_lookup_notes_label.setWordWrap(True)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(14)
        hero_row.addWidget(self.kiosk_visual_icon_label, 0, Qt.AlignmentFlag.AlignTop)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(8)
        hero_text.addWidget(self.kiosk_lookup_sku_label)
        hero_text.addWidget(self.kiosk_lookup_product_label)
        hero_text.addWidget(self.kiosk_lookup_price_label)
        hero_text.addWidget(self.kiosk_lookup_status_label, 0, Qt.AlignmentFlag.AlignLeft)
        hero_row.addLayout(hero_text, 1)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(8)
        quick_actions.addWidget(self.kiosk_open_quote_button)
        quick_actions.addWidget(self.kiosk_open_search_button)
        quick_actions.addStretch()

        left_layout.addLayout(scan_row)
        left_layout.addLayout(hero_row)
        left_layout.addWidget(self.kiosk_lookup_detail_label)
        left_layout.addWidget(self.kiosk_lookup_context_label)
        left_layout.addWidget(self.kiosk_lookup_notes_label)
        left_layout.addLayout(quick_actions)
        left_layout.addStretch()
        left.setLayout(left_layout)

        right = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)
        recent_title = QLabel("Escaneos recientes")
        recent_title.setObjectName("satDetailTitle")
        recent_hint = QLabel("Toca una fila para volver a cargarla.")
        recent_hint.setObjectName("satMeta")
        self.kiosk_recent_table.setColumnCount(5)
        self.kiosk_recent_table.setHorizontalHeaderLabels(["SKU", "Producto", "Precio", "Escuela", "Detalle"])
        self.kiosk_recent_table.verticalHeader().setVisible(False)
        self.kiosk_recent_table.setAlternatingRowColors(True)
        self.kiosk_recent_table.setSelectionBehavior(self.kiosk_recent_table.SelectionBehavior.SelectRows)
        self.kiosk_recent_table.setMinimumWidth(480)
        self.kiosk_recent_table.setMinimumHeight(520)
        right_layout.addWidget(recent_title)
        right_layout.addWidget(recent_hint)
        right_layout.addWidget(self.kiosk_recent_table, 1)
        right.setLayout(right_layout)

        layout.addWidget(left, 4)
        layout.addWidget(right, 3)
        panel.setLayout(layout)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        editor_box = QGroupBox("Presupuesto actual")
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(10)
        configure_friendly_date_edit(self.quote_validity_input, initial_date=QDate.currentDate().addDays(15))
        self.quote_note_input.setMaximumHeight(90)
        self.quote_note_input.setPlaceholderText("Observaciones o condiciones")

        self.quote_draft_button.setObjectName("ghostButton")
        self.quote_emit_button.setObjectName("primaryButton")
        self.quote_remove_button.setObjectName("secondaryButton")
        self.quote_clear_button.setObjectName("ghostButton")
        self.quote_create_client_button.setObjectName("ghostButton")
        self.quote_school_scope_combo.addItem("Todas las escuelas", "")

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Folio"), 0, 0)
        form.addWidget(self.quote_folio_input, 0, 1, 1, 2)
        form.addWidget(QLabel("Cliente"), 0, 3)
        form.addWidget(self.quote_client_combo, 0, 4, 1, 2)
        form.addWidget(self.quote_create_client_button, 0, 6)
        form.addWidget(QLabel("Vigencia"), 1, 0)
        form.addWidget(self.quote_validity_input, 1, 1, 1, 2)
        form.addWidget(QLabel("Escuela"), 1, 3)
        form.addWidget(self.quote_school_scope_combo, 1, 4, 1, 2)
        form.addWidget(QLabel("Observacion"), 2, 0)
        form.addWidget(self.quote_note_input, 2, 1, 1, 6)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.quote_draft_button)
        actions.addWidget(self.quote_emit_button)
        actions.addStretch()
        actions.addWidget(self.quote_remove_button)
        actions.addWidget(self.quote_clear_button)

        editor_layout.addLayout(form)
        editor_layout.addLayout(actions)
        editor_box.setLayout(editor_layout)

        cart_box = QGroupBox("Carrito")
        cart_layout = QVBoxLayout()
        cart_layout.setSpacing(10)
        self.quote_cart_table.setColumnCount(7)
        self.quote_cart_table.setHorizontalHeaderLabels(
            ["SKU", "Nivel", "Escuela", "Producto", "Cantidad", "Precio", "Subtotal"]
        )
        self.quote_cart_table.verticalHeader().setVisible(False)
        self.quote_cart_table.setAlternatingRowColors(True)
        self.quote_cart_table.setSelectionBehavior(self.quote_cart_table.SelectionBehavior.SelectRows)
        self.quote_cart_table.setMinimumHeight(260)

        totals_card = QFrame()
        totals_card.setObjectName("satTotalsCard")
        totals_layout = QVBoxLayout()
        totals_layout.setContentsMargins(16, 14, 16, 14)
        totals_layout.setSpacing(4)
        totals_title = QLabel("Total estimado")
        totals_title.setObjectName("satMeta")
        self.quote_total_label.setObjectName("satTotal")
        totals_layout.addWidget(totals_title)
        totals_layout.addWidget(self.quote_total_label)
        totals_card.setLayout(totals_layout)
        self.quote_summary_label.setObjectName("satSummary")
        self.quote_school_summary_label.setObjectName("satDetailMeta")
        self.quote_school_summary_label.setWordWrap(True)

        cart_layout.addWidget(self.quote_cart_table)
        cart_layout.addWidget(totals_card, 0, Qt.AlignmentFlag.AlignRight)
        cart_layout.addWidget(self.quote_summary_label)
        cart_layout.addWidget(self.quote_school_summary_label)
        cart_box.setLayout(cart_layout)

        layout.addWidget(editor_box)
        layout.addWidget(cart_box, 1)
        panel.setLayout(layout)
        return panel

    def _build_history_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        history_box = QGroupBox("Presupuestos recientes")
        history_layout = QVBoxLayout()
        history_layout.setSpacing(10)
        self.quote_search_input.setPlaceholderText("Buscar por folio, cliente, telefono o SKU")
        self.quote_search_input.setClearButtonEnabled(True)
        self.quote_state_combo.addItem("Estado: todos", "")
        self.quote_state_combo.addItem("Emitidos", "EMITIDO")
        self.quote_state_combo.addItem("Borradores", "BORRADOR")
        self.quote_state_combo.addItem("Cancelados", "CANCELADO")
        self.quote_state_combo.addItem("Convertidos", "CONVERTIDO")
        self.quote_refresh_button.setObjectName("ghostButton")
        self.quote_resume_button.setObjectName("secondaryButton")
        self.quote_emit_selected_button.setObjectName("secondaryButton")
        self.quote_open_share_button.setObjectName("ghostButton")
        self.quote_cancel_button.setObjectName("dangerButton")
        self.quote_status_label.setObjectName("satStatus")

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.quote_search_input, 1)
        filters.addWidget(self.quote_state_combo)
        filters.addWidget(self.quote_refresh_button)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.quote_resume_button)
        actions.addWidget(self.quote_emit_selected_button)
        actions.addWidget(self.quote_open_share_button)
        actions.addStretch()
        actions.addWidget(self.quote_cancel_button)

        self.quote_table.setColumnCount(7)
        self.quote_table.setHorizontalHeaderLabels(
            ["Folio", "Cliente", "Estado", "Total", "Usuario", "Vigencia", "Fecha"]
        )
        self.quote_table.verticalHeader().setVisible(False)
        self.quote_table.setAlternatingRowColors(True)
        self.quote_table.setSelectionBehavior(self.quote_table.SelectionBehavior.SelectRows)
        self.quote_table.setMinimumHeight(320)

        history_layout.addWidget(self.quote_status_label)
        history_layout.addLayout(filters)
        history_layout.addLayout(actions)
        history_layout.addWidget(self.quote_table)
        history_box.setLayout(history_layout)

        detail_box = QGroupBox("Detalle seleccionado")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(8)
        self.quote_customer_label.setObjectName("satDetailTitle")
        self.quote_meta_label.setObjectName("satDetailMeta")
        self.quote_meta_label.setWordWrap(True)
        self.quote_notes_label.setObjectName("satDetailNotes")
        self.quote_notes_label.setWordWrap(True)
        self.quote_detail_table.setColumnCount(5)
        self.quote_detail_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
        self.quote_detail_table.verticalHeader().setVisible(False)
        self.quote_detail_table.setAlternatingRowColors(True)
        self.quote_detail_table.setSelectionBehavior(self.quote_detail_table.SelectionBehavior.SelectRows)
        detail_layout.addWidget(self.quote_customer_label)
        detail_layout.addWidget(self.quote_meta_label)
        detail_layout.addWidget(self.quote_notes_label)
        detail_layout.addWidget(self.quote_detail_table)
        detail_box.setLayout(detail_layout)

        layout.addWidget(history_box)
        layout.addWidget(detail_box, 1)
        panel.setLayout(layout)
        return panel

    def _bind_events(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_all)
        self.nav_kiosk_button.clicked.connect(lambda: self._set_page("kiosk"))
        self.nav_catalog_button.clicked.connect(lambda: self._set_page("catalog"))
        self.nav_guided_button.clicked.connect(lambda: self._set_page("guided"))
        self.nav_quote_button.clicked.connect(lambda: self._set_page("quote"))
        self.nav_search_button.clicked.connect(lambda: self._set_page("search"))
        self.nav_share_button.clicked.connect(lambda: self._set_page("share"))
        self.kiosk_open_quote_button.clicked.connect(lambda: self._set_page("quote"))
        self.kiosk_open_search_button.clicked.connect(lambda: self._set_page("catalog"))
        self.quote_refresh_button.clicked.connect(self.refresh_all)
        self.kiosk_lookup_button.clicked.connect(self._handle_lookup_scan)
        self.kiosk_scan_input.returnPressed.connect(self._handle_lookup_scan)
        self.kiosk_add_button.clicked.connect(self._handle_add_lookup_to_quote)
        self.kiosk_recent_table.itemSelectionChanged.connect(self._handle_recent_scan_selection)
        self.catalog_refresh_button.clicked.connect(self.refresh_all)
        self.catalog_search_input.textChanged.connect(self._refresh_catalog_browser)
        self.catalog_level_combo.currentIndexChanged.connect(self._handle_catalog_level_changed)
        self.catalog_school_combo.currentIndexChanged.connect(self._refresh_catalog_browser)
        self.catalog_include_general_combo.currentIndexChanged.connect(self._refresh_catalog_browser)
        self.catalog_table.itemSelectionChanged.connect(self._handle_catalog_selection)
        self.catalog_add_button.clicked.connect(self._handle_add_catalog_selection_to_quote)
        self.guided_add_button.clicked.connect(self._handle_add_guided_selection_to_quote)
        self.quote_school_scope_combo.currentIndexChanged.connect(self._refresh_quote_cart_table)
        self.quote_remove_button.clicked.connect(self._handle_remove_quote_item)
        self.quote_clear_button.clicked.connect(self._handle_clear_quote_cart)
        self.quote_draft_button.clicked.connect(self._handle_save_quote_draft)
        self.quote_emit_button.clicked.connect(self._handle_emit_quote)
        self.quote_create_client_button.clicked.connect(self._handle_create_quote_client)
        self.quote_search_input.textChanged.connect(self._handle_quote_filters_changed)
        self.quote_state_combo.currentIndexChanged.connect(self._handle_quote_filters_changed)
        self.quote_table.itemSelectionChanged.connect(self._handle_quote_selection)
        self.quote_resume_button.clicked.connect(self._handle_resume_quote)
        self.quote_emit_selected_button.clicked.connect(self._handle_emit_selected_quote)
        self.quote_open_share_button.clicked.connect(self._handle_open_share_page)
        self.quote_whatsapp_button.clicked.connect(self._handle_open_quote_whatsapp)
        self.quote_print_button.clicked.connect(self._handle_print_quote)
        self.quote_cancel_button.clicked.connect(self._handle_cancel_quote)
        self.share_back_search_button.clicked.connect(lambda: self._set_page("search"))
        self.share_refresh_button.clicked.connect(self._handle_refresh_selected_quote_detail)

    def _load_operator_context(self) -> None:
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("Usuario no encontrado.")
                if not usuario.activo:
                    raise PermissionError("El usuario no esta activo.")
                if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
                    raise PermissionError("Este usuario no puede operar el satelite de presupuestos.")
                self.current_username = str(usuario.username)
                self.current_full_name = str(usuario.nombre_completo or usuario.username)
                self.current_role = usuario.rol
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Acceso no disponible", str(exc))
            raise
        self.operator_label.setText(
            f"{self.current_full_name}"
        )

    def _set_page(self, page_key: str) -> None:
        page_index_map = {
            "kiosk": 0,
            "catalog": 1,
            "guided": 2,
            "quote": 3,
            "search": 4,
            "share": 5,
        }
        button_map = {
            "kiosk": self.nav_kiosk_button,
            "catalog": self.nav_catalog_button,
            "guided": self.nav_guided_button,
            "quote": self.nav_quote_button,
            "search": self.nav_search_button,
            "share": self.nav_share_button,
        }
        page_title_map = {
            "kiosk": "Kiosko listo para escaneo rapido.",
            "catalog": "Catalogo simplificado para cotizar por escuela.",
            "guided": "Cotiza por pasos.",
            "quote": "Ajusta el presupuesto.",
            "search": "Busqueda y seguimiento de presupuestos.",
            "share": "Salida por WhatsApp o impresion.",
        }
        self.page_stack.setCurrentIndex(page_index_map[page_key])
        button_map[page_key].setChecked(True)
        self._set_status(page_title_map[page_key])

    def refresh_all(self) -> None:
        try:
            with get_session() as session:
                self._refresh_client_combo(session)
                self._refresh_catalog_snapshot(session)
                self._refresh_quotes(session)
            self._refresh_catalog_browser()
            self._refresh_guided_browser()
            self._refresh_quote_cart_table()
            self._refresh_recent_lookup_table()
            self._set_status("Datos actualizados.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))

    def _refresh_catalog_snapshot(self, session) -> None:
        self.catalog_snapshot_rows = load_catalog_snapshot_rows(session)
        selected_level = str(self.catalog_level_combo.currentData() or "")
        level_options = sorted(
            {
                str(row["nivel_educativo_nombre"]).strip()
                for row in self.catalog_snapshot_rows
                if str(row.get("nivel_educativo_nombre", "")).strip()
                and str(row["nivel_educativo_nombre"]).strip() != "Sin nivel"
            }
        )
        self.catalog_level_combo.blockSignals(True)
        self.catalog_level_combo.clear()
        self.catalog_level_combo.addItem("Todos los niveles", "")
        for level_name in level_options:
            self.catalog_level_combo.addItem(_level_icon(level_name), level_name, level_name)
        if selected_level:
            for index in range(self.catalog_level_combo.count()):
                if str(self.catalog_level_combo.itemData(index) or "") == selected_level:
                    self.catalog_level_combo.setCurrentIndex(index)
                    break
        self.catalog_level_combo.blockSignals(False)
        self._refresh_catalog_school_options(selected_level=selected_level)

    def _handle_catalog_level_changed(self) -> None:
        self._refresh_catalog_school_options(
            selected_level=str(self.catalog_level_combo.currentData() or ""),
        )
        self._refresh_catalog_browser()

    def _refresh_catalog_school_options(self, *, selected_level: str) -> None:
        previous_school = str(self.catalog_school_combo.currentData() or "")
        school_options = build_quote_catalog_school_options(
            self.catalog_snapshot_rows,
            level_filter=selected_level,
        )
        self.catalog_school_combo.blockSignals(True)
        self.catalog_school_combo.clear()
        self.catalog_school_combo.addItem("Todas las escuelas", "")
        for school_name in school_options:
            self.catalog_school_combo.addItem(school_name, school_name)
        if previous_school and previous_school in school_options:
            for index in range(self.catalog_school_combo.count()):
                if str(self.catalog_school_combo.itemData(index) or "") == previous_school:
                    self.catalog_school_combo.setCurrentIndex(index)
                    break
        else:
            self.catalog_school_combo.setCurrentIndex(0)
        self.catalog_school_combo.blockSignals(False)

    def _refresh_catalog_browser(self) -> None:
        mode = str(self.catalog_include_general_combo.currentData() or "include_general")
        school_filter = str(self.catalog_school_combo.currentData() or "")
        include_general = mode == "include_general"
        effective_school_filter = school_filter
        if mode == "general_only":
            effective_school_filter = "General"
            include_general = False

        rows, summary = build_quote_catalog_browser(
            snapshot_rows=self.catalog_snapshot_rows,
            level_filter=str(self.catalog_level_combo.currentData() or ""),
            school_filter=effective_school_filter,
            include_general=include_general,
            search_text=self.catalog_search_input.text(),
        )
        self.catalog_table.setRowCount(len(rows))
        for row_index, row_view in enumerate(rows):
            for column_index, value in enumerate(row_view.values):
                self.catalog_table.setItem(row_index, column_index, _table_item(value))
            item = self.catalog_table.item(row_index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, row_view.sku)
        self.catalog_table.resizeColumnsToContents()
        self.catalog_status_label.setText(summary.status_label)

        if self.catalog_table.rowCount() > 0 and self.catalog_table.currentRow() < 0:
            self.catalog_table.selectRow(0)
        elif self.catalog_table.rowCount() == 0:
            self._apply_catalog_detail(None)
        self._apply_action_state()

    def _handle_catalog_selection(self) -> None:
        sku = self._selected_catalog_sku()
        if not sku:
            self._apply_catalog_detail(None)
            self._apply_action_state()
            return
        selected_row = next((row for row in self.catalog_snapshot_rows if str(row["sku"]) == sku), None)
        self._apply_catalog_detail(selected_row)
        self._apply_action_state()

    def _apply_catalog_detail(self, row: dict[str, object] | None) -> None:
        if row is None:
            self.catalog_visual_icon_label.setPixmap(_scaled_asset_pixmap("qr_icons/default.png", 72))
            self.catalog_detail_title_label.setText("Sin seleccion.")
            self.catalog_detail_meta_label.setText("Elige una variante del catalogo para verla mejor.")
            self.catalog_detail_notes_label.setText("")
            return
        self.catalog_visual_icon_label.setPixmap(_catalog_row_icon(row))
        self.catalog_detail_title_label.setText(
            f"{row['sku']} | {row['producto_nombre_base']}"
        )
        self.catalog_detail_meta_label.setText(
            f"Nivel {row['nivel_educativo_nombre']} | Escuela {row['escuela_nombre']} | {row['tipo_prenda_nombre']} | {row['tipo_pieza_nombre']} | "
            f"Talla {row['talla']} | Color {row['color']} | Precio ${Decimal(str(row['precio_venta'])).quantize(Decimal('0.01'))}"
        )
        self.catalog_detail_notes_label.setText(str(row.get("producto_descripcion") or "Sin descripcion adicional."))

    def _handle_add_catalog_selection_to_quote(self) -> None:
        sku = self._selected_catalog_sku()
        if not sku:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una variante del catalogo para agregarla.")
            return
        self._add_quote_item_by_sku(sku, self.catalog_qty_spin.value())
        self.catalog_qty_spin.setValue(1)
        self._set_page("quote")

    def _handle_guided_mode_change(self, mode_key: str) -> None:
        self.guided_mode = "basics" if mode_key == "basics" else "school"
        self.guided_selected_level = ""
        self.guided_selected_school = ""
        self.guided_selected_sku = ""
        self._refresh_guided_browser()

    def _handle_guided_level_selected(self, level_name: str) -> None:
        self.guided_selected_level = level_name
        self.guided_selected_school = ""
        self.guided_selected_sku = ""
        self._refresh_guided_browser()

    def _handle_guided_school_selected(self, school_name: str) -> None:
        self.guided_selected_school = school_name
        self.guided_selected_sku = ""
        self._refresh_guided_browser()

    def _handle_guided_gender_selected(self, gender_key: str) -> None:
        self.guided_selected_gender = gender_key
        self.guided_selected_sku = ""
        self._refresh_guided_browser()

    def _handle_guided_product_selected(self, sku: str) -> None:
        self.guided_selected_sku = sku
        row = next((item for item in self.catalog_snapshot_rows if str(item.get("sku")) == sku), None)
        self._apply_guided_detail(row)
        self._refresh_guided_product_checks()
        self._apply_action_state()

    def _refresh_guided_browser(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=self.catalog_snapshot_rows,
            mode_key=self.guided_mode,
            level_filter=self.guided_selected_level,
            school_filter=self.guided_selected_school,
            gender_filter=self.guided_selected_gender,
        )
        available_levels = {option.key for option in view.level_options}
        if self.guided_mode == "school" and self.guided_selected_level and self.guided_selected_level not in available_levels:
            self.guided_selected_level = ""
            self.guided_selected_school = ""
            self.guided_selected_sku = ""
            self._refresh_guided_browser()
            return
        available_schools = {option.key for option in view.school_options}
        if self.guided_mode == "school" and self.guided_selected_school and self.guided_selected_school not in available_schools:
            self.guided_selected_school = ""
            self.guided_selected_sku = ""
            self._refresh_guided_browser()
            return
        self.guided_status_label.setText(view.status_label)
        self.guided_path_label.setText(view.path_label)
        self.guided_empty_label.setText(view.empty_label or "Toca un producto para ver detalle.")
        show_level = self.guided_mode == "school"
        show_school = self.guided_mode == "school" and bool(self.guided_selected_level)
        show_gender = self.guided_mode == "basics" or bool(self.guided_selected_school)
        show_products = self.guided_mode == "basics" or bool(self.guided_selected_school)
        self.guided_level_section.setVisible(show_level)
        self.guided_school_section.setVisible(show_school)

        self._rebuild_guided_mode_buttons()
        self._rebuild_guided_level_buttons(view.level_options)
        self._rebuild_guided_school_buttons(view.school_options)
        self._rebuild_guided_gender_buttons(view.gender_options)
        self._rebuild_guided_product_buttons(view.product_cards)
        self.guided_gender_section.setVisible(show_gender)
        self.guided_products_section.setVisible(show_products)

        visible_skus = {card.sku for card in view.product_cards}
        if self.guided_selected_sku not in visible_skus:
            self.guided_selected_sku = view.product_cards[0].sku if view.product_cards else ""
        if self.guided_selected_sku:
            row = next(
                (item for item in self.catalog_snapshot_rows if str(item.get("sku")) == self.guided_selected_sku),
                None,
            )
            self._apply_guided_detail(row)
        else:
            self._apply_guided_detail(None)
        self._refresh_guided_product_checks()
        self._apply_action_state()

    def _rebuild_guided_mode_buttons(self) -> None:
        definitions = (
            ("school", "Uniformes por escuela\nNivel > Escuela > Genero"),
            ("basics", "Basicos y extras\nSolo piezas generales"),
        )
        if not self.guided_mode_buttons:
            for key, label in definitions:
                button = self._build_guided_choice_button(label)
                button.clicked.connect(lambda checked=False, selected=key: self._handle_guided_mode_change(selected))
                self.guided_mode_row.addWidget(button)
                self.guided_mode_buttons[key] = button
        for key, button in self.guided_mode_buttons.items():
            button.setChecked(self.guided_mode == key)

    def _rebuild_guided_level_buttons(self, options) -> None:
        self.guided_level_buttons = self._rebuild_guided_option_grid(
            layout=self.guided_level_grid,
            options=options,
            selected_key=self.guided_selected_level,
            click_handler=self._handle_guided_level_selected,
            icon_builder=lambda option: _level_icon(option.label),
        )

    def _rebuild_guided_school_buttons(self, options) -> None:
        self.guided_school_buttons = self._rebuild_guided_option_grid(
            layout=self.guided_school_grid,
            options=options,
            selected_key=self.guided_selected_school,
            click_handler=self._handle_guided_school_selected,
        )

    def _rebuild_guided_gender_buttons(self, options) -> None:
        _clear_layout(self.guided_gender_row)
        self.guided_gender_buttons = {}
        for option in options:
            button = self._build_guided_choice_button(option.label)
            button.setEnabled(option.enabled)
            button.setChecked(self.guided_selected_gender == option.key)
            button.clicked.connect(lambda checked=False, selected=option.key: self._handle_guided_gender_selected(selected))
            self.guided_gender_row.addWidget(button)
            self.guided_gender_buttons[option.key] = button
        self.guided_gender_row.addStretch()

    def _rebuild_guided_product_buttons(self, product_cards) -> None:
        _clear_layout(self.guided_product_grid)
        self.guided_product_buttons = {}
        for index, card in enumerate(product_cards):
            button = self._build_guided_product_button(card)
            button.setChecked(self.guided_selected_sku == card.sku)
            button.clicked.connect(lambda checked=False, selected=card.sku: self._handle_guided_product_selected(selected))
            self.guided_product_grid.addWidget(button, index // 3, index % 3)
            self.guided_product_buttons[card.sku] = button

    def _rebuild_guided_option_grid(self, *, layout: QGridLayout, options, selected_key: str, click_handler, icon_builder=None):
        _clear_layout(layout)
        buttons: dict[str, QPushButton] = {}
        for index, option in enumerate(options):
            button = self._build_guided_choice_button(option.label)
            button.setEnabled(option.enabled)
            button.setChecked(selected_key == option.key)
            if icon_builder is not None:
                icon = icon_builder(option)
                if not icon.isNull():
                    button.setIcon(icon)
                    button.setIconSize(QSize(24, 24))
            button.clicked.connect(lambda checked=False, selected=option.key: click_handler(selected))
            layout.addWidget(button, index // 3, index % 3)
            buttons[option.key] = button
        return buttons

    def _build_guided_choice_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("guidedChoiceButton")
        button.setCheckable(True)
        button.setMinimumHeight(60)
        return button

    def _build_guided_product_button(self, card) -> QPushButton:
        button = QPushButton(
            f"{card.title}\n{card.subtitle}\n{card.meta_label}\n{card.price_label}"
        )
        button.setObjectName("guidedProductButton")
        button.setCheckable(True)
        button.setMinimumHeight(94)
        button.setMinimumWidth(250)
        row = next((item for item in self.catalog_snapshot_rows if str(item.get("sku")) == card.sku), None)
        if row is not None:
            button.setIcon(QIcon(_catalog_row_icon(row)))
            button.setIconSize(QSize(34, 34))
        return button

    def _refresh_guided_product_checks(self) -> None:
        for sku, button in self.guided_product_buttons.items():
            button.setChecked(sku == self.guided_selected_sku)

    def _apply_guided_detail(self, row: dict[str, object] | None) -> None:
        if row is None:
            self.guided_visual_icon_label.setPixmap(_scaled_asset_pixmap("qr_icons/default.png", 72))
            self.guided_detail_title_label.setText("Sin seleccion.")
            self.guided_detail_meta_label.setText("Completa la ruta guiada y toca un producto para verlo aqui.")
            self.guided_detail_notes_label.setText("")
            return
        self.guided_visual_icon_label.setPixmap(_catalog_row_icon(row))
        segmento = _guided_segment_label(row)
        self.guided_detail_title_label.setText(f"{row['sku']} | {row['producto_nombre_base']}")
        self.guided_detail_meta_label.setText(
            f"Nivel {row['nivel_educativo_nombre']} | Escuela {row['escuela_nombre']} | Linea {segmento} | "
            f"{row['tipo_prenda_nombre']} | {row['tipo_pieza_nombre']} | Talla {row['talla']} | Color {row['color']} | "
            f"Precio ${Decimal(str(row['precio_venta'])).quantize(Decimal('0.01'))}"
        )
        self.guided_detail_notes_label.setText(str(row.get("producto_descripcion") or "Sin descripcion adicional."))

    def _handle_add_guided_selection_to_quote(self) -> None:
        if not self.guided_selected_sku:
            QMessageBox.warning(self, "Sin seleccion", "Elige un producto guiado antes de agregarlo.")
            return
        self._add_quote_item_by_sku(self.guided_selected_sku, self.guided_qty_spin.value())
        self.guided_qty_spin.setValue(1)
        self._set_page("quote")

    def _refresh_client_combo(self, session) -> None:
        selected_client_id = self._selected_client_id()
        clients = session.scalars(
            select(Cliente).where(Cliente.activo.is_(True)).order_by(Cliente.nombre.asc())
        ).all()
        self.quote_client_combo.blockSignals(True)
        self.quote_client_combo.clear()
        self.quote_client_combo.addItem("Manual / sin cliente", None)
        for client in clients:
            self.quote_client_combo.addItem(
                f"{client.codigo_cliente} · {client.nombre}",
                {
                    "id": int(client.id),
                    "nombre": str(client.nombre),
                    "telefono": str(client.telefono or ""),
                },
            )
        if selected_client_id is not None:
            for index in range(self.quote_client_combo.count()):
                item_data = self.quote_client_combo.itemData(index)
                if isinstance(item_data, dict) and int(item_data.get("id", 0)) == selected_client_id:
                    self.quote_client_combo.setCurrentIndex(index)
                    break
        self.quote_client_combo.blockSignals(False)

    def _handle_lookup_scan(self) -> None:
        sku = self.kiosk_scan_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "SKU faltante", "Escanea o captura un SKU para consultarlo.")
            return
        try:
            with get_session() as session:
                snapshot = load_quote_kiosk_lookup_snapshot(session, sku=sku)
            self.lookup_snapshot = snapshot
            self.lookup_history = push_quote_kiosk_recent_scan(self.lookup_history, snapshot)
            self._apply_lookup_view(build_quote_kiosk_lookup_view(snapshot))
            self._refresh_recent_lookup_table()
            self.kiosk_scan_input.clear()
            self.kiosk_qty_spin.setValue(1)
            self._set_status(f"{snapshot.sku} listo para presupuesto.")
        except Exception as exc:  # noqa: BLE001
            self.lookup_snapshot = None
            self._apply_lookup_view(build_error_quote_kiosk_lookup_view(str(exc)))
            QMessageBox.warning(self, "Consulta no disponible", str(exc))
        self._apply_action_state()
        self.kiosk_scan_input.setFocus()

    def _handle_add_lookup_to_quote(self) -> None:
        if self.lookup_snapshot is None:
            QMessageBox.warning(self, "Sin consulta", "Consulta primero un SKU para agregarlo al presupuesto.")
            self.kiosk_scan_input.setFocus()
            return
        self._add_quote_item_by_sku(self.lookup_snapshot.sku, self.kiosk_qty_spin.value())
        self._set_page("quote")

    def _add_quote_item_by_sku(self, sku: str, quantity: int) -> None:
        feedback = build_quote_guard_feedback(
            "add_item",
            can_operate=self._can_operate(),
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        normalized_sku = sku.strip().upper()
        if not normalized_sku:
            QMessageBox.warning(self, "Datos incompletos", "Captura un SKU antes de agregarlo.")
            return

        try:
            with get_session() as session:
                variant = PresupuestoService.obtener_variante_por_sku(session, normalized_sku)
                if variant is None:
                    raise ValueError(f"El SKU '{normalized_sku}' no existe o esta inactivo.")
                existing = next((item for item in self.quote_cart if item["sku"] == normalized_sku), None)
                if existing is None:
                    self.quote_cart.append(
                        {
                            "sku": normalized_sku,
                            "producto_nombre": str(variant.producto.nombre_base),
                            "escuela_nombre": str(variant.producto.escuela.nombre if variant.producto.escuela else "General"),
                            "nivel_educativo_nombre": str(
                                variant.producto.nivel_educativo.nombre
                                if variant.producto.nivel_educativo
                                else "Sin nivel"
                            ),
                            "cantidad": quantity,
                            "precio_unitario": Decimal(variant.precio_venta),
                        }
                    )
                else:
                    existing["cantidad"] = int(existing["cantidad"]) + quantity
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo agregar", str(exc))
            return

        self._refresh_quote_cart_table()
        self.kiosk_qty_spin.setValue(1)
        self.kiosk_scan_input.setFocus()
        self._set_status(f"{normalized_sku} agregado al presupuesto.")

    def _handle_recent_scan_selection(self) -> None:
        selected_row = self.kiosk_recent_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.lookup_history):
            return
        snapshot = self.lookup_history[selected_row]
        self.lookup_snapshot = snapshot
        self._apply_lookup_view(build_quote_kiosk_lookup_view(snapshot))
        self._apply_action_state()

    def _handle_remove_quote_item(self) -> None:
        selected_row = self.quote_cart_table.currentRow()
        feedback = build_quote_guard_feedback(
            "remove_item",
            has_selection=0 <= selected_row < len(self.quote_cart),
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        self.quote_cart.pop(selected_row)
        self._refresh_quote_cart_table()

    def _handle_clear_quote_cart(self) -> None:
        self.quote_cart.clear()
        self._refresh_quote_cart_table()
        self._reset_quote_form()
        self._set_status("Armado limpiado.")

    def _handle_save_quote_draft(self) -> None:
        self._persist_quote(EstadoPresupuesto.BORRADOR)

    def _handle_emit_quote(self) -> None:
        self._persist_quote(EstadoPresupuesto.EMITIDO)

    def _persist_quote(self, target_state: EstadoPresupuesto) -> None:
        action_key = "save_quote" if target_state == EstadoPresupuesto.EMITIDO else "save_quote"
        feedback = build_quote_guard_feedback(
            action_key,
            can_operate=self._can_operate(),
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        if not self.quote_cart:
            feedback = build_quote_guard_feedback("save_quote", has_items=bool(self.quote_cart))
            if feedback is not None:
                QMessageBox.warning(self, feedback.title, feedback.message)
                return
        try:
            with get_session() as session:
                result = save_quote_from_editor(
                    session,
                    user_id=self.user_id,
                    payload=self._build_quote_save_payload(target_state),
                )
                session.commit()
            self.quote_cart.clear()
            self._refresh_quote_cart_table()
            self._reset_quote_form()
            self.refresh_all()
            title, message = _quote_result_message(result.action_key, result.folio)
            QMessageBox.information(self, title, message)
        except Exception as exc:  # noqa: BLE001
            title = "No se pudo emitir" if target_state == EstadoPresupuesto.EMITIDO else "No se pudo guardar"
            QMessageBox.critical(self, title, str(exc))

    def _build_quote_save_payload(self, target_state: EstadoPresupuesto) -> QuoteSavePayload:
        return QuoteSavePayload(
            quote_id=self.quote_editing_id,
            folio=self.quote_folio_input.text().strip() or self._generate_quote_folio(),
            customer_id=self._selected_client_id(),
            validity_at=datetime.combine(
                self.quote_validity_input.date().toPyDate(),
                datetime.min.time(),
            ),
            notes_text=self.quote_note_input.toPlainText().strip(),
            items=tuple(
                PresupuestoItemInput(sku=str(item["sku"]), cantidad=int(item["cantidad"]))
                for item in self.quote_cart
            ),
            target_state=target_state,
        )

    def _handle_create_quote_client(self) -> None:
        feedback = build_quote_guard_feedback(
            "create_client",
            can_operate=self._can_operate(),
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        payload = self._prompt_quick_client_data()
        if payload is None:
            return
        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                client = ClientService.create_client_quick(
                    session=session,
                    usuario=user,
                    nombre=payload["nombre"],
                    telefono=payload["telefono"],
                )
                session.flush()
                client_id = int(client.id)
                session.commit()
            self.refresh_all()
            self._select_client_id(client_id)
            self._set_status(f"Cliente {payload['nombre']} creado.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))

    def _prompt_quick_client_data(self) -> dict[str, str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo cliente rapido")
        dialog.resize(420, 210)
        layout = QVBoxLayout()
        intro = QLabel("Registra nombre y telefono para seguir con el presupuesto.")
        intro.setWordWrap(True)
        form = QFormLayout()
        name_input = QLineEdit()
        phone_input = QLineEdit()
        name_input.setPlaceholderText("Nombre del cliente")
        phone_input.setPlaceholderText("Telefono")
        form.addRow("Nombre", name_input)
        form.addRow("Telefono", phone_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "nombre": name_input.text().strip(),
            "telefono": phone_input.text().strip(),
        }

    def _handle_quote_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_quotes(session)
            self._set_status("Filtros aplicados.")
        except SQLAlchemyError as exc:
            QMessageBox.critical(self, "No se pudo filtrar", str(exc))

    def _refresh_quotes(self, session) -> None:
        selected_quote_id = self._selected_quote_id()
        quote_snapshots = build_quote_history_input_rows(load_quote_snapshot_rows(session, limit=300))
        rows = build_quote_satellite_rows(
            quote_snapshots=quote_snapshots,
            search_text=self.quote_search_input.text(),
            state_filter=str(self.quote_state_combo.currentData() or ""),
        )
        summary_view = build_quote_summary_view(
            visible_count=len(rows),
            search_text=self.quote_search_input.text(),
            state_filter_value=self.quote_state_combo.currentData(),
            state_filter_text=self.quote_state_combo.currentText(),
        )
        self.quote_rows = rows

        row_views = build_quote_table_row_views(rows)
        self.quote_table.setRowCount(len(row_views))
        for row_index, row_view in enumerate(row_views):
            for column_index, value in enumerate(row_view.values):
                self.quote_table.setItem(row_index, column_index, _table_item(value))
            item = self.quote_table.item(row_index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, row_view.quote_id)
            _style_badge(self.quote_table.item(row_index, 2), row_view.status_tone)
            _style_badge(self.quote_table.item(row_index, 3), row_view.total_tone)
        self.quote_table.resizeColumnsToContents()
        self.quote_status_label.setText(summary_view.status_label)

        restored = False
        if selected_quote_id is not None:
            self.quote_table.blockSignals(True)
            for row_index in range(self.quote_table.rowCount()):
                item = self.quote_table.item(row_index, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_quote_id:
                    self.quote_table.setCurrentCell(row_index, 0)
                    self.quote_table.selectRow(row_index)
                    restored = True
                    break
            self.quote_table.blockSignals(False)
        if not restored and self.quote_table.rowCount() > 0:
            self.quote_table.selectRow(0)

        self._refresh_quote_detail(self._selected_quote_id())
        self._apply_action_state()

    def _handle_quote_selection(self) -> None:
        self._refresh_quote_detail(self._selected_quote_id())
        self._apply_action_state()

    def _handle_open_share_page(self) -> None:
        if self._selected_quote_id() is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto antes de abrir Compartir.")
            return
        self._set_page("share")

    def _handle_refresh_selected_quote_detail(self) -> None:
        self._refresh_quote_detail(self._selected_quote_id())
        if self._selected_quote_id() is not None:
            self._set_status("Detalle actualizado para compartir.")

    def _refresh_quote_detail(self, quote_id: int | None) -> None:
        if quote_id is None:
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            self._apply_quote_detail_view(build_empty_quote_detail_view())
            self._apply_share_detail_view(build_empty_quote_detail_view())
            self.share_status_label.setText("Selecciona un presupuesto desde Buscar.")
            return
        try:
            with get_session() as session:
                quote_snapshot = load_quote_detail_snapshot(session, quote_id=quote_id)
            self.selected_quote_state = str(quote_snapshot.status_label)
            self.selected_quote_phone = (
                ""
                if str(quote_snapshot.phone_text).strip().lower() == "sin telefono"
                else str(quote_snapshot.phone_text)
            )
            detail_view = build_quote_detail_view(
                folio=quote_snapshot.folio,
                client_name=quote_snapshot.customer_label,
                status_label=quote_snapshot.status_label,
                phone_text=quote_snapshot.phone_text,
                total=quote_snapshot.total,
                validity_label=quote_snapshot.validity_label,
                user_label=quote_snapshot.user_label,
                notes_text=quote_snapshot.notes_text,
                detail_rows=[
                    {
                        "sku": detail.sku,
                        "description": detail.description,
                        "quantity": detail.quantity,
                        "unit_price": detail.unit_price,
                        "subtotal": detail.subtotal,
                    }
                    for detail in quote_snapshot.detail_rows
                ],
            )
            self._apply_quote_detail_view(detail_view)
            self._apply_share_detail_view(detail_view)
            self.share_status_label.setText(f"Presupuesto {quote_snapshot.folio} listo para compartir.")
        except Exception as exc:  # noqa: BLE001
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            self._apply_quote_detail_view(build_error_quote_detail_view(str(exc)))
            self._apply_share_detail_view(build_error_quote_detail_view(str(exc)))
            self.share_status_label.setText("No se pudo cargar el detalle para compartir.")

    def _apply_quote_detail_view(self, detail_view) -> None:
        self.quote_customer_label.setText(detail_view.customer_label)
        self.quote_meta_label.setText(detail_view.meta_label)
        self.quote_notes_label.setText(detail_view.notes_label)
        self.quote_detail_table.setRowCount(len(detail_view.detail_rows))
        for row_index, detail in enumerate(detail_view.detail_rows):
            values = [
                detail.sku,
                detail.description,
                detail.quantity,
                detail.unit_price,
                detail.subtotal,
            ]
            for column_index, value in enumerate(values):
                self.quote_detail_table.setItem(row_index, column_index, _table_item(value))
        self.quote_detail_table.resizeColumnsToContents()

    def _apply_share_detail_view(self, detail_view) -> None:
        self.share_customer_label.setText(detail_view.customer_label)
        self.share_meta_label.setText(detail_view.meta_label)
        self.share_notes_label.setText(detail_view.notes_label)
        self.share_detail_table.setRowCount(len(detail_view.detail_rows))
        for row_index, detail in enumerate(detail_view.detail_rows):
            values = [
                detail.sku,
                detail.description,
                detail.quantity,
                detail.unit_price,
                detail.subtotal,
            ]
            for column_index, value in enumerate(values):
                self.share_detail_table.setItem(row_index, column_index, _table_item(value))
        self.share_detail_table.resizeColumnsToContents()

    def _apply_action_state(self) -> None:
        action_state = build_quote_satellite_action_state(
            can_operate=self._can_operate(),
            has_selection=self._selected_quote_id() is not None,
            selected_state=self.selected_quote_state,
            has_phone=bool(_normalize_whatsapp_phone(self.selected_quote_phone)),
        )
        self.quote_resume_button.setEnabled(action_state.resume_enabled)
        self.quote_emit_selected_button.setEnabled(action_state.emit_enabled)
        self.quote_cancel_button.setEnabled(action_state.cancel_enabled)
        self.quote_open_share_button.setEnabled(self._selected_quote_id() is not None)
        self.quote_whatsapp_button.setEnabled(action_state.whatsapp_enabled)
        self.quote_print_button.setEnabled(action_state.print_enabled)
        self.share_refresh_button.setEnabled(self._selected_quote_id() is not None)
        self.kiosk_add_button.setEnabled(self.lookup_snapshot is not None and self._can_operate())
        self.catalog_add_button.setEnabled(self._selected_catalog_sku() is not None and self._can_operate())
        self.guided_add_button.setEnabled(bool(self.guided_selected_sku) and self._can_operate())
        self.quote_remove_button.setEnabled(bool(self.quote_cart))
        self.quote_clear_button.setEnabled(bool(self.quote_cart))

    def _handle_resume_quote(self) -> None:
        quote_id = self._selected_quote_id()
        if quote_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un borrador para reanudarlo.")
            return
        if self.selected_quote_state != "BORRADOR":
            QMessageBox.warning(self, "Solo borradores", "Solo se pueden reanudar presupuestos en borrador.")
            return
        if self.quote_cart and QMessageBox.question(
            self,
            "Reanudar borrador",
            "El armado actual se reemplazara por el borrador seleccionado. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                snapshot = load_quote_editor_snapshot(session, quote_id=quote_id)
            self._apply_editor_snapshot(snapshot)
            self._set_status(f"Borrador {snapshot.folio} cargado.")
            self._set_page("quote")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo reanudar", str(exc))

    def _apply_editor_snapshot(self, snapshot) -> None:
        self.quote_editing_id = int(snapshot.quote_id)
        self.quote_folio_input.setText(str(snapshot.folio))
        self.quote_note_input.setPlainText(str(snapshot.notes_text or ""))
        if snapshot.validity_at is not None:
            self.quote_validity_input.setDate(
                QDate(snapshot.validity_at.year, snapshot.validity_at.month, snapshot.validity_at.day)
            )
        else:
            self.quote_validity_input.setDate(QDate.currentDate().addDays(15))
        self.quote_cart = [
            {
                "sku": line.sku,
                "producto_nombre": line.description,
                "escuela_nombre": line.school_name,
                "nivel_educativo_nombre": line.education_level_name,
                "cantidad": line.quantity,
                "precio_unitario": Decimal(line.unit_price),
            }
            for line in snapshot.detail_rows
        ]
        self._select_client_id(snapshot.customer_id)
        self._refresh_quote_cart_table()
        self.kiosk_scan_input.setFocus()

    def _handle_emit_selected_quote(self) -> None:
        quote_id = self._selected_quote_id()
        if quote_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un borrador para emitirlo.")
            return
        if self.selected_quote_state != "BORRADOR":
            QMessageBox.warning(self, "Solo borradores", "Solo se pueden emitir presupuestos en borrador.")
            return
        try:
            with get_session() as session:
                emit_quote(session, quote_id=quote_id, user_id=self.user_id)
                session.commit()
            self.refresh_all()
            folio = self._selected_quote_folio() or str(quote_id)
            title, message = _quote_result_message("emit_quote", folio)
            QMessageBox.information(self, title, message)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo emitir", str(exc))

    def _handle_cancel_quote(self) -> None:
        quote_id = self._selected_quote_id()
        feedback = build_quote_guard_feedback("cancel_quote", has_selection=quote_id is not None)
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert quote_id is not None
        if QMessageBox.question(
            self,
            "Cancelar presupuesto",
            "El presupuesto seleccionado quedara marcado como cancelado. ¿Continuar?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                cancel_quote(session, quote_id=quote_id, user_id=self.user_id)
                session.commit()
            self.refresh_all()
            title, message = _quote_result_message("cancel_quote", "")
            QMessageBox.information(self, title, message)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cancelar", str(exc))

    def _handle_print_quote(self) -> None:
        quote_id = self._selected_quote_id()
        if quote_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para imprimirlo.")
            return
        try:
            open_printable_document_flow(
                parent=self,
                session_factory=get_session,
                build_document_view=lambda session: build_quote_document_view(session, quote_id=quote_id),
                open_dialog=open_printable_text_dialog,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Impresion no disponible", str(exc))

    def _handle_open_quote_whatsapp(self) -> None:
        quote_id = self._selected_quote_id()
        if quote_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para compartirlo.")
            return
        if not self.selected_quote_phone:
            QMessageBox.warning(self, "Telefono faltante", "El presupuesto seleccionado no tiene telefono.")
            return
        try:
            with get_session() as session:
                whatsapp_view = build_quote_whatsapp_view(session, quote_id=quote_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WhatsApp no disponible", str(exc))
            return

        normalized_phone = _normalize_whatsapp_phone(whatsapp_view.phone_number)
        if not normalized_phone:
            QMessageBox.warning(self, "WhatsApp no disponible", "El telefono del presupuesto no es valido.")
            return
        whatsapp_url = f"https://wa.me/{normalized_phone}?text={quote(whatsapp_view.message)}"
        if not webbrowser.open(whatsapp_url):
            QMessageBox.warning(
                self,
                "No se pudo abrir WhatsApp",
                "No se pudo abrir WhatsApp automaticamente. Verifica que tengas navegador disponible.",
            )
            return
        self._set_status(f"WhatsApp preparado para {whatsapp_view.customer_label}.")

    def _refresh_quote_cart_table(self) -> None:
        selected_school = str(self.quote_school_scope_combo.currentData() or "")
        overall_cart_view = build_quote_cart_view(self.quote_cart)
        self._refresh_quote_school_scope_options(overall_cart_view.school_options)
        selected_school = str(self.quote_school_scope_combo.currentData() or "")
        cart_view = build_quote_cart_view(self.quote_cart, school_filter=selected_school)
        self.quote_cart_table.setRowCount(len(cart_view.rows))
        for row_index, row in enumerate(cart_view.rows):
            for column_index, value in enumerate(row.values):
                self.quote_cart_table.setItem(row_index, column_index, _table_item(value))
        self.quote_cart_table.resizeColumnsToContents()
        self.quote_total_label.setText(cart_view.summary.total_label)
        self.quote_summary_label.setText(
            cart_view.summary.summary_label
            if not selected_school
            else f"{cart_view.summary.summary_label} | Vista: {selected_school}"
        )
        self.quote_school_summary_label.setText(overall_cart_view.summary.school_summary_label)
        self.sidebar_total_label.setText(overall_cart_view.summary.total_label)
        self.sidebar_summary_label.setText(
            f"{overall_cart_view.summary.summary_label}\n{overall_cart_view.summary.school_summary_label}"
        )
        self.kiosk_budget_total_label.setText(overall_cart_view.summary.total_label)
        self.kiosk_budget_summary_label.setText(
            f"{overall_cart_view.summary.summary_label}\n{overall_cart_view.summary.school_summary_label}"
        )
        self._apply_action_state()

    def _refresh_quote_school_scope_options(self, school_options: tuple[str, ...]) -> None:
        selected_school = str(self.quote_school_scope_combo.currentData() or "")
        self.quote_school_scope_combo.blockSignals(True)
        self.quote_school_scope_combo.clear()
        self.quote_school_scope_combo.addItem("Todas las escuelas", "")
        for school_name in school_options:
            self.quote_school_scope_combo.addItem(school_name, school_name)
        if selected_school:
            for index in range(self.quote_school_scope_combo.count()):
                if str(self.quote_school_scope_combo.itemData(index) or "") == selected_school:
                    self.quote_school_scope_combo.setCurrentIndex(index)
                    break
        self.quote_school_scope_combo.blockSignals(False)

    def _apply_lookup_view(self, lookup_view) -> None:
        lookup_row = None
        if self.lookup_snapshot is not None:
            lookup_row = next(
                (row for row in self.catalog_snapshot_rows if str(row.get("sku")) == str(self.lookup_snapshot.sku)),
                None,
            )
        self.kiosk_visual_icon_label.setPixmap(
            _catalog_row_icon(lookup_row) if lookup_row is not None else _scaled_asset_pixmap("qr_icons/default.png", 112)
        )
        self.kiosk_lookup_sku_label.setText(lookup_view.sku_label)
        self.kiosk_lookup_product_label.setText(lookup_view.product_label)
        self.kiosk_lookup_price_label.setText(lookup_view.price_label)
        self.kiosk_lookup_status_label.setText(lookup_view.status_badge.text)
        _style_badge_label(self.kiosk_lookup_status_label, lookup_view.status_badge.tone)
        self.kiosk_lookup_detail_label.setText(lookup_view.detail_label)
        self.kiosk_lookup_context_label.setText(lookup_view.context_label)
        self.kiosk_lookup_notes_label.setText(lookup_view.notes_label)
        self.kiosk_lookup_notes_label.setVisible(bool(lookup_view.notes_label.strip()))

    def _refresh_recent_lookup_table(self) -> None:
        row_views = build_quote_kiosk_recent_scan_rows(self.lookup_history)
        self.kiosk_recent_table.setRowCount(len(row_views))
        for row_index, row_view in enumerate(row_views):
            for column_index, value in enumerate(row_view.values):
                self.kiosk_recent_table.setItem(row_index, column_index, _table_item(value))
            item = self.kiosk_recent_table.item(row_index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, row_view.sku)
        self.kiosk_recent_table.resizeColumnsToContents()

    def _reset_quote_form(self) -> None:
        self.quote_editing_id = None
        self.quote_client_combo.setCurrentIndex(0)
        self.quote_validity_input.setDate(QDate.currentDate().addDays(15))
        self.quote_note_input.clear()
        self.quote_folio_input.setText(self._generate_quote_folio())

    def _selected_client_id(self) -> int | None:
        selected = self.quote_client_combo.currentData()
        if isinstance(selected, dict) and selected.get("id"):
            return int(selected["id"])
        return None

    def _select_client_id(self, client_id: int | None) -> None:
        if client_id is None:
            self.quote_client_combo.setCurrentIndex(0)
            return
        for index in range(self.quote_client_combo.count()):
            item_data = self.quote_client_combo.itemData(index)
            if isinstance(item_data, dict) and int(item_data.get("id", 0)) == int(client_id):
                self.quote_client_combo.setCurrentIndex(index)
                return
        self.quote_client_combo.setCurrentIndex(0)

    def _selected_quote_id(self) -> int | None:
        selected_row = self.quote_table.currentRow()
        if selected_row < 0:
            return None
        item = self.quote_table.item(selected_row, 0)
        if item is None:
            return None
        quote_id = item.data(Qt.ItemDataRole.UserRole)
        return int(quote_id) if quote_id is not None else None

    def _selected_catalog_sku(self) -> str:
        selected_row = self.catalog_table.currentRow()
        if selected_row < 0:
            return ""
        item = self.catalog_table.item(selected_row, 0)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()

    def _selected_quote_folio(self) -> str:
        selected_row = self.quote_table.currentRow()
        if selected_row < 0:
            return ""
        item = self.quote_table.item(selected_row, 0)
        return item.text().strip() if item is not None else ""

    def _can_operate(self) -> bool:
        return self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    @staticmethod
    def _generate_quote_folio() -> str:
        return f"PRE-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"


def _table_item(value: object) -> QTableWidgetItem:
    if isinstance(value, Decimal):
        text = f"{value.quantize(Decimal('0.01'))}"
    else:
        text = str(value)
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
    item.setForeground(QBrush(QColor("#2f2a24")))
    return item


def _style_badge(item: QTableWidgetItem | None, tone: str) -> None:
    if item is None:
        return
    palette = {
        "positive": QColor("#dbeedb"),
        "warning": QColor("#f7e8be"),
        "danger": QColor("#f4d8d4"),
        "muted": QColor("#ebe4da"),
    }
    item.setBackground(palette.get(tone, palette["muted"]))


def _style_badge_label(label: QLabel, tone: str) -> None:
    palette = {
        "positive": ("#dbeedb", "#1f4d26"),
        "warning": ("#f7e8be", "#7a5710"),
        "danger": ("#f4d8d4", "#7b241b"),
        "neutral": ("#ebe4da", "#5d4c3f"),
        "muted": ("#ebe4da", "#5d4c3f"),
    }
    background, foreground = palette.get(tone, palette["muted"])
    label.setStyleSheet(
        f"background: {background}; color: {foreground}; border-radius: 12px; padding: 8px 12px; font-weight: 800;"
    )


def _asset_path(relative_path: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / relative_path


def _icon_from_asset(relative_path: str) -> QIcon:
    asset_path = _asset_path(relative_path)
    return QIcon(str(asset_path)) if asset_path.exists() else QIcon()


def _scaled_asset_pixmap(relative_path: str, size: int) -> QPixmap:
    pixmap = QPixmap(str(_asset_path(relative_path)))
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _level_icon(level_name: str) -> QIcon:
    normalized = str(level_name).strip().lower()
    asset_name = {
        "preescolar": "kiosk_icons/level_pre.svg",
        "primaria": "kiosk_icons/level_prim.svg",
        "secundaria": "kiosk_icons/level_sec.svg",
        "prepa": "kiosk_icons/level_prepa.svg",
        "preparatoria": "kiosk_icons/level_prepa.svg",
    }.get(normalized, "kiosk_icons/level_prim.svg")
    return _icon_from_asset(asset_name)


def _catalog_row_icon(row: dict[str, object]) -> QPixmap:
    product_name = str(row.get("producto_nombre_base") or "").lower()
    garment_type = str(row.get("tipo_prenda_nombre") or "").lower()
    piece_type = str(row.get("tipo_pieza_nombre") or "").lower()
    icon_candidates = (
        garment_type,
        piece_type,
        product_name,
    )
    icon_map = {
        "camisa": "qr_icons/camisa.png",
        "playera": "qr_icons/playera.png",
        "falda": "qr_icons/falda.png",
        "pantalon": "qr_icons/pantalon.png",
        "pants": "qr_icons/pants_suelto.png",
        "sueter": "qr_icons/sueter.png",
        "chaleco": "qr_icons/chaleco.png",
        "jumper": "qr_icons/jumper.png",
        "calceta": "qr_icons/calceta.png",
        "corbata": "qr_icons/corbata.png",
        "corbatin": "qr_icons/corbatin.png",
        "bata": "qr_icons/bata.png",
        "boina": "qr_icons/boina.png",
        "malla": "qr_icons/malla.png",
        "guante": "qr_icons/guante.png",
        "chamarra": "qr_icons/chamarra.png",
    }
    for candidate in icon_candidates:
        for token, asset_name in icon_map.items():
            if token in candidate:
                return _scaled_asset_pixmap(asset_name, 72)
    return _scaled_asset_pixmap("qr_icons/default.png", 72)


def _normalize_whatsapp_phone(phone: str) -> str:
    digits = "".join(character for character in str(phone) if character.isdigit())
    if digits.startswith("521") and len(digits) == 13:
        return f"52{digits[3:]}"
    if len(digits) == 10:
        return f"52{digits}"
    return digits


def _quote_result_message(action_key: str, folio: str) -> tuple[str, str]:
    if action_key == "save_quote_draft":
        return "Borrador guardado", f"Borrador {folio} guardado correctamente."
    if action_key == "update_quote_draft":
        return "Borrador actualizado", f"Borrador {folio} actualizado correctamente."
    if action_key == "save_quote":
        return "Presupuesto emitido", f"Presupuesto {folio} emitido correctamente."
    if action_key == "emit_quote":
        return "Presupuesto emitido", f"Presupuesto {folio} emitido correctamente."
    if action_key == "cancel_quote":
        return "Presupuesto cancelado", "El presupuesto se marco como cancelado."
    return "Operacion completada", f"Operacion completada para {folio}."


def _guided_segment_label(row: dict[str, object]) -> str:
    garment_type = str(row.get("tipo_prenda_nombre") or "").strip().lower()
    gender = str(row.get("producto_genero") or "").strip().lower()
    if "deport" in garment_type:
        return "Deportivo"
    if "niña" in gender or "nina" in gender or "femen" in gender or "dama" in gender:
        return "Oficial Niña"
    if "niño" in gender or "nino" in gender or "mascul" in gender or "caballero" in gender:
        return "Oficial Niño"
    return "Oficial"


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)
