"""Ventana principal funcional del sistema POS."""

import csv
import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace
import unicodedata
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import engine, get_session, test_connection
from pos_uniformes.database.models import (
    AtributoProducto,
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    CambioCatalogo,
    Categoria,
    Cliente,
    Compra,
    Escuela,
    EstadoApartado,
    EstadoPresupuesto,
    EstadoCompra,
    EstadoVenta,
    Marca,
    MovimientoInventario,
    ImportacionCatalogoFila,
    NivelLealtad,
    NivelEducativo,
    Presupuesto,
    Producto,
    Proveedor,
    RolUsuario,
    SesionCaja,
    TipoCliente,
    TipoCambioCatalogo,
    TipoMovimientoCaja,
    TipoMovimientoInventario,
    TipoEntidadCatalogo,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
    Venta,
    VentaDetalle,
)
from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService
from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_active_filters_summary,
    build_filters_label,
)
from pos_uniformes.services.bootstrap_service import BootstrapService
from pos_uniformes.services.backup_service import (
    backup_output_dir,
    create_backup,
    format_size,
    list_backups,
    restore_backup,
)
from pos_uniformes.services.business_settings_service import BusinessSettingsInput, BusinessSettingsService
from pos_uniformes.services.caja_service import CajaService
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.compra_service import CompraItemInput, CompraService
from pos_uniformes.services.customer_card_service import CustomerCardRenderInput, CustomerCardService
from pos_uniformes.services.inventario_service import (
    AjusteMasivoFilaInput,
    InventarioService,
)
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.manual_promo_flow_service import (
    apply_manual_promo_authorization,
    build_manual_promo_state,
    clear_manual_promo_state,
    current_manual_promo_percent,
    decide_manual_promo_change,
)
from pos_uniformes.services.manual_promo_service import ManualPromoService
from pos_uniformes.services.marketing_audit_service import MarketingAuditService
from pos_uniformes.services.presupuesto_service import PresupuestoItemInput, PresupuestoService
from pos_uniformes.services.business_payment_settings_service import load_business_payment_settings_snapshot
from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
from pos_uniformes.services.layaway_receipt_text_service import build_layaway_receipt_text
from pos_uniformes.services.sale_note_service import build_sale_note_parts
from pos_uniformes.services.sale_loyalty_notice_service import build_sale_loyalty_transition_notice
from pos_uniformes.services.sale_discount_option_service import (
    build_sale_discount_options,
    expected_discount_option_label,
)
from pos_uniformes.services.sale_ticket_text_service import build_sale_ticket_text
from pos_uniformes.services.sale_document_service import (
    load_layaway_for_receipt,
    load_sale_for_layaway_ticket,
    load_sale_for_ticket,
)
from pos_uniformes.services.sale_client_benefit_service import resolve_sale_client_benefit
from pos_uniformes.services.sale_client_discount_service import resolve_sale_client_discount
from pos_uniformes.services.sale_client_sync_service import resolve_sale_client_sync_state
from pos_uniformes.services.sale_discount_lock_service import (
    build_sale_discount_lock_state,
    build_sale_discount_lock_tooltip,
)
from pos_uniformes.services.sale_discount_service import (
    build_sale_discount_breakdown,
    calculate_sale_pricing,
    calculate_sale_totals,
    effective_sale_discount_percent,
    format_discount_label,
    normalize_discount_value,
)
from pos_uniformes.services.search_filter_service import row_matches_search
from pos_uniformes.services.scanned_client_flow_service import (
    build_client_already_linked_feedback,
    build_client_linked_feedback,
    build_replace_client_confirmation,
    build_scanned_client_kept_feedback,
    decide_scanned_client_action,
)
from pos_uniformes.services.supplier_service import SupplierService
from pos_uniformes.services.user_service import UserService
from pos_uniformes.services.venta_service import VentaItemInput, VentaService
from pos_uniformes.ui.login_dialog import LoginDialog
from pos_uniformes.ui.dialogs.settings_dialogs import (
    build_backup_settings_dialog,
    build_business_settings_dialog,
    build_cash_history_settings_dialog,
    build_clients_settings_dialog,
    build_marketing_settings_dialog,
    build_suppliers_settings_dialog,
    build_whatsapp_settings_dialog,
    build_users_settings_dialog,
)
from pos_uniformes.ui.dialogs.payment_dialogs import (
    build_cash_payment_dialog,
    build_mixed_payment_dialog,
    build_transfer_payment_dialog,
)
from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog
from pos_uniformes.ui.helpers.sale_cart_table_helper import build_sale_cart_table_view
from pos_uniformes.ui.helpers.sale_cashier_summary_helper import build_sale_cashier_summary
from pos_uniformes.ui.views.analytics_view import build_analytics_tab
from pos_uniformes.ui.views.cashier_view import build_cashier_tab
from pos_uniformes.ui.views.dashboard_view import build_dashboard_tab
from pos_uniformes.ui.views.history_view import build_history_tab
from pos_uniformes.ui.views.inventory_view import build_inventory_tab
from pos_uniformes.ui.views.layaway_view import build_layaway_tab
from pos_uniformes.ui.views.products_view import build_products_tab
from pos_uniformes.ui.views.quotes_view import build_quotes_tab
from pos_uniformes.ui.views.settings_view import build_settings_tab
from pos_uniformes.utils.product_templates import (
    build_price_blocks,
    build_product_template_preview,
    build_step_template_preview,
    load_legacy_config_choices,
    load_legacy_product_templates,
    load_step_product_templates,
    merge_choice_lists,
    product_template_defaults,
    suggest_price_capture_mode,
    suggest_presentation_template,
    step_template_defaults,
)
from pos_uniformes.utils.label_generator import LabelGenerator
from pos_uniformes.utils.qr_generator import QrGenerator


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class MultiSelectFilterButton(QToolButton):
    selectionChanged = pyqtSignal()

    def __init__(self, default_label: str) -> None:
        super().__init__()
        self._default_label = default_label
        self._short_label = default_label.split(":", 1)[0]
        self._updating = False
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._update_text()

    def set_items(self, items: list[tuple[str, str]]) -> None:
        selected_values = self.selected_values()
        self._updating = True
        self._menu.clear()
        for label, data in items:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(str(data))
            action.setChecked(str(data) in selected_values)
            action.toggled.connect(self._handle_action_toggled)
            self._menu.addAction(action)
        self._updating = False
        self._update_text()

    def selected_values(self) -> set[str]:
        return {
            str(action.data())
            for action in self._menu.actions()
            if action.isCheckable() and action.isChecked()
        }

    def selected_labels(self) -> list[str]:
        return [
            action.text()
            for action in self._menu.actions()
            if action.isCheckable() and action.isChecked()
        ]

    def has_selection(self) -> bool:
        return bool(self.selected_values())

    def clear_selection(self) -> None:
        self._updating = True
        for action in self._menu.actions():
            if action.isCheckable():
                action.setChecked(False)
        self._updating = False
        self._update_text()
        self.selectionChanged.emit()

    def set_selected_values(self, values: list[str] | set[str]) -> None:
        normalized = {str(value) for value in values if str(value).strip()}
        self._updating = True
        for action in self._menu.actions():
            if action.isCheckable():
                action.setChecked(str(action.data()) in normalized)
        self._updating = False
        self._update_text()
        self.selectionChanged.emit()

    def _handle_action_toggled(self, _checked: bool) -> None:
        if self._updating:
            return
        self._update_text()
        self.selectionChanged.emit()

    def _update_text(self) -> None:
        labels = self.selected_labels()
        if not labels:
            self.setText(self._default_label)
            self.setToolTip(self._default_label)
            return
        joined = ", ".join(labels[:2])
        if len(labels) <= 2 and len(joined) <= 32:
            self.setText(joined)
        else:
            self.setText(f"{self._short_label}: {len(labels)}")
        self.setToolTip(f"{self._short_label}: {', '.join(labels)}")


class MultiSelectPickerButton(QPushButton):
    selectionChanged = pyqtSignal()

    def __init__(
        self,
        default_label: str,
        *,
        title: str,
        helper_text: str,
        columns: int = 4,
        presets: list[tuple[str, list[str] | Callable[[list[str]], list[str]]]] | None = None,
    ) -> None:
        super().__init__(default_label)
        self._default_label = default_label
        self._short_label = default_label.split(":", 1)[0]
        self._title = title
        self._helper_text = helper_text
        self._columns = max(1, columns)
        self._items: list[tuple[str, str]] = []
        self._selected_values: set[str] = set()
        self._presets = presets or []
        self.clicked.connect(self._open_picker)
        self._update_text()

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self._items = [(str(label), str(data)) for label, data in items if str(label).strip() and str(data).strip()]
        valid_values = {data for _label, data in self._items}
        self._selected_values = {value for value in self._selected_values if value in valid_values}
        self._update_text()

    def selected_values(self) -> set[str]:
        return set(self._selected_values)

    def selected_labels(self) -> list[str]:
        selected = self.selected_values()
        return [label for label, data in self._items if data in selected]

    def clear_selection(self) -> None:
        if not self._selected_values:
            return
        self._selected_values.clear()
        self._update_text()
        self.selectionChanged.emit()

    def set_selected_values(self, values: list[str] | set[str]) -> None:
        normalized = {str(value).strip() for value in values if str(value).strip()}
        valid_values = {data for _label, data in self._items}
        new_values = {value for value in normalized if value in valid_values}
        if new_values == self._selected_values:
            return
        self._selected_values = new_values
        self._update_text()
        self.selectionChanged.emit()

    def _update_text(self) -> None:
        labels = self.selected_labels()
        if not labels:
            self.setText(self._default_label)
            self.setToolTip(self._default_label)
            return
        joined = ", ".join(labels[:2])
        if len(labels) <= 2 and len(joined) <= 28:
            self.setText(joined)
        else:
            self.setText(f"{self._short_label}: {len(labels)}")
        self.setToolTip(f"{self._short_label}: {', '.join(labels)}")

    def _open_picker(self) -> None:
        dialog = QDialog(self.window())
        dialog.setWindowTitle(self._title)
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout()
        layout.setSpacing(12)

        helper_label = QLabel(self._helper_text)
        helper_label.setWordWrap(True)
        helper_label.setObjectName("subtleLine")
        layout.addWidget(helper_label)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Filtrar opciones")
        layout.addWidget(search_input)

        actions_row = QHBoxLayout()
        select_all_button = QPushButton("Todas")
        clear_button = QPushButton("Ninguna")
        count_label = QLabel()
        count_label.setObjectName("subtleLine")
        actions_row.addWidget(select_all_button)
        actions_row.addWidget(clear_button)
        actions_row.addWidget(count_label, 1)
        layout.addLayout(actions_row)

        if self._presets:
            preset_row = QHBoxLayout()
            preset_row.setSpacing(8)

            def current_values() -> list[str]:
                return [data for _label, data in self._items]

            def apply_preset(raw_values: list[str] | Callable[[list[str]], list[str]]) -> None:
                if callable(raw_values):
                    values = raw_values(current_values())
                else:
                    values = list(raw_values)
                normalized = {str(value).strip() for value in values if str(value).strip()}
                valid_values = {data for _label, data in self._items}
                for checkbox, _label, data in checkboxes:
                    checkbox.setChecked(data in normalized and data in valid_values)
                refresh_count()

            for label, values in self._presets:
                button = QPushButton(label)
                button.setObjectName("chipButton")
                button.clicked.connect(lambda _checked=False, preset=values: apply_preset(preset))
                preset_row.addWidget(button)
            preset_row.addStretch(1)
            layout.addLayout(preset_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        grid = QGridLayout()
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        checkboxes: list[tuple[QCheckBox, str, str]] = []
        for index, (label, data) in enumerate(self._items):
            checkbox = QCheckBox(label)
            checkbox.setChecked(data in self._selected_values)
            checkbox.setProperty("search_text", label.casefold())
            grid.addWidget(checkbox, index // self._columns, index % self._columns)
            checkboxes.append((checkbox, label, data))
        content.setLayout(grid)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        layout.addWidget(buttons)
        dialog.setLayout(layout)

        def refresh_count() -> None:
            selected_count = sum(1 for checkbox, _label, _data in checkboxes if checkbox.isChecked())
            count_label.setText(f"Seleccionadas: {selected_count}")

        def apply_search(text: str) -> None:
            needle = text.strip().casefold()
            for checkbox, label, _data in checkboxes:
                visible = not needle or needle in label.casefold()
                checkbox.setVisible(visible)

        def set_all_visible(checked: bool) -> None:
            for checkbox, _label, _data in checkboxes:
                if checkbox.isVisible():
                    checkbox.setChecked(checked)
            refresh_count()

        search_input.textChanged.connect(apply_search)
        select_all_button.clicked.connect(lambda: set_all_visible(True))
        clear_button.clicked.connect(lambda: set_all_visible(False))
        for checkbox, _label, _data in checkboxes:
            checkbox.toggled.connect(lambda _checked: refresh_count())
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        refresh_count()

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        selected = {
            data
            for checkbox, _label, data in checkboxes
            if checkbox.isChecked()
        }
        if selected == self._selected_values:
            return
        self._selected_values = selected
        self._update_text()
        self.selectionChanged.emit()


def _set_table_badge_style(item: QTableWidgetItem, tone: str) -> None:
    palette = {
        "positive": ("#f8dfcf", "#8f4527"),
        "warning": ("#fbf0cf", "#8a5a00"),
        "danger": ("#f8dfd9", "#9a2f22"),
        "muted": ("#ece8e1", "#6e675f"),
    }
    background, foreground = palette.get(tone, palette["muted"])
    item.setBackground(QColor(background))
    item.setForeground(QColor(foreground))
    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))


def _inline_metric_badge(label: str, value: object, tone: str) -> str:
    palette = {
        "positive": ("#f8dfcf", "#8f4527", "#dfb496"),
        "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
        "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
        "neutral": ("#fbf3ec", "#8c6656", "#ecd5c5"),
    }
    background, foreground, border = palette.get(tone, palette["neutral"])
    return (
        f"<span style=\"display:inline-block; margin-right:8px; margin-bottom:4px; "
        f"padding:5px 9px; border-radius:999px; background:{background}; color:{foreground}; "
        f"border:1px solid {border}; font-weight:700;\">"
        f"{label}: {value}</span>"
    )


def _stock_table_text(stock_value: int) -> str:
    if stock_value == 0:
        return "0 Agotado"
    if stock_value <= 3:
        return f"{stock_value} Bajo"
    return f"{stock_value} OK"


COMMON_COLORS = [
    "Negro",
    "Blanco",
    "Gris",
    "Azul",
    "Marino",
    "Celeste",
    "Rojo",
    "Verde",
    "Olivo",
    "Amarillo",
    "Beige",
    "Cafe",
    "Camel",
    "Khaki",
    "Rosa",
    "Morado",
    "Naranja",
    "Vino",
    "Plateado",
    "Dorado",
    "Multicolor",
]

COMMON_SIZES = [
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "XXL",
    "22",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
]

DEFAULT_VARIANT_SIZE = "Unitalla"
DEFAULT_VARIANT_COLOR = "Sin color"

PRODUCT_TEMPLATES = [
    {"label": "Jeans", "category": "Ropa", "name": "Jeans", "description": "Pantalon de mezclilla casual."},
    {"label": "Pantalon vestir", "category": "Ropa", "name": "Pantalon vestir", "description": "Pantalon formal para uso diario."},
    {"label": "Short", "category": "Ropa", "name": "Short", "description": "Short casual para temporada calida."},
    {"label": "Playera", "category": "Ropa", "name": "Playera", "description": "Playera basica de manga corta."},
    {"label": "Polo", "category": "Ropa", "name": "Polo", "description": "Playera tipo polo de uso casual."},
    {"label": "Camisa", "category": "Ropa", "name": "Camisa", "description": "Camisa casual o formal de manga larga."},
    {"label": "Blusa", "category": "Ropa", "name": "Blusa", "description": "Blusa ligera para uso diario."},
    {"label": "Sudadera", "category": "Ropa", "name": "Sudadera", "description": "Sudadera comoda para clima fresco."},
    {"label": "Chamarra", "category": "Ropa", "name": "Chamarra", "description": "Chamarra ligera o abrigadora."},
    {"label": "Vestido", "category": "Ropa", "name": "Vestido", "description": "Vestido casual o de ocasion especial."},
    {"label": "Falda", "category": "Ropa", "name": "Falda", "description": "Falda para uso casual o formal."},
    {"label": "Tenis", "category": "Calzado", "name": "Tenis", "description": "Calzado deportivo o casual."},
    {"label": "Zapato casual", "category": "Calzado", "name": "Zapato casual", "description": "Zapato comodo para uso diario."},
    {"label": "Zapato vestir", "category": "Calzado", "name": "Zapato vestir", "description": "Calzado formal para eventos o trabajo."},
    {"label": "Bota", "category": "Calzado", "name": "Bota", "description": "Bota casual o de trabajo."},
    {"label": "Botin", "category": "Calzado", "name": "Botin", "description": "Botin corto para temporada fresca."},
    {"label": "Sandalia", "category": "Calzado", "name": "Sandalia", "description": "Calzado abierto para clima calido."},
    {"label": "Pantufla", "category": "Calzado", "name": "Pantufla", "description": "Calzado comodo para interior."},
    {"label": "Cinturon", "category": "Accesorios", "name": "Cinturon", "description": "Accesorio de vestir para pantalones."},
    {"label": "Bolsa", "category": "Accesorios", "name": "Bolsa", "description": "Bolsa o bolso para uso diario."},
    {"label": "Mochila", "category": "Accesorios", "name": "Mochila", "description": "Mochila practica para escuela o trabajo."},
    {"label": "Gorra", "category": "Accesorios", "name": "Gorra", "description": "Gorra casual para uso diario."},
]

UNIFORM_MACRO_TYPES = ["Deportivo", "Oficial", "Basico", "Escolta", "Accesorio"]


class MainWindow(QMainWindow):
    def __init__(self, user_id: int) -> None:
        super().__init__()
        self.user_id = user_id
        self.current_username = ""
        self.current_full_name = ""
        self.current_role = RolUsuario.CAJERO
        self.cash_session_requires_cut = False
        self.cash_session_cut_reminder_key: tuple[int, date] | None = None
        self.catalog_rows: list[dict[str, object]] = []
        self.inventory_rows: list[dict[str, object]] = []
        self.sale_cart: list[dict[str, object]] = []
        self.layaway_rows: list[dict[str, object]] = []
        self.quote_cart: list[dict[str, object]] = []
        self.quote_rows: list[dict[str, object]] = []

        self.setWindowTitle("POS Uniformes")
        self.resize(1320, 860)

        self.session_label = QLabel()
        self.status_label = QLabel()
        self.metrics_label = QLabel()
        self.analytics_label = QLabel()
        self.layaway_alerts_label = QLabel()
        self.cash_session_label = QLabel()
        self.kpi_users_value = QLabel("0")
        self.kpi_products_value = QLabel("0")
        self.kpi_stock_value = QLabel("0")
        self.kpi_sales_value = QLabel("0")
        self.analytics_period_combo = QComboBox()
        self.analytics_client_combo = QComboBox()
        self.analytics_from_input = QDateEdit()
        self.analytics_to_input = QDateEdit()
        self.analytics_export_button = QPushButton("Exportar CSV/JSON")
        self.analytics_export_status_label = QLabel()
        self.analytics_sales_value = QLabel("$0.00")
        self.analytics_tickets_value = QLabel("0")
        self.analytics_average_value = QLabel("$0.00")
        self.analytics_units_value = QLabel("0")
        self.analytics_identified_sales_value = QLabel("0")
        self.analytics_identified_income_value = QLabel("$0.00")
        self.analytics_repeat_clients_value = QLabel("0")
        self.analytics_average_client_value = QLabel("$0.00")
        self.analytics_payment_table = QTableWidget()
        self.analytics_stock_table = QTableWidget()
        self.analytics_clients_table = QTableWidget()
        self.analytics_layaway_active_label = QLabel()
        self.analytics_layaway_balance_label = QLabel()
        self.analytics_layaway_overdue_label = QLabel()
        self.analytics_layaway_delivered_label = QLabel()
        self.dashboard_users_card: QFrame | None = None
        self.dashboard_manual_promo_box: QWidget | None = None
        self.dashboard_help_box: QWidget | None = None
        self.products_quick_setup_box: QWidget | None = None

        self.catalog_table = QTableWidget()
        self.recent_sales_table = QTableWidget()
        self.top_products_table = QTableWidget()
        self.movements_table = QTableWidget()

        self.category_name_input = QLineEdit()
        self.brand_name_input = QLineEdit()
        self.product_category_combo = QComboBox()
        self.product_brand_combo = QComboBox()
        self.product_name_input = QLineEdit()
        self.product_description_input = QTextEdit()
        self.variant_product_combo = QComboBox()
        self.variant_sku_input = QLineEdit()
        self.variant_size_input = QLineEdit()
        self.variant_color_input = QLineEdit()
        self.variant_price_input = QLineEdit()
        self.variant_cost_input = QLineEdit()
        self.variant_initial_stock_spin = QSpinBox()
        self.category_button = QPushButton("Crear categoria")
        self.brand_button = QPushButton("Crear marca")
        self.inventory_category_button = QPushButton("Crear categoria")
        self.inventory_brand_button = QPushButton("Crear marca")
        self.product_button = QPushButton("Crear producto")
        self.variant_button = QPushButton("Crear presentacion")
        self.catalog_permission_label = QLabel()
        self.catalog_results_label = QLabel()
        self.catalog_active_filters_label = QLabel()
        self.catalog_selection_label = QLabel("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label = QLabel("Consulta uniformes y usa filtros macro como Deportivo, Oficial, Basico, Escolta o Accesorio.")
        self.catalog_search_input = QLineEdit()
        self.catalog_category_filter_combo = MultiSelectFilterButton("Categoria: todas")
        self.catalog_brand_filter_combo = MultiSelectFilterButton("Marca: todas")
        self.catalog_school_filter_combo = MultiSelectFilterButton("Escuela: todas")
        self.catalog_type_filter_combo = MultiSelectFilterButton("Tipo uniforme: todos")
        self.catalog_piece_filter_combo = MultiSelectFilterButton("Pieza: todas")
        self.catalog_size_filter_combo = MultiSelectFilterButton("Talla: todas")
        self.catalog_color_filter_combo = MultiSelectFilterButton("Color: todos")
        self.catalog_uniform_macro_buttons: dict[str, QPushButton] = {}
        self.catalog_status_filter_combo = QComboBox()
        self.catalog_stock_filter_combo = QComboBox()
        self.catalog_layaway_filter_combo = QComboBox()
        self.catalog_origin_filter_combo = QComboBox()
        self.catalog_duplicate_filter_combo = QComboBox()
        self.catalog_clear_filters_button = QPushButton("Limpiar filtros")
        self.edit_product_category_combo = QComboBox()
        self.edit_product_brand_combo = QComboBox()
        self.edit_product_name_input = QLineEdit()
        self.edit_product_description_input = QTextEdit()
        self.update_product_button = QPushButton("Guardar producto")
        self.toggle_product_button = QPushButton("Desactivar producto")
        self.edit_variant_product_combo = QComboBox()
        self.edit_variant_sku_input = QLineEdit()
        self.edit_variant_size_input = QLineEdit()
        self.edit_variant_color_input = QLineEdit()
        self.edit_variant_price_input = QLineEdit()
        self.edit_variant_cost_input = QLineEdit()
        self.update_variant_button = QPushButton("Guardar presentacion")
        self.toggle_variant_button = QPushButton("Desactivar presentacion")
        self.delete_product_button = QPushButton("Eliminar producto")
        self.delete_variant_button = QPushButton("Eliminar presentacion")

        self.purchase_provider_combo = QComboBox()
        self.purchase_variant_combo = QComboBox()
        self.purchase_qty_spin = QSpinBox()
        self.purchase_cost_input = QLineEdit()
        self.purchase_document_input = QLineEdit()
        self.purchase_button = QPushButton("Confirmar compra")
        self.purchase_permission_label = QLabel()

        self.sale_sku_input = QLineEdit()
        self.sale_qty_spin = QSpinBox()
        self.sale_folio_input = QLabel()
        self.sale_client_combo = QComboBox()
        self.sale_payment_combo = QComboBox()
        self.sale_discount_combo = QComboBox()
        self.sale_received_spin = QDoubleSpinBox()
        self.sale_add_button = QPushButton("Agregar al carrito")
        self.sale_button = QPushButton("Confirmar venta")
        self.sale_layaway_button = QPushButton("Convertir a apartado")
        self.sale_recent_button = QPushButton("Ventas recientes")
        self.sale_ticket_button = QPushButton("Ver ticket")
        self.cancel_button = QPushButton("Cancelar venta seleccionada")
        self.cancel_permission_label = QLabel()
        self.sale_cart_table = QTableWidget()
        self.sale_remove_button = QPushButton("Quitar linea")
        self.sale_clear_button = QPushButton("Vaciar carrito")
        self.sale_summary_label = QLabel("Carrito vacio.")
        self.sale_total_label = QLabel("$0.00")
        self.sale_total_meta_label = QLabel("Total a cobrar")
        self.sale_change_label = QLabel("$0.00")
        self.sale_feedback_label = QLabel("Listo para escanear.")
        self.sales_dialog: QDialog | None = None
        self.sale_processing = False
        self.sale_last_scanned_sku = ""
        self.sale_last_scanned_at = 0.0
        self.sale_discount_locked_to_client = False
        self.sale_locked_discount_percent = Decimal("0.00")
        self.sale_locked_discount_source = ""
        self.sale_manual_promo_authorized = False
        self.sale_manual_promo_authorized_percent = Decimal("0.00")

        self.quote_sku_input = QLineEdit()
        self.quote_qty_spin = QSpinBox()
        self.quote_folio_input = QLabel()
        self.quote_client_combo = QComboBox()
        self.quote_create_client_button = QPushButton("Nuevo cliente")
        self.quote_customer_input = QLineEdit()
        self.quote_phone_input = QLineEdit()
        self.quote_validity_input = QDateEdit()
        self.quote_note_input = QTextEdit()
        self.quote_add_button = QPushButton("Agregar al presupuesto")
        self.quote_save_button = QPushButton("Guardar presupuesto")
        self.quote_remove_button = QPushButton("Quitar linea")
        self.quote_clear_button = QPushButton("Vaciar presupuesto")
        self.quote_cancel_button = QPushButton("Cancelar presupuesto")
        self.quote_refresh_button = QPushButton("Refrescar")
        self.quote_status_label = QLabel("Sin presupuestos cargados.")
        self.quote_summary_label = QLabel("Presupuesto vacio.")
        self.quote_total_label = QLabel("$0.00")
        self.quote_total_meta_label = QLabel("Total estimado")
        self.quote_customer_label = QLabel("Sin detalle.")
        self.quote_meta_label = QLabel("")
        self.quote_notes_label = QLabel("")
        self.quote_cart_table = QTableWidget()
        self.quote_table = QTableWidget()
        self.quote_detail_table = QTableWidget()
        self.quote_search_input = QLineEdit()
        self.quote_state_combo = QComboBox()

        self.seed_button = QPushButton("Cargar datos iniciales")
        self.cash_cut_button = QPushButton("Corte de caja")
        self.cash_movement_button = QToolButton()
        self.logout_button = QPushButton("Cerrar sesion")
        self.active_cash_session_id: int | None = None

        self.inventory_variant_combo = QComboBox()
        self.inventory_adjustment_type_combo = QComboBox()
        self.inventory_adjustment_qty_spin = QSpinBox()
        self.inventory_reference_input = QLineEdit()
        self.inventory_note_input = QTextEdit()
        self.inventory_adjust_button = QPushButton("Aplicar ajuste")
        self.inventory_count_button = QPushButton("Conteo fisico")
        self.inventory_bulk_adjust_button = QPushButton("Ajuste masivo")
        self.inventory_bulk_price_button = QPushButton("Precio masivo")
        self.inventory_generate_qr_button = QPushButton("Generar QR de presentacion")
        self.inventory_print_label_button = QPushButton("Imprimir etiqueta")
        self.inventory_generate_all_qr_button = QPushButton("Generar QR de todas las presentaciones")
        self.inventory_permission_label = QLabel()
        self.qr_status_label = QLabel()
        self.qr_preview_label = QLabel("Preview QR")
        self.qr_preview_info_label = QLabel()
        self.inventory_overview_label = QLabel("Selecciona una presentacion")
        self.inventory_product_label = QLabel("Elige una fila para ver su ficha rapida.")
        self.inventory_status_badge = QLabel("Sin seleccion")
        self.inventory_stock_badge = QLabel("Sin stock")
        self.inventory_stock_hint_label = QLabel("")
        self.inventory_meta_label = QLabel("")
        self.inventory_last_movement_label = QLabel("")
        self.inventory_results_label = QLabel()
        self.inventory_active_filters_label = QLabel()
        self.inventory_search_input = QLineEdit()
        self.inventory_category_filter_combo = MultiSelectFilterButton("Categoria: todas")
        self.inventory_brand_filter_combo = MultiSelectFilterButton("Marca: todas")
        self.inventory_school_filter_combo = MultiSelectFilterButton("Escuela: todas")
        self.inventory_type_filter_combo = MultiSelectFilterButton("Tipo: todos")
        self.inventory_piece_filter_combo = MultiSelectFilterButton("Pieza: todas")
        self.inventory_size_filter_combo = MultiSelectFilterButton("Talla: todas")
        self.inventory_color_filter_combo = MultiSelectFilterButton("Color: todos")
        self.inventory_status_filter_combo = QComboBox()
        self.inventory_stock_filter_combo = QComboBox()
        self.inventory_qr_filter_combo = QComboBox()
        self.inventory_origin_filter_combo = QComboBox()
        self.inventory_duplicate_filter_combo = QComboBox()
        self.inventory_clear_filters_button = QPushButton("Limpiar filtros")
        self.inventory_out_counter = QLabel("Agotados: 0")
        self.inventory_low_counter = QLabel("Bajo stock: 0")
        self.inventory_qr_pending_counter = QLabel("Sin QR: 0")
        self.inventory_inactive_counter = QLabel("Inactivas: 0")
        self.inventory_new_button = QToolButton()
        self.inventory_edit_button = QToolButton()
        self.inventory_stock_button = QToolButton()
        self.inventory_more_button = QToolButton()
        self.inventory_table = QTableWidget()

        self.layaway_search_input = QLineEdit()
        self.layaway_state_combo = QComboBox()
        self.layaway_due_combo = QComboBox()
        self.layaway_create_button = QPushButton("Nuevo apartado")
        self.layaway_payment_button = QPushButton("Registrar abono")
        self.layaway_deliver_button = QPushButton("Entregar")
        self.layaway_cancel_button = QPushButton("Cancelar")
        self.layaway_receipt_button = QPushButton("Comprobante")
        self.layaway_sale_ticket_button = QPushButton("Ticket venta")
        self.layaway_whatsapp_button = QPushButton("WhatsApp")
        self.layaway_status_label = QLabel("Sin apartados cargados.")
        self.layaway_quick_alerts_label = QLabel("")
        self.layaway_table = QTableWidget()
        self.layaway_detail_table = QTableWidget()
        self.layaway_payments_table = QTableWidget()
        self.layaway_summary_label = QLabel("Selecciona un apartado")
        self.layaway_customer_label = QLabel("Sin detalle.")
        self.layaway_balance_label = QLabel("")
        self.layaway_commitment_label = QLabel("")
        self.layaway_due_status_label = QLabel("")
        self.layaway_notes_label = QLabel("")

        self.history_sku_input = QLineEdit()
        self.history_source_combo = QComboBox()
        self.history_entity_combo = QComboBox()
        self.history_type_combo = QComboBox()
        self.history_from_input = QDateEdit()
        self.history_to_input = QDateEdit()
        self.history_today_button = QPushButton("Hoy")
        self.history_clear_button = QPushButton("Limpiar")
        self.history_filter_button = QPushButton("Aplicar filtros")

        self.settings_backup_format_combo = QComboBox()
        self.settings_backup_table = QTableWidget()
        self.settings_backup_status_label = QLabel("Sin respaldos cargados.")
        self.settings_backup_location_label = QLabel(str(backup_output_dir()))
        self.settings_create_backup_button = QPushButton("Crear respaldo")
        self.settings_refresh_backups_button = QPushButton("Refrescar lista")
        self.settings_open_backups_button = QPushButton("Abrir carpeta")
        self.settings_restore_backup_button = QPushButton("Restaurar seleccionado")
        self.settings_users_button = QPushButton("Usuarios y acceso")
        self.settings_suppliers_button = QPushButton("Proveedores")
        self.settings_clients_button = QPushButton("Clientes")
        self.settings_marketing_button = QPushButton("Marketing y promociones")
        self.settings_whatsapp_button = QPushButton("WhatsApp y mensajes")
        self.settings_backup_button = QPushButton("Respaldo y restauracion")
        self.settings_cash_history_button = QPushButton("Historial de cortes")
        self.settings_business_button = QPushButton("Negocio e impresion")
        self.settings_users_table = QTableWidget()
        self.settings_users_status_label = QLabel("Sin usuarios cargados.")
        self.settings_create_user_button = QPushButton("Crear usuario")
        self.settings_edit_user_button = QPushButton("Editar usuario")
        self.settings_toggle_user_button = QPushButton("Activar / desactivar")
        self.settings_change_role_button = QPushButton("Cambiar rol")
        self.settings_change_password_button = QPushButton("Cambiar contrasena")
        self.settings_users_dialog: QDialog | None = None
        self.settings_suppliers_table = QTableWidget()
        self.settings_suppliers_status_label = QLabel("Sin proveedores cargados.")
        self.settings_suppliers_search_input = QLineEdit()
        self.settings_create_supplier_button = QPushButton("Crear proveedor")
        self.settings_update_supplier_button = QPushButton("Editar proveedor")
        self.settings_toggle_supplier_button = QPushButton("Activar / desactivar")
        self.settings_suppliers_dialog: QDialog | None = None
        self.settings_clients_table = QTableWidget()
        self.settings_clients_status_label = QLabel("Sin clientes cargados.")
        self.settings_clients_search_input = QLineEdit()
        self.settings_create_client_button = QPushButton("Crear cliente")
        self.settings_update_client_button = QPushButton("Editar cliente")
        self.settings_toggle_client_button = QPushButton("Activar / desactivar")
        self.settings_generate_client_qr_button = QPushButton("Generar QR")
        self.settings_client_whatsapp_button = QPushButton("WhatsApp")
        self.settings_clients_dialog: QDialog | None = None
        self.settings_backup_dialog: QDialog | None = None
        self.settings_cash_history_dialog: QDialog | None = None
        self.settings_business_dialog: QDialog | None = None
        self.settings_marketing_dialog: QDialog | None = None
        self.settings_whatsapp_dialog: QDialog | None = None
        self.settings_cash_history_table = QTableWidget()
        self.settings_cash_history_movements_table = QTableWidget()
        self.settings_cash_history_status_label = QLabel("Sin cortes cargados.")
        self.settings_cash_history_movements_label = QLabel("Selecciona un corte para ver sus movimientos.")
        self.settings_cash_history_state_combo = QComboBox()
        self.settings_cash_history_from_input = QDateEdit()
        self.settings_cash_history_to_input = QDateEdit()
        self.settings_cash_history_refresh_button = QPushButton("Refrescar")
        self.settings_cash_history_detail_button = QPushButton("Ver detalle")
        self.settings_cash_history_rows: dict[int, list[dict[str, object]]] = {}
        self.settings_business_name_input = QLineEdit()
        self.settings_business_logo_input = QLineEdit()
        self.settings_business_logo_pick_button = QPushButton("Seleccionar")
        self.settings_business_logo_clear_button = QPushButton("Limpiar")
        self.settings_business_logo_preview_label = QLabel("Sin logo")
        self.settings_business_demo_button = QPushButton("Ver credencial demo")
        self.settings_marketing_status_label = QLabel("Sin configuracion cargada.")
        self.settings_marketing_summary_label = QLabel("Sin resumen disponible.")
        self.dashboard_manual_promo_label = QLabel("Sin promociones manuales hoy.")
        self.settings_marketing_review_days_spin = QSpinBox()
        self.settings_marketing_leal_spend_spin = QDoubleSpinBox()
        self.settings_marketing_leal_purchase_count_spin = QSpinBox()
        self.settings_marketing_leal_purchase_sum_spin = QDoubleSpinBox()
        self.settings_marketing_discount_basico_spin = QDoubleSpinBox()
        self.settings_marketing_discount_leal_spin = QDoubleSpinBox()
        self.settings_marketing_discount_profesor_spin = QDoubleSpinBox()
        self.settings_marketing_discount_mayorista_spin = QDoubleSpinBox()
        self.settings_marketing_save_button = QPushButton("Guardar reglas")
        self.settings_marketing_recalculate_button = QPushButton("Recalcular niveles")
        self.settings_marketing_history_button = QPushButton("Historial")
        self.settings_business_phone_input = QLineEdit()
        self.settings_business_address_input = QTextEdit()
        self.settings_business_footer_input = QTextEdit()
        self.settings_business_transfer_bank_input = QLineEdit()
        self.settings_business_transfer_beneficiary_input = QLineEdit()
        self.settings_business_transfer_clabe_input = QLineEdit()
        self.settings_business_transfer_instructions_input = QTextEdit()
        self.settings_business_promo_code_input = QLineEdit()
        self.settings_whatsapp_layaway_reminder_input = QTextEdit()
        self.settings_whatsapp_layaway_liquidated_input = QTextEdit()
        self.settings_whatsapp_client_promotion_input = QTextEdit()
        self.settings_whatsapp_client_followup_input = QTextEdit()
        self.settings_whatsapp_client_greeting_input = QTextEdit()
        self.settings_whatsapp_status_label = QLabel("Sin configuracion cargada.")
        self.settings_whatsapp_save_button = QPushButton("Guardar plantillas")
        self.settings_whatsapp_preview_combo = QComboBox()
        self.settings_whatsapp_preview_button = QPushButton("Vista previa")
        self.settings_whatsapp_reset_button = QPushButton("Sugeridas")
        self.settings_whatsapp_preview_output = QTextEdit()
        self.settings_business_printer_combo = QComboBox()
        self.settings_business_copies_spin = QSpinBox()
        self.settings_business_status_label = QLabel("Sin configuracion cargada.")
        self.settings_business_save_button = QPushButton("Guardar configuracion")
        self.tabs: QTabWidget | None = None
        self.connection_button: QPushButton | None = None
        self.header_more_button: QToolButton | None = None
        self.cash_movement_menu: QMenu | None = None
        self.cash_reactivo_action: QAction | None = None
        self.cash_ingreso_action: QAction | None = None
        self.cash_retiro_action: QAction | None = None
        self.connection_action: QAction | None = None
        self.seed_action: QAction | None = None
        self.page_help_button: QPushButton | None = None
        self.refresh_button: QPushButton | None = None

        self._apply_styles()
        self._build_ui()
        self._configure_help_texts()
        self._configure_shortcuts()
        self.operational_check_timer = QTimer(self)
        self.operational_check_timer.setInterval(60_000)
        self.operational_check_timer.timeout.connect(self._run_operational_checks)
        self.operational_check_timer.start()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.session_label.setObjectName("heroPrimaryText")
        self.cash_session_label.setObjectName("heroMetaText")
        self.status_label.setObjectName("statusLine")
        self.metrics_label.setObjectName("subtleLine")
        self.analytics_label.setObjectName("analyticsLine")
        self.layaway_alerts_label.setObjectName("analyticsLine")

        top_actions = QHBoxLayout()
        top_actions.setSpacing(10)
        header_menu = QMenu(self)
        self.connection_action = header_menu.addAction("Verificar conexion")
        self.connection_action.triggered.connect(self._handle_test_connection)
        self.seed_action = header_menu.addAction("Cargar datos iniciales")
        self.seed_action.triggered.connect(self._handle_seed_data)
        self.header_more_button = QToolButton()
        self.header_more_button.setText("Mas")
        self.header_more_button.setObjectName("toolbarSoftButton")
        self.header_more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.header_more_button.setMenu(header_menu)
        self.page_help_button = QPushButton("?")
        self.page_help_button.setObjectName("toolbarSoftButton")
        self.page_help_button.setToolTip("Ayuda de la pestaña actual")
        self.page_help_button.clicked.connect(self._open_current_tab_help)
        self.cash_cut_button.setObjectName("toolbarActionButton")
        self.cash_cut_button.clicked.connect(self._handle_cash_cut)
        self.cash_movement_menu = QMenu(self)
        self.cash_opening_correction_action = self.cash_movement_menu.addAction("Corregir apertura")
        self.cash_reactivo_action = self.cash_movement_menu.addAction("Ajustar reactivo")
        self.cash_ingreso_action = self.cash_movement_menu.addAction("Ingreso")
        self.cash_retiro_action = self.cash_movement_menu.addAction("Retiro")
        self.cash_opening_correction_action.triggered.connect(self._handle_correct_cash_opening)
        self.cash_reactivo_action.triggered.connect(
            lambda: self._handle_cash_movement(TipoMovimientoCaja.REACTIVO)
        )
        self.cash_ingreso_action.triggered.connect(
            lambda: self._handle_cash_movement(TipoMovimientoCaja.INGRESO)
        )
        self.cash_retiro_action.triggered.connect(
            lambda: self._handle_cash_movement(TipoMovimientoCaja.RETIRO)
        )
        self.cash_movement_button.setText("Movimientos")
        self.cash_movement_button.setObjectName("toolbarSoftButton")
        self.cash_movement_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.cash_movement_button.setMenu(self.cash_movement_menu)
        self.logout_button.setText("Salir")
        self.logout_button.setObjectName("toolbarDangerButton")
        self.logout_button.clicked.connect(self._handle_logout)
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setObjectName("toolbarAccentButton")
        self.refresh_button.setToolTip("Refrescar datos")
        self.refresh_button.clicked.connect(self.refresh_all)
        top_actions.addWidget(self.page_help_button)
        top_actions.addWidget(self.header_more_button)
        top_actions.addWidget(self.cash_cut_button)
        top_actions.addWidget(self.cash_movement_button)
        top_actions.addWidget(self.logout_button)
        top_actions.addWidget(self.refresh_button)
        top_actions.addStretch()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_tab_scroll(self._build_dashboard_tab()), "Resumen")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_cashier_tab()), "Caja")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_quotes_tab()), "Presupuestos")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_layaway_tab()), "Apartados")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_catalog_tab()), "Catalogo")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_inventory_tab()), "Inventario")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_history_tab()), "Historial inventarios")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_analytics_tab()), "Analitica")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_settings_tab()), "Configuracion")

        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QHBoxLayout()
        hero_layout.setContentsMargins(12, 10, 12, 10)
        hero_layout.setSpacing(10)
        hero_info_card = QFrame()
        hero_info_card.setObjectName("heroInfoCard")
        hero_info_layout = QVBoxLayout()
        hero_info_layout.setContentsMargins(12, 8, 12, 8)
        hero_info_layout.setSpacing(4)
        hero_info_layout.addWidget(self.session_label)
        hero_info_layout.addWidget(self.cash_session_label)
        hero_info_card.setLayout(hero_info_layout)
        hero_layout.addWidget(hero_info_card, 1)
        hero_layout.addLayout(top_actions, 0)
        hero.setLayout(hero_layout)

        layout.addWidget(hero)
        layout.addWidget(self.tabs)
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _configure_help_texts(self) -> None:
        help_map = {
            self.category_button: "Abre una ventana para crear una categoria nueva.",
            self.brand_button: "Abre una ventana para crear una marca nueva.",
            self.inventory_category_button: "Abre una ventana para crear una categoria nueva desde Inventario.",
            self.inventory_brand_button: "Abre una ventana para crear una marca nueva desde Inventario.",
            self.product_button: "Abre una ventana para registrar un producto nuevo y, si quieres, su primera presentacion.",
            self.variant_button: "Abre una ventana para crear una presentacion nueva con talla, color, precio y SKU.",
            self.update_product_button: "Edita los datos generales del producto seleccionado.",
            self.update_variant_button: "Edita la presentacion seleccionada, incluyendo precio, SKU, talla y color.",
            self.toggle_product_button: "Activa o desactiva el producto seleccionado y sus presentaciones.",
            self.toggle_variant_button: "Activa o desactiva solo la presentacion seleccionada.",
            self.delete_product_button: "Elimina el producto si no tiene stock ni historial operativo.",
            self.delete_variant_button: "Elimina la presentacion si no tiene stock ni historial operativo.",
            self.purchase_button: "Registra entrada de mercancia para la presentacion seleccionada.",
            self.inventory_adjust_button: "Corrige el stock final de la presentacion seleccionada para conteos o diferencias.",
            self.inventory_count_button: "Abre un conteo fisico para capturar existencias y aplicar diferencias en bloque.",
            self.inventory_bulk_adjust_button: "Aplica un lote de ajustes masivos con preview, validacion y auditoria por movimiento.",
            self.inventory_bulk_price_button: "Actualiza precios por lote con preview, aumentos, descuentos y auditoria de catalogo.",
            self.inventory_generate_qr_button: "Genera el codigo QR de la presentacion seleccionada.",
            self.inventory_print_label_button: "Abre la impresion de etiquetas para la presentacion seleccionada. La logica completa se integrara en la siguiente fase.",
            self.inventory_generate_all_qr_button: "Genera codigos QR para todas las presentaciones activas.",
            self.inventory_new_button: "Crea catalogo base, productos o presentaciones nuevas desde un solo menu.",
            self.inventory_edit_button: "Edita el producto o la presentacion seleccionada.",
            self.inventory_stock_button: "Abre acciones de stock como entrada, conteo fisico y correccion.",
            self.inventory_more_button: "Abre acciones poco frecuentes como eliminar y generar QRs masivos.",
            self.layaway_create_button: "Crea un apartado nuevo y reserva stock disponible.",
            self.layaway_payment_button: "Registra un abono sobre el apartado seleccionado.",
            self.layaway_deliver_button: "Marca como entregado un apartado ya liquidado.",
            self.layaway_cancel_button: "Cancela el apartado seleccionado y libera el stock reservado.",
            self.layaway_receipt_button: "Abre un comprobante del apartado seleccionado para revisar o imprimir.",
            self.layaway_sale_ticket_button: "Abre el ticket de la venta generada al entregar el apartado.",
            self.layaway_whatsapp_button: "Abre WhatsApp con un recordatorio prellenado para el cliente del apartado.",
            self.sale_layaway_button: "Convierte el carrito actual en un apartado y reserva el stock de sus lineas.",
            self.quote_add_button: "Agrega el SKU capturado al presupuesto actual sin afectar inventario.",
            self.quote_create_client_button: "Crea un cliente rapido desde Presupuestos usando solo nombre y telefono.",
            self.quote_save_button: "Guarda el presupuesto actual con folio, cliente opcional y vigencia.",
            self.quote_remove_button: "Quita la linea seleccionada del presupuesto en armado.",
            self.quote_clear_button: "Vacía por completo el presupuesto actual.",
            self.quote_cancel_button: "Marca como cancelado el presupuesto seleccionado sin tocar inventario.",
            self.quote_refresh_button: "Vuelve a leer los presupuestos recientes con los filtros actuales.",
            self.sale_add_button: "Agrega el SKU capturado al carrito de venta.",
            self.sale_button: "Confirma la venta de todos los productos del carrito.",
            self.sale_recent_button: "Abre las ventas recientes en una ventana separada para consultar o cancelar.",
            self.sale_ticket_button: "Abre una vista de ticket para la venta seleccionada.",
            self.cancel_button: "Cancela la venta seleccionada y revierte el inventario. Solo ADMIN.",
            self.sale_remove_button: "Quita la linea seleccionada del carrito.",
            self.sale_clear_button: "Vacía por completo el carrito actual.",
            self.seed_button: "Carga datos demo para pruebas del sistema. Solo ADMIN.",
            self.history_filter_button: "Aplica los filtros del historial de movimientos.",
            self.history_today_button: "Filtra movimientos del dia actual.",
            self.history_clear_button: "Limpia las fechas y el resto de filtros del historial.",
            self.settings_create_backup_button: "Genera un respaldo manual nuevo de la base de datos.",
            self.settings_refresh_backups_button: "Vuelve a leer la carpeta de respaldos disponibles.",
            self.settings_open_backups_button: "Abre la carpeta donde se guardan los respaldos.",
            self.settings_restore_backup_button: "Restaura el respaldo .dump seleccionado sobre la base actual.",
            self.settings_users_button: "Abre la configuracion de usuarios y acceso.",
            self.settings_marketing_button: "Abre la configuracion de marketing, promociones y reglas de lealtad.",
            self.settings_backup_button: "Abre la configuracion de respaldo y restauracion.",
            self.settings_cash_history_button: "Abre el historial de aperturas, cierres y diferencias de caja.",
            self.settings_cash_history_detail_button: "Abre el detalle del corte seleccionado, incluyendo observaciones.",
            self.settings_business_button: "Abre la configuracion de negocio e impresion.",
            self.settings_marketing_save_button: "Guarda reglas automaticas de lealtad y descuentos por nivel.",
            self.settings_marketing_recalculate_button: "Recalcula los niveles de todos los clientes usando las reglas vigentes.",
            self.settings_marketing_history_button: "Abre el historial de cambios en reglas y descuentos de marketing.",
            self.cash_cut_button: "Abre el corte de caja actual o permite cerrar la caja abierta.",
            self.cash_movement_button: "Registra movimientos manuales de caja: Corregir apertura, Ajustar reactivo, Ingreso o Retiro.",
            self.logout_button: "Cierra la sesion actual y permite entrar con otro usuario.",
            self.settings_create_user_button: "Crea un usuario nuevo con rol y contrasena inicial.",
            self.settings_toggle_user_button: "Activa o desactiva el usuario seleccionado.",
            self.settings_change_role_button: "Cambia el rol del usuario seleccionado.",
            self.settings_change_password_button: "Cambia la contrasena del usuario seleccionado.",
            self.settings_business_save_button: "Guarda los datos del negocio y la configuracion de impresion.",
        }
        for widget, text in help_map.items():
            widget.setToolTip(text)
            widget.setStatusTip(text)
            widget.setWhatsThis(text)

        self.catalog_table.setToolTip("Consulta productos disponibles, precios, stock y estado actual.")
        self.catalog_layaway_filter_combo.setToolTip(
            "Filtra la lista para mostrar solo presentaciones con piezas comprometidas por apartados."
        )
        self.catalog_search_input.setToolTip(
            "Acepta busqueda libre y prefijos como sku:, escuela:, tipo:, pieza:, producto:, legacy:, talla:, color:."
        )
        self.catalog_clear_filters_button.setToolTip("Limpia todos los filtros del catalogo y muestra nuevamente todo el catalogo.")
        self.inventory_search_input.setToolTip(
            "Acepta busqueda libre y prefijos como sku:, escuela:, tipo:, pieza:, producto:, legacy:, talla:, color:."
        )
        self.inventory_clear_filters_button.setToolTip("Limpia todos los filtros del inventario y muestra nuevamente todas las presentaciones.")
        self.inventory_table.setToolTip("Selecciona una presentacion para gestionar inventario, precio, QR o estado.")
        self.layaway_table.setToolTip("Consulta apartados, saldo pendiente y fechas compromiso.")
        self.layaway_due_combo.setToolTip("Filtra apartados por vencimiento.")
        self.recent_sales_table.setToolTip("Historial reciente de ventas registradas en el sistema.")
        self.sale_payment_combo.setToolTip("Selecciona el metodo de pago de la venta actual.")
        self.sale_discount_combo.setToolTip("Aplica un descuento porcentual predefinido a la venta actual.")
        self.sale_client_combo.setToolTip("Asocia un cliente a la venta si aplica. Puedes dejar Mostrador para venta general.")
        self.movements_table.setToolTip("Historial de movimientos de inventario con filtros por fecha, SKU y tipo.")

    def _create_page_help_button(self, page_key: str) -> QPushButton:
        button = QPushButton("Ayuda")
        button.setObjectName("toolbarGhostButton")
        button.clicked.connect(lambda: self._open_page_help(page_key))
        return button

    def _open_current_tab_help(self) -> None:
        if self.tabs is None:
            self._open_page_help("dashboard")
            return
        current_label = self.tabs.tabText(self.tabs.currentIndex()).strip().lower()
        page_key = {
            "resumen": "dashboard",
            "caja": "cashier",
            "apartados": "layaway",
            "catalogo": "products",
            "inventario": "inventory",
            "historial inventarios": "history",
            "analitica": "analytics",
            "configuracion": "settings",
        }.get(current_label, "dashboard")
        self._open_page_help(page_key)

    def _open_page_help(self, page_key: str) -> None:
        page_help = {
            "dashboard": (
                "Ayuda de resumen",
                [
                    "Muestra el estado general del sistema y los indicadores principales.",
                    "Si eres cajero, esta vista se limita a datos utiles para operacion diaria.",
                    "Si eres ADMIN, tambien veras alertas y contexto operativo adicional.",
                ],
            ),
            "products": (
                "Ayuda de productos",
                [
                    "Esta pestaña es de consulta rapida para caja.",
                    "Puedes buscar por SKU, marca, producto, talla o color y filtrar por categoria, marca, estado o apartados.",
                    "Las altas, cambios de precio y existencias se administran desde Inventario.",
                ],
            ),
            "cashier": (
                "Ayuda de caja",
                [
                    "Captura o escanea el SKU y presiona Enter para agregarlo al carrito.",
                    "Elige metodo de pago y cobra cuando el carrito este listo.",
                    "Desde aqui tambien puedes convertir el carrito en apartado.",
                ],
            ),
            "inventory": (
                "Ayuda de inventario",
                [
                    "Selecciona una presentacion en la tabla para ver su ficha y sus acciones.",
                    "Usa los menus Nuevo, Editar, Stock y Mas para administrar catalogo, existencias y QR.",
                    "El panel lateral muestra estado, stock, ultimo movimiento y vista previa del QR.",
                ],
            ),
            "layaway": (
                "Ayuda de apartados",
                [
                    "Crea apartados, registra abonos, entrega apartados liquidados o cancela apartados activos.",
                    "El stock se reserva al crear el apartado y se libera si lo cancelas.",
                    "Usa los filtros para localizar apartados por cliente, estado o vencimiento.",
                ],
            ),
            "analytics": (
                "Ayuda de analitica",
                [
                    "Muestra productos mas vendidos e ingreso acumulado por ventas confirmadas.",
                    "Sirve como referencia rapida; no sustituye reportes detallados.",
                ],
            ),
            "history": (
                "Ayuda de historial",
                [
                    "Consulta movimientos de inventario por SKU, tipo o rango de fechas.",
                    "Usa Hoy o Limpiar para navegar mas rapido entre periodos.",
                ],
            ),
            "settings": (
                "Ayuda de configuracion",
                [
                    "Aqui se concentran los modulos administrativos del sistema.",
                    "Usuarios y acceso controla cuentas y roles.",
                    "Proveedores centraliza contactos para compras y reposicion.",
                    "Clientes prepara la base para ventas identificadas, apartados y fidelizacion futura.",
                    "WhatsApp y mensajes centraliza las plantillas para recordatorios y promociones.",
                    "Respaldo y restauracion protege la base de datos, y Negocio e impresion define ticket y datos de cobro.",
                ],
            ),
        }
        title, lines = page_help.get(page_key, ("Ayuda", ["Sin informacion disponible."]))
        dialog, layout = self._create_modal_dialog(title, width=520)
        body = QLabel("\n".join(f"• {line}" for line in lines))
        body.setWordWrap(True)
        body.setObjectName("subtleLine")
        close_button = QPushButton("Cerrar")
        close_button.setObjectName("toolbarPrimaryButton")
        close_button.clicked.connect(dialog.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_button)
        layout.addWidget(body)
        layout.addLayout(row)
        dialog.exec()

    def _configure_shortcuts(self) -> None:
        focus_sku_shortcut = QShortcut(QKeySequence("F8"), self)
        focus_sku_shortcut.activated.connect(self._focus_sale_capture)
        sell_shortcut = QShortcut(QKeySequence("F2"), self)
        sell_shortcut.activated.connect(self._handle_sale)
        recent_shortcut = QShortcut(QKeySequence("F6"), self)
        recent_shortcut.activated.connect(self._open_recent_sales_dialog)
        remove_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        remove_shortcut.activated.connect(self._handle_remove_sale_item)
        clear_capture_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        clear_capture_shortcut.activated.connect(self._clear_sale_capture)

    def _focus_sale_capture(self) -> None:
        self.sale_sku_input.setFocus()
        self.sale_sku_input.selectAll()

    def _clear_sale_capture(self) -> None:
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self.sale_last_scanned_sku = ""
        self.sale_last_scanned_at = 0.0
        self._set_sale_feedback("Captura limpia. Puedes escribir o escanear.", "neutral", auto_clear_ms=1200)

    def _apply_role_navigation(self) -> None:
        if self.tabs is None:
            return

        is_admin = self.current_role == RolUsuario.ADMIN
        can_manage_layaways = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        visible_by_index = {
            0: True,      # Resumen
            1: True,      # Caja
            2: True,      # Presupuestos
            3: can_manage_layaways,  # Apartados
            4: True,      # Catalogo
            5: is_admin,  # Inventario
            6: is_admin,  # Historial inventarios
            7: is_admin,  # Analitica
            8: is_admin,  # Configuracion
        }
        for index, is_visible in visible_by_index.items():
            self.tabs.setTabVisible(index, is_visible)

        current_index = self.tabs.currentIndex()
        if not visible_by_index.get(current_index, False):
            self.tabs.setCurrentIndex(1 if not is_admin else 0)

    def _focus_default_tab_for_role(self) -> None:
        if self.tabs is None:
            return
        self.tabs.setCurrentIndex(0 if self.current_role == RolUsuario.ADMIN else 1)
        self.tabs.update()
        self.tabs.repaint()

    @staticmethod
    def _is_stale_cash_session(active_session: SesionCaja) -> bool:
        if active_session.abierta_at is None:
            return False
        current_date = (
            datetime.now(active_session.abierta_at.tzinfo).date()
            if active_session.abierta_at.tzinfo is not None
            else date.today()
        )
        return active_session.abierta_at.date() < current_date

    def _ensure_cash_session_current_day_for_operation(self, action_label: str) -> bool:
        if not self.cash_session_requires_cut:
            return True
        QMessageBox.warning(
            self,
            "Corte pendiente",
            (
                "Hay una caja abierta de un dia anterior sin corte.\n\n"
                f"Debes realizar el corte antes de {action_label.lower()}."
            ),
        )
        return False

    def _run_operational_checks(self) -> None:
        if self.active_cash_session_id is None or self.cash_session_requires_cut:
            return
        try:
            with get_session() as session:
                active_session = session.get(SesionCaja, self.active_cash_session_id)
                if active_session is None or active_session.cerrada_at is not None:
                    return
                current_dt = (
                    datetime.now(active_session.abierta_at.tzinfo)
                    if active_session.abierta_at is not None and active_session.abierta_at.tzinfo is not None
                    else datetime.now()
                )
                reminder_key = (active_session.id, current_dt.date())
                if current_dt.hour >= 17 and self.cash_session_cut_reminder_key != reminder_key:
                    self.cash_session_cut_reminder_key = reminder_key
                    QMessageBox.information(
                        self,
                        "Recordatorio de corte",
                        "Son las 5:00 PM o mas tarde y la caja sigue abierta. Si ya termino la operacion del dia, realiza el corte.",
                    )
        except Exception:
            return

    def _build_dashboard_tab(self) -> QWidget:
        return build_dashboard_tab(self)

    def _wrap_tab_scroll(self, widget: QWidget) -> QWidget:
        if isinstance(widget, QScrollArea):
            return widget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def _build_catalog_tab(self) -> QWidget:
        return build_products_tab(self)

    def _build_cashier_tab(self) -> QWidget:
        return build_cashier_tab(self)

    def _build_quotes_tab(self) -> QWidget:
        return build_quotes_tab(self)

    def _build_inventory_tab(self) -> QWidget:
        return build_inventory_tab(self)

    def _build_analytics_tab(self) -> QWidget:
        return build_analytics_tab(self)

    def _build_layaway_tab(self) -> QWidget:
        return build_layaway_tab(self)

    def _build_history_tab(self) -> QWidget:
        return build_history_tab(self)

    def _build_settings_tab(self) -> QWidget:
        return build_settings_tab(self)

    def _refresh_settings_backups(self) -> None:
        backup_dir = backup_output_dir()
        self.settings_backup_location_label.setText(f"Carpeta de respaldos: {backup_dir}")
        try:
            backups = list_backups(backup_dir)
        except Exception as exc:  # noqa: BLE001
            self.settings_backup_status_label.setText(f"No se pudo leer la carpeta de respaldos: {exc}")
            self.settings_backup_table.setRowCount(0)
            return

        self.settings_backup_table.setRowCount(len(backups))
        for row_index, backup in enumerate(backups):
            values = [
                backup.path.name,
                "Dump" if backup.dump_format == "custom" else "SQL",
                backup.modified_at.strftime("%Y-%m-%d %H:%M"),
                format_size(backup.size_bytes),
                "Si" if backup.dump_format == "custom" else "No",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(backup.path))
                self.settings_backup_table.setItem(row_index, column_index, item)
        self.settings_backup_table.resizeColumnsToContents()
        if backups:
            self.settings_backup_status_label.setText(
                f"Respaldos disponibles: {len(backups)} | Ultimo: {backups[0].path.name}"
            )
        else:
            self.settings_backup_status_label.setText("No hay respaldos todavia en la carpeta configurada.")

    def _open_users_settings_dialog(self) -> None:
        if self.settings_users_dialog is None:
            self.settings_users_dialog = build_users_settings_dialog(self)

        self._refresh_settings_users()
        self.settings_users_dialog.show()
        self.settings_users_dialog.raise_()
        self.settings_users_dialog.activateWindow()

    def _open_suppliers_settings_dialog(self) -> None:
        if self.settings_suppliers_dialog is None:
            self.settings_suppliers_dialog = build_suppliers_settings_dialog(self)

        self._refresh_settings_suppliers()
        self.settings_suppliers_dialog.show()
        self.settings_suppliers_dialog.raise_()
        self.settings_suppliers_dialog.activateWindow()

    def _open_clients_settings_dialog(self) -> None:
        if self.settings_clients_dialog is None:
            self.settings_clients_dialog = build_clients_settings_dialog(self)

        self._refresh_settings_clients()
        self.settings_clients_dialog.show()
        self.settings_clients_dialog.raise_()
        self.settings_clients_dialog.activateWindow()

    def _open_business_settings_dialog(self) -> None:
        if self.settings_business_dialog is None:
            self.settings_business_dialog = build_business_settings_dialog(self)

        self._refresh_business_settings_form()
        self.settings_business_dialog.show()
        self.settings_business_dialog.raise_()
        self.settings_business_dialog.activateWindow()

    def _open_marketing_settings_dialog(self) -> None:
        if self.settings_marketing_dialog is None:
            self.settings_marketing_dialog = build_marketing_settings_dialog(self)

        self._refresh_business_settings_form()
        self.settings_marketing_dialog.show()
        self.settings_marketing_dialog.raise_()
        self.settings_marketing_dialog.activateWindow()

    def _open_cash_history_settings_dialog(self) -> None:
        if self.settings_cash_history_dialog is None:
            self.settings_cash_history_dialog = build_cash_history_settings_dialog(self)
            today = QDate.currentDate()
            self.settings_cash_history_to_input.setDate(today)
            self.settings_cash_history_from_input.setDate(today.addDays(-30))

        self._refresh_settings_cash_history()
        self.settings_cash_history_dialog.show()
        self.settings_cash_history_dialog.raise_()
        self.settings_cash_history_dialog.activateWindow()

    def _open_whatsapp_settings_dialog(self) -> None:
        if self.settings_whatsapp_dialog is None:
            self.settings_whatsapp_dialog = build_whatsapp_settings_dialog(self)

        self._refresh_business_settings_form()
        self.settings_whatsapp_dialog.show()
        self.settings_whatsapp_dialog.raise_()
        self.settings_whatsapp_dialog.activateWindow()

    def _open_backup_settings_dialog(self) -> None:
        if self.settings_backup_dialog is None:
            self.settings_backup_dialog = build_backup_settings_dialog(self)

        self._refresh_settings_backups()
        self.settings_backup_dialog.show()
        self.settings_backup_dialog.raise_()
        self.settings_backup_dialog.activateWindow()

    def _refresh_settings_cash_history(self) -> None:
        estado = self.settings_cash_history_state_combo.currentData() or "todas"
        fecha_desde = self.settings_cash_history_from_input.date().toPyDate()
        fecha_hasta = self.settings_cash_history_to_input.date().toPyDate()
        try:
            with get_session() as session:
                cash_sessions = CajaService.listar_sesiones(
                    session,
                    str(estado),
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                )
        except Exception as exc:
            self.settings_cash_history_status_label.setText(f"No se pudo cargar el historial de caja: {exc}")
            return

        self.settings_cash_history_rows = {}
        self.settings_cash_history_table.setRowCount(len(cash_sessions))
        abiertas = 0
        cerradas = 0
        for row_index, cash_session in enumerate(cash_sessions):
            is_closed = cash_session.cerrada_at is not None
            if is_closed:
                cerradas += 1
            else:
                abiertas += 1
            opened_by = cash_session.abierta_por.nombre_completo if cash_session.abierta_por is not None else "-"
            closed_by = cash_session.cerrada_por.nombre_completo if cash_session.cerrada_por is not None else "-"
            self.settings_cash_history_rows[cash_session.id] = [
                {
                    "fecha": movement.created_at.strftime("%Y-%m-%d %H:%M") if movement.created_at else "-",
                    "tipo": movement.tipo.value,
                    "monto": Decimal(movement.monto).quantize(Decimal("0.01")),
                    "usuario": movement.usuario.nombre_completo if movement.usuario is not None else "-",
                    "concepto": movement.concepto or "",
                }
                for movement in cash_session.movimientos
            ]
            values = [
                cash_session.id,
                "Cerrada" if is_closed else "Abierta",
                cash_session.abierta_at.strftime("%Y-%m-%d %H:%M") if cash_session.abierta_at else "",
                opened_by,
                f"${Decimal(cash_session.monto_apertura or 0).quantize(Decimal('0.01'))}",
                cash_session.cerrada_at.strftime("%Y-%m-%d %H:%M") if cash_session.cerrada_at else "-",
                closed_by,
                f"${Decimal(cash_session.monto_esperado_cierre or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
                f"${Decimal(cash_session.monto_cierre_declarado or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
                f"${Decimal(cash_session.diferencia_cierre or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, cash_session.id)
                if column_index == 1:
                    _set_table_badge_style(item, "muted" if is_closed else "positive")
                elif column_index == 9 and is_closed:
                    difference = Decimal(cash_session.diferencia_cierre or 0).quantize(Decimal("0.01"))
                    if difference == Decimal("0.00"):
                        _set_table_badge_style(item, "positive")
                    elif difference > Decimal("0.00"):
                        _set_table_badge_style(item, "warning")
                    else:
                        _set_table_badge_style(item, "danger")
                self.settings_cash_history_table.setItem(row_index, column_index, item)
        self.settings_cash_history_table.resizeColumnsToContents()
        self.settings_cash_history_status_label.setText(
            f"Cortes registrados: {len(cash_sessions)} | Abiertas: {abiertas} | Cerradas: {cerradas} | Rango: {fecha_desde.isoformat()} a {fecha_hasta.isoformat()}"
        )
        if cash_sessions:
            self.settings_cash_history_table.setCurrentCell(0, 0)
            self._refresh_selected_cash_history_movements()
        else:
            self._refresh_selected_cash_history_movements()

    def _refresh_selected_cash_history_movements(self) -> None:
        cash_session_id = self._selected_cash_history_id()
        movements = self.settings_cash_history_rows.get(cash_session_id or -1, [])
        self.settings_cash_history_movements_table.setRowCount(len(movements))
        for row_index, movement in enumerate(movements):
            values = [
                movement["fecha"],
                movement["tipo"],
                f"${movement['monto']}",
                movement["usuario"],
                movement["concepto"] or "-",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 1:
                    tone = {
                        "REACTIVO": "positive",
                        "INGRESO": "warning",
                        "RETIRO": "danger",
                    }.get(str(movement["tipo"]), "muted")
                    _set_table_badge_style(item, tone)
                self.settings_cash_history_movements_table.setItem(row_index, column_index, item)
        self.settings_cash_history_movements_table.resizeColumnsToContents()
        if cash_session_id is None:
            self.settings_cash_history_movements_label.setText("Selecciona un corte para ver sus movimientos.")
        elif movements:
            self.settings_cash_history_movements_label.setText(
                f"Movimientos registrados en la sesion #{cash_session_id}: {len(movements)}"
            )
        else:
            self.settings_cash_history_movements_label.setText(
                f"La sesion #{cash_session_id} no tiene movimientos manuales registrados."
            )

    def _selected_cash_history_id(self) -> int | None:
        row = self.settings_cash_history_table.currentRow()
        if row < 0:
            return None
        item = self.settings_cash_history_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    @staticmethod
    def _extract_opening_corrections(opening_note: str) -> list[str]:
        if not opening_note:
            return []
        return [
            token.strip()
            for token in opening_note.split(" | ")
            if token.strip().startswith("Correccion de apertura ")
        ]

    def _handle_view_cash_history_detail(self) -> None:
        cash_session_id = self._selected_cash_history_id()
        if cash_session_id is None:
            QMessageBox.information(self, "Selecciona un corte", "Selecciona primero un corte de caja.")
            return
        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, cash_session_id)
                if cash_session is None:
                    raise ValueError("No se encontro la sesion de caja seleccionada.")
                resumen = CajaService.resumir_sesion(session, cash_session)
                opened_by = cash_session.abierta_por.nombre_completo if cash_session.abierta_por is not None else "-"
                closed_by = cash_session.cerrada_por.nombre_completo if cash_session.cerrada_por is not None else "-"
                movement_rows = []
                for movement in cash_session.movimientos:
                    movement_rows.append(
                        {
                            "fecha": movement.created_at.strftime("%Y-%m-%d %H:%M") if movement.created_at else "-",
                            "tipo": movement.tipo.value,
                            "monto": Decimal(movement.monto).quantize(Decimal("0.01")),
                            "usuario": movement.usuario.nombre_completo if movement.usuario is not None else "-",
                            "concepto": movement.concepto or "",
                        }
                    )
                detail = {
                    "id": cash_session.id,
                    "status": "Cerrada" if cash_session.cerrada_at else "Abierta",
                    "opened_at": cash_session.abierta_at.strftime("%Y-%m-%d %H:%M") if cash_session.abierta_at else "-",
                    "opened_by": opened_by,
                    "opening_amount": Decimal(cash_session.monto_apertura or 0).quantize(Decimal("0.01")),
                    "opening_note": cash_session.observacion_apertura or "Sin observacion",
                    "opening_corrections": self._extract_opening_corrections(cash_session.observacion_apertura or ""),
                    "closed_at": cash_session.cerrada_at.strftime("%Y-%m-%d %H:%M") if cash_session.cerrada_at else "-",
                    "closed_by": closed_by,
                    "expected_amount": Decimal(cash_session.monto_esperado_cierre or 0).quantize(Decimal("0.01")),
                    "declared_amount": Decimal(cash_session.monto_cierre_declarado or 0).quantize(Decimal("0.01")),
                    "difference": Decimal(cash_session.diferencia_cierre or 0).quantize(Decimal("0.01")),
                    "closing_note": cash_session.observacion_cierre or "Sin observacion",
                    "is_closed": cash_session.cerrada_at is not None,
                    "cash_sales_count": resumen.ventas_efectivo_count,
                    "cash_sales_total": resumen.efectivo_ventas,
                    "cash_payments_count": resumen.abonos_efectivo_count,
                    "cash_payments_total": resumen.efectivo_abonos,
                    "reactivo_count": resumen.reactivo_count,
                    "reactivo_total": resumen.reactivo_total,
                    "ingresos_count": resumen.ingresos_count,
                    "ingresos_total": resumen.ingresos_total,
                    "retiros_count": resumen.retiros_count,
                    "retiros_total": resumen.retiros_total,
                    "movements": movement_rows,
                }
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo abrir el detalle", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Detalle del corte #{detail['id']}")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        status_row = QHBoxLayout()
        title = QLabel(f"Corte #{detail['id']}")
        title.setObjectName("inventoryTitle")
        status_badge = QLabel(str(detail["status"]))
        status_badge.setObjectName("inventoryStatusBadge")
        self._set_badge_state(status_badge, str(detail["status"]), "muted" if detail["is_closed"] else "positive")
        status_row.addWidget(title)
        status_row.addStretch()
        status_row.addWidget(status_badge)

        open_box = QGroupBox("Apertura")
        open_box.setObjectName("infoCard")
        open_form = QFormLayout()
        open_form.addRow("Fecha", QLabel(str(detail["opened_at"])))
        open_form.addRow("Usuario", QLabel(str(detail["opened_by"])))
        open_form.addRow("Reactivo inicial", QLabel(f"${detail['opening_amount']}"))
        opening_note = QLabel(str(detail["opening_note"]))
        opening_note.setWordWrap(True)
        opening_note.setObjectName("subtleLine")
        open_form.addRow("Observacion", opening_note)
        open_box.setLayout(open_form)

        layout.addLayout(status_row)
        layout.addWidget(open_box)

        if detail["opening_corrections"]:
            corrections_box = QGroupBox("Correcciones de apertura")
            corrections_box.setObjectName("infoCard")
            corrections_layout = QVBoxLayout()
            corrections_layout.setSpacing(8)
            for correction in detail["opening_corrections"]:
                correction_row = QFrame()
                correction_row.setObjectName("infoCard")
                correction_row_layout = QHBoxLayout()
                correction_row_layout.setContentsMargins(10, 8, 10, 8)
                correction_row_layout.setSpacing(8)
                correction_badge = QLabel("CORRECCION")
                correction_badge.setObjectName("inventoryStatusBadge")
                self._set_badge_state(correction_badge, "CORRECCION", "warning")
                correction_label = QLabel(correction)
                correction_label.setWordWrap(True)
                correction_label.setObjectName("analyticsLine")
                correction_row_layout.addWidget(correction_badge, 0, Qt.AlignmentFlag.AlignTop)
                correction_row_layout.addWidget(correction_label, 1)
                correction_row.setLayout(correction_row_layout)
                corrections_layout.addWidget(correction_row)
            corrections_box.setLayout(corrections_layout)
            layout.addWidget(corrections_box)

        flow_box = QGroupBox("Movimiento de efectivo")
        flow_box.setObjectName("infoCard")
        flow_form = QFormLayout()
        flow_form.addRow("Reactivos extra", QLabel(f"{detail['reactivo_count']} | ${detail['reactivo_total']}"))
        flow_form.addRow("Ingresos manuales", QLabel(f"{detail['ingresos_count']} | ${detail['ingresos_total']}"))
        flow_form.addRow("Retiros manuales", QLabel(f"{detail['retiros_count']} | ${detail['retiros_total']}"))
        flow_form.addRow("Ventas con efectivo", QLabel(f"{detail['cash_sales_count']}"))
        flow_form.addRow("Efectivo por ventas", QLabel(f"${detail['cash_sales_total']}"))
        flow_form.addRow("Abonos con efectivo", QLabel(f"{detail['cash_payments_count']}"))
        flow_form.addRow("Efectivo por abonos", QLabel(f"${detail['cash_payments_total']}"))
        flow_box.setLayout(flow_form)
        layout.addWidget(flow_box)

        movements_box = QGroupBox("Movimientos manuales")
        movements_box.setObjectName("infoCard")
        movements_layout = QVBoxLayout()
        movements_table = QTableWidget()
        movements_table.setColumnCount(5)
        movements_table.setHorizontalHeaderLabels(["Fecha", "Tipo", "Monto", "Usuario", "Concepto"])
        movements_table.setObjectName("dataTable")
        movements_table.verticalHeader().setVisible(False)
        movements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        movements_table.setAlternatingRowColors(True)
        movement_rows = detail["movements"]
        movements_table.setRowCount(len(movement_rows))
        for row_index, movement in enumerate(movement_rows):
            values = [
                movement["fecha"],
                movement["tipo"],
                f"${movement['monto']}",
                movement["usuario"],
                movement["concepto"] or "-",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 1:
                    tone = {
                        "REACTIVO": "positive",
                        "INGRESO": "warning",
                        "RETIRO": "danger",
                    }.get(str(movement["tipo"]), "muted")
                    _set_table_badge_style(item, tone)
                movements_table.setItem(row_index, column_index, item)
        movements_table.resizeColumnsToContents()
        movements_table.setMinimumHeight(160)
        movements_layout.addWidget(movements_table)
        movements_box.setLayout(movements_layout)
        layout.addWidget(movements_box)

        if detail["is_closed"]:
            close_box = QGroupBox("Cierre")
            close_box.setObjectName("infoCard")
            close_form = QFormLayout()
            close_form.addRow("Fecha", QLabel(str(detail["closed_at"])))
            close_form.addRow("Usuario", QLabel(str(detail["closed_by"])))
            close_form.addRow("Esperado", QLabel(f"${detail['expected_amount']}"))
            close_form.addRow("Contado", QLabel(f"${detail['declared_amount']}"))
            difference_label = QLabel(f"${detail['difference']}")
            difference_label.setObjectName("inventoryStatusBadge")
            difference_tone = "positive" if detail["difference"] == Decimal("0.00") else ("warning" if detail["difference"] > Decimal("0.00") else "danger")
            self._set_badge_state(difference_label, f"${detail['difference']}", difference_tone)
            close_form.addRow("Diferencia", difference_label)
            closing_note = QLabel(str(detail["closing_note"]))
            closing_note.setWordWrap(True)
            closing_note.setObjectName("subtleLine")
            close_form.addRow("Observacion", closing_note)
            close_box.setLayout(close_form)
            layout.addWidget(close_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec()

    def _refresh_business_settings_form(self) -> None:
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                defaults = self._default_whatsapp_templates()
                self.settings_business_name_input.setText(config.nombre_negocio)
                self.settings_business_logo_input.setText(config.logo_path or "")
                self._refresh_business_logo_preview(config.logo_path or "")
                self.settings_marketing_review_days_spin.setValue(config.loyalty_review_window_days or 365)
                self.settings_marketing_leal_spend_spin.setValue(float(config.leal_spend_threshold or 3000))
                self.settings_marketing_leal_purchase_count_spin.setValue(config.leal_purchase_count_threshold or 3)
                self.settings_marketing_leal_purchase_sum_spin.setValue(float(config.leal_purchase_sum_threshold or 2000))
                self.settings_marketing_discount_basico_spin.setValue(float(config.discount_basico or 5))
                self.settings_marketing_discount_leal_spin.setValue(float(config.discount_leal or 10))
                self.settings_marketing_discount_profesor_spin.setValue(float(config.discount_profesor or 15))
                self.settings_marketing_discount_mayorista_spin.setValue(float(config.discount_mayorista or 20))
                self.settings_business_phone_input.setText(config.telefono or "")
                self.settings_business_address_input.setPlainText(config.direccion or "")
                self.settings_business_footer_input.setPlainText(config.pie_ticket or "")
                self.settings_business_transfer_bank_input.setText(config.transferencia_banco or "")
                self.settings_business_transfer_beneficiary_input.setText(config.transferencia_beneficiario or "")
                self.settings_business_transfer_clabe_input.setText(config.transferencia_clabe or "")
                self.settings_business_transfer_instructions_input.setPlainText(config.transferencia_instrucciones or "")
                self.settings_business_promo_code_input.clear()
                self.settings_business_promo_code_input.setPlaceholderText(
                    "Deja vacio para conservar el codigo actual"
                )
                self.settings_whatsapp_layaway_reminder_input.setPlainText(
                    config.whatsapp_apartado_recordatorio or defaults["layaway_reminder"]
                )
                self.settings_whatsapp_layaway_liquidated_input.setPlainText(
                    config.whatsapp_apartado_liquidado or defaults["layaway_liquidated"]
                )
                self.settings_whatsapp_client_promotion_input.setPlainText(
                    config.whatsapp_cliente_promocion or defaults["client_promotion"]
                )
                self.settings_whatsapp_client_followup_input.setPlainText(
                    config.whatsapp_cliente_seguimiento or defaults["client_followup"]
                )
                self.settings_whatsapp_client_greeting_input.setPlainText(
                    config.whatsapp_cliente_saludo or defaults["client_greeting"]
                )
                printer_index = self.settings_business_printer_combo.findData(config.impresora_preferida or "")
                self.settings_business_printer_combo.setCurrentIndex(printer_index if printer_index >= 0 else 0)
                self.settings_business_copies_spin.setValue(config.copias_ticket or 1)
                self.settings_business_status_label.setText("Configuracion cargada correctamente.")
                self.settings_marketing_status_label.setText("Reglas de marketing cargadas correctamente.")
                self.settings_whatsapp_status_label.setText("Plantillas cargadas correctamente.")
                self._refresh_sale_discount_options()
                self._refresh_marketing_summary(session)
                self._refresh_whatsapp_preview()
        except Exception as exc:  # noqa: BLE001
            self.settings_business_status_label.setText(f"No se pudo cargar la configuracion: {exc}")
            self.settings_marketing_status_label.setText(f"No se pudieron cargar las reglas: {exc}")
            self.settings_whatsapp_status_label.setText(f"No se pudieron cargar las plantillas: {exc}")
            self._refresh_business_logo_preview("")
            self.settings_marketing_summary_label.setText("Sin resumen disponible.")

    def _build_business_settings_payload(self) -> BusinessSettingsInput:
        return BusinessSettingsInput(
            nombre_negocio=self.settings_business_name_input.text(),
            logo_path=self.settings_business_logo_input.text(),
            loyalty_review_window_days=self.settings_marketing_review_days_spin.value(),
            leal_spend_threshold=Decimal(str(self.settings_marketing_leal_spend_spin.value())).quantize(Decimal("0.01")),
            leal_purchase_count_threshold=self.settings_marketing_leal_purchase_count_spin.value(),
            leal_purchase_sum_threshold=Decimal(str(self.settings_marketing_leal_purchase_sum_spin.value())).quantize(Decimal("0.01")),
            discount_basico=Decimal(str(self.settings_marketing_discount_basico_spin.value())).quantize(Decimal("0.01")),
            discount_leal=Decimal(str(self.settings_marketing_discount_leal_spin.value())).quantize(Decimal("0.01")),
            discount_profesor=Decimal(str(self.settings_marketing_discount_profesor_spin.value())).quantize(Decimal("0.01")),
            discount_mayorista=Decimal(str(self.settings_marketing_discount_mayorista_spin.value())).quantize(Decimal("0.01")),
            telefono=self.settings_business_phone_input.text(),
            direccion=self.settings_business_address_input.toPlainText(),
            pie_ticket=self.settings_business_footer_input.toPlainText(),
            transferencia_banco=self.settings_business_transfer_bank_input.text(),
            transferencia_beneficiario=self.settings_business_transfer_beneficiary_input.text(),
            transferencia_clabe=self.settings_business_transfer_clabe_input.text(),
            transferencia_instrucciones=self.settings_business_transfer_instructions_input.toPlainText(),
            promo_authorization_code=self.settings_business_promo_code_input.text(),
            whatsapp_apartado_recordatorio=self.settings_whatsapp_layaway_reminder_input.toPlainText(),
            whatsapp_apartado_liquidado=self.settings_whatsapp_layaway_liquidated_input.toPlainText(),
            whatsapp_cliente_promocion=self.settings_whatsapp_client_promotion_input.toPlainText(),
            whatsapp_cliente_seguimiento=self.settings_whatsapp_client_followup_input.toPlainText(),
            whatsapp_cliente_saludo=self.settings_whatsapp_client_greeting_input.toPlainText(),
            impresora_preferida=str(self.settings_business_printer_combo.currentData() or ""),
            copias_ticket=self.settings_business_copies_spin.value(),
        )

    def _refresh_marketing_summary(self, session) -> None:
        clients = session.scalars(select(Cliente)).all()
        counts = {
            NivelLealtad.BASICO: 0,
            NivelLealtad.LEAL: 0,
            NivelLealtad.PROFESOR: 0,
            NivelLealtad.MAYORISTA: 0,
        }
        for client in clients:
            counts[client.nivel_lealtad] = counts.get(client.nivel_lealtad, 0) + 1
        total = len(clients)
        self.settings_marketing_summary_label.setText(
            (
                f"Clientes registrados: {total}\n"
                f"BASICO: {counts[NivelLealtad.BASICO]} | "
                f"LEAL: {counts[NivelLealtad.LEAL]} | "
                f"PROFESOR: {counts[NivelLealtad.PROFESOR]} | "
                f"MAYORISTA: {counts[NivelLealtad.MAYORISTA]}"
            )
        )

    def _save_business_settings(self, success_message: str) -> bool:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede actualizar esta configuracion.")
            return False
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                if admin_user is None:
                    raise ValueError("Administrador no encontrado.")
                BusinessSettingsService.update_settings(
                    session=session,
                    admin_user=admin_user,
                    payload=self._build_business_settings_payload(),
                )
                session.commit()
                self._refresh_marketing_summary(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return False

        self.settings_business_status_label.setText(success_message)
        self.settings_marketing_status_label.setText(success_message)
        self.settings_whatsapp_status_label.setText(success_message)
        self.settings_business_promo_code_input.clear()
        QMessageBox.information(self, "Configuracion guardada", success_message)
        return True

    def _handle_save_business_settings(self) -> None:
        self._save_business_settings("Los datos del negocio se actualizaron correctamente.")

    def _handle_save_marketing_settings(self) -> None:
        self._save_business_settings("Las reglas de marketing y promociones se actualizaron correctamente.")

    def _handle_select_business_logo(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Seleccionar logo",
            str(Path.home()),
            "Imagenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_path:
            return
        try:
            managed_logo = CustomerCardService.install_logo_asset(file_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Logo no disponible", str(exc))
            return
        self.settings_business_logo_input.setText(str(managed_logo))
        self._refresh_business_logo_preview(str(managed_logo))
        self.settings_business_status_label.setText("Logo listo para guardarse en la configuracion.")

    def _handle_clear_business_logo(self) -> None:
        self.settings_business_logo_input.clear()
        self._refresh_business_logo_preview("")
        self.settings_business_status_label.setText("Logo limpiado. Guarda para aplicar el cambio.")

    def _refresh_business_logo_preview(self, raw_path: str) -> None:
        path_text = (raw_path or "").strip()
        self.settings_business_logo_preview_label.clear()
        if not path_text:
            self.settings_business_logo_preview_label.setText("Sin logo")
            return
        pixmap = QPixmap(path_text)
        if pixmap.isNull():
            self.settings_business_logo_preview_label.setText("Preview no disponible")
            return
        scaled = pixmap.scaled(
            self.settings_business_logo_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.settings_business_logo_preview_label.setPixmap(scaled)

    def _handle_preview_business_card(self) -> None:
        logo_path = self.settings_business_logo_input.text().strip() or None
        business_name = self.settings_business_name_input.text().strip() or "POS Uniformes"
        sample_qr = CustomerCardService.preview_dir() / "sample-qr.png"
        if not sample_qr.exists():
            QMessageBox.warning(self, "Demo no disponible", f"No se encontro el QR demo:\n{sample_qr}")
            return
        payload = CustomerCardRenderInput(
            business_name=business_name,
            logo_path=logo_path,
            full_name="Daniel Fabian",
            customer_since=datetime.now(),
            loyalty_level="PROFESOR",
            level_label="Profesor",
            primary_color="#1F3A44",
            secondary_color="#D7E3E7",
            qr_path=str(sample_qr),
        )
        output_path = CustomerCardService.demo_output_path()
        try:
            rendered_path = CustomerCardService.render_card(payload, output_path)
            self._open_path(rendered_path)
            self.settings_business_status_label.setText(f"Demo actualizada en {rendered_path.name}.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo generar la demo", str(exc))

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=True)
            elif os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.run(["xdg-open", str(path)], check=True)
        except Exception:
            return

    def _handle_save_whatsapp_settings(self) -> None:
        self._save_business_settings("Las plantillas de WhatsApp se actualizaron correctamente.")

    def _handle_recalculate_loyalty_levels(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede recalcular niveles.")
            return
        confirmation = QMessageBox.question(
            self,
            "Recalcular niveles",
            "Se recalcularan los niveles y descuentos de todos los clientes segun las reglas vigentes. Continuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                if admin_user is None:
                    raise ValueError("Administrador no encontrado.")
                summary = LoyaltyService.recalculate_all_clients(
                    session,
                    actor_user=admin_user,
                    reason="recalculo_manual_marketing",
                )
                session.commit()
                self._refresh_marketing_summary(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo recalcular", str(exc))
            return

        self.refresh_all()
        message = (
            f"Niveles revisados: {summary['total']}\n"
            f"Clientes con cambio aplicado: {summary['changed']}"
        )
        self.settings_marketing_status_label.setText(message)
        QMessageBox.information(self, "Recalculo completado", message)

    def _handle_open_marketing_history(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede consultar este historial.")
            return

        try:
            with get_session() as session:
                changes = MarketingAuditService.list_recent(session, limit=120)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Historial no disponible", str(exc))
            return

        dialog, layout = self._create_modal_dialog(
            "Historial de Marketing y promociones",
            "Consulta los ultimos cambios guardados en reglas de lealtad y descuentos por nivel.",
            width=1080,
        )
        status = QLabel(
            f"Cambios registrados: {len(changes)}"
            if changes
            else "Aun no hay cambios auditados en Marketing y promociones."
        )
        status.setObjectName("analyticsLine")
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(
            ["Fecha", "Usuario", "Rol", "Seccion", "Campo", "Valor anterior", "Valor nuevo"]
        )
        table.setObjectName("dataTable")
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setRowCount(len(changes))

        for row_index, change in enumerate(changes):
            values = [
                change.created_at.strftime("%Y-%m-%d %H:%M") if change.created_at else "",
                change.usuario.username if change.usuario is not None else "-",
                change.rol_usuario or "-",
                change.seccion.title(),
                change.etiqueta_campo,
                change.valor_anterior or "-",
                change.valor_nuevo or "-",
            ]
            for column_index, value in enumerate(values):
                table.setItem(row_index, column_index, _table_item(value))
        table.resizeColumnsToContents()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(status)
        layout.addWidget(table)
        layout.addWidget(buttons)
        dialog.exec()

    def _refresh_settings_users(self) -> None:
        try:
            with get_session() as session:
                users = UserService.list_users(session)
        except Exception as exc:  # noqa: BLE001
            self.settings_users_status_label.setText(f"No se pudieron cargar usuarios: {exc}")
            self.settings_users_table.setRowCount(0)
            return

        self.settings_users_table.setRowCount(len(users))
        for row_index, user in enumerate(users):
            values = [
                user.username,
                user.nombre_completo,
                user.rol.value,
                "ACTIVO" if user.activo else "INACTIVO",
                user.updated_at.strftime("%Y-%m-%d %H:%M") if user.updated_at else "",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(user.id))
                self.settings_users_table.setItem(row_index, column_index, item)
        self.settings_users_table.resizeColumnsToContents()
        self.settings_users_status_label.setText(f"Usuarios registrados: {len(users)}")

    def _refresh_settings_suppliers(self) -> None:
        search_text = self.settings_suppliers_search_input.text().strip()
        try:
            with get_session() as session:
                suppliers = SupplierService.list_suppliers(session, search_text)
        except Exception as exc:  # noqa: BLE001
            self.settings_suppliers_status_label.setText(f"No se pudieron cargar proveedores: {exc}")
            self.settings_suppliers_table.setRowCount(0)
            return

        self.settings_suppliers_table.setRowCount(len(suppliers))
        for row_index, supplier in enumerate(suppliers):
            values = [
                supplier.nombre,
                supplier.telefono or "",
                supplier.email or "",
                supplier.direccion or "",
                "ACTIVO" if supplier.activo else "INACTIVO",
                supplier.updated_at.strftime("%Y-%m-%d %H:%M") if supplier.updated_at else "",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(supplier.id))
                if column_index == 4:
                    _set_table_badge_style(item, "positive" if supplier.activo else "muted")
                self.settings_suppliers_table.setItem(row_index, column_index, item)
        self.settings_suppliers_table.resizeColumnsToContents()
        self.settings_suppliers_status_label.setText(f"Proveedores registrados: {len(suppliers)}")

    def _refresh_settings_clients(self) -> None:
        search_text = self.settings_clients_search_input.text().strip()
        try:
            with get_session() as session:
                clients = ClientService.list_clients(session, search_text)
        except Exception as exc:  # noqa: BLE001
            self.settings_clients_status_label.setText(f"No se pudieron cargar clientes: {exc}")
            self.settings_clients_table.setRowCount(0)
            return

        self.settings_clients_table.setRowCount(len(clients))
        for row_index, client in enumerate(clients):
            card_ready = bool(client.card_image_path) and Path(str(client.card_image_path)).exists()
            values = [
                client.codigo_cliente,
                client.nombre,
                client.tipo_cliente.value,
                client.nivel_lealtad.value,
                f"{Decimal(client.descuento_preferente).quantize(Decimal('0.01'))}%",
                client.telefono or "",
                client.notas or "",
                "Listo" if QrGenerator.exists_for_client(client) else "Pendiente",
                "Lista" if card_ready else "Pendiente",
                "ACTIVO" if client.activo else "INACTIVO",
                client.updated_at.strftime("%Y-%m-%d %H:%M") if client.updated_at else "",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole + 1, str(client.codigo_cliente))
                if column_index == 1:
                    item.setData(Qt.ItemDataRole.UserRole, int(client.id))
                if column_index == 2:
                    tone = {
                        TipoCliente.GENERAL.value: "muted",
                        TipoCliente.PROFESOR.value: "positive",
                        TipoCliente.MAYORISTA.value: "warning",
                    }.get(str(value), "muted")
                    _set_table_badge_style(item, tone)
                if column_index == 3:
                    level_tone = {
                        NivelLealtad.BASICO.value: "muted",
                        NivelLealtad.LEAL.value: "warning",
                        NivelLealtad.PROFESOR.value: "positive",
                        NivelLealtad.MAYORISTA.value: "warning",
                    }.get(str(value), "muted")
                    _set_table_badge_style(item, level_tone)
                if column_index == 4 and Decimal(client.descuento_preferente) > Decimal("0.00"):
                    _set_table_badge_style(item, "positive")
                if column_index == 7:
                    _set_table_badge_style(item, "positive" if value == "Listo" else "warning")
                if column_index == 8:
                    _set_table_badge_style(item, "positive" if value == "Lista" else "muted")
                if column_index == 9:
                    _set_table_badge_style(item, "positive" if client.activo else "muted")
                self.settings_clients_table.setItem(row_index, column_index, item)
        self.settings_clients_table.resizeColumnsToContents()
        self.settings_clients_status_label.setText(f"Clientes registrados: {len(clients)}")

    def _selected_settings_user_id(self) -> int | None:
        selected_row = self.settings_users_table.currentRow()
        if selected_row < 0:
            return None
        item = self.settings_users_table.item(selected_row, 0)
        if item is None:
            return None
        user_id = item.data(Qt.ItemDataRole.UserRole)
        return int(user_id) if user_id is not None else None

    def _selected_settings_supplier_id(self) -> int | None:
        selected_row = self.settings_suppliers_table.currentRow()
        if selected_row < 0:
            return None
        item = self.settings_suppliers_table.item(selected_row, 0)
        if item is None:
            return None
        supplier_id = item.data(Qt.ItemDataRole.UserRole)
        return int(supplier_id) if supplier_id is not None else None

    def _selected_settings_client_id(self) -> int | None:
        selected_row = self.settings_clients_table.currentRow()
        if selected_row < 0:
            return None
        item = self.settings_clients_table.item(selected_row, 1)
        if item is None:
            return None
        client_id = item.data(Qt.ItemDataRole.UserRole)
        return int(client_id) if client_id is not None else None

    def _prompt_create_user_data(self) -> dict[str, object] | None:
        dialog, layout = self._create_modal_dialog(
            "Crear usuario",
            "Define username, nombre, rol y contrasena inicial.",
            width=480,
        )
        form = QFormLayout()
        username_input = QLineEdit()
        username_input.setPlaceholderText("ejemplo: cajero2")
        full_name_input = QLineEdit()
        full_name_input.setPlaceholderText("Nombre completo")
        role_combo = QComboBox()
        role_combo.addItem("ADMIN", RolUsuario.ADMIN)
        role_combo.addItem("CAJERO", RolUsuario.CAJERO)
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input.setPlaceholderText("Contrasena inicial")
        form.addRow("Username", username_input)
        form.addRow("Nombre", full_name_input)
        form.addRow("Rol", role_combo)
        form.addRow("Contrasena", password_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "username": username_input.text().strip(),
            "nombre_completo": full_name_input.text().strip(),
            "rol": role_combo.currentData(),
            "password": password_input.text(),
        }

    def _prompt_edit_user_data(
        self,
        username: str,
        nombre_completo: str,
        current_role: RolUsuario,
    ) -> dict[str, object] | None:
        dialog, layout = self._create_modal_dialog(
            "Editar usuario",
            "Actualiza username, nombre y rol del usuario seleccionado.",
            width=480,
        )
        form = QFormLayout()
        username_input = QLineEdit()
        username_input.setText(username)
        full_name_input = QLineEdit()
        full_name_input.setText(nombre_completo)
        role_combo = QComboBox()
        role_combo.addItem("ADMIN", RolUsuario.ADMIN)
        role_combo.addItem("CAJERO", RolUsuario.CAJERO)
        role_combo.setCurrentIndex(0 if current_role == RolUsuario.ADMIN else 1)
        form.addRow("Username", username_input)
        form.addRow("Nombre", full_name_input)
        form.addRow("Rol", role_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "username": username_input.text().strip(),
            "nombre_completo": full_name_input.text().strip(),
            "rol": role_combo.currentData(),
        }

    def _prompt_role_change(self, current_role: RolUsuario) -> RolUsuario | None:
        dialog, layout = self._create_modal_dialog("Cambiar rol", width=360)
        form = QFormLayout()
        role_combo = QComboBox()
        role_combo.addItem("ADMIN", RolUsuario.ADMIN)
        role_combo.addItem("CAJERO", RolUsuario.CAJERO)
        role_combo.setCurrentIndex(0 if current_role == RolUsuario.ADMIN else 1)
        form.addRow("Nuevo rol", role_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return role_combo.currentData()

    def _prompt_password_change(self) -> str | None:
        dialog, layout = self._create_modal_dialog("Cambiar contrasena", width=420)
        form = QFormLayout()
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input.setPlaceholderText("Nueva contrasena")
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_input.setPlaceholderText("Confirmar contrasena")
        form.addRow("Nueva", password_input)
        form.addRow("Confirmar", confirm_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        if password_input.text() != confirm_input.text():
            raise ValueError("La confirmacion de contrasena no coincide.")
        return password_input.text()

    def _prompt_supplier_data(
        self,
        title: str,
        helper_text: str,
        current_values: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        dialog, layout = self._create_modal_dialog(title, helper_text, width=520)
        form = QFormLayout()
        name_input = QLineEdit()
        phone_input = QLineEdit()
        email_input = QLineEdit()
        address_input = QTextEdit()
        address_input.setMinimumHeight(90)
        name_input.setPlaceholderText("Nombre comercial o razon social")
        phone_input.setPlaceholderText("Telefono")
        email_input.setPlaceholderText("correo@proveedor.com")
        address_input.setPlaceholderText("Direccion o notas de ubicacion")
        if current_values:
            name_input.setText(current_values.get("nombre", ""))
            phone_input.setText(current_values.get("telefono", ""))
            email_input.setText(current_values.get("email", ""))
            address_input.setPlainText(current_values.get("direccion", ""))
        form.addRow("Nombre", name_input)
        form.addRow("Telefono", phone_input)
        form.addRow("Correo", email_input)
        form.addRow("Direccion", address_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "nombre": name_input.text().strip(),
            "telefono": phone_input.text().strip(),
            "email": email_input.text().strip(),
            "direccion": address_input.toPlainText().strip(),
        }

    def _prompt_client_data(
        self,
        title: str,
        helper_text: str,
        current_values: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        dialog, layout = self._create_modal_dialog(title, helper_text, width=560)
        form = QFormLayout()
        name_input = QLineEdit()
        client_type_combo = QComboBox()
        client_type_combo.addItem("GENERAL", TipoCliente.GENERAL)
        client_type_combo.addItem("PROFESOR", TipoCliente.PROFESOR)
        client_type_combo.addItem("MAYORISTA", TipoCliente.MAYORISTA)
        discount_spin = QDoubleSpinBox()
        discount_spin.setRange(0.0, 100.0)
        discount_spin.setDecimals(2)
        discount_spin.setSuffix("%")
        discount_spin.setSingleStep(5.0)
        phone_input = QLineEdit()
        notes_input = QTextEdit()
        notes_input.setMinimumHeight(90)
        name_input.setPlaceholderText("Nombre completo o identificacion del cliente")
        phone_input.setPlaceholderText("Telefono")
        notes_input.setPlaceholderText("Notas internas o referencias")
        if current_values:
            name_input.setText(current_values.get("nombre", ""))
            initial_type = current_values.get("tipo_cliente", TipoCliente.GENERAL.value)
            type_index = client_type_combo.findData(TipoCliente(initial_type))
            client_type_combo.setCurrentIndex(type_index if type_index >= 0 else 0)
            discount_spin.setValue(float(current_values.get("descuento_preferente", "0") or 0))
            phone_input.setText(current_values.get("telefono", ""))
            notes_input.setPlainText(current_values.get("notas", ""))
        else:
            discount_spin.setValue(float(ClientService.default_discount_for_type(TipoCliente.GENERAL)))

        def _sync_discount_with_type() -> None:
            tipo = client_type_combo.currentData()
            if not isinstance(tipo, TipoCliente):
                return
            suggested = ClientService.default_discount_for_type(tipo)
            if tipo != TipoCliente.GENERAL:
                discount_spin.setValue(float(suggested))

        client_type_combo.currentIndexChanged.connect(_sync_discount_with_type)
        form.addRow("Nombre", name_input)
        form.addRow("Tipo cliente", client_type_combo)
        form.addRow("Desc. preferente", discount_spin)
        form.addRow("Telefono", phone_input)
        form.addRow("Notas", notes_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "nombre": name_input.text().strip(),
            "tipo_cliente": str((client_type_combo.currentData() or TipoCliente.GENERAL).value),
            "descuento_preferente": str(Decimal(str(discount_spin.value())).quantize(Decimal("0.01"))),
            "telefono": phone_input.text().strip(),
            "notas": notes_input.toPlainText().strip(),
        }

    def _prompt_client_whatsapp_data(self, client_name: str) -> tuple[str, str] | None:
        dialog, layout = self._create_modal_dialog(
            "Mensaje de WhatsApp",
            f"Prepara un mensaje para {client_name}. Se generara o reutilizara su credencial para que puedas adjuntarla por WhatsApp.",
            width=520,
        )
        form = QFormLayout()
        message_type_combo = QComboBox()
        message_type_combo.addItem("Promocion / descuento", "promotion")
        message_type_combo.addItem("Seguimiento general", "followup")
        message_type_combo.addItem("Saludo", "greeting")
        extra_message_input = QTextEdit()
        extra_message_input.setMinimumHeight(110)
        extra_message_input.setPlaceholderText("Texto extra opcional")
        form.addRow("Tipo", message_type_combo)
        form.addRow("Extra", extra_message_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return str(message_type_combo.currentData() or "followup"), extra_message_input.toPlainText().strip()

    def _handle_create_user(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear usuarios.")
            return
        data = self._prompt_create_user_data()
        if data is None:
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                if admin_user is None:
                    raise ValueError("Administrador no encontrado.")
                UserService.create_user(
                    session=session,
                    admin_user=admin_user,
                    username=str(data["username"]),
                    nombre_completo=str(data["nombre_completo"]),
                    rol=data["rol"],
                    password=str(data["password"]),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self._refresh_settings_users()
        QMessageBox.information(self, "Usuario creado", f"Usuario '{data['username']}' creado correctamente.")

    def _handle_toggle_user(self) -> None:
        user_id = self._selected_settings_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un usuario en la tabla.")
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                target_user = session.get(Usuario, user_id)
                if admin_user is None or target_user is None:
                    raise ValueError("No se pudo cargar el usuario seleccionado.")
                UserService.toggle_active(session, admin_user, target_user)
                session.commit()
                username = target_user.username
                status = "activado" if target_user.activo else "desactivado"
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self._refresh_settings_users()
        QMessageBox.information(self, "Estado actualizado", f"Usuario '{username}' {status} correctamente.")

    def _handle_change_user_role(self) -> None:
        user_id = self._selected_settings_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un usuario en la tabla.")
            return
        try:
            with get_session() as session:
                target_user = session.get(Usuario, user_id)
                if target_user is None:
                    raise ValueError("No se encontro el usuario seleccionado.")
                new_role = self._prompt_role_change(target_user.rol)
                if new_role is None:
                    return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return

        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                target_user = session.get(Usuario, user_id)
                if admin_user is None or target_user is None:
                    raise ValueError("No se pudo cargar el usuario seleccionado.")
                UserService.change_role(session, admin_user, target_user, new_role)
                session.commit()
                username = target_user.username
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cambiar rol", str(exc))
            return

        self._refresh_settings_users()
        QMessageBox.information(self, "Rol actualizado", f"Usuario '{username}' ahora es {new_role.value}.")

    def _handle_change_user_password(self) -> None:
        user_id = self._selected_settings_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un usuario en la tabla.")
            return
        try:
            new_password = self._prompt_password_change()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Contrasena invalida", str(exc))
            return
        if new_password is None:
            return

        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                target_user = session.get(Usuario, user_id)
                if admin_user is None or target_user is None:
                    raise ValueError("No se pudo cargar el usuario seleccionado.")
                UserService.change_password(session, admin_user, target_user, new_password)
                session.commit()
                username = target_user.username
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cambiar contrasena", str(exc))
            return

        QMessageBox.information(self, "Contrasena actualizada", f"Contrasena de '{username}' actualizada correctamente.")

    def _handle_edit_user(self) -> None:
        user_id = self._selected_settings_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un usuario en la tabla.")
            return
        try:
            with get_session() as session:
                target_user = session.get(Usuario, user_id)
                if target_user is None:
                    raise ValueError("No se encontro el usuario seleccionado.")
                data = self._prompt_edit_user_data(
                    username=target_user.username,
                    nombre_completo=target_user.nombre_completo,
                    current_role=target_user.rol,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                target_user = session.get(Usuario, user_id)
                if admin_user is None or target_user is None:
                    raise ValueError("No se pudo cargar el usuario seleccionado.")
                UserService.update_user(
                    session=session,
                    admin_user=admin_user,
                    target_user=target_user,
                    username=str(data["username"]),
                    nombre_completo=str(data["nombre_completo"]),
                    rol=data["rol"],
                )
                session.commit()
                updated_username = target_user.username
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self._refresh_settings_users()
        QMessageBox.information(self, "Usuario actualizado", f"Usuario '{updated_username}' actualizado correctamente.")

    def _handle_create_supplier(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear proveedores.")
            return
        data = self._prompt_supplier_data(
            "Crear proveedor",
            "Captura los datos base del proveedor para usarlo despues en compras.",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                if admin_user is None:
                    raise ValueError("Administrador no encontrado.")
                SupplierService.create_supplier(
                    session=session,
                    admin_user=admin_user,
                    nombre=data["nombre"],
                    telefono=data["telefono"],
                    email=data["email"],
                    direccion=data["direccion"],
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Proveedor creado", f"Proveedor '{data['nombre']}' creado correctamente.")

    def _handle_update_supplier(self) -> None:
        supplier_id = self._selected_settings_supplier_id()
        if supplier_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un proveedor en la tabla.")
            return
        try:
            with get_session() as session:
                supplier = session.get(Proveedor, supplier_id)
                if supplier is None:
                    raise ValueError("No se encontro el proveedor seleccionado.")
                data = self._prompt_supplier_data(
                    "Editar proveedor",
                    "Actualiza contacto, correo o direccion del proveedor.",
                    current_values={
                        "nombre": supplier.nombre,
                        "telefono": supplier.telefono or "",
                        "email": supplier.email or "",
                        "direccion": supplier.direccion or "",
                    },
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                supplier = session.get(Proveedor, supplier_id)
                if admin_user is None or supplier is None:
                    raise ValueError("No se pudo cargar el proveedor seleccionado.")
                SupplierService.update_supplier(
                    session=session,
                    admin_user=admin_user,
                    supplier=supplier,
                    nombre=data["nombre"],
                    telefono=data["telefono"],
                    email=data["email"],
                    direccion=data["direccion"],
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Proveedor actualizado", f"Proveedor '{data['nombre']}' actualizado.")

    def _handle_toggle_supplier(self) -> None:
        supplier_id = self._selected_settings_supplier_id()
        if supplier_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un proveedor en la tabla.")
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                supplier = session.get(Proveedor, supplier_id)
                if admin_user is None or supplier is None:
                    raise ValueError("No se pudo cargar el proveedor seleccionado.")
                SupplierService.toggle_active(session, admin_user, supplier)
                session.commit()
                supplier_name = supplier.nombre
                status_text = "activado" if supplier.activo else "desactivado"
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Proveedor actualizado",
            f"Proveedor '{supplier_name}' {status_text} correctamente.",
        )

    def _handle_create_client(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear clientes.")
            return
        data = self._prompt_client_data(
            "Crear cliente",
            "Captura los datos base del cliente para futuras ventas, apartados o programas de fidelizacion.",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                if admin_user is None:
                    raise ValueError("Administrador no encontrado.")
                client = ClientService.create_client(
                    session=session,
                    admin_user=admin_user,
                    nombre=data["nombre"],
                    tipo_cliente=TipoCliente(str(data["tipo_cliente"])),
                    descuento_preferente=Decimal(str(data["descuento_preferente"])),
                    telefono=data["telefono"],
                    notas=data["notas"],
                )
                session.flush()
                card_path, card_error = self._render_client_card_safe(client)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        message = f"Cliente '{data['nombre']}' creado correctamente."
        if card_path is not None:
            message = f"{message}\nCredencial lista en:\n{card_path}"
        elif card_error:
            message = f"{message}\nLa credencial quedo pendiente: {card_error}"
        QMessageBox.information(self, "Cliente creado", message)

    def _handle_update_client(self) -> None:
        client_id = self._selected_settings_client_id()
        if client_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un cliente en la tabla.")
            return
        try:
            with get_session() as session:
                client = session.get(Cliente, client_id)
                if client is None:
                    raise ValueError("No se encontro el cliente seleccionado.")
                data = self._prompt_client_data(
                    "Editar cliente",
                    "Actualiza telefono, tipo comercial, descuento o notas del cliente.",
                    current_values={
                        "nombre": client.nombre,
                        "tipo_cliente": client.tipo_cliente.value,
                        "descuento_preferente": str(Decimal(client.descuento_preferente).quantize(Decimal("0.01"))),
                        "telefono": client.telefono or "",
                        "notas": client.notas or "",
                    },
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                client = session.get(Cliente, client_id)
                if admin_user is None or client is None:
                    raise ValueError("No se pudo cargar el cliente seleccionado.")
                ClientService.update_client(
                    session=session,
                    admin_user=admin_user,
                    client=client,
                    nombre=data["nombre"],
                    tipo_cliente=TipoCliente(str(data["tipo_cliente"])),
                    descuento_preferente=Decimal(str(data["descuento_preferente"])),
                    telefono=data["telefono"],
                    notas=data["notas"],
                )
                session.flush()
                card_path, card_error = self._render_client_card_safe(client)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        message = f"Cliente '{data['nombre']}' actualizado."
        if card_path is not None:
            message = f"{message}\nCredencial regenerada en:\n{card_path}"
        elif card_error:
            message = f"{message}\nLa credencial sigue pendiente: {card_error}"
        QMessageBox.information(self, "Cliente actualizado", message)

    def _handle_toggle_client(self) -> None:
        client_id = self._selected_settings_client_id()
        if client_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un cliente en la tabla.")
            return
        try:
            with get_session() as session:
                admin_user = session.get(Usuario, self.user_id)
                client = session.get(Cliente, client_id)
                if admin_user is None or client is None:
                    raise ValueError("No se pudo cargar el cliente seleccionado.")
                ClientService.toggle_active(session, admin_user, client)
                session.commit()
                client_name = client.nombre
                status_text = "activado" if client.activo else "desactivado"
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Cliente actualizado",
            f"Cliente '{client_name}' {status_text} correctamente.",
        )

    def _handle_generate_client_qr(self) -> None:
        client_id = self._selected_settings_client_id()
        if client_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un cliente en la tabla.")
            return
        try:
            with get_session() as session:
                client = session.get(Cliente, client_id)
                if client is None:
                    raise ValueError("No se encontro el cliente seleccionado.")
                path = QrGenerator.generate_for_client(client)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        self._refresh_settings_clients()
        QMessageBox.information(
            self,
            "QR generado",
            f"QR del cliente '{client.codigo_cliente}' guardado en:\n{path}",
        )

    def _handle_open_client_whatsapp(self) -> None:
        client_id = self._selected_settings_client_id()
        if client_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un cliente en la tabla.")
            return
        try:
            with get_session() as session:
                client = session.get(Cliente, client_id)
                if client is None:
                    raise ValueError("No se encontro el cliente seleccionado.")
                normalized_phone, asset_path, delivery_note = self._prepare_client_card_delivery(client)
                payload = self._prompt_client_whatsapp_data(client.nombre)
                if payload is None:
                    return
                message_type, extra_message = payload
                templates = self._get_whatsapp_templates()
                base_message = {
                    "promotion": templates["client_promotion"],
                    "greeting": templates["client_greeting"],
                    "followup": templates["client_followup"],
                }.get(message_type, templates["client_followup"])
                base_message = self._render_whatsapp_template(
                    base_message,
                    {"cliente": client.nombre, "codigo_cliente": client.codigo_cliente},
                )
                full_message = f"{base_message}\n\n{delivery_note}"
                if extra_message:
                    full_message = f"{full_message}\n\n{extra_message}"
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WhatsApp no disponible", str(exc))
            return

        whatsapp_url = f"https://wa.me/{normalized_phone}?text={quote(full_message)}"
        if not webbrowser.open(whatsapp_url):
            QMessageBox.warning(
                self,
                "No se pudo abrir WhatsApp",
                "No se pudo abrir WhatsApp automaticamente. Verifica que tengas navegador disponible.",
            )
            return
        self._reveal_path(asset_path)
        QMessageBox.information(
            self,
            "WhatsApp preparado",
            (
                f"Se abrio WhatsApp para {client.nombre}.\n"
                f"La credencial del cliente ya esta lista para adjuntarla:\n{asset_path}"
            ),
        )

    def _prepare_client_qr_delivery(self, client: Cliente) -> tuple[str, Path, str]:
        if not (client.telefono or "").strip():
            raise ValueError("El cliente no tiene telefono registrado.")
        normalized_phone = self._normalize_whatsapp_phone(client.telefono or "")
        if len(normalized_phone) < 10:
            raise ValueError("El telefono del cliente no parece valido para WhatsApp.")
        qr_path = QrGenerator.path_for_client(client)
        if not qr_path.exists():
            qr_path = QrGenerator.generate_for_client(client)
        qr_note = (
            f"Codigo de cliente: {client.codigo_cliente}\n"
            f"Tipo: {client.tipo_cliente.value}\n"
            f"Descuento registrado: {Decimal(client.descuento_preferente).quantize(Decimal('0.01'))}%\n"
            "Te comparto tu QR de cliente en la imagen adjunta."
        )
        return normalized_phone, qr_path, qr_note

    def _prepare_client_card_delivery(self, client: Cliente) -> tuple[str, Path, str]:
        normalized_phone, _qr_path, _qr_note = self._prepare_client_qr_delivery(client)
        # Regenera la credencial para evitar reutilizar un PNG desactualizado
        # cuando cambia la plantilla, el nivel o el logo del negocio.
        card_path = CustomerCardService.render_and_attach(client)
        card_note = (
            f"Codigo de cliente: {client.codigo_cliente}\n"
            f"Nivel: {client.nivel_lealtad.value}\n"
            "Te comparto tu credencial de cliente en la imagen adjunta."
        )
        return normalized_phone, card_path, card_note

    def _render_client_card_safe(self, client: Cliente) -> tuple[Path | None, str | None]:
        try:
            card_path = CustomerCardService.render_and_attach(client)
            return card_path, None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _selected_backup_path(self) -> Path | None:
        selected_row = self.settings_backup_table.currentRow()
        if selected_row < 0:
            return None
        item = self.settings_backup_table.item(selected_row, 0)
        if item is None:
            return None
        raw_path = item.data(Qt.ItemDataRole.UserRole)
        if not raw_path:
            return None
        return Path(str(raw_path))

    def _handle_create_backup(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear respaldos manuales.")
            return
        dump_format = str(self.settings_backup_format_combo.currentData() or "plain")
        try:
            backup_file, deleted_files = create_backup(
                output_dir=backup_output_dir(),
                dump_format=dump_format,
                retention_days=7,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Respaldo fallido", str(exc))
            return

        self._refresh_settings_backups()
        deleted_note = f" | Rotacion elimino {len(deleted_files)} respaldo(s)." if deleted_files else ""
        QMessageBox.information(self, "Respaldo creado", f"Se genero {backup_file.name}{deleted_note}")

    def _handle_open_backup_folder(self) -> None:
        target_dir = backup_output_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(target_dir)], check=True)
            elif os.name == "nt":
                os.startfile(str(target_dir))
            else:
                subprocess.run(["xdg-open", str(target_dir)], check=True)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo abrir", str(exc))

    @staticmethod
    def _reveal_path(path: Path) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(path)], check=True)
            elif os.name == "nt":
                os.startfile(str(path.parent))
            else:
                subprocess.run(["xdg-open", str(path.parent)], check=True)
        except Exception:
            return

    def _handle_restore_backup(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede restaurar respaldos.")
            return
        backup_path = self._selected_backup_path()
        if backup_path is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un respaldo en la tabla.")
            return
        if backup_path.suffix != ".dump":
            QMessageBox.warning(
                self,
                "Formato no soportado",
                "La restauracion desde la app solo soporta respaldos .dump. Crea uno en formato restaurable.",
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Restaurar respaldo",
            (
                f"Se restaurara el respaldo '{backup_path.name}' sobre la base actual.\n\n"
                "Esta accion reemplaza la informacion actual del POS.\n"
                "Asegurate de tener un respaldo reciente antes de continuar.\n\n"
                "Deseas continuar?"
            ),
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            engine.dispose()
            restore_backup(backup_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Restauracion fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Restauracion completada", f"Se restauro {backup_path.name} correctamente.")

    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
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

    def _prompt_text_value(self, title: str, label: str, placeholder: str, initial: str = "") -> str | None:
        dialog, layout = self._create_modal_dialog(title)
        form = QFormLayout()
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setText(initial)
        form.addRow(label, field)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return field.text().strip()

    def ensure_cash_session(self) -> bool:
        try:
            with get_session() as session:
                active_session = CajaService.obtener_sesion_activa(session)
                if active_session is not None:
                    self.active_cash_session_id = active_session.id
                    self.cash_session_requires_cut = self._is_stale_cash_session(active_session)
                    opened_by = (
                        active_session.abierta_por.nombre_completo
                        if active_session.abierta_por is not None
                        else "otro usuario"
                    )
                    opened_at = (
                        active_session.abierta_at.strftime("%Y-%m-%d %H:%M")
                        if active_session.abierta_at is not None
                        else "sin fecha"
                    )
                    if self.cash_session_requires_cut:
                        QMessageBox.warning(
                            self,
                            "Caja pendiente de corte",
                            (
                                "Se detecto una caja abierta de un dia anterior.\n\n"
                                "Debes realizar el corte antes de registrar ventas, apartados o abonos.\n\n"
                                f"Apertura: {opened_at}\n"
                                f"Abierta por: {opened_by}\n"
                                f"Reactivo inicial: ${Decimal(active_session.monto_apertura).quantize(Decimal('0.01'))}"
                            ),
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "Caja abierta detectada",
                            (
                                "Ya existe una caja abierta. Se reanudara la sesion actual.\n\n"
                                f"Apertura: {opened_at}\n"
                                f"Abierta por: {opened_by}\n"
                                f"Reactivo inicial: ${Decimal(active_session.monto_apertura).quantize(Decimal('0.01'))}"
                            ),
                        )
                    return True
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("No se encontro el usuario autenticado.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Caja no disponible", str(exc))
            return False

        payload = self._prompt_open_cash_session()
        if payload is None:
            return False

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("No se encontro el usuario autenticado.")
                cash_session = CajaService.abrir_sesion(
                    session=session,
                    usuario=user,
                    monto_apertura=payload["monto_apertura"],
                    observacion=payload["observacion"],
                )
                session.commit()
                self.active_cash_session_id = cash_session.id
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir caja", str(exc))
            return False
        return True

    def _prompt_open_cash_session(self) -> dict[str, object] | None:
        suggested_amount: Decimal | None = None
        try:
            with get_session() as session:
                suggested_amount = CajaService.obtener_ultimo_reactivo_sugerido(session)
        except Exception:
            suggested_amount = None
        dialog, layout = self._create_modal_dialog(
            "Apertura de caja",
            "Antes de operar, confirma cuanto reactivo inicial hay actualmente en caja.",
            width=420,
        )
        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0.0, 999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setSingleStep(50.0)
        if suggested_amount is not None:
            amount_spin.setValue(float(suggested_amount))
        note_input = QTextEdit()
        note_input.setPlaceholderText("Observacion opcional")
        note_input.setMaximumHeight(90)
        reuse_button = QPushButton("Usar ultimo reactivo")
        reuse_button.setObjectName("toolbarSecondaryButton")
        reuse_button.setEnabled(suggested_amount is not None)
        reuse_hint = QLabel(
            f"Ultimo reactivo sugerido: ${suggested_amount}" if suggested_amount is not None else "No hay un reactivo anterior registrado."
        )
        reuse_hint.setObjectName("subtleLine")
        reuse_hint.setWordWrap(True)
        if suggested_amount is not None:
            reuse_button.clicked.connect(lambda: amount_spin.setValue(float(suggested_amount)))
        form = QFormLayout()
        form.addRow("Reactivo inicial", amount_spin)
        form.addRow("", reuse_button)
        form.addRow("Observacion", note_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Abrir caja")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(reuse_hint)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "monto_apertura": Decimal(str(amount_spin.value())).quantize(Decimal("0.01")),
            "observacion": note_input.toPlainText().strip(),
        }

    def _prompt_cash_movement_data(self, movement_type: TipoMovimientoCaja) -> dict[str, object] | None:
        labels = {
            TipoMovimientoCaja.REACTIVO: (
                "Ajustar reactivo",
                "Captura el total actual de reactivo en caja. El sistema calculara la diferencia automaticamente.",
            ),
            TipoMovimientoCaja.INGRESO: ("Ingreso", "Registra una entrada manual de efectivo a la caja actual."),
            TipoMovimientoCaja.RETIRO: ("Retiro", "Registra una salida manual de efectivo de la caja actual."),
        }
        title, helper = labels[movement_type]
        dialog, layout = self._create_modal_dialog(title, helper, width=420)
        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0.00, 999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setSingleStep(50.0)
        concept_input = QTextEdit()
        concept_input.setPlaceholderText("Concepto u observacion")
        concept_input.setMaximumHeight(90)
        form = QFormLayout()
        delta_label = QLabel("")
        delta_label.setObjectName("cashierChangeValue")
        target_total: Decimal | None = None
        if movement_type == TipoMovimientoCaja.REACTIVO:
            try:
                with get_session() as session:
                    cash_session = session.get(SesionCaja, self.active_cash_session_id)
                    if cash_session is not None:
                        resumen = CajaService.resumir_sesion(session, cash_session)
                        target_total = (
                            Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))
                            + resumen.reactivo_total
                        ).quantize(Decimal("0.01"))
            except Exception:
                target_total = None
            if target_total is not None:
                amount_spin.setValue(float(target_total))

            current_label = QLabel(
                f"Reactivo actual registrado: ${target_total}" if target_total is not None else "No se pudo calcular el reactivo actual."
            )
            current_label.setObjectName("subtleLine")
            current_label.setWordWrap(True)

            def update_delta() -> None:
                current_total = target_total or Decimal("0.00")
                delta = (Decimal(str(amount_spin.value())).quantize(Decimal("0.01")) - current_total).quantize(Decimal("0.01"))
                sign = "+" if delta >= Decimal("0.00") else ""
                delta_label.setText(f"Diferencia a registrar: {sign}${delta}")

            amount_spin.valueChanged.connect(update_delta)
            form.addRow(current_label)
            form.addRow("Total actual", amount_spin)
            form.addRow("Diferencia", delta_label)
            update_delta()
        else:
            form.addRow("Monto", amount_spin)
        form.addRow("Concepto", concept_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(f"Registrar {title.lower()}")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        amount = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
        if movement_type == TipoMovimientoCaja.REACTIVO:
            current_total = target_total or Decimal("0.00")
            amount = (amount - current_total).quantize(Decimal("0.01"))
            if amount == Decimal("0.00"):
                QMessageBox.information(dialog, "Sin cambios", "El total actual coincide con el reactivo ya registrado.")
                return None
        return {
            "monto": amount,
            "total_objetivo": Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
            if movement_type == TipoMovimientoCaja.REACTIVO
            else None,
            "concepto": concept_input.toPlainText().strip(),
        }

    def _prompt_cash_opening_correction(self) -> dict[str, object] | None:
        dialog, layout = self._create_modal_dialog(
            "Corregir apertura",
            "Actualiza el reactivo inicial de la caja abierta. Usa esto solo si la apertura se registro con un monto incorrecto.",
            width=430,
        )
        current_amount = Decimal("0.00")
        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, self.active_cash_session_id)
                if cash_session is not None:
                    current_amount = Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))
        except Exception:
            current_amount = Decimal("0.00")

        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0.00, 999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setSingleStep(50.0)
        amount_spin.setValue(float(current_amount))

        difference_label = QLabel("")
        difference_label.setObjectName("cashierChangeValue")
        current_label = QLabel(f"Reactivo inicial registrado: ${current_amount}")
        current_label.setObjectName("subtleLine")
        current_label.setWordWrap(True)

        reason_input = QTextEdit()
        reason_input.setPlaceholderText("Motivo o aclaracion de la correccion")
        reason_input.setMaximumHeight(90)

        def update_difference() -> None:
            nuevo = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
            delta = (nuevo - current_amount).quantize(Decimal("0.01"))
            sign = "+" if delta >= Decimal("0.00") else ""
            difference_label.setText(f"Cambio sobre apertura: {sign}${delta}")

        amount_spin.valueChanged.connect(update_difference)
        update_difference()

        form = QFormLayout()
        form.addRow(current_label)
        form.addRow("Nuevo reactivo inicial", amount_spin)
        form.addRow("Diferencia", difference_label)
        form.addRow("Motivo", reason_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar correccion")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        nuevo_monto = Decimal(str(amount_spin.value())).quantize(Decimal("0.01"))
        if nuevo_monto == current_amount:
            QMessageBox.information(dialog, "Sin cambios", "El reactivo inicial ya tiene ese valor.")
            return None
        return {
            "monto_anterior": current_amount,
            "nuevo_monto": nuevo_monto,
            "motivo": reason_input.toPlainText().strip(),
        }

    def _handle_cash_movement(self, movement_type: TipoMovimientoCaja) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede registrar movimientos de caja.")
            return
        if self.active_cash_session_id is None:
            if not self.ensure_cash_session():
                return
            self.refresh_all()
        payload = self._prompt_cash_movement_data(movement_type)
        if payload is None:
            return
        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, self.active_cash_session_id)
                user = session.get(Usuario, self.user_id)
                if cash_session is None or user is None:
                    raise ValueError("No se pudo cargar la caja activa o el usuario.")
                CajaService.registrar_movimiento(
                    session=session,
                    cash_session=cash_session,
                    usuario=user,
                    tipo=movement_type,
                    monto=Decimal(payload["monto"]),
                    concepto=str(payload["concepto"]) or None,
                )
                session.commit()
        except Exception as exc:
            QMessageBox.critical(self, "Movimiento no registrado", str(exc))
            return
        self.refresh_all()
        label = {
            TipoMovimientoCaja.REACTIVO: "Ajuste de reactivo",
            TipoMovimientoCaja.INGRESO: "Ingreso",
            TipoMovimientoCaja.RETIRO: "Retiro",
        }[movement_type]
        QMessageBox.information(
            self,
            "Movimiento registrado",
            (
                f"{label} ajustado correctamente. Total objetivo: ${payload['total_objetivo']}."
                if movement_type == TipoMovimientoCaja.REACTIVO
                else f"{label} por ${payload['monto']} registrado correctamente."
            ),
        )

    def _handle_correct_cash_opening(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede corregir la apertura de caja.")
            return
        if self.active_cash_session_id is None:
            if not self.ensure_cash_session():
                return
            self.refresh_all()
        payload = self._prompt_cash_opening_correction()
        if payload is None:
            return
        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, self.active_cash_session_id)
                user = session.get(Usuario, self.user_id)
                if cash_session is None or user is None:
                    raise ValueError("No se pudo cargar la caja activa o el usuario.")
                CajaService.corregir_apertura(
                    session=session,
                    cash_session=cash_session,
                    usuario=user,
                    nuevo_monto_apertura=Decimal(payload["nuevo_monto"]),
                    observacion=str(payload["motivo"]) or None,
                )
                session.commit()
        except Exception as exc:
            QMessageBox.critical(self, "Correccion no registrada", str(exc))
            return
        self.refresh_all()
        QMessageBox.information(
            self,
            "Apertura corregida",
            (
                f"Reactivo inicial actualizado de ${payload['monto_anterior']} "
                f"a ${payload['nuevo_monto']}."
            ),
        )

    def _handle_cash_cut(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede operar la caja.")
            return
        if self.active_cash_session_id is None:
            if self.ensure_cash_session():
                self.refresh_all()
            return

        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, self.active_cash_session_id)
                if cash_session is None:
                    raise ValueError("No se encontro la caja activa.")
                resumen = CajaService.resumir_sesion(session, cash_session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Corte no disponible", str(exc))
            return

        dialog, layout = self._create_modal_dialog(
            "Corte de caja",
            "Revisa el efectivo esperado y captura el monto contado para cerrar la caja.",
            width=520,
        )
        info = QLabel(
            "\n".join(
                [
                    f"Apertura: {cash_session.abierta_at.strftime('%Y-%m-%d %H:%M') if cash_session.abierta_at else ''}",
                    f"Reactivo inicial: ${Decimal(cash_session.monto_apertura)}",
                    f"Reactivos extra: {resumen.reactivo_count} | ${resumen.reactivo_total}",
                    f"Ingresos manuales: {resumen.ingresos_count} | ${resumen.ingresos_total}",
                    f"Retiros manuales: {resumen.retiros_count} | ${resumen.retiros_total}",
                    f"Ventas con efectivo: {resumen.ventas_efectivo_count}",
                    f"Efectivo por ventas: ${resumen.efectivo_ventas}",
                    f"Abonos con efectivo: {resumen.abonos_efectivo_count}",
                    f"Efectivo por abonos: ${resumen.efectivo_abonos}",
                    f"Esperado en caja: ${resumen.esperado_en_caja}",
                ]
            )
        )
        info.setWordWrap(True)
        info.setObjectName("inventoryMetaCard")
        counted_spin = QDoubleSpinBox()
        counted_spin.setRange(0.0, 999999.99)
        counted_spin.setDecimals(2)
        counted_spin.setPrefix("$")
        counted_spin.setSingleStep(50.0)
        counted_spin.setValue(float(resumen.esperado_en_caja))
        difference_label = QLabel("$0.00")
        difference_label.setObjectName("cashierChangeValue")
        note_input = QTextEdit()
        note_input.setPlaceholderText("Observaciones del corte")
        note_input.setMaximumHeight(90)

        def update_difference() -> None:
            counted = Decimal(str(counted_spin.value())).quantize(Decimal("0.01"))
            difference = (counted - resumen.esperado_en_caja).quantize(Decimal("0.01"))
            difference_label.setText(f"${difference}")

        counted_spin.valueChanged.connect(update_difference)
        form = QFormLayout()
        form.addRow("Monto contado", counted_spin)
        form.addRow("Diferencia", difference_label)
        form.addRow("Observacion", note_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Cerrar caja")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)
        update_difference()
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        try:
            with get_session() as session:
                cash_session = session.get(SesionCaja, self.active_cash_session_id)
                user = session.get(Usuario, self.user_id)
                if cash_session is None or user is None:
                    raise ValueError("No se pudo cargar la caja o el usuario.")
                closed_session = CajaService.cerrar_sesion(
                    session=session,
                    cash_session=cash_session,
                    usuario=user,
                    monto_contado=Decimal(str(counted_spin.value())).quantize(Decimal("0.01")),
                    observacion=note_input.toPlainText().strip(),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cerrar caja", str(exc))
            return

        self.active_cash_session_id = None
        self.refresh_all()
        QMessageBox.information(
            self,
            "Caja cerrada",
            (
                "El corte se registro correctamente.\n"
                f"Esperado: ${closed_session.monto_esperado_cierre} | "
                f"Contado: ${closed_session.monto_cierre_declarado} | "
                f"Diferencia: ${closed_session.diferencia_cierre}"
            ),
        )

    def _handle_logout(self) -> None:
        confirmation = QMessageBox.question(
            self,
            "Cerrar sesion",
            "Se cerrara la sesion actual y volveras al acceso del sistema.\n\nContinuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        for dialog in (
            self.sales_dialog,
            self.settings_users_dialog,
            self.settings_suppliers_dialog,
            self.settings_clients_dialog,
            self.settings_backup_dialog,
            self.settings_cash_history_dialog,
            self.settings_business_dialog,
            self.settings_whatsapp_dialog,
        ):
            if dialog is not None:
                dialog.close()

        self.hide()
        dialog = LoginDialog()
        if dialog.exec() != LoginDialog.DialogCode.Accepted or dialog.user_id is None:
            self.close()
            return

        previous_user_id = self.user_id
        previous_cart = list(self.sale_cart)
        self.user_id = dialog.user_id
        if not self.ensure_cash_session():
            self.user_id = previous_user_id
            self.sale_cart = previous_cart
            self.refresh_all()
            self.show()
            self.raise_()
            self.activateWindow()
            return

        self.sale_cart.clear()
        self._reset_sale_form()
        self.sales_dialog = None
        self.refresh_all()
        self._apply_role_navigation()
        self._focus_default_tab_for_role()
        self.show()
        self.raise_()
        self.activateWindow()
        self._set_sale_feedback("Sesion actualizada correctamente.", "positive", auto_clear_ms=1800)

    def _prompt_product_data(self, initial: dict[str, object] | None = None) -> dict[str, object] | None:
        with get_session() as session:
            categorias = [
                (categoria.id, categoria.nombre)
                for categoria in session.scalars(
                    select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)
                ).all()
            ]
            marcas = [
                (marca.id, marca.nombre)
                for marca in session.scalars(
                    select(Marca).where(Marca.activo.is_(True)).order_by(Marca.nombre)
                ).all()
            ]
            escuelas = [escuela.nombre for escuela in session.scalars(select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)).all()]
            tipos_prenda = [tipo.nombre for tipo in session.scalars(select(TipoPrenda).where(TipoPrenda.activo.is_(True)).order_by(TipoPrenda.nombre)).all()]
            tipos_pieza = [tipo.nombre for tipo in session.scalars(select(TipoPieza).where(TipoPieza.activo.is_(True)).order_by(TipoPieza.nombre)).all()]
            atributos = [atributo.nombre for atributo in session.scalars(select(AtributoProducto).where(AtributoProducto.activo.is_(True)).order_by(AtributoProducto.nombre)).all()]
            niveles = [nivel.nombre for nivel in session.scalars(select(NivelEducativo).where(NivelEducativo.activo.is_(True)).order_by(NivelEducativo.nombre)).all()]
            product_initial = None
            if initial is not None:
                producto = session.get(Producto, int(initial["producto_id"]))
                if producto is not None:
                    product_initial = {
                        "categoria_id": producto.categoria_id,
                        "marca_id": producto.marca_id,
                        "nombre_base": producto.nombre_base,
                        "descripcion": producto.descripcion or "",
                        "escuela": producto.escuela.nombre if producto.escuela else "",
                        "tipo_prenda": producto.tipo_prenda.nombre if producto.tipo_prenda else "",
                        "tipo_pieza": producto.tipo_pieza.nombre if producto.tipo_pieza else "",
                        "atributo": producto.atributo.nombre if producto.atributo else "",
                        "nivel_educativo": producto.nivel_educativo.nombre if producto.nivel_educativo else "",
                        "genero": producto.genero or "",
                        "escudo": producto.escudo or "",
                        "ubicacion": producto.ubicacion or "",
                    }

        if not categorias or not marcas:
            raise ValueError("Primero necesitas al menos una categoria y una marca activas.")

        legacy_choices = load_legacy_config_choices()
        escuelas = merge_choice_lists(escuelas)
        tipos_uniforme = ["Deportivo", "Oficial", "Basico", "Escolta", "Accesorio"]
        tipos_prenda = merge_choice_lists(tipos_prenda, legacy_choices.get("TIPOS_PRENDA", []), tipos_uniforme)
        tipos_pieza = merge_choice_lists(tipos_pieza, legacy_choices.get("TIPOS_PIEZA", []))
        atributos = merge_choice_lists(atributos, legacy_choices.get("ATRIBUTOS", []))
        niveles = merge_choice_lists(niveles, legacy_choices.get("NIVELES_EDUCATIVOS", []))
        generos_disponibles = merge_choice_lists(legacy_choices.get("GENEROS", []))
        escudos_disponibles = merge_choice_lists(legacy_choices.get("ESCUDOS", []))
        ubicaciones_disponibles = merge_choice_lists(legacy_choices.get("UBICACIONES", []))

        dialog, layout = self._create_modal_dialog(
            "Producto",
            "Captura los datos base del producto. Esta accion no altera inventario por si sola.",
            width=1040,
            expand_to_screen=True,
        )
        legacy_templates = load_legacy_product_templates()
        template_entries: list[dict[str, object]] = [
            {
                "source": "builtin",
                "label": str(template["label"]),
                "category": str(template["category"]),
                "name": str(template["name"]),
                "description": str(template["description"]),
            }
            for template in PRODUCT_TEMPLATES
        ]
        template_entries.extend(legacy_templates)
        base_step_templates = load_step_product_templates("base")
        context_step_templates = load_step_product_templates("context")
        presentation_step_templates = load_step_product_templates("presentation")
        template_combo = QComboBox()
        template_combo.addItem("Selecciona una plantilla", None)
        for template_entry in template_entries:
            template_combo.addItem(str(template_entry["label"]), template_entry)
        base_template_combo = QComboBox()
        base_template_combo.addItem("Selecciona plantilla base", None)
        for template_entry in base_step_templates:
            base_template_combo.addItem(str(template_entry["label"]), template_entry)
        context_template_combo = QComboBox()
        context_template_combo.addItem("Selecciona plantilla de contexto", None)
        for template_entry in context_step_templates:
            context_template_combo.addItem(str(template_entry["label"]), template_entry)
        presentation_template_combo = QComboBox()
        presentation_template_combo.addItem("Selecciona plantilla de presentaciones", None)
        for template_entry in presentation_step_templates:
            presentation_template_combo.addItem(str(template_entry["label"]), template_entry)
        categoria_combo = QComboBox()
        categoria_combo.addItem("Selecciona categoria", None)
        for categoria_id, categoria_nombre in categorias:
            categoria_combo.addItem(categoria_nombre, categoria_id)
        marca_combo = QComboBox()
        marca_combo.addItem("Selecciona marca", None)
        for marca_id, marca_nombre in marcas:
            marca_combo.addItem(marca_nombre, marca_id)
        add_category_button = QPushButton("+")
        add_brand_button = QPushButton("+")
        add_category_button.setObjectName("iconButton")
        add_brand_button.setObjectName("iconButton")
        add_category_button.setToolTip("Crear una categoria nueva sin salir de esta ventana.")
        add_brand_button.setToolTip("Crear una marca nueva sin salir de esta ventana.")
        uniform_category_label = QLabel("Uniformes")
        uniform_category_label.setObjectName("readOnlyField")
        nombre_input = QLineEdit()
        descripcion_input = QTextEdit()
        descripcion_input.setFixedHeight(90)
        escuela_combo = QComboBox()
        escuela_combo.setEditable(True)
        escuela_combo.addItem("")
        escuela_combo.addItems(escuelas)
        tipo_prenda_combo = QComboBox()
        tipo_prenda_combo.setEditable(True)
        tipo_prenda_combo.addItem("")
        tipo_prenda_combo.addItems(tipos_prenda)
        tipo_pieza_combo = QComboBox()
        tipo_pieza_combo.setEditable(True)
        tipo_pieza_combo.addItem("")
        tipo_pieza_combo.addItems(tipos_pieza)
        atributo_combo = QComboBox()
        atributo_combo.setEditable(True)
        atributo_combo.addItem("")
        atributo_combo.addItems(atributos)
        nivel_combo = QComboBox()
        nivel_combo.setEditable(True)
        nivel_combo.addItem("")
        nivel_combo.addItems(niveles)
        genero_input = QComboBox()
        genero_input.setEditable(True)
        genero_input.addItem("")
        genero_input.addItems(generos_disponibles)
        escudo_input = QComboBox()
        escudo_input.setEditable(True)
        escudo_input.addItem("")
        escudo_input.addItems(escudos_disponibles)
        ubicacion_input = QComboBox()
        ubicacion_input.setEditable(True)
        ubicacion_input.addItem("")
        ubicacion_input.addItems(ubicaciones_disponibles)
        variant_sizes_button = MultiSelectPickerButton(
            "Tallas: ninguna",
            title="Seleccionar tallas",
            helper_text="Marca varias tallas sin que el selector se cierre a cada clic. Puedes filtrar, elegir varias y aplicar al final.",
            columns=5,
            presets=[
                ("Basicas", ["2", "4", "6", "8", "10", "12", "14", "16"]),
                ("Pants", ["16", "CH", "MD", "GD", "EXG"]),
                ("Mallas", ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"]),
                ("Pares", lambda values: [value for value in values if value.isdigit() and int(value) % 2 == 0]),
                ("Todas", lambda values: list(values)),
                ("Ninguna", []),
            ],
        )
        variant_colors_button = MultiSelectPickerButton(
            "Colores: ninguno",
            title="Seleccionar colores",
            helper_text="Marca uno o varios colores para generar las presentaciones en lote. Si no eliges color, se usara Sin color.",
            columns=4,
            presets=[
                ("Todos", lambda values: [value for value in values if value != DEFAULT_VARIANT_COLOR]),
                ("Ninguno", []),
            ],
        )
        variant_price_input = QLineEdit()
        variant_price_input.setPlaceholderText("Ej. 199.00")
        variant_cost_input = QLineEdit()
        variant_cost_input.setPlaceholderText("Opcional")
        variant_stock_spin = QSpinBox()
        variant_stock_spin.setRange(0, 10000)
        variant_sizes_summary = QLabel("Sin tallas seleccionadas.")
        variant_colors_summary = QLabel("Sin colores seleccionados.")
        variant_count_summary = QLabel("Si eliges tallas y colores, al guardar podremos crear presentaciones por lote.")
        price_mode_combo = QComboBox()
        price_mode_combo.addItem("Precio unico", "single")
        price_mode_combo.addItem("Precio por bloques", "blocks")
        price_mode_combo.addItem("Precio manual por talla", "manual")
        configure_prices_button = QPushButton("Configurar precios")
        price_mode_hint = QLabel("Captura un solo precio para todas las tallas o usa bloques si manejas escalones.")
        price_mode_hint.setWordWrap(True)
        price_mode_hint.setObjectName("subtleLine")
        price_strategy_summary = QLabel("Todavia no hay estructura de precios definida.")
        price_strategy_summary.setWordWrap(True)
        price_strategy_summary.setObjectName("subtleLine")
        variant_sizes_summary.setObjectName("subtleLine")
        variant_colors_summary.setObjectName("subtleLine")
        variant_count_summary.setObjectName("subtleLine")
        auto_name_checkbox = QCheckBox("Auto")
        auto_name_checkbox.setChecked(initial is None)
        generate_name_button = QPushButton("Generar")
        final_name_preview = QLabel("Nombre final pendiente.")
        final_name_preview.setWordWrap(True)
        final_name_preview.setObjectName("subtleLine")
        live_name_card = QFrame()
        live_name_card.setObjectName("infoCard")
        live_name_card_layout = QVBoxLayout()
        live_name_card_layout.setContentsMargins(16, 14, 16, 14)
        live_name_card_layout.setSpacing(4)
        live_name_caption = QLabel("Nombre del producto")
        live_name_caption.setObjectName("liveNameCaption")
        live_name_title = QLabel("Nombre en construccion")
        live_name_title.setWordWrap(True)
        live_name_title.setObjectName("liveNameValue")
        live_name_hint = QLabel(
            "Se construye conforme avanzas en base, contexto y presentaciones."
        )
        live_name_hint.setWordWrap(True)
        live_name_hint.setObjectName("liveNameHint")
        live_name_card_layout.addWidget(live_name_caption)
        live_name_card_layout.addWidget(live_name_title)
        live_name_card_layout.addWidget(live_name_hint)
        live_name_card.setLayout(live_name_card_layout)
        capture_summary_card = QFrame()
        capture_summary_card.setObjectName("infoCard")
        capture_summary_layout = QVBoxLayout()
        capture_summary_layout.setContentsMargins(12, 10, 12, 10)
        capture_summary_layout.setSpacing(4)
        capture_summary_label = QLabel("Completa los datos para ver un resumen en vivo.")
        capture_summary_label.setWordWrap(True)
        capture_summary_label.setTextFormat(Qt.TextFormat.RichText)
        capture_summary_label.setObjectName("templatePreviewLabel")
        capture_summary_layout.addWidget(capture_summary_label)
        capture_summary_card.setLayout(capture_summary_layout)
        apply_template_button = QPushButton("Aplicar")
        apply_template_button.setEnabled(False)
        apply_template_button.setToolTip(
            "Aplica los valores visibles de la plantilla al producto base para que revises el resultado antes de guardar."
        )
        apply_base_template_button = QPushButton("Aplicar base")
        apply_base_template_button.setEnabled(False)
        base_template_preview = QLabel("Selecciona una plantilla base para sugerir familia, pieza y descripcion.")
        base_template_preview.setWordWrap(True)
        base_template_preview.setTextFormat(Qt.TextFormat.RichText)
        base_template_preview.setObjectName("templatePreviewLabel")
        apply_context_template_button = QPushButton("Aplicar contexto")
        apply_context_template_button.setEnabled(False)
        context_template_preview = QLabel("Selecciona una plantilla de contexto para sugerir nivel, prenda y escudo.")
        context_template_preview.setWordWrap(True)
        context_template_preview.setTextFormat(Qt.TextFormat.RichText)
        context_template_preview.setObjectName("templatePreviewLabel")
        context_inheritance_hint = QLabel("La herencia desde plantilla base aparecera aqui cuando aplique.")
        context_inheritance_hint.setWordWrap(True)
        context_inheritance_hint.setObjectName("subtleLine")
        apply_presentation_template_button = QPushButton("Aplicar presentaciones")
        apply_presentation_template_button.setEnabled(False)
        presentation_template_preview = QLabel("Selecciona una plantilla de presentaciones para sugerir tallas y colores.")
        presentation_template_preview.setWordWrap(True)
        presentation_template_preview.setTextFormat(Qt.TextFormat.RichText)
        presentation_template_preview.setObjectName("templatePreviewLabel")
        presentation_template_hint = QLabel("Aun no hay una sugerencia automatica para este paso.")
        presentation_template_hint.setWordWrap(True)
        presentation_template_hint.setObjectName("subtleLine")
        template_preview_card = QFrame()
        template_preview_card.setObjectName("infoCard")
        template_preview_layout = QVBoxLayout()
        template_preview_layout.setContentsMargins(12, 10, 12, 10)
        template_preview_layout.setSpacing(4)
        template_preview = QLabel("Selecciona una plantilla para revisar su resumen antes de aplicarla.")
        template_preview.setWordWrap(True)
        template_preview.setTextFormat(Qt.TextFormat.RichText)
        template_preview.setObjectName("templatePreviewLabel")
        template_preview_layout.addWidget(template_preview)
        template_preview_card.setLayout(template_preview_layout)
        template_preview_card.setMinimumHeight(132)
        template_preview_card.setMaximumHeight(180)
        base_template_preview_card = QFrame()
        base_template_preview_card.setObjectName("infoCard")
        base_template_preview_card_layout = QVBoxLayout()
        base_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
        base_template_preview_card_layout.setSpacing(4)
        base_template_preview_card_layout.addWidget(base_template_preview)
        base_template_preview_card.setLayout(base_template_preview_card_layout)
        base_template_preview_card.setMaximumHeight(132)
        context_template_preview_card = QFrame()
        context_template_preview_card.setObjectName("infoCard")
        context_template_preview_card_layout = QVBoxLayout()
        context_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
        context_template_preview_card_layout.setSpacing(4)
        context_template_preview_card_layout.addWidget(context_template_preview)
        context_template_preview_card_layout.addWidget(context_inheritance_hint)
        context_template_preview_card.setLayout(context_template_preview_card_layout)
        context_template_preview_card.setMaximumHeight(132)
        presentation_template_preview_card = QFrame()
        presentation_template_preview_card.setObjectName("infoCard")
        presentation_template_preview_card_layout = QVBoxLayout()
        presentation_template_preview_card_layout.setContentsMargins(12, 10, 12, 10)
        presentation_template_preview_card_layout.setSpacing(4)
        presentation_template_preview_card_layout.addWidget(presentation_template_preview)
        presentation_template_preview_card_layout.addWidget(presentation_template_hint)
        presentation_template_preview_card.setLayout(presentation_template_preview_card_layout)
        presentation_template_preview_card.setMaximumHeight(148)

        def unique_values(values: list[str]) -> list[str]:
            return [value for value in dict.fromkeys(values) if value]

        def normalize_values(raw_values: object) -> list[str]:
            if not isinstance(raw_values, list):
                return []
            normalized: list[str] = []
            for raw_value in raw_values:
                value = str(raw_value or "").strip()
                if value:
                    normalized.append(value)
            return unique_values(normalized)

        def preview_values(values: list[str], *, max_items: int = 6) -> str:
            if not values:
                return "ninguno"
            if len(values) <= max_items:
                return ", ".join(values)
            return f"{', '.join(values[:max_items])} ... (+{len(values) - max_items})"

        def normalize_lookup_text(value: str) -> str:
            decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
            return "".join(char for char in decomposed if not unicodedata.combining(char))

        def is_placeholder_brand(value: str) -> bool:
            normalized = normalize_lookup_text(value)
            return normalized in {"", "sin marca", "selecciona marca"}

        def select_combo_text(combo: QComboBox, text: str) -> bool:
            normalized_target = normalize_lookup_text(text)
            if not normalized_target:
                return False
            for index in range(combo.count()):
                if normalize_lookup_text(combo.itemText(index)) == normalized_target:
                    combo.setCurrentIndex(index)
                    return True
            return False

        def set_editable_combo_text(combo: QComboBox, text: str) -> None:
            normalized_text = text.strip()
            if not normalized_text:
                return
            if not select_combo_text(combo, normalized_text):
                combo.setEditText(normalized_text)

        def current_base_template_defaults() -> dict[str, object]:
            template_entry = base_template_combo.currentData()
            if isinstance(template_entry, dict):
                return step_template_defaults("base", template_entry)
            return {}

        def merged_context_defaults(template_entry: dict[str, object]) -> dict[str, object]:
            resolved = dict(step_template_defaults("context", template_entry))
            base_defaults = current_base_template_defaults()
            for key in ("garment_type", "piece_type", "attribute", "gender"):
                if not str(resolved.get(key) or "").strip():
                    inherited_value = str(base_defaults.get(key) or "").strip()
                    if inherited_value:
                        resolved[key] = inherited_value
            return resolved

        def update_context_inheritance_hint() -> None:
            template_entry = context_template_combo.currentData()
            if not isinstance(template_entry, dict):
                context_inheritance_hint.setText("La herencia desde plantilla base aparecera aqui cuando aplique.")
                return
            base_defaults = current_base_template_defaults()
            inherited_parts: list[str] = []
            for key, label in (
                ("piece_type", "pieza"),
                ("attribute", "atributo"),
                ("gender", "genero"),
            ):
                context_value = str(template_entry.get(key) or "").strip()
                base_value = str(base_defaults.get(key) or "").strip()
                if not context_value and base_value:
                    inherited_parts.append(f"{label}: {base_value}")
            if inherited_parts:
                context_inheritance_hint.setText(
                    f"Si aplicas este contexto, heredara desde la plantilla base: {' | '.join(inherited_parts)}."
                )
            else:
                context_inheritance_hint.setText(
                    "Este contexto ya trae sus propios datos clave o no necesita herencia adicional."
                )

        def ensure_uniform_category() -> bool:
            normalized_name = "Uniformes"
            if not normalized_name:
                return False
            if select_combo_text(categoria_combo, normalized_name):
                return True
            if self.current_role != RolUsuario.ADMIN:
                return False
            try:
                with get_session() as session:
                    user = session.get(Usuario, self.user_id)
                    if user is None:
                        raise ValueError("Usuario no encontrado.")
                    categoria = CatalogService.crear_categoria(
                        session,
                        user,
                        normalized_name,
                        descripcion=f"Creada desde plantilla: {normalized_name}.",
                    )
                    session.commit()
                    categoria_id = int(categoria.id)
            except Exception:
                return False
            categoria_combo.addItem(normalized_name, categoria_id)
            categoria_combo.setCurrentIndex(categoria_combo.count() - 1)
            return True

        def update_variant_summary() -> None:
            selected_sizes = variant_sizes_button.selected_labels()
            selected_colors = variant_colors_button.selected_labels()
            variant_sizes_summary.setText(
                f"Tallas elegidas: {preview_values(selected_sizes)}"
                if selected_sizes
                else "Tallas elegidas: ninguna. Si el producto no maneja talla, usaremos Unitalla."
            )
            variant_colors_summary.setText(
                f"Colores elegidos: {preview_values(selected_colors, max_items=5)}"
                if selected_colors
                else "Colores elegidos: ninguno. Si el producto no maneja color, usaremos Sin color."
            )
            total_sizes = max(1, len(selected_sizes))
            total_colors = max(1, len(selected_colors))
            total_variants = total_sizes * total_colors
            variant_count_summary.setText(
                f"Presentaciones previstas: {total_variants}. Se generaran despues de guardar el producto base."
            )
            update_capture_summary()

        auto_name_enabled = {"value": bool(initial is None)}
        last_auto_name = {"value": ""}
        presentation_template_state = {"suggested_label": ""}
        price_mode_state = {"manual_override": False}
        price_value_store: dict[str, dict[str, str] | str] = {
            "single": "",
            "blocks": {},
            "manual": {},
        }

        def gender_abbreviation(raw_value: str) -> str:
            normalized = raw_value.strip().casefold()
            mapping = {
                "hombre": "H",
                "mujer": "M",
                "unisex": "U",
                "nino": "N",
                "niño": "N",
                "nina": "N",
                "niña": "N",
            }
            return mapping.get(normalized, raw_value.strip())

        def looks_feminine_piece(raw_value: str) -> bool:
            normalized = normalize_lookup_text(raw_value)
            feminine_terms = (
                "chamarra",
                "playera",
                "blusa",
                "falda",
                "malla",
                "sudadera",
                "camisa",
            )
            return any(term in normalized for term in feminine_terms)

        def garment_descriptor(piece_value: str, garment_value: str) -> str:
            normalized = normalize_lookup_text(garment_value)
            if not normalized:
                return ""
            if normalized == "deportivo":
                return "deportiva" if looks_feminine_piece(piece_value) else "deportivo"
            if normalized == "basico":
                return "basica" if looks_feminine_piece(piece_value) else "basico"
            if normalized == "accesorio":
                return "escolar"
            return garment_value.strip()

        def build_suggested_base_name() -> str:
            base_template_entry = base_template_combo.currentData()
            if isinstance(base_template_entry, dict):
                base_template_label = str(base_template_entry.get("label") or "").strip()
                if base_template_label:
                    return base_template_label

            template_entry = template_combo.currentData()
            template_name = ""
            if isinstance(template_entry, dict):
                template_name = str(template_entry.get("name") or "").strip()
            piece_type = tipo_pieza_combo.currentText().strip()
            garment_type = tipo_prenda_combo.currentText().strip()
            brand = marca_combo.currentText().strip() if marca_combo.currentData() is not None else ""
            if is_placeholder_brand(brand):
                brand = ""
            attribute = atributo_combo.currentText().strip()
            gender = gender_abbreviation(genero_input.currentText()) if genero_input.currentIndex() > 0 else ""
            parts: list[str] = []
            if piece_type:
                parts.append(piece_type)
            elif template_name:
                parts.append(template_name)
            descriptor = attribute or garment_descriptor(piece_type or template_name, garment_type)
            for candidate in (descriptor, brand, gender):
                if candidate and candidate.casefold() not in {part.casefold() for part in parts}:
                    parts.append(candidate)
            return " ".join(part for part in parts if part).strip()

        def build_display_name_preview(base_name: str) -> str:
            if not base_name.strip():
                return "Nombre final pendiente."
            normalized_base = normalize_lookup_text(base_name)
            suffix_parts: list[str] = []
            seen_suffixes: set[str] = set()
            for value in (
                escuela_combo.currentText().strip(),
                tipo_prenda_combo.currentText().strip(),
                tipo_pieza_combo.currentText().strip(),
            ):
                normalized_value = normalize_lookup_text(value)
                if not normalized_value or normalized_value in seen_suffixes:
                    continue
                if normalized_value in normalized_base:
                    continue
                seen_suffixes.add(normalized_value)
                suffix_parts.append(value)
            if not suffix_parts:
                return base_name.strip()
            return f"{base_name.strip()} | {' | '.join(suffix_parts)}"

        def update_final_name_preview() -> None:
            preview_text = build_display_name_preview(nombre_input.text().strip())
            final_name_preview.setText(
                preview_text
                if preview_text != "Nombre final pendiente."
                else "El nombre completo aparecera arriba en cuanto haya base suficiente."
            )
            live_name_title.setText(
                preview_text if preview_text != "Nombre final pendiente." else "Nombre en construccion"
            )

        def build_variant_examples_preview(sizes: list[str], colors: list[str], *, max_items: int = 4) -> str:
            normalized_sizes = sizes or [DEFAULT_VARIANT_SIZE]
            normalized_colors = colors or [DEFAULT_VARIANT_COLOR]
            examples: list[str] = []
            for size in normalized_sizes:
                for color in normalized_colors:
                    examples.append(f"{size} / {color}")
                    if len(examples) >= max_items:
                        return ", ".join(examples)
            return ", ".join(examples)

        def preview_next_skus(count: int) -> list[str]:
            normalized_count = max(0, int(count))
            if normalized_count == 0:
                return []
            try:
                with get_session() as session:
                    return CatalogService.preview_next_skus(session, normalized_count)
            except Exception:
                return []

        def format_sku_preview(count: int) -> str:
            preview_list = preview_next_skus(count)
            if not preview_list:
                return "SKU pendiente."
            if len(preview_list) == 1:
                return preview_list[0]
            preview_head = ", ".join(preview_list[:4])
            if len(preview_list) <= 4:
                return f"{preview_head} | rango {preview_list[0]} -> {preview_list[-1]}"
            return f"{preview_head} ... (+{len(preview_list) - 4}) | rango {preview_list[0]} -> {preview_list[-1]}"

        def selected_sizes_for_pricing() -> list[str]:
            selected_sizes = variant_sizes_button.selected_labels()
            return selected_sizes or [DEFAULT_VARIANT_SIZE]

        def current_price_block_definitions() -> list[dict[str, object]]:
            return build_price_blocks(
                {
                    "garment_type": tipo_prenda_combo.currentText(),
                    "piece_type": tipo_pieza_combo.currentText(),
                    "education_level": nivel_combo.currentText(),
                    "gender": genero_input.currentText(),
                },
                selected_sizes_for_pricing(),
            )

        def build_price_assignment() -> tuple[dict[str, str], list[str], str]:
            normalized_sizes = selected_sizes_for_pricing()
            mode = str(price_mode_combo.currentData() or "single")
            price_map: dict[str, str] = {}
            missing: list[str] = []
            if mode == "single":
                price_text = variant_price_input.text().strip()
                if not price_text:
                    missing.append("precio unico")
                else:
                    for size in normalized_sizes:
                        price_map[size] = price_text
                summary = f"Precio unico: {price_text or '-'}"
                return price_map, missing, summary
            if mode == "blocks":
                block_values = price_value_store["blocks"]
                assert isinstance(block_values, dict)
                summary_parts: list[str] = []
                for block in current_price_block_definitions():
                    block_key = str(block["key"])
                    block_label = str(block["label"])
                    block_sizes = [str(value) for value in block.get("sizes", [])]
                    price_text = str(block_values.get(block_key) or "").strip()
                    if not price_text:
                        missing.append(block_label)
                    else:
                        for size in block_sizes:
                            price_map[size] = price_text
                    summary_parts.append(
                        f"{block_label} ({preview_values(block_sizes, max_items=8)}): {price_text or '-'}"
                    )
                return price_map, missing, " | ".join(summary_parts) if summary_parts else "Sin bloques disponibles."
            manual_values = price_value_store["manual"]
            assert isinstance(manual_values, dict)
            summary_parts = []
            for size in normalized_sizes:
                price_text = str(manual_values.get(size) or "").strip()
                if not price_text:
                    missing.append(size)
                else:
                    price_map[size] = price_text
                summary_parts.append(f"{size}: {price_text or '-'}")
            return price_map, missing, " | ".join(summary_parts) if summary_parts else "Sin precios por talla."

        def update_price_inputs_ui() -> None:
            mode = str(price_mode_combo.currentData() or "single")
            if mode == "single":
                configure_prices_button.setText("Capturar precio")
                price_mode_hint.setText(
                    "Usa un solo precio para todas las presentaciones y configuralo desde el popup."
                )
            elif mode == "blocks":
                configure_prices_button.setText("Configurar bloques")
                price_mode_hint.setText(
                    "Captura un precio por bloque de tallas desde el popup. Es ideal cuando infantil, numericas o letras cambian de precio."
                )
            else:
                configure_prices_button.setText("Configurar por talla")
                price_mode_hint.setText(
                    "Define un precio por talla desde el popup solo cuando haya muchas excepciones."
                )
            price_map, missing_prices, strategy_summary = build_price_assignment()
            missing_label = (
                f"Faltan precios en: {', '.join(missing_prices)}."
                if missing_prices
                else f"Precios listos para {len(price_map)} talla(s)."
            )
            price_strategy_summary.setText(f"{strategy_summary}\n{missing_label}")

        def open_price_configuration_dialog() -> None:
            mode = str(price_mode_combo.currentData() or "single")
            temp_single_price = variant_price_input.text().strip()
            temp_blocks = dict(price_value_store["blocks"]) if isinstance(price_value_store["blocks"], dict) else {}
            temp_manual = dict(price_value_store["manual"]) if isinstance(price_value_store["manual"], dict) else {}

            pricing_dialog, pricing_layout = self._create_modal_dialog(
                "Configurar precios",
                "Captura la estructura de precios sin saturar el formulario principal.",
                width=640,
            )
            context_label = QLabel(
                f"Modo actual: {price_mode_combo.currentText()} | Tallas: {preview_values(selected_sizes_for_pricing(), max_items=10)}"
            )
            context_label.setWordWrap(True)
            context_label.setObjectName("subtleLine")
            pricing_layout.addWidget(context_label)

            if mode == "single":
                editor_form = QFormLayout()
                single_input = QLineEdit(temp_single_price)
                single_input.setPlaceholderText("Ej. 199.00")
                helper_label = QLabel("Este precio se aplicara a todas las tallas seleccionadas.")
                helper_label.setWordWrap(True)
                helper_label.setObjectName("subtleLine")
                editor_form.addRow("Precio unico", single_input)
                editor_form.addRow("", helper_label)
                pricing_layout.addLayout(editor_form)
            else:
                editor_scroll = QScrollArea()
                editor_scroll.setWidgetResizable(True)
                editor_container = QWidget()
                editor_container_layout = QVBoxLayout()
                editor_container_layout.setContentsMargins(0, 0, 0, 0)
                editor_container_layout.setSpacing(8)
                editor_inputs: dict[str, QLineEdit] = {}
                if mode == "blocks":
                    for block in current_price_block_definitions():
                        block_key = str(block["key"])
                        block_label = str(block["label"])
                        block_sizes = [str(value) for value in block.get("sizes", [])]
                        row_box = QFrame()
                        row_box.setObjectName("infoCard")
                        row_layout = QVBoxLayout()
                        row_layout.setContentsMargins(10, 10, 10, 10)
                        row_layout.setSpacing(4)
                        title_label = QLabel(block_label)
                        title_label.setObjectName("tableSectionTitle")
                        price_input = QLineEdit(str(temp_blocks.get(block_key) or ""))
                        price_input.setPlaceholderText("Ej. 199.00")
                        sizes_label = QLabel(f"Tallas: {preview_values(block_sizes, max_items=10)}")
                        sizes_label.setWordWrap(True)
                        sizes_label.setObjectName("subtleLine")
                        row_layout.addWidget(title_label)
                        row_layout.addWidget(price_input)
                        row_layout.addWidget(sizes_label)
                        row_box.setLayout(row_layout)
                        editor_container_layout.addWidget(row_box)
                        editor_inputs[block_key] = price_input
                else:
                    for size in selected_sizes_for_pricing():
                        row_box = QFrame()
                        row_box.setObjectName("infoCard")
                        row_layout = QVBoxLayout()
                        row_layout.setContentsMargins(10, 10, 10, 10)
                        row_layout.setSpacing(4)
                        title_label = QLabel(f"Talla {size}")
                        title_label.setObjectName("tableSectionTitle")
                        price_input = QLineEdit(str(temp_manual.get(size) or ""))
                        price_input.setPlaceholderText("Ej. 199.00")
                        row_layout.addWidget(title_label)
                        row_layout.addWidget(price_input)
                        row_box.setLayout(row_layout)
                        editor_container_layout.addWidget(row_box)
                        editor_inputs[size] = price_input
                editor_container_layout.addStretch(1)
                editor_container.setLayout(editor_container_layout)
                editor_scroll.setWidget(editor_container)
                pricing_layout.addWidget(editor_scroll, 1)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(pricing_dialog.accept)
            buttons.rejected.connect(pricing_dialog.reject)
            pricing_layout.addWidget(buttons)
            if pricing_dialog.exec() != int(QDialog.DialogCode.Accepted):
                return

            if mode == "single":
                variant_price_input.setText(single_input.text().strip())
            elif mode == "blocks":
                price_value_store["blocks"] = {
                    key: input_widget.text().strip()
                    for key, input_widget in editor_inputs.items()
                }
            else:
                price_value_store["manual"] = {
                    key: input_widget.text().strip()
                    for key, input_widget in editor_inputs.items()
                }
            update_capture_summary()
            update_review_details()

        def sync_price_mode_suggestion(*, force: bool = False) -> None:
            suggested_mode = suggest_price_capture_mode(
                {
                    "garment_type": tipo_prenda_combo.currentText(),
                    "piece_type": tipo_pieza_combo.currentText(),
                    "education_level": nivel_combo.currentText(),
                    "gender": genero_input.currentText(),
                },
                selected_sizes_for_pricing(),
            )
            if force or not price_mode_state["manual_override"]:
                target_index = price_mode_combo.findData(suggested_mode)
                if target_index >= 0 and price_mode_combo.currentIndex() != target_index:
                    price_mode_combo.blockSignals(True)
                    price_mode_combo.setCurrentIndex(target_index)
                    price_mode_combo.blockSignals(False)
            update_price_inputs_ui()

        def update_capture_summary() -> None:
            final_name = build_display_name_preview(nombre_input.text().strip())
            selected_sizes = variant_sizes_button.selected_labels()
            selected_colors = variant_colors_button.selected_labels()
            total_sizes = max(1, len(selected_sizes))
            total_colors = max(1, len(selected_colors))
            total_variants = total_sizes * total_colors
            price_map, missing_prices, price_summary = build_price_assignment()
            stock_text = str(variant_stock_spin.value())
            sku_summary = format_sku_preview(total_variants)
            notes: list[str] = []
            if not nombre_input.text().strip():
                notes.append("Define el nombre base para evitar guardar un producto incompleto.")
            if not selected_sizes:
                notes.append("Sin tallas elegidas: se usara Unitalla si creas el lote.")
            if not selected_colors:
                notes.append("Sin colores elegidos: se usara Sin color si creas el lote.")
            if missing_prices:
                notes.append(
                    "Todavia faltan precios para poder crear presentaciones sin correcciones: "
                    + ", ".join(missing_prices)
                    + "."
                )
            price_strategy_summary.setText(
                f"{price_summary}\n"
                + (
                    f"Faltan precios en: {', '.join(missing_prices)}."
                    if missing_prices
                    else f"Precios listos para {len(price_map)} talla(s)."
                )
            )
            capture_summary_label.setText(
                "<div><b>Resumen en vivo</b></div>"
                f"<div><b>Producto:</b> {final_name}</div>"
                f"<div><b>Presentaciones previstas:</b> {total_variants}</div>"
                f"<div><b>SKU previstos:</b> {sku_summary}</div>"
                "<div><b>QR:</b> Manual bajo demanda. Puedes generarlo al final o desde Inventario.</div>"
                f"<div><b>Ejemplos:</b> {build_variant_examples_preview(selected_sizes, selected_colors)}</div>"
                f"<div><b>Precio / stock inicial:</b> {price_summary} / {stock_text}</div>"
                f"<div style='color:#7e3a22;'>{' | '.join(notes) if notes else 'Listo para guardar el producto y crear el lote de presentaciones.'}</div>"
            )

        def sync_name_suggestion(*, force: bool = False) -> None:
            suggested_name = build_suggested_base_name()
            previous_auto = last_auto_name["value"]
            last_auto_name["value"] = suggested_name
            if force or auto_name_enabled["value"] or nombre_input.text().strip() == previous_auto:
                if suggested_name:
                    nombre_input.setText(suggested_name)
            update_final_name_preview()

        def handle_name_manual_edit(value: str) -> None:
            normalized_value = value.strip()
            auto_name_enabled["value"] = auto_name_checkbox.isChecked() and normalized_value == last_auto_name["value"]
            if normalized_value and normalized_value != last_auto_name["value"]:
                auto_name_checkbox.setChecked(False)
                auto_name_enabled["value"] = False
            update_final_name_preview()
            update_capture_summary()

        def sync_variant_options(
            template_entry: dict[str, object] | None,
            *,
            apply_defaults: bool,
        ) -> None:
            suggested_sizes = normalize_values(template_entry.get("tallas")) if template_entry else []
            suggested_colors = normalize_values(template_entry.get("colores")) if template_entry else []
            available_sizes = merge_choice_lists(
                suggested_sizes,
                legacy_choices.get("TALLAS", []),
                COMMON_SIZES,
                [DEFAULT_VARIANT_SIZE],
            )
            available_colors = merge_choice_lists(
                suggested_colors,
                legacy_choices.get("COLORES", []),
                COMMON_COLORS,
                [DEFAULT_VARIANT_COLOR],
            )
            variant_sizes_button.set_items([(value, value) for value in available_sizes])
            variant_colors_button.set_items([(value, value) for value in available_colors])
            if apply_defaults:
                variant_sizes_button.set_selected_values(suggested_sizes)
                variant_colors_button.set_selected_values(suggested_colors)
            update_variant_summary()

        def presentation_template_index_by_label(label: str) -> int:
            normalized = normalize_lookup_text(label)
            if not normalized:
                return -1
            for index in range(presentation_template_combo.count()):
                if normalize_lookup_text(presentation_template_combo.itemText(index)) == normalized:
                    return index
            return -1

        def update_presentation_template_suggestion() -> None:
            suggested_label = suggest_presentation_template(
                {
                    "garment_type": tipo_prenda_combo.currentText(),
                    "piece_type": tipo_pieza_combo.currentText(),
                    "education_level": nivel_combo.currentText(),
                    "gender": genero_input.currentText(),
                }
            ) or ""
            previous_label = presentation_template_state["suggested_label"]
            current_entry = presentation_template_combo.currentData()
            current_label = (
                str(current_entry.get("label") or "").strip()
                if isinstance(current_entry, dict)
                else ""
            )
            if suggested_label:
                presentation_template_hint.setText(
                    f"Sugerida por el contexto actual: {suggested_label}. Puedes aplicarla o cambiarla."
                )
            else:
                presentation_template_hint.setText(
                    "Aun no hay una sugerencia automatica para este paso."
                )
            should_sync_selection = not current_label or current_label == previous_label
            presentation_template_state["suggested_label"] = suggested_label
            if should_sync_selection:
                target_index = presentation_template_index_by_label(suggested_label) if suggested_label else 0
                if presentation_template_combo.currentIndex() != target_index:
                    presentation_template_combo.blockSignals(True)
                    presentation_template_combo.setCurrentIndex(target_index)
                    presentation_template_combo.blockSignals(False)
                    update_presentation_template_preview()
            sync_price_mode_suggestion()

        sync_variant_options(None, apply_defaults=False)

        def create_inline_category() -> None:
            if self.current_role != RolUsuario.ADMIN:
                QMessageBox.warning(dialog, "Sin permisos", "Solo ADMIN puede crear categorias.")
                return
            name = self._prompt_text_value("Nueva categoria", "Categoria", "Nueva categoria")
            if name is None or not name:
                return
            try:
                with get_session() as session:
                    user = session.get(Usuario, self.user_id)
                    if user is None:
                        raise ValueError("Usuario no encontrado.")
                    categoria = CatalogService.crear_categoria(session, user, name)
                    session.commit()
                    categoria_id = int(categoria.id)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(dialog, "Categoria fallida", str(exc))
                return
            categoria_combo.addItem(name, categoria_id)
            categoria_combo.setCurrentIndex(categoria_combo.count() - 1)

        def create_inline_brand() -> None:
            if self.current_role != RolUsuario.ADMIN:
                QMessageBox.warning(dialog, "Sin permisos", "Solo ADMIN puede crear marcas.")
                return
            name = self._prompt_text_value("Nueva marca", "Marca", "Nueva marca")
            if name is None or not name:
                return
            try:
                with get_session() as session:
                    user = session.get(Usuario, self.user_id)
                    if user is None:
                        raise ValueError("Usuario no encontrado.")
                    marca = CatalogService.crear_marca(session, user, name)
                    session.commit()
                    marca_id = int(marca.id)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(dialog, "Marca fallida", str(exc))
                return
            marca_combo.addItem(name, marca_id)
            marca_combo.setCurrentIndex(marca_combo.count() - 1)

        add_category_button.clicked.connect(create_inline_category)
        add_brand_button.clicked.connect(create_inline_brand)

        def update_template_preview() -> None:
            template_entry = template_combo.currentData()
            if not isinstance(template_entry, dict):
                apply_template_button.setEnabled(False)
                template_preview.setText("Selecciona una plantilla para revisar su resumen antes de aplicarla.")
                sync_variant_options(None, apply_defaults=False)
                return
            apply_template_button.setEnabled(True)
            template_preview.setText(build_product_template_preview(template_entry))
            sync_variant_options(template_entry, apply_defaults=False)

        def apply_selected_template() -> None:
            template_entry = template_combo.currentData()
            if not isinstance(template_entry, dict):
                return

            defaults = product_template_defaults(template_entry)

            category_name = defaults["category"]
            if category_name:
                ensure_uniform_category()

            brand_name = defaults["brand"]
            if brand_name and not is_placeholder_brand(brand_name):
                select_combo_text(marca_combo, brand_name)

            if defaults["name"]:
                nombre_input.setText(defaults["name"])
            if defaults["description"]:
                descripcion_input.setPlainText(defaults["description"])
            if defaults["school"]:
                set_editable_combo_text(escuela_combo, defaults["school"])
            if defaults["garment_type"]:
                set_editable_combo_text(tipo_prenda_combo, defaults["garment_type"])
            if defaults["piece_type"]:
                set_editable_combo_text(tipo_pieza_combo, defaults["piece_type"])
            if defaults["attribute"]:
                set_editable_combo_text(atributo_combo, defaults["attribute"])
            if defaults["education_level"]:
                set_editable_combo_text(nivel_combo, defaults["education_level"])
            if defaults["gender"]:
                set_editable_combo_text(genero_input, defaults["gender"])
            if defaults["shield"]:
                set_editable_combo_text(escudo_input, defaults["shield"])
            if defaults["location"]:
                set_editable_combo_text(ubicacion_input, defaults["location"])
            if str(template_entry.get("precio") or "").strip():
                variant_price_input.setText(str(template_entry.get("precio") or "").strip())
                price_mode_state["manual_override"] = False
                target_index = price_mode_combo.findData("single")
                if target_index >= 0:
                    price_mode_combo.setCurrentIndex(target_index)
            sync_variant_options(template_entry, apply_defaults=True)
            sync_price_mode_suggestion(force=bool(template_entry.get("precio")))
            if auto_name_checkbox.isChecked():
                sync_name_suggestion(force=True)

        def update_base_template_preview() -> None:
            template_entry = base_template_combo.currentData()
            if not isinstance(template_entry, dict):
                apply_base_template_button.setEnabled(False)
                base_template_preview.setText("Selecciona una plantilla base para sugerir familia, pieza y descripcion.")
                update_context_inheritance_hint()
                return
            apply_base_template_button.setEnabled(True)
            base_template_preview.setText(build_step_template_preview("base", template_entry))
            update_context_inheritance_hint()

        def apply_base_step_template() -> None:
            template_entry = base_template_combo.currentData()
            if not isinstance(template_entry, dict):
                return
            defaults = step_template_defaults("base", template_entry)
            ensure_uniform_category()
            if defaults.get("garment_type"):
                set_editable_combo_text(tipo_prenda_combo, str(defaults["garment_type"]))
            if defaults.get("piece_type"):
                set_editable_combo_text(tipo_pieza_combo, str(defaults["piece_type"]))
            if defaults.get("attribute"):
                set_editable_combo_text(atributo_combo, str(defaults["attribute"]))
            if defaults.get("gender"):
                set_editable_combo_text(genero_input, str(defaults["gender"]))
            if defaults.get("description"):
                descripcion_input.setPlainText(str(defaults["description"]))
            if auto_name_checkbox.isChecked():
                sync_name_suggestion(force=True)
            elif defaults.get("name") and not nombre_input.text().strip():
                nombre_input.setText(str(defaults["name"]))
                update_final_name_preview()
                update_capture_summary()
            update_review_details()

        def update_context_template_preview() -> None:
            template_entry = context_template_combo.currentData()
            if not isinstance(template_entry, dict):
                apply_context_template_button.setEnabled(False)
                context_template_preview.setText("Selecciona una plantilla de contexto para sugerir nivel, prenda y escudo.")
                update_context_inheritance_hint()
                return
            apply_context_template_button.setEnabled(True)
            context_template_preview.setText(build_step_template_preview("context", template_entry))
            update_context_inheritance_hint()

        def apply_context_step_template() -> None:
            template_entry = context_template_combo.currentData()
            if not isinstance(template_entry, dict):
                return
            defaults = merged_context_defaults(template_entry)
            ensure_uniform_category()
            if defaults.get("garment_type"):
                set_editable_combo_text(tipo_prenda_combo, str(defaults["garment_type"]))
            if defaults.get("piece_type"):
                set_editable_combo_text(tipo_pieza_combo, str(defaults["piece_type"]))
            if defaults.get("attribute"):
                set_editable_combo_text(atributo_combo, str(defaults["attribute"]))
            if defaults.get("education_level"):
                set_editable_combo_text(nivel_combo, str(defaults["education_level"]))
            if defaults.get("gender"):
                set_editable_combo_text(genero_input, str(defaults["gender"]))
            if defaults.get("shield"):
                set_editable_combo_text(escudo_input, str(defaults["shield"]))
            if defaults.get("location"):
                set_editable_combo_text(ubicacion_input, str(defaults["location"]))
            if auto_name_checkbox.isChecked():
                sync_name_suggestion(force=True)
            update_capture_summary()
            update_review_details()
            update_context_inheritance_hint()

        def update_presentation_template_preview() -> None:
            template_entry = presentation_template_combo.currentData()
            if not isinstance(template_entry, dict):
                apply_presentation_template_button.setEnabled(False)
                presentation_template_preview.setText("Selecciona una plantilla de presentaciones para sugerir tallas y colores.")
                return
            apply_presentation_template_button.setEnabled(True)
            presentation_template_preview.setText(build_step_template_preview("presentation", template_entry))

        def apply_presentation_step_template() -> None:
            template_entry = presentation_template_combo.currentData()
            if not isinstance(template_entry, dict):
                return
            defaults = step_template_defaults("presentation", template_entry)
            variant_sizes_button.set_selected_values(list(defaults.get("sizes", [])))
            variant_colors_button.set_selected_values(list(defaults.get("colors", [])))
            if defaults.get("price"):
                variant_price_input.setText(str(defaults["price"]))
                price_mode_state["manual_override"] = False
                target_index = price_mode_combo.findData("single")
                if target_index >= 0:
                    price_mode_combo.setCurrentIndex(target_index)
            if defaults.get("stock"):
                variant_stock_spin.setValue(int(defaults["stock"]))
            sync_price_mode_suggestion(force=not bool(defaults.get("price")))
            update_capture_summary()
            update_review_details()

        template_combo.currentIndexChanged.connect(lambda _: update_template_preview())
        apply_template_button.clicked.connect(apply_selected_template)
        base_template_combo.currentIndexChanged.connect(lambda _: update_base_template_preview())
        apply_base_template_button.clicked.connect(apply_base_step_template)
        context_template_combo.currentIndexChanged.connect(lambda _: update_context_template_preview())
        apply_context_template_button.clicked.connect(apply_context_step_template)
        presentation_template_combo.currentIndexChanged.connect(lambda _: update_presentation_template_preview())
        apply_presentation_template_button.clicked.connect(apply_presentation_step_template)
        variant_sizes_button.selectionChanged.connect(
            lambda: (update_variant_summary(), sync_price_mode_suggestion())
        )
        variant_colors_button.selectionChanged.connect(update_variant_summary)
        auto_name_checkbox.toggled.connect(
            lambda checked: (
                auto_name_enabled.__setitem__("value", bool(checked)),
                sync_name_suggestion(force=bool(checked)),
            )
        )
        generate_name_button.clicked.connect(lambda: sync_name_suggestion(force=True))
        nombre_input.textEdited.connect(handle_name_manual_edit)
        marca_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
        tipo_pieza_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
        atributo_combo.currentTextChanged.connect(lambda _: sync_name_suggestion())
        genero_input.currentTextChanged.connect(lambda _: sync_name_suggestion())
        escuela_combo.currentTextChanged.connect(lambda _: (update_final_name_preview(), update_capture_summary()))
        tipo_prenda_combo.currentTextChanged.connect(
            lambda _: (
                update_final_name_preview(),
                update_capture_summary(),
                update_presentation_template_suggestion(),
                sync_price_mode_suggestion(),
            )
        )
        tipo_pieza_combo.currentTextChanged.connect(
            lambda _: (
                update_final_name_preview(),
                update_capture_summary(),
                update_presentation_template_suggestion(),
                sync_price_mode_suggestion(),
            )
        )
        nivel_combo.currentTextChanged.connect(
            lambda _: (update_presentation_template_suggestion(), sync_price_mode_suggestion())
        )
        genero_input.currentTextChanged.connect(
            lambda _: (update_presentation_template_suggestion(), sync_price_mode_suggestion())
        )
        price_mode_combo.currentIndexChanged.connect(
            lambda _: (
                price_mode_state.__setitem__("manual_override", True),
                update_price_inputs_ui(),
                update_capture_summary(),
            )
        )
        configure_prices_button.clicked.connect(open_price_configuration_dialog)
        variant_price_input.textChanged.connect(lambda _: update_capture_summary())
        variant_stock_spin.valueChanged.connect(lambda _: update_capture_summary())

        if product_initial:
            self._set_combo_value(categoria_combo, product_initial["categoria_id"])
            self._set_combo_value(marca_combo, product_initial["marca_id"])
            nombre_input.setText(str(product_initial["nombre_base"]))
            descripcion_input.setPlainText(str(product_initial["descripcion"]))
            set_editable_combo_text(escuela_combo, str(product_initial["escuela"]))
            set_editable_combo_text(tipo_prenda_combo, str(product_initial["tipo_prenda"]))
            set_editable_combo_text(tipo_pieza_combo, str(product_initial["tipo_pieza"]))
            set_editable_combo_text(atributo_combo, str(product_initial["atributo"]))
            set_editable_combo_text(nivel_combo, str(product_initial["nivel_educativo"]))
            set_editable_combo_text(genero_input, str(product_initial["genero"]))
            set_editable_combo_text(escudo_input, str(product_initial["escudo"]))
            set_editable_combo_text(ubicacion_input, str(product_initial["ubicacion"]))
            auto_name_checkbox.setChecked(False)
            auto_name_enabled["value"] = False

        ensure_uniform_category()
        sync_name_suggestion(force=bool(initial is None and not nombre_input.text().strip()))
        update_final_name_preview()
        update_capture_summary()
        update_context_inheritance_hint()
        update_presentation_template_suggestion()
        sync_price_mode_suggestion(force=True)

        template_row = QHBoxLayout()
        template_row.setSpacing(10)
        template_row.addWidget(template_combo, 1)
        template_row.addWidget(apply_template_button)
        base_template_row = QHBoxLayout()
        base_template_row.setSpacing(10)
        base_template_row.addWidget(base_template_combo, 1)
        base_template_row.addWidget(apply_base_template_button)
        context_template_row = QHBoxLayout()
        context_template_row.setSpacing(10)
        context_template_row.addWidget(context_template_combo, 1)
        context_template_row.addWidget(apply_context_template_button)
        presentation_template_row = QHBoxLayout()
        presentation_template_row.setSpacing(10)
        presentation_template_row.addWidget(presentation_template_combo, 1)
        presentation_template_row.addWidget(apply_presentation_template_button)
        marca_row = QHBoxLayout()
        marca_row.setSpacing(10)
        marca_row.addWidget(marca_combo)
        marca_row.addWidget(add_brand_button)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_row.addWidget(nombre_input, 1)
        name_row.addWidget(auto_name_checkbox)
        name_row.addWidget(generate_name_button)
        template_box = QGroupBox("Paso 1 · Base")
        template_box.setObjectName("infoCard")
        template_box_layout = QVBoxLayout()
        template_box_layout.setContentsMargins(16, 18, 16, 16)
        template_box_layout.setSpacing(14)
        template_hint = QLabel(
            "Empieza por plantilla, marca y nombre base. La categoria se maneja internamente como Uniformes."
        )
        template_hint.setWordWrap(True)
        template_hint.setObjectName("subtleLine")
        base_templates_panel = QFrame()
        base_templates_panel.setObjectName("infoCard")
        base_templates_layout = QFormLayout()
        base_templates_layout.setContentsMargins(14, 14, 14, 14)
        base_templates_layout.setSpacing(10)
        base_templates_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        base_templates_layout.addRow("Plantilla global", template_row)
        base_templates_layout.addRow("Vista global", template_preview_card)
        base_templates_layout.addRow("Plantilla base", base_template_row)
        base_templates_layout.addRow("Resumen base", base_template_preview_card)
        base_templates_panel.setLayout(base_templates_layout)
        base_fields_panel = QFrame()
        base_fields_panel.setObjectName("infoCard")
        base_fields_layout = QGridLayout()
        base_fields_layout.setContentsMargins(14, 14, 14, 14)
        base_fields_layout.setHorizontalSpacing(12)
        base_fields_layout.setVerticalSpacing(10)
        base_fields_layout.addWidget(QLabel("Categoria"), 0, 0)
        base_fields_layout.addWidget(uniform_category_label, 0, 1)
        base_fields_layout.addWidget(QLabel("Marca"), 0, 2)
        base_fields_layout.addLayout(marca_row, 0, 3)
        base_fields_layout.addWidget(QLabel("Nombre base"), 1, 0)
        base_fields_layout.addLayout(name_row, 1, 1, 1, 3)
        base_fields_layout.addWidget(QLabel("Descripcion"), 2, 0)
        base_fields_layout.addWidget(descripcion_input, 2, 1, 1, 3)
        base_fields_layout.addWidget(final_name_preview, 3, 0, 1, 4)
        base_fields_layout.setColumnStretch(1, 3)
        base_fields_layout.setColumnStretch(3, 3)
        base_fields_panel.setLayout(base_fields_layout)
        base_content_row = QHBoxLayout()
        base_content_row.setSpacing(14)
        base_content_row.addWidget(base_templates_panel, 5)
        base_content_row.addWidget(base_fields_panel, 6)
        template_box_layout.addWidget(template_hint)
        template_box_layout.addLayout(base_content_row)
        template_box_layout.addStretch(1)
        template_box.setLayout(template_box_layout)

        context_box = QGroupBox("Paso 2 · Contexto")
        context_box.setObjectName("infoCard")
        context_layout = QVBoxLayout()
        context_layout.setContentsMargins(16, 18, 16, 16)
        context_layout.setSpacing(14)
        context_hint = QLabel(
            "Define el contexto escolar del producto. Aqui decides tipo de uniforme, nivel, pieza y detalles."
        )
        context_hint.setWordWrap(True)
        context_hint.setObjectName("subtleLine")
        context_template_panel = QFrame()
        context_template_panel.setObjectName("infoCard")
        context_template_layout = QFormLayout()
        context_template_layout.setContentsMargins(14, 14, 14, 14)
        context_template_layout.setSpacing(10)
        context_template_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        context_template_layout.addRow("Plantilla contexto", context_template_row)
        context_template_layout.addRow("Resumen contexto", context_template_preview_card)
        context_template_panel.setLayout(context_template_layout)
        context_fields_panel = QFrame()
        context_fields_panel.setObjectName("infoCard")
        context_fields_layout = QGridLayout()
        context_fields_layout.setContentsMargins(14, 14, 14, 14)
        context_fields_layout.setHorizontalSpacing(12)
        context_fields_layout.setVerticalSpacing(10)
        context_fields_layout.addWidget(QLabel("Escuela"), 0, 0)
        context_fields_layout.addWidget(escuela_combo, 0, 1, 1, 3)
        context_fields_layout.addWidget(QLabel("Tipo de uniforme"), 1, 0)
        context_fields_layout.addWidget(tipo_prenda_combo, 1, 1)
        context_fields_layout.addWidget(QLabel("Tipo pieza"), 1, 2)
        context_fields_layout.addWidget(tipo_pieza_combo, 1, 3)
        context_fields_layout.addWidget(QLabel("Atributo"), 2, 0)
        context_fields_layout.addWidget(atributo_combo, 2, 1)
        context_fields_layout.addWidget(QLabel("Nivel educativo"), 2, 2)
        context_fields_layout.addWidget(nivel_combo, 2, 3)
        context_fields_layout.addWidget(QLabel("Genero"), 3, 0)
        context_fields_layout.addWidget(genero_input, 3, 1)
        context_fields_layout.addWidget(QLabel("Escudo"), 3, 2)
        context_fields_layout.addWidget(escudo_input, 3, 3)
        context_fields_layout.addWidget(QLabel("Ubicacion"), 4, 0)
        context_fields_layout.addWidget(ubicacion_input, 4, 1)
        context_fields_layout.setColumnStretch(1, 3)
        context_fields_layout.setColumnStretch(3, 3)
        context_fields_panel.setLayout(context_fields_layout)
        context_content_row = QHBoxLayout()
        context_content_row.setSpacing(14)
        context_content_row.addWidget(context_template_panel, 4)
        context_content_row.addWidget(context_fields_panel, 7)
        context_layout.addWidget(context_hint)
        context_layout.addLayout(context_content_row)
        context_layout.addStretch(1)
        context_box.setLayout(context_layout)

        variants_box = QGroupBox("Paso 3 · Presentaciones")
        variants_box.setObjectName("infoCard")
        variants_layout = QGridLayout()
        variants_layout.setContentsMargins(16, 18, 16, 16)
        variants_layout.setHorizontalSpacing(12)
        variants_layout.setVerticalSpacing(10)
        variants_hint = QLabel(
            "Define tallas, colores y precio. Aqui decides si el producto creara presentaciones por lote despues de guardar."
        )
        variants_hint.setWordWrap(True)
        variants_hint.setObjectName("subtleLine")
        variants_layout.addWidget(variants_hint, 0, 0, 1, 4)
        variants_layout.addWidget(QLabel("Plantilla present."), 1, 0)
        variants_layout.addLayout(presentation_template_row, 1, 1, 1, 3)
        variants_layout.addWidget(presentation_template_preview_card, 2, 0, 1, 4)
        variants_layout.addWidget(QLabel("Tallas"), 3, 0)
        variants_layout.addWidget(variant_sizes_button, 3, 1)
        variants_layout.addWidget(QLabel("Colores"), 3, 2)
        variants_layout.addWidget(variant_colors_button, 3, 3)
        variants_layout.addWidget(variant_sizes_summary, 4, 0, 1, 2)
        variants_layout.addWidget(variant_colors_summary, 4, 2, 1, 2)
        variants_layout.addWidget(QLabel("Modo precio"), 5, 0)
        variants_layout.addWidget(price_mode_combo, 5, 1, 1, 2)
        variants_layout.addWidget(configure_prices_button, 5, 3)
        variants_layout.addWidget(price_mode_hint, 6, 0, 1, 4)
        variants_layout.addWidget(price_strategy_summary, 7, 0, 1, 4)
        variants_layout.addWidget(QLabel("Costo ref."), 8, 0)
        variants_layout.addWidget(variant_cost_input, 8, 1)
        variants_layout.addWidget(QLabel("Stock inicial"), 8, 2)
        variants_layout.addWidget(variant_stock_spin, 8, 3)
        variants_layout.addWidget(variant_count_summary, 9, 0, 1, 4)
        variants_box.setLayout(variants_layout)

        review_box = QGroupBox("Paso 4 · Revisar")
        review_box.setObjectName("infoCard")
        review_layout = QVBoxLayout()
        review_layout.setContentsMargins(16, 18, 16, 16)
        review_layout.setSpacing(10)
        review_hint = QLabel(
            "Revisa el resumen final. Si algo no cuadra, vuelve al paso correspondiente antes de guardar."
        )
        review_hint.setWordWrap(True)
        review_hint.setObjectName("subtleLine")
        review_details_label = QLabel("Aun no hay suficiente informacion para revisar.")
        review_details_label.setWordWrap(True)
        review_details_label.setTextFormat(Qt.TextFormat.RichText)
        review_details_label.setObjectName("templatePreviewLabel")
        review_layout.addWidget(review_hint)
        review_layout.addWidget(review_details_label)
        review_layout.addStretch(1)
        review_box.setLayout(review_layout)

        def update_review_details() -> None:
            selected_sizes = variant_sizes_button.selected_labels()
            selected_colors = variant_colors_button.selected_labels()
            _, missing_prices, price_summary = build_price_assignment()
            total_variants = max(1, len(selected_sizes) or 1) * max(1, len(selected_colors) or 1)
            sku_summary = format_sku_preview(total_variants)
            review_notes: list[str] = []
            if categoria_combo.currentData() is None:
                review_notes.append("Falta categoria.")
            if marca_combo.currentData() is None:
                review_notes.append("Falta marca.")
            if not nombre_input.text().strip():
                review_notes.append("Falta nombre base.")
            if missing_prices:
                review_notes.append(
                    "Hay precios pendientes en: " + ", ".join(missing_prices) + "."
                )
            review_details_label.setText(
                "<div><b>Revision final</b></div>"
                f"<div><b>Producto:</b> {build_display_name_preview(nombre_input.text().strip())}</div>"
                f"<div><b>Categoria / marca:</b> Uniformes / {marca_combo.currentText().strip() or '-'}</div>"
                f"<div><b>Contexto:</b> {' | '.join(value for value in [escuela_combo.currentText().strip(), tipo_prenda_combo.currentText().strip(), tipo_pieza_combo.currentText().strip(), atributo_combo.currentText().strip()] if value) or 'Sin contexto adicional'}</div>"
                f"<div><b>Tallas:</b> {preview_values(selected_sizes)}</div>"
                f"<div><b>Colores:</b> {preview_values(selected_colors, max_items=5)}</div>"
                f"<div><b>SKU previstos:</b> {sku_summary}</div>"
                "<div><b>QR:</b> Quedara pendiente. Puedes generarlo al terminar el lote o despues desde Inventario.</div>"
                f"<div><b>Precio / stock:</b> {price_summary} / {variant_stock_spin.value()}</div>"
                f"<div style='color:#7e3a22;'>{' | '.join(review_notes) if review_notes else 'Todo listo para guardar.'}</div>"
            )

        step_stack = QStackedWidget()
        step_pages: list[QWidget] = []
        for box in (template_box, context_box, variants_box, review_box):
            page = QWidget()
            page_layout = QVBoxLayout()
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)
            page_layout.addWidget(box)
            page.setLayout(page_layout)
            step_stack.addWidget(page)
            step_pages.append(page)

        summary_box = QGroupBox("Resumen")
        summary_box.setObjectName("infoCard")
        summary_box.setMinimumWidth(300)
        summary_box.setMaximumWidth(360)
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(16, 18, 16, 16)
        summary_layout.setSpacing(10)
        summary_hint = QLabel(
            "Este panel se actualiza en tiempo real mientras avanzas por los pasos."
        )
        summary_hint.setWordWrap(True)
        summary_hint.setObjectName("subtleLine")
        summary_layout.addWidget(summary_hint)
        summary_layout.addWidget(capture_summary_card)
        summary_layout.addStretch(1)
        summary_box.setLayout(summary_layout)

        step_titles = ["1 Base", "2 Contexto", "3 Presentaciones", "4 Revisar"]
        step_buttons: list[QPushButton] = []
        stepper_row = QHBoxLayout()
        stepper_row.setSpacing(8)
        current_step = {"index": 0}

        def validate_step(step_index: int) -> bool:
            if step_index == 0:
                if categoria_combo.currentData() is None:
                    QMessageBox.warning(dialog, "Paso 1 incompleto", "Selecciona una categoria antes de continuar.")
                    return False
                if marca_combo.currentData() is None:
                    QMessageBox.warning(dialog, "Paso 1 incompleto", "Selecciona una marca antes de continuar.")
                    return False
                if not nombre_input.text().strip():
                    QMessageBox.warning(dialog, "Paso 1 incompleto", "Captura o genera el nombre base antes de continuar.")
                    return False
            if step_index == 2:
                has_variant_intent = bool(variant_sizes_button.selected_labels() or variant_colors_button.selected_labels())
                _, missing_prices, _ = build_price_assignment()
                if has_variant_intent and missing_prices:
                    QMessageBox.warning(
                        dialog,
                        "Paso 3 incompleto",
                        "Todavia faltan precios para algunas tallas o bloques. Revísalos antes de continuar.",
                    )
                    return False
            return True

        def refresh_step_ui() -> None:
            for index, button in enumerate(step_buttons):
                is_active = index == current_step["index"]
                button.setProperty("active", "true" if is_active else "false")
                button.style().unpolish(button)
                button.style().polish(button)
            previous_button.setEnabled(current_step["index"] > 0)
            next_button.setVisible(current_step["index"] < len(step_titles) - 1)
            save_button.setVisible(current_step["index"] == len(step_titles) - 1)
            step_stack.setCurrentIndex(current_step["index"])
            update_review_details()

        def go_to_step(target_index: int) -> None:
            if target_index > current_step["index"] and not validate_step(current_step["index"]):
                return
            current_step["index"] = max(0, min(target_index, len(step_titles) - 1))
            refresh_step_ui()

        for index, title in enumerate(step_titles):
            button = QPushButton(title)
            button.setObjectName("stepButton")
            button.clicked.connect(lambda _checked=False, target=index: go_to_step(target))
            step_buttons.append(button)
            stepper_row.addWidget(button)
        stepper_row.addStretch(1)

        main_content_row = QHBoxLayout()
        main_content_row.setSpacing(14)
        main_content_row.addWidget(step_stack, 7)
        main_content_row.addWidget(summary_box, 4)

        navigation_row = QHBoxLayout()
        navigation_row.setSpacing(10)
        previous_button = QPushButton("Anterior")
        next_button = QPushButton("Siguiente")
        save_button = QPushButton("Guardar")
        cancel_button = QPushButton("Cancelar")
        previous_button.clicked.connect(lambda: go_to_step(current_step["index"] - 1))
        next_button.clicked.connect(lambda: go_to_step(current_step["index"] + 1))
        save_button.clicked.connect(
            lambda: dialog.accept() if validate_step(0) and validate_step(2) else None
        )
        cancel_button.clicked.connect(dialog.reject)
        navigation_row.addWidget(previous_button)
        navigation_row.addWidget(next_button)
        navigation_row.addStretch(1)
        navigation_row.addWidget(cancel_button)
        navigation_row.addWidget(save_button)

        refresh_step_ui()
        layout.addWidget(live_name_card)
        layout.addLayout(stepper_row)
        layout.addLayout(main_content_row)
        layout.addLayout(navigation_row)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        prices_by_size, _, price_summary = build_price_assignment()
        return {
            "categoria_id": categoria_combo.currentData(),
            "marca_id": marca_combo.currentData(),
            "nombre": nombre_input.text().strip(),
            "escuela": escuela_combo.currentText().strip(),
            "tipo_prenda": tipo_prenda_combo.currentText().strip(),
            "tipo_pieza": tipo_pieza_combo.currentText().strip(),
            "atributo": atributo_combo.currentText().strip(),
            "nivel_educativo": nivel_combo.currentText().strip(),
            "genero": genero_input.currentText().strip(),
            "escudo": escudo_input.currentText().strip(),
            "ubicacion": ubicacion_input.currentText().strip(),
            "descripcion": descripcion_input.toPlainText().strip(),
            "tallas": variant_sizes_button.selected_labels(),
            "colores": variant_colors_button.selected_labels(),
            "precio_variante": variant_price_input.text().strip(),
            "precio_modo": str(price_mode_combo.currentData() or "single"),
            "precios_por_talla": prices_by_size,
            "resumen_precio": price_summary,
            "costo_variante": variant_cost_input.text().strip(),
            "stock_inicial_variante": variant_stock_spin.value(),
        }

    def _prompt_batch_variant_data(
        self,
        *,
        sizes: list[str],
        colors: list[str],
        initial_price: str = "",
        pricing_mode: str = "single",
        prices_by_size: dict[str, str] | None = None,
        price_summary: str = "",
        initial_cost: str = "",
        initial_stock: int = 0,
    ) -> dict[str, object] | None:
        normalized_sizes = [value for value in sizes if str(value).strip()] or [DEFAULT_VARIANT_SIZE]
        normalized_colors = [value for value in colors if str(value).strip()] or [DEFAULT_VARIANT_COLOR]
        total_variants = len(normalized_sizes) * len(normalized_colors)

        dialog, layout = self._create_modal_dialog(
            "Presentaciones por lote",
            "Confirma las tallas, colores y estructura de precio para crear las presentaciones del producto en una sola operacion.",
            width=720,
        )
        form = QFormLayout()
        sizes_label = QLabel(", ".join(normalized_sizes))
        sizes_label.setWordWrap(True)
        sizes_label.setObjectName("subtleLine")
        colors_label = QLabel(", ".join(normalized_colors))
        colors_label.setWordWrap(True)
        colors_label.setObjectName("subtleLine")
        summary_label = QLabel(f"Se crearan {total_variants} presentaciones.")
        summary_label.setObjectName("subtleLine")
        sku_summary_label = QLabel(self._format_sku_preview(total_variants))
        sku_summary_label.setWordWrap(True)
        sku_summary_label.setObjectName("subtleLine")
        pricing_map = {
            str(size).strip(): str(price).strip()
            for size, price in (prices_by_size or {}).items()
            if str(size).strip() and str(price).strip()
        }
        effective_price_summary = price_summary.strip() or (initial_price.strip() if initial_price.strip() else "-")
        price_label = QLabel(effective_price_summary)
        price_label.setWordWrap(True)
        price_label.setObjectName("subtleLine")
        price_mode_label = QLabel(
            {
                "single": "Precio unico",
                "blocks": "Precio por bloques",
                "manual": "Precio manual por talla",
            }.get(pricing_mode, "Precio unico")
        )
        price_mode_label.setObjectName("subtleLine")
        cost_input = QLineEdit()
        cost_input.setPlaceholderText("Opcional")
        cost_input.setText(initial_cost)
        stock_spin = QSpinBox()
        stock_spin.setRange(0, 10000)
        stock_spin.setValue(initial_stock)
        form.addRow("Tallas", sizes_label)
        form.addRow("Colores", colors_label)
        form.addRow("", summary_label)
        form.addRow("SKU previstos", sku_summary_label)
        form.addRow("Modo precio", price_mode_label)
        form.addRow("Precio venta", price_label)
        form.addRow("Costo ref.", cost_input)
        form.addRow("Stock inicial", stock_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "tallas": normalized_sizes,
            "colores": normalized_colors,
            "precio": initial_price.strip(),
            "precio_modo": pricing_mode,
            "precios_por_talla": pricing_map,
            "resumen_precio": effective_price_summary,
            "costo": cost_input.text().strip(),
            "stock_inicial": stock_spin.value(),
        }

    def _create_variants_batch(
        self,
        *,
        product_id: int,
        sizes: list[str],
        colors: list[str],
        price_text: str,
        prices_by_size: dict[str, str] | None = None,
        cost_text: str = "",
        stock_initial: int = 0,
    ) -> tuple[int, int | None, list[str], list[str]]:
        normalized_sizes = [value.strip() for value in sizes if value and value.strip()] or [DEFAULT_VARIANT_SIZE]
        normalized_colors = [value.strip() for value in colors if value and value.strip()] or [DEFAULT_VARIANT_COLOR]
        try:
            default_price = Decimal(price_text) if str(price_text).strip() else None
            cost = Decimal(cost_text) if cost_text else None
        except InvalidOperation as exc:
            raise ValueError("Precio o costo con formato invalido.") from exc
        normalized_price_map: dict[str, Decimal] = {}
        for size, raw_price in (prices_by_size or {}).items():
            size_key = str(size).strip()
            price_value = str(raw_price).strip()
            if not size_key or not price_value:
                continue
            try:
                normalized_price_map[size_key] = Decimal(price_value)
            except InvalidOperation as exc:
                raise ValueError(f"Precio invalido para talla {size_key}.") from exc

        created_count = 0
        first_variant_id: int | None = None
        errors: list[str] = []
        created_skus: list[str] = []
        with get_session() as session:
            user = session.get(Usuario, self.user_id)
            producto = session.get(Producto, int(product_id))
            if user is None or producto is None:
                raise ValueError("Usuario o producto no encontrado.")
            for size in normalized_sizes:
                for color in normalized_colors:
                    try:
                        price = normalized_price_map.get(size, default_price)
                        if price is None:
                            raise ValueError(f"Falta precio para la talla {size}.")
                        with session.begin_nested():
                            presentacion = CatalogService.crear_variante(
                                session=session,
                                usuario=user,
                                producto=producto,
                                sku=None,
                                talla=size,
                                color=color,
                                precio_venta=price,
                                costo_referencia=cost,
                                stock_inicial=stock_initial,
                            )
                            session.flush()
                            created_count += 1
                            created_skus.append(str(presentacion.sku))
                            if first_variant_id is None:
                                first_variant_id = int(presentacion.id)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{size} / {color}: {exc}")
            if created_count == 0:
                raise ValueError("No se pudo crear ninguna presentacion.")
            session.commit()
        return created_count, first_variant_id, errors, created_skus

    def _prompt_variant_data(
        self,
        initial: dict[str, object] | None = None,
        include_stock: bool = False,
        default_product_id: int | None = None,
    ) -> dict[str, object] | None:
        legacy_choices = load_legacy_config_choices()
        with get_session() as session:
            productos = [
                {
                    "id": producto.id,
                    "nombre": producto.nombre,
                    "nombre_base": producto.nombre_base,
                    "marca": producto.marca.nombre,
                    "escuela": producto.escuela.nombre if producto.escuela else "",
                    "tipo_prenda": producto.tipo_prenda.nombre if producto.tipo_prenda else "",
                    "tipo_pieza": producto.tipo_pieza.nombre if producto.tipo_pieza else "",
                }
                for producto in session.scalars(
                    select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre)
                ).all()
            ]

        if not productos:
            raise ValueError("Primero necesitas al menos un producto activo.")

        dialog, layout = self._create_modal_dialog(
            "Presentacion",
            "Cada presentacion representa una combinacion vendible de producto, talla y color con su propio SKU, precio y stock.",
        )
        form = QFormLayout()
        producto_combo = QComboBox()
        product_map = {producto["id"]: producto for producto in productos}
        for producto in productos:
            context = " | ".join(
                part for part in (producto["escuela"], producto["tipo_prenda"], producto["tipo_pieza"]) if part
            )
            if context:
                producto_combo.addItem(
                    f"{producto['nombre_base']} | {context} | {producto['marca']}",
                    producto["id"],
                )
            else:
                producto_combo.addItem(f"{producto['nombre_base']} | {producto['marca']}", producto["id"])
        sku_input = QLineEdit()
        sku_input.setPlaceholderText("Se genera automaticamente si lo dejas vacio")
        talla_combo = QComboBox()
        talla_combo.setEditable(True)
        talla_combo.addItems(merge_choice_lists(legacy_choices.get("TALLAS", []), COMMON_SIZES, [DEFAULT_VARIANT_SIZE]))
        if talla_combo.lineEdit() is not None:
            talla_combo.lineEdit().setPlaceholderText("Selecciona o escribe una talla")
        color_combo = QComboBox()
        color_combo.setEditable(True)
        color_combo.addItems(merge_choice_lists(legacy_choices.get("COLORES", []), COMMON_COLORS, [DEFAULT_VARIANT_COLOR]))
        if color_combo.lineEdit() is not None:
            color_combo.lineEdit().setPlaceholderText("Selecciona o escribe un color")
        precio_input = QLineEdit()
        costo_input = QLineEdit()
        stock_spin = QSpinBox()
        stock_spin.setRange(0, 10000)
        sku_hint = QLabel()
        sku_hint.setObjectName("subtleLine")
        auto_sku_enabled = {"value": True}
        last_auto_sku = {"value": ""}

        def refresh_sku_suggestion() -> None:
            producto_id = producto_combo.currentData()
            talla = talla_combo.currentText().strip()
            color = color_combo.currentText().strip()
            producto_info = product_map.get(producto_id)
            if producto_info is None or not talla or not color:
                sku_hint.setText("Completa producto, talla y color para sugerir un SKU.")
                return

            class _FakeMarca:
                def __init__(self, nombre: str) -> None:
                    self.nombre = nombre

            class _FakeProducto:
                def __init__(self, nombre: str, marca_nombre: str) -> None:
                    self.nombre = nombre
                    self.marca = _FakeMarca(marca_nombre)

            fake_producto = _FakeProducto(producto_info["nombre_base"], producto_info["marca"])
            with get_session() as session:
                suggested = CatalogService.generar_sku_sugerido(
                    session=session,
                    producto=fake_producto,  # type: ignore[arg-type]
                    talla=talla,
                    color=color,
                    excluding_variant_id=int(initial["variante_id"]) if initial else None,
                )
            previous_auto = last_auto_sku["value"]
            last_auto_sku["value"] = suggested
            sku_hint.setText(f"SKU sugerido: {suggested}")
            if auto_sku_enabled["value"] or sku_input.text().strip().upper() == previous_auto:
                auto_sku_enabled["value"] = True
                sku_input.setText(suggested)

        def mark_manual_override(value: str) -> None:
            auto_sku_enabled["value"] = value.strip().upper() == last_auto_sku["value"]

        if initial:
            self._set_combo_value(producto_combo, initial["producto_id"])
            sku_input.setText(str(initial["sku"]))
            last_auto_sku["value"] = str(initial["sku"]).strip().upper()
            talla_text = str(initial["talla"])
            talla_index = talla_combo.findText(talla_text)
            if talla_index >= 0:
                talla_combo.setCurrentIndex(talla_index)
            else:
                talla_combo.setEditText(talla_text)
            color_text = str(initial["color"])
            color_index = color_combo.findText(color_text)
            if color_index >= 0:
                color_combo.setCurrentIndex(color_index)
            else:
                color_combo.setEditText(color_text)
            precio_input.setText(str(initial["precio_venta"]))
            costo_input.setText("" if initial["costo_referencia"] is None else str(initial["costo_referencia"]))
            sku_hint.setText(f"SKU actual: {initial['sku']}")
        elif default_product_id is not None:
            self._set_combo_value(producto_combo, default_product_id)
            sku_hint.setText("Completa talla y color para sugerir un SKU.")
        else:
            sku_hint.setText("Completa producto, talla y color para sugerir un SKU.")

        form.addRow("Producto", producto_combo)
        form.addRow("SKU", sku_input)
        form.addRow("", sku_hint)
        form.addRow("Talla", talla_combo)
        form.addRow("Color", color_combo)
        form.addRow("Precio venta", precio_input)
        form.addRow("Costo referencia", costo_input)
        if include_stock:
            form.addRow("Stock inicial", stock_spin)

        producto_combo.currentIndexChanged.connect(lambda _: refresh_sku_suggestion())
        talla_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
        color_combo.currentTextChanged.connect(lambda _: refresh_sku_suggestion())
        sku_input.textEdited.connect(mark_manual_override)
        if not initial:
            refresh_sku_suggestion()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "producto_id": producto_combo.currentData(),
            "sku": sku_input.text().strip(),
            "talla": talla_combo.currentText().strip(),
            "color": color_combo.currentText().strip(),
            "precio": precio_input.text().strip(),
            "costo": costo_input.text().strip(),
            "stock_inicial": stock_spin.value(),
        }

    @staticmethod
    def _resolve_named_taxonomy(session, model, raw_name: str):
        normalized = raw_name.strip()
        if not normalized:
            return None
        existing = session.scalar(select(model).where(model.nombre == normalized))
        if existing is not None:
            return existing
        created = model(nombre=normalized)
        session.add(created)
        session.flush()
        return created

    def _prompt_purchase_data(self) -> dict[str, object] | None:
        with get_session() as session:
            proveedores = [
                (proveedor.id, proveedor.nombre)
                for proveedor in session.scalars(
                    select(Proveedor).where(Proveedor.activo.is_(True)).order_by(Proveedor.nombre)
                ).all()
            ]
            variantes = [
                (variante.id, variante.sku, variante.producto.nombre, variante.stock_actual)
                for variante in session.scalars(
                    select(Variante).where(Variante.activo.is_(True)).order_by(Variante.sku)
                ).all()
            ]

        if not proveedores or not variantes:
            raise ValueError("Necesitas al menos un proveedor activo y una presentacion activa.")

        dialog, layout = self._create_modal_dialog(
            "Registrar entrada",
            "Usa esta ventana para ingresar nueva mercancia de una presentacion existente.",
        )
        form = QFormLayout()
        proveedor_combo = QComboBox()
        for proveedor_id, proveedor_nombre in proveedores:
            proveedor_combo.addItem(proveedor_nombre, proveedor_id)
        presentacion_combo = QComboBox()
        for variante_id, sku, producto_nombre, stock_actual in variantes:
            presentacion_combo.addItem(
                f"{sku} | {producto_nombre} | stock {stock_actual}",
                variante_id,
            )
        self._set_combo_value(presentacion_combo, self.inventory_variant_combo.currentData())
        cantidad_spin = QSpinBox()
        cantidad_spin.setRange(1, 1000)
        costo_input = QLineEdit()
        costo_input.setPlaceholderText("550.00")
        documento_input = QLineEdit()
        documento_input.setPlaceholderText("COMP-0001")
        form.addRow("Proveedor", proveedor_combo)
        form.addRow("Presentacion", presentacion_combo)
        form.addRow("Cantidad", cantidad_spin)
        form.addRow("Costo unitario", costo_input)
        form.addRow("Documento", documento_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "proveedor_id": proveedor_combo.currentData(),
            "variante_id": presentacion_combo.currentData(),
            "cantidad": cantidad_spin.value(),
            "costo": costo_input.text().strip(),
            "documento": documento_input.text().strip(),
        }

    def _prompt_inventory_adjustment_data(self) -> dict[str, object] | None:
        with get_session() as session:
            variantes = [
                (variante.id, variante.sku, variante.producto.nombre, variante.stock_actual)
                for variante in session.scalars(
                    select(Variante).where(Variante.activo.is_(True)).order_by(Variante.sku)
                ).all()
            ]

        if not variantes:
            raise ValueError("No hay presentaciones activas disponibles para ajustar.")

        dialog, layout = self._create_modal_dialog(
            "Ajuste manual de inventario",
            "Captura el stock final deseado. El sistema calcula automaticamente la diferencia contra el stock actual.",
        )
        form = QFormLayout()
        presentacion_combo = QComboBox()
        stock_map: dict[int, int] = {}
        for variante_id, sku, producto_nombre, stock_actual in variantes:
            stock_map[int(variante_id)] = int(stock_actual)
            presentacion_combo.addItem(
                f"{sku} | {producto_nombre} | stock {stock_actual}",
                variante_id,
            )
        self._set_combo_value(presentacion_combo, self.inventory_variant_combo.currentData())
        stock_actual_label = QLabel()
        stock_actual_label.setObjectName("analyticsLine")
        stock_final_spin = QSpinBox()
        stock_final_spin.setRange(0, 100000)
        stock_final_spin.setAccelerated(True)
        diferencia_label = QLabel()
        diferencia_label.setObjectName("subtleLine")
        referencia_input = QLineEdit()
        referencia_input.setPlaceholderText("AJUSTE-0001")
        observacion_input = QTextEdit()
        observacion_input.setFixedHeight(90)
        observacion_input.setPlaceholderText("Motivo del ajuste")

        def refresh_adjustment_labels() -> None:
            variante_id = presentacion_combo.currentData()
            current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
            stock_actual_label.setText(f"Stock actual: {current_stock}")
            stock_final_spin.blockSignals(True)
            stock_final_spin.setValue(current_stock)
            stock_final_spin.blockSignals(False)
            diferencia_label.setText("Sin cambios pendientes.")

        def refresh_difference_label() -> None:
            variante_id = presentacion_combo.currentData()
            current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
            target_stock = stock_final_spin.value()
            delta = target_stock - current_stock
            if delta == 0:
                diferencia_label.setText("Sin cambios pendientes.")
            elif delta > 0:
                diferencia_label.setText(f"Se agregaran {delta} unidades para dejar stock en {target_stock}.")
            else:
                diferencia_label.setText(f"Se descontaran {abs(delta)} unidades para dejar stock en {target_stock}.")

        presentacion_combo.currentIndexChanged.connect(lambda _: refresh_adjustment_labels())
        stock_final_spin.valueChanged.connect(lambda _: refresh_difference_label())
        refresh_adjustment_labels()

        form.addRow("Presentacion", presentacion_combo)
        form.addRow("Stock actual", stock_actual_label)
        form.addRow("Stock final", stock_final_spin)
        form.addRow("Impacto", diferencia_label)
        form.addRow("Referencia", referencia_input)
        form.addRow("Observacion", observacion_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        variante_id = presentacion_combo.currentData()
        current_stock = stock_map.get(int(variante_id), 0) if variante_id is not None else 0
        target_stock = stock_final_spin.value()
        return {
            "variante_id": variante_id,
            "cantidad": target_stock - current_stock,
            "stock_actual": current_stock,
            "stock_final": target_stock,
            "referencia": referencia_input.text().strip(),
            "observacion": observacion_input.toPlainText().strip(),
        }

    def _prompt_inventory_count_data(self) -> dict[str, object] | None:
        with get_session() as session:
            variantes = [
                (variante.id, variante.sku, variante.producto.nombre, variante.talla, variante.color, variante.stock_actual)
                for variante in session.scalars(select(Variante).order_by(Variante.sku)).all()
            ]

        if not variantes:
            raise ValueError("No hay presentaciones disponibles para conteo.")

        dialog, layout = self._create_modal_dialog(
            "Conteo fisico",
            "Captura el stock contado de cada presentacion. Solo se aplicaran filas con diferencia.",
            width=760,
        )
        referencia_input = QLineEdit()
        referencia_input.setPlaceholderText("CONTEO-0001")
        observacion_input = QLineEdit()
        observacion_input.setPlaceholderText("Conteo general de piso o almacen")

        header_form = QFormLayout()
        header_form.addRow("Referencia", referencia_input)
        header_form.addRow("Observacion", observacion_input)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["SKU", "Producto", "Talla", "Color", "Sistema", "Contado"])
        table.setObjectName("dataTable")
        table.verticalHeader().setVisible(False)
        table.setRowCount(len(variantes))

        selected_variant_id = self.inventory_variant_combo.currentData()
        selected_row_index = None
        for row_index, (variante_id, sku, producto_nombre, talla, color, stock_actual) in enumerate(variantes):
            values = [sku, producto_nombre, talla, color, stock_actual]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                table.setItem(row_index, column_index, item)
            contado_spin = QSpinBox()
            contado_spin.setRange(0, 100000)
            contado_spin.setValue(int(stock_actual))
            table.setCellWidget(row_index, 5, contado_spin)
            table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, variante_id)
            if selected_variant_id is not None and int(variante_id) == int(selected_variant_id):
                selected_row_index = row_index

        if selected_row_index is not None:
            table.setCurrentCell(selected_row_index, 0)
            table.selectRow(selected_row_index)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addLayout(header_form)
        layout.addWidget(table)
        layout.addWidget(buttons)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        conteos: list[dict[str, int]] = []
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item is None:
                continue
            variante_id = item.data(Qt.ItemDataRole.UserRole)
            system_stock_item = table.item(row_index, 4)
            counted_widget = table.cellWidget(row_index, 5)
            if variante_id is None or system_stock_item is None or not isinstance(counted_widget, QSpinBox):
                continue
            stock_sistema = int(system_stock_item.text())
            stock_contado = counted_widget.value()
            delta = stock_contado - stock_sistema
            if delta == 0:
                continue
            conteos.append(
                {
                    "variante_id": int(variante_id),
                    "stock_sistema": stock_sistema,
                    "stock_contado": stock_contado,
                    "delta": delta,
                }
            )

        return {
            "referencia": referencia_input.text().strip(),
            "observacion": observacion_input.text().strip(),
            "conteos": conteos,
        }

    @staticmethod
    def _generate_inventory_batch_reference(prefix: str = "AJL") -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{timestamp}-{uuid4().hex[:4].upper()}"

    def _prompt_inventory_bulk_adjustment_data(self) -> dict[str, object] | None:
        selected_ids = self._selected_inventory_variant_ids()
        filtered_rows = list(self.inventory_rows)
        if not selected_ids and not filtered_rows:
            raise ValueError("No hay presentaciones disponibles para ajuste masivo.")

        source_options: list[tuple[str, str, list[dict[str, object]]]] = []
        if selected_ids:
            selected_rows = [row for row in filtered_rows if int(row["variante_id"]) in set(selected_ids)]
            source_options.append(
                (f"Filas seleccionadas ({len(selected_rows)})", "SELECCION", selected_rows)
            )
        if filtered_rows:
            source_options.append(
                (f"Resultados filtrados ({len(filtered_rows)})", "FILTRADO", filtered_rows)
            )

        dialog, layout = self._create_modal_dialog(
            "Ajuste masivo de stock",
            "Aplica ajustes por lote sobre varias presentaciones. Cada fila genera su movimiento auditado.",
            width=980,
        )
        layout.setSpacing(8)
        header_grid = QGridLayout()
        header_grid.setHorizontalSpacing(8)
        header_grid.setVerticalSpacing(6)
        source_combo = QComboBox()
        source_payloads: dict[str, list[dict[str, object]]] = {}
        for label, code, rows in source_options:
            source_combo.addItem(label, code)
            source_payloads[code] = rows
        mode_combo = QComboBox()
        mode_combo.addItem("Stock final", "STOCK_FINAL")
        mode_combo.addItem("Diferencia (+/-)", "DELTA")
        reference_input = QLineEdit()
        reference_input.setText(self._generate_inventory_batch_reference())
        reference_input.setReadOnly(True)
        reference_input.setObjectName("inventoryFilterInput")
        motive_input = QLineEdit()
        motive_input.setPlaceholderText("Conteo general / correccion de lote")
        note_input = QLineEdit()
        note_input.setPlaceholderText("Observacion adicional")
        source_label = QLabel("Fuente")
        mode_label = QLabel("Tipo")
        reference_label = QLabel("Referencia")
        motive_label = QLabel("Motivo")
        note_label = QLabel("Observacion")
        for label in (source_label, mode_label, reference_label, motive_label, note_label):
            label.setObjectName("inventoryFilterLabel")
        header_grid.addWidget(source_label, 0, 0)
        header_grid.addWidget(source_combo, 0, 1)
        header_grid.addWidget(mode_label, 0, 2)
        header_grid.addWidget(mode_combo, 0, 3)
        header_grid.addWidget(reference_label, 1, 0)
        header_grid.addWidget(reference_input, 1, 1)
        header_grid.addWidget(motive_label, 1, 2)
        header_grid.addWidget(motive_input, 1, 3)
        header_grid.addWidget(note_label, 2, 0)
        header_grid.addWidget(note_input, 2, 1, 1, 3)
        header_grid.setColumnStretch(1, 1)
        header_grid.setColumnStretch(3, 1)

        quick_actions_row = QHBoxLayout()
        quick_actions_row.setSpacing(6)
        quick_value_spin = QSpinBox()
        quick_value_spin.setRange(-100000, 100000)
        quick_value_spin.setAccelerated(True)
        quick_apply_all_button = QPushButton("Aplicar a todas")
        quick_apply_selected_button = QPushButton("Aplicar a seleccionadas")
        quick_reset_button = QPushButton("Restablecer")
        for button in (quick_apply_all_button, quick_apply_selected_button, quick_reset_button):
            button.setObjectName("secondaryButton")
        quick_apply_all_button.setStyleSheet("font-weight: 700;")
        quick_apply_selected_button.setStyleSheet("font-weight: 700;")
        quick_label = QLabel("Valor rapido")
        quick_label.setObjectName("inventoryFilterLabel")
        quick_actions_row.addWidget(quick_label)
        quick_actions_row.addWidget(quick_value_spin)
        quick_actions_row.addWidget(quick_apply_all_button)
        quick_actions_row.addWidget(quick_apply_selected_button)
        quick_actions_row.addWidget(quick_reset_button)
        quick_actions_row.addStretch()

        table = QTableWidget()
        table.setObjectName("dataTable")
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["SKU", "Producto", "Talla", "Color", "Stock", "Apartado", "Entrada", "Resultado", "Estado", "Mensaje"]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(380)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        summary_label = QLabel("Sin filas cargadas.")
        summary_label.setObjectName("subtleLine")
        summary_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #fbf3ec; border: 1px solid #e4d2c2;"
            "color: #694a3e; font-weight: 600;"
        )
        status_banner_label = QLabel("Carga un lote para validar resultados.")
        status_banner_label.setObjectName("subtleLine")
        status_banner_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #fbf3ec; border: 1px solid #e4d2c2;"
            "color: #8c6656; font-weight: 700;"
        )

        def set_banner_style(tone: str) -> None:
            palette = {
                "positive": ("#f8dfcf", "#8f4527", "#dfb496"),
                "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
                "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
                "neutral": ("#fbf3ec", "#8c6656", "#e4d2c2"),
            }
            background, foreground, border = palette.get(tone, palette["neutral"])
            status_banner_label.setStyleSheet(
                f"padding: 8px 10px; border-radius: 12px; background: {background}; "
                f"border: 1px solid {border}; color: {foreground}; font-weight: 700;"
            )

        def current_source_rows() -> list[dict[str, object]]:
            return source_payloads.get(str(source_combo.currentData() or ""), [])

        def refresh_summary() -> None:
            rows = current_source_rows()
            valid_rows = 0
            error_rows = 0
            warning_rows = 0
            unchanged_rows = 0
            plus_units = 0
            minus_units = 0
            for row_index in range(len(rows)):
                state_item = table.item(row_index, 8)
                result_item = table.item(row_index, 7)
                if state_item is None or result_item is None:
                    continue
                state_text = state_item.text()
                delta_value = int(result_item.data(Qt.ItemDataRole.UserRole) or 0)
                if state_text == "OK":
                    valid_rows += 1
                    if delta_value > 0:
                        plus_units += delta_value
                    elif delta_value < 0:
                        minus_units += abs(delta_value)
                elif state_text == "WARNING":
                    warning_rows += 1
                    if delta_value > 0:
                        plus_units += delta_value
                    elif delta_value < 0:
                        minus_units += abs(delta_value)
                elif state_text == "ERROR":
                    error_rows += 1
                elif state_text == "SIN CAMBIOS":
                    unchanged_rows += 1
            summary_label.setText(
                f"Filas: {len(rows)} | OK: {valid_rows} | Warning: {warning_rows} | "
                f"Sin cambios: {unchanged_rows} | Error: {error_rows} | "
                f"Unidades +: {plus_units} | Unidades -: {minus_units}"
            )
            ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button is not None:
                ok_button.setEnabled(error_rows == 0 and (valid_rows > 0 or warning_rows > 0))
            if error_rows > 0:
                status_banner_label.setText(
                    "Hay filas con error. Corrige los valores capturados antes de aplicar el lote."
                )
                set_banner_style("danger")
            elif warning_rows > 0:
                status_banner_label.setText(
                    "Hay advertencias. El lote se puede aplicar, pero revisa las filas resaltadas."
                )
                set_banner_style("warning")
            elif valid_rows == 0:
                status_banner_label.setText("No hay cambios efectivos para aplicar en este lote.")
                set_banner_style("neutral")
            else:
                status_banner_label.setText("Lote listo para aplicar.")
                set_banner_style("positive")

        def update_preview() -> None:
            rows = current_source_rows()
            mode = str(mode_combo.currentData() or "STOCK_FINAL")
            table.setRowCount(len(rows))
            quick_value_spin.setRange(0, 100000) if mode == "STOCK_FINAL" else quick_value_spin.setRange(-100000, 100000)
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(
                    [
                        row["sku"],
                        row["producto_nombre_base"],
                        row["talla"],
                        row["color"],
                        row["stock_actual"],
                        row["apartado_cantidad"],
                    ]
                ):
                    item = _table_item(value)
                    table.setItem(row_index, column_index, item)
                spin = table.cellWidget(row_index, 6)
                if not isinstance(spin, QSpinBox):
                    spin = QSpinBox()
                    spin.setRange(-100000, 100000)
                    spin.valueChanged.connect(lambda _value, idx=row_index: _recalc_bulk_row(idx))
                    table.setCellWidget(row_index, 6, spin)
                spin.blockSignals(True)
                spin.setRange(0, 100000) if mode == "STOCK_FINAL" else spin.setRange(-100000, 100000)
                spin.setValue(int(row["stock_actual"]) if mode == "STOCK_FINAL" else 0)
                spin.blockSignals(False)
                recalc_row(row_index)
            refresh_summary()
            table.resizeColumnsToContents()

        def recalc_row(row_index: int) -> None:
            rows = current_source_rows()
            if row_index >= len(rows):
                return
            row = rows[row_index]
            mode = str(mode_combo.currentData() or "STOCK_FINAL")
            spin = table.cellWidget(row_index, 6)
            if not isinstance(spin, QSpinBox):
                return
            captured_value = spin.value()
            stock_actual = int(row["stock_actual"])
            apartado = int(row["apartado_cantidad"])
            delta = captured_value - stock_actual if mode == "STOCK_FINAL" else captured_value
            stock_final = captured_value if mode == "STOCK_FINAL" else stock_actual + captured_value
            estado = "OK"
            mensaje = "Ajuste listo."
            tone = "positive"
            if stock_final < 0:
                estado = "ERROR"
                mensaje = f"El stock final seria {stock_final}. No se permite stock negativo."
                tone = "danger"
            elif stock_final < apartado:
                estado = "ERROR"
                mensaje = f"El stock final ({stock_final}) queda por debajo del apartado comprometido ({apartado})."
                tone = "danger"
            elif delta == 0:
                estado = "SIN CAMBIOS"
                mensaje = "El valor capturado no cambia el stock actual."
                tone = "muted"
            elif apartado > 0 and stock_final == apartado:
                estado = "WARNING"
                mensaje = "El stock final queda exactamente igual al comprometido por apartados."
                tone = "warning"
            elif not bool(row["variante_activa"]):
                estado = "WARNING"
                mensaje = "La presentacion esta inactiva; el ajuste se puede aplicar, pero conviene revisarla."
                tone = "warning"
            elif abs(delta) >= max(10, stock_actual * 2) and stock_actual > 0:
                estado = "WARNING"
                mensaje = f"El ajuste cambia {abs(delta)} unidades. Revisa que el lote sea correcto."
                tone = "warning"
            result_item = _table_item(stock_final)
            result_item.setData(Qt.ItemDataRole.UserRole, delta)
            state_item = _table_item(estado)
            message_item = _table_item(mensaje)
            _set_table_badge_style(state_item, tone)
            if estado == "ERROR":
                _set_table_badge_style(message_item, "danger")
            elif estado == "SIN CAMBIOS":
                _set_table_badge_style(message_item, "muted")
            elif estado == "WARNING":
                _set_table_badge_style(message_item, "warning")
            table.setItem(row_index, 7, result_item)
            table.setItem(row_index, 8, state_item)
            table.setItem(row_index, 9, message_item)

        def _recalc_bulk_row(row_index: int) -> None:
            recalc_row(row_index)
            refresh_summary()

        def _apply_quick_value(selected_only: bool) -> None:
            target_rows = (
                sorted({index.row() for index in table.selectionModel().selectedRows()})
                if selected_only
                else list(range(table.rowCount()))
            )
            if selected_only and not target_rows:
                QMessageBox.information(dialog, "Sin seleccion", "Selecciona al menos una fila del preview.")
                return
            value = quick_value_spin.value()
            for row_index in target_rows:
                spin = table.cellWidget(row_index, 6)
                if isinstance(spin, QSpinBox):
                    spin.setValue(value)

        def _reset_quick_values() -> None:
            update_preview()

        source_combo.currentIndexChanged.connect(lambda _: update_preview())
        mode_combo.currentIndexChanged.connect(lambda _: update_preview())
        quick_apply_all_button.clicked.connect(lambda: _apply_quick_value(False))
        quick_apply_selected_button.clicked.connect(lambda: _apply_quick_value(True))
        quick_reset_button.clicked.connect(_reset_quick_values)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Aplicar lote")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(header_grid)
        layout.addWidget(status_banner_label)
        layout.addLayout(quick_actions_row)
        layout.addWidget(summary_label)
        layout.addWidget(table)
        layout.addWidget(buttons)
        update_preview()
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        rows = current_source_rows()
        items: list[dict[str, int]] = []
        mode = str(mode_combo.currentData() or "STOCK_FINAL")
        for row_index, row in enumerate(rows):
            spin = table.cellWidget(row_index, 6)
            state_item = table.item(row_index, 8)
            if not isinstance(spin, QSpinBox) or state_item is None:
                continue
            items.append(
                {
                    "variante_id": int(row["variante_id"]),
                    "valor": int(spin.value()),
                    "estado": 1 if state_item.text() == "OK" else 0,
                }
            )

        return {
            "tipo_fuente": str(source_combo.currentData() or "SELECCION"),
            "tipo_ajuste": mode,
            "referencia": reference_input.text().strip(),
            "motivo": motive_input.text().strip(),
            "observacion": note_input.text().strip(),
            "items": items,
        }

    def _prompt_inventory_bulk_price_data(self) -> dict[str, object] | None:
        selected_ids = self._selected_inventory_variant_ids()
        filtered_rows = list(self.inventory_rows)
        if not selected_ids and not filtered_rows:
            raise ValueError("No hay presentaciones disponibles para cambio masivo de precio.")

        source_options: list[tuple[str, str, list[dict[str, object]]]] = []
        if selected_ids:
            selected_rows = [row for row in filtered_rows if int(row["variante_id"]) in set(selected_ids)]
            source_options.append((f"Filas seleccionadas ({len(selected_rows)})", "SELECCION", selected_rows))
        if filtered_rows:
            source_options.append((f"Resultados filtrados ({len(filtered_rows)})", "FILTRADO", filtered_rows))

        dialog, layout = self._create_modal_dialog(
            "Precio masivo",
            "Actualiza precios por lote con preview y auditoria. Cada fila deja rastro en historial de catalogo.",
            width=980,
        )
        layout.setSpacing(8)
        header_grid = QGridLayout()
        header_grid.setHorizontalSpacing(8)
        header_grid.setVerticalSpacing(6)

        source_combo = QComboBox()
        source_payloads: dict[str, list[dict[str, object]]] = {}
        for label, code, rows in source_options:
            source_combo.addItem(label, code)
            source_payloads[code] = rows

        mode_combo = QComboBox()
        mode_combo.addItem("Fijar precio", "SET")
        mode_combo.addItem("Aumentar monto", "INCREASE_AMOUNT")
        mode_combo.addItem("Disminuir monto", "DECREASE_AMOUNT")
        mode_combo.addItem("Aumentar %", "INCREASE_PERCENT")
        mode_combo.addItem("Disminuir %", "DECREASE_PERCENT")

        reference_input = QLineEdit()
        reference_input.setText(self._generate_inventory_batch_reference(prefix="PRL"))
        reference_input.setReadOnly(True)
        reference_input.setObjectName("inventoryFilterInput")
        motive_input = QLineEdit()
        motive_input.setPlaceholderText("Ajuste de lista / temporada / correccion comercial")
        note_input = QLineEdit()
        note_input.setPlaceholderText("Observacion adicional")
        for label_text, row_index, column_index in (
            ("Fuente", 0, 0),
            ("Operacion", 0, 2),
            ("Referencia", 1, 0),
            ("Motivo", 1, 2),
            ("Observacion", 2, 0),
        ):
            label = QLabel(label_text)
            label.setObjectName("inventoryFilterLabel")
            header_grid.addWidget(label, row_index, column_index)
        header_grid.addWidget(source_combo, 0, 1)
        header_grid.addWidget(mode_combo, 0, 3)
        header_grid.addWidget(reference_input, 1, 1)
        header_grid.addWidget(motive_input, 1, 3)
        header_grid.addWidget(note_input, 2, 1, 1, 3)
        header_grid.setColumnStretch(1, 1)
        header_grid.setColumnStretch(3, 1)

        operation_hint_label = QLabel()
        operation_hint_label.setObjectName("subtleLine")
        operation_hint_label.setStyleSheet("padding: 4px 2px; color: #8c6656;")

        quick_actions_row = QHBoxLayout()
        quick_actions_row.setSpacing(6)
        quick_label = QLabel("Valor rapido")
        quick_label.setObjectName("inventoryFilterLabel")
        quick_value_spin = QDoubleSpinBox()
        quick_value_spin.setDecimals(2)
        quick_value_spin.setSingleStep(1.0)
        quick_value_spin.setRange(0.00, 100000.00)
        quick_value_spin.setObjectName("inventoryFilterInput")
        quick_apply_all_button = QPushButton("Aplicar a todas")
        quick_apply_selected_button = QPushButton("Aplicar a seleccionadas")
        quick_reset_button = QPushButton("Restablecer")
        for button in (quick_apply_all_button, quick_apply_selected_button, quick_reset_button):
            button.setObjectName("secondaryButton")
        quick_apply_all_button.setStyleSheet("font-weight: 700;")
        quick_apply_selected_button.setStyleSheet("font-weight: 700;")
        quick_actions_row.addWidget(quick_label)
        quick_actions_row.addWidget(quick_value_spin)
        quick_actions_row.addWidget(quick_apply_all_button)
        quick_actions_row.addWidget(quick_apply_selected_button)
        quick_actions_row.addWidget(quick_reset_button)
        quick_actions_row.addStretch()

        table = QTableWidget()
        table.setObjectName("dataTable")
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["SKU", "Producto", "Talla", "Color", "Actual", "Entrada", "Nuevo", "Delta", "Estado", "Mensaje"]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(380)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        summary_label = QLabel("Sin filas cargadas.")
        summary_label.setObjectName("subtleLine")
        summary_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #fbf3ec; border: 1px solid #e4d2c2;"
            "color: #694a3e; font-weight: 600;"
        )
        status_banner_label = QLabel("Carga un lote para validar resultados.")
        status_banner_label.setObjectName("subtleLine")
        status_banner_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #fbf3ec; border: 1px solid #e4d2c2;"
            "color: #8c6656; font-weight: 700;"
        )

        def set_banner_style(tone: str) -> None:
            palette = {
                "positive": ("#f8dfcf", "#8f4527", "#dfb496"),
                "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
                "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
                "neutral": ("#fbf3ec", "#8c6656", "#e4d2c2"),
            }
            background, foreground, border = palette.get(tone, palette["neutral"])
            status_banner_label.setStyleSheet(
                f"padding: 8px 10px; border-radius: 12px; background: {background}; "
                f"border: 1px solid {border}; color: {foreground}; font-weight: 700;"
            )

        def format_money(value: Decimal) -> str:
            return f"${value.quantize(Decimal('0.01'))}"

        def current_source_rows() -> list[dict[str, object]]:
            return source_payloads.get(str(source_combo.currentData() or ""), [])

        def current_mode() -> str:
            return str(mode_combo.currentData() or "SET")

        def update_operation_hint() -> None:
            hint_map = {
                "SET": "Captura el precio final deseado por fila.",
                "INCREASE_AMOUNT": "Captura cuanto quieres aumentar en dinero a cada presentacion.",
                "DECREASE_AMOUNT": "Captura cuanto quieres descontar en dinero a cada presentacion.",
                "INCREASE_PERCENT": "Captura el porcentaje de aumento por fila.",
                "DECREASE_PERCENT": "Captura el porcentaje de descuento por fila.",
            }
            operation_hint_label.setText(hint_map.get(current_mode(), "Define la operacion comercial a aplicar."))
            quick_value_spin.setSuffix("%" if current_mode().endswith("PERCENT") else "")
            quick_value_spin.setSingleStep(1.0 if current_mode().endswith("PERCENT") else 5.0)

        def refresh_summary() -> None:
            rows = current_source_rows()
            ok_rows = 0
            warning_rows = 0
            unchanged_rows = 0
            error_rows = 0
            increased_rows = 0
            decreased_rows = 0
            for row_index in range(len(rows)):
                state_item = table.item(row_index, 8)
                delta_item = table.item(row_index, 7)
                if state_item is None or delta_item is None:
                    continue
                state_text = state_item.text()
                delta_text = str(delta_item.data(Qt.ItemDataRole.UserRole) or "0.00")
                delta_value = Decimal(delta_text).quantize(Decimal("0.01"))
                if state_text == "OK":
                    ok_rows += 1
                elif state_text == "WARNING":
                    warning_rows += 1
                elif state_text == "ERROR":
                    error_rows += 1
                elif state_text == "SIN CAMBIOS":
                    unchanged_rows += 1
                if delta_value > Decimal("0.00"):
                    increased_rows += 1
                elif delta_value < Decimal("0.00"):
                    decreased_rows += 1

            summary_label.setText(
                f"Filas: {len(rows)} | OK: {ok_rows} | Warning: {warning_rows} | "
                f"Sin cambios: {unchanged_rows} | Error: {error_rows} | "
                f"Suben: {increased_rows} | Bajan: {decreased_rows}"
            )
            ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button is not None:
                ok_button.setEnabled(error_rows == 0 and (ok_rows > 0 or warning_rows > 0))
            if error_rows > 0:
                status_banner_label.setText(
                    "Hay filas con error. Corrige los valores capturados antes de aplicar el lote."
                )
                set_banner_style("danger")
            elif warning_rows > 0:
                status_banner_label.setText(
                    "Hay advertencias. El lote se puede aplicar, pero conviene revisar las filas marcadas."
                )
                set_banner_style("warning")
            elif ok_rows == 0:
                status_banner_label.setText("No hay cambios efectivos de precio para aplicar en este lote.")
                set_banner_style("neutral")
            else:
                status_banner_label.setText("Lote de precio listo para aplicar.")
                set_banner_style("positive")

        def recalc_row(row_index: int) -> None:
            rows = current_source_rows()
            if row_index >= len(rows):
                return
            row = rows[row_index]
            spin = table.cellWidget(row_index, 5)
            if not isinstance(spin, QDoubleSpinBox):
                return

            price_actual = Decimal(str(row["precio_venta"])).quantize(Decimal("0.01"))
            captured_value = Decimal(str(spin.value())).quantize(Decimal("0.01"))
            mode = current_mode()
            if mode == "SET":
                new_price = captured_value
                delta_value = (new_price - price_actual).quantize(Decimal("0.01"))
            elif mode == "INCREASE_AMOUNT":
                delta_value = captured_value
                new_price = (price_actual + captured_value).quantize(Decimal("0.01"))
            elif mode == "DECREASE_AMOUNT":
                delta_value = (captured_value * Decimal("-1")).quantize(Decimal("0.01"))
                new_price = (price_actual - captured_value).quantize(Decimal("0.01"))
            elif mode == "INCREASE_PERCENT":
                delta_value = (price_actual * captured_value / Decimal("100.00")).quantize(Decimal("0.01"))
                new_price = (price_actual + delta_value).quantize(Decimal("0.01"))
            else:
                delta_value = ((price_actual * captured_value / Decimal("100.00")) * Decimal("-1")).quantize(Decimal("0.01"))
                new_price = (price_actual + delta_value).quantize(Decimal("0.01"))

            estado = "OK"
            mensaje = "Cambio listo."
            tone = "positive"
            costo_referencia = row.get("costo_referencia")
            if new_price < Decimal("0.00"):
                estado = "ERROR"
                mensaje = f"El precio final seria {format_money(new_price)}. No se permiten precios negativos."
                tone = "danger"
            elif new_price == price_actual:
                estado = "SIN CAMBIOS"
                mensaje = "La operacion no cambia el precio actual."
                tone = "muted"
            elif new_price == Decimal("0.00"):
                estado = "WARNING"
                mensaje = "El precio final queda en $0.00. Verifica si realmente es correcto."
                tone = "warning"
            elif costo_referencia is not None and new_price < Decimal(str(costo_referencia)).quantize(Decimal("0.01")):
                estado = "WARNING"
                mensaje = f"El precio queda por debajo del costo de referencia {format_money(Decimal(str(costo_referencia)))}."
                tone = "warning"
            elif not bool(row["variante_activa"]):
                estado = "WARNING"
                mensaje = "La presentacion esta inactiva; el cambio se puede aplicar, pero conviene revisarla."
                tone = "warning"
            elif price_actual > Decimal("0.00") and abs(delta_value) >= max(Decimal("50.00"), price_actual * Decimal("0.50")):
                estado = "WARNING"
                mensaje = f"El cambio mueve {format_money(abs(delta_value))} respecto al precio actual."
                tone = "warning"

            new_item = _table_item(format_money(new_price))
            new_item.setData(Qt.ItemDataRole.UserRole, str(new_price))
            delta_prefix = "+" if delta_value > Decimal("0.00") else ""
            delta_item = _table_item(f"{delta_prefix}{format_money(delta_value)}")
            delta_item.setData(Qt.ItemDataRole.UserRole, str(delta_value))
            state_item = _table_item(estado)
            message_item = _table_item(mensaje)
            if delta_value > Decimal("0.00"):
                _set_table_badge_style(delta_item, "positive")
            elif delta_value < Decimal("0.00"):
                _set_table_badge_style(delta_item, "warning")
            else:
                _set_table_badge_style(delta_item, "muted")
            _set_table_badge_style(state_item, tone)
            if estado == "ERROR":
                _set_table_badge_style(message_item, "danger")
            elif estado == "WARNING":
                _set_table_badge_style(message_item, "warning")
            elif estado == "SIN CAMBIOS":
                _set_table_badge_style(message_item, "muted")
            table.setItem(row_index, 6, new_item)
            table.setItem(row_index, 7, delta_item)
            table.setItem(row_index, 8, state_item)
            table.setItem(row_index, 9, message_item)

        def _recalc_price_row(row_index: int) -> None:
            recalc_row(row_index)
            refresh_summary()

        def update_preview() -> None:
            rows = current_source_rows()
            mode = current_mode()
            table.setRowCount(len(rows))
            update_operation_hint()
            quick_value_spin.setRange(0.00, 100000.00)
            for row_index, row in enumerate(rows):
                base_values = [
                    row["sku"],
                    row["producto_nombre_base"],
                    row["talla"],
                    row["color"],
                    format_money(Decimal(str(row["precio_venta"]))),
                ]
                for column_index, value in enumerate(base_values):
                    table.setItem(row_index, column_index, _table_item(value))
                spin = table.cellWidget(row_index, 5)
                if not isinstance(spin, QDoubleSpinBox):
                    spin = QDoubleSpinBox()
                    spin.setDecimals(2)
                    spin.setRange(0.00, 100000.00)
                    spin.setSingleStep(1.0)
                    spin.valueChanged.connect(lambda _value, idx=row_index: _recalc_price_row(idx))
                    table.setCellWidget(row_index, 5, spin)
                spin.blockSignals(True)
                spin.setSuffix("%" if mode.endswith("PERCENT") else "")
                spin.setSingleStep(1.0 if mode.endswith("PERCENT") else 5.0)
                spin.setValue(float(Decimal(str(row["precio_venta"])).quantize(Decimal("0.01"))) if mode == "SET" else 0.0)
                spin.blockSignals(False)
                recalc_row(row_index)
            refresh_summary()
            table.resizeColumnsToContents()

        def _apply_quick_value(selected_only: bool) -> None:
            target_rows = (
                sorted({index.row() for index in table.selectionModel().selectedRows()})
                if selected_only
                else list(range(table.rowCount()))
            )
            if selected_only and not target_rows:
                QMessageBox.information(dialog, "Sin seleccion", "Selecciona al menos una fila del preview.")
                return
            value = quick_value_spin.value()
            for row_index in target_rows:
                spin = table.cellWidget(row_index, 5)
                if isinstance(spin, QDoubleSpinBox):
                    spin.setValue(value)

        def _reset_quick_values() -> None:
            update_preview()

        source_combo.currentIndexChanged.connect(lambda _: update_preview())
        mode_combo.currentIndexChanged.connect(lambda _: update_preview())
        quick_apply_all_button.clicked.connect(lambda: _apply_quick_value(False))
        quick_apply_selected_button.clicked.connect(lambda: _apply_quick_value(True))
        quick_reset_button.clicked.connect(_reset_quick_values)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Aplicar lote")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addLayout(header_grid)
        layout.addWidget(operation_hint_label)
        layout.addWidget(status_banner_label)
        layout.addLayout(quick_actions_row)
        layout.addWidget(summary_label)
        layout.addWidget(table)
        layout.addWidget(buttons)
        update_preview()
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        rows = current_source_rows()
        items: list[dict[str, object]] = []
        for row_index, row in enumerate(rows):
            state_item = table.item(row_index, 8)
            new_item = table.item(row_index, 6)
            if state_item is None or new_item is None:
                continue
            items.append(
                {
                    "variante_id": int(row["variante_id"]),
                    "precio_nuevo": str(new_item.data(Qt.ItemDataRole.UserRole) or "0.00"),
                    "estado": state_item.text(),
                }
            )

        return {
            "tipo_fuente": str(source_combo.currentData() or "SELECCION"),
            "tipo_operacion": current_mode(),
            "referencia": reference_input.text().strip(),
            "motivo": motive_input.text().strip(),
            "observacion": note_input.text().strip(),
            "items": items,
        }

    def _handle_test_connection(self) -> None:
        try:
            test_connection()
        except SQLAlchemyError as exc:
            QMessageBox.critical(self, "Conexion fallida", str(exc))
            return
        QMessageBox.information(self, "Conexion exitosa", "PostgreSQL respondio correctamente.")

    def _handle_seed_data(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede cargar datos demo.")
            return

        try:
            with get_session() as session:
                result = BootstrapService.seed_initial_data(session)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Datos iniciales",
            (
                "Datos base listos.\n"
                f"Usuarios: {result['usuarios']}\n"
                f"Proveedores: {result['proveedores']}\n"
                f"Productos: {result['productos']}\n"
                f"Presentaciones: {result['variantes']}"
            ),
        )

    def _handle_create_category(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear categorias.")
            return

        name = self._prompt_text_value("Nueva categoria", "Categoria", "Nueva categoria")
        if name is None:
            return
        if not name:
            QMessageBox.warning(self, "Datos incompletos", "Captura el nombre de la categoria.")
            return

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                CatalogService.crear_categoria(session, user, name)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Categoria fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Categoria creada", f"Categoria '{name}' creada correctamente.")

    def _handle_create_brand(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear marcas.")
            return

        name = self._prompt_text_value("Nueva marca", "Marca", "Nueva marca")
        if name is None:
            return
        if not name:
            QMessageBox.warning(self, "Datos incompletos", "Captura el nombre de la marca.")
            return

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                CatalogService.crear_marca(session, user, name)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Marca fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Marca creada", f"Marca '{name}' creada correctamente.")

    def _create_or_edit_presentation(
        self,
        *,
        initial: dict[str, object] | None = None,
        default_product_id: int | None = None,
        include_stock: bool,
    ) -> tuple[str, int] | None:
        try:
            data = self._prompt_variant_data(
                initial=initial,
                include_stock=include_stock,
                default_product_id=default_product_id,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Datos incompletos", str(exc))
            return None
        if data is None:
            return None

        if default_product_id is not None:
            data["producto_id"] = default_product_id

        producto_id = data["producto_id"]
        sku = str(data["sku"]).strip()
        talla = str(data["talla"]).strip()
        color = str(data["color"]).strip() or "Sin color"
        price_text = str(data["precio"]).strip()
        cost_text = str(data["costo"]).strip()
        if not producto_id or not talla or not price_text:
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "Selecciona producto y captura talla y precio.",
            )
            return None

        try:
            precio = Decimal(price_text)
            costo = Decimal(cost_text) if cost_text else None
        except InvalidOperation:
            QMessageBox.warning(self, "Valores invalidos", "Precio o costo con formato invalido.")
            return None

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                producto = session.get(Producto, int(producto_id))
                if user is None or producto is None:
                    raise ValueError("Usuario o producto no encontrado.")
                if initial is None:
                    presentacion = CatalogService.crear_variante(
                        session=session,
                        usuario=user,
                        producto=producto,
                        sku=sku,
                        talla=talla,
                        color=color,
                        precio_venta=precio,
                        costo_referencia=costo,
                        stock_inicial=int(data["stock_inicial"]),
                    )
                else:
                    variante = session.get(Variante, int(initial["variante_id"]))
                    if variante is None:
                        raise ValueError("Presentacion no encontrada.")
                    presentacion = CatalogService.actualizar_variante(
                        session=session,
                        usuario=user,
                        variante=variante,
                        producto=producto,
                        sku=sku,
                        talla=talla,
                        color=color,
                        precio_venta=precio,
                        costo_referencia=costo,
                    )
                session.commit()
                return str(presentacion.sku), int(presentacion.id)
        except Exception as exc:  # noqa: BLE001
            title = "Presentacion fallida" if initial is None else "Presentacion no actualizada"
            QMessageBox.critical(self, title, str(exc))
            return None

    def _offer_generate_qr_for_variants(
        self,
        variant_ids: list[int],
        *,
        title: str,
        summary_message: str,
    ) -> None:
        normalized_ids = [int(value) for value in variant_ids if value]
        if not normalized_ids:
            return
        reply = QMessageBox.question(
            self,
            title,
            (
                f"{summary_message}\n\n"
                "Los QR quedan pendientes por default para no frenar el alta.\n"
                "Quieres generarlos ahora?"
            ),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_session() as session:
                variantes = [
                    variante
                    for variant_id in normalized_ids
                    if (variante := session.get(Variante, int(variant_id))) is not None
                ]
                if not variantes:
                    raise ValueError("No se encontraron presentaciones activas para generar QR.")
                paths = QrGenerator.generate_many(variantes)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        self.refresh_all()
        self._set_combo_value(self.inventory_variant_combo, normalized_ids[0])
        self._refresh_selected_qr_preview()
        generated_count = len(paths)
        if generated_count == 1:
            qr_message = f"Se genero 1 QR en:\n{paths[0]}"
        else:
            qr_message = (
                f"Se generaron {generated_count} QR en:\n{QrGenerator.output_dir()}\n"
                f"Primer archivo: {paths[0].name}"
            )
        QMessageBox.information(self, "QR generado", qr_message)

    def _handle_create_product(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear productos.")
            return

        try:
            data = self._prompt_product_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Datos incompletos", str(exc))
            return
        if data is None:
            return

        categoria_id = data["categoria_id"]
        marca_id = data["marca_id"]
        nombre = str(data["nombre"]).strip()
        descripcion = str(data["descripcion"]).strip()
        if not categoria_id or not marca_id or not nombre:
            QMessageBox.warning(self, "Datos incompletos", "Selecciona categoria, marca y nombre.")
            return

        created_product_id: int | None = None
        selected_sizes = [str(value).strip() for value in data.get("tallas", []) if str(value).strip()]
        selected_colors = [str(value).strip() for value in data.get("colores", []) if str(value).strip()]
        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                categoria = session.get(Categoria, int(categoria_id))
                marca = session.get(Marca, int(marca_id))
                if user is None or categoria is None or marca is None:
                    raise ValueError("Usuario, categoria o marca no encontrada.")
                escuela = self._resolve_named_taxonomy(session, Escuela, str(data["escuela"]))
                tipo_prenda = self._resolve_named_taxonomy(session, TipoPrenda, str(data["tipo_prenda"]))
                tipo_pieza = self._resolve_named_taxonomy(session, TipoPieza, str(data["tipo_pieza"]))
                atributo = self._resolve_named_taxonomy(session, AtributoProducto, str(data["atributo"]))
                nivel_educativo = self._resolve_named_taxonomy(session, NivelEducativo, str(data["nivel_educativo"]))
                producto = CatalogService.crear_producto(
                    session,
                    user,
                    categoria,
                    marca,
                    nombre,
                    descripcion,
                    escuela=escuela,
                    tipo_prenda=tipo_prenda,
                    tipo_pieza=tipo_pieza,
                    nivel_educativo=nivel_educativo,
                    atributo=atributo,
                    genero=str(data["genero"]),
                    escudo=str(data["escudo"]),
                    ubicacion=str(data["ubicacion"]),
                )
                session.commit()
                created_product_id = int(producto.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Producto fallido", str(exc))
            return

        self.refresh_all()
        if created_product_id is not None and (selected_sizes or selected_colors):
            total_sizes = max(1, len(selected_sizes))
            total_colors = max(1, len(selected_colors))
            total_variants = total_sizes * total_colors
            try:
                with get_session() as session:
                    sku_preview_list = CatalogService.preview_next_skus(session, total_variants)
            except Exception:
                sku_preview_list = []
            if not sku_preview_list:
                sku_preview = "SKU pendiente."
            elif len(sku_preview_list) == 1:
                sku_preview = sku_preview_list[0]
            else:
                sku_head = ", ".join(sku_preview_list[:4])
                if len(sku_preview_list) > 4:
                    sku_head += f" ... (+{len(sku_preview_list) - 4})"
                sku_preview = f"{sku_head} | rango {sku_preview_list[0]} -> {sku_preview_list[-1]}"
            reply = QMessageBox.question(
                self,
                "Producto creado",
                (
                    f"Producto '{nombre}' creado correctamente.\n\n"
                    f"Ya dejaste {total_variants} presentaciones sugeridas con tallas y colores.\n"
                    f"SKU previstos: {sku_preview}\n\n"
                    "Quieres crearlas ahora por lote?"
                ),
            )
            if reply == QMessageBox.StandardButton.Yes:
                batch_data = self._prompt_batch_variant_data(
                    sizes=selected_sizes,
                    colors=selected_colors,
                    initial_price=str(data.get("precio_variante") or ""),
                    pricing_mode=str(data.get("precio_modo") or "single"),
                    prices_by_size=dict(data.get("precios_por_talla") or {}),
                    price_summary=str(data.get("resumen_precio") or ""),
                    initial_cost=str(data.get("costo_variante") or ""),
                    initial_stock=int(data.get("stock_inicial_variante") or 0),
                )
                if batch_data is not None:
                    try:
                        created_count, first_variant_id, errors, created_skus = self._create_variants_batch(
                            product_id=created_product_id,
                            sizes=list(batch_data["tallas"]),
                            colors=list(batch_data["colores"]),
                            price_text=str(batch_data["precio"]),
                            prices_by_size=dict(batch_data.get("precios_por_talla") or {}),
                            cost_text=str(batch_data["costo"]),
                            stock_initial=int(batch_data["stock_inicial"]),
                        )
                    except Exception as exc:  # noqa: BLE001
                        QMessageBox.critical(self, "Presentaciones fallidas", str(exc))
                        return
                    self.refresh_all()
                    if first_variant_id is not None:
                        self._set_combo_value(self.inventory_variant_combo, first_variant_id)
                    message = f"Se crearon {created_count} presentaciones para '{nombre}'."
                    if created_skus:
                        preview_skus = ", ".join(created_skus[:8])
                        if len(created_skus) > 8:
                            preview_skus += f", ... (+{len(created_skus) - 8})"
                        message += (
                            f"\n\nSKU creados:\n{preview_skus}"
                            f"\nRango: {created_skus[0]} -> {created_skus[-1]}"
                        )
                    if errors:
                        preview_errors = "\n".join(errors[:4])
                        if len(errors) > 4:
                            preview_errors += f"\n... y {len(errors) - 4} mas."
                        message += f"\n\nIncidencias:\n{preview_errors}"
                    message += (
                        "\n\nQR: pendiente. Puedes generarlo ahora o despues desde Inventario."
                    )
                    created_variant_ids: list[int] = []
                    if created_skus:
                        try:
                            with get_session() as session:
                                created_variant_ids = list(
                                    session.scalars(
                                        select(Variante.id)
                                        .where(Variante.sku.in_(created_skus))
                                        .order_by(Variante.sku)
                                    ).all()
                                )
                        except Exception:
                            created_variant_ids = []
                    self._offer_generate_qr_for_variants(
                        created_variant_ids,
                        title="Presentaciones creadas",
                        summary_message=message,
                    )
                return

        reply = QMessageBox.question(
            self,
            "Producto creado",
            f"Producto '{nombre}' creado correctamente.\n\nQuieres agregar su primera presentacion ahora?",
        )
        if reply == QMessageBox.StandardButton.Yes and created_product_id is not None:
            result = self._create_or_edit_presentation(
                default_product_id=created_product_id,
                include_stock=True,
            )
            if result is not None:
                sku, variant_id = result
                self.refresh_all()
                self._offer_generate_qr_for_variants(
                    [variant_id],
                    title="Presentacion creada",
                    summary_message=(
                        f"Se agrego la primera presentacion del producto con SKU '{sku}'.\n\n"
                        "QR: pendiente."
                    ),
                )

    def _handle_create_variant(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear presentaciones.")
            return

        result = self._create_or_edit_presentation(include_stock=True)
        if result is None:
            return

        sku, variant_id = result
        self.refresh_all()
        self._set_combo_value(self.inventory_variant_combo, variant_id)
        self._offer_generate_qr_for_variants(
            [variant_id],
            title="Presentacion creada",
            summary_message=f"Presentacion '{sku.upper()}' creada correctamente.\n\nQR: pendiente.",
        )

    def _handle_catalog_selection(self) -> None:
        selected_row = self.catalog_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.catalog_rows):
            self.products_selection_label.setText(
                "Consulta uniformes y usa filtros macro como Deportivo, Oficial, Basico, Escolta o Accesorio."
            )
            return

        row = self.catalog_rows[selected_row]
        context_parts = [
            str(row["escuela_nombre"]),
            str(row["tipo_prenda_nombre"]),
            str(row["tipo_pieza_nombre"]),
        ]
        context_text = " | ".join(part for part in context_parts if part and part != "-")
        legacy_note = (
            f" | legacy: {row['nombre_legacy']}"
            if row["origen_legacy"] and row["nombre_legacy"] and row["nombre_legacy"] != row["producto_nombre"]
            else ""
        )
        if self.current_role == RolUsuario.ADMIN:
            self.products_selection_label.setText(
                f"{row['sku']} | {row['producto_nombre_base']} | {context_text or 'General'} | "
                f"precio {row['precio_venta']} | stock {row['stock_actual']} | apartado {row['apartado_cantidad']} | "
                f"{row['variante_estado']} | {row['origen_etiqueta']}{legacy_note}"
            )
        else:
            self.products_selection_label.setText(
                f"{row['producto_nombre_base']} | {row['sku']} | {context_text or 'General'} | "
                f"precio {row['precio_venta']} | stock {row['stock_actual']}"
            )

    def _handle_update_product(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion para editar su producto.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede editar productos.")
            return

        try:
            data = self._prompt_product_data(selected)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se puede editar", str(exc))
            return
        if data is None:
            return

        categoria_id = data["categoria_id"]
        marca_id = data["marca_id"]
        nombre = str(data["nombre"]).strip()
        descripcion = str(data["descripcion"]).strip()
        if not categoria_id or not marca_id or not nombre:
            QMessageBox.warning(self, "Datos incompletos", "Categoria, marca y nombre son obligatorios.")
            return

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                producto = session.get(Producto, int(selected["producto_id"]))
                categoria = session.get(Categoria, int(categoria_id))
                marca = session.get(Marca, int(marca_id))
                if usuario is None or producto is None or categoria is None or marca is None:
                    raise ValueError("No se pudo cargar el producto, categoria o marca.")
                escuela = self._resolve_named_taxonomy(session, Escuela, str(data["escuela"]))
                tipo_prenda = self._resolve_named_taxonomy(session, TipoPrenda, str(data["tipo_prenda"]))
                tipo_pieza = self._resolve_named_taxonomy(session, TipoPieza, str(data["tipo_pieza"]))
                atributo = self._resolve_named_taxonomy(session, AtributoProducto, str(data["atributo"]))
                nivel_educativo = self._resolve_named_taxonomy(session, NivelEducativo, str(data["nivel_educativo"]))
                CatalogService.actualizar_producto(
                    session=session,
                    usuario=usuario,
                    producto=producto,
                    categoria=categoria,
                    marca=marca,
                    nombre=nombre,
                    descripcion=descripcion,
                    escuela=escuela,
                    tipo_prenda=tipo_prenda,
                    tipo_pieza=tipo_pieza,
                    nivel_educativo=nivel_educativo,
                    atributo=atributo,
                    genero=str(data["genero"]),
                    escudo=str(data["escudo"]),
                    ubicacion=str(data["ubicacion"]),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Producto no actualizado", str(exc))
            return

        self.refresh_all()
        self._select_catalog_variant(int(selected["variante_id"]))
        QMessageBox.information(self, "Producto actualizado", f"Producto '{nombre}' actualizado correctamente.")

    def _handle_update_variant(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion para editarla.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede editar presentaciones.")
            return

        result = self._create_or_edit_presentation(initial=selected, include_stock=False)
        if result is None:
            return

        sku, variant_id = result
        old_sku = str(selected["sku"]).strip().upper()
        if old_sku != sku.upper():
            try:
                with get_session() as session:
                    variante = session.get(Variante, variant_id)
                    if variante is not None:
                        QrGenerator.sync_after_sku_change(old_sku, variante)
            except Exception:
                pass
        self.refresh_all()
        self._set_combo_value(self.inventory_variant_combo, variant_id)
        self._select_catalog_variant(variant_id)
        QMessageBox.information(self, "Presentacion actualizada", f"Presentacion '{sku.upper()}' actualizada correctamente.")

    def _handle_toggle_product(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion para cambiar el estado del producto.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede activar o desactivar productos.")
            return

        target_state = not bool(selected["producto_activo"])
        action = "activar" if target_state else "desactivar"

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                producto = session.get(Producto, int(selected["producto_id"]))
                if usuario is None or producto is None:
                    raise ValueError("No se pudo cargar el producto.")
                CatalogService.cambiar_estado_producto(session, usuario, producto, target_state)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Estado no actualizado", str(exc))
            return

        self.refresh_all()
        self._select_catalog_variant(int(selected["variante_id"]))
        QMessageBox.information(self, "Producto actualizado", f"Producto listo para {action} correctamente.")

    def _handle_toggle_variant(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion para cambiar su estado.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede activar o desactivar presentaciones.")
            return

        target_state = not bool(selected["variante_activo"])
        action = "activar" if target_state else "desactivar"

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                variante = session.get(Variante, int(selected["variante_id"]))
                if usuario is None or variante is None:
                    raise ValueError("No se pudo cargar la presentacion.")
                CatalogService.cambiar_estado_variante(session, usuario, variante, target_state)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Estado no actualizado", str(exc))
            return

        self.refresh_all()
        self._select_catalog_variant(int(selected["variante_id"]))
        QMessageBox.information(self, "Presentacion actualizada", f"Presentacion lista para {action} correctamente.")

    def _handle_delete_product(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion del producto que quieres eliminar.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede eliminar productos.")
            return

        product_name = str(selected["producto_nombre"])
        confirmation = QMessageBox.question(
            self,
            "Eliminar producto",
            (
                f"Se intentara eliminar el producto '{product_name}'.\n\n"
                "Solo se eliminara si ninguna presentacion tiene stock ni historial.\n"
                "Si existe historial, usa desactivar en lugar de eliminar.\n\n"
                "Deseas continuar?"
            ),
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                producto = session.get(Producto, int(selected["producto_id"]))
                if usuario is None or producto is None:
                    raise ValueError("No se pudo cargar el producto.")
                CatalogService.eliminar_producto(session, usuario, producto)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo eliminar", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Producto eliminado", f"Producto '{product_name}' eliminado correctamente.")

    def _handle_delete_variant(self) -> None:
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una presentacion para eliminarla.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede eliminar presentaciones.")
            return

        sku = str(selected["sku"])
        confirmation = QMessageBox.question(
            self,
            "Eliminar presentacion",
            (
                f"Se intentara eliminar la presentacion '{sku}'.\n\n"
                "Solo se eliminara si no tiene stock ni historial.\n"
                "Si existe historial, usa desactivar en lugar de eliminar.\n\n"
                "Deseas continuar?"
            ),
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                variante = session.get(Variante, int(selected["variante_id"]))
                if usuario is None or variante is None:
                    raise ValueError("No se pudo cargar la presentacion.")
                CatalogService.eliminar_variante(session, usuario, variante)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo eliminar", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Presentacion eliminada", f"Presentacion '{sku}' eliminada correctamente.")

    def _handle_purchase(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede registrar compras.")
            return
        try:
            data = self._prompt_purchase_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Datos incompletos", str(exc))
            return
        if data is None:
            return

        proveedor_id = data["proveedor_id"]
        variante_id = data["variante_id"]
        document = str(data["documento"]).strip() or f"COMP-{uuid4().hex[:8].upper()}"
        cost_text = str(data["costo"]).strip()
        if not proveedor_id or not variante_id:
            QMessageBox.warning(self, "Datos incompletos", "Selecciona proveedor y presentacion.")
            return
        if not cost_text:
            QMessageBox.warning(self, "Datos incompletos", "Captura el costo unitario.")
            return

        try:
            costo = Decimal(cost_text)
            if costo < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            QMessageBox.warning(self, "Costo invalido", "El costo unitario debe ser un numero positivo.")
            return

        try:
            with get_session() as session:
                proveedor = session.get(Proveedor, int(proveedor_id))
                usuario = session.get(Usuario, self.user_id)
                if proveedor is None or usuario is None:
                    raise ValueError("Proveedor o usuario no encontrado.")
                compra = CompraService.crear_borrador(
                    session=session,
                    proveedor=proveedor,
                    usuario=usuario,
                    numero_documento=document,
                    items=[
                        CompraItemInput(
                            variante_id=int(variante_id),
                            cantidad=int(data["cantidad"]),
                            costo_unitario=costo,
                        )
                    ],
                )
                CompraService.confirmar_compra(session, compra)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Compra fallida", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Compra registrada", f"Compra {document} confirmada correctamente.")

    def _open_recent_sales_dialog(self) -> None:
        if self.sales_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Ventas recientes")
            dialog.resize(980, 560)
            layout = QVBoxLayout()
            layout.setSpacing(10)

            helper = QLabel("Consulta ventas recientes. Selecciona una confirmada si necesitas cancelarla.")
            helper.setObjectName("subtleLine")
            helper.setWordWrap(True)
            self.cancel_permission_label.setObjectName("cashierWarningLine")
            self.cancel_permission_label.setWordWrap(True)
            self.sale_ticket_button.setObjectName("toolbarSecondaryButton")
            self.cancel_button.clicked.connect(self._handle_cancel_sale)
            self.sale_ticket_button.clicked.connect(self._handle_view_sale_ticket)

            header = QHBoxLayout()
            header.addWidget(helper, 1)
            header.addWidget(self.sale_ticket_button)
            header.addWidget(self.cancel_button)

            layout.addLayout(header)
            layout.addWidget(self.cancel_permission_label)
            layout.addWidget(self.recent_sales_table, 1)
            dialog.setLayout(layout)
            self.sales_dialog = dialog

        self.recent_sales_table.resizeColumnsToContents()
        self.sales_dialog.show()
        self.sales_dialog.raise_()
        self.sales_dialog.activateWindow()

    def _selected_recent_sale_id(self) -> int | None:
        selected_row = self.recent_sales_table.currentRow()
        if selected_row < 0:
            return None
        sale_id_item = self.recent_sales_table.item(selected_row, 0)
        if sale_id_item is None:
            return None
        try:
            return int(sale_id_item.text())
        except (TypeError, ValueError):
            return None

    def _build_sale_ticket_text(self, sale: Venta) -> str:
        try:
            with get_session() as session:
                settings = load_business_print_settings_snapshot(session)
        except Exception:
            settings = SimpleNamespace(
                business_name="POS Uniformes",
                business_phone="",
                business_address="",
                ticket_footer="Gracias por tu compra.",
                preferred_printer="",
                ticket_copies=1,
            )
        return build_sale_ticket_text(
            sale=sale,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
            preferred_printer=settings.preferred_printer,
            ticket_copies=settings.ticket_copies,
        )

    def _handle_view_sale_ticket(self) -> None:
        sale_id = self._selected_recent_sale_id()
        if sale_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una venta para ver su ticket.")
            return

        try:
            with get_session() as session:
                sale = load_sale_for_ticket(session, sale_id)
                ticket_text = self._build_sale_ticket_text(sale)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

        open_printable_text_dialog(self, f"Ticket {sale_id}", ticket_text)

    def _build_layaway_receipt_text(self, layaway: Apartado) -> str:
        try:
            with get_session() as session:
                settings = load_business_print_settings_snapshot(
                    session,
                    default_ticket_footer="Gracias por tu preferencia.",
                )
        except Exception:
            settings = SimpleNamespace(
                business_name="POS Uniformes",
                business_phone="",
                business_address="",
                ticket_footer="Gracias por tu preferencia.",
                preferred_printer="",
                ticket_copies=1,
            )
        return build_layaway_receipt_text(
            layaway=layaway,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
            preferred_printer=settings.preferred_printer,
            ticket_copies=settings.ticket_copies,
        )

    def _handle_view_layaway_receipt(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su comprobante.")
            return

        try:
            with get_session() as session:
                layaway = load_layaway_for_receipt(session, apartado_id)
                receipt_text = self._build_layaway_receipt_text(layaway)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Comprobante no disponible", str(exc))
            return

        open_printable_text_dialog(self, f"Apartado {apartado_id}", receipt_text)

    def _handle_view_layaway_sale_ticket(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su ticket de venta.")
            return

        try:
            with get_session() as session:
                sale = load_sale_for_layaway_ticket(session, apartado_id)
                ticket_text = self._build_sale_ticket_text(sale)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

        open_printable_text_dialog(self, f"Ticket de entrega {apartado_id}", ticket_text)

    @staticmethod
    def _generate_sale_folio() -> str:
        return f"VTA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"

    @staticmethod
    def _generate_quote_folio() -> str:
        return f"PRE-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"

    def _reset_sale_form(self) -> None:
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self.sale_payment_combo.setCurrentText("Efectivo")
        self.sale_client_combo.setCurrentIndex(0)
        self._set_sale_discount_lock_state(locked=False, discount_percent=Decimal("0.00"))
        self._clear_sale_manual_promo_authorization()
        self._refresh_sale_discount_options(selected_discount=Decimal("0.00"))
        self.sale_received_spin.setValue(0.0)
        self.sale_folio_input.setText(self._generate_sale_folio())
        self.sale_last_scanned_sku = ""
        self.sale_last_scanned_at = 0.0
        self._refresh_payment_fields()

    def _reset_quote_form(self) -> None:
        self.quote_sku_input.clear()
        self.quote_qty_spin.setValue(1)
        self.quote_client_combo.setCurrentIndex(0)
        self.quote_validity_input.setDate(QDate.currentDate().addDays(15))
        self.quote_note_input.clear()
        self.quote_folio_input.setText(self._generate_quote_folio())

    def _play_sale_feedback_sound(self) -> None:
        QApplication.beep()

    def _set_sale_feedback(self, text: str, tone: str = "neutral", auto_clear_ms: int | None = None) -> None:
        self.sale_feedback_label.setText(text)
        self.sale_feedback_label.setProperty("tone", tone)
        self.sale_feedback_label.style().unpolish(self.sale_feedback_label)
        self.sale_feedback_label.style().polish(self.sale_feedback_label)
        self.sale_feedback_label.update()
        if auto_clear_ms:
            QTimer.singleShot(auto_clear_ms, self._clear_sale_feedback)

    def _clear_sale_feedback(self) -> None:
        if self.sale_feedback_label.text() == "Listo para escanear.":
            return
        self._set_sale_feedback("Listo para escanear.", "neutral")

    def _set_sale_processing(self, active: bool) -> None:
        self.sale_processing = active
        self.sale_button.setEnabled(not active and self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO})
        self.sale_button.setText("Procesando..." if active else "Cobrar")

    @staticmethod
    def _normalize_discount_value(value: object | None) -> Decimal:
        return normalize_discount_value(value)

    @classmethod
    def _format_discount_label(cls, value: Decimal) -> str:
        return format_discount_label(value)

    def _preview_next_skus(self, count: int) -> list[str]:
        normalized_count = max(0, int(count))
        if normalized_count == 0:
            return []
        try:
            with get_session() as session:
                return CatalogService.preview_next_skus(session, normalized_count)
        except Exception:
            return []

    def _format_sku_preview(self, count: int) -> str:
        preview_list = self._preview_next_skus(count)
        if not preview_list:
            return "SKU pendiente."
        if len(preview_list) == 1:
            return preview_list[0]
        preview_head = ", ".join(preview_list[:4])
        if len(preview_list) <= 4:
            return f"{preview_head} | rango {preview_list[0]} -> {preview_list[-1]}"
        return f"{preview_head} ... (+{len(preview_list) - 4}) | rango {preview_list[0]} -> {preview_list[-1]}"

    @staticmethod
    def _find_active_client_by_code(session, client_code: str) -> Cliente | None:
        normalized_code = client_code.strip().upper()
        if not normalized_code:
            return None
        return session.scalar(
            select(Cliente).where(
                func.upper(Cliente.codigo_cliente) == normalized_code,
                Cliente.activo.is_(True),
            )
        )

    def _apply_scanned_client_to_sale(self, client: Cliente, scanned_code: str) -> bool:
        current_client_id = self.sale_client_combo.currentData()
        decision = decide_scanned_client_action(
            current_client_id=current_client_id,
            scanned_client_id=client.id,
            has_sale_cart=bool(self.sale_cart),
        )
        if decision.action == "already_linked":
            self.sale_sku_input.clear()
            self.sale_qty_spin.setValue(1)
            self._set_sale_feedback(
                build_client_already_linked_feedback(client.codigo_cliente),
                "neutral",
                auto_clear_ms=1700,
            )
            self.sale_sku_input.setFocus()
            return True

        if decision.action == "confirm_replace":
            current_label = self.sale_client_combo.currentText().strip() or "Cliente actual"
            confirmation = QMessageBox.question(
                self,
                "Cambiar cliente de la venta",
                build_replace_client_confirmation(
                    current_label=current_label,
                    scanned_client_code=client.codigo_cliente,
                    scanned_client_name=client.nombre,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                self.sale_sku_input.clear()
                self.sale_qty_spin.setValue(1)
                self._set_sale_feedback(
                    build_scanned_client_kept_feedback(),
                    "warning",
                    auto_clear_ms=2000,
                )
                self.sale_sku_input.setFocus()
                return True

        combo_index = self.sale_client_combo.findData(int(client.id))
        if combo_index < 0:
            raise ValueError(f"El cliente escaneado '{scanned_code}' no esta disponible en Caja.")

        self.sale_client_combo.setCurrentIndex(combo_index)
        self.sale_last_scanned_sku = client.codigo_cliente
        self.sale_last_scanned_at = monotonic()
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self._play_sale_feedback_sound()
        discount = self._selected_sale_client_discount()
        discount_label = self._format_discount_label(discount) if discount > Decimal("0.00") else "0%"
        self._set_sale_feedback(
            build_client_linked_feedback(
                client_code=client.codigo_cliente,
                client_name=client.nombre,
                discount_label=discount_label,
            ),
            "positive",
            auto_clear_ms=2200,
        )
        self.sale_sku_input.setFocus()
        return True

    @staticmethod
    def _build_sale_loyalty_transition_notice(
        client_name: str,
        previous_label: str,
        new_label: str,
        new_discount: Decimal | str | int | float,
    ) -> str:
        return build_sale_loyalty_transition_notice(
            client_name=client_name,
            previous_label=previous_label,
            new_label=new_label,
            new_discount=new_discount,
            format_discount_label=MainWindow._format_discount_label,
        )

    def _sale_discount_presets(self) -> list[Decimal]:
        default_values = [
            Decimal("5.00"),
            Decimal("10.00"),
            Decimal("15.00"),
            Decimal("20.00"),
        ]
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                values = [
                    self._normalize_discount_value(config.discount_basico),
                    self._normalize_discount_value(config.discount_leal),
                    self._normalize_discount_value(config.discount_profesor),
                    self._normalize_discount_value(config.discount_mayorista),
                ]
        except Exception:
            values = default_values
        return sorted({value for value in values if value > Decimal("0.00")})

    def _selected_sale_client_discount(self) -> Decimal:
        selected_client_id = self.sale_client_combo.currentData()
        if selected_client_id in {None, ""}:
            return Decimal("0.00")
        try:
            with get_session() as session:
                client = session.get(Cliente, int(selected_client_id))
                if client is None:
                    return Decimal("0.00")
                benefit = resolve_sale_client_benefit(
                    preferred_discount=client.descuento_preferente,
                    loyalty_level=client.nivel_lealtad,
                    loyalty_discount_resolver=lambda level: LoyaltyService.discount_for_level(level, session=session),
                    normalize_discount_value=self._normalize_discount_value,
                )
                return benefit.discount_percent
        except Exception:
            return Decimal("0.00")

    def _reset_sale_client_discount_sync(self) -> None:
        state = resolve_sale_client_sync_state(
            has_selected_client=False,
            discount_percent=Decimal("0.00"),
            source_label="",
            normalize_discount_value=self._normalize_discount_value,
        )
        self._set_sale_discount_lock_state(
            locked=state.locked,
            discount_percent=state.discount_percent,
            source_label=state.source_label,
        )
        self._refresh_sale_cart_table()

    def _refresh_sale_discount_options(self, *, selected_discount: Decimal | int | float | str | None = None) -> None:
        current_discount = (
            self._normalize_discount_value(selected_discount)
            if selected_discount is not None
            else self._normalize_discount_value(self.sale_discount_combo.currentData())
        )
        deduped_options = build_sale_discount_options(
            preset_values=self._sale_discount_presets(),
            current_discount=current_discount,
            normalize_discount_value=self._normalize_discount_value,
            format_discount_label=self._format_discount_label,
        )

        self.sale_discount_combo.blockSignals(True)
        self.sale_discount_combo.clear()
        for label, value in deduped_options:
            self.sale_discount_combo.addItem(label, float(value))
        index = self.sale_discount_combo.findData(float(current_discount))
        self.sale_discount_combo.setCurrentIndex(index if index >= 0 else 0)
        self.sale_discount_combo.blockSignals(False)

    def _ensure_sale_discount_option(self, discount_percent: Decimal | str | int | float) -> int:
        normalized = self._normalize_discount_value(discount_percent)
        for index in range(self.sale_discount_combo.count()):
            option_value = self._normalize_discount_value(self.sale_discount_combo.itemData(index))
            if option_value == normalized:
                current_label = self.sale_discount_combo.itemText(index).strip()
                expected_label = expected_discount_option_label(
                    normalized,
                    normalize_discount_value=self._normalize_discount_value,
                    format_discount_label=self._format_discount_label,
                )
                if current_label != expected_label:
                    self.sale_discount_combo.setItemText(index, expected_label)
                return index
        label = expected_discount_option_label(
            normalized,
            normalize_discount_value=self._normalize_discount_value,
            format_discount_label=self._format_discount_label,
        )
        self.sale_discount_combo.addItem(label, float(normalized))
        return self.sale_discount_combo.count() - 1

    def _set_sale_discount_lock_state(self, *, locked: bool, discount_percent: Decimal, source_label: str = "") -> None:
        state = build_sale_discount_lock_state(
            locked=locked,
            discount_percent=discount_percent,
            source_label=source_label,
            normalize_discount_value=self._normalize_discount_value,
        )
        self.sale_discount_locked_to_client = state.locked
        self.sale_locked_discount_percent = state.discount_percent
        self.sale_locked_discount_source = state.source_label
        self.sale_discount_combo.setToolTip(
            build_sale_discount_lock_tooltip(
                state=state,
                format_discount_label=self._format_discount_label,
            )
        )

    def _set_sale_discount_combo_percent(self, discount_percent: Decimal | str | int | float) -> None:
        index = self._ensure_sale_discount_option(discount_percent)
        previous_state = self.sale_discount_combo.blockSignals(True)
        self.sale_discount_combo.setCurrentIndex(index)
        self.sale_discount_combo.blockSignals(previous_state)

    def _clear_sale_manual_promo_authorization(self) -> None:
        state = clear_manual_promo_state()
        self.sale_manual_promo_authorized = state.authorized
        self.sale_manual_promo_authorized_percent = state.authorized_percent

    def _current_manual_promo_percent(self) -> Decimal:
        return current_manual_promo_percent(
            selected_percent=self.sale_discount_combo.currentData(),
            state=build_manual_promo_state(
                authorized=self.sale_manual_promo_authorized,
                authorized_percent=self.sale_manual_promo_authorized_percent,
            ),
        )

    def _prompt_manual_promo_authorization(self, promo_percent: Decimal) -> bool:
        code, accepted = QInputDialog.getText(
            self,
            "Autorizar promocion manual",
            (
                f"Captura el codigo para autorizar la promocion manual de "
                f"{self._format_discount_label(promo_percent)}."
            ),
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return False
        try:
            with get_session() as session:
                if not ManualPromoService.verify_authorization_code(session, code):
                    raise ValueError("Codigo invalido.")
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Codigo invalido", str(exc))
            return False
        return True

    def _handle_sale_discount_changed(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=self.sale_discount_combo.currentData(),
            state=build_manual_promo_state(
                authorized=self.sale_manual_promo_authorized,
                authorized_percent=self.sale_manual_promo_authorized_percent,
            ),
        )
        if decision.action == "clear":
            self._clear_sale_manual_promo_authorization()
            self._refresh_sale_cart_table()
            return
        if decision.action == "keep":
            self._refresh_sale_cart_table()
            return
        if not self._prompt_manual_promo_authorization(decision.selected_percent):
            self._set_sale_discount_combo_percent(decision.revert_percent)
            if not decision.previous_state.authorized:
                self._clear_sale_manual_promo_authorization()
            self._refresh_sale_cart_table()
            return
        new_state = apply_manual_promo_authorization(decision.selected_percent)
        self.sale_manual_promo_authorized = new_state.authorized
        self.sale_manual_promo_authorized_percent = new_state.authorized_percent
        self._set_sale_feedback(
            f"Promocion manual {self._format_discount_label(decision.selected_percent)} autorizada con codigo.",
            "warning",
            auto_clear_ms=1800,
        )
        self._refresh_sale_cart_table()

    def _sync_sale_discount_with_selected_client(self, *, reset_manual: bool = False) -> None:
        if reset_manual:
            self._set_sale_discount_combo_percent(Decimal("0.00"))
            self._clear_sale_manual_promo_authorization()

        selected_client_id = self.sale_client_combo.currentData()
        if selected_client_id in {None, ""}:
            self._reset_sale_client_discount_sync()
            return

        try:
            with get_session() as session:
                client = session.get(Cliente, int(selected_client_id))
                if client is None:
                    raise ValueError("No se pudo cargar el cliente seleccionado.")
                benefit = resolve_sale_client_benefit(
                    preferred_discount=client.descuento_preferente,
                    loyalty_level=client.nivel_lealtad,
                    loyalty_discount_resolver=lambda level: LoyaltyService.discount_for_level(level, session=session),
                    normalize_discount_value=self._normalize_discount_value,
                )
        except Exception:
            self._reset_sale_client_discount_sync()
            return

        state = resolve_sale_client_sync_state(
            has_selected_client=True,
            discount_percent=benefit.discount_percent,
            source_label=benefit.source_label,
            normalize_discount_value=self._normalize_discount_value,
        )
        self._set_sale_discount_lock_state(
            locked=state.locked,
            discount_percent=state.discount_percent,
            source_label=state.source_label,
        )
        self._refresh_sale_cart_table()

    def _handle_sale_client_changed(self) -> None:
        self._sync_sale_discount_with_selected_client(reset_manual=True)

    def _effective_sale_discount_percent(self) -> Decimal:
        loyalty_discount = self.sale_locked_discount_percent if self.sale_discount_locked_to_client else Decimal("0.00")
        promo_discount = self._current_manual_promo_percent()
        return effective_sale_discount_percent(
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
        )

    def _sale_discount_breakdown(self) -> dict[str, object]:
        loyalty_discount = self.sale_locked_discount_percent if self.sale_discount_locked_to_client else Decimal("0.00")
        promo_discount = self._current_manual_promo_percent()
        return build_sale_discount_breakdown(
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
            loyalty_source=self.sale_locked_discount_source or "Cliente",
        )

    def _calculate_sale_totals(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        loyalty_discount = self.sale_locked_discount_percent if self.sale_discount_locked_to_client else Decimal("0.00")
        promo_discount = self._current_manual_promo_percent()
        return calculate_sale_totals(
            self.sale_cart,
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
        )

    def _calculate_sale_pricing(self):
        loyalty_discount = self.sale_locked_discount_percent if self.sale_discount_locked_to_client else Decimal("0.00")
        promo_discount = self._current_manual_promo_percent()
        return calculate_sale_pricing(
            self.sale_cart,
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
        )

    def _load_business_payment_settings_snapshot(self):
        try:
            with get_session() as session:
                return load_business_payment_settings_snapshot(session)
        except Exception:
            return SimpleNamespace(
                business_name="POS Uniformes",
                transfer_bank="",
                transfer_beneficiary="",
                transfer_clabe="",
                transfer_instructions="",
            )

    def _prompt_cash_payment(self, total: Decimal) -> dict[str, object] | None:
        return build_cash_payment_dialog(self, total)

    def _prompt_transfer_payment(self, total: Decimal) -> dict[str, object] | None:
        business = self._load_business_payment_settings_snapshot()
        return build_transfer_payment_dialog(self, total, business)

    def _prompt_mixed_payment(self, total: Decimal) -> dict[str, object] | None:
        business = self._load_business_payment_settings_snapshot()
        return build_mixed_payment_dialog(self, total, business)

    def _collect_sale_payment_details(self, payment_method: str, total: Decimal) -> dict[str, object] | None:
        if payment_method == "Efectivo":
            return self._prompt_cash_payment(total)
        if payment_method == "Transferencia":
            return self._prompt_transfer_payment(total)
        if payment_method == "Mixto":
            return self._prompt_mixed_payment(total)
        return {"nota": []}

    def _refresh_payment_fields(self) -> None:
        pricing = self._calculate_sale_pricing()
        total = pricing.collected_total
        payment_method = self.sale_payment_combo.currentText() or "Efectivo"
        self.sale_received_spin.setValue(float(total))
        self.sale_change_label.setText("$0.00")
        self.sale_feedback_label.setToolTip(
            f"El cobro se completara en una ventana aparte para {payment_method.lower()}."
        )

    def _handle_add_sale_item(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede registrar ventas.")
            return
        if self.active_cash_session_id is None:
            QMessageBox.information(self, "Caja cerrada", "Abre caja antes de registrar ventas.")
            self._handle_cash_cut()
            return
        if not self._ensure_cash_session_current_day_for_operation("registrar ventas"):
            return

        sku = self.sale_sku_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "Datos incompletos", "Captura un SKU antes de agregar al carrito.")
            return

        quantity = self.sale_qty_spin.value()
        now = monotonic()
        if (
            quantity == 1
            and sku == self.sale_last_scanned_sku
            and now - self.sale_last_scanned_at <= 0.8
        ):
            self.sale_sku_input.clear()
            self.sale_qty_spin.setValue(1)
            self._set_sale_feedback(
                f"Se ignoro un posible doble escaneo de {sku}.",
                "warning",
                auto_clear_ms=1800,
            )
            self.sale_sku_input.setFocus()
            return

        try:
            with get_session() as session:
                client = self._find_active_client_by_code(session, sku)
                if client is not None:
                    if self._apply_scanned_client_to_sale(client, sku):
                        return
                variante = VentaService.obtener_variante_por_sku(session, sku)
                if variante is None:
                    raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")

                existing = next((item for item in self.sale_cart if item["sku"] == sku), None)
                new_quantity = quantity if existing is None else int(existing["cantidad"]) + quantity
                VentaService.validar_stock_disponible(variante, new_quantity)

                if existing is None:
                    self.sale_cart.append(
                        {
                            "sku": sku,
                            "variante_id": variante.id,
                            "producto_nombre": variante.producto.nombre,
                            "cantidad": quantity,
                            "precio_unitario": Decimal(variante.precio_venta),
                        }
                    )
                else:
                    existing["cantidad"] = new_quantity
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "Stock insuficiente" in message:
                message = f"No hay stock suficiente para agregar {quantity} pieza(s) de '{sku}'."
            QMessageBox.warning(self, "No se pudo agregar", message)
            self.sale_sku_input.setFocus()
            self.sale_sku_input.selectAll()
            return

        self.sale_last_scanned_sku = sku
        self.sale_last_scanned_at = now
        self._play_sale_feedback_sound()
        self._set_sale_feedback(
            f"{sku} agregado al carrito.",
            "positive",
            auto_clear_ms=1600,
        )
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self._refresh_sale_cart_table()
        self.sale_sku_input.setFocus()

    def _handle_remove_sale_item(self) -> None:
        selected_row = self.sale_cart_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.sale_cart):
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una linea del carrito.")
            return

        self.sale_cart.pop(selected_row)
        self._refresh_sale_cart_table()

    def _handle_clear_sale_cart(self) -> None:
        self.sale_cart.clear()
        self._refresh_sale_cart_table()
        self._reset_sale_form()
        self._set_sale_feedback("Carrito limpiado.", "neutral", auto_clear_ms=1400)

    def _prompt_quick_quote_client_data(self) -> dict[str, str] | None:
        dialog, layout = self._create_modal_dialog(
            "Nuevo cliente rapido",
            "Registra un cliente basico desde Presupuestos. Por ahora lo esencial es nombre y telefono.",
            width=420,
        )
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
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "nombre": name_input.text().strip(),
            "telefono": phone_input.text().strip(),
        }

    def _handle_create_quote_client(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede crear clientes desde Presupuestos.")
            return
        data = self._prompt_quick_quote_client_data()
        if data is None:
            return
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("Usuario no encontrado.")
                client = ClientService.create_client_quick(
                    session=session,
                    usuario=usuario,
                    nombre=data["nombre"],
                    telefono=data["telefono"],
                )
                session.flush()
                client_id = int(client.id)
                card_path, card_error = self._render_client_card_safe(client)
                session.commit()
                normalized_phone, qr_path, _qr_note = self._prepare_client_qr_delivery(client)
                _phone_for_card, _asset_path, card_note = self._prepare_client_card_delivery(client)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        for index in range(self.quote_client_combo.count()):
            client_data = self.quote_client_combo.itemData(index)
            if isinstance(client_data, dict) and int(client_data.get("id", 0)) == client_id:
                self.quote_client_combo.setCurrentIndex(index)
                break
        QMessageBox.information(
            self,
            "Cliente creado",
            (
                f"Cliente '{data['nombre']}' registrado y seleccionado en el presupuesto.\n"
                f"Telefono guardado: {normalized_phone}\n"
                f"QR listo para envio futuro por WhatsApp:\n{qr_path}\n\n"
                f"{'Credencial lista para enviar por WhatsApp: ' + str(card_path) if card_path is not None else 'Credencial pendiente: ' + str(card_error or 'sin detalle')}\n\n"
                f"Mensaje base preparado:\n{card_note}"
            ),
        )

    def _handle_add_quote_item(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede crear presupuestos.")
            return

        sku = self.quote_sku_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "Datos incompletos", "Captura un SKU antes de agregar al presupuesto.")
            return

        quantity = self.quote_qty_spin.value()
        try:
            with get_session() as session:
                variante = PresupuestoService.obtener_variante_por_sku(session, sku)
                if variante is None:
                    raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")
                existing = next((item for item in self.quote_cart if item["sku"] == sku), None)
                if existing is None:
                    self.quote_cart.append(
                        {
                            "sku": sku,
                            "variante_id": variante.id,
                            "producto_nombre": variante.producto.nombre_base,
                            "cantidad": quantity,
                            "precio_unitario": Decimal(variante.precio_venta),
                        }
                    )
                else:
                    existing["cantidad"] = int(existing["cantidad"]) + quantity
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo agregar", str(exc))
            return

        self.quote_sku_input.clear()
        self.quote_qty_spin.setValue(1)
        self._refresh_quote_cart_table()
        self.quote_sku_input.setFocus()

    def _handle_remove_quote_item(self) -> None:
        selected_row = self.quote_cart_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.quote_cart):
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una linea del presupuesto.")
            return
        self.quote_cart.pop(selected_row)
        self._refresh_quote_cart_table()

    def _handle_clear_quote_cart(self) -> None:
        self.quote_cart.clear()
        self._refresh_quote_cart_table()
        self._reset_quote_form()

    def _handle_save_quote(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "Tu usuario no puede crear presupuestos.")
            return
        if not self.quote_cart:
            if self.quote_sku_input.text().strip():
                self._handle_add_quote_item()
            if not self.quote_cart:
                QMessageBox.warning(self, "Presupuesto vacio", "Agrega al menos una linea al presupuesto.")
                return

        selected_client = self.quote_client_combo.currentData()
        client_id = int(selected_client["id"]) if isinstance(selected_client, dict) and selected_client.get("id") else None

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("Usuario no encontrado.")
                cliente = session.get(Cliente, client_id) if client_id is not None else None
                presupuesto = PresupuestoService.crear_presupuesto(
                    session=session,
                    usuario=usuario,
                    folio=self.quote_folio_input.text().strip() or self._generate_quote_folio(),
                    items=[
                        PresupuestoItemInput(sku=str(item["sku"]), cantidad=int(item["cantidad"]))
                        for item in self.quote_cart
                    ],
                    cliente=cliente,
                    cliente_nombre=cliente.nombre if cliente is not None else None,
                    cliente_telefono=cliente.telefono if cliente is not None else None,
                    vigencia_hasta=datetime.combine(
                        self.quote_validity_input.date().toPyDate(),
                        datetime.min.time(),
                    ),
                    observacion=self.quote_note_input.toPlainText().strip(),
                    estado=EstadoPresupuesto.EMITIDO,
                )
                session.commit()
                presupuesto_folio = presupuesto.folio
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return

        self.quote_cart.clear()
        self._refresh_quote_cart_table()
        self._reset_quote_form()
        self.refresh_all()
        QMessageBox.information(self, "Presupuesto guardado", f"Presupuesto {presupuesto_folio} registrado correctamente.")

    def _selected_quote_id(self) -> int | None:
        selected_row = self.quote_table.currentRow()
        if selected_row < 0:
            return None
        item = self.quote_table.item(selected_row, 0)
        if item is None:
            return None
        quote_id = item.data(Qt.ItemDataRole.UserRole)
        return int(quote_id) if quote_id is not None else None

    def _handle_quote_selection(self) -> None:
        self._refresh_quote_detail(self._selected_quote_id())
        self._refresh_permissions()

    def _handle_quote_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_quotes(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de presupuestos.")

    def _handle_cancel_quote(self) -> None:
        quote_id = self._selected_quote_id()
        if quote_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un presupuesto para cancelarlo.")
            return
        if QMessageBox.question(
            self,
            "Cancelar presupuesto",
            "Este cambio no afecta inventario, pero el presupuesto quedara marcado como cancelado. ¿Continuar?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                presupuesto = PresupuestoService.obtener_presupuesto(session, quote_id)
                usuario = session.get(Usuario, self.user_id)
                if presupuesto is None or usuario is None:
                    raise ValueError("No se pudo cargar el presupuesto seleccionado.")
                PresupuestoService.cancelar_presupuesto(
                    session=session,
                    presupuesto=presupuesto,
                    usuario=usuario,
                    observacion=f"Cancelado desde interfaz por {usuario.username}.",
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cancelar", str(exc))
            return
        self.refresh_all()
        QMessageBox.information(self, "Presupuesto cancelado", "El presupuesto se marco como cancelado.")

    def _handle_sale(self) -> None:
        if self.sale_processing:
            return
        if self.active_cash_session_id is None:
            QMessageBox.information(self, "Caja cerrada", "Abre caja antes de cobrar.")
            self._handle_cash_cut()
            return
        if not self._ensure_cash_session_current_day_for_operation("cobrar"):
            return
        folio = self.sale_folio_input.text().strip() or self._generate_sale_folio()
        if not self.sale_cart:
            if self.sale_sku_input.text().strip():
                self._handle_add_sale_item()
            if not self.sale_cart:
                QMessageBox.warning(self, "Carrito vacio", "Agrega al menos una linea al carrito.")
                return

        pricing = self._calculate_sale_pricing()
        subtotal = pricing.subtotal
        discount_percent = pricing.discount_percent
        applied_discount = pricing.applied_discount
        rounding_adjustment = pricing.rounding_adjustment
        total = pricing.collected_total
        payment_method = self.sale_payment_combo.currentText().strip() or "Efectivo"
        selected_client_id = self.sale_client_combo.currentData()
        breakdown = self._sale_discount_breakdown()
        loyalty_discount = self._normalize_discount_value(breakdown["loyalty_discount"])
        promo_discount = self._normalize_discount_value(breakdown["promo_discount"])
        payment_details = self._collect_sale_payment_details(payment_method, total)
        if payment_details is None:
            return
        sale_note_parts = build_sale_note_parts(
            payment_method=payment_method,
            discount_percent=discount_percent,
            applied_discount=applied_discount,
            rounding_adjustment=rounding_adjustment,
            breakdown=breakdown,
            format_discount_label=self._format_discount_label,
            extra_notes=list(payment_details.get("nota", [])),
        )
        loyalty_transition_notice = ""

        self._set_sale_processing(True)
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("Usuario no encontrado.")
                cliente = None
                previous_level = None
                previous_discount = None
                previous_level_label = ""
                client_name_for_notice = ""
                if selected_client_id not in {None, ""}:
                    cliente = session.get(Cliente, int(selected_client_id))
                    if cliente is None:
                        raise ValueError("No se pudo cargar el cliente seleccionado.")
                    previous_level = LoyaltyService.coerce_level(cliente.nivel_lealtad)
                    previous_discount = Decimal(str(cliente.descuento_preferente or Decimal("0.00"))).quantize(
                        Decimal("0.01")
                    )
                    previous_level_label = LoyaltyService.visual_spec(previous_level).label
                    client_name_for_notice = str(cliente.nombre)
                venta = VentaService.crear_borrador(
                    session=session,
                    usuario=usuario,
                    folio=folio,
                    items=[
                        VentaItemInput(sku=str(item["sku"]), cantidad=int(item["cantidad"]))
                        for item in self.sale_cart
                    ],
                    observacion=" | ".join(sale_note_parts),
                    cliente=cliente,
                )
                venta.subtotal = subtotal
                venta.descuento_porcentaje = discount_percent
                venta.descuento_monto = applied_discount
                venta.total = total
                VentaService.confirmar_venta(session, venta)
                if promo_discount > Decimal("0.00"):
                    ManualPromoService.log_authorized_promo(
                        session,
                        venta=venta,
                        actor_user=usuario,
                        cliente=cliente,
                        loyalty_percent=loyalty_discount,
                        promo_percent=promo_discount,
                        applied_percent=discount_percent,
                        applied_source=str(breakdown["winner_source"]),
                        note="Promocion manual autorizada con codigo en caja.",
                    )
                if cliente is not None and previous_level is not None and previous_discount is not None:
                    updated_level = LoyaltyService.coerce_level(cliente.nivel_lealtad)
                    updated_discount = Decimal(str(cliente.descuento_preferente or Decimal("0.00"))).quantize(
                        Decimal("0.01")
                    )
                    if updated_level != previous_level or updated_discount != previous_discount:
                        updated_label = LoyaltyService.visual_spec(updated_level).label
                        loyalty_transition_notice = self._build_sale_loyalty_transition_notice(
                            client_name_for_notice,
                            previous_level_label,
                            updated_label,
                            updated_discount,
                        )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            self._set_sale_processing(False)
            message = str(exc)
            if "Stock insuficiente" in message:
                message = "Uno de los productos ya no tiene stock suficiente. Revisa el carrito y vuelve a intentar."
            QMessageBox.critical(self, "Venta no completada", message)
            return
        finally:
            self._set_sale_processing(False)

        self._play_sale_feedback_sound()
        self.sale_cart.clear()
        self._refresh_sale_cart_table()
        self._reset_sale_form()
        self.refresh_all()
        self.sale_sku_input.setFocus()
        self._set_sale_feedback(
            f"Venta {folio} registrada. Total cobrado: {total} via {payment_method}.",
            "positive",
            auto_clear_ms=2200,
        )
        if loyalty_transition_notice:
            QMessageBox.information(
                self,
                "Nivel actualizado para siguiente compra",
                loyalty_transition_notice,
            )

    def _handle_cancel_sale(self) -> None:
        selected_row = self.recent_sales_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una venta en la tabla.")
            return
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede cancelar ventas.")
            return

        sale_id_item = self.recent_sales_table.item(selected_row, 0)
        if sale_id_item is None:
            QMessageBox.warning(self, "Sin seleccion", "No se pudo identificar la venta seleccionada.")
            return

        try:
            with get_session() as session:
                venta = session.get(Venta, int(sale_id_item.text()))
                admin = session.get(Usuario, self.user_id)
                if venta is None or admin is None:
                    raise ValueError("Venta o usuario ADMIN no encontrado.")
                VentaService.cancelar_venta(
                    session=session,
                    venta=venta,
                    admin_usuario=admin,
                    observacion="Cancelacion desde interfaz POS.",
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Cancelacion fallida", str(exc))
            return

        self.refresh_all()
        self._set_sale_feedback("Venta cancelada correctamente.", "warning", auto_clear_ms=1800)

    def _handle_inventory_adjustment(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede ajustar inventario.")
            return

        try:
            data = self._prompt_inventory_adjustment_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Datos incompletos", str(exc))
            return
        if data is None:
            return

        variante_id = data["variante_id"]
        if not variante_id:
            QMessageBox.warning(self, "Datos incompletos", "Selecciona una presentacion.")
            return

        signed_quantity = int(data["cantidad"])
        if signed_quantity == 0:
            QMessageBox.information(self, "Sin cambios", "El stock final coincide con el stock actual.")
            return
        reference = str(data["referencia"]).strip() or f"ADJ-{uuid4().hex[:8].upper()}"
        note = str(data["observacion"]).strip() or None
        target_stock = int(data.get("stock_final", 0))

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                variante = session.get(Variante, int(variante_id))
                if user is None or variante is None:
                    raise ValueError("Usuario o presentacion no encontrada.")
                InventarioService.registrar_ajuste_manual(
                    session=session,
                    variante=variante,
                    cantidad=signed_quantity,
                    usuario=user,
                    referencia=reference,
                    observacion=note,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ajuste fallido", str(exc))
            return

        self._set_combo_value(self.inventory_variant_combo, variante_id)
        self.refresh_all()
        QMessageBox.information(
            self,
            "Inventario actualizado",
            f"Ajuste {reference} aplicado correctamente. Stock final: {target_stock}.",
        )

    def _handle_inventory_bulk_adjustment(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede ajustar inventario en lote.")
            return

        try:
            data = self._prompt_inventory_bulk_adjustment_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Ajuste masivo no disponible", str(exc))
            return
        if data is None:
            return

        items = [
            AjusteMasivoFilaInput(variante_id=int(item["variante_id"]), valor_capturado=int(item["valor"]))
            for item in data.get("items", [])
        ]
        if not items:
            QMessageBox.warning(self, "Sin filas", "No hay filas para ajustar en el lote.")
            return

        reference = str(data["referencia"]).strip()
        motive = str(data["motivo"]).strip() or "Ajuste masivo desde interfaz POS."
        note = str(data["observacion"]).strip() or None

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                lote, preview = InventarioService.aplicar_ajuste_masivo(
                    session=session,
                    usuario=user,
                    tipo_fuente=str(data["tipo_fuente"]),
                    tipo_ajuste=str(data["tipo_ajuste"]),
                    referencia=reference,
                    motivo=motive,
                    observacion=note,
                    filas_input=items,
                )
                session.commit()
                lote_id = int(lote.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ajuste masivo fallido", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Ajuste masivo aplicado",
            (
                f"Lote {reference} aplicado correctamente.\n"
                f"ID lote: {lote_id}\n"
                f"Filas: {preview.total_filas}\n"
                f"Validas: {preview.filas_validas}\n"
                f"Unidades +: {preview.unidades_positivas}\n"
                f"Unidades -: {preview.unidades_negativas}"
            ),
        )

    def _handle_inventory_bulk_price_update(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede actualizar precios en lote.")
            return

        try:
            data = self._prompt_inventory_bulk_price_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Precio masivo no disponible", str(exc))
            return
        if data is None:
            return

        items = [
            (int(item["variante_id"]), Decimal(str(item["precio_nuevo"])))
            for item in data.get("items", [])
            if str(item.get("estado", "")) != "ERROR"
        ]
        if not items:
            QMessageBox.warning(self, "Sin filas", "No hay filas validas para actualizar precio en el lote.")
            return

        reference = str(data["referencia"]).strip()
        motive = str(data["motivo"]).strip() or "Cambio masivo de precio desde interfaz POS."
        note = str(data["observacion"]).strip() or None

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                resumen = CatalogService.aplicar_cambio_masivo_precio(
                    session=session,
                    usuario=user,
                    referencia=reference,
                    motivo=motive,
                    observacion=note,
                    precios_por_variante=items,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Precio masivo fallido", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Precio masivo aplicado",
            (
                f"Lote {reference} aplicado correctamente.\n"
                f"Filas: {resumen['total_filas']}\n"
                f"Actualizadas: {resumen['aplicadas']}\n"
                f"Suben: {resumen['suben']}\n"
                f"Bajan: {resumen['bajan']}\n"
                f"Sin cambios: {resumen['sin_cambios']}"
            ),
        )

    def _handle_inventory_count(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede realizar conteos fisicos.")
            return

        try:
            data = self._prompt_inventory_count_data()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Conteo no disponible", str(exc))
            return
        if data is None:
            return

        conteos = list(data.get("conteos", []))
        if not conteos:
            QMessageBox.information(self, "Sin diferencias", "No se detectaron diferencias entre sistema y conteo.")
            return

        reference = str(data["referencia"]).strip() or f"CONTEO-{uuid4().hex[:8].upper()}"
        note = str(data["observacion"]).strip() or "Conteo fisico desde interfaz POS."

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                for row in conteos:
                    variante = session.get(Variante, int(row["variante_id"]))
                    if variante is None:
                        raise ValueError("Presentacion no encontrada durante el conteo.")
                    InventarioService.registrar_ajuste_manual(
                        session=session,
                        variante=variante,
                        cantidad=int(row["delta"]),
                        usuario=user,
                        referencia=reference,
                        observacion=(
                            f"{note} Stock sistema {row['stock_sistema']} -> contado {row['stock_contado']}."
                        ),
                    )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Conteo fallido", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(
            self,
            "Conteo aplicado",
            f"Conteo {reference} aplicado correctamente. Filas ajustadas: {len(conteos)}.",
        )

    def _handle_generate_selected_qr(self) -> None:
        variante_id = self.inventory_variant_combo.currentData()
        if not variante_id:
            QMessageBox.warning(self, "Sin presentacion", "Selecciona una presentacion para generar su QR.")
            return

        try:
            with get_session() as session:
                variante = session.get(Variante, int(variante_id))
                if variante is None:
                    raise ValueError("Presentacion no encontrada.")
                path = QrGenerator.generate_for_variant(variante)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        self.qr_status_label.setText(f"Ultimo QR generado: {path.name}")
        self._set_combo_value(self.inventory_variant_combo, variante_id)
        self._load_qr_preview(path)
        self._handle_inventory_filters_changed()
        QMessageBox.information(self, "QR generado", f"QR guardado en:\n{path}")

    def _handle_generate_all_qr(self) -> None:
        try:
            with get_session() as session:
                variantes = session.scalars(
                    select(Variante).where(Variante.activo.is_(True)).order_by(Variante.sku)
                ).all()
                paths = QrGenerator.generate_many(list(variantes))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        directory = QrGenerator.output_dir()
        self.qr_status_label.setText(f"QRs generados en: {directory}")
        self._handle_inventory_filters_changed()
        self._refresh_selected_qr_preview()
        QMessageBox.information(
            self,
            "QRs generados",
            f"Se generaron {len(paths)} archivos en:\n{directory}",
        )

    def _handle_history_filter(self) -> None:
        try:
            with get_session() as session:
                self._refresh_history(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Filtros invalidos", str(exc))

    def refresh_all(self) -> None:
        try:
            with get_session() as session:
                self._refresh_current_user(session)
                self._refresh_cash_session(session)
                self._refresh_permissions()
                self._refresh_summary(session)
                self._refresh_combos(session)
                self._refresh_catalog(session)
                self._refresh_inventory_table(session)
                self._refresh_quotes(session)
                self._refresh_layaways(session)
                self._refresh_sales_table(session)
                self._refresh_analytics(session)
                self._refresh_history(session)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Estado: error al cargar datos - {exc}")
            return

        self._refresh_settings_backups()
        self._refresh_settings_users()
        self._refresh_settings_suppliers()
        self._refresh_settings_clients()
        metrics_text = self.metrics_label.text().strip()
        self.status_label.setText(
            "Estado: datos sincronizados con PostgreSQL."
            if not metrics_text
            else f"Estado: datos sincronizados con PostgreSQL. | {metrics_text}"
        )

    def _refresh_current_user(self, session) -> None:
        user = session.get(Usuario, self.user_id)
        if user is None or not user.activo:
            raise ValueError("El usuario autenticado ya no esta disponible.")

        self.current_username = user.username
        self.current_full_name = user.nombre_completo
        self.current_role = user.rol
        self.session_label.setText(f"{self.current_username} | {self.current_full_name}")

    def _refresh_cash_session(self, session) -> None:
        active_session = CajaService.obtener_sesion_activa(session)
        self.active_cash_session_id = active_session.id if active_session is not None else None
        if active_session is None:
            self.cash_session_requires_cut = False
            self.cash_session_label.setText(f"Rol {self.current_role.value} · Caja cerrada")
            self.cash_cut_button.setText("Abrir caja")
            return

        self.cash_session_requires_cut = self._is_stale_cash_session(active_session)
        resumen = CajaService.resumir_sesion(session, active_session)
        self.cash_session_label.setText(
            f"Rol {self.current_role.value} · Reactivo inicial ${Decimal(active_session.monto_apertura)} · Esperado ${resumen.esperado_en_caja}"
            + (" · Corte pendiente" if self.cash_session_requires_cut else "")
        )
        self.cash_cut_button.setText("Corte")

    def _refresh_permissions(self) -> None:
        is_admin = self.current_role == RolUsuario.ADMIN
        can_sell = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        can_manage_layaways = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        has_cash_session = self.active_cash_session_id is not None
        can_operate_open_cash = has_cash_session and not self.cash_session_requires_cut
        self._apply_role_navigation()
        self.category_button.setEnabled(is_admin)
        self.brand_button.setEnabled(is_admin)
        self.inventory_category_button.setEnabled(is_admin)
        self.inventory_brand_button.setEnabled(is_admin)
        self.product_button.setEnabled(is_admin)
        self.variant_button.setEnabled(is_admin)
        self.update_product_button.setEnabled(is_admin)
        self.update_variant_button.setEnabled(is_admin)
        self.toggle_product_button.setEnabled(is_admin)
        self.toggle_variant_button.setEnabled(is_admin)
        self.delete_product_button.setEnabled(is_admin)
        self.delete_variant_button.setEnabled(is_admin)
        self.inventory_new_button.setEnabled(is_admin)
        self.inventory_edit_button.setEnabled(is_admin)
        self.inventory_stock_button.setEnabled(is_admin)
        self.inventory_bulk_adjust_button.setEnabled(is_admin)
        self.inventory_bulk_price_button.setEnabled(is_admin)
        self.inventory_more_button.setEnabled(is_admin)
        self.purchase_button.setEnabled(is_admin)
        self.inventory_count_button.setEnabled(is_admin)
        self.inventory_print_label_button.setEnabled(is_admin)
        self.quote_add_button.setEnabled(can_sell)
        self.quote_create_client_button.setEnabled(can_sell)
        self.quote_save_button.setEnabled(can_sell)
        self.quote_remove_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_clear_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_cancel_button.setEnabled(can_sell and self._selected_quote_id() is not None)
        self.quote_refresh_button.setEnabled(can_sell)
        if self.header_more_button is not None:
            self.header_more_button.setVisible(is_admin)
        if self.connection_action is not None:
            self.connection_action.setEnabled(is_admin)
        if self.seed_action is not None:
            self.seed_action.setEnabled(is_admin)
        self.cancel_button.setEnabled(is_admin)
        self.inventory_adjust_button.setEnabled(is_admin)
        self.layaway_create_button.setEnabled(can_manage_layaways and can_operate_open_cash)
        self.layaway_payment_button.setEnabled(can_manage_layaways and can_operate_open_cash)
        self.layaway_deliver_button.setEnabled(can_manage_layaways and can_operate_open_cash)
        self.layaway_cancel_button.setEnabled(is_admin)
        self.layaway_receipt_button.setEnabled(can_manage_layaways)
        self.layaway_sale_ticket_button.setEnabled(can_manage_layaways and self._selected_layaway_id() is not None)
        self.layaway_whatsapp_button.setEnabled(can_manage_layaways and self._selected_layaway_id() is not None)
        self.sale_layaway_button.setEnabled(can_manage_layaways and can_operate_open_cash and bool(self.sale_cart))
        self.sale_layaway_button.setVisible(can_manage_layaways)
        self.cash_cut_button.setEnabled(can_sell)
        self.cash_movement_button.setEnabled(can_sell and has_cash_session)
        self.logout_button.setEnabled(True)
        self.sale_add_button.setEnabled(can_sell and can_operate_open_cash)
        self.sale_button.setEnabled(can_sell and can_operate_open_cash)
        self.sale_recent_button.setEnabled(True)
        self.sale_ticket_button.setEnabled(True)
        self.sale_remove_button.setEnabled(can_sell and can_operate_open_cash and bool(self.sale_cart))
        self.sale_clear_button.setEnabled(can_sell and can_operate_open_cash and bool(self.sale_cart))
        self.sale_layaway_button.setEnabled(can_manage_layaways and can_operate_open_cash and bool(self.sale_cart))
        self.sale_client_combo.setEnabled(is_admin)
        self.sale_discount_combo.setEnabled(is_admin)
        if is_admin:
            self.sale_client_combo.setToolTip(
                "Asocia un cliente manualmente o por QR. Puedes dejar Mostrador para venta general."
            )
            self.sale_discount_combo.setToolTip(
                "Aplica una promocion manual no acumulable. Si hay lealtad, se aplicara el mayor beneficio."
            )
        else:
            self.sale_client_combo.setToolTip(
                "Para CAJERO, el cliente solo se enlaza al escanear su QR o codigo."
            )
            self.sale_discount_combo.setToolTip(
                "Para CAJERO, el descuento se refleja automaticamente segun el cliente escaneado."
            )
        self.settings_create_backup_button.setEnabled(is_admin)
        self.settings_refresh_backups_button.setEnabled(True)
        self.settings_open_backups_button.setEnabled(True)
        self.settings_restore_backup_button.setEnabled(is_admin)
        self.settings_users_button.setEnabled(is_admin)
        self.settings_suppliers_button.setEnabled(is_admin)
        self.settings_clients_button.setEnabled(is_admin)
        self.settings_marketing_button.setEnabled(is_admin)
        self.settings_whatsapp_button.setEnabled(is_admin)
        self.settings_backup_button.setEnabled(is_admin)
        self.settings_cash_history_button.setEnabled(is_admin)
        self.settings_business_button.setEnabled(is_admin)
        self.settings_create_user_button.setEnabled(is_admin)
        self.settings_edit_user_button.setEnabled(is_admin)
        self.settings_toggle_user_button.setEnabled(is_admin)
        self.settings_change_role_button.setEnabled(is_admin)
        self.settings_change_password_button.setEnabled(is_admin)
        self.settings_create_supplier_button.setEnabled(is_admin)
        self.settings_update_supplier_button.setEnabled(is_admin)
        self.settings_toggle_supplier_button.setEnabled(is_admin)
        self.settings_create_client_button.setEnabled(is_admin)
        self.settings_update_client_button.setEnabled(is_admin)
        self.settings_toggle_client_button.setEnabled(is_admin)
        self.settings_generate_client_qr_button.setEnabled(is_admin)
        self.settings_client_whatsapp_button.setEnabled(is_admin)
        self.settings_marketing_save_button.setEnabled(is_admin)
        self.settings_marketing_recalculate_button.setEnabled(is_admin)
        self.settings_marketing_history_button.setEnabled(is_admin)
        self.settings_whatsapp_save_button.setEnabled(is_admin)
        self.settings_business_save_button.setEnabled(is_admin)
        self.settings_cash_history_refresh_button.setEnabled(is_admin)
        self.settings_cash_history_detail_button.setEnabled(is_admin and self._selected_cash_history_id() is not None)

        if self.dashboard_users_card is not None:
            self.dashboard_users_card.setVisible(is_admin)
        if self.dashboard_manual_promo_box is not None:
            self.dashboard_manual_promo_box.setVisible(is_admin)
        if self.dashboard_help_box is not None:
            self.dashboard_help_box.setTitle("Flujo sugerido" if is_admin else "Flujo rapido de caja")
        self.analytics_label.setVisible(is_admin)
        self.layaway_alerts_label.setVisible(is_admin)
        if self.products_quick_setup_box is not None:
            self.products_quick_setup_box.setVisible(is_admin)

        self.catalog_permission_label.setText(
            "Esta pestaña es de consulta. Las altas, cambios de precio y existencias se gestionan en Inventario."
            if is_admin
            else "Consulta precio, stock y estado de cada presentacion sin salir de caja."
        )
        self.purchase_permission_label.setText(
            "" if is_admin else "Compras y carga de datos demo disponibles solo para ADMIN."
        )
        self.cancel_permission_label.setText(
            "" if is_admin else "La cancelacion de ventas esta restringida a ADMIN."
        )
        self.inventory_permission_label.setText(
            "" if is_admin else "Las altas, entradas, conteos, ajustes, cambios de precio y eliminacion estan restringidos a ADMIN."
        )
        self.layaway_status_label.setText(self.layaway_status_label.text())
        self.layaway_quick_alerts_label.setText(self.layaway_quick_alerts_label.text())

    def _refresh_summary(self, session) -> None:
        usuarios = session.scalar(select(func.count(Usuario.id))) or 0
        proveedores = session.scalar(select(func.count(Proveedor.id))) or 0
        productos = session.scalar(select(func.count(Producto.id))) or 0
        variantes = session.scalar(select(func.count(Variante.id))) or 0
        stock_total = session.scalar(select(func.coalesce(func.sum(Variante.stock_actual), 0))) or 0
        compras = session.scalar(select(func.count(Compra.id))) or 0
        ventas = session.scalar(select(func.count(Venta.id))) or 0
        ventas_confirmadas = session.scalar(
            select(func.count(Venta.id)).where(Venta.estado == EstadoVenta.CONFIRMADA)
        ) or 0
        ingresos = session.scalar(
            select(func.coalesce(func.sum(Venta.total), 0)).where(Venta.estado == EstadoVenta.CONFIRMADA)
        ) or Decimal("0.00")
        compras_confirmadas = session.scalar(
            select(func.coalesce(func.sum(Compra.total), 0)).where(Compra.estado == EstadoCompra.CONFIRMADA)
        ) or Decimal("0.00")
        stock_bajo = session.scalar(select(func.count(Variante.id)).where(Variante.stock_actual <= 3)) or 0
        hoy = date.today()
        semana = hoy + timedelta(days=7)
        apartados_vencidos = session.scalar(
            select(func.count(Apartado.id)).where(
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
                Apartado.fecha_compromiso.is_not(None),
                func.date(Apartado.fecha_compromiso) < hoy,
            )
        ) or 0
        apartados_hoy = session.scalar(
            select(func.count(Apartado.id)).where(
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
                Apartado.fecha_compromiso.is_not(None),
                func.date(Apartado.fecha_compromiso) == hoy,
            )
        ) or 0
        apartados_semana = session.scalar(
            select(func.count(Apartado.id)).where(
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
                Apartado.fecha_compromiso.is_not(None),
                func.date(Apartado.fecha_compromiso) > hoy,
                func.date(Apartado.fecha_compromiso) <= semana,
            )
        ) or 0
        manual_promo_summary = ManualPromoService.summarize_today(session, limit=4)

        is_admin = self.current_role == RolUsuario.ADMIN
        self.metrics_label.setText(
            " | ".join(
                [
                    f"Usuarios: {usuarios}",
                    f"Proveedores: {proveedores}",
                    f"Productos: {productos}",
                    f"Presentaciones: {variantes}",
                    f"Stock total: {stock_total}",
                    f"Compras: {compras}",
                    f"Ventas: {ventas}",
                ]
                if is_admin
                else [
                    f"Productos: {productos}",
                    f"Presentaciones: {variantes}",
                    f"Stock total: {stock_total}",
                    f"Ventas: {ventas}",
                ]
            )
        )
        self.kpi_users_value.setText(str(usuarios))
        self.kpi_products_value.setText(str(productos))
        self.kpi_stock_value.setText(str(stock_total))
        self.kpi_sales_value.setText(str(ventas))
        self.analytics_label.setText(
            " | ".join(
                [
                    f"Ventas confirmadas: {ventas_confirmadas}",
                    f"Ingreso confirmado: {ingresos}",
                    f"Compras confirmadas: {compras_confirmadas}",
                    f"Presentaciones con stock bajo (<=3): {stock_bajo}",
                ]
                if is_admin
                else [
                    f"Ventas confirmadas: {ventas_confirmadas}",
                    f"Ingreso confirmado: {ingresos}",
                ]
            )
        )
        self.layaway_alerts_label.setTextFormat(Qt.TextFormat.RichText)
        self.layaway_alerts_label.setText(
            "".join(
                [
                    _inline_metric_badge("Vencidos", apartados_vencidos, "danger" if apartados_vencidos else "neutral"),
                    _inline_metric_badge("Hoy", apartados_hoy, "warning" if apartados_hoy else "neutral"),
                    _inline_metric_badge("7 dias", apartados_semana, "positive" if apartados_semana else "neutral"),
                ]
            )
        )
        self.layaway_quick_alerts_label.setText(
            " | ".join(
                [
                    f"Apartados vencidos: {apartados_vencidos}",
                    f"Vencen hoy: {apartados_hoy}",
                    f"Proximos 7 dias: {apartados_semana}",
                ]
            )
        )
        if manual_promo_summary.total_hoy <= 0:
            self.dashboard_manual_promo_label.setText("Sin promociones manuales autorizadas hoy.")
            self.dashboard_manual_promo_label.setProperty("tone", "neutral")
        else:
            recent_lines = []
            for item in manual_promo_summary.recientes:
                actor = item.usuario.nombre_completo if item.usuario is not None else (item.rol_usuario or "Usuario")
                folio = item.folio_venta or "Sin folio"
                promo = self._format_discount_label(Decimal(str(item.porcentaje_promocion or Decimal("0.00"))))
                recent_lines.append(f"{actor} · {folio} · {promo}")
            self.dashboard_manual_promo_label.setText(
                f"Promos manuales hoy: {manual_promo_summary.total_hoy}\n" + "\n".join(recent_lines)
            )
            self.dashboard_manual_promo_label.setProperty(
                "tone",
                "warning" if manual_promo_summary.total_hoy <= 3 else "danger",
            )
        self.dashboard_manual_promo_label.style().unpolish(self.dashboard_manual_promo_label)
        self.dashboard_manual_promo_label.style().polish(self.dashboard_manual_promo_label)
        self.dashboard_manual_promo_label.update()

    def _refresh_catalog(self, session) -> None:
        selected_variant_id = None
        selected_row = self.catalog_table.currentRow()
        if 0 <= selected_row < len(self.catalog_rows):
            selected_variant_id = int(self.catalog_rows[selected_row]["variante_id"])

        layaway_reserved_subquery = (
            select(
                ApartadoDetalle.variante_id.label("variante_id"),
                func.coalesce(func.sum(ApartadoDetalle.cantidad), 0).label("apartado_cantidad"),
            )
            .join(ApartadoDetalle.apartado)
            .where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
            .group_by(ApartadoDetalle.variante_id)
            .subquery()
        )

        rows = session.execute(
            select(
                Variante.id,
                Producto.id,
                Categoria.id,
                Marca.id,
                Escuela.id,
                Variante.sku,
                Categoria.nombre,
                Marca.nombre,
                Escuela.nombre,
                TipoPrenda.nombre,
                TipoPieza.nombre,
                Producto.nombre,
                Producto.nombre_base,
                Producto.descripcion,
                Variante.nombre_legacy,
                Variante.origen_legacy,
                Variante.talla,
                Variante.color,
                Variante.precio_venta,
                Variante.costo_referencia,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Producto.activo,
                Variante.activo,
                func.coalesce(ImportacionCatalogoFila.producto_fallback, False),
            )
            .join(Variante.producto)
            .join(Producto.categoria)
            .join(Producto.marca)
            .outerjoin(Producto.escuela)
            .outerjoin(Producto.tipo_prenda)
            .outerjoin(Producto.tipo_pieza)
            .outerjoin(ImportacionCatalogoFila, ImportacionCatalogoFila.variante_id == Variante.id)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
            .order_by(
                Categoria.nombre.asc(),
                Escuela.nombre.asc().nullslast(),
                Marca.nombre.asc(),
                Producto.nombre.asc(),
                Variante.sku.asc(),
            )
        ).all()

        search_text = self.catalog_search_input.text().strip()
        category_filters = self.catalog_category_filter_combo.selected_values()
        brand_filters = self.catalog_brand_filter_combo.selected_values()
        school_filters = self.catalog_school_filter_combo.selected_values()
        type_filters = self.catalog_type_filter_combo.selected_values()
        piece_filters = self.catalog_piece_filter_combo.selected_values()
        size_filters = self.catalog_size_filter_combo.selected_values()
        color_filters = self.catalog_color_filter_combo.selected_values()
        status_filter = str(self.catalog_status_filter_combo.currentData() or "")
        stock_filter = str(self.catalog_stock_filter_combo.currentData() or "")
        catalog_filter = str(self.catalog_layaway_filter_combo.currentData() or "")
        origin_filter = str(self.catalog_origin_filter_combo.currentData() or "")
        duplicate_filter = str(self.catalog_duplicate_filter_combo.currentData() or "")

        self.catalog_rows = [
            {
                "variante_id": row[0],
                "producto_id": row[1],
                "categoria_id": row[2],
                "marca_id": row[3],
                "escuela_id": row[4],
                "sku": row[5],
                "categoria_nombre": row[6],
                "marca_nombre": row[7],
                "escuela_nombre": row[8] or "General",
                "tipo_prenda_nombre": row[9] or "-",
                "tipo_pieza_nombre": row[10] or "-",
                "producto_nombre": row[11],
                "producto_nombre_base": row[12],
                "producto_descripcion": row[13],
                "nombre_legacy": row[14],
                "origen_legacy": bool(row[15]),
                "talla": row[16],
                "color": row[17],
                "precio_venta": row[18],
                "costo_referencia": row[19],
                "stock_actual": row[20],
                "apartado_cantidad": row[21],
                "producto_activo": row[22],
                "variante_activo": row[23],
                "producto_estado": "ACTIVO" if row[22] else "INACTIVO",
                "variante_estado": "ACTIVA" if row[23] else "INACTIVA",
                "origen_etiqueta": "LEGACY" if row[15] else "NUEVO",
                "fallback_importacion": bool(row[24]),
            }
            for row in rows
            if (
                self._catalog_row_matches_search(
                    {
                        "sku": row[5],
                        "categoria_nombre": row[6],
                        "marca_nombre": row[7],
                        "escuela_nombre": row[8] or "General",
                        "tipo_prenda_nombre": row[9] or "-",
                        "tipo_pieza_nombre": row[10] or "-",
                        "producto_nombre": row[11],
                        "producto_nombre_base": row[12],
                        "producto_descripcion": row[13],
                        "nombre_legacy": row[14],
                        "origen_etiqueta": "LEGACY" if row[15] else "NUEVO",
                        "producto_estado": "ACTIVO" if row[22] else "INACTIVO",
                        "variante_estado": "ACTIVA" if row[23] else "INACTIVA",
                        "fallback_text": "fallback" if bool(row[24]) else "",
                        "talla": row[16],
                        "color": row[17],
                    },
                    search_text,
                )
                and (not category_filters or str(row[6] or "") in category_filters)
                and (not brand_filters or str(row[7] or "") in brand_filters)
                and (not school_filters or str(row[8] or "General") in school_filters)
                and (not type_filters or str(row[9] or "-") in type_filters)
                and (not piece_filters or str(row[10] or "-") in piece_filters)
                and (not size_filters or str(row[16] or "") in size_filters)
                and (not color_filters or str(row[17] or "") in color_filters)
                and (
                    not status_filter
                    or (status_filter == "active" and bool(row[23]))
                    or (status_filter == "inactive" and not bool(row[23]))
                )
                and (
                    not stock_filter
                    or (stock_filter == "in_stock" and int(row[20]) > 0)
                    or (stock_filter == "out_of_stock" and int(row[20]) == 0)
                    or (stock_filter == "low_stock" and 0 < int(row[20]) <= 3)
                    or (stock_filter == "available_over_reserved" and int(row[20]) > int(row[21]))
                )
                and (
                    not catalog_filter
                    or (catalog_filter == "reserved" and int(row[21]) > 0)
                    or (catalog_filter == "free" and int(row[21]) == 0)
                )
                and (
                    not origin_filter
                    or (origin_filter == "legacy" and bool(row[15]))
                    or (origin_filter == "native" and not bool(row[15]))
                )
                and (
                    not duplicate_filter
                    or (duplicate_filter == "fallback_only" and bool(row[24]))
                    or (duplicate_filter == "fallback_exclude" and not bool(row[24]))
                )
            )
        ]

        self.catalog_table.setRowCount(len(self.catalog_rows))
        for row_index, row in enumerate(self.catalog_rows):
            values = [
                row["sku"],
                row["escuela_nombre"],
                row["tipo_prenda_nombre"],
                row["tipo_pieza_nombre"],
                row["marca_nombre"],
                row["producto_nombre_base"],
                row["talla"],
                row["color"],
                row["precio_venta"],
                row["stock_actual"],
                row["apartado_cantidad"],
                row["variante_estado"],
            ]
            for column_index, value in enumerate(values):
                self.catalog_table.setItem(row_index, column_index, _table_item(value))
        self.catalog_table.resizeColumnsToContents()
        self.catalog_results_label.setText(self._build_catalog_results_summary(rows_count=len(rows)))
        self.catalog_active_filters_label.setText(self._build_catalog_active_filters_summary())
        if selected_variant_id is not None and not self._select_catalog_variant(selected_variant_id):
            self._clear_catalog_editor()
        elif selected_variant_id is None:
            self._clear_catalog_editor()

    @staticmethod
    def _catalog_search_alias_map() -> dict[str, tuple[str, ...]]:
        return {
            "sku": ("sku",),
            "escuela": ("escuela_nombre",),
            "tipo": ("tipo_prenda_nombre",),
            "pieza": ("tipo_pieza_nombre",),
            "producto": ("producto_nombre_base", "producto_nombre"),
            "legacy": ("nombre_legacy",),
            "talla": ("talla",),
            "color": ("color",),
            "marca": ("marca_nombre",),
            "categoria": ("categoria_nombre",),
            "origen": ("origen_etiqueta",),
            "estado": ("producto_estado", "variante_estado"),
            "fallback": ("fallback_text",),
        }

    @classmethod
    def _catalog_row_matches_search(cls, row: dict[str, object], search_text: str) -> bool:
        return row_matches_search(
            row,
            search_text=search_text,
            alias_map=cls._catalog_search_alias_map(),
            general_fields=(
                "sku",
                "categoria_nombre",
                "marca_nombre",
                "escuela_nombre",
                "tipo_prenda_nombre",
                "tipo_pieza_nombre",
                "producto_nombre",
                "producto_nombre_base",
                "producto_descripcion",
                "nombre_legacy",
                "talla",
                "color",
                "origen_etiqueta",
                "producto_estado",
                "variante_estado",
                "fallback_text",
            ),
        )

    def _build_catalog_results_summary(self, *, rows_count: int) -> str:
        filtered_count = len(self.catalog_rows)
        total_stock = sum(int(row["stock_actual"]) for row in self.catalog_rows)
        reserved_count = sum(1 for row in self.catalog_rows if int(row["apartado_cantidad"]) > 0)
        fallback_count = sum(1 for row in self.catalog_rows if bool(row.get("fallback_importacion")))
        active_filters = self._catalog_active_filter_labels()
        filters_label = build_filters_label(active_filters)
        return (
            f"Resultados: {filtered_count} de {rows_count} | Stock visible: {total_stock} | "
            f"Con apartados: {reserved_count} | Fallbacks: {fallback_count} | Filtros: {filters_label}"
        )

    def _catalog_active_filter_labels(self) -> list[str]:
        return build_active_filter_labels(
            search_text=self.catalog_search_input.text(),
            multi_filters=(
                ("categoria", self.catalog_category_filter_combo.selected_labels()),
                ("marca", self.catalog_brand_filter_combo.selected_labels()),
                ("escuela", self.catalog_school_filter_combo.selected_labels()),
                ("tipo_uniforme", self.catalog_type_filter_combo.selected_labels()),
                ("pieza", self.catalog_piece_filter_combo.selected_labels()),
                ("talla", self.catalog_size_filter_combo.selected_labels()),
                ("color", self.catalog_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("estado", self.catalog_status_filter_combo.currentData(), self.catalog_status_filter_combo.currentText()),
                ("stock", self.catalog_stock_filter_combo.currentData(), self.catalog_stock_filter_combo.currentText()),
                ("apartados", self.catalog_layaway_filter_combo.currentData(), self.catalog_layaway_filter_combo.currentText()),
                ("origen", self.catalog_origin_filter_combo.currentData(), self.catalog_origin_filter_combo.currentText()),
                ("incidencias", self.catalog_duplicate_filter_combo.currentData(), self.catalog_duplicate_filter_combo.currentText()),
            ),
        )

    def _build_catalog_active_filters_summary(self) -> str:
        return build_active_filters_summary(self._catalog_active_filter_labels())

    @staticmethod
    def _inventory_search_alias_map() -> dict[str, tuple[str, ...]]:
        return {
            "sku": ("sku",),
            "escuela": ("escuela_nombre",),
            "tipo": ("tipo_prenda_nombre",),
            "pieza": ("tipo_pieza_nombre",),
            "producto": ("producto_nombre_base", "producto_nombre"),
            "legacy": ("nombre_legacy",),
            "talla": ("talla",),
            "color": ("color",),
            "marca": ("marca_nombre",),
            "categoria": ("categoria_nombre",),
            "origen": ("origen_etiqueta",),
            "estado": ("variante_estado",),
            "fallback": ("fallback_text",),
        }

    @classmethod
    def _inventory_row_matches_search(cls, row: dict[str, object], search_text: str) -> bool:
        return row_matches_search(
            row,
            search_text=search_text,
            alias_map=cls._inventory_search_alias_map(),
            general_fields=(
                "sku",
                "categoria_nombre",
                "marca_nombre",
                "escuela_nombre",
                "tipo_prenda_nombre",
                "tipo_pieza_nombre",
                "producto_nombre",
                "producto_nombre_base",
                "nombre_legacy",
                "talla",
                "color",
                "origen_etiqueta",
                "variante_estado",
                "fallback_text",
            ),
        )

    def _inventory_active_filter_labels(self) -> list[str]:
        return build_active_filter_labels(
            search_text=self.inventory_search_input.text(),
            multi_filters=(
                ("categoria", self.inventory_category_filter_combo.selected_labels()),
                ("marca", self.inventory_brand_filter_combo.selected_labels()),
                ("escuela", self.inventory_school_filter_combo.selected_labels()),
                ("tipo", self.inventory_type_filter_combo.selected_labels()),
                ("pieza", self.inventory_piece_filter_combo.selected_labels()),
                ("talla", self.inventory_size_filter_combo.selected_labels()),
                ("color", self.inventory_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("estado", self.inventory_status_filter_combo.currentData(), self.inventory_status_filter_combo.currentText()),
                ("stock", self.inventory_stock_filter_combo.currentData(), self.inventory_stock_filter_combo.currentText()),
                ("qr", self.inventory_qr_filter_combo.currentData(), self.inventory_qr_filter_combo.currentText()),
                ("origen", self.inventory_origin_filter_combo.currentData(), self.inventory_origin_filter_combo.currentText()),
                ("incidencias", self.inventory_duplicate_filter_combo.currentData(), self.inventory_duplicate_filter_combo.currentText()),
            ),
        )

    def _build_inventory_active_filters_summary(self) -> str:
        return build_active_filters_summary(self._inventory_active_filter_labels())

    def _build_inventory_results_summary(self, *, total_rows: int, visible_rows: list[dict[str, object]]) -> str:
        total_stock = sum(int(row["stock_actual"]) for row in visible_rows)
        reserved_count = sum(1 for row in visible_rows if int(row["apartado_cantidad"]) > 0)
        fallback_count = sum(1 for row in visible_rows if bool(row.get("fallback_importacion")))
        filters_label = build_filters_label(self._inventory_active_filter_labels())
        return (
            f"Resultados: {len(visible_rows)} de {total_rows} | Stock visible: {total_stock} | "
            f"Con apartados: {reserved_count} | Fallbacks: {fallback_count} | Filtros: {filters_label}"
        )

    def _refresh_combos(self, session) -> None:
        categorias = session.scalars(select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)).all()
        marcas = session.scalars(select(Marca).where(Marca.activo.is_(True)).order_by(Marca.nombre)).all()
        escuelas = session.scalars(select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)).all()
        tipos_prenda = session.scalars(select(TipoPrenda).where(TipoPrenda.activo.is_(True)).order_by(TipoPrenda.nombre)).all()
        tipos_pieza = session.scalars(select(TipoPieza).where(TipoPieza.activo.is_(True)).order_by(TipoPieza.nombre)).all()
        tallas = session.execute(select(Variante.talla).distinct().order_by(Variante.talla)).scalars().all()
        colores = session.execute(select(Variante.color).distinct().order_by(Variante.color)).scalars().all()
        productos = session.scalars(select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre)).all()
        proveedores = session.scalars(select(Proveedor).where(Proveedor.activo.is_(True)).order_by(Proveedor.nombre)).all()
        clientes = session.scalars(select(Cliente).where(Cliente.activo.is_(True)).order_by(Cliente.nombre)).all()
        variantes_activas = session.scalars(
            select(Variante).where(Variante.activo.is_(True)).order_by(Variante.sku)
        ).all()
        variantes_inventario = session.scalars(select(Variante).order_by(Variante.sku)).all()

        self._populate_combo(self.product_category_combo, [(categoria.nombre, categoria.id) for categoria in categorias])
        self._populate_combo(self.product_brand_combo, [(marca.nombre, marca.id) for marca in marcas])
        self._populate_combo(self.edit_product_category_combo, [(categoria.nombre, categoria.id) for categoria in categorias])
        self._populate_combo(self.edit_product_brand_combo, [(marca.nombre, marca.id) for marca in marcas])
        self.catalog_category_filter_combo.set_items([(categoria.nombre, categoria.nombre) for categoria in categorias])
        self.catalog_brand_filter_combo.set_items([(marca.nombre, marca.nombre) for marca in marcas])
        self.catalog_school_filter_combo.set_items([(escuela.nombre, escuela.nombre) for escuela in escuelas])
        self.catalog_type_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_prenda])
        self.catalog_piece_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_pieza])
        self.catalog_size_filter_combo.set_items([(str(talla), str(talla)) for talla in tallas if talla])
        self.catalog_color_filter_combo.set_items([(str(color), str(color)) for color in colores if color])
        self.inventory_category_filter_combo.set_items([(categoria.nombre, categoria.nombre) for categoria in categorias])
        self.inventory_brand_filter_combo.set_items([(marca.nombre, marca.nombre) for marca in marcas])
        self.inventory_school_filter_combo.set_items([(escuela.nombre, escuela.nombre) for escuela in escuelas])
        self.inventory_type_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_prenda])
        self.inventory_piece_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_pieza])
        self.inventory_size_filter_combo.set_items([(str(talla), str(talla)) for talla in tallas if talla])
        self.inventory_color_filter_combo.set_items([(str(color), str(color)) for color in colores if color])
        self._populate_combo(
            self.variant_product_combo,
            [(f"{producto.nombre} | {producto.marca.nombre}", producto.id) for producto in productos],
        )
        self._populate_combo(
            self.edit_variant_product_combo,
            [(f"{producto.nombre} | {producto.marca.nombre}", producto.id) for producto in productos],
        )
        self._populate_combo(
            self.purchase_provider_combo,
            [(proveedor.nombre, proveedor.id) for proveedor in proveedores],
        )
        self._populate_filter_combo(
            self.sale_client_combo,
            "Mostrador / sin cliente",
            [(f"{cliente.codigo_cliente} · {cliente.nombre}", cliente.id) for cliente in clientes],
        )
        self._refresh_sale_discount_options()
        self.quote_client_combo.blockSignals(True)
        self.quote_client_combo.clear()
        self.quote_client_combo.addItem("Manual / sin cliente", None)
        for cliente in clientes:
            self.quote_client_combo.addItem(
                f"{cliente.codigo_cliente} · {cliente.nombre}",
                {
                    "id": int(cliente.id),
                    "nombre": cliente.nombre,
                    "telefono": cliente.telefono or "",
                },
            )
        self.quote_client_combo.blockSignals(False)
        self._populate_filter_combo(
            self.analytics_client_combo,
            "Cliente: todos",
            [(f"{cliente.codigo_cliente} · {cliente.nombre}", cliente.id) for cliente in clientes],
        )
        purchase_variant_items = [
            (f"{variante.sku} | {variante.producto.nombre} | stock {variante.stock_actual}", variante.id)
            for variante in variantes_activas
        ]
        inventory_variant_items = [
            (f"{variante.sku} | {variante.producto.nombre} | stock {variante.stock_actual}", variante.id)
            for variante in variantes_inventario
        ]
        self._populate_combo(self.purchase_variant_combo, purchase_variant_items)
        self._populate_combo(self.inventory_variant_combo, inventory_variant_items)
        self._refresh_selected_qr_preview()

    def _refresh_sales_table(self, session) -> None:
        sales = session.scalars(select(Venta).order_by(desc(Venta.created_at)).limit(20)).all()
        self.recent_sales_table.setRowCount(len(sales))
        for row_index, sale in enumerate(sales):
            values = [
                sale.id,
                sale.folio,
                sale.cliente.nombre if sale.cliente is not None else "Mostrador",
                sale.usuario.username if sale.usuario else "",
                sale.estado.value,
                sale.total,
                sale.created_at.strftime("%Y-%m-%d %H:%M") if sale.created_at else "",
            ]
            for column_index, value in enumerate(values):
                self.recent_sales_table.setItem(row_index, column_index, _table_item(value))
        self.recent_sales_table.resizeColumnsToContents()
        self._refresh_sale_cart_table()

    def _refresh_quotes(self, session) -> None:
        selected_quote_id = self._selected_quote_id()
        search_text = self.quote_search_input.text().strip().lower()
        state_filter = str(self.quote_state_combo.currentData() or "")
        presupuestos = PresupuestoService.listar_presupuestos(session, limit=200)

        rows: list[dict[str, object]] = []
        for presupuesto in presupuestos:
            if state_filter and presupuesto.estado.value != state_filter:
                continue
            searchable = " ".join(
                [
                    presupuesto.folio,
                    presupuesto.cliente_nombre or "",
                    presupuesto.cliente_telefono or "",
                    " ".join(detalle.sku_snapshot for detalle in presupuesto.detalles),
                ]
            ).lower()
            if search_text and search_text not in searchable:
                continue
            rows.append(
                {
                    "id": int(presupuesto.id),
                    "folio": presupuesto.folio,
                    "cliente": presupuesto.cliente_nombre or (presupuesto.cliente.nombre if presupuesto.cliente else "Mostrador / sin cliente"),
                    "estado": presupuesto.estado.value,
                    "total": Decimal(presupuesto.total),
                    "usuario": presupuesto.usuario.username if presupuesto.usuario else "",
                    "vigencia": presupuesto.vigencia_hasta.strftime("%Y-%m-%d") if presupuesto.vigencia_hasta else "Sin vigencia",
                    "fecha": presupuesto.created_at.strftime("%Y-%m-%d %H:%M") if presupuesto.created_at else "",
                }
            )

        self.quote_rows = rows
        self.quote_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["folio"],
                row["cliente"],
                row["estado"],
                row["total"],
                row["usuario"],
                row["vigencia"],
                row["fecha"],
            ]
            for column_index, value in enumerate(values):
                self.quote_table.setItem(row_index, column_index, _table_item(value))
            self.quote_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            status_item = self.quote_table.item(row_index, 2)
            total_item = self.quote_table.item(row_index, 3)
            if status_item is not None:
                tone = {
                    EstadoPresupuesto.EMITIDO.value: "positive",
                    EstadoPresupuesto.BORRADOR.value: "warning",
                    EstadoPresupuesto.CANCELADO.value: "danger",
                    EstadoPresupuesto.CONVERTIDO.value: "muted",
                }.get(str(row["estado"]), "muted")
                _set_table_badge_style(status_item, tone)
            if total_item is not None:
                _set_table_badge_style(total_item, "positive")
        self.quote_table.resizeColumnsToContents()
        self.quote_status_label.setText(
            f"Presupuestos visibles: {len(rows)} | Filtro: {self.quote_state_combo.currentText()}"
            if rows
            else "No hay presupuestos con esos filtros."
        )

        if selected_quote_id is not None:
            self.quote_table.blockSignals(True)
            for row_index in range(self.quote_table.rowCount()):
                item = self.quote_table.item(row_index, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_quote_id:
                    self.quote_table.setCurrentCell(row_index, 0)
                    self.quote_table.selectRow(row_index)
                    break
            self.quote_table.blockSignals(False)

        self._refresh_quote_detail(self._selected_quote_id())
        self._refresh_permissions()

    def _refresh_quote_detail(self, quote_id: int | None) -> None:
        if not quote_id:
            self.quote_customer_label.setText("Sin detalle.")
            self.quote_meta_label.setText("")
            self.quote_notes_label.setText("")
            self.quote_detail_table.setRowCount(0)
            return

        try:
            with get_session() as session:
                presupuesto = PresupuestoService.obtener_presupuesto(session, quote_id)
                if presupuesto is None:
                    raise ValueError("Presupuesto no encontrado.")
                client_text = presupuesto.cliente_nombre or (presupuesto.cliente.nombre if presupuesto.cliente else "Mostrador / sin cliente")
                phone_text = presupuesto.cliente_telefono or (presupuesto.cliente.telefono if presupuesto.cliente else "Sin telefono")
                self.quote_customer_label.setText(f"{presupuesto.folio} | {client_text}")
                self.quote_meta_label.setText(
                    " | ".join(
                        [
                            f"Estado {presupuesto.estado.value}",
                            f"Telefono {phone_text}",
                            f"Total ${Decimal(presupuesto.total).quantize(Decimal('0.01'))}",
                            f"Vigencia {presupuesto.vigencia_hasta.strftime('%Y-%m-%d') if presupuesto.vigencia_hasta else 'Sin vigencia'}",
                            f"Usuario {presupuesto.usuario.username if presupuesto.usuario else '-'}",
                        ]
                    )
                )
                self.quote_notes_label.setText(presupuesto.observacion or "Sin observaciones.")
                self.quote_detail_table.setRowCount(len(presupuesto.detalles))
                for row_index, detalle in enumerate(presupuesto.detalles):
                    values = [
                        detalle.sku_snapshot,
                        detalle.descripcion_snapshot,
                        detalle.cantidad,
                        detalle.precio_unitario,
                        detalle.subtotal_linea,
                    ]
                    for column_index, value in enumerate(values):
                        self.quote_detail_table.setItem(row_index, column_index, _table_item(value))
                self.quote_detail_table.resizeColumnsToContents()
        except Exception as exc:  # noqa: BLE001
            self.quote_customer_label.setText("No se pudo cargar el presupuesto")
            self.quote_meta_label.setText(str(exc))
            self.quote_notes_label.setText("")
            self.quote_detail_table.setRowCount(0)

    def _refresh_inventory_table(self, session) -> None:
        current_variant_id = self.inventory_variant_combo.currentData()
        layaway_reserved_subquery = (
            select(
                ApartadoDetalle.variante_id.label("variante_id"),
                func.coalesce(func.sum(ApartadoDetalle.cantidad), 0).label("apartado_cantidad"),
            )
            .join(ApartadoDetalle.apartado)
            .where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
            .group_by(ApartadoDetalle.variante_id)
            .subquery()
        )
        statement = (
            select(
                Variante.id,
                Variante.sku,
                Categoria.nombre,
                Marca.nombre,
                Producto.nombre,
                Producto.nombre_base,
                Escuela.nombre,
                TipoPrenda.nombre,
                TipoPieza.nombre,
                Variante.nombre_legacy,
                Variante.origen_legacy,
                Variante.talla,
                Variante.color,
                Variante.precio_venta,
                Variante.costo_referencia,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Variante.activo,
                func.coalesce(ImportacionCatalogoFila.producto_fallback, False),
            )
            .join(Variante.producto)
            .join(Producto.categoria)
            .join(Producto.marca)
            .outerjoin(Producto.escuela)
            .outerjoin(Producto.tipo_prenda)
            .outerjoin(Producto.tipo_pieza)
            .outerjoin(ImportacionCatalogoFila, ImportacionCatalogoFila.variante_id == Variante.id)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
        )
        rows = session.execute(statement.order_by(Producto.nombre.asc(), Variante.sku.asc())).all()

        search_text = self.inventory_search_input.text().strip()
        category_filters = self.inventory_category_filter_combo.selected_values()
        brand_filters = self.inventory_brand_filter_combo.selected_values()
        school_filters = self.inventory_school_filter_combo.selected_values()
        type_filters = self.inventory_type_filter_combo.selected_values()
        piece_filters = self.inventory_piece_filter_combo.selected_values()
        size_filters = self.inventory_size_filter_combo.selected_values()
        color_filters = self.inventory_color_filter_combo.selected_values()
        status_filter = str(self.inventory_status_filter_combo.currentData() or "")
        stock_filter = str(self.inventory_stock_filter_combo.currentData() or "")
        qr_filter = str(self.inventory_qr_filter_combo.currentData() or "")
        origin_filter = str(self.inventory_origin_filter_combo.currentData() or "")
        duplicate_filter = str(self.inventory_duplicate_filter_combo.currentData() or "")

        visible_rows: list[dict[str, object]] = []
        count_out = 0
        count_low = 0
        count_missing_qr = 0
        count_inactive = 0
        for row in rows:
            qr_exists = (QrGenerator.output_dir() / f"{row[1]}.png").exists()
            row_data = {
                "variante_id": row[0],
                "sku": row[1],
                "categoria_nombre": row[2],
                "marca_nombre": row[3],
                "producto_nombre": row[4],
                "producto_nombre_base": row[5],
                "escuela_nombre": row[6] or "General",
                "tipo_prenda_nombre": row[7] or "-",
                "tipo_pieza_nombre": row[8] or "-",
                "nombre_legacy": row[9],
                "origen_legacy": bool(row[10]),
                "talla": row[11],
                "color": row[12],
                "precio_venta": Decimal(row[13]).quantize(Decimal("0.01")),
                "costo_referencia": Decimal(row[14]).quantize(Decimal("0.01")) if row[14] is not None else None,
                "stock_actual": int(row[15]),
                "apartado_cantidad": int(row[16]),
                "variante_activa": bool(row[17]),
                "fallback_importacion": bool(row[18]),
                "qr_exists": qr_exists,
                "origen_etiqueta": "LEGACY" if row[10] else "NUEVO",
                "variante_estado": "ACTIVA" if row[17] else "INACTIVA",
                "fallback_text": "fallback" if bool(row[18]) else "",
            }
            if not self._inventory_row_matches_search(row_data, search_text):
                continue
            if category_filters and str(row_data["categoria_nombre"]) not in category_filters:
                continue
            if brand_filters and str(row_data["marca_nombre"]) not in brand_filters:
                continue
            if school_filters and str(row_data["escuela_nombre"]) not in school_filters:
                continue
            if type_filters and str(row_data["tipo_prenda_nombre"]) not in type_filters:
                continue
            if piece_filters and str(row_data["tipo_pieza_nombre"]) not in piece_filters:
                continue
            if size_filters and str(row_data["talla"]) not in size_filters:
                continue
            if color_filters and str(row_data["color"]) not in color_filters:
                continue
            if status_filter == "active" and not bool(row_data["variante_activa"]):
                continue
            if status_filter == "inactive" and bool(row_data["variante_activa"]):
                continue
            if stock_filter == "zero" and int(row_data["stock_actual"]) != 0:
                continue
            if stock_filter == "low" and not (0 < int(row_data["stock_actual"]) <= 3):
                continue
            if stock_filter == "available" and int(row_data["stock_actual"]) <= 0:
                continue
            if qr_filter == "ready" and not qr_exists:
                continue
            if qr_filter == "missing" and qr_exists:
                continue
            if origin_filter == "legacy" and not bool(row_data["origen_legacy"]):
                continue
            if origin_filter == "native" and bool(row_data["origen_legacy"]):
                continue
            if duplicate_filter == "fallback_only" and not bool(row_data["fallback_importacion"]):
                continue
            if duplicate_filter == "fallback_exclude" and bool(row_data["fallback_importacion"]):
                continue

            stock_value = int(row_data["stock_actual"])
            committed_value = int(row_data["apartado_cantidad"])
            if stock_value == 0:
                count_out += 1
            elif stock_value <= 3:
                count_low += 1
            if not qr_exists:
                count_missing_qr += 1
            if not bool(row_data["variante_activa"]):
                count_inactive += 1
            visible_rows.append(row_data)

        self._set_badge_state(
            self.inventory_out_counter,
            f"Agotados: {count_out}",
            "danger" if count_out else "positive",
        )
        self._set_badge_state(
            self.inventory_low_counter,
            f"Bajo stock: {count_low}",
            "warning" if count_low else "positive",
        )
        self._set_badge_state(
            self.inventory_qr_pending_counter,
            f"Sin QR: {count_missing_qr}",
            "warning" if count_missing_qr else "positive",
        )
        self._set_badge_state(
            self.inventory_inactive_counter,
            f"Inactivas: {count_inactive}",
            "muted" if count_inactive else "positive",
        )

        self.inventory_table.setRowCount(len(visible_rows))
        self.inventory_rows = visible_rows
        for row_index, row in enumerate(visible_rows):
            stock_value = int(row["stock_actual"])
            committed_value = int(row["apartado_cantidad"])
            stock_tone = "danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive"
            estado_text = "ACTIVA" if row["variante_activa"] else "INACTIVA"
            estado_tone = "positive" if row["variante_activa"] else "muted"
            qr_text = "Listo" if row["qr_exists"] else "Pendiente"
            qr_tone = "positive" if row["qr_exists"] else "warning"
            values = [
                row["sku"],
                row["producto_nombre_base"],
                row["talla"],
                row["color"],
                _stock_table_text(stock_value),
                committed_value,
                estado_text,
                qr_text,
            ]
            for column_index, value in enumerate(values):
                self.inventory_table.setItem(row_index, column_index, _table_item(value))
            self.inventory_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row["variante_id"])
            stock_item = self.inventory_table.item(row_index, 4)
            committed_item = self.inventory_table.item(row_index, 5)
            status_item = self.inventory_table.item(row_index, 6)
            qr_item = self.inventory_table.item(row_index, 7)
            if stock_item is not None:
                _set_table_badge_style(stock_item, stock_tone)
            if committed_item is not None and committed_value > 0:
                _set_table_badge_style(committed_item, "warning")
            if status_item is not None:
                _set_table_badge_style(status_item, estado_tone)
            if qr_item is not None:
                _set_table_badge_style(qr_item, qr_tone)
        self.inventory_table.resizeColumnsToContents()
        self.inventory_results_label.setText(self._build_inventory_results_summary(total_rows=len(rows), visible_rows=visible_rows))
        self.inventory_active_filters_label.setText(self._build_inventory_active_filters_summary())
        self._sync_inventory_table_selection(current_variant_id)
        self._refresh_inventory_overview()

    def _handle_inventory_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_inventory_table(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de inventario.")

    def _handle_clear_inventory_filters(self) -> None:
        self.inventory_search_input.clear()
        for combo in (
            self.inventory_status_filter_combo,
            self.inventory_stock_filter_combo,
            self.inventory_qr_filter_combo,
            self.inventory_origin_filter_combo,
            self.inventory_duplicate_filter_combo,
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        for widget in (
            self.inventory_category_filter_combo,
            self.inventory_brand_filter_combo,
            self.inventory_school_filter_combo,
            self.inventory_type_filter_combo,
            self.inventory_piece_filter_combo,
            self.inventory_size_filter_combo,
            self.inventory_color_filter_combo,
        ):
            widget.clear_selection()
        self._handle_inventory_filters_changed()

    def _analytics_period_bounds(self) -> tuple[datetime, datetime]:
        period_key = str(self.analytics_period_combo.currentData() or "today")
        today = date.today()
        if period_key == "7d":
            start_date = today - timedelta(days=6)
            end_date = today
        elif period_key == "30d":
            start_date = today - timedelta(days=29)
            end_date = today
        elif period_key == "month":
            start_date = today.replace(day=1)
            end_date = today
        elif period_key == "manual":
            start_date = self.analytics_from_input.date().toPyDate()
            end_date = self.analytics_to_input.date().toPyDate()
        else:
            start_date = today
            end_date = today
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        return (
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )

    def _handle_analytics_period_changed(self) -> None:
        is_manual = str(self.analytics_period_combo.currentData() or "") == "manual"
        self.analytics_from_input.setEnabled(is_manual)
        self.analytics_to_input.setEnabled(is_manual)
        try:
            with get_session() as session:
                self._refresh_analytics(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudo refrescar la analitica.")

    def _refresh_analytics(self, session) -> None:
        period_start, period_end = self._analytics_period_bounds()
        selected_client_id = self.analytics_client_combo.currentData()
        sales = list(
            session.scalars(
                select(Venta).where(
                    Venta.estado == EstadoVenta.CONFIRMADA,
                    Venta.confirmada_at.is_not(None),
                    Venta.confirmada_at >= period_start,
                    Venta.confirmada_at < period_end,
                    *((Venta.cliente_id == int(selected_client_id),) if selected_client_id not in {None, ""} else ()),
                )
            )
        )
        total_sales = sum((Decimal(sale.total) for sale in sales), Decimal("0.00"))
        total_tickets = len(sales)
        total_units = sum((sum(int(detalle.cantidad) for detalle in sale.detalles) for sale in sales), 0)
        average_ticket = (
            (total_sales / Decimal(total_tickets)).quantize(Decimal("0.01"))
            if total_tickets
            else Decimal("0.00")
        )
        self.analytics_sales_value.setText(f"${total_sales}")
        self.analytics_tickets_value.setText(str(total_tickets))
        self.analytics_average_value.setText(f"${average_ticket}")
        self.analytics_units_value.setText(str(total_units))
        identified_sales = [sale for sale in sales if sale.cliente_id is not None]
        identified_income = sum((Decimal(sale.total) for sale in identified_sales), Decimal("0.00"))
        unique_clients = {int(sale.cliente_id) for sale in identified_sales if sale.cliente_id is not None}
        repeat_clients = 0
        if identified_sales:
            counts_by_client: dict[int, int] = {}
            for sale in identified_sales:
                if sale.cliente_id is None:
                    continue
                counts_by_client[int(sale.cliente_id)] = counts_by_client.get(int(sale.cliente_id), 0) + 1
            repeat_clients = sum(1 for count in counts_by_client.values() if count > 1)
        average_per_client = (
            (identified_income / Decimal(len(unique_clients))).quantize(Decimal("0.01"))
            if unique_clients
            else Decimal("0.00")
        )
        self.analytics_identified_sales_value.setText(str(len(identified_sales)))
        self.analytics_identified_income_value.setText(f"${identified_income}")
        self.analytics_repeat_clients_value.setText(str(repeat_clients))
        self.analytics_average_client_value.setText(f"${average_per_client}")

        payment_buckets: dict[str, dict[str, Decimal | int]] = {
            "Efectivo": {"count": 0, "amount": Decimal("0.00")},
            "Tarjeta": {"count": 0, "amount": Decimal("0.00")},
            "Transferencia": {"count": 0, "amount": Decimal("0.00")},
            "Mixto": {"count": 0, "amount": Decimal("0.00")},
        }
        for sale in sales:
            note = sale.observacion or ""
            method = "Efectivo"
            for candidate in payment_buckets:
                if f"Metodo de pago: {candidate}" in note:
                    method = candidate
                    break
            payment_buckets[method]["count"] = int(payment_buckets[method]["count"]) + 1
            payment_buckets[method]["amount"] = Decimal(payment_buckets[method]["amount"]) + Decimal(sale.total)

        payment_rows = [
            (method, int(data["count"]), Decimal(data["amount"]))
            for method, data in payment_buckets.items()
            if int(data["count"]) > 0 or Decimal(data["amount"]) > Decimal("0.00")
        ]
        self.analytics_payment_table.setRowCount(len(payment_rows))
        for row_index, row in enumerate(payment_rows):
            for column_index, value in enumerate(row):
                self.analytics_payment_table.setItem(row_index, column_index, _table_item(value))
        self.analytics_payment_table.resizeColumnsToContents()

        rows = session.execute(
            select(
                Variante.sku,
                Producto.nombre,
                func.coalesce(func.sum(VentaDetalle.cantidad), 0),
                func.coalesce(func.sum(VentaDetalle.subtotal_linea), 0),
            )
            .join(VentaDetalle.variante)
            .join(Variante.producto)
            .join(VentaDetalle.venta)
            .where(
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.confirmada_at.is_not(None),
                Venta.confirmada_at >= period_start,
                Venta.confirmada_at < period_end,
                *((Venta.cliente_id == int(selected_client_id),) if selected_client_id not in {None, ""} else ()),
            )
            .group_by(Variante.sku, Producto.nombre)
            .order_by(desc(func.sum(VentaDetalle.cantidad)), Variante.sku.asc())
            .limit(10)
        ).all()

        self.top_products_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.top_products_table.setItem(row_index, column_index, _table_item(value))
        self.top_products_table.resizeColumnsToContents()

        top_client_rows = session.execute(
            select(
                Cliente.nombre,
                Cliente.codigo_cliente,
                func.count(Venta.id),
                func.coalesce(func.sum(Venta.total), 0),
            )
            .join(Venta, Venta.cliente_id == Cliente.id)
            .where(
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.confirmada_at.is_not(None),
                Venta.confirmada_at >= period_start,
                Venta.confirmada_at < period_end,
                *((Venta.cliente_id == int(selected_client_id),) if selected_client_id not in {None, ""} else ()),
            )
            .group_by(Cliente.id, Cliente.nombre, Cliente.codigo_cliente)
            .order_by(desc(func.sum(Venta.total)), Cliente.nombre.asc())
            .limit(10)
        ).all()
        self.analytics_clients_table.setRowCount(len(top_client_rows))
        for row_index, row in enumerate(top_client_rows):
            for column_index, value in enumerate(row):
                self.analytics_clients_table.setItem(row_index, column_index, _table_item(value))
            sales_item = self.analytics_clients_table.item(row_index, 2)
            amount_item = self.analytics_clients_table.item(row_index, 3)
            if sales_item is not None:
                _set_table_badge_style(sales_item, "positive" if int(row[2]) >= 2 else "warning")
            if amount_item is not None:
                _set_table_badge_style(amount_item, "positive")
        self.analytics_clients_table.resizeColumnsToContents()

        active_layaways = session.scalar(
            select(func.count(Apartado.id)).where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
        ) or 0
        pending_balance = session.scalar(
            select(func.coalesce(func.sum(Apartado.saldo_pendiente), 0)).where(
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO])
            )
        ) or Decimal("0.00")
        overdue_count = session.scalar(
            select(func.count(Apartado.id)).where(
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
                Apartado.fecha_compromiso.is_not(None),
                func.date(Apartado.fecha_compromiso) < date.today(),
            )
        ) or 0
        delivered_in_period = session.scalar(
            select(func.count(Apartado.id)).where(
                Apartado.estado == EstadoApartado.ENTREGADO,
                Apartado.entregado_at.is_not(None),
                Apartado.entregado_at >= period_start,
                Apartado.entregado_at < period_end,
            )
        ) or 0
        self.analytics_layaway_active_label.setText(f"Apartados activos\n{active_layaways}")
        self.analytics_layaway_balance_label.setText(f"Saldo pendiente\n${pending_balance}")
        self.analytics_layaway_overdue_label.setText(f"Vencidos\n{overdue_count}")
        self.analytics_layaway_delivered_label.setText(f"Entregados periodo\n{delivered_in_period}")
        layaway_label_states = (
            (self.analytics_layaway_active_label, "positive" if active_layaways else "neutral"),
            (self.analytics_layaway_balance_label, "warning" if Decimal(pending_balance) > Decimal("0.00") else "neutral"),
            (self.analytics_layaway_overdue_label, "danger" if overdue_count else "neutral"),
            (self.analytics_layaway_delivered_label, "positive" if delivered_in_period else "neutral"),
        )
        for label, tone in layaway_label_states:
            label.setProperty("tone", tone)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

        layaway_reserved_subquery = (
            select(
                ApartadoDetalle.variante_id.label("variante_id"),
                func.coalesce(func.sum(ApartadoDetalle.cantidad), 0).label("apartado_cantidad"),
            )
            .join(ApartadoDetalle.apartado)
            .where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
            .group_by(ApartadoDetalle.variante_id)
            .subquery()
        )
        stock_rows = session.execute(
            select(
                Variante.sku,
                Producto.nombre,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Variante.activo,
            )
            .join(Variante.producto)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
            .where(or_(Variante.stock_actual <= 3, Variante.activo.is_(False)))
            .order_by(Variante.stock_actual.asc(), Producto.nombre.asc(), Variante.sku.asc())
            .limit(10)
        ).all()
        self.analytics_stock_table.setRowCount(len(stock_rows))
        for row_index, row in enumerate(stock_rows):
            values = [row[0], row[1], row[2], row[3], "ACTIVA" if bool(row[4]) else "INACTIVA"]
            for column_index, value in enumerate(values):
                self.analytics_stock_table.setItem(row_index, column_index, _table_item(value))
            stock_item = self.analytics_stock_table.item(row_index, 2)
            reserved_item = self.analytics_stock_table.item(row_index, 3)
            state_item = self.analytics_stock_table.item(row_index, 4)
            if stock_item is not None:
                stock_value = int(row[2])
                _set_table_badge_style(
                    stock_item,
                    "danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive",
                )
            if reserved_item is not None:
                _set_table_badge_style(
                    reserved_item,
                    "warning" if int(row[3]) > 0 else "muted",
                )
            if state_item is not None:
                _set_table_badge_style(state_item, "positive" if bool(row[4]) else "muted")
        self.analytics_stock_table.resizeColumnsToContents()
        client_label = "todos" if selected_client_id in {None, ""} else self.analytics_client_combo.currentText()
        self.analytics_export_status_label.setText(f"Periodo listo para analisis. Cliente: {client_label}.")

    @staticmethod
    def _analytics_export_dir() -> Path:
        output_dir = Path(__file__).resolve().parents[1] / "exports" / "analytics"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def _serialize_export_value(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _handle_export_analytics(self) -> None:
        period_start, period_end = self._analytics_period_bounds()
        selected_client_id = self.analytics_client_combo.currentData()
        try:
            with get_session() as session:
                sales_statement = (
                    select(Venta)
                    .where(
                        Venta.estado == EstadoVenta.CONFIRMADA,
                        Venta.confirmada_at.is_not(None),
                        Venta.confirmada_at >= period_start,
                        Venta.confirmada_at < period_end,
                    )
                    .order_by(Venta.confirmada_at.asc())
                )
                if selected_client_id not in {None, ""}:
                    sales_statement = sales_statement.where(Venta.cliente_id == int(selected_client_id))
                sales = list(session.scalars(sales_statement))

                sales_rows: list[dict[str, object]] = []
                detail_rows: list[dict[str, object]] = []
                for sale in sales:
                    sales_rows.append(
                        {
                            "venta_id": sale.id,
                            "folio": sale.folio,
                            "cliente_id": sale.cliente_id,
                            "cliente": sale.cliente.nombre if sale.cliente is not None else "Mostrador",
                            "codigo_cliente": sale.cliente.codigo_cliente if sale.cliente is not None else None,
                            "usuario": sale.usuario.username if sale.usuario else None,
                            "estado": sale.estado.value,
                            "subtotal": sale.subtotal,
                            "total": sale.total,
                            "observacion": sale.observacion,
                            "confirmada_at": sale.confirmada_at,
                        }
                    )
                    for detalle in sale.detalles:
                        detail_rows.append(
                            {
                                "venta_id": sale.id,
                                "folio": sale.folio,
                                "cliente": sale.cliente.nombre if sale.cliente is not None else "Mostrador",
                                "sku": detalle.variante.sku if detalle.variante else None,
                                "producto": (
                                    detalle.variante.producto.nombre
                                    if detalle.variante is not None and detalle.variante.producto is not None
                                    else None
                                ),
                                "cantidad": detalle.cantidad,
                                "precio_unitario": detalle.precio_unitario,
                                "subtotal_linea": detalle.subtotal_linea,
                            }
                        )

                top_products_rows = [
                    {
                        "sku": self.top_products_table.item(row, 0).text() if self.top_products_table.item(row, 0) else "",
                        "producto": self.top_products_table.item(row, 1).text() if self.top_products_table.item(row, 1) else "",
                        "unidades_vendidas": self.top_products_table.item(row, 2).text() if self.top_products_table.item(row, 2) else "",
                        "ingreso": self.top_products_table.item(row, 3).text() if self.top_products_table.item(row, 3) else "",
                    }
                    for row in range(self.top_products_table.rowCount())
                ]
                top_clients_rows = [
                    {
                        "cliente": self.analytics_clients_table.item(row, 0).text() if self.analytics_clients_table.item(row, 0) else "",
                        "codigo_cliente": self.analytics_clients_table.item(row, 1).text() if self.analytics_clients_table.item(row, 1) else "",
                        "ventas": self.analytics_clients_table.item(row, 2).text() if self.analytics_clients_table.item(row, 2) else "",
                        "monto": self.analytics_clients_table.item(row, 3).text() if self.analytics_clients_table.item(row, 3) else "",
                    }
                    for row in range(self.analytics_clients_table.rowCount())
                ]
                payment_rows = [
                    {
                        "metodo": self.analytics_payment_table.item(row, 0).text() if self.analytics_payment_table.item(row, 0) else "",
                        "ventas": self.analytics_payment_table.item(row, 1).text() if self.analytics_payment_table.item(row, 1) else "",
                        "monto": self.analytics_payment_table.item(row, 2).text() if self.analytics_payment_table.item(row, 2) else "",
                    }
                    for row in range(self.analytics_payment_table.rowCount())
                ]
                stock_rows = [
                    {
                        "sku": self.analytics_stock_table.item(row, 0).text() if self.analytics_stock_table.item(row, 0) else "",
                        "producto": self.analytics_stock_table.item(row, 1).text() if self.analytics_stock_table.item(row, 1) else "",
                        "stock": self.analytics_stock_table.item(row, 2).text() if self.analytics_stock_table.item(row, 2) else "",
                        "apartado": self.analytics_stock_table.item(row, 3).text() if self.analytics_stock_table.item(row, 3) else "",
                        "estado": self.analytics_stock_table.item(row, 4).text() if self.analytics_stock_table.item(row, 4) else "",
                    }
                    for row in range(self.analytics_stock_table.rowCount())
                ]
                movement_rows = [
                    {
                        "fecha": movimiento.created_at,
                        "sku": movimiento.variante.sku if movimiento.variante is not None else None,
                        "producto": (
                            movimiento.variante.producto.nombre
                            if movimiento.variante is not None and movimiento.variante.producto is not None
                            else None
                        ),
                        "tipo": movimiento.tipo_movimiento.value,
                        "cantidad": movimiento.cantidad,
                        "stock_anterior": movimiento.stock_anterior,
                        "stock_posterior": movimiento.stock_posterior,
                        "referencia": movimiento.referencia,
                        "creado_por": movimiento.creado_por,
                        "observacion": movimiento.observacion,
                    }
                    for movimiento in session.scalars(
                        select(MovimientoInventario)
                        .join(MovimientoInventario.variante)
                        .join(Variante.producto)
                        .where(
                            MovimientoInventario.created_at >= period_start,
                            MovimientoInventario.created_at < period_end,
                        )
                        .order_by(MovimientoInventario.created_at.asc())
                    )
                ]
                purchase_rows: list[dict[str, object]] = []
                purchase_detail_rows: list[dict[str, object]] = []
                for compra in session.scalars(
                    select(Compra)
                    .where(
                        Compra.estado == EstadoCompra.CONFIRMADA,
                        Compra.confirmada_at.is_not(None),
                        Compra.confirmada_at >= period_start,
                        Compra.confirmada_at < period_end,
                    )
                    .order_by(Compra.confirmada_at.asc())
                ):
                    purchase_rows.append(
                        {
                            "compra_id": compra.id,
                            "documento": compra.numero_documento,
                            "proveedor": compra.proveedor.nombre if compra.proveedor is not None else None,
                            "usuario": compra.usuario.username if compra.usuario is not None else None,
                            "estado": compra.estado.value,
                            "subtotal": compra.subtotal,
                            "total": compra.total,
                            "observacion": compra.observacion,
                            "confirmada_at": compra.confirmada_at,
                        }
                    )
                    for detalle in compra.detalles:
                        purchase_detail_rows.append(
                            {
                                "compra_id": compra.id,
                                "documento": compra.numero_documento,
                                "proveedor": compra.proveedor.nombre if compra.proveedor is not None else None,
                                "sku": detalle.variante.sku if detalle.variante is not None else None,
                                "producto": (
                                    detalle.variante.producto.nombre
                                    if detalle.variante is not None and detalle.variante.producto is not None
                                    else None
                                ),
                                "cantidad": detalle.cantidad,
                                "costo_unitario": detalle.costo_unitario,
                                "subtotal_linea": detalle.subtotal_linea,
                            }
                        )
                cash_cut_rows = [
                    {
                        "sesion_id": sesion.id,
                        "abierta_por": sesion.abierta_por.username if sesion.abierta_por is not None else None,
                        "cerrada_por": sesion.cerrada_por.username if sesion.cerrada_por is not None else None,
                        "monto_apertura": sesion.monto_apertura,
                        "monto_esperado_cierre": sesion.monto_esperado_cierre,
                        "monto_cierre_declarado": sesion.monto_cierre_declarado,
                        "diferencia_cierre": sesion.diferencia_cierre,
                        "observacion_apertura": sesion.observacion_apertura,
                        "observacion_cierre": sesion.observacion_cierre,
                        "abierta_at": sesion.abierta_at,
                        "cerrada_at": sesion.cerrada_at,
                        "estado": "ABIERTA" if sesion.cerrada_at is None else "CERRADA",
                    }
                    for sesion in session.scalars(
                        select(SesionCaja)
                        .where(
                            or_(
                                and_(SesionCaja.abierta_at >= period_start, SesionCaja.abierta_at < period_end),
                                and_(
                                    SesionCaja.cerrada_at.is_not(None),
                                    SesionCaja.cerrada_at >= period_start,
                                    SesionCaja.cerrada_at < period_end,
                                ),
                            )
                        )
                        .order_by(SesionCaja.abierta_at.asc())
                    )
                ]

                layaway_rows = [
                    {
                        "activos": self.analytics_layaway_active_label.text(),
                        "saldo_pendiente": self.analytics_layaway_balance_label.text(),
                        "vencidos": self.analytics_layaway_overdue_label.text(),
                        "entregados_periodo": self.analytics_layaway_delivered_label.text(),
                    }
                ]

                export_sets = {
                    "ventas": sales_rows,
                    "detalle_ventas": detail_rows,
                    "top_productos": top_products_rows,
                    "top_clientes": top_clients_rows,
                    "metodos_pago": payment_rows,
                    "stock_critico": stock_rows,
                    "movimientos": movement_rows,
                    "compras": purchase_rows,
                    "detalle_compras": purchase_detail_rows,
                    "cortes_caja": cash_cut_rows,
                    "apartados_resumen": layaway_rows,
                }

                export_dir = self._analytics_export_dir() / datetime.now().strftime("%Y%m%d_%H%M%S")
                export_dir.mkdir(parents=True, exist_ok=True)
                for name, rows in export_sets.items():
                    json_path = export_dir / f"{name}.json"
                    json_path.write_text(
                        json.dumps(
                            [
                                {key: self._serialize_export_value(value) for key, value in row.items()}
                                for row in rows
                            ],
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    csv_path = export_dir / f"{name}.csv"
                    with csv_path.open("w", newline="", encoding="utf-8") as fh:
                        if rows:
                            fieldnames = list(rows[0].keys())
                            writer = csv.DictWriter(fh, fieldnames=fieldnames)
                            writer.writeheader()
                            for row in rows:
                                writer.writerow({key: self._serialize_export_value(value) for key, value in row.items()})
                        else:
                            fh.write("")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportacion no generada", str(exc))
            return

        self.analytics_export_status_label.setText(f"Exportacion generada en {export_dir}.")
        QMessageBox.information(self, "Exportacion lista", f"Se generaron archivos CSV y JSON en:\n{export_dir}")

    def _refresh_history(self, session) -> None:
        source_filter = str(self.history_source_combo.currentData() or "")
        entity_filter = str(self.history_entity_combo.currentData() or "")
        sku_filter = self.history_sku_input.text().strip()
        type_filter = str(self.history_type_combo.currentData() or "")

        start_datetime = None
        if self.history_from_input.date() > self.history_from_input.minimumDate():
            start_date = self.history_from_input.date().toPyDate()
            start_datetime = datetime.combine(start_date, datetime.min.time())

        end_datetime = None
        if self.history_to_input.date() > self.history_to_input.minimumDate():
            end_date = self.history_to_input.date().toPyDate() + timedelta(days=1)
            end_datetime = datetime.combine(end_date, datetime.min.time())

        rows: list[dict[str, object]] = []

        if source_filter in {"", "inventory"}:
            inventory_statement = (
                select(
                    MovimientoInventario.created_at,
                    Variante.sku,
                    MovimientoInventario.tipo_movimiento,
                    MovimientoInventario.cantidad,
                    MovimientoInventario.stock_posterior,
                    MovimientoInventario.referencia,
                    MovimientoInventario.creado_por,
                    MovimientoInventario.observacion,
                    Producto.nombre,
                )
                .join(MovimientoInventario.variante)
                .join(Variante.producto)
                .order_by(desc(MovimientoInventario.created_at))
                .limit(200)
            )

            if sku_filter:
                inventory_statement = inventory_statement.where(
                    or_(
                        Variante.sku.ilike(f"%{sku_filter}%"),
                        Producto.nombre.ilike(f"%{sku_filter}%"),
                        MovimientoInventario.referencia.ilike(f"%{sku_filter}%"),
                        MovimientoInventario.creado_por.ilike(f"%{sku_filter}%"),
                        MovimientoInventario.observacion.ilike(f"%{sku_filter}%"),
                    )
                )
            if entity_filter and entity_filter != "PRESENTACION":
                inventory_statement = inventory_statement.where(Variante.id == -1)
            if type_filter.startswith("inventory:"):
                inventory_statement = inventory_statement.where(
                    MovimientoInventario.tipo_movimiento == TipoMovimientoInventario(type_filter.split(":", 1)[1])
                )
            if start_datetime is not None:
                inventory_statement = inventory_statement.where(MovimientoInventario.created_at >= start_datetime)
            if end_datetime is not None:
                inventory_statement = inventory_statement.where(MovimientoInventario.created_at < end_datetime)

            for row in session.execute(inventory_statement).all():
                rows.append(
                    {
                        "fecha": row[0],
                        "origen": "Inventario",
                        "registro": row[1],
                        "entidad": "PRESENTACION",
                        "tipo": row[2].value if row[2] else "",
                        "cambio": row[3],
                        "resultado": row[4],
                        "usuario": row[6],
                        "detalle": " | ".join(part for part in [row[8], row[5], row[7]] if part),
                    }
                )

        if source_filter in {"", "catalog"}:
            catalog_statement = (
                select(
                    CambioCatalogo.created_at,
                    CambioCatalogo.descripcion_entidad,
                    CambioCatalogo.accion,
                    CambioCatalogo.campo,
                    CambioCatalogo.valor_anterior,
                    CambioCatalogo.valor_nuevo,
                    Usuario.username,
                    CambioCatalogo.observacion,
                    CambioCatalogo.entidad_tipo,
                )
                .join(CambioCatalogo.usuario)
                .order_by(desc(CambioCatalogo.created_at))
                .limit(200)
            )

            if sku_filter:
                catalog_statement = catalog_statement.where(
                    or_(
                        CambioCatalogo.descripcion_entidad.ilike(f"%{sku_filter}%"),
                        CambioCatalogo.campo.ilike(f"%{sku_filter}%"),
                        CambioCatalogo.valor_anterior.ilike(f"%{sku_filter}%"),
                        CambioCatalogo.valor_nuevo.ilike(f"%{sku_filter}%"),
                        CambioCatalogo.observacion.ilike(f"%{sku_filter}%"),
                        Usuario.username.ilike(f"%{sku_filter}%"),
                    )
                )
            if entity_filter:
                catalog_statement = catalog_statement.where(CambioCatalogo.entidad_tipo == TipoEntidadCatalogo(entity_filter))
            if type_filter.startswith("catalog:"):
                catalog_statement = catalog_statement.where(
                    CambioCatalogo.accion == TipoCambioCatalogo(type_filter.split(":", 1)[1])
                )
            if start_datetime is not None:
                catalog_statement = catalog_statement.where(CambioCatalogo.created_at >= start_datetime)
            if end_datetime is not None:
                catalog_statement = catalog_statement.where(CambioCatalogo.created_at < end_datetime)

            for row in session.execute(catalog_statement).all():
                rows.append(
                    {
                        "fecha": row[0],
                        "origen": "Catalogo",
                        "registro": row[1],
                        "entidad": row[8].value if row[8] else "",
                        "tipo": f"{row[2].value} · {row[3]}",
                        "cambio": row[4] if row[4] is not None else "—",
                        "resultado": row[5] if row[5] is not None else "—",
                        "usuario": row[6],
                        "detalle": row[7] or "",
                    }
                )

        rows.sort(key=lambda item: item["fecha"] or datetime.min, reverse=True)
        rows = rows[:200]

        self.movements_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["fecha"].strftime("%Y-%m-%d %H:%M") if row["fecha"] else "",
                row["origen"],
                row["registro"],
                row["tipo"],
                row["cambio"],
                row["resultado"],
                row["usuario"],
                row["detalle"],
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 1:
                    _set_table_badge_style(item, "positive" if row["origen"] == "Inventario" else "warning")
                elif column_index == 3:
                    tipo_text = str(row["tipo"])
                    if "ELIMINACION" in tipo_text or "SALIDA" in tipo_text:
                        _set_table_badge_style(item, "danger")
                    elif "ESTADO" in tipo_text or "AJUSTE" in tipo_text:
                        _set_table_badge_style(item, "warning")
                    elif "CREACION" in tipo_text or "ENTRADA" in tipo_text or "RESERVA" in tipo_text:
                        _set_table_badge_style(item, "positive")
                    else:
                        _set_table_badge_style(item, "muted")
                self.movements_table.setItem(row_index, column_index, item)
        self.movements_table.resizeColumnsToContents()

    @staticmethod
    def _generate_layaway_folio() -> str:
        return f"APT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"

    @staticmethod
    def _classify_layaway_due(
        commitment: datetime | None,
        estado: EstadoApartado,
    ) -> tuple[str, str]:
        if commitment is None:
            return ("Sin fecha", "muted")
        if estado in {EstadoApartado.ENTREGADO, EstadoApartado.CANCELADO}:
            return (commitment.strftime("%Y-%m-%d"), "muted")
        today = date.today()
        due_date = commitment.date()
        if due_date < today:
            return (f"Vencido desde {due_date.isoformat()}", "danger")
        if due_date == today:
            return ("Vence hoy", "warning")
        if due_date <= today + timedelta(days=7):
            return (f"Vence {due_date.isoformat()}", "warning")
        return (f"Vence {due_date.isoformat()}", "positive")

    def _selected_layaway_id(self) -> int | None:
        selected_row = self.layaway_table.currentRow()
        if selected_row < 0:
            return None
        item = self.layaway_table.item(selected_row, 0)
        if item is None:
            return None
        apartado_id = item.data(Qt.ItemDataRole.UserRole)
        return int(apartado_id) if apartado_id is not None else None

    @staticmethod
    def _normalize_whatsapp_phone(phone: str) -> str:
        digits = "".join(character for character in phone if character.isdigit())
        if digits.startswith("521") and len(digits) == 13:
            return f"52{digits[3:]}"
        if len(digits) == 10:
            return f"52{digits}"
        return digits

    @staticmethod
    def _default_whatsapp_templates() -> dict[str, str]:
        return {
            "layaway_reminder": (
                "Hola {cliente}, te recordamos tu apartado {folio}. "
                "Saldo pendiente: ${saldo}. Estado de vencimiento: {vencimiento}. "
                "Fecha compromiso: {fecha_compromiso}."
            ),
            "layaway_liquidated": (
                "Hola {cliente}, tu apartado {folio} ya esta liquidado y listo para entrega. "
                "Fecha compromiso: {fecha_compromiso}."
            ),
            "client_promotion": (
                "Hola {cliente}, queremos compartirte una promocion especial disponible en tienda."
            ),
            "client_followup": (
                "Hola {cliente}, te escribimos para dar seguimiento y ponernos a tus ordenes."
            ),
            "client_greeting": (
                "Hola {cliente}, gracias por seguir en contacto con nosotros."
            ),
        }

    @staticmethod
    def _render_whatsapp_template(template: str, values: dict[str, object]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    def _get_whatsapp_templates(self) -> dict[str, str]:
        defaults = self._default_whatsapp_templates()
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                return {
                    "layaway_reminder": config.whatsapp_apartado_recordatorio or defaults["layaway_reminder"],
                    "layaway_liquidated": config.whatsapp_apartado_liquidado or defaults["layaway_liquidated"],
                    "client_promotion": config.whatsapp_cliente_promocion or defaults["client_promotion"],
                    "client_followup": config.whatsapp_cliente_seguimiento or defaults["client_followup"],
                    "client_greeting": config.whatsapp_cliente_saludo or defaults["client_greeting"],
                }
        except Exception:
            return defaults

    def _refresh_whatsapp_preview(self) -> None:
        template_key = str(self.settings_whatsapp_preview_combo.currentData() or "layaway_reminder")
        template_map = {
            "layaway_reminder": self.settings_whatsapp_layaway_reminder_input.toPlainText().strip(),
            "layaway_liquidated": self.settings_whatsapp_layaway_liquidated_input.toPlainText().strip(),
            "client_promotion": self.settings_whatsapp_client_promotion_input.toPlainText().strip(),
            "client_followup": self.settings_whatsapp_client_followup_input.toPlainText().strip(),
            "client_greeting": self.settings_whatsapp_client_greeting_input.toPlainText().strip(),
        }
        sample_values = {
            "cliente": "Ana Perez",
            "folio": "APT-20260311-AB12",
            "saldo": "350.00",
            "vencimiento": "Vence hoy",
            "fecha_compromiso": "2026-03-11",
            "codigo_cliente": "CLI-000125",
        }
        template_text = template_map.get(template_key) or self._default_whatsapp_templates().get(template_key, "")
        self.settings_whatsapp_preview_output.setPlainText(
            self._render_whatsapp_template(template_text, sample_values)
        )

    def _handle_reset_whatsapp_templates(self) -> None:
        defaults = self._default_whatsapp_templates()
        self.settings_whatsapp_layaway_reminder_input.setPlainText(defaults["layaway_reminder"])
        self.settings_whatsapp_layaway_liquidated_input.setPlainText(defaults["layaway_liquidated"])
        self.settings_whatsapp_client_promotion_input.setPlainText(defaults["client_promotion"])
        self.settings_whatsapp_client_followup_input.setPlainText(defaults["client_followup"])
        self.settings_whatsapp_client_greeting_input.setPlainText(defaults["client_greeting"])
        self._refresh_whatsapp_preview()
        self.settings_whatsapp_status_label.setText("Se cargaron plantillas sugeridas. Guarda para aplicarlas.")

    def _build_layaway_whatsapp_message(self, apartado: Apartado) -> str:
        due_text, _ = self._classify_layaway_due(apartado.fecha_compromiso, apartado.estado)
        due_date_text = (
            apartado.fecha_compromiso.strftime("%Y-%m-%d")
            if apartado.fecha_compromiso
            else "sin fecha definida"
        )
        templates = self._get_whatsapp_templates()
        values = {
            "cliente": apartado.cliente_nombre,
            "folio": apartado.folio,
            "saldo": apartado.saldo_pendiente,
            "vencimiento": due_text,
            "fecha_compromiso": due_date_text,
        }
        if apartado.estado == EstadoApartado.ENTREGADO:
            return (
                f"Hola {apartado.cliente_nombre}, tu apartado {apartado.folio} ya fue entregado. "
                "Gracias por tu compra."
            )
        if apartado.estado == EstadoApartado.CANCELADO:
            return (
                f"Hola {apartado.cliente_nombre}, tu apartado {apartado.folio} fue cancelado. "
                "Si necesitas apoyo, escribenos."
            )
        if Decimal(apartado.saldo_pendiente) <= Decimal("0.00"):
            return self._render_whatsapp_template(templates["layaway_liquidated"], values)
        return self._render_whatsapp_template(templates["layaway_reminder"], values)

    def _handle_layaway_selection(self) -> None:
        self._refresh_layaway_detail(self._selected_layaway_id())

    def _handle_layaway_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_layaways(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de apartados.")

    def _handle_catalog_filters_changed(self) -> None:
        self._refresh_catalog_uniform_macro_buttons()
        try:
            with get_session() as session:
                self._refresh_catalog(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de productos.")

    def _handle_clear_catalog_filters(self) -> None:
        self.catalog_search_input.clear()
        for combo in (
            self.catalog_status_filter_combo,
            self.catalog_stock_filter_combo,
            self.catalog_layaway_filter_combo,
            self.catalog_origin_filter_combo,
            self.catalog_duplicate_filter_combo,
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        for widget in (
            self.catalog_category_filter_combo,
            self.catalog_brand_filter_combo,
            self.catalog_school_filter_combo,
            self.catalog_type_filter_combo,
            self.catalog_piece_filter_combo,
            self.catalog_size_filter_combo,
            self.catalog_color_filter_combo,
        ):
            widget.clear_selection()
        self._refresh_catalog_uniform_macro_buttons()
        self._handle_catalog_filters_changed()

    def _set_catalog_uniform_macro_filter(self, macro_type: str) -> None:
        current_selection = self.catalog_type_filter_combo.selected_values()
        if current_selection == {macro_type}:
            self.catalog_type_filter_combo.clear_selection()
        else:
            self.catalog_type_filter_combo.set_selected_values([macro_type])
        self._refresh_catalog_uniform_macro_buttons()

    def _refresh_catalog_uniform_macro_buttons(self) -> None:
        selected_types = self.catalog_type_filter_combo.selected_values()
        active_macro = next(iter(selected_types)) if len(selected_types) == 1 else ""
        for macro_type, button in self.catalog_uniform_macro_buttons.items():
            is_active = macro_type == active_macro
            button.setProperty("active", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _handle_history_source_changed(self) -> None:
        current_source = str(self.history_source_combo.currentData() or "")
        current_type = str(self.history_type_combo.currentData() or "")
        self.history_type_combo.blockSignals(True)
        self.history_type_combo.clear()
        self.history_type_combo.addItem("Todos", "")
        if current_source in {"", "inventory"}:
            for tipo in TipoMovimientoInventario:
                self.history_type_combo.addItem(f"Inv. {tipo.value}", f"inventory:{tipo.value}")
        if current_source in {"", "catalog"}:
            for tipo in TipoCambioCatalogo:
                self.history_type_combo.addItem(f"Cat. {tipo.value}", f"catalog:{tipo.value}")
        if current_type:
            index = self.history_type_combo.findData(current_type)
            if index >= 0:
                self.history_type_combo.setCurrentIndex(index)
        self.history_type_combo.blockSignals(False)
        self._handle_history_filter()

    def _set_history_today(self) -> None:
        today = QDate.currentDate()
        self.history_from_input.setDate(today)
        self.history_to_input.setDate(today)
        self._handle_history_filter()

    def _clear_history_filters(self) -> None:
        empty_date = self.history_from_input.minimumDate()
        self.history_sku_input.clear()
        self.history_source_combo.setCurrentIndex(0)
        self.history_entity_combo.setCurrentIndex(0)
        self.history_type_combo.setCurrentIndex(0)
        self.history_from_input.setDate(empty_date)
        self.history_to_input.setDate(empty_date)
        self._handle_history_filter()

    def _refresh_layaways(self, session) -> None:
        apartados = ApartadoService.listar_apartados(session)
        search_text = self.layaway_search_input.text().strip().lower()
        state_filter = str(self.layaway_state_combo.currentData() or "")
        due_filter = str(self.layaway_due_combo.currentData() or "")
        selected_id = self._selected_layaway_id()
        today = date.today()
        week_limit = today + timedelta(days=7)

        rows: list[dict[str, object]] = []
        for apartado in apartados:
            if state_filter and apartado.estado.value != state_filter:
                continue
            searchable = " ".join(
                [
                    apartado.folio,
                    apartado.cliente.codigo_cliente if apartado.cliente is not None else "",
                    apartado.cliente_nombre,
                    apartado.cliente_telefono or "",
                ]
            ).lower()
            if search_text and search_text not in searchable:
                continue
            due_date = apartado.fecha_compromiso.date() if apartado.fecha_compromiso else None
            due_bucket = "none"
            if due_date is not None and apartado.estado not in {EstadoApartado.ENTREGADO, EstadoApartado.CANCELADO}:
                if due_date < today:
                    due_bucket = "overdue"
                elif due_date == today:
                    due_bucket = "today"
                elif due_date <= week_limit:
                    due_bucket = "week"
            if due_filter and due_bucket != due_filter:
                continue
            due_text, due_tone = self._classify_layaway_due(apartado.fecha_compromiso, apartado.estado)
            rows.append(
                {
                    "id": apartado.id,
                    "folio": apartado.folio,
                    "cliente": (
                        f"{apartado.cliente.codigo_cliente} · {apartado.cliente_nombre}"
                        if apartado.cliente is not None
                        else f"Manual · {apartado.cliente_nombre}"
                    ),
                    "estado": apartado.estado.value,
                    "total": Decimal(apartado.total),
                    "abonado": Decimal(apartado.total_abonado),
                    "saldo": Decimal(apartado.saldo_pendiente),
                    "fecha_compromiso": apartado.fecha_compromiso,
                    "due_text": due_text,
                    "due_tone": due_tone,
                }
            )

        self.layaway_rows = rows
        self.layaway_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["folio"],
                row["cliente"],
                row["estado"],
                row["total"],
                row["abonado"],
                row["saldo"],
                row["due_text"],
            ]
            for column_index, value in enumerate(values):
                self.layaway_table.setItem(row_index, column_index, _table_item(value))
            self.layaway_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, int(row["id"]))
            status_item = self.layaway_table.item(row_index, 2)
            balance_item = self.layaway_table.item(row_index, 5)
            due_item = self.layaway_table.item(row_index, 6)
            if status_item is not None:
                tone = {
                    EstadoApartado.ACTIVO.value: "warning",
                    EstadoApartado.LIQUIDADO.value: "positive",
                    EstadoApartado.ENTREGADO.value: "muted",
                    EstadoApartado.CANCELADO.value: "danger",
                }.get(str(row["estado"]), "muted")
                _set_table_badge_style(status_item, tone)
            if balance_item is not None:
                _set_table_badge_style(
                    balance_item,
                    "positive" if Decimal(row["saldo"]) == Decimal("0.00") else "warning",
                )
            if due_item is not None:
                _set_table_badge_style(due_item, str(row["due_tone"]))
        self.layaway_table.resizeColumnsToContents()

        if rows:
            self.layaway_status_label.setText(
                f"Apartados visibles: {len(rows)} | Pendiente total: ${sum(Decimal(r['saldo']) for r in rows)}"
            )
        else:
            self.layaway_status_label.setText("No hay apartados con esos filtros.")

        if selected_id is not None:
            self.layaway_table.blockSignals(True)
            for row_index in range(self.layaway_table.rowCount()):
                item = self.layaway_table.item(row_index, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self.layaway_table.setCurrentCell(row_index, 0)
                    self.layaway_table.selectRow(row_index)
                    break
            self.layaway_table.blockSignals(False)

        self._refresh_layaway_detail(self._selected_layaway_id())

    def _refresh_layaway_detail(self, apartado_id: int | None) -> None:
        if not apartado_id:
            self.layaway_summary_label.setText("Selecciona un apartado")
            self.layaway_customer_label.setText("Sin detalle.")
            self.layaway_balance_label.setText("")
            self.layaway_commitment_label.setText("")
            self._set_badge_state(self.layaway_due_status_label, "Sin detalle", "neutral")
            self.layaway_notes_label.setText("")
            self.layaway_detail_table.setRowCount(0)
            self.layaway_payments_table.setRowCount(0)
            self.layaway_sale_ticket_button.setEnabled(False)
            self.layaway_whatsapp_button.setEnabled(False)
            return

        try:
            with get_session() as session:
                apartado = ApartadoService.obtener_apartado(session, apartado_id)
                if apartado is None:
                    raise ValueError("Apartado no encontrado.")

                self.layaway_summary_label.setText(f"{apartado.folio} | {apartado.estado.value}")
                self.layaway_customer_label.setText(
                    " | ".join(
                        filter(
                            None,
                            [
                                apartado.cliente.codigo_cliente if apartado.cliente is not None else "",
                                apartado.cliente_nombre,
                                apartado.cliente_telefono or "Sin telefono",
                            ],
                        )
                    )
                )
                self.layaway_balance_label.setText(
                    f"Total ${apartado.total} | Abonado ${apartado.total_abonado} | Saldo ${apartado.saldo_pendiente}"
                )
                self.layaway_commitment_label.setText(
                    "Compromiso: "
                    + (apartado.fecha_compromiso.strftime("%Y-%m-%d") if apartado.fecha_compromiso else "Sin fecha")
                )
                due_text, due_tone = self._classify_layaway_due(apartado.fecha_compromiso, apartado.estado)
                self._set_badge_state(self.layaway_due_status_label, due_text, due_tone)
                self.layaway_notes_label.setText(apartado.observacion or "Sin observaciones.")
                can_manage_layaways = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
                self.layaway_sale_ticket_button.setEnabled(
                    can_manage_layaways and apartado.estado == EstadoApartado.ENTREGADO
                )
                self.layaway_whatsapp_button.setEnabled(
                    can_manage_layaways and bool((apartado.cliente_telefono or "").strip())
                )

                self.layaway_detail_table.setRowCount(len(apartado.detalles))
                for row_index, detalle in enumerate(apartado.detalles):
                    values = [
                        detalle.variante.sku,
                        detalle.variante.producto.nombre,
                        detalle.cantidad,
                        detalle.precio_unitario,
                        detalle.subtotal_linea,
                    ]
                    for column_index, value in enumerate(values):
                        self.layaway_detail_table.setItem(row_index, column_index, _table_item(value))
                self.layaway_detail_table.resizeColumnsToContents()

                self.layaway_payments_table.setRowCount(len(apartado.abonos))
                for row_index, abono in enumerate(apartado.abonos):
                    values = [
                        abono.created_at.strftime("%Y-%m-%d %H:%M") if abono.created_at else "",
                        abono.monto,
                        abono.referencia or "",
                        abono.usuario.username,
                    ]
                    for column_index, value in enumerate(values):
                        self.layaway_payments_table.setItem(row_index, column_index, _table_item(value))
                self.layaway_payments_table.resizeColumnsToContents()
        except Exception as exc:  # noqa: BLE001
            self.layaway_summary_label.setText("No se pudo cargar el apartado")
            self.layaway_customer_label.setText(str(exc))
            self.layaway_balance_label.setText("")
            self.layaway_commitment_label.setText("")
            self._set_badge_state(self.layaway_due_status_label, "Sin detalle", "neutral")
            self.layaway_notes_label.setText("")
            self.layaway_detail_table.setRowCount(0)
            self.layaway_payments_table.setRowCount(0)
            self.layaway_sale_ticket_button.setEnabled(False)
            self.layaway_whatsapp_button.setEnabled(False)

    def _handle_open_layaway_whatsapp(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para abrir WhatsApp.")
            return

        try:
            with get_session() as session:
                apartado = ApartadoService.obtener_apartado(session, apartado_id)
                if apartado is None:
                    raise ValueError("No se encontro el apartado seleccionado.")
                if not (apartado.cliente_telefono or "").strip():
                    raise ValueError("El apartado seleccionado no tiene telefono registrado.")
                normalized_phone = self._normalize_whatsapp_phone(apartado.cliente_telefono or "")
                if len(normalized_phone) < 10:
                    raise ValueError("El telefono del cliente no parece valido para WhatsApp.")
                message = self._build_layaway_whatsapp_message(apartado)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WhatsApp no disponible", str(exc))
            return

        whatsapp_url = f"https://wa.me/{normalized_phone}?text={quote(message)}"
        if not webbrowser.open(whatsapp_url):
            QMessageBox.warning(
                self,
                "No se pudo abrir WhatsApp",
                "No se pudo abrir WhatsApp automaticamente. Verifica que tengas navegador disponible.",
            )

    def _prompt_create_layaway_data(self, initial_items: list[dict[str, object]] | None = None) -> dict[str, object] | None:
        dialog, layout = self._create_modal_dialog(
            "Nuevo apartado",
            "Agrega una o varias presentaciones y registra el anticipo inicial del apartado.",
            width=760,
        )
        form = QFormLayout()
        client_selector = QComboBox()
        client_selector.addItem("Manual / sin cliente", None)
        customer_input = QLineEdit()
        customer_input.setPlaceholderText("Nombre del cliente")
        phone_input = QLineEdit()
        phone_input.setPlaceholderText("Telefono")
        last_autofill = {"nombre": "", "telefono": ""}
        try:
            with get_session() as session:
                for client in [item for item in ClientService.list_clients(session) if item.activo]:
                    client_selector.addItem(
                        f"{client.codigo_cliente} · {client.nombre}",
                        {
                            "id": int(client.id),
                            "nombre": client.nombre,
                            "telefono": client.telefono or "",
                        },
                    )
        except Exception:
            pass

        def sync_selected_client() -> None:
            nonlocal last_autofill
            selected_client = client_selector.currentData()
            if isinstance(selected_client, dict):
                nombre = str(selected_client.get("nombre", "")).strip()
                telefono = str(selected_client.get("telefono", "")).strip()
                customer_input.setText(nombre)
                phone_input.setText(telefono)
                last_autofill = {"nombre": nombre, "telefono": telefono}
                return
            if customer_input.text().strip() == last_autofill["nombre"]:
                customer_input.clear()
            if phone_input.text().strip() == last_autofill["telefono"]:
                phone_input.clear()
            last_autofill = {"nombre": "", "telefono": ""}

        client_selector.currentIndexChanged.connect(sync_selected_client)
        form.addRow("Cliente guardado", client_selector)
        form.addRow("Cliente", customer_input)
        form.addRow("Telefono", phone_input)

        items: list[dict[str, object]] = [
            {
                "sku": str(item["sku"]),
                "producto_nombre": str(item["producto_nombre"]),
                "cantidad": int(item["cantidad"]),
                "precio_unitario": Decimal(item["precio_unitario"]),
            }
            for item in (initial_items or [])
        ]
        sku_input = QLineEdit()
        sku_input.setPlaceholderText("SKU")
        selected = self._selected_catalog_row()
        if selected is not None:
            sku_input.setText(str(selected["sku"]))
        qty_spin = QSpinBox()
        qty_spin.setRange(1, 100)
        add_item_button = QPushButton("Agregar presentacion")
        remove_item_button = QPushButton("Quitar seleccionada")
        items_table = QTableWidget()
        items_table.setColumnCount(5)
        items_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
        items_table.setObjectName("dataTable")
        items_table.verticalHeader().setVisible(False)
        items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        items_table.setAlternatingRowColors(True)
        total_label = QLabel("Total estimado: $0.00")
        total_label.setObjectName("analyticsLine")

        def refresh_items_table() -> None:
            total = Decimal("0.00")
            items_table.setRowCount(len(items))
            for row_index, item in enumerate(items):
                subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
                total += subtotal
                values = [
                    item["sku"],
                    item["producto_nombre"],
                    item["cantidad"],
                    item["precio_unitario"],
                    subtotal,
                ]
                for column_index, value in enumerate(values):
                    items_table.setItem(row_index, column_index, _table_item(value))
            items_table.resizeColumnsToContents()
            total_label.setText(f"Total estimado: ${total}")

        def handle_add_item() -> None:
            sku = sku_input.text().strip().upper()
            cantidad = qty_spin.value()
            if not sku:
                QMessageBox.warning(dialog, "SKU requerido", "Captura o escanea un SKU para agregarlo.")
                return
            try:
                with get_session() as session:
                    variante = ApartadoService.obtener_variante_por_sku(session, sku)
                    if variante is None:
                        raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")
                    InventarioService.validar_stock_disponible(variante, cantidad)
                    producto_nombre = variante.producto.nombre
                    precio_unitario = Decimal(variante.precio_venta)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if "Stock insuficiente" in message:
                    message = f"No hay stock suficiente para reservar {cantidad} pieza(s) de '{sku}'."
                QMessageBox.warning(dialog, "No se pudo agregar", message)
                return

            existing = next((item for item in items if str(item["sku"]) == sku), None)
            if existing is not None:
                nueva_cantidad = int(existing["cantidad"]) + cantidad
                try:
                    with get_session() as session:
                        variante = ApartadoService.obtener_variante_por_sku(session, sku)
                        if variante is None:
                            raise ValueError(f"El SKU '{sku}' no existe o esta inactivo.")
                        InventarioService.validar_stock_disponible(variante, nueva_cantidad)
                except Exception as exc:  # noqa: BLE001
                    message = str(exc)
                    if "Stock insuficiente" in message:
                        message = f"No hay stock suficiente para dejar {nueva_cantidad} pieza(s) de '{sku}' en el apartado."
                    QMessageBox.warning(dialog, "Stock insuficiente", message)
                    return
                existing["cantidad"] = nueva_cantidad
            else:
                items.append(
                    {
                        "sku": sku,
                        "producto_nombre": producto_nombre,
                        "cantidad": cantidad,
                        "precio_unitario": precio_unitario,
                    }
                )

            sku_input.clear()
            qty_spin.setValue(1)
            refresh_items_table()

        def handle_remove_item() -> None:
            row_index = items_table.currentRow()
            if row_index < 0 or row_index >= len(items):
                return
            items.pop(row_index)
            refresh_items_table()

        add_item_button.clicked.connect(handle_add_item)
        remove_item_button.clicked.connect(handle_remove_item)

        line_row = QHBoxLayout()
        line_row.setSpacing(8)
        line_row.addWidget(QLabel("SKU"))
        line_row.addWidget(sku_input, 1)
        line_row.addWidget(QLabel("Cantidad"))
        line_row.addWidget(qty_spin)
        line_row.addWidget(add_item_button)
        line_row.addWidget(remove_item_button)

        due_input = QLineEdit()
        due_input.setPlaceholderText("YYYY-MM-DD")
        due_input.setText((date.today() + timedelta(days=15)).isoformat())
        deposit_spin = QDoubleSpinBox()
        deposit_spin.setRange(0.0, 999999.99)
        deposit_spin.setDecimals(2)
        deposit_spin.setPrefix("$")
        notes_input = QTextEdit()
        notes_input.setMaximumHeight(90)
        form.addRow("Anticipo", deposit_spin)
        form.addRow("Fecha compromiso", due_input)
        form.addRow("Observacion", notes_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addLayout(line_row)
        layout.addWidget(items_table)
        layout.addWidget(total_label)
        layout.addWidget(buttons)
        refresh_items_table()
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        if not items:
            QMessageBox.warning(self, "Sin presentaciones", "Agrega al menos una presentacion al apartado.")
            return None
        return {
            "cliente_id": (
                int(client_selector.currentData()["id"])
                if isinstance(client_selector.currentData(), dict)
                else None
            ),
            "cliente_nombre": customer_input.text().strip(),
            "cliente_telefono": phone_input.text().strip(),
            "items": [
                ApartadoItemInput(
                    sku=str(item["sku"]),
                    cantidad=int(item["cantidad"]),
                )
                for item in items
            ],
            "anticipo": Decimal(str(deposit_spin.value())),
            "fecha_compromiso": due_input.text().strip(),
            "observacion": notes_input.toPlainText().strip(),
        }

    def _handle_create_layaway(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "No tienes permisos para crear apartados.")
            return
        if not self._ensure_cash_session_current_day_for_operation("crear apartados"):
            return
        payload = self._prompt_create_layaway_data()
        if payload is None:
            return

        try:
            due_value = None
            if payload["fecha_compromiso"]:
                due_date = date.fromisoformat(str(payload["fecha_compromiso"]))
                due_value = datetime.combine(due_date, datetime.min.time())
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("No se pudo cargar el usuario actual.")
                cliente = None
                if payload["cliente_id"] is not None:
                    cliente = session.get(Cliente, int(payload["cliente_id"]))
                    if cliente is None:
                        raise ValueError("No se pudo cargar el cliente seleccionado.")
                apartado = ApartadoService.crear_apartado(
                    session=session,
                    usuario=usuario,
                    folio=self._generate_layaway_folio(),
                    cliente_nombre=str(payload["cliente_nombre"]),
                    cliente_telefono=str(payload["cliente_telefono"]),
                    items=list(payload["items"]),
                    anticipo=Decimal(payload["anticipo"]),
                    fecha_compromiso=due_value,
                    observacion=str(payload["observacion"]) or None,
                    cliente=cliente,
                )
                session.commit()
                apartado_id = apartado.id
                apartado_folio = apartado.folio
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Apartado no creado", str(exc))
            return

        self.refresh_all()
        self._select_layaway(apartado_id)
        QMessageBox.information(self, "Apartado creado", f"Apartado {apartado_folio} registrado correctamente.")

    def _handle_convert_sale_cart_to_layaway(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "No tienes permisos para convertir el carrito en apartado.")
            return
        if self.active_cash_session_id is None:
            QMessageBox.information(self, "Caja cerrada", "Abre caja antes de convertir el carrito en apartado.")
            self._handle_cash_cut()
            return
        if not self._ensure_cash_session_current_day_for_operation("convertir a apartado"):
            return
        if not self.sale_cart:
            if self.sale_sku_input.text().strip():
                self._handle_add_sale_item()
            if not self.sale_cart:
                QMessageBox.warning(self, "Carrito vacio", "Agrega al menos una linea antes de convertirla en apartado.")
                return

        payload = self._prompt_create_layaway_data(initial_items=self.sale_cart)
        if payload is None:
            return

        try:
            due_value = None
            if payload["fecha_compromiso"]:
                due_date = date.fromisoformat(str(payload["fecha_compromiso"]))
                due_value = datetime.combine(due_date, datetime.min.time())
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("No se pudo cargar el usuario actual.")
                cliente = None
                if payload["cliente_id"] is not None:
                    cliente = session.get(Cliente, int(payload["cliente_id"]))
                    if cliente is None:
                        raise ValueError("No se pudo cargar el cliente seleccionado.")
                apartado = ApartadoService.crear_apartado(
                    session=session,
                    usuario=usuario,
                    folio=self._generate_layaway_folio(),
                    cliente_nombre=str(payload["cliente_nombre"]),
                    cliente_telefono=str(payload["cliente_telefono"]),
                    items=list(payload["items"]),
                    anticipo=Decimal(payload["anticipo"]),
                    fecha_compromiso=due_value,
                    observacion=str(payload["observacion"]) or "Creado desde Caja.",
                    cliente=cliente,
                )
                session.commit()
                apartado_id = apartado.id
                apartado_folio = apartado.folio
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo convertir", str(exc))
            return

        self.sale_cart.clear()
        self._refresh_sale_cart_table()
        self._reset_sale_form()
        self.refresh_all()
        self._select_layaway(apartado_id)
        if self.tabs is not None:
            self.tabs.setCurrentIndex(2)
        self._set_sale_feedback(
            f"Carrito convertido en apartado {apartado_folio}.",
            "positive",
            auto_clear_ms=2200,
        )
        QMessageBox.information(
            self,
            "Apartado creado",
            f"El carrito actual se convirtio en el apartado {apartado_folio}.",
        )

    def _prompt_layaway_payment_data(self) -> tuple[Decimal, str, Decimal, str, str] | None:
        dialog, layout = self._create_modal_dialog("Registrar abono", width=420)
        form = QFormLayout()
        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0.01, 999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        payment_combo = QComboBox()
        payment_combo.addItems(["Efectivo", "Transferencia", "Mixto"])
        cash_spin = QDoubleSpinBox()
        cash_spin.setRange(0.00, 999999.99)
        cash_spin.setDecimals(2)
        cash_spin.setPrefix("$")
        reference_input = QLineEdit()
        reference_input.setPlaceholderText("Referencia opcional")
        notes_input = QTextEdit()
        notes_input.setMaximumHeight(90)
        form.addRow("Monto", amount_spin)
        form.addRow("Metodo", payment_combo)
        form.addRow("Efectivo en caja", cash_spin)
        form.addRow("Referencia", reference_input)
        form.addRow("Observacion", notes_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

        def sync_cash_spin() -> None:
            method = payment_combo.currentText()
            amount_spin_value = amount_spin.value()
            if method == "Efectivo":
                cash_spin.blockSignals(True)
                cash_spin.setValue(amount_spin_value)
                cash_spin.blockSignals(False)
                cash_spin.setEnabled(False)
            elif method == "Transferencia":
                cash_spin.blockSignals(True)
                cash_spin.setValue(0.0)
                cash_spin.blockSignals(False)
                cash_spin.setEnabled(False)
            else:
                cash_spin.setEnabled(True)
                cash_spin.setMaximum(amount_spin_value)

        payment_combo.currentTextChanged.connect(sync_cash_spin)
        amount_spin.valueChanged.connect(sync_cash_spin)
        sync_cash_spin()

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return (
            Decimal(str(amount_spin.value())),
            payment_combo.currentText().strip() or "Efectivo",
            Decimal(str(cash_spin.value())),
            reference_input.text().strip(),
            notes_input.toPlainText().strip(),
        )

    def _handle_register_layaway_payment(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para registrar abono.")
            return
        if not self._ensure_cash_session_current_day_for_operation("registrar abonos"):
            return
        payload = self._prompt_layaway_payment_data()
        if payload is None:
            return
        amount, payment_method, cash_amount, reference, notes = payload
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                apartado = ApartadoService.obtener_apartado(session, apartado_id)
                if usuario is None or apartado is None:
                    raise ValueError("No se pudo cargar el apartado seleccionado.")
                ApartadoService.registrar_abono(
                    session=session,
                    apartado=apartado,
                    usuario=usuario,
                    monto=amount,
                    metodo_pago=payment_method,
                    monto_efectivo=cash_amount,
                    referencia=reference or None,
                    observacion=notes or None,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Abono no registrado", str(exc))
            return

        self.refresh_all()
        self._select_layaway(apartado_id)
        QMessageBox.information(
            self,
            "Abono registrado",
            f"Se registro un abono por ${amount}. Efectivo en caja: ${cash_amount}.",
        )

    def _handle_deliver_layaway(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para entregarlo.")
            return
        if not self._ensure_cash_session_current_day_for_operation("entregar apartados"):
            return
        confirmation = QMessageBox.question(
            self,
            "Entregar apartado",
            "El apartado se marcara como entregado. Esta accion no cambia stock porque ya estaba reservado.\n\nContinuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                apartado = ApartadoService.obtener_apartado(session, apartado_id)
                if usuario is None or apartado is None:
                    raise ValueError("No se pudo cargar el apartado seleccionado.")
                sale = VentaService.crear_confirmada_desde_apartado(
                    session=session,
                    usuario=usuario,
                    apartado=apartado,
                    folio=f"ENT-{apartado.folio}",
                    observacion=f"Entrega de apartado {apartado.folio}",
                )
                ApartadoService.entregar_apartado(session, apartado, usuario)
                session.commit()
                sale_folio = sale.folio
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo entregar", str(exc))
            return

        self.refresh_all()
        self._select_layaway(apartado_id)
        QMessageBox.information(
            self,
            "Apartado entregado",
            f"La mercancia quedo marcada como entregada y se genero la venta {sale_folio}.",
        )

    def _handle_cancel_layaway(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para cancelarlo.")
            return
        dialog, layout = self._create_modal_dialog("Cancelar apartado", width=420)
        note_input = QTextEdit()
        note_input.setPlaceholderText("Motivo de cancelacion")
        note_input.setMaximumHeight(100)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(note_input)
        layout.addWidget(buttons)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                apartado = ApartadoService.obtener_apartado(session, apartado_id)
                if usuario is None or apartado is None:
                    raise ValueError("No se pudo cargar el apartado seleccionado.")
                ApartadoService.cancelar_apartado(
                    session=session,
                    apartado=apartado,
                    usuario=usuario,
                    observacion=note_input.toPlainText().strip() or None,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cancelar", str(exc))
            return

        self.refresh_all()
        self._select_layaway(apartado_id)
        QMessageBox.information(self, "Apartado cancelado", "El stock reservado se libero correctamente.")

    def _select_layaway(self, apartado_id: int) -> None:
        self.layaway_table.blockSignals(True)
        for row_index in range(self.layaway_table.rowCount()):
            item = self.layaway_table.item(row_index, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == apartado_id:
                self.layaway_table.setCurrentCell(row_index, 0)
                self.layaway_table.selectRow(row_index)
                break
        self.layaway_table.blockSignals(False)
        self._refresh_layaway_detail(apartado_id)

    def _refresh_selected_qr_preview(self) -> None:
        variante_id = self.inventory_variant_combo.currentData()
        if not variante_id:
            self.inventory_generate_qr_button.setText("Generar QR")
            self.qr_preview_label.clear()
            self.qr_preview_label.setText("QR pendiente")
            self.qr_preview_info_label.setText("")
            self._set_badge_state(self.qr_status_label, "Sin seleccion", "neutral")
            self._refresh_inventory_overview()
            return

        try:
            with get_session() as session:
                variante = session.get(Variante, int(variante_id))
                if variante is None:
                    raise ValueError("Presentacion no encontrada.")
                path = QrGenerator.path_for_variant(variante)
                self.qr_preview_info_label.setText(
                    f"{variante.sku} | {variante.producto.nombre} | talla {variante.talla} | color {variante.color}"
                )
                if not path.exists():
                    self.inventory_generate_qr_button.setText("Generar QR")
                    self.qr_preview_label.clear()
                    self.qr_preview_label.setText("QR pendiente")
                    self._set_badge_state(
                        self.qr_status_label,
                        "QR pendiente. Genera la etiqueta cuando la necesites.",
                        "warning",
                    )
                    self._refresh_inventory_overview()
                    self._sync_inventory_table_selection(variante_id)
                    return
        except Exception:  # noqa: BLE001
            self.inventory_generate_qr_button.setText("Generar QR")
            self.qr_preview_label.clear()
            self.qr_preview_label.setText("QR pendiente")
            self.qr_preview_info_label.setText("")
            self._set_badge_state(self.qr_status_label, "Sin datos de QR", "muted")
            self._refresh_inventory_overview()
            return

        self.inventory_generate_qr_button.setText("Regenerar QR")
        self._load_qr_preview(path)
        self._set_badge_state(self.qr_status_label, f"QR disponible: {path.name}", "positive")
        self._refresh_inventory_overview()
        self._sync_inventory_table_selection(variante_id)

    def _render_inventory_label(
        self,
        *,
        variant_id: int,
        mode: str,
        requested_copies: int,
    ):
        with get_session() as session:
            variante = session.get(Variante, int(variant_id))
            if variante is None:
                raise ValueError("Presentacion no encontrada.")
            # Forzar carga de relaciones usadas en el render antes de salir de sesion.
            _ = variante.producto.nombre
            if variante.producto.escuela is not None:
                _ = variante.producto.escuela.nombre
            if variante.producto.nivel_educativo is not None:
                _ = variante.producto.nivel_educativo.nombre
            return LabelGenerator.render_for_variant(
                variante,
                mode=mode,
                requested_copies=requested_copies,
            )

    def _print_image_path(
        self,
        image_path: Path,
        *,
        title: str,
        copies: int,
        parent: QDialog | None = None,
    ) -> bool:
        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError(f"No se pudo abrir la imagen de etiqueta:\n{image_path}")
        printer = QPrinter()
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                preferred_printer = config.impresora_preferida or ""
        except Exception:
            preferred_printer = ""
        if preferred_printer:
            printer.setPrinterName(preferred_printer)
        print_dialog = QPrintDialog(printer, parent or self)
        print_dialog.setWindowTitle(title)
        if print_dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        painter = QPainter()
        if not painter.begin(printer):
            raise ValueError("No se pudo iniciar la impresion de la etiqueta.")
        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            scaled = image.scaled(
                page_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_pos = page_rect.x() + max(0, (page_rect.width() - scaled.width()) // 2)
            y_pos = page_rect.y() + max(0, (page_rect.height() - scaled.height()) // 2)
            for copy_index in range(max(1, copies)):
                if copy_index > 0:
                    printer.newPage()
                painter.drawImage(x_pos, y_pos, scaled)
        finally:
            painter.end()
        return True

    def _handle_inventory_print_label(self) -> None:
        variante_id = self.inventory_variant_combo.currentData()
        if not variante_id:
            QMessageBox.warning(
                self,
                "Sin presentacion",
                "Selecciona una presentacion para preparar la impresion de su etiqueta.",
            )
            return

        try:
            with get_session() as session:
                variante = session.get(Variante, int(variante_id))
                if variante is None:
                    raise ValueError("Presentacion no encontrada.")
                product_name = variante.producto.nombre
                sku = variante.sku
                talla = variante.talla
                color = variante.color
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Impresion no disponible", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Imprimir etiqueta")
        dialog.resize(720, 620)
        layout = QVBoxLayout()
        header = QLabel(f"{sku} | {product_name} | talla {talla} | color {color}")
        header.setWordWrap(True)
        header.setObjectName("inventoryMetaCard")
        layout.addWidget(header)

        controls = QGridLayout()
        mode_combo = QComboBox()
        mode_combo.addItem("Normal", "standard")
        mode_combo.addItem("Split", "split")
        copies_spin = QSpinBox()
        copies_spin.setRange(1, 500)
        copies_spin.setValue(1)
        mode_hint = QLabel(
            "Normal imprime una etiqueta por pieza. Split mantiene la hoja dividida en 4 y calcula hojas automaticamente."
        )
        mode_hint.setWordWrap(True)
        mode_hint.setObjectName("subtleLine")
        controls.addWidget(QLabel("Modo"), 0, 0)
        controls.addWidget(mode_combo, 0, 1)
        controls.addWidget(QLabel("Piezas / copias"), 0, 2)
        controls.addWidget(copies_spin, 0, 3)
        controls.addWidget(mode_hint, 1, 0, 1, 4)
        layout.addLayout(controls)

        preview_label = QLabel("Generando vista previa...")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setMinimumHeight(280)
        preview_label.setObjectName("qrPreview")
        summary_label = QLabel("")
        summary_label.setWordWrap(True)
        summary_label.setObjectName("subtleLine")
        layout.addWidget(preview_label, 1)
        layout.addWidget(summary_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

        preview_state: dict[str, object] = {"result": None}

        def refresh_preview() -> None:
            try:
                result = self._render_inventory_label(
                    variant_id=int(variante_id),
                    mode=str(mode_combo.currentData() or "standard"),
                    requested_copies=int(copies_spin.value()),
                )
            except Exception as exc:  # noqa: BLE001
                preview_state["result"] = None
                preview_label.clear()
                preview_label.setText("No se pudo generar la etiqueta")
                summary_label.setText(str(exc))
                print_button.setEnabled(False)
                return

            preview_state["result"] = result
            pixmap = QPixmap(str(result.image_path))
            if pixmap.isNull():
                preview_label.clear()
                preview_label.setText("Sin vista previa")
            else:
                scaled = pixmap.scaled(
                    preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                preview_label.setPixmap(scaled)
            mode_label = "Split" if result.mode == "split" else "Normal"
            if result.mode == "split":
                summary_label.setText(
                    f"Modo {mode_label} | Piezas solicitadas: {result.requested_copies} | "
                    f"Hojas a imprimir: {result.effective_copies} | Archivo: {result.image_path.name}"
                )
            else:
                summary_label.setText(
                    f"Modo {mode_label} | Copias a imprimir: {result.effective_copies} | Archivo: {result.image_path.name}"
                )
            print_button.setEnabled(True)

        def handle_print() -> None:
            result = preview_state.get("result")
            if result is None:
                refresh_preview()
                result = preview_state.get("result")
            if result is None:
                return
            try:
                printed = self._print_image_path(
                    result.image_path,
                    title=f"Etiqueta {sku}",
                    copies=int(result.effective_copies),
                    parent=dialog,
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(dialog, "Impresion fallida", str(exc))
                return
            if printed:
                QMessageBox.information(
                    dialog,
                    "Etiqueta enviada",
                    (
                        f"Se envio la etiqueta de '{sku}' a impresion.\n\n"
                        f"Modo: {'Split' if result.mode == 'split' else 'Normal'}\n"
                        f"Piezas solicitadas: {result.requested_copies}\n"
                        f"Copias/hojas impresas: {result.effective_copies}"
                    ),
                )

        mode_combo.currentIndexChanged.connect(lambda _: refresh_preview())
        copies_spin.valueChanged.connect(lambda _: refresh_preview())
        print_button.clicked.connect(handle_print)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        refresh_preview()
        dialog.exec()

    def _load_qr_preview(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.qr_preview_label.clear()
            self.qr_preview_label.setText("Sin preview")
            return
        scaled = pixmap.scaled(
            self.qr_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.qr_preview_label.setPixmap(scaled)

    def _refresh_sale_cart_table(self) -> None:
        self.sale_cart_table.setRowCount(len(self.sale_cart))
        table_view = build_sale_cart_table_view(self.sale_cart)
        for row_index, row in enumerate(table_view.rows):
            for column_index, value in enumerate(row.values):
                self.sale_cart_table.setItem(row_index, column_index, _table_item(value))
        self.sale_cart_table.resizeColumnsToContents()
        pricing = self._calculate_sale_pricing()
        subtotal = pricing.subtotal
        applied_discount = pricing.applied_discount
        rounding_adjustment = pricing.rounding_adjustment
        total = pricing.collected_total
        breakdown = self._sale_discount_breakdown()
        winner_label = str(breakdown["winner_label"])
        payment_method = self.sale_payment_combo.currentText().strip() or "Efectivo"
        summary = build_sale_cashier_summary(
            has_items=bool(self.sale_cart),
            lines_count=len(self.sale_cart),
            total_items=table_view.total_items,
            subtotal=subtotal,
            applied_discount=applied_discount,
            rounding_adjustment=rounding_adjustment,
            collected_total=total,
            payment_method=payment_method,
            winner_label=winner_label,
        )
        self.sale_total_label.setText(summary.total_label)
        self.sale_total_meta_label.setText(summary.meta_label)
        self.sale_summary_label.setText(summary.summary_label)
        self._refresh_payment_fields()
        can_sell = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        self.sale_remove_button.setEnabled(can_sell and bool(self.sale_cart))
        self.sale_clear_button.setEnabled(can_sell and bool(self.sale_cart))
        self._refresh_permissions()

    def _refresh_quote_cart_table(self) -> None:
        self.quote_cart_table.setRowCount(len(self.quote_cart))
        total_items = 0
        total = Decimal("0.00")
        for row_index, item in enumerate(self.quote_cart):
            line_subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
            total_items += int(item["cantidad"])
            total += line_subtotal
            values = [
                item["sku"],
                item["producto_nombre"],
                item["cantidad"],
                item["precio_unitario"],
                line_subtotal,
            ]
            for column_index, value in enumerate(values):
                self.quote_cart_table.setItem(row_index, column_index, _table_item(value))
        self.quote_cart_table.resizeColumnsToContents()
        self.quote_total_label.setText(f"${total.quantize(Decimal('0.01'))}")
        self.quote_summary_label.setText(
            (
                f"Lineas: {len(self.quote_cart)} | Piezas: {total_items} | Total estimado: ${total.quantize(Decimal('0.01'))}"
            )
            if self.quote_cart
            else "Presupuesto vacio."
        )
        self._refresh_permissions()

    def _selected_catalog_row(self) -> dict[str, object] | None:
        selected_inventory_row = self.inventory_table.currentRow()
        if selected_inventory_row >= 0:
            item = self.inventory_table.item(selected_inventory_row, 0)
            if item is not None:
                variant_id = item.data(Qt.ItemDataRole.UserRole)
                if variant_id is not None:
                    return next(
                        (row for row in self.catalog_rows if int(row["variante_id"]) == int(variant_id)),
                        None,
                    )

        selected_row = self.catalog_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.catalog_rows):
            return None
        return self.catalog_rows[selected_row]

    def _handle_inventory_table_selection(self) -> None:
        selected_row = self.inventory_table.currentRow()
        if selected_row < 0:
            return
        item = self.inventory_table.item(selected_row, 0)
        if item is None:
            return
        variant_id = item.data(Qt.ItemDataRole.UserRole)
        if variant_id is None:
            return
        self._set_combo_value(self.inventory_variant_combo, variant_id)

    def _selected_inventory_variant_ids(self) -> list[int]:
        ids: list[int] = []
        seen: set[int] = set()
        for item in self.inventory_table.selectedItems():
            if item.column() != 0:
                continue
            variant_id = item.data(Qt.ItemDataRole.UserRole)
            if variant_id is None:
                continue
            parsed = int(variant_id)
            if parsed in seen:
                continue
            seen.add(parsed)
            ids.append(parsed)
        return ids

    def _handle_inventory_table_double_click(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.information(
                self,
                "Solo consulta",
                "El doble clic para editar esta disponible solo para ADMIN.",
            )
            return
        self._handle_update_variant()

    def _show_inventory_context_menu(self, pos) -> None:
        row_index = self.inventory_table.rowAt(pos.y())
        if row_index < 0:
            return
        self.inventory_table.setCurrentCell(row_index, 0)
        self.inventory_table.selectRow(row_index)

        selected = self._selected_catalog_row()
        if selected is None:
            return

        menu = QMenu(self)
        qr_exists = (QrGenerator.output_dir() / f"{selected['sku']}.png").exists()
        edit_action = menu.addAction("Editar presentacion")
        entry_action = menu.addAction("Registrar entrada")
        adjust_action = menu.addAction("Corregir stock")
        qr_action = menu.addAction("Regenerar QR" if qr_exists else "Generar QR")
        print_action = menu.addAction("Imprimir etiqueta")
        toggle_action = menu.addAction(
            "Activar presentacion" if not bool(selected["variante_activo"]) else "Desactivar presentacion"
        )

        is_admin = self.current_role == RolUsuario.ADMIN
        edit_action.setEnabled(is_admin)
        entry_action.setEnabled(is_admin)
        adjust_action.setEnabled(is_admin)
        toggle_action.setEnabled(is_admin)
        print_action.setEnabled(is_admin)

        chosen = menu.exec(self.inventory_table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self._handle_update_variant()
        elif chosen == entry_action:
            self._handle_purchase()
        elif chosen == adjust_action:
            self._handle_inventory_adjustment()
        elif chosen == qr_action:
            self._handle_generate_selected_qr()
        elif chosen == print_action:
            self._handle_inventory_print_label()
        elif chosen == toggle_action:
            self._handle_toggle_variant()

    def _sync_inventory_table_selection(self, variant_id: object) -> None:
        if variant_id is None:
            self.inventory_table.clearSelection()
            return
        self.inventory_table.blockSignals(True)
        for row_index in range(self.inventory_table.rowCount()):
            item = self.inventory_table.item(row_index, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == variant_id:
                self.inventory_table.setCurrentCell(row_index, 0)
                self.inventory_table.selectRow(row_index)
                break
        self.inventory_table.blockSignals(False)

    def _refresh_inventory_overview(self) -> None:
        variante_id = self.inventory_variant_combo.currentData()
        if not variante_id:
            self.inventory_overview_label.setText("Selecciona una presentacion")
            self.inventory_product_label.setText("Elige una fila para ver su ficha rapida.")
            self._set_badge_state(self.inventory_status_badge, "Sin seleccion", "neutral")
            self._set_badge_state(self.inventory_stock_badge, "Sin stock", "neutral")
            self.inventory_stock_hint_label.setText("")
            self.inventory_meta_label.setText("")
            self.inventory_last_movement_label.setText("")
            return

        try:
            with get_session() as session:
                variante = session.get(Variante, int(variante_id))
                if variante is None:
                    raise ValueError
                status = "ACTIVA" if variante.activo else "INACTIVA"
                stock_label = "agotado" if variante.stock_actual == 0 else "bajo" if variante.stock_actual <= 3 else "saludable"
                movement = session.scalar(
                    select(MovimientoInventario)
                    .where(MovimientoInventario.variante_id == variante.id)
                    .order_by(desc(MovimientoInventario.created_at))
                    .limit(1)
                )
                matching_row = next(
                    (row for row in self.catalog_rows if int(row["variante_id"]) == int(variante_id)),
                    None,
                )
                self.inventory_overview_label.setText(variante.sku)
                self.inventory_product_label.setText(
                    matching_row["producto_nombre_base"] if matching_row is not None else variante.producto.nombre
                )
                self._set_badge_state(
                    self.inventory_status_badge,
                    status,
                    "positive" if variante.activo else "muted",
                )
                stock_tone = "danger" if variante.stock_actual == 0 else "warning" if variante.stock_actual <= 3 else "positive"
                self._set_badge_state(
                    self.inventory_stock_badge,
                    stock_label.capitalize(),
                    stock_tone,
                )
                self.inventory_stock_hint_label.setText(
                    f"Talla {variante.talla} | Color {variante.color} | Precio {variante.precio_venta} | {matching_row['origen_etiqueta'] if matching_row is not None else 'NUEVO'}"
                )
                self.inventory_meta_label.setText(
                    f"Stock actual {variante.stock_actual} | Apartado {matching_row['apartado_cantidad'] if matching_row is not None else 0} | Escuela {matching_row['escuela_nombre'] if matching_row is not None else 'General'}"
                )
                if movement is None:
                    self.inventory_last_movement_label.setText("Sin movimientos registrados.")
                else:
                    movement_date = movement.created_at.strftime("%Y-%m-%d %H:%M") if movement.created_at else ""
                    movement_type = movement.tipo_movimiento.value.replace("_", " ").title()
                    self.inventory_last_movement_label.setText(
                        f"Ultimo movimiento: {movement_type} | {movement.cantidad:+} | {movement_date}"
                    )
                self.catalog_selection_label.setText(
                    f"{variante.sku} | {matching_row['producto_nombre_base'] if matching_row is not None else variante.producto.nombre} | {matching_row['tipo_prenda_nombre'] if matching_row is not None else '-'} | "
                    f"{matching_row['tipo_pieza_nombre'] if matching_row is not None else '-'} | precio {variante.precio_venta} | "
                    f"stock {variante.stock_actual} | apartado {matching_row['apartado_cantidad'] if matching_row is not None else 0}"
                )
                if matching_row is not None:
                    self.toggle_product_button.setText(
                        "Activar prod." if matching_row["producto_activo"] is False else "Desactivar prod."
                    )
                    self.toggle_variant_button.setText(
                        "Activar var." if matching_row["variante_activo"] is False else "Desactivar var."
                    )
        except Exception:  # noqa: BLE001
            self.inventory_overview_label.setText("No se pudo cargar la presentacion seleccionada.")
            self.inventory_product_label.setText("")
            self._set_badge_state(self.inventory_status_badge, "Error", "danger")
            self._set_badge_state(self.inventory_stock_badge, "Sin stock", "neutral")
            self.inventory_stock_hint_label.setText("")
            self.inventory_meta_label.setText("")
            self.inventory_last_movement_label.setText("")

    def _clear_catalog_editor(self) -> None:
        self.catalog_selection_label.setText("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label.setText(
            "Consulta uniformes y usa filtros macro como Deportivo, Oficial, Basico, Escolta o Accesorio."
        )
        self.toggle_product_button.setText("Prod.")
        self.toggle_variant_button.setText("Pres.")

    def _select_catalog_variant(self, variant_id: int) -> bool:
        for row_index, row in enumerate(self.catalog_rows):
            if int(row["variante_id"]) == variant_id:
                self.catalog_table.blockSignals(True)
                self.catalog_table.setCurrentCell(row_index, 0)
                self.catalog_table.selectRow(row_index)
                self.catalog_table.blockSignals(False)
                self._handle_catalog_selection()
                return True
        return False

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _populate_combo(combo: QComboBox, items: list[tuple[str, int]]) -> None:
        current_value = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, data in items:
            combo.addItem(label, data)
        if current_value is not None:
            index = combo.findData(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    @staticmethod
    def _populate_filter_combo(combo: QComboBox, default_label: str, items: list[tuple[str, int]]) -> None:
        current_value = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(default_label, "")
        for label, data in items:
            combo.addItem(label, data)
        if current_value not in {None, ""}:
            index = combo.findData(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    @staticmethod
    def _set_badge_state(label: QLabel, text: str, tone: str) -> None:
        label.setText(text)
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def _create_kpi_card(self, title: str, value_label: QLabel, subtitle: str) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("kpiTitle")
        value_label.setObjectName("kpiValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("kpiSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        card.setLayout(layout)
        return card

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3efe8;
                color: #1f1f1b;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #d7d0c4;
                border-radius: 18px;
                background: #fbf8f2;
                top: -1px;
                padding: 10px;
            }
            QTabBar::tab {
                background: transparent;
                color: #6d665e;
                padding: 10px 16px;
                margin-right: 6px;
                border-radius: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #a84f2d;
                color: #f7f1e8;
            }
            QTabBar::tab:hover:!selected {
                background: #e7ded0;
                color: #2d2b27;
            }
            #heroPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6f331d, stop:0.55 #a84f2d, stop:1 #c96a35);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            #heroTitle {
                color: #f9f4ea;
                font-size: 22px;
                font-weight: 800;
            }
            #heroSubtitle {
                color: #f4d5bf;
                font-size: 12px;
            }
            #heroInfoCard {
                background: rgba(249, 244, 234, 0.09);
                border: 1px solid rgba(249, 244, 234, 0.14);
                border-radius: 14px;
            }
            #heroPrimaryText {
                color: #f9f4ea;
                font-size: 16px;
                font-weight: 800;
                background: transparent;
                border: none;
                padding: 0;
            }
            #heroMetaText {
                color: #f6ddca;
                font-size: 11px;
                font-weight: 700;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 999px;
                padding: 5px 9px;
            }
            #statusLine, #subtleLine, #analyticsLine {
                background: #fffaf2;
                border: 1px solid #e1d8cb;
                border-radius: 12px;
                padding: 6px 10px;
            }
            #templatePreviewLabel {
                background: transparent;
                border: none;
                padding: 0;
                color: #4a433d;
                font-size: 12px;
                line-height: 1.35em;
            }
            #liveNameCaption {
                background: transparent;
                border: none;
                padding: 0;
                color: #7e3a22;
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            #liveNameValue {
                background: transparent;
                border: none;
                padding: 0;
                color: #4a362c;
                font-size: 22px;
                font-weight: 900;
                line-height: 1.15em;
            }
            #liveNameHint {
                background: transparent;
                border: none;
                padding: 0;
                color: #7a7067;
                font-size: 12px;
                font-weight: 600;
            }
            #chipButton {
                background: #efe7d9;
                color: #6b4b3a;
                border: 1px solid #ddcbb8;
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #chipButton:hover {
                background: #f8dfcf;
                border-color: #dfb496;
                color: #8f4527;
            }
            #chipButton[active="true"] {
                background: #a84f2d;
                color: #f9f4ea;
                border-color: #8a4326;
            }
            #stepButton {
                background: #efe7d9;
                color: #6e675f;
                border: 1px solid #ddd3c6;
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 800;
            }
            #stepButton[active="true"] {
                background: #a84f2d;
                color: #f7f1e8;
                border-color: #8a4326;
            }
            #stepButton:hover {
                background: #f8dfcf;
                color: #8f4527;
                border-color: #dfb496;
            }
            #analyticsLine {
                background: #efe7d9;
                color: #4a433d;
            }
            #cashierSummaryCard {
                background: #faeadf;
                color: #7e3a22;
                border: 1px solid #efccb8;
                border-radius: 14px;
                padding: 10px 12px;
                font-size: 15px;
                font-weight: 800;
            }
            #cashierWarningLine {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierFeedbackLabel {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierFeedbackLabel[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #cashierFeedbackLabel[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #cashierFeedbackLabel[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #cashierFeedbackLabel[tone="neutral"] {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            #cashierTotalsCard {
                background: #a84f2d;
                border: 1px solid #8a4326;
                border-radius: 16px;
            }
            #cashierTotalValue {
                background: transparent;
                color: #f9f4ea;
                border: none;
                padding: 0;
                font-size: 30px;
                font-weight: 900;
            }
            #cashierMetaLabel {
                background: transparent;
                color: #f1d7c5;
                border: none;
                padding: 0;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierChangeValue {
                background: #faeadf;
                color: #7e3a22;
                border: 1px solid #efccb8;
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 800;
            }
            #readOnlyField {
                background: #f2eee6;
                color: #564d45;
                border: 1px solid #ddd3c6;
                border-radius: 12px;
                padding: 9px 12px;
                font-weight: 700;
            }
            #settingsLaunchCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 18px;
            }
            QPushButton#settingsLaunchButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: none;
                border-radius: 14px;
                padding: 14px 16px;
                text-align: left;
                font-size: 15px;
                font-weight: 800;
            }
            QPushButton#settingsLaunchButton:hover {
                background: #bb613c;
            }
            #inventoryTitle {
                color: #7e3a22;
                font-size: 20px;
                font-weight: 800;
                background: transparent;
                border: none;
                padding: 0;
            }
            #inventorySubtitle {
                color: #6f665f;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
                padding: 0;
            }
            #inventoryStatusBadge {
                background: #f6decd;
                color: #7e3a22;
                border: 1px solid #e1b89d;
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            #inventoryStatusBadge[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #inventoryStatusBadge[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #inventoryStatusBadge[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #inventoryStatusBadge[tone="muted"], #inventoryStatusBadge[tone="neutral"] {
                background: #ece8e1;
                color: #6e675f;
                border: 1px solid #d7cec1;
            }
            #inventoryMetaCard, #inventoryMetaCardAlt {
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid #e4dacd;
                font-weight: 600;
            }
            #inventoryMetaCard {
                background: #faeadf;
                color: #8a4326;
                border: 1px solid #efccb8;
            }
            #inventoryMetaCardAlt {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            #inventoryQrCaption {
                color: #6f665f;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0 4px 2px 4px;
            }
            #inventoryCounterChip {
                background: #fae9dc;
                color: #92492a;
                border: 1px solid #ecc7ac;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #inventoryCounterChip[tone="positive"], #inventoryQrStatus[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #inventoryCounterChip[tone="warning"], #inventoryQrStatus[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #inventoryCounterChip[tone="danger"], #inventoryQrStatus[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #inventoryCounterChip[tone="muted"], #inventoryCounterChip[tone="neutral"],
            #inventoryQrStatus[tone="muted"], #inventoryQrStatus[tone="neutral"] {
                background: #ece8e1;
                color: #6e675f;
                border: 1px solid #d7cec1;
            }
            #inventoryQrStatus {
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #analyticsFlagCard {
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid #ecd5c5;
                background: #fbf3ec;
                color: #8c6656;
                font-size: 13px;
                font-weight: 800;
            }
            #analyticsFlagCard[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #analyticsFlagCard[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #analyticsFlagCard[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #analyticsFlagCard[tone="neutral"], #analyticsFlagCard[tone="muted"] {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            QGroupBox, #infoCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 18px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 6px;
                color: #51483f;
            }
            #kpiCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 20px;
            }
            #kpiTitle {
                color: #6b625a;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 700;
            }
            #kpiValue {
                color: #7a351d;
                font-size: 30px;
                font-weight: 800;
            }
            #kpiSubtitle {
                color: #857b70;
                font-size: 12px;
            }
            QPushButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
            }
            QPushButton#adminCompactButton {
                border-radius: 10px;
                padding: 7px 12px;
                min-height: 30px;
            }
            QPushButton#inventoryActionButton {
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QToolButton#inventoryMenuButton, QToolButton#inventoryMenuSecondaryButton {
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 30px;
                font-size: 13px;
                font-weight: 800;
                text-align: left;
            }
            QToolButton#inventoryMenuButton {
                background: #a84f2d;
                color: #f7f1e8;
                border: 1px solid #8a4326;
            }
            QToolButton#inventoryMenuButton:hover {
                background: #bb613c;
            }
            QToolButton#inventoryMenuSecondaryButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
            }
            QToolButton#inventoryMenuSecondaryButton:hover {
                background: #e6dccd;
            }
            QToolButton#inventoryMenuButton::menu-indicator, QToolButton#inventoryMenuSecondaryButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 8px;
            }
            QPushButton#inventoryDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton#inventoryDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#cashierDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 30px;
            }
            QPushButton#cashierDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#inventorySecondaryButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton#inventorySecondaryButton:hover {
                background: #e6dccd;
            }
            QPushButton#iconButton {
                border-radius: 10px;
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                font-size: 18px;
            }
            QPushButton#toolbarSecondaryButton, QPushButton#toolbarGhostButton, QPushButton#toolbarPrimaryButton,
            QPushButton#toolbarSoftButton, QPushButton#toolbarActionButton, QPushButton#toolbarDangerButton,
            QPushButton#toolbarAccentButton, QToolButton#toolbarSecondaryButton, QToolButton#toolbarGhostButton,
            QToolButton#toolbarSoftButton, QToolButton#toolbarActionButton, QToolButton#toolbarDangerButton,
            QToolButton#toolbarAccentButton {
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 34px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #bb613c;
            }
            QPushButton:pressed {
                background: #6f331d;
            }
            QPushButton:disabled {
                background: #c8c0b6;
                color: #f7f1e8;
            }
            QPushButton#primaryButton {
                background: #a84f2d;
            }
            QPushButton#primaryButton:hover {
                background: #bb613c;
            }
            QPushButton#ghostButton, QPushButton#secondaryButton, QPushButton#toolbarSecondaryButton, QPushButton#toolbarGhostButton,
            QToolButton#toolbarSecondaryButton, QToolButton#toolbarGhostButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
            }
            QPushButton#ghostButton:hover, QPushButton#secondaryButton:hover, QPushButton#toolbarSecondaryButton:hover, QPushButton#toolbarGhostButton:hover,
            QToolButton#toolbarSecondaryButton:hover, QToolButton#toolbarGhostButton:hover {
                background: #e6dccd;
            }
            QPushButton#toolbarPrimaryButton, QToolButton#toolbarPrimaryButton {
                background: #a84f2d;
            }
            QPushButton#toolbarPrimaryButton:hover, QToolButton#toolbarPrimaryButton:hover {
                background: #bb613c;
            }
            QPushButton#toolbarSoftButton, QToolButton#toolbarSoftButton {
                background: #fae9dc;
                color: #a84f2d;
                border: 1px solid #ecc7ac;
            }
            QPushButton#toolbarSoftButton:hover, QToolButton#toolbarSoftButton:hover {
                background: #f8dfcf;
            }
            QPushButton#toolbarActionButton, QToolButton#toolbarActionButton {
                background: #a84f2d;
                color: #f7f1e8;
                border: 1px solid #8a4326;
            }
            QPushButton#toolbarActionButton:hover, QToolButton#toolbarActionButton:hover {
                background: #bb613c;
            }
            QPushButton#toolbarDangerButton, QToolButton#toolbarDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
            }
            QPushButton#toolbarDangerButton:hover, QToolButton#toolbarDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#toolbarAccentButton, QToolButton#toolbarAccentButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: 1px solid #944226;
            }
            QPushButton#toolbarAccentButton:hover, QToolButton#toolbarAccentButton:hover {
                background: #bb613c;
            }
            QToolButton#toolbarSoftButton::menu-indicator, QToolButton#toolbarActionButton::menu-indicator,
            QToolButton#toolbarSecondaryButton::menu-indicator, QToolButton#toolbarGhostButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 8px;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background: #fffdf8;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 8px 12px;
                min-height: 34px;
                selection-background-color: #a84f2d;
            }
            QLineEdit#inventoryFilterInput, QComboBox#inventoryFilterCombo {
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
            }
            QLabel#inventoryFilterLabel {
                color: #5f564d;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
                border: none;
                padding: 0 2px;
            }
            QComboBox#inventoryFilterCombo:hover, QLineEdit#inventoryFilterInput:hover {
                background: #f9efe7;
                border: 1px solid #dfb496;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
                border: 2px solid #c96a35;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                width: 22px;
            }
            QComboBox QAbstractItemView {
                background: #fffdf8;
                color: #1f1f1b;
                border: 1px solid #d8cfc3;
                selection-background-color: #f8dfcf;
                selection-color: #8f4527;
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 6px 10px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #fae9dc;
                color: #8f4527;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #f4d4bb;
                color: #73341c;
                font-weight: 700;
            }
            QComboBox QAbstractItemView::item:selected:hover {
                background: #efc39f;
                color: #6a2f1a;
            }
            #dataTable {
                background: #fffdf8;
                alternate-background-color: #f5efe6;
                gridline-color: #e2d9cc;
                border: 1px solid #ddd3c6;
                border-radius: 16px;
                selection-background-color: #efccb5;
                selection-color: #5a2816;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #efe7d9;
                color: #4a433d;
                border: none;
                border-right: 1px solid #ddd3c6;
                border-bottom: 1px solid #ddd3c6;
                padding: 8px 10px;
                font-weight: 700;
            }
            #qrPreview {
                border: 1px dashed #b7ad9e;
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #f6f1e8);
                color: #8a8075;
                max-width: 180px;
                max-height: 180px;
                padding: 10px;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(user_id=1)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
