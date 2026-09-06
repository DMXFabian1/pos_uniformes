"""Ventana satelite para gestion dedicada de Presupuestos."""

from __future__ import annotations

import logging
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

from PyQt6.QtCore import QDate, QSize, QStringListModel, QThread, QTimer, Qt, pyqtSignal
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
    QListWidget,
    QListWidgetItem,
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
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCompleter,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Cliente, Empleada, EstadoPresupuesto, RolUsuario, Usuario
from pos_uniformes.services.active_filter_service import build_active_filter_tokens
from pos_uniformes.services.catalog_local_cache_service import (
    catalog_cache_saved_at,
    format_cache_age_label,
    load_catalog_cache,
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
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget
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
from pos_uniformes.ui.helpers.quote_cart_view_helper import build_quote_cart_view, normalize_cart_row_index
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
from pos_uniformes.utils.date_format import local_day_window
from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
from pos_uniformes.services.inventory_label_service import (
    InventoryLabelContext,
    load_inventory_label_context,
    render_inventory_label,
    render_inventory_label_from_cache_row,
)

logger = logging.getLogger(__name__)

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


class _MeilisearchWorker(QThread):
    """Ejecuta operaciones de Meilisearch en segundo plano."""

    progress: pyqtSignal = pyqtSignal(str)
    finished: pyqtSignal = pyqtSignal(bool, str)  # (ok, mensaje)

    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode  # 'start' | 'sync'

    def run(self) -> None:
        try:
            from pos_uniformes.services import meilisearch_service

            if self._mode == "start":
                if meilisearch_service.is_available():
                    self.finished.emit(True, "Meilisearch ya está corriendo.")
                    return
                self.progress.emit("Iniciando Meilisearch...")
                status = meilisearch_service.ensure_installed(on_progress=self.progress.emit)
                self.finished.emit(meilisearch_service.is_available(), status)

            elif self._mode == "sync":
                if not meilisearch_service.is_available():
                    self.progress.emit("Iniciando Meilisearch...")
                    meilisearch_service.ensure_installed(on_progress=self.progress.emit)
                    if not meilisearch_service.is_available():
                        self.finished.emit(False, "No se pudo iniciar Meilisearch.")
                        return
                self.progress.emit("Configurando índice...")
                meilisearch_service.configure_index()
                self.progress.emit("Indexando catálogo...")
                from pos_uniformes.database.connection import get_session
                with get_session() as session:
                    count = meilisearch_service.index_from_db(session)
                self.finished.emit(True, f"Catálogo re-indexado: {count} presentaciones.")

        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, f"Error: {exc}")


class _MeilisearchProgressDialog(QDialog):
    """Diálogo con barra de progreso para operaciones de Meilisearch."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 22)

        self._icon_label = QLabel("⚙️")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size:32px;")
        layout.addWidget(self._icon_label)

        self._status_label = QLabel("Iniciando...")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("font-size:13px; color:#2f2a24;")
        layout.addWidget(self._status_label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            "QProgressBar{border-radius:4px;background:#f0ebe4;}"
            "QProgressBar::chunk{border-radius:4px;background:#7b2d14;}"
        )
        layout.addWidget(self._bar)

        self._close_btn = QPushButton("Cerrar")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        layout.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def update_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def finish(self, success: bool, msg: str) -> None:
        self._icon_label.setText("✅" if success else "❌")
        self._status_label.setText(msg)
        self._bar.setRange(0, 100)
        self._bar.setValue(100 if success else 0)
        self._close_btn.setEnabled(True)


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
        try:
            super().mouseDoubleClickEvent(event)
        except RuntimeError:
            pass


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


# Escuelas por página en el paso guiado "Elige escuela".
_GUIDED_SCHOOLS_PER_PAGE = 9
# Modelos por página en el paso guiado "Modelos sugeridos".
# 8 = 2 filas de 4 en la pantalla del kiosko (evita la 3ª fila que obliga a scroll).
_GUIDED_MODELS_PER_PAGE = 8


def _paginate(options: list, page: int, per_page: int) -> tuple[list, int, int]:
    """Devuelve (opciones_de_la_pagina, pagina_ajustada, total_paginas).

    `page` se acota a [0, total_paginas-1]. Con lista vacía -> ([], 0, 1).
    """
    total = len(options)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return options[start : start + per_page], page, total_pages


_DIA_CORTO = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


class QuoteSatelliteWindow(QMainWindow):
    # Emite el resultado del watchdog de reconexión desde el hilo de fondo al
    # hilo de UI: (rows | None, school_links | None). None = DB no disponible.
    _db_refresh_ready = pyqtSignal(object, object)
    # Avisa (en hilo de UI) que el cache de anuncios se refrescó desde la DB.
    _anuncios_ready = pyqtSignal()
    # Hay versión nueva publicada en la PC principal (payload: la versión).
    _update_disponible = pyqtSignal(str)
    # False hasta el primer _refresh_catalog_snapshot: el reindex de arranque
    # ya corre en background, solo los refresh posteriores notifican de nuevo.
    _catalog_snapshot_loaded_once = False

    def __init__(
        self,
        user_id: int | None,
        offline_mode: bool = False,
        offline_catalog_cache: list[dict] | None = None,
    ) -> None:
        super().__init__()
        self.user_id = user_id
        self.offline_mode = offline_mode
        # Estado de conectividad cacheado (lo mantiene el watchdog off-thread).
        # Arranca según cómo booteó la ventana: si booteó offline, la DB no está.
        # El despachador lo consulta para NO abrir conexiones que congelan la UI.
        self._db_online = not offline_mode
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
        self._sku_index: dict[str, dict[str, object]] = {}
        self.catalog_browser_visible_skus: tuple[str, ...] = ()
        self.catalog_browser_page_index = 0
        self.current_page_key = "kiosk"
        self.catalog_browser_debounce_timer = QTimer(self)
        self.catalog_browser_debounce_timer.setSingleShot(True)
        self.catalog_browser_debounce_timer.setInterval(SATELLITE_SEARCH_DEBOUNCE_MS)
        self.catalog_browser_debounce_timer.timeout.connect(self._run_catalog_browser_refresh)
        self._quote_filter_debounce_timer = QTimer(self)
        self._quote_filter_debounce_timer.setSingleShot(True)
        self._quote_filter_debounce_timer.setInterval(SATELLITE_SEARCH_DEBOUNCE_MS)
        self._quote_filter_debounce_timer.timeout.connect(self._handle_quote_filters_changed)
        seed_favorites_from_bundle()
        self._favorites: set[str] = load_favorites()
        self._school_links: list[dict] = load_school_links_cache()

        self._build_widgets()
        self._apply_icons()
        self._apply_styles()
        self._build_ui()
        self._bind_events()

        # Conectar ANTES de cualquier refresh: el arranque cache-first lanza
        # _start_background_db_refresh dentro de refresh_all, y si el worker
        # termina antes de este connect (PC principal apagada: el probe falla
        # en ~1ms) la señal se perdería y _db_refresh_running quedaría
        # atorado en True — watchdog muerto hasta reiniciar.
        self._db_refresh_ready.connect(self._on_db_refresh_ready)
        self._update_disponible.connect(self._ofrecer_actualizacion)
        # Buscar actualizaciones en background poco después de arrancar
        # (también hay botón manual en el admin Ctrl+Shift+A).
        QTimer.singleShot(20_000, self._buscar_actualizacion_en_background)

        if self.offline_mode:
            self._init_offline(offline_catalog_cache or [])
        else:
            self._load_operator_context()
            self._reset_quote_form()
            self._apply_lookup_view(build_empty_quote_kiosk_lookup_view())
            self._apply_catalog_detail(None)
            self._apply_guided_detail(None)
            self._refresh_recent_lookup_table()
            self.refresh_all(catalog_from_cache=True)

        QTimer.singleShot(0, self.kiosk_scan_input.setFocus)

        # Watchdog de reconexión: el modo (online/offline) se fija al arrancar,
        # pero la PC principal puede encenderse/apagarse después. Este timer
        # revisa la DB en segundo plano y refresca el catálogo cuando está
        # disponible — así el orden de encendido deja de importar y el satélite
        # nunca se queda con precios viejos ni se cae si la PC se apaga.
        # (la señal _db_refresh_ready se conecta arriba, antes del refresh)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(300_000)  # cada 5 min
        self._reconnect_timer.timeout.connect(self._start_background_db_refresh)
        self._reconnect_timer.start()
        # Primer chequeo pronto (60 s) para tomar la PC si encendió tarde.
        QTimer.singleShot(60_000, self._start_background_db_refresh)

        # Heartbeat de presencia: este satélite se registra y late cada 60 s para
        # que el punto de control (Mac / satélite-servidor / PWA) sepa que está
        # encendido y pueda dirigirle anuncios. Off-thread, best-effort.
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(60_000)
        self._heartbeat_timer.timeout.connect(self._enviar_heartbeat)
        self._heartbeat_timer.start()
        QTimer.singleShot(3_000, self._enviar_heartbeat)  # primer latido pronto

        # Despachador de trabajos: si esta PC imprime local (es el satélite
        # físico con las impresoras), drena la cola que le mandan el POS/kiosko.
        self._trabajo_dispatcher = None
        QTimer.singleShot(2_000, self._start_trabajo_dispatcher)

        # Banner de conteo pendiente: chequeo inicial + periódico (cada 10 min).
        QTimer.singleShot(4_000, self._refresh_conteo_banner)
        self._conteo_banner_timer = QTimer(self)
        self._conteo_banner_timer.setInterval(600_000)
        self._conteo_banner_timer.timeout.connect(self._refresh_conteo_banner)
        self._conteo_banner_timer.start()
        # Nota: NO se imprimen órdenes de conteo automáticamente. El banner solo
        # avisa qué escuelas están vencidas; la impresión es manual desde
        # "Imprimir orden de conteo" (el trabajador elige la escuela).

        # Cartelera de anuncios: overlay a pantalla completa con los anuncios que
        # se difunden a todos los satélites (cartelera al estar inactivo + aviso
        # inmediato). Se crea diferido para no bloquear el arranque de la ventana.
        self._anuncio_cartelera = None
        self._anuncio_listener = None
        self._anuncio_inmediato_pendiente = None
        self._anuncios_ready.connect(self._on_anuncios_ready)
        QTimer.singleShot(2_500, self._setup_anuncio_cartelera)

    def _start_trabajo_dispatcher(self) -> None:
        """Arranca el despachador solo si esta máquina está en modo LOCAL.

        En modo LOCAL esta PC tiene las impresoras: además de imprimir sus
        propios tickets, drena la cola de trabajos enviados por otras máquinas.
        En modo SATÉLITE (envía a otra PC) no despacha nada.
        """
        try:
            from pos_uniformes.services.print_routing_cache_service import (
                MODO_LOCAL,
                load_print_routing,
            )

            modo, _origen = load_print_routing()
            if modo != MODO_LOCAL:
                return

            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher
            from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

            self._trabajo_dispatcher = TrabajoDispatcher(
                get_session,
                build_handlers(),
                schedule=QTimer.singleShot,
                on_event=self._on_trabajo_event,
                # No abrir conexión (que bloquea el hilo de UI hasta el
                # connect_timeout) mientras el watchdog sepa que la DB está caída.
                connectivity_probe=lambda: self._db_online,
            )
            self._trabajo_dispatcher.start()
        except Exception:  # noqa: BLE001 — nunca impedir que la ventana funcione
            self._trabajo_dispatcher = None
            return

        # LISTEN/NOTIFY: despacha al instante cuando llega un trabajo. Si no se
        # puede (driver/conexión), el polling del despachador sigue de respaldo.
        try:
            from pos_uniformes.ui.helpers.trabajo_listener import TrabajoNotifyListener

            self._trabajo_listener = TrabajoNotifyListener(self)
            self._trabajo_listener.notificado.connect(self._trabajo_dispatcher.drain)
            self._trabajo_listener.start()
        except Exception:  # noqa: BLE001
            self._trabajo_listener = None

        # Limpieza periódica de trabajos terminados viejos.
        self._trabajo_cleanup_timer = QTimer(self)
        self._trabajo_cleanup_timer.setInterval(6 * 60 * 60 * 1000)  # cada 6h
        self._trabajo_cleanup_timer.timeout.connect(self._limpiar_trabajos_viejos)
        self._trabajo_cleanup_timer.start()
        QTimer.singleShot(300_000, self._limpiar_trabajos_viejos)  # una vez a los 5 min

        # Servidor de impresión sin impresora de tickets elegida: avisar. Si no,
        # los tickets van a la predeterminada de Windows y se marcan "impresos"
        # sin salir papel. Diferido para no bloquear el arranque de la ventana.
        QTimer.singleShot(1_500, self._advertir_impresora_tickets_sin_elegir)

    def _advertir_impresora_tickets_sin_elegir(self) -> None:
        """Avisa (una vez, al arrancar el servidor) si falta elegir impresora."""
        try:
            from pos_uniformes.services.ticket_print_settings_cache_service import (
                falta_impresora_tickets,
            )

            if not falta_impresora_tickets():
                return
        except Exception:  # noqa: BLE001
            return
        QMessageBox.warning(
            self,
            "Falta elegir la impresora de tickets",
            "Esta PC es el Servidor de impresión pero no tiene una impresora de "
            "tickets elegida.\n\nLos tickets saldrán por la impresora "
            "PREDETERMINADA de Windows (que puede no ser la térmica) y se marcarán "
            "como impresos aunque no salga papel.\n\n"
            "Ve a Ctrl+Shift+A → 🖨 Impresoras y elige la impresora térmica.",
        )

    def _limpiar_trabajos_viejos(self) -> None:
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import trabajos_service as trabajos_svc

            with get_session() as session:
                n = trabajos_svc.limpiar_trabajos_viejos(session, dias=7)
                session.commit()
            if n:
                import logging

                logging.getLogger(__name__).info("Limpieza: %s trabajo(s) viejos borrados", n)
        except Exception:  # noqa: BLE001 — la limpieza nunca debe molestar
            pass

    def _on_trabajo_event(self, trabajo_id, estado, error) -> None:
        import logging

        msg = f"[despachador] trabajo {trabajo_id} -> {estado.value}"
        if error:
            logging.getLogger(__name__).warning("%s: %s", msg, error)
        else:
            logging.getLogger(__name__).info(msg)

        # Si el panel de la cola está abierto, refrescarlo en vivo.
        panel = getattr(self, "_dispatcher_panel", None)
        if panel is not None:
            try:
                panel.refresh()
            except Exception:  # noqa: BLE001
                pass

    def closeEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        for attr in ("_trabajo_listener", "_anuncio_listener"):
            listener = getattr(self, attr, None)
            if listener is not None:
                try:
                    listener.stop()
                    listener.wait(1000)
                except Exception:  # noqa: BLE001
                    pass
        super().closeEvent(event)

    def _start_background_db_refresh(self) -> None:
        """Lanza un hilo que revisa la DB y trae catálogo fresco si se puede."""
        if getattr(self, "_db_refresh_running", False):
            return
        self._db_refresh_running = True
        import threading

        def _worker() -> None:
            rows = None
            links = None
            anuncios_ok = False
            try:
                from pos_uniformes.services.satellite_startup_service import probe_database_host
                if probe_database_host():
                    with get_session() as session:
                        rows = load_catalog_snapshot_rows(session)
                        try:
                            links = list_all_active_links(session)
                        except Exception:  # noqa: BLE001
                            links = None
                        # Baja los anuncios DIRIGIDOS a este satélite y los cachea
                        # localmente para que la cartelera funcione aun con el
                        # servidor apagado. De paso, late (presencia).
                        try:
                            from pos_uniformes.services.anuncio_service import filas_para_cache
                            from pos_uniformes.services.anuncio_local_cache_service import (
                                save_anuncios_cache,
                            )
                            from pos_uniformes.services.satellite_identity_service import (
                                get_satellite_id,
                                get_satellite_name,
                            )
                            from pos_uniformes.services.satelite_registry_service import registrar

                            mi_id = get_satellite_id()
                            registrar(session, mi_id, get_satellite_name())
                            session.commit()
                            save_anuncios_cache(filas_para_cache(session, para=mi_id))
                            anuncios_ok = True
                        except Exception:  # noqa: BLE001
                            anuncios_ok = False
            except Exception:  # noqa: BLE001 — nunca tumbar por el watchdog
                rows = None
                links = None
            finally:
                # Resetear ANTES de emitir: si la emisión se perdiera por
                # cualquier razón, el watchdog no debe quedar atorado.
                self._db_refresh_running = False
                self._db_refresh_ready.emit(rows, links)
                if anuncios_ok:
                    self._anuncios_ready.emit()

        threading.Thread(target=_worker, daemon=True, name="satellite-db-watchdog").start()

    def _on_db_refresh_ready(self, rows, links) -> None:
        """Slot en hilo de UI: aplica el catálogo fresco (o marca sin conexión)."""
        self._db_refresh_running = False
        if not rows:
            # DB no disponible ahora — seguimos con el cache, sin cerrar nada.
            self._db_online = False
            self._set_db_connectivity_banner(online=False)
            return
        self._db_online = True
        # El servidor volvió: drena de una lo que se haya acumulado en la cola.
        disp = getattr(self, "_trabajo_dispatcher", None)
        if disp is not None:
            QTimer.singleShot(0, disp.drain)
        self.catalog_snapshot_rows = rows
        self._rebuild_sku_index()
        try:
            save_catalog_cache(rows)
        except Exception:  # noqa: BLE001
            pass
        if links is not None:
            self._school_links = links
            try:
                save_school_links_cache(links)
            except Exception:  # noqa: BLE001
                pass
        # Repintar lo que muestra el catálogo: con el arranque cache-first,
        # este es el camino por el que llegan las filas frescas — sin esto,
        # el navegador y el combo de niveles se quedan con el cache de disco.
        self._rebuild_catalog_level_combo()
        self._refresh_catalog_browser()
        self._refresh_guided_browser()
        self._set_db_connectivity_banner(online=True)

    def _set_db_connectivity_banner(self, *, online: bool) -> None:
        """Actualiza el banner según la conectividad detectada en runtime."""
        if online:
            # Con conexión: ocultar el banner de modo local (si estaba).
            if not self.offline_mode:
                self.offline_banner.setVisible(False)
            else:
                self.offline_banner.setText(
                    "Catalogo actualizado desde la PC principal. "
                    "Reinicia para operar en linea completa."
                )
                self.offline_banner.setVisible(True)
        else:
            saved_at = catalog_cache_saved_at()
            age_text = format_cache_age_label(saved_at) if saved_at else "cache local"
            self.offline_banner.setText(
                f"Sin conexion con la PC principal — Catalogo {age_text}."
            )
            self.offline_banner.setVisible(True)

    def _init_offline(self, cache_rows: list[dict]) -> None:
        """Inicializa la ventana en modo local sin tocar la base de datos."""
        self.catalog_snapshot_rows = cache_rows
        self._rebuild_sku_index()
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
        self._refresh_tariff_schools()
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
        self.page_stack.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_button_group = QButtonGroup(self)
        self.nav_kiosk_button = QPushButton("Kiosko")
        self.nav_catalog_button = QPushButton("Catalogo")
        self.nav_guided_button = QPushButton("Presupuesto guiado")
        self.nav_quote_button = QPushButton("Presupuesto")
        self.nav_quicksale_button = QPushButton("Venta rapida")
        self.nav_share_button = QPushButton("Compartir")
        self.nav_search_button = QPushButton("Buscar")
        self.nav_tariff_button = QPushButton("Tarifarios")
        self.nav_libreta_button = QPushButton("Libreta")
        self.nav_conteos_button = QPushButton("Calendario")
        # "Tarifarios" oculto (decisión de Daniel, 2026-09-02): su lugar lo
        # toma "Libreta". La página y su código siguen vivos; para restaurarla
        # basta quitar esta línea.
        self.nav_tariff_button.setVisible(False)
        # Ocultos temporalmente (2026-07-05, decisión de Daniel): "Presupuesto"
        # y "Buscar" no se usan en piso por ahora — las páginas siguen vivas y
        # se retomarán después; para restaurarlas basta quitar estas 2 líneas.
        self.nav_quote_button.setVisible(False)
        self.nav_search_button.setVisible(False)
        # Sección "Catálogo" oculta (decisión de Daniel, 2026-07-11): no se usa
        # en piso. La página sigue viva; para restaurarla, quitar esta línea y la
        # del botón "Abrir catalogo" más abajo.
        self.nav_catalog_button.setVisible(False)
        self.sidebar_total_label = QLabel("$0.00")
        self.sidebar_summary_label = QLabel("Sin piezas en el presupuesto actual.")
        self.sidebar_items_count_label = QLabel("0 lineas | 0 pzas")
        self.sidebar_items_scroll = QScrollArea()
        self.sidebar_items_content = QWidget()
        self.sidebar_items_layout = QVBoxLayout()
        self.kiosk_open_quote_button = QPushButton("Ver presupuesto")
        # Navega a la página "Presupuesto" (oculta temporalmente) — se oculta junto.
        self.kiosk_open_quote_button.setVisible(False)
        self.kiosk_open_search_button = QPushButton("Abrir catalogo")
        # Atajo a la sección "Catálogo" (oculta) — se oculta junto.
        self.kiosk_open_search_button.setVisible(False)
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
        # Los controles de Meilisearch viven en el menú admin (Ctrl+Shift+A);
        # el header solo muestra un indicador pasivo ●/○. Los botones siguen
        # existiendo (sin agregarse a ningún layout) para no romper wiring.
        self.guided_reindex_button = QPushButton("↻ Sync")
        self.guided_meilisearch_btn = QPushButton("○ Meilisearch")
        self.guided_meili_indicator = QLabel("○")
        self.guided_reset_button = QPushButton("Limpiar pasos")
        self.guided_basics_button = QPushButton("Piezas generales")
        self.guided_visual_icon_label = QLabel()
        self.guided_detail_title_label = QLabel("Sin seleccion.")
        self.guided_detail_meta_label = QLabel("")
        self.guided_detail_notes_label = QLabel("")
        self.guided_mode_buttons: dict[str, QPushButton] = {}
        self.guided_level_buttons: dict[str, QPushButton] = {}
        self.guided_school_buttons: dict[str, QPushButton] = {}
        # Paginación del paso "Elige escuela".
        self._guided_school_all_options: list = []
        self._guided_school_option_keys: list | None = None
        self._guided_school_page: int = 0
        self.guided_gender_buttons: dict[str, QPushButton] = {}
        self.guided_profile_buttons: dict[str, QPushButton] = {}
        self.guided_bucket_buttons: dict[str, QPushButton] = {}
        self.guided_piece_buttons: dict[str, QPushButton] = {}
        self.guided_variant_buttons: dict[str, QPushButton] = {}
        self.guided_product_buttons: dict[str, QPushButton] = {}
        # Paginación del paso "Modelos sugeridos".
        self._guided_product_all_cards: list = []
        self._guided_product_key_set: frozenset | None = None
        self._guided_product_page: int = 0

        # Búsqueda rápida Meilisearch
        self.guided_search_input = QLineEdit()
        self.guided_search_input.setPlaceholderText("Buscar producto rapido…")
        self.guided_search_input.setClearButtonEnabled(True)
        self._guided_search_timer = QTimer()
        self._guided_search_timer.setSingleShot(True)
        self._guided_search_timer.setInterval(250)
        self._guided_search_timer.timeout.connect(self._run_guided_search)
        self.guided_search_input.textChanged.connect(self._on_guided_search_text_changed)
        self.guided_search_input.returnPressed.connect(self._run_guided_search)
        self._guided_search_input_submitted = False
        # Completer predictivo
        self._search_completer_model = QStringListModel()
        self._search_completer = QCompleter(self._search_completer_model, self)
        self._search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._search_completer.setMaxVisibleItems(8)
        self._search_completer.activated.connect(self._on_search_suggestion_selected)
        self.guided_search_input.setCompleter(self._search_completer)
        self._suggest_timer = QTimer()
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(150)
        self._suggest_timer.timeout.connect(self._update_search_suggestions)
        self._guided_steps_widget: QFrame | None = None
        self._guided_detail_widget: QFrame | None = None
        self._search_results_widget: QWidget | None = None
        self._search_results_layout: QVBoxLayout | None = None
        self._selected_search_btn: _DoubleClickButton | None = None

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
        # — Tarifario widgets —
        self.tariff_school_combo = QComboBox()
        self.tariff_generate_button = QPushButton("Generar tarifario")
        self.tariff_print_button = QPushButton("Imprimir")
        self.tariff_preview = QTextEdit()
        self.tariff_preview.setReadOnly(True)
        self._current_tariff: dict | None = None

    def _apply_icons(self) -> None:
        nav_icons = {
            self.nav_kiosk_button: _icon_from_asset("kiosk_icons/kiosk_scan.svg"),
            self.nav_catalog_button: _icon_from_asset("kiosk_icons/catalog_grid.svg"),
            self.nav_guided_button: _icon_from_asset("kiosk_icons/quote_stack.svg"),
            self.nav_quote_button: _icon_from_asset("kiosk_icons/quote_stack.svg"),
            self.nav_quicksale_button: _icon_from_asset("kiosk_icons/kiosk_scan.svg"),
            self.nav_share_button: _icon_from_asset("kiosk_icons/share_send.svg"),
            self.nav_search_button: _icon_from_asset("kiosk_icons/search_quote.svg"),
            self.nav_tariff_button: _icon_from_asset("kiosk_icons/catalog_grid.svg"),
            self.nav_libreta_button: _icon_from_asset("kiosk_icons/quote_stack.svg"),
            self.nav_conteos_button: _icon_from_asset("kiosk_icons/calendar.svg"),
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
        page_scrolls = [
            self.page_stack.widget(i)
            for i in range(self.page_stack.count())
            if isinstance(self.page_stack.widget(i), QScrollArea)
        ]
        for scroll_area in [
            self.sidebar_items_scroll,
            self.guided_product_scroll,
            self.guided_page_scroll,
            self.guided_school_scroll,
            *page_scrolls,
        ]:
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
            self.nav_quicksale_button,
            self.nav_catalog_button,
            self.nav_guided_button,
            self.nav_quote_button,
            self.nav_search_button,
            self.nav_tariff_button,
            self.nav_libreta_button,
            self.nav_conteos_button,
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
        # Cuadro de resumen RETIRADO (pedido de Daniel 2026-09-05): repetía
        # el total y robaba espacio a "Piezas agregadas" — las líneas/piezas
        # ya se ven en el contador de esa sección. setVisible(True) lo revive.
        self.sidebar_summary_label.setVisible(False)
        budget_card.setLayout(budget_layout)
        # Tarjeta "Tu presupuesto" RETIRADA completa (pedido de Daniel
        # 2026-09-05): todo el sidebar es para "Piezas agregadas".
        # setVisible(True) la revive.
        budget_card.setVisible(False)

        items_card = QFrame()
        items_card.setObjectName("satTotalsCard")
        items_layout = QVBoxLayout()
        items_layout.setContentsMargins(14, 14, 14, 14)
        items_layout.setSpacing(8)
        items_title = QLabel("Piezas agregadas")
        items_title.setObjectName("satSidebarTitle")
        self.sidebar_clear_button = QPushButton()
        self.sidebar_clear_button.setObjectName("satSidebarClearButton")
        self.sidebar_clear_button.setToolTip("Limpiar piezas agregadas")
        self.sidebar_clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_clear_button.setFixedSize(34, 34)
        self.sidebar_clear_button.setIcon(_icon_from_asset("kiosk_icons/trash.svg"))
        self.sidebar_clear_button.setIconSize(QSize(20, 20))
        self.sidebar_clear_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; }"
            "QPushButton:hover { background: #fdecea; border-radius: 8px; }"
        )
        self.sidebar_clear_button.clicked.connect(self._handle_sidebar_clear_pieces)
        items_header = QHBoxLayout()
        items_header.setContentsMargins(0, 0, 0, 0)
        items_header.addWidget(items_title)
        items_header.addStretch(1)
        items_header.addWidget(self.sidebar_clear_button)
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
        items_layout.addLayout(items_header)
        items_layout.addWidget(self.sidebar_items_count_label)
        items_layout.addWidget(self.sidebar_items_scroll, 1)
        items_card.setLayout(items_layout)

        layout.addWidget(budget_card)
        layout.addWidget(items_card, 1)
        card.setLayout(layout)
        return card

    @staticmethod
    def _scrollable(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget { border: none; background: transparent; }"
        )
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        # setWidget() activa autoFillBackground y pinta la paleta del sistema
        # (oscura en Windows) en los huecos entre tarjetas.
        widget.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        # Pantalla táctil: arrastrar con el dedo scrollea la página (gesto
        # touch puro — el mouse y los clics no cambian).
        try:
            from PyQt6.QtWidgets import QScroller

            QScroller.grabGesture(
                scroll.viewport(), QScroller.ScrollerGestureType.TouchGesture
            )
        except Exception:  # noqa: BLE001 — sin gesto, el scrollbar sigue ahí
            pass
        return scroll

    def _build_page_stack(self) -> QWidget:
        self.page_stack.addWidget(self._scrollable(self._build_kiosk_page()))
        self.quick_sale_widget = QuickSaleWidget(self)
        self.page_stack.addWidget(self._scrollable(self.quick_sale_widget))
        self.page_stack.addWidget(self._scrollable(self._build_catalog_page()))
        self.page_stack.addWidget(self._scrollable(self._build_guided_page()))
        self.page_stack.addWidget(self._scrollable(self._build_quote_page()))
        self.page_stack.addWidget(self._scrollable(self._build_share_page()))
        self.page_stack.addWidget(self._scrollable(self._build_tariff_page()))
        # "search" va al final del stack para no mover los indices existentes
        self.page_stack.addWidget(self._scrollable(self._build_search_page()))
        self.page_stack.addWidget(self._scrollable(self._build_conteos_page()))
        self.page_stack.addWidget(self._scrollable(self._build_libreta_page()))
        return self.page_stack

    def _build_libreta_page(self) -> QWidget:
        """Página "Libreta" — registro digital de ventas por empleada.

        Gate por gafete: cada empleada ve SUS operaciones (piezas, sin
        montos); el gafete del dueño abre la vista completa con montos.
        Reemplaza a Tarifarios en el sidebar (esa página sigue viva, oculta).
        """
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Sin banner de título: el sidebar ya dice "Libreta" y la franja
        # solo quitaba espacio vertical (pedido de Daniel 2026-09-04).

        # ── Gate: escanear gafete ────────────────────────────────────────
        # Réplica exacta del login de Venta Rápida (mismo _GATE_STYLE
        # importado de quick_sale_view: una sola fuente del look).
        from pos_uniformes.ui.views.quick_sale_view import _GATE_STYLE

        self.libreta_gate = QWidget()
        self.libreta_gate.setObjectName("gateRoot")
        self.libreta_gate.setStyleSheet(_GATE_STYLE)
        gate_outer = QVBoxLayout()
        gate_outer.setContentsMargins(40, 40, 40, 40)

        gate_card = QFrame()
        gate_card.setObjectName("gateCard")
        gate_cl = QVBoxLayout()
        gate_cl.setContentsMargins(48, 40, 48, 40)
        gate_cl.setSpacing(12)
        gate_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        gate_icon = QLabel("📒")
        gate_icon.setObjectName("gateEmoji")
        gate_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gate_cl.addWidget(gate_icon)

        gate_title = QLabel("Libreta")
        gate_title.setObjectName("gateTitle")
        gate_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gate_cl.addWidget(gate_title)

        gate_hint = QLabel("Escanea tu gafete para abrir tu libreta")
        gate_hint.setObjectName("gateHint")
        gate_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gate_cl.addWidget(gate_hint)

        gate_cl.addSpacing(8)

        self.libreta_gate_input = QLineEdit()
        self.libreta_gate_input.setObjectName("gateInput")
        self.libreta_gate_input.setPlaceholderText("Gafete...")
        self.libreta_gate_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.libreta_gate_input.returnPressed.connect(self._on_libreta_gate_scan)
        gate_cl.addWidget(self.libreta_gate_input, 0, Qt.AlignmentFlag.AlignCenter)

        self.libreta_gate_error = QLabel("")
        self.libreta_gate_error.setObjectName("gateError")
        self.libreta_gate_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.libreta_gate_error.setVisible(False)
        gate_cl.addWidget(self.libreta_gate_error)

        gate_card.setLayout(gate_cl)
        gate_outer.addStretch()
        gate_outer.addWidget(gate_card, 0, Qt.AlignmentFlag.AlignHCenter)
        gate_outer.addStretch()
        self.libreta_gate.setLayout(gate_outer)
        layout.addWidget(self.libreta_gate)

        # ── Vista (empleada o dueño) ─────────────────────────────────────
        self.libreta_view = QWidget()
        view_ly = QVBoxLayout()
        view_ly.setContentsMargins(0, 0, 0, 0)
        view_ly.setSpacing(8)

        header = QHBoxLayout()
        self.libreta_titular_label = QLabel("")
        self.libreta_titular_label.setObjectName("libretaSaludo")
        header.addWidget(self.libreta_titular_label)
        header.addStretch()
        self.libreta_hoy_button = QPushButton("Hoy")
        self.libreta_semana_button = QPushButton("Semana")
        self.libreta_sem_pasada_button = QPushButton("Sem. pasada")
        # "Mi ciclo"/"Su ciclo": desde el último pago — el respaldo del
        # banner de comisiones (la semana calendario ya no coincide con el
        # ciclo de nadie, cada quien cobra en su día).
        self.libreta_ciclo_button = QPushButton("Mi ciclo")
        self._libreta_periodo_buttons = {
            "hoy": self.libreta_hoy_button,
            "semana": self.libreta_semana_button,
            "semana_pasada": self.libreta_sem_pasada_button,
            "ciclo": self.libreta_ciclo_button,
        }
        for periodo_key, button in self._libreta_periodo_buttons.items():
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.clicked.connect(
                lambda _checked=False, k=periodo_key: self._set_libreta_periodo(k)
            )
            header.addWidget(button)
        # Menos métricas (pedido de Daniel 2026-09-04): quedan Hoy y Ciclo.
        # Semana/Sem. pasada eran de cuando el pago iba por semana calendario;
        # el ciclo las sustituye. Código vivo: setVisible(True) las revive.
        self.libreta_semana_button.setVisible(False)
        self.libreta_sem_pasada_button.setVisible(False)
        self.libreta_hoy_button.setChecked(True)
        self.libreta_refresh_button = QPushButton("Actualizar")
        self.libreta_refresh_button.setAutoDefault(False)
        self.libreta_refresh_button.clicked.connect(self._refresh_libreta_view)
        header.addWidget(self.libreta_refresh_button)
        self.libreta_calendario_button = QPushButton("📅 Calendario")
        self.libreta_calendario_button.setAutoDefault(False)
        self.libreta_calendario_button.clicked.connect(self._abrir_calendario_libreta)
        header.addWidget(self.libreta_calendario_button)
        self.libreta_salir_button = QPushButton("Salir")
        self.libreta_salir_button.setAutoDefault(False)
        self.libreta_salir_button.clicked.connect(self._libreta_logout)
        header.addWidget(self.libreta_salir_button)
        view_ly.addLayout(header)

        # Tarjetas de métricas: números grandes y amigables, sin tecnicismos.
        # La primera (destacada) cambia según quién mira: comisiones para la
        # empleada, EN CAJA para el dueño.
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._libreta_cards: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []
        for index in range(4):
            card = QFrame()
            card.setObjectName("libretaCardDestacada" if index == 0 else "libretaCard")
            card_ly = QVBoxLayout()
            card_ly.setContentsMargins(16, 12, 16, 12)
            card_ly.setSpacing(2)
            titulo_card = QLabel("")
            titulo_card.setObjectName(
                "libretaCardTituloClaro" if index == 0 else "libretaCardTitulo"
            )
            valor_card = QLabel("—")
            valor_card.setObjectName(
                "libretaCardValorClaro" if index == 0 else "libretaCardValor"
            )
            sub_card = QLabel("")
            sub_card.setObjectName(
                "libretaCardSubClaro" if index == 0 else "libretaCardSub"
            )
            sub_card.setVisible(False)
            card_ly.addWidget(titulo_card)
            card_ly.addWidget(valor_card)
            card_ly.addWidget(sub_card)
            card.setLayout(card_ly)
            cards_row.addWidget(card, 1)
            self._libreta_cards.append((card, titulo_card, valor_card, sub_card))
        view_ly.addLayout(cards_row)

        # Banner del ciclo de pago (empleada): comisiones acumuladas desde su
        # último pago + cuándo le toca el siguiente. Se llena al refrescar.
        self.libreta_ciclo_banner = QLabel("")
        self.libreta_ciclo_banner.setObjectName("libretaCicloBanner")
        self.libreta_ciclo_banner.setWordWrap(True)
        self.libreta_ciclo_banner.setStyleSheet(
            "background: #a84f2d; color: #ffffff; border-radius: 10px;"
            "padding: 10px 14px; font-size: 15px; font-weight: 700;"
        )
        self.libreta_ciclo_banner.setVisible(False)
        view_ly.addWidget(self.libreta_ciclo_banner)

        # Barra del dueño: lo de todos los días (imprimir corte) a la vista;
        # lo ocasional (rango de fechas, meta semanal) plegado bajo "Más
        # opciones". Las correcciones de un movimiento (reimprimir, cambiar
        # pago, borrar) viven junto a la tabla de movimientos, no aquí.
        self.libreta_owner_bar = QWidget()
        owner_bar_ly = QVBoxLayout()
        owner_bar_ly.setContentsMargins(0, 0, 0, 0)
        owner_bar_ly.setSpacing(6)
        owner_row = QHBoxLayout()
        owner_row.setSpacing(8)
        self.libreta_print_button = QPushButton("🧾 Imprimir corte")
        self.libreta_print_button.setObjectName("primaryButton")
        self.libreta_print_button.setAutoDefault(False)
        self.libreta_print_button.setMinimumHeight(44)
        self.libreta_print_button.clicked.connect(self._imprimir_corte_libreta)
        owner_row.addWidget(self.libreta_print_button)
        owner_row.addStretch()
        self.libreta_opciones_button = QPushButton("⚙ Más opciones")
        self.libreta_opciones_button.setObjectName("secondaryButton")
        self.libreta_opciones_button.setCheckable(True)
        self.libreta_opciones_button.setAutoDefault(False)
        self.libreta_opciones_button.setMinimumHeight(44)
        self.libreta_opciones_button.toggled.connect(
            lambda on: self.libreta_opciones_panel.setVisible(on)
        )
        owner_row.addWidget(self.libreta_opciones_button)
        owner_bar_ly.addLayout(owner_row)

        self.libreta_opciones_panel = QFrame()
        self.libreta_opciones_panel.setObjectName("libretaCard")
        opciones_ly = QHBoxLayout()
        opciones_ly.setContentsMargins(14, 10, 14, 10)
        opciones_ly.setSpacing(8)
        # Rango libre de fechas (calendario): "cuántas comisiones hizo Ana
        # del día X al día Y" — se combina con el filtro por empleada.
        opciones_ly.addWidget(QLabel("Ver del:"))
        self.libreta_rango_desde = QDateEdit(QDate.currentDate().addDays(-7))
        self.libreta_rango_hasta = QDateEdit(QDate.currentDate())
        for date_edit in (self.libreta_rango_desde, self.libreta_rango_hasta):
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("dd/MM/yyyy")
        opciones_ly.addWidget(self.libreta_rango_desde)
        opciones_ly.addWidget(QLabel("al:"))
        opciones_ly.addWidget(self.libreta_rango_hasta)
        self.libreta_rango_button = QPushButton("Ver rango")
        self.libreta_rango_button.setCheckable(True)
        self.libreta_rango_button.setAutoDefault(False)
        self.libreta_rango_button.clicked.connect(
            lambda: self._set_libreta_periodo("rango")
        )
        opciones_ly.addWidget(self.libreta_rango_button)
        opciones_ly.addStretch()
        opciones_ly.addWidget(QLabel("Meta semanal (comisiones):"))
        self.libreta_meta_spin = QSpinBox()
        self.libreta_meta_spin.setRange(0, 9999)
        self.libreta_meta_spin.setSpecialValueText("Sin meta")
        opciones_ly.addWidget(self.libreta_meta_spin)
        self.libreta_meta_save_button = QPushButton("Guardar meta")
        self.libreta_meta_save_button.setAutoDefault(False)
        self.libreta_meta_save_button.clicked.connect(self._guardar_meta_libreta)
        opciones_ly.addWidget(self.libreta_meta_save_button)
        self.libreta_opciones_panel.setLayout(opciones_ly)
        self.libreta_opciones_panel.setVisible(False)
        owner_bar_ly.addWidget(self.libreta_opciones_panel)
        self.libreta_owner_bar.setLayout(owner_bar_ly)
        view_ly.addWidget(self.libreta_owner_bar)

        # Tarjeta de la meta semanal de la empleada, con barra de progreso
        self.libreta_meta_bar = QFrame()
        self.libreta_meta_bar.setObjectName("libretaMetaCard")
        meta_bar_ly = QHBoxLayout()
        meta_bar_ly.setContentsMargins(16, 12, 16, 12)
        meta_bar_ly.setSpacing(12)
        self.libreta_meta_label = QLabel("")
        self.libreta_meta_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        meta_bar_ly.addWidget(self.libreta_meta_label)
        self.libreta_meta_progress = QProgressBar()
        self.libreta_meta_progress.setObjectName("libretaMetaProgress")
        self.libreta_meta_progress.setTextVisible(True)
        meta_bar_ly.addWidget(self.libreta_meta_progress, 1)
        self.libreta_meta_bar.setLayout(meta_bar_ly)
        view_ly.addWidget(self.libreta_meta_bar)

        self.libreta_resumen_label = QLabel("")
        self.libreta_resumen_label.setStyleSheet("font-size: 13px; color: #555;")
        view_ly.addWidget(self.libreta_resumen_label)

        self.libreta_status_label = QLabel("")
        self.libreta_status_label.setStyleSheet("font-size: 12px; color: #b9770e;")
        self.libreta_status_label.setVisible(False)
        view_ly.addWidget(self.libreta_status_label)

        # Registros locales que aún no suben al servidor
        self.libreta_pendientes_label = QLabel("")
        self.libreta_pendientes_label.setStyleSheet("font-size: 12px; color: #b9770e;")
        self.libreta_pendientes_label.setVisible(False)
        view_ly.addWidget(self.libreta_pendientes_label)

        # Lista amigable de la empleada: sus movimientos en lenguaje simple,
        # sin columnas técnicas ni dinero.
        self.libreta_emp_list = QListWidget()
        self.libreta_emp_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.libreta_emp_list.setObjectName("libretaLista")
        self.libreta_emp_list.itemDoubleClicked.connect(
            lambda item: self._mostrar_detalle_libreta(self.libreta_emp_list.row(item))
        )
        view_ly.addWidget(self.libreta_emp_list, 1)

        # ── Panel del dueño: corte por día, ranking de empleadas y detalle ──
        self.libreta_owner_panel = QWidget()
        owner_panel_ly = QVBoxLayout()
        owner_panel_ly.setContentsMargins(0, 0, 0, 0)
        owner_panel_ly.setSpacing(8)

        def _seccion(texto: str) -> QLabel:
            etiqueta = QLabel(texto)
            etiqueta.setObjectName("libretaSeccion")
            return etiqueta

        # Desglose por día: solo tiene sentido en periodos de varios días
        # (ciclo, rango). En "Hoy" repetiría las tarjetas → se oculta.
        self.libreta_daily_seccion = _seccion("POR DÍA")
        owner_panel_ly.addWidget(self.libreta_daily_seccion)
        self.libreta_daily_table = QTableWidget(0, 6)
        self.libreta_daily_table.setObjectName("libretaTabla")
        self.libreta_daily_table.setHorizontalHeaderLabels(
            ["Día", "En el cajón $", "Vendido $", "Neto $", "Abonos $", "Operaciones"]
        )
        self.libreta_daily_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.libreta_daily_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.libreta_daily_table.verticalHeader().setVisible(False)
        self.libreta_daily_table.setAlternatingRowColors(True)
        # Crece con sus días y scrollea la página (sin scroll interno).
        self.libreta_daily_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        owner_panel_ly.addWidget(self.libreta_daily_table)

        owner_panel_ly.addWidget(_seccion("EQUIPO  ·  toca un nombre para ver solo sus movimientos"))
        self.libreta_ranking_list = QListWidget()
        self.libreta_ranking_list.setObjectName("libretaLista")
        self.libreta_ranking_list.setMaximumHeight(170)
        self.libreta_ranking_list.itemClicked.connect(self._on_libreta_ranking_click)
        owner_panel_ly.addWidget(self.libreta_ranking_list)

        owner_panel_ly.addWidget(_seccion("MOVIMIENTOS"))
        # Filtros rápidos por tipo (para cuadrar tarjeta vs voucher, etc.)
        filtros_ly = QHBoxLayout()
        filtros_ly.setSpacing(6)
        self._libreta_tipo_buttons: dict[str, QPushButton] = {}
        for filtro_key, filtro_label in (
            ("todo", "Todo"),
            ("venta", "Ventas"),
            ("apartado", "Apartados"),
            ("abono", "Abonos"),
            ("tarjeta", "💳 Tarjeta"),
        ):
            filtro_btn = QPushButton(filtro_label)
            filtro_btn.setCheckable(True)
            filtro_btn.setAutoDefault(False)
            filtro_btn.clicked.connect(
                lambda _checked=False, k=filtro_key: self._set_libreta_tipo_filtro(k)
            )
            self._libreta_tipo_buttons[filtro_key] = filtro_btn
            filtros_ly.addWidget(filtro_btn)
        self._libreta_tipo_buttons["todo"].setChecked(True)
        self.libreta_filtro_emp_label = QLabel("")
        self.libreta_filtro_emp_label.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #73341c;"
        )
        self.libreta_filtro_emp_label.setVisible(False)
        filtros_ly.addWidget(self.libreta_filtro_emp_label)
        filtros_ly.addStretch()
        owner_panel_ly.addLayout(filtros_ly)
        # Correcciones sobre UN movimiento (se elige en la tabla). Solo
        # dueño: reimprimir NO registra otra venta; cambiar pago recalcula
        # el neto; borrar deja el registro fuera del corte.
        acciones_ly = QHBoxLayout()
        acciones_ly.setSpacing(6)
        acciones_label = QLabel("Con el movimiento seleccionado:")
        acciones_label.setStyleSheet("font-size: 12px; color: #8a8177;")
        acciones_ly.addWidget(acciones_label)
        self.libreta_reprint_button = QPushButton("🖨 Reimprimir ticket")
        self.libreta_reprint_button.clicked.connect(self._reimprimir_ticket_libreta)
        self.libreta_pago_button = QPushButton("💳 Cambiar pago")
        self.libreta_pago_button.clicked.connect(self._cambiar_pago_libreta)
        self.libreta_delete_button = QPushButton("🗑 Borrar")
        self.libreta_delete_button.clicked.connect(self._borrar_registro_libreta)
        for accion_btn in (
            self.libreta_reprint_button,
            self.libreta_pago_button,
            self.libreta_delete_button,
        ):
            accion_btn.setObjectName("secondaryButton")
            accion_btn.setAutoDefault(False)
            acciones_ly.addWidget(accion_btn)
        acciones_ly.addStretch()
        owner_panel_ly.addLayout(acciones_ly)
        self.libreta_table = QTableWidget(0, 7)
        self.libreta_table.setObjectName("libretaTabla")
        self.libreta_table.setHorizontalHeaderLabels(
            ["Fecha", "Hora", "Tipo", "Piezas", "Comisiones", "Prendas", "Monto"]
        )
        self.libreta_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.libreta_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # En táctil, tabla-con-scroll-dentro-de-página-con-scroll es una
        # trampa: la tabla crece con sus filas y la página entera scrollea.
        self.libreta_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.libreta_table.verticalHeader().setVisible(False)
        self.libreta_table.setAlternatingRowColors(True)
        self.libreta_table.cellDoubleClicked.connect(
            lambda fila, _col: self._mostrar_detalle_libreta(fila)
        )
        owner_panel_ly.addWidget(self.libreta_table, 1)
        # Paginación de movimientos: 25 por página (días grandes no hacen
        # la página kilométrica). Botones tamaño dedo.
        self.libreta_pag_prev = QPushButton("◀  Anteriores")
        self.libreta_pag_next = QPushButton("Siguientes  ▶")
        self.libreta_pag_label = QLabel("")
        self.libreta_pag_label.setStyleSheet("font-weight: 700; color: #5f594f;")
        for btn in (self.libreta_pag_prev, self.libreta_pag_next):
            btn.setAutoDefault(False)
            btn.setMinimumHeight(44)
        self.libreta_pag_prev.clicked.connect(lambda: self._cambiar_pagina_libreta(-1))
        self.libreta_pag_next.clicked.connect(lambda: self._cambiar_pagina_libreta(1))
        self.libreta_pag_bar = QWidget()
        pag_ly = QHBoxLayout()
        pag_ly.setContentsMargins(0, 4, 0, 0)
        pag_ly.setSpacing(10)
        pag_ly.addWidget(self.libreta_pag_prev)
        pag_ly.addStretch()
        pag_ly.addWidget(self.libreta_pag_label)
        pag_ly.addStretch()
        pag_ly.addWidget(self.libreta_pag_next)
        self.libreta_pag_bar.setLayout(pag_ly)
        self.libreta_pag_bar.setVisible(False)
        owner_panel_ly.addWidget(self.libreta_pag_bar)

        self.libreta_owner_panel.setLayout(owner_panel_ly)
        view_ly.addWidget(self.libreta_owner_panel, 1)

        self.libreta_view.setLayout(view_ly)
        self.libreta_view.setVisible(False)
        layout.addWidget(self.libreta_view, 1)

        self._libreta_code: str | None = None
        self._libreta_is_owner = False
        # Periodo: "hoy" | "semana" | "semana_pasada" | "rango"
        self._libreta_periodo = "hoy"
        self._libreta_tipo_filtro = "todo"
        self._libreta_emp_filtro: str | None = None
        self._libreta_ranking_codes: list[str] = []
        # Últimos agregados pintados (para el ticket de corte)
        self._libreta_last_cortes: list = []
        self._libreta_last_por_empleada: list = []

        page.setLayout(layout)
        return page

    def _on_libreta_gate_scan(self) -> None:
        code = QuickSaleWidget._clean_scanned_code(self.libreta_gate_input.text())
        self.libreta_gate_input.clear()
        if not code:
            return
        from pos_uniformes.services.calendario_empleadas_service import ENCARGADO_CODE

        if code == ENCARGADO_CODE:
            # Gafete del encargado: directo al calendario en su modo (marca
            # faltas/descansos, sin dinero) — la Libreta no se abre.
            self._abrir_calendario_encargado()
            return
        # Validar el gafete (mismo criterio que el gate de venta rápida):
        # un código inventado NO abre la Libreta. Offline o con la DB caída
        # se exige al menos el formato VEND-N para no dejar fuera al equipo.
        if not self._gafete_libreta_valido(code):
            self.libreta_gate_error.setText(
                f"Gafete '{code}' no encontrado o inactivo."
            )
            self.libreta_gate_error.setVisible(True)
            QTimer.singleShot(0, self.libreta_gate_input.setFocus)
            return
        self._libreta_code = code
        self._libreta_is_owner = code == QuickSaleWidget._OWNER_CODE
        self._libreta_periodo = "hoy"
        self._libreta_tipo_filtro = "todo"
        self._libreta_emp_filtro = None
        self._libreta_pagina = 0
        self._sync_libreta_filtros()
        self.libreta_gate_error.setVisible(False)
        self.libreta_gate.setVisible(False)
        self.libreta_view.setVisible(True)
        # La columna de dinero, el corte diario, el resumen por empleada y
        # los controles de corte/meta son solo del dueño; la barra de
        # progreso de meta es de la empleada.
        self.libreta_owner_panel.setVisible(self._libreta_is_owner)
        self.libreta_owner_bar.setVisible(self._libreta_is_owner)
        self.libreta_meta_bar.setVisible(False)  # se muestra al refrescar si hay meta
        # La empleada ve su lista amigable; el panel técnico es del dueño.
        self.libreta_emp_list.setVisible(not self._libreta_is_owner)
        self.libreta_table.setColumnHidden(6, not self._libreta_is_owner)
        if self._libreta_is_owner:
            from pos_uniformes.services.libreta_meta_service import load_meta_semanal

            self.libreta_meta_spin.setValue(load_meta_semanal())
        self.libreta_titular_label.setText(
            "📒 Libreta de la tienda"
            if self._libreta_is_owner
            else f"Hola, {code} 👋"
        )
        self.libreta_ciclo_button.setText(
            "Su ciclo" if self._libreta_is_owner else "Mi ciclo"
        )
        self._refresh_libreta_view()

    def _gafete_libreta_valido(self, code: str) -> bool:
        if getattr(self, "offline_mode", False):
            return code.startswith("VEND-")
        try:
            from sqlalchemy import select as _select

            from pos_uniformes.database.models import Empleada

            with get_session() as session:
                emp = session.scalar(
                    _select(Empleada).where(
                        Empleada.codigo == code, Empleada.activo.is_(True)
                    )
                )
            return emp is not None
        except Exception:  # noqa: BLE001 — DB caída ≠ gafete falso
            logger.exception("Libreta: error de DB validando gafete '%s'", code)
            return code.startswith("VEND-")

    def _libreta_logout(self) -> None:
        self._libreta_code = None
        self._libreta_is_owner = False
        self.libreta_view.setVisible(False)
        self.libreta_gate.setVisible(True)
        QTimer.singleShot(0, self.libreta_gate_input.setFocus)

    def _texto_ciclo_libreta(self, session) -> str | None:
        """Banner de la empleada: comisiones desde su último pago + resumen
        de su próximo pago/descanso. None si aún no tiene ciclo iniciado."""
        try:
            from pos_uniformes.services.calendario_empleadas_service import (
                cargar_horario,
                comisiones_desde_ultimo_pago,
                resumen_empleada,
            )

            horario = cargar_horario(session, self._libreta_code)
            if horario.fecha_ultimo_pago is None and horario.descanso_weekday is None:
                return None  # sin ciclo configurado: no ensuciar la vista
            comisiones = comisiones_desde_ultimo_pago(
                session, self._libreta_code, horario
            )
            from datetime import date as _date

            partes = [f"⭐ Comisiones desde tu último pago: {comisiones}"]
            resumen = resumen_empleada(horario, _date.today())
            if resumen and "Sin horario" not in resumen:
                partes.append(resumen)
            return "   ·   ".join(partes)
        except Exception:  # noqa: BLE001
            logger.exception("Libreta: fallo el banner del ciclo")
            return None

    def _abrir_calendario_encargado(self) -> None:
        # Modo ultra-simple para León: tres preguntas con botones grandes
        # (¿quién? → ¿qué pasó? → ¿cuándo?), sin combos ni configuración.
        from pos_uniformes.ui.dialogs.calendario_empleadas_dialog import (
            CalendarioEncargadoDialog,
        )

        dialog = CalendarioEncargadoDialog(self)
        dialog.exec()
        QTimer.singleShot(0, self.libreta_gate_input.setFocus)

    def _abrir_calendario_libreta(self) -> None:
        """Calendario de descansos/faltas/pagos; la empleada ve el suyo y el
        dueño gestiona el de todas."""
        if not self._libreta_code:
            return
        from pos_uniformes.ui.dialogs.calendario_empleadas_dialog import (
            CalendarioEmpleadasDialog,
        )

        dialog = CalendarioEmpleadasDialog(
            self,
            employee_code=self._libreta_code,
            employee_name=self._libreta_code,
            is_owner=self._libreta_is_owner,
        )
        dialog.exec()

    def _set_libreta_periodo(self, periodo: str) -> None:
        self._libreta_pagina = 0
        if (
            periodo == "ciclo"
            and self._libreta_is_owner
            and not self._libreta_emp_filtro
        ):
            # El ciclo es POR empleada: el dueño primero elige a quién.
            QMessageBox.information(
                self,
                "Elige empleada",
                "Primero elige a la empleada (clic en su nombre en el ranking)\n"
                "y luego 'Su ciclo' te muestra lo que va desde su último pago.",
            )
            self._sync_libreta_filtros()  # el botón no se queda prendido
            return
        self._libreta_periodo = periodo
        self._sync_libreta_filtros()
        self._refresh_libreta_view()

    def _set_libreta_tipo_filtro(self, filtro: str) -> None:
        self._libreta_pagina = 0
        self._libreta_tipo_filtro = filtro
        self._sync_libreta_filtros()
        self._refresh_libreta_view()

    def _on_libreta_ranking_click(self, item) -> None:
        """Clic en una empleada del ranking = filtrar sus movimientos;
        clic en la misma otra vez = quitar el filtro."""
        idx = self.libreta_ranking_list.row(item)
        if idx < 0 or idx >= len(self._libreta_ranking_codes):
            return
        code = self._libreta_ranking_codes[idx]
        self._libreta_emp_filtro = None if self._libreta_emp_filtro == code else code
        self._libreta_pagina = 0
        if self._libreta_emp_filtro is None and self._libreta_periodo == "ciclo":
            self._libreta_periodo = "hoy"  # el ciclo era DE esa empleada
        self._sync_libreta_filtros()
        self._refresh_libreta_view()

    def _sync_libreta_filtros(self) -> None:
        """Refleja periodo/filtros en los botones y etiquetas."""
        for key, button in self._libreta_periodo_buttons.items():
            button.setChecked(key == self._libreta_periodo)
        self.libreta_rango_button.setChecked(self._libreta_periodo == "rango")
        if self._libreta_periodo == "rango":
            # El rango vive plegado bajo "Más opciones": si está activo,
            # que se vea de dónde sale.
            self.libreta_opciones_button.setChecked(True)
        for key, button in self._libreta_tipo_buttons.items():
            button.setChecked(key == self._libreta_tipo_filtro)
        if self._libreta_emp_filtro:
            self.libreta_filtro_emp_label.setText(
                f"Filtrando: {self._libreta_emp_filtro} (clic en el ranking para quitar)"
            )
            self.libreta_filtro_emp_label.setVisible(True)
        else:
            self.libreta_filtro_emp_label.setVisible(False)

    def _libreta_ventana_actual(self):
        """(desde, hasta) según el periodo elegido."""
        from pos_uniformes.services.libreta_service import (
            ventana_rango,
            ventana_semana,
            ventana_semana_anterior,
        )

        if self._libreta_periodo == "ciclo":
            return self._ventana_ciclo_actual()
        if self._libreta_periodo == "semana_pasada":
            return ventana_semana_anterior()
        if self._libreta_periodo == "rango":
            return ventana_rango(
                self.libreta_rango_desde.date().toPyDate(),
                self.libreta_rango_hasta.date().toPyDate(),
            )
        # "hoy" y "semana" comparten ventana de semana (hoy se filtra en
        # memoria; la meta semanal necesita la semana completa).
        return ventana_semana()

    def _ventana_ciclo_actual(self):
        """Ventana "desde el último pago" de la empleada en contexto:
        la propia en modo empleada; la filtrada en el ranking, para el dueño."""
        from pos_uniformes.services.libreta_service import ventana_ciclo, ventana_semana

        code = (
            self._libreta_emp_filtro if self._libreta_is_owner else self._libreta_code
        )
        if not code:
            return ventana_semana()
        try:
            from pos_uniformes.services.calendario_empleadas_service import (
                cargar_horario,
            )

            with get_session() as session:
                horario = cargar_horario(session, code)
            return ventana_ciclo(horario.fecha_ultimo_pago)
        except Exception:  # noqa: BLE001 — sin conexión: mejor semana que nada
            logger.exception("Libreta: no se pudo cargar el ciclo de %s", code)
            return ventana_semana()

    def _libreta_periodo_texto(self) -> str:
        if self._libreta_periodo == "ciclo":
            return (
                f"desde el último pago de {self._libreta_emp_filtro}"
                if self._libreta_is_owner
                else "desde tu último pago"
            )
        if self._libreta_periodo == "semana":
            return "esta semana"
        if self._libreta_periodo == "semana_pasada":
            return "la semana pasada"
        if self._libreta_periodo == "rango":
            desde = self.libreta_rango_desde.date().toPyDate().strftime("%d/%m")
            hasta = self.libreta_rango_hasta.date().toPyDate().strftime("%d/%m")
            return f"del {desde} al {hasta}"
        return "hoy"

    def _refresh_libreta_view(self) -> None:
        if not self._libreta_code:
            return
        from pos_uniformes.services import libreta_local_queue_service as libreta_cola
        from pos_uniformes.services.libreta_service import (
            filtrar_de_hoy,
            filtrar_operaciones,
            listar_operaciones,
        )
        from pos_uniformes.services.satellite_startup_service import probe_database_host

        # La ventana depende del periodo; "hoy" y "semana" comparten la de la
        # semana (hoy se filtra en memoria; la meta la necesita completa).
        desde, hasta = self._libreta_ventana_actual()
        employee_filter = None if self._libreta_is_owner else self._libreta_code

        week_rows: list = []
        fuente_db = False
        ciclo_texto: str | None = None
        if probe_database_host(0.5):
            try:
                with get_session() as session:
                    # Fold: lo pendiente local se sube antes de consultar.
                    try:
                        libreta_cola.drenar_pendientes(session)
                    except Exception:  # noqa: BLE001
                        session.rollback()
                    try:
                        libreta_cola.drenar_cortes(session)
                    except Exception:  # noqa: BLE001
                        session.rollback()
                    week_rows = listar_operaciones(
                        session, desde=desde, hasta=hasta, employee_code=employee_filter
                    )
                    if not self._libreta_is_owner:
                        ciclo_texto = self._texto_ciclo_libreta(session)
                fuente_db = True
            except Exception:  # noqa: BLE001
                logger.exception("Libreta: fallo la consulta a la base")
        self.libreta_ciclo_banner.setVisible(bool(ciclo_texto))
        if ciclo_texto:
            self.libreta_ciclo_banner.setText(ciclo_texto)

        if not fuente_db:
            week_rows = self._libreta_rows_locales(desde, hasta, employee_filter)
        self.libreta_status_label.setVisible(not fuente_db)
        self.libreta_status_label.setText(
            "Sin conexion con la PC principal: mostrando solo lo registrado en esta terminal."
        )

        pendientes = len(libreta_cola.pendientes())
        self.libreta_pendientes_label.setVisible(pendientes > 0)
        self.libreta_pendientes_label.setText(
            f"{pendientes} registro(s) de esta terminal aun sin subir al servidor."
        )

        # La meta semanal solo aplica viendo la semana en curso.
        if self._libreta_periodo in ("hoy", "semana"):
            self._actualizar_meta_libreta(week_rows)
        else:
            self.libreta_meta_bar.setVisible(False)

        rows = filtrar_de_hoy(week_rows) if self._libreta_periodo == "hoy" else week_rows

        # Filtros del dueño: tipo/tarjeta afectan todo; el ranking se pinta
        # SIN el filtro de empleada (funciona como selector).
        ranking_rows = rows
        if self._libreta_is_owner:
            ranking_rows = filtrar_operaciones(
                rows,
                tipo=(
                    self._libreta_tipo_filtro
                    if self._libreta_tipo_filtro in ("venta", "apartado", "abono")
                    else None
                ),
                solo_tarjeta=self._libreta_tipo_filtro == "tarjeta",
            )
            rows = filtrar_operaciones(
                ranking_rows, employee_code=self._libreta_emp_filtro
            )
        self._pintar_libreta(rows, ranking_rows=ranking_rows)

    def _actualizar_meta_libreta(self, week_rows: list) -> None:
        """Barra de progreso de la empleada contra la meta semanal."""
        if self._libreta_is_owner:
            return
        from pos_uniformes.services.libreta_meta_service import load_meta_semanal

        meta = load_meta_semanal()
        if meta <= 0:
            self.libreta_meta_bar.setVisible(False)
            return
        comisiones_semana = sum(int(getattr(r, "comisiones", 0) or 0) for r in week_rows)
        self.libreta_meta_progress.setRange(0, meta)
        self.libreta_meta_progress.setValue(min(comisiones_semana, meta))
        self.libreta_meta_progress.setFormat(f"{comisiones_semana} / {meta}")
        if comisiones_semana >= meta:
            self.libreta_meta_label.setText("¡Meta de la semana cumplida! 🎉")
        else:
            faltan = meta - comisiones_semana
            self.libreta_meta_label.setText(f"🎯 Meta de la semana — te faltan {faltan}")
        self.libreta_meta_bar.setVisible(True)

    def _guardar_meta_libreta(self) -> None:
        from pos_uniformes.services.libreta_meta_service import save_meta_semanal

        save_meta_semanal(int(self.libreta_meta_spin.value()))
        self._set_status("Meta semanal de la Libreta guardada.")

    def _mostrar_detalle_libreta(self, idx: int) -> None:
        """Doble clic en una operación: todas sus líneas completas.

        Con precios solo en la vista del dueño (privacidad de empleadas)."""
        rows = list(getattr(self, "_libreta_rows_pintadas", []) or [])
        if idx < 0 or idx >= len(rows):
            return
        row = rows[idx]
        from pos_uniformes.services.libreta_service import lineas_detalle

        con_precios = bool(self._libreta_is_owner)
        local_dt = (
            row.created_at.astimezone() if row.created_at.tzinfo else row.created_at
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de la operación")
        dlg.setMinimumWidth(520)
        ly = QVBoxLayout()
        ly.setContentsMargins(20, 16, 20, 16)
        ly.setSpacing(10)

        encabezado = (
            f"{str(row.tipo).capitalize()} · {local_dt.strftime('%d/%m/%Y %H:%M')}"
        )
        nombre = row.employee_name or row.employee_code
        encabezado += f" · {nombre}"
        if getattr(row, "pago_tarjeta", False):
            encabezado += " · 💳 tarjeta"
        titulo = QLabel(encabezado)
        titulo.setStyleSheet("font-size: 14px; font-weight: 700;")
        ly.addWidget(titulo)

        cliente = getattr(row, "cliente", None)
        if cliente:
            ly.addWidget(QLabel(f"Cliente: {cliente}"))

        filas = lineas_detalle(list(row.detalle or []), con_precios=con_precios)
        if filas:
            headers = ["Producto", "Talla", "Cant."] + (
                ["Precio", "Subtotal"] if con_precios else []
            )
            tabla = QTableWidget(len(filas), len(headers))
            tabla.setObjectName("libretaTabla")
            tabla.setHorizontalHeaderLabels(headers)
            tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tabla.verticalHeader().setVisible(False)
            for i, fila in enumerate(filas):
                for j, valor in enumerate(fila):
                    tabla.setItem(i, j, QTableWidgetItem(valor))
            ly.addWidget(tabla, 1)

        resumen = f"{int(row.piezas or 0)} pieza(s) · {int(getattr(row, 'comisiones', 0) or 0)} comision(es)"
        if con_precios:
            resumen += f" · Total: ${Decimal(str(row.monto_total or 0)):,.2f}"
            neto = Decimal(str(getattr(row, "monto_neto", None) or row.monto_total or 0))
            if getattr(row, "pago_tarjeta", False):
                resumen += f" · Neto: ${neto:,.2f}"
        pie = QLabel(resumen)
        pie.setStyleSheet("font-size: 13px; font-weight: 700; color: #73341c;")
        ly.addWidget(pie)

        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(dlg.accept)
        ly.addWidget(cerrar)
        dlg.setLayout(ly)
        dlg.exec()

    def _cambiar_pago_libreta(self) -> None:
        """Alterna tarjeta/efectivo del registro seleccionado (solo dueño)
        y recalcula el neto. Para cuando la empleada olvidó marcarlo."""
        if not self._libreta_is_owner:
            return
        rows = list(getattr(self, "_libreta_rows_pintadas", []) or [])
        idx = self.libreta_table.currentRow()
        if idx < 0 or idx >= len(rows):
            QMessageBox.information(
                self, "Sin selección",
                "Selecciona en MOVIMIENTOS el registro cuyo pago quieres corregir.",
            )
            return
        row = rows[idx]
        entry_id = getattr(row, "id", None)
        if entry_id is None:
            QMessageBox.information(
                self, "Aún sin sincronizar",
                "Ese registro todavía no sube al servidor; presiona "
                "Actualizar en un momento e inténtalo de nuevo.",
            )
            return
        era_tarjeta = bool(getattr(row, "pago_tarjeta", False))
        nuevo_modo = "EFECTIVO" if era_tarjeta else "TARJETA"
        confirmacion = QMessageBox.question(
            self,
            "Cambiar forma de pago",
            f"Este registro está como {'TARJETA' if era_tarjeta else 'EFECTIVO'}.\n"
            f"¿Cambiarlo a {nuevo_modo}?\n\n"
            "El neto se recalcula solo (4.5% de terminal si es tarjeta).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        from pos_uniformes.services.libreta_service import cambiar_pago_tarjeta

        try:
            with get_session() as session:
                cambiar_pago_tarjeta(session, int(entry_id), not era_tarjeta)
        except Exception:  # noqa: BLE001
            logger.exception("Libreta: no se pudo cambiar la forma de pago")
            QMessageBox.warning(self, "Sin conexión", "No se pudo guardar. Intenta de nuevo.")
            return
        self._set_status(f"Pago cambiado a {nuevo_modo}.")
        self._refresh_libreta_view()

    def _reimprimir_ticket_libreta(self) -> None:
        """Reimprime el ticket del registro seleccionado en MOVIMIENTOS
        (solo dueño). Es una copia del ticket original — con la fecha de
        entonces y la leyenda REIMPRESION — y NO registra nada en la Libreta."""
        if not self._libreta_is_owner:
            return
        rows = list(getattr(self, "_libreta_rows_pintadas", []) or [])
        idx = self.libreta_table.currentRow()
        if idx < 0 or idx >= len(rows):
            QMessageBox.information(
                self, "Sin selección",
                "Selecciona en MOVIMIENTOS el ticket que quieres reimprimir.",
            )
            return
        row = rows[idx]
        texto = self.quick_sale_widget.build_reprint_ticket(
            tipo=str(row.tipo),
            detalle=list(row.detalle or []),
            cliente=getattr(row, "cliente", None),
            employee_name=str(row.employee_name or row.employee_code or ""),
            descuento_empleada=bool(getattr(row, "descuento_empleada", False)),
            created_at=row.created_at,
        )
        if not texto:
            QMessageBox.information(
                self, "Sin ticket", "Los abonos no generan ticket para reimprimir."
            )
            return
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        # Sin on_printed: reimprimir jamás vuelve a registrar la venta.
        route_tickets(self, "Reimpresión de ticket", [texto])

    def _borrar_registro_libreta(self) -> None:
        """Borra el registro seleccionado en MOVIMIENTOS (solo dueño).

        Para corregir cuando se imprimió por error o la venta no se
        concretó; con confirmación y refresco inmediato del corte."""
        if not self._libreta_is_owner:
            return
        rows = list(getattr(self, "_libreta_rows_pintadas", []) or [])
        idx = self.libreta_table.currentRow()
        if idx < 0 or idx >= len(rows):
            QMessageBox.information(
                self, "Sin selección",
                "Selecciona en MOVIMIENTOS el registro que quieres borrar.",
            )
            return
        row = rows[idx]
        entry_id = getattr(row, "id", None)
        if entry_id is None:
            QMessageBox.information(
                self, "Aún sin sincronizar",
                "Ese registro todavía no sube al servidor; presiona "
                "Actualizar en un momento e inténtalo de nuevo.",
            )
            return
        local_dt = (
            row.created_at.astimezone() if row.created_at.tzinfo else row.created_at
        )
        detalle = (
            f"{local_dt.strftime('%d/%m %H:%M')} · {str(row.tipo).capitalize()} · "
            f"{row.employee_name or row.employee_code} · "
            f"${Decimal(str(row.monto_total or 0)):,.2f}"
        )
        confirmacion = QMessageBox.question(
            self,
            "Borrar registro",
            f"¿Borrar este registro de la Libreta?\n\n{detalle}\n\n"
            "Esto no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        from pos_uniformes.services.libreta_service import eliminar_operacion

        try:
            with get_session() as session:
                existia = eliminar_operacion(session, int(entry_id))
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo borrar", str(exc))
            return
        self._set_status(
            "Registro borrado de la Libreta." if existia else "El registro ya no existía."
        )
        self._refresh_libreta_view()

    def _imprimir_corte_libreta(self) -> None:
        """Imprime el corte del periodo visible (solo vista dueño)."""
        if not self._libreta_is_owner:
            return
        from pos_uniformes.ui.helpers.libreta_corte_ticket_helper import (
            build_corte_ticket_text,
        )
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        cortes = list(self._libreta_last_cortes or [])
        if not cortes:
            QMessageBox.information(
                self, "Sin datos", "No hay operaciones en el periodo para imprimir."
            )
            return
        periodo = self._libreta_periodo_texto().upper()
        if self._libreta_emp_filtro:
            periodo += f" - {self._libreta_emp_filtro}"

        # Cierre formal: el dueño cuenta el cajón y captura el efectivo REAL
        # (precargado con el esperado, editable solo aquí — la barra es suya);
        # el ticket sale con esperado vs real y la diferencia.
        from decimal import Decimal as _Dec

        from PyQt6.QtWidgets import QDoubleSpinBox, QLineEdit

        esperado = sum((c.monto_en_caja for c in cortes), _Dec("0.00"))
        dlg = QDialog(self)
        dlg.setWindowTitle("Hacer corte")
        dlg_ly = QVBoxLayout()
        dlg_ly.setContentsMargins(20, 18, 20, 18)
        dlg_ly.setSpacing(10)
        referencia = QLabel(
            f"Esperado según la Libreta: ${esperado:,.2f}\n"
            "(solo para que compares — esto NO se imprime)"
        )
        dlg_ly.addWidget(referencia)
        dlg_ly.addWidget(QLabel("Cantidad FINAL que saldrá en el ticket:"))
        spin_real = QDoubleSpinBox()
        spin_real.setRange(0.0, 9_999_999.0)
        spin_real.setDecimals(2)
        spin_real.setPrefix("$ ")
        spin_real.setValue(float(esperado))
        spin_real.setStyleSheet("font-size: 18px; font-weight: 700; padding: 6px;")
        dlg_ly.addWidget(spin_real)
        dlg_ly.addWidget(QLabel("Nota (opcional):"))
        nota_input = QLineEdit()
        nota_input.setPlaceholderText("Ej. faltante por cambio, billete roto...")
        dlg_ly.addWidget(nota_input)
        botones_ly = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setAutoDefault(False)
        btn_cancelar.clicked.connect(dlg.reject)
        botones_ly.addWidget(btn_cancelar)
        btn_imprimir = QPushButton("🖨 Imprimir corte")
        btn_imprimir.setObjectName("primaryButton")
        btn_imprimir.clicked.connect(dlg.accept)
        botones_ly.addWidget(btn_imprimir, 1)
        dlg_ly.addLayout(botones_ly)
        dlg.setLayout(dlg_ly)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        monto_final = _Dec(str(spin_real.value())).quantize(_Dec("0.01"))
        nota = nota_input.text().strip()

        # El corte se guarda con SOLO la cifra final (nunca la esperada):
        # es el número oficial y lo que León consulta en "Ver cortes".
        # Sin conexión NO se pierde: cae a la cola local y sube al reconectar.
        from datetime import date as _date

        corte_entry = {
            "fecha": _date.today().isoformat(),
            "monto_final": str(monto_final),
            "operaciones": sum(c.operaciones for c in cortes),
            "piezas": sum(c.piezas for c in cortes),
            "periodo_label": periodo,
            "nota": nota,
            "creado_por": str(self._libreta_code or ""),
        }
        try:
            from pos_uniformes.services.libreta_service import guardar_corte

            with get_session() as session:
                guardar_corte(
                    session,
                    fecha=_date.today(),
                    monto_final=monto_final,
                    operaciones=corte_entry["operaciones"],
                    piezas=corte_entry["piezas"],
                    periodo_label=periodo,
                    nota=nota,
                    creado_por=corte_entry["creado_por"],
                )
        except Exception:  # noqa: BLE001 — sin conexión: a la cola local
            logger.exception("Libreta: corte a cola local (sin conexión)")
            try:
                from pos_uniformes.services import libreta_local_queue_service as cola

                cola.encolar_corte(corte_entry)
            except Exception:  # noqa: BLE001
                logger.exception("Libreta: tampoco se pudo encolar el corte")

        texto = build_corte_ticket_text(
            periodo_label=periodo,
            cortes=cortes,
            por_empleada=list(self._libreta_last_por_empleada or []),
            generado_por=str(self._libreta_code or ""),
            efectivo_real=monto_final,
            nota=nota,
        )
        route_tickets(self, "Corte de Libreta", [texto])

    @staticmethod
    def _libreta_rows_locales(desde, hasta, employee_filter):
        """Fallback offline: las operaciones pendientes de ESTA terminal."""
        from datetime import datetime as _dt
        from decimal import Decimal as _Dec
        from types import SimpleNamespace

        from pos_uniformes.services import libreta_local_queue_service as libreta_cola

        rows = []
        for entry in libreta_cola.pendientes():
            try:
                created = _dt.fromisoformat(str(entry.get("created_at", "")))
            except (TypeError, ValueError):
                continue
            code = str(entry.get("employee_code", "")).upper()
            if employee_filter and code != str(employee_filter).upper():
                continue
            if not (desde <= created <= hasta):
                continue
            items = list(entry.get("items", []))
            from pos_uniformes.services.libreta_service import comisiones_de_items

            monto = _Dec(str(entry.get("monto_total", "0")))
            comisiones = entry.get("comisiones")
            rows.append(
                SimpleNamespace(
                    created_at=created,
                    employee_code=code,
                    employee_name=str(entry.get("employee_name", "")),
                    tipo=str(entry.get("tipo", "venta")),
                    cliente=entry.get("cliente"),
                    piezas=sum(int(it.get("cantidad", 0) or 0) for it in items),
                    comisiones=(
                        int(comisiones) if comisiones is not None else comisiones_de_items(items)
                    ),
                    monto_total=monto,
                    monto_neto=_Dec(str(entry.get("monto_neto") or monto)),
                    pago_tarjeta=bool(entry.get("pago_tarjeta", False)),
                    detalle=items,
                )
            )
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows

    def _llenar_libreta_cards(self, valores: list[tuple]) -> None:
        """Rellena las 4 tarjetas; cada valor es (titulo, valor[, subtitulo])."""
        for (card, titulo, valor, sub), datos in zip(self._libreta_cards, valores):
            titulo.setText(str(datos[0]))
            valor.setText(str(datos[1]))
            texto_sub = str(datos[2]) if len(datos) > 2 and datos[2] else ""
            sub.setText(texto_sub)
            sub.setVisible(bool(texto_sub))

    def _llenar_libreta_lista(self, rows: list) -> None:
        """Movimientos de la empleada en lenguaje simple, sin dinero."""
        from pos_uniformes.services.libreta_service import describir_detalle

        self.libreta_emp_list.clear()
        if not rows:
            item = QListWidgetItem("Aquí van a aparecer tus ventas del día. 🌱")
            self.libreta_emp_list.addItem(item)
            return
        for row in rows:
            local_dt = (
                row.created_at.astimezone()
                if row.created_at.tzinfo is not None
                else row.created_at
            )
            hora = local_dt.strftime("%H:%M")
            dia = (
                f"{_DIA_CORTO[local_dt.weekday()]} {local_dt.strftime('%d/%m')} · "
                if self._libreta_periodo != "hoy"
                else ""
            )
            comisiones = int(getattr(row, "comisiones", 0) or 0)
            tipo = str(row.tipo)
            if tipo == "abono":
                cliente = getattr(row, "cliente", None)
                texto = f"💵  {dia}{hora} · Recibiste un abono"
                if cliente:
                    texto += f" de {cliente}"
            else:
                piezas = int(row.piezas or 0)
                verbo = "Apartaste" if tipo == "apartado" else "Vendiste"
                icono = "📦" if tipo == "apartado" else "🛍️"
                prendas = describir_detalle(list(row.detalle or []))
                texto = f"{icono}  {dia}{hora} · {verbo} {piezas} pieza(s): {prendas}"
                if comisiones:
                    texto += f"  (+{comisiones} com.)"
            self.libreta_emp_list.addItem(QListWidgetItem(texto))
        # Igual que la tabla del dueño: la lista crece y scrollea la página.
        alto = 2 * self.libreta_emp_list.frameWidth() + 8
        for i in range(self.libreta_emp_list.count()):
            alto += self.libreta_emp_list.sizeHintForRow(i)
        self.libreta_emp_list.setFixedHeight(max(alto, 120))

    def _pintar_libreta(self, rows: list, ranking_rows: list | None = None) -> None:
        self._libreta_last_pintura = (list(rows), ranking_rows)
        from pos_uniformes.services.libreta_service import (
            describir_detalle,
            resumir_por_dia,
            resumir_por_empleada,
        )

        # Alineadas con las filas de la tabla MOVIMIENTOS (para poder borrar).
        self._libreta_rows_pintadas = list(rows)

        total_ops = len(rows)
        total_piezas = sum(int(r.piezas or 0) for r in rows)
        total_comisiones = sum(int(getattr(r, "comisiones", 0) or 0) for r in rows)
        ventas_count = sum(1 for r in rows if str(r.tipo) == "venta")
        apartados_count = sum(1 for r in rows if str(r.tipo) == "apartado")
        periodo = self._libreta_periodo_texto()
        cortes = resumir_por_dia(rows) if self._libreta_is_owner else []
        self._libreta_last_cortes = cortes

        if self._libreta_is_owner:
            total_monto = sum(Decimal(str(r.monto_total or 0)) for r in rows)
            total_en_caja = sum((c.monto_en_caja for c in cortes), Decimal("0.00"))
            total_neto = sum((c.monto_neto_ventas for c in cortes), Decimal("0.00"))
            total_abonos = sum((c.monto_abonos for c in cortes), Decimal("0.00"))
            total_tarjeta = sum(
                (
                    Decimal(str(r.monto_total or 0))
                    for r in rows
                    if bool(getattr(r, "pago_tarjeta", False))
                ),
                Decimal("0.00"),
            )
            # Cuatro cifras que no se confunden entre sí: lo que hay en el
            # cajón (la del corte), lo vendido en total (efectivo + tarjeta),
            # lo abonado a apartados, y las comisiones del equipo.
            self._llenar_libreta_cards(
                [
                    (
                        "EN EL CAJÓN (EFECTIVO)",
                        f"${total_en_caja:,.0f}",
                        "ventas + abonos en efectivo · es la cifra del corte",
                    ),
                    (
                        "VENDIDO EN TOTAL",
                        f"${total_monto:,.0f}",
                        f"efectivo + tarjeta · con tarjeta: ${total_tarjeta:,.0f}"
                        f" · neto: ${total_neto:,.0f}",
                    ),
                    (
                        "ABONOS A APARTADOS",
                        f"${total_abonos:,.0f}",
                        f"{apartados_count} apartado(s) nuevos",
                    ),
                    (
                        "COMISIONES",
                        str(total_comisiones),
                        f"{ventas_count} ventas · {total_piezas} piezas",
                    ),
                ]
            )
            self.libreta_resumen_label.setText(
                f"{total_ops} operacion(es) {periodo}"
            )
        else:
            # Saludo con el nombre real en cuanto lo conocemos por sus filas.
            for row in rows:
                if getattr(row, "employee_name", ""):
                    nombre_pila = str(row.employee_name).split()[0].capitalize()
                    self.libreta_titular_label.setText(f"Hola, {nombre_pila} 👋")
                    break
            self._llenar_libreta_cards(
                [
                    ("COMISIONES", str(total_comisiones)),
                    ("PIEZAS VENDIDAS", str(total_piezas)),
                    ("VENTAS", str(ventas_count)),
                    ("APARTADOS", str(apartados_count)),
                ]
            )
            if total_ops == 0:
                mensaje = f"Aún no tienes movimientos {periodo}. ¡Tú puedes! 💪"
            else:
                mensaje = (
                    f"Llevas {total_piezas} pieza(s) y "
                    f"{total_comisiones} comision(es) {periodo}. ¡Bien! ✨"
                )
            self.libreta_resumen_label.setText(mensaje)

        if self._libreta_is_owner:
            # En "Hoy" el desglose por día es una sola fila que repite las
            # tarjetas: se oculta para no saturar. Aparece en ciclo y rango.
            mostrar_dias = self._libreta_periodo != "hoy"
            self.libreta_daily_seccion.setVisible(mostrar_dias)
            self.libreta_daily_table.setVisible(mostrar_dias)
            self.libreta_daily_table.setRowCount(len(cortes))
            for i, corte in enumerate(cortes):
                self.libreta_daily_table.setItem(i, 0, QTableWidgetItem(corte.dia_label))
                self.libreta_daily_table.setItem(
                    i, 1, QTableWidgetItem(f"${corte.monto_en_caja:,.2f}")
                )
                self.libreta_daily_table.setItem(
                    i, 2, QTableWidgetItem(f"${corte.monto_ventas:,.2f}")
                )
                self.libreta_daily_table.setItem(
                    i, 3, QTableWidgetItem(f"${corte.monto_neto_ventas:,.2f}")
                )
                self.libreta_daily_table.setItem(
                    i, 4, QTableWidgetItem(f"${corte.monto_abonos:,.2f}")
                )
                self.libreta_daily_table.setItem(i, 5, QTableWidgetItem(str(corte.operaciones)))
            self._ajustar_alto_tabla_libreta(self.libreta_daily_table)

        if self._libreta_is_owner:
            # El ranking se pinta sin el filtro de empleada: es el selector.
            por_empleada = resumir_por_empleada(
                rows if ranking_rows is None else ranking_rows
            )
            self._libreta_last_por_empleada = resumir_por_empleada(rows)
            self._libreta_ranking_codes = [r.employee_code for r in por_empleada]
            self.libreta_ranking_list.clear()
            medallas = ("🥇", "🥈", "🥉")
            if not por_empleada:
                self.libreta_ranking_list.addItem(
                    QListWidgetItem("Sin movimientos de empleadas en el periodo.")
                )
            for i, r in enumerate(por_empleada):
                nombre = r.employee_name or r.employee_code
                lugar = medallas[i] if i < len(medallas) else f" {i + 1}."
                marca = " ◀" if r.employee_code == self._libreta_emp_filtro else ""
                self.libreta_ranking_list.addItem(
                    QListWidgetItem(
                        f"{lugar}  {nombre} — {r.comisiones} comisiones · "
                        f"${r.monto_total:,.0f} vendidos · {r.operaciones} operaciones{marca}"
                    )
                )

        if not self._libreta_is_owner:
            self._llenar_libreta_lista(rows)
            return

        # ── Paginación: 25 movimientos por página ──
        _POR_PAGINA = 25
        self._libreta_rows_completas = list(rows)
        total_paginas = max(1, -(-len(rows) // _POR_PAGINA))
        self._libreta_pagina = min(
            max(getattr(self, "_libreta_pagina", 0), 0), total_paginas - 1
        )
        inicio = self._libreta_pagina * _POR_PAGINA
        rows = rows[inicio : inicio + _POR_PAGINA]
        # Realineadas con la tabla visible (borrar/detalle van por índice).
        self._libreta_rows_pintadas = list(rows)
        self.libreta_pag_bar.setVisible(total_paginas > 1)
        self.libreta_pag_label.setText(
            f"Página {self._libreta_pagina + 1} de {total_paginas}"
            f"  ·  {len(self._libreta_rows_completas)} movimientos"
        )
        self.libreta_pag_prev.setEnabled(self._libreta_pagina > 0)
        self.libreta_pag_next.setEnabled(self._libreta_pagina < total_paginas - 1)

        self.libreta_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            local_dt = (
                row.created_at.astimezone()
                if row.created_at.tzinfo is not None
                else row.created_at
            )
            tipo_txt = str(row.tipo).capitalize()
            if getattr(row, "pago_tarjeta", False):
                tipo_txt += " (tarjeta)"
            if self._libreta_is_owner:
                nombre = row.employee_name or row.employee_code
                tipo_txt = f"{tipo_txt} — {nombre}"
            if str(row.tipo) == "abono":
                prendas_txt = f"Abono — {getattr(row, 'cliente', None) or 'cliente'}"
            else:
                prendas_txt = describir_detalle(list(row.detalle or []))
            self.libreta_table.setItem(i, 0, QTableWidgetItem(local_dt.strftime("%d/%m")))
            self.libreta_table.setItem(i, 1, QTableWidgetItem(local_dt.strftime("%H:%M")))
            self.libreta_table.setItem(i, 2, QTableWidgetItem(tipo_txt))
            self.libreta_table.setItem(i, 3, QTableWidgetItem(str(row.piezas)))
            self.libreta_table.setItem(
                i, 4, QTableWidgetItem(str(getattr(row, "comisiones", 0) or 0))
            )
            self.libreta_table.setItem(i, 5, QTableWidgetItem(prendas_txt))
            self.libreta_table.setItem(
                i, 6, QTableWidgetItem(f"${Decimal(str(row.monto_total or 0)):,.2f}")
            )
        self._ajustar_alto_tabla_libreta()

    def _cambiar_pagina_libreta(self, delta: int) -> None:
        self._libreta_pagina = max(0, getattr(self, "_libreta_pagina", 0) + delta)
        rows, ranking = getattr(self, "_libreta_last_pintura", (None, None))
        if rows is not None:
            self._pintar_libreta(rows, ranking_rows=ranking)

    def _ajustar_alto_tabla_libreta(self, tabla=None) -> None:
        """Alto exacto al contenido para que scrollee la PÁGINA, no la tabla."""
        tabla = tabla if tabla is not None else self.libreta_table
        alto = tabla.horizontalHeader().height() + 2 * tabla.frameWidth()
        for fila in range(tabla.rowCount()):
            alto += tabla.rowHeight(fila)
        tabla.setFixedHeight(max(alto + 6, 120))

    def _build_conteos_page(self) -> QWidget:
        """Página "Calendario" del kiosko (después de Tarifarios).

        Vista principal = calendario visual del mes; los trabajadores pueden ver
        qué toca y imprimir la orden. La frecuencia se edita solo desde el admin.
        """
        from pos_uniformes.ui.dialogs.conteo_calendario_mes_panel import (
            ConteoCalendarioMesPanel,
        )

        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        header = QHBoxLayout()
        titulo = QLabel("Calendario de conteos")
        titulo.setObjectName("guidedStepTitle")
        header.addWidget(titulo)
        header.addStretch()
        subir_btn = QPushButton("📤 Subir conteo")
        subir_btn.setObjectName("secondaryButton")
        subir_btn.clicked.connect(self._open_conteo_subir)
        header.addWidget(subir_btn)
        orden_btn = QPushButton("🖨 Imprimir orden de conteo")
        orden_btn.setObjectName("secondaryButton")
        orden_btn.clicked.connect(self._open_conteo_orden)
        header.addWidget(orden_btn)
        layout.addLayout(header)

        self.conteos_panel = ConteoCalendarioMesPanel(page, refresh_on_init=False)
        layout.addWidget(self.conteos_panel, 1)
        page.setLayout(layout)
        return page

    def _build_kiosk_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_conteo_banner())
        layout.addWidget(self._build_kiosk_panel(), 1)
        page.setLayout(layout)
        return page

    def _build_conteo_banner(self) -> QWidget:
        """Aviso de conteo pendiente (oculto si no hay nada vencido)."""
        self.conteo_banner = QFrame()
        self.conteo_banner.setObjectName("conteoBanner")
        self.conteo_banner.setStyleSheet(
            "#conteoBanner { background: #fff3e0; border: 1px solid #e0a96d; border-radius: 10px; }"
            "#conteoBanner QLabel { color: #8a4b1a; font-weight: 700; background: transparent; border: none; }"
        )
        row = QHBoxLayout()
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)
        self.conteo_banner_label = QLabel("")
        row.addWidget(self.conteo_banner_label, 1)
        banner_btn = QPushButton("Imprimir orden de conteo")
        banner_btn.setObjectName("secondaryButton")
        banner_btn.clicked.connect(self._open_conteo_orden)
        row.addWidget(banner_btn)
        self.conteo_banner.setLayout(row)
        self.conteo_banner.setVisible(False)
        return self.conteo_banner

    def _refresh_conteo_banner(self) -> None:
        """Consulta escuelas con conteo vencido y muestra/oculta el banner."""
        banner = getattr(self, "conteo_banner", None)
        if banner is None:
            return
        if self.offline_mode:
            banner.setVisible(False)
            return
        try:
            from pos_uniformes.services.conteo_calendario_service import (
                escuelas_con_conteo_vencido,
            )

            with get_session() as session:
                vencidas = escuelas_con_conteo_vencido(session)
        except Exception:  # noqa: BLE001 — sin conexión: no molestar
            banner.setVisible(False)
            return

        n = len(vencidas)
        if n == 0:
            banner.setVisible(False)
            return
        if n == 1:
            texto = f"⚠  Conteo pendiente: {vencidas[0].escuela_nombre}"
        else:
            texto = f"⚠  Conteo pendiente en {n} escuelas"
        self.conteo_banner_label.setText(texto)
        banner.setVisible(True)

    def _open_conteo_orden(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_orden_dialog import ConteoOrdenDialog

        ConteoOrdenDialog(self).exec()
        self._refresh_conteo_banner()

    def _open_conteo_subir(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog

        ConteoSubirDialog(self).exec()
        self._refresh_conteo_banner()

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
        self.catalog_include_general_combo.setCurrentIndex(0)
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

        # Barra de búsqueda rápida (Meilisearch)
        search_bar_layout = QHBoxLayout()
        search_bar_layout.setContentsMargins(12, 8, 12, 4)
        self.guided_search_input.setMinimumHeight(44)
        self.guided_search_input.setObjectName("guidedSearchInput")
        search_bar_layout.addWidget(self.guided_search_input)
        page_layout.addLayout(search_bar_layout)

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

        steps_card = self._build_guided_steps_card()
        detail_card = self._build_guided_detail_card()
        self._guided_steps_widget = steps_card
        self._guided_detail_widget = detail_card

        # Contenedor de resultados de búsqueda (dentro del mismo scroll)
        self._search_results_widget = QWidget()
        self._search_results_layout = QVBoxLayout()
        self._search_results_layout.setContentsMargins(0, 0, 0, 0)
        self._search_results_layout.setSpacing(8)
        self._search_results_widget.setLayout(self._search_results_layout)
        self._search_results_widget.setVisible(False)

        layout.addWidget(steps_card)
        layout.addWidget(self._search_results_widget)
        layout.addWidget(detail_card)
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
        steps_layout.setContentsMargins(16, 14, 16, 14)
        steps_layout.setSpacing(12)
        _steps_header = QHBoxLayout()
        _steps_header.setSpacing(8)
        _steps_title = QLabel("Cotiza por pasos")
        _steps_title.setObjectName("guidedGroupBoxTitle")
        self.guided_favorites_button.setObjectName("chipButton")
        self.guided_favorites_button.setFixedHeight(32)
        self.guided_meili_indicator.setToolTip(
            "Estado de la búsqueda inteligente — se administra en Ctrl+Shift+A"
        )
        _steps_header.addWidget(_steps_title)
        _steps_header.addStretch()
        _steps_header.addWidget(self.guided_meili_indicator)
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
        school_scroll.setMinimumHeight(200)
        school_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        school_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
        school_layout.addWidget(school_scroll, 1)

        # Paginación de escuelas: avanzar / regresar de página.
        self.guided_school_prev_button = QPushButton("◀ Anterior")
        self.guided_school_prev_button.setObjectName("secondaryButton")
        self.guided_school_prev_button.setMinimumHeight(44)
        self.guided_school_next_button = QPushButton("Siguiente ▶")
        self.guided_school_next_button.setObjectName("secondaryButton")
        self.guided_school_next_button.setMinimumHeight(44)
        self.guided_school_page_label = QLabel("Página 1 / 1")
        self.guided_school_page_label.setObjectName("guidedStepHint")
        self.guided_school_prev_button.clicked.connect(lambda: self._handle_guided_school_page(-1))
        self.guided_school_next_button.clicked.connect(lambda: self._handle_guided_school_page(1))
        self.guided_school_pager = QWidget()
        _school_pager_layout = QHBoxLayout()
        _school_pager_layout.setContentsMargins(0, 0, 0, 0)
        _school_pager_layout.setSpacing(8)
        _school_pager_layout.addWidget(self.guided_school_prev_button)
        _school_pager_layout.addStretch()
        _school_pager_layout.addWidget(self.guided_school_page_label)
        _school_pager_layout.addStretch()
        _school_pager_layout.addWidget(self.guided_school_next_button)
        self.guided_school_pager.setLayout(_school_pager_layout)
        self.guided_school_pager.setVisible(False)
        school_layout.addWidget(self.guided_school_pager)

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
        self.guided_product_scroll.setMinimumHeight(180)
        self.guided_product_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.guided_product_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.guided_product_scroll.setObjectName("guidedScrollArea")
        self.guided_product_scroll.viewport().setObjectName("guidedScrollViewport")
        self.guided_product_container = QWidget()
        self.guided_product_container.setObjectName("guidedGridSurface")
        self.guided_product_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.guided_product_flow_layout = FlowLayout(margin=4, h_spacing=6, v_spacing=6)
        self.guided_product_container.setLayout(self.guided_product_flow_layout)
        self.guided_product_scroll.setWidget(self.guided_product_container)
        products_section_layout.addWidget(self.guided_products_title_label)
        products_section_layout.addWidget(self.guided_products_hint_label)
        # Se agrega el paginador de modelos al final (tras el scroll).
        products_section_layout.addWidget(self.guided_empty_label)
        products_section_layout.addWidget(self.guided_product_scroll, 1)

        # Paginación de modelos: avanzar / regresar de página.
        self.guided_product_prev_button = QPushButton("◀ Anterior")
        self.guided_product_prev_button.setObjectName("secondaryButton")
        self.guided_product_prev_button.setMinimumHeight(44)
        self.guided_product_next_button = QPushButton("Siguiente ▶")
        self.guided_product_next_button.setObjectName("secondaryButton")
        self.guided_product_next_button.setMinimumHeight(44)
        self.guided_product_page_label = QLabel("Página 1 / 1")
        self.guided_product_page_label.setObjectName("guidedStepHint")
        self.guided_product_prev_button.clicked.connect(lambda: self._handle_guided_product_page(-1))
        self.guided_product_next_button.clicked.connect(lambda: self._handle_guided_product_page(1))
        self.guided_product_pager = QWidget()
        _product_pager_layout = QHBoxLayout()
        _product_pager_layout.setContentsMargins(0, 0, 0, 0)
        _product_pager_layout.setSpacing(8)
        _product_pager_layout.addWidget(self.guided_product_prev_button)
        _product_pager_layout.addStretch()
        _product_pager_layout.addWidget(self.guided_product_page_label)
        _product_pager_layout.addStretch()
        _product_pager_layout.addWidget(self.guided_product_next_button)
        self.guided_product_pager.setLayout(_product_pager_layout)
        self.guided_product_pager.setVisible(False)
        products_section_layout.addWidget(self.guided_product_pager)

        self.guided_products_section.setLayout(products_section_layout)
        steps_layout.addWidget(self.guided_products_section, 1)

        # Footer removido (2026-07-11): "Limpiar pasos" y "Piezas generales" ya
        # no se usan — la ruta se elige en el paso 1 y la navegación de escuelas
        # ahora es por páginas (paso 3). Los botones siguen creados por si se
        # retoman, pero no se muestran.

        steps_box.setLayout(steps_layout)
        return steps_box

    def _build_guided_detail_card(self) -> QFrame:
        """Construye el card de producto seleccionado (ícono + variantes + acciones)."""
        detail_box = QFrame()
        detail_box.setObjectName("guidedStepsCard")
        detail_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(12, 8, 12, 8)
        detail_layout.setSpacing(4)

        # Fila compacta: ícono + texto + acciones
        self._guided_detail_compact_row = QHBoxLayout()
        self._guided_detail_compact_row.setSpacing(8)
        self.guided_visual_icon_label.setFixedSize(48, 48)
        self._guided_detail_compact_row.addWidget(
            self.guided_visual_icon_label, 0, Qt.AlignmentFlag.AlignVCenter
        )
        self.guided_detail_title_label.setObjectName("satDetailTitle")
        self.guided_detail_meta_label.setObjectName("satDetailMeta")
        self.guided_detail_meta_label.setWordWrap(True)
        self.guided_detail_notes_label.setObjectName("satDetailNotes")
        self.guided_detail_notes_label.setWordWrap(True)
        detail_text_layout = QVBoxLayout()
        detail_text_layout.setSpacing(0)
        detail_text_layout.addWidget(self.guided_detail_title_label)
        detail_text_layout.addWidget(self.guided_detail_meta_label)
        self._guided_detail_compact_row.addLayout(detail_text_layout, 1)

        # Acciones en la misma fila
        self.guided_qty_spin.setRange(1, 100)
        self.guided_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.guided_qty_spin.setValue(1)
        self.guided_add_button.setObjectName("primaryButton")
        self.guided_add_button.setMinimumHeight(34)
        self.guided_print_label_button.setObjectName("ghostButton")
        self._guided_detail_compact_row.addWidget(self.guided_print_label_button)
        self._guided_detail_compact_row.addWidget(self.guided_qty_spin)
        self._guided_detail_compact_row.addWidget(self.guided_add_button)

        detail_layout.addLayout(self._guided_detail_compact_row)
        detail_layout.addWidget(self.guided_detail_notes_label)

        # Variantes (sección expandida, se oculta durante búsqueda)
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
        self.guided_detail_scroll = self.guided_variant_section

        detail_layout.addWidget(self.guided_variant_section)
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

    def _build_tariff_page(self) -> QWidget:
        from PyQt6.QtGui import QFontDatabase
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_FONT_POINT_SIZE

        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # — Selector de escuela —
        selector_card = QGroupBox("Selecciona una escuela")
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(10)
        self.tariff_school_combo.setMinimumWidth(280)
        self.tariff_school_combo.setPlaceholderText("Elige escuela...")
        self.tariff_generate_button.setObjectName("primaryButton")
        self.tariff_print_button.setObjectName("secondaryButton")
        self.tariff_print_button.setEnabled(False)
        selector_layout.addWidget(self.tariff_school_combo, 1)
        selector_layout.addWidget(self.tariff_generate_button)
        selector_layout.addWidget(self.tariff_print_button)
        selector_card.setLayout(selector_layout)

        # — Vista previa —
        preview_card = QGroupBox("Vista previa del tarifario")
        preview_layout = QVBoxLayout()
        mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self.tariff_preview.setStyleSheet(
            f'QTextEdit {{ font-family: "{mono_family}"; font-size: {TICKET_FONT_POINT_SIZE}pt;'
            f" font-weight: bold; }}"
        )
        self.tariff_preview.setPlaceholderText("Selecciona una escuela y presiona Generar.")
        preview_layout.addWidget(self.tariff_preview)
        preview_card.setLayout(preview_layout)

        layout.addWidget(selector_card)
        layout.addWidget(preview_card, 1)
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
        totals_title = QLabel("Presupuesto estimado")
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
        self.nav_quicksale_button.clicked.connect(lambda: self._set_page("quicksale"))
        self.nav_share_button.clicked.connect(lambda: self._set_page("share"))
        self.nav_search_button.clicked.connect(lambda: self._set_page("search"))
        self.nav_tariff_button.clicked.connect(lambda: self._set_page("tariff"))
        self.nav_libreta_button.clicked.connect(lambda: self._set_page("libreta"))
        self.nav_conteos_button.clicked.connect(lambda: self._set_page("conteos"))
        self.tariff_generate_button.clicked.connect(self._handle_generate_tariff)
        self.tariff_print_button.clicked.connect(self._handle_print_tariff)
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
        _esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        _esc_shortcut.activated.connect(self._handle_escape_key)
        _kiosk_ctrl_s = QShortcut(QKeySequence("Ctrl+S"), self)
        _kiosk_ctrl_s.activated.connect(self._handle_quick_search)
        _admin_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        _admin_shortcut.activated.connect(self._open_satellite_admin)
        _cola_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        _cola_shortcut.activated.connect(self._open_dispatcher_panel)
        _pedidos_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        _pedidos_shortcut.activated.connect(self._open_pedido_board)
        # Navegación de secciones con Ctrl+←/→. Se usa Ctrl (no flechas peladas)
        # porque el campo de escaneo y los buscadores tienen el foco casi siempre
        # y se quedarían con las flechas.
        _sec_next = QShortcut(QKeySequence("Ctrl+Right"), self)
        _sec_next.activated.connect(lambda: self._navegar_seccion(1))
        _sec_prev = QShortcut(QKeySequence("Ctrl+Left"), self)
        _sec_prev.activated.connect(lambda: self._navegar_seccion(-1))
        # Ctrl+K global via event filter (funciona en diálogos modales)
        from PyQt6.QtCore import QEvent, QObject as _QObj

        class _KioskKeyFilter(_QObj):
            def __init__(self, owner):
                super().__init__(owner)
                self._owner = owner

            def eventFilter(self, obj, event):
                tipo = event.type()
                # Actividad del usuario: reinicia la inactividad de la cartelera y
                # cierra el overlay si estaba puesto. Barato (solo press/teclas).
                if tipo in (
                    QEvent.Type.KeyPress,
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.TouchBegin,
                ):
                    # Un hook GLOBAL (corre en cada tecla/clic) jamás debe poder
                    # tumbar la app: cualquier fallo aquí se traga y se sigue.
                    try:
                        cartelera = getattr(self._owner, "_anuncio_cartelera", None)
                        if cartelera is not None:
                            cartelera.notar_actividad()
                    except Exception:  # noqa: BLE001
                        pass
                if tipo == QEvent.Type.KeyPress:
                    mods = event.modifiers()
                    key = event.key()
                    ctrl = mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.MetaModifier
                    if ctrl and key == Qt.Key.Key_K:
                        self._owner._open_quick_kiosk()
                        return True
                return False

        self._kiosk_filter = _KioskKeyFilter(self)
        QApplication.instance().installEventFilter(self._kiosk_filter)
        self.catalog_previous_page_button.clicked.connect(self._handle_catalog_browser_previous_page)
        self.catalog_next_page_button.clicked.connect(self._handle_catalog_browser_next_page)
        self.guided_add_button.clicked.connect(self._handle_add_guided_selection_to_quote)
        self.guided_print_label_button.clicked.connect(self._print_label_for_guided_selection)
        self.guided_favorites_button.clicked.connect(self._open_favorites_dialog)
        self.guided_reindex_button.clicked.connect(self._handle_reindex_meilisearch)
        self.guided_meilisearch_btn.clicked.connect(self._handle_start_meilisearch)
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
        self.quote_search_input.textChanged.connect(lambda: self._quote_filter_debounce_timer.start())
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

    # ── Actualizaciones (buscar y aplicar vía el lanzador) ───────────────

    def _buscar_actualizacion_en_background(self) -> None:
        """Chequeo silencioso post-arranque; si hay versión nueva, la ofrece."""
        import threading

        def _worker() -> None:
            try:
                from pos_uniformes.services.satellite_startup_service import (
                    probe_database_host,
                )

                if not probe_database_host():
                    return
                from pos_uniformes.services.satellite_update_service import (
                    estado_actualizacion,
                )

                _local, remota, hay = estado_actualizacion()
                if hay and remota:
                    self._update_disponible.emit(remota)
            except Exception:  # noqa: BLE001
                logger.debug("Chequeo de actualización pospuesto", exc_info=True)

        threading.Thread(target=_worker, daemon=True, name="update-check").start()

    def buscar_actualizaciones_interactivo(self, parent=None) -> None:
        """Botón del admin: busca ahora y reporta el resultado con diálogos."""
        from pos_uniformes.services.satellite_startup_service import probe_database_host
        from pos_uniformes.services.satellite_update_service import estado_actualizacion

        parent = parent or self
        if not probe_database_host():
            QMessageBox.warning(
                parent, "Sin conexión",
                "No se alcanzó la PC principal. Revisa que esté encendida y en red.",
            )
            return
        local, remota, hay = estado_actualizacion()
        if remota is None:
            QMessageBox.warning(
                parent, "Carpeta de updates no disponible",
                "La PC principal responde pero no se pudo leer "
                "\\\\servidor\\pos_updates. Revisa el share o corre la build.",
            )
            return
        if not hay:
            QMessageBox.information(
                parent, "Al día", f"Ya tienes la versión más reciente ({local})."
            )
            return
        self._ofrecer_actualizacion(remota, parent=parent)

    def _ofrecer_actualizacion(self, remota: str, parent=None) -> None:
        from pos_uniformes.services.satellite_update_service import version_local

        parent = parent or self
        box = QMessageBox(parent)
        box.setWindowTitle("Actualización disponible")
        box.setText(
            "Hay una versión nueva del satélite:\n\n"
            f"    Instalada:  {version_local()}\n"
            f"    Disponible: {remota}\n\n"
            "Al actualizar, la app se cierra unos segundos y el lanzador "
            "la reabre ya actualizada."
        )
        actualizar = box.addButton("Actualizar ahora", QMessageBox.ButtonRole.YesRole)
        box.addButton("Ahora no", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() is actualizar:
            self._aplicar_actualizacion(parent)

    def _aplicar_actualizacion(self, parent=None) -> None:
        from pos_uniformes.services.satellite_update_service import lanzar_actualizador

        if not lanzar_actualizador():
            QMessageBox.warning(
                parent or self, "No se encontró el lanzador",
                "No se encontró lanzador_satelite.bat en este equipo.\n"
                "Cierra la app y ábrela con el acceso directo del lanzador "
                "para que se actualice.",
            )
            return
        # Cerrar el PROCESO completo, no solo la ventana: la cartelera u
        # otros widgets pueden mantener vivo el exe y entonces el lanzador
        # no puede copiar (archivos bloqueados) ni reabrir (candado de
        # instancia única) — se veía como "abre el cmd y no hace nada".
        self.close()
        QApplication.quit()

    def _set_page(self, page_key: str) -> None:
        # Al salir de la Libreta se cierra la sesión sola: la vista del dueño
        # (con dinero) no debe quedar abierta en el kiosko.
        if page_key != "libreta" and getattr(self, "_libreta_code", None):
            self._libreta_logout()
        page_index_map = {
            "kiosk": 0,
            "quicksale": 1,
            "catalog": 2,
            "guided": 3,
            "quote": 4,
            "share": 5,
            "tariff": 6,
            "search": 7,
            "conteos": 8,
            "libreta": 9,
        }
        button_map = {
            "kiosk": self.nav_kiosk_button,
            "quicksale": self.nav_quicksale_button,
            "catalog": self.nav_catalog_button,
            "guided": self.nav_guided_button,
            "quote": self.nav_quote_button,
            "share": self.nav_share_button,
            "tariff": self.nav_tariff_button,
            "search": self.nav_search_button,
            "conteos": self.nav_conteos_button,
            "libreta": self.nav_libreta_button,
        }
        page_title_map = {
            "kiosk": "Kiosko listo para escaneo rapido.",
            "quicksale": "Venta rapida — escanea productos y genera nota.",
            "catalog": "Catalogo simplificado para cotizar por escuela.",
            "guided": "Cotiza por pasos.",
            "quote": "Ajusta el presupuesto.",
            "share": "Compartir por WhatsApp o imprimir.",
            "tariff": "Tarifario de precios por escuela.",
            "search": "Busqueda y seguimiento de presupuestos.",
            "conteos": "Calendario de conteos por escuela.",
            "libreta": "Libreta de la tienda.",
        }
        self.current_page_key = page_key
        self.page_stack.setCurrentIndex(page_index_map[page_key])
        button_map[page_key].setChecked(True)
        self._set_status(page_title_map[page_key])
        if page_key == "conteos":
            self.conteos_panel.refresh()
        if page_key == "kiosk":
            QTimer.singleShot(0, self.kiosk_scan_input.setFocus)
        if page_key == "quicksale":
            self.quick_sale_widget.focus_input()
        if page_key == "libreta":
            # Igual que venta rápida: el cursor cae solo en el campo del
            # gafete al entrar (la página siempre abre en el gate, porque
            # salir de ella cierra la sesión).
            QTimer.singleShot(0, self.libreta_gate_input.setFocus)
        if page_key == "search" and self.offline_mode:
            self._refresh_offline_quotes()

    # Orden de las secciones tal como aparecen en el sidebar. Las ocultas
    # (Catálogo, Presupuesto, Buscar) se saltan solas al navegar.
    _SECCIONES_NAV = (
        "kiosk", "quicksale", "catalog", "guided", "quote", "search", "tariff",
        "libreta", "conteos",
    )

    def _secciones_visibles(self) -> list[str]:
        """Secciones navegables, en orden del sidebar, sin las ocultas."""
        botones = {
            "kiosk": self.nav_kiosk_button,
            "quicksale": self.nav_quicksale_button,
            "catalog": self.nav_catalog_button,
            "guided": self.nav_guided_button,
            "quote": self.nav_quote_button,
            "search": self.nav_search_button,
            "tariff": self.nav_tariff_button,
            "libreta": self.nav_libreta_button,
            "conteos": self.nav_conteos_button,
        }
        return [k for k in self._SECCIONES_NAV if not botones[k].isHidden()]

    def _navegar_seccion(self, delta: int) -> None:
        """Ctrl+→ / Ctrl+← : sección siguiente / anterior. Se detiene en el extremo."""
        secciones = self._secciones_visibles()
        if not secciones:
            return
        actual = getattr(self, "current_page_key", None)
        try:
            i = secciones.index(actual)
        except ValueError:
            # Página que no está en el sidebar (p.ej. "share"): arranca del inicio.
            self._set_page(secciones[0])
            return
        destino = i + delta
        if 0 <= destino < len(secciones):
            self._set_page(secciones[destino])

    def refresh_all(self, *, catalog_from_cache: bool = False) -> None:
        if self.offline_mode:
            self._refresh_catalog_browser()
            self._refresh_guided_browser()
            self._refresh_quote_cart_table()
            self._refresh_recent_lookup_table()
            self._refresh_offline_quotes()
            self._refresh_tariff_schools()
            self._set_status("Vista refrescada (modo local).")
            return
        try:
            # Arranque: el catálogo se pinta desde el cache local (~35ms) en
            # vez de esperar la query de ~4,800 filas por red; el watchdog en
            # background trae el fresco sin congelar el splash.
            catalog_ready = catalog_from_cache and self._load_catalog_from_disk_cache()
            with get_session() as session:
                self._refresh_client_combo(session)
                if not catalog_ready:
                    self._refresh_catalog_snapshot(session)
                self._refresh_quotes(session)
                self._refresh_tariff_schools(session)
            self._refresh_catalog_browser()
            self._refresh_guided_browser()
            self._refresh_quote_cart_table()
            self._refresh_recent_lookup_table()
            if catalog_ready:
                self._start_background_db_refresh()
                self._set_status("Catalogo del cache local; actualizando en segundo plano...")
            else:
                self._set_status("Datos actualizados.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo actualizar", str(exc))

    def _load_catalog_from_disk_cache(self) -> bool:
        """Carga catalog_cache.json en memoria. True si el cache sirvió;
        False para caer a la query completa contra la base."""
        try:
            rows = load_catalog_cache()
        except Exception:  # noqa: BLE001
            return False
        if not rows:
            return False
        self.catalog_snapshot_rows = rows
        self._rebuild_sku_index()
        self._rebuild_catalog_level_combo()
        # El próximo _refresh_catalog_snapshot (refresh manual) sí debe
        # re-indexar Meilisearch en background: trae filas nuevas.
        self._catalog_snapshot_loaded_once = True
        self._update_meilisearch_status()
        QTimer.singleShot(10_000, self._update_meilisearch_status)
        return True

    def _rebuild_sku_index(self) -> None:
        """Reconstruye el indice por SKU para busquedas O(1) en el catalogo."""
        self._sku_index = {
            str(row.get("sku", "")).strip().upper(): row
            for row in self.catalog_snapshot_rows
            if row.get("sku")
        }

    def _find_row_by_sku(self, sku: str) -> dict[str, object] | None:
        """Busca una fila del catalogo por SKU en O(1)."""
        return self._sku_index.get(str(sku).strip().upper())

    def _refresh_catalog_snapshot(self, session) -> None:
        self.catalog_snapshot_rows = load_catalog_snapshot_rows(session)
        self._rebuild_sku_index()
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
        # Antes aquí se indexaba Meilisearch SÍNCRONO en el hilo de UI (hasta
        # 40s con ~4,800 variantes). El arranque ya reindexa en background
        # (autostart_and_reindex en presupuestos_satelite_main); solo los
        # refresh posteriores re-indexan, y también en background.
        if self._catalog_snapshot_loaded_once:
            from pos_uniformes.services import meilisearch_service

            meilisearch_service.notify_catalog_changed()
        self._catalog_snapshot_loaded_once = True
        self._update_meilisearch_status()
        # El auto-arranque de Meilisearch corre en background al abrir la app;
        # re-checar el indicador cuando ya haya tenido tiempo de levantar.
        QTimer.singleShot(10_000, self._update_meilisearch_status)

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

        search_text = self.catalog_search_input.text().strip()
        source_rows = self.catalog_snapshot_rows
        used_meili = False

        # Meilisearch resuelve el texto (matchingStrategy=all: exige todas las
        # palabras con typos y sinónimos). El filtro local de texto solo corre
        # como fallback — si se re-aplicara, mataría la tolerancia a typos.
        if search_text:
            try:
                from pos_uniformes.services import meilisearch_service
                if meilisearch_service.is_available():
                    hits = meilisearch_service.search(search_text, limit=100)
                    if hits:
                        hit_skus = {str(h.get("sku", "")) for h in hits}
                        source_rows = [r for r in self.catalog_snapshot_rows if str(r.get("sku", "")) in hit_skus]
                        used_meili = True
            except Exception:
                pass  # fallback al filtro local

        rows, summary = build_quote_catalog_browser(
            snapshot_rows=source_rows,
            level_filter=str(self.catalog_level_combo.currentData() or ""),
            school_filter=effective_school_filter,
            include_general=include_general,
            search_text="" if used_meili else search_text,
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
        selected_row = self._find_row_by_sku(sku)
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
        row = self._find_row_by_sku(sku)
        self._apply_guided_detail(row)
        self._refresh_guided_product_checks()
        self._refresh_guided_variant_checks()
        self._apply_action_state()

    # ── Búsqueda rápida Meilisearch ─────────────────────────────────────

    def _update_meilisearch_status(self) -> None:
        try:
            from pos_uniformes.services import meilisearch_service
            running = meilisearch_service.is_available()
        except Exception:  # noqa: BLE001
            running = False
        try:
            if running:
                self.guided_meili_indicator.setText("●")
                self.guided_meili_indicator.setStyleSheet("color:#2e7d32; font-weight:bold; font-size:15px;")
                self.guided_meili_indicator.setToolTip("Búsqueda inteligente activa (typos y sinónimos)")
            else:
                self.guided_meili_indicator.setText("○")
                self.guided_meili_indicator.setStyleSheet("color:#9a8c7c; font-size:15px;")
                self.guided_meili_indicator.setToolTip(
                    "Búsqueda inteligente no disponible — se usa búsqueda local.\nAdministrar: Ctrl+Shift+A"
                )
        except RuntimeError:
            # El re-chequeo diferido (QTimer 10s) puede disparar con la
            # ventana ya destruida.
            pass

    def _handle_start_meilisearch(self) -> None:
        dlg = _MeilisearchProgressDialog("Iniciando Meilisearch", self)
        self._ms_worker = _MeilisearchWorker(mode="start")
        self._ms_worker.progress.connect(dlg.update_status)
        self._ms_worker.finished.connect(
            lambda ok, msg: (dlg.finish(ok, msg), self._update_meilisearch_status())
        )
        self._ms_worker.start()
        dlg.exec()

    def _handle_reindex_meilisearch(self) -> None:
        dlg = _MeilisearchProgressDialog("Sincronizando Meilisearch", self)
        self._ms_worker = _MeilisearchWorker(mode="sync")
        self._ms_worker.progress.connect(dlg.update_status)
        self._ms_worker.finished.connect(
            lambda ok, msg: (dlg.finish(ok, msg), self._update_meilisearch_status())
        )
        self._ms_worker.start()
        dlg.exec()

    def _on_guided_search_text_changed(self, text: str) -> None:
        if self._guided_search_input_submitted:
            self._guided_search_input_submitted = False
            return
        if self._search_results_widget is None:
            return
        if text.strip():
            self._suggest_timer.start()
            self._guided_search_timer.start()
        else:
            self._suggest_timer.stop()
            self._guided_search_timer.stop()
            self._exit_search_mode()

    def _update_search_suggestions(self) -> None:
        query = self.guided_search_input.text().strip()
        if not query:
            return
        try:
            from pos_uniformes.services import meilisearch_service
            hits = meilisearch_service.search(query, limit=20)
            seen: set[str] = set()
            suggestions: list[str] = []
            for hit in hits:
                name = hit.get("nombre_base", "")
                if name and name not in seen:
                    seen.add(name)
                    suggestions.append(name)
            self._search_completer_model.setStringList(suggestions)
            if suggestions:
                self._search_completer.complete()
        except Exception:  # noqa: BLE001
            pass

    def _on_search_suggestion_selected(self, text: str) -> None:
        self._guided_search_input_submitted = True
        self.guided_search_input.setText(text)
        self._suggest_timer.stop()
        self._guided_search_timer.stop()
        self._run_guided_search()

    def _run_guided_search(self) -> None:
        query = self.guided_search_input.text().strip()
        if not query:
            return

        try:
            from pos_uniformes.services import meilisearch_service
            families = meilisearch_service.search_as_families(query, limit=60)
        except Exception:
            families = []

        # Limpiar resultados anteriores
        self._selected_search_btn = None
        while self._search_results_layout.count():
            item = self._search_results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not families:
            no_results = QLabel("Sin resultados.")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.setStyleSheet("color: #888; padding: 24px;")
            self._search_results_layout.addWidget(no_results)
        else:
            for fam in families:
                card = self._build_search_family_card(fam)
                self._search_results_layout.addWidget(card)

        self._enter_search_mode()
        # Scroll al inicio de resultados
        if self.guided_page_scroll is not None:
            self.guided_page_scroll.verticalScrollBar().setValue(0)

    def _build_search_family_card(self, family: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("guidedStepsCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 14, 16, 12)
        card_layout.setSpacing(8)

        nombre = family.get("nombre_base", "")
        tipo_pieza = family.get("tipo_pieza", "")
        precio_desde = family.get("precio_desde", 0)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header = QLabel(nombre)
        header.setObjectName("guidedGroupBoxTitle")
        header.setWordWrap(True)
        header_layout.addWidget(header, 1)
        precio_label = QLabel(f"desde ${precio_desde:,.2f}")
        precio_label.setObjectName("guidedStepHint")
        precio_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        header_layout.addWidget(precio_label, 0, Qt.AlignmentFlag.AlignRight)
        card_layout.addLayout(header_layout)

        meta = QLabel(tipo_pieza)
        meta.setObjectName("guidedStepHint")
        card_layout.addWidget(meta)

        variantes = family.get("variantes", [])
        # Tallas de menor a mayor dentro de cada grupo de precio (Meilisearch
        # las devuelve por relevancia, no por talla).
        from pos_uniformes.ui.helpers.quote_guided_catalog_helper import build_search_price_groups

        for precio, grupo in build_search_price_groups(variantes):
            price_header = QLabel(f"${precio:,.2f}")
            price_header.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #6B4226;"
                " padding: 4px 0 2px 0;"
            )
            card_layout.addWidget(price_header)

            flow = FlowLayout(margin=0, h_spacing=6, v_spacing=6)
            for v in grupo:
                sku = v.get("sku", "")
                talla = v.get("talla", "") or sku
                btn = _DoubleClickButton(f"Talla {talla} · ${precio:,.2f}")
                btn.setFixedHeight(32)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"SKU: {sku}")
                btn.setProperty("searchVariantSku", sku)
                btn.setStyleSheet(
                    "QPushButton { background: #f5f0e8; border: 1px solid #c4b9a8;"
                    " border-radius: 6px; font-size: 12px; color: #3a2a1a;"
                    " padding: 4px 12px; }"
                    "QPushButton:hover { background: #e8dfd2; border-color: #8B5E3C; }"
                )
                btn.clicked.connect(lambda checked, s=sku, b=btn: self._on_search_variant_select(s, b))

                def _on_dbl(sku=sku):
                    self._on_search_variant_select(sku)
                    self._add_quote_item_by_sku(sku, 1)
                btn.double_clicked.connect(_on_dbl)
                flow.addWidget(btn)
            flow_container = QWidget()
            flow_container.setLayout(flow)
            card_layout.addWidget(flow_container)
        card.setLayout(card_layout)
        return card

    def _enter_search_mode(self) -> None:
        self._guided_steps_widget.setVisible(False)
        self._search_results_widget.setVisible(True)

    def _handle_escape_key(self) -> None:
        """ESC: si hay busqueda activa la cierra, si no resetea el flujo guiado o limpia tarifario."""
        if self._search_results_widget is not None and self._search_results_widget.isVisible():
            self._exit_search_mode()
            return
        if self.current_page_key == "quicksale" and self.quick_sale_widget.is_session_active():
            self.quick_sale_widget.logout()
            return
        if self.current_page_key == "libreta" and getattr(self, "_libreta_code", None):
            # Privacidad rápida: Esc cierra la sesión de la Libreta (igual
            # que el cambio de página) y regresa al gate del gafete.
            self._libreta_logout()
            return
        if self.current_page_key == "tariff":
            self.tariff_school_combo.setCurrentIndex(-1)
            self.tariff_preview.clear()
            self._current_tariff = None
            self.tariff_print_button.setEnabled(False)
            return
        # Resetear flujo guiado completo
        if self._gfs.mode == "basics":
            self._reset_guided_route(mode_key="basics")
        else:
            self._reset_guided_route(mode_key="school")

    def _exit_search_mode(self) -> None:
        self._search_results_widget.setVisible(False)
        self._guided_steps_widget.setVisible(True)
        self._selected_search_btn = None
        self.guided_search_input.clear()
        self._guided_search_input_submitted = False

    def _on_search_variant_select(self, sku: str, btn: _DoubleClickButton | None = None) -> None:
        """Single click — selecciona variante con highlight naranja + detail card."""
        # Quitar highlight del botón anterior
        if self._selected_search_btn is not None:
            self._selected_search_btn.setStyleSheet(
                "QPushButton { background: #f5f0e8; border: 1px solid #c4b9a8;"
                " border-radius: 6px; font-size: 12px; color: #3a2a1a;"
                " padding: 4px 12px; }"
                "QPushButton:hover { background: #e8dfd2; border-color: #8B5E3C; }"
            )
        # Aplicar highlight naranja al botón clickeado
        if btn is not None:
            btn.setStyleSheet(
                "QPushButton { background: #87492c; border: 1px solid #87492c;"
                " border-radius: 6px; font-size: 12px; color: #fbf8f2;"
                " padding: 4px 12px; font-weight: bold; }"
            )
            self._selected_search_btn = btn

        self._gfs.sku = sku
        row = self._find_row_by_sku(sku)
        self._apply_guided_detail(row)
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
            row = self._find_row_by_sku(self._gfs.sku)
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
        options = list(options)
        keys = [getattr(o, "key", None) for o in options]
        # Al cambiar la lista de escuelas (p.ej. otro nivel), volver a la página 1.
        if keys != self._guided_school_option_keys:
            self._guided_school_page = 0
            self._guided_school_option_keys = keys
        self._guided_school_all_options = options
        self._render_guided_school_page()

    def _render_guided_school_page(self) -> None:
        """Dibuja solo la página actual de escuelas y actualiza el paginador."""
        page_options, page, total_pages = _paginate(
            self._guided_school_all_options, self._guided_school_page, _GUIDED_SCHOOLS_PER_PAGE
        )
        self._guided_school_page = page
        self.guided_school_buttons = self._rebuild_guided_option_grid(
            layout=self.guided_school_grid,
            options=page_options,
            selected_key=self._gfs.school,
            click_handler=self._handle_guided_school_selected,
        )
        self.guided_school_page_label.setText(f"Página {page + 1} / {total_pages}")
        self.guided_school_prev_button.setEnabled(page > 0)
        self.guided_school_next_button.setEnabled(page < total_pages - 1)
        # El paginador solo aparece si hay más de una página.
        self.guided_school_pager.setVisible(total_pages > 1)

    def _handle_guided_school_page(self, delta: int) -> None:
        self._guided_school_page += delta
        self._render_guided_school_page()

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
        sorted_cards = sorted(product_cards, key=lambda c: (c.key not in self._favorites, 0))
        key_set = frozenset(getattr(c, "key", None) for c in sorted_cards)
        # Al cambiar el conjunto de modelos (otro filtro), volver a la página 1.
        # Marcar favorito reordena pero no cambia el conjunto -> conserva la página.
        if key_set != self._guided_product_key_set:
            self._guided_product_page = 0
            self._guided_product_key_set = key_set
        self._guided_product_all_cards = sorted_cards
        self._render_guided_product_page()

    def _render_guided_product_page(self) -> None:
        """Dibuja solo la página actual de modelos y actualiza el paginador."""
        page_cards, page, total_pages = _paginate(
            self._guided_product_all_cards, self._guided_product_page, _GUIDED_MODELS_PER_PAGE
        )
        self._guided_product_page = page
        _clear_layout(self.guided_product_flow_layout)
        self.guided_product_buttons = {}
        for card in page_cards:
            product_btn = self._build_guided_product_button(card)
            product_btn.setChecked(self._gfs.product_key == card.key)
            product_btn.clicked.connect(lambda checked=False, selected=card.key: self._handle_guided_product_selected(selected))
            # Corazón como overlay dentro del botón
            is_fav = card.key in self._favorites
            heart_btn = QPushButton("♥" if is_fav else "♡", product_btn)
            heart_btn.setObjectName("favoriteOverlayButton")
            heart_btn.setFixedSize(26, 26)
            heart_btn.setCheckable(True)
            heart_btn.setChecked(is_fav)
            heart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            heart_btn.setToolTip("Quitar de favoritos" if is_fav else "Agregar a favoritos")
            heart_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; font-size: 16px;"
                " color: #c4b9a8; padding: 0; }"
                "QPushButton:checked { color: #c45425; }"
                "QPushButton:hover { color: #a84f2d; }"
            )
            heart_btn.clicked.connect(lambda checked=False, key=card.key: self._handle_toggle_favorite(key))
            # Posicionar en esquina superior derecha
            heart_btn.move(product_btn.width() - 30, 4)

            def _make_resize_handler(hb, pb, orig):
                def _on_resize(event):
                    orig(event)
                    hb.move(pb.width() - 30, 4)
                return _on_resize

            product_btn.resizeEvent = _make_resize_handler(heart_btn, product_btn, product_btn.resizeEvent)
            self.guided_product_flow_layout.addWidget(product_btn)
            self.guided_product_buttons[card.key] = product_btn

        self.guided_product_page_label.setText(f"Página {page + 1} / {total_pages}")
        self.guided_product_prev_button.setEnabled(page > 0)
        self.guided_product_next_button.setEnabled(page < total_pages - 1)
        # El paginador solo aparece si hay más de una página.
        self.guided_product_pager.setVisible(total_pages > 1)

    def _handle_guided_product_page(self, delta: int) -> None:
        self._guided_product_page += delta
        self._render_guided_product_page()

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

    def _authorize_with_employee_qr(self) -> str | None:
        """Muestra diálogo de escaneo QR. Retorna nombre del empleado si autorizado, None si no."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Autorización requerida")
        dialog.setModal(True)
        dialog.setMinimumWidth(320)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        lbl = QLabel("Escanea el QR del empleado autorizado para continuar.")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        code_input = QLineEdit()
        code_input.setPlaceholderText("Escanea el QR aquí")
        layout.addWidget(code_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        code_input.returnPressed.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        QTimer.singleShot(0, code_input.setFocus)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        raw = code_input.text()
        scanned = "".join(c for c in raw if c.isprintable()).strip()
        # QR scanner sends HID keycodes; Spanish keyboard maps : → Ñ, - → '
        scanned = scanned.replace("Ñ", ":").replace("ñ", ":").replace("'", "-")
        scanned = scanned.upper()
        if scanned.startswith("EMP:"):
            scanned = scanned[4:]
        if not scanned:
            return None
        if self.offline_mode:
            if not scanned.startswith("VEND-"):
                QMessageBox.warning(
                    self, "No autorizado", "Formato esperado: VEND-1, VEND-2, etc."
                )
                return None
            return scanned
        try:
            with get_session() as session:
                emp = session.execute(
                    select(Empleada).where(
                        func.lower(Empleada.codigo) == scanned.lower(),
                        Empleada.activo.is_(True),
                    )
                ).scalar_one_or_none()
            if emp is None:
                QMessageBox.warning(self, "No autorizado", "QR no reconocido o empleado inactivo.")
                return None
            return emp.nombre_completo
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error de autorización", str(exc))
            return None

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

    def _open_quick_kiosk(self) -> None:
        from pos_uniformes.ui.dialogs.quick_kiosk_dialog import QuickKioskDialog

        if not hasattr(self, "_quick_kiosk_dialog") or self._quick_kiosk_dialog is None:
            self._quick_kiosk_dialog = QuickKioskDialog(self)
        self._quick_kiosk_dialog.show()
        self._quick_kiosk_dialog.raise_()
        self._quick_kiosk_dialog.activateWindow()

    def _setup_anuncio_cartelera(self) -> None:
        """Crea el controlador de la cartelera y arranca el listener de anuncios.

        Nunca impide que la ventana funcione si algo falla (kiosko robusto).
        """
        try:
            from pos_uniformes.ui.helpers.anuncio_cartelera import AnuncioCartelera
            from pos_uniformes.services.anuncio_local_cache_service import load_anuncios_cache

            self._anuncio_cartelera = AnuncioCartelera(self)
            # Arranca con lo último cacheado (funciona aun sin conexión).
            self._anuncio_cartelera.set_anuncios(load_anuncios_cache())
            self._anuncio_cartelera.start()
        except Exception:  # noqa: BLE001
            self._anuncio_cartelera = None
            return

        # Si hay conexión, el watchdog ya refrescará; forzamos un primer refresco
        # pronto para no depender de su ciclo de 5 min al abrir.
        if not self.offline_mode:
            QTimer.singleShot(1_000, self._start_background_db_refresh)

        # Listener NOTIFY: refresca/avisa al instante cuando cambia un anuncio.
        try:
            from pos_uniformes.ui.helpers.anuncio_listener import AnuncioNotifyListener

            self._anuncio_listener = AnuncioNotifyListener(self)
            self._anuncio_listener.recibido.connect(self._on_anuncio_notify)
            self._anuncio_listener.start()
        except Exception:  # noqa: BLE001
            self._anuncio_listener = None

    def _enviar_heartbeat(self) -> None:
        """Registra/actualiza este satélite en la DB (off-thread, best-effort)."""
        import threading

        def _worker() -> None:
            try:
                from pos_uniformes.services.satellite_startup_service import probe_database_host

                if not probe_database_host():
                    return  # DB caída: no bloquear ni fallar ruidosamente
                from pos_uniformes.services.satellite_identity_service import (
                    get_satellite_id,
                    get_satellite_name,
                )
                from pos_uniformes.services.satelite_registry_service import registrar

                with get_session() as session:
                    registrar(session, get_satellite_id(), get_satellite_name())
                    session.commit()
            except Exception:  # noqa: BLE001 — presencia es best-effort
                pass

        threading.Thread(target=_worker, daemon=True, name="satellite-heartbeat").start()

    def _on_anuncio_notify(self, accion: str, anuncio_id: int) -> None:
        """Llega un NOTIFY del canal 'anuncio': recarga y, si aplica, avisa ya."""
        if accion == "inmediato" and anuncio_id:
            self._anuncio_inmediato_pendiente = anuncio_id
        self._start_background_db_refresh()

    def _on_anuncios_ready(self) -> None:
        """El cache de anuncios se refrescó: actualiza la cartelera (hilo de UI)."""
        cartelera = getattr(self, "_anuncio_cartelera", None)
        if cartelera is None:
            return
        from pos_uniformes.services.anuncio_local_cache_service import load_anuncios_cache

        anuncios = load_anuncios_cache()
        cartelera.set_anuncios(anuncios)
        pendiente = self._anuncio_inmediato_pendiente
        if pendiente:
            self._anuncio_inmediato_pendiente = None
            match = next((a for a in anuncios if a.get("id") == pendiente), None)
            if match:
                cartelera.mostrar_inmediato(match)

    def _open_satellite_admin(self) -> None:
        from pos_uniformes.ui.dialogs.satellite_admin_dialog import open_satellite_admin_dialog
        open_satellite_admin_dialog(self)

    def _open_dispatcher_panel(self) -> None:
        """Abre el panel de la cola del satélite (Ctrl+Shift+Q)."""
        from pos_uniformes.ui.dialogs.dispatcher_panel_dialog import DispatcherPanelDialog

        panel = getattr(self, "_dispatcher_panel", None)
        if panel is None:
            panel = DispatcherPanelDialog(self)
            panel.finished.connect(lambda _r: setattr(self, "_dispatcher_panel", None))
            self._dispatcher_panel = panel
            panel.show()
        else:
            panel.raise_()
            panel.activateWindow()

    def _open_pedido_board(self) -> None:
        """Abre el tablero de pedidos del satélite (Ctrl+Shift+P)."""
        from pos_uniformes.ui.dialogs.pedido_board_dialog import PedidoBoardDialog

        board = getattr(self, "_pedido_board", None)
        if board is None:
            board = PedidoBoardDialog(self)
            board.finished.connect(lambda _r: setattr(self, "_pedido_board", None))
            self._pedido_board = board
            board.show()
        else:
            board.raise_()
            board.activateWindow()

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
            row = self._find_row_by_sku(card.sku)
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
            from pos_uniformes.ui.helpers.quote_guided_catalog_helper import favorites_variant_sort_key
            family_rows.sort(key=favorites_variant_sort_key)

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
                row = self._find_row_by_sku(card.sku)
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
            selected_row = self._find_row_by_sku(sku)
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
        row = self._find_row_by_sku(card.sku)
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
        if self.offline_mode:
            # Sin conexion no hay lookup de clientes (get_session bloquearia
            # el connect_timeout completo); el escaneo se trata como SKU y la
            # ruta de SKU ya resuelve contra el catalogo local.
            self._add_quote_item_by_sku(scan_code, 1)
            self.quick_scan_input.clear()
            self.quick_scan_input.setFocus()
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

    def _handle_quick_search(self) -> None:
        """Ctrl+S: abre búsqueda rápida. En Venta Rápida agrega a la venta;
        en el resto, a consulta de kiosko o al presupuesto."""
        from pos_uniformes.ui.dialogs.quick_product_search_dialog import QuickProductSearchDialog

        if getattr(self, "current_page_key", None) == "quicksale":
            dialog = QuickProductSearchDialog(
                self, catalog_rows=self.catalog_snapshot_rows, kiosk_mode=False
            )
            added_skus: list[str] = []

            def _add_and_track(sku: str, qty: int) -> None:
                if self.quick_sale_widget.add_sku(sku, qty):
                    added_skus.append(sku)

            dialog.sku_selected.connect(_add_and_track)
            dialog.exec()
            # Igual que en caja: ofrecer imprimir etiquetas de lo agregado.
            if added_skus:
                self._offer_label_print_for_added_skus(added_skus)
            self.quick_sale_widget.focus_input()
            return

        dialog = QuickProductSearchDialog(self, catalog_rows=self.catalog_snapshot_rows, kiosk_mode=True)

        def _on_kiosk(sku: str, qty: int) -> None:
            self._set_page("kiosk")
            self.kiosk_scan_input.setText(sku)
            self.kiosk_qty_spin.setValue(max(1, qty))
            self._handle_lookup_scan()

        def _on_add_to_quote(sku: str, qty: int) -> None:
            self._add_quote_item_by_sku(sku, qty)

        dialog.sku_to_kiosk.connect(_on_kiosk)
        dialog.sku_selected.connect(_on_add_to_quote)
        dialog.exec()

    def _offer_label_print_for_added_skus(self, skus: list[str]) -> None:
        """Confirmación con checkboxes (como caja) e impresión de etiquetas."""
        from pos_uniformes.ui.dialogs.label_print_confirmation_dialog import (
            build_label_entries,
            open_label_print_confirmation,
        )

        entries = build_label_entries(skus, self._find_row_by_sku)
        selected, mode = open_label_print_confirmation(self, entries)
        if selected:
            self._print_labels_for_skus(selected, mode)

    def _print_labels_for_skus(self, skus: list[str], mode: str = "standard") -> None:
        from pos_uniformes.services.inventory_label_service import (
            render_inventory_label_from_cache_row,
        )

        failed: list[str] = []
        for sku in skus:
            row = self._find_row_by_sku(sku)
            if row is None:
                failed.append(sku)
                continue
            try:
                result = render_inventory_label_from_cache_row(
                    row, mode=mode, requested_copies=1
                )
                # El tipo elegido decide la impresora: Normal/Split → rollo
                # continuo; Label (dk1221) → troquelada. paper_mode = mode.
                if not self._print_satellite_label(
                    result.image_path, title=f"Etiqueta {sku}", copies=1,
                    paper_mode=mode,
                ):
                    failed.append(sku)
            except Exception:  # noqa: BLE001 — una etiqueta fallida no aborta el resto
                logger.exception("Error imprimiendo etiqueta de %s", sku)
                failed.append(sku)
        if failed:
            QMessageBox.warning(
                self,
                "Etiquetas",
                "No se pudieron imprimir: " + ", ".join(failed),
            )

    def _handle_lookup_scan(self) -> None:
        raw = self.kiosk_scan_input.text()
        sku = raw.strip().upper()
        if not sku:
            QMessageBox.warning(self, "SKU faltante", "Escanea o captura un SKU para consultarlo.")
            return
        # El gafete de una empleada (QR EMP:VEND-N) no es un producto: en
        # esta pestaña se ignora sin buscarlo (pedido de Daniel 2026-09-05).
        from pos_uniformes.services.employee_identity_service import (
            EmployeeIdentityService,
        )

        if EmployeeIdentityService.looks_like_employee_qr(raw):
            self.kiosk_scan_input.clear()
            self._set_status("Gafete ignorado — aquí se escanean productos.")
            QTimer.singleShot(0, self.kiosk_scan_input.setFocus)
            return
        fell_back_to_cache = False
        try:
            if self.offline_mode:
                snapshot = self._kiosk_lookup_from_cache(sku)
            else:
                try:
                    with get_session() as session:
                        snapshot = load_quote_kiosk_lookup_snapshot(session, sku=sku)
                except SQLAlchemyError as db_exc:
                    # La conexión con la PC principal se cayó (LAN inestable /
                    # Postgres reiniciado). En vez del traceback feo, usamos el
                    # catálogo guardado localmente — igual que en modo offline.
                    logger.warning("Consulta online falló, usando catálogo local: %s", db_exc)
                    snapshot = self._kiosk_lookup_from_cache(sku)
                    fell_back_to_cache = True
            self.lookup_snapshot = snapshot
            self.lookup_history = push_quote_kiosk_recent_scan(self.lookup_history, snapshot)
            self._apply_lookup_view(build_quote_kiosk_lookup_view(snapshot))
            self._refresh_recent_lookup_table()
            if fell_back_to_cache:
                self._set_status(f"{snapshot.sku} — precio del catalogo guardado (sin conexion).")
            else:
                self._set_status(f"{snapshot.sku} — precio del catalogo guardado.")
        except Exception as exc:  # noqa: BLE001
            self.lookup_snapshot = None
            friendly = str(exc)
            if isinstance(exc, SQLAlchemyError):
                friendly = "Sin conexion con la PC principal. Intenta de nuevo en unos segundos."
            self._apply_lookup_view(build_error_quote_kiosk_lookup_view(friendly))
            QMessageBox.warning(self, "Consulta no disponible", friendly)
        # Limpiar el cajón SIEMPRE (éxito o error) para que el siguiente
        # escaneo no se apile con un código previo que no existía.
        self.kiosk_scan_input.clear()
        self._apply_action_state()
        self.kiosk_scan_input.setFocus()

    def _kiosk_lookup_from_cache(self, sku: str) -> "QuoteKioskLookupSnapshot":
        """Construye el snapshot del kiosko buscando en catalog_snapshot_rows (sin DB)."""
        from decimal import Decimal as _Decimal

        normalized = sku.strip().upper()
        row = self._find_row_by_sku(normalized)
        if row is None:
            raise ValueError(f"No existe una presentacion activa para el SKU '{normalized}' en el catalogo guardado.")
        if not row.get("producto_activo") or not row.get("variante_activo"):
            raise ValueError(f"El SKU '{normalized}' esta inactivo en el catalogo guardado.")

        school = str(row.get("escuela_nombre") or "General")
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
        except SQLAlchemyError as db_exc:
            # Conexión caída: agregar desde el catálogo local en vez de fallar.
            logger.warning("Agregar online falló, usando catálogo local: %s", db_exc)
            self._add_quote_item_from_cache(normalized_sku, quantity)
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "No se pudo agregar", str(exc))
            return

        self._refresh_quote_cart_table()
        self.kiosk_scan_input.setFocus()
        self._set_status(result.feedback_message)

    def _add_quote_item_from_cache(self, normalized_sku: str, quantity: int) -> None:
        row = self._find_row_by_sku(normalized_sku)
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
                "tipo_pieza_nombre": str(row.get("tipo_pieza_nombre") or ""),
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
        index = normalize_cart_row_index(row_index, len(self.quote_cart))
        if index is None:
            return
        item = self.quote_cart[index]
        new_qty = max(1, int(item.get("cantidad") or 1) + delta)
        if self.offline_mode:
            item["cantidad"] = new_qty
        else:
            try:
                with get_session() as session:
                    update_sale_cart_item_quantity(
                        session,
                        sale_cart=self.quote_cart,
                        row_index=index,
                        new_quantity=new_qty,
                        variant_loader=PresupuestoService.obtener_variante_por_sku,
                        stock_validator=lambda _v, _c: None,
                    )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Cantidad no actualizada", str(exc))
                return
        self._refresh_quote_cart_table()

    def _remove_quote_item_at_index(self, row_index: int) -> None:
        index = normalize_cart_row_index(row_index, len(self.quote_cart))
        if index is None:
            return
        removed_line_item = dict(self.quote_cart[index])
        self.quote_cart.pop(index)
        restore_message = restore_sports_uniform_playera_price_if_needed(
            self.quote_cart,
            removed_line_item=removed_line_item,
        )
        self._refresh_quote_cart_table()
        if self.quote_cart:
            self.quote_cart_table.selectRow(min(index, len(self.quote_cart) - 1))
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
        if self.offline_mode:
            selected_item["cantidad"] = new_quantity
        else:
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

    def _handle_sidebar_clear_pieces(self) -> None:
        """Papelera de la barra 'Piezas agregadas': vacía el armado actual."""
        if not self.quote_cart:
            return  # nada que limpiar
        confirm = QMessageBox.question(
            self,
            "Limpiar piezas",
            "¿Quitar todas las piezas agregadas del presupuesto actual?",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._handle_clear_quote_cart()

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
        feedback = build_quote_guard_feedback(
            "save_quote",
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
            validity_at=local_day_window(self.quote_validity_input.date().toPyDate())[0],
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
        dialog.setModal(True)
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        intro = QLabel("Registra un cliente con nombre y telefono para vincularlo al presupuesto.")
        intro.setWordWrap(True)
        intro.setObjectName("subtleLine")
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
        layout.addWidget(intro)
        layout.addWidget(name_label)
        layout.addWidget(name_input)
        layout.addWidget(phone_label)
        layout.addWidget(phone_input)
        layout.addWidget(error_label)
        layout.addWidget(preview_label)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        name_input.setFocus()
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return {
            "nombre": name_input.text().strip(),
            "telefono": phone_input.text().strip(),
        }

    def _handle_quote_filters_changed(self) -> None:
        if self.offline_mode:
            # Los presupuestos locales no tienen estados que filtrar; solo se
            # re-pinta la lista local (sin tocar la DB, que bloquearia 5s).
            self._refresh_offline_quotes()
            return
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
                "tipo_pieza": str(item.get("tipo_pieza_nombre") or item.get("tipo_pieza", "")),
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

    # ── Tarifario por escuela ──────────────────────────────────────

    def _refresh_tariff_schools(self, session=None) -> None:
        previous = self.tariff_school_combo.currentData()
        self.tariff_school_combo.blockSignals(True)
        self.tariff_school_combo.clear()

        if session is not None:
            from pos_uniformes.services.school_tariff_service import list_schools_for_tariff
            schools = list_schools_for_tariff(session)
            for s in schools:
                # userData = (escuela_id, nivel_id) para poder filtrar al generar
                self.tariff_school_combo.addItem(s["display_name"], (s["escuela_id"], s["nivel_id"]))
        else:
            # Modo offline: extraer escuelas del cache local
            seen: set[str] = set()
            schools_offline: list[str] = []
            for row in self.catalog_snapshot_rows:
                name = str(row.get("escuela_nombre") or "").strip()
                if name and name not in seen:
                    seen.add(name)
                    schools_offline.append(name)
            schools_offline.sort()
            for name in schools_offline:
                self.tariff_school_combo.addItem(name, name)

        if previous is not None:
            for i in range(self.tariff_school_combo.count()):
                if self.tariff_school_combo.itemData(i) == previous:
                    self.tariff_school_combo.setCurrentIndex(i)
                    break
        self.tariff_school_combo.blockSignals(False)

    def _handle_generate_tariff(self) -> None:
        from pos_uniformes.services.school_tariff_text_service import build_school_tariff_text

        escuela_data = self.tariff_school_combo.currentData()
        if escuela_data is None:
            self._set_status("Selecciona una escuela primero.")
            return
        try:
            if self.offline_mode:
                tariff = self._build_tariff_from_cache(str(self.tariff_school_combo.currentText()))
            else:
                from pos_uniformes.services.school_tariff_service import build_school_tariff
                escuela_id, nivel_id = escuela_data if isinstance(escuela_data, tuple) else (escuela_data, None)
                with get_session() as session:
                    tariff = build_school_tariff(session, escuela_id, nivel_id=nivel_id)
            business_name = _load_business_name()
            business_phone = _load_business_phone()
            text = build_school_tariff_text(
                tariff=tariff,
                business_name=business_name,
                business_phone=business_phone,
            )
            self._current_tariff = tariff
            # Vista previa HTML moderna; plain text solo va a impresión
            try:
                from pos_uniformes.services.school_tariff_preview_service import build_school_tariff_html
                self.tariff_preview.setHtml(build_school_tariff_html(
                    tariff=tariff,
                    business_name=business_name,
                    business_phone=business_phone,
                ))
            except Exception:
                self.tariff_preview.setPlainText(text)
            self.tariff_print_button.setEnabled(True)
            n = len(tariff.get("productos", []))
            self._set_status(f"Tarifario generado: {tariff['escuela_nombre']} — {n} productos.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al generar tarifario", str(exc))

    def _build_tariff_from_cache(self, escuela_nombre: str) -> dict:
        """Construye tarifario desde catalog_snapshot_rows (modo offline)."""
        from decimal import Decimal
        from pos_uniformes.services.school_tariff_service import (
            _merge_same_price_products,
            _talla_sort_key,
            _tariff_product_sort_key,
        )

        rows = [
            r for r in self.catalog_snapshot_rows
            if str(r.get("escuela_nombre") or "").strip() == escuela_nombre
        ]

        # Agrupar por nombre_base (producto)
        import re
        products: dict[str, dict] = {}
        for r in rows:
            name = str(r.get("producto_nombre_base") or r.get("producto_nombre") or "")
            tipo_pieza = str(r.get("tipo_pieza_nombre") or "")
            # Limpiar nombre de escuela y "Ad hoc"
            cleaned = re.sub(re.escape(escuela_nombre), "", name, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"\bAd\s+hoc\b", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            genero = str(r.get("producto_genero") or "").strip().upper()
            color = str(r.get("color") or "").strip()
            key = cleaned or name
            if key not in products:
                products[key] = {"tipo_pieza": tipo_pieza, "tallas": [], "genero": genero, "colores": set()}
            products[key]["tallas"].append({
                "talla": str(r.get("talla") or "U"),
                "precio": Decimal(str(r.get("precio_venta") or 0)),
            })
            if color:
                products[key]["colores"].add(color)

        result_products: list[dict] = []
        for nombre, data in products.items():
            # Deduplicar y ordenar tallas
            seen: set[str] = set()
            unique: list[dict] = []
            for t in data["tallas"]:
                if t["talla"] not in seen:
                    seen.add(t["talla"])
                    unique.append(t)
            unique.sort(key=lambda t: _talla_sort_key(t["talla"]))
            result_products.append({
                "nombre": nombre,
                "tipo_pieza": data["tipo_pieza"],
                "tallas": unique,
                "genero": data.get("genero", ""),
                "colores": sorted(data.get("colores", set())),
            })

        result_products.sort(key=lambda p: _tariff_product_sort_key(p.get("tipo_pieza", "")))
        merged = _merge_same_price_products(result_products)

        return {"escuela_nombre": escuela_nombre, "productos": merged}

    def _handle_print_tariff(self) -> None:
        if not self._current_tariff:
            self._set_status("Genera un tarifario primero.")
            return

        # ── Diálogo táctil de selección de género ───────────────────────
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
        )
        from PyQt6.QtCore import Qt

        _SS_CARD = (
            "QFrame { background:#FFF8F5; border:2px solid #E2C9BE;"
            " border-radius:14px; }"
        )
        _SS_CARD_PRESSED = (
            "QFrame { background:#7B2D14; border:3px solid #C96030;"
            " border-radius:14px; }"
        )

        genero_result: list = [None]

        class _GenderCard(QFrame):
            def __init__(self_, icon_str, label_str, value):
                super().__init__()
                self_._value = value
                self_.setCursor(Qt.CursorShape.PointingHandCursor)
                self_.setFixedSize(148, 172)
                self_.setStyleSheet(_SS_CARD)
                vbox = QVBoxLayout(self_)
                vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
                vbox.setSpacing(6)
                vbox.setContentsMargins(8, 16, 8, 16)
                lbl_icon = QLabel(icon_str)
                lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_icon.setStyleSheet(
                    "font-size:52px; background:transparent; border:none;"
                )
                lbl_text = QLabel(label_str)
                lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_text.setWordWrap(True)
                lbl_text.setStyleSheet(
                    "font-size:13px; font-weight:bold;"
                    " background:transparent; border:none; color:#4A1505;"
                )
                vbox.addWidget(lbl_icon)
                vbox.addWidget(lbl_text)

            def mousePressEvent(self_, _ev):
                self_.setStyleSheet(_SS_CARD_PRESSED)
                genero_result[0] = self_._value
                dlg.accept()

        dlg = QDialog(self)
        dlg.setWindowTitle("¿Para quién es el tarifario?")
        dlg.setFixedWidth(520)

        outer = QVBoxLayout(dlg)
        outer.setSpacing(20)
        outer.setContentsMargins(24, 24, 24, 20)

        ttl = QLabel("¿Para quién es el tarifario?")
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setStyleSheet(
            "font-size:17px; font-weight:bold; color:#4A1505; margin-bottom:4px;"
        )
        outer.addWidget(ttl)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)
        for icon_s, label_s, val in [
            ("👨‍👩‍👧‍👦", "Ambos\n(Niño y Niña)", None),
            ("👦", "Solo\nNiño", "NIÑO"),
            ("👧", "Solo\nNiña", "NIÑA"),
        ]:
            cards_row.addWidget(_GenderCard(icon_s, label_s, val))
        outer.addLayout(cards_row)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFlat(True)
        cancel_btn.setStyleSheet(
            "color:#A07060; font-size:12px; padding:6px 16px;"
        )
        cancel_btn.clicked.connect(dlg.reject)
        outer.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        genero_filter: str | None = genero_result[0]

        # ── Regenerar texto con el filtro elegido ───────────────────────
        from pos_uniformes.services.school_tariff_text_service import build_school_tariff_text
        content = build_school_tariff_text(
            tariff=self._current_tariff,
            business_name=_load_business_name(),
            business_phone=_load_business_phone(),
            genero_filter=genero_filter,
        )
        from pos_uniformes.ui.dialogs.printable_text_dialog import open_printable_text_dialog
        open_printable_text_dialog(
            parent=self,
            title="Tarifario",
            content=content,
        )

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
                _hint = ""
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
        self.kiosk_add_button.setEnabled(self.lookup_snapshot is not None and self._can_build_cart())
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

        # Precio en SU PROPIA fila: con "c/u" ensanchaba la tarjeta y
        # empujaba los botones ± fuera del sidebar (bug de 2 piezas).
        price_label = QLabel(
            f"${subtotal}" + (f"  (${unit_price} c/u)" if quantity > 1 else "")
        )
        price_label.setObjectName("satSidebarItemQty")
        price_label.setWordWrap(True)

        minus_btn = QPushButton("−")
        minus_btn.setObjectName("sidebarItemRemoveButton")
        minus_btn.setFixedSize(34, 34)
        minus_btn.clicked.connect(lambda checked=False, index=row_index: self._change_sidebar_item_quantity(index, -1))

        qty_label = QLabel(str(quantity))
        qty_label.setObjectName("satSidebarItemQty")
        qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qty_label.setFixedWidth(28)

        plus_btn = QPushButton("+")
        plus_btn.setObjectName("sidebarItemRemoveButton")
        plus_btn.setFixedSize(34, 34)
        plus_btn.clicked.connect(lambda checked=False, index=row_index: self._change_sidebar_item_quantity(index, 1))

        qty_row = QHBoxLayout()
        qty_row.setContentsMargins(0, 0, 0, 0)
        qty_row.setSpacing(6)
        qty_row.addStretch()
        qty_row.addWidget(minus_btn)
        qty_row.addWidget(qty_label)
        qty_row.addWidget(plus_btn)

        layout.addLayout(name_row)
        if meta_parts:
            layout.addWidget(meta_label)
        layout.addWidget(price_label)
        layout.addLayout(qty_row)
        card.setLayout(layout)

        card.double_clicked.connect(self._show_cart_popup)
        return card

    def _show_cart_popup(self) -> None:
        """Popup "Piezas agregadas" — rediseño táctil (2026-09-06): tabla
        limpia (sin columna Color), cantidad con −/+ grandes, bote por
        renglón y solo las acciones útiles: Imprimir, WhatsApp, Limpiar y
        Cerrar. "Guardar borrador" y "Ticket de venta" se RETIRARON (Daniel
        no los usa; sus handlers siguen vivos por si se reviven)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Piezas agregadas")
        dlg.setMinimumWidth(820)
        dlg.setMinimumHeight(520)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
            "QTableWidget { background: #fffdf8; border: 1px solid #ddd0c0;"
            "  border-radius: 12px; font-size: 16px; color: #2c2a27; }"
            "QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #f0e6db; }"
            "QTableWidget::item:selected { background: #f7e3d8; color: #2c2a27; }"
            "QHeaderView::section { background: #f4ede2; color: #73341c;"
            "  font-weight: 800; font-size: 13px; padding: 10px 10px; border: none;"
            "  border-bottom: 2px solid #ddd0c0; }"
        )
        dlg_layout = QVBoxLayout()
        dlg_layout.setContentsMargins(18, 16, 18, 16)
        dlg_layout.setSpacing(12)

        # --- Resumen superior ---
        summary_frame = QFrame()
        summary_frame.setStyleSheet(
            "QFrame { background: #fffdf8; border: 1px solid #ddd0c0; border-radius: 14px; }"
        )
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(24)
        lines_label = QLabel()
        pieces_label = QLabel()
        for lbl in (lines_label, pieces_label):
            lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #5f594f; border: none;")
        summary_total_label = QLabel()
        summary_total_label.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: #87492c; border: none;"
        )
        summary_layout.addWidget(lines_label)
        summary_layout.addWidget(pieces_label)
        summary_layout.addStretch()
        summary_layout.addWidget(summary_total_label)
        summary_frame.setLayout(summary_layout)

        # --- Tabla ---
        columns = ["Producto", "Talla", "SKU", "Cantidad", "Precio", "Subtotal", ""]
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, width in ((1, 80), (2, 130), (3, 170), (4, 110), (5, 120), (6, 64)):
            table.setColumnWidth(col, width)
        # Fila = botones(40) + padding(6+6) + holgura (misma lección del carrito)
        _ALTO_FILA = 56

        _BTN_QTY = (
            "QPushButton { background: #ffffff; color: #2c2a27;"
            "  border: 1.5px solid #ddd0c0; border-radius: 10px;"
            "  font-size: 20px; font-weight: 800; }"
            "QPushButton:pressed { background: #f1e6d6; }"
        )
        _BTN_DEL = (
            "QPushButton { background: #ffffff; color: #a33b25;"
            "  border: 1.5px solid #e2b7ad; border-radius: 10px;"
            "  font-size: 18px; font-weight: 800; }"
            "QPushButton:pressed { background: #fde3dd; }"
        )

        def _refresh_table():
            table.setRowCount(0)
            total = Decimal("0")
            total_pieces = 0
            for original_idx, item in enumerate(self.quote_cart):
                qty = max(int(item.get("cantidad") or 0), 0)
                unit_price = Decimal(str(item.get("precio_unitario") or "0")).quantize(Decimal("0.01"))
                subtotal = (unit_price * Decimal(qty)).quantize(Decimal("0.01"))
                total += subtotal
                total_pieces += qty
                pname = str(
                    item.get("producto_nombre") or item.get("descripcion") or item.get("sku") or "Producto"
                )
                talla = str(item.get("talla") or "—").strip()
                sku = str(item.get("sku") or "—").strip()

                row = table.rowCount()
                table.insertRow(row)
                values = [pname, talla, sku, "", f"${unit_price:,.2f}", f"${subtotal:,.2f}"]
                for col_idx, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    align = Qt.AlignmentFlag.AlignVCenter | (
                        Qt.AlignmentFlag.AlignRight if col_idx >= 4
                        else Qt.AlignmentFlag.AlignCenter if col_idx == 1
                        else Qt.AlignmentFlag.AlignLeft
                    )
                    cell.setTextAlignment(align)
                    if col_idx == 5:
                        font = cell.font(); font.setBold(True); cell.setFont(font)
                    table.setItem(row, col_idx, cell)

                # Cantidad: − [n] + (tamaño dedo)
                qty_widget = QWidget()
                qty_hl = QHBoxLayout(qty_widget)
                qty_hl.setContentsMargins(0, 0, 0, 0)
                qty_hl.setSpacing(4)
                qty_hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                minus_btn = QPushButton("−")
                plus_btn = QPushButton("+")
                for b in (minus_btn, plus_btn):
                    b.setFixedSize(44, 40)
                    b.setAutoDefault(False)
                    b.setStyleSheet(_BTN_QTY)
                qty_lbl = QLabel(str(qty))
                qty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                qty_lbl.setFixedWidth(34)
                qty_lbl.setStyleSheet("font-weight: 800; font-size: 18px; color: #2c2a27;")

                # clicked pasa checked como primer argumento posicional:
                # sin absorberlo, index recibiría False (== fila 0).
                def _on_minus(checked=False, index=original_idx):
                    self._change_sidebar_item_quantity(index, -1)
                    _refresh_table()

                def _on_plus(checked=False, index=original_idx):
                    self._change_sidebar_item_quantity(index, 1)
                    _refresh_table()

                minus_btn.clicked.connect(_on_minus)
                plus_btn.clicked.connect(_on_plus)
                qty_hl.addWidget(minus_btn)
                qty_hl.addWidget(qty_lbl)
                qty_hl.addWidget(plus_btn)
                table.setCellWidget(row, 3, qty_widget)

                # Eliminar línea
                remove_holder = QWidget()
                rh = QHBoxLayout(remove_holder)
                rh.setContentsMargins(0, 0, 0, 0)
                rh.setAlignment(Qt.AlignmentFlag.AlignCenter)
                remove_btn = QPushButton("")
                remove_btn.setFixedSize(44, 40)
                remove_btn.setAutoDefault(False)
                remove_btn.setStyleSheet(_BTN_DEL)
                remove_btn.setToolTip("Quitar esta pieza")
                try:
                    remove_btn.setIcon(_icon_from_asset("kiosk_icons/trash.svg"))
                    remove_btn.setIconSize(QSize(18, 18))
                except Exception:  # noqa: BLE001
                    remove_btn.setText("✕")

                def _on_remove(checked=False, index=original_idx):
                    self._remove_quote_item_at_index(index)
                    _refresh_table()

                remove_btn.clicked.connect(_on_remove)
                rh.addWidget(remove_btn)
                table.setCellWidget(row, 6, remove_holder)
                table.setRowHeight(row, _ALTO_FILA)

            n_lines = len(self.quote_cart)
            lines_label.setText(f"{n_lines} línea{'s' if n_lines != 1 else ''}")
            pieces_label.setText(f"{total_pieces} pieza{'s' if total_pieces != 1 else ''}")
            summary_total_label.setText(f"Total: ${total.quantize(Decimal('0.01')):,.2f}")
            if not self.quote_cart:
                lines_label.setText("Presupuesto vacío")
                pieces_label.setText("")
                summary_total_label.setText("$0.00")

        _refresh_table()

        # --- Acciones (solo las útiles) ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        _post_action = None

        def _close_and_run(action):
            nonlocal _post_action
            _post_action = action
            dlg.accept()

        _BTN_PRIMARIO = (
            "QPushButton { background: #a84f2d; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 58px; padding: 0 26px;"
            "  font-size: 17px; font-weight: 800; }"
            "QPushButton:pressed { background: #8a4326; }"
        )
        _BTN_SUAVE = (
            "QPushButton { background: #f8f2e9; color: #73341c;"
            "  border: 1px solid #ddd0c0; border-radius: 14px; min-height: 58px;"
            "  padding: 0 22px; font-size: 16px; font-weight: 700; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        _BTN_PELIGRO = (
            "QPushButton { background: #ffffff; color: #a33b25;"
            "  border: 1.5px solid #e2b7ad; border-radius: 14px; min-height: 58px;"
            "  padding: 0 22px; font-size: 16px; font-weight: 700; }"
            "QPushButton:pressed { background: #fde3dd; }"
        )

        print_btn = QPushButton("🖨  Imprimir")
        print_btn.setStyleSheet(_BTN_PRIMARIO)
        print_btn.clicked.connect(lambda: _close_and_run(self._handle_print_cart))

        whatsapp_btn = QPushButton("WhatsApp")
        whatsapp_btn.setStyleSheet(_BTN_SUAVE)
        whatsapp_btn.clicked.connect(lambda: _close_and_run(self._handle_open_quote_whatsapp))

        clear_btn = QPushButton("Limpiar")
        clear_btn.setStyleSheet(_BTN_PELIGRO)

        def _handle_clear():
            confirm = QMessageBox.question(
                dlg,
                "Limpiar presupuesto",
                "¿Eliminar todas las piezas del presupuesto actual?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.quote_cart.clear()
                _refresh_table()
                self._refresh_quote_cart_table()

        clear_btn.clicked.connect(_handle_clear)

        close_btn = QPushButton("Cerrar")
        close_btn.setStyleSheet(_BTN_SUAVE)
        close_btn.clicked.connect(dlg.accept)
        for b in (print_btn, whatsapp_btn, clear_btn, close_btn):
            b.setAutoDefault(False)

        actions_layout.addWidget(print_btn, 2)
        actions_layout.addWidget(whatsapp_btn, 1)
        actions_layout.addWidget(clear_btn, 1)
        actions_layout.addStretch(1)
        actions_layout.addWidget(close_btn, 1)

        dlg_layout.addWidget(summary_frame)
        dlg_layout.addWidget(table, 1)
        dlg_layout.addLayout(actions_layout)
        dlg.setLayout(dlg_layout)
        dlg.exec()
        if _post_action is not None:
            _post_action()

    def _apply_lookup_view(self, lookup_view) -> None:
        lookup_row = None
        if self.lookup_snapshot is not None:
            lookup_row = self._find_row_by_sku(self.lookup_snapshot.sku)
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
        paper_mode: str = "die_cut",
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
        if sys.platform.startswith("win"):
            from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
                print_inventory_label_via_windows,
            )
            # Prioridad 1: config local de impresoras de etiquetas por modo
            # (menú admin). Normal/Split/Continua → una impresora, Label → otra.
            from pos_uniformes.services.label_printer_settings_cache_service import (
                load_label_printer_settings,
                resolve_label_printer_for_mode,
            )
            normal_printer, label_printer = load_label_printer_settings()
            preferred_printer = resolve_label_printer_for_mode(
                paper_mode, normal_printer=normal_printer, label_printer=label_printer
            )
            # Prioridad 2 (sin config local): impresora preferida de la BD.
            if not preferred_printer and not self.offline_mode:
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
                paper_mode=paper_mode,
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
        selected_row = self._find_row_by_sku(sku)
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

            def _render_label_offline(mode: str, requested_copies: int, show_price: bool | None = None) -> "object":
                return render_inventory_label_from_cache_row(
                    offline_render_state["row"], mode=mode, requested_copies=requested_copies, show_price=show_price,
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
                    paper_mode=mode,
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

        def _render_label(mode: str, requested_copies: int, show_price: bool | None = None) -> "object":
            with get_session() as session:
                return render_inventory_label(
                    session,
                    render_state["variant_id"],
                    mode=mode,
                    requested_copies=requested_copies,
                    show_price=show_price,
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
                paper_mode=mode,
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
        "bachillerato": "kiosk_icons/level_prepa.svg",
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


def _load_business_name() -> str:
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import BusinessSettingsService
        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            return config.nombre_negocio or "MAXIMODA"
    except Exception:  # noqa: BLE001
        return "MAXIMODA"


def _load_business_phone() -> str:
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import BusinessSettingsService
        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            return str(getattr(config, "telefono", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _build_snapshot_ticket_text(snapshot: QuoteDetailSnapshot) -> str:
    from pos_uniformes.services.quote_text_service import DEFAULT_QUOTE_TERMS_LINES
    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH as _W,
        tk_bot, tk_center, tk_dbl, tk_field, tk_fmt,
        tk_line, tk_mid, tk_product_price, tk_row, tk_top,
    )

    _IW = _W - 4
    biz = _load_business_name()
    lines: list[str] = []

    # — Encabezado —
    lines.append(biz.center(_W))
    lines.append("Presupuesto".center(_W))
    lines.append("")
    lines.append("ESTE NO ES UN COMPROBANTE".center(_W))
    lines.append("FISCAL NI DE COMPRA".center(_W))
    lines.append("Precios solo de referencia".center(_W))

    # — Datos —
    lines.append(tk_top())
    tk_field("Folio:", snapshot.folio, lines)
    tk_field("Estado:", snapshot.status_label, lines)
    tk_field("Cliente:", snapshot.customer_label, lines)
    if snapshot.phone_text and snapshot.phone_text.lower() != "sin telefono":
        tk_field("Telefono:", snapshot.phone_text, lines)
    if snapshot.validity_label and snapshot.validity_label.lower() != "sin vigencia":
        tk_field("Vigencia:", snapshot.validity_label, lines)

    # — Piezas (ordenadas por tipo de pieza) —
    lines.append(tk_mid())
    lines.append(tk_center("PIEZAS"))
    lines.append(tk_mid())
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    sorted_details = sorted(
        snapshot.detail_rows,
        key=lambda d: _tariff_product_sort_key(getattr(d, "tipo_pieza", "") or ""),
    )
    first_detail = True
    for detail in sorted_details:
        unit_price = Decimal(str(detail.unit_price)).quantize(Decimal("0.01"))
        subtotal = Decimal(str(detail.subtotal)).quantize(Decimal("0.01"))
        talla = str(detail.size_label or "").strip()
        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(str(detail.description), width=_IW) or [str(detail.description)]:
            lines.append(tk_line(dl))
        if talla and talla != "-":
            lines.append(tk_line(f"Talla: {talla}"))
        tk_product_price(f"{detail.quantity} x ${unit_price}", f"${subtotal}", lines)

    # — Total —
    lines.append(tk_dbl())
    lines.append(tk_row("PRESUPUESTO ESTIMADO:", f"${tk_fmt(snapshot.total)}"))
    lines.append(tk_bot())

    # — Observaciones y términos —
    if snapshot.notes_text and snapshot.notes_text.lower() != "sin observaciones.":
        lines.append("")
        lines.append("Observaciones:")
        lines.extend(textwrap.wrap(snapshot.notes_text, width=_W))
    lines.append("")
    lines.append("Terminos y condiciones")
    lines.append("─" * _W)
    all_terms = list(DEFAULT_QUOTE_TERMS_LINES)
    promo_line = all_terms.pop() if all_terms else ""
    for term_line in all_terms:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])
    if promo_line:
        lines.append("")
        lines.append("─" * _W)
        for wrapped in textwrap.wrap(promo_line, width=_W):
            lines.append(wrapped.center(_W))
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
    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH as _W,
        tk_bot, tk_center, tk_dbl, tk_field, tk_fmt,
        tk_line, tk_mid, tk_product_price, tk_row, tk_top,
    )

    _IW = _W - 4
    biz = _load_business_name()
    lines: list[str] = []

    # — Encabezado —
    lines.append(biz.center(_W))
    lines.append("Presupuesto".center(_W))
    lines.append("")
    lines.append("ESTE NO ES UN COMPROBANTE".center(_W))
    lines.append("FISCAL NI DE COMPRA".center(_W))
    lines.append("Precios solo de referencia".center(_W))

    # — Datos —
    lines.append(tk_top())
    tk_field("Folio:", folio, lines)
    tk_field("Cliente:", client_name, lines)
    if validity_date is not None:
        try:
            tk_field("Vigencia:", validity_date.strftime("%d/%m/%Y"), lines)
        except Exception:  # noqa: BLE001
            pass

    # — Piezas (ordenadas por tipo de pieza) —
    lines.append(tk_mid())
    lines.append(tk_center("PIEZAS"))
    lines.append(tk_mid())
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    sorted_cart = sorted(
        cart,
        key=lambda item: _tariff_product_sort_key(
            str(item.get("tipo_pieza_nombre") or item.get("tipo_pieza", ""))
        ),
    )
    first_detail = True
    for item in sorted_cart:
        qty = int(item["cantidad"])
        unit_price = Decimal(str(item["precio_unitario"])).quantize(Decimal("0.01"))
        subtotal = (unit_price * qty).quantize(Decimal("0.01"))
        description = str(item.get("producto_nombre") or item.get("sku", ""))
        talla = str(item.get("talla") or "").strip()
        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(description, width=_IW) or [description]:
            lines.append(tk_line(dl))
        if talla and talla != "-":
            lines.append(tk_line(f"Talla: {talla}"))
        tk_product_price(f"{qty} x ${unit_price}", f"${subtotal}", lines)

    # — Total —
    lines.append(tk_dbl())
    lines.append(tk_row("PRESUPUESTO ESTIMADO:", f"${tk_fmt(total)}"))
    # Mínimo para apartar (25% con la regla de redondeo de caja) — mismo dato
    # que muestra el ticket de apartado de Venta Rápida.
    from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding
    _LAYAWAY_MIN_PCT = Decimal("25")
    minimo_apartado = resolve_sale_rounding(
        (Decimal(str(total)) * _LAYAWAY_MIN_PCT / Decimal("100")).quantize(Decimal("0.01"))
    ).collected_total
    lines.append(tk_mid())
    lines.append(tk_row(f"Apartado minimo ({_LAYAWAY_MIN_PCT:.0f}%):", f"${tk_fmt(minimo_apartado)}"))
    lines.append(tk_bot())

    # — Observaciones y términos —
    if notes:
        lines.append("")
        lines.append("Observaciones:")
        lines.extend(textwrap.wrap(notes, width=_W))
    lines.append("")
    lines.append("Terminos y condiciones")
    lines.append("─" * _W)
    all_terms = list(DEFAULT_QUOTE_TERMS_LINES)
    promo_line = all_terms.pop() if all_terms else ""
    for term_line in all_terms:
        if term_line == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(term_line, width=_W) or [""])
    if promo_line:
        lines.append("")
        lines.append("─" * _W)
        for wrapped in textwrap.wrap(promo_line, width=_W):
            lines.append(wrapped.center(_W))
    return "\n".join(lines)


def _build_sale_ticket_text(
    *,
    authorized_by: str,
    cart: list[dict],
    total: object,
) -> str:
    import datetime

    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH as _W,
        tk_bot, tk_center, tk_dbl, tk_field, tk_fmt,
        tk_line, tk_mid, tk_product_price, tk_row, tk_top,
    )

    _IW = _W - 4
    biz = _load_business_name()
    lines: list[str] = []

    lines.append(biz.center(_W))
    lines.append("Ticket de Venta".center(_W))
    lines.append("")

    lines.append(tk_top())
    now = datetime.datetime.now()
    tk_field("Fecha:", now.strftime("%d/%m/%Y %H:%M"), lines)
    tk_field("Autorizado:", authorized_by, lines)

    lines.append(tk_mid())
    lines.append(tk_center("PIEZAS"))
    lines.append(tk_mid())
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    sorted_cart = sorted(
        cart,
        key=lambda item: _tariff_product_sort_key(
            str(item.get("tipo_pieza_nombre") or item.get("tipo_pieza", ""))
        ),
    )
    first_detail = True
    for item in sorted_cart:
        qty = int(item["cantidad"])
        unit_price = Decimal(str(item["precio_unitario"])).quantize(Decimal("0.01"))
        subtotal = (unit_price * qty).quantize(Decimal("0.01"))
        description = str(item.get("producto_nombre") or item.get("sku", ""))
        talla = str(item.get("talla") or "").strip()
        if not first_detail:
            lines.append(tk_mid())
        first_detail = False
        for dl in textwrap.wrap(description, width=_IW) or [description]:
            lines.append(tk_line(dl))
        if talla and talla != "-":
            lines.append(tk_line(f"Talla: {talla}"))
        tk_product_price(f"{qty} x ${unit_price}", f"${subtotal}", lines)

    lines.append(tk_dbl())
    lines.append(tk_row("TOTAL:", f"${tk_fmt(total)}"))
    lines.append(tk_bot())

    lines.append("")
    lines.append("Terminos y Condiciones".center(_W))
    _SALE_TERMS = (
        "1. Revise su mercancia antes de retirarse del establecimiento.\n"
        "2. Tiene 15 dias naturales para realizar cambios presentando este ticket."
        " La prenda debe estar en buen estado y con sus etiquetas.\n"
        "3. Conserve este ticket como comprobante de pago.\n"
        "4. Para cualquier aclaracion, presente este ticket.\n"
        "5. No se aceptan devoluciones.\n"
        "6. Para solicitar factura, presente este ticket y sus datos fiscales."
    )
    for term_line in _SALE_TERMS.split("\n"):
        lines.extend(textwrap.wrap(term_line, width=_W, subsequent_indent="   "))

    lines.append("")
    lines.append("Gracias por su compra.".center(_W))

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
        f"Presupuesto estimado: ${Decimal(str(total)).quantize(Decimal('0.01'))}",
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
    "chaleco",    # Chaleco
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
