"""Ventana satelite para gestion dedicada de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import sys
import textwrap
import unicodedata
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, QSize, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
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
from pos_uniformes.services.catalog_school_link_service import list_all_active_links
from pos_uniformes.services.school_links_cache_service import load_school_links_cache, save_school_links_cache
from pos_uniformes.ui.dialogs.school_product_link_dialog import prompt_school_product_link_admin
from pos_uniformes.services.satellite_favorites_service import load_favorites, seed_favorites_from_bundle, toggle_favorite
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.presupuesto_service import PresupuestoService
from pos_uniformes.services.offline_quote_storage_service import (
    delete_offline_quote,
    get_offline_quote,
    list_offline_quotes,
    save_offline_quote,
)
from pos_uniformes.services.quote_client_creation_feedback_service import build_quote_client_created_feedback
from pos_uniformes.services.quote_action_service import cancel_quote, emit_quote
from pos_uniformes.services.quote_detail_service import QuoteDetailSnapshot, load_quote_detail_snapshot
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
from pos_uniformes.ui.helpers.quote_guided_catalog_helper import build_favorites_catalog_view, build_guided_catalog_view
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


class _DoubleClickButton(QPushButton):
    """QPushButton que emite una señal dedicada al hacer doble clic."""

    from PyQt6.QtCore import pyqtSignal as _pyqtSignal
    double_clicked = _pyqtSignal()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class _DoubleClickFrame(QFrame):
    """QFrame que emite una señal dedicada al hacer doble clic."""

    from PyQt6.QtCore import pyqtSignal as _pyqtSignal
    double_clicked = _pyqtSignal()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


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
        self._current_share_snapshot: QuoteDetailSnapshot | None = None
        self.offline_saved_quotes_table: QTableWidget | None = None
        self.offline_saved_box: QGroupBox | None = None
        self._offline_selected_quote: dict | None = None
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
        seed_favorites_from_bundle()
        self._favorites: set[str] = load_favorites()
        self._school_links: list[dict] = load_school_links_cache()

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
        self.nav_search_button.setEnabled(True)
        self.nav_search_button.setToolTip("Presupuestos guardados localmente")
        self.nav_share_button.setEnabled(True)
        self.nav_share_button.setToolTip("Compartir presupuesto guardado localmente")
        self.refresh_button.setEnabled(False)
        self.refresh_button.setToolTip("Sin conexion con la PC principal")
        # Presupuesto: tab habilitado pero guardado a DB desactivado — emit local disponible
        self.nav_quote_button.setToolTip("Modo local — solo emision por WhatsApp")

        self._reset_quote_form()
        self._apply_lookup_view(build_empty_quote_kiosk_lookup_view())
        self._apply_catalog_detail(None)
        self._apply_guided_detail(None)
        self._refresh_recent_lookup_table()

        # Refrescar vistas que no necesitan DB
        self._refresh_catalog_snapshot_from_cache()
        self._refresh_catalog_browser()
        self._refresh_offline_saved_list()
        self._refresh_offline_quotes()
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
        self.guided_favorites_button = QPushButton("♥ Favoritos")
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
        self.kiosk_lookup_talla_label = QLabel("")
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
        self.quote_print_cart_button = QPushButton("Imprimir")
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
        self.quote_action_hint_label = QLabel("")
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

        self.guided_status_label.setObjectName("guidedStepHint")
        self.guided_path_label.setObjectName("guidedPath")

        content = QWidget()
        content.setObjectName("guidedPageSurface")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._build_guided_steps_card())
        layout.addWidget(self._build_guided_detail_card())
        layout.addSpacing(160)
        content.setLayout(layout)
        scroll.setWidget(content)

        page_layout.addWidget(scroll, 1)
        page.setLayout(page_layout)
        return page

    def _build_guided_steps_card(self) -> QFrame:
        """Construye el card de navegación por pasos (pasos 1–7 + footer)."""
        steps_box = QFrame()
        steps_box.setObjectName("guidedStepsCard")
        steps_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        steps_layout = QVBoxLayout()
        steps_layout.setContentsMargins(12, 10, 12, 8)
        steps_layout.setSpacing(4)
        _steps_header = QHBoxLayout()
        _steps_header.setSpacing(8)
        _steps_title = QLabel("Cotiza por pasos")
        _steps_title.setObjectName("guidedGroupBoxTitle")
        self.guided_favorites_button.setObjectName("chipButton")
        self.guided_favorites_button.setFixedHeight(32)
        _steps_header.addWidget(_steps_title)
        _steps_header.addStretch()
        _steps_header.addWidget(self.guided_favorites_button)
        steps_layout.addLayout(_steps_header)
        steps_layout.addWidget(self.guided_path_label)

        # Paso 1 — Ruta
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

        # Paso 2 — Nivel
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

        # Paso 3 — Escuela
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

        # Paso 4 — Tipo de uniforme
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

        # Paso 5a — Perfil oficial
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

        # Paso 5b — Grupo (básicos/extras)
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

        # Paso 6 — Tipo de pieza
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

        # Paso 7 — Modelos sugeridos
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

        # Footer
        guided_footer_actions = QHBoxLayout()
        guided_footer_actions.setSpacing(8)
        guided_footer_actions.addStretch()
        self.guided_reset_button.setObjectName("ghostButton")
        self.guided_basics_button.setObjectName("secondaryButton")
        guided_footer_actions.addWidget(self.guided_reset_button)
        guided_footer_actions.addWidget(self.guided_basics_button)
        steps_layout.addLayout(guided_footer_actions)

        steps_box.setLayout(steps_layout)
        return steps_box

    def _build_guided_detail_card(self) -> QFrame:
        """Construye el card de producto seleccionado (ícono + variantes + acciones)."""
        detail_box = QFrame()
        detail_box.setObjectName("guidedStepsCard")
        detail_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(12, 10, 12, 8)
        detail_layout.setSpacing(8)
        _detail_title = QLabel("Producto seleccionado")
        _detail_title.setObjectName("guidedGroupBoxTitle")
        detail_layout.addWidget(_detail_title)

        # Header: ícono + texto
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

        # Variantes
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

        # Acciones
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
        return detail_box

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
        root = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ======== COLUMNA IZQUIERDA ========
        left = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)

        # --- Tarjeta de escaneo ---
        self.kiosk_scan_input.setPlaceholderText("Escanea o captura el SKU aquí")
        self.kiosk_scan_input.setClearButtonEnabled(True)
        self.kiosk_scan_input.setObjectName("satScanInput")
        self.kiosk_scan_input.setMinimumHeight(46)
        self.kiosk_scan_input.setMinimumWidth(0)
        self.kiosk_lookup_button.setObjectName("secondaryButton")
        self.kiosk_add_button.setObjectName("addToCartButton")

        scan_field_label = QLabel("CÓDIGO DE PRODUCTO")
        scan_field_label.setObjectName("satKioskScanLabel")

        scan_input_row = QHBoxLayout()
        scan_input_row.setSpacing(10)
        scan_input_row.addWidget(self.kiosk_scan_input, 1)

        scan_action_row = QHBoxLayout()
        scan_action_row.setSpacing(10)
        scan_action_row.addWidget(self.kiosk_lookup_button)
        scan_action_row.addWidget(self.kiosk_add_button, 1)

        scan_card = QFrame()
        scan_card.setObjectName("satScanCard")
        scan_card_layout = QVBoxLayout()
        scan_card_layout.setContentsMargins(20, 16, 20, 16)
        scan_card_layout.setSpacing(12)
        scan_card_layout.addWidget(scan_field_label)
        scan_card_layout.addLayout(scan_input_row)
        scan_card_layout.addLayout(scan_action_row)
        scan_card.setLayout(scan_card_layout)

        # --- Tarjeta hero del producto ---
        self.kiosk_lookup_sku_label.setObjectName("satKioskSku")
        self.kiosk_lookup_product_label.setObjectName("satKioskProduct")
        self.kiosk_lookup_talla_label.setObjectName("satKioskTalla")
        self.kiosk_lookup_talla_label.setWordWrap(True)
        self.kiosk_lookup_price_label.setObjectName("satKioskPrice")
        self.kiosk_lookup_status_label.setObjectName("satKioskBadge")
        self.kiosk_lookup_detail_label.setObjectName("satKioskBody")
        self.kiosk_lookup_context_label.setObjectName("satKioskBody")
        self.kiosk_lookup_notes_label.setObjectName("satKioskBody")
        self.kiosk_visual_icon_label.setFixedSize(148, 148)
        self.kiosk_lookup_product_label.setWordWrap(True)
        self.kiosk_lookup_detail_label.setWordWrap(True)
        self.kiosk_lookup_context_label.setWordWrap(True)
        self.kiosk_lookup_notes_label.setWordWrap(True)

        hero_icon_text = QHBoxLayout()
        hero_icon_text.setSpacing(20)
        hero_icon_text.addWidget(self.kiosk_visual_icon_label, 0, Qt.AlignmentFlag.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        hero_text.addWidget(self.kiosk_lookup_sku_label)
        hero_text.addWidget(self.kiosk_lookup_product_label)
        hero_text.addWidget(self.kiosk_lookup_talla_label)
        hero_text.addSpacing(6)
        hero_text.addWidget(self.kiosk_lookup_price_label)
        hero_text.addWidget(self.kiosk_lookup_status_label, 0, Qt.AlignmentFlag.AlignLeft)
        hero_icon_text.addLayout(hero_text, 1)

        hero_divider = QFrame()
        hero_divider.setObjectName("satHeroDivider")
        hero_divider.setFrameShape(QFrame.Shape.HLine)

        hero_card = QFrame()
        hero_card.setObjectName("satProductHeroCard")
        hero_card_layout = QVBoxLayout()
        hero_card_layout.setContentsMargins(22, 20, 22, 20)
        hero_card_layout.setSpacing(12)
        hero_card_layout.addLayout(hero_icon_text)
        hero_card_layout.addWidget(hero_divider)
        hero_card_layout.addWidget(self.kiosk_lookup_detail_label)
        hero_card_layout.addWidget(self.kiosk_lookup_context_label)
        hero_card_layout.addWidget(self.kiosk_lookup_notes_label)
        hero_card_layout.addStretch()
        hero_card.setLayout(hero_card_layout)

        left_layout.addWidget(scan_card)
        left_layout.addWidget(hero_card, 1)
        left.setLayout(left_layout)

        # ======== COLUMNA DERECHA ========
        self.kiosk_open_quote_button.setObjectName("secondaryButton")
        self.kiosk_open_search_button.setObjectName("ghostButton")

        quick_nav_row = QHBoxLayout()
        quick_nav_row.setSpacing(8)
        quick_nav_row.addWidget(self.kiosk_open_quote_button, 1)
        quick_nav_row.addWidget(self.kiosk_open_search_button, 1)

        recent_title = QLabel("Escaneos recientes")
        recent_title.setObjectName("satDetailTitle")
        recent_hint = QLabel("Toca una fila para volver a cargarla.")
        recent_hint.setObjectName("satMeta")

        self.kiosk_recent_table.setColumnCount(5)
        self.kiosk_recent_table.setHorizontalHeaderLabels(
            ["SKU", "Producto", "Precio", "Escuela", "Detalle"]
        )
        self.kiosk_recent_table.verticalHeader().setVisible(False)
        self.kiosk_recent_table.setAlternatingRowColors(True)
        self.kiosk_recent_table.setSelectionBehavior(
            self.kiosk_recent_table.SelectionBehavior.SelectRows
        )
        self.kiosk_recent_table.setMinimumWidth(480)
        self.kiosk_recent_table.setMinimumHeight(520)
        _configure_satellite_table(
            self.kiosk_recent_table,
            stretch_columns=(1, 4),
            resize_columns=(0, 2, 3),
        )

        recent_card = QFrame()
        recent_card.setObjectName("satRecentCard")
        recent_card_layout = QVBoxLayout()
        recent_card_layout.setContentsMargins(16, 16, 16, 16)
        recent_card_layout.setSpacing(10)
        recent_card_layout.addWidget(recent_title)
        recent_card_layout.addWidget(recent_hint)
        recent_card_layout.addWidget(self.kiosk_recent_table, 1)
        recent_card.setLayout(recent_card_layout)

        right = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addLayout(quick_nav_row)
        right_layout.addWidget(recent_card, 1)
        right.setLayout(right_layout)

        layout.addWidget(left, 5)
        layout.addWidget(right, 3)
        root.setLayout(layout)
        return root

    def _make_form_label(self, text: str) -> QLabel:
        """Etiqueta de campo de formulario con estilo satFieldLabel."""
        label = QLabel(text)
        label.setObjectName("satFieldLabel")
        return label

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.addWidget(self._build_editor_form_panel())
        layout.addWidget(self._build_editor_cart_panel(), 1)
        layout.addWidget(self._build_offline_saved_panel())
        panel.setLayout(layout)
        return panel

    def _build_editor_form_panel(self) -> QGroupBox:
        """Construye el panel de datos del presupuesto: escaneo, form y acciones."""
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
        self.quote_print_cart_button.setObjectName("ghostButton")
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
        self.quote_client_combo.setEnabled(False)
        self.quote_client_combo.setToolTip("Cliente asignado por escaneo QR. No se puede cambiar manualmente.")

        scan_stack = QVBoxLayout()
        scan_stack.setSpacing(4)
        scan_stack.addWidget(self._make_form_label("Escaneo"))
        scan_row = QHBoxLayout()
        scan_row.setSpacing(6)
        scan_row.addWidget(self.quick_scan_input, 1)
        scan_row.addWidget(self.quick_scan_button)
        scan_row.addStretch(2)
        scan_stack.addLayout(scan_row)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.addWidget(self._make_form_label("Folio"), 0, 0)
        form.addWidget(self.quote_folio_input, 0, 1, 1, 2)
        form.addWidget(self._make_form_label("Cliente (QR)"), 0, 3)
        form.addWidget(self.quote_client_combo, 0, 4, 1, 2)
        form.addWidget(self.quote_create_client_button, 0, 6)
        form.addWidget(self._make_form_label("Vigencia"), 1, 0)
        form.addWidget(self.quote_validity_input, 1, 1, 1, 2)
        form.addWidget(self._make_form_label("Observacion"), 2, 0)
        form.addWidget(self.quote_note_input, 2, 1, 1, 6)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.quote_draft_button)
        actions.addWidget(self.quote_emit_button)
        actions.addWidget(self.quote_print_cart_button)
        actions.addStretch()
        actions.addWidget(self.quote_qty_down_button)
        actions.addWidget(self.quote_qty_up_button)
        actions.addWidget(self.quote_remove_button)
        actions.addWidget(self.quote_clear_button)

        editor_layout.addLayout(scan_stack)
        editor_layout.addLayout(form)
        editor_layout.addLayout(actions)
        editor_box.setLayout(editor_layout)
        return editor_box

    def _build_editor_cart_panel(self) -> QGroupBox:
        """Construye el panel del carrito: tabla de líneas, totales y resumen."""
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
        return cart_box

    def _build_offline_saved_panel(self) -> QGroupBox:
        box = QGroupBox("Guardados localmente (sin conexion)")
        box.setObjectName("infoCard")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Folio", "Cliente", "Total", "Acciones"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(120)
        table.setMaximumHeight(220)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)

        self.offline_saved_quotes_table = table
        self.offline_saved_box = box
        layout.addWidget(table)
        box.setLayout(layout)
        box.setVisible(False)
        return box

    def _refresh_offline_saved_list(self) -> None:
        if self.offline_saved_quotes_table is None or self.offline_saved_box is None:
            return
        quotes = list_offline_quotes()
        self.offline_saved_box.setVisible(bool(quotes))
        table = self.offline_saved_quotes_table
        table.setRowCount(len(quotes))
        for row_idx, q in enumerate(quotes):
            folio = str(q.get("folio", ""))
            table.setItem(row_idx, 0, _table_item(folio))
            table.setItem(row_idx, 1, _table_item(str(q.get("client_name", ""))))
            table.setItem(row_idx, 2, _table_item(f"${q.get('total', '0')}"))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)
            print_btn = QPushButton("Imprimir")
            print_btn.setObjectName("ghostButton")
            del_btn = QPushButton("Eliminar")
            del_btn.setObjectName("dangerButton")
            print_btn.clicked.connect(lambda _checked, f=folio: self._handle_print_offline_quote(f))
            del_btn.clicked.connect(lambda _checked, f=folio: self._handle_delete_offline_quote(f))
            btn_layout.addWidget(print_btn)
            btn_layout.addWidget(del_btn)
            btn_widget.setLayout(btn_layout)
            table.setCellWidget(row_idx, 3, btn_widget)

    def _handle_print_offline_quote(self, folio: str) -> None:
        q = get_offline_quote(folio)
        if q is None:
            QMessageBox.warning(self, "No encontrado", f"El presupuesto {folio} no existe.")
            return
        from datetime import date
        try:
            validity_str = q.get("validity_date", "")
            validity_date = date.fromisoformat(validity_str) if validity_str else None
        except Exception:
            validity_date = None
        cart_view = build_quote_cart_view(q.get("cart", []))
        content = _build_cart_ticket_text(
            folio=folio,
            client_name=str(q.get("client_name", "Sin cliente")),
            cart=q.get("cart", []),
            total=cart_view.total,
            validity_date=validity_date,
            notes=str(q.get("notes", "")),
        )
        open_printable_text_dialog(self, f"Presupuesto {folio}", content)

    def _handle_delete_offline_quote(self, folio: str) -> None:
        reply = QMessageBox.question(
            self,
            "Eliminar presupuesto local",
            f"¿Eliminar el presupuesto {folio} del almacenamiento local?\nEsta accion no se puede deshacer.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_offline_quote(folio)
            self._refresh_offline_saved_list()

    def _refresh_offline_quotes(self) -> None:
        """Popula quote_table con los presupuestos guardados localmente."""
        from datetime import date as _date
        quotes = list_offline_quotes()
        self.quote_table.setRowCount(len(quotes))
        for row_index, q in enumerate(quotes):
            folio = str(q.get("folio", ""))
            client = str(q.get("client_name", ""))
            total = f"${q.get('total', '0')}"
            validity_str = str(q.get("validity_date", ""))
            try:
                validity_label = _date.fromisoformat(validity_str).strftime("%d/%m/%Y") if validity_str else ""
            except Exception:
                validity_label = validity_str
            created_str = str(q.get("created_at", ""))[:10]
            values = [folio, client, "LOCAL", total, "", validity_label, created_str]
            for col, val in enumerate(values):
                self.quote_table.setItem(row_index, col, _table_item(val))
            item = self.quote_table.item(row_index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, folio)
        self.quote_status_label.setText(
            f"{len(quotes)} presupuesto(s) guardado(s) localmente."
            if quotes else "Sin presupuestos locales aun."
        )
        self._offline_selected_quote = None
        self.selected_quote_state = ""
        self.selected_quote_phone = ""
        self._apply_quote_detail_view(build_empty_quote_detail_view())
        self._apply_share_detail_view(build_empty_quote_detail_view())
        self.share_status_label.setText("Selecciona un presupuesto local para compartirlo.")
        self._apply_action_state()

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
        self.quote_state_combo.addItem("Vencidos", "VENCIDO")
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

        self.quote_action_hint_label.setObjectName("quoteActionHint")
        history_layout.addWidget(self.quote_status_label)
        history_layout.addLayout(filters)
        history_layout.addLayout(actions)
        history_layout.addWidget(self.quote_action_hint_label)
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
        _guided_ctrl_shift_l = QShortcut(QKeySequence("Ctrl+Shift+L"), self.guided_page_scroll)
        _guided_ctrl_shift_l.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        _guided_ctrl_shift_l.activated.connect(self._open_school_product_link_admin)
        _admin_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        _admin_shortcut.activated.connect(self._open_satellite_admin)
        self.catalog_previous_page_button.clicked.connect(self._handle_catalog_browser_previous_page)
        self.catalog_next_page_button.clicked.connect(self._handle_catalog_browser_next_page)
        self.guided_add_button.clicked.connect(self._handle_add_guided_selection_to_quote)
        self.guided_print_label_button.clicked.connect(self._print_label_for_guided_selection)
        self.guided_favorites_button.clicked.connect(self._open_favorites_dialog)
        self.guided_reset_button.clicked.connect(self._handle_guided_reset_steps)
        self.guided_basics_button.clicked.connect(self._handle_guided_go_to_basics)
        self.quote_remove_button.clicked.connect(self._handle_remove_quote_item)
        self.quote_qty_down_button.clicked.connect(self._handle_decrease_quote_item_quantity)
        self.quote_qty_up_button.clicked.connect(self._handle_increase_quote_item_quantity)
        self.quote_clear_button.clicked.connect(self._handle_clear_quote_cart)
        self.quote_draft_button.clicked.connect(self._handle_save_quote_draft)
        self.quote_emit_button.clicked.connect(self._handle_emit_quote)
        self.quote_print_cart_button.clicked.connect(self._handle_print_cart)
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
        if page_key == "search" and self.offline_mode:
            self._refresh_offline_quotes()

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
        try:
            save_catalog_cache(self.catalog_snapshot_rows)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._school_links = list_all_active_links(session)
            save_school_links_cache(self._school_links)
        except Exception:  # noqa: BLE001
            pass
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
            school_links=self._school_links or None,
        )
        if self._correct_guided_state(view):
            return
        self._apply_guided_view(view)

    def _correct_guided_state(self, view) -> bool:
        """Corrige selecciones obsoletas contra las opciones disponibles en un solo pase.

        Retorna True si corrigió algo y se debe re-invocar _refresh_guided_browser.
        No recursea — resetea todo el estado inválido de una vez.
        """
        corrected = False

        available_levels = {opt.key for opt in view.level_options}
        if self._gfs.mode == "school" and self._gfs.level and self._gfs.level not in available_levels:
            self._gfs.level = ""
            self._gfs.school = ""
            self._gfs.sku = ""
            corrected = True

        available_schools = {opt.key for opt in view.school_options}
        if self._gfs.mode == "school" and self._gfs.school and self._gfs.school not in available_schools:
            self._gfs.school = ""
            self._gfs.profile = "TODOS"
            self._gfs.sku = ""
            corrected = True

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
            corrected = True

        available_buckets = {opt.key for opt in view.bucket_options}
        if self._gfs.mode == "basics" and self._gfs.bucket and self._gfs.bucket not in available_buckets:
            self._gfs.bucket = "BASICO" if "BASICO" in available_buckets else "TODOS"
            self._gfs.piece = ""
            self._gfs.product_key = ""
            self._gfs.sku = ""
            corrected = True

        available_pieces = {opt.key for opt in view.piece_options}
        if self._gfs.mode == "basics" and self._gfs.piece and self._gfs.piece not in available_pieces:
            self._gfs.piece = ""
            self._gfs.product_key = ""
            self._gfs.sku = ""
            corrected = True

        if corrected:
            self._refresh_guided_browser()
        return corrected

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
        sorted_cards = sorted(product_cards, key=lambda c: (c.key not in self._favorites, 0))
        for card in sorted_cards:
            product_btn = self._build_guided_product_button(card)
            product_btn.setChecked(self._gfs.product_key == card.key)
            product_btn.clicked.connect(lambda checked=False, selected=card.key: self._handle_guided_product_selected(selected))
            is_fav = card.key in self._favorites
            heart_btn = QPushButton("♥" if is_fav else "♡")
            heart_btn.setObjectName("favoriteButton")
            heart_btn.setFixedHeight(28)
            heart_btn.setCheckable(True)
            heart_btn.setChecked(is_fav)
            heart_btn.setToolTip("Quitar de favoritos" if is_fav else "Agregar a favoritos")
            heart_btn.clicked.connect(lambda checked=False, key=card.key: self._handle_toggle_favorite(key))
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(2)
            container_layout.addWidget(product_btn)
            container_layout.addWidget(heart_btn)
            self.guided_product_flow_layout.addWidget(container)
            self.guided_product_buttons[card.key] = product_btn

    def _confirm_favorites_password(self, action: str) -> bool:
        """Pide contraseña para agregar o quitar un favorito. Retorna True si es correcta."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Favoritos")
        dialog.setModal(True)
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        lbl = QLabel(f"Ingresa la contraseña para {action}.")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_input.setPlaceholderText("Contraseña")
        layout.addWidget(pwd_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        pwd_input.returnPressed.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        if pwd_input.text().strip() != "12345":
            QMessageBox.warning(self, "Contraseña incorrecta", "La contraseña ingresada no es válida.")
            return False
        return True

    def _handle_toggle_favorite(self, product_key: str) -> None:
        self._favorites = set(load_favorites())
        if product_key in self._favorites:
            if not self._confirm_favorites_password("quitar este favorito"):
                self._refresh_guided_browser()
                return
        else:
            if not self._confirm_favorites_password("agregar este favorito"):
                self._refresh_guided_browser()
                return
        toggle_favorite(product_key)
        self._favorites = set(load_favorites())
        self._refresh_guided_browser()

    def _open_satellite_admin(self) -> None:
        from pos_uniformes.ui.dialogs.satellite_admin_dialog import open_satellite_admin_dialog
        open_satellite_admin_dialog(self)

    def _open_school_product_link_admin(self) -> None:
        if self.offline_mode:
            QMessageBox.information(
                self,
                "No disponible",
                "La administración de ligas requiere conexión con la PC principal.",
            )
            return
        prompt_school_product_link_admin(
            self,
            on_links_changed=self._reload_school_links,
        )

    def _reload_school_links(self) -> None:
        try:
            with get_session() as session:
                self._school_links = list_all_active_links(session)
                save_school_links_cache(self._school_links)
        except Exception:  # noqa: BLE001
            pass
        self._refresh_guided_browser()

    def _open_favorites_dialog(self) -> None:
        """Abre un dialog con todas las piezas favoritas para agregar rápidamente al carrito."""
        self._favorites = set(load_favorites())
        if not self._favorites:
            QMessageBox.information(
                self,
                "Sin favoritos",
                "No hay favoritos guardados.\nToca ♥ en las piezas del flujo guiado para marcarlas.",
            )
            return

        _extra_css = """
QFrame#favDialogHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6f331d, stop:0.55 #a84f2d, stop:1 #c96a35);
}
QLabel#favDialogTitle {
    font-size: 22px;
    font-weight: 900;
    color: #f9f4ea;
}
QLabel#favDialogCount {
    font-size: 13px;
    font-weight: 700;
    color: #f6ddca;
    background: rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 3px 10px;
}
QWidget#favDialogLeft {
    background: #f4efe7;
}
QWidget#favDialogRight {
    background: #fbf8f2;
    border-left: 1px solid #dce5eb;
}
QLabel#favDialogGroupLabel {
    color: #87492c;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 0.8px;
    padding: 8px 0 2px 2px;
}
QLabel#favDialogProductName {
    font-size: 17px;
    font-weight: 800;
    color: #2f2a24;
}
QFrame#favDialogSep {
    background: #e3d8ca;
    max-height: 1px;
    border: none;
}
QLabel#favDialogPriceLabel {
    color: #87492c;
    font-size: 12px;
    font-weight: 800;
    padding: 4px 0 2px 0;
}
"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Los favoritos de Maximoda")
        dialog.setModal(True)
        dialog.setMinimumWidth(1104)
        dialog.setMinimumHeight(759)
        dialog.setStyleSheet(build_satellite_stylesheet() + _extra_css)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setObjectName("favDialogHeader")
        header_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h_row = QHBoxLayout()
        h_row.setContentsMargins(20, 14, 16, 14)
        h_row.setSpacing(12)
        title_lbl = QLabel("♥  Los favoritos de Maximoda")
        title_lbl.setObjectName("favDialogTitle")
        count_lbl = QLabel("")
        count_lbl.setObjectName("favDialogCount")
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("ghostButton")
        close_btn.setFixedWidth(88)
        h_row.addWidget(title_lbl)
        h_row.addWidget(count_lbl)
        h_row.addStretch()
        h_row.addWidget(close_btn)
        header_frame.setLayout(h_row)
        root.addWidget(header_frame)

        # ── Body ──────────────────────────────────────────────────────
        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)

        # Panel izquierdo — lista de piezas agrupadas
        left_panel = QWidget()
        left_panel.setObjectName("favDialogLeft")
        left_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_vbox = QVBoxLayout()
        left_vbox.setContentsMargins(14, 12, 10, 14)
        left_vbox.setSpacing(4)
        left_section_lbl = QLabel("PIEZAS GUARDADAS")
        left_section_lbl.setObjectName("satFieldLabel")
        left_vbox.addWidget(left_section_lbl)
        products_scroll = QScrollArea()
        products_scroll.setWidgetResizable(True)
        products_scroll.setFrameShape(QFrame.Shape.NoFrame)
        products_scroll.setObjectName("guidedScrollArea")
        products_scroll.viewport().setObjectName("guidedScrollViewport")
        left_vbox.addWidget(products_scroll, 1)
        left_panel.setLayout(left_vbox)
        body_row.addWidget(left_panel, 55)

        # Panel derecho — detalle + tallas + acciones
        right_panel = QWidget()
        right_panel.setObjectName("favDialogRight")
        right_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right_vbox = QVBoxLayout()
        right_vbox.setContentsMargins(16, 14, 16, 16)
        right_vbox.setSpacing(0)

        right_section_lbl = QLabel("PRODUCTO SELECCIONADO")
        right_section_lbl.setObjectName("satFieldLabel")
        right_vbox.addWidget(right_section_lbl)
        right_vbox.addSpacing(10)

        detail_icon_lbl = QLabel()
        detail_icon_lbl.setFixedSize(56, 56)
        detail_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_icon_lbl.setPixmap(_scaled_asset_pixmap("qr_icons/default.png", 40))

        detail_name_lbl = QLabel("Selecciona una pieza")
        detail_name_lbl.setObjectName("favDialogProductName")
        detail_name_lbl.setWordWrap(True)
        detail_subtitle_lbl = QLabel("Toca una tarjeta de la izquierda.")
        detail_subtitle_lbl.setObjectName("guidedStepHint")
        detail_subtitle_lbl.setWordWrap(True)

        detail_hrow = QHBoxLayout()
        detail_hrow.setSpacing(12)
        detail_hrow.addWidget(detail_icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
        detail_texts = QVBoxLayout()
        detail_texts.setSpacing(4)
        detail_texts.addWidget(detail_name_lbl)
        detail_texts.addWidget(detail_subtitle_lbl)
        detail_hrow.addLayout(detail_texts, 1)
        right_vbox.addLayout(detail_hrow)
        right_vbox.addSpacing(12)

        top_sep = QFrame()
        top_sep.setFrameShape(QFrame.Shape.HLine)
        top_sep.setObjectName("favDialogSep")
        right_vbox.addWidget(top_sep)
        right_vbox.addSpacing(10)

        variants_title_lbl = QLabel("ELIGE TALLA")
        variants_title_lbl.setObjectName("satFieldLabel")
        variants_title_lbl.setVisible(False)
        right_vbox.addWidget(variants_title_lbl)
        right_vbox.addSpacing(6)

        variants_container = QWidget()
        variants_vbox = QVBoxLayout()
        variants_vbox.setContentsMargins(0, 0, 0, 0)
        variants_vbox.setSpacing(4)
        variants_container.setLayout(variants_vbox)
        variants_container.setVisible(False)
        right_vbox.addWidget(variants_container)

        right_vbox.addStretch()

        footer_sep = QFrame()
        footer_sep.setFrameShape(QFrame.Shape.HLine)
        footer_sep.setObjectName("favDialogSep")
        right_vbox.addWidget(footer_sep)
        right_vbox.addSpacing(12)

        add_btn = QPushButton("Agregar al presupuesto")
        add_btn.setObjectName("primaryButton")
        add_btn.setEnabled(False)
        right_vbox.addWidget(add_btn)

        right_panel.setLayout(right_vbox)
        body_row.addWidget(right_panel, 45)

        root.addLayout(body_row, 1)
        dialog.setLayout(root)

        # ── Estado interno ─────────────────────────────────────────────
        _state: dict[str, str] = {"product_key": "", "sku": ""}
        _variant_buttons: dict[str, QPushButton] = {}
        _product_buttons: dict[str, QPushButton] = {}

        def _make_fav_card(card) -> QPushButton:
            lines = [card.title]
            if card.subtitle:
                lines.append(card.subtitle)
            btn = QPushButton("\n".join(lines))
            btn.setObjectName("guidedProductButton")
            btn.setCheckable(True)
            btn.setProperty("compactCard", True)
            btn.setMinimumHeight(72)
            btn.setFixedWidth(210)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            row = next((r for r in self.catalog_snapshot_rows if str(r.get("sku")) == card.sku), None)
            if row is not None:
                btn.setIcon(QIcon(_catalog_row_icon(row)))
                btn.setIconSize(QSize(26, 26))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            return btn

        def _rebuild_products() -> None:
            _product_buttons.clear()
            view = build_favorites_catalog_view(self.catalog_snapshot_rows, self._favorites)
            n = len(view.product_cards)
            count_lbl.setText(f"{n} pieza{'s' if n != 1 else ''}")

            new_container = QWidget()
            new_container.setObjectName("guidedGridSurface")
            new_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            new_vbox = QVBoxLayout()
            new_vbox.setContentsMargins(0, 4, 0, 16)
            new_vbox.setSpacing(0)

            # Agrupar por tipo de pieza (extraído del key: "pieza||nombre")
            groups: dict[str, list] = {}
            for card in view.product_cards:
                piece = card.key.split("||")[0].strip() if "||" in card.key else "Piezas"
                groups.setdefault(piece, []).append(card)

            for piece_label in sorted(groups, key=_fav_piece_sort_key):
                grp_lbl = QLabel(piece_label.upper())
                grp_lbl.setObjectName("favDialogGroupLabel")
                new_vbox.addWidget(grp_lbl)
                grp_container = QWidget()
                grp_flow = FlowLayout(margin=0, h_spacing=6, v_spacing=6)
                grp_container.setLayout(grp_flow)
                for card in groups[piece_label]:
                    pbtn = _make_fav_card(card)
                    pbtn.setChecked(card.key == _state["product_key"])
                    pbtn.clicked.connect(lambda checked=False, k=card.key: _select_product(k))
                    grp_flow.addWidget(pbtn)
                    _product_buttons[card.key] = pbtn
                new_vbox.addWidget(grp_container)
                new_vbox.addSpacing(2)

            new_vbox.addStretch()
            new_container.setLayout(new_vbox)
            products_scroll.setWidget(new_container)

        def _rebuild_variants(product_key: str) -> None:
            from decimal import Decimal as _D
            _clear_layout(variants_vbox)
            _variant_buttons.clear()

            # Filtrar directamente de snapshot para tener escuela_nombre disponible
            family_rows = [
                r for r in self.catalog_snapshot_rows
                if (
                    str(r.get("tipo_pieza_nombre") or "").strip()
                    + "||"
                    + str(r.get("producto_nombre_base") or r.get("producto_nombre") or "").strip()
                ) == product_key
                and r.get("activo", True)
            ]
            def _talla_sort_key(talla_str: str):
                try:
                    return (0, float(talla_str))
                except (ValueError, TypeError):
                    return (1, talla_str)

            family_rows.sort(key=lambda r: (
                str(r.get("escuela_nombre") or "General") != "General",  # General primero (False < True)
                str(r.get("escuela_nombre") or ""),
                _D(str(r.get("precio_venta") or "0")),
                _talla_sort_key(str(r.get("talla") or "")),
            ))

            if not family_rows:
                variants_title_lbl.setVisible(False)
                variants_container.setVisible(False)
                return
            variants_title_lbl.setVisible(True)
            variants_container.setVisible(True)

            # Agrupar por escuela → precio
            escuelas_distintas = {str(rr.get("escuela_nombre") or "General") for rr in family_rows}
            multi_escuela = len(escuelas_distintas) > 1
            current_school: str | None = None
            current_price: str | None = None
            current_flow: FlowLayout | None = None
            for r in family_rows:
                school = str(r.get("escuela_nombre") or "General").strip()
                price = f"${_D(str(r.get('precio_venta') or '0')).quantize(_D('0.01'))}"
                talla = str(r.get("talla") or "").strip()
                sku = str(r.get("sku") or "")

                if multi_escuela and school != current_school:
                    current_school = school
                    current_price = None  # forzar nuevo encabezado de precio
                    school_lbl = QLabel(
                        "Precio general" if school == "General" else f"Precio {school}"
                    )
                    school_lbl.setObjectName("favDialogGroupLabel")
                    variants_vbox.addWidget(school_lbl)

                if price != current_price or current_flow is None:
                    current_price = price
                    price_grp_lbl = QLabel(price)
                    price_grp_lbl.setObjectName("favDialogPriceLabel")
                    variants_vbox.addWidget(price_grp_lbl)
                    grp_widget = QWidget()
                    current_flow = FlowLayout(margin=0, h_spacing=6, v_spacing=6)
                    grp_widget.setLayout(current_flow)
                    variants_vbox.addWidget(grp_widget)

                size_text = f"Talla {talla}" if talla else sku
                vbtn = QPushButton(size_text)
                vbtn.setObjectName("guidedChoiceButton")
                vbtn.setCheckable(True)
                vbtn.setProperty("compactChoice", True)
                vbtn.setMinimumHeight(44)
                vbtn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                vbtn.clicked.connect(lambda checked=False, s=sku: _select_sku(s))
                current_flow.addWidget(vbtn)
                _variant_buttons[sku] = vbtn

        def _select_product(key: str) -> None:
            _state["product_key"] = key
            _state["sku"] = ""
            add_btn.setEnabled(False)
            for k, b in _product_buttons.items():
                b.setChecked(k == key)
            view = build_favorites_catalog_view(
                self.catalog_snapshot_rows, self._favorites, selected_product_key=key
            )
            card_map = {c.key: c for c in view.product_cards}
            card = card_map.get(key)
            if card:
                detail_name_lbl.setText(card.title)
                detail_subtitle_lbl.setText(card.subtitle or "")
                row = next((r for r in self.catalog_snapshot_rows if str(r.get("sku")) == card.sku), None)
                if row is not None:
                    detail_icon_lbl.setPixmap(
                        _catalog_row_icon(row).scaled(
                            48, 48,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    detail_icon_lbl.setPixmap(_scaled_asset_pixmap("qr_icons/default.png", 40))
            _rebuild_variants(key)

        def _select_sku(sku: str) -> None:
            _state["sku"] = sku
            add_btn.setEnabled(bool(sku))
            for s, b in _variant_buttons.items():
                b.setChecked(s == sku)

        def _add_to_cart() -> None:
            if not _state["sku"]:
                return
            self._add_quote_item_by_sku(_state["sku"], 1)
            _state["sku"] = ""
            add_btn.setEnabled(False)
            for b in _variant_buttons.values():
                b.setChecked(False)
            detail_subtitle_lbl.setText("✓ Agregado — elige otra talla o pieza.")

        def _do_print_label() -> None:
            sku = _state["sku"]
            if not sku:
                return
            selected_row = next(
                (r for r in self.catalog_snapshot_rows if str(r.get("sku")) == sku), None
            )
            if selected_row is None:
                return
            self._open_label_dialog_for_row(selected_row)

        add_btn.clicked.connect(_add_to_cart)
        QShortcut(QKeySequence("Ctrl+P"), dialog).activated.connect(_do_print_label)
        close_btn.clicked.connect(dialog.accept)

        _rebuild_products()
        dialog.exec()
        self._refresh_guided_browser()

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
            button = _DoubleClickButton(option.label)
            button.setObjectName("guidedChoiceButton")
            button.setCheckable(True)
            button.setMinimumHeight(60)
            button.setProperty("compactChoice", True)
            button.setMinimumHeight(42)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setChecked(self._gfs.sku == option.sku)
            button.clicked.connect(lambda checked=False, selected=option.sku: self._handle_guided_variant_selected(selected))
            def _on_variant_double_click(sku=option.sku):
                self._handle_guided_variant_selected(sku)
                self._handle_add_guided_selection_to_quote()
            button.double_clicked.connect(_on_variant_double_click)
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
            can_operate=self._can_build_cart(),
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        normalized_sku = sku.strip().upper()
        if not normalized_sku:
            QMessageBox.warning(self, "Datos incompletos", "Captura un SKU antes de agregarlo.")
            return

        if self.offline_mode:
            self._add_quote_item_from_cache(normalized_sku, quantity)
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

    def _add_quote_item_from_cache(self, normalized_sku: str, quantity: int) -> None:
        row = next(
            (r for r in self.catalog_snapshot_rows if str(r.get("sku", "")).upper() == normalized_sku),
            None,
        )
        if row is None:
            QMessageBox.warning(self, "SKU no encontrado", f"'{normalized_sku}' no esta en el catalogo local.")
            return
        product_name = str(row.get("producto_nombre_base") or row.get("producto_nombre") or normalized_sku)
        unit_price = Decimal(str(row.get("precio_venta") or "0"))
        existing = next((i for i in self.quote_cart if str(i.get("sku", "")) == normalized_sku), None)
        if existing:
            existing["cantidad"] = int(existing["cantidad"]) + quantity
        else:
            self.quote_cart.append({
                "sku": normalized_sku,
                "producto_nombre": product_name,
                "cantidad": quantity,
                "precio_unitario": unit_price,
                "talla": str(row.get("talla") or ""),
                "nivel_educativo_nombre": str(row.get("nivel_educativo_nombre") or ""),
                "escuela_nombre": str(row.get("escuela_nombre") or ""),
            })
        self._refresh_quote_cart_table()
        self.kiosk_scan_input.setFocus()
        self._set_status(f"Agregado: {product_name} ({normalized_sku})")

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
        if self.offline_mode:
            self._handle_offline_save_draft()
            return
        self._persist_quote(EstadoPresupuesto.BORRADOR)

    def _handle_offline_save_draft(self) -> None:
        if not self.quote_cart:
            QMessageBox.warning(self, "Presupuesto vacio", "Agrega al menos un producto al presupuesto.")
            return
        folio = self._generate_quote_folio()
        client_name = self.quote_client_combo.currentText().strip() or "Mostrador / sin cliente"
        notes = self.quote_note_input.toPlainText().strip()
        validity_date = self.quote_validity_input.date().toPyDate()
        cart_view = build_quote_cart_view(self.quote_cart)
        try:
            save_offline_quote(
                folio=folio,
                client_name=client_name,
                client_phone="",
                notes=notes,
                validity_date=validity_date,
                cart=self.quote_cart,
                total=cart_view.total,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar localmente:\n{exc}")
            return
        self.quote_cart.clear()
        self._refresh_quote_cart_table()
        self._refresh_offline_saved_list()
        self._set_status(f"Presupuesto {folio} guardado localmente.")
        QMessageBox.information(
            self,
            "Guardado localmente",
            f"Presupuesto {folio} guardado.\nAparece en la lista inferior. Puedes imprimirlo desde ahi.",
        )

    def _handle_emit_quote(self) -> None:
        if self.offline_mode:
            self._handle_offline_emit()
            return
        self._persist_quote(EstadoPresupuesto.EMITIDO)

    def _handle_offline_emit(self) -> None:
        """Emite el presupuesto en modo local: genera folio y abre WhatsApp sin guardar en DB."""
        if not self.quote_cart:
            QMessageBox.warning(self, "Presupuesto vacio", "Agrega al menos un producto al presupuesto.")
            return
        client_info = self._prompt_offline_client_info()
        if client_info is None:
            return
        folio = self._generate_quote_folio()
        client_name = client_info["nombre"] or "cliente"
        phone = client_info["telefono"]
        cart_view = build_quote_cart_view(self.quote_cart)
        message = _build_offline_whatsapp_message(
            folio=folio,
            client_name=client_name,
            cart=self.quote_cart,
            total=cart_view.total,
            validity_date=self.quote_validity_input.date().toPyDate(),
            notes=self.quote_note_input.toPlainText().strip(),
        )
        if phone:
            normalized = _normalize_whatsapp_phone(phone)
            if normalized:
                from urllib.parse import quote as _url_quote
                whatsapp_url = f"https://wa.me/{normalized}?text={_url_quote(message)}"
                if webbrowser.open(whatsapp_url):
                    self._set_status(f"Presupuesto {folio} enviado por WhatsApp (modo local).")
                    return
        # Fallback: show dialog with copyable message
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Presupuesto {folio} — modo local")
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout()
        hint = QLabel("Copia el mensaje y envialo manualmente por WhatsApp.")
        hint.setWordWrap(True)
        text_area = QTextEdit()
        text_area.setPlainText(message)
        text_area.setReadOnly(True)
        text_area.setMinimumHeight(220)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Copiar mensaje")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(message))
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(hint)
        layout.addWidget(text_area)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec()
        self._set_status(f"Presupuesto {folio} generado en modo local.")

    def _prompt_offline_client_info(self) -> dict | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Datos del cliente")
        layout = QVBoxLayout()
        intro = QLabel("Datos del cliente para el mensaje de WhatsApp (opcionales).")
        intro.setWordWrap(True)
        name_input = QLineEdit()
        name_input.setPlaceholderText("Nombre del cliente")
        phone_input = QLineEdit()
        phone_input.setPlaceholderText("Telefono (ej: 521234567890)")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(intro)
        layout.addWidget(name_input)
        layout.addWidget(phone_input)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {"nombre": name_input.text().strip(), "telefono": phone_input.text().strip()}

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
                state_filter=str(getattr(target_state, "value", target_state)).strip().upper(),
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
        from PyQt6.QtGui import QRegularExpressionValidator
        from PyQt6.QtCore import QRegularExpression
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo cliente rapido")
        dialog.resize(420, 230)
        layout = QVBoxLayout()
        intro = QLabel("Registra nombre y telefono para seguir con el presupuesto.")
        intro.setWordWrap(True)
        form = QFormLayout()
        name_input = QLineEdit()
        phone_input = QLineEdit()
        name_input.setPlaceholderText("Nombre del cliente")
        phone_input.setPlaceholderText("10 digitos")
        phone_input.setMaxLength(10)
        phone_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}")))
        error_label = QLabel("")
        error_label.setStyleSheet("color: #c0392b; font-size: 12px;")
        error_label.setVisible(False)
        form.addRow("Nombre", name_input)
        form.addRow("Telefono", phone_input)
        form.addRow("", error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)

        def _try_accept() -> None:
            digits = phone_input.text().strip()
            if len(digits) != 10:
                error_label.setText("El telefono debe tener exactamente 10 digitos.")
                error_label.setVisible(True)
                phone_input.setFocus()
                return
            error_label.setVisible(False)
            dialog.accept()

        buttons.accepted.connect(_try_accept)
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
        if self.offline_mode:
            self._refresh_offline_quote_detail(self._selected_offline_folio())
        else:
            self._refresh_quote_detail(self._selected_quote_id())
        self._apply_action_state()

    def _handle_open_share_page(self) -> None:
        if self.offline_mode:
            if self._offline_selected_quote is None:
                QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto antes de abrir Compartir.")
                return
        elif self._selected_quote_id() is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto antes de abrir Compartir.")
            return
        self._set_page("share")

    def _handle_refresh_selected_quote_detail(self) -> None:
        self._refresh_quote_detail(self._selected_quote_id())
        if self._selected_quote_id() is not None:
            self._set_status("Detalle actualizado para compartir.")

    def _refresh_offline_quote_detail(self, folio: str | None) -> None:
        from datetime import date as _date
        from decimal import Decimal as _Decimal
        if folio is None:
            self._offline_selected_quote = None
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            self._apply_quote_detail_view(build_empty_quote_detail_view())
            self._apply_share_detail_view(build_empty_quote_detail_view())
            self.share_status_label.setText("Selecciona un presupuesto local para compartirlo.")
            return
        q = get_offline_quote(folio)
        if q is None:
            self._offline_selected_quote = None
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            self._apply_quote_detail_view(build_error_quote_detail_view(f"No se encontro el presupuesto {folio}"))
            self._apply_share_detail_view(build_error_quote_detail_view(f"No se encontro el presupuesto {folio}"))
            self.share_status_label.setText(f"No se encontro el presupuesto {folio}.")
            return
        self._offline_selected_quote = q
        self.selected_quote_state = "EMITIDO"
        phone = str(q.get("client_phone", ""))
        self.selected_quote_phone = phone if phone.strip() else ""
        validity_str = str(q.get("validity_date", ""))
        try:
            validity_label = _date.fromisoformat(validity_str).strftime("%d/%m/%Y") if validity_str else "Sin vigencia"
        except Exception:
            validity_label = validity_str or "Sin vigencia"
        cart = q.get("cart", [])
        detail_rows = [
            {
                "sku": str(item.get("sku", "")),
                "description": str(item.get("producto_nombre") or item.get("sku", "")),
                "size_label": str(item.get("talla") or "-"),
                "quantity": int(item.get("cantidad", 1)),
                "unit_price": str(_Decimal(str(item.get("precio_unitario", "0"))).quantize(_Decimal("0.01"))),
                "subtotal": str((_Decimal(str(item.get("precio_unitario", "0"))) * int(item.get("cantidad", 1))).quantize(_Decimal("0.01"))),
            }
            for item in cart
        ]
        detail_view = build_quote_detail_view(
            folio=folio,
            client_name=str(q.get("client_name", "Sin cliente")),
            status_label="LOCAL",
            phone_text=phone or "Sin telefono",
            total=str(q.get("total", "0")),
            validity_label=validity_label,
            user_label="local",
            notes_text=str(q.get("notes", "")),
            detail_rows=detail_rows,
        )
        self._apply_quote_detail_view(detail_view)
        self._apply_share_detail_view(detail_view)
        self.share_status_label.setText(f"Presupuesto local {folio} listo para imprimir o compartir.")

    def _refresh_quote_detail(self, quote_id: int | None) -> None:
        if quote_id is None:
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            self._current_share_snapshot = None
            self._apply_quote_detail_view(build_empty_quote_detail_view())
            self._apply_share_detail_view(build_empty_quote_detail_view())
            self.share_status_label.setText("Selecciona un presupuesto desde Buscar.")
            return
        try:
            with get_session() as session:
                quote_snapshot = load_quote_detail_snapshot(session, quote_id=quote_id)
            self._current_share_snapshot = quote_snapshot
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
            self._current_share_snapshot = None
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
        if self.offline_mode:
            has_offline = self._offline_selected_quote is not None
            has_phone = bool(_normalize_whatsapp_phone(self.selected_quote_phone))
            self.quote_resume_button.setEnabled(False)
            self.quote_emit_selected_button.setEnabled(False)
            _hint = "Presupuesto local — solo puedes imprimirlo o compartirlo." if has_offline else "Selecciona un presupuesto local para ver las acciones disponibles."
            self.quote_action_hint_label.setText(_hint)
            self.quote_action_hint_label.setVisible(True)
            self.quote_cancel_button.setEnabled(False)
            self.quote_open_share_button.setEnabled(has_offline)
            self.quote_whatsapp_button.setEnabled(has_offline and has_phone)
            self.quote_print_button.setEnabled(has_offline)
            self.share_refresh_button.setEnabled(False)
        else:
            action_state = build_quote_satellite_action_state(
                can_operate=self._can_operate(),
                has_selection=self._selected_quote_id() is not None,
                selected_state=self.selected_quote_state,
                has_phone=bool(_normalize_whatsapp_phone(self.selected_quote_phone)),
            )
            self.quote_resume_button.setEnabled(action_state.resume_enabled)
            self.quote_emit_selected_button.setEnabled(action_state.emit_enabled)
            _state = self.selected_quote_state.strip().upper()
            if self._selected_quote_id() is None:
                _hint = "Selecciona un presupuesto para ver las acciones disponibles."
            elif _state == "BORRADOR":
                _hint = "Borrador — puedes retomarlo o emitirlo directamente."
            elif _state == "EMITIDO":
                _hint = "Ya emitido — solo puedes cancelarlo o compartirlo."
            elif _state == "CANCELADO":
                _hint = "Cancelado — sin acciones disponibles."
            elif _state == "CONVERTIDO":
                _hint = "Convertido a venta — sin acciones disponibles."
            else:
                _hint = ""
            self.quote_action_hint_label.setText(_hint)
            self.quote_action_hint_label.setVisible(bool(_hint))
            self.quote_cancel_button.setEnabled(action_state.cancel_enabled)
            self.quote_open_share_button.setEnabled(action_state.share_enabled)
            self.quote_whatsapp_button.setEnabled(action_state.whatsapp_enabled)
            self.quote_print_button.setEnabled(action_state.print_enabled)
            self.share_refresh_button.setEnabled(self._selected_quote_id() is not None)
        self.kiosk_add_button.setEnabled(self.lookup_snapshot is not None and self._can_operate())
        self.catalog_add_button.setEnabled(bool(self._selected_catalog_sku()) and self._can_build_cart())
        self.catalog_print_label_button.setEnabled(bool(self._selected_catalog_sku()))
        self.guided_add_button.setEnabled(bool(self._gfs.sku) and self._can_build_cart())
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
        if self.selected_quote_state.strip().upper() != "BORRADOR":
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
        if self.selected_quote_state.strip().upper() != "BORRADOR":
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

    def _handle_print_cart(self) -> None:
        if not self.quote_cart:
            QMessageBox.warning(self, "Presupuesto vacio", "Agrega al menos un producto al presupuesto.")
            return
        folio = self._generate_quote_folio()
        client_name = self.quote_client_combo.currentText().strip() or "Mostrador / sin cliente"
        notes = self.quote_note_input.toPlainText().strip()
        validity_date = self.quote_validity_input.date().toPyDate()
        cart_view = build_quote_cart_view(self.quote_cart)
        content = _build_cart_ticket_text(
            folio=folio,
            client_name=client_name,
            cart=self.quote_cart,
            total=cart_view.total,
            validity_date=validity_date,
            notes=notes,
        )
        open_printable_text_dialog(self, f"Presupuesto {folio}", content)

    def _handle_print_quote(self) -> None:
        if self.offline_mode:
            q = self._offline_selected_quote
            if q is None:
                QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para imprimirlo.")
                return
            from datetime import date as _date
            validity_str = str(q.get("validity_date", ""))
            try:
                validity_date = _date.fromisoformat(validity_str) if validity_str else None
            except Exception:
                validity_date = None
            cart_view = build_quote_cart_view(q.get("cart", []))
            content = _build_cart_ticket_text(
                folio=str(q.get("folio", "")),
                client_name=str(q.get("client_name", "Sin cliente")),
                cart=q.get("cart", []),
                total=cart_view.total,
                validity_date=validity_date,
                notes=str(q.get("notes", "")),
            )
            open_printable_text_dialog(self, f"Presupuesto {q.get('folio', '')}", content)
            return
        snapshot = self._current_share_snapshot
        if snapshot is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para imprimirlo.")
            return
        content = _build_snapshot_ticket_text(snapshot)
        open_printable_text_dialog(self, f"Presupuesto {snapshot.folio}", content)

    def _handle_open_quote_whatsapp(self) -> None:
        if self.offline_mode:
            q = self._offline_selected_quote
            if q is None:
                QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para compartirlo.")
                return
            phone = str(q.get("client_phone", ""))
            normalized_phone = _normalize_whatsapp_phone(phone)
            if not normalized_phone:
                QMessageBox.warning(self, "Telefono faltante", "El presupuesto seleccionado no tiene telefono valido.")
                return
            from datetime import date as _date
            validity_str = str(q.get("validity_date", ""))
            try:
                validity_date = _date.fromisoformat(validity_str) if validity_str else None
            except Exception:
                validity_date = None
            message = _build_offline_whatsapp_message(
                folio=str(q.get("folio", "")),
                client_name=str(q.get("client_name", "cliente")),
                cart=q.get("cart", []),
                total=q.get("total", "0"),
                validity_date=validity_date,
                notes=str(q.get("notes", "")),
            )
            whatsapp_url = f"https://wa.me/{normalized_phone}?text={quote(message)}"
            if not webbrowser.open(whatsapp_url):
                QMessageBox.warning(
                    self,
                    "No se pudo abrir WhatsApp",
                    "No se pudo abrir WhatsApp automaticamente. Verifica que tengas navegador disponible.",
                )
                return
            self._set_status(f"WhatsApp preparado para {q.get('client_name', 'cliente')}.")
            return
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
        card = _DoubleClickFrame()
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

        card.double_clicked.connect(self._show_cart_popup)
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
                def _on_remove(index=row_idx):
                    self._remove_quote_item_at_index(index)
                    _refresh_table()
                remove_btn.clicked.connect(_on_remove)
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
        self.kiosk_lookup_talla_label.setText(lookup_view.talla_label)
        self.kiosk_lookup_talla_label.setVisible(bool(lookup_view.talla_label))
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
        if quote_id is None:
            return None
        try:
            return int(quote_id)
        except (ValueError, TypeError):
            return None

    def _selected_offline_folio(self) -> str | None:
        selected_row = self.quote_table.currentRow()
        if selected_row < 0:
            return None
        item = self.quote_table.item(selected_row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return str(data) if data is not None else None

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

    def _can_build_cart(self) -> bool:
        """Permite agregar piezas al armado incluso en modo local (sin DB)."""
        if self.offline_mode:
            return True
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
        cut_between_copies: bool = False,
    ) -> bool:
        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError(f"No se pudo abrir la imagen de etiqueta:\n{image_path}")
        if sys.platform.startswith("win"):
            from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
                print_inventory_label_via_windows,
            )
            preferred_printer = ""
            if not self.offline_mode:
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
                cut_between_copies=cut_between_copies,
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
        if self.offline_mode:
            # Modo offline: renderizar desde cache, sin DB
            # Recopilar siblings del mismo producto para Anterior/Siguiente
            _product_name_off = str(selected_row.get("producto_nombre_base") or selected_row.get("producto_nombre") or "")
            _escuela_off = str(selected_row.get("escuela_nombre") or "")
            _nivel_off = str(selected_row.get("nivel_educativo_nombre") or "")
            offline_siblings = [
                r for r in self.catalog_snapshot_rows
                if str(r.get("producto_nombre_base") or r.get("producto_nombre") or "") == _product_name_off
                and str(r.get("escuela_nombre") or "") == _escuela_off
                and str(r.get("nivel_educativo_nombre") or "") == _nivel_off
            ] or [selected_row]
            _current_sku = str(selected_row["sku"])
            _off_index = next((i for i, r in enumerate(offline_siblings) if str(r["sku"]) == _current_sku), 0)

            def _make_offline_context(row: dict) -> "InventoryLabelContext":
                return InventoryLabelContext(
                    variant_id=0,
                    sku=str(row["sku"]),
                    product_name=str(row.get("producto_nombre_base") or row.get("producto_nombre") or ""),
                    talla=str(row.get("talla") or ""),
                    color=str(row.get("color") or ""),
                )

            offline_render_state: dict[str, object] = {"row": selected_row}

            def _render_label_offline(mode: str, requested_copies: int) -> "object":
                return render_inventory_label_from_cache_row(
                    offline_render_state["row"], mode=mode, requested_copies=requested_copies
                )

            def _load_context_offline(idx: int) -> "InventoryLabelContext":
                row = offline_siblings[idx] if 0 <= idx < len(offline_siblings) else selected_row
                offline_render_state["row"] = row
                return _make_offline_context(row)

            build_inventory_label_dialog(
                self,
                initial_context=_make_offline_context(selected_row),
                variant_ids=list(range(len(offline_siblings))),
                current_index=_off_index,
                load_context=_load_context_offline,
                render_label=_render_label_offline,
                print_label=lambda image_path, copies, sku_val, parent, mode: self._print_satellite_label(
                    image_path,
                    title=f"Etiqueta {sku_val}",
                    copies=copies,
                    parent=parent,
                    cut_between_copies=(mode == "continuous"),
                ),
            )
            return

        # Modo online: cargar desde DB
        variant_id = int(selected_row["variante_id"])

        # Recopilar todas las variantes del mismo producto para habilitar Anterior/Siguiente
        product_name = str(selected_row.get("producto_nombre_base") or selected_row.get("producto_nombre") or "")
        escuela_nombre = str(selected_row.get("escuela_nombre") or "")
        nivel_nombre = str(selected_row.get("nivel_educativo_nombre") or "")
        sibling_rows = [
            r for r in self.catalog_snapshot_rows
            if str(r.get("producto_nombre_base") or r.get("producto_nombre") or "") == product_name
            and str(r.get("escuela_nombre") or "") == escuela_nombre
            and str(r.get("nivel_educativo_nombre") or "") == nivel_nombre
            and r.get("variante_id") is not None
        ]
        sibling_variant_ids = [int(r["variante_id"]) for r in sibling_rows]
        if variant_id not in sibling_variant_ids:
            sibling_variant_ids = [variant_id]
        current_index = sibling_variant_ids.index(variant_id)

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
            variant_ids=sibling_variant_ids,
            current_index=current_index,
            load_context=_load_context,
            render_label=_render_label,
            print_label=lambda image_path, copies, sku_val, parent, mode: self._print_satellite_label(
                image_path,
                title=f"Etiqueta {sku_val}",
                copies=copies,
                parent=parent,
                cut_between_copies=(mode == "continuous"),
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


def _build_snapshot_ticket_text(snapshot: QuoteDetailSnapshot) -> str:
    from pos_uniformes.services.quote_text_service import DEFAULT_QUOTE_TERMS_LINES

    _W = 38

    def _sep() -> str:
        return "─" * _W

    def _center(text: str) -> str:
        return text.center(_W)

    def _row(label: str, value: str) -> str:
        gap = _W - len(label) - len(value)
        return f"{label}{' ' * max(1, gap)}{value}"

    def _fmt(value: object) -> str:
        try:
            return str(Decimal(str(value)).quantize(Decimal("0.01")))
        except Exception:  # noqa: BLE001
            return str(value)

    lines: list[str] = []
    lines.append(_center("POS Uniformes"))
    lines.append(_center("Presupuesto"))
    lines.append(_sep())
    lines.append(_row("Folio:", snapshot.folio))
    lines.append(_row("Estado:", snapshot.status_label))
    lines.append(_row("Cliente:", snapshot.customer_label))
    if snapshot.phone_text and snapshot.phone_text.lower() != "sin telefono":
        lines.append(_row("Telefono:", snapshot.phone_text))
    if snapshot.validity_label and snapshot.validity_label.lower() != "sin vigencia":
        lines.append(_row("Vigencia:", snapshot.validity_label))
    lines.append(_sep())
    lines.append("PIEZAS")
    lines.append(_sep())
    for detail in snapshot.detail_rows:
        unit_price = Decimal(str(detail.unit_price)).quantize(Decimal("0.01"))
        subtotal = Decimal(str(detail.subtotal)).quantize(Decimal("0.01"))
        talla = str(detail.size_label or "").strip()
        lines.append("")
        lines.append(str(detail.description))
        if talla and talla != "-":
            lines.append(f"Talla: {talla}")
        lines.append(_row(f"{detail.sku} | {detail.quantity} x ${unit_price}", f"${subtotal}"))
    lines.append("")
    lines.append(_sep())
    lines.append(_row("TOTAL ESTIMADO:", f"${_fmt(snapshot.total)}"))
    lines.append(_sep())
    if snapshot.notes_text and snapshot.notes_text.lower() != "sin observaciones.":
        lines.append("Observaciones:")
        lines.append(snapshot.notes_text)
        lines.append("")
    lines.append("Terminos y condiciones")
    lines.append(_sep())
    for term_line in DEFAULT_QUOTE_TERMS_LINES:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])
    return "\n".join(lines)


def _build_cart_ticket_text(
    *,
    folio: str,
    client_name: str,
    cart: list[dict],
    total: object,
    validity_date: object,
    notes: str,
) -> str:
    from pos_uniformes.services.quote_text_service import DEFAULT_QUOTE_TERMS_LINES

    _W = 38

    def _sep() -> str:
        return "─" * _W

    def _center(text: str) -> str:
        return text.center(_W)

    def _row(label: str, value: str) -> str:
        gap = _W - len(label) - len(value)
        return f"{label}{' ' * max(1, gap)}{value}"

    def _fmt(value: object) -> str:
        try:
            return str(Decimal(str(value)).quantize(Decimal("0.01")))
        except Exception:  # noqa: BLE001
            return str(value)

    lines: list[str] = []
    lines.append(_center("POS Uniformes"))
    lines.append(_center("Presupuesto"))
    lines.append(_sep())
    lines.append(_row("Folio:", folio))
    lines.append(_row("Cliente:", client_name))
    if validity_date is not None:
        try:
            lines.append(_row("Vigencia:", validity_date.strftime("%d/%m/%Y")))
        except Exception:  # noqa: BLE001
            pass
    lines.append(_sep())
    lines.append("PIEZAS")
    lines.append(_sep())
    for item in cart:
        qty = int(item["cantidad"])
        unit_price = Decimal(str(item["precio_unitario"])).quantize(Decimal("0.01"))
        subtotal = (unit_price * qty).quantize(Decimal("0.01"))
        description = str(item.get("producto_nombre") or item.get("sku", ""))
        sku = str(item["sku"])
        talla = str(item.get("talla") or "").strip()
        lines.append("")
        lines.append(description)
        if talla and talla != "-":
            lines.append(f"Talla: {talla}")
        lines.append(_row(f"{sku} | {qty} x ${unit_price}", f"${subtotal}"))
    lines.append("")
    lines.append(_sep())
    lines.append(_row("TOTAL ESTIMADO:", f"${_fmt(total)}"))
    lines.append(_sep())
    if notes:
        lines.append("Observaciones:")
        lines.append(notes)
        lines.append("")
    lines.append("Terminos y condiciones")
    lines.append(_sep())
    for term_line in DEFAULT_QUOTE_TERMS_LINES:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])
    return "\n".join(lines)


def _build_offline_whatsapp_message(
    *,
    folio: str,
    client_name: str,
    cart: list[dict],
    total: object,
    validity_date: object,
    notes: str,
) -> str:
    lines = [
        f"Hola {client_name}, te compartimos tu presupuesto {folio}.",
        "POS Uniformes",
        f"Total estimado: ${Decimal(str(total)).quantize(Decimal('0.01'))}",
    ]
    if validity_date is not None:
        try:
            lines.append(f"Vigencia: {validity_date.strftime('%d/%m/%Y')}")
        except Exception:  # noqa: BLE001
            pass
    lines.append("Piezas:")
    for item in cart:
        qty = int(item["cantidad"])
        unit_price = Decimal(str(item["precio_unitario"])).quantize(Decimal("0.01"))
        subtotal = (unit_price * qty).quantize(Decimal("0.01"))
        description = str(item.get("producto_nombre") or item.get("sku", ""))
        talla = str(item.get("talla") or "").strip()
        talla_suffix = f" T:{talla}" if talla and talla != "-" else ""
        lines.append(f"- {description}{talla_suffix}")
        lines.append(f"  SKU {item['sku']} | {qty} x {unit_price} = {subtotal}")
    if notes:
        lines.append(f"Observaciones: {notes}")
    lines.append(f"Para confirmar, menciona el folio {folio}.")
    return "\n".join(lines)


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


_FAV_PIECE_ORDER = [
    "pantalon",   # Pantalón
    "falda",      # Falda
    "sueter",     # Suéter
    "camisa",     # Camisa
    "playera",    # Playera
    "calceta",    # Calceta
    "malla",      # Malla
]


def _fav_piece_sort_key(label: str) -> tuple[int, str]:
    """Orden personalizado para grupos de piezas en el dialog de favoritos.

    Quita acentos antes de comparar para que 'Pantalón' → 'pantalon' y
    'Suéter' → 'sueter' coincidan con las keywords sin acento.
    """
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", label.lower())
        if unicodedata.category(c) != "Mn"
    )
    for i, kw in enumerate(_FAV_PIECE_ORDER):
        if kw in stripped:
            return (i, stripped)
    return (len(_FAV_PIECE_ORDER), stripped)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)
