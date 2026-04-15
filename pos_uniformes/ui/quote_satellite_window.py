"""Ventana satelite para gestion dedicada de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, QSize, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QImage, QKeySequence, QPixmap, QShortcut
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
    QHeaderView,
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
    QSizePolicy,
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
from pos_uniformes.services.active_filter_service import build_active_filter_tokens
from pos_uniformes.services.catalog_local_cache_service import (
    catalog_cache_saved_at,
    format_cache_age_label,
    save_catalog_cache,
)
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.presupuesto_service import PresupuestoService
from pos_uniformes.services.quote_client_creation_feedback_service import build_quote_client_created_feedback
from pos_uniformes.services.quote_action_service import cancel_quote, emit_quote
from pos_uniformes.services.quote_detail_service import load_quote_detail_snapshot
from pos_uniformes.services.quote_document_view_service import build_quote_document_view
from pos_uniformes.services.quote_editor_service import QuoteSavePayload, load_quote_editor_snapshot, save_quote_from_editor
from pos_uniformes.services.quote_kiosk_lookup_service import QuoteKioskLookupSnapshot, load_quote_kiosk_lookup_snapshot
from pos_uniformes.services.quote_snapshot_service import build_quote_history_input_rows, load_quote_snapshot_rows
from pos_uniformes.services.quote_whatsapp_service import build_quote_whatsapp_view
from pos_uniformes.services.sale_selected_client_service import find_active_sale_client_by_code
from pos_uniformes.services.sale_cart_update_service import update_sale_cart_item_quantity
from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog
from pos_uniformes.ui.helpers.date_field_helper import configure_friendly_date_edit
from pos_uniformes.ui.helpers.flow_layout import FlowLayout
from pos_uniformes.ui.helpers.active_filter_chip_helper import rebuild_active_filter_chips
from pos_uniformes.ui.helpers.printable_document_flow_helper import open_printable_document_flow
from pos_uniformes.ui.helpers.catalog_pagination_helper import build_catalog_pagination_view
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
from pos_uniformes.ui.helpers.quote_scanned_client_helper import build_quote_scanned_client_ui_state
from pos_uniformes.ui.helpers.quote_sports_uniform_helper import (
    add_quote_scan_variants,
    build_quote_presupuesto_inputs,
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
from pos_uniformes.ui.styles.satellite_styles import build_satellite_stylesheet
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import restore_sports_uniform_playera_price_if_needed
from pos_uniformes.utils.app_metadata import satellite_build_label, satellite_display_name, satellite_windows_icon_path
from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
from pos_uniformes.services.inventory_label_service import (
    InventoryLabelContext,
    load_inventory_label_context,
    render_inventory_label,
    render_inventory_label_from_cache_row,
)

SATELLITE_SEARCH_DEBOUNCE_MS = 300
_LABEL_PRINT_PINS = {"634700", "12345"}
SATELLITE_CATALOG_PAGE_SIZE = 25
SATELLITE_QUOTE_VALIDITY_DAYS = 7

try:
    from PyQt6.QtWidgets import QScroller as _QScroller
    _SCROLLER_GESTURE = _QScroller.ScrollerGestureType.LeftMouseButtonGesture
    _TOUCH_SCROLL_AVAILABLE = True
except Exception:
    _TOUCH_SCROLL_AVAILABLE = False


@dataclass
class GuidedFlowState:
    """Estado de navegación de la página de presupuesto guiado."""

    mode: str = "school"
    level: str = ""
    school: str = ""
    gender: str = "TODOS"
    profile: str = "TODOS"
    bucket: str = "TODOS"
    piece: str = ""
    product_key: str = ""
    sku: str = ""

    def reset(self, mode_key: str) -> None:
        self.mode = "basics" if mode_key == "basics" else "school"
        self.level = ""
        self.school = ""
        self.gender = "TODOS"
        self.profile = "TODOS"
        self.bucket = "BASICO" if self.mode == "basics" else "TODOS"
        self.piece = ""
        self.product_key = ""
        self.sku = ""


class QuoteSatelliteWindow(QMainWindow):
    def __init__(
        self,
        user_id: int | None,
        offline_mode: bool = False,
        offline_catalog_cache: list[dict] | None = None,
    ) -> None:
        super().__init__()
        self.user_id = user_id
        self.offline_mode = offline_mode
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
        self.catalog_browser_visible_skus: tuple[str, ...] = ()
        self.catalog_browser_page_index = 0
        self.current_page_key = "kiosk"
        self.catalog_browser_debounce_timer = QTimer(self)
        self.catalog_browser_debounce_timer.setSingleShot(True)
        self.catalog_browser_debounce_timer.setInterval(SATELLITE_SEARCH_DEBOUNCE_MS)
        self.catalog_browser_debounce_timer.timeout.connect(self._run_catalog_browser_refresh)

        self._build_widgets()
        self._apply_icons()
        self._apply_styles()
        self._build_ui()
        self._bind_events()

        if self.offline_mode:
            self._init_offline(offline_catalog_cache or [])
        else:
            self._load_operator_context()
            self._reset_quote_form()
            self._apply_lookup_view(build_empty_quote_kiosk_lookup_view())
            self._apply_catalog_detail(None)
            self._apply_guided_detail(None)
            self._refresh_recent_lookup_table()
            self.refresh_all()

        QTimer.singleShot(0, self.kiosk_scan_input.setFocus)

    def _init_offline(self, cache_rows: list[dict]) -> None:
        """Inicializa la ventana en modo local sin tocar la base de datos."""
        self.catalog_snapshot_rows = cache_rows
        self.operator_label.setText("Modo local")

        # Mostrar banner con antiguedad del cache
        saved_at = catalog_cache_saved_at()
        age_text = format_cache_age_label(saved_at) if saved_at else "cache local disponible"
        self.offline_banner.setText(
            f"Modo local \u2014 Catalogo {age_text}. "
            "Enciende la PC principal para datos en vivo."
        )
        self.offline_banner.setVisible(True)

        # Deshabilitar pestanas que requieren base de datos
        self.nav_quote_button.setEnabled(False)
        self.nav_quote_button.setToolTip("No disponible en modo local")
        self.nav_share_button.setEnabled(False)
        self.nav_share_button.setToolTip("No disponible en modo local")
        self.refresh_button.setEnabled(False)
        self.refresh_button.setToolTip("Sin conexion con la PC principal")

        self._reset_quote_form()
        self._apply_lookup_view(build_empty_quote_kiosk_lookup_view())
        self._apply_catalog_detail(None)
        self._apply_guided_detail(None)
        self._refresh_recent_lookup_table()

        # Refrescar vistas que no necesitan DB
        self._refresh_catalog_snapshot_from_cache()
        self._refresh_catalog_browser()
        self._refresh_guided_browser()
        self._set_status("Modo local — catalogo guardado disponible.")

    def _build_widgets(self) -> None:
        self.operator_label = QLabel("Sin operador")
        self.version_label = QLabel(satellite_build_label())
        self.status_label = QLabel("Listo.")
        self.offline_banner = QLabel("")
        self.offline_banner.setObjectName("offlineBanner")
        self.offline_banner.setWordWrap(True)
        self.offline_banner.setVisible(False)
        self.quick_scan_input = QLineEdit()
        self.quick_scan_button = QPushButton("Escanear")
        self.refresh_button = QPushButton("Refrescar")
        self.exit_button = QPushButton("Salir")
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
        self.sidebar_items_count_label = QLabel("0 lineas | 0 pzas")
        self.sidebar_items_scroll = QScrollArea()
        self.sidebar_items_content = QWidget()
        self.sidebar_items_layout = QVBoxLayout()
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
        self.catalog_print_label_button = QPushButton("Imprimir etiqueta")
        self.catalog_status_label = QLabel("Sin catalogo cargado.")
        self.catalog_active_filters_wrap = QWidget()
        self.catalog_active_filters_flow_layout = None
        self.catalog_pagination_label = QLabel("0 de 0 | p. 1/1")
        self.catalog_previous_page_button = QPushButton("Anterior")
        self.catalog_next_page_button = QPushButton("Siguiente")
        self.catalog_table = QTableWidget()
        self.catalog_visual_icon_label = QLabel()
        self.catalog_detail_title_label = QLabel("Sin seleccion.")
        self.catalog_detail_meta_label = QLabel("")
        self.catalog_detail_notes_label = QLabel("")
        self.catalog_level_combo = QComboBox()
        self._gfs = GuidedFlowState()
        self.guided_status_label = QLabel("Empieza eligiendo una ruta.")
        self.guided_path_label = QLabel("Uniformes > sin nivel > sin escuela > Todos")
        self.guided_empty_label = QLabel("Selecciona una ruta para comenzar.")
        self.guided_qty_spin = QSpinBox()
        self.guided_add_button = QPushButton("Agregar al presupuesto")
        self.guided_print_label_button = QPushButton("Imprimir etiqueta")
        self.guided_reset_button = QPushButton("Limpiar pasos")
        self.guided_basics_button = QPushButton("Piezas generales")
        self.guided_visual_icon_label = QLabel()
        self.guided_detail_title_label = QLabel("Sin seleccion.")
        self.guided_detail_meta_label = QLabel("")
        self.guided_detail_notes_label = QLabel("")
        self.guided_mode_buttons: dict[str, QPushButton] = {}
        self.guided_level_buttons: dict[str, QPushButton] = {}
        self.guided_school_buttons: dict[str, QPushButton] = {}
        self.guided_gender_buttons: dict[str, QPushButton] = {}
        self.guided_profile_buttons: dict[str, QPushButton] = {}
        self.guided_bucket_buttons: dict[str, QPushButton] = {}
        self.guided_piece_buttons: dict[str, QPushButton] = {}
        self.guided_variant_buttons: dict[str, QPushButton] = {}
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
        self.quote_qty_down_button = QPushButton("-1")
        self.quote_qty_up_button = QPushButton("+1")
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
        self.quote_whatsapp_button = QPushButton("Compartir por WhatsApp")
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
        self.setStyleSheet(build_satellite_stylesheet())

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{satellite_display_name()} | {satellite_build_label()}")
        self.resize(1560, 980)
        icon_path = satellite_windows_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        header_card = QFrame()
        header_card.setObjectName("satHeaderCard")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel(satellite_display_name())
        title.setObjectName("satTitle")
        self.operator_label.setObjectName("satMeta")
        self.version_label.setObjectName("satMeta")
        self.status_label.setObjectName("satStatus")
        title_layout.addWidget(title)
        title_layout.addWidget(self.version_label)
        title_layout.addWidget(self.operator_label)
        header_layout.addLayout(title_layout, 1)
        header_layout.addWidget(self.status_label, 1, Qt.AlignmentFlag.AlignRight)
        self.refresh_button.setObjectName("secondaryButton")
        self.exit_button.setObjectName("exitButton")
        header_layout.addWidget(self.refresh_button)
        header_layout.addWidget(self.exit_button)
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
        root_layout.addWidget(self.offline_banner)
        root_layout.addWidget(content, 1)
        root.setLayout(root_layout)
        self.setCentralWidget(root)
        self._set_page("kiosk")
        self._apply_touch_scrolling()

    def _apply_touch_scrolling(self) -> None:
        """Activa scroll por arrastre en todas las tablas y areas scrollables."""
        if not _TOUCH_SCROLL_AVAILABLE:
            return
        for widget in (
            self.catalog_table,
            self.kiosk_recent_table,
            self.quote_table,
            self.share_detail_table,
            self.quote_cart_table,
        ):
            _QScroller.grabGesture(widget.viewport(), _SCROLLER_GESTURE)
        for scroll_area in (
            self.sidebar_items_scroll,
            self.guided_product_scroll,
            self.guided_page_scroll,
            self.guided_school_scroll,
        ):
            _QScroller.grabGesture(scroll_area.viewport(), _SCROLLER_GESTURE)

    def _build_sidebar(self) -> QWidget:
        card = QFrame()
        card.setObjectName("satSidebarCard")
        card.setFixedWidth(278)
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

        items_card = QFrame()
        items_card.setObjectName("satTotalsCard")
        items_layout = QVBoxLayout()
        items_layout.setContentsMargins(14, 14, 14, 14)
        items_layout.setSpacing(8)
        items_title = QLabel("Piezas agregadas")
        items_title.setObjectName("satSidebarTitle")
        self.sidebar_items_count_label.setObjectName("satSidebarSectionMeta")
        self.sidebar_items_scroll.setObjectName("satSidebarItemsScroll")
        self.sidebar_items_scroll.setWidgetResizable(True)
        self.sidebar_items_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_items_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_items_scroll.viewport().setObjectName("satSidebarItemsViewport")
        self.sidebar_items_content.setObjectName("satSidebarItemsContent")
        self.sidebar_items_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_items_layout.setSpacing(8)
        self.sidebar_items_content.setLayout(self.sidebar_items_layout)
        self.sidebar_items_scroll.setWidget(self.sidebar_items_content)
        self.sidebar_items_scroll.setMinimumHeight(180)
        items_layout.addWidget(items_title)
        items_layout.addWidget(self.sidebar_items_count_label)
        items_layout.addWidget(self.sidebar_items_scroll, 1)
        items_card.setLayout(items_layout)

        layout.addWidget(budget_card)
        layout.addWidget(items_card, 1)
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
        self.catalog_pagination_label.setObjectName("satPager")
        self.catalog_search_input.setPlaceholderText("Buscar por SKU, producto, talla, color o tipo")
        self.catalog_search_input.setClearButtonEnabled(True)
        self.catalog_search_input.setMinimumWidth(520)
        self.catalog_refresh_button.setObjectName("ghostButton")
        self.catalog_add_button.setObjectName("primaryButton")
        self.catalog_add_button.setMinimumHeight(38)
        self.catalog_previous_page_button.setObjectName("ghostButton")
        self.catalog_next_page_button.setObjectName("ghostButton")
        self.catalog_level_combo.setObjectName("satFilterCombo")
        self.catalog_school_combo.setObjectName("satFilterCombo")
        self.catalog_include_general_combo.setObjectName("satFilterCombo")
        self.catalog_level_combo.addItem("Todos los niveles", "")
        self.catalog_include_general_combo.addItem("Escuela + extras generales", "include_general")
        self.catalog_include_general_combo.addItem("Solo escuela", "school_only")
        self.catalog_include_general_combo.addItem("Solo generales", "general_only")
        self.catalog_include_general_combo.setCurrentIndex(1)
        self.catalog_school_combo.addItem("Todas las escuelas", "")
        self.catalog_status_label.setVisible(False)
        self.catalog_active_filters_wrap.setVisible(False)
        self.catalog_active_filters_flow_layout = FlowLayout(
            self.catalog_active_filters_wrap,
            margin=0,
            h_spacing=6,
            v_spacing=6,
        )
        self.catalog_active_filters_wrap.setLayout(self.catalog_active_filters_flow_layout)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.catalog_level_combo, 2)
        filters.addWidget(self.catalog_school_combo, 3)
        filters.addWidget(self.catalog_include_general_combo, 3)

        self.catalog_print_label_button.setObjectName("ghostButton")

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.catalog_search_input, 2)
        search_row.addStretch(1)
        search_row.addWidget(self.catalog_print_label_button)
        search_row.addWidget(self.catalog_add_button)
        search_row.addWidget(self.catalog_refresh_button)

        self.catalog_table.setColumnCount(8)
        self.catalog_table.setHorizontalHeaderLabels(
            ["SKU", "Nivel", "Escuela", "Producto", "Prenda", "Talla", "Color", "Precio"]
        )
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSelectionBehavior(self.catalog_table.SelectionBehavior.SelectRows)
        self.catalog_table.setMinimumHeight(360)
        _configure_satellite_table(
            self.catalog_table,
            stretch_columns=(3,),
            resize_columns=(0, 1, 2, 4, 5, 6, 7),
        )

        browser_layout.addLayout(filters)
        browser_layout.addLayout(search_row)
        browser_layout.addWidget(self.catalog_active_filters_wrap)
        pager_row = QHBoxLayout()
        pager_row.setSpacing(8)
        pager_row.addWidget(self.catalog_pagination_label)
        pager_row.addStretch()
        pager_row.addWidget(self.catalog_previous_page_button)
        pager_row.addWidget(self.catalog_next_page_button)
        browser_layout.addLayout(pager_row)
        browser_layout.addWidget(self.catalog_table, 1)
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
        page.setObjectName("guidedPageRoot")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        self.guided_page_scroll = scroll
        scroll.setObjectName("guidedPageScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setObjectName("guidedPageViewport")

        content = QWidget()
        content.setObjectName("guidedPageSurface")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.guided_status_label.setObjectName("guidedStepHint")
        self.guided_path_label.setObjectName("guidedPath")

        steps_box = QFrame()
        steps_box.setObjectName("guidedStepsCard")
        steps_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        steps_layout = QVBoxLayout()
        steps_layout.setContentsMargins(12, 10, 12, 8)
        steps_layout.setSpacing(4)
        _steps_title = QLabel("Cotiza por pasos")
        _steps_title.setObjectName("guidedGroupBoxTitle")
        steps_layout.addWidget(_steps_title)
        steps_layout.addWidget(self.guided_path_label)

        mode_title = QLabel("1. Elige una ruta")
        mode_title.setObjectName("guidedStepTitle")
        mode_title.setProperty("step", "1")
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
        level_title.setProperty("step", "2")
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
        school_title.setProperty("step", "3")
        school_hint = QLabel("Escuelas del nivel elegido.")
        school_hint.setObjectName("guidedStepHint")
        school_hint.setWordWrap(True)
        school_scroll = QScrollArea()
        self.guided_school_scroll = school_scroll
        school_scroll.setWidgetResizable(True)
        school_scroll.setFrameShape(QFrame.Shape.NoFrame)
        school_scroll.setMinimumHeight(120)
        school_scroll.setObjectName("guidedScrollArea")
        school_scroll.viewport().setObjectName("guidedScrollViewport")
        self.guided_school_container = QWidget()
        self.guided_school_container.setObjectName("guidedGridSurface")
        self.guided_school_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        self.guided_gender_title_label = QLabel("4. Elige tipo de uniforme")
        self.guided_gender_title_label.setObjectName("guidedStepTitle")
        self.guided_gender_title_label.setProperty("step", "4")
        self.guided_gender_hint_label = QLabel("Elige la linea mas cercana a lo que buscan.")
        self.guided_gender_hint_label.setObjectName("guidedStepHint")
        self.guided_gender_hint_label.setWordWrap(True)
        self.guided_gender_row = QHBoxLayout()
        self.guided_gender_row.setSpacing(8)
        gender_section_layout.addWidget(self.guided_gender_title_label)
        gender_section_layout.addWidget(self.guided_gender_hint_label)
        gender_section_layout.addLayout(self.guided_gender_row)
        self.guided_gender_section.setLayout(gender_section_layout)
        steps_layout.addWidget(self.guided_gender_section)

        self.guided_profile_section = QWidget()
        profile_section_layout = QVBoxLayout()
        profile_section_layout.setContentsMargins(0, 0, 0, 0)
        profile_section_layout.setSpacing(8)
        self.guided_profile_title_label = QLabel("5. Elige perfil oficial")
        self.guided_profile_title_label.setObjectName("guidedStepTitle")
        self.guided_profile_title_label.setProperty("step", "5")
        self.guided_profile_hint_label = QLabel("Usa este paso solo para separar niña, niño o compartido.")
        self.guided_profile_hint_label.setObjectName("guidedStepHint")
        self.guided_profile_hint_label.setWordWrap(True)
        self.guided_profile_row = QHBoxLayout()
        self.guided_profile_row.setSpacing(8)
        profile_section_layout.addWidget(self.guided_profile_title_label)
        profile_section_layout.addWidget(self.guided_profile_hint_label)
        profile_section_layout.addLayout(self.guided_profile_row)
        self.guided_profile_section.setLayout(profile_section_layout)
        steps_layout.addWidget(self.guided_profile_section)

        self.guided_bucket_section = QWidget()
        bucket_section_layout = QVBoxLayout()
        bucket_section_layout.setContentsMargins(0, 0, 0, 0)
        bucket_section_layout.setSpacing(8)
        self.guided_bucket_title_label = QLabel("5. Elige grupo")
        self.guided_bucket_title_label.setObjectName("guidedStepTitle")
        self.guided_bucket_title_label.setProperty("step", "5")
        self.guided_bucket_hint_label = QLabel("Separa basicos y extras para reducir la lista.")
        self.guided_bucket_hint_label.setObjectName("guidedStepHint")
        self.guided_bucket_hint_label.setWordWrap(True)
        self.guided_bucket_row = QHBoxLayout()
        self.guided_bucket_row.setSpacing(8)
        bucket_section_layout.addWidget(self.guided_bucket_title_label)
        bucket_section_layout.addWidget(self.guided_bucket_hint_label)
        bucket_section_layout.addLayout(self.guided_bucket_row)
        self.guided_bucket_section.setLayout(bucket_section_layout)
        steps_layout.addWidget(self.guided_bucket_section)

        self.guided_piece_section = QWidget()
        piece_section_layout = QVBoxLayout()
        piece_section_layout.setContentsMargins(0, 0, 0, 0)
        piece_section_layout.setSpacing(8)
        self.guided_piece_title_label = QLabel("6. Elige tipo de pieza")
        self.guided_piece_title_label.setObjectName("guidedStepTitle")
        self.guided_piece_title_label.setProperty("step", "6")
        self.guided_piece_hint_label = QLabel("Primero elige la familia de prenda que buscan.")
        self.guided_piece_hint_label.setObjectName("guidedStepHint")
        self.guided_piece_hint_label.setWordWrap(True)
        self.guided_piece_groups_layout = QVBoxLayout()
        self.guided_piece_groups_layout.setContentsMargins(0, 0, 0, 0)
        self.guided_piece_groups_layout.setSpacing(6)
        piece_section_layout.addWidget(self.guided_piece_title_label)
        piece_section_layout.addWidget(self.guided_piece_hint_label)
        piece_section_layout.addLayout(self.guided_piece_groups_layout)
        self.guided_piece_section.setLayout(piece_section_layout)
        steps_layout.addWidget(self.guided_piece_section)

        self.guided_products_section = QWidget()
        products_section_layout = QVBoxLayout()
        products_section_layout.setContentsMargins(0, 0, 0, 0)
        products_section_layout.setSpacing(8)
        self.guided_products_title_label = QLabel("7. Modelos sugeridos")
        self.guided_products_title_label.setObjectName("guidedStepTitle")
        self.guided_products_title_label.setProperty("step", "7")
        self.guided_products_hint_label = QLabel("Toca una tarjeta para elegir el modelo.")
        self.guided_products_hint_label.setObjectName("guidedStepHint")
        self.guided_products_hint_label.setWordWrap(True)
        self.guided_empty_label.setObjectName("guidedPath")
        self.guided_product_scroll = QScrollArea()
        self.guided_product_scroll.setWidgetResizable(True)
        self.guided_product_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.guided_product_scroll.setMinimumHeight(160)
        self.guided_product_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.guided_product_scroll.setObjectName("guidedScrollArea")
        self.guided_product_scroll.viewport().setObjectName("guidedScrollViewport")
        self.guided_product_container = QWidget()
        self.guided_product_container.setObjectName("guidedGridSurface")
        self.guided_product_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.guided_product_flow_layout = FlowLayout(margin=0, h_spacing=4, v_spacing=8)
        self.guided_product_container.setLayout(self.guided_product_flow_layout)
        self.guided_product_scroll.setWidget(self.guided_product_container)
        products_section_layout.addWidget(self.guided_products_title_label)
        products_section_layout.addWidget(self.guided_products_hint_label)
        products_section_layout.addWidget(self.guided_empty_label)
        products_section_layout.addWidget(self.guided_product_scroll, 1)
        self.guided_products_section.setLayout(products_section_layout)
        steps_layout.addWidget(self.guided_products_section, 1)
        guided_footer_actions = QHBoxLayout()
        guided_footer_actions.setSpacing(8)
        guided_footer_actions.addStretch()
        self.guided_reset_button.setObjectName("ghostButton")
        self.guided_basics_button.setObjectName("secondaryButton")
        guided_footer_actions.addWidget(self.guided_reset_button)
        guided_footer_actions.addWidget(self.guided_basics_button)
        steps_layout.addLayout(guided_footer_actions)
        steps_box.setLayout(steps_layout)

        detail_box = QFrame()
        detail_box.setObjectName("guidedStepsCard")
        detail_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(12, 10, 12, 8)
        detail_layout.setSpacing(8)
        _detail_title = QLabel("Producto seleccionado")
        _detail_title.setObjectName("guidedGroupBoxTitle")
        detail_layout.addWidget(_detail_title)
        detail_header = QHBoxLayout()
        detail_header.setSpacing(10)
        self.guided_visual_icon_label.setFixedSize(72, 72)
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
        self.guided_variant_section = QWidget()
        variant_section_layout = QVBoxLayout()
        variant_section_layout.setContentsMargins(0, 0, 0, 0)
        variant_section_layout.setSpacing(6)
        self.guided_variant_title_label = QLabel("Variantes disponibles")
        self.guided_variant_title_label.setObjectName("guidedStepHint")
        self.guided_variant_groups_layout = QVBoxLayout()
        self.guided_variant_groups_layout.setContentsMargins(0, 0, 0, 0)
        self.guided_variant_groups_layout.setSpacing(6)
        variant_section_layout.addWidget(self.guided_variant_title_label)
        variant_section_layout.addLayout(self.guided_variant_groups_layout)
        self.guided_variant_section.setLayout(variant_section_layout)
        self.guided_detail_scroll = self.guided_variant_section  # alias para compatibilidad

        detail_actions = QHBoxLayout()
        detail_actions.setSpacing(8)
        self.guided_qty_spin.setRange(1, 100)
        self.guided_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.guided_qty_spin.setValue(1)
        self.guided_add_button.setObjectName("primaryButton")
        self.guided_add_button.setMinimumHeight(38)
        self.guided_print_label_button.setObjectName("ghostButton")
        detail_actions.addStretch()
        detail_actions.addWidget(self.guided_print_label_button)
        detail_actions.addWidget(QLabel("Cantidad"))
        detail_actions.addWidget(self.guided_qty_spin)
        detail_actions.addWidget(self.guided_add_button)
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.guided_detail_notes_label)
        detail_layout.addWidget(self.guided_variant_section)
        detail_layout.addLayout(detail_actions)
        detail_box.setLayout(detail_layout)

        layout.addWidget(steps_box)
        layout.addWidget(detail_box)
        layout.addSpacing(160)
        content.setLayout(layout)
        scroll.setWidget(content)

        page_layout.addWidget(scroll, 1)
        page.setLayout(page_layout)
        return page

    def _build_share_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        action_card = QGroupBox("Salida del presupuesto")
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
        self.share_detail_table.setColumnCount(6)
        self.share_detail_table.setHorizontalHeaderLabels(["SKU", "Producto", "Talla", "Cantidad", "Precio", "Subtotal"])
        self.share_detail_table.verticalHeader().setVisible(False)
        self.share_detail_table.setAlternatingRowColors(True)
        self.share_detail_table.setSelectionBehavior(self.share_detail_table.SelectionBehavior.SelectRows)
        _configure_satellite_table(
            self.share_detail_table,
            stretch_columns=(1,),
            resize_columns=(0, 2, 3, 4, 5),
        )
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
        self.kiosk_scan_input.setObjectName("satScanInput")
        self.kiosk_scan_input.setMinimumWidth(0)
        self.kiosk_lookup_button.setObjectName("primaryButton")
        self.kiosk_add_button.setObjectName("primaryButton")
        self.kiosk_add_button.setMinimumHeight(38)
        self.kiosk_open_quote_button.setObjectName("secondaryButton")
        self.kiosk_open_search_button.setObjectName("ghostButton")

        top_scan_row = QHBoxLayout()
        top_scan_row.setSpacing(10)
        top_scan_row.addWidget(self.kiosk_scan_input, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.kiosk_lookup_button)
        action_row.addWidget(self.kiosk_add_button)
        action_row.addStretch()

        scan_label = QLabel("SKU")
        scan_label.setObjectName("satFieldLabel")

        scan_block = QVBoxLayout()
        scan_block.setSpacing(8)
        scan_block.addWidget(scan_label)
        scan_block.addLayout(top_scan_row)
        scan_block.addLayout(action_row)

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

        left_layout.addLayout(scan_block)
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
        _configure_satellite_table(
            self.kiosk_recent_table,
            stretch_columns=(1, 4),
            resize_columns=(0, 2, 3),
        )
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
        configure_friendly_date_edit(
            self.quote_validity_input,
            minimum_date=QDate.currentDate(),
            initial_date=self._default_quote_validity_date(),
        )
        self.quote_note_input.setMaximumHeight(90)
        self.quote_note_input.setPlaceholderText("Observaciones adicionales")

        self.quote_draft_button.setObjectName("ghostButton")
        self.quote_emit_button.setObjectName("primaryButton")
        self.quote_qty_down_button.setObjectName("ghostButton")
        self.quote_qty_up_button.setObjectName("ghostButton")
        self.quote_remove_button.setObjectName("secondaryButton")
        self.quote_clear_button.setObjectName("ghostButton")
        self.quote_create_client_button.setObjectName("ghostButton")
        self.quote_folio_input.setObjectName("satFieldValue")
        self.quick_scan_input.setPlaceholderText("Escanea cliente o SKU")
        self.quick_scan_input.setClearButtonEnabled(True)
        self.quick_scan_input.setMinimumWidth(440)
        self.quick_scan_input.setMaximumWidth(520)
        self.quick_scan_input.setObjectName("satScanInput")
        self.quick_scan_input.setToolTip("Escanea codigo de cliente o SKU de producto. Empleada se integrara despues.")
        self.quick_scan_button.setObjectName("ghostButton")
        self.quick_scan_button.setText("OK")
        self.quote_client_combo.setToolTip(
            "El cliente se asigna al crear uno nuevo o al reanudar un borrador existente."
        )

        def form_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("satFieldLabel")
            return label

        scan_stack = QVBoxLayout()
        scan_stack.setSpacing(4)
        scan_stack.addWidget(form_label("Escaneo"))

        scan_row = QHBoxLayout()
        scan_row.setSpacing(6)
        scan_row.addWidget(self.quick_scan_input, 1)
        scan_row.addWidget(self.quick_scan_button)
        scan_row.addStretch(2)
        scan_stack.addLayout(scan_row)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.addWidget(form_label("Folio"), 0, 0)
        form.addWidget(self.quote_folio_input, 0, 1, 1, 2)
        form.addWidget(form_label("Cliente asignado"), 0, 3)
        form.addWidget(self.quote_client_combo, 0, 4, 1, 2)
        form.addWidget(self.quote_create_client_button, 0, 6)
        form.addWidget(form_label("Vigencia"), 1, 0)
        form.addWidget(self.quote_validity_input, 1, 1, 1, 2)
        form.addWidget(form_label("Observacion"), 2, 0)
        form.addWidget(self.quote_note_input, 2, 1, 1, 6)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.quote_draft_button)
        actions.addWidget(self.quote_emit_button)
        actions.addStretch()
        actions.addWidget(self.quote_qty_down_button)
        actions.addWidget(self.quote_qty_up_button)
        actions.addWidget(self.quote_remove_button)
        actions.addWidget(self.quote_clear_button)

        editor_layout.addLayout(scan_stack)
        editor_layout.addLayout(form)
        editor_layout.addLayout(actions)
        editor_box.setLayout(editor_layout)

        cart_box = QGroupBox("Carrito")
        cart_layout = QVBoxLayout()
        cart_layout.setSpacing(10)
        self.quote_cart_table.setColumnCount(7)
        self.quote_cart_table.setHorizontalHeaderLabels(
            ["Cantidad", "Producto", "Talla", "Nivel", "Escuela", "Precio", "Subtotal"]
        )
        self.quote_cart_table.setObjectName("cashierCartTable")
        self.quote_cart_table.verticalHeader().setVisible(False)
        self.quote_cart_table.verticalHeader().setDefaultSectionSize(46)
        self.quote_cart_table.setAlternatingRowColors(True)
        self.quote_cart_table.setSelectionBehavior(self.quote_cart_table.SelectionBehavior.SelectRows)
        self.quote_cart_table.setMinimumHeight(320)
        _configure_satellite_table(
            self.quote_cart_table,
            stretch_columns=(1,),
            resize_columns=(0, 2, 3, 4, 5, 6),
        )

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
        _configure_satellite_table(
            self.quote_table,
            stretch_columns=(1,),
            resize_columns=(0, 2, 3, 4, 5, 6),
        )

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
        self.quote_detail_table.setColumnCount(6)
        self.quote_detail_table.setHorizontalHeaderLabels(["SKU", "Producto", "Talla", "Cantidad", "Precio", "Subtotal"])
        self.quote_detail_table.verticalHeader().setVisible(False)
        self.quote_detail_table.setAlternatingRowColors(True)
        self.quote_detail_table.setSelectionBehavior(self.quote_detail_table.SelectionBehavior.SelectRows)
        _configure_satellite_table(
            self.quote_detail_table,
            stretch_columns=(1,),
            resize_columns=(0, 2, 3, 4, 5),
        )
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
        self.exit_button.clicked.connect(self.close)
        self.nav_kiosk_button.clicked.connect(lambda: self._set_page("kiosk"))
        self.nav_catalog_button.clicked.connect(lambda: self._set_page("catalog"))
        self.nav_guided_button.clicked.connect(lambda: self._set_page("guided"))
        self.nav_quote_button.clicked.connect(lambda: self._set_page("quote"))
        self.nav_search_button.clicked.connect(lambda: self._set_page("search"))
        self.nav_share_button.clicked.connect(lambda: self._set_page("share"))
        self.quick_scan_button.clicked.connect(self._handle_quick_scan)
        self.quick_scan_input.returnPressed.connect(self._handle_quick_scan)
        self.kiosk_open_quote_button.clicked.connect(lambda: self._set_page("quote"))
        self.kiosk_open_search_button.clicked.connect(lambda: self._set_page("catalog"))
        self.quote_refresh_button.clicked.connect(self.refresh_all)
        self.kiosk_lookup_button.clicked.connect(self._handle_lookup_scan)
        self.kiosk_scan_input.returnPressed.connect(self._handle_lookup_scan)
        self.kiosk_add_button.clicked.connect(self._handle_add_lookup_to_quote)
        self.kiosk_recent_table.itemSelectionChanged.connect(self._handle_recent_scan_selection)
        self.catalog_refresh_button.clicked.connect(self.refresh_all)
        self.catalog_search_input.textChanged.connect(lambda _: self._schedule_catalog_browser_refresh_reset_page())
        self.catalog_search_input.returnPressed.connect(self._handle_catalog_browser_filters_changed_reset_page)
        self.catalog_level_combo.currentIndexChanged.connect(self._handle_catalog_level_changed)
        self.catalog_school_combo.currentIndexChanged.connect(self._handle_catalog_browser_filters_changed_reset_page)
        self.catalog_include_general_combo.currentIndexChanged.connect(self._handle_catalog_browser_filters_changed_reset_page)
        self.catalog_table.itemSelectionChanged.connect(self._handle_catalog_selection)
        self.catalog_add_button.clicked.connect(self._handle_add_catalog_selection_to_quote)
        self.catalog_print_label_button.clicked.connect(self._print_label_for_selected_catalog_row)
        QShortcut(QKeySequence("Ctrl+P"), self.catalog_table).activated.connect(
            self._print_label_for_selected_catalog_row
        )
        _guided_ctrl_p = QShortcut(QKeySequence("Ctrl+P"), self.guided_page_scroll)
        _guided_ctrl_p.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        _guided_ctrl_p.activated.connect(self._print_label_for_guided_selection)
        self.catalog_previous_page_button.clicked.connect(self._handle_catalog_browser_previous_page)
        self.catalog_next_page_button.clicked.connect(self._handle_catalog_browser_next_page)
        self.guided_add_button.clicked.connect(self._handle_add_guided_selection_to_quote)
        self.guided_print_label_button.clicked.connect(self._print_label_for_guided_selection)
        self.guided_reset_button.clicked.connect(self._handle_guided_reset_steps)
        self.guided_basics_button.clicked.connect(self._handle_guided_go_to_basics)
        self.quote_remove_button.clicked.connect(self._handle_remove_quote_item)
        self.quote_qty_down_button.clicked.connect(self._handle_decrease_quote_item_quantity)
        self.quote_qty_up_button.clicked.connect(self._handle_increase_quote_item_quantity)
        self.quote_clear_button.clicked.connect(self._handle_clear_quote_cart)
        self.quote_draft_button.clicked.connect(self._handle_save_quote_draft)
        self.quote_emit_button.clicked.connect(self._handle_emit_quote)
        self.quote_create_client_button.clicked.connect(self._handle_create_quote_client)
        self.quote_search_input.textChanged.connect(self._handle_quote_filters_changed)
        self.quote_state_combo.currentIndexChanged.connect(self._handle_quote_filters_changed)
        self.quote_table.itemSelectionChanged.connect(self._handle_quote_selection)
        self.quote_cart_table.itemSelectionChanged.connect(self._apply_action_state)
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
            "share": "Compartir por WhatsApp o imprimir.",
        }
        self.current_page_key = page_key
        self.page_stack.setCurrentIndex(page_index_map[page_key])
        button_map[page_key].setChecked(True)
        self._set_status(page_title_map[page_key])
        if page_key == "kiosk":
            QTimer.singleShot(0, self.kiosk_scan_input.setFocus)

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
        # Guardar cache local para que el proximo arranque sin conexion pueda usarla.
        try:
            save_catalog_cache(self.catalog_snapshot_rows)
        except Exception:  # noqa: BLE001
            pass  # Un fallo al guardar cache no debe interrumpir el flujo normal.
        self._rebuild_catalog_level_combo()

    def _refresh_catalog_snapshot_from_cache(self) -> None:
        """Sincroniza el combo de niveles desde el cache local (sin DB)."""
        self._rebuild_catalog_level_combo()

    def _rebuild_catalog_level_combo(self) -> None:
        """Reconstruye el combo de niveles a partir de catalog_snapshot_rows."""
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
        self._handle_catalog_browser_filters_changed_reset_page()

    def _schedule_catalog_browser_refresh(self) -> None:
        self.catalog_browser_debounce_timer.start()

    def _schedule_catalog_browser_refresh_reset_page(self) -> None:
        self.catalog_browser_page_index = 0
        self._schedule_catalog_browser_refresh()

    def _run_catalog_browser_refresh(self) -> None:
        try:
            self._refresh_catalog_browser()
        except Exception:  # noqa: BLE001
            self._set_status("No se pudo aplicar la busqueda del catalogo.")

    def _handle_catalog_browser_filters_changed(self) -> None:
        if self.catalog_browser_debounce_timer.isActive():
            self.catalog_browser_debounce_timer.stop()
        self._run_catalog_browser_refresh()

    def _handle_catalog_browser_filters_changed_reset_page(self) -> None:
        self.catalog_browser_page_index = 0
        self._handle_catalog_browser_filters_changed()

    def _handle_catalog_browser_previous_page(self) -> None:
        if self.catalog_browser_page_index <= 0:
            return
        self.catalog_browser_page_index -= 1
        self._handle_catalog_browser_filters_changed()

    def _handle_catalog_browser_next_page(self) -> None:
        self.catalog_browser_page_index += 1
        self._handle_catalog_browser_filters_changed()

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
        pagination_view = build_catalog_pagination_view(
            list(rows),
            current_page_index=self.catalog_browser_page_index,
            page_size=SATELLITE_CATALOG_PAGE_SIZE,
        )
        self.catalog_browser_page_index = pagination_view.current_page_index
        self.catalog_browser_visible_skus = tuple(str(row.sku) for row in pagination_view.page_rows)
        _reload_satellite_table_widget(
            self.catalog_table,
            row_count=len(pagination_view.page_rows),
            populate_rows=lambda: self._populate_catalog_browser_rows(tuple(pagination_view.page_rows)),
        )
        self.catalog_status_label.setText(summary.status_label)
        self._refresh_catalog_active_filter_chips()
        self.catalog_pagination_label.setText(
            (
                f"Mostrando {pagination_view.start_row_number}-{pagination_view.end_row_number} de "
                f"{pagination_view.total_rows} | Pagina {pagination_view.current_page_index + 1} de {pagination_view.total_pages}"
            )
            if pagination_view.total_rows
            else "Mostrando 0 de 0 | Pagina 1 de 1"
        )
        self.catalog_previous_page_button.setEnabled(pagination_view.previous_enabled)
        self.catalog_next_page_button.setEnabled(pagination_view.next_enabled)

        if self.catalog_table.rowCount() > 0 and self.catalog_table.currentRow() < 0:
            self.catalog_table.selectRow(0)
        elif self.catalog_table.rowCount() == 0:
            self._apply_catalog_detail(None)
        self._apply_action_state()

    def _catalog_active_filter_tokens(self):
        route_value = self.catalog_include_general_combo.currentData()
        return build_active_filter_tokens(
            search_text=self.catalog_search_input.text(),
            multi_filters=(),
            combo_filters=(
                ("nivel", self.catalog_level_combo.currentData(), self.catalog_level_combo.currentText()),
                ("escuela", self.catalog_school_combo.currentData(), self.catalog_school_combo.currentText()),
                (
                    "ruta",
                    "" if route_value == "include_general" else route_value,
                    self.catalog_include_general_combo.currentText(),
                ),
            ),
        )

    def _refresh_catalog_active_filter_chips(self) -> None:
        rebuild_active_filter_chips(
            container=self.catalog_active_filters_wrap,
            layout=self.catalog_active_filters_flow_layout,
            tokens=self._catalog_active_filter_tokens(),
            on_remove=self._handle_remove_catalog_filter_token,
        )

    def _handle_remove_catalog_filter_token(self, token) -> None:
        if token.key == "texto":
            self.catalog_search_input.blockSignals(True)
            self.catalog_search_input.clear()
            self.catalog_search_input.blockSignals(False)
            self._handle_catalog_browser_filters_changed_reset_page()
            return
        combo_filters = {
            "nivel": self.catalog_level_combo,
            "escuela": self.catalog_school_combo,
            "ruta": self.catalog_include_general_combo,
        }
        combo = combo_filters.get(token.key)
        if combo is None:
            return
        combo.setCurrentIndex(0)

    def _populate_catalog_browser_rows(self, rows: tuple[QuoteCatalogBrowserRow, ...]) -> None:
        for row_index, row_view in enumerate(rows):
            for column_index, value in enumerate(row_view.values):
                self.catalog_table.setItem(row_index, column_index, _table_item(value))
            item = self.catalog_table.item(row_index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, row_view.sku)

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
        product_name = str(row.get("producto_nombre_base") or row.get("producto_nombre") or "Producto")
        school_name = str(row.get("escuela_nombre") or "General")
        level_name = str(row.get("nivel_educativo_nombre") or "Sin nivel")
        garment_name = str(row.get("tipo_prenda_nombre") or "-")
        piece_name = str(row.get("tipo_pieza_nombre") or "-")
        size_label = str(row.get("talla") or "-")
        color_label = str(row.get("color") or "-")
        price_value = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
        self.catalog_detail_title_label.setText(
            f"{row.get('sku', '')} | {product_name}"
        )
        self.catalog_detail_meta_label.setText(
            f"Nivel {level_name} | Escuela {school_name} | {garment_name} | {piece_name} | "
            f"Talla {size_label} | Color {color_label} | Precio ${price_value}"
        )
        self.catalog_detail_notes_label.setText(str(row.get("producto_descripcion") or "Sin descripcion adicional."))

    def _handle_add_catalog_selection_to_quote(self) -> None:
        sku = self._selected_catalog_sku()
        if not sku:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una variante del catalogo para agregarla.")
            return
        self._add_quote_item_by_sku(sku, 1)

    def _handle_guided_mode_change(self, mode_key: str) -> None:
        self._reset_guided_route(mode_key=mode_key)

    def _reset_guided_route(self, *, mode_key: str) -> None:
        self._gfs.reset(mode_key)
        self.guided_qty_spin.setValue(1)
        self._refresh_guided_browser()

    def _handle_guided_reset_steps(self) -> None:
        self._reset_guided_route(mode_key="school")

    def _handle_guided_go_to_basics(self) -> None:
        self._reset_guided_route(mode_key="basics")

    def _handle_guided_level_selected(self, level_name: str) -> None:
        self._gfs.level = level_name
        self._gfs.school = ""
        self._gfs.profile = "TODOS"
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_school_selected(self, school_name: str) -> None:
        self._gfs.school = school_name
        self._gfs.profile = "TODOS"
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_gender_selected(self, gender_key: str) -> None:
        self._gfs.gender = gender_key
        self._gfs.profile = "TODOS"
        self._gfs.piece = ""
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_profile_selected(self, profile_key: str) -> None:
        self._gfs.profile = profile_key
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_bucket_selected(self, bucket_key: str) -> None:
        self._gfs.bucket = bucket_key
        self._gfs.piece = ""
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_piece_selected(self, piece_key: str) -> None:
        self._gfs.piece = piece_key
        self._gfs.product_key = ""
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_product_selected(self, product_key: str) -> None:
        self._gfs.product_key = product_key
        self._gfs.sku = ""
        self._refresh_guided_browser()

    def _handle_guided_variant_selected(self, sku: str) -> None:
        self._gfs.sku = sku
        row = next((item for item in self.catalog_snapshot_rows if str(item.get("sku")) == sku), None)
        self._apply_guided_detail(row)
        self._refresh_guided_product_checks()
        self._refresh_guided_variant_checks()
        self._apply_action_state()

    def _refresh_guided_browser(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=self.catalog_snapshot_rows,
            mode_key=self._gfs.mode,
            level_filter=self._gfs.level,
            school_filter=self._gfs.school,
            gender_filter=self._gfs.gender,
            profile_filter=self._gfs.profile,
            bucket_filter=self._gfs.bucket,
            piece_filter=self._gfs.piece,
            selected_product_key=self._gfs.product_key,
            selected_sku=self._gfs.sku,
        )
        if self._correct_guided_state(view):
            return
        self._apply_guided_view(view)

    def _correct_guided_state(self, view) -> bool:
        """Corrige selecciones obsoletas contra las opciones disponibles.

        Retorna True si hizo una corrección y ya re-invocó _refresh_guided_browser.
        """
        available_levels = {opt.key for opt in view.level_options}
        if self._gfs.mode == "school" and self._gfs.level and self._gfs.level not in available_levels:
            self._gfs.level = ""
            self._gfs.school = ""
            self._gfs.sku = ""
            self._refresh_guided_browser()
            return True

        available_schools = {opt.key for opt in view.school_options}
        if self._gfs.mode == "school" and self._gfs.school and self._gfs.school not in available_schools:
            self._gfs.school = ""
            self._gfs.profile = "TODOS"
            self._gfs.sku = ""
            self._refresh_guided_browser()
            return True

        available_profiles = {opt.key for opt in view.profile_options}
        if (
            self._gfs.mode == "school"
            and self._gfs.gender == "OFICIAL"
            and self._gfs.profile not in {"", "TODOS"}
            and self._gfs.profile not in available_profiles
        ):
            self._gfs.profile = "TODOS"
            self._gfs.product_key = ""
            self._gfs.sku = ""
            self._refresh_guided_browser()
            return True

        available_buckets = {opt.key for opt in view.bucket_options}
        if self._gfs.mode == "basics" and self._gfs.bucket and self._gfs.bucket not in available_buckets:
            self._gfs.bucket = "BASICO" if "BASICO" in available_buckets else "TODOS"
            self._gfs.piece = ""
            self._gfs.product_key = ""
            self._gfs.sku = ""
            self._refresh_guided_browser()
            return True

        available_pieces = {opt.key for opt in view.piece_options}
        if self._gfs.mode == "basics" and self._gfs.piece and self._gfs.piece not in available_pieces:
            self._gfs.piece = ""
            self._gfs.product_key = ""
            self._gfs.sku = ""
            self._refresh_guided_browser()
            return True

        return False

    def _apply_guided_view(self, view) -> None:
        """Aplica el view calculado a todos los widgets de la página guiada."""
        self._gfs.product_key = view.selected_product_key
        self._gfs.sku = view.selected_sku
        self.guided_status_label.setText(view.status_label)
        self.guided_path_label.setText(view.path_label)
        self.guided_empty_label.setText(view.empty_label or "Toca un producto para ver detalle.")

        self._rebuild_guided_mode_buttons()
        self._rebuild_guided_level_buttons(view.level_options)
        self._rebuild_guided_school_buttons(view.school_options)
        self._rebuild_guided_gender_buttons(view.gender_options)
        self._rebuild_guided_profile_buttons(view.profile_options)
        self._rebuild_guided_bucket_buttons(view.bucket_options)
        self._rebuild_guided_piece_buttons(view.piece_options)
        self._rebuild_guided_product_buttons(view.product_cards)
        self._rebuild_guided_variant_buttons(view.variant_options)

        self._apply_guided_section_visibility(view)
        self._apply_guided_product_section_labels(view)

        if self._gfs.sku:
            row = next(
                (item for item in self.catalog_snapshot_rows if str(item.get("sku")) == self._gfs.sku),
                None,
            )
            self._apply_guided_detail(row)
        else:
            self._apply_guided_detail(None)
        self._refresh_guided_product_checks()
        self._refresh_guided_variant_checks()
        self._apply_action_state()

    def _apply_guided_section_visibility(self, view) -> None:
        """Muestra u oculta cada sección de pasos según el estado actual."""
        mode = self._gfs.mode
        show_level = mode == "school"
        show_school = mode == "school" and bool(self._gfs.level)
        show_gender = mode == "basics" or bool(self._gfs.school)
        show_profile = mode == "school" and self._gfs.gender == "OFICIAL" and bool(view.profile_options)
        show_bucket = mode == "basics" and bool(view.bucket_options)
        show_piece = mode == "basics" and bool(view.piece_options)
        show_products = (mode == "basics" and bool(self._gfs.piece)) or (mode == "school" and bool(self._gfs.school))

        self.guided_level_section.setVisible(show_level)
        self.guided_school_section.setVisible(show_school)
        self.guided_gender_section.setVisible(show_gender)
        self.guided_profile_section.setVisible(show_profile)
        self.guided_bucket_section.setVisible(show_bucket)
        self.guided_piece_section.setVisible(show_piece)
        self.guided_products_section.setVisible(show_products)

        if mode == "school":
            self.guided_gender_title_label.setText("4. Elige linea")
            self.guided_gender_hint_label.setText("Primero separa deportivo de oficial.")
        else:
            self.guided_gender_title_label.setText("4. Elige tipo de uniforme")
            self.guided_gender_hint_label.setText("Elige la linea mas cercana a lo que buscan.")

    def _apply_guided_product_section_labels(self, view) -> None:
        """Actualiza el título y hint de la sección de modelos según el paso activo."""
        mode = self._gfs.mode
        show_profile = mode == "school" and self._gfs.gender == "OFICIAL" and bool(view.profile_options)
        show_bucket = mode == "basics" and bool(view.bucket_options)
        show_piece = mode == "basics" and bool(view.piece_options)
        if show_piece:
            self.guided_products_title_label.setText("7. Modelos sugeridos")
            self.guided_products_hint_label.setText("Primero elige el tipo de pieza; luego toca un modelo.")
        elif show_bucket:
            self.guided_products_title_label.setText("6. Modelos sugeridos")
            self.guided_products_hint_label.setText("Elige Basicos, Extras o Todos; luego toca un modelo.")
        elif show_profile:
            self.guided_products_title_label.setText("6. Modelos sugeridos")
            self.guided_products_hint_label.setText("Primero elige el perfil oficial; luego toca un modelo.")
        else:
            self.guided_products_title_label.setText("5. Modelos sugeridos")
            self.guided_products_hint_label.setText("Primero toca un modelo; luego elige la variante que quieren.")

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
            button.setChecked(self._gfs.mode == key)

    def _rebuild_guided_level_buttons(self, options) -> None:
        self.guided_level_buttons = self._rebuild_guided_option_grid(
            layout=self.guided_level_grid,
            options=options,
            selected_key=self._gfs.level,
            click_handler=self._handle_guided_level_selected,
            icon_builder=lambda option: _level_icon(option.label),
        )

    def _rebuild_guided_school_buttons(self, options) -> None:
        self.guided_school_buttons = self._rebuild_guided_option_grid(
            layout=self.guided_school_grid,
            options=options,
            selected_key=self._gfs.school,
            click_handler=self._handle_guided_school_selected,
        )

    def _rebuild_guided_hrow(self, layout: QHBoxLayout, options, selected_key: str, click_handler) -> dict:
        _clear_layout(layout)
        buttons: dict[str, QPushButton] = {}
        for option in options:
            button = self._build_guided_choice_button(option.label)
            button.setEnabled(option.enabled)
            button.setChecked(selected_key == option.key)
            button.clicked.connect(lambda checked=False, selected=option.key: click_handler(selected))
            layout.addWidget(button)
            buttons[option.key] = button
        layout.addStretch()
        return buttons

    def _rebuild_guided_gender_buttons(self, options) -> None:
        self.guided_gender_buttons = self._rebuild_guided_hrow(
            self.guided_gender_row, options, self._gfs.gender, self._handle_guided_gender_selected)

    def _rebuild_guided_profile_buttons(self, options) -> None:
        self.guided_profile_buttons = self._rebuild_guided_hrow(
            self.guided_profile_row, options, self._gfs.profile, self._handle_guided_profile_selected)

    def _rebuild_guided_bucket_buttons(self, options) -> None:
        self.guided_bucket_buttons = self._rebuild_guided_hrow(
            self.guided_bucket_row, options, self._gfs.bucket, self._handle_guided_bucket_selected)

    def _rebuild_guided_piece_buttons(self, options) -> None:
        _clear_layout(self.guided_piece_groups_layout)
        self.guided_piece_buttons = {}
        buttons_per_row = 3
        grouped_options: dict[str, list[object]] = {}
        for option in options:
            group_label = getattr(option, "group_label", "") or "Piezas"
            grouped_options.setdefault(group_label, []).append(option)

        for group_label, group_options in grouped_options.items():
            label = QLabel(group_label)
            label.setObjectName("guidedGroupLabel")
            self.guided_piece_groups_layout.addWidget(label)

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(6)

            for index, option in enumerate(group_options):
                button = self._build_guided_choice_button(option.label)
                button.setProperty("compactChoice", True)
                button.setEnabled(option.enabled)
                button.setChecked(self._gfs.piece == option.key)
                button.setMinimumHeight(42)
                button.setMinimumWidth(170)
                button.setMaximumWidth(170)
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                button.style().unpolish(button)
                button.style().polish(button)
                button.clicked.connect(lambda checked=False, selected=option.key: self._handle_guided_piece_selected(selected))
                grid.addWidget(
                    button,
                    index // buttons_per_row,
                    index % buttons_per_row,
                    alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                )
                self.guided_piece_buttons[option.key] = button

            row_layout.addLayout(grid)
            row_layout.addStretch()
            self.guided_piece_groups_layout.addLayout(row_layout)

    def _rebuild_guided_product_buttons(self, product_cards) -> None:
        _clear_layout(self.guided_product_flow_layout)
        self.guided_product_buttons = {}
        for card in product_cards:
            button = self._build_guided_product_button(card)
            button.setChecked(self._gfs.product_key == card.key)
            button.clicked.connect(lambda checked=False, selected=card.key: self._handle_guided_product_selected(selected))
            self.guided_product_flow_layout.addWidget(button)
            self.guided_product_buttons[card.key] = button

    def _rebuild_guided_variant_buttons(self, variant_options) -> None:
        _clear_layout(self.guided_variant_groups_layout)
        self.guided_variant_buttons = {}
        if not variant_options:
            self.guided_detail_scroll.setVisible(False)
            return
        self.guided_detail_scroll.setVisible(True)
        current_price = None
        current_flow = None
        for option in variant_options:
            price_label = getattr(option, "price_label", "") or str(option.label).split("·")[-1].strip()
            if price_label != current_price or current_flow is None:
                current_price = price_label
                current_flow = FlowLayout(margin=0, h_spacing=6, v_spacing=8)
                self.guided_variant_groups_layout.addLayout(current_flow)
            button = self._build_guided_choice_button(option.label)
            button.setProperty("compactChoice", True)
            button.setMinimumHeight(42)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setChecked(self._gfs.sku == option.sku)
            button.clicked.connect(lambda checked=False, selected=option.sku: self._handle_guided_variant_selected(selected))

            def _make_dblclick(sku, btn):
                def _dblclick(event):
                    self._handle_guided_variant_selected(sku)
                    self._handle_add_guided_selection_to_quote()
                    QPushButton.mouseDoubleClickEvent(btn, event)
                return _dblclick

            button.mouseDoubleClickEvent = _make_dblclick(option.sku, button)
            current_flow.addWidget(button)
            self.guided_variant_buttons[option.sku] = button

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
        button_lines = [card.title]
        if card.subtitle:
            button_lines.append(card.subtitle)
        button = QPushButton("\n".join(button_lines))
        button.setObjectName("guidedProductButton")
        button.setCheckable(True)
        compact_card = (self._gfs.mode == "basics" and bool(self._gfs.piece)) or (
            self._gfs.mode == "school" and bool(self._gfs.school)
        )
        button.setProperty("compactCard", compact_card)
        if compact_card:
            button.setMinimumHeight(68)
            button.setFixedWidth(252)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            button.setMinimumHeight(94)
            button.setMinimumWidth(250)
        row = next((item for item in self.catalog_snapshot_rows if str(item.get("sku")) == card.sku), None)
        if row is not None:
            button.setIcon(QIcon(_catalog_row_icon(row)))
            button.setIconSize(QSize(24, 24) if compact_card else QSize(34, 34))
        button.style().unpolish(button)
        button.style().polish(button)
        return button

    def _refresh_guided_product_checks(self) -> None:
        for key, button in self.guided_product_buttons.items():
            button.setChecked(key == self._gfs.product_key)

    def _refresh_guided_variant_checks(self) -> None:
        for sku, button in self.guided_variant_buttons.items():
            button.setChecked(sku == self._gfs.sku)

    def _apply_guided_detail(self, row: dict[str, object] | None) -> None:
        if row is None:
            self.guided_visual_icon_label.setPixmap(_scaled_asset_pixmap("qr_icons/default.png", 48))
            self.guided_visual_icon_label.setFixedSize(48, 48)
            self.guided_detail_title_label.setText("Sin seleccion — toca un modelo para verlo aqui.")
            self.guided_detail_meta_label.setVisible(False)
            self.guided_detail_notes_label.setVisible(False)
            self.guided_detail_scroll.setVisible(False)
            return
        self.guided_visual_icon_label.setFixedSize(72, 72)
        self.guided_visual_icon_label.setPixmap(_catalog_row_icon(row))
        self.guided_detail_meta_label.setVisible(True)
        self.guided_detail_notes_label.setVisible(False)
        self.guided_detail_scroll.setVisible(True)
        segmento = _guided_segment_label(row)
        color_label = _guided_display_color_label(row.get("color"))
        detail_parts = [
            f"Nivel {row['nivel_educativo_nombre']}",
            f"Escuela {row['escuela_nombre']}",
            f"Linea {segmento}",
            f"{row['tipo_prenda_nombre']}",
            f"{row['tipo_pieza_nombre']}",
            f"Talla {row['talla']}",
        ]
        if color_label:
            detail_parts.append(f"Color {color_label}")
        detail_parts.append(f"Precio ${Decimal(str(row['precio_venta'])).quantize(Decimal('0.01'))}")
        title = str(row["producto_nombre_base"])
        if self._gfs.mode != "basics":
            title = f"{row['sku']} | {title}"
        self.guided_detail_title_label.setText(title)
        self.guided_detail_meta_label.setText(" | ".join(detail_parts))
        self.guided_detail_notes_label.setText(str(row.get("producto_descripcion") or "Sin descripcion adicional."))
        self.guided_detail_scroll.setVisible(bool(self.guided_variant_buttons))

    def _handle_add_guided_selection_to_quote(self) -> None:
        if not self._gfs.sku:
            QMessageBox.warning(self, "Sin seleccion", "Elige un producto guiado antes de agregarlo.")
            return
        self._add_quote_item_by_sku(self._gfs.sku, self.guided_qty_spin.value())
        self.guided_qty_spin.setValue(1)

    def _refresh_client_combo(self, session) -> None:
        selected_client_id = self._selected_client_id()
        self.quote_client_combo.blockSignals(True)
        self.quote_client_combo.clear()
        self.quote_client_combo.addItem("Sin cliente asignado", None)
        if selected_client_id is not None:
            client = session.get(Cliente, selected_client_id)
            if client is not None:
                self.quote_client_combo.addItem(
                    f"{client.codigo_cliente} · {client.nombre}",
                    {
                        "id": int(client.id),
                        "nombre": str(client.nombre),
                        "telefono": str(client.telefono or ""),
                    },
                )
                self.quote_client_combo.setCurrentIndex(self.quote_client_combo.count() - 1)
        self.quote_client_combo.blockSignals(False)

    def _handle_quick_scan(self) -> None:
        scan_code = self.quick_scan_input.text().strip().upper()
        if not scan_code:
            QMessageBox.warning(self, "Codigo faltante", "Escanea o captura un codigo de cliente o SKU.")
            return
        try:
            with get_session() as session:
                client = find_active_sale_client_by_code(session, scan_code)
                if client is not None:
                    self._apply_scanned_client_to_quote(client, scan_code)
                else:
                    self._add_quote_item_by_sku(scan_code, 1)
            self.quick_scan_input.clear()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Escaneo no disponible", str(exc))
        self.quick_scan_input.setFocus()

    def _apply_scanned_client_to_quote(self, client: Cliente, scanned_code: str) -> None:
        ui_state = build_quote_scanned_client_ui_state(
            current_client_id=self._selected_client_id(),
            current_client_label=self.quote_client_combo.currentText().strip() or "Cliente actual",
            scanned_client_id=client.id,
            scanned_client_code=client.codigo_cliente,
            scanned_client_name=client.nombre,
            has_quote_cart=bool(self.quote_cart),
        )
        if ui_state.action == "already_linked":
            if ui_state.immediate_message:
                self._set_status(ui_state.immediate_message)
            return

        if ui_state.action == "confirm_replace":
            confirmation = QMessageBox.question(
                self,
                "Cambiar cliente del presupuesto",
                ui_state.confirmation_message or "Deseas reemplazar el cliente asignado?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                if ui_state.rejected_message:
                    self._set_status(ui_state.rejected_message)
                return

        self._select_client_id(int(client.id))
        if ui_state.applied_message:
            self._set_status(ui_state.applied_message)

    def _handle_lookup_scan(self) -> None:
        sku = self.kiosk_scan_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "SKU faltante", "Escanea o captura un SKU para consultarlo.")
            return
        try:
            if self.offline_mode:
                snapshot = self._kiosk_lookup_from_cache(sku)
            else:
                with get_session() as session:
                    snapshot = load_quote_kiosk_lookup_snapshot(session, sku=sku)
            self.lookup_snapshot = snapshot
            self.lookup_history = push_quote_kiosk_recent_scan(self.lookup_history, snapshot)
            self._apply_lookup_view(build_quote_kiosk_lookup_view(snapshot))
            self._refresh_recent_lookup_table()
            self.kiosk_scan_input.clear()
            self._set_status(f"{snapshot.sku} — precio del catalogo guardado.")
        except Exception as exc:  # noqa: BLE001
            self.lookup_snapshot = None
            self._apply_lookup_view(build_error_quote_kiosk_lookup_view(str(exc)))
            QMessageBox.warning(self, "Consulta no disponible", str(exc))
        self._apply_action_state()
        self.kiosk_scan_input.setFocus()

    def _kiosk_lookup_from_cache(self, sku: str) -> "QuoteKioskLookupSnapshot":
        """Construye el snapshot del kiosko buscando en catalog_snapshot_rows (sin DB)."""
        from decimal import Decimal as _Decimal

        normalized = sku.strip().upper()
        row = next(
            (
                r for r in self.catalog_snapshot_rows
                if str(r.get("sku", "")).strip().upper() == normalized
            ),
            None,
        )
        if row is None:
            raise ValueError(f"No existe una presentacion activa para el SKU '{normalized}' en el catalogo guardado.")
        if not row.get("producto_activo") or not row.get("variante_activo"):
            raise ValueError(f"El SKU '{normalized}' esta inactivo en el catalogo guardado.")

        school = str(row.get("escuela_nombre") or "General")
        if school == "General":
            school = "General"
        return QuoteKioskLookupSnapshot(
            sku=normalized,
            product_name=str(row.get("producto_nombre_base") or row.get("producto_nombre") or ""),
            school_name=school,
            garment_type_name=str(row.get("tipo_prenda_nombre") or "Sin tipo de prenda"),
            piece_type_name=str(row.get("tipo_pieza_nombre") or "Sin tipo de pieza"),
            size_label=str(row.get("talla") or ""),
            color_label=str(row.get("color") or ""),
            price=_Decimal(str(row.get("precio_venta") or "0")).quantize(_Decimal("0.01")),
            stock_actual=int(row.get("stock_actual") or 0),
            location_label="",
            description_text=str(row.get("producto_descripcion") or ""),
            origin_label="Legacy" if row.get("origen_legacy") else "Catalogo actual",
        )

    def _handle_add_lookup_to_quote(self) -> None:
        if self.lookup_snapshot is None:
            QMessageBox.warning(self, "Sin consulta", "Consulta primero un SKU para agregarlo al presupuesto.")
            self.kiosk_scan_input.setFocus()
            return
        self._add_quote_item_by_sku(self.lookup_snapshot.sku, 1)

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
                result = add_quote_scan_variants(
                    self,
                    session,
                    quote_cart=self.quote_cart,
                    scanned_variant=variant,
                    quantity=quantity,
                    variant_loader=PresupuestoService.obtener_variante_por_sku,
                )
                if result is None:
                    self.kiosk_scan_input.setFocus()
                    return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo agregar", str(exc))
            return

        self._refresh_quote_cart_table()
        self.kiosk_scan_input.setFocus()
        self._set_status(result.feedback_message)

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
        self._remove_quote_item_at_index(selected_row)

    def _change_sidebar_item_quantity(self, row_index: int, delta: int) -> None:
        if row_index < 0 or row_index >= len(self.quote_cart):
            return
        item = self.quote_cart[row_index]
        new_qty = max(1, int(item.get("cantidad") or 1) + delta)
        try:
            with get_session() as session:
                update_sale_cart_item_quantity(
                    session,
                    sale_cart=self.quote_cart,
                    row_index=row_index,
                    new_quantity=new_qty,
                    variant_loader=PresupuestoService.obtener_variante_por_sku,
                    stock_validator=lambda _v, _c: None,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Cantidad no actualizada", str(exc))
            return
        self._refresh_quote_cart_table()

    def _remove_quote_item_at_index(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self.quote_cart):
            return
        removed_line_item = dict(self.quote_cart[row_index])
        self.quote_cart.pop(row_index)
        restore_message = restore_sports_uniform_playera_price_if_needed(
            self.quote_cart,
            removed_line_item=removed_line_item,
        )
        self._refresh_quote_cart_table()
        if self.quote_cart:
            self.quote_cart_table.selectRow(min(row_index, len(self.quote_cart) - 1))
        if restore_message:
            self._set_status(restore_message)

    def _change_selected_quote_item_quantity(self, delta: int) -> None:
        selected_row = self.quote_cart_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.quote_cart):
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una linea del presupuesto.")
            return

        selected_item = self.quote_cart[selected_row]
        current_quantity = int(selected_item.get("cantidad") or 1)
        new_quantity = current_quantity + int(delta)
        if new_quantity <= 0:
            QMessageBox.information(
                self,
                "Cantidad minima",
                "Usa 'Quitar linea' si quieres sacar por completo el articulo del presupuesto.",
            )
            return
        try:
            with get_session() as session:
                update_sale_cart_item_quantity(
                    session,
                    sale_cart=self.quote_cart,
                    row_index=selected_row,
                    new_quantity=new_quantity,
                    variant_loader=PresupuestoService.obtener_variante_por_sku,
                    stock_validator=lambda _variante, _cantidad: None,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Cantidad no actualizada", str(exc))
            return
        self._refresh_quote_cart_table()
        self.quote_cart_table.selectRow(selected_row)

    def _handle_decrease_quote_item_quantity(self) -> None:
        self._change_selected_quote_item_quantity(-1)

    def _handle_increase_quote_item_quantity(self) -> None:
        self._change_selected_quote_item_quantity(1)

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
            self._reveal_saved_quote(
                quote_id=result.quote_id,
                state_filter=_state_value(target_state),
            )
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
            items=tuple(build_quote_presupuesto_inputs(self.quote_cart)),
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
                client_message = build_quote_client_created_feedback(
                    session,
                    client_name=str(client.nombre),
                    client_code=str(client.codigo_cliente),
                )
                session.commit()
            self.refresh_all()
            self._select_client_id(client_id)
            QMessageBox.information(self, "Cliente creado", client_message)
            self._set_status(f"Cliente {payload['nombre']} creado y asignado.")
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

    def _refresh_quotes(self, session, preferred_quote_id: int | None = None) -> None:
        selected_quote_id = preferred_quote_id if preferred_quote_id is not None else self._selected_quote_id()
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

    def _reveal_saved_quote(self, *, quote_id: int, state_filter: str) -> None:
        self._set_quote_state_filter(state_filter)
        with get_session() as session:
            self._refresh_quotes(session, preferred_quote_id=quote_id)
        self._set_page("search")

    def _set_quote_state_filter(self, state_filter: str) -> None:
        normalized_filter = str(state_filter or "").strip().upper()
        self.quote_state_combo.blockSignals(True)
        try:
            target_index = 0
            for index in range(self.quote_state_combo.count()):
                item_value = str(self.quote_state_combo.itemData(index) or "").strip().upper()
                if item_value == normalized_filter:
                    target_index = index
                    break
            self.quote_state_combo.setCurrentIndex(target_index)
        finally:
            self.quote_state_combo.blockSignals(False)

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
                        "size_label": detail.size_label,
                        "quantity": detail.quantity,
                        "unit_price": detail.unit_price,
                        "subtotal": detail.subtotal,
                    }
                    for detail in quote_snapshot.detail_rows
                ],
            )
            self._apply_quote_detail_view(detail_view)
            self._apply_share_detail_view(detail_view)
            self.share_status_label.setText(
                f"Presupuesto {quote_snapshot.folio} listo para compartir por WhatsApp o imprimir."
            )
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
                detail.size_label,
                detail.quantity,
                detail.unit_price,
                detail.subtotal,
            ]
            for column_index, value in enumerate(values):
                self.quote_detail_table.setItem(row_index, column_index, _table_item(value))
    def _apply_share_detail_view(self, detail_view) -> None:
        self.share_customer_label.setText(detail_view.customer_label)
        self.share_meta_label.setText(detail_view.meta_label)
        self.share_notes_label.setText(detail_view.notes_label)
        self.share_detail_table.setRowCount(len(detail_view.detail_rows))
        for row_index, detail in enumerate(detail_view.detail_rows):
            values = [
                detail.sku,
                detail.description,
                detail.size_label,
                detail.quantity,
                detail.unit_price,
                detail.subtotal,
            ]
            for column_index, value in enumerate(values):
                self.share_detail_table.setItem(row_index, column_index, _table_item(value))
    def _apply_action_state(self) -> None:
        selected_quote_line = 0 <= self.quote_cart_table.currentRow() < len(self.quote_cart)
        action_state = build_quote_satellite_action_state(
            can_operate=self._can_operate(),
            has_selection=self._selected_quote_id() is not None,
            selected_state=self.selected_quote_state,
            has_phone=bool(_normalize_whatsapp_phone(self.selected_quote_phone)),
        )
        self.quote_resume_button.setEnabled(action_state.resume_enabled)
        self.quote_emit_selected_button.setEnabled(action_state.emit_enabled)
        self.quote_cancel_button.setEnabled(action_state.cancel_enabled)
        self.quote_open_share_button.setEnabled(action_state.share_enabled)
        self.quote_whatsapp_button.setEnabled(action_state.whatsapp_enabled)
        self.quote_print_button.setEnabled(action_state.print_enabled)
        self.share_refresh_button.setEnabled(self._selected_quote_id() is not None)
        self.kiosk_add_button.setEnabled(self.lookup_snapshot is not None and self._can_operate())
        self.catalog_add_button.setEnabled(bool(self._selected_catalog_sku()) and self._can_operate())
        self.catalog_print_label_button.setEnabled(bool(self._selected_catalog_sku()))
        self.guided_add_button.setEnabled(bool(self._gfs.sku) and self._can_operate())
        self.guided_print_label_button.setEnabled(bool(self._gfs.sku))
        self.quote_qty_down_button.setEnabled(selected_quote_line)
        self.quote_qty_up_button.setEnabled(selected_quote_line)
        self.quote_remove_button.setEnabled(selected_quote_line)
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
            self.quote_validity_input.setDate(self._default_quote_validity_date())
        self.quote_cart = [
            {
                "sku": line.sku,
                "producto_nombre": line.description,
                "talla": line.size_label,
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
        overall_cart_view = build_quote_cart_view(self.quote_cart)
        cart_view = overall_cart_view
        self.quote_cart_table.setRowCount(len(cart_view.rows))
        for row_index, row in enumerate(cart_view.rows):
            for column_index, value in enumerate(row.values):
                self.quote_cart_table.setItem(row_index, column_index, _table_item(value))
        self.quote_total_label.setText(cart_view.summary.total_label)
        self.quote_summary_label.setText(cart_view.summary.summary_label)
        self.quote_school_summary_label.setText(overall_cart_view.summary.school_summary_label)
        self.sidebar_total_label.setText(overall_cart_view.summary.total_label)
        self.sidebar_summary_label.setText(
            f"{overall_cart_view.summary.summary_label}\n{overall_cart_view.summary.school_summary_label}"
        )
        self._refresh_sidebar_quote_items()
        self.kiosk_budget_total_label.setText(overall_cart_view.summary.total_label)
        self.kiosk_budget_summary_label.setText(
            f"{overall_cart_view.summary.summary_label}\n{overall_cart_view.summary.school_summary_label}"
        )
        self._apply_action_state()

    def _refresh_sidebar_quote_items(self) -> None:
        _clear_layout(self.sidebar_items_layout)
        line_count = len(self.quote_cart)
        piece_count = sum(max(int(item.get("cantidad") or 0), 0) for item in self.quote_cart)
        line_label = "linea" if line_count == 1 else "lineas"
        piece_label = "pza" if piece_count == 1 else "pzas"
        self.sidebar_items_count_label.setText(f"{line_count} {line_label} | {piece_count} {piece_label}")
        if not self.quote_cart:
            empty_label = QLabel("Aun no agregas piezas.\nAqui veras el armado listo para revisar.")
            empty_label.setObjectName("satSidebarItemEmpty")
            empty_label.setWordWrap(True)
            self.sidebar_items_layout.addWidget(empty_label)
            self.sidebar_items_layout.addStretch()
            return
        for row_index, line_item in enumerate(self.quote_cart):
            self.sidebar_items_layout.addWidget(self._build_sidebar_quote_item_card(row_index, line_item))
        self.sidebar_items_layout.addStretch()

    def _build_sidebar_quote_item_card(self, row_index: int, line_item: dict[str, object]) -> QFrame:
        card = QFrame()
        card.setObjectName("satSidebarItemCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        quantity = max(int(line_item.get("cantidad") or 0), 0)
        unit_price = Decimal(str(line_item.get("precio_unitario") or "0")).quantize(Decimal("0.01"))
        subtotal = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))

        product_name = str(
            line_item.get("producto_nombre")
            or line_item.get("descripcion")
            or line_item.get("sku")
            or "Producto"
        )
        talla = str(line_item.get("talla") or "").strip()
        sku = str(line_item.get("sku") or "").strip()

        # Fila superior: nombre + quitar
        name_label = QLabel(product_name)
        name_label.setObjectName("satSidebarItemName")
        name_label.setWordWrap(True)
        remove_button = QPushButton("✕")
        remove_button.setObjectName("sidebarItemRemoveButton")
        remove_button.setFixedSize(26, 26)
        remove_button.clicked.connect(lambda checked=False, index=row_index: self._remove_quote_item_at_index(index))
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(4)
        name_row.addWidget(name_label, 1)
        name_row.addWidget(remove_button, 0, Qt.AlignmentFlag.AlignTop)

        # Fila meta: talla + sku
        meta_parts = []
        if talla and talla != "-":
            meta_parts.append(f"Talla {talla}")
        if sku:
            meta_parts.append(sku)
        if meta_parts:
            meta_label = QLabel(" · ".join(meta_parts))
            meta_label.setObjectName("satSidebarItemMeta")

        # Fila inferior: precio + ±cantidad
        price_label = QLabel(f"${subtotal}" + (f"  (${unit_price} c/u)" if quantity > 1 else ""))
        price_label.setObjectName("satSidebarItemQty")

        minus_btn = QPushButton("−")
        minus_btn.setObjectName("sidebarItemRemoveButton")
        minus_btn.setFixedSize(26, 26)
        minus_btn.clicked.connect(lambda checked=False, index=row_index: self._change_sidebar_item_quantity(index, -1))

        qty_label = QLabel(str(quantity))
        qty_label.setObjectName("satSidebarItemQty")
        qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qty_label.setFixedWidth(22)

        plus_btn = QPushButton("+")
        plus_btn.setObjectName("sidebarItemRemoveButton")
        plus_btn.setFixedSize(26, 26)
        plus_btn.clicked.connect(lambda checked=False, index=row_index: self._change_sidebar_item_quantity(index, 1))

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(4)
        footer_row.addWidget(price_label, 1)
        footer_row.addWidget(minus_btn)
        footer_row.addWidget(qty_label)
        footer_row.addWidget(plus_btn)

        layout.addLayout(name_row)
        if meta_parts:
            layout.addWidget(meta_label)
        layout.addLayout(footer_row)
        card.setLayout(layout)

        def _dblclick(event, _card=card):
            self._show_cart_popup()
            QFrame.mouseDoubleClickEvent(_card, event)

        card.mouseDoubleClickEvent = _dblclick
        return card

    def _show_cart_popup(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Piezas agregadas")
        dlg.setMinimumWidth(640)
        dlg.setMinimumHeight(420)
        dlg_layout = QVBoxLayout()
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(10)

        columns = ["Producto", "Talla", "SKU", "Cant.", "Precio unit.", "Subtotal", ""]
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setShowGrid(False)

        total_label = QLabel()
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        def _refresh_table():
            table.setRowCount(0)
            total = Decimal("0")
            for row_idx, item in enumerate(self.quote_cart):
                qty = max(int(item.get("cantidad") or 0), 0)
                unit_price = Decimal(str(item.get("precio_unitario") or "0")).quantize(Decimal("0.01"))
                subtotal = (unit_price * Decimal(qty)).quantize(Decimal("0.01"))
                total += subtotal
                product_name = str(
                    item.get("producto_nombre") or item.get("descripcion") or item.get("sku") or "Producto"
                )
                talla = str(item.get("talla") or "—").strip()
                sku = str(item.get("sku") or "—").strip()
                table.insertRow(row_idx)
                for col_idx, value in enumerate([
                    product_name, talla, sku, str(qty), f"${unit_price}", f"${subtotal}",
                ]):
                    cell = QTableWidgetItem(value)
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (
                        Qt.AlignmentFlag.AlignRight if col_idx >= 3 else Qt.AlignmentFlag.AlignLeft
                    ))
                    table.setItem(row_idx, col_idx, cell)
                remove_btn = QPushButton("✕")
                remove_btn.setObjectName("sidebarItemRemoveButton")
                remove_btn.setFixedSize(26, 26)
                remove_btn.clicked.connect(lambda checked=False, index=row_idx: (
                    self._remove_quote_item_at_index(index),
                    _refresh_table(),
                ))
                table.setCellWidget(row_idx, 6, remove_btn)
            table.resizeColumnToContents(1)
            table.resizeColumnToContents(2)
            table.resizeColumnToContents(3)
            table.resizeColumnToContents(4)
            table.resizeColumnToContents(5)
            table.setColumnWidth(6, 36)
            total_label.setText(f"Total: <b>${total.quantize(Decimal('0.01'))}</b>")

        _refresh_table()

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(dlg.accept)

        dlg_layout.addWidget(table, 1)
        dlg_layout.addWidget(total_label)
        dlg_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
        dlg.setLayout(dlg_layout)
        dlg.exec()

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
    def _reset_quote_form(self) -> None:
        self.quote_editing_id = None
        self.quote_client_combo.setCurrentIndex(0)
        self.quote_validity_input.setDate(self._default_quote_validity_date())
        self.quote_note_input.clear()
        self.quote_folio_input.setText(self._generate_quote_folio())

    def _default_quote_validity_date(self) -> QDate:
        return QDate.currentDate().addDays(SATELLITE_QUOTE_VALIDITY_DAYS)

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
        try:
            with get_session() as session:
                client = session.get(Cliente, int(client_id))
        except Exception:  # noqa: BLE001
            client = None
        if client is not None:
            self.quote_client_combo.addItem(
                f"{client.codigo_cliente} · {client.nombre}",
                {
                    "id": int(client.id),
                    "nombre": str(client.nombre),
                    "telefono": str(client.telefono or ""),
                },
            )
            self.quote_client_combo.setCurrentIndex(self.quote_client_combo.count() - 1)
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
        current_row_count = self.catalog_table.rowCount()
        if current_row_count == len(self.catalog_snapshot_rows) and selected_row < len(self.catalog_snapshot_rows):
            return str(self.catalog_snapshot_rows[selected_row].get("sku") or "").strip()
        if current_row_count == len(self.catalog_browser_visible_skus) and selected_row < len(self.catalog_browser_visible_skus):
            return self.catalog_browser_visible_skus[selected_row].strip()
        item = self.catalog_table.item(selected_row, 0)
        if item is None:
            if selected_row < len(self.catalog_snapshot_rows):
                return str(self.catalog_snapshot_rows[selected_row].get("sku") or "").strip()
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()

    def _selected_quote_folio(self) -> str:
        selected_row = self.quote_table.currentRow()
        if selected_row < 0:
            return ""
        item = self.quote_table.item(selected_row, 0)
        return item.text().strip() if item is not None else ""

    def _can_operate(self) -> bool:
        if self.offline_mode:
            return False
        return self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    # Impresion de etiquetas desde catalogo
    # ------------------------------------------------------------------

    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, object]:
        from PyQt6.QtWidgets import QApplication
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        if expand_to_screen:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                dialog.resize(
                    max(width, int(available.width() * 0.94)),
                    int(available.height() * 0.9),
                )
                dialog.setMinimumSize(
                    min(max(width, int(available.width() * 0.82)), available.width()),
                    min(int(available.height() * 0.72), available.height()),
                )
            else:
                dialog.setMinimumWidth(width)
        else:
            dialog.setMinimumWidth(width)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        if helper_text:
            helper = QLabel(helper_text)
            helper.setWordWrap(True)
            helper.setObjectName("subtleLine")
            layout.addWidget(helper)
        dialog.setLayout(layout)
        return dialog, layout

    def _show_pin_dialog(self) -> bool:
        """Pide un PIN antes de abrir el diálogo de etiquetas. Retorna True si es válido."""
        dialog = QDialog(self)
        dialog.setWindowTitle("PIN requerido")
        dialog.setModal(True)
        dialog.setMinimumWidth(320)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        hint = QLabel("Ingresa el PIN para imprimir etiquetas.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        pin_input = QLineEdit()
        pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        pin_input.setPlaceholderText("PIN")
        pin_input.setMaxLength(10)
        layout.addWidget(pin_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        pin_input.returnPressed.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        entered = pin_input.text().strip()
        if entered not in _LABEL_PRINT_PINS:
            QMessageBox.warning(self, "PIN incorrecto", "El PIN ingresado no es válido.")
            return False
        return True

    def _print_satellite_label(
        self,
        image_path: "Path",
        *,
        title: str,
        copies: int,
        parent: "QDialog | None" = None,
    ) -> bool:
        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError(f"No se pudo abrir la imagen de etiqueta:\n{image_path}")
        if sys.platform.startswith("win"):
            from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
                print_inventory_label_via_windows,
            )
            try:
                with get_session() as session:
                    from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
                    preferred_printer = load_business_print_settings_snapshot(session).preferred_printer
            except Exception:
                preferred_printer = ""
            resolution = print_inventory_label_via_windows(
                image_path,
                sku=title.replace("Etiqueta ", "", 1),
                copies=copies,
                preferred_printer_name=preferred_printer,
            )
            if resolution.fallback_used:
                QMessageBox.information(
                    parent or self,
                    "Impresora ajustada",
                    (
                        f'Se envió la etiqueta a "{resolution.printer_name}" '
                        "porque la impresora preferida no estaba disponible en esta PC."
                    ),
                )
            return True
        # Fallback para macOS / Linux (entorno de desarrollo)
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
        from PyQt6.QtCore import QMarginsF, QSizeF
        from PyQt6.QtGui import QPageLayout, QPageSize
        from pos_uniformes.ui.helpers.inventory_label_print_helper import build_inventory_label_print_layout
        from pos_uniformes.ui.helpers.qt_image_scale_helper import normalize_printable_image
        image = normalize_printable_image(image)
        print_layout = build_inventory_label_print_layout(image.width(), image.height())
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setFullPage(True)
        printer.setResolution(300)
        printer.setPageOrientation(
            QPageLayout.Orientation.Landscape
            if print_layout.orientation == "landscape"
            else QPageLayout.Orientation.Portrait
        )
        printer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        printer.setPageSize(
            QPageSize(
                QSizeF(print_layout.width_mm, print_layout.height_mm),
                QPageSize.Unit.Millimeter,
                "inventory-label",
            )
        )
        print_dialog = QPrintDialog(printer, parent or self)
        print_dialog.setWindowTitle(title)
        return print_dialog.exec() == QDialog.DialogCode.Accepted

    def _print_label_for_guided_selection(self) -> None:
        self._print_label_for_sku(self._gfs.sku)

    def _print_label_for_selected_catalog_row(self) -> None:
        self._print_label_for_sku(self._selected_catalog_sku())

    def _print_label_for_sku(self, sku: str) -> None:
        sku = (sku or "").strip()
        if not sku:
            return
        selected_row = next(
            (row for row in self.catalog_snapshot_rows if str(row.get("sku")) == sku), None
        )
        if selected_row is None:
            return
        self._open_label_dialog_for_row(selected_row)

    def _open_label_dialog_for_row(self, selected_row: dict) -> None:
        if not self._show_pin_dialog():
            return

        if self.offline_mode:
            # Modo offline: renderizar desde cache, sin DB
            label_context = InventoryLabelContext(
                variant_id=0,
                sku=str(selected_row["sku"]),
                product_name=str(selected_row.get("producto_nombre_base") or selected_row.get("producto_nombre") or ""),
                talla=str(selected_row.get("talla") or ""),
                color=str(selected_row.get("color") or ""),
            )
            cache_row = selected_row

            def _render_label_offline(mode: str, requested_copies: int) -> "object":
                return render_inventory_label_from_cache_row(
                    cache_row, mode=mode, requested_copies=requested_copies
                )

            build_inventory_label_dialog(
                self,
                initial_context=label_context,
                variant_ids=[0],
                current_index=0,
                load_context=lambda _vid: label_context,
                render_label=_render_label_offline,
                print_label=lambda image_path, copies, sku_val, parent: self._print_satellite_label(
                    image_path,
                    title=f"Etiqueta {sku_val}",
                    copies=copies,
                    parent=parent,
                ),
            )
            return

        # Modo online: cargar desde DB
        variant_id = int(selected_row["variante_id"])
        try:
            with get_session() as session:
                label_context = load_inventory_label_context(session, variant_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error al cargar etiqueta", str(exc))
            return

        render_state = {"variant_id": variant_id}

        def _render_label(mode: str, requested_copies: int) -> "object":
            with get_session() as session:
                return render_inventory_label(
                    session,
                    render_state["variant_id"],
                    mode=mode,
                    requested_copies=requested_copies,
                )

        def _load_context(vid: int) -> "InventoryLabelContext":
            with get_session() as session:
                ctx = load_inventory_label_context(session, vid)
            render_state["variant_id"] = ctx.variant_id
            return ctx

        build_inventory_label_dialog(
            self,
            initial_context=label_context,
            variant_ids=[variant_id],
            current_index=0,
            load_context=_load_context,
            render_label=_render_label,
            print_label=lambda image_path, copies, sku_val, parent: self._print_satellite_label(
                image_path,
                title=f"Etiqueta {sku_val}",
                copies=copies,
                parent=parent,
            ),
        )

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


def _configure_satellite_table(
    table: QTableWidget,
    *,
    stretch_columns: tuple[int, ...],
    resize_columns: tuple[int, ...],
) -> None:
    table.setCornerButtonEnabled(False)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.verticalHeader().setDefaultSectionSize(38)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setMinimumSectionSize(56)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setStretchLastSection(False)
    for column_index in range(table.columnCount()):
        header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.ResizeToContents)
    for column_index in stretch_columns:
        header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
    for column_index in resize_columns:
        header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.ResizeToContents)


def _reload_satellite_table_widget(
    table: QTableWidget,
    *,
    row_count: int,
    populate_rows,
) -> None:
    previous_updates_enabled = table.updatesEnabled()
    previous_signals_blocked = table.signalsBlocked()
    table.setUpdatesEnabled(False)
    table.blockSignals(True)
    try:
        table.clearContents()
        table.setRowCount(row_count)
        populate_rows()
    finally:
        table.blockSignals(previous_signals_blocked)
        table.setUpdatesEnabled(previous_updates_enabled)


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


def _guided_display_color_label(raw_value: object) -> str:
    color_label = str(raw_value or "").strip()
    normalized = color_label.lower().replace(" ", "").replace("-", "")
    if not color_label or normalized in {"sincolor", "adhoc"}:
        return ""
    return color_label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)
