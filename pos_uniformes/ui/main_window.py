"""Ventana principal funcional del sistema POS."""

import csv
import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unicodedata
from urllib.parse import quote
from uuid import uuid4
import weakref
import webbrowser

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

from PyQt6.QtCore import QDate, QEvent, QMarginsF, QObject, QSizeF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QImage, QKeySequence, QPainter, QPageLayout, QPageSize, QPixmap, QShortcut
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
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
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
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from pos_uniformes.database.connection import engine, get_session, test_connection
from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Cliente,
    Compra,
    Empleada,
    Escuela,
    EstadoPresupuesto,
    EstadoCompra,
    Marca,
    MovimientoInventario,
    NivelEducativo,
    Producto,
    Proveedor,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_active_filters_summary,
    build_active_filter_tokens,
)
from pos_uniformes.services.analytics_snapshot_service import (
    build_analytics_sales_snapshot,
    load_confirmed_sales_for_analytics,
)
from pos_uniformes.services.analytics_layaway_service import load_analytics_layaway_snapshot
from pos_uniformes.services.analytics_top_clients_service import load_analytics_top_client_snapshot_rows
from pos_uniformes.services.analytics_top_products_service import load_analytics_top_product_snapshot_rows
from pos_uniformes.services.analytics_stock_service import load_analytics_stock_snapshot_rows
from pos_uniformes.services.auth_service import AuthService
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
from pos_uniformes.services.employee_activity_service import (
    build_employee_activity_empty_snapshot,
    build_employee_activity_state,
    build_employee_activity_sort_key,
    load_employee_activity_snapshot,
    load_employee_activity_snapshots,
)
from pos_uniformes.services.employee_sales_history_service import (
    list_employee_day_sale_rows,
    load_employee_sale_detail_snapshot,
)
from pos_uniformes.services.employee_ranking_service import build_ranking_period_dates
from pos_uniformes.ui.helpers.settings_employee_ranking_helper import build_libreta_ranking_view
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
from pos_uniformes.services import conjunto_service
from pos_uniformes.services import exportacion_libreta_service
from pos_uniformes.services import resumen_pos_service
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.services.catalog_mutation_service import (
    delete_catalog_product,
    delete_catalog_variant,
    toggle_catalog_product_state,
    toggle_catalog_variant_state,
)
from pos_uniformes.services.compra_service import CompraItemInput, CompraService
from pos_uniformes.services.customer_card_service import (
    COLOR_ESTANDAR_PRIMARIO,
    COLOR_ESTANDAR_SECUNDARIO,
    CustomerCardRenderInput,
    CustomerCardService,
)
from pos_uniformes.services.employee_card_service import EmployeeCardService
from pos_uniformes.services.history_snapshot_service import (
    HistorySnapshotFilters,
    load_history_snapshot_rows,
)
from pos_uniformes.services.inventario_service import (
    AjusteMasivoFilaInput,
    InventarioService,
)
from pos_uniformes.services.inventory_label_service import (
    load_inventory_label_context,
    render_inventory_label,
)
from pos_uniformes.services.inventario_busqueda_service import combinar_hits_meili
from pos_uniformes.services.inventory_overview_service import load_inventory_overview_snapshot
from pos_uniformes.services.inventory_snapshot_service import load_inventory_snapshot_rows
from pos_uniformes.services.presupuesto_service import PresupuestoService
from pos_uniformes.services.quote_snapshot_service import (
    build_quote_history_input_rows,
    load_quote_snapshot_rows,
)
from pos_uniformes.services.quote_detail_service import load_quote_detail_snapshot
from pos_uniformes.services.quote_action_service import cancel_quote
from pos_uniformes.services.quote_whatsapp_service import build_quote_whatsapp_view
from pos_uniformes.services.layaway_alerts_service import load_layaway_alerts_snapshot
from pos_uniformes.services.sale_cart_update_service import update_sale_cart_item_quantity
from pos_uniformes.services.sale_discount_service import format_discount_label
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
from pos_uniformes.services.settings_client_action_service import generate_settings_client_qr
from pos_uniformes.services.settings_cliente_admin_actions import (
    alternar_estado,
    cargar_ficha,
    crear_cliente,
    editar_cliente,
    tipos_para_combo,
)
from pos_uniformes.services.clientes.identidad_service import (
    CoincidenciasPorConfirmarError,
    TelefonoInvalidoError,
    mensaje_telefono_ya_registrado,
)
from pos_uniformes.ui.dialogs.cliente_admin_dialogs import prompt_cliente_ficha, prompt_motivo
from pos_uniformes.ui.dialogs.cliente_ficha_dialog import ORIGEN_ETIQUETAS, construir_ficha_dialog, etiqueta_origen
from pos_uniformes.services.clientes import admin_service
from pos_uniformes.services.clientes.ficha_service import cargar_ficha as cargar_ficha_cliente
from pos_uniformes.services.settings_marketing_action_service import (
    load_settings_marketing_history_rows,
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
from pos_uniformes.services.settings_employee_action_service import (
    create_settings_employee,
    generate_settings_employee_card,
    generate_settings_employee_qr,
    load_settings_employee_prompt_snapshot,
    set_settings_employee_pin,
    toggle_settings_employee,
    update_settings_employee,
)
from pos_uniformes.services.supplier_service import SupplierService
from pos_uniformes.services.user_service import UserService
from pos_uniformes.ui.login_dialog import LoginDialog
from pos_uniformes.ui.dialogs.settings_dialogs import (
    build_backup_settings_dialog,
    build_business_settings_dialog,
    build_clients_settings_dialog,
    build_employees_settings_dialog,
    build_marketing_settings_dialog,
    build_suppliers_settings_dialog,
    build_whatsapp_settings_dialog,
    build_users_settings_dialog,
)
from pos_uniformes.ui.dialogs.settings_prompt_dialogs import (
    prompt_employee_data,
    prompt_employee_pin,
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
from pos_uniformes.ui.dialogs.inventory_context_menu_dialog import prompt_inventory_context_action
from pos_uniformes.ui.dialogs.inventory_count_dialog import prompt_inventory_count_data
from pos_uniformes.ui.dialogs.inventory_label_batch_dialog import build_inventory_label_batch_dialog
from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
from pos_uniformes.ui.dialogs.marketing_history_dialog import build_marketing_history_dialog
from pos_uniformes.ui.helpers.busy_feedback_helper import BusyFeedbackController
from pos_uniformes.ui.helpers.inventory_bulk_qr_helper import (
    InventoryBulkQrCancelled,
    generate_inventory_bulk_qr,
)
from pos_uniformes.ui.helpers.bulk_qr_worker import BulkQrWorker
from pos_uniformes.ui.helpers.catalog_access_helper import build_catalog_access_view
from pos_uniformes.ui.helpers.catalog_action_guard_helper import build_catalog_action_guard_feedback
from pos_uniformes.ui.helpers.catalog_action_feedback_helper import (
    build_catalog_delete_confirmation,
    build_catalog_error_title,
    build_catalog_success_result,
    build_product_delete_label,
    build_variant_delete_label,
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
from pos_uniformes.ui.helpers.active_filter_chip_helper import rebuild_active_filter_chips
from pos_uniformes.ui.helpers.catalog_summary_helper import build_catalog_summary_view
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
from pos_uniformes.ui.helpers.inventory_selection_helper import (
    collect_inventory_row_variant_ids,
    collect_selected_inventory_variant_ids,
    find_catalog_row_by_variant_id,
    find_inventory_row_index_by_variant_id,
    normalize_inventory_variant_id,
)
from pos_uniformes.ui.helpers.inventory_summary_helper import INVENTORY_SEARCH_LIMIT, build_inventory_summary_view
from pos_uniformes.ui.helpers.inventory_alta_texts import (
    TITULO_ERROR_LOTE,
    mensaje_talla_creada,
    mensaje_tallas_creadas,
)
from pos_uniformes.ui.helpers.inventory_help_texts import aplicar_ayudas_inventario
from pos_uniformes.ui.helpers.inventory_toggle_helper import (
    confirmacion_desactivar_prenda,
    confirmacion_desactivar_talla,
    contar_tallas_de_prenda,
    preguntar as preguntar_desactivar,
)
from pos_uniformes.ui.helpers.inventory_table_row_helper import (
    COLUMNA_STOCK as INVENTORY_COLUMNA_STOCK,
    build_inventory_table_row_views,
)
from pos_uniformes.ui.helpers.layaway_alerts_helper import build_layaway_alerts_view
from pos_uniformes.ui.helpers.window_close_helper import build_main_window_close_decision
from pos_uniformes.ui.helpers.quote_cart_view_helper import build_quote_cart_view
from pos_uniformes.ui.helpers.quote_history_helper import build_quote_history_rows
from pos_uniformes.ui.helpers.quote_detail_helper import (
    build_empty_quote_detail_view,
    build_error_quote_detail_view,
    build_quote_detail_view,
)
from pos_uniformes.ui.helpers.quote_sports_uniform_helper import (
    add_quote_scan_variants,
    build_quote_presupuesto_inputs,
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
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    restore_sports_uniform_playera_price_if_needed,
)
from pos_uniformes.services.quote_client_creation_feedback_service import build_quote_client_created_feedback
from pos_uniformes.ui.helpers.size_option_sort_helper import group_size_options, sort_size_options
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
    build_settings_employee_guard_feedback,
    build_settings_employee_result_feedback,
    build_settings_marketing_guard_feedback,
    build_settings_supplier_guard_feedback,
    build_settings_supplier_result_feedback,
)
from pos_uniformes.ui.helpers.settings_crm_selection_helper import (
    resolve_selected_settings_client_id,
    resolve_selected_settings_employee_id,
    resolve_selected_settings_supplier_id,
)
from pos_uniformes.ui.helpers.settings_clients_helper import (
    CLIENTES_ADMIN_COLUMNAS,
    COLUMNA_CREDENCIAL,
    COLUMNA_ESTADO,
    COLUMNA_QR,
    build_clientes_admin_view,
    build_settings_clients_error_view,
)
from pos_uniformes.ui.helpers.settings_employees_helper import (
    build_settings_employees_error_view,
    build_settings_employees_view,
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
from pos_uniformes.ui.views.dashboard_view import build_dashboard_tab
from pos_uniformes.ui.views.history_view import build_history_tab
from pos_uniformes.ui.views.inventory_view import build_inventory_tab
from pos_uniformes.ui.views.products_view import build_products_tab
from pos_uniformes.ui.views.quotes_view import build_quotes_tab
from pos_uniformes.ui.views.bodega_view import build_bodega_tab
from pos_uniformes.ui.views.panel_uniformes_view import build_panel_uniformes_tab
from pos_uniformes.ui.views.settings_view import build_settings_tab
from pos_uniformes.ui.styles.main_window_styles import build_main_window_stylesheet
from pos_uniformes.utils.date_format import format_display_date, format_display_datetime, local_day_window
from pos_uniformes.utils.product_templates import merge_choice_lists
from pos_uniformes.utils.product_name import sanitize_product_display_name
from pos_uniformes.utils.qr_generator import QrGenerator
from pos_uniformes.services.nombres_empleadas_service import mostrar as _nombre_de
from pos_uniformes.services.nombres_empleadas_service import nombres_por_codigo

# Pestañas que dejaron de tener sentido aquí porque su trabajo se mudó al
# kiosko: los presupuestos se hacen en Presupuesto guiado y el catálogo se
# lleva desde Panel Uniformes e Inventario.
#
# Se ocultan, NO se borran: fueron la base del sistema, sus datos siguen
# intactos y el código completo sigue en el repositorio. Para volver a ver
# alguna, quitar su nombre de esta tupla.
#
# 2026-11-12: la Caja antigua ya no está en la tupla porque ya no se oculta,
# se retiró (pestaña, carrito, cobro, ventas recientes y sus atajos). Daniel:
# «la caja antigua ya no es de utilidad, todo lo demás corre en libreta y
# kioskos y es lo único que importa, es donde vive nuestra operación».
# Después: «no lo necesito, retira también movimientos y el corte». Se fueron
# el botón Movimientos y la sesión/corte de caja de esta ventana; el corte
# vive en el kiosko.
#
# 2026-11-12: la pestaña Apartados tampoco se oculta ya: se retiró (vista,
# botones crear/abonar/editar/entregar/cancelar, comprobantes, WhatsApp y su
# refresco). Daniel: «retira también apartados». Los apartados se hacen en
# Venta Rápida del kiosko y quedan en la Libreta; la tabla `apartado`, sus
# datos y los servicios de dominio (services/apartado_service.py y
# services/layaway_*) siguen intactos.

PESTANAS_MUDADAS_AL_KIOSKO = ("Presupuestos", "Catálogo")

LISTING_SEARCH_DEBOUNCE_MS = 300
CATALOG_PAGE_SIZE = 25
INVENTORY_PAGE_SIZE = 25


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class _TableSpinTabNavigator(QObject):
    def __init__(
        self,
        *,
        anchor_before: QWidget | None = None,
        anchor_after: QWidget | None = None,
    ) -> None:
        super().__init__(anchor_after or anchor_before)
        self._anchor_before = anchor_before
        self._anchor_after = anchor_after
        self._inputs: list[QWidget] = []

    def set_inputs(self, inputs: list[QWidget]) -> None:
        self._inputs = list(inputs)
        for input_widget in self._inputs:
            input_widget.installEventFilter(self)
            editor = self._editor_for(input_widget)
            if editor is not None:
                editor.installEventFilter(self)
        if not self._inputs:
            return
        if self._anchor_before is not None:
            QWidget.setTabOrder(self._anchor_before, self._inputs[0])
        previous_widget = self._inputs[0]
        for input_widget in self._inputs[1:]:
            QWidget.setTabOrder(previous_widget, input_widget)
            previous_widget = input_widget
        if self._anchor_after is not None:
            QWidget.setTabOrder(previous_widget, self._anchor_after)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        if key not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return super().eventFilter(watched, event)
        direction = -1 if key == Qt.Key.Key_Backtab else 1
        owner_widget = self._resolve_input_owner(watched)
        if owner_widget is None:
            return super().eventFilter(watched, event)
        return self._move_focus(owner_widget, direction)

    def _resolve_input_owner(self, watched: QObject) -> QWidget | None:
        if watched in self._inputs:
            return watched if isinstance(watched, QWidget) else None
        for input_widget in self._inputs:
            if self._editor_for(input_widget) is watched:
                return input_widget
        return None

    @staticmethod
    def _editor_for(widget: QWidget) -> QWidget | None:
        line_edit = getattr(widget, "lineEdit", None)
        if callable(line_edit):
            return line_edit()
        return None

    def _move_focus(self, source_widget: QWidget, direction: int) -> bool:
        try:
            current_index = self._inputs.index(source_widget)
        except ValueError:
            return False
        if direction > 0:
            if current_index + 1 < len(self._inputs):
                target = self._inputs[current_index + 1]
            else:
                target = self._anchor_after
        else:
            if current_index - 1 >= 0:
                target = self._inputs[current_index - 1]
            else:
                target = self._anchor_before
        if not isinstance(target, QWidget):
            return False
        target.setFocus(Qt.FocusReason.TabFocusReason)
        editor = self._editor_for(target)
        if editor is not None and hasattr(editor, "selectAll"):
            editor.selectAll()
        return True


def _normalize_filter_value(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _catalog_toggle_feedback_action(target_state: bool) -> str:
    return "activate" if target_state else "deactivate"


class MultiSelectFilterButton(QToolButton):
    selectionChanged = pyqtSignal()

    def __init__(self, default_label: str, *, group_values_by_format: bool = False) -> None:
        super().__init__()
        self._default_label = default_label
        self._short_label = default_label.split(":", 1)[0]
        self._group_values_by_format = group_values_by_format
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
        group_values_by_format: bool = False,
        allow_custom: bool = False,
        presets: list[tuple[str, list[str] | Callable[[list[str]], list[str]]]] | None = None,
    ) -> None:
        super().__init__(default_label)
        self._default_label = default_label
        self._short_label = default_label.split(":", 1)[0]
        self._title = title
        self._helper_text = helper_text
        self._columns = max(1, columns)
        self._group_values_by_format = group_values_by_format
        self._allow_custom = allow_custom
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

        # ── Custom value input ───────────────────────────────────────────
        if self._allow_custom:
            custom_row = QHBoxLayout()
            custom_row.setSpacing(8)
            custom_input = QLineEdit()
            custom_input.setPlaceholderText("Escribir nuevo valor y presionar Agregar...")
            custom_add_btn = QPushButton("+ Agregar")
            custom_add_btn.setObjectName("chipButton")
            custom_add_btn.setStyleSheet(
                "QPushButton { background: #2e7d32; color: white; font-weight: 600;"
                " padding: 4px 14px; border-radius: 6px; font-size: 12px; }"
                "QPushButton:hover { background: #1b5e20; }"
            )
            custom_row.addWidget(custom_input, 1)
            custom_row.addWidget(custom_add_btn)
            layout.addLayout(custom_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(10)
        checkboxes: list[tuple[QCheckBox, str, str]] = []
        checkbox_groups: list[tuple[QWidget, list[QCheckBox]]] = []

        # Grupo especial para valores custom añadidos en esta sesión
        custom_group_widget: QWidget | None = None
        custom_grid: QGridLayout | None = None
        custom_checkboxes: list[QCheckBox] = []

        def add_group(group_label: str | None, items: list[tuple[str, str]]) -> None:
            group_widget = QWidget()
            group_layout = QVBoxLayout()
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(6)
            visible_checkboxes: list[QCheckBox] = []
            if group_label:
                title = QLabel(group_label)
                title.setObjectName("catalogSectionHint")
                group_layout.addWidget(title)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(8)
            for index, (label, data) in enumerate(items):
                checkbox = QCheckBox(label)
                checkbox.setChecked(data in self._selected_values)
                checkbox.setProperty("search_text", label.casefold())
                grid.addWidget(checkbox, index // self._columns, index % self._columns)
                checkboxes.append((checkbox, label, data))
                visible_checkboxes.append(checkbox)
            group_layout.addLayout(grid)
            group_widget.setLayout(group_layout)
            content_layout.addWidget(group_widget)
            checkbox_groups.append((group_widget, visible_checkboxes))

        if self._group_values_by_format:
            grouped_items = [
                (group_label, [(value, value) for value in group_values])
                for group_label, group_values in group_size_options([data for _label, data in self._items])
            ]
            for group_label, items in grouped_items:
                add_group(group_label, items)
        else:
            add_group(None, self._items)

        def _add_custom_value() -> None:
            nonlocal custom_group_widget, custom_grid
            if not self._allow_custom:
                return
            value = custom_input.text().strip()
            if not value:
                return
            # No duplicar
            existing = {data for _cb, _lbl, data in checkboxes}
            if value in existing:
                # Si ya existe, solo marcarlo
                for cb, _lbl, data in checkboxes:
                    if data == value:
                        cb.setChecked(True)
                        break
                custom_input.clear()
                refresh_count()
                return
            # Crear grupo "Nuevos" si no existe
            if custom_group_widget is None:
                custom_group_widget = QWidget()
                cg_layout = QVBoxLayout()
                cg_layout.setContentsMargins(0, 0, 0, 0)
                cg_layout.setSpacing(6)
                cg_title = QLabel("Nuevos")
                cg_title.setObjectName("catalogSectionHint")
                cg_title.setStyleSheet("font-weight:700; color:#2e7d32;")
                cg_layout.addWidget(cg_title)
                custom_grid = QGridLayout()
                custom_grid.setContentsMargins(0, 0, 0, 0)
                custom_grid.setHorizontalSpacing(10)
                custom_grid.setVerticalSpacing(8)
                cg_layout.addLayout(custom_grid)
                custom_group_widget.setLayout(cg_layout)
                # Insertar al inicio del content_layout
                content_layout.insertWidget(0, custom_group_widget)
                checkbox_groups.append((custom_group_widget, custom_checkboxes))
            # Añadir checkbox
            idx = len(custom_checkboxes)
            cb = QCheckBox(value)
            cb.setChecked(True)
            cb.setProperty("search_text", value.casefold())
            cb.toggled.connect(lambda _: refresh_count())
            custom_grid.addWidget(cb, idx // self._columns, idx % self._columns)
            checkboxes.append((cb, value, value))
            custom_checkboxes.append(cb)
            self._items.append((value, value))
            custom_input.clear()
            refresh_count()

        if self._allow_custom:
            custom_add_btn.clicked.connect(_add_custom_value)
            custom_input.returnPressed.connect(_add_custom_value)

        content_layout.addStretch(1)
        content.setLayout(content_layout)
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
            for group_widget, group_checkboxes in checkbox_groups:
                group_widget.setVisible(any(checkbox.isVisible() for checkbox in group_checkboxes))

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


def _set_table_badge_style(item: QTableWidgetItem, tone: str, *, con_fondo: bool = True) -> None:
    palette = {
        "positive": ("#e5f2eb", "#245241"),
        "warning": ("#fbf0cf", "#8a5a00"),
        "danger": ("#f8dfd9", "#9a2f22"),
        "reserved": ("#e5edf6", "#2d5068"),
        "muted": ("#ece8e1", "#6e675f"),
    }
    background, foreground = palette.get(tone, palette["muted"])
    if con_fondo:
        item.setBackground(QColor(background))
    item.setForeground(QColor(foreground))
    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))


def _set_table_row_tint(item: QTableWidgetItem, tone: str) -> None:
    palette = {
        "danger": ("#fff2ef", "#7a2b1d"),
        "warning": ("#fffaf0", "#7a5a14"),
        "muted": ("#f5f0ea", "#7a6d60"),
        "neutral": ("#fdfaf6", "#7a6d60"),
        "reserved": ("#f0ebe4", "#5a4a3f"),
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
    "Café",
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


def _build_bulk_selection_label(selected_ids: list[int], matched_rows: list[dict[str, object]]) -> str:
    matched = len(matched_rows)
    total = len(selected_ids)
    if total > matched:
        return f"Filas seleccionadas ({matched} de {total} — {total - matched} no coinciden con el filtro actual)"
    return f"Filas seleccionadas ({matched})"


class _KioskKeyFilter(QObject):
    """Ctrl+K global: funciona incluso con un diálogo modal encima.

    Vive a nivel de módulo a propósito. Definida dentro de `__init__` creaba una
    clase NUEVA por cada ventana; al recolectar una de esas clases con una
    instancia todavía instalada en el QApplication, el siguiente evento entraba
    a memoria liberada y el proceso moría con un segfault dentro de eventFilter
    (con la línea sin resolver, `line ???`, porque el code object ya no existía).
    Se veía al construir muchas ventanas seguidas, que es justo lo que hacen los
    tests.

    Guarda al dueño con una referencia débil: el filtro se instala en el
    QApplication, que vive toda la sesión, y una referencia fuerte mantendría
    viva la ventana para siempre.
    """

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner_ref = weakref.ref(owner)

    def eventFilter(self, obj, event):  # noqa: N802 — API de Qt
        if event.type() == QEvent.Type.KeyPress:
            mods = event.modifiers()
            key = event.key()
            ctrl = (
                mods & Qt.KeyboardModifier.ControlModifier
                or mods & Qt.KeyboardModifier.MetaModifier
            )
            if ctrl and key == Qt.Key.Key_K:
                owner = self._owner_ref()
                if owner is None:
                    return False
                owner._open_quick_kiosk()
                return True
        return False


class MainWindow(QMainWindow):
    def __init__(self, user_id: int) -> None:
        super().__init__()
        self.user_id = user_id
        self.current_username = ""
        self.current_full_name = ""
        self.current_role = RolUsuario.CAJERO
        self._busy_feedback = BusyFeedbackController()
        self._force_close = False
        self.catalog_rows: list[dict[str, object]] = []
        self.catalog_filtered_rows: list[dict[str, object]] = []
        self.catalog_page_index = 0
        self.catalog_preserve_selection_on_refresh = True
        self.inventory_rows: list[dict[str, object]] = []
        self.inventory_filtered_rows: list[dict[str, object]] = []
        self.inventory_page_index = 0
        self.catalog_snapshot_cache: SnapshotCache[list[dict[str, object]]] = SnapshotCache()
        self.inventory_snapshot_cache: SnapshotCache[list[dict[str, object]]] = SnapshotCache()
        self.catalog_filter_debounce_timer = self._make_search_debounce_timer(
            lambda: self._run_catalog_filter_refresh()
        )
        self.inventory_filter_debounce_timer = self._make_search_debounce_timer(
            lambda: self._run_inventory_filter_refresh()
        )
        # Debounce de las búsquedas de Configuración: sin esto, cada tecla
        # disparaba una query (empleadas además con N+1) congelando la UI.
        self.settings_suppliers_debounce_timer = self._make_search_debounce_timer(
            lambda: self._refresh_settings_suppliers()
        )
        self.settings_clients_debounce_timer = self._make_search_debounce_timer(
            lambda: self._refresh_settings_clients()
        )
        self.settings_employees_debounce_timer = self._make_search_debounce_timer(
            lambda: self._refresh_settings_employees()
        )
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
        self.dashboard_help_box: QWidget | None = None
        self.products_quick_setup_box: QWidget | None = None

        self.catalog_table = QTableWidget()
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
        self.catalog_active_filters_wrap = QWidget()
        self.catalog_active_filters_flow_layout = None
        self.catalog_pagination_label = QLabel()
        self.catalog_selection_label = QLabel("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label = QLabel(build_empty_catalog_selection_view().selection_label)
        self.catalog_search_input = QLineEdit()
        self.catalog_category_filter_combo = MultiSelectFilterButton("Categoria: todas")
        self.catalog_brand_filter_combo = MultiSelectFilterButton("Marca: todas")
        self.catalog_school_filter_combo = MultiSelectFilterButton("Escuela: todas")
        self.catalog_type_filter_combo = MultiSelectFilterButton("Linea: todas")
        self.catalog_piece_filter_combo = MultiSelectFilterButton("Pieza: todas")
        self.catalog_size_filter_combo = MultiSelectFilterButton("Talla: todas", group_values_by_format=True)
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
        self.toggle_product_button = QPushButton("Desactivar toda la prenda…")
        self.edit_variant_product_combo = QComboBox()
        self.edit_variant_sku_input = QLineEdit()
        self.edit_variant_size_input = QLineEdit()
        self.edit_variant_color_input = QLineEdit()
        self.edit_variant_price_input = QLineEdit()
        self.edit_variant_cost_input = QLineEdit()
        self.update_variant_button = QPushButton("Guardar presentacion")
        self.toggle_variant_button = QPushButton("Desactivar esta talla…")
        self.delete_product_button = QPushButton("Eliminar producto")
        self.delete_variant_button = QPushButton("Eliminar presentacion")

        self.purchase_provider_combo = QComboBox()
        self.purchase_variant_combo = QComboBox()
        self.purchase_qty_spin = QSpinBox()
        self.purchase_cost_input = QLineEdit()
        self.purchase_document_input = QLineEdit()
        self.purchase_button = QPushButton("Confirmar compra")
        self.purchase_permission_label = QLabel()

        # 2026-11-12: se retiró la Caja antigua (carrito, cobro, ventas recientes).
        # Daniel: «la caja antigua ya no es de utilidad, todo lo demás corre en
        # libreta y kioskos y es lo único que importa, es donde vive nuestra operación».

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
        self.quote_remove_button = QPushButton("Quitar línea")
        self.quote_clear_button = QPushButton("Vaciar presupuesto")
        self.quote_cancel_button = QPushButton("Cancelar presupuesto")
        self.quote_whatsapp_button = QPushButton("WhatsApp")
        self.quote_refresh_button = QPushButton("Refrescar")
        self.quote_status_label = QLabel("Sin presupuestos cargados.")
        self.quote_summary_label = QLabel("Presupuesto vacio.")
        self.quote_total_label = QLabel("$0.00")
        self.quote_total_meta_label = QLabel("Presupuesto estimado")
        self.quote_customer_label = QLabel("Sin detalle.")
        self.quote_meta_label = QLabel("")
        self.quote_notes_label = QLabel("")
        self.quote_cart_table = QTableWidget()
        self.quote_table = QTableWidget()
        self.quote_detail_table = QTableWidget()
        self.quote_search_input = QLineEdit()
        self.quote_state_combo = QComboBox()

        self.logout_button = QPushButton("Cerrar sesion")

        self.inventory_variant_combo = QComboBox()
        self.inventory_adjustment_type_combo = QComboBox()
        self.inventory_adjustment_qty_spin = QSpinBox()
        self.inventory_reference_input = QLineEdit()
        self.inventory_note_input = QTextEdit()
        self.inventory_adjust_button = QPushButton("Aplicar ajuste")
        self.inventory_count_button = QPushButton("Conteo fisico")
        self.inventory_bulk_adjust_button = QPushButton("Ajuste masivo")
        self.inventory_bulk_price_button = QPushButton("Precio masivo")
        self.inventory_print_label_button = QPushButton("Imprimir etiqueta")
        self.inventory_generate_all_qr_button = QPushButton("Generar QR en lote")
        self.inventory_permission_label = QLabel()
        self.inventory_overview_label = QLabel("Elige una talla")
        self.inventory_product_label = QLabel("Toca una fila de la tabla para ver su ficha.")
        self.inventory_status_badge = QLabel("Sin selección")
        self.inventory_stock_badge = QLabel("Sin stock")
        self.inventory_stock_hint_label = QLabel("")
        self.inventory_meta_label = QLabel("")
        self.inventory_last_movement_label = QLabel("")
        self.inventory_results_label = QLabel()
        self.inventory_active_filters_label = QLabel()
        self.inventory_active_filters_wrap = QWidget()
        self.inventory_active_filters_flow_layout = None
        self.inventory_pagination_label = QLabel()
        self.inventory_search_input = QLineEdit()
        self.inventory_category_filter_combo = MultiSelectFilterButton("Categoria: todas")
        self.inventory_brand_filter_combo = MultiSelectFilterButton("Marca: todas")
        self.inventory_school_filter_combo = MultiSelectFilterButton("Escuela: todas")
        self.inventory_type_filter_combo = MultiSelectFilterButton("Tipo: todos")
        self.inventory_piece_filter_combo = MultiSelectFilterButton("Pieza: todas")
        self.inventory_size_filter_combo = MultiSelectFilterButton("Talla: todas", group_values_by_format=True)
        self.inventory_color_filter_combo = MultiSelectFilterButton("Color: todos")
        self.inventory_use_filter_combo = QComboBox()
        self.inventory_status_filter_combo = QComboBox()
        self.inventory_stock_filter_combo = QComboBox()
        self.inventory_conteo_filter_combo = QComboBox()
        self.inventory_precio_filter_combo = QComboBox()
        self.inventory_precio_text_input = QLineEdit()
        self.inventory_clear_filters_button = QPushButton("Limpiar filtros")
        self.inventory_previous_page_button = QPushButton("Anterior")
        self.inventory_next_page_button = QPushButton("Siguiente")
        self.inventory_negative_counter = QLabel("En negativo: 0")
        self.inventory_out_counter = QLabel("Agotadas: 0")
        self.inventory_low_counter = QLabel("Quedan pocas: 0")
        self.inventory_inactive_counter = QLabel("Desactivadas: 0")
        self.inventory_new_button = QToolButton()
        self.inventory_edit_button = QToolButton()
        self.inventory_stock_button = QToolButton()
        self.inventory_labels_button = QToolButton()
        self.inventory_more_button = QToolButton()
        self.inventory_table = QTableWidget()


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
        self.settings_employees_button = QPushButton("Empleadas")
        self.settings_marketing_button = QPushButton("Marketing y promociones")
        self.settings_whatsapp_button = QPushButton("WhatsApp y mensajes")
        self.settings_backup_button = QPushButton("Respaldo y restauracion")
        self.settings_business_button = QPushButton("Negocio e impresion")
        self.settings_meilisearch_button = QPushButton("Meilisearch (búsqueda)")
        self.settings_monederos_button = QPushButton("Monederos de clientes")
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
        # E1-C3: filtros de la lista y ficha de solo lectura.
        self.settings_clients_estado_combo = QComboBox()
        for _etiqueta, _estado in (
            ("Activos", admin_service.ESTADO_ACTIVOS),
            ("Inactivos", admin_service.ESTADO_INACTIVOS),
            ("Archivados", admin_service.ESTADO_ARCHIVADOS),
            ("Todos", admin_service.ESTADO_TODOS),
        ):
            self.settings_clients_estado_combo.addItem(_etiqueta, _estado)
        self.settings_clients_tipo_combo = QComboBox()
        self.settings_clients_tipo_combo.addItem("Todos los tipos", None)
        self.settings_clients_origen_combo = QComboBox()
        self.settings_clients_origen_combo.addItem("Todos los origenes", None)
        for _origen, _etiqueta in ORIGEN_ETIQUETAS.items():
            self.settings_clients_origen_combo.addItem(_etiqueta, _origen or admin_service.ORIGEN_ANTERIOR)
        # E4-D: filtro «Programa» y ventana «Programas».
        self.settings_clients_programa_combo = QComboBox()
        for _etiqueta, _valor in (
            ("Todos los programas", None),
            ("Sin programa", admin_service.PROGRAMA_NINGUNO),
            ("Con propuesta pendiente", admin_service.PROGRAMA_PENDIENTE),
            ("Maximoda Club", "CLUB"),
            ("Maximoda Profesional", "PROFESIONAL"),
            ("Maximoda Mayorista", "MAYORISTA"),
        ):
            self.settings_clients_programa_combo.addItem(_etiqueta, _valor)
        self.settings_client_programas_button = QPushButton("Programas")
        self.settings_view_client_button = QPushButton("Ver ficha")
        self.settings_create_client_button = QPushButton("Crear cliente")
        self.settings_update_client_button = QPushButton("Editar cliente")
        self.settings_toggle_client_button = QPushButton("Activar / desactivar")
        self.settings_generate_client_qr_button = QPushButton("Generar QR")
        self.settings_client_whatsapp_button = QPushButton("WhatsApp")
        self.settings_clients_dialog: QDialog | None = None
        self.settings_employees_table = QTableWidget()
        self.settings_employees_status_label = QLabel("Sin empleadas cargadas.")
        self.settings_employees_search_input = QLineEdit()
        self.settings_employees_activity_filter_combo = QComboBox()
        self.settings_create_employee_button = QPushButton("Crear empleada")
        self.settings_update_employee_button = QPushButton("Editar empleada")
        self.settings_toggle_employee_button = QPushButton("Activar / desactivar")
        self.settings_set_employee_pin_button = QPushButton("Definir PIN")
        self.settings_generate_employee_qr_button = QPushButton("Generar QR")
        self.settings_generate_employee_card_button = QPushButton("Generar credencial")
        self.settings_employee_detail_name_label = QLabel("Selecciona una empleada.")
        self.settings_employee_detail_meta_label = QLabel(
            "Aqui veras el nombre visible, codigo y estado de la seleccion."
        )
        self.settings_employee_detail_assets_label = QLabel("PIN, QR y credencial apareceran aqui.")
        self.settings_employee_detail_today_label = QLabel("Hoy: -")
        self.settings_employee_detail_last_sale_label = QLabel("Ultima venta: -")
        self.settings_employee_activity_status_label = QLabel(
            "Selecciona una empleada para revisar su actividad reciente."
        )
        self.settings_employee_toggle_amounts_button = QPushButton("Ocultar monto")
        self.settings_employee_period_combo = QComboBox()
        self.settings_employee_activity_table = QTableWidget()
        self.settings_employee_activity_table.setColumnCount(4)
        self.settings_employee_activity_table.setHorizontalHeaderLabels(["Dia", "Piezas", "Tickets", "Monto"])
        self.settings_employee_amounts_visible = False
        self.settings_employee_day_sales_table = QTableWidget()
        self.settings_employee_day_sales_status_label = QLabel("Sin tickets cargados.")
        self.settings_employee_view_ticket_button = QPushButton("Ver ticket")
        self.settings_employee_day_sales_dialog: QDialog | None = None
        self.settings_employee_sale_detail_status_label = QLabel("Sin ticket seleccionado.")
        self.settings_employee_sale_detail_table = QTableWidget()
        self.settings_employee_sale_detail_dialog: QDialog | None = None
        self.settings_open_employee_ranking_button = QPushButton("Ranking")
        self.settings_employee_ranking_table = QTableWidget()
        self.settings_employee_ranking_abonos_table = QTableWidget()
        self.settings_employee_ranking_status_label = QLabel("Sin datos.")
        self.settings_employee_ranking_period_combo = QComboBox()
        self.settings_employee_ranking_toggle_amounts_button = QPushButton("Ocultar monto")
        self.settings_employee_ranking_amounts_visible = True
        self.settings_employee_ranking_dialog: QDialog | None = None
        self.settings_employees_dialog: QDialog | None = None
        self.settings_backup_dialog: QDialog | None = None
        self.settings_business_dialog: QDialog | None = None
        self.settings_marketing_dialog: QDialog | None = None
        self.settings_whatsapp_dialog: QDialog | None = None
        self.settings_business_name_input = QLineEdit()
        self.settings_business_logo_input = QLineEdit()
        self.settings_business_logo_pick_button = QPushButton("Seleccionar")
        self.settings_business_logo_clear_button = QPushButton("Limpiar")
        self.settings_business_logo_preview_label = QLabel("Sin logo")
        self.settings_business_demo_button = QPushButton("Ver credencial demo")
        self.settings_marketing_status_label = QLabel("Sin configuración cargada.")
        self.settings_marketing_summary_label = QLabel("Sin resumen disponible.")
        self.settings_marketing_review_days_spin = QSpinBox()
        self.settings_marketing_leal_spend_spin = QDoubleSpinBox()
        self.settings_marketing_save_button = QPushButton("Guardar reglas")
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
        self.settings_whatsapp_status_label = QLabel("Sin configuración cargada.")
        self.settings_whatsapp_save_button = QPushButton("Guardar plantillas")
        self.settings_whatsapp_preview_combo = QComboBox()
        self.settings_whatsapp_preview_button = QPushButton("Vista previa")
        self.settings_whatsapp_reset_button = QPushButton("Sugeridas")
        self.settings_whatsapp_preview_output = QTextEdit()
        self.settings_business_printer_combo = QComboBox()
        self.settings_business_ticket_printer_combo = QComboBox()
        self.settings_business_copies_spin = QSpinBox()
        self.settings_business_status_label = QLabel("Sin configuración cargada.")
        self.settings_business_save_button = QPushButton("Guardar configuración")
        self.tabs: QTabWidget | None = None
        self.connection_button: QPushButton | None = None
        self.header_more_button: QToolButton | None = None
        self.connection_action: QAction | None = None
        self.quick_backup_action: QAction | None = None
        self.api_server_action: QAction | None = None
        self._api_server_process: object | None = None
        self.page_help_button: QPushButton | None = None
        self.refresh_button: QPushButton | None = None

        self._apply_styles()
        self._build_ui()
        self._configure_help_texts()
        self._configure_shortcuts()
        self.refresh_all()

    def _make_search_debounce_timer(self, slot) -> QTimer:
        """Timer estándar de debounce para búsquedas de listados."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(LISTING_SEARCH_DEBOUNCE_MS)
        timer.timeout.connect(slot)
        return timer

    def _busy_scope(self, message: str, *, status_label: QLabel | None = None):
        return self._busy_feedback.scope(
            status_label=status_label or self.status_label,
            message=message,
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        if self._api_server_process is not None and self._api_server_process.poll() is None:
            self._api_server_process.terminate()
            self._api_server_process = None

        if self._force_close:
            self._force_close = False
            event.accept()
            return

        decision = build_main_window_close_decision(is_busy=self._busy_feedback.is_busy)
        if decision.should_block:
            QMessageBox.warning(self, decision.title, decision.message)
            event.ignore()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(decision.title)
        dialog.setModal(True)
        dialog.setMinimumWidth(420)
        dlg_layout = QVBoxLayout()
        dlg_layout.setSpacing(16)
        dlg_layout.setContentsMargins(24, 24, 24, 20)
        title_label = QLabel(decision.title)
        title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #1a1a1a;")
        desc_label = QLabel(decision.message)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("subtleLine")
        dlg_layout.addWidget(title_label)
        dlg_layout.addWidget(desc_label)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("toolbarGhostButton")
        cancel_btn.clicked.connect(dialog.reject)
        close_btn = QPushButton("Cerrar aplicacion")
        close_btn.setObjectName("toolbarPrimaryButton")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(close_btn)
        dlg_layout.addLayout(btn_layout)
        dialog.setLayout(dlg_layout)
        if dialog.exec() == int(QDialog.DialogCode.Accepted):
            event.accept()
            return
        event.ignore()

    def _build_ui(self) -> None:
        self.session_label.setObjectName("heroPrimaryText")
        self.status_label.setObjectName("statusLine")
        self.metrics_label.setObjectName("subtleLine")
        self.analytics_label.setObjectName("analyticsLine")
        self.layaway_alerts_label.setObjectName("analyticsLine")

        top_actions = QHBoxLayout()
        top_actions.setSpacing(10)
        header_menu = QMenu(self)
        self.connection_action = header_menu.addAction("Verificar conexion")
        self.connection_action.triggered.connect(self._handle_test_connection)
        self.quick_backup_action = header_menu.addAction("Respaldo rapido (.dump)")
        self.quick_backup_action.triggered.connect(self._handle_quick_backup)
        header_menu.addSeparator()
        self.api_server_action = header_menu.addAction("Iniciar servidor movil")
        self.api_server_action.triggered.connect(self._toggle_api_server)
        header_menu.addSeparator()
        self.conteo_calendario_action = header_menu.addAction("Calendario de conteos")
        self.conteo_calendario_action.triggered.connect(self._handle_open_conteo_calendario)
        self.uniformes_escuela_action = header_menu.addAction("Uniformes por escuela")
        self.uniformes_escuela_action.triggered.connect(self._handle_open_uniformes_escuela)
        header_menu.addSeparator()
        self.buzon_action = header_menu.addAction("Buzón entre PCs")
        self.buzon_action.triggered.connect(self._handle_open_buzon)
        self.por_nombrar_action = header_menu.addAction("Mercancía por nombrar")
        self.por_nombrar_action.triggered.connect(self._handle_open_por_nombrar)
        # El texto dice cuántas faltan; se cuenta al abrir el menú, no antes.
        header_menu.aboutToShow.connect(self._refrescar_por_nombrar_action)
        try:
            from pos_uniformes.ui.helpers.buzon_aviso import BuzonAviso

            self._buzon_aviso = BuzonAviso(self)
        except Exception:  # noqa: BLE001 — un aviso nunca impide abrir el POS
            pass
        self.header_more_button = QToolButton()
        self.header_more_button.setText("Más")
        self.header_more_button.setObjectName("toolbarSoftButton")
        self.header_more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.header_more_button.setMenu(header_menu)
        self.page_help_button = QPushButton("?")
        self.page_help_button.setObjectName("toolbarSoftButton")
        self.page_help_button.setToolTip("Ayuda de la pestaña actual")
        self.page_help_button.clicked.connect(self._open_current_tab_help)
        self.logout_button.setText("Salir")
        self.logout_button.setObjectName("toolbarDangerButton")
        self.logout_button.clicked.connect(self._handle_logout)
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setObjectName("toolbarAccentButton")
        self.refresh_button.setToolTip("Refrescar datos")
        self.refresh_button.clicked.connect(self.refresh_all)
        top_actions.addWidget(self.page_help_button)
        top_actions.addWidget(self.header_more_button)
        top_actions.addWidget(self.logout_button)
        top_actions.addWidget(self.refresh_button)
        top_actions.addStretch()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_tab_scroll(self._build_dashboard_tab()), "Resumen")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_quotes_tab()), "Presupuestos")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_catalog_tab()), "Catálogo")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_inventory_tab()), "Inventario")
        self.tabs.addTab(self._build_bodega_tab(), "Bodega")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_history_tab()), "Historial inventarios")
        self.tabs.addTab(self._build_panel_uniformes_tab(), "Panel Uniformes")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_analytics_tab()), "Analítica")
        self.tabs.addTab(self._wrap_tab_scroll(self._build_settings_tab()), "Configuración")

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
            self.product_button: "Abre una ventana para registrar un producto nuevo y, si quieres, su primera presentacion.",
            self.variant_button: "Abre una ventana para crear una presentacion nueva con talla, color, precio y SKU.",
            self.update_product_button: "Edita los datos generales del producto seleccionado.",
            self.update_variant_button: "Edita la presentacion seleccionada, incluyendo precio, SKU, talla y color.",
            self.toggle_product_button: "Activa o desactiva la prenda con todas sus tallas (pregunta antes de desactivar).",
            self.toggle_variant_button: "Activa o desactiva solo esta talla (pregunta antes de desactivar).",
            self.delete_product_button: "Elimina el producto si no tiene stock ni historial operativo.",
            self.delete_variant_button: "Elimina la presentacion si no tiene stock ni historial operativo.",
            self.inventory_new_button: "Dar de alta una prenda, una talla o un color.",
            self.inventory_edit_button: "Editar la prenda o la talla elegida, su foto o sus precios.",
            self.inventory_stock_button: "Registrar una entrada, contar o corregir cuántas hay.",
            self.inventory_more_button: "Lo poco usado: eliminar y, en «Poco usado», los QR.",
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
            self.settings_business_button: "Abre la configuracion de negocio e impresion.",
            self.settings_marketing_save_button: "Guarda la regla de subida a Maximoda Leal.",
            self.settings_marketing_history_button: "Abre el historial de cambios en reglas y descuentos de marketing.",
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
        self.catalog_clear_filters_button.setToolTip("Limpia todos los filtros del catálogo y muestra nuevamente todo el catálogo.")
        self.inventory_table.setToolTip(
            "Elige una talla para ver su ficha. Ctrl/Cmd + clic elige varias, Shift un rango, "
            "Esc limpia y doble clic edita."
        )
        self.movements_table.setToolTip("Historial de movimientos de inventario con filtros por fecha, SKU y tipo.")
        aplicar_ayudas_inventario(self)

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
            "inventory": (
                "Ayuda de inventario",
                [
                    "Selecciona una presentacion en la tabla para ver su ficha y sus acciones.",
                    "Usa los menus Nuevo, Editar, Stock y Mas para administrar catalogo, existencias y QR.",
                    "El panel lateral muestra estado, stock, ultimo movimiento y vista previa del QR.",
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
        # 2026-11-12: F2 (cobrar), F8 (captura de SKU), F6 (ventas recientes),
        # y Supr (quitar línea) eran de la Caja antigua y se retiraron con ella.
        # Daniel: «la caja antigua ya no es de utilidad, todo lo demás corre en
        # libreta y kioskos». Ctrl+S / Cmd+S se queda solo para consultar precio
        # y existencia, sin agregar a ningún carrito. Escape se queda solo para
        # limpiar Presupuestos y Catálogo.
        clear_capture_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        clear_capture_shortcut.activated.connect(self._handle_escape)
        quick_backup_shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), self)
        quick_backup_shortcut.activated.connect(self._handle_quick_backup)
        quick_backup_shortcut_mac = QShortcut(QKeySequence("Meta+Shift+B"), self)
        quick_backup_shortcut_mac.activated.connect(self._handle_quick_backup)
        # Ctrl+Shift+M mapa de escuelas · Ctrl+Shift+E tipos de escocés (2026-11-07).
        from pos_uniformes.ui.helpers.abrir_consultas import instalar_atajos

        self._atajos_consultas = instalar_atajos(self)
        from pos_uniformes.ui.helpers.abrir_consultas import instalar_busqueda_de_consulta

        self._atajos_busqueda = instalar_busqueda_de_consulta(self)
        # Ctrl+K global via event filter (funciona incluso en diálogos modales)
        from PyQt6.QtWidgets import QApplication

        self._kiosk_filter = _KioskKeyFilter(self)
        QApplication.instance().installEventFilter(self._kiosk_filter)

    def _open_quick_kiosk(self) -> None:
        from pos_uniformes.ui.dialogs.quick_kiosk_dialog import QuickKioskDialog

        if not hasattr(self, "_quick_kiosk_dialog") or self._quick_kiosk_dialog is None:
            self._quick_kiosk_dialog = QuickKioskDialog(self)
        self._quick_kiosk_dialog.show()
        self._quick_kiosk_dialog.raise_()
        self._quick_kiosk_dialog.activateWindow()

    def _handle_escape(self) -> None:
        idx = self.tabs.currentIndex() if self.tabs else -1
        tab_name = self.tabs.tabText(idx) if self.tabs and idx >= 0 else ""
        if tab_name == "Presupuestos":
            self._clear_quote_capture()
        elif tab_name == "Catálogo":
            self._clear_catalog_capture()

    def _clear_quote_capture(self) -> None:
        self.quote_sku_input.clear()
        self.quote_qty_spin.setValue(1)
        self.quote_client_combo.setCurrentIndex(0)

    def _clear_catalog_capture(self) -> None:
        if hasattr(self, "catalog_search_input"):
            self.catalog_search_input.clear()
            self.catalog_search_input.setFocus()

    def _apply_role_navigation(self) -> None:
        if self.tabs is None:
            return

        is_admin = self.current_role == RolUsuario.ADMIN
        visible_by_index = {
            # 2026-11-12: las pestañas Caja (antes índice 1) y Apartados
            # (antes índice 2) ya no se construyen.
            0: is_admin,  # Resumen
            1: True,      # Presupuestos
            2: True,      # Catalogo
            3: is_admin,  # Inventario
            4: is_admin,  # Bodega
            5: is_admin,  # Historial inventarios
            6: is_admin,  # Panel Uniformes
            7: is_admin,  # Analitica
            8: is_admin,  # Configuracion
        }
        # Estas ya no viven aquí: los presupuestos se hacen en Presupuesto
        # guiado y el catálogo en Panel Uniformes e Inventario. Se ocultan,
        # no se borran — sus datos siguen intactos. Para volver a verlas,
        # vaciar PESTANAS_MUDADAS_AL_KIOSKO.
        # (La Caja antigua y Apartados ya no se ocultan: se retiraron, 2026-11-12.)
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index).strip() in PESTANAS_MUDADAS_AL_KIOSKO:
                visible_by_index[index] = False

        for index, is_visible in visible_by_index.items():
            self.tabs.setTabVisible(index, is_visible)

        current_index = self.tabs.currentIndex()
        if not visible_by_index.get(current_index, False):
            self.tabs.setCurrentIndex(self._primera_pestana_visible(visible_by_index, is_admin))

    @staticmethod
    def _primera_pestana_visible(visible_by_index: dict, is_admin: bool) -> int:
        """A dónde caer cuando la pestaña actual quedó oculta."""
        preferida = 0 if is_admin else 1
        if visible_by_index.get(preferida, False):
            return preferida
        return next((i for i, visible in sorted(visible_by_index.items()) if visible), 0)

    def _focus_default_tab_for_role(self) -> None:
        if self.tabs is None:
            return
        preferida = 0 if self.current_role == RolUsuario.ADMIN else 1
        if not self.tabs.isTabVisible(preferida):
            preferida = next(
                (i for i in range(self.tabs.count()) if self.tabs.isTabVisible(i)), 0
            )
        self.tabs.setCurrentIndex(preferida)
        self.tabs.update()
        self.tabs.repaint()

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

    def _build_quotes_tab(self) -> QWidget:
        return build_quotes_tab(self)

    def _build_inventory_tab(self) -> QWidget:
        return build_inventory_tab(self)

    def _build_bodega_tab(self) -> QWidget:
        return build_bodega_tab(self)

    def _build_analytics_tab(self) -> QWidget:
        return build_analytics_tab(self)

    def _build_history_tab(self) -> QWidget:
        return build_history_tab(self)

    def _build_settings_tab(self) -> QWidget:
        return build_settings_tab(self)

    def _build_panel_uniformes_tab(self) -> QWidget:
        return build_panel_uniformes_tab(self)

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

    def _open_employees_settings_dialog(self) -> None:
        if self.settings_employees_dialog is None:
            self.settings_employees_dialog = build_employees_settings_dialog(self)

        self.settings_employee_amounts_visible = False
        self._refresh_settings_employees()
        self.settings_employees_dialog.show()
        self.settings_employees_dialog.raise_()
        self.settings_employees_dialog.activateWindow()

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

    def _open_monederos_settings_dialog(self) -> None:
        from pos_uniformes.ui.dialogs.monederos_dialog import open_monederos_dialog

        open_monederos_dialog(self, usuario_id=self.user_id)

    def _open_meilisearch_settings_dialog(self) -> None:
        from pos_uniformes.ui.dialogs.meilisearch_settings_dialog import open_meilisearch_settings_dialog
        open_meilisearch_settings_dialog(self)

    def _handle_open_uniforms_panel(self) -> None:
        # Navegar a la pestaña Panel Uniformes (índice 6 desde que se
        # retiraron las pestañas Caja y Apartados, 2026-11-12)
        if self.tabs is not None:
            self.tabs.setCurrentIndex(6)

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
                ticket_printer_index = self.settings_business_ticket_printer_combo.findData(snapshot.ticket_printer)
                self.settings_business_ticket_printer_combo.setCurrentIndex(ticket_printer_index if ticket_printer_index >= 0 else 0)
                self.settings_business_copies_spin.setValue(snapshot.ticket_copies)
                self.settings_business_status_label.setText("Configuración cargada correctamente.")
                self.settings_marketing_status_label.setText("Reglas de marketing cargadas correctamente.")
                self.settings_whatsapp_status_label.setText("Plantillas cargadas correctamente.")
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
            impresora_tickets=str(self.settings_business_ticket_printer_combo.currentData() or ""),
            copias_ticket=self.settings_business_copies_spin.value(),
        )

    def _refresh_marketing_summary(self, session) -> None:
        clientes = session.scalars(select(Cliente.id)).all()
        self.settings_marketing_summary_label.setText(
            build_settings_marketing_summary_label(list(clientes))
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
        self.settings_business_status_label.setText("Logo listo para guardarse en la configuración.")

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
            loyalty_level="",
            level_label="",
            primary_color=COLOR_ESTANDAR_PRIMARIO,
            secondary_color=COLOR_ESTANDAR_SECUNDARIO,
            qr_path=str(sample_qr),
            client_code="CLI-000123",
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

    def _refresh_settings_users(self, session=None) -> None:
        try:
            if session is not None:
                users = UserService.list_users(session)
            else:
                with get_session() as s:
                    users = UserService.list_users(s)
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

    def _refresh_settings_suppliers(self, *, session=None) -> None:
        # session keyword-only: conectar este método directo a textChanged
        # metía el TEXTO tecleado como session y caía a la vista de error.
        search_text = self.settings_suppliers_search_input.text().strip()
        try:
            if session is not None:
                suppliers = SupplierService.list_suppliers(session, search_text)
            else:
                with get_session() as s:
                    suppliers = SupplierService.list_suppliers(s, search_text)
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

    def _refresh_settings_clients(self, *, session=None) -> None:
        """E1-C3: lista del ADMIN con filtros de estado, tipo y origen.

        Sin columnas de Nivel ni Desc. (D5)."""
        search_text = self.settings_clients_search_input.text().strip()
        estado = self.settings_clients_estado_combo.currentData() or admin_service.ESTADO_ACTIVOS
        tipo_clave = self.settings_clients_tipo_combo.currentData() or None
        origen = self.settings_clients_origen_combo.currentData() or None
        programa_combo = getattr(self, "settings_clients_programa_combo", None)  # E4-D
        programa = (programa_combo.currentData() if programa_combo is not None else None) or None

        def _cargar(s):
            if self.settings_clients_tipo_combo.count() <= 1:
                for clave, nombre in tipos_para_combo(s):
                    self.settings_clients_tipo_combo.addItem(nombre, clave)
            return admin_service.listar_para_admin(
                s, self.user_id, texto=search_text, estado=estado, tipo_clave=tipo_clave, origen=origen,
                programa=programa,
            )

        try:
            if session is not None:
                filas = _cargar(session)
            else:
                with get_session() as s:
                    filas = _cargar(s)
        except Exception as exc:  # noqa: BLE001
            clients_view = build_settings_clients_error_view(str(exc))
            self.settings_clients_status_label.setText(clients_view.status_label)
            self.settings_clients_table.setRowCount(len(clients_view.rows))
            return
        clients_view = build_clientes_admin_view(
            [
                {
                    "id": fila.id,
                    "code": fila.codigo,
                    "name": fila.nombre,
                    "tipo": fila.tipo,
                    "phone": fila.telefono,
                    "origen": etiqueta_origen(fila.origen),
                    "alta": format_display_datetime(fila.alta),
                    "qr_label": "Listo" if QrGenerator.exists_for_client(SimpleNamespace(codigo_cliente=fila.codigo)) else "Pendiente",
                    "card_label": (
                        "Lista" if CustomerCardService.exists_for_client(SimpleNamespace(codigo_cliente=fila.codigo)) else "Pendiente"
                    ),
                    "status_label": "ARCHIVADO" if fila.archivado else ("ACTIVO" if fila.activo else "INACTIVO"),
                    "notes": fila.notas,
                    "programa": fila.programa,
                }
                for fila in filas
            ],
            estado_label=self.settings_clients_estado_combo.currentText(),
        )
        tabla_clientes = self.settings_clients_table
        encabezados_actuales = [
            (tabla_clientes.horizontalHeaderItem(i).text() if tabla_clientes.horizontalHeaderItem(i) else "")
            for i in range(tabla_clientes.columnCount())
        ]
        if encabezados_actuales != list(CLIENTES_ADMIN_COLUMNAS):  # E4-D: también si cambian los textos
            self.settings_clients_table.setColumnCount(len(CLIENTES_ADMIN_COLUMNAS))
            self.settings_clients_table.setHorizontalHeaderLabels(list(CLIENTES_ADMIN_COLUMNAS))
        self.settings_clients_table.setRowCount(len(clients_view.rows))
        for row_index, client_row in enumerate(clients_view.rows):
            for column_index, value in enumerate(client_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole + 1, client_row.client_code)
                if column_index == 1:
                    item.setData(Qt.ItemDataRole.UserRole, client_row.client_id)
                if column_index == COLUMNA_QR:
                    _set_table_badge_style(item, client_row.qr_tone)
                if column_index == COLUMNA_CREDENCIAL:
                    _set_table_badge_style(item, client_row.card_tone)
                if column_index == COLUMNA_ESTADO:
                    _set_table_badge_style(item, client_row.status_tone)
                self.settings_clients_table.setItem(row_index, column_index, item)
        self.settings_clients_table.resizeColumnsToContents()  # Programa y Notas se estiran solas (settings_dialogs)
        self.settings_clients_status_label.setText(clients_view.status_label)

    def _handle_view_client_ficha(self) -> None:
        """E1-C3: ficha de solo lectura del cliente seleccionado."""
        client_id = self._selected_settings_client_id()
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permiso", "Solo ADMIN puede ver la ficha del cliente.")
            return
        if client_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un cliente en la tabla.")
            return
        try:
            with get_session() as session:
                ficha = cargar_ficha_cliente(session, cliente_id=client_id, usuario_id=self.user_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir la ficha", str(exc))
            return
        from pos_uniformes.ui.dialogs.cliente_fidelizacion_panel import FidelizacionPanel

        panel = FidelizacionPanel(get_session, cliente_id=client_id, usuario_id=self.user_id)  # E4-D
        construir_ficha_dialog(self, ficha, panel_fidelizacion=panel).exec()
        if panel.hubo_cambios:
            self._refresh_settings_clients()

    def _handle_open_rebajas(self) -> None:
        """E7: «Ofertas y liquidación» (solo ADMIN)."""
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permiso", "Solo ADMIN puede poner prendas en oferta o liquidación.")
            return
        from pos_uniformes.ui.dialogs.rebajas_dialog import RebajasDialog, imprimir_etiqueta_rebaja

        RebajasDialog(
            self, get_session, usuario_id=self.user_id,
            imprimir=lambda fila: imprimir_etiqueta_rebaja(fila, self._print_image_path),
        ).exec()
        # La columna «Precio» de Inventario muestra «Oferta $X»: que se vea al cerrar.
        self._invalidate_listing_snapshot_caches(catalog=False, inventory=True)
        self._handle_inventory_filters_changed()

    def _handle_open_programas(self) -> None:
        """E4-D: ventana «Programas» (solo ADMIN)."""
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permiso", "Solo ADMIN puede administrar los programas.")
            return
        from pos_uniformes.ui.dialogs.programas_dialog import ProgramasDialog

        ProgramasDialog(self, get_session, usuario_id=self.user_id).exec()
        self._refresh_settings_clients()

    def _refresh_settings_employees(self) -> None:
        search_text = self.settings_employees_search_input.text().strip()
        activity_filter = self.settings_employees_activity_filter_combo.currentText().strip()
        selected_employee_id = self._selected_settings_employee_id()
        try:
            with get_session() as session:
                employees = EmployeeIdentityService.list_employees(session, search_text)
                # Batch: una sola query de ventas para todas (antes era un
                # N+1 por empleada que congelaba la pestaña al teclear).
                try:
                    employee_activity_snapshots = dict(
                        load_employee_activity_snapshots(session, employees)
                    )
                except Exception:  # noqa: BLE001
                    employee_activity_snapshots = {}
                employee_activity_states: dict[int, tuple[str, str]] = {}
                for employee in employees:
                    activity_snapshot = employee_activity_snapshots.get(int(employee.id))
                    if activity_snapshot is None:
                        activity_snapshot = build_employee_activity_empty_snapshot()
                        employee_activity_snapshots[int(employee.id)] = activity_snapshot
                    activity_state = build_employee_activity_state(activity_snapshot)
                    employee_activity_states[int(employee.id)] = (activity_state.label, activity_state.tone)
            self._employee_activity_snapshots_cache = employee_activity_snapshots
        except Exception as exc:  # noqa: BLE001
            employees_view = build_settings_employees_error_view(str(exc))
            self.settings_employees_status_label.setText(employees_view.status_label)
            self.settings_employees_table.setRowCount(len(employees_view.rows))
            self._refresh_settings_employee_detail()
            return
        sorted_employees = sorted(
            employees,
            key=lambda employee: build_employee_activity_sort_key(employee_activity_snapshots[int(employee.id)]),
        )
        filtered_employees = [
            employee
            for employee in sorted_employees
            if not activity_filter
            or activity_filter == "Todas"
            or employee_activity_states[int(employee.id)][0] == activity_filter
        ]
        employees_view = build_settings_employees_view(
            [
                {
                    "id": int(employee.id),
                    "code": employee.codigo,
                    "name": employee.nombre_completo,
                    "display_name": EmployeeIdentityService.build_visible_employee_name(employee.nombre_completo),
                    "activity_label": employee_activity_states[int(employee.id)][0],
                    "activity_tone": employee_activity_states[int(employee.id)][1],
                    "pin_label": "Listo" if EmployeeIdentityService.has_pin(employee) else "Pendiente",
                    "qr_label": "Listo" if QrGenerator.exists_for_employee(employee) else "Pendiente",
                    "card_label": "Lista" if EmployeeCardService.exists_for_employee(employee) else "Pendiente",
                    "active": bool(employee.activo),
                    "active_label": "ACTIVA" if employee.activo else "INACTIVA",
                    "updated_label": format_display_datetime(employee.updated_at),
                }
                for employee in filtered_employees
            ]
        )
        self.settings_employees_table.blockSignals(True)
        self.settings_employees_table.setRowCount(len(employees_view.rows))
        for row_index, employee_row in enumerate(employees_view.rows):
            for column_index, value in enumerate(employee_row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, employee_row.employee_id)
                if column_index == 3:
                    _set_table_badge_style(item, employee_row.activity_tone)
                if column_index == 4:
                    _set_table_badge_style(item, employee_row.pin_tone)
                if column_index == 5:
                    _set_table_badge_style(item, employee_row.qr_tone)
                if column_index == 6:
                    _set_table_badge_style(item, employee_row.card_tone)
                if column_index == 7:
                    _set_table_badge_style(item, employee_row.status_tone)
                self.settings_employees_table.setItem(row_index, column_index, item)
        self.settings_employees_table.resizeColumnsToContents()
        restored_row = -1
        if selected_employee_id is not None:
            for row_index in range(self.settings_employees_table.rowCount()):
                item = self.settings_employees_table.item(row_index, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_employee_id:
                    restored_row = row_index
                    break
        if restored_row >= 0:
            self.settings_employees_table.setCurrentCell(restored_row, 0)
        elif self.settings_employees_table.rowCount() > 0:
            self.settings_employees_table.clearSelection()
            self.settings_employees_table.setCurrentItem(None)
        self.settings_employees_table.blockSignals(False)
        if activity_filter and activity_filter != "Todas":
            self.settings_employees_status_label.setText(
                f"{employees_view.status_label} | filtro: {activity_filter}"
            )
        else:
            self.settings_employees_status_label.setText(employees_view.status_label)
        self._refresh_settings_employee_detail()

    def _refresh_settings_employee_detail(self) -> None:
        employee_id = self._selected_settings_employee_id()
        summary_days = self._selected_settings_employee_summary_days()
        if employee_id is None:
            snapshot = build_employee_activity_empty_snapshot()
            self._apply_settings_employee_detail_snapshot(snapshot, has_selection=False)
            return
        cache = getattr(self, "_employee_activity_snapshots_cache", {})
        if summary_days == 1 and employee_id in cache:
            self._apply_settings_employee_detail_snapshot(cache[employee_id], has_selection=True)
            return
        try:
            with get_session() as session:
                snapshot = load_employee_activity_snapshot(session, employee_id=employee_id, summary_days=summary_days)
        except Exception as exc:  # noqa: BLE001
            self.settings_employee_detail_name_label.setText("Detalle no disponible.")
            self.settings_employee_detail_meta_label.setText(str(exc))
            self.settings_employee_detail_assets_label.setText("No se pudo cargar el resumen de la empleada.")
            self.settings_employee_detail_today_label.setText(f"{self.settings_employee_period_combo.currentText() or 'Hoy'}: -")
            self.settings_employee_detail_last_sale_label.setText("Ultima venta: -")
            self.settings_employee_activity_status_label.setText("Actividad no disponible.")
            self.settings_employee_activity_table.setRowCount(0)
            self._refresh_settings_employee_amount_visibility()
            return
        self._apply_settings_employee_detail_snapshot(snapshot, has_selection=True)

    def _selected_settings_employee_summary_days(self) -> int:
        raw_value = self.settings_employee_period_combo.currentText().strip().lower()
        if raw_value == "7 dias":
            return 7
        if raw_value == "30 dias":
            return 30
        return 1

    def _apply_settings_employee_detail_snapshot(self, snapshot, *, has_selection: bool) -> None:
        if not has_selection:
            self.settings_employee_detail_name_label.setText("Selecciona una empleada.")
            self.settings_employee_detail_meta_label.setText(
                "Aqui veras el nombre visible, codigo y estado de la seleccion."
            )
            self.settings_employee_detail_assets_label.setText("PIN, QR y credencial apareceran aqui.")
            self.settings_employee_detail_today_label.setText(f"{self.settings_employee_period_combo.currentText() or 'Hoy'}: -")
            self.settings_employee_detail_last_sale_label.setText("Ultima venta: -")
            self.settings_employee_activity_status_label.setText(
                "Selecciona una empleada para revisar sus ultimos 7 dias."
            )
        else:
            self.settings_employee_detail_name_label.setText(snapshot.visible_name or snapshot.full_name or "Sin nombre")
            self.settings_employee_detail_meta_label.setText(
                f"Codigo: {snapshot.employee_code} | Estado: {snapshot.active_label}"
            )
            self.settings_employee_detail_assets_label.setText(
                f"PIN: {snapshot.pin_label} | QR: {snapshot.qr_label} | Credencial: {snapshot.card_label}"
            )
            today_text = f"{snapshot.period_label}: {snapshot.period_pieces} piezas | {snapshot.period_tickets} tickets"
            if self.settings_employee_amounts_visible:
                today_text = f"{today_text} | ${snapshot.period_amount:,.2f}"
            self.settings_employee_detail_today_label.setText(today_text)
            if snapshot.last_sale_at is None:
                self.settings_employee_detail_last_sale_label.setText("Ultima venta: Sin ventas en la Libreta.")
            else:
                self.settings_employee_detail_last_sale_label.setText(
                    f"Ultima venta: {format_display_datetime(snapshot.last_sale_at)}"
                )
            self.settings_employee_activity_status_label.setText(
                "Ultimos 7 dias de lo que vendio en la Libreta (ventas y apartados; monto: solo ventas)."
            )

        self.settings_employee_activity_table.setRowCount(len(snapshot.day_rows) if has_selection else 0)
        if has_selection:
            for row_index, day_row in enumerate(snapshot.day_rows):
                values = (
                    day_row.day_label,
                    str(day_row.pieces),
                    str(day_row.tickets),
                    f"${day_row.amount:,.2f}",
                )
                for column_index, value in enumerate(values):
                    item = _table_item(value)
                    if column_index == 0:
                        item.setData(Qt.ItemDataRole.UserRole, day_row.day)
                    self.settings_employee_activity_table.setItem(row_index, column_index, item)
            self.settings_employee_activity_table.resizeColumnsToContents()
        self._refresh_settings_employee_amount_visibility()

    def _handle_toggle_settings_employee_amounts(self) -> None:
        if not self.settings_employee_amounts_visible:
            if not self._prompt_settings_employee_amount_access():
                return
            self.settings_employee_amounts_visible = True
        else:
            self.settings_employee_amounts_visible = False
        self._refresh_settings_employee_detail()

    def _refresh_settings_employee_amount_visibility(self) -> None:
        self.settings_employee_toggle_amounts_button.setText(
            "Ocultar monto" if self.settings_employee_amounts_visible else "Mostrar monto"
        )
        self.settings_employee_activity_table.setColumnHidden(3, not self.settings_employee_amounts_visible)

    def _selected_settings_employee_activity_day(self) -> date | None:
        selected_row = self.settings_employee_activity_table.currentRow()
        item = self.settings_employee_activity_table.item(selected_row, 0)
        raw_day = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(raw_day, date):
            return None
        return raw_day

    def _selected_settings_employee_day_sale_id(self) -> int | None:
        selected_row = self.settings_employee_day_sales_table.currentRow()
        item = self.settings_employee_day_sales_table.item(selected_row, 0)
        raw_sale_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if raw_sale_id is None:
            return None
        return int(raw_sale_id)

    def _open_settings_employee_day_sales_dialog(self) -> None:
        employee_id = self._selected_settings_employee_id()
        target_day = self._selected_settings_employee_activity_day()
        if employee_id is None or target_day is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un dia del historial para ver sus tickets.")
            return
        try:
            with get_session() as session:
                employee = session.get(Empleada, employee_id)
                if employee is None:
                    raise ValueError("No se encontro la empleada seleccionada.")
                rows = list_employee_day_sale_rows(session, employee_code=str(employee.codigo), target_day=target_day)
                visible_name = EmployeeIdentityService.build_visible_employee_name(str(employee.nombre_completo))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudieron cargar tickets", str(exc))
            return

        if self.settings_employee_day_sales_dialog is None:
            from pos_uniformes.ui.dialogs.settings_dialogs import build_employee_day_sales_dialog

            self.settings_employee_day_sales_dialog = build_employee_day_sales_dialog(self)

        self.settings_employee_day_sales_dialog.setWindowTitle(
            f"{visible_name or 'Empleada'} · {format_display_date(target_day)}"
        )
        self.settings_employee_day_sales_status_label.setText(
            f"Operaciones de la Libreta del dia: {len(rows)}"
            if rows
            else "No vendio nada en la Libreta ese dia."
        )
        self.settings_employee_day_sales_table.setRowCount(len(rows))
        for row_index, row_view in enumerate(rows):
            for column_index, value in enumerate(row_view.values):
                display_value = f"${Decimal(value):,.2f}" if column_index == 4 else value
                item = _table_item(display_value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row_view.sale_id)
                self.settings_employee_day_sales_table.setItem(row_index, column_index, item)
        if rows:
            self.settings_employee_day_sales_table.setCurrentCell(0, 0)
        else:
            self.settings_employee_day_sales_table.clearSelection()
            self.settings_employee_day_sales_table.setCurrentItem(None)
        self.settings_employee_day_sales_table.resizeColumnsToContents()
        self._refresh_settings_employee_day_sale_actions()
        self.settings_employee_day_sales_dialog.show()
        self.settings_employee_day_sales_dialog.raise_()
        self.settings_employee_day_sales_dialog.activateWindow()

    def _refresh_settings_employee_day_sale_actions(self) -> None:
        self.settings_employee_view_ticket_button.setEnabled(self._selected_settings_employee_day_sale_id() is not None)

    def _open_employee_ranking_dialog(self) -> None:
        if self.settings_employee_ranking_dialog is None:
            from pos_uniformes.ui.dialogs.settings_dialogs import build_employee_ranking_dialog

            self.settings_employee_ranking_dialog = build_employee_ranking_dialog(self)
        self._refresh_employee_ranking()
        self.settings_employee_ranking_dialog.show()
        self.settings_employee_ranking_dialog.raise_()
        self.settings_employee_ranking_dialog.activateWindow()

    def _refresh_employee_ranking(self) -> None:
        from datetime import timedelta

        period = self.settings_employee_ranking_period_combo.currentText().strip() or "Hoy"
        start_date, end_date = build_ranking_period_dates(period)
        period_label = {
            "Hoy": "hoy",
            "7 dias": "ultimos 7 dias",
            "Este mes": "este mes",
        }.get(period, period.lower())
        # Fuente: la Libreta (kioskos). El POS formal ya no registra ventas, así
        # que su ranking (`load_employee_ranking`) dejó de recibir datos.
        from pos_uniformes.services import ranking_libreta_service

        try:
            with get_session() as session:
                ranking_rows = ranking_libreta_service.cargar(session, start_date, end_date)
        except Exception as exc:  # noqa: BLE001
            self.settings_employee_ranking_status_label.setText(f"No se pudo cargar el ranking: {exc}")
            self.settings_employee_ranking_table.setRowCount(0)
            self.settings_employee_ranking_abonos_table.setRowCount(0)
            return
        view = build_libreta_ranking_view(
            ranking_rows,
            period_label=period_label,
            amounts_visible=self.settings_employee_ranking_amounts_visible,
        )
        self.settings_employee_ranking_status_label.setText(view.status_label)
        self.settings_employee_ranking_table.setRowCount(len(view.rows))
        for row_index, row in enumerate(view.rows):
            for col_index, value in enumerate(row.values):
                item = _table_item(value)
                if col_index in {0, 2, 3, 4, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_index in {5, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if row.is_top:
                    item.setForeground(self.palette().highlight())
                self.settings_employee_ranking_table.setItem(row_index, col_index, item)
        abonos = self.settings_employee_ranking_abonos_table
        abonos.setRowCount(len(view.abonos_rows))
        for row_index, values in enumerate(view.abonos_rows):
            for col_index, value in enumerate(values):
                item = _table_item(value)
                if col_index == 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_index == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                abonos.setItem(row_index, col_index, item)
        if view.rows:
            self.settings_employee_ranking_table.setCurrentCell(0, 0)
        else:
            self.settings_employee_ranking_table.clearSelection()

    def _handle_toggle_employee_ranking_amounts(self) -> None:
        self.settings_employee_ranking_amounts_visible = not self.settings_employee_ranking_amounts_visible
        self.settings_employee_ranking_toggle_amounts_button.setText(
            "Ocultar monto" if self.settings_employee_ranking_amounts_visible else "Mostrar monto"
        )
        self._refresh_employee_ranking()

    def _handle_view_settings_employee_day_sale_ticket(self) -> None:
        sale_id = self._selected_settings_employee_day_sale_id()
        if sale_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un ticket del listado para abrirlo.")
            return
        try:
            with get_session() as session:
                snapshot = load_employee_sale_detail_snapshot(session, sale_id=sale_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

        if self.settings_employee_sale_detail_dialog is None:
            from pos_uniformes.ui.dialogs.settings_dialogs import build_employee_sale_detail_dialog

            self.settings_employee_sale_detail_dialog = build_employee_sale_detail_dialog(self)

        self.settings_employee_sale_detail_dialog.setWindowTitle(
            f"{snapshot.folio or 'Ticket'} · {snapshot.time_label}"
        )
        self.settings_employee_sale_detail_status_label.setText(
            f"Cliente: {snapshot.client_name} | Piezas: {snapshot.pieces} | Total: ${snapshot.total:,.2f}"
        )
        self.settings_employee_sale_detail_table.setRowCount(len(snapshot.rows))
        for row_index, row_view in enumerate(snapshot.rows):
            for column_index, value in enumerate(row_view.values):
                display_value = f"${Decimal(value):,.2f}" if column_index in {3, 4} else value
                item = _table_item(display_value)
                self.settings_employee_sale_detail_table.setItem(row_index, column_index, item)
        self.settings_employee_sale_detail_table.resizeColumnsToContents()
        self.settings_employee_sale_detail_dialog.show()
        self.settings_employee_sale_detail_dialog.raise_()
        self.settings_employee_sale_detail_dialog.activateWindow()

    def _prompt_settings_employee_amount_access(self) -> bool:
        password, accepted = QInputDialog.getText(
            self,
            "Mostrar montos",
            "Captura tu contrasena para ver montos en Empleadas.",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return False
        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None or not user.activo:
                    raise ValueError("No se pudo validar tu usuario actual.")
                if not AuthService.verify_password(password, str(user.password_hash)):
                    raise ValueError("La contrasena no coincide.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Acceso denegado", str(exc))
            return False
        return True

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

    def _selected_settings_employee_id(self) -> int | None:
        selected_row = self.settings_employees_table.currentRow()
        item = self.settings_employees_table.item(selected_row, 0)
        raw_employee_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return resolve_selected_settings_employee_id(
            current_row=selected_row,
            raw_employee_id=raw_employee_id,
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
        try:
            with get_session() as session:
                tipos = tipos_para_combo(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        # E1-C1: la ficha pide identidad y tipo; no hay nivel ni descuento (D5).
        data = prompt_cliente_ficha(
            self,
            title="Crear cliente",
            helper_text="Captura nombre, telefono y tipo del cliente.",
            tipos=tipos,
        )
        if data is None:
            return
        try:
            with get_session() as session:
                result = crear_cliente(
                    session,
                    admin_user_id=self.user_id,
                    datos=data,
                    render_card=self._render_client_card_safe,
                )
                session.commit()
        except CoincidenciasPorConfirmarError as exc:
            QMessageBox.warning(self, "Teléfono ya registrado", mensaje_telefono_ya_registrado(exc.coincidencias))
            return
        except TelefonoInvalidoError as exc:
            QMessageBox.warning(self, "Teléfono inválido", str(exc))
            return
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
                actuales = cargar_ficha(session, client_id=client_id)
                tipos = tipos_para_combo(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if actuales.get("archivado") == "1":
            QMessageBox.warning(self, "Ficha archivada", "La ficha esta archivada y no se puede editar.")
            return
        # E1-C1: editar nunca toca nivel, descuento ni programas (C1).
        data = prompt_cliente_ficha(
            self,
            title="Editar cliente",
            helper_text="Actualiza nombre, telefono, tipo o notas del cliente.",
            tipos=tipos,
            current_values=actuales,
        )
        if data is None:
            return

        try:
            with get_session() as session:
                result = editar_cliente(
                    session,
                    admin_user_id=self.user_id,
                    client_id=client_id,
                    datos=data,
                )
                session.commit()
        except CoincidenciasPorConfirmarError as exc:
            QMessageBox.warning(self, "Teléfono ya registrado", mensaje_telefono_ya_registrado(exc.coincidencias))
            return
        except TelefonoInvalidoError as exc:
            QMessageBox.warning(self, "Teléfono inválido", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_client_result_feedback(
            "update_client",
            client_name=result.client_name,
            asset_path=None,
            asset_error=None,
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
        # E1-C1: activar o desactivar pide un motivo y deja evento.
        motivo = prompt_motivo(
            self,
            title="Cambiar estado del cliente",
            helper_text="Escribe por que se activa o desactiva esta ficha. Queda en su historial.",
        )
        if motivo is None:
            return
        try:
            with get_session() as session:
                result = alternar_estado(
                    session,
                    admin_user_id=self.user_id,
                    client_id=client_id,
                    motivo=motivo,
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
            with self._busy_scope(
                "Clientes: generando QR del cliente...",
                status_label=self.settings_clients_status_label,
            ), get_session() as session:
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

    def _handle_create_employee(self) -> None:
        feedback = build_settings_employee_guard_feedback(
            "create_employee",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=False,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        data = prompt_employee_data(
            self,
            title="Crear empleada",
            helper_text="Captura el nombre completo del equipo comercial. El codigo EMP se genera automaticamente.",
            generated_code="Se genera automaticamente",
        )
        if data is None:
            return
        try:
            with get_session() as session:
                result = create_settings_employee(
                    session,
                    admin_user_id=self.user_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_employee_result_feedback(
            "create_employee",
            employee_name=result.employee_name,
            employee_code=result.employee_code,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_update_employee(self) -> None:
        employee_id = self._selected_settings_employee_id()
        feedback = build_settings_employee_guard_feedback(
            "update_employee",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=employee_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_employee_prompt_snapshot(session, employee_id=employee_id)
                data = prompt_employee_data(
                    self,
                    title="Editar empleada",
                    helper_text="Actualiza el nombre visible del equipo comercial. El codigo se mantiene fijo.",
                    current_values={
                        "codigo": prompt_snapshot.code,
                        "nombre_completo": prompt_snapshot.full_name,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if data is None:
            return

        try:
            with get_session() as session:
                result = update_settings_employee(
                    session,
                    admin_user_id=self.user_id,
                    employee_id=employee_id,
                    payload=data,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_employee_result_feedback(
            "update_employee",
            employee_name=result.employee_name,
            employee_code=result.employee_code,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_toggle_employee(self) -> None:
        employee_id = self._selected_settings_employee_id()
        feedback = build_settings_employee_guard_feedback(
            "toggle_employee",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=employee_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                result = toggle_settings_employee(
                    session,
                    admin_user_id=self.user_id,
                    employee_id=employee_id,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Operacion fallida", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_employee_result_feedback(
            "toggle_employee",
            employee_name=result.employee_name,
            employee_code=result.employee_code,
            status_text=result.status_text,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_set_employee_pin(self) -> None:
        employee_id = self._selected_settings_employee_id()
        feedback = build_settings_employee_guard_feedback(
            "set_employee_pin",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=employee_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with get_session() as session:
                prompt_snapshot = load_settings_employee_prompt_snapshot(session, employee_id=employee_id)
                pin = prompt_employee_pin(self, employee_name=prompt_snapshot.full_name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "PIN invalido", str(exc))
            return
        if pin is None:
            return

        try:
            with get_session() as session:
                result = set_settings_employee_pin(
                    session,
                    admin_user_id=self.user_id,
                    employee_id=employee_id,
                    pin=pin,
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar PIN", str(exc))
            return

        self.refresh_all()
        result_feedback = build_settings_employee_result_feedback(
            "set_employee_pin",
            employee_name=result.employee_name,
            employee_code=result.employee_code,
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_generate_employee_qr(self) -> None:
        employee_id = self._selected_settings_employee_id()
        feedback = build_settings_employee_guard_feedback(
            "generate_employee_qr",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=employee_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with self._busy_scope(
                "Empleadas: generando QR...",
                status_label=self.settings_employees_status_label,
            ), get_session() as session:
                result = generate_settings_employee_qr(session, employee_id=employee_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "QR fallido", str(exc))
            return

        self._refresh_settings_employees()
        result_feedback = build_settings_employee_result_feedback(
            "generate_employee_qr",
            employee_name=result.employee_name,
            employee_code=result.employee_code,
            asset_path=str(result.asset_path) if result.asset_path is not None else "",
        )
        QMessageBox.information(self, result_feedback.title, result_feedback.message)

    def _handle_generate_employee_card(self) -> None:
        employee_id = self._selected_settings_employee_id()
        feedback = build_settings_employee_guard_feedback(
            "generate_employee_card",
            is_admin=self.current_role == RolUsuario.ADMIN,
            has_selection=employee_id is not None,
        )
        if feedback is not None:
            QMessageBox.warning(self, feedback.title, feedback.message)
            return
        try:
            with self._busy_scope(
                "Empleadas: generando credencial...",
                status_label=self.settings_employees_status_label,
            ), get_session() as session:
                result = generate_settings_employee_card(session, employee_id=employee_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Credencial fallida", str(exc))
            return

        self._refresh_settings_employees()
        if result.asset_path is not None:
            self._reveal_path(result.asset_path)
        self.settings_employees_status_label.setText(
            f"Credencial de staff '{result.employee_code}' generada."
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
        # E1-C2: sin tipo ni descuento; el mensaje solo lleva el codigo.
        qr_note = (
            f"Codigo de cliente: {client.codigo_cliente}\n"
            "Te comparto tu QR de cliente en la imagen adjunta."
        )
        return normalized_phone, qr_path, qr_note

    def _prepare_client_card_delivery(self, client: Cliente) -> tuple[str, Path, str]:
        normalized_phone, _qr_path, _qr_note = self._prepare_client_qr_delivery(client)
        # E1-C2: credencial estandar para todos, con o sin nivel viejo. Se
        # regenera para no reutilizar un PNG desactualizado (plantilla o logo).
        # `render_for_client` no escribe en la ficha (`card_image_path`).
        card_path = CustomerCardService.render_for_client(client)
        card_note = (
            f"Codigo de cliente: {client.codigo_cliente}\n"
            "Te comparto tu credencial de cliente en la imagen adjunta."
        )
        return normalized_phone, card_path, card_note

    def _render_client_card_safe(self, client: Cliente) -> tuple[Path | None, str | None]:
        try:
            # E1-C2: credencial estandar, sin nivel; no escribe en la ficha.
            card_path = CustomerCardService.render_for_client(client)
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

    def _toggle_api_server(self) -> None:
        import subprocess
        import socket

        if self._api_server_process is not None and self._api_server_process.poll() is None:
            self._api_server_process.terminate()
            self._api_server_process.wait(timeout=5)
            self._api_server_process = None
            if self.api_server_action:
                self.api_server_action.setText("Iniciar servidor movil")
            QMessageBox.information(self, "Servidor movil", "Servidor detenido.")
            return

        try:
            venv_python = Path(__file__).resolve().parent.parent / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
            if not venv_python.exists():
                venv_python = sys.executable

            self._api_server_process = subprocess.Popen(
                [str(venv_python), "-m", "uvicorn", "pos_uniformes.api.main:app",
                 "--host", "0.0.0.0", "--port", "8000", "--workers", "1"],
                cwd=str(Path(__file__).resolve().parent.parent.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                pass

            if self.api_server_action:
                self.api_server_action.setText("Detener servidor movil")

            QMessageBox.information(
                self,
                "Servidor movil",
                f"Servidor iniciado.\n\n"
                f"Las empleadas pueden entrar desde su celular a:\n"
                f"https://{local_ip}:5173\n\n"
                f"(deben estar en la misma red WiFi)",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo iniciar el servidor:\n{exc}")

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

    def _handle_logout(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Cerrar sesion")
        dialog.setModal(True)
        dialog.setMinimumWidth(420)
        dlg_layout = QVBoxLayout()
        dlg_layout.setSpacing(16)
        dlg_layout.setContentsMargins(24, 24, 24, 20)
        title = QLabel("Cerrar sesion")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1a1a1a;")
        desc = QLabel(
            "Se cerrara la sesion actual y volveras a la pantalla de acceso.\n"
            "Los datos no guardados se perderan."
        )
        desc.setWordWrap(True)
        desc.setObjectName("subtleLine")
        dlg_layout.addWidget(title)
        dlg_layout.addWidget(desc)

        is_admin = self.current_role == RolUsuario.ADMIN
        backup_check: QCheckBox | None = None
        if is_admin:
            backup_check = QCheckBox("Crear respaldo (.dump) antes de salir")
            backup_check.setChecked(True)
            backup_check.setToolTip("Genera un checkpoint restaurable antes de cambiar de usuario.")
            dlg_layout.addWidget(backup_check)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("toolbarGhostButton")
        cancel_btn.clicked.connect(dialog.reject)
        logout_btn = QPushButton("Cerrar sesion")
        logout_btn.setObjectName("toolbarPrimaryButton")
        logout_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(logout_btn)
        dlg_layout.addLayout(btn_layout)
        dialog.setLayout(dlg_layout)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        if is_admin and backup_check is not None and backup_check.isChecked():
            if not self._run_quick_backup_flow(allow_continue_on_error=True):
                return

        previous_user_id = self.user_id
        self._close_cached_logout_dialogs()

        self.hide()
        dialog = LoginDialog()
        switch_completed = False

        def _switch_user(authenticated_user_id: int) -> None:
            nonlocal switch_completed
            try:
                dialog.hide()
                self.user_id = authenticated_user_id
                self.show()
                self.raise_()
                self.activateWindow()
                self.refresh_all()
                self._apply_role_navigation()
                self._focus_default_tab_for_role()
            except Exception as exc:  # noqa: BLE001
                self.user_id = previous_user_id
                self.refresh_all()
                self.hide()
                dialog.clear_loading_state()
                dialog.show()
                QMessageBox.critical(dialog, "No se pudo iniciar la sesion", str(exc))
                dialog.raise_()
                dialog.activateWindow()
                return

            switch_completed = True
            dialog.clear_loading_state()
            dialog.accept()

        dialog.authenticated.connect(_switch_user)
        if dialog.exec() != LoginDialog.DialogCode.Accepted or not switch_completed:
            self._force_close = True
            self.close()
            return

        self.show()
        self.raise_()
        self.activateWindow()

    def _close_cached_logout_dialogs(self) -> None:
        dialog_attr_names = (
            "settings_users_dialog",
            "settings_suppliers_dialog",
            "settings_clients_dialog",
            "settings_employees_dialog",
            "settings_employee_day_sales_dialog",
            "settings_employee_sale_detail_dialog",
            "settings_backup_dialog",
            "settings_business_dialog",
            "settings_marketing_dialog",
            "settings_whatsapp_dialog",
        )
        for attr_name in dialog_attr_names:
            dialog = getattr(self, attr_name, None)
            if dialog is not None:
                dialog.close()
            setattr(self, attr_name, None)

    def _load_db_colors_and_sizes(self) -> tuple[list[str], list[str]]:
        """Carga colores y tallas distintos de variantes activas en la BD."""
        db_colors: list[str] = []
        db_sizes: list[str] = []
        try:
            with get_session() as session:
                rows = session.execute(
                    select(Variante.color).where(Variante.activo.is_(True)).distinct()
                ).scalars().all()
                db_colors = [c.strip() for c in rows if c and c.strip() and c.strip() != DEFAULT_VARIANT_COLOR]
                rows = session.execute(
                    select(Variante.talla).where(Variante.activo.is_(True)).distinct()
                ).scalars().all()
                db_sizes = [t.strip() for t in rows if t and t.strip() and t.strip() != DEFAULT_VARIANT_SIZE]
        except Exception:  # noqa: BLE001
            pass
        return db_colors, db_sizes

    def _prompt_product_data(self, initial: dict[str, object] | None = None) -> dict[str, object] | None:
        db_colors, db_sizes = self._load_db_colors_and_sizes()
        return build_catalog_product_dialog(
            self,
            initial=initial,
            picker_button_class=MultiSelectPickerButton,
            product_templates=PRODUCT_TEMPLATES,
            common_sizes=merge_choice_lists(COMMON_SIZES, db_sizes),
            common_colors=merge_choice_lists(COMMON_COLORS, db_colors),
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
        prefill: dict[str, object] | None = None,
        include_stock: bool = False,
        default_product_id: int | None = None,
    ) -> dict[str, object] | None:
        db_colors, db_sizes = self._load_db_colors_and_sizes()
        return build_catalog_variant_dialog(
            self,
            initial=initial,
            prefill=prefill,
            include_stock=include_stock,
            default_product_id=default_product_id,
            common_sizes=merge_choice_lists(COMMON_SIZES, db_sizes),
            common_colors=merge_choice_lists(COMMON_COLORS, db_colors),
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
        self._set_combo_value(presentacion_combo, self._dialog_prefill_variant_id())
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
        self._set_combo_value(presentacion_combo, self._dialog_prefill_variant_id())
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
        payload = prompt_inventory_count_data(
            self,
            print_labels_callback=self._handle_inventory_count_print_labels,
        )
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
            "todos_variante_ids": [int(v) for v in payload.get("all_variante_ids", [])],
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
                (_build_bulk_selection_label(selected_ids, selected_rows), "SELECCION", selected_rows)
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
        note_input.setPlaceholderText("Observación adicional")
        source_label = QLabel("Fuente")
        mode_label = QLabel("Tipo")
        reference_label = QLabel("Referencia")
        motive_label = QLabel("Motivo")
        note_label = QLabel("Observación")
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
            "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
            "color: #50606c; font-weight: 600;"
        )
        status_banner_label = QLabel("Carga un lote para validar resultados.")
        status_banner_label.setObjectName("subtleLine")
        status_banner_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
            "color: #5f6d78; font-weight: 700;"
        )

        def set_banner_style(tone: str) -> None:
            palette = {
                "positive": ("#e5f2eb", "#245241", "#bfdccd"),
                "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
                "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
                "neutral": ("#f3f7fa", "#5f6d78", "#d7e2ea"),
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
            tab_navigator.set_inputs(
                [
                    spin
                    for row_index in range(table.rowCount())
                    if isinstance((spin := table.cellWidget(row_index, 6)), QSpinBox)
                ]
            )
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
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        tab_navigator = _TableSpinTabNavigator(
            anchor_before=quick_reset_button,
            anchor_after=cancel_button or ok_button,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addLayout(header_grid)
        layout.addWidget(status_banner_label)
        layout.addLayout(quick_actions_row)
        layout.addWidget(summary_label)
        layout.addWidget(table)
        layout.addWidget(buttons)
        update_preview()
        if ok_button is not None and cancel_button is not None:
            QWidget.setTabOrder(cancel_button, ok_button)
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
        note_input.setPlaceholderText("Observación adicional")
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
        operation_hint_label.setStyleSheet("padding: 4px 2px; color: #5f6d78;")

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
            "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
            "color: #50606c; font-weight: 600;"
        )
        status_banner_label = QLabel("Carga un lote para validar resultados.")
        status_banner_label.setObjectName("subtleLine")
        status_banner_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #f3f7fa; border: 1px solid #d7e2ea;"
            "color: #5f6d78; font-weight: 700;"
        )

        def set_banner_style(tone: str) -> None:
            palette = {
                "positive": ("#e5f2eb", "#245241", "#bfdccd"),
                "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
                "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
                "neutral": ("#f3f7fa", "#5f6d78", "#d7e2ea"),
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
            tab_navigator.set_inputs(
                [
                    spin
                    for row_index in range(table.rowCount())
                    if isinstance((spin := table.cellWidget(row_index, 5)), QDoubleSpinBox)
                ]
            )
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
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        tab_navigator = _TableSpinTabNavigator(
            anchor_before=quick_reset_button,
            anchor_after=cancel_button or ok_button,
        )
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
        if ok_button is not None and cancel_button is not None:
            QWidget.setTabOrder(cancel_button, ok_button)
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
        prefill: dict[str, object] | None = None,
        default_product_id: int | None = None,
        include_stock: bool,
    ) -> tuple[str, int] | None:
        if initial is not None and prefill is not None:
            raise ValueError("No se puede usar initial (editar) y prefill (duplicar) al mismo tiempo.")
        try:
            data = self._prompt_variant_data(
                initial=initial,
                prefill=prefill,
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
                    stock_minimo_raw = data.get("stock_minimo")
                    stock_minimo = int(stock_minimo_raw) if stock_minimo_raw is not None else None
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
                        stock_minimo=stock_minimo,
                    )
                session.commit()
                return str(presentacion.sku), int(presentacion.id)
        except Exception as exc:  # noqa: BLE001
            title = "Presentacion fallida" if initial is None else "Presentacion no actualizada"
            QMessageBox.critical(self, title, str(exc))
            return None

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
        is_regular_product_mode = str(data.get("modo_catalogo") or "").strip() == "regular"

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
                escuela = None if is_regular_product_mode else self._resolve_named_taxonomy(session, Escuela, str(data["escuela"]))
                tipo_prenda = self._resolve_named_taxonomy(session, TipoPrenda, str(data["tipo_prenda"]))
                tipo_pieza = self._resolve_named_taxonomy(session, TipoPieza, str(data["tipo_pieza"]))
                atributo = self._resolve_named_taxonomy(session, AtributoProducto, str(data["atributo"]))
                nivel_educativo = (
                    None
                    if is_regular_product_mode
                    else self._resolve_named_taxonomy(session, NivelEducativo, str(data["nivel_educativo"]))
                )
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
                    escudo="" if is_regular_product_mode else str(data["escudo"]),
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
                    f"Ya dejaste {total_variants} tallas sugeridas con sus colores.\n"
                    f"SKU previstos: {sku_preview}\n\n"
                    "¿Quieres crearlas ahora todas juntas?"
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
                        QMessageBox.critical(self, TITULO_ERROR_LOTE, str(exc))
                        return
                    self.refresh_all()
                    if first_variant_id is not None:
                        self._set_combo_value(self.inventory_variant_combo, first_variant_id)
                    QMessageBox.information(
                        self,
                        "Tallas creadas",
                        mensaje_tallas_creadas(nombre, created_count, created_skus, errors),
                    )
                return

        reply = QMessageBox.question(
            self,
            "Producto creado",
            f"Producto '{nombre}' creado correctamente.\n\n¿Quieres agregar su primera talla ahora?",
        )
        if reply == QMessageBox.StandardButton.Yes and created_product_id is not None:
            result = self._create_or_edit_presentation(
                default_product_id=created_product_id,
                include_stock=True,
            )
            if result is not None:
                sku, variant_id = result
                self.refresh_all()
                QMessageBox.information(self, "Talla creada", self._mensaje_talla_creada(variant_id, sku))

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
        QMessageBox.information(self, "Talla creada", self._mensaje_talla_creada(variant_id, sku))

    def _handle_duplicate_variant(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede crear presentaciones.")
            return
        inventory_variant_id = self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())
        if inventory_variant_id is None:
            QMessageBox.warning(
                self,
                "Sin seleccion",
                "Selecciona una presentacion en la tabla de inventario para duplicar.",
            )
            return
        selected = self._selected_catalog_row()
        if selected is None:
            QMessageBox.warning(self, "Presentacion no encontrada", "No se pudo cargar la presentacion seleccionada.")
            return
        result = self._create_or_edit_presentation(
            prefill=selected,
            default_product_id=int(selected["producto_id"]),
            include_stock=True,
        )
        if result is None:
            return
        sku, variant_id = result
        self.refresh_all()
        self._set_combo_value(self.inventory_variant_combo, variant_id)
        QMessageBox.information(self, "Talla duplicada", self._mensaje_talla_creada(variant_id, sku))

    def _mensaje_talla_creada(self, variant_id: object, sku: object) -> str:
        try:
            fila = find_catalog_row_by_variant_id(self._load_inventory_snapshot_rows(), variant_id)
        except Exception:  # noqa: BLE001
            fila = None
        return mensaje_talla_creada(fila, sku)

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

    def _handle_product_photo(self) -> None:
        """La foto del modelo seleccionado, con la webcam o un archivo (2026-10-20)."""
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
        from pos_uniformes.ui.dialogs.foto_producto_dialog import abrir_foto_producto

        cambio = abrir_foto_producto(
            self,
            producto_id=int(selected["producto_id"]),
            titulo=str(selected.get("producto_nombre_base") or selected.get("producto_nombre") or ""),
        )
        if cambio:
            self._refresh_catalog()

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
        is_regular_product_mode = str(data.get("modo_catalogo") or "").strip() == "regular"

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
                escuela = None if is_regular_product_mode else self._resolve_named_taxonomy(session, Escuela, str(data["escuela"]))
                tipo_prenda = self._resolve_named_taxonomy(session, TipoPrenda, str(data["tipo_prenda"]))
                tipo_pieza = self._resolve_named_taxonomy(session, TipoPieza, str(data["tipo_pieza"]))
                atributo = self._resolve_named_taxonomy(session, AtributoProducto, str(data["atributo"]))
                nivel_educativo = (
                    None
                    if is_regular_product_mode
                    else self._resolve_named_taxonomy(session, NivelEducativo, str(data["nivel_educativo"]))
                )
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
                    escudo="" if is_regular_product_mode else str(data["escudo"]),
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
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(
                    self,
                    "QR no sincronizado",
                    f"El SKU cambio de {old_sku} a {sku.upper()} pero el archivo QR no se pudo actualizar:\n{exc}",
                )
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
        action = _catalog_toggle_feedback_action(target_state)
        if not target_state and not preguntar_desactivar(
            self,
            confirmacion_desactivar_prenda(
                selected.get("producto_nombre"),
                contar_tallas_de_prenda(self._load_inventory_snapshot_rows(), selected.get("producto_id")),
            ),
        ):
            return

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
        self._restore_catalog_selection_after_mutation(int(selected["variante_id"]))
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
        action = _catalog_toggle_feedback_action(target_state)
        if not target_state and not preguntar_desactivar(
            self,
            confirmacion_desactivar_talla(selected.get("producto_nombre"), selected.get("talla"), selected.get("color")),
        ):
            return

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
        self._restore_catalog_selection_after_mutation(int(selected["variante_id"]))
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
            item_label=build_product_delete_label(selected),
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
            item_label=build_variant_delete_label(selected),
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

    @staticmethod
    def _generate_quote_folio() -> str:
        return f"PRE-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"

    def _reset_quote_form(self) -> None:
        self.quote_sku_input.clear()
        self.quote_qty_spin.setValue(1)
        self.quote_client_combo.setCurrentIndex(0)
        self.quote_validity_input.setDate(QDate.currentDate().addDays(7))
        self.quote_note_input.clear()
        self.quote_folio_input.setText(self._generate_quote_folio())

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

    def _prompt_quick_quote_client_data(self) -> dict[str, str] | None:
        from PyQt6.QtCore import QRegularExpression
        from PyQt6.QtGui import QRegularExpressionValidator

        dialog, layout = self._create_modal_dialog(
            "Nuevo cliente rapido",
            "Registra un cliente con nombre y telefono para vincularlo al presupuesto.",
            width=500,
        )
        name_label = QLabel("Nombre")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Nombre completo del cliente")
        name_input.setMinimumHeight(36)
        phone_label = QLabel("Telefono")
        phone_input = QLineEdit()
        phone_input.setPlaceholderText("10 digitos")
        phone_input.setMinimumHeight(36)
        phone_input.setMaxLength(10)
        phone_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}")))
        error_label = QLabel("")
        error_label.setStyleSheet("color: #c0392b; font-size: 12px;")
        error_label.setVisible(False)
        preview_label = QLabel("")
        preview_label.setObjectName("subtleLine")
        preview_label.setVisible(False)

        def _update_preview() -> None:
            name = name_input.text().strip()
            phone = phone_input.text().strip()
            if name:
                parts = [f"<b>{name}</b>"]
                if phone:
                    parts.append(f" · Tel: {phone}")
                preview_label.setText("".join(parts))
                preview_label.setVisible(True)
            else:
                preview_label.setVisible(False)

        name_input.textChanged.connect(_update_preview)
        phone_input.textChanged.connect(_update_preview)

        layout.addWidget(name_label)
        layout.addWidget(name_input)
        layout.addWidget(phone_label)
        layout.addWidget(phone_input)
        layout.addWidget(error_label)
        layout.addWidget(preview_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("Crear cliente")
        if cancel_btn is not None:
            cancel_btn.setText("Cancelar")

        def _try_accept() -> None:
            name = name_input.text().strip()
            phone = phone_input.text().strip()
            if not name:
                error_label.setText("El nombre es obligatorio.")
                error_label.setVisible(True)
                name_input.setFocus()
                return
            if phone and len(phone) != 10:
                error_label.setText("El telefono debe tener exactamente 10 digitos.")
                error_label.setVisible(True)
                phone_input.setFocus()
                return
            error_label.setVisible(False)
            dialog.accept()

        buttons.accepted.connect(_try_accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        name_input.setFocus()
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
                client_message = build_quote_client_created_feedback(
                    session,
                    client_name=str(client.nombre),
                    client_code=str(client.codigo_cliente),
                )
                session.commit()
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
            client_message,
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
                result = add_quote_scan_variants(
                    self,
                    session,
                    quote_cart=self.quote_cart,
                    scanned_variant=variante,
                    quantity=quantity,
                    variant_loader=PresupuestoService.obtener_variante_por_sku,
                )
                if result is None:
                    self.quote_sku_input.setFocus()
                    self.quote_sku_input.selectAll()
                    return
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
        removed_line_item = dict(self.quote_cart[selected_row])
        self.quote_cart.pop(selected_row)
        restore_message = restore_sports_uniform_playera_price_if_needed(
            self.quote_cart,
            removed_line_item=removed_line_item,
        )
        self._refresh_quote_cart_table()
        if restore_message:
            QMessageBox.information(self, "Precio restaurado", restore_message)

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
                    items=build_quote_presupuesto_inputs(self.quote_cart),
                    cliente=cliente,
                    cliente_nombre=cliente.nombre if cliente is not None else None,
                    cliente_telefono=cliente.telefono if cliente is not None else None,
                    vigencia_hasta=local_day_window(self.quote_validity_input.date().toPyDate())[0],
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

        self.refresh_all()
        self._set_combo_value(self.inventory_variant_combo, variante_id)
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

    def _handle_open_conteo_calendario(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(
                self, "Sin permisos", "Solo ADMIN puede ver el calendario de conteos."
            )
            return
        from pos_uniformes.ui.dialogs.conteo_calendario_dialog import ConteoCalendarioDialog

        ConteoCalendarioDialog(self).exec()

    def _refrescar_por_nombrar_action(self) -> None:
        try:
            from pos_uniformes.services import por_nombrar_service as pn

            with get_session() as session:
                n = pn.cuantos(session)
        except Exception:  # noqa: BLE001 — sin base, el texto pelón
            n = 0
        self.por_nombrar_action.setText(f"Mercancía por nombrar ({n})" if n else "Mercancía por nombrar")

    def _handle_open_por_nombrar(self) -> None:
        """Ropa normal que entró con el código del proveedor (2026-10-20)."""
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede nombrar productos.")
            return
        from pos_uniformes.ui.dialogs.por_nombrar_dialog import abrir_por_nombrar

        abrir_por_nombrar(
            self, user_id=self.user_id,
            on_print_labels=self._handle_inventory_count_print_labels,
            on_changed=self._refresh_catalog,
        )

    def _handle_open_buzon(self) -> None:
        """Chat de texto con los kioskos y con Claude (2026-10-15)."""
        from pos_uniformes.ui.dialogs.buzon_dialog import abrir_buzon

        abrir_buzon(self)

    def _handle_open_uniformes_escuela(self) -> None:
        if self.current_role != RolUsuario.ADMIN:
            QMessageBox.warning(self, "Sin permisos", "Solo ADMIN puede armar los uniformes.")
            return
        from pos_uniformes.ui.dialogs.uniforme_escuela_dialog import prompt_uniforme_escuela_admin

        prompt_uniforme_escuela_admin(self)

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
        todos_variante_ids: list[int] = [int(v) for v in data.get("todos_variante_ids", [])]

        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                if user is None:
                    raise ValueError("Usuario no encontrado.")
                now = datetime.now(tz=timezone.utc)
                applied_ids: set[int] = set()
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
                    variante.ultimo_conteo_at = now
                    applied_ids.add(int(row["variante_id"]))
                for variante_id in todos_variante_ids:
                    if variante_id not in applied_ids:
                        v = session.get(Variante, variante_id)
                        if v is not None:
                            v.ultimo_conteo_at = now
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

    def _handle_generate_all_qr(self) -> None:
        selected_variant_ids = self._selected_inventory_variant_ids()
        if not selected_variant_ids:
            QMessageBox.warning(
                self,
                "Sin seleccion",
                "Selecciona una o mas presentaciones en Inventario para generar su lote de QR.",
            )
            return
        progress_dialog: QProgressDialog | None = None
        try:
            with self._busy_scope("Inventario: generando QR en lote..."), get_session() as session:
                variantes = session.scalars(
                    select(Variante)
                    .where(
                        Variante.id.in_(selected_variant_ids),
                        Variante.activo.is_(True),
                    )
                    .order_by(Variante.sku)
                ).all()
                if not variantes:
                    raise ValueError("No se encontraron presentaciones activas dentro de la seleccion para generar QR.")

                progress_dialog = QProgressDialog("Preparando generacion de etiquetas...", "Cancelar", 0, len(variantes), self)
                progress_dialog.setWindowTitle("Generando QR")
                progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setAutoClose(False)
                progress_dialog.setAutoReset(False)
                progress_dialog.setValue(0)
                QApplication.processEvents()

                def _on_progress(progress) -> None:
                    if progress_dialog is None:
                        return
                    progress_dialog.setLabelText(progress.message)
                    progress_dialog.setValue(progress.current - 1)
                    QApplication.processEvents()

                paths = generate_inventory_bulk_qr(
                    list(variantes),
                    on_progress=_on_progress,
                    is_cancelled=(progress_dialog.wasCanceled if progress_dialog is not None else None),
                )
                if progress_dialog is not None:
                    progress_dialog.setValue(len(variantes))
                    QApplication.processEvents()
        except InventoryBulkQrCancelled:
            if progress_dialog is not None:
                progress_dialog.close()
            QMessageBox.information(
                self,
                "Generacion cancelada",
                "La generacion masiva se cancelo. Los QR ya procesados quedaron guardados.",
            )
            return
        except Exception as exc:  # noqa: BLE001
            if progress_dialog is not None:
                progress_dialog.close()
            QMessageBox.critical(self, "QR fallido", str(exc))
            return
        if progress_dialog is not None:
            progress_dialog.close()

        directory = QrGenerator.output_dir()
        QMessageBox.information(
            self,
            "QRs generados",
            f"Se generaron {len(paths)} QR del lote seleccionado en:\n{directory}",
        )

    def _handle_generate_missing_qr(self) -> None:
        self._launch_bulk_qr_worker("missing")

    def _handle_regenerate_all_qr(self) -> None:
        confirmation = QMessageBox.question(
            self,
            "Regenerar todos los QR",
            "Esto va a recrear los QR de TODAS las presentaciones activas.\n"
            "Los archivos QR existentes se sobreescriben.\n\n"
            "Continuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._launch_bulk_qr_worker("all")

    def _launch_bulk_qr_worker(self, mode: str) -> None:
        if getattr(self, "_bulk_qr_worker", None) is not None and self._bulk_qr_worker.isRunning():
            QMessageBox.information(self, "En progreso", "Ya hay una generacion masiva de QR en curso.")
            return

        label = "Generando QR faltantes..." if mode == "missing" else "Regenerando todos los QR..."
        progress = QProgressDialog(label, "Cancelar", 0, 0, self)
        progress.setWindowTitle("QR masivo")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        worker = BulkQrWorker(mode, parent=self)
        self._bulk_qr_worker = worker
        self._bulk_qr_progress = progress

        def on_progress(current: int, total: int, message: str) -> None:
            if progress.wasCanceled():
                return
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(message)

        def on_finished(generated: int, skipped: int) -> None:
            progress.close()
            self._bulk_qr_worker = None
            self._bulk_qr_progress = None
            parts = [f"QR generados: {generated}"]
            if skipped:
                parts.append(f"Ya existentes (omitidos): {skipped}")
            QMessageBox.information(self, "QR masivo completado", "\n".join(parts))

        def on_failed(error: str) -> None:
            progress.close()
            self._bulk_qr_worker = None
            self._bulk_qr_progress = None
            QMessageBox.critical(self, "QR masivo fallido", error)

        worker.progress.connect(on_progress)
        worker.finished_ok.connect(on_finished)
        worker.failed.connect(on_failed)
        progress.canceled.connect(worker.cancel)
        worker.start()

    def _handle_history_filter(self) -> None:
        try:
            with get_session() as session:
                self._refresh_history(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Filtros invalidos", str(exc))

    def refresh_all(self) -> None:
        self._invalidate_listing_snapshot_caches()
        try:
            with self._busy_scope("Estado: cargando datos..."), get_session() as session:
                nombres_por_codigo(session)
                self._refresh_current_user(session)
                self._refresh_permissions()
                self._refresh_summary(session)
                self._refresh_combos(session)
                self._refresh_catalog(session)
                self._refresh_inventory_table(session)
                self._refresh_quotes(session)
                self._refresh_analytics(session)
                self._refresh_history(session)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Estado: error al cargar datos - {exc}")
            return

        self._refresh_settings_backups()
        with get_session() as settings_session:
            self._refresh_settings_users(settings_session)
            self._refresh_settings_suppliers(session=settings_session)
            self._refresh_settings_clients(session=settings_session)
        self._refresh_settings_employees()
        self.status_label.setText("Estado: datos sincronizados con PostgreSQL.")

    def _refresh_current_user(self, session) -> None:
        user = session.get(Usuario, self.user_id)
        if user is None or not user.activo:
            raise ValueError("El usuario autenticado ya no esta disponible.")

        self.current_username = user.username
        self.current_full_name = user.nombre_completo
        self.current_role = user.rol
        self.session_label.setText(f"{self.current_username} | {self.current_full_name}")

    def _refresh_permissions(self) -> None:
        is_admin = self.current_role == RolUsuario.ADMIN
        can_sell = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
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
        self.inventory_labels_button.setEnabled(is_admin)
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
        self.inventory_adjust_button.setEnabled(is_admin)
        self.logout_button.setEnabled(True)
        self._apply_quote_action_state()
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
        self.settings_business_button.setEnabled(is_admin)
        self.settings_meilisearch_button.setEnabled(is_admin)
        self.settings_monederos_button.setEnabled(is_admin)
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
        self.settings_employees_button.setEnabled(is_admin)
        self.settings_create_employee_button.setEnabled(is_admin)
        self.settings_update_employee_button.setEnabled(is_admin)
        self.settings_toggle_employee_button.setEnabled(is_admin)
        self.settings_set_employee_pin_button.setEnabled(is_admin)
        self.settings_generate_employee_qr_button.setEnabled(is_admin)
        self.settings_generate_employee_card_button.setEnabled(is_admin)
        self.settings_marketing_save_button.setEnabled(is_admin)
        self.settings_marketing_history_button.setEnabled(is_admin)
        self.settings_whatsapp_save_button.setEnabled(is_admin)
        self.settings_business_save_button.setEnabled(is_admin)

        if self.dashboard_users_card is not None:
            self.dashboard_users_card.setVisible(is_admin)
        if self.dashboard_help_box is not None:
            self.dashboard_help_box.setTitle("Flujo sugerido" if is_admin else "Flujo rapido de caja")
        self.analytics_label.setVisible(is_admin)
        self.layaway_alerts_label.setVisible(is_admin)
        if self.products_quick_setup_box is not None:
            self.products_quick_setup_box.setVisible(catalog_access_view.quick_setup_visible)

        self.catalog_permission_label.setText(catalog_access_view.permission_label)
        self.purchase_permission_label.setText(
            "" if is_admin else "Compras disponibles solo para ADMIN."
        )
        self.inventory_permission_label.setText(
            "" if is_admin else "Las altas, entradas, conteos, ajustes, cambios de precio y eliminacion estan restringidos a ADMIN."
        )

    def _refresh_summary(self, session) -> None:
        # Un solo round-trip: antes eran 11 queries escalares secuenciales,
        # cada una pagando latencia de red completa.
        summary_row = session.execute(
            select(
                select(func.count(Usuario.id)).scalar_subquery(),
                select(func.count(Proveedor.id)).scalar_subquery(),
                select(func.count(Producto.id)).scalar_subquery(),
                select(func.count(Variante.id)).scalar_subquery(),
                # Sin los conjuntos (3pz, chamarra): su existencia es la de sus
                # piezas, sumarla otra vez inflaria el total. Ver conjunto_service.
                select(func.coalesce(func.sum(Variante.stock_actual), 0))
                .select_from(Variante).join(Variante.producto)
                .where(conjunto_service.filtro_sin_conjuntos())
                .scalar_subquery(),
                select(func.count(Compra.id)).scalar_subquery(),
                select(func.coalesce(func.sum(Compra.total), 0))
                .where(Compra.estado == EstadoCompra.CONFIRMADA)
                .scalar_subquery(),
                select(func.count(Variante.id))
                .select_from(Variante).join(Variante.producto)
                .where(Variante.stock_actual <= 3, conjunto_service.filtro_sin_conjuntos())
                .scalar_subquery(),
            )
        ).one()
        usuarios = summary_row[0] or 0
        proveedores = summary_row[1] or 0
        productos = summary_row[2] or 0
        variantes = summary_row[3] or 0
        stock_total = summary_row[4] or 0
        compras = summary_row[5] or 0
        compras_confirmadas = summary_row[6] or Decimal("0.00")
        stock_bajo = summary_row[7] or 0
        layaway_alerts_snapshot = load_layaway_alerts_snapshot(session, today=date.today())

        is_admin = self.current_role == RolUsuario.ADMIN
        # Ventas y cobrado desde la Libreta (2026-11-12): la tabla `venta` es
        # de la Caja antigua y ya no crece.
        resumen_libreta = resumen_pos_service.cargar(session, incluir_privados=is_admin)
        status_view = build_dashboard_status_view(
            usuarios=usuarios,
            proveedores=proveedores,
            productos=productos,
            variantes=variantes,
            stock_total=stock_total,
            compras=compras,
            ventas_hoy=resumen_libreta.hoy.ventas,
            ventas_mes=resumen_libreta.mes.ventas,
            is_admin=is_admin,
        )
        operations_view = build_dashboard_operations_view(
            ventas_hoy=resumen_libreta.hoy.ventas,
            cobrado_hoy=resumen_libreta.hoy.cobrado,
            ventas_mes=resumen_libreta.mes.ventas,
            cobrado_mes=resumen_libreta.mes.cobrado,
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
            ventas_hoy=resumen_libreta.hoy.ventas,
            ventas_mes=resumen_libreta.mes.ventas,
            apartados_hoy=resumen_libreta.hoy.apartados,
            stock_bajo=stock_bajo,
            is_admin=is_admin,
        )

        self.metrics_label.setText(status_view.metrics_text)
        self.kpi_users_value.setText(str(usuarios))
        self.kpi_products_value.setText(str(productos))
        self.kpi_stock_value.setText(str(stock_total))
        self.kpi_sales_value.setText(str(resumen_libreta.hoy.ventas))
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
            now=datetime.now(timezone.utc),
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
        used_meili = False

        # Meilisearch resuelve el texto (matchingStrategy=all); el filtro local
        # de texto solo corre como fallback para no matar los typos/sinónimos.
        if search_text:
            try:
                from pos_uniformes.services import meilisearch_service
                if meilisearch_service.is_available():
                    hits = meilisearch_service.search(search_text, limit=500)
                    if hits:
                        hit_skus = {str(h.get("sku", "")) for h in hits}
                        catalog_snapshot_rows = [
                            r for r in catalog_snapshot_rows
                            if str(r.get("sku", "")) in hit_skus
                        ]
                        used_meili = True
            except Exception:
                pass

        search_terms = compile_search_terms("" if used_meili else search_text)
        school_scope_filter = str(self.catalog_school_scope_filter_combo.currentData() or "")
        category_filters = (
            self.catalog_category_filter_combo.selected_values()
            if not self.catalog_category_filter_combo.isHidden()
            else set()
        )
        brand_filters = self.catalog_brand_filter_combo.selected_values()
        school_filters = self.catalog_school_filter_combo.selected_values()
        type_filters = self.catalog_type_filter_combo.selected_values()
        piece_filters = self.catalog_piece_filter_combo.selected_values()
        size_filters = self.catalog_size_filter_combo.selected_values()
        color_filters = self.catalog_color_filter_combo.selected_values()
        status_filter = (
            str(self.catalog_status_filter_combo.currentData() or "")
            if not self.catalog_status_filter_combo.isHidden()
            else "active"
        )
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
        self._refresh_catalog_active_filter_chips()
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
                ("marca", self.catalog_brand_filter_combo.selected_labels()),
                ("escuela", self.catalog_school_filter_combo.selected_labels()),
                ("linea", self.catalog_type_filter_combo.selected_labels()),
                ("pieza", self.catalog_piece_filter_combo.selected_labels()),
                ("talla", self.catalog_size_filter_combo.selected_labels()),
                ("color", self.catalog_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("seccion", self.catalog_school_scope_filter_combo.currentData(), self.catalog_school_scope_filter_combo.currentText()),
                ("stock", self.catalog_stock_filter_combo.currentData(), self.catalog_stock_filter_combo.currentText()),
                ("apartados", self.catalog_layaway_filter_combo.currentData(), self.catalog_layaway_filter_combo.currentText()),
                ("origen", self.catalog_origin_filter_combo.currentData(), self.catalog_origin_filter_combo.currentText()),
                ("incidencias", self.catalog_duplicate_filter_combo.currentData(), self.catalog_duplicate_filter_combo.currentText()),
            ),
        )

    def _catalog_active_filter_tokens(self):
        return build_active_filter_tokens(
            search_text=self.catalog_search_input.text(),
            multi_filters=(
                ("marca", self.catalog_brand_filter_combo.selected_labels()),
                ("escuela", self.catalog_school_filter_combo.selected_labels()),
                ("linea", self.catalog_type_filter_combo.selected_labels()),
                ("pieza", self.catalog_piece_filter_combo.selected_labels()),
                ("talla", self.catalog_size_filter_combo.selected_labels()),
                ("color", self.catalog_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("seccion", self.catalog_school_scope_filter_combo.currentData(), self.catalog_school_scope_filter_combo.currentText()),
                ("stock", self.catalog_stock_filter_combo.currentData(), self.catalog_stock_filter_combo.currentText()),
                ("apartados", self.catalog_layaway_filter_combo.currentData(), self.catalog_layaway_filter_combo.currentText()),
                ("origen", self.catalog_origin_filter_combo.currentData(), self.catalog_origin_filter_combo.currentText()),
                ("incidencias", self.catalog_duplicate_filter_combo.currentData(), self.catalog_duplicate_filter_combo.currentText()),
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
        combo_filters = {
            "seccion": self.catalog_school_scope_filter_combo,
            "stock": self.catalog_stock_filter_combo,
            "apartados": self.catalog_layaway_filter_combo,
            "origen": self.catalog_origin_filter_combo,
            "incidencias": self.catalog_duplicate_filter_combo,
        }
        multi_filters = {
            "marca": self.catalog_brand_filter_combo,
            "escuela": self.catalog_school_filter_combo,
            "linea": self.catalog_type_filter_combo,
            "pieza": self.catalog_piece_filter_combo,
            "talla": self.catalog_size_filter_combo,
            "color": self.catalog_color_filter_combo,
        }
        if token.key == "texto":
            self.catalog_search_input.blockSignals(True)
            self.catalog_search_input.clear()
            self.catalog_search_input.blockSignals(False)
            self._handle_catalog_filters_changed_reset_page()
            return
        combo = combo_filters.get(token.key)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            self._handle_catalog_filters_changed_reset_page()
            return
        multi_filter = multi_filters.get(token.key)
        if multi_filter is not None:
            selected_values = {
                value
                for value in multi_filter.selected_values()
                if _normalize_filter_value(value) != _normalize_filter_value(token.value)
            }
            multi_filter.set_selected_values(selected_values)

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
                ("marca", self.inventory_brand_filter_combo.selected_labels()),
                ("escuela", self.inventory_school_filter_combo.selected_labels()),
                ("tipo", self.inventory_type_filter_combo.selected_labels()),
                ("pieza", self.inventory_piece_filter_combo.selected_labels()),
                ("talla", self.inventory_size_filter_combo.selected_labels()),
                ("color", self.inventory_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("uso", self.inventory_use_filter_combo.currentData(), self.inventory_use_filter_combo.currentText()),
                ("estado", self.inventory_status_filter_combo.currentData(), self.inventory_status_filter_combo.currentText()),
                ("stock", self.inventory_stock_filter_combo.currentData(), self.inventory_stock_filter_combo.currentText()),
                ("conteo", self.inventory_conteo_filter_combo.currentData(), self.inventory_conteo_filter_combo.currentText()),
                ("precio", self.inventory_precio_filter_combo.currentData(), self.inventory_precio_filter_combo.currentText()),
                ("precio_exacto", self.inventory_precio_text_input.text().strip() or None, f"${self.inventory_precio_text_input.text().strip()}" if self.inventory_precio_text_input.text().strip() else ""),
            ),
        )

    def _inventory_active_filter_tokens(self):
        return build_active_filter_tokens(
            search_text=self.inventory_search_input.text(),
            multi_filters=(
                ("marca", self.inventory_brand_filter_combo.selected_labels()),
                ("escuela", self.inventory_school_filter_combo.selected_labels()),
                ("tipo", self.inventory_type_filter_combo.selected_labels()),
                ("pieza", self.inventory_piece_filter_combo.selected_labels()),
                ("talla", self.inventory_size_filter_combo.selected_labels()),
                ("color", self.inventory_color_filter_combo.selected_labels()),
            ),
            combo_filters=(
                ("uso", self.inventory_use_filter_combo.currentData(), self.inventory_use_filter_combo.currentText()),
                ("estado", self.inventory_status_filter_combo.currentData(), self.inventory_status_filter_combo.currentText()),
                ("stock", self.inventory_stock_filter_combo.currentData(), self.inventory_stock_filter_combo.currentText()),
                ("conteo", self.inventory_conteo_filter_combo.currentData(), self.inventory_conteo_filter_combo.currentText()),
                ("precio", self.inventory_precio_filter_combo.currentData(), self.inventory_precio_filter_combo.currentText()),
                ("precio_exacto", self.inventory_precio_text_input.text().strip() or None, f"${self.inventory_precio_text_input.text().strip()}" if self.inventory_precio_text_input.text().strip() else ""),
            ),
        )

    def _build_inventory_active_filters_summary(self) -> str:
        return build_active_filters_summary(self._inventory_active_filter_labels())

    def _refresh_inventory_active_filter_chips(self) -> None:
        rebuild_active_filter_chips(
            container=self.inventory_active_filters_wrap,
            layout=self.inventory_active_filters_flow_layout,
            tokens=self._inventory_active_filter_tokens(),
            on_remove=self._handle_remove_inventory_filter_token,
        )

    def _handle_remove_inventory_filter_token(self, token) -> None:
        combo_filters = {
            "uso": self.inventory_use_filter_combo,
            "estado": self.inventory_status_filter_combo,
            "stock": self.inventory_stock_filter_combo,
            "conteo": self.inventory_conteo_filter_combo,
            "precio": self.inventory_precio_filter_combo,
        }
        multi_filters = {
            "marca": self.inventory_brand_filter_combo,
            "escuela": self.inventory_school_filter_combo,
            "tipo": self.inventory_type_filter_combo,
            "pieza": self.inventory_piece_filter_combo,
            "talla": self.inventory_size_filter_combo,
            "color": self.inventory_color_filter_combo,
        }
        text_inputs = {
            "texto": self.inventory_search_input,
            "precio_exacto": self.inventory_precio_text_input,
        }
        text_input = text_inputs.get(token.key)
        if text_input is not None:
            text_input.blockSignals(True)
            text_input.clear()
            text_input.blockSignals(False)
            self._handle_inventory_filters_changed_reset_page()
            return
        combo = combo_filters.get(token.key)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            self._handle_inventory_filters_changed_reset_page()
            return
        multi_filter = multi_filters.get(token.key)
        if multi_filter is not None:
            selected_values = {
                value
                for value in multi_filter.selected_values()
                if _normalize_filter_value(value) != _normalize_filter_value(token.value)
            }
            multi_filter.set_selected_values(selected_values)

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
        # Una sola pasada por las ~4,800 variantes (antes se hidrataban dos
        # veces) y con el producto precargado para no disparar un lazy-load
        # por fila. selectinload (no joinedload): el JOIN repetiría todas las
        # columnas de Producto en cada una de las ~4,800 filas por la red.
        from sqlalchemy.orm import selectinload

        variantes_inventario = session.scalars(
            select(Variante).options(selectinload(Variante.producto)).order_by(Variante.sku)
        ).all()
        variantes_activas = [v for v in variantes_inventario if v.activo]

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
        current_inventory_variant_id = self.inventory_variant_combo.currentData()
        self._populate_combo(self.inventory_variant_combo, inventory_variant_items)
        if current_inventory_variant_id is None:
            self.inventory_variant_combo.setCurrentIndex(-1)
        self._refresh_catalog_section_controls()
        self._refresh_inventory_selection_panel()

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
                            "size_label": detail.size_label,
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
            values = list(detalle.table_values)
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column_index in {4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.quote_detail_table.setItem(row_index, column_index, item)
        self.quote_detail_table.resizeColumnsToContents()

    def _refresh_inventory_table(self, session=None) -> None:
        current_variant_id = self.inventory_variant_combo.currentData()
        inventory_snapshot_rows = self._load_inventory_snapshot_rows(session)

        search_text = self.inventory_search_input.text().strip()
        used_meili = False
        search_hits_count = None

        # Meilisearch resuelve el texto (matchingStrategy=all); el filtro local
        # de texto solo corre como fallback para no matar los typos/sinónimos.
        if search_text:
            try:
                from pos_uniformes.services import meilisearch_service
                if meilisearch_service.is_available():
                    hits = meilisearch_service.search(search_text, limit=INVENTORY_SEARCH_LIMIT)
                    if hits:
                        search_hits_count = len(hits)
                        hit_skus = {str(h.get("sku", "")) for h in hits}
                        local_terms = compile_search_terms(search_text)
                        inventory_snapshot_rows = combinar_hits_meili(
                            inventory_snapshot_rows,
                            hit_skus,
                            lambda row: row_matches_search(
                                row,
                                search_text=search_text,
                                search_terms=local_terms,
                                alias_map=INVENTORY_SEARCH_ALIAS_MAP,
                                general_fields=INVENTORY_SEARCH_GENERAL_FIELDS,
                            ),
                        )
                        used_meili = True
            except Exception:
                pass
        search_terms = compile_search_terms("" if used_meili else search_text)
        use_filter = str(self.inventory_use_filter_combo.currentData() or "")
        category_filters = (
            self.inventory_category_filter_combo.selected_values()
            if not self.inventory_category_filter_combo.isHidden()
            else set()
        )
        brand_filters = self.inventory_brand_filter_combo.selected_values()
        school_filters = self.inventory_school_filter_combo.selected_values()
        type_filters = self.inventory_type_filter_combo.selected_values()
        piece_filters = self.inventory_piece_filter_combo.selected_values()
        size_filters = self.inventory_size_filter_combo.selected_values()
        color_filters = self.inventory_color_filter_combo.selected_values()
        status_filter = str(self.inventory_status_filter_combo.currentData() or "")
        stock_filter = str(self.inventory_stock_filter_combo.currentData() or "")
        conteo_filter = str(self.inventory_conteo_filter_combo.currentData() or "")
        precio_filter = str(self.inventory_precio_filter_combo.currentData() or "")
        precio_text_filter = self.inventory_precio_text_input.text().strip()

        self.inventory_filtered_rows = filter_visible_inventory_rows(
            inventory_snapshot_rows,
            filters=InventoryVisibleFilterState(
                search_text=search_text,
                use_filter=use_filter,
                category_filters=tuple(category_filters),
                brand_filters=tuple(brand_filters),
                school_filters=tuple(school_filters),
                type_filters=tuple(type_filters),
                piece_filters=tuple(piece_filters),
                size_filters=tuple(size_filters),
                color_filters=tuple(color_filters),
                status_filter=status_filter,
                stock_filter=stock_filter,
                conteo_filter=conteo_filter,
                precio_filter=precio_filter,
                precio_text_filter=precio_text_filter,
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
            search_hits_count=search_hits_count,
        )
        self._set_badge_state(
            self.inventory_negative_counter,
            summary_view.negative_counter.text,
            summary_view.negative_counter.tone,
        )
        self._set_badge_state(self.inventory_out_counter, summary_view.out_counter.text, summary_view.out_counter.tone)
        self._set_badge_state(self.inventory_low_counter, summary_view.low_counter.text, summary_view.low_counter.tone)
        self._set_badge_state(
            self.inventory_inactive_counter,
            summary_view.inactive_counter.text,
            summary_view.inactive_counter.tone,
        )

        if current_variant_id is not None:
            selected_filtered_index = find_catalog_row_index_by_variant_id(
                self.inventory_filtered_rows,
                current_variant_id,
            )
            if selected_filtered_index is not None:
                self.inventory_page_index = selected_filtered_index // INVENTORY_PAGE_SIZE

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
        self._refresh_inventory_active_filter_chips()
        self.inventory_pagination_label.setText(pagination_view.page_label)
        self.inventory_previous_page_button.setEnabled(pagination_view.previous_enabled)
        self.inventory_next_page_button.setEnabled(pagination_view.next_enabled)
        self._sync_inventory_table_selection(current_variant_id)
        self._refresh_inventory_overview()

    def _populate_inventory_table_rows(self, table_row_views) -> None:
        for row_index, row_view in enumerate(table_row_views):
            for column_index, value in enumerate(row_view.values):
                self.inventory_table.setItem(row_index, column_index, _table_item(value))
            if row_view.row_tone is not None or row_view.tooltip:
                for column_index in range(len(row_view.values)):
                    item = self.inventory_table.item(row_index, column_index)
                    if item is None:
                        continue
                    if row_view.row_tone is not None:
                        _set_table_row_tint(item, row_view.row_tone)
                    if row_view.tooltip:
                        item.setToolTip(row_view.tooltip)
            for column_index, tooltip in row_view.cell_tooltips:
                item = self.inventory_table.item(row_index, column_index)
                if item is not None:
                    item.setToolTip(tooltip)
            self.inventory_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row_view.variant_id)
            stock_item = self.inventory_table.item(row_index, INVENTORY_COLUMNA_STOCK)
            if stock_item is not None:
                _set_table_badge_style(stock_item, row_view.stock_tone, con_fondo=row_view.stock_con_fondo)

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
        self.inventory_search_input.blockSignals(True)
        self.inventory_search_input.clear()
        self.inventory_search_input.blockSignals(False)
        self.inventory_precio_text_input.blockSignals(True)
        self.inventory_precio_text_input.clear()
        self.inventory_precio_text_input.blockSignals(False)
        for combo in (
            self.inventory_use_filter_combo,
            self.inventory_status_filter_combo,
            self.inventory_stock_filter_combo,
            self.inventory_conteo_filter_combo,
            self.inventory_precio_filter_combo,
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
            widget.blockSignals(True)
            widget.clear_selection()
            widget.blockSignals(False)
        self._clear_inventory_table_selection()
        self._handle_inventory_filters_changed()

    def _handle_inventory_previous_page(self) -> None:
        if self.inventory_page_index <= 0:
            return
        self.inventory_page_index -= 1
        self.inventory_variant_combo.setCurrentIndex(-1)
        self._handle_inventory_filters_changed()

    def _handle_inventory_next_page(self) -> None:
        self.inventory_page_index += 1
        self.inventory_variant_combo.setCurrentIndex(-1)
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
            self.status_label.setText("Estado: no se pudo refrescar la analítica.")

    def _refresh_analytics(self, session) -> None:
        """La pestaña Analítica, toda desde la Libreta (2026-11-07). La de antes
        leía la tabla `venta` del POS (8 registros de abril)."""
        from pos_uniformes.ui.helpers.analytics_tablero import refrescar

        if getattr(self, "_ana_estado", None) is None:
            return
        refrescar(self, session)

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
                # 06 y 07 desde la Libreta (2026-11-12): la tabla `venta` es de
                # la Caja antigua y ya no crece. Ver exportacion_libreta_service.
                sales_rows, detail_rows = exportacion_libreta_service.cargar(
                    session, period_start, period_end, cliente_id=selected_client_id
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
                        "creado_por": _nombre_de(movimiento.creado_por),
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
        is_general_only = str(self.catalog_school_scope_filter_combo.currentData() or "") in ("general_only", "unidentified")
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

    def _refresh_inventory_selection_panel(self) -> None:
        """Ficha de la talla elegida (la vista previa del QR salió en la tanda 2)."""
        variante_id = self.inventory_variant_combo.currentData()
        self._refresh_inventory_overview()
        if variante_id:
            self._sync_inventory_table_selection(variante_id)

    def _print_image_path(
        self,
        image_path: Path,
        *,
        title: str,
        copies: int,
        parent: QDialog | None = None,
        paper_mode: str = "standard",
    ) -> bool:
        from pos_uniformes.ui.helpers.label_routing_helper import maybe_route_label_to_satellite
        if maybe_route_label_to_satellite(
            image_path,
            sku=title.replace("Etiqueta ", "", 1),
            copies=copies,
            paper_mode=paper_mode,
            parent=parent or self,
        ):
            return True

        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError(f"No se pudo abrir la imagen de etiqueta:\n{image_path}")
        # Impresora según el TIPO de etiqueta (config local por máquina), igual
        # que el satélite: Normal/Split/Continua → una; Label (dk1221) → otra.
        from pos_uniformes.services.label_printer_settings_cache_service import (
            load_label_printer_settings,
            resolve_label_printer_for_mode,
        )
        normal_printer, label_printer = load_label_printer_settings()
        preferred_printer = resolve_label_printer_for_mode(
            paper_mode, normal_printer=normal_printer, label_printer=label_printer
        )
        # Fallback (sin config local): impresora preferida de la BD.
        if not preferred_printer:
            try:
                with get_session() as session:
                    preferred_printer = load_business_print_settings_snapshot(session).preferred_printer
            except Exception:
                preferred_printer = ""

        if sys.platform.startswith("win"):
            # DK-1221 die-cut: brother_ql genera raster + spooler RAW.
            # Esquiva el GDI/DEVMODE (que no respeta el paper size en QL-800).
            if paper_mode == "die_cut":
                from pos_uniformes.ui.helpers.brother_ql_print_helper import (
                    is_brother_ql_available,
                    print_dk1221_via_brother_ql,
                )
                from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
                    resolve_windows_inventory_label_printer,
                )
                if is_brother_ql_available():
                    try:
                        target = resolve_windows_inventory_label_printer(preferred_printer)
                        print_dk1221_via_brother_ql(
                            image_path,
                            printer_name=target.printer_name,
                            copies=copies,
                        )
                        return True
                    except Exception as exc:  # noqa: BLE001 - caer a GDI como fallback
                        print(f"[etiquetas] brother_ql fallo, usando GDI: {exc}")

            resolution = print_inventory_label_via_windows(
                image_path,
                sku=title.replace("Etiqueta ", "", 1),
                copies=copies,
                preferred_printer_name=preferred_printer,
                paper_mode=paper_mode,
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
        selected_variant_ids = self._selected_inventory_variant_ids()
        if len(selected_variant_ids) > 1:
            self._handle_inventory_print_label_batch(selected_variant_ids)
            return

        variante_id = (
            selected_variant_ids[0]
            if len(selected_variant_ids) == 1
            else self.inventory_variant_combo.currentData()
        )
        if not variante_id:
            QMessageBox.warning(
                self,
                "Sin presentacion",
                "Selecciona una presentacion para preparar la impresion de su etiqueta.",
            )
            return

        self._open_inventory_label_dialog_for_variant(int(variante_id))

    def _handle_inventory_print_visible_labels(self) -> None:
        visible_variant_ids = collect_inventory_row_variant_ids(self.inventory_filtered_rows)
        if not visible_variant_ids:
            QMessageBox.warning(
                self,
                "Sin resultados",
                "No hay presentaciones visibles en Inventario para preparar etiquetas.",
            )
            return
        if len(visible_variant_ids) == 1:
            self._open_inventory_label_dialog_for_variant(int(visible_variant_ids[0]))
            return
        self._handle_inventory_print_label_batch(visible_variant_ids)

    def _handle_inventory_count_print_labels(self, variant_ids: list[int]) -> None:
        ordered_variant_ids = [int(variant_id) for variant_id in variant_ids if int(variant_id)]
        if not ordered_variant_ids:
            QMessageBox.information(
                self,
                "Sin lecturas",
                "Aun no hay piezas capturadas para preparar etiquetas desde el conteo.",
            )
            return
        if len(ordered_variant_ids) == 1:
            self._open_inventory_label_dialog_for_variant(int(ordered_variant_ids[0]))
            return
        self._handle_inventory_print_label_batch(ordered_variant_ids)

    def _open_inventory_label_dialog_for_variant(self, variante_id: int) -> None:
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

        def render_label(mode: str, requested_copies: int, show_price: bool | None = None):
            with get_session() as session:
                return render_inventory_label(
                    session,
                    int(label_render_state["variant_id"]),
                    mode=mode,
                    requested_copies=requested_copies,
                    show_price=show_price,
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
            print_label=lambda image_path, copies, sku, parent, mode: self._print_image_path(
                image_path,
                title=f"Etiqueta {sku}",
                copies=copies,
                parent=parent,
                paper_mode={"continuous": "continuous", "dk1221": "die_cut"}.get(mode, "standard"),
            ),
        )

    def _handle_inventory_print_label_batch(self, variant_ids: list[int]) -> None:
        ordered_variant_ids = [int(variant_id) for variant_id in variant_ids if int(variant_id)]
        if not ordered_variant_ids:
            QMessageBox.warning(
                self,
                "Sin seleccion",
                "Selecciona al menos dos presentaciones en Inventario para preparar el lote de etiquetas.",
            )
            return
        try:
            with get_session() as session:
                contexts = [
                    load_inventory_label_context(session, int(variant_id))
                    for variant_id in ordered_variant_ids
                ]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Impresion por lote no disponible", str(exc))
            return

        def render_label(variant_id: int, mode: str, requested_copies: int, show_price: bool | None = None):
            with get_session() as session:
                return render_inventory_label(
                    session,
                    int(variant_id),
                    mode=mode,
                    requested_copies=requested_copies,
                    show_price=show_price,
                )

        build_inventory_label_batch_dialog(
            self,
            contexts=contexts,
            render_label=render_label,
            print_label=lambda image_path, copies, sku, parent, mode: self._print_image_path(
                image_path,
                title=f"Etiqueta {sku}",
                copies=copies,
                parent=parent,
                paper_mode={"continuous": "continuous", "dk1221": "die_cut"}.get(mode, "standard"),
            ),
        )

    def _refresh_quote_cart_table(self) -> None:
        quote_cart_view = build_quote_cart_view(self.quote_cart)
        self.quote_cart_table.setRowCount(len(quote_cart_view.rows))
        for row_index, row in enumerate(quote_cart_view.rows):
            for column_index, value in enumerate(row.values):
                item = _table_item(value)
                if column_index == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif column_index in {5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.quote_cart_table.setItem(row_index, column_index, item)
        self.quote_cart_table.resizeColumnsToContents()
        self.quote_total_label.setText(quote_cart_view.summary.total_label)
        self.quote_summary_label.setText(quote_cart_view.summary.summary_label)
        can_sell = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        self.quote_qty_down_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_qty_up_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_remove_button.setEnabled(can_sell and bool(self.quote_cart))
        self.quote_clear_button.setEnabled(can_sell and bool(self.quote_cart))

    def _selected_catalog_row(self) -> dict[str, object] | None:
        inventory_variant_id = self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())
        if inventory_variant_id is None:
            # Sin selección en inventario → usar la tabla de catálogo (pestaña Catálogo).
            return resolve_catalog_row(self.catalog_rows, self.catalog_table.currentRow())
        selected_from_inventory = find_catalog_row_by_variant_id(
            self.catalog_filtered_rows,
            inventory_variant_id,
        )
        if selected_from_inventory is not None:
            return selected_from_inventory
        return find_catalog_row_by_variant_id(
            self._load_catalog_snapshot_rows(),
            inventory_variant_id,
        )

    def _handle_inventory_table_selection(self) -> None:
        variant_id = self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())
        if variant_id is None:
            return
        self._set_combo_value(self.inventory_variant_combo, variant_id)

    def _clear_inventory_table_selection(self) -> None:
        self.inventory_table.blockSignals(True)
        try:
            self.inventory_table.clearSelection()
            self.inventory_table.setCurrentCell(-1, -1)
        finally:
            self.inventory_table.blockSignals(False)
        self.inventory_variant_combo.blockSignals(True)
        try:
            self.inventory_variant_combo.setCurrentIndex(-1)
        finally:
            self.inventory_variant_combo.blockSignals(False)
        self._refresh_inventory_selection_panel()

    def _dialog_prefill_variant_id(self) -> int | None:
        """Variante a pre-seleccionar en dialogs de stock/compra: siempre desde inventory_table."""
        return self._inventory_table_variant_id_at_row(self.inventory_table.currentRow())

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
        variant_id = self._inventory_table_variant_id_at_row(row_index)
        if variant_id is not None:
            self._set_combo_value(self.inventory_variant_combo, variant_id)

        selected = self._selected_catalog_row()
        if selected is None:
            return

        action_key = prompt_inventory_context_action(
            self,
            global_pos=self.inventory_table.viewport().mapToGlobal(pos),
            action_specs=build_inventory_context_menu_actions(
                is_admin=self.current_role == RolUsuario.ADMIN,
                variante_activa=bool(selected["variante_activo"]),
            ),
        )
        self._handle_inventory_context_action(action_key)

    def _handle_inventory_context_action(self, action_key: str | None) -> None:
        handlers = {
            "edit": self._handle_update_variant,
            "entry": self._handle_purchase,
            "adjust": self._handle_inventory_adjustment,
            "print": self._handle_inventory_print_label,
            "toggle": self._handle_toggle_variant,
        }
        handler = handlers.get(action_key or "")
        if handler is not None:
            handler()

    def _sync_inventory_table_selection(self, variant_id: object) -> None:
        if variant_id is None:
            self.inventory_table.blockSignals(True)
            try:
                self.inventory_table.clearSelection()
            finally:
                self.inventory_table.blockSignals(False)
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
                # La rebaja ya viene pegada a la fila de la tabla: sin otra consulta.
                fila_tabla = find_catalog_row_by_variant_id(self.inventory_filtered_rows, variante_id) or {}
                self._apply_inventory_overview_view(
                    build_inventory_overview_view(
                        sku=overview_snapshot.sku,
                        product_name=overview_snapshot.product_name,
                        product_active=overview_snapshot.product_active,
                        variant_active=overview_snapshot.variant_active,
                        stock_actual=overview_snapshot.stock_actual,
                        stock_minimo=overview_snapshot.stock_minimo,
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
                        es_conjunto=overview_snapshot.es_conjunto,
                        rebaja_tipo=fila_tabla.get("rebaja_tipo"),
                        rebaja_precio=fila_tabla.get("rebaja_precio"),
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
        self.catalog_selection_label.setText(build_empty_inventory_overview_view().catalog_selection_label)
        self.products_selection_label.setText(build_empty_catalog_selection_view().selection_label)
        empty_overview = build_empty_inventory_overview_view()
        self.toggle_product_button.setText(empty_overview.toggle_product_label)
        self.toggle_variant_button.setText(empty_overview.toggle_variant_label)

    def _restore_catalog_selection_after_mutation(self, variant_id: int) -> None:
        restored = self._select_catalog_variant(variant_id)
        if restored:
            return
        self.catalog_table.clearSelection()
        self.catalog_table.setCurrentCell(-1, -1)
        self.inventory_table.clearSelection()
        self.inventory_table.setCurrentCell(-1, -1)
        self._clear_catalog_editor()

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
        if value is None:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(-1)

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
