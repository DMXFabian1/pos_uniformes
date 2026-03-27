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
import unicodedata
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, QMarginsF, QSizeF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QPageLayout, QPageSize, QPixmap, QShortcut
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import engine, get_session, test_connection
from pos_uniformes.database.models import (
    AtributoProducto,
    Apartado,
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
    NivelEducativo,
    Producto,
    Proveedor,
    RolUsuario,
    SesionCaja,
    TipoMovimientoCaja,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
    Venta,
)
from pos_uniformes.services.apartado_service import ApartadoService
from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_active_filters_summary,
)
from pos_uniformes.services.bootstrap_service import BootstrapService
from pos_uniformes.services.analytics_snapshot_service import (
    build_analytics_sales_snapshot,
    load_confirmed_sales_for_analytics,
)
from pos_uniformes.services.analytics_layaway_service import load_analytics_layaway_snapshot
from pos_uniformes.services.analytics_top_clients_service import load_analytics_top_client_snapshot_rows
from pos_uniformes.services.analytics_top_products_service import load_analytics_top_product_snapshot_rows
from pos_uniformes.services.analytics_stock_service import load_analytics_stock_snapshot_rows
from pos_uniformes.services.backup_service import (
    AutomaticBackupStatus,
    read_automatic_backup_status,
    backup_output_dir,
    format_size,
    list_backups,
)
from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
from pos_uniformes.services.business_settings_service import BusinessSettingsInput, BusinessSettingsService
from pos_uniformes.services.settings_business_action_service import (
    load_settings_business_form_snapshot,
    save_settings_business_payload,
)
from pos_uniformes.services.cash_session_action_service import (
    close_cash_session_action,
    correct_cash_opening_action,
    load_cash_cut_prompt_snapshot,
    load_cash_movement_target_snapshot,
    load_cash_opening_amount,
    load_cash_opening_suggested_amount,
    load_cash_session_gate_snapshot,
    open_cash_session_action,
    register_cash_movement_action,
)
from pos_uniformes.services.caja_service import CajaService
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.services.catalog_mutation_service import (
    delete_catalog_product,
    delete_catalog_variant,
    toggle_catalog_product_state,
    toggle_catalog_variant_state,
)
from pos_uniformes.services.compra_service import CompraItemInput, CompraService
from pos_uniformes.services.customer_card_service import CustomerCardRenderInput, CustomerCardService
from pos_uniformes.services.history_snapshot_service import (
    HistorySnapshotFilters,
    load_history_snapshot_rows,
)
from pos_uniformes.services.inventario_service import (
    AjusteMasivoFilaInput,
    InventarioService,
)
from pos_uniformes.services.layaway_snapshot_service import (
    build_layaway_history_input_rows,
    load_layaway_snapshot_rows,
)
from pos_uniformes.services.inventory_label_service import (
    load_inventory_label_context,
    render_inventory_label,
)
from pos_uniformes.services.inventory_overview_service import load_inventory_overview_snapshot
from pos_uniformes.services.inventory_snapshot_service import (
    invalidate_inventory_qr_exists_cache,
    load_inventory_snapshot_rows,
)
from pos_uniformes.services.manual_promo_service import ManualPromoService
from pos_uniformes.services.presupuesto_service import PresupuestoItemInput, PresupuestoService
from pos_uniformes.services.quote_snapshot_service import (
    build_quote_history_input_rows,
    load_quote_snapshot_rows,
)
from pos_uniformes.services.quote_detail_service import load_quote_detail_snapshot
from pos_uniformes.services.quote_action_service import cancel_quote
from pos_uniformes.services.quote_whatsapp_service import build_quote_whatsapp_view
from pos_uniformes.services.layaway_alerts_service import load_layaway_alerts_snapshot
from pos_uniformes.services.layaway_closure_service import (
    cancel_layaway,
    deliver_layaway,
    load_layaway_delivery_confirmation,
    settle_and_deliver_layaway,
)
from pos_uniformes.services.layaway_creation_service import create_layaway_from_payload
from pos_uniformes.services.layaway_detail_service import load_layaway_detail_snapshot
from pos_uniformes.services.layaway_payment_action_service import register_layaway_payment
from pos_uniformes.services.sale_loyalty_notice_service import build_sale_loyalty_transition_notice
from pos_uniformes.services.sale_payment_context_service import build_sale_payment_note_context
from pos_uniformes.services.sale_checkout_action_service import complete_sale_checkout
from pos_uniformes.services.sale_discount_context_service import (
    build_sale_discount_context,
    build_sale_manual_promo_snapshot,
    calculate_sale_discount_pricing,
    calculate_sale_discount_totals,
    clear_sale_manual_promo_snapshot,
    load_sale_discount_presets,
    resolve_sale_client_discount_ui_state,
    resolve_sale_manual_discount_transition,
    verify_sale_manual_promo_code,
)
from pos_uniformes.services.sale_discount_option_service import (
    build_sale_discount_options,
    expected_discount_option_label,
)
from pos_uniformes.services.sale_document_view_service import (
    build_layaway_receipt_document_view,
    build_layaway_sale_ticket_document_view,
    build_sale_ticket_document_view,
)
from pos_uniformes.services.sale_cart_update_service import update_sale_cart_item_quantity
from pos_uniformes.services.sale_selected_client_service import (
    find_active_sale_client_by_code,
    load_sale_selected_client_discount_percent,
)
from pos_uniformes.services.sale_discount_service import (
    format_discount_label,
    normalize_discount_value,
)
from pos_uniformes.services.recent_sale_service import list_recent_sale_rows
from pos_uniformes.services.recent_sale_action_service import cancel_recent_sale
from pos_uniformes.services.search_filter_service import (
    CATALOG_SEARCH_ALIAS_MAP,
    CATALOG_SEARCH_GENERAL_FIELDS,
    INVENTORY_SEARCH_ALIAS_MAP,
    INVENTORY_SEARCH_GENERAL_FIELDS,
    compile_search_terms,
    row_matches_search,
)
from pos_uniformes.services.settings_backup_action_service import (
    create_settings_backup,
    open_settings_backup_folder,
    restore_settings_backup,
)
from pos_uniformes.services.settings_client_action_service import (
    create_settings_client,
    generate_settings_client_qr,
    load_settings_client_prompt_snapshot,
    toggle_settings_client,
    update_settings_client,
)
from pos_uniformes.services.settings_marketing_action_service import (
    load_settings_marketing_history_rows,
    recalculate_settings_loyalty_levels,
)
from pos_uniformes.services.settings_supplier_action_service import (
    create_settings_supplier,
    load_settings_supplier_prompt_snapshot,
    toggle_settings_supplier,
    update_settings_supplier,
)
from pos_uniformes.services.settings_whatsapp_template_service import (
    build_default_settings_whatsapp_templates,
    build_settings_whatsapp_template_map,
    render_settings_whatsapp_template,
    resolve_settings_whatsapp_templates,
)
from pos_uniformes.services.settings_user_action_service import (
    change_settings_user_password,
    change_settings_user_role,
    create_settings_user,
    load_settings_user_prompt_snapshot,
    toggle_settings_user,
    update_settings_user,
)
from pos_uniformes.services.supplier_service import SupplierService
from pos_uniformes.services.user_service import UserService
from pos_uniformes.services.venta_service import VentaService
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
from pos_uniformes.ui.dialogs.settings_prompt_dialogs import (
    prompt_client_data,
    prompt_client_whatsapp_data,
    prompt_create_user_data,
    prompt_edit_user_data,
    prompt_password_change,
    prompt_role_change,
    prompt_supplier_data,
)
from pos_uniformes.ui.dialogs.catalog_product_dialog import build_catalog_product_dialog
from pos_uniformes.ui.dialogs.catalog_variant_dialog import (
    build_catalog_batch_variant_dialog,
    build_catalog_variant_dialog,
)
from pos_uniformes.ui.dialogs.layaway_payment_dialog import build_layaway_payment_dialog
from pos_uniformes.ui.dialogs.create_layaway_dialog import build_create_layaway_dialog
from pos_uniformes.ui.dialogs.inventory_context_menu_dialog import prompt_inventory_context_action
from pos_uniformes.ui.dialogs.inventory_count_dialog import prompt_inventory_count_data
from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
from pos_uniformes.ui.dialogs.marketing_history_dialog import build_marketing_history_dialog
from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog
from pos_uniformes.ui.dialogs.cash_session_prompt_dialogs import (
    CashCutSummaryView,
    prompt_cash_cut_data,
    prompt_cash_movement_data,
    prompt_cash_opening_correction,
    prompt_open_cash_session,
)
from pos_uniformes.ui.helpers.catalog_access_helper import build_catalog_access_view
from pos_uniformes.ui.helpers.catalog_action_guard_helper import build_catalog_action_guard_feedback
from pos_uniformes.ui.helpers.catalog_action_feedback_helper import (
    build_catalog_delete_confirmation,
    build_catalog_error_title,
    build_catalog_success_result,
)
from pos_uniformes.ui.helpers.catalog_filter_helper import (
    CatalogVisibleFilterState,
    filter_visible_catalog_rows,
)
from pos_uniformes.ui.helpers.catalog_pagination_helper import build_catalog_pagination_view
from pos_uniformes.ui.helpers.catalog_macro_filter_helper import (
    build_catalog_uniform_macro_button_states,
    resolve_catalog_uniform_macro_selection,
)
from pos_uniformes.ui.helpers.catalog_form_payload_helper import (
    validate_catalog_product_submission,
    validate_catalog_variant_submission,
)
from pos_uniformes.ui.helpers.analytics_payment_helper import build_analytics_payment_rows
from pos_uniformes.ui.helpers.analytics_layaway_helper import build_analytics_layaway_labels_view
from pos_uniformes.ui.helpers.analytics_export_helper import (
    build_analytics_layaway_export_rows,
    build_analytics_summary_export_rows,
    build_table_export_rows,
)
from pos_uniformes.ui.helpers.analytics_period_helper import (
    build_analytics_export_status_text,
    is_manual_analytics_period,
    resolve_analytics_period_bounds,
    resolve_previous_analytics_period_bounds,
)
from pos_uniformes.ui.helpers.analytics_summary_helper import (
    build_analytics_alerts_text,
    build_analytics_operational_alerts,
    build_analytics_summary_trend_view,
)
from pos_uniformes.ui.helpers.dashboard_summary_helper import (
    build_dashboard_future_alerts_view,
    build_dashboard_kpi_cards_view,
    build_dashboard_operational_alerts_view,
    build_dashboard_operations_view,
    build_dashboard_status_view,
)
from pos_uniformes.ui.helpers.analytics_top_clients_helper import build_analytics_top_client_row_views
from pos_uniformes.ui.helpers.analytics_top_products_helper import build_analytics_top_product_rows
from pos_uniformes.ui.helpers.analytics_stock_helper import build_analytics_stock_row_views
from pos_uniformes.ui.helpers.catalog_refresh_helper import (
    build_catalog_table_values,
)
from pos_uniformes.ui.helpers.catalog_table_row_helper import build_catalog_table_row_views
from pos_uniformes.ui.helpers.history_filter_helper import build_history_type_options
from pos_uniformes.ui.helpers.history_filter_state_helper import (
    build_history_clear_filter_state,
    build_history_current_month_filter_dates,
    build_history_filter_state,
    build_history_last_days_filter_dates,
    build_history_today_filter_dates,
    build_history_type_options_state,
)
from pos_uniformes.ui.helpers.history_detail_helper import build_history_detail_view
from pos_uniformes.ui.helpers.history_export_helper import (
    build_history_export_dir_name,
    build_history_export_rows,
)
from pos_uniformes.ui.helpers.history_summary_helper import build_history_summary_view
from pos_uniformes.ui.helpers.history_table_helper import build_history_table_rows
from pos_uniformes.ui.helpers.catalog_selection_helper import (
    build_catalog_selection_view_from_row,
    build_empty_catalog_selection_view,
    find_catalog_row_index_by_variant_id,
    resolve_catalog_row,
)
from pos_uniformes.ui.helpers.catalog_summary_helper import build_catalog_summary_view
from pos_uniformes.ui.helpers.cash_session_feedback_helper import (
    build_cash_close_success_feedback,
    build_cash_movement_success_feedback,
    build_cash_opening_correction_success_feedback,
    build_cash_session_gate_feedback,
)
from pos_uniformes.ui.helpers.inventory_context_menu_helper import build_inventory_context_menu_actions
from pos_uniformes.ui.helpers.inventory_filter_helper import (
    InventoryVisibleFilterState,
    filter_visible_inventory_rows,
)
from pos_uniformes.ui.helpers.inventory_overview_helper import (
    build_empty_inventory_overview_view,
    build_error_inventory_overview_view,
    build_inventory_overview_view,
)
from pos_uniformes.ui.helpers.inventory_qr_preview_helper import (
    InventoryQrPreviewView,
    build_available_inventory_qr_preview_view,
    build_empty_inventory_qr_preview_view,
    build_error_inventory_qr_preview_view,
    build_pending_inventory_qr_preview_view,
)
from pos_uniformes.ui.helpers.inventory_selection_helper import (
    collect_selected_inventory_variant_ids,
    find_catalog_row_by_variant_id,
    find_inventory_row_index_by_variant_id,
    normalize_inventory_variant_id,
)
from pos_uniformes.ui.helpers.inventory_summary_helper import build_inventory_summary_view
from pos_uniformes.ui.helpers.inventory_table_row_helper import build_inventory_table_row_views
from pos_uniformes.ui.helpers.layaway_action_helper import build_layaway_action_state
from pos_uniformes.ui.helpers.layaway_alerts_helper import build_layaway_alerts_view
from pos_uniformes.ui.helpers.layaway_detail_helper import (
    build_empty_layaway_detail_view,
    build_error_layaway_detail_view,
    build_layaway_detail_view,
)
from pos_uniformes.ui.helpers.layaway_delivery_feedback_helper import (
    build_layaway_delivery_confirmation_view,
    build_layaway_delivery_result_view,
)
from pos_uniformes.ui.helpers.layaway_history_helper import build_layaway_history_rows
from pos_uniformes.ui.helpers.layaway_summary_helper import build_layaway_summary_view
from pos_uniformes.ui.helpers.layaway_table_row_helper import build_layaway_table_row_views
from pos_uniformes.ui.helpers.recent_sale_table_helper import build_recent_sale_table_row_views
from pos_uniformes.ui.helpers.recent_sale_selection_helper import (
    build_recent_sale_action_state,
    resolve_selected_recent_sale_id,
)
from pos_uniformes.ui.helpers.recent_sale_feedback_helper import (
    build_recent_sale_guard_feedback,
    build_recent_sale_permission_label,
)
from pos_uniformes.ui.helpers.quote_cart_view_helper import build_quote_cart_view
from pos_uniformes.ui.helpers.quote_history_helper import build_quote_history_rows
from pos_uniformes.ui.helpers.quote_detail_helper import (
    build_empty_quote_detail_view,
    build_error_quote_detail_view,
    build_quote_detail_view,
)
from pos_uniformes.ui.helpers.quote_feedback_helper import (
    build_quote_guard_feedback,
    build_quote_result_feedback,
)
from pos_uniformes.ui.helpers.quote_selection_helper import (
    build_quote_action_state,
    resolve_selected_quote_id,
)
from pos_uniformes.ui.helpers.quote_summary_helper import build_quote_summary_view
from pos_uniformes.ui.helpers.quote_table_row_helper import build_quote_table_row_views
from pos_uniformes.ui.helpers.printable_document_flow_helper import open_printable_document_flow
from pos_uniformes.ui.helpers.sale_client_selection_helper import (
    build_empty_sale_client_selection_ui_state,
)
from pos_uniformes.ui.helpers.sale_cashier_panel_helper import build_sale_cashier_panel_view
from pos_uniformes.ui.helpers.sale_checkout_feedback_helper import (
    build_sale_checkout_error_message,
)
from pos_uniformes.ui.helpers.sale_post_action_feedback_helper import (
    SalePostActionView,
    build_sale_cancel_post_action_view,
    build_sale_checkout_post_action_view,
)
from pos_uniformes.ui.helpers.sale_payment_helper import collect_sale_payment_details
from pos_uniformes.ui.helpers.sale_scanned_client_helper import build_sale_scanned_client_ui_state
from pos_uniformes.ui.helpers.size_option_sort_helper import sort_size_options
from pos_uniformes.ui.helpers.snapshot_cache_helper import SnapshotCache
from pos_uniformes.ui.helpers.settings_backup_helper import (
    build_settings_backup_error_view,
    build_settings_backup_view,
)
from pos_uniformes.ui.helpers.settings_backup_feedback_helper import (
    build_settings_backup_guard_feedback,
    build_settings_backup_restore_confirmation,
    build_settings_backup_result_feedback,
)
from pos_uniformes.ui.helpers.settings_business_feedback_helper import (
    build_settings_business_guard_feedback,
    build_settings_business_result_feedback,
)
from pos_uniformes.ui.helpers.settings_backup_selection_helper import (
    resolve_selected_settings_backup_path,
)
from pos_uniformes.ui.helpers.settings_crm_feedback_helper import (
    build_settings_client_guard_feedback,
    build_settings_client_result_feedback,
    build_settings_marketing_guard_feedback,
    build_settings_marketing_result_feedback,
    build_settings_supplier_guard_feedback,
    build_settings_supplier_result_feedback,
)
from pos_uniformes.ui.helpers.settings_crm_selection_helper import (
    resolve_selected_settings_client_id,
    resolve_selected_settings_supplier_id,
)
from pos_uniformes.ui.helpers.settings_cash_history_helper import (
    build_settings_cash_history_rows,
)
from pos_uniformes.ui.helpers.settings_cash_history_detail_helper import (
    build_settings_cash_history_detail_view,
)
from pos_uniformes.ui.helpers.settings_cash_history_movements_helper import (
    build_settings_cash_history_movements_view,
)
from pos_uniformes.ui.helpers.settings_cash_history_summary_helper import (
    build_settings_cash_history_status_label,
)
from pos_uniformes.ui.helpers.settings_clients_helper import (
    build_settings_clients_error_view,
    build_settings_clients_view,
)
from pos_uniformes.ui.helpers.settings_marketing_helper import (
    build_settings_marketing_summary_label,
)
from pos_uniformes.ui.helpers.settings_suppliers_helper import (
    build_settings_suppliers_error_view,
    build_settings_suppliers_view,
)
from pos_uniformes.ui.helpers.settings_users_helper import (
    build_settings_users_error_view,
    build_settings_users_view,
)
from pos_uniformes.ui.helpers.settings_user_feedback_helper import (
    build_settings_user_guard_feedback,
    build_settings_user_result_feedback,
)
from pos_uniformes.ui.helpers.settings_user_selection_helper import (
    resolve_selected_settings_user_id,
)
from pos_uniformes.ui.helpers.settings_whatsapp_preview_helper import (
    build_settings_whatsapp_preview_text,
)
from pos_uniformes.ui.helpers.qt_image_scale_helper import (
    build_centered_paint_rect,
    normalize_scaled_target_size,
    normalize_printable_image,
)
from pos_uniformes.ui.helpers.inventory_label_print_helper import build_inventory_label_print_layout
from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import print_inventory_label_via_windows
from pos_uniformes.ui.views.analytics_view import build_analytics_tab
from pos_uniformes.ui.views.cashier_view import build_cashier_tab
from pos_uniformes.ui.views.dashboard_view import build_dashboard_tab
from pos_uniformes.ui.views.history_view import build_history_tab
from pos_uniformes.ui.views.inventory_view import build_inventory_tab
from pos_uniformes.ui.views.layaway_view import build_layaway_tab
from pos_uniformes.ui.views.products_view import build_products_tab
from pos_uniformes.ui.views.quotes_view import build_quotes_tab
from pos_uniformes.ui.views.settings_view import build_settings_tab
from pos_uniformes.ui.styles.main_window_styles import build_main_window_stylesheet
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name
from pos_uniformes.utils.qr_generator import QrGenerator

LISTING_SEARCH_DEBOUNCE_MS = 300
CATALOG_PAGE_SIZE = 25
INVENTORY_PAGE_SIZE = 25


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _normalize_filter_value(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


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
        selected_values = {_normalize_filter_value(value) for value in self.selected_values()}
        self._updating = True
        self._menu.clear()
        for label, data in items:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(str(data))
            action.setChecked(_normalize_filter_value(data) in selected_values)
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
        normalized = {
            _normalize_filter_value(value)
            for value in values
            if str(value).strip()
        }
        self._updating = True
        for action in self._menu.actions():
            if action.isCheckable():
                action.setChecked(_normalize_filter_value(action.data()) in normalized)
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


def _set_table_row_tint(item: QTableWidgetItem, tone: str) -> None:
    palette = {
        "danger": ("#fff1ec", "#7a2b1d"),
        "warning": ("#fff8e7", "#7a5a14"),
        "muted": ("#f3f0ea", "#6e675f"),
        "neutral": ("#f7f3ee", "#645d56"),
        "reserved": ("#fff3ea", "#8a4d22"),
    }
    background, foreground = palette.get(tone, palette["neutral"])
    item.setBackground(QColor(background))
    item.setForeground(QColor(foreground))

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
        self.catalog_filtered_rows: list[dict[str, object]] = []
        self.catalog_page_index = 0
        self.catalog_preserve_selection_on_refresh = True
        self.inventory_rows: list[dict[str, object]] = []
        self.inventory_filtered_rows: list[dict[str, object]] = []
        self.inventory_page_index = 0
        self.catalog_snapshot_cache: SnapshotCache[list[dict[str, object]]] = SnapshotCache()
        self.inventory_snapshot_cache: SnapshotCache[list[dict[str, object]]] = SnapshotCache()
        self.catalog_filter_debounce_timer = QTimer(self)
        self.catalog_filter_debounce_timer.setSingleShot(True)
        self.catalog_filter_debounce_timer.setInterval(LISTING_SEARCH_DEBOUNCE_MS)
        self.catalog_filter_debounce_timer.timeout.connect(lambda: self._run_catalog_filter_refresh())
        self.inventory_filter_debounce_timer = QTimer(self)
        self.inventory_filter_debounce_timer.setSingleShot(True)
        self.inventory_filter_debounce_timer.setInterval(LISTING_SEARCH_DEBOUNCE_MS)
        self.inventory_filter_debounce_timer.timeout.connect(lambda: self._run_inventory_filter_refresh())
        self.sale_cart: list[dict[str, object]] = []
        self.layaway_rows: list[dict[str, object]] = []
        self.history_rows: list[dict[str, object]] = []
        self.quote_cart: list[dict[str, object]] = []
        self.quote_rows: list[dict[str, object]] = []
        self.selected_quote_state = ""
        self.selected_quote_phone = ""

        self.setWindowTitle("POS Uniformes")
        self.resize(1320, 860)

        self.session_label = QLabel()
        self.status_label = QLabel()
        self.metrics_label = QLabel()
        self.analytics_label = QLabel()
        self.dashboard_operations_label = QLabel()
        self.dashboard_future_alerts_label = QLabel()
        self.layaway_alerts_label = QLabel()
        self.cash_session_label = QLabel()
        self.kpi_users_value = QLabel("0")
        self.kpi_products_value = QLabel("0")
        self.kpi_stock_value = QLabel("0")
        self.kpi_sales_value = QLabel("0")
        self.dashboard_users_context_label = QLabel("")
        self.dashboard_products_context_label = QLabel("")
        self.dashboard_stock_context_label = QLabel("")
        self.dashboard_sales_context_label = QLabel("")
        self.dashboard_operational_alerts_label = QLabel("")
        self.analytics_period_combo = QComboBox()
        self.analytics_client_combo = QComboBox()
        self.analytics_from_input = QDateEdit()
        self.analytics_to_input = QDateEdit()
        self.analytics_export_button = QPushButton("Exportar CSV/JSON")
        self.analytics_export_status_label = QLabel()
        self.analytics_alerts_label = QLabel("Sin alertas operativas relevantes en este momento.")
        self.analytics_sales_value = QLabel("$0.00")
        self.analytics_sales_context_label = QLabel("")
        self.analytics_tickets_value = QLabel("0")
        self.analytics_tickets_context_label = QLabel("")
        self.analytics_average_value = QLabel("$0.00")
        self.analytics_average_context_label = QLabel("")
        self.analytics_units_value = QLabel("0")
        self.analytics_units_context_label = QLabel("")
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
        self.dashboard_products_card: QFrame | None = None
        self.dashboard_stock_card: QFrame | None = None
        self.dashboard_sales_card: QFrame | None = None
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
        self.catalog_pagination_label = QLabel()
        self.catalog_selection_label = QLabel("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label = QLabel(build_empty_catalog_selection_view().selection_label)
        self.catalog_search_input = QLineEdit()
        self.catalog_category_filter_combo = MultiSelectFilterButton("Categoria: todas")
        self.catalog_brand_filter_combo = MultiSelectFilterButton("Marca: todas")
        self.catalog_school_filter_combo = MultiSelectFilterButton("Escuela: todas")
        self.catalog_type_filter_combo = MultiSelectFilterButton("Linea: todas")
        self.catalog_piece_filter_combo = MultiSelectFilterButton("Pieza: todas")
        self.catalog_size_filter_combo = MultiSelectFilterButton("Talla: todas")
        self.catalog_color_filter_combo = MultiSelectFilterButton("Color: todos")
        self.catalog_uniform_macro_buttons: dict[str, QPushButton] = {}
        self.catalog_school_scope_filter_combo = QComboBox()
        self.catalog_status_filter_combo = QComboBox()
        self.catalog_stock_filter_combo = QComboBox()
        self.catalog_layaway_filter_combo = QComboBox()
        self.catalog_origin_filter_combo = QComboBox()
        self.catalog_duplicate_filter_combo = QComboBox()
        self.catalog_clear_filters_button = QPushButton("Limpiar filtros")
        self.catalog_previous_page_button = QPushButton("Anterior")
        self.catalog_next_page_button = QPushButton("Siguiente")
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
        self.sale_client_display_label = QLabel("Mostrador / sin cliente")
        self.sale_payment_combo = QComboBox()
        self.sale_discount_combo = QComboBox()
        self.sale_add_button = QPushButton("Agregar al carrito")
        self.sale_button = QPushButton("Confirmar venta")
        self.sale_layaway_button = QPushButton("Convertir a apartado")
        self.sale_recent_button = QPushButton("Ventas recientes")
        self.sale_ticket_button = QPushButton("Ver ticket")
        self.cancel_button = QPushButton("Cancelar venta seleccionada")
        self.cancel_permission_label = QLabel()
        self.sale_cart_table = QTableWidget()
        self.sale_qty_down_button = QPushButton("-1")
        self.sale_qty_up_button = QPushButton("+1")
        self.sale_remove_button = QPushButton("Quitar linea")
        self.sale_clear_button = QPushButton("Vaciar carrito")
        self.sale_summary_label = QLabel("Carrito vacio.")
        self.sale_context_label = QLabel("Cliente: Mostrador / sin cliente | Pago: Efectivo | Descuento: Sin descuento")
        self.sale_total_label = QLabel("$0.00")
        self.sale_total_meta_label = QLabel("Total a cobrar")
        self.sale_status_label = QLabel("Escanea un SKU para empezar a vender.")
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
        self.quote_qty_down_button = QPushButton("-1")
        self.quote_qty_up_button = QPushButton("+1")
        self.quote_remove_button = QPushButton("Quitar linea")
        self.quote_clear_button = QPushButton("Vaciar presupuesto")
        self.quote_cancel_button = QPushButton("Cancelar presupuesto")
        self.quote_whatsapp_button = QPushButton("WhatsApp")
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
        self.inventory_pagination_label = QLabel()
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
        self.inventory_previous_page_button = QPushButton("Anterior")
        self.inventory_next_page_button = QPushButton("Siguiente")
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
        self.layaway_breakdown_label = QLabel("")
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
        self.history_last_7_button = QPushButton("7 dias")
        self.history_last_30_button = QPushButton("30 dias")
        self.history_month_button = QPushButton("Mes actual")
        self.history_clear_button = QPushButton("Limpiar")
        self.history_filter_button = QPushButton("Aplicar filtros")
        self.history_export_button = QPushButton("Exportar")
        self.history_status_label = QLabel("Sin movimientos cargados.")
        self.history_search_hint_label = QLabel("")
        self.history_detail_summary_label = QLabel("Selecciona un movimiento para ver el detalle.")
        self.history_detail_meta_label = QLabel("Sin movimiento seleccionado.")
        self.history_detail_change_label = QLabel("Cambio y resultado visibles aqui cuando elijas una fila.")
        self.history_detail_notes_label = QLabel("El detalle extendido aparecera aqui para revisar la trazabilidad.")

        self.settings_backup_format_combo = QComboBox()
        self.settings_backup_table = QTableWidget()
        self.settings_backup_status_label = QLabel("Sin respaldos cargados.")
        self.settings_backup_automatic_status_label = QLabel("Automatico: sin informacion todavia.")
        self.settings_backup_automatic_detail_label = QLabel("")
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
        self.quick_backup_action: QAction | None = None
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
        self.quick_backup_action = header_menu.addAction("Respaldo rapido (.dump)")
        self.quick_backup_action.triggered.connect(self._handle_quick_backup)
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
            self.quote_save_button: "Emite el presupuesto rapido actual con folio, cliente opcional y vigencia.",
            self.quote_qty_down_button: "Reduce una pieza de la linea seleccionada del presupuesto.",
            self.quote_qty_up_button: "Aumenta una pieza de la linea seleccionada del presupuesto.",
            self.quote_remove_button: "Quita la linea seleccionada del presupuesto en armado.",
            self.quote_clear_button: "Vacía por completo el presupuesto actual.",
            self.quote_whatsapp_button: "Abre WhatsApp con un mensaje prellenado para el cliente del presupuesto seleccionado.",
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
            self.quick_backup_action: "Genera un respaldo rapido restaurable (.dump) sin abrir Configuracion.",
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
            "Busca por producto, color, talla, marca, escuela o SKU. Si quieres mas precision, tambien acepta prefijos como sku:, producto: o color:."
        )
        self.catalog_school_scope_filter_combo.setToolTip(
            "Separa el catalogo entre uniforme escolar y ropa normal segun la categoria real del producto."
        )
        self.catalog_clear_filters_button.setToolTip("Limpia todos los filtros del catalogo y muestra nuevamente todo el catalogo.")
        self.inventory_search_input.setToolTip(
            "Busca por producto, color, talla, marca, escuela o SKU. Si quieres mas precision, tambien acepta prefijos como sku:, producto: o color:."
        )
        self.inventory_clear_filters_button.setToolTip("Limpia todos los filtros del inventario y muestra nuevamente todas las presentaciones.")
        self.inventory_table.setToolTip("Selecciona una presentacion para gestionar inventario, precio, QR o estado.")
        self.layaway_table.setToolTip("Consulta apartados, saldo pendiente y fechas de vencimiento.")
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
        quick_backup_shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), self)
        quick_backup_shortcut.activated.connect(self._handle_quick_backup)
        quick_backup_shortcut_mac = QShortcut(QKeySequence("Meta+Shift+B"), self)
        quick_backup_shortcut_mac.activated.connect(self._handle_quick_backup)

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
        automatic_status = None
        try:
            automatic = read_automatic_backup_status(backup_dir)
        except Exception as exc:  # noqa: BLE001
            automatic = None
            automatic_status = {
                "last_run_at": None,
                "last_success_at": None,
                "backup_name": None,
                "retention_days": None,
                "last_error": f"Estado automatico invalido: {exc}",
            }
        else:
            if automatic is not None:
                automatic_status = {
                    "last_run_at": automatic.last_run_at,
                    "last_success_at": automatic.last_success_at,
                    "backup_name": automatic.last_backup_path.name if automatic.last_backup_path else None,
                    "retention_days": automatic.retention_days,
                    "last_error": automatic.last_error,
                }
        try:
            backups = list_backups(backup_dir)
        except Exception as exc:  # noqa: BLE001
            backup_view = build_settings_backup_error_view(
                backup_dir=str(backup_dir),
                error_message=str(exc),
                automatic_status=automatic_status,
            )
            self.settings_backup_location_label.setText(backup_view.location_label)
            self.settings_backup_status_label.setText(backup_view.status_label)
            self.settings_backup_automatic_status_label.setText(backup_view.automatic_status_label)
            self.settings_backup_automatic_detail_label.setText(backup_view.automatic_detail_label)
            self.settings_backup_table.setRowCount(len(backup_view.rows))
            return

        backup_view = build_settings_backup_view(
            backup_dir=str(backup_dir),
            backups=[
                {
                    "path_value": str(backup.path),
                    "name": backup.path.name,
                    "format_label": "Dump" if backup.dump_format == "custom" else "SQL",
                    "modified_label": format_display_datetime(backup.modified_at),
                    "size_label": format_size(backup.size_bytes),
                    "restorable_label": "Si" if backup.dump_format == "custom" else "No",
                }
                for backup in backups
            ],
            automatic_status=automatic_status,
        )
        self.settings_backup_location_label.setText(backup_view.location_label)
        self.settings_backup_automatic_status_label.setText(backup_view.automatic_status_label)
        self.settings_backup_automatic_detail_label.setText(backup_view.automatic_detail_label)
        self.settings_backup_table.setRowCount(len(backup_view.rows))
        for row_index, backup_row in enumerate(backup_view.rows):
            for column_index, value in enumerate(backup_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, backup_row.path_value)
                self.settings_backup_table.setItem(row_index, column_index, item)
        self.settings_backup_table.resizeColumnsToContents()
        self.settings_backup_status_label.setText(backup_view.status_label)

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
        abiertas = 0
        cerradas = 0
        cash_session_snapshots: list[dict[str, object]] = []
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
                    "fecha": format_display_datetime(movement.created_at, empty="-"),
                    "tipo": movement.tipo.value,
                    "monto": Decimal(movement.monto).quantize(Decimal("0.01")),
                    "usuario": movement.usuario.nombre_completo if movement.usuario is not None else "-",
                    "concepto": movement.concepto or "",
                }
                for movement in cash_session.movimientos
            ]
            cash_session_snapshots.append(
                {
                    "session_id": cash_session.id,
                    "is_closed": is_closed,
                    "status_label": "Cerrada" if is_closed else "Abierta",
                    "opened_at": format_display_datetime(cash_session.abierta_at),
                    "opened_by": opened_by,
                    "opening_amount": f"${Decimal(cash_session.monto_apertura or 0).quantize(Decimal('0.01'))}",
                    "closed_at": format_display_datetime(cash_session.cerrada_at, empty="-"),
                    "closed_by": closed_by,
                    "expected_amount": f"${Decimal(cash_session.monto_esperado_cierre or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
                    "declared_amount": f"${Decimal(cash_session.monto_cierre_declarado or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
                    "difference_amount": f"${Decimal(cash_session.diferencia_cierre or 0).quantize(Decimal('0.01'))}" if is_closed else "-",
                    "difference": str(Decimal(cash_session.diferencia_cierre or 0).quantize(Decimal("0.01"))),
                }
            )
        cash_history_rows = build_settings_cash_history_rows(cash_session_snapshots)
        self.settings_cash_history_table.setRowCount(len(cash_history_rows))
        for row_index, cash_history_row in enumerate(cash_history_rows):
            for column_index, value in enumerate(cash_history_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, cash_history_row.session_id)
                if column_index == 1:
                    _set_table_badge_style(item, cash_history_row.status_tone)
                elif column_index == 9 and cash_history_row.difference_tone is not None:
                    _set_table_badge_style(item, cash_history_row.difference_tone)
                self.settings_cash_history_table.setItem(row_index, column_index, item)
        self.settings_cash_history_table.resizeColumnsToContents()
        self.settings_cash_history_status_label.setText(
            build_settings_cash_history_status_label(
                total_sessions=len(cash_sessions),
                open_sessions=abiertas,
                closed_sessions=cerradas,
                date_from_iso=fecha_desde.isoformat(),
                date_to_iso=fecha_hasta.isoformat(),
            )
        )
        if cash_sessions:
            self.settings_cash_history_table.setCurrentCell(0, 0)
            self._refresh_selected_cash_history_movements()
        else:
            self._refresh_selected_cash_history_movements()

    def _refresh_selected_cash_history_movements(self) -> None:
        cash_session_id = self._selected_cash_history_id()
        movements = self.settings_cash_history_rows.get(cash_session_id or -1, [])
        movements_view = build_settings_cash_history_movements_view(
            cash_session_id=cash_session_id,
            movements=movements,
        )
        self.settings_cash_history_movements_table.setRowCount(len(movements_view.rows))
        for row_index, movement_row in enumerate(movements_view.rows):
            for column_index, value in enumerate(movement_row.values):
                item = _table_item(value)
                if column_index == 1:
                    _set_table_badge_style(item, movement_row.type_tone)
                self.settings_cash_history_movements_table.setItem(row_index, column_index, item)
        self.settings_cash_history_movements_table.resizeColumnsToContents()
        self.settings_cash_history_movements_label.setText(movements_view.status_label)

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
                            "fecha": format_display_datetime(movement.created_at, empty="-"),
                            "tipo": movement.tipo.value,
                            "monto": Decimal(movement.monto).quantize(Decimal("0.01")),
                            "usuario": movement.usuario.nombre_completo if movement.usuario is not None else "-",
                            "concepto": movement.concepto or "",
                        }
                    )
                detail = {
                    "id": cash_session.id,
                    "status": "Cerrada" if cash_session.cerrada_at else "Abierta",
                    "opened_at": format_display_datetime(cash_session.abierta_at, empty="-"),
                    "opened_by": opened_by,
                    "opening_amount": Decimal(cash_session.monto_apertura or 0).quantize(Decimal("0.01")),
                    "opening_note": cash_session.observacion_apertura or "Sin observacion",
                    "opening_corrections": self._extract_opening_corrections(cash_session.observacion_apertura or ""),
                    "closed_at": format_display_datetime(cash_session.cerrada_at, empty="-"),
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
        detail_view = build_settings_cash_history_detail_view(
            session_id=int(detail["id"]),
            is_closed=bool(detail["is_closed"]),
            opened_at=str(detail["opened_at"]),
            opened_by=str(detail["opened_by"]),
            opening_amount=detail["opening_amount"],
            opening_note=str(detail["opening_note"]),
            opening_corrections=list(detail["opening_corrections"]),
            reactivo_count=int(detail["reactivo_count"]),
            reactivo_total=detail["reactivo_total"],
            ingresos_count=int(detail["ingresos_count"]),
            ingresos_total=detail["ingresos_total"],
            retiros_count=int(detail["retiros_count"]),
            retiros_total=detail["retiros_total"],
            cash_sales_count=int(detail["cash_sales_count"]),
            cash_sales_total=detail["cash_sales_total"],
            cash_payments_count=int(detail["cash_payments_count"]),
            cash_payments_total=detail["cash_payments_total"],
            movement_rows=list(detail["movements"]),
            closed_at=str(detail["closed_at"]),
            closed_by=str(detail["closed_by"]),
            expected_amount=detail["expected_amount"],
            declared_amount=detail["declared_amount"],
            difference=detail["difference"],
            closing_note=str(detail["closing_note"]),
        )
        dialog.setWindowTitle(detail_view.dialog_title)
        dialog.setModal(True)
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        status_row = QHBoxLayout()
        title = QLabel(detail_view.title_label)
        title.setObjectName("inventoryTitle")
        status_badge = QLabel(detail_view.status_badge.text)
        status_badge.setObjectName("inventoryStatusBadge")
        self._set_badge_state(status_badge, detail_view.status_badge.text, detail_view.status_badge.tone)
        status_row.addWidget(title)
        status_row.addStretch()
        status_row.addWidget(status_badge)

        open_box = QGroupBox("Apertura")
        open_box.setObjectName("infoCard")
        open_form = QFormLayout()
        for label, value in detail_view.opening_rows:
            open_form.addRow(label, QLabel(value))
        opening_note = QLabel(detail_view.opening_note)
        opening_note.setWordWrap(True)
        opening_note.setObjectName("subtleLine")
        open_form.addRow("Observacion", opening_note)
        open_box.setLayout(open_form)

        layout.addLayout(status_row)
        layout.addWidget(open_box)

        if detail_view.opening_corrections:
            corrections_box = QGroupBox("Correcciones de apertura")
            corrections_box.setObjectName("infoCard")
            corrections_layout = QVBoxLayout()
            corrections_layout.setSpacing(8)
            for correction in detail_view.opening_corrections:
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
        for label, value in detail_view.flow_rows:
            flow_form.addRow(label, QLabel(value))
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
        movements_table.setRowCount(len(detail_view.movement_rows))
        for row_index, movement_row in enumerate(detail_view.movement_rows):
            for column_index, value in enumerate(movement_row.values):
                item = _table_item(value)
                if column_index == 1:
                    _set_table_badge_style(item, movement_row.type_tone)
                movements_table.setItem(row_index, column_index, item)
        movements_table.resizeColumnsToContents()
        movements_table.setMinimumHeight(160)
        movements_layout.addWidget(movements_table)
        movements_box.setLayout(movements_layout)
        layout.addWidget(movements_box)

        if detail_view.closing_visible:
            close_box = QGroupBox("Cierre")
            close_box.setObjectName("infoCard")
            close_form = QFormLayout()
            for label, value in detail_view.closing_rows:
                close_form.addRow(label, QLabel(value))
            difference_label = QLabel(detail_view.difference_badge.text if detail_view.difference_badge is not None else "")
            difference_label.setObjectName("inventoryStatusBadge")
            if detail_view.difference_badge is not None:
                self._set_badge_state(
                    difference_label,
                    detail_view.difference_badge.text,
                    detail_view.difference_badge.tone,
                )
            close_form.addRow("Diferencia", difference_label)
            closing_note = QLabel(detail_view.closing_note)
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
                defaults = build_default_settings_whatsapp_templates()
                snapshot = load_settings_business_form_snapshot(
                    session,
                    default_templates=defaults,
                )
                self.settings_business_name_input.setText(snapshot.business_name)
                self.settings_business_logo_input.setText(snapshot.logo_path)
                self._refresh_business_logo_preview(snapshot.logo_path)
                self.settings_marketing_review_days_spin.setValue(snapshot.loyalty_review_window_days)
                self.settings_marketing_leal_spend_spin.setValue(snapshot.leal_spend_threshold)
                self.settings_marketing_leal_purchase_count_spin.setValue(snapshot.leal_purchase_count_threshold)
                self.settings_marketing_leal_purchase_sum_spin.setValue(snapshot.leal_purchase_sum_threshold)
                self.settings_marketing_discount_basico_spin.setValue(snapshot.discount_basico)
                self.settings_marketing_discount_leal_spin.setValue(snapshot.discount_leal)
                self.settings_marketing_discount_profesor_spin.setValue(snapshot.discount_profesor)
                self.settings_marketing_discount_mayorista_spin.setValue(snapshot.discount_mayorista)
                self.settings_business_phone_input.setText(snapshot.phone)
                self.settings_business_address_input.setPlainText(snapshot.address)
                self.settings_business_footer_input.setPlainText(snapshot.footer)
                self.settings_business_transfer_bank_input.setText(snapshot.transfer_bank)
                self.settings_business_transfer_beneficiary_input.setText(snapshot.transfer_beneficiary)
                self.settings_business_transfer_clabe_input.setText(snapshot.transfer_clabe)
                self.settings_business_transfer_instructions_input.setPlainText(snapshot.transfer_instructions)
                self.settings_business_promo_code_input.clear()
                self.settings_business_promo_code_input.setPlaceholderText(
                    "Deja vacio para conservar el codigo actual"
                )
                self.settings_whatsapp_layaway_reminder_input.setPlainText(snapshot.whatsapp_layaway_reminder)
                self.settings_whatsapp_layaway_liquidated_input.setPlainText(snapshot.whatsapp_layaway_liquidated)
                self.settings_whatsapp_client_promotion_input.setPlainText(snapshot.whatsapp_client_promotion)
                self.settings_whatsapp_client_followup_input.setPlainText(snapshot.whatsapp_client_followup)
                self.settings_whatsapp_client_greeting_input.setPlainText(snapshot.whatsapp_client_greeting)
                printer_index = self.settings_business_printer_combo.findData(snapshot.preferred_printer)
                self.settings_business_printer_combo.setCurrentIndex(printer_index if printer_index >= 0 else 0)
                self.settings_business_copies_spin.setValue(snapshot.ticket_copies)
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
        loyalty_levels = session.scalars(select(Cliente.nivel_lealtad)).all()
        self.settings_marketing_summary_label.setText(
            build_settings_marketing_summary_label(list(loyalty_levels))
        )

    def _save_business_settings(self, success_message: str) -> bool:
        feedback = build_settings_business_guard_feedback(
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return False
        try:
            with get_session() as session:
                save_settings_business_payload(
                    session,
                    admin_user_id=self.user_id,
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
        result_feedback = build_settings_business_result_feedback(success_message)
        QMessageBox.information(self, result_feedback.title, result_feedback.message)
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
        feedback = build_settings_marketing_guard_feedback(
            "recalculate_levels",
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
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
                result = recalculate_settings_loyalty_levels(
                    session,
                    admin_user_id=self.user_id,
                )
                session.commit()
                self._refresh_marketing_summary(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo recalcular", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_marketing_result_feedback(
            total=result.total,
            changed=result.changed,
        )
        self.settings_marketing_status_label.setText(result_feedback.message)
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_open_marketing_history(self) -> None:
        feedback = build_settings_marketing_guard_feedback(
            "open_history",
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        try:
            with get_session() as session:
                changes = load_settings_marketing_history_rows(session, limit=120)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Historial no disponible", str(exc))
            return
        build_marketing_history_dialog(
            self,
            changes=changes,
        )

    def _refresh_settings_users(self) -> None:
        try:
            with get_session() as session:
                users = UserService.list_users(session)
        except Exception as exc:  # noqa: BLE001
            users_view = build_settings_users_error_view(str(exc))
            self.settings_users_status_label.setText(users_view.status_label)
            self.settings_users_table.setRowCount(len(users_view.rows))
            return

        users_view = build_settings_users_view(
            [
                {
                    "id": int(user.id),
                    "username": user.username,
                    "full_name": user.nombre_completo,
                    "role": user.rol.value,
                    "active_label": "ACTIVO" if user.activo else "INACTIVO",
                    "updated_label": format_display_datetime(user.updated_at),
                }
                for user in users
            ]
        )
        self.settings_users_table.setRowCount(len(users_view.rows))
        for row_index, user_row in enumerate(users_view.rows):
            for column_index, value in enumerate(user_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, user_row.user_id)
                self.settings_users_table.setItem(row_index, column_index, item)
        self.settings_users_table.resizeColumnsToContents()
        self.settings_users_status_label.setText(users_view.status_label)

    def _refresh_settings_suppliers(self) -> None:
        search_text = self.settings_suppliers_search_input.text().strip()
        try:
            with get_session() as session:
                suppliers = SupplierService.list_suppliers(session, search_text)
        except Exception as exc:  # noqa: BLE001
            suppliers_view = build_settings_suppliers_error_view(str(exc))
            self.settings_suppliers_status_label.setText(suppliers_view.status_label)
            self.settings_suppliers_table.setRowCount(len(suppliers_view.rows))
            return
        suppliers_view = build_settings_suppliers_view(
            [
                {
                    "id": int(supplier.id),
                    "name": supplier.nombre,
                    "phone": supplier.telefono or "",
                    "email": supplier.email or "",
                    "address": supplier.direccion or "",
                    "active": bool(supplier.activo),
                    "active_label": "ACTIVO" if supplier.activo else "INACTIVO",
                    "updated_label": format_display_datetime(supplier.updated_at),
                }
                for supplier in suppliers
            ]
        )
        self.settings_suppliers_table.setRowCount(len(suppliers_view.rows))
        for row_index, supplier_row in enumerate(suppliers_view.rows):
            for column_index, value in enumerate(supplier_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, supplier_row.supplier_id)
                if column_index == 4:
                    _set_table_badge_style(item, supplier_row.status_tone)
                self.settings_suppliers_table.setItem(row_index, column_index, item)
        self.settings_suppliers_table.resizeColumnsToContents()
        self.settings_suppliers_status_label.setText(suppliers_view.status_label)

    def _refresh_settings_clients(self) -> None:
        search_text = self.settings_clients_search_input.text().strip()
        try:
            with get_session() as session:
                clients = ClientService.list_clients(session, search_text)
        except Exception as exc:  # noqa: BLE001
            clients_view = build_settings_clients_error_view(str(exc))
            self.settings_clients_status_label.setText(clients_view.status_label)
            self.settings_clients_table.setRowCount(len(clients_view.rows))
            return
        clients_view = build_settings_clients_view(
            [
                {
                    "id": int(client.id),
                    "code": client.codigo_cliente,
                    "name": client.nombre,
                    "client_type": client.tipo_cliente.value,
                    "loyalty_level": client.nivel_lealtad.value,
                    "discount_label": f"{Decimal(client.descuento_preferente).quantize(Decimal('0.01'))}%",
                    "has_discount": Decimal(client.descuento_preferente) > Decimal("0.00"),
                    "phone": client.telefono or "",
                    "notes": client.notas or "",
                    "qr_label": "Listo" if QrGenerator.exists_for_client(client) else "Pendiente",
                    "card_label": "Lista" if bool(client.card_image_path) and Path(str(client.card_image_path)).exists() else "Pendiente",
                    "active": bool(client.activo),
                    "active_label": "ACTIVO" if client.activo else "INACTIVO",
                    "updated_label": format_display_datetime(client.updated_at),
                }
                for client in clients
            ]
        )
        self.settings_clients_table.setRowCount(len(clients_view.rows))
        for row_index, client_row in enumerate(clients_view.rows):
            for column_index, value in enumerate(client_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole + 1, client_row.client_code)
                if column_index == 1:
                    item.setData(Qt.ItemDataRole.UserRole, client_row.client_id)
                if column_index == 2:
                    _set_table_badge_style(item, client_row.client_type_tone)
                if column_index == 3:
                    _set_table_badge_style(item, client_row.loyalty_level_tone)
                if column_index == 4 and client_row.discount_tone is not None:
                    _set_table_badge_style(item, client_row.discount_tone)
                if column_index == 7:
                    _set_table_badge_style(item, client_row.qr_tone)
                if column_index == 8:
                    _set_table_badge_style(item, client_row.card_tone)
                if column_index == 9:
                    _set_table_badge_style(item, client_row.status_tone)
                self.settings_clients_table.setItem(row_index, column_index, item)
        self.settings_clients_table.resizeColumnsToContents()
        self.settings_clients_status_label.setText(clients_view.status_label)

    def _selected_settings_user_id(self) -> int | None:
        selected_row = self.settings_users_table.currentRow()
        item = self.settings_users_table.item(selected_row, 0)
        raw_user_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return resolve_selected_settings_user_id(
            current_row=selected_row,
            raw_user_id=raw_user_id,
        )

    def _selected_settings_supplier_id(self) -> int | None:
        selected_row = self.settings_suppliers_table.currentRow()
        item = self.settings_suppliers_table.item(selected_row, 0)
        raw_supplier_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return resolve_selected_settings_supplier_id(
            current_row=selected_row,
            raw_supplier_id=raw_supplier_id,
        )

    def _selected_settings_client_id(self) -> int | None:
        selected_row = self.settings_clients_table.currentRow()
        item = self.settings_clients_table.item(selected_row, 1)
        raw_client_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return resolve_selected_settings_client_id(
            current_row=selected_row,
            raw_client_id=raw_client_id,
        )

    def _handle_create_user(self) -> None:
        feedback = build_settings_user_guard_feedback(
            "create_user",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=False,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        data = prompt_create_user_data(self)
        if data is None:
            return
        try:
            with get_session() as session:
                result = create_settings_user(
                    session,
                    admin_user_id=self.user_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self._refresh_settings_users()
        result_feedback = build_settings_user_result_feedback(
            "create_user",
            username=result.username,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_toggle_user(self) -> None:
        user_id = self._selected_settings_user_id()
        feedback = build_settings_user_guard_feedback(
            "toggle_user",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=user_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                result = toggle_settings_user(
                    session,
                    admin_user_id=self.user_id,
                    user_id=user_id,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self._refresh_settings_users()
        result_feedback = build_settings_user_result_feedback(
            "toggle_user",
            username=result.username,
            status_text=result.status_text,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_change_user_role(self) -> None:
        user_id = self._selected_settings_user_id()
        feedback = build_settings_user_guard_feedback(
            "change_user_role",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=user_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_user_prompt_snapshot(session, user_id=user_id)
                new_role = prompt_role_change(self, prompt_snapshot.current_role)
                if new_role is None:
                    return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return

        try:
            with get_session() as session:
                result = change_settings_user_role(
                    session,
                    admin_user_id=self.user_id,
                    user_id=user_id,
                    new_role=new_role,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cambiar rol", str(exc))
            return

        self._refresh_settings_users()
        result_feedback = build_settings_user_result_feedback(
            "change_user_role",
            username=result.username,
            role_label=result.role_label,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_change_user_password(self) -> None:
        user_id = self._selected_settings_user_id()
        feedback = build_settings_user_guard_feedback(
            "change_user_password",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=user_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            new_password = prompt_password_change(self)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Contrasena invalida", str(exc))
            return
        if new_password is None:
            return

        try:
            with get_session() as session:
                result = change_settings_user_password(
                    session,
                    admin_user_id=self.user_id,
                    user_id=user_id,
                    new_password=new_password,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cambiar contrasena", str(exc))
            return

        result_feedback = build_settings_user_result_feedback(
            "change_user_password",
            username=result.username,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_edit_user(self) -> None:
        user_id = self._selected_settings_user_id()
        feedback = build_settings_user_guard_feedback(
            "edit_user",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=user_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_user_prompt_snapshot(session, user_id=user_id)
                data = prompt_edit_user_data(
                    self,
                    username=prompt_snapshot.username,
                    nombre_completo=prompt_snapshot.full_name,
                    current_role=prompt_snapshot.current_role,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                result = update_settings_user(
                    session,
                    admin_user_id=self.user_id,
                    user_id=user_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self._refresh_settings_users()
        result_feedback = build_settings_user_result_feedback(
            "edit_user",
            username=result.username,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_create_supplier(self) -> None:
        feedback = build_settings_supplier_guard_feedback(
            "create_supplier",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=False,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        data = prompt_supplier_data(
            self,
            title="Crear proveedor",
            helper_text="Captura los datos base del proveedor para usarlo despues en compras.",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                result = create_settings_supplier(
                    session,
                    admin_user_id=self.user_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_supplier_result_feedback(
            "create_supplier",
            supplier_name=result.supplier_name,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_update_supplier(self) -> None:
        supplier_id = self._selected_settings_supplier_id()
        feedback = build_settings_supplier_guard_feedback(
            "update_supplier",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=supplier_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_supplier_prompt_snapshot(session, supplier_id=supplier_id)
                data = prompt_supplier_data(
                    self,
                    title="Editar proveedor",
                    helper_text="Actualiza contacto, correo o direccion del proveedor.",
                    current_values={
                        "nombre": prompt_snapshot.name,
                        "telefono": prompt_snapshot.phone,
                        "email": prompt_snapshot.email,
                        "direccion": prompt_snapshot.address,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                result = update_settings_supplier(
                    session,
                    admin_user_id=self.user_id,
                    supplier_id=supplier_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_supplier_result_feedback(
            "update_supplier",
            supplier_name=result.supplier_name,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_toggle_supplier(self) -> None:
        supplier_id = self._selected_settings_supplier_id()
        feedback = build_settings_supplier_guard_feedback(
            "toggle_supplier",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=supplier_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                result = toggle_settings_supplier(
                    session,
                    admin_user_id=self.user_id,
                    supplier_id=supplier_id,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_supplier_result_feedback(
            "toggle_supplier",
            supplier_name=result.supplier_name,
            status_text=result.status_text,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_create_client(self) -> None:
        feedback = build_settings_client_guard_feedback(
            "create_client",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=False,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        data = prompt_client_data(
            self,
            title="Crear cliente",
            helper_text="Captura los datos base del cliente para futuras ventas, apartados o programas de fidelizacion.",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                result = create_settings_client(
                    session,
                    admin_user_id=self.user_id,
                    payload=data,
                    render_card=self._render_client_card_safe,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_client_result_feedback(
            "create_client",
            client_name=result.client_name,
            asset_path=str(result.card_path) if result.card_path is not None else None,
            asset_error=result.card_error,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_update_client(self) -> None:
        client_id = self._selected_settings_client_id()
        feedback = build_settings_client_guard_feedback(
            "update_client",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=client_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_client_prompt_snapshot(session, client_id=client_id)
                data = prompt_client_data(
                    self,
                    title="Editar cliente",
                    helper_text="Actualiza telefono, tipo comercial, descuento o notas del cliente.",
                    current_values={
                        "nombre": prompt_snapshot.name,
                        "tipo_cliente": prompt_snapshot.client_type,
                        "descuento_preferente": prompt_snapshot.discount_label,
                        "telefono": prompt_snapshot.phone,
                        "notas": prompt_snapshot.notes,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                result = update_settings_client(
                    session,
                    admin_user_id=self.user_id,
                    client_id=client_id,
                    payload=data,
                    render_card=self._render_client_card_safe,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_client_result_feedback(
            "update_client",
            client_name=result.client_name,
            asset_path=str(result.card_path) if result.card_path is not None else None,
            asset_error=result.card_error,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_toggle_client(self) -> None:
        client_id = self._selected_settings_client_id()
        feedback = build_settings_client_guard_feedback(
            "toggle_client",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=client_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                result = toggle_settings_client(
                    session,
                    admin_user_id=self.user_id,
                    client_id=client_id,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_client_result_feedback(
            "toggle_client",
            client_name=result.client_name,
            status_text=result.status_text,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_generate_client_qr(self) -> None:
        client_id = self._selected_settings_client_id()
        feedback = build_settings_client_guard_feedback(
            "generate_client_qr",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=client_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                result = generate_settings_client_qr(session, client_id=client_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        self._refresh_settings_clients()
        result_feedback = build_settings_client_result_feedback(
            "generate_client_qr",
            client_name=result.client_name,
            client_code=result.client_code,
            asset_path=str(result.card_path) if result.card_path is not None else "",
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

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
                payload = prompt_client_whatsapp_data(self, client.nombre)
                if payload is None:
                    return
                message_type, extra_message = payload
                templates = self._get_whatsapp_templates()
                base_message = {
                    "promotion": templates["client_promotion"],
                    "greeting": templates["client_greeting"],
                    "followup": templates["client_followup"],
                }.get(message_type, templates["client_followup"])
                base_message = render_settings_whatsapp_template(
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
        item = self.settings_backup_table.item(selected_row, 0)
        raw_path = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return resolve_selected_settings_backup_path(
            current_row=selected_row,
            raw_path=raw_path,
        )

    def _handle_create_backup(self) -> None:
        feedback = build_settings_backup_guard_feedback(
            "create_backup",
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        dump_format = str(self.settings_backup_format_combo.currentData() or "plain")
        try:
            result = create_settings_backup(
                dump_format=dump_format,
                retention_days=7,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Respaldo fallido", str(exc))
            return

        self._refresh_settings_backups()
        result_feedback = build_settings_backup_result_feedback(
            "create_backup",
            backup_name=result.backup_file.name,
            deleted_count=len(result.deleted_files),
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _run_quick_backup_flow(self, *, allow_continue_on_error: bool = False) -> bool:
        feedback = build_settings_backup_guard_feedback(
            "create_backup",
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return False
        try:
            result = create_settings_backup(
                dump_format="custom",
                retention_days=14,
            )
        except Exception as exc:  # noqa: BLE001
            if not allow_continue_on_error:
                QMessageBox.critical(self, "Respaldo fallido", str(exc))
                return False
            continue_after_error = QMessageBox.question(
                self,
                "Respaldo fallido",
                f"No se pudo generar el respaldo antes de salir.\n\n{exc}\n\nQuieres continuar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return continue_after_error == QMessageBox.StandardButton.Yes

        self._refresh_settings_backups()
        result_feedback = build_settings_backup_result_feedback(
            "create_backup",
            backup_name=result.backup_file.name,
            deleted_count=len(result.deleted_files),
        )
        QMessageBox.information(self, "Respaldo rapido listo", result_feedback.message)
        return True

    def _handle_quick_backup(self) -> None:
        self._run_quick_backup_flow()

    def _handle_open_backup_folder(self) -> None:
        try:
            open_settings_backup_folder()
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
        backup_path = self._selected_backup_path()
        feedback = build_settings_backup_guard_feedback(
            "restore_backup",
            is_admin=self.current_role == RolUsuario.ADMIN,
            backup_path=backup_path,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        assert backup_path is not None
        confirmation_view = build_settings_backup_restore_confirmation(backup_path.name)
        confirmation = QMessageBox.question(
            self,
            confirmation_view.title,
            confirmation_view.message,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_settings_backup(
                backup_path,
                dispose_database=engine.dispose,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Restauracion fallida", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_backup_result_feedback(
            "restore_backup",
            backup_name=backup_path.name,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

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
                gate_snapshot = load_cash_session_gate_snapshot(
                    session,
                    user_id=self.user_id,
                    is_stale_session=self._is_stale_cash_session,
                )
                if gate_snapshot.has_active_session:
                    self.active_cash_session_id = gate_snapshot.active_session_id
                    self.cash_session_requires_cut = gate_snapshot.requires_cut
                    feedback = build_cash_session_gate_feedback(
                        requires_cut=gate_snapshot.requires_cut,
                        opened_at_label=gate_snapshot.opened_at_label,
                        opened_by=gate_snapshot.opened_by,
                        opening_amount=gate_snapshot.opening_amount,
                    )
                    if gate_snapshot.requires_cut:
                        QMessageBox.warning(self, feedback.title, feedback.message)
                    else:
                        QMessageBox.information(self, feedback.title, feedback.message)
                    return True
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Caja no disponible", str(exc))
            return False

        payload = self._prompt_open_cash_session()
        if payload is None:
            return False

        try:
            with get_session() as session:
                self.active_cash_session_id = open_cash_session_action(
                    session,
                    user_id=self.user_id,
                    opening_amount=Decimal(payload["monto_apertura"]),
                    opening_note=str(payload["observacion"]),
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir caja", str(exc))
            return False
        return True

    def _prompt_open_cash_session(self) -> dict[str, object] | None:
        suggested_amount: Decimal | None = None
        try:
            with get_session() as session:
                suggested_amount = load_cash_opening_suggested_amount(session)
        except Exception:
            suggested_amount = None
        return prompt_open_cash_session(
            self,
            suggested_amount=suggested_amount,
        )

    def _prompt_cash_movement_data(self, movement_type: TipoMovimientoCaja) -> dict[str, object] | None:
        target_total: Decimal | None = None
        try:
            with get_session() as session:
                target_snapshot = load_cash_movement_target_snapshot(
                    session,
                    active_cash_session_id=self.active_cash_session_id,
                    movement_type=movement_type,
                )
                target_total = target_snapshot.target_total
        except Exception:
            target_total = None
        return prompt_cash_movement_data(
            self,
            movement_type=movement_type,
            target_total=target_total,
        )

    def _prompt_cash_opening_correction(self) -> dict[str, object] | None:
        current_amount = Decimal("0.00")
        try:
            with get_session() as session:
                current_amount = load_cash_opening_amount(
                    session,
                    active_cash_session_id=self.active_cash_session_id,
                )
        except Exception:
            current_amount = Decimal("0.00")
        return prompt_cash_opening_correction(
            self,
            current_amount=current_amount,
        )

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
                register_cash_movement_action(
                    session,
                    active_cash_session_id=int(self.active_cash_session_id),
                    user_id=self.user_id,
                    movement_type=movement_type,
                    amount=Decimal(payload["monto"]),
                    concept=str(payload["concepto"]) or None,
                )
        except Exception as exc:
            QMessageBox.critical(self, "Movimiento no registrado", str(exc))
            return
        self.refresh_all()
        feedback = build_cash_movement_success_feedback(
            movement_type=movement_type,
            amount=Decimal(payload["monto"]),
            target_total=payload.get("total_objetivo"),
        )
        QMessageBox.information(self, feedback.title, feedback.message)

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
                result = correct_cash_opening_action(
                    session,
                    active_cash_session_id=int(self.active_cash_session_id),
                    user_id=self.user_id,
                    new_amount=Decimal(payload["nuevo_monto"]),
                    note=str(payload["motivo"]) or None,
                )
        except Exception as exc:
            QMessageBox.critical(self, "Correccion no registrada", str(exc))
            return
        self.refresh_all()
        feedback = build_cash_opening_correction_success_feedback(
            previous_amount=result.previous_amount,
            new_amount=result.new_amount,
        )
        QMessageBox.information(self, feedback.title, feedback.message)

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
                prompt_snapshot = load_cash_cut_prompt_snapshot(
                    session,
                    active_cash_session_id=int(self.active_cash_session_id),
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Corte no disponible", str(exc))
            return

        payload = prompt_cash_cut_data(
            self,
            summary_view=CashCutSummaryView(
                opened_at_label=prompt_snapshot.opened_at_label,
                opening_amount=prompt_snapshot.opening_amount,
                reactivo_count=prompt_snapshot.reactivo_count,
                reactivo_total=prompt_snapshot.reactivo_total,
                ingresos_count=prompt_snapshot.ingresos_count,
                ingresos_total=prompt_snapshot.ingresos_total,
                retiros_count=prompt_snapshot.retiros_count,
                retiros_total=prompt_snapshot.retiros_total,
                cash_sales_count=prompt_snapshot.cash_sales_count,
                cash_sales_total=prompt_snapshot.cash_sales_total,
                cash_payments_count=prompt_snapshot.cash_payments_count,
                cash_payments_total=prompt_snapshot.cash_payments_total,
                expected_amount=prompt_snapshot.expected_amount,
            ),
        )
        if payload is None:
            return

        try:
            with get_session() as session:
                result = close_cash_session_action(
                    session,
                    active_cash_session_id=int(self.active_cash_session_id),
                    user_id=self.user_id,
                    counted_amount=Decimal(payload["monto_contado"]),
                    closing_note=str(payload["observacion"]),
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cerrar caja", str(exc))
            return

        self.active_cash_session_id = None
        self.refresh_all()
        feedback = build_cash_close_success_feedback(
            expected_amount=result.expected_amount,
            counted_amount=result.counted_amount,
            difference=result.difference,
        )
        QMessageBox.information(self, feedback.title, feedback.message)

    def _handle_logout(self) -> None:
        confirmation = QMessageBox.question(
            self,
            "Cerrar sesion",
            "Se cerrara la sesion actual y volveras al acceso del sistema.\n\nContinuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        if self.current_role == RolUsuario.ADMIN:
            backup_prompt = QMessageBox.question(
                self,
                "Respaldo antes de salir",
                "Quieres crear un respaldo restaurable (.dump) antes de cerrar sesion?\n\n"
                "Te deja un checkpoint rapido antes de cambiar de usuario o salir del POS.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if backup_prompt == QMessageBox.StandardButton.Cancel:
                return
            if backup_prompt == QMessageBox.StandardButton.Yes:
                if not self._run_quick_backup_flow(allow_continue_on_error=True):
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
        return build_catalog_product_dialog(
            self,
            initial=initial,
            picker_button_class=MultiSelectPickerButton,
            product_templates=PRODUCT_TEMPLATES,
            common_sizes=COMMON_SIZES,
            common_colors=COMMON_COLORS,
            default_variant_size=DEFAULT_VARIANT_SIZE,
            default_variant_color=DEFAULT_VARIANT_COLOR,
        )

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
        return build_catalog_batch_variant_dialog(
            self,
            sizes=sizes,
            colors=colors,
            initial_price=initial_price,
            pricing_mode=pricing_mode,
            prices_by_size=prices_by_size,
            price_summary=price_summary,
            initial_cost=initial_cost,
            initial_stock=initial_stock,
            default_variant_size=DEFAULT_VARIANT_SIZE,
            default_variant_color=DEFAULT_VARIANT_COLOR,
        )

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
        return build_catalog_variant_dialog(
            self,
            initial=initial,
            include_stock=include_stock,
            default_product_id=default_product_id,
            common_sizes=COMMON_SIZES,
            common_colors=COMMON_COLORS,
            default_variant_size=DEFAULT_VARIANT_SIZE,
            default_variant_color=DEFAULT_VARIANT_COLOR,
        )

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
                (
                    variante.id,
                    variante.sku,
                    sanitize_product_display_name(variante.producto.nombre),
                    variante.stock_actual,
                )
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
                (
                    variante.id,
                    variante.sku,
                    sanitize_product_display_name(variante.producto.nombre),
                    variante.stock_actual,
                )
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
        payload = prompt_inventory_count_data(self)
        if payload is None:
            return None
        return {
            "referencia": str(payload.get("reference", "")).strip(),
            "observacion": str(payload.get("observation", "")).strip(),
            "conteos": [
                {
                    "variante_id": int(row["variante_id"]),
                    "stock_sistema": int(row["stock_sistema"]),
                    "stock_contado": int(row["stock_contado"]),
                    "delta": int(row["delta"]),
                }
                for row in list(payload.get("rows", []))
            ],
        }

    @staticmethod
    def _generate_inventory_batch_reference(prefix: str = "AJL") -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{timestamp}-{uuid4().hex[:4].upper()}"

    def _prompt_inventory_bulk_adjustment_data(self) -> dict[str, object] | None:
        selected_ids = self._selected_inventory_variant_ids()
        filtered_rows = list(self.inventory_filtered_rows)
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
        filtered_rows = list(self.inventory_filtered_rows)
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

        validation_feedback = validate_catalog_variant_submission(data, require_stock=include_stock)
        if validation_feedback is not None:
            QMessageBox.warning(self, "Datos incompletos", validation_feedback)
            return None

        producto_id = data["producto_id"]
        sku = str(data["sku"]).strip()
        talla = str(data["talla"]).strip()
        color = str(data["color"]).strip() or "Sin color"
        price_text = str(data["precio"]).strip()
        cost_text = str(data["costo"]).strip()

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

        validation_feedback = validate_catalog_product_submission(data)
        if validation_feedback is not None:
            QMessageBox.warning(self, "Datos incompletos", validation_feedback)
            return

        categoria_id = data["categoria_id"]
        categoria_nombre = str(data.get("categoria_nombre") or "")
        marca_id = data["marca_id"]
        nombre = str(data["nombre"]).strip()
        descripcion = str(data["descripcion"]).strip()

        created_product_id: int | None = None
        selected_sizes = [str(value).strip() for value in data.get("tallas", []) if str(value).strip()]
        selected_colors = [str(value).strip() for value in data.get("colores", []) if str(value).strip()]
        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                categoria = (
                    session.get(Categoria, int(categoria_id))
                    if categoria_id is not None
                    else self._resolve_named_taxonomy(session, Categoria, categoria_nombre)
                )
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
        row = resolve_catalog_row(self.catalog_rows, self.catalog_table.currentRow())
        if row is None:
            self.products_selection_label.setText(build_empty_catalog_selection_view().selection_label)
            return

        selection_view = build_catalog_selection_view_from_row(
            is_admin=self.current_role == RolUsuario.ADMIN,
            row=row,
        )
        self.products_selection_label.setText(selection_view.selection_label)

    def _handle_update_product(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="update_product",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

        try:
            data = self._prompt_product_data(selected)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se puede editar", str(exc))
            return
        if data is None:
            return

        categoria_id = data["categoria_id"]
        categoria_nombre = str(data.get("categoria_nombre") or "")
        marca_id = data["marca_id"]
        nombre = str(data["nombre"]).strip()
        descripcion = str(data["descripcion"]).strip()

        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                producto = session.get(Producto, int(selected["producto_id"]))
                categoria = (
                    session.get(Categoria, int(categoria_id))
                    if categoria_id is not None
                    else self._resolve_named_taxonomy(session, Categoria, categoria_nombre)
                )
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
        result_view = build_catalog_success_result(
            action_key="update_product",
            item_label=nombre,
        )
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_update_variant(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="update_variant",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

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
        result_view = build_catalog_success_result(
            action_key="update_variant",
            item_label=sku.upper(),
        )
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_toggle_product(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="toggle_product",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

        target_state = not bool(selected["producto_activo"])
        action = "activar" if target_state else "desactivar"

        try:
            with get_session() as session:
                toggle_catalog_product_state(
                    session,
                    user_id=self.user_id,
                    product_id=int(selected["producto_id"]),
                    target_state=target_state,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, build_catalog_error_title("toggle_product"), str(exc))
            return

        self.refresh_all()
        self._select_catalog_variant(int(selected["variante_id"]))
        result_view = build_catalog_success_result(
            action_key=f"toggle_product_{action}",
            item_label=str(selected["producto_nombre"]),
        )
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_toggle_variant(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="toggle_variant",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

        target_state = not bool(selected["variante_activo"])
        action = "activar" if target_state else "desactivar"

        try:
            with get_session() as session:
                toggle_catalog_variant_state(
                    session,
                    user_id=self.user_id,
                    variant_id=int(selected["variante_id"]),
                    target_state=target_state,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, build_catalog_error_title("toggle_variant"), str(exc))
            return

        self.refresh_all()
        self._select_catalog_variant(int(selected["variante_id"]))
        result_view = build_catalog_success_result(
            action_key=f"toggle_variant_{action}",
            item_label=str(selected["sku"]),
        )
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_delete_product(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="delete_product",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

        product_name = str(selected["producto_nombre"])
        confirmation_view = build_catalog_delete_confirmation(
            action_key="delete_product",
            item_label=product_name,
        )
        confirmation = QMessageBox.question(self, confirmation_view.title, confirmation_view.message)
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_session() as session:
                delete_catalog_product(
                    session,
                    user_id=self.user_id,
                    product_id=int(selected["producto_id"]),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, build_catalog_error_title("delete_product"), str(exc))
            return

        self.refresh_all()
        result_view = build_catalog_success_result(
            action_key="delete_product",
            item_label=product_name,
        )
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_delete_variant(self) -> None:
        selected = self._selected_catalog_row()
        feedback = build_catalog_action_guard_feedback(
            action_key="delete_variant",
            has_selection=selected is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert selected is not None

        sku = str(selected["sku"])
        confirmation_view = build_catalog_delete_confirmation(
            action_key="delete_variant",
            item_label=sku,
        )
        confirmation = QMessageBox.question(self, confirmation_view.title, confirmation_view.message)
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            with get_session() as session:
                delete_catalog_variant(
                    session,
                    user_id=self.user_id,
                    variant_id=int(selected["variante_id"]),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, build_catalog_error_title("delete_variant"), str(exc))
            return

        self.refresh_all()
        result_view = build_catalog_success_result(
            action_key="delete_variant",
            item_label=sku,
        )
        QMessageBox.information(self, result_view.title, result_view.message)

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
            self.recent_sales_table.itemSelectionChanged.connect(self._apply_recent_sale_action_state)
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

        self._apply_recent_sale_action_state()
        self.recent_sales_table.resizeColumnsToContents()
        self.sales_dialog.show()
        self.sales_dialog.raise_()
        self.sales_dialog.activateWindow()

    def _selected_recent_sale_id(self) -> int | None:
        return resolve_selected_recent_sale_id(self.recent_sales_table)

    def _apply_recent_sale_action_state(self) -> None:
        action_state = build_recent_sale_action_state(
            has_selection=self._selected_recent_sale_id() is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        self.sale_ticket_button.setEnabled(action_state.ticket_enabled)
        self.cancel_button.setEnabled(action_state.cancel_enabled)

    def _handle_view_sale_ticket(self) -> None:
        sale_id = self._selected_recent_sale_id()
        feedback = build_recent_sale_guard_feedback(
            "view_ticket",
            has_selection=sale_id is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert sale_id is not None

        try:
            open_printable_document_flow(
                parent=self,
                session_factory=get_session,
                build_document_view=lambda session: build_sale_ticket_document_view(session, sale_id=sale_id),
                open_dialog=open_printable_text_dialog,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

    def _handle_view_layaway_receipt(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su comprobante.")
            return

        try:
            open_printable_document_flow(
                parent=self,
                session_factory=get_session,
                build_document_view=lambda session: build_layaway_receipt_document_view(session, layaway_id=apartado_id),
                open_dialog=open_printable_text_dialog,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Comprobante no disponible", str(exc))
            return

    def _handle_view_layaway_sale_ticket(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su ticket de venta.")
            return

        try:
            open_printable_document_flow(
                parent=self,
                session_factory=get_session,
                build_document_view=lambda session: build_layaway_sale_ticket_document_view(session, layaway_id=apartado_id),
                open_dialog=open_printable_text_dialog,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

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
        self._refresh_sale_client_display()
        self._apply_sale_client_selection_ui_state(
            build_empty_sale_client_selection_ui_state(
                normalize_discount_value=self._normalize_discount_value,
                format_discount_label=self._format_discount_label,
            )
        )
        self._refresh_sale_discount_options(selected_discount=Decimal("0.00"))
        self.sale_folio_input.setText(self._generate_sale_folio())
        self.sale_last_scanned_sku = ""
        self.sale_last_scanned_at = 0.0
        self._refresh_payment_fields()

    def _refresh_sale_client_display(self) -> None:
        current_label = self.sale_client_combo.currentText().strip() or "Mostrador / sin cliente"
        self.sale_client_display_label.setText(current_label)

    def _reset_quote_form(self) -> None:
        self.quote_sku_input.clear()
        self.quote_qty_spin.setValue(1)
        self.quote_client_combo.setCurrentIndex(0)
        self.quote_validity_input.setDate(QDate.currentDate().addDays(7))
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

    def _apply_sale_post_action_view(self, view: SalePostActionView) -> None:
        if view.play_feedback_sound:
            self._play_sale_feedback_sound()
        if view.clear_sale_cart:
            self.sale_cart.clear()
            self._refresh_sale_cart_table()
        if view.reset_sale_form:
            self._reset_sale_form()
        if view.refresh_all:
            self.refresh_all()
        if view.focus_sale_input:
            self.sale_sku_input.setFocus()
        self._set_sale_feedback(
            view.feedback_message,
            view.feedback_tone,
            auto_clear_ms=view.feedback_auto_clear_ms,
        )
        if view.notice_title and view.notice_message:
            QMessageBox.information(self, view.notice_title, view.notice_message)

    def _set_sale_processing(self, active: bool) -> None:
        self.sale_processing = active
        self.sale_button.setEnabled(not active and self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO})
        self.sale_button.setText("Procesando..." if active else "Cobrar")
        self._refresh_payment_fields()

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

    def _apply_scanned_client_to_sale(self, session, client: Cliente, scanned_code: str) -> bool:
        ui_state = build_sale_scanned_client_ui_state(
            current_client_id=self.sale_client_combo.currentData(),
            current_client_label=self.sale_client_combo.currentText().strip() or "Cliente actual",
            scanned_client_id=client.id,
            scanned_client_code=client.codigo_cliente,
            scanned_client_name=client.nombre,
            has_sale_cart=bool(self.sale_cart),
            discount_percent=load_sale_selected_client_discount_percent(
                session,
                selected_client_id=client.id,
                normalize_discount_value=self._normalize_discount_value,
            ),
            format_discount_label=self._format_discount_label,
        )
        if ui_state.action == "already_linked":
            self.sale_sku_input.clear()
            self.sale_qty_spin.setValue(1)
            assert ui_state.immediate_feedback is not None
            self._set_sale_feedback(
                ui_state.immediate_feedback.message,
                ui_state.immediate_feedback.tone,
                auto_clear_ms=ui_state.immediate_feedback.auto_clear_ms,
            )
            self.sale_sku_input.setFocus()
            return True

        if ui_state.action == "confirm_replace":
            confirmation = QMessageBox.question(
                self,
                "Cambiar cliente de la venta",
                ui_state.confirmation_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                self.sale_sku_input.clear()
                self.sale_qty_spin.setValue(1)
                assert ui_state.rejected_feedback is not None
                self._set_sale_feedback(
                    ui_state.rejected_feedback.message,
                    ui_state.rejected_feedback.tone,
                    auto_clear_ms=ui_state.rejected_feedback.auto_clear_ms,
                )
                self.sale_sku_input.setFocus()
                return True

        combo_index = self.sale_client_combo.findData(int(client.id))
        if combo_index < 0:
            raise ValueError(f"El cliente escaneado '{scanned_code}' no esta disponible en Caja.")

        self.sale_client_combo.setCurrentIndex(combo_index)
        self._refresh_sale_client_display()
        self.sale_last_scanned_sku = client.codigo_cliente
        self.sale_last_scanned_at = monotonic()
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self._play_sale_feedback_sound()
        assert ui_state.applied_feedback is not None
        self._set_sale_feedback(
            ui_state.applied_feedback.message,
            ui_state.applied_feedback.tone,
            auto_clear_ms=ui_state.applied_feedback.auto_clear_ms,
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
        try:
            with get_session() as session:
                return load_sale_discount_presets(
                    session,
                    normalize_discount_value=self._normalize_discount_value,
                )
        except Exception:
            return load_sale_discount_presets(
                None,
                normalize_discount_value=self._normalize_discount_value,
            )

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

    def _set_sale_discount_combo_percent(self, discount_percent: Decimal | str | int | float) -> None:
        index = self._ensure_sale_discount_option(discount_percent)
        previous_state = self.sale_discount_combo.blockSignals(True)
        self.sale_discount_combo.setCurrentIndex(index)
        self.sale_discount_combo.blockSignals(previous_state)

    def _clear_sale_manual_promo_authorization(self) -> None:
        state = clear_sale_manual_promo_snapshot()
        self.sale_manual_promo_authorized = state.authorized
        self.sale_manual_promo_authorized_percent = state.authorized_percent

    def _sale_manual_promo_state(self):
        return build_sale_manual_promo_snapshot(
            authorized=self.sale_manual_promo_authorized,
            authorized_percent=self.sale_manual_promo_authorized_percent,
        )

    def _apply_sale_manual_promo_state(self, state) -> None:
        self.sale_manual_promo_authorized = state.authorized
        self.sale_manual_promo_authorized_percent = state.authorized_percent

    def _apply_sale_client_selection_ui_state(self, ui_state) -> None:
        if ui_state.combo_discount_percent is not None:
            self._set_sale_discount_combo_percent(ui_state.combo_discount_percent)
        if ui_state.clear_manual_promo:
            self._clear_sale_manual_promo_authorization()
        self.sale_discount_locked_to_client = ui_state.lock_state.locked
        self.sale_locked_discount_percent = ui_state.lock_state.discount_percent
        self.sale_locked_discount_source = ui_state.lock_state.source_label
        self.sale_discount_combo.setToolTip(ui_state.lock_tooltip)

    def _current_manual_promo_percent(self) -> Decimal:
        return build_sale_discount_context(
            locked_to_client=self.sale_discount_locked_to_client,
            locked_discount_percent=self.sale_locked_discount_percent,
            locked_source_label=self.sale_locked_discount_source,
            selected_discount_percent=self.sale_discount_combo.currentData(),
            manual_promo_authorized=self.sale_manual_promo_authorized,
            manual_promo_authorized_percent=self.sale_manual_promo_authorized_percent,
        ).promo_discount

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
                verify_sale_manual_promo_code(session, code)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Codigo invalido", str(exc))
            return False
        return True

    def _handle_sale_discount_changed(self) -> None:
        transition = resolve_sale_manual_discount_transition(
            selected_percent=self.sale_discount_combo.currentData(),
            authorized=self.sale_manual_promo_authorized,
            authorized_percent=self.sale_manual_promo_authorized_percent,
            format_discount_label=self._format_discount_label,
            authorize_manual_promo=self._prompt_manual_promo_authorization,
        )
        self._apply_sale_manual_promo_state(transition.next_state)
        self._set_sale_discount_combo_percent(transition.combo_percent)
        if transition.feedback_message:
            self._set_sale_feedback(
                transition.feedback_message,
                transition.feedback_tone,
                auto_clear_ms=transition.feedback_auto_clear_ms,
            )
        self._refresh_sale_cart_table()

    def _sync_sale_discount_with_selected_client(self, *, reset_manual: bool = False) -> None:
        try:
            with get_session() as session:
                ui_state = resolve_sale_client_discount_ui_state(
                    session,
                    selected_client_id=self.sale_client_combo.currentData(),
                    reset_manual=reset_manual,
                    normalize_discount_value=self._normalize_discount_value,
                    format_discount_label=self._format_discount_label,
                )
        except Exception:
            ui_state = resolve_sale_client_discount_ui_state(
                None,
                selected_client_id=None,
                reset_manual=reset_manual,
                normalize_discount_value=self._normalize_discount_value,
                format_discount_label=self._format_discount_label,
            )
        self._apply_sale_client_selection_ui_state(ui_state)
        self._refresh_sale_cart_table()

    def _handle_sale_client_changed(self) -> None:
        self._refresh_sale_client_display()
        self._sync_sale_discount_with_selected_client(reset_manual=True)

    def _effective_sale_discount_percent(self) -> Decimal:
        return build_sale_discount_context(
            locked_to_client=self.sale_discount_locked_to_client,
            locked_discount_percent=self.sale_locked_discount_percent,
            locked_source_label=self.sale_locked_discount_source,
            selected_discount_percent=self.sale_discount_combo.currentData(),
            manual_promo_authorized=self.sale_manual_promo_authorized,
            manual_promo_authorized_percent=self.sale_manual_promo_authorized_percent,
        ).effective_discount

    def _sale_discount_breakdown(self) -> dict[str, object]:
        return build_sale_discount_context(
            locked_to_client=self.sale_discount_locked_to_client,
            locked_discount_percent=self.sale_locked_discount_percent,
            locked_source_label=self.sale_locked_discount_source,
            selected_discount_percent=self.sale_discount_combo.currentData(),
            manual_promo_authorized=self.sale_manual_promo_authorized,
            manual_promo_authorized_percent=self.sale_manual_promo_authorized_percent,
        ).breakdown

    def _calculate_sale_totals(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return calculate_sale_discount_totals(
            self.sale_cart,
            locked_to_client=self.sale_discount_locked_to_client,
            locked_discount_percent=self.sale_locked_discount_percent,
            selected_discount_percent=self.sale_discount_combo.currentData(),
            manual_promo_authorized=self.sale_manual_promo_authorized,
            manual_promo_authorized_percent=self.sale_manual_promo_authorized_percent,
        )

    def _calculate_sale_pricing(self):
        return calculate_sale_discount_pricing(
            self.sale_cart,
            locked_to_client=self.sale_discount_locked_to_client,
            locked_discount_percent=self.sale_locked_discount_percent,
            selected_discount_percent=self.sale_discount_combo.currentData(),
            manual_promo_authorized=self.sale_manual_promo_authorized,
            manual_promo_authorized_percent=self.sale_manual_promo_authorized_percent,
        )

    def _refresh_payment_fields(self) -> None:
        panel_view = build_sale_cashier_panel_view(
            sale_cart=self.sale_cart,
            subtotal=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("0.00"),
            payment_method=self.sale_payment_combo.currentText(),
            winner_label="",
            selected_client_label=self.sale_client_combo.currentText(),
            can_sell=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
            has_cash_session=self.active_cash_session_id is not None,
            is_processing=self.sale_processing,
        )
        self.sale_feedback_label.setToolTip(panel_view.payment_tooltip)
        self.sale_context_label.setText(panel_view.context_label)
        self.sale_status_label.setText(panel_view.status_label)
        self.sale_status_label.setProperty("tone", panel_view.status_tone)
        self.sale_status_label.style().unpolish(self.sale_status_label)
        self.sale_status_label.style().polish(self.sale_status_label)
        self.sale_status_label.update()

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
                client = find_active_sale_client_by_code(session, sku)
                if client is not None:
                    if self._apply_scanned_client_to_sale(session, client, sku):
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
                            "producto_nombre": sanitize_product_display_name(variante.producto.nombre),
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

    def _change_selected_sale_item_quantity(self, delta: int) -> None:
        selected_row = self.sale_cart_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.sale_cart):
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una linea del carrito.")
            return

        selected_item = self.sale_cart[selected_row]
        current_quantity = int(selected_item.get("cantidad") or 1)
        new_quantity = current_quantity + int(delta)
        if new_quantity <= 0:
            QMessageBox.information(
                self,
                "Cantidad minima",
                "Usa 'Quitar linea' si quieres sacar por completo el articulo del carrito.",
            )
            return
        try:
            with get_session() as session:
                update_sale_cart_item_quantity(
                    session,
                    sale_cart=self.sale_cart,
                    row_index=selected_row,
                    new_quantity=new_quantity,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Cantidad no actualizada", str(exc))
            return
        self._refresh_sale_cart_table()
        self.sale_cart_table.selectRow(selected_row)

    def _handle_decrease_sale_item_quantity(self) -> None:
        self._change_selected_sale_item_quantity(-1)

    def _handle_increase_sale_item_quantity(self) -> None:
        self._change_selected_sale_item_quantity(1)

    def _handle_clear_sale_cart(self) -> None:
        self.sale_cart.clear()
        self._refresh_sale_cart_table()
        self._reset_sale_form()
        self._set_sale_feedback("Carrito limpiado.", "neutral", auto_clear_ms=1400)

    def _handle_sale_cart_item_double_click(self, item) -> None:
        if item is None or item.column() != 2:
            return
        self._handle_update_sale_item_quantity()

    def _handle_update_sale_item_quantity(self) -> None:
        selected_row = self.sale_cart_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.sale_cart):
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una linea del carrito.")
            return

        selected_item = self.sale_cart[selected_row]
        sku = str(selected_item.get("sku") or "").strip().upper()
        current_quantity = int(selected_item.get("cantidad") or 1)
        new_quantity, accepted = QInputDialog.getInt(
            self,
            "Actualizar cantidad",
            f"Cantidad para {sku}:",
            current_quantity,
            1,
            1000,
            1,
        )
        if not accepted or new_quantity == current_quantity:
            return

        try:
            with get_session() as session:
                update_sale_cart_item_quantity(
                    session,
                    sale_cart=self.sale_cart,
                    row_index=selected_row,
                    new_quantity=new_quantity,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Cantidad no actualizada", str(exc))
            return

        self._refresh_sale_cart_table()
        if 0 <= selected_row < self.sale_cart_table.rowCount():
            self.sale_cart_table.setCurrentCell(selected_row, 2)
            self.sale_cart_table.selectRow(selected_row)
        self._set_sale_feedback(
            f"{sku} actualizado a {new_quantity} pieza(s).",
            "positive",
            auto_clear_ms=1600,
        )

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
        feedback = build_quote_guard_feedback(
            "create_client",
            can_operate=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
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
        feedback = build_quote_guard_feedback(
            "add_item",
            can_operate=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        sku = self.quote_sku_input.text().strip().upper()
        if not sku:
            QMessageBox.warning(self, "Datos incompletos", "Captura un SKU antes de agregar al presupuesto.")
            return

        quantity = 1
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
        self._refresh_quote_cart_table()
        self.quote_sku_input.setFocus()

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

    def _handle_save_quote(self) -> None:
        feedback = build_quote_guard_feedback(
            "save_quote",
            can_operate=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        if not self.quote_cart:
            if self.quote_sku_input.text().strip():
                self._handle_add_quote_item()
                if not self.quote_cart:
                    return
            feedback = build_quote_guard_feedback("save_quote", has_items=bool(self.quote_cart))
            if feedback is not None:
                QMessageBox.warning(self, feedback.title, feedback.message)
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
        result_view = build_quote_result_feedback("save_quote", item_label=presupuesto_folio)
        QMessageBox.information(self, result_view.title, result_view.message)

    def _selected_quote_id(self) -> int | None:
        return resolve_selected_quote_id(self.quote_table)

    def _handle_quote_selection(self) -> None:
        self._refresh_quote_detail(self._selected_quote_id())
        self._apply_quote_action_state()
        self._refresh_permissions()

    def _apply_quote_action_state(self) -> None:
        action_state = build_quote_action_state(
            can_sell=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
            has_selection=self._selected_quote_id() is not None,
            selected_state=self.selected_quote_state,
            has_phone=bool(self.selected_quote_phone.strip()),
        )
        self.quote_cancel_button.setEnabled(action_state.cancel_enabled)
        self.quote_whatsapp_button.setEnabled(action_state.whatsapp_enabled)

    def _handle_quote_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_quotes(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de presupuestos.")

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
            "Este cambio no afecta inventario, pero el presupuesto quedara marcado como cancelado. ¿Continuar?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                cancel_quote(session, quote_id=quote_id, user_id=self.user_id)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo cancelar", str(exc))
            return
        self.refresh_all()
        result_view = build_quote_result_feedback("cancel_quote")
        QMessageBox.information(self, result_view.title, result_view.message)

    def _handle_open_quote_whatsapp(self) -> None:
        quote_id = self._selected_quote_id()
        feedback = build_quote_guard_feedback("open_whatsapp", has_selection=quote_id is not None)
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return

        assert quote_id is not None
        try:
            with get_session() as session:
                whatsapp_view = build_quote_whatsapp_view(session, quote_id=quote_id)
            normalized_phone = self._normalize_whatsapp_phone(whatsapp_view.phone_number)
            if len(normalized_phone) < 10:
                raise ValueError("El telefono del cliente no parece valido para WhatsApp.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WhatsApp no disponible", str(exc))
            return

        whatsapp_url = f"https://wa.me/{normalized_phone}?text={quote(whatsapp_view.message)}"
        if not webbrowser.open(whatsapp_url):
            QMessageBox.warning(
                self,
                "No se pudo abrir WhatsApp",
                "No se pudo abrir WhatsApp automaticamente. Verifica que tengas navegador disponible.",
            )
            return

        self.quote_status_label.setText(
            f"WhatsApp preparado para {whatsapp_view.customer_label}."
        )

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
        payment_details = collect_sale_payment_details(
            self,
            payment_method=payment_method,
            total=total,
        )
        if payment_details is None:
            return
        payment_context = build_sale_payment_note_context(
            payment_method=payment_method,
            discount_percent=discount_percent,
            applied_discount=applied_discount,
            rounding_adjustment=rounding_adjustment,
            breakdown=breakdown,
            format_discount_label=self._format_discount_label,
            payment_details=payment_details,
        )

        self._set_sale_processing(True)
        try:
            with get_session() as session:
                result = complete_sale_checkout(
                    session,
                    user_id=self.user_id,
                    folio=folio,
                    sale_cart=self.sale_cart,
                    subtotal=subtotal,
                    discount_percent=discount_percent,
                    applied_discount=applied_discount,
                    total=total,
                    selected_client_id=selected_client_id,
                    breakdown=breakdown,
                    payment_method=payment_context.payment_method,
                    note_parts=list(payment_context.note_parts),
                    build_notice=self._build_sale_loyalty_transition_notice,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            self._set_sale_processing(False)
            QMessageBox.critical(
                self,
                "Venta no completada",
                build_sale_checkout_error_message(str(exc)),
            )
            return
        finally:
            self._set_sale_processing(False)

        post_action_view = build_sale_checkout_post_action_view(
            folio=result.folio,
            total=result.total,
            payment_method=result.payment_method,
            loyalty_transition_notice=result.loyalty_transition_notice,
        )
        self._apply_sale_post_action_view(post_action_view)

    def _handle_cancel_sale(self) -> None:
        sale_id = self._selected_recent_sale_id()
        feedback = build_recent_sale_guard_feedback(
            "cancel_sale",
            has_selection=sale_id is not None,
            is_admin=self.current_role == RolUsuario.ADMIN,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        assert sale_id is not None

        try:
            with get_session() as session:
                cancel_recent_sale(session, sale_id=sale_id, admin_user_id=self.user_id)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Cancelacion fallida", str(exc))
            return

        self._apply_sale_post_action_view(build_sale_cancel_post_action_view())

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

        self._apply_inventory_qr_preview_view(
            build_available_inventory_qr_preview_view(
                sku=str(variante.sku),
                product_name=str(variante.producto.nombre),
                talla=str(variante.talla),
                color=str(variante.color),
                file_name=path.name,
            ),
            preview_path=path,
        )
        self._set_combo_value(self.inventory_variant_combo, variante_id)
        invalidate_inventory_qr_exists_cache(sku=str(variante.sku))
        self._invalidate_listing_snapshot_caches(catalog=False, inventory=True)
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
        invalidate_inventory_qr_exists_cache()
        self._invalidate_listing_snapshot_caches(catalog=False, inventory=True)
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
        self._invalidate_listing_snapshot_caches()
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
        self.status_label.setText("Estado: datos sincronizados con PostgreSQL.")

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
        catalog_access_view = build_catalog_access_view(is_admin=is_admin)
        self._apply_role_navigation()
        self.category_button.setEnabled(is_admin)
        self.brand_button.setEnabled(is_admin)
        self.inventory_category_button.setEnabled(is_admin)
        self.inventory_brand_button.setEnabled(is_admin)
        self.product_button.setEnabled(catalog_access_view.create_product_enabled)
        self.variant_button.setEnabled(catalog_access_view.create_variant_enabled)
        self.update_product_button.setEnabled(catalog_access_view.update_product_enabled)
        self.update_variant_button.setEnabled(catalog_access_view.update_variant_enabled)
        self.toggle_product_button.setEnabled(catalog_access_view.toggle_product_enabled)
        self.toggle_variant_button.setEnabled(catalog_access_view.toggle_variant_enabled)
        self.delete_product_button.setEnabled(catalog_access_view.delete_product_enabled)
        self.delete_variant_button.setEnabled(catalog_access_view.delete_variant_enabled)
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
        self.quote_qty_down_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_qty_up_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_remove_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_clear_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_refresh_button.setEnabled(can_sell)
        if self.header_more_button is not None:
            self.header_more_button.setVisible(is_admin)
        if self.connection_action is not None:
            self.connection_action.setEnabled(is_admin)
        if self.seed_action is not None:
            self.seed_action.setEnabled(is_admin)
        self.inventory_adjust_button.setEnabled(is_admin)
        layaway_action_state = build_layaway_action_state(
            can_manage_layaways=can_manage_layaways,
            can_operate_open_cash=can_operate_open_cash,
            is_admin=is_admin,
            has_selected_layaway=self._selected_layaway_id() is not None,
            has_sale_cart=bool(self.sale_cart),
        )
        self.layaway_create_button.setEnabled(layaway_action_state.create_enabled)
        self.layaway_payment_button.setEnabled(layaway_action_state.payment_enabled)
        self.layaway_deliver_button.setEnabled(layaway_action_state.deliver_enabled)
        self.layaway_cancel_button.setEnabled(layaway_action_state.cancel_enabled)
        self.layaway_receipt_button.setEnabled(layaway_action_state.receipt_enabled)
        self.layaway_sale_ticket_button.setEnabled(layaway_action_state.sale_ticket_enabled)
        self.layaway_whatsapp_button.setEnabled(layaway_action_state.whatsapp_enabled)
        self.sale_layaway_button.setEnabled(layaway_action_state.convert_sale_enabled)
        self.sale_layaway_button.setVisible(layaway_action_state.convert_sale_visible)
        self.cash_cut_button.setEnabled(can_sell)
        self.cash_movement_button.setEnabled(can_sell and has_cash_session)
        self.logout_button.setEnabled(True)
        self.sale_add_button.setEnabled(can_sell and can_operate_open_cash)
        self.sale_button.setEnabled(can_sell and can_operate_open_cash)
        self.sale_recent_button.setEnabled(True)
        self._apply_quote_action_state()
        self._apply_recent_sale_action_state()
        self.sale_remove_button.setEnabled(can_sell and can_operate_open_cash and bool(self.sale_cart))
        self.sale_clear_button.setEnabled(can_sell and can_operate_open_cash and bool(self.sale_cart))
        self.sale_layaway_button.setEnabled(can_manage_layaways and can_operate_open_cash and bool(self.sale_cart))
        self.sale_client_combo.setEnabled(False)
        self.sale_discount_combo.setEnabled(is_admin)
        if is_admin:
            self.sale_client_display_label.setToolTip(
                "El cliente visible en Caja se enlaza al escanear su QR o codigo. Por defecto la venta queda en Mostrador."
            )
            self.sale_discount_combo.setToolTip(
                "Aplica una promocion manual no acumulable. Si hay lealtad, se aplicara el mayor beneficio."
            )
        else:
            self.sale_client_display_label.setToolTip(
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
            self.products_quick_setup_box.setVisible(catalog_access_view.quick_setup_visible)

        self.catalog_permission_label.setText(catalog_access_view.permission_label)
        self.purchase_permission_label.setText(
            "" if is_admin else "Compras y carga de datos demo disponibles solo para ADMIN."
        )
        self.cancel_permission_label.setText(build_recent_sale_permission_label(is_admin=is_admin))
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
        layaway_alerts_snapshot = load_layaway_alerts_snapshot(session, today=date.today())
        manual_promo_summary = ManualPromoService.summarize_today(session, limit=4)

        is_admin = self.current_role == RolUsuario.ADMIN
        status_view = build_dashboard_status_view(
            usuarios=usuarios,
            proveedores=proveedores,
            productos=productos,
            variantes=variantes,
            stock_total=stock_total,
            compras=compras,
            ventas=ventas,
            is_admin=is_admin,
        )
        operations_view = build_dashboard_operations_view(
            ventas_confirmadas=ventas_confirmadas,
            ingresos=Decimal(ingresos),
            compras_confirmadas=Decimal(compras_confirmadas),
            stock_bajo=stock_bajo,
            is_admin=is_admin,
        )
        future_alerts_view = build_dashboard_future_alerts_view(is_admin=is_admin)
        kpi_cards_view = build_dashboard_kpi_cards_view(
            usuarios=usuarios,
            productos=productos,
            variantes=variantes,
            stock_total=stock_total,
            ventas=ventas,
            ventas_confirmadas=ventas_confirmadas,
            stock_bajo=stock_bajo,
            is_admin=is_admin,
        )

        self.metrics_label.setText(status_view.metrics_text)
        self.kpi_users_value.setText(str(usuarios))
        self.kpi_products_value.setText(str(productos))
        self.kpi_stock_value.setText(str(stock_total))
        self.kpi_sales_value.setText(str(ventas))
        self.dashboard_users_context_label.setText(kpi_cards_view.users.detail_text)
        self.dashboard_products_context_label.setText(kpi_cards_view.products.detail_text)
        self.dashboard_stock_context_label.setText(kpi_cards_view.stock.detail_text)
        self.dashboard_sales_context_label.setText(kpi_cards_view.sales.detail_text)
        self.analytics_label.setText(operations_view.primary_text)
        self.dashboard_operations_label.setText(operations_view.secondary_text)
        try:
            automatic_backup_status = read_automatic_backup_status(backup_output_dir())
        except Exception:  # noqa: BLE001
            automatic_backup_status = None
        operational_alerts = build_analytics_operational_alerts(
            stock_critical_count=stock_bajo,
            overdue_layaways=layaway_alerts_snapshot.overdue_count,
            automatic_backup_status=automatic_backup_status,
            now=datetime.now(),
        )
        dashboard_alerts_view = build_dashboard_operational_alerts_view(operational_alerts)
        self.dashboard_operational_alerts_label.setText(dashboard_alerts_view.text)
        self.dashboard_operational_alerts_label.setProperty("tone", dashboard_alerts_view.tone)
        self.dashboard_future_alerts_label.setText(
            f"{future_alerts_view.title_text}\n{future_alerts_view.body_text}"
        )
        self.dashboard_future_alerts_label.setProperty("tone", "neutral")
        layaway_alerts_view = build_layaway_alerts_view(
            overdue_count=layaway_alerts_snapshot.overdue_count,
            due_today_count=layaway_alerts_snapshot.due_today_count,
            due_week_count=layaway_alerts_snapshot.due_week_count,
        )
        self.layaway_alerts_label.setTextFormat(Qt.TextFormat.RichText)
        self.layaway_alerts_label.setText(layaway_alerts_view.alerts_rich_text)
        for card, tone in (
            (self.dashboard_users_card, kpi_cards_view.users.tone),
            (self.dashboard_products_card, kpi_cards_view.products.tone),
            (self.dashboard_stock_card, kpi_cards_view.stock.tone),
            (self.dashboard_sales_card, kpi_cards_view.sales.tone),
        ):
            if card is None:
                continue
            card.setProperty("tone", tone)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
        for label, tone in (
            (self.dashboard_users_context_label, kpi_cards_view.users.tone),
            (self.dashboard_products_context_label, kpi_cards_view.products.tone),
            (self.dashboard_stock_context_label, kpi_cards_view.stock.tone),
            (self.dashboard_sales_context_label, kpi_cards_view.sales.tone),
        ):
            label.setProperty("tone", tone)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()
        for label, tone in (
            (self.dashboard_operational_alerts_label, dashboard_alerts_view.tone),
            (self.dashboard_future_alerts_label, "neutral"),
        ):
            label.setProperty("tone", tone)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()
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

    def _invalidate_listing_snapshot_caches(
        self,
        *,
        catalog: bool = True,
        inventory: bool = True,
    ) -> None:
        if catalog:
            self.catalog_snapshot_cache.invalidate()
        if inventory:
            self.inventory_snapshot_cache.invalidate()

    def _load_catalog_snapshot_rows(self, session=None) -> list[dict[str, object]]:
        def loader() -> list[dict[str, object]]:
            if session is not None:
                return load_catalog_snapshot_rows(session)
            with get_session() as local_session:
                return load_catalog_snapshot_rows(local_session)

        return self.catalog_snapshot_cache.get_or_load(loader)

    def _load_inventory_snapshot_rows(self, session=None) -> list[dict[str, object]]:
        def loader() -> list[dict[str, object]]:
            if session is not None:
                return load_inventory_snapshot_rows(session)
            with get_session() as local_session:
                return load_inventory_snapshot_rows(local_session)

        return self.inventory_snapshot_cache.get_or_load(loader)

    def _refresh_catalog(self, session=None) -> None:
        selected_variant_id = None
        if self.catalog_preserve_selection_on_refresh:
            selected_row = self.catalog_table.currentRow()
            if 0 <= selected_row < len(self.catalog_rows):
                selected_variant_id = int(self.catalog_rows[selected_row]["variante_id"])
        self.catalog_preserve_selection_on_refresh = True

        catalog_snapshot_rows = self._load_catalog_snapshot_rows(session)

        search_text = self.catalog_search_input.text().strip()
        search_terms = compile_search_terms(search_text)
        school_scope_filter = str(self.catalog_school_scope_filter_combo.currentData() or "")
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

        self.catalog_filtered_rows = filter_visible_catalog_rows(
            catalog_snapshot_rows,
            filters=CatalogVisibleFilterState(
                search_text=search_text,
                school_scope_filter=school_scope_filter,
                category_filters=tuple(category_filters),
                brand_filters=tuple(brand_filters),
                school_filters=tuple(school_filters),
                type_filters=tuple(type_filters),
                piece_filters=tuple(piece_filters),
                size_filters=tuple(size_filters),
                color_filters=tuple(color_filters),
                status_filter=status_filter,
                stock_filter=stock_filter,
                layaway_filter=catalog_filter,
                origin_filter=origin_filter,
                duplicate_filter=duplicate_filter,
            ),
            search_matcher=lambda row, _search_text: row_matches_search(
                row,
                search_text=search_text,
                search_terms=search_terms,
                alias_map=CATALOG_SEARCH_ALIAS_MAP,
                general_fields=CATALOG_SEARCH_GENERAL_FIELDS,
            ),
        )

        if selected_variant_id is not None:
            selected_filtered_index = find_catalog_row_index_by_variant_id(
                self.catalog_filtered_rows,
                selected_variant_id,
            )
            if selected_filtered_index is not None:
                self.catalog_page_index = selected_filtered_index // CATALOG_PAGE_SIZE

        pagination_view = build_catalog_pagination_view(
            self.catalog_filtered_rows,
            current_page_index=self.catalog_page_index,
            page_size=CATALOG_PAGE_SIZE,
        )
        self.catalog_page_index = pagination_view.current_page_index
        self.catalog_rows = pagination_view.page_rows

        table_row_views = build_catalog_table_row_views(self.catalog_rows)
        self._reload_table_widget(
            self.catalog_table,
            row_count=len(table_row_views),
            populate_rows=lambda: self._populate_catalog_table_rows(table_row_views),
        )
        active_filter_labels = self._catalog_active_filter_labels()
        catalog_summary_view = build_catalog_summary_view(
            total_rows=len(catalog_snapshot_rows),
            visible_rows=self.catalog_filtered_rows,
            active_filter_labels=active_filter_labels,
        )
        self.catalog_results_label.setText(catalog_summary_view.results_summary)
        self.catalog_active_filters_label.setText(catalog_summary_view.active_filters_summary)
        self.catalog_pagination_label.setText(pagination_view.page_label)
        self.catalog_previous_page_button.setEnabled(pagination_view.previous_enabled)
        self.catalog_next_page_button.setEnabled(pagination_view.next_enabled)
        if selected_variant_id is not None and not self._select_catalog_variant(selected_variant_id):
            self._clear_catalog_editor()
        elif selected_variant_id is None:
            self._clear_catalog_editor()

    @staticmethod
    def _reload_table_widget(
        table: QTableWidget,
        *,
        row_count: int,
        populate_rows: Callable[[], None],
    ) -> None:
        previous_updates_enabled = table.updatesEnabled()
        previous_signals_blocked = table.blockSignals(True)
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(row_count)
            populate_rows()
        finally:
            table.blockSignals(previous_signals_blocked)
            table.setUpdatesEnabled(previous_updates_enabled)
            table.viewport().update()

    def _populate_catalog_table_rows(self, table_row_views) -> None:
        for row_index, row_view in enumerate(table_row_views):
            for column_index, value in enumerate(row_view.values):
                self.catalog_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None:
                for column_index in range(len(row_view.values)):
                    item = self.catalog_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row_view.row_tone)
            stock_item = self.catalog_table.item(row_index, 9)
            layaway_item = self.catalog_table.item(row_index, 10)
            status_item = self.catalog_table.item(row_index, 11)
            if stock_item is not None:
                _set_table_badge_style(stock_item, row_view.stock_tone)
            if layaway_item is not None and row_view.layaway_tone is not None:
                _set_table_badge_style(layaway_item, row_view.layaway_tone)
            if status_item is not None:
                _set_table_badge_style(status_item, row_view.status_tone)

    def _handle_catalog_previous_page(self) -> None:
        if self.catalog_page_index <= 0:
            return
        self.catalog_page_index -= 1
        self.catalog_preserve_selection_on_refresh = False
        self._handle_catalog_filters_changed()

    def _handle_catalog_next_page(self) -> None:
        self.catalog_page_index += 1
        self.catalog_preserve_selection_on_refresh = False
        self._handle_catalog_filters_changed()

    @staticmethod
    def _catalog_search_alias_map() -> dict[str, tuple[str, ...]]:
        return CATALOG_SEARCH_ALIAS_MAP

    @classmethod
    def _catalog_row_matches_search(cls, row: dict[str, object], search_text: str) -> bool:
        return row_matches_search(
            row,
            search_text=search_text,
            alias_map=cls._catalog_search_alias_map(),
            general_fields=CATALOG_SEARCH_GENERAL_FIELDS,
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
                ("seccion", self.catalog_school_scope_filter_combo.currentData(), self.catalog_school_scope_filter_combo.currentText()),
                ("estado", self.catalog_status_filter_combo.currentData(), self.catalog_status_filter_combo.currentText()),
                ("stock", self.catalog_stock_filter_combo.currentData(), self.catalog_stock_filter_combo.currentText()),
                ("apartados", self.catalog_layaway_filter_combo.currentData(), self.catalog_layaway_filter_combo.currentText()),
                ("origen", self.catalog_origin_filter_combo.currentData(), self.catalog_origin_filter_combo.currentText()),
                ("incidencias", self.catalog_duplicate_filter_combo.currentData(), self.catalog_duplicate_filter_combo.currentText()),
            ),
        )

    @staticmethod
    def _inventory_search_alias_map() -> dict[str, tuple[str, ...]]:
        return INVENTORY_SEARCH_ALIAS_MAP

    @classmethod
    def _inventory_row_matches_search(cls, row: dict[str, object], search_text: str) -> bool:
        return row_matches_search(
            row,
            search_text=search_text,
            alias_map=cls._inventory_search_alias_map(),
            general_fields=INVENTORY_SEARCH_GENERAL_FIELDS,
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

    def _refresh_combos(self, session) -> None:
        categorias = session.scalars(select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)).all()
        marcas = session.scalars(select(Marca).where(Marca.activo.is_(True)).order_by(Marca.nombre)).all()
        escuelas = session.scalars(select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)).all()
        tipos_prenda = session.scalars(select(TipoPrenda).where(TipoPrenda.activo.is_(True)).order_by(TipoPrenda.nombre)).all()
        tipos_pieza = session.scalars(select(TipoPieza).where(TipoPieza.activo.is_(True)).order_by(TipoPieza.nombre)).all()
        tallas = sort_size_options(session.execute(select(Variante.talla).distinct()).scalars().all())
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
        self.catalog_size_filter_combo.set_items([(talla, talla) for talla in tallas])
        self.catalog_color_filter_combo.set_items([(str(color), str(color)) for color in colores if color])
        self.inventory_category_filter_combo.set_items([(categoria.nombre, categoria.nombre) for categoria in categorias])
        self.inventory_brand_filter_combo.set_items([(marca.nombre, marca.nombre) for marca in marcas])
        self.inventory_school_filter_combo.set_items([(escuela.nombre, escuela.nombre) for escuela in escuelas])
        self.inventory_type_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_prenda])
        self.inventory_piece_filter_combo.set_items([(tipo.nombre, tipo.nombre) for tipo in tipos_pieza])
        self.inventory_size_filter_combo.set_items([(talla, talla) for talla in tallas])
        self.inventory_color_filter_combo.set_items([(str(color), str(color)) for color in colores if color])
        self._populate_combo(
            self.variant_product_combo,
            [
                (
                    f"{sanitize_product_display_name(producto.nombre)} | {producto.marca.nombre}",
                    producto.id,
                )
                for producto in productos
            ],
        )
        self._populate_combo(
            self.edit_variant_product_combo,
            [
                (
                    f"{sanitize_product_display_name(producto.nombre)} | {producto.marca.nombre}",
                    producto.id,
                )
                for producto in productos
            ],
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
        self._refresh_sale_client_display()
        self._refresh_sale_discount_options()
        self.quote_client_combo.blockSignals(True)
        self.quote_client_combo.clear()
        self.quote_client_combo.addItem("Sin cliente asignado", None)
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
            (
                f"{variante.sku} | {sanitize_product_display_name(variante.producto.nombre)} | "
                f"stock {variante.stock_actual}",
                variante.id,
            )
            for variante in variantes_activas
        ]
        inventory_variant_items = [
            (
                f"{variante.sku} | {sanitize_product_display_name(variante.producto.nombre)} | "
                f"stock {variante.stock_actual}",
                variante.id,
            )
            for variante in variantes_inventario
        ]
        self._populate_combo(self.purchase_variant_combo, purchase_variant_items)
        self._populate_combo(self.inventory_variant_combo, inventory_variant_items)
        self._refresh_catalog_section_controls()
        self._refresh_selected_qr_preview()

    def _refresh_sales_table(self, session) -> None:
        row_views = build_recent_sale_table_row_views(list_recent_sale_rows(session, limit=20))
        self.recent_sales_table.setRowCount(len(row_views))
        for row_index, row_view in enumerate(row_views):
            for column_index, value in enumerate(row_view.values):
                self.recent_sales_table.setItem(row_index, column_index, _table_item(value))
        self.recent_sales_table.resizeColumnsToContents()
        self._apply_recent_sale_action_state()
        self._refresh_sale_cart_table()

    def _refresh_quotes(self, session) -> None:
        selected_quote_id = self._selected_quote_id()
        search_text = self.quote_search_input.text().strip().lower()
        state_filter = str(self.quote_state_combo.currentData() or "")
        quote_snapshots = build_quote_history_input_rows(load_quote_snapshot_rows(session, limit=200))
        rows = build_quote_history_rows(
            quote_snapshots=quote_snapshots,
            search_text=search_text,
            state_filter=state_filter,
        )
        quote_summary_view = build_quote_summary_view(
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
            self.quote_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row_view.quote_id)
            status_item = self.quote_table.item(row_index, 2)
            total_item = self.quote_table.item(row_index, 3)
            if status_item is not None:
                _set_table_badge_style(status_item, row_view.status_tone)
            if total_item is not None:
                _set_table_badge_style(total_item, row_view.total_tone)
        self.quote_table.resizeColumnsToContents()
        self.quote_status_label.setText(quote_summary_view.status_label)
        self._apply_quote_action_state()

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
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            detail_view = build_empty_quote_detail_view()
            self._apply_quote_detail_view(detail_view)
            self._apply_quote_action_state()
            return

        try:
            with get_session() as session:
                quote_snapshot = load_quote_detail_snapshot(session, quote_id=quote_id)
                self.selected_quote_state = str(quote_snapshot.status_label)
                self.selected_quote_phone = (
                    ""
                    if str(quote_snapshot.phone_text).strip().lower() == "sin telefono"
                    else str(quote_snapshot.phone_text).strip()
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
        except Exception as exc:  # noqa: BLE001
            self.selected_quote_state = ""
            self.selected_quote_phone = ""
            detail_view = build_error_quote_detail_view(str(exc))
            self._apply_quote_detail_view(detail_view)
        self._apply_quote_action_state()

    def _apply_quote_detail_view(self, detail_view) -> None:
        self.quote_customer_label.setText(detail_view.customer_label)
        self.quote_meta_label.setText(detail_view.meta_label)
        self.quote_notes_label.setText(detail_view.notes_label)
        self.quote_detail_table.setRowCount(len(detail_view.detail_rows))
        for row_index, detalle in enumerate(detail_view.detail_rows):
            values = [
                detalle.sku,
                detalle.description,
                detalle.quantity,
                detalle.unit_price,
                detalle.subtotal,
            ]
            for column_index, value in enumerate(values):
                self.quote_detail_table.setItem(row_index, column_index, _table_item(value))
        self.quote_detail_table.resizeColumnsToContents()

    def _refresh_inventory_table(self, session=None) -> None:
        current_variant_id = self.inventory_variant_combo.currentData()
        inventory_snapshot_rows = self._load_inventory_snapshot_rows(session)

        search_text = self.inventory_search_input.text().strip()
        search_terms = compile_search_terms(search_text)
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

        self.inventory_filtered_rows = filter_visible_inventory_rows(
            inventory_snapshot_rows,
            filters=InventoryVisibleFilterState(
                search_text=search_text,
                category_filters=tuple(category_filters),
                brand_filters=tuple(brand_filters),
                school_filters=tuple(school_filters),
                type_filters=tuple(type_filters),
                piece_filters=tuple(piece_filters),
                size_filters=tuple(size_filters),
                color_filters=tuple(color_filters),
                status_filter=status_filter,
                stock_filter=stock_filter,
                qr_filter=qr_filter,
                origin_filter=origin_filter,
                duplicate_filter=duplicate_filter,
            ),
            search_matcher=lambda row, _search_text: row_matches_search(
                row,
                search_text=search_text,
                search_terms=search_terms,
                alias_map=INVENTORY_SEARCH_ALIAS_MAP,
                general_fields=INVENTORY_SEARCH_GENERAL_FIELDS,
            ),
        )

        summary_view = build_inventory_summary_view(
            total_rows=len(inventory_snapshot_rows),
            visible_rows=self.inventory_filtered_rows,
            active_filter_labels=self._inventory_active_filter_labels(),
        )
        self._set_badge_state(self.inventory_out_counter, summary_view.out_counter.text, summary_view.out_counter.tone)
        self._set_badge_state(self.inventory_low_counter, summary_view.low_counter.text, summary_view.low_counter.tone)
        self._set_badge_state(
            self.inventory_qr_pending_counter,
            summary_view.qr_pending_counter.text,
            summary_view.qr_pending_counter.tone,
        )
        self._set_badge_state(
            self.inventory_inactive_counter,
            summary_view.inactive_counter.text,
            summary_view.inactive_counter.tone,
        )

        pagination_view = build_catalog_pagination_view(
            self.inventory_filtered_rows,
            current_page_index=self.inventory_page_index,
            page_size=INVENTORY_PAGE_SIZE,
        )
        self.inventory_page_index = pagination_view.current_page_index
        self.inventory_rows = pagination_view.page_rows
        table_row_views = build_inventory_table_row_views(self.inventory_rows)
        self._reload_table_widget(
            self.inventory_table,
            row_count=len(table_row_views),
            populate_rows=lambda: self._populate_inventory_table_rows(table_row_views),
        )
        self.inventory_results_label.setText(summary_view.results_summary)
        self.inventory_active_filters_label.setText(self._build_inventory_active_filters_summary())
        self.inventory_pagination_label.setText(pagination_view.page_label)
        self.inventory_previous_page_button.setEnabled(pagination_view.previous_enabled)
        self.inventory_next_page_button.setEnabled(pagination_view.next_enabled)
        self._sync_inventory_table_selection(current_variant_id)
        self._refresh_inventory_overview()

    def _populate_inventory_table_rows(self, table_row_views) -> None:
        for row_index, row_view in enumerate(table_row_views):
            for column_index, value in enumerate(row_view.values):
                self.inventory_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None:
                for column_index in range(len(row_view.values)):
                    item = self.inventory_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row_view.row_tone)
            self.inventory_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row_view.variant_id)
            stock_item = self.inventory_table.item(row_index, 4)
            committed_item = self.inventory_table.item(row_index, 5)
            status_item = self.inventory_table.item(row_index, 6)
            qr_item = self.inventory_table.item(row_index, 7)
            if stock_item is not None:
                _set_table_badge_style(stock_item, row_view.stock_tone)
            if committed_item is not None and row_view.committed_tone is not None:
                _set_table_badge_style(committed_item, row_view.committed_tone)
            if status_item is not None:
                _set_table_badge_style(status_item, row_view.status_tone)
            if qr_item is not None:
                _set_table_badge_style(qr_item, row_view.qr_tone)

    def _schedule_inventory_filter_refresh(self) -> None:
        self.inventory_filter_debounce_timer.start()

    def _schedule_inventory_filter_refresh_reset_page(self) -> None:
        self.inventory_page_index = 0
        self._schedule_inventory_filter_refresh()

    def _run_inventory_filter_refresh(self) -> None:
        try:
            self._refresh_inventory_table()
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de inventario.")

    def _handle_inventory_filters_changed(self) -> None:
        if self.inventory_filter_debounce_timer.isActive():
            self.inventory_filter_debounce_timer.stop()
        self._run_inventory_filter_refresh()

    def _handle_inventory_filters_changed_reset_page(self) -> None:
        self.inventory_page_index = 0
        self._handle_inventory_filters_changed()

    def _handle_clear_inventory_filters(self) -> None:
        self.inventory_page_index = 0
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

    def _handle_inventory_previous_page(self) -> None:
        if self.inventory_page_index <= 0:
            return
        self.inventory_page_index -= 1
        self._handle_inventory_filters_changed()

    def _handle_inventory_next_page(self) -> None:
        self.inventory_page_index += 1
        self._handle_inventory_filters_changed()

    def _analytics_period_bounds(self) -> tuple[datetime, datetime]:
        return resolve_analytics_period_bounds(
            self.analytics_period_combo.currentData(),
            today=date.today(),
            manual_from=self.analytics_from_input.date().toPyDate(),
            manual_to=self.analytics_to_input.date().toPyDate(),
        )

    def _apply_analytics_quick_period(self, period_key: str) -> None:
        for index in range(self.analytics_period_combo.count()):
            if self.analytics_period_combo.itemData(index) == period_key:
                self.analytics_period_combo.setCurrentIndex(index)
                return

    def _handle_analytics_period_changed(self) -> None:
        is_manual = is_manual_analytics_period(self.analytics_period_combo.currentData())
        self.analytics_from_input.setEnabled(is_manual)
        self.analytics_to_input.setEnabled(is_manual)
        try:
            with get_session() as session:
                self._refresh_analytics(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudo refrescar la analitica.")

    def _refresh_analytics(self, session) -> None:
        period_start, period_end = self._analytics_period_bounds()
        previous_period_start, previous_period_end = resolve_previous_analytics_period_bounds(
            period_start=period_start,
            period_end=period_end,
        )
        selected_client_id = self.analytics_client_combo.currentData()
        sales = load_confirmed_sales_for_analytics(
            session,
            period_start=period_start,
            period_end=period_end,
            selected_client_id=selected_client_id,
        )
        previous_sales = load_confirmed_sales_for_analytics(
            session,
            period_start=previous_period_start,
            period_end=previous_period_end,
            selected_client_id=selected_client_id,
        )
        sales_snapshot = build_analytics_sales_snapshot(sales)
        previous_snapshot = build_analytics_sales_snapshot(previous_sales)
        trend_view = build_analytics_summary_trend_view(sales_snapshot, previous_snapshot)
        self.analytics_sales_value.setText(f"${sales_snapshot.total_sales}")
        self.analytics_sales_context_label.setText(trend_view.sales.text)
        self.analytics_tickets_value.setText(str(sales_snapshot.total_tickets))
        self.analytics_tickets_context_label.setText(trend_view.tickets.text)
        self.analytics_average_value.setText(f"${sales_snapshot.average_ticket}")
        self.analytics_average_context_label.setText(trend_view.average.text)
        self.analytics_units_value.setText(str(sales_snapshot.total_units))
        self.analytics_units_context_label.setText(trend_view.units.text)
        self.analytics_identified_sales_value.setText(str(sales_snapshot.identified_sales_count))
        self.analytics_identified_income_value.setText(f"${sales_snapshot.identified_income}")
        self.analytics_repeat_clients_value.setText(str(sales_snapshot.repeat_clients))
        self.analytics_average_client_value.setText(f"${sales_snapshot.average_per_client}")
        for label, tone in (
            (self.analytics_sales_context_label, trend_view.sales.tone),
            (self.analytics_tickets_context_label, trend_view.tickets.tone),
            (self.analytics_average_context_label, trend_view.average.tone),
            (self.analytics_units_context_label, trend_view.units.tone),
        ):
            label.setProperty("tone", tone)
            label.setObjectName("kpiSubtitle")
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

        payment_rows = build_analytics_payment_rows(sales)
        self.analytics_payment_table.setRowCount(len(payment_rows))
        for row_index, row in enumerate(payment_rows):
            for column_index, value in enumerate(row.values):
                self.analytics_payment_table.setItem(row_index, column_index, _table_item(value))
            if row.row_tone is not None:
                for column_index in range(len(row.values)):
                    item = self.analytics_payment_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row.row_tone)
            sales_item = self.analytics_payment_table.item(row_index, 1)
            amount_item = self.analytics_payment_table.item(row_index, 2)
            if sales_item is not None:
                _set_table_badge_style(sales_item, row.sales_tone)
            if amount_item is not None:
                _set_table_badge_style(amount_item, row.amount_tone)

        top_product_snapshot_rows = load_analytics_top_product_snapshot_rows(
            session,
            period_start=period_start,
            period_end=period_end,
            selected_client_id=selected_client_id,
        )
        top_product_rows = build_analytics_top_product_rows(top_product_snapshot_rows)
        self.top_products_table.setRowCount(len(top_product_rows))
        for row_index, row_view in enumerate(top_product_rows):
            for column_index, value in enumerate(row_view.values):
                self.top_products_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None:
                for column_index in range(len(row_view.values)):
                    item = self.top_products_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row_view.row_tone)
            units_item = self.top_products_table.item(row_index, 2)
            revenue_item = self.top_products_table.item(row_index, 3)
            if units_item is not None:
                _set_table_badge_style(units_item, row_view.units_tone)
            if revenue_item is not None:
                _set_table_badge_style(revenue_item, row_view.revenue_tone)

        top_client_snapshot_rows = load_analytics_top_client_snapshot_rows(
            session,
            period_start=period_start,
            period_end=period_end,
            selected_client_id=selected_client_id,
        )
        top_client_row_views = build_analytics_top_client_row_views(top_client_snapshot_rows)
        self.analytics_clients_table.setRowCount(len(top_client_row_views))
        for row_index, row_view in enumerate(top_client_row_views):
            for column_index, value in enumerate(row_view.values):
                self.analytics_clients_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None:
                for column_index in range(len(row_view.values)):
                    item = self.analytics_clients_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row_view.row_tone)
            sales_item = self.analytics_clients_table.item(row_index, 2)
            amount_item = self.analytics_clients_table.item(row_index, 3)
            if sales_item is not None:
                _set_table_badge_style(sales_item, row_view.sales_tone)
            if amount_item is not None:
                _set_table_badge_style(amount_item, row_view.amount_tone)

        layaway_snapshot = load_analytics_layaway_snapshot(
            session,
            period_start=period_start,
            period_end=period_end,
        )
        layaway_labels_view = build_analytics_layaway_labels_view(
            active_count=layaway_snapshot.active_count,
            pending_balance=layaway_snapshot.pending_balance,
            overdue_count=layaway_snapshot.overdue_count,
            delivered_in_period=layaway_snapshot.delivered_in_period,
        )
        self.analytics_layaway_active_label.setText(layaway_labels_view.active.text)
        self.analytics_layaway_balance_label.setText(layaway_labels_view.balance.text)
        self.analytics_layaway_overdue_label.setText(layaway_labels_view.overdue.text)
        self.analytics_layaway_delivered_label.setText(layaway_labels_view.delivered.text)
        layaway_label_states = (
            (self.analytics_layaway_active_label, layaway_labels_view.active.tone),
            (self.analytics_layaway_balance_label, layaway_labels_view.balance.tone),
            (self.analytics_layaway_overdue_label, layaway_labels_view.overdue.tone),
            (self.analytics_layaway_delivered_label, layaway_labels_view.delivered.tone),
        )
        for label, tone in layaway_label_states:
            label.setProperty("tone", tone)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

        stock_snapshot_rows = load_analytics_stock_snapshot_rows(session)
        stock_row_views = build_analytics_stock_row_views(stock_snapshot_rows)
        self.analytics_stock_table.setRowCount(len(stock_row_views))
        for row_index, row_view in enumerate(stock_row_views):
            for column_index, value in enumerate(row_view.values):
                self.analytics_stock_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None:
                for column_index in range(len(row_view.values)):
                    item = self.analytics_stock_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_row_tint(item, row_view.row_tone)
            stock_item = self.analytics_stock_table.item(row_index, 2)
            reserved_item = self.analytics_stock_table.item(row_index, 3)
            state_item = self.analytics_stock_table.item(row_index, 4)
            if stock_item is not None:
                _set_table_badge_style(stock_item, row_view.stock_tone)
            if reserved_item is not None:
                _set_table_badge_style(reserved_item, row_view.reserved_tone)
            if state_item is not None:
                _set_table_badge_style(state_item, row_view.state_tone)
        automatic_backup_status: AutomaticBackupStatus | None
        try:
            automatic_backup_status = read_automatic_backup_status(backup_output_dir())
        except Exception:  # noqa: BLE001
            automatic_backup_status = None
        alerts = build_analytics_operational_alerts(
            stock_critical_count=len(stock_row_views),
            overdue_layaways=layaway_snapshot.overdue_count,
            automatic_backup_status=automatic_backup_status,
            now=datetime.now(),
        )
        self.analytics_alerts_label.setText(build_analytics_alerts_text(alerts))
        self.analytics_export_status_label.setText(
            build_analytics_export_status_text(
                selected_client_id=selected_client_id,
                selected_client_label=self.analytics_client_combo.currentText(),
            )
        )

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
                                    sanitize_product_display_name(detalle.variante.producto.nombre)
                                    if detalle.variante is not None and detalle.variante.producto is not None
                                    else None
                                ),
                                "cantidad": detalle.cantidad,
                                "precio_unitario": detalle.precio_unitario,
                                "subtotal_linea": detalle.subtotal_linea,
                            }
                        )

                top_products_rows = build_table_export_rows(
                    self.top_products_table,
                    (
                        ("sku", 0),
                        ("producto", 1),
                        ("unidades_vendidas", 2),
                        ("ingreso", 3),
                    ),
                )
                top_clients_rows = build_table_export_rows(
                    self.analytics_clients_table,
                    (
                        ("cliente", 0),
                        ("codigo_cliente", 1),
                        ("ventas", 2),
                        ("monto", 3),
                    ),
                )
                payment_rows = build_table_export_rows(
                    self.analytics_payment_table,
                    (
                        ("metodo", 0),
                        ("ventas", 1),
                        ("monto", 2),
                    ),
                )
                stock_rows = build_table_export_rows(
                    self.analytics_stock_table,
                    (
                        ("sku", 0),
                        ("producto", 1),
                        ("stock", 2),
                        ("apartado", 3),
                        ("estado", 4),
                    ),
                )
                movement_rows = [
                    {
                        "fecha": movimiento.created_at,
                        "sku": movimiento.variante.sku if movimiento.variante is not None else None,
                        "producto": (
                            sanitize_product_display_name(movimiento.variante.producto.nombre)
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
                                    sanitize_product_display_name(detalle.variante.producto.nombre)
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

                layaway_rows = build_analytics_layaway_export_rows(
                    active_text=self.analytics_layaway_active_label.text(),
                    pending_balance_text=self.analytics_layaway_balance_label.text(),
                    overdue_text=self.analytics_layaway_overdue_label.text(),
                    delivered_text=self.analytics_layaway_delivered_label.text(),
                )
                summary_rows = build_analytics_summary_export_rows(
                    period_label=self.analytics_period_combo.currentText(),
                    client_label="todos"
                    if selected_client_id in {None, ""}
                    else self.analytics_client_combo.currentText(),
                    total_sales=self.analytics_sales_value.text(),
                    total_tickets=self.analytics_tickets_value.text(),
                    average_ticket=self.analytics_average_value.text(),
                    total_units=self.analytics_units_value.text(),
                )

                export_sets = [
                    ("00_resumen_general", summary_rows),
                    ("01_metodos_pago", payment_rows),
                    ("02_apartados_resumen", layaway_rows),
                    ("03_top_productos", top_products_rows),
                    ("04_top_clientes", top_clients_rows),
                    ("05_stock_critico", stock_rows),
                    ("06_ventas", sales_rows),
                    ("07_detalle_ventas", detail_rows),
                    ("08_movimientos", movement_rows),
                    ("09_compras", purchase_rows),
                    ("10_detalle_compras", purchase_detail_rows),
                    ("11_cortes_caja", cash_cut_rows),
                ]

                export_dir = self._analytics_export_dir() / datetime.now().strftime("%Y%m%d_%H%M%S")
                export_dir.mkdir(parents=True, exist_ok=True)
                for name, rows in export_sets:
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
        filter_state = build_history_filter_state(
            source_filter=self.history_source_combo.currentData(),
            entity_filter=self.history_entity_combo.currentData(),
            sku_filter=self.history_sku_input.text(),
            type_filter=self.history_type_combo.currentData(),
            source_filter_text=self.history_source_combo.currentText(),
            entity_filter_text=self.history_entity_combo.currentText(),
            type_filter_text=self.history_type_combo.currentText(),
            from_date=self.history_from_input.date().toPyDate(),
            to_date=self.history_to_input.date().toPyDate(),
            minimum_date=self.history_from_input.minimumDate().toPyDate(),
        )
        rows = load_history_snapshot_rows(
            session,
            filters=HistorySnapshotFilters(
                source_filter=filter_state.source_filter,
                entity_filter=filter_state.entity_filter,
                sku_filter=filter_state.sku_filter,
                type_filter=filter_state.type_filter,
                start_datetime=filter_state.date_range.start_datetime,
                end_datetime=filter_state.date_range.end_datetime,
            ),
        )
        history_rows = build_history_table_rows(rows)
        self.history_rows = [row.source_row for row in history_rows]

        self.movements_table.setRowCount(len(history_rows))
        for row_index, row in enumerate(history_rows):
            for column_index, value in enumerate(row.values):
                item = _table_item(value)
                if column_index == 1:
                    _set_table_badge_style(item, row.source_tone)
                elif column_index == 3:
                    _set_table_badge_style(item, row.type_tone)
                elif column_index in {4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row.row_tone != "muted":
                    _set_table_row_tint(item, row.row_tone)
                self.movements_table.setItem(row_index, column_index, item)
        self.movements_table.resizeColumnsToContents()
        header = self.movements_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        history_summary = build_history_summary_view(
            visible_count=len(history_rows),
            search_text=filter_state.sku_filter,
            source_filter_value=filter_state.source_filter,
            source_filter_text=filter_state.source_filter_text,
            entity_filter_value=filter_state.entity_filter,
            entity_filter_text=filter_state.entity_filter_text,
            type_filter_value=filter_state.type_filter,
            type_filter_text=filter_state.type_filter_text,
            date_from_label=filter_state.date_range.start_date_label,
            date_to_label=filter_state.date_range.end_date_label,
        )
        self.history_status_label.setText(history_summary.status_label)
        self._refresh_history_detail()

    def _refresh_history_detail(self) -> None:
        selected_row = self.movements_table.currentRow()
        source_row = self.history_rows[selected_row] if 0 <= selected_row < len(self.history_rows) else None
        detail_view = build_history_detail_view(source_row)
        self.history_detail_summary_label.setText(detail_view.summary_label)
        self.history_detail_meta_label.setText(detail_view.meta_label)
        self.history_detail_change_label.setText(detail_view.change_label)
        self.history_detail_notes_label.setText(detail_view.notes_label)

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
            return (format_display_date(commitment), "muted")
        today = date.today()
        due_date = commitment.date()
        if due_date < today:
            return (f"Vencido desde {format_display_date(due_date)}", "danger")
        if due_date == today:
            return ("Vence hoy", "warning")
        if due_date <= today + timedelta(days=7):
            return (f"Vence {format_display_date(due_date)}", "warning")
        return (f"Vence {format_display_date(due_date)}", "positive")

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

    def _get_whatsapp_templates(self) -> dict[str, str]:
        defaults = build_default_settings_whatsapp_templates()
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                return resolve_settings_whatsapp_templates(
                    config,
                    default_templates=defaults,
                )
        except Exception:
            return defaults

    def _refresh_whatsapp_preview(self) -> None:
        template_key = str(self.settings_whatsapp_preview_combo.currentData() or "layaway_reminder")
        template_map = build_settings_whatsapp_template_map(
            layaway_reminder=self.settings_whatsapp_layaway_reminder_input.toPlainText(),
            layaway_liquidated=self.settings_whatsapp_layaway_liquidated_input.toPlainText(),
            client_promotion=self.settings_whatsapp_client_promotion_input.toPlainText(),
            client_followup=self.settings_whatsapp_client_followup_input.toPlainText(),
            client_greeting=self.settings_whatsapp_client_greeting_input.toPlainText(),
        )
        self.settings_whatsapp_preview_output.setPlainText(
            build_settings_whatsapp_preview_text(
                template_key=template_key,
                template_map=template_map,
                default_templates=build_default_settings_whatsapp_templates(),
            )
        )

    def _handle_reset_whatsapp_templates(self) -> None:
        defaults = build_default_settings_whatsapp_templates()
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
            format_display_date(apartado.fecha_compromiso)
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
            return render_settings_whatsapp_template(templates["layaway_liquidated"], values)
        return render_settings_whatsapp_template(templates["layaway_reminder"], values)

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
        self._refresh_catalog_section_controls()
        if self.catalog_filter_debounce_timer.isActive():
            self.catalog_filter_debounce_timer.stop()
        self._run_catalog_filter_refresh()

    def _handle_catalog_filters_changed_reset_page(self) -> None:
        self.catalog_page_index = 0
        self._handle_catalog_filters_changed()

    def _schedule_catalog_filter_refresh(self) -> None:
        self.catalog_filter_debounce_timer.start()

    def _schedule_catalog_filter_refresh_reset_page(self) -> None:
        self.catalog_page_index = 0
        self._schedule_catalog_filter_refresh()

    def _run_catalog_filter_refresh(self) -> None:
        try:
            self._refresh_catalog()
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de productos.")

    def _handle_clear_catalog_filters(self) -> None:
        self.catalog_page_index = 0
        self.catalog_search_input.clear()
        for combo in (
            self.catalog_school_scope_filter_combo,
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
        self._refresh_catalog_section_controls()
        self._handle_catalog_filters_changed()

    def _set_catalog_uniform_macro_filter(self, macro_type: str) -> None:
        current_selection = self.catalog_type_filter_combo.selected_values()
        next_selection = resolve_catalog_uniform_macro_selection(
            current_selection=current_selection,
            macro_type=macro_type,
        )
        if not next_selection:
            self.catalog_type_filter_combo.clear_selection()
        else:
            self.catalog_type_filter_combo.set_selected_values(next_selection)
        self._refresh_catalog_uniform_macro_buttons()

    def _refresh_catalog_uniform_macro_buttons(self) -> None:
        macro_states = build_catalog_uniform_macro_button_states(
            available_macros=self.catalog_uniform_macro_buttons.keys(),
            selected_types=self.catalog_type_filter_combo.selected_values(),
        )
        for macro_type, button in self.catalog_uniform_macro_buttons.items():
            is_active = macro_states.get(macro_type, False)
            button.setProperty("active", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _refresh_catalog_section_controls(self) -> None:
        is_general_only = str(self.catalog_school_scope_filter_combo.currentData() or "") == "general_only"
        if is_general_only and self.catalog_school_filter_combo.selected_values():
            self.catalog_school_filter_combo.clear_selection()
        self.catalog_school_filter_combo.setEnabled(not is_general_only)

    def _handle_history_source_changed(self) -> None:
        options_state = build_history_type_options_state(
            source_filter=str(self.history_source_combo.currentData() or ""),
            current_type=str(self.history_type_combo.currentData() or ""),
            build_options=build_history_type_options,
        )
        self.history_type_combo.blockSignals(True)
        self.history_type_combo.clear()
        for label, value in options_state.options:
            self.history_type_combo.addItem(label, value)
        if options_state.selected_type_value:
            index = self.history_type_combo.findData(options_state.selected_type_value)
            if index >= 0:
                self.history_type_combo.setCurrentIndex(index)
        self.history_type_combo.blockSignals(False)
        self._handle_history_filter()

    def _set_history_today(self) -> None:
        today = QDate.currentDate().toPyDate()
        from_date, to_date = build_history_today_filter_dates(today)
        self.history_from_input.setDate(QDate(from_date.year, from_date.month, from_date.day))
        self.history_to_input.setDate(QDate(to_date.year, to_date.month, to_date.day))
        self._handle_history_filter()

    def _set_history_last_7_days(self) -> None:
        range_state = build_history_last_days_filter_dates(today=QDate.currentDate().toPyDate(), days=7)
        self.history_from_input.setDate(QDate(range_state.from_date.year, range_state.from_date.month, range_state.from_date.day))
        self.history_to_input.setDate(QDate(range_state.to_date.year, range_state.to_date.month, range_state.to_date.day))
        self._handle_history_filter()

    def _set_history_last_30_days(self) -> None:
        range_state = build_history_last_days_filter_dates(today=QDate.currentDate().toPyDate(), days=30)
        self.history_from_input.setDate(QDate(range_state.from_date.year, range_state.from_date.month, range_state.from_date.day))
        self.history_to_input.setDate(QDate(range_state.to_date.year, range_state.to_date.month, range_state.to_date.day))
        self._handle_history_filter()

    def _set_history_current_month(self) -> None:
        range_state = build_history_current_month_filter_dates(QDate.currentDate().toPyDate())
        self.history_from_input.setDate(QDate(range_state.from_date.year, range_state.from_date.month, range_state.from_date.day))
        self.history_to_input.setDate(QDate(range_state.to_date.year, range_state.to_date.month, range_state.to_date.day))
        self._handle_history_filter()

    def _clear_history_filters(self) -> None:
        reset_state = build_history_clear_filter_state(self.history_from_input.minimumDate().toPyDate())
        self.history_sku_input.clear()
        self.history_source_combo.setCurrentIndex(reset_state.source_index)
        self.history_entity_combo.setCurrentIndex(reset_state.entity_index)
        self.history_type_combo.setCurrentIndex(reset_state.type_index)
        self.history_from_input.setDate(QDate(reset_state.from_date.year, reset_state.from_date.month, reset_state.from_date.day))
        self.history_to_input.setDate(QDate(reset_state.to_date.year, reset_state.to_date.month, reset_state.to_date.day))
        self._handle_history_filter()

    @staticmethod
    def _history_export_dir() -> Path:
        output_dir = Path(__file__).resolve().parents[1] / "exports" / "history"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _export_history_filtered(self) -> None:
        export_rows = build_history_export_rows(self.history_rows)
        export_dir = self._history_export_dir() / build_history_export_dir_name()
        export_dir.mkdir(parents=True, exist_ok=True)
        json_path = export_dir / "history_filtered.json"
        json_path.write_text(
            json.dumps(export_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        csv_path = export_dir / "history_filtered.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            if export_rows:
                fieldnames = list(export_rows[0].keys())
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for row in export_rows:
                    writer.writerow(row)
            else:
                fh.write("")
        QMessageBox.information(
            self,
            "Historial exportado",
            f"Se exporto el historial filtrado actual en:\n{export_dir}",
        )

    def _refresh_layaways(self, session) -> None:
        search_text = self.layaway_search_input.text().strip().lower()
        state_filter = str(self.layaway_state_combo.currentData() or "")
        due_filter = str(self.layaway_due_combo.currentData() or "")
        selected_id = self._selected_layaway_id()
        layaway_snapshots = build_layaway_history_input_rows(
            load_layaway_snapshot_rows(
                session,
                today=date.today(),
                classify_due=self._classify_layaway_due,
            )
        )
        rows = build_layaway_history_rows(
            layaway_snapshots=layaway_snapshots,
            search_text=search_text,
            state_filter=state_filter,
            due_filter=due_filter,
        )
        layaway_summary_view = build_layaway_summary_view(
            visible_rows=rows,
            search_text=self.layaway_search_input.text(),
            state_filter_value=self.layaway_state_combo.currentData(),
            state_filter_text=self.layaway_state_combo.currentText(),
            due_filter_value=self.layaway_due_combo.currentData(),
            due_filter_text=self.layaway_due_combo.currentText(),
        )

        self.layaway_rows = rows
        row_views = build_layaway_table_row_views(rows)
        self.layaway_table.setRowCount(len(row_views))
        for row_index, row_view in enumerate(row_views):
            for column_index, value in enumerate(row_view.values):
                self.layaway_table.setItem(row_index, column_index, _table_item(value))
            self.layaway_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row_view.layaway_id)
            status_item = self.layaway_table.item(row_index, 2)
            balance_item = self.layaway_table.item(row_index, 5)
            due_item = self.layaway_table.item(row_index, 6)
            if status_item is not None:
                _set_table_badge_style(status_item, row_view.status_tone)
            if balance_item is not None:
                _set_table_badge_style(balance_item, row_view.balance_tone)
            if due_item is not None:
                _set_table_badge_style(due_item, row_view.due_tone)
        self.layaway_table.resizeColumnsToContents()
        self.layaway_status_label.setText(layaway_summary_view.status_label)

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
            detail_view = build_empty_layaway_detail_view()
            self._apply_layaway_detail_view(detail_view)
            return

        try:
            with get_session() as session:
                detail_snapshot = load_layaway_detail_snapshot(
                    session,
                    layaway_id=apartado_id,
                    current_role=self.current_role,
                    classify_due=self._classify_layaway_due,
                )
                detail_view = build_layaway_detail_view(
                    folio=detail_snapshot.folio,
                    estado=detail_snapshot.estado,
                    customer_code=detail_snapshot.customer_code,
                    customer_name=detail_snapshot.customer_name,
                    customer_phone=detail_snapshot.customer_phone,
                    subtotal=detail_snapshot.subtotal,
                    rounding_adjustment=detail_snapshot.rounding_adjustment,
                    total=detail_snapshot.total,
                    total_paid=detail_snapshot.total_paid,
                    balance_due=detail_snapshot.balance_due,
                    commitment_label=detail_snapshot.commitment_label,
                    due_text=detail_snapshot.due_text,
                    due_tone=detail_snapshot.due_tone,
                    notes_text=detail_snapshot.notes_text,
                    detail_rows=[
                        {
                            "sku": row.sku,
                            "product_name": row.product_name,
                            "quantity": row.quantity,
                            "unit_price": row.unit_price,
                            "subtotal": row.subtotal,
                        }
                        for row in detail_snapshot.detail_rows
                    ],
                    payment_rows=[
                        {
                            "created_at": row.created_at_label,
                            "amount": row.amount,
                            "reference": row.reference,
                            "username": row.username,
                        }
                        for row in detail_snapshot.payment_rows
                    ],
                    sale_ticket_enabled=detail_snapshot.sale_ticket_enabled,
                    whatsapp_enabled=detail_snapshot.whatsapp_enabled,
                )
                self._apply_layaway_detail_view(detail_view)
        except Exception as exc:  # noqa: BLE001
            detail_view = build_error_layaway_detail_view(str(exc))
            self._apply_layaway_detail_view(detail_view)

    def _apply_layaway_detail_view(self, detail_view) -> None:
        self.layaway_summary_label.setText(detail_view.summary_label)
        self.layaway_customer_label.setText(detail_view.customer_label)
        self.layaway_balance_label.setText(detail_view.balance_label)
        self.layaway_breakdown_label.setText(detail_view.breakdown_label)
        self.layaway_commitment_label.setText(detail_view.commitment_label)
        self._set_badge_state(
            self.layaway_due_status_label,
            detail_view.due_badge.text,
            detail_view.due_badge.tone,
        )
        self.layaway_notes_label.setText(detail_view.notes_label)
        self.layaway_sale_ticket_button.setEnabled(detail_view.sale_ticket_enabled)
        self.layaway_whatsapp_button.setEnabled(detail_view.whatsapp_enabled)

        self.layaway_detail_table.setRowCount(len(detail_view.detail_rows))
        for row_index, detail_row in enumerate(detail_view.detail_rows):
            for column_index, value in enumerate(detail_row.values):
                self.layaway_detail_table.setItem(row_index, column_index, _table_item(value))
            if detail_row.tone:
                for column_index in (1, 4):
                    item = self.layaway_detail_table.item(row_index, column_index)
                    if item is not None:
                        _set_table_badge_style(item, detail_row.tone)
        self.layaway_detail_table.resizeColumnsToContents()

        self.layaway_payments_table.setRowCount(len(detail_view.payment_rows))
        for row_index, payment_row in enumerate(detail_view.payment_rows):
            for column_index, value in enumerate(payment_row.values):
                self.layaway_payments_table.setItem(row_index, column_index, _table_item(value))
        self.layaway_payments_table.resizeColumnsToContents()

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

    def _handle_create_layaway(self) -> None:
        if self.current_role not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            QMessageBox.warning(self, "Sin permisos", "No tienes permisos para crear apartados.")
            return
        if not self._ensure_cash_session_current_day_for_operation("crear apartados"):
            return
        payload = build_create_layaway_dialog(
            self,
            initial_items=None,
            selected_catalog_row=self._selected_catalog_row(),
        )
        if payload is None:
            return

        try:
            with get_session() as session:
                result = create_layaway_from_payload(
                    session=session,
                    user_id=self.user_id,
                    folio=self._generate_layaway_folio(),
                    payload=payload,
                )
                session.commit()
                apartado_id = result.layaway_id
                apartado_folio = result.layaway_folio
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

        payload = build_create_layaway_dialog(
            self,
            initial_items=self.sale_cart,
            selected_catalog_row=self._selected_catalog_row(),
        )
        if payload is None:
            return

        try:
            with get_session() as session:
                result = create_layaway_from_payload(
                    session=session,
                    user_id=self.user_id,
                    folio=self._generate_layaway_folio(),
                    payload=payload,
                    default_note="Creado desde Caja.",
                )
                session.commit()
                apartado_id = result.layaway_id
                apartado_folio = result.layaway_folio
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

    def _handle_register_layaway_payment(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para registrar abono.")
            return
        if not self._ensure_cash_session_current_day_for_operation("registrar abonos"):
            return
        payload = build_layaway_payment_dialog(self)
        if payload is None:
            return
        try:
            with get_session() as session:
                register_layaway_payment(
                    session,
                    layaway_id=apartado_id,
                    user_id=self.user_id,
                    payment_input=payload,
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
            f"Se registro un abono por ${payload.amount}. Efectivo en caja: ${payload.cash_amount}.",
        )

    def _handle_deliver_layaway(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para entregarlo.")
            return
        if not self._ensure_cash_session_current_day_for_operation("entregar apartados"):
            return
        try:
            with get_session() as session:
                confirmation_snapshot = load_layaway_delivery_confirmation(session, layaway_id=apartado_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo preparar la entrega", str(exc))
            return

        confirmation_view = build_layaway_delivery_confirmation_view(confirmation_snapshot)
        confirmation_box = QMessageBox(self)
        confirmation_box.setIcon(QMessageBox.Icon.Question)
        confirmation_box.setWindowTitle(confirmation_view.title)
        confirmation_box.setText(confirmation_view.message)
        deliver_button = confirmation_box.addButton("Entregar", QMessageBox.ButtonRole.AcceptRole)
        confirmation_box.addButton(QMessageBox.StandardButton.Cancel)
        confirmation_box.exec()
        if confirmation_box.clickedButton() is not deliver_button:
            return
        payment_payload = None
        if confirmation_snapshot.balance_due > Decimal("0.00"):
            payment_payload = build_layaway_payment_dialog(
                self,
                title="Liquidar y entregar apartado",
                helper_text=(
                    f"Saldo pendiente actual: ${confirmation_snapshot.balance_due}. "
                    "Registra el abono final para completar la entrega."
                ),
                initial_amount=confirmation_snapshot.balance_due,
                fixed_amount=True,
                default_notes=f"Liquidacion final previa a la entrega del apartado {confirmation_snapshot.layaway_folio}.",
                accept_button_label="Liquidar y entregar",
            )
            if payment_payload is None:
                return
        try:
            with get_session() as session:
                if payment_payload is None:
                    result = deliver_layaway(
                        session,
                        layaway_id=apartado_id,
                        user_id=self.user_id,
                    )
                else:
                    result = settle_and_deliver_layaway(
                        session,
                        layaway_id=apartado_id,
                        user_id=self.user_id,
                        payment_input=payment_payload,
                    )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo entregar", str(exc))
            return

        self.refresh_all()
        self._select_layaway(apartado_id)
        result_view = build_layaway_delivery_result_view(result)
        result_box = QMessageBox(self)
        result_box.setIcon(QMessageBox.Icon.Information)
        result_box.setWindowTitle(result_view.title)
        result_box.setText(result_view.message)
        open_ticket_button = result_box.addButton("Ver ticket", QMessageBox.ButtonRole.ActionRole)
        result_box.addButton(QMessageBox.StandardButton.Close)
        result_box.exec()
        if result_box.clickedButton() is open_ticket_button:
            self._handle_view_layaway_sale_ticket()

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
                cancel_layaway(
                    session,
                    layaway_id=apartado_id,
                    user_id=self.user_id,
                    note=note_input.toPlainText().strip() or None,
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
            self._apply_inventory_qr_preview_view(build_empty_inventory_qr_preview_view())
            self._refresh_inventory_overview()
            return

        preview_path: Path | None = None
        sku = ""
        product_name = ""
        talla = ""
        color = ""
        try:
            with get_session() as session:
                variante = session.get(Variante, int(variante_id))
                if variante is None:
                    raise ValueError("Presentacion no encontrada.")
                path = QrGenerator.path_for_variant(variante)
                sku = str(variante.sku)
                product_name = str(variante.producto.nombre)
                talla = str(variante.talla)
                color = str(variante.color)
                if not path.exists():
                    self._apply_inventory_qr_preview_view(
                        build_pending_inventory_qr_preview_view(
                            sku=sku,
                            product_name=product_name,
                            talla=talla,
                            color=color,
                        )
                    )
                    self._refresh_inventory_overview()
                    self._sync_inventory_table_selection(variante_id)
                    return
                preview_path = path
        except Exception:  # noqa: BLE001
            self._apply_inventory_qr_preview_view(build_error_inventory_qr_preview_view())
            self._refresh_inventory_overview()
            return

        self._apply_inventory_qr_preview_view(
            build_available_inventory_qr_preview_view(
                sku=sku,
                product_name=product_name,
                talla=talla,
                color=color,
                file_name=path.name,
            ),
            preview_path=preview_path,
        )
        self._refresh_inventory_overview()
        self._sync_inventory_table_selection(variante_id)

    def _apply_inventory_qr_preview_view(
        self,
        view: InventoryQrPreviewView,
        *,
        preview_path: Path | None = None,
    ) -> None:
        self.inventory_generate_qr_button.setText(view.button_label)
        self.qr_preview_info_label.setText(view.info_label)
        self._set_badge_state(self.qr_status_label, view.status_text, view.status_tone)
        if view.preview_available and preview_path is not None:
            self._load_qr_preview(preview_path)
            return
        self.qr_preview_label.clear()
        self.qr_preview_label.setText(view.placeholder_text)

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
        try:
            with get_session() as session:
                preferred_printer = load_business_print_settings_snapshot(session).preferred_printer
        except Exception:
            preferred_printer = ""

        if sys.platform.startswith("win"):
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
                        f'Se envio la etiqueta a "{resolution.printer_name}" '
                        "porque la impresora preferida no estaba disponible en esta PC."
                    ),
                )
            return True

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
            target_size = normalize_scaled_target_size(page_rect.size())
            scaled = image.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            target_rect = build_centered_paint_rect(page_rect, scaled.size())
            for copy_index in range(max(1, copies)):
                if copy_index > 0:
                    printer.newPage()
                painter.drawImage(target_rect, scaled)
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

        variant_ids = [
            int(item_data)
            for index in range(self.inventory_variant_combo.count())
            if (item_data := self.inventory_variant_combo.itemData(index))
        ]
        current_index = 0
        if int(variante_id) in variant_ids:
            current_index = variant_ids.index(int(variante_id))

        try:
            with get_session() as session:
                label_context = load_inventory_label_context(session, int(variante_id))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Impresion no disponible", str(exc))
            return

        def load_context(variant_id: int):
            with get_session() as session:
                return load_inventory_label_context(session, int(variant_id))

        label_render_state = {"variant_id": label_context.variant_id}

        def render_label(mode: str, requested_copies: int):
            with get_session() as session:
                return render_inventory_label(
                    session,
                    int(label_render_state["variant_id"]),
                    mode=mode,
                    requested_copies=requested_copies,
                )

        def load_context_for_dialog(variant_id: int):
            context = load_context(int(variant_id))
            label_render_state["variant_id"] = context.variant_id
            return context

        build_inventory_label_dialog(
            self,
            initial_context=label_context,
            variant_ids=variant_ids or [label_context.variant_id],
            current_index=current_index,
            load_context=load_context_for_dialog,
            render_label=render_label,
            print_label=lambda image_path, copies, sku, parent: self._print_image_path(
                image_path,
                title=f"Etiqueta {sku}",
                copies=copies,
                parent=parent,
            ),
        )

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
        pricing = self._calculate_sale_pricing()
        breakdown = self._sale_discount_breakdown()
        panel_view = build_sale_cashier_panel_view(
            sale_cart=self.sale_cart,
            subtotal=pricing.subtotal,
            applied_discount=pricing.applied_discount,
            rounding_adjustment=pricing.rounding_adjustment,
            collected_total=pricing.collected_total,
            payment_method=self.sale_payment_combo.currentText().strip() or "Efectivo",
            winner_label=str(breakdown["winner_label"]),
            selected_client_label=self.sale_client_combo.currentText(),
            can_sell=self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO},
            has_cash_session=self.active_cash_session_id is not None,
            is_processing=self.sale_processing,
        )
        for row_index, row in enumerate(panel_view.cashier_view.table_view.rows):
            for column_index, value in enumerate(row.values):
                item = _table_item(value)
                if column_index == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column_index in {3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.sale_cart_table.setItem(row_index, column_index, item)
        for column_index in (0, 2, 3, 4):
            self.sale_cart_table.resizeColumnToContents(column_index)
        self.sale_total_label.setText(panel_view.cashier_view.summary.total_label)
        self.sale_total_meta_label.setText(panel_view.cashier_view.summary.meta_label)
        self.sale_summary_label.setText(panel_view.cashier_view.summary.summary_label)
        self.sale_context_label.setText(panel_view.context_label)
        self.sale_status_label.setText(panel_view.status_label)
        self.sale_status_label.setProperty("tone", panel_view.status_tone)
        self.sale_status_label.style().unpolish(self.sale_status_label)
        self.sale_status_label.style().polish(self.sale_status_label)
        self.sale_status_label.update()
        self.sale_feedback_label.setToolTip(panel_view.payment_tooltip)
        self.sale_qty_down_button.setEnabled(panel_view.quick_adjust_enabled)
        self.sale_qty_up_button.setEnabled(panel_view.quick_adjust_enabled)
        self.sale_remove_button.setEnabled(panel_view.remove_enabled)
        self.sale_clear_button.setEnabled(panel_view.clear_enabled)
        self._refresh_permissions()

    def _refresh_quote_cart_table(self) -> None:
        quote_cart_view = build_quote_cart_view(self.quote_cart)
        self.quote_cart_table.setRowCount(len(quote_cart_view.rows))
        for row_index, row in enumerate(quote_cart_view.rows):
            for column_index, value in enumerate(row.values):
                self.quote_cart_table.setItem(row_index, column_index, _table_item(value))
        self.quote_cart_table.resizeColumnsToContents()
        self.quote_total_label.setText(quote_cart_view.summary.total_label)
        self.quote_summary_label.setText(quote_cart_view.summary.summary_label)
        self._refresh_permissions()

    def _selected_catalog_row(self) -> dict[str, object] | None:
        inventory_variant_id = self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())
        selected_from_inventory = find_catalog_row_by_variant_id(
            self.catalog_filtered_rows,
            inventory_variant_id,
        )
        if selected_from_inventory is not None:
            return selected_from_inventory
        return resolve_catalog_row(self.catalog_rows, self.catalog_table.currentRow())

    def _handle_inventory_table_selection(self) -> None:
        variant_id = self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())
        if variant_id is None:
            return
        self._set_combo_value(self.inventory_variant_combo, variant_id)

    def _selected_inventory_variant_ids(self) -> list[int]:
        return collect_selected_inventory_variant_ids(
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.inventory_table.selectedItems()
            if item.column() == 0
        )

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

        qr_exists = (QrGenerator.output_dir() / f"{selected['sku']}.png").exists()
        action_key = prompt_inventory_context_action(
            self,
            global_pos=self.inventory_table.viewport().mapToGlobal(pos),
            action_specs=build_inventory_context_menu_actions(
                is_admin=self.current_role == RolUsuario.ADMIN,
                qr_exists=qr_exists,
                variante_activa=bool(selected["variante_activo"]),
            ),
        )
        self._handle_inventory_context_action(action_key)

    def _handle_inventory_context_action(self, action_key: str | None) -> None:
        handlers = {
            "edit": self._handle_update_variant,
            "entry": self._handle_purchase,
            "adjust": self._handle_inventory_adjustment,
            "qr": self._handle_generate_selected_qr,
            "print": self._handle_inventory_print_label,
            "toggle": self._handle_toggle_variant,
        }
        handler = handlers.get(action_key or "")
        if handler is not None:
            handler()

    def _sync_inventory_table_selection(self, variant_id: object) -> None:
        if variant_id is None:
            self.inventory_table.clearSelection()
            return
        row_variant_ids = [
            self._inventory_table_variant_id_at_row(row_index)
            for row_index in range(self.inventory_table.rowCount())
        ]
        row_index = find_inventory_row_index_by_variant_id(row_variant_ids, variant_id)
        if row_index is None:
            return
        self.inventory_table.blockSignals(True)
        try:
            self.inventory_table.setCurrentCell(row_index, 0)
            self.inventory_table.selectRow(row_index)
        finally:
            self.inventory_table.blockSignals(False)

    def _refresh_inventory_overview(self) -> None:
        variante_id = self.inventory_variant_combo.currentData()
        if not variante_id:
            self._apply_inventory_overview_view(build_empty_inventory_overview_view())
            return

        try:
            with get_session() as session:
                overview_snapshot = load_inventory_overview_snapshot(
                    session,
                    variant_id=int(variante_id),
                    catalog_rows=self.catalog_filtered_rows,
                )
                self._apply_inventory_overview_view(
                    build_inventory_overview_view(
                        sku=overview_snapshot.sku,
                        product_name=overview_snapshot.product_name,
                        product_active=overview_snapshot.product_active,
                        variant_active=overview_snapshot.variant_active,
                        stock_actual=overview_snapshot.stock_actual,
                        apartado_cantidad=overview_snapshot.apartado_cantidad,
                        talla=overview_snapshot.talla,
                        color=overview_snapshot.color,
                        precio_venta=overview_snapshot.precio_venta,
                        origen_etiqueta=overview_snapshot.origen_etiqueta,
                        escuela_nombre=overview_snapshot.escuela_nombre,
                        tipo_prenda_nombre=overview_snapshot.tipo_prenda_nombre,
                        tipo_pieza_nombre=overview_snapshot.tipo_pieza_nombre,
                        movement_type=overview_snapshot.movement_type,
                        movement_quantity=overview_snapshot.movement_quantity,
                        movement_date=overview_snapshot.movement_date,
                    )
                )
        except Exception:  # noqa: BLE001
            self._apply_inventory_overview_view(build_error_inventory_overview_view())

    def _apply_inventory_overview_view(self, overview_view) -> None:
        self.inventory_overview_label.setText(overview_view.overview_label)
        self.inventory_product_label.setText(overview_view.product_label)
        self._set_badge_state(
            self.inventory_status_badge,
            overview_view.status_badge.text,
            overview_view.status_badge.tone,
        )
        self._set_badge_state(
            self.inventory_stock_badge,
            overview_view.stock_badge.text,
            overview_view.stock_badge.tone,
        )
        self.inventory_stock_hint_label.setText(overview_view.stock_hint_label)
        self.inventory_meta_label.setText(overview_view.meta_label)
        self.inventory_last_movement_label.setText(overview_view.last_movement_label)
        self.catalog_selection_label.setText(overview_view.catalog_selection_label)
        self.toggle_product_button.setText(overview_view.toggle_product_label)
        self.toggle_variant_button.setText(overview_view.toggle_variant_label)

    def _inventory_table_variant_id_at_row(self, row_index: int) -> int | None:
        if row_index < 0:
            return None
        item = self.inventory_table.item(row_index, 0)
        if item is None:
            return None
        return normalize_inventory_variant_id(item.data(Qt.ItemDataRole.UserRole))

    def _clear_catalog_editor(self) -> None:
        self.catalog_selection_label.setText("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label.setText(build_empty_catalog_selection_view().selection_label)
        self.toggle_product_button.setText("Prod.")
        self.toggle_variant_button.setText("Pres.")

    def _select_catalog_variant(self, variant_id: int) -> bool:
        filtered_row_index = find_catalog_row_index_by_variant_id(self.catalog_filtered_rows, variant_id)
        if filtered_row_index is None:
            return False
        target_page_index = filtered_row_index // CATALOG_PAGE_SIZE
        if target_page_index != self.catalog_page_index:
            self.catalog_page_index = target_page_index
            self._run_catalog_filter_refresh()
        row_index = find_catalog_row_index_by_variant_id(self.catalog_rows, variant_id)
        if row_index is None:
            return False
        self.catalog_table.blockSignals(True)
        try:
            self.catalog_table.setCurrentCell(row_index, 0)
            self.catalog_table.selectRow(row_index)
        finally:
            self.catalog_table.blockSignals(False)
        self._handle_catalog_selection()
        return True

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

    def _create_kpi_card(
        self,
        title: str,
        value_label: QLabel,
        subtitle: str,
        detail_label: QLabel | None = None,
    ) -> QFrame:
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
        if detail_label is not None:
            detail_label.setObjectName("kpiSubtitle")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
        card.setLayout(layout)
        return card

    def _apply_styles(self) -> None:
        self.setStyleSheet(build_main_window_stylesheet())


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(user_id=1)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
