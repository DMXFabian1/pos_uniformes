"""Ventana principal funcional del sistema POS."""

import csv
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import subprocess
import sys
from time import monotonic
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QKeySequence, QPixmap, QShortcut
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
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
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import engine, get_session, test_connection
from pos_uniformes.database.models import (
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    CambioCatalogo,
    Categoria,
    Cliente,
    Compra,
    EstadoApartado,
    EstadoCompra,
    EstadoVenta,
    Marca,
    MovimientoInventario,
    Producto,
    Proveedor,
    RolUsuario,
    SesionCaja,
    TipoCambioCatalogo,
    TipoMovimientoCaja,
    TipoMovimientoInventario,
    TipoEntidadCatalogo,
    Usuario,
    Variante,
    Venta,
    VentaDetalle,
)
from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService
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
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.supplier_service import SupplierService
from pos_uniformes.services.user_service import UserService
from pos_uniformes.services.venta_service import VentaItemInput, VentaService
from pos_uniformes.ui.login_dialog import LoginDialog
from pos_uniformes.ui.dialogs.settings_dialogs import (
    build_backup_settings_dialog,
    build_business_settings_dialog,
    build_cash_history_settings_dialog,
    build_clients_settings_dialog,
    build_suppliers_settings_dialog,
    build_whatsapp_settings_dialog,
    build_users_settings_dialog,
)
from pos_uniformes.ui.views.analytics_view import build_analytics_tab
from pos_uniformes.ui.views.cashier_view import build_cashier_tab
from pos_uniformes.ui.views.dashboard_view import build_dashboard_tab
from pos_uniformes.ui.views.history_view import build_history_tab
from pos_uniformes.ui.views.inventory_view import build_inventory_tab
from pos_uniformes.ui.views.layaway_view import build_layaway_tab
from pos_uniformes.ui.views.products_view import build_products_tab
from pos_uniformes.ui.views.settings_view import build_settings_tab
from pos_uniformes.utils.qr_generator import QrGenerator


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


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
        self.sale_cart: list[dict[str, object]] = []
        self.layaway_rows: list[dict[str, object]] = []

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
        self.catalog_selection_label = QLabel("Selecciona una presentacion en inventario para gestionar cambios.")
        self.products_selection_label = QLabel("Consulta productos, precios y stock disponible para venta.")
        self.catalog_search_input = QLineEdit()
        self.catalog_category_filter_combo = QComboBox()
        self.catalog_brand_filter_combo = QComboBox()
        self.catalog_status_filter_combo = QComboBox()
        self.catalog_layaway_filter_combo = QComboBox()
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
        self.inventory_generate_qr_button = QPushButton("Generar QR de presentacion")
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
        self.inventory_search_input = QLineEdit()
        self.inventory_category_filter_combo = QComboBox()
        self.inventory_brand_filter_combo = QComboBox()
        self.inventory_status_filter_combo = QComboBox()
        self.inventory_stock_filter_combo = QComboBox()
        self.inventory_qr_filter_combo = QComboBox()
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
        self.settings_business_phone_input = QLineEdit()
        self.settings_business_address_input = QTextEdit()
        self.settings_business_footer_input = QTextEdit()
        self.settings_business_transfer_bank_input = QLineEdit()
        self.settings_business_transfer_beneficiary_input = QLineEdit()
        self.settings_business_transfer_clabe_input = QLineEdit()
        self.settings_business_transfer_instructions_input = QTextEdit()
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
            self.inventory_generate_qr_button: "Genera el codigo QR de la presentacion seleccionada.",
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
            self.settings_backup_button: "Abre la configuracion de respaldo y restauracion.",
            self.settings_cash_history_button: "Abre el historial de aperturas, cierres y diferencias de caja.",
            self.settings_cash_history_detail_button: "Abre el detalle del corte seleccionado, incluyendo observaciones.",
            self.settings_business_button: "Abre la configuracion de negocio e impresion.",
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
            2: can_manage_layaways,  # Apartados
            3: True,      # Catalogo
            4: is_admin,  # Inventario
            5: is_admin,  # Historial inventarios
            6: is_admin,  # Analitica
            7: is_admin,  # Configuracion
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
                template_updates = {
                    "whatsapp_apartado_recordatorio": config.whatsapp_apartado_recordatorio or defaults["layaway_reminder"],
                    "whatsapp_apartado_liquidado": config.whatsapp_apartado_liquidado or defaults["layaway_liquidated"],
                    "whatsapp_cliente_promocion": config.whatsapp_cliente_promocion or defaults["client_promotion"],
                    "whatsapp_cliente_seguimiento": config.whatsapp_cliente_seguimiento or defaults["client_followup"],
                    "whatsapp_cliente_saludo": config.whatsapp_cliente_saludo or defaults["client_greeting"],
                }
                dirty = False
                for field_name, field_value in template_updates.items():
                    if getattr(config, field_name) != field_value:
                        setattr(config, field_name, field_value)
                        dirty = True
                if dirty:
                    session.add(config)
                    session.commit()
                self.settings_business_name_input.setText(config.nombre_negocio)
                self.settings_business_phone_input.setText(config.telefono or "")
                self.settings_business_address_input.setPlainText(config.direccion or "")
                self.settings_business_footer_input.setPlainText(config.pie_ticket or "")
                self.settings_business_transfer_bank_input.setText(config.transferencia_banco or "")
                self.settings_business_transfer_beneficiary_input.setText(config.transferencia_beneficiario or "")
                self.settings_business_transfer_clabe_input.setText(config.transferencia_clabe or "")
                self.settings_business_transfer_instructions_input.setPlainText(config.transferencia_instrucciones or "")
                self.settings_whatsapp_layaway_reminder_input.setPlainText(
                    config.whatsapp_apartado_recordatorio or ""
                )
                self.settings_whatsapp_layaway_liquidated_input.setPlainText(
                    config.whatsapp_apartado_liquidado or ""
                )
                self.settings_whatsapp_client_promotion_input.setPlainText(
                    config.whatsapp_cliente_promocion or ""
                )
                self.settings_whatsapp_client_followup_input.setPlainText(
                    config.whatsapp_cliente_seguimiento or ""
                )
                self.settings_whatsapp_client_greeting_input.setPlainText(
                    config.whatsapp_cliente_saludo or ""
                )
                printer_index = self.settings_business_printer_combo.findData(config.impresora_preferida or "")
                self.settings_business_printer_combo.setCurrentIndex(printer_index if printer_index >= 0 else 0)
                self.settings_business_copies_spin.setValue(config.copias_ticket or 1)
                self.settings_business_status_label.setText("Configuracion cargada correctamente.")
                self.settings_whatsapp_status_label.setText("Plantillas cargadas correctamente.")
                self._refresh_whatsapp_preview()
        except Exception as exc:  # noqa: BLE001
            self.settings_business_status_label.setText(f"No se pudo cargar la configuracion: {exc}")
            self.settings_whatsapp_status_label.setText(f"No se pudieron cargar las plantillas: {exc}")

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
                    payload=BusinessSettingsInput(
                        nombre_negocio=self.settings_business_name_input.text(),
                        telefono=self.settings_business_phone_input.text(),
                        direccion=self.settings_business_address_input.toPlainText(),
                        pie_ticket=self.settings_business_footer_input.toPlainText(),
                        transferencia_banco=self.settings_business_transfer_bank_input.text(),
                        transferencia_beneficiario=self.settings_business_transfer_beneficiary_input.text(),
                        transferencia_clabe=self.settings_business_transfer_clabe_input.text(),
                        transferencia_instrucciones=self.settings_business_transfer_instructions_input.toPlainText(),
                        whatsapp_apartado_recordatorio=self.settings_whatsapp_layaway_reminder_input.toPlainText(),
                        whatsapp_apartado_liquidado=self.settings_whatsapp_layaway_liquidated_input.toPlainText(),
                        whatsapp_cliente_promocion=self.settings_whatsapp_client_promotion_input.toPlainText(),
                        whatsapp_cliente_seguimiento=self.settings_whatsapp_client_followup_input.toPlainText(),
                        whatsapp_cliente_saludo=self.settings_whatsapp_client_greeting_input.toPlainText(),
                        impresora_preferida=str(self.settings_business_printer_combo.currentData() or ""),
                        copias_ticket=self.settings_business_copies_spin.value(),
                    ),
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return False

        self.settings_business_status_label.setText(success_message)
        self.settings_whatsapp_status_label.setText(success_message)
        QMessageBox.information(self, "Configuracion guardada", success_message)
        return True

    def _handle_save_business_settings(self) -> None:
        self._save_business_settings("Los datos del negocio se actualizaron correctamente.")

    def _handle_save_whatsapp_settings(self) -> None:
        self._save_business_settings("Las plantillas de WhatsApp se actualizaron correctamente.")

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
            values = [
                client.codigo_cliente,
                client.nombre,
                client.telefono or "",
                client.email or "",
                client.direccion or "",
                client.notas or "",
                "Listo" if QrGenerator.exists_for_client(client) else "Pendiente",
                "ACTIVO" if client.activo else "INACTIVO",
                client.updated_at.strftime("%Y-%m-%d %H:%M") if client.updated_at else "",
            ]
            for column_index, value in enumerate(values):
                item = _table_item(value)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole + 1, str(client.codigo_cliente))
                if column_index == 1:
                    item.setData(Qt.ItemDataRole.UserRole, int(client.id))
                if column_index == 6:
                    _set_table_badge_style(item, "positive" if value == "Listo" else "warning")
                if column_index == 7:
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
        phone_input = QLineEdit()
        email_input = QLineEdit()
        address_input = QTextEdit()
        notes_input = QTextEdit()
        address_input.setMinimumHeight(70)
        notes_input.setMinimumHeight(90)
        name_input.setPlaceholderText("Nombre completo o identificacion del cliente")
        phone_input.setPlaceholderText("Telefono")
        email_input.setPlaceholderText("correo@cliente.com")
        address_input.setPlaceholderText("Direccion")
        notes_input.setPlaceholderText("Notas internas o referencias")
        if current_values:
            name_input.setText(current_values.get("nombre", ""))
            phone_input.setText(current_values.get("telefono", ""))
            email_input.setText(current_values.get("email", ""))
            address_input.setPlainText(current_values.get("direccion", ""))
            notes_input.setPlainText(current_values.get("notas", ""))
        form.addRow("Nombre", name_input)
        form.addRow("Telefono", phone_input)
        form.addRow("Correo", email_input)
        form.addRow("Direccion", address_input)
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
            "telefono": phone_input.text().strip(),
            "email": email_input.text().strip(),
            "direccion": address_input.toPlainText().strip(),
            "notas": notes_input.toPlainText().strip(),
        }

    def _prompt_client_whatsapp_data(self, client_name: str) -> tuple[str, str] | None:
        dialog, layout = self._create_modal_dialog(
            "Mensaje de WhatsApp",
            f"Prepara un mensaje para {client_name}. Puedes usarlo para promociones o seguimiento.",
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
                ClientService.create_client(
                    session=session,
                    admin_user=admin_user,
                    nombre=data["nombre"],
                    telefono=data["telefono"],
                    email=data["email"],
                    direccion=data["direccion"],
                    notas=data["notas"],
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo crear", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Cliente creado", f"Cliente '{data['nombre']}' creado correctamente.")

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
                    "Actualiza telefono, correo, direccion o notas del cliente.",
                    current_values={
                        "nombre": client.nombre,
                        "telefono": client.telefono or "",
                        "email": client.email or "",
                        "direccion": client.direccion or "",
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
                    telefono=data["telefono"],
                    email=data["email"],
                    direccion=data["direccion"],
                    notas=data["notas"],
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))
            return

        self.refresh_all()
        QMessageBox.information(self, "Cliente actualizado", f"Cliente '{data['nombre']}' actualizado.")

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
                if not (client.telefono or "").strip():
                    raise ValueError("El cliente seleccionado no tiene telefono registrado.")
                normalized_phone = self._normalize_whatsapp_phone(client.telefono or "")
                if len(normalized_phone) < 10:
                    raise ValueError("El telefono del cliente no parece valido para WhatsApp.")
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
                full_message = base_message if not extra_message else f"{base_message}\n\n{extra_message}"
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

    def _create_modal_dialog(self, title: str, helper_text: str | None = None, width: int = 460) -> tuple[QDialog, QVBoxLayout]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
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

        if not categorias or not marcas:
            raise ValueError("Primero necesitas al menos una categoria y una marca activas.")

        dialog, layout = self._create_modal_dialog(
            "Producto",
            "Captura los datos base del producto. Esta accion no altera inventario por si sola.",
        )
        form = QFormLayout()
        template_combo = QComboBox()
        template_combo.addItem("Selecciona una plantilla", None)
        for template in PRODUCT_TEMPLATES:
            template_combo.addItem(template["label"], template)
        categoria_combo = QComboBox()
        for categoria_id, categoria_nombre in categorias:
            categoria_combo.addItem(categoria_nombre, categoria_id)
        marca_combo = QComboBox()
        for marca_id, marca_nombre in marcas:
            marca_combo.addItem(marca_nombre, marca_id)
        add_category_button = QPushButton("+")
        add_brand_button = QPushButton("+")
        add_category_button.setObjectName("iconButton")
        add_brand_button.setObjectName("iconButton")
        add_category_button.setToolTip("Crear una categoria nueva sin salir de esta ventana.")
        add_brand_button.setToolTip("Crear una marca nueva sin salir de esta ventana.")
        nombre_input = QLineEdit()
        descripcion_input = QTextEdit()
        descripcion_input.setFixedHeight(90)

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

        def apply_template() -> None:
            template = template_combo.currentData()
            if not isinstance(template, dict):
                return

            category_name = str(template["category"])
            category_index = categoria_combo.findText(category_name)
            if category_index >= 0:
                categoria_combo.setCurrentIndex(category_index)

            if not nombre_input.text().strip():
                nombre_input.setText(str(template["name"]))
            if not descripcion_input.toPlainText().strip():
                descripcion_input.setPlainText(str(template["description"]))

        template_combo.currentIndexChanged.connect(lambda _: apply_template())

        if initial:
            self._set_combo_value(categoria_combo, initial["categoria_id"])
            self._set_combo_value(marca_combo, initial["marca_id"])
            nombre_input.setText(str(initial["producto_nombre"]))
            descripcion_input.setPlainText(str(initial["producto_descripcion"] or ""))

        form.addRow("Plantilla", template_combo)
        categoria_row = QHBoxLayout()
        categoria_row.addWidget(categoria_combo)
        categoria_row.addWidget(add_category_button)
        marca_row = QHBoxLayout()
        marca_row.addWidget(marca_combo)
        marca_row.addWidget(add_brand_button)

        form.addRow("Categoria", categoria_row)
        form.addRow("Marca", marca_row)
        form.addRow("Nombre", nombre_input)
        form.addRow("Descripcion", descripcion_input)
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
            "categoria_id": categoria_combo.currentData(),
            "marca_id": marca_combo.currentData(),
            "nombre": nombre_input.text().strip(),
            "descripcion": descripcion_input.toPlainText().strip(),
        }

    def _prompt_variant_data(
        self,
        initial: dict[str, object] | None = None,
        include_stock: bool = False,
        default_product_id: int | None = None,
    ) -> dict[str, object] | None:
        with get_session() as session:
            productos = [
                {
                    "id": producto.id,
                    "nombre": producto.nombre,
                    "marca": producto.marca.nombre,
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
            producto_combo.addItem(f"{producto['nombre']} | {producto['marca']}", producto["id"])
        sku_input = QLineEdit()
        sku_input.setPlaceholderText("Se genera automaticamente si lo dejas vacio")
        talla_combo = QComboBox()
        talla_combo.setEditable(True)
        talla_combo.addItems(COMMON_SIZES)
        if talla_combo.lineEdit() is not None:
            talla_combo.lineEdit().setPlaceholderText("Selecciona o escribe una talla")
        color_combo = QComboBox()
        color_combo.setEditable(True)
        color_combo.addItems(COMMON_COLORS)
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

            fake_producto = _FakeProducto(producto_info["nombre"], producto_info["marca"])
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
        color = str(data["color"]).strip()
        price_text = str(data["precio"]).strip()
        cost_text = str(data["costo"]).strip()
        if not producto_id or not talla or not color or not price_text:
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "Selecciona producto y captura talla, color y precio.",
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
        try:
            with get_session() as session:
                user = session.get(Usuario, self.user_id)
                categoria = session.get(Categoria, int(categoria_id))
                marca = session.get(Marca, int(marca_id))
                if user is None or categoria is None or marca is None:
                    raise ValueError("Usuario, categoria o marca no encontrada.")
                producto = CatalogService.crear_producto(session, user, categoria, marca, nombre, descripcion)
                session.commit()
                created_product_id = int(producto.id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Producto fallido", str(exc))
            return

        self.refresh_all()
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
                sku, _variant_id = result
                self.refresh_all()
                QMessageBox.information(
                    self,
                    "Presentacion creada",
                    f"Se agrego la primera presentacion del producto con SKU '{sku}'.",
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
        QMessageBox.information(self, "Presentacion creada", f"Presentacion '{sku.upper()}' creada correctamente.")

    def _handle_catalog_selection(self) -> None:
        selected_row = self.catalog_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.catalog_rows):
            self.products_selection_label.setText("Consulta productos, precios y stock disponible para venta.")
            return

        row = self.catalog_rows[selected_row]
        if self.current_role == RolUsuario.ADMIN:
            self.products_selection_label.setText(
                f"{row['sku']} | {row['producto_nombre']} | precio {row['precio_venta']} | "
                f"stock {row['stock_actual']} | apartado {row['apartado_cantidad']} | {row['variante_estado']}"
            )
        else:
            self.products_selection_label.setText(
                f"{row['producto_nombre']} | {row['sku']} | precio {row['precio_venta']} | stock {row['stock_actual']}"
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
                CatalogService.actualizar_producto(
                    session=session,
                    usuario=usuario,
                    producto=producto,
                    categoria=categoria,
                    marca=marca,
                    nombre=nombre,
                    descripcion=descripcion,
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
        business_name = "POS Uniformes"
        business_phone = ""
        business_address = ""
        ticket_footer = "Gracias por tu compra."
        preferred_printer = ""
        ticket_copies = 1
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                business_name = config.nombre_negocio
                business_phone = config.telefono or ""
                business_address = config.direccion or ""
                ticket_footer = config.pie_ticket or ticket_footer
                preferred_printer = config.impresora_preferida or ""
                ticket_copies = config.copias_ticket or 1
        except Exception:
            preferred_printer = ""
            ticket_copies = 1

        lines = [
            business_name,
            "Ticket de venta",
            "",
            f"Folio: {sale.folio}",
            f"Fecha: {sale.created_at.strftime('%Y-%m-%d %H:%M') if sale.created_at else ''}",
            f"Usuario: {sale.usuario.username if sale.usuario else ''}",
            f"Estado: {sale.estado.value}",
            "",
        ]
        if sale.cliente is not None:
            lines.extend(
                [
                    f"Cliente: {sale.cliente.nombre}",
                    f"Codigo cliente: {sale.cliente.codigo_cliente}",
                ]
            )
            if sale.cliente.telefono:
                lines.append(f"Telefono cliente: {sale.cliente.telefono}")
            lines.append("")
        if business_phone:
            lines.append(f"Telefono: {business_phone}")
        if business_address:
            lines.append(f"Direccion: {business_address}")
        lines.extend(
            [
                "",
            "Detalle",
            ]
        )
        for detalle in sale.detalles:
            producto = detalle.variante.producto.nombre if detalle.variante and detalle.variante.producto else ""
            sku = detalle.variante.sku if detalle.variante else ""
            lines.append(
                f"- {producto} | {sku} | {detalle.cantidad} x {detalle.precio_unitario} = {detalle.subtotal_linea}"
            )
        lines.extend(
            [
                "",
                f"Subtotal: {sale.subtotal}",
                f"Total: {sale.total}",
            ]
        )
        if sale.observacion:
            lines.extend(["", f"Notas: {sale.observacion}"])
        lines.extend(["", ticket_footer, f"Copias configuradas: {ticket_copies}"])
        lines.append(f"Impresora preferida: {preferred_printer or 'Preguntar siempre'}")
        return "\n".join(lines)

    def _open_text_ticket_dialog(self, title: str, ticket_text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(620, 520)
        layout = QVBoxLayout()
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(ticket_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

        def handle_print() -> None:
            printer = QPrinter()
            try:
                with get_session() as session:
                    config = BusinessSettingsService.get_or_create(session)
                    preferred_printer = config.impresora_preferida or ""
                    copies = config.copias_ticket or 1
            except Exception:
                preferred_printer = ""
                copies = 1
            if preferred_printer:
                printer.setPrinterName(preferred_printer)
            printer.setCopyCount(copies)
            print_dialog = QPrintDialog(printer, dialog)
            if print_dialog.exec() == QDialog.DialogCode.Accepted:
                editor.print(printer)

        print_button.clicked.connect(handle_print)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec()

    def _handle_view_sale_ticket(self) -> None:
        sale_id = self._selected_recent_sale_id()
        if sale_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona una venta para ver su ticket.")
            return

        try:
            with get_session() as session:
                sale = session.get(Venta, sale_id)
                if sale is None:
                    raise ValueError("Venta no encontrada.")
                # Force-load details while the session is active.
                _ = [(detalle.variante.sku if detalle.variante else "") for detalle in sale.detalles]
                _ = sale.cliente.codigo_cliente if sale.cliente is not None else ""
                ticket_text = self._build_sale_ticket_text(sale)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

        self._open_text_ticket_dialog(f"Ticket {sale_id}", ticket_text)

    def _build_layaway_receipt_text(self, layaway: Apartado) -> str:
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                business_name = config.nombre_negocio
                business_phone = config.telefono or ""
                business_address = config.direccion or ""
                ticket_footer = config.pie_ticket or "Gracias por tu preferencia."
                preferred_printer = config.impresora_preferida or ""
                ticket_copies = config.copias_ticket or 1
        except Exception:
            business_name = "POS Uniformes"
            business_phone = ""
            business_address = ""
            ticket_footer = "Gracias por tu preferencia."
            preferred_printer = ""
            ticket_copies = 1

        lines = [
            business_name,
            business_phone,
            business_address,
            "",
            f"Comprobante de apartado: {layaway.folio}",
            f"Estado: {layaway.estado.value}",
            f"Cliente: {layaway.cliente_nombre}",
            (
                f"Codigo cliente: {layaway.cliente.codigo_cliente}"
                if layaway.cliente is not None
                else "Codigo cliente: Manual / sin cliente"
            ),
            f"Telefono: {layaway.cliente_telefono or 'Sin telefono'}",
            f"Fecha: {layaway.created_at.strftime('%Y-%m-%d %H:%M') if layaway.created_at else ''}",
            (
                "Compromiso: "
                + (layaway.fecha_compromiso.strftime("%Y-%m-%d") if layaway.fecha_compromiso else "Sin fecha")
            ),
            "",
            "Presentaciones:",
        ]
        for detalle in layaway.detalles:
            producto = detalle.variante.producto.nombre if detalle.variante and detalle.variante.producto else ""
            sku = detalle.variante.sku if detalle.variante else ""
            lines.append(
                f"- {producto} | {sku} | {detalle.cantidad} x {detalle.precio_unitario} = {detalle.subtotal_linea}"
            )
        lines.extend(
            [
                "",
                f"Total: {layaway.total}",
                f"Abonado: {layaway.total_abonado}",
                f"Saldo pendiente: {layaway.saldo_pendiente}",
            ]
        )
        if layaway.abonos:
            lines.extend(["", "Abonos:"])
            for abono in layaway.abonos:
                lines.append(
                    f"- {abono.created_at.strftime('%Y-%m-%d %H:%M') if abono.created_at else ''} | "
                    f"{abono.monto} | {abono.referencia or 'Sin referencia'} | {abono.usuario.username}"
                )
        if layaway.observacion:
            lines.extend(["", f"Notas: {layaway.observacion}"])
        lines.extend(["", ticket_footer, f"Copias configuradas: {ticket_copies}"])
        lines.append(f"Impresora preferida: {preferred_printer or 'Preguntar siempre'}")
        return "\n".join(lines)

    def _handle_view_layaway_receipt(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su comprobante.")
            return

        try:
            with get_session() as session:
                layaway = ApartadoService.obtener_apartado(session, apartado_id)
                if layaway is None:
                    raise ValueError("Apartado no encontrado.")
                _ = [detalle.variante.sku if detalle.variante else "" for detalle in layaway.detalles]
                _ = [abono.usuario.username if abono.usuario else "" for abono in layaway.abonos]
                receipt_text = self._build_layaway_receipt_text(layaway)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Comprobante no disponible", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Apartado {apartado_id}")
        dialog.resize(620, 520)
        layout = QVBoxLayout()
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(receipt_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

        def handle_print() -> None:
            printer = QPrinter()
            try:
                with get_session() as session:
                    config = BusinessSettingsService.get_or_create(session)
                    preferred_printer = config.impresora_preferida or ""
                    copies = config.copias_ticket or 1
            except Exception:
                preferred_printer = ""
                copies = 1
            if preferred_printer:
                printer.setPrinterName(preferred_printer)
            printer.setCopyCount(copies)
            print_dialog = QPrintDialog(printer, dialog)
            if print_dialog.exec() == QDialog.DialogCode.Accepted:
                editor.print(printer)

        print_button.clicked.connect(handle_print)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec()

    def _handle_view_layaway_sale_ticket(self) -> None:
        apartado_id = self._selected_layaway_id()
        if apartado_id is None:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un apartado para ver su ticket de venta.")
            return

        try:
            with get_session() as session:
                layaway = ApartadoService.obtener_apartado(session, apartado_id)
                if layaway is None:
                    raise ValueError("Apartado no encontrado.")
                if layaway.estado != EstadoApartado.ENTREGADO:
                    raise ValueError("El ticket de venta solo esta disponible para apartados entregados.")
                sale = session.scalar(select(Venta).where(Venta.folio == f"ENT-{layaway.folio}"))
                if sale is None:
                    raise ValueError("No se encontro la venta generada para este apartado.")
                _ = [detalle.variante.sku if detalle.variante else "" for detalle in sale.detalles]
                _ = sale.cliente.codigo_cliente if sale.cliente is not None else ""
                ticket_text = self._build_sale_ticket_text(sale)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ticket no disponible", str(exc))
            return

        self._open_text_ticket_dialog(f"Ticket de entrega {apartado_id}", ticket_text)

    @staticmethod
    def _generate_sale_folio() -> str:
        return f"VTA-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4].upper()}"

    def _reset_sale_form(self) -> None:
        self.sale_sku_input.clear()
        self.sale_qty_spin.setValue(1)
        self.sale_payment_combo.setCurrentText("Efectivo")
        self.sale_discount_combo.setCurrentIndex(0)
        self.sale_client_combo.setCurrentIndex(0)
        self.sale_received_spin.setValue(0.0)
        self.sale_folio_input.setText(self._generate_sale_folio())
        self.sale_last_scanned_sku = ""
        self.sale_last_scanned_at = 0.0
        self._refresh_payment_fields()

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

    def _calculate_sale_totals(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        subtotal = Decimal("0.00")
        for item in self.sale_cart:
            subtotal += Decimal(item["precio_unitario"]) * int(item["cantidad"])
        discount_percent = Decimal(str(self.sale_discount_combo.currentData() or 0)).quantize(Decimal("0.01"))
        applied_discount = (subtotal * discount_percent / Decimal("100.00")).quantize(Decimal("0.01"))
        if applied_discount > subtotal:
            applied_discount = subtotal
        total = subtotal - applied_discount
        return subtotal, discount_percent, applied_discount, total

    def _load_business_settings_snapshot(self) -> dict[str, object]:
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                return {
                    "nombre_negocio": config.nombre_negocio,
                    "transferencia_banco": config.transferencia_banco or "",
                    "transferencia_beneficiario": config.transferencia_beneficiario or "",
                    "transferencia_clabe": config.transferencia_clabe or "",
                    "transferencia_instrucciones": config.transferencia_instrucciones or "",
                }
        except Exception:
            return {
                "nombre_negocio": "POS Uniformes",
                "transferencia_banco": "",
                "transferencia_beneficiario": "",
                "transferencia_clabe": "",
                "transferencia_instrucciones": "",
            }

    def _prompt_cash_payment(self, total: Decimal) -> dict[str, object] | None:
        dialog, layout = self._create_modal_dialog(
            "Cobro en efectivo",
            "Captura el efectivo recibido. Puedes usar el teclado numerico o los montos rapidos.",
            width=420,
        )
        total_label = QLabel(f"Total a cobrar: ${total}")
        total_label.setObjectName("inventoryTitle")
        received_label = QLabel("$0.00")
        received_label.setObjectName("cashierTotalValue")
        change_label = QLabel("$0.00")
        change_label.setObjectName("cashierChangeValue")
        status_label = QLabel("Captura el monto recibido.")
        status_label.setObjectName("analyticsLine")
        keypad_display = QLineEdit("0.00")
        keypad_display.setReadOnly(True)
        keypad_display.setObjectName("readOnlyField")
        reference_input = QLineEdit()
        reference_input.setPlaceholderText("Referencia opcional")

        def parse_received() -> Decimal:
            try:
                return Decimal(keypad_display.text()).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                return Decimal("0.00")

        def update_cash_labels() -> None:
            received = parse_received()
            change = received - total
            if change < 0:
                change = Decimal("0.00")
                status_label.setText("Falta efectivo para cubrir el total.")
                status_label.setProperty("tone", "warning")
            else:
                status_label.setText("Monto suficiente para cobrar.")
                status_label.setProperty("tone", "positive")
            status_label.style().unpolish(status_label)
            status_label.style().polish(status_label)
            received_label.setText(f"${received}")
            change_label.setText(f"${change}")

        def append_keypad(value: str) -> None:
            current = keypad_display.text()
            if current == "0.00" and value != ".":
                current = ""
            if value == "." and "." in current:
                return
            keypad_display.setText((current + value) or "0")
            update_cash_labels()

        def clear_keypad() -> None:
            keypad_display.setText("0.00")
            update_cash_labels()

        def backspace_keypad() -> None:
            current = keypad_display.text()
            current = current[:-1]
            keypad_display.setText(current if current and current != "-" else "0")
            if "." not in keypad_display.text():
                keypad_display.setText(f"{keypad_display.text()}.00")
            update_cash_labels()

        summary_grid = QGridLayout()
        summary_grid.addWidget(QLabel("Recibido"), 0, 0)
        summary_grid.addWidget(received_label, 0, 1)
        summary_grid.addWidget(QLabel("Cambio"), 1, 0)
        summary_grid.addWidget(change_label, 1, 1)

        quick_row = QHBoxLayout()
        for amount in (100, 200, 500, 1000):
            button = QPushButton(f"${amount}")
            button.setObjectName("toolbarSecondaryButton")
            button.clicked.connect(lambda _checked=False, amt=amount: (keypad_display.setText(f"{amt:.2f}"), update_cash_labels()))
            quick_row.addWidget(button)
        quick_row.addStretch()

        keypad = QGridLayout()
        keys = [
            ("7", 0, 0),
            ("8", 0, 1),
            ("9", 0, 2),
            ("4", 1, 0),
            ("5", 1, 1),
            ("6", 1, 2),
            ("1", 2, 0),
            ("2", 2, 1),
            ("3", 2, 2),
            ("0", 3, 0),
            ("00", 3, 1),
            (".", 3, 2),
        ]
        for key, row, column in keys:
            button = QPushButton(key)
            button.setMinimumHeight(42)
            button.clicked.connect(lambda _checked=False, value=key: append_keypad(value))
            keypad.addWidget(button, row, column)
        clear_button = QPushButton("Limpiar")
        clear_button.clicked.connect(clear_keypad)
        keypad.addWidget(clear_button, 4, 0, 1, 2)
        backspace_button = QPushButton("Borrar")
        backspace_button.clicked.connect(backspace_keypad)
        keypad.addWidget(backspace_button, 4, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(total_label)
        layout.addWidget(keypad_display)
        layout.addLayout(summary_grid)
        layout.addWidget(status_label)
        layout.addLayout(quick_row)
        layout.addLayout(keypad)
        layout.addWidget(QLabel("Referencia"))
        layout.addWidget(reference_input)
        layout.addWidget(buttons)
        update_cash_labels()

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        received = parse_received()
        if received < total:
            QMessageBox.warning(self, "Pago insuficiente", "El monto recibido debe cubrir el total de la venta.")
            return None
        change = (received - total).quantize(Decimal("0.01"))
        return {
            "recibido": received,
            "cambio": change,
            "nota": [
                f"Recibido: {received}",
                f"Cambio: {change}",
                f"Referencia: {reference_input.text().strip() or 'Sin referencia'}",
            ],
        }

    def _prompt_transfer_payment(self, total: Decimal) -> dict[str, object] | None:
        business = self._load_business_settings_snapshot()
        if not business["transferencia_clabe"] and not business["transferencia_instrucciones"]:
            QMessageBox.warning(
                self,
                "Transferencia no configurada",
                "Configura CLABE o instrucciones de transferencia en Configuracion > Negocio e impresion.",
            )
            return None

        dialog, layout = self._create_modal_dialog(
            "Cobro por transferencia",
            "Muestra los datos de pago al cliente y confirma cuando la transferencia este registrada.",
            width=520,
        )
        info_lines = [
            f"Negocio: {business['nombre_negocio']}",
            f"Banco: {business['transferencia_banco'] or 'No configurado'}",
            f"Beneficiario: {business['transferencia_beneficiario'] or 'No configurado'}",
            f"CLABE: {business['transferencia_clabe'] or 'No configurada'}",
            f"Total a transferir: ${total}",
        ]
        info_label = QLabel("\n".join(info_lines))
        info_label.setWordWrap(True)
        info_label.setObjectName("inventoryMetaCard")
        instructions_label = QLabel(str(business["transferencia_instrucciones"] or "Sin instrucciones adicionales."))
        instructions_label.setWordWrap(True)
        instructions_label.setObjectName("inventoryMetaCardAlt")
        reference_input = QLineEdit()
        reference_input.setPlaceholderText("Folio o referencia de transferencia")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar pago")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(info_label)
        layout.addWidget(QLabel("Indicaciones"))
        layout.addWidget(instructions_label)
        layout.addWidget(QLabel("Referencia"))
        layout.addWidget(reference_input)
        layout.addWidget(buttons)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        return {
            "nota": [
                f"Referencia transferencia: {reference_input.text().strip() or 'Sin referencia'}",
            ]
        }

    def _prompt_mixed_payment(self, total: Decimal) -> dict[str, object] | None:
        business = self._load_business_settings_snapshot()
        dialog, layout = self._create_modal_dialog(
            "Cobro mixto",
            "Registra cuanto entra por transferencia y cuanto efectivo recibes. El sistema calcula el cambio.",
            width=520,
        )
        total_label = QLabel(f"Total a cobrar: ${total}")
        total_label.setObjectName("inventoryTitle")
        transfer_info = QLabel(
            "\n".join(
                [
                    f"Banco: {business['transferencia_banco'] or 'No configurado'}",
                    f"Beneficiario: {business['transferencia_beneficiario'] or 'No configurado'}",
                    f"CLABE: {business['transferencia_clabe'] or 'No configurada'}",
                ]
            )
        )
        transfer_info.setWordWrap(True)
        transfer_info.setObjectName("inventoryMetaCard")
        transfer_spin = QDoubleSpinBox()
        transfer_spin.setRange(0.0, 999999.99)
        transfer_spin.setDecimals(2)
        transfer_spin.setPrefix("$")
        transfer_spin.setSingleStep(50.0)
        cash_received_spin = QDoubleSpinBox()
        cash_received_spin.setRange(0.0, 999999.99)
        cash_received_spin.setDecimals(2)
        cash_received_spin.setPrefix("$")
        cash_received_spin.setSingleStep(50.0)
        remaining_label = QLabel("$0.00")
        remaining_label.setObjectName("cashierMetaLabel")
        change_label = QLabel("$0.00")
        change_label.setObjectName("cashierChangeValue")
        reference_input = QLineEdit()
        reference_input.setPlaceholderText("Referencia transferencia opcional")

        def update_mixed_labels() -> None:
            transfer_amount = Decimal(str(transfer_spin.value())).quantize(Decimal("0.01"))
            cash_received = Decimal(str(cash_received_spin.value())).quantize(Decimal("0.01"))
            remaining_cash = total - transfer_amount
            if remaining_cash < Decimal("0.00"):
                remaining_cash = Decimal("0.00")
            change = cash_received - remaining_cash
            if change < Decimal("0.00"):
                change = Decimal("0.00")
            remaining_label.setText(f"${remaining_cash}")
            change_label.setText(f"${change}")

        transfer_spin.valueChanged.connect(update_mixed_labels)
        cash_received_spin.valueChanged.connect(update_mixed_labels)

        form = QFormLayout()
        form.addRow("Transferencia", transfer_spin)
        form.addRow("Efectivo recibido", cash_received_spin)
        form.addRow("Efectivo a cubrir", remaining_label)
        form.addRow("Cambio", change_label)
        form.addRow("Referencia", reference_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar pago")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(total_label)
        layout.addWidget(transfer_info)
        layout.addLayout(form)
        layout.addWidget(buttons)
        update_mixed_labels()

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None

        transfer_amount = Decimal(str(transfer_spin.value())).quantize(Decimal("0.01"))
        cash_received = Decimal(str(cash_received_spin.value())).quantize(Decimal("0.01"))
        cash_due = total - transfer_amount
        if cash_due < Decimal("0.00"):
            cash_due = Decimal("0.00")
        if transfer_amount + cash_received < total:
            QMessageBox.warning(self, "Pago insuficiente", "La suma de transferencia y efectivo debe cubrir el total.")
            return None
        change = (cash_received - cash_due).quantize(Decimal("0.01"))
        if change < Decimal("0.00"):
            change = Decimal("0.00")
        return {
            "nota": [
                f"Transferencia: {transfer_amount}",
                f"Efectivo recibido: {cash_received}",
                f"Cambio: {change}",
                f"Referencia transferencia: {reference_input.text().strip() or 'Sin referencia'}",
            ]
        }

    def _collect_sale_payment_details(self, payment_method: str, total: Decimal) -> dict[str, object] | None:
        if payment_method == "Efectivo":
            return self._prompt_cash_payment(total)
        if payment_method == "Transferencia":
            return self._prompt_transfer_payment(total)
        if payment_method == "Mixto":
            return self._prompt_mixed_payment(total)
        return {"nota": []}

    def _refresh_payment_fields(self) -> None:
        _, _, _, total = self._calculate_sale_totals()
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

        subtotal, discount_percent, applied_discount, total = self._calculate_sale_totals()
        payment_method = self.sale_payment_combo.currentText().strip() or "Efectivo"
        selected_client_id = self.sale_client_combo.currentData()
        sale_note_parts = [f"Metodo de pago: {payment_method}"]
        sale_note_parts.append(f"Descuento: {discount_percent}%")
        if applied_discount > 0:
            sale_note_parts.append(f"Descuento aplicado: {applied_discount}")
        payment_details = self._collect_sale_payment_details(payment_method, total)
        if payment_details is None:
            return
        sale_note_parts.extend([str(note) for note in payment_details.get("nota", [])])

        self._set_sale_processing(True)
        try:
            with get_session() as session:
                usuario = session.get(Usuario, self.user_id)
                if usuario is None:
                    raise ValueError("Usuario no encontrado.")
                cliente = None
                if selected_client_id not in {None, ""}:
                    cliente = session.get(Cliente, int(selected_client_id))
                    if cliente is None:
                        raise ValueError("No se pudo cargar el cliente seleccionado.")
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
                venta.total = total
                VentaService.confirmar_venta(session, venta)
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
        self.inventory_more_button.setEnabled(is_admin)
        self.purchase_button.setEnabled(is_admin)
        self.inventory_count_button.setEnabled(is_admin)
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
        self.settings_create_backup_button.setEnabled(is_admin)
        self.settings_refresh_backups_button.setEnabled(True)
        self.settings_open_backups_button.setEnabled(True)
        self.settings_restore_backup_button.setEnabled(is_admin)
        self.settings_users_button.setEnabled(is_admin)
        self.settings_suppliers_button.setEnabled(is_admin)
        self.settings_clients_button.setEnabled(is_admin)
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
        self.settings_whatsapp_save_button.setEnabled(is_admin)
        self.settings_business_save_button.setEnabled(is_admin)
        self.settings_cash_history_refresh_button.setEnabled(is_admin)
        self.settings_cash_history_detail_button.setEnabled(is_admin and self._selected_cash_history_id() is not None)

        if self.dashboard_users_card is not None:
            self.dashboard_users_card.setVisible(is_admin)
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
                Variante.sku,
                Categoria.nombre,
                Marca.nombre,
                Producto.nombre,
                Producto.descripcion,
                Variante.talla,
                Variante.color,
                Variante.precio_venta,
                Variante.costo_referencia,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Producto.activo,
                Variante.activo,
            )
            .join(Variante.producto)
            .join(Producto.categoria)
            .join(Producto.marca)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
            .order_by(Categoria.nombre.asc(), Marca.nombre.asc(), Producto.nombre.asc(), Variante.sku.asc())
        ).all()

        search_text = self.catalog_search_input.text().strip()
        category_filter = self.catalog_category_filter_combo.currentData()
        brand_filter = self.catalog_brand_filter_combo.currentData()
        status_filter = str(self.catalog_status_filter_combo.currentData() or "")
        catalog_filter = str(self.catalog_layaway_filter_combo.currentData() or "")

        self.catalog_rows = [
            {
                "variante_id": row[0],
                "producto_id": row[1],
                "categoria_id": row[2],
                "marca_id": row[3],
                "sku": row[4],
                "categoria_nombre": row[5],
                "marca_nombre": row[6],
                "producto_nombre": row[7],
                "producto_descripcion": row[8],
                "talla": row[9],
                "color": row[10],
                "precio_venta": row[11],
                "costo_referencia": row[12],
                "stock_actual": row[13],
                "apartado_cantidad": row[14],
                "producto_activo": row[15],
                "variante_activo": row[16],
                "producto_estado": "ACTIVO" if row[15] else "INACTIVO",
                "variante_estado": "ACTIVA" if row[16] else "INACTIVA",
            }
            for row in rows
            if (
                (not search_text or search_text.lower() in " ".join(
                    str(value).lower()
                    for value in (row[4], row[5], row[6], row[7], row[9], row[10])
                ))
                and (not category_filter or int(row[2]) == int(category_filter))
                and (not brand_filter or int(row[3]) == int(brand_filter))
                and (
                    not status_filter
                    or (status_filter == "active" and bool(row[16]))
                    or (status_filter == "inactive" and not bool(row[16]))
                )
                and (not catalog_filter or (catalog_filter == "reserved" and int(row[14]) > 0))
            )
        ]

        self.catalog_table.setRowCount(len(self.catalog_rows))
        for row_index, row in enumerate(self.catalog_rows):
            values = [
                row["sku"],
                row["marca_nombre"],
                row["producto_nombre"],
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
        if selected_variant_id is not None and not self._select_catalog_variant(selected_variant_id):
            self._clear_catalog_editor()
        elif selected_variant_id is None:
            self._clear_catalog_editor()

    def _refresh_combos(self, session) -> None:
        categorias = session.scalars(select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)).all()
        marcas = session.scalars(select(Marca).where(Marca.activo.is_(True)).order_by(Marca.nombre)).all()
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
        self._populate_filter_combo(
            self.catalog_category_filter_combo,
            "Categoria: todas",
            [(categoria.nombre, categoria.id) for categoria in categorias],
        )
        self._populate_filter_combo(
            self.catalog_brand_filter_combo,
            "Marca: todas",
            [(marca.nombre, marca.id) for marca in marcas],
        )
        self._populate_filter_combo(
            self.inventory_category_filter_combo,
            "Categoria: todas",
            [(categoria.nombre, categoria.id) for categoria in categorias],
        )
        self._populate_filter_combo(
            self.inventory_brand_filter_combo,
            "Marca: todas",
            [(marca.nombre, marca.id) for marca in marcas],
        )
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
                Variante.talla,
                Variante.color,
                Variante.stock_actual,
                func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
                Variante.activo,
            )
            .join(Variante.producto)
            .join(Producto.categoria)
            .join(Producto.marca)
            .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
        )

        search_text = self.inventory_search_input.text().strip()
        if search_text:
            statement = statement.where(
                or_(
                    Variante.sku.ilike(f"%{search_text}%"),
                    Producto.nombre.ilike(f"%{search_text}%"),
                    Variante.talla.ilike(f"%{search_text}%"),
                    Variante.color.ilike(f"%{search_text}%"),
                    Categoria.nombre.ilike(f"%{search_text}%"),
                    Marca.nombre.ilike(f"%{search_text}%"),
                )
            )

        category_filter = self.inventory_category_filter_combo.currentData()
        if category_filter:
            statement = statement.where(Categoria.id == int(category_filter))

        brand_filter = self.inventory_brand_filter_combo.currentData()
        if brand_filter:
            statement = statement.where(Marca.id == int(brand_filter))

        status_filter = self.inventory_status_filter_combo.currentData()
        if status_filter == "active":
            statement = statement.where(Variante.activo.is_(True))
        elif status_filter == "inactive":
            statement = statement.where(Variante.activo.is_(False))

        stock_filter = self.inventory_stock_filter_combo.currentData()
        if stock_filter == "zero":
            statement = statement.where(Variante.stock_actual == 0)
        elif stock_filter == "low":
            statement = statement.where(Variante.stock_actual.between(1, 3))
        elif stock_filter == "available":
            statement = statement.where(Variante.stock_actual > 0)

        qr_filter = self.inventory_qr_filter_combo.currentData()

        rows = session.execute(statement.order_by(Producto.nombre.asc(), Variante.sku.asc())).all()

        visible_rows: list[tuple[object, ...]] = []
        count_out = 0
        count_low = 0
        count_missing_qr = 0
        count_inactive = 0
        for row in rows:
            qr_exists = False
            variante = session.get(Variante, int(row[0]))
            if variante is not None:
                qr_exists = QrGenerator.exists_for_variant(variante)
            if qr_filter == "ready" and not qr_exists:
                continue
            if qr_filter == "missing" and qr_exists:
                continue
            stock_value = int(row[7])
            committed_value = int(row[8])
            if stock_value == 0:
                count_out += 1
            elif stock_value <= 3:
                count_low += 1
            if not qr_exists:
                count_missing_qr += 1
            if not bool(row[9]):
                count_inactive += 1
            visible_rows.append((*row, qr_exists))

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
        for row_index, row in enumerate(visible_rows):
            stock_value = int(row[7])
            committed_value = int(row[8])
            stock_tone = "danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive"
            estado_text = "ACTIVA" if row[9] else "INACTIVA"
            estado_tone = "positive" if row[9] else "muted"
            qr_text = "Listo" if row[10] else "Pendiente"
            qr_tone = "positive" if row[10] else "warning"
            values = [
                row[1],
                row[4],
                row[5],
                row[6],
                _stock_table_text(stock_value),
                committed_value,
                estado_text,
                qr_text,
            ]
            for column_index, value in enumerate(values):
                self.inventory_table.setItem(row_index, column_index, _table_item(value))
            self.inventory_table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row[0])
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
        self._sync_inventory_table_selection(current_variant_id)
        self._refresh_inventory_overview()

    def _handle_inventory_filters_changed(self) -> None:
        try:
            with get_session() as session:
                self._refresh_inventory_table(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de inventario.")

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
        try:
            with get_session() as session:
                self._refresh_catalog(session)
        except SQLAlchemyError:
            self.status_label.setText("Estado: no se pudieron aplicar los filtros de productos.")

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
        total_items = 0
        for row_index, item in enumerate(self.sale_cart):
            line_subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
            total_items += int(item["cantidad"])
            values = [
                item["sku"],
                item["producto_nombre"],
                item["cantidad"],
                item["precio_unitario"],
                line_subtotal,
            ]
            for column_index, value in enumerate(values):
                self.sale_cart_table.setItem(row_index, column_index, _table_item(value))
        self.sale_cart_table.resizeColumnsToContents()
        subtotal, discount_percent, applied_discount, total = self._calculate_sale_totals()
        payment_method = self.sale_payment_combo.currentText().strip() or "Efectivo"
        self.sale_total_label.setText(f"${total}")
        self.sale_total_meta_label.setText(
            f"Pago: {payment_method} | Desc.: {discount_percent}% (${applied_discount})"
            if self.sale_cart
            else "Total a cobrar"
        )
        self.sale_summary_label.setText(
            (
                f"Lineas: {len(self.sale_cart)} | Piezas: {total_items} | "
                f"Subtotal: ${subtotal} | Descuento: {discount_percent}% (${applied_discount}) | Total: ${total}"
            )
            if self.sale_cart
            else "Carrito vacio."
        )
        self._refresh_payment_fields()
        can_sell = self.current_role in {RolUsuario.ADMIN, RolUsuario.CAJERO}
        self.sale_remove_button.setEnabled(can_sell and bool(self.sale_cart))
        self.sale_clear_button.setEnabled(can_sell and bool(self.sale_cart))
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
        toggle_action = menu.addAction(
            "Activar presentacion" if not bool(selected["variante_activo"]) else "Desactivar presentacion"
        )

        is_admin = self.current_role == RolUsuario.ADMIN
        edit_action.setEnabled(is_admin)
        entry_action.setEnabled(is_admin)
        adjust_action.setEnabled(is_admin)
        toggle_action.setEnabled(is_admin)

        chosen = menu.exec(self.inventory_table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self._handle_update_variant()
        elif chosen == entry_action:
            self._handle_purchase()
        elif chosen == adjust_action:
            self._handle_inventory_adjustment()
        elif chosen == qr_action:
            self._handle_generate_selected_qr()
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
                self.inventory_overview_label.setText(variante.sku)
                self.inventory_product_label.setText(variante.producto.nombre)
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
                matching_row = next(
                    (row for row in self.catalog_rows if int(row["variante_id"]) == int(variante_id)),
                    None,
                )
                self.inventory_stock_hint_label.setText(
                    f"Talla {variante.talla} | Color {variante.color} | Precio {variante.precio_venta}"
                )
                self.inventory_meta_label.setText(
                    f"Stock actual {variante.stock_actual} | Apartado {matching_row['apartado_cantidad'] if matching_row is not None else 0}"
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
                    f"{variante.sku} | {variante.producto.nombre} | precio {variante.precio_venta} | "
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
        self.products_selection_label.setText("Consulta productos, precios y stock disponible para venta.")
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
