"""Venta Rápida — escaneo rápido con lista editable y gate de empleada."""

from __future__ import annotations

import logging
import re
import textwrap
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Empleada
from pos_uniformes.services.libreta_service import (
    TERMINAL_COMMISSION_PERCENT as _TERMINAL_COMMISSION,
)
from pos_uniformes.services.quote_kiosk_lookup_service import (
    QuoteKioskLookupSnapshot,
    load_quote_kiosk_lookup_snapshot,
)
from sqlalchemy import select

_logger = logging.getLogger(__name__)

from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.services.business_info_cache_service import (
    load_business_info as load_business_info_cache,
    save_business_info as save_business_info_cache,
)
from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets
from pos_uniformes.ui.helpers.quick_sale_cliente_helper import ClienteRapidoMixin
from pos_uniformes.ui.helpers.quick_sale_programa_helper import ProgramaClienteMixin
from pos_uniformes.ui.helpers.quick_sale_compradora_helper import CompradoraEmpleadaMixin
from pos_uniformes.ui.helpers.quick_sale_monedero_helper import (
    MonederoVentaMixin,
    lineas_ticket_monedero,
)
from pos_uniformes.ui.helpers.quick_sale_sports_uniform_helper import (
    adapt_cache_row,
    build_promo_playera_item,
    load_playera_candidates_from_rows,
    mark_promo_base_item,
    restore_promo_playera_after_base_removed,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    is_deportivo_two_piece_variant,
    resolve_sale_scan_variants,
)
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_CHAR_WIDTH as _TW,
    tk_bot,
    tk_center,
    tk_dbl_bot,
    tk_dbl_row,
    tk_dbl_top,
    tk_dbl,
    tk_field,
    tk_fmt,
    tk_line,
    tk_mid,
    tk_product_price,
    tk_row,
    tk_top,
)

_TIW = _TW - 4


def mezclar_colores(base: str, encima: str, cuanto: float) -> str:
    """Un color a medio camino entre otros dos. `cuanto` 0 = base, 1 = encima.

    Existe para que la ayuda de la tarjeta de escaneo se tiña de temporada sin
    quedar del mismo color que el título: si los dos van igual, los renglones
    se leen como un bloque y deja de verse cuál manda."""
    try:
        from PyQt6.QtGui import QColor

        a, b = QColor(base), QColor(encima)
        if not (a.isValid() and b.isValid()):
            return base
        t = max(0.0, min(1.0, float(cuanto)))
        return QColor(
            round(a.red() + (b.red() - a.red()) * t),
            round(a.green() + (b.green() - a.green()) * t),
            round(a.blue() + (b.blue() - a.blue()) * t),
        ).name()
    except Exception:  # noqa: BLE001 — sin mezcla, el gris de siempre
        return base


def _botones_sin_cortar(*botones) -> None:
    """QMessageBox reparte a sus botones menos ancho del que piden con la letra
    del kiosko: «Cerrar (queda pendiente)» salía como «rar (queda pendie»
    (prueba en tienda 2026-11-09; pasa igual con el estilo de Windows). Cada
    botón queda, como mínimo, del ancho de su propio texto."""
    for boton in botones:
        try:
            boton.ensurePolished()
            boton.setMinimumWidth(boton.sizeHint().width())
        except Exception:  # noqa: BLE001 — un botón angosto no detiene el aviso
            pass


def _temporada_de_hoy():
    """La temporada del calendario, o None. Nunca estorba si algo falla."""
    try:
        from pos_uniformes.services.temporada_service import actual

        return actual()
    except Exception:  # noqa: BLE001 — un adorno no puede impedir que se venda
        return None

if TYPE_CHECKING:
    from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

# ── Colores ──────────────────────────────────────────────────────────────────

_BRAND = "#87492c"
_BRAND_DARK = "#5c3019"
_BRAND_LIGHT = "#f5ebe0"
_WARM_BG = "#fdf8f3"
_CARD_BG = "#ffffff"
_BORDER = "#e8d5c4"
_BORDER_FOCUS = "#c4956a"
_MUTED = "#9a8a7c"
_TEXT = "#3d2e22"
_DANGER = "#b9402e"

# ── Estilos ──────────────────────────────────────────────────────────────────

_GATE_STYLE = f"""
QWidget#gateRoot {{ background: {_WARM_BG}; }}
QFrame#gateCard {{
    background: {_CARD_BG};
    border: 1.5px solid {_BORDER};
    border-radius: 16px;
}}
QLabel#gateEmoji {{ font-size: 44px; }}
QLabel#gateTitle {{
    font-size: 24px; font-weight: 800; color: {_TEXT};
}}
QLabel#gateHint {{
    font-size: 14px; color: {_MUTED};
}}
QLineEdit#gateInput {{
    font-size: 20px; padding: 16px 22px;
    border: 1.5px solid {_BORDER}; border-radius: 12px;
    background: {_WARM_BG}; color: {_TEXT}; min-width: 360px;
}}
QLineEdit#gateInput:focus {{ border-color: {_BRAND}; background: white; }}
QLabel#gatePie {{
    font-size: 13px; color: {_MUTED}; padding-top: 2px;
}}
QLabel#gateChip {{
    font-size: 13px; color: {_TEXT}; background: {_WARM_BG};
    border: 1px solid {_BORDER}; border-radius: 14px; padding: 5px 13px;
}}
QLabel#gateChip[lider="true"] {{
    color: {_BRAND}; background: {_BRAND_LIGHT}; border-color: {_BRAND};
}}
QLabel#gateError {{
    font-size: 12px; color: {_DANGER}; font-weight: 500;
    padding: 6px 12px; background: #fef0ee; border-radius: 6px;
}}
"""

_SALE_STYLE = f"""
QWidget#saleRoot {{ background: {_WARM_BG}; }}

QFrame#totalBar {{
    background: {_CARD_BG}; border: 1.5px solid {_BORDER}; border-radius: 14px;
}}
QLabel#totalAmount {{
    font-size: 38px; font-weight: 800; color: {_BRAND};
}}
QLabel#totalMeta {{
    font-size: 12px; color: {_MUTED}; font-weight: 500;
}}
QLabel#empBadge {{
    font-size: 12px; color: {_BRAND}; font-weight: 500;
    padding: 5px 14px; background: {_BRAND_LIGHT};
    border: 1px solid {_BORDER}; border-radius: 14px;
}}

QFrame#scanBar {{
    background: {_CARD_BG}; border: 1.5px solid {_BORDER}; border-radius: 12px;
}}
QLineEdit#scanInput {{
    font-size: 15px; padding: 12px 16px;
    border: 1.5px solid {_BORDER}; border-radius: 10px;
    background: {_WARM_BG}; color: {_TEXT};
}}
QLineEdit#scanInput:focus {{ border-color: {_BRAND}; background: white; }}
QLabel#scanHint {{
    font-size: 11px; color: {_MUTED}; font-style: italic;
}}

QFrame#tableCard {{
    background: {_CARD_BG}; border: 1.5px solid {_BORDER}; border-radius: 12px;
}}

QPushButton#btnPrimary {{
    font-size: 14px; font-weight: 600; padding: 10px 24px;
    background: {_BRAND}; color: white; border: none; border-radius: 10px;
    min-height: 40px;
}}
QPushButton#btnPrimary:hover {{ background: {_BRAND_DARK}; }}
QPushButton#btnSecondary {{
    font-size: 14px; font-weight: 500; padding: 10px 24px;
    background: {_BRAND_LIGHT}; color: {_BRAND}; border: 1.5px solid {_BORDER};
    border-radius: 10px; min-height: 40px;
}}
QPushButton#btnSecondary:hover {{ background: #ede0d0; }}
QPushButton#btnDanger {{
    font-size: 12px; font-weight: 500; padding: 8px 16px;
    background: transparent; color: {_DANGER}; border: 1px solid {_DANGER};
    border-radius: 8px;
}}
QPushButton#btnDanger:hover {{ background: #fef0ee; }}
QPushButton#btnGhost {{
    font-size: 12px; font-weight: 500; padding: 6px 10px;
    background: transparent; color: {_MUTED}; border: none;
}}
QPushButton#btnGhost:hover {{ color: {_DANGER}; }}
QPushButton#btnLogout {{
    font-size: 11px; font-weight: 500; padding: 5px 14px;
    background: transparent; color: {_MUTED}; border: 1px solid {_BORDER};
    border-radius: 14px;
}}
QPushButton#btnLogout:hover {{ color: {_DANGER}; border-color: {_DANGER}; }}
"""


class QuickSaleWidget(
    ClienteRapidoMixin, ProgramaClienteMixin, MonederoVentaMixin, CompradoraEmpleadaMixin, QWidget
):
    #: Lo de hoy para el pie del gafete, leído en un hilo (el kiosko sin red no se congela).
    _pie_gafete_leido = pyqtSignal(object)
    """Página de Venta Rápida para la app satélite."""

    _SCAN_HINT_DEFAULT = ""  # el hint solo muestra avisos breves (flash)

    def __init__(self, satellite: "QuoteSatelliteWindow"):
        super().__init__()
        self.satellite = satellite
        self._employee_code: str | None = None
        self._employee_name: str | None = None
        self._items: list[dict] = []
        self._discount_active = False
        self._biz_info: tuple[str, str, str] | None = None
        # Monedero: cliente identificado para esta venta (ver _identificar_cliente).
        self._cliente: dict | None = None
        self._usar_saldo = False
        # E5-A: el Mayorista eligió descuento en vez de Monedero en esta venta.
        self._usar_descuento_programa = False
        # Operaciones YA cobradas que no se pudieron anotar: la foto exacta
        # de cada una, para «Reintentar anotar» (ver _retener_anotacion).
        self._anotaciones_pendientes: list[dict] = []
        self._reintentando_anotacion = False
        # Reintentos fallidos SEGUIDOS: al llegar a _REINTENTOS_ANTES_DE_PARAR
        # el aviso deja de ofrecer «Reintentar» (no se queda dando vueltas).
        self._reintentos_fallidos = 0
        # Respaldo en disco (C1): uuid de cada entrada pendiente → uuid de su
        # operación (= nombre del archivo en data/sin_anotar). Operaciones
        # que NI el respaldo se pudo guardar (se pierden si se cierra).
        self._operacion_de: dict[str, str] = {}
        self._sin_respaldo: dict[str, dict] = {}  # clave → {entradas, confirmadas}
        # Entradas ya anotadas en este proceso cuyo respaldo no se pudo
        # actualizar o borrar: no se vuelven a contar como pendientes.
        self._ya_anotadas: set[str] = set()
        self._sin_anotar_revisar: list[str] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._gate_widget = self._build_gate()
        layout.addWidget(self._gate_widget)

        self._sale_widget = self._build_sale_view()
        self._sale_widget.setVisible(False)
        layout.addWidget(self._sale_widget)

        self.setLayout(layout)

        # C1: lo cobrado y no anotado en una sesión anterior sigue en disco.
        if self._recuperar_pendientes_persistidos():
            QTimer.singleShot(1500, self._avisar_pendientes_recuperados)

    # ─── Gate de empleada ────────────────────────────────────────────────

    def _build_gate(self) -> QWidget:
        """La pantalla de «escanea tu gafete», que es la misma de Libreta y
        Conteos: una sola, en `helpers/pantalla_de_gafete.py`.

        Eran tres copias calcadas a mano. Se juntaron el 07/10, cuando la
        escena de temporada y el texto en color habían entrado solo aquí y
        Daniel los pidió en las otras dos: teñir tres copias arregla hoy y se
        vuelve a romper la próxima vez.
        """
        from pos_uniformes.ui.helpers.pantalla_de_gafete import construir_gate

        gate = construir_gate(
            emoji="📋",
            titulo="Venta rápida",
            ayuda="Escanea tu QR de empleada para comenzar",
            marcador="VEND-1",
            hoja=_GATE_STYLE,
            al_escanear=self._on_gate_scan,
            con_pie=True,
        )
        self._gate_fondo = gate.raiz
        self._gate_input = gate.entrada
        self._gate_error = gate.error
        self._gate = gate
        self._gate_pie = gate.pie
        self._pie_gafete_leido.connect(self._pintar_pie_gafete)
        # Se refresca al volver al gafete y cada minuto mientras esté a la vista.
        self._pie_timer = QTimer(self)
        self._pie_timer.setInterval(60_000)
        self._pie_timer.timeout.connect(self.refrescar_pie_gafete)
        self._pie_timer.start()
        self.refrescar_pie_gafete()
        return gate.raiz

    def refrescar_pie_gafete(self) -> None:
        """Cuántas operaciones lleva cada una hoy y quién vendió al último."""
        if self._gate_pie is None or not self._gate_widget_visible():
            return
        import threading

        def _leer() -> None:
            try:
                from pos_uniformes.database.connection import get_session
                from pos_uniformes.services import gafete_hoy_service as gh

                with get_session() as session:
                    resumen = gh.resumen_de_hoy(session)
            except Exception:  # noqa: BLE001 — sin base, el pie se queda como estaba
                return
            try:
                self._pie_gafete_leido.emit(resumen)
            except RuntimeError:
                pass

        threading.Thread(target=_leer, daemon=True, name="pie-gafete").start()

    def _gate_widget_visible(self) -> bool:
        gate = getattr(self, "_gate_widget", None)
        return gate is None or not gate.isHidden()

    def _pintar_pie_gafete(self, resumen) -> None:
        from pos_uniformes.ui.helpers.pantalla_de_gafete import pintar_pie

        pintar_pie(self._gate, resumen)

    @staticmethod
    def _normalize_scan(raw: str) -> str:
        """Única normalización del escáner: printable + mapeo del teclado
        español HID (: → Ñ, - → ') + mayúsculas. Todo lo que interprete
        escaneos debe pasar por aquí para no divergir."""
        clean = "".join(c for c in raw if c.isprintable()).strip()
        clean = clean.replace("Ñ", ":").replace("ñ", ":").replace("'", "-")
        return clean.upper()

    @staticmethod
    def _clean_scanned_code(raw: str) -> str:
        clean = QuickSaleWidget._normalize_scan(raw)
        if clean.startswith("EMP:"):
            clean = clean[4:]
        return clean

    def _on_gate_scan(self) -> None:
        code = self._clean_scanned_code(self._gate_input.text())
        if not code:
            return

        emp_code = code
        emp_name = code

        if self.satellite.offline_mode:
            if not code.startswith("VEND-"):
                self._gate_error.setText("Formato esperado: VEND-1, VEND-2, etc.")
                self._gate_error.setVisible(True)
                self._gate_input.clear()
                self._gate_input.setFocus()
                return
        else:
            sin_conexion = False
            try:
                with get_session() as session:
                    emp = session.scalar(
                        select(Empleada).where(
                            Empleada.codigo == code,
                            Empleada.activo.is_(True),
                        )
                    )
            except Exception:
                # Sin log, un error real de DB se veia como "codigo no encontrado".
                _logger.exception("Error de DB al validar empleada '%s' en el gate", code)
                emp = None
                sin_conexion = True

            if sin_conexion:
                # No es lo mismo "tu gafete no existe" que "no alcanzo la PC".
                # Decirle lo primero cuando pasa lo segundo la deja parada en la
                # puerta creyendo que su gafete está mal, y de ahí a apagar y
                # volver a abrir hay un paso.
                resuelto = self._empleada_de_cache(code)
                self._avisar_sin_conexion()
                if resuelto is None:
                    self._gate_error.setText(
                        "Sin conexión con la PC principal y tu gafete no está guardado aquí. "
                        "Pide que te abran con otro gafete."
                    )
                    self._gate_error.setVisible(True)
                    self._gate_input.clear()
                    self._gate_input.setFocus()
                    return
                emp_code, emp_name = resuelto
            elif not emp:
                self._gate_error.setText(f"Codigo '{code}' no encontrado o inactivo.")
                self._gate_error.setVisible(True)
                self._gate_input.clear()
                self._gate_input.setFocus()
                return
            else:
                emp_code = emp.codigo
                emp_name = emp.nombre_completo

        self._employee_code = emp_code
        self._employee_name = emp_name
        self._gate_widget.setVisible(False)
        self._sale_widget.setVisible(True)
        self._emp_badge.setText(f"  {emp_name}  ")
        self._items.clear()
        self._refresh_items_table()
        self._refresh_totals()
        QTimer.singleShot(0, self._scan_input.setFocus)

    def _empleada_de_cache(self, code: str) -> tuple[str, str] | None:
        """(código, nombre) desde la copia local de empleadas, o None.

        La copia la deja el watchdog cada vez que hay conexión, así que con la
        PC principal apagada se sigue sabiendo de quién es cada gafete — y la
        venta queda a nombre de quien de verdad atendió, no de un código suelto.
        """
        try:
            from pos_uniformes.services.nombres_empleadas_service import nombres_por_codigo

            nombres = nombres_por_codigo()
        except Exception:  # noqa: BLE001
            nombres = {}
        limpio = str(code or "").strip().upper()
        nombre = nombres.get(limpio)
        if nombre:
            return limpio, nombre
        # Sin copia local: se acepta el formato de siempre, igual que cuando
        # el programa arranca sin conexión. Vale más vender que validar.
        if limpio.startswith(("VEND-", "ENC-")):
            return limpio, limpio
        return None

    def _avisar_sin_conexion(self) -> None:
        """Le dice a la ventana que la base no contestó, para no reintentarla.

        Sin esto cada operación vuelve a chocar con el timeout de cinco
        segundos hasta que pase el watchdog, que tarda cinco minutos.
        """
        marcar = getattr(self.satellite, "marcar_sin_conexion", None)
        if callable(marcar):
            try:
                marcar()
            except Exception:  # noqa: BLE001
                pass

    # ─── Vista de venta ──────────────────────────────────────────────────

    def _build_sale_view(self) -> QWidget:
        root = QWidget()
        root.setObjectName("saleRoot")
        root.setStyleSheet(_SALE_STYLE)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # ── Barra superior: empleada + logout ──
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._emp_badge = QLabel("")
        self._emp_badge.setObjectName("empBadge")
        top_row.addWidget(self._emp_badge)
        top_row.addStretch()
        btn_logout = QPushButton("Cerrar sesion")
        btn_logout.setObjectName("btnLogout")
        btn_logout.clicked.connect(self._on_logout)
        top_row.addWidget(btn_logout)
        layout.addLayout(top_row)

        # ── Total card ──
        total_bar = QFrame()
        total_bar.setObjectName("totalBar")
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(20, 14, 20, 14)
        tb_layout.setSpacing(12)

        total_left = QVBoxLayout()
        total_left.setSpacing(0)
        self._total_meta = QLabel("0 piezas")
        self._total_meta.setObjectName("totalMeta")
        total_left.addWidget(self._total_meta)
        self._total_label = QLabel("$0.00")
        self._total_label.setObjectName("totalAmount")
        total_left.addWidget(self._total_label)
        tb_layout.addLayout(total_left)

        tb_layout.addStretch()

        btn_venta = QPushButton("Ticket Venta")
        btn_venta.setObjectName("btnPrimary")
        btn_venta.clicked.connect(self._on_ticket_venta)
        tb_layout.addWidget(btn_venta)

        btn_apartado = QPushButton("Ticket Apartado")
        btn_apartado.setObjectName("btnSecondary")
        btn_apartado.clicked.connect(self._on_ticket_apartado)
        tb_layout.addWidget(btn_apartado)

        btn_abono = QPushButton("Abono")
        btn_abono.setObjectName("btnSecondary")
        btn_abono.clicked.connect(self._on_abono)
        tb_layout.addWidget(btn_abono)

        btn_pedido = QPushButton("Enviar a preparar")
        btn_pedido.setObjectName("btnGhost")
        btn_pedido.setToolTip("Manda las piezas al tablero de pedidos del satélite para prepararlas")
        btn_pedido.clicked.connect(self._on_enviar_pedido)
        tb_layout.addWidget(btn_pedido)
        # "Enviar a preparar" oculto (decisión de Daniel, 2026-09-02): no lo
        # usa en su operación. El flujo y el tablero de pedidos siguen vivos;
        # para restaurarlo basta quitar esta línea.
        btn_pedido.setVisible(False)

        total_bar.setLayout(tb_layout)
        layout.addWidget(total_bar)
        layout.addWidget(self._build_cliente_bar())
        layout.addWidget(self._build_programa_bar())  # E4-C: programa del cliente

        # ── Scan bar ──
        scan_bar = QFrame()
        scan_bar.setObjectName("scanBar")
        sb_layout = QHBoxLayout()
        sb_layout.setContentsMargins(14, 10, 14, 10)
        sb_layout.setSpacing(8)

        self._scan_input = QLineEdit()
        self._scan_input.setObjectName("scanInput")
        self._scan_input.setPlaceholderText("Escanea o escribe el SKU...")
        self._scan_input.returnPressed.connect(self._on_scan_and_add)
        sb_layout.addWidget(self._scan_input, 1)

        self._qty_spin = QSpinBox()
        self._qty_spin.setMinimum(1)
        self._qty_spin.setMaximum(999)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(64)
        self._qty_spin.setMinimumHeight(42)
        self._qty_spin.setStyleSheet(
            f"QSpinBox {{ font-size: 14px; padding: 4px 8px; border: 1.5px solid {_BORDER}; "
            f"border-radius: 10px; background: {_WARM_BG}; color: {_TEXT}; }}"
            f"QSpinBox:focus {{ border-color: {_BRAND}; background: white; }}"
        )
        sb_layout.addWidget(self._qty_spin)

        self._scan_hint = QLabel(self._SCAN_HINT_DEFAULT)
        self._scan_hint.setObjectName("scanHint")
        sb_layout.addWidget(self._scan_hint)
        # Solo aparece si una operación cobrada no se pudo anotar: reintenta
        # la MISMA operación (no cobra ni imprime otra vez).
        self._btn_reintentar_anotar = QPushButton()
        self._btn_reintentar_anotar.setObjectName("reintentarAnotarButton")
        self._btn_reintentar_anotar.setAutoDefault(False)
        self._btn_reintentar_anotar.setStyleSheet(
            "QPushButton { background: #fdecea; color: #8a1f11;"
            "  border: 2px solid #d9534f; border-radius: 12px;"
            "  padding: 6px 12px; font-size: 13px; font-weight: 700; }"
        )
        self._btn_reintentar_anotar.clicked.connect(self._reintentar_anotacion)
        self._btn_reintentar_anotar.setVisible(False)
        sb_layout.addWidget(self._btn_reintentar_anotar)
        # Venta de productos SIN código (listones, parches, arreglos...):
        # abre un diálogo táctil con teclado numérico para el precio.
        self._btn_sin_codigo = QPushButton("➕  Sin código")
        self._btn_sin_codigo.setToolTip("Vender un producto que no tiene código de barras")
        self._btn_sin_codigo.setAutoDefault(False)
        self._btn_sin_codigo.setStyleSheet(
            "QPushButton { background: #f8f2e9; color: #73341c;"
            "  border: 1.5px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 48px; padding: 0 18px; font-size: 15px; font-weight: 800; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        self._btn_sin_codigo.clicked.connect(self._on_producto_sin_codigo)
        sb_layout.addWidget(self._btn_sin_codigo)
        # Gasto de la tienda (bolsas, un mandado, el agua): sale del cajón y
        # el corte lo cuenta en «Gastos». Lo apunta quien esté atendiendo
        # (Daniel, 2026-10-01); a él le llega el aviso al instante.
        self._btn_gasto = QPushButton("🧾  Gasto")
        self._btn_gasto.setToolTip("Apuntar un gasto de la tienda que salió del cajón")
        self._btn_gasto.setAutoDefault(False)
        self._btn_gasto.setStyleSheet(self._btn_sin_codigo.styleSheet())
        self._btn_gasto.clicked.connect(self._on_gasto_tienda)
        sb_layout.addWidget(self._btn_gasto)
        self._btn_cliente = QPushButton("👛  Cliente")
        self._btn_cliente.setToolTip("Buscar o registrar al cliente (para usar saldo, escanea su QR)")
        self._btn_cliente.setAutoDefault(False)
        self._btn_cliente.setStyleSheet(self._btn_sin_codigo.styleSheet())
        self._btn_cliente.clicked.connect(self._on_cliente_rapido)  # E1-B: buscador y alta
        sb_layout.addWidget(self._btn_cliente)

        scan_bar.setLayout(sb_layout)
        layout.addWidget(scan_bar)

        # ── Tabla de items ──
        table_card = QFrame()
        table_card.setObjectName("tableCard")
        tc_layout = QVBoxLayout()
        tc_layout.setContentsMargins(2, 2, 2, 2)
        tc_layout.setSpacing(0)

        self._items_table = QTableWidget()
        self._items_table.setColumnCount(5)
        self._items_table.setHorizontalHeaderLabels(["Producto", "Talla", "Cant.", "Subtotal", ""])
        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._items_table.setShowGrid(False)
        self._items_table.setAlternatingRowColors(True)
        h = self._items_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._items_table.setColumnWidth(1, 70)
        self._items_table.setColumnWidth(2, 60)
        self._items_table.setColumnWidth(3, 100)
        self._items_table.setColumnWidth(4, 172)
        # El alto de fila se fija al pintar (ver _refresh_items_table): el
        # auto-medido solo considera el texto, no el widget de botones.
        self._items_table.verticalHeader().setDefaultSectionSize(
            self._ALTO_BOTON_CARRITO + 2 * self._PAD_ITEM_CARRITO + 2
        )
        self._items_table.setStyleSheet(f"""
            QTableWidget {{
                background: white; border: none; font-size: 16px; color: {_TEXT};
            }}
            QTableWidget::item {{
                padding: 8px 10px; border-bottom: 1px solid #f0e6db;
            }}
            QTableWidget::item:alternate {{ background: {_WARM_BG}; }}
            QTableWidget::item:selected {{ background: {_BRAND_LIGHT}; color: {_TEXT}; }}
            QHeaderView::section {{
                background: {_WARM_BG}; color: {_MUTED}; font-weight: 600;
                font-size: 12px; padding: 8px 10px; border: none;
                border-bottom: 1.5px solid {_BORDER};
                text-transform: uppercase;
            }}
        """)
        tc_layout.addWidget(self._items_table)
        table_card.setLayout(tc_layout)
        layout.addWidget(table_card, 1)

        # ── Footer: limpiar + descuento ──
        footer = QHBoxLayout()
        footer.setSpacing(8)
        btn_clear = QPushButton("Limpiar todo")
        btn_clear.setObjectName("btnDanger")
        btn_clear.clicked.connect(self._on_clear_all)
        footer.addWidget(btn_clear)
        footer.addStretch()
        self._discount_check = QCheckBox("Descuento")
        self._discount_check.setStyleSheet(
            f"QCheckBox {{ font-size: 13px; color: {_BRAND}; font-weight: 500; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; }}"
        )
        self._discount_check.clicked.connect(self._on_discount_toggle)
        footer.addWidget(self._discount_check)
        layout.addLayout(footer)

        root.setLayout(layout)
        return root

    # ─── Escaneo de producto ─────────────────────────────────────────────

    def _is_employee_badge_scan(self, raw: str) -> bool:
        """Detecta si lo escaneado es un gafete de empleada y no un SKU.

        El sensor tiene mucho alcance y a veces relee el gafete colgado de la
        empleada mientras escanea productos; eso no debe abrir ningún diálogo.
        """
        if self._normalize_scan(raw).startswith("EMP:"):
            return True
        code = self._clean_scanned_code(raw)
        if self._employee_code and code == self._employee_code:
            return True
        return bool(re.fullmatch(r"VEND-\d+", code))

    def _flash_scan_hint(self, message: str) -> None:
        self._scan_hint.setText(message)
        QTimer.singleShot(
            1800, lambda: self._scan_hint.setText(self._SCAN_HINT_DEFAULT)
        )

    def _on_scan_and_add(self) -> None:
        sku = self._scan_input.text().strip().upper()
        if not sku:
            return
        if self._is_employee_badge_scan(sku):
            # Gafete releído por el sensor: se ignora sin cortar la venta.
            self._flash_scan_hint("Gafete ignorado")
            self._scan_input.clear()
            self._scan_input.setFocus()
            return
        if self._es_qr_cliente(sku):
            self._scan_input.clear()
            self._identificar_cliente(self._codigo_cliente_de(sku), por_qr=True)
            self._scan_input.setFocus()
            return
        self.add_sku(sku, self._qty_spin.value())
        self._qty_spin.setValue(1)
        self._scan_input.clear()
        self._scan_input.setFocus()

    def add_sku(self, sku: str, qty: int = 1) -> bool:
        """Busca el SKU y lo agrega a la venta. Punto de entrada para Ctrl+S.

        Retorna True si se agregó, False si falló o falta autorización.
        """
        if not self._employee_code:
            QMessageBox.warning(self, "Sin autorizar", "Escanea primero tu QR de empleada.")
            return False
        sku = (sku or "").strip().upper()
        if not sku:
            return False
        try:
            snap = self._lookup_sku(sku)
        except Exception as exc:
            QMessageBox.warning(self, "SKU no encontrado", str(exc))
            return False

        try:
            qty = max(1, int(qty))
        except (TypeError, ValueError):
            # Una cantidad corrupta no debe tumbar la venta — cae a 1 pieza.
            _logger.warning("Cantidad invalida %r para SKU %s; usando 1", qty, snap.sku)
            qty = 1

        # ── Promo 3pz: pants 2pz deportivo puede llevar playera a $100 ──
        promo_playera_item: dict | None = None
        base_adapter = adapt_cache_row(self._find_satellite_row(snap.sku))
        if base_adapter is not None and is_deportivo_two_piece_variant(base_adapter):
            try:
                resolution = resolve_sale_scan_variants(
                    self,
                    None,  # sin sesión: los loaders resuelven contra el cache
                    base_adapter,
                    variant_loader=lambda _s, sku2: adapt_cache_row(self._find_satellite_row(sku2)),
                    playera_candidates_loader=lambda _s, base: load_playera_candidates_from_rows(
                        self._satellite_rows(), base
                    ),
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Playera no valida", str(exc))
                return False
            if resolution is None:
                return False  # la empleada canceló el flujo
            if resolution.composed_as_three_pieces:
                promo_playera_item = build_promo_playera_item(
                    resolution.variants[1], base_sku=snap.sku
                )

        existing = next((it for it in self._items if it["sku"] == snap.sku), None)
        if existing:
            existing["cantidad"] += qty
            base_item = existing
        else:
            base_item = {
                "sku": snap.sku,
                # Con color si su producto tiene varios (Short Deportivo Rojo):
                # de aquí lo toman el ticket, la Libreta y la demanda.
                "nombre": getattr(snap, "sale_name", snap.product_name),
                "talla": snap.size_label,
                "color": snap.color_label,
                "precio": snap.price,
                "cantidad": qty,
            }
            self._items.append(base_item)

        if promo_playera_item is not None:
            mark_promo_base_item(base_item, playera_sku=str(promo_playera_item["sku"]))
            existing_playera = next(
                (
                    it
                    for it in self._items
                    if it["sku"] == promo_playera_item["sku"]
                    and it.get("sports_uniform_role") == "playera"
                ),
                None,
            )
            if existing_playera:
                existing_playera["cantidad"] += 1
            else:
                self._items.append(promo_playera_item)

        self._refresh_items_table()
        self._refresh_totals()
        return True

    def _lookup_sku(self, sku: str):
        """El catálogo en memoria primero; Postgres solo si el SKU no está.

        Antes, en línea, cada escaneo viajaba a la PC principal por Wi-Fi
        aunque el catálogo ya estuviera cargado (y se refresca cada 5 min y
        al cambiar precios). Daniel (2026-09-17): "éntrale". Sin conexión se
        queda con el cache, como siempre.
        """
        finder = getattr(self.satellite, "_kiosk_lookup_from_cache", None)
        if callable(finder):
            try:
                return finder(sku)
            except Exception:
                if self.satellite.offline_mode:
                    raise
        elif self.satellite.offline_mode:
            raise ValueError(f"No existe una presentacion activa para el SKU '{sku}' en el catalogo guardado.")
        # No está en el cache (producto recién dado de alta): la base manda.
        with get_session() as session:
            return load_quote_kiosk_lookup_snapshot(session, sku=sku)

    def _satellite_rows(self) -> list[dict]:
        return list(getattr(self.satellite, "catalog_snapshot_rows", None) or [])

    def _find_satellite_row(self, sku: str) -> dict | None:
        finder = getattr(self.satellite, "_find_row_by_sku", None)
        if not callable(finder):
            return None
        try:
            return finder(sku.strip().upper())
        except Exception:  # noqa: BLE001
            return None

    # ─── Tabla de items ──────────────────────────────────────────────────

    def _refresh_items_table(self) -> None:
        self._items_table.clearSpans()
        self._items_table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            name_item = QTableWidgetItem(item["nombre"])
            name_item.setToolTip(f"SKU: {item['sku']}")
            self._items_table.setItem(row, 0, name_item)
            self._items_table.setItem(row, 1, QTableWidgetItem(item["talla"]))

            cant_item = QTableWidgetItem(str(item["cantidad"]))
            cant_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cant_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self._items_table.setItem(row, 2, cant_item)

            subtotal = item["precio"] * item["cantidad"]
            price_item = QTableWidgetItem(f"${subtotal:,.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self._items_table.setItem(row, 3, price_item)

            self._items_table.setCellWidget(row, 4, self._build_row_actions(row))

        # Medido en estilo nativo (macOS) y Fusion: la fila se mide por el
        # TEXTO y el widget de la celda recibe fila − 16 (el padding 8+8 del
        # ::item). Por eso la fila se fija explícita: botones + 16 + 2 de
        # holgura → el widget recibe 38 y los botones de 36 quedan centrados.
        alto_fila = self._ALTO_BOTON_CARRITO + 2 * self._PAD_ITEM_CARRITO + 2
        for row in range(len(self._items)):
            self._items_table.setRowHeight(row, alto_fila)

        self._items_table.setRowCount(max(len(self._items), 1))
        if not self._items:
            placeholder = QTableWidgetItem("Escanea productos para agregarlos aqui...")
            placeholder.setForeground(QColor(_MUTED))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._items_table.setItem(0, 0, placeholder)
            self._items_table.setSpan(0, 0, 1, 5)

    def _refresh_totals(self) -> None:
        subtotal, discount, total = self._compute_totals()
        total_pzas = sum(it["cantidad"] for it in self._items)
        self._total_label.setText(f"${total:,.2f}")
        pzas_text = f"{total_pzas} pieza{'s' if total_pzas != 1 else ''}"
        lineas_text = f"{len(self._items)} linea{'s' if len(self._items) != 1 else ''}"
        meta = f"{lineas_text}  ·  {pzas_text}" if self._items else "Sin piezas"

        if discount > 0 and self._items:
            etiqueta = "Desc. mayoreo" if self._pct_descuento_programa() else "Desc."
            meta += f"  ·  {etiqueta} (-${discount:,.2f})"
            if self._texto_compradora():
                meta += f"  ·  {self._texto_compradora()}"
        canje = self._canje_actual(total)
        if canje > 0:
            meta += f"  ·  Saldo -${canje:,.2f}  ·  Por cobrar ${total - canje:,.2f}"
        self._total_meta.setText(meta)
        self._pintar_cliente_bar()
        self._pintar_programa_bar()

    # Geometría del carrito: padding del ::item (stylesheet) y alto de botón.
    _PAD_ITEM_CARRITO = 8
    _ALTO_BOTON_CARRITO = 36

    def _build_row_actions(self, row: int) -> QWidget:
        """[−] [+] [🗑] por renglón, tamaño dedo (pedido de Daniel).

        Estética: crema/terracota como el resto del kiosko, y el bote usa
        el MISMO icono SVG del sidebar (el emoji 🗑 se ve alambrado en
        Windows)."""
        _BASE = (
            "QPushButton {{ background: {bg}; border: 1.5px solid {borde};"
            "  border-radius: 12px; font-size: 20px; font-weight: 800;"
            "  color: {color}; }}"
            "QPushButton:pressed {{ background: {press}; }}"
        )
        btn_minus = QPushButton("−")
        btn_minus.setToolTip("Quitar 1 pieza")
        btn_minus.setStyleSheet(_BASE.format(
            bg="#ffffff", borde=_BORDER, color=_TEXT, press="#f1e6d6"))
        btn_minus.clicked.connect(lambda checked=False, r=row: self._on_remove(r))

        btn_plus = QPushButton("+")
        btn_plus.setToolTip("Agregar 1 pieza")
        btn_plus.setStyleSheet(_BASE.format(
            bg="#ffffff", borde=_BORDER, color=_TEXT, press="#f1e6d6"))
        btn_plus.clicked.connect(lambda checked=False, r=row: self._on_add_one(r))

        btn_trash = QPushButton("")
        btn_trash.setToolTip("Eliminar la línea completa")
        btn_trash.setStyleSheet(_BASE.format(
            bg="#ffffff", borde="#e2b7ad", color=_DANGER, press="#fde3dd"))
        try:
            from pos_uniformes.ui.quote_satellite_window import _icon_from_asset

            btn_trash.setIcon(_icon_from_asset("kiosk_icons/trash.svg"))
            btn_trash.setIconSize(QSize(20, 20))
        except Exception:  # noqa: BLE001 — sin icono, cae al texto
            btn_trash.setText("🗑")
        btn_trash.clicked.connect(lambda checked=False, r=row: self._on_delete_line(r))

        holder = QWidget()
        ly = QHBoxLayout(holder)
        # OJO: el estilo nativo (macOS/Windows) descuenta el padding del
        # ::item (8px arriba/abajo, 10px a los lados) del rectángulo que le
        # da al widget — los márgenes van en CERO y los botones deben caber
        # en ese rectángulo (36 de alto, 3×46+2×5=148 de ancho). En nativo
        # centra el padding; en Fusion centra el AlignCenter.
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(5)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for btn in (btn_minus, btn_plus, btn_trash):
            btn.setFixedSize(46, self._ALTO_BOTON_CARRITO)
            ly.addWidget(btn)
        return holder

    def _on_add_one(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self._items[row]["cantidad"] += 1
            self._refresh_items_table()
            self._refresh_totals()

    def _on_delete_line(self, row: int) -> None:
        """Elimina la línea completa (todas sus piezas de un golpe)."""
        if 0 <= row < len(self._items):
            removed = self._items.pop(row)
            message = restore_promo_playera_after_base_removed(self._items, removed)
            if message:
                QMessageBox.information(self, "Promo 3pz", message)
            self._refresh_items_table()
            self._refresh_totals()

    def _on_remove(self, row: int) -> None:
        if 0 <= row < len(self._items):
            item = self._items[row]
            if item["cantidad"] > 1:
                item["cantidad"] -= 1
            else:
                removed = self._items.pop(row)
                # Si se quitó el pants base de la promo 3pz, la playera
                # regresa a su precio original (igual que en caja).
                message = restore_promo_playera_after_base_removed(self._items, removed)
                if message:
                    QMessageBox.information(self, "Promo 3pz", message)
            self._refresh_items_table()
            self._refresh_totals()

    # ─── Descuento ───────────────────────────────────────────────────────

    _DISCOUNT_PERCENT = Decimal("5")
    _MIN_LAYAWAY_PERCENT = Decimal("25")
    _OWNER_NAME = "daniel fabian"
    _OWNER_CODE = "VEND-1"

    def _on_discount_toggle(self) -> None:
        if self._discount_check.isChecked():
            if not self._authorize_owner():
                self._discount_check.setChecked(False)
                return
            self._discount_active = True
            # E6: su nivel según lo que vendió el mes pasado.
            self._elegir_compradora()
        else:
            self._discount_active = False
            self._quitar_compradora()
        self._refresh_totals()

    def _authorize_owner(self) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle("Autorizar descuento")
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {_WARM_BG}; }}
            QLabel {{ font-size: 13px; color: {_TEXT}; }}
            QLineEdit {{
                font-size: 16px; padding: 12px 16px;
                border: 1.5px solid {_BORDER}; border-radius: 10px;
                background: white; color: {_TEXT};
            }}
            QLineEdit:focus {{ border-color: {_BRAND}; }}
        """)
        ly = QVBoxLayout()
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(10)
        ly.addWidget(QLabel("Escanea QR de administrador"))
        code_input = QLineEdit()
        code_input.setPlaceholderText("QR de administrador...")
        code_input.returnPressed.connect(dlg.accept)
        ly.addWidget(code_input)
        dlg.setLayout(ly)
        QTimer.singleShot(0, code_input.setFocus)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        scanned = self._clean_scanned_code(code_input.text())
        if not scanned:
            return False
        if self.satellite.offline_mode:
            if scanned != self._OWNER_CODE:
                QMessageBox.warning(
                    self, "No autorizado", "Solo el administrador puede autorizar descuentos."
                )
                return False
            return True
        try:
            with get_session() as session:
                emp = session.scalar(
                    select(Empleada).where(
                        Empleada.codigo == scanned,
                        Empleada.activo.is_(True),
                    )
                )
        except Exception:
            # Sin log, un error real de DB se veia como "QR no reconocido".
            _logger.exception("Error de DB al autorizar descuento con QR '%s'", scanned)
            emp = None
        if emp is None:
            QMessageBox.warning(self, "No autorizado", "QR no reconocido.")
            return False
        full_name = (emp.nombre_completo or "").casefold()
        if self._OWNER_NAME not in full_name:
            QMessageBox.warning(self, "No autorizado", "Solo el administrador puede autorizar descuentos.")
            return False
        return True

    # Comisión que cobra la terminal bancaria; se descuenta por producto en la
    # copia interna y en el neto de la Libreta cuando la venta fue con tarjeta.
    # El porcentaje vive en libreta_service (única fuente).
    _TERMINAL_COMMISSION_PERCENT = _TERMINAL_COMMISSION

    def _apply_terminal_commission(self, precio: Decimal) -> Decimal:
        from pos_uniformes.services.libreta_service import aplicar_comision_terminal

        return aplicar_comision_terminal(Decimal(str(precio)))

    def _commission_items(self) -> list[dict]:
        """Items con el precio unitario ya descontado y redondeado."""
        return [
            {**it, "precio": self._apply_terminal_commission(it["precio"])}
            for it in self._items
        ]

    @staticmethod
    def _round_total(total: Decimal) -> Decimal:
        # Delegado al servicio compartido: la regla de redondeo de la tienda
        # vive en UN solo lugar (antes esto era una copia que podía divergir).
        from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding

        return resolve_sale_rounding(total).collected_total

    def _compute_totals(self, items: list[dict] | None = None) -> tuple[Decimal, Decimal, Decimal]:
        items = self._items if items is None else items
        subtotal = Decimal(str(sum(it["precio"] * it["cantidad"] for it in items)))
        pct_programa = self._pct_descuento_programa()
        self._asignar_pct_empleada(items)
        if pct_programa or (self._discount_active and self._hay_pct_por_renglon(items)):
            # E5-A: precio de mayoreo; por renglón gana el más alto y la promo
            # 3pz no lo lleva (descuento_programa_service).
            from pos_uniformes.services.fidelizacion import descuento_programa_service as dps

            discount = dps.descuento(
                items, empleada=(self._DISCOUNT_PERCENT if self._discount_active else None), programa=pct_programa
            )
        elif self._discount_active:
            discount = (subtotal * self._DISCOUNT_PERCENT / Decimal("100")).quantize(Decimal("0.01"))
        else:
            discount = Decimal("0.00")
        total = self._round_total(subtotal - discount)
        return subtotal, discount, total

    # ─── Acciones ────────────────────────────────────────────────────────

    def _on_clear_all(self) -> None:
        if not self._items:
            return
        reply = QMessageBox.question(
            self, "Limpiar",
            "¿Eliminar todas las piezas de la lista?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._anotar_carrito_cancelado()
            self._items.clear()
            self._refresh_items_table()
            self._refresh_totals()
            self._scan_input.setFocus()

    def _anotar_carrito_cancelado(self) -> None:
        """Piezas que se escanearon y no se cobraron.

        No siempre es venta perdida (a veces es un error de escaneo), por eso
        se guarda aparte y no se suma a nada. Sirve para ver patrones: la
        misma prenda cancelada muchas veces sí dice algo.
        """
        try:
            from pos_uniformes.services import demanda_service

            for item in list(self._items):
                demanda_service.anotar(
                    demanda_service.CARRITO_VACIO,
                    sku=str(item.get("sku", "")),
                    producto=str(item.get("nombre", "")),
                    talla=str(item.get("talla", "")),
                    piezas=int(item.get("cantidad", 1) or 1),
                    employee_code=str(self._employee_code or ""),
                )
        except Exception:  # noqa: BLE001 — jamás estorbar al mostrador
            pass

    # ─── Tickets ─────────────────────────────────────────────────────────

    _TERMS_VENTA = (
        "1. Revise su mercancía antes de retirarse del establecimiento.\n"
        "2. Tiene 15 días naturales para realizar cambios presentando este ticket. La prenda debe estar en buen estado y con sus etiquetas.\n"
        "3. Conserve este ticket como comprobante de pago.\n"
        "4. Para cualquier aclaración, presente este ticket.\n"
        "5. No se aceptan devoluciones.\n"
        "6. Para solicitar factura, presente este ticket y sus datos fiscales."
    )

    _TERMS_APARTADO = (
        "1. Requisitos para el Apartado\n"
        "  1.1. El cliente debe proporcionar nombre completo, con el que recogera su apartado.\n"
        "  1.2. El minimo de apartado es el 25% del valor total.\n"
        "2. Plazo para Liquidacion\n"
        "  2.1. El cliente tiene 30 dias naturales para liquidar el total.\n"
        "  2.2. Si no liquida en el tiempo establecido, el apartado se cancelara sin reembolso.\n"
        "3. Cambios y Cancelaciones\n"
        "  3.1. No se permiten cambios de modelo o talla.\n"
        "  3.2. En caso de cancelacion, el anticipo no es reembolsable.\n"
        "  3.3. Si hay errores de inventario, se ofrecera cambio o reembolso de la pieza faltante.\n"
        "4. Entrega del Producto\n"
        "  4.1. La entrega se hara solo con el pago total, sin liquidaciones parciales."
    )

    def _monto_neto_actual(self, total: Decimal, *, pago_tarjeta: bool) -> Decimal:
        """Neto tras la comisión de terminal: 4.5% por producto (redondeado
        con la regla de la tienda) sobre el precio efectivamente cobrado —
        con descuento de empleada, sobre el precio ya descontado. En
        efectivo, igual al total."""
        if not pago_tarjeta:
            return total
        discount_factor = (Decimal("100") - self._DISCOUNT_PERCENT) / Decimal("100")
        pct_programa = self._pct_descuento_programa()
        self._asignar_pct_empleada(self._items)
        por_renglon = pct_programa or (self._discount_active and self._hay_pct_por_renglon(self._items))
        neto = Decimal("0.00")
        for it in self._items:
            unit = Decimal(str(it["precio"]))
            if por_renglon:
                from pos_uniformes.services.fidelizacion import descuento_programa_service as dps

                pct = dps.porcentaje_de_linea(
                    it, empleada=(self._DISCOUNT_PERCENT if self._discount_active else None), programa=pct_programa
                )
                unit = dps.precio_con_descuento(unit, pct)
            elif self._discount_active:
                unit = (unit * discount_factor).quantize(Decimal("0.01"))
            unit = self._apply_terminal_commission(unit)
            neto += unit * int(it["cantidad"])
        return neto.quantize(Decimal("0.01"))

    # ─── Anotar en la Libreta ────────────────────────────────────────────
    # Cuatro cosas distintas que NO son la misma operación (auditoría
    # 2026-11-08, A2/A3):
    #   1. cobrar al cliente  — pasa en el mostrador, fuera del sistema;
    #   2. imprimir el ticket — `route_tickets`; si falla, NO se anota nada
    #      (on_printed no se llama) y el carrito sigue intacto;
    #   3. anotar             — escribir la operación en la cola local de
    #      esta PC (este bloque). Si falla, el cliente YA pagó: se guarda una
    #      foto exacta de la operación y se ofrece «Reintentar anotar»;
    #   4. sincronizar        — un hilo sube la cola a la base después. Si
    #      falla, la operación ya está anotada y la Libreta dice cuántas
    #      faltan por subir; no hay nada que reintentar aquí.

    def _registrar_en_libreta(
        self,
        tipo: str,
        *,
        cliente: str | None = None,
        pago_tarjeta: bool = False,
        anticipo: Decimal | None = None,
        anticipo_tarjeta: bool = False,
    ) -> bool:
        """Anota la operación en la Libreta: local primero (nunca bloquea el
        mostrador), y un hilo la sube a la base.

        Un apartado con `anticipo` anota además un abono por ese monto: es el
        dinero que sí entró al cajón hoy. Las dos piezas se arman JUNTAS, con
        su propio `operacion_uuid` cada una, antes de intentar guardar.

        Devuelve True si quedó anotada. Si no se pudo guardar, la operación
        queda retenida tal cual (ver `_retener_anotacion`) y devuelve False."""
        # Un carrito vacío no es una venta. NO se compara contra la venta
        # anterior: dos ventas iguales seguidas (mismo uniforme, otra
        # clienta) son dos ventas. Lo que evita el doble registro es que
        # el diálogo llama on_printed UNA vez y _registrar_y_vaciar vacía
        # el carrito en el mismo acto; reimprimir desde la Libreta no
        # pasa por aquí (sin on_printed).
        if not self._items:
            return True
        try:
            entradas = self._armar_anotacion(
                tipo, cliente=cliente, pago_tarjeta=pago_tarjeta,
                anticipo=anticipo, anticipo_tarjeta=anticipo_tarjeta,
            )
        except Exception:  # noqa: BLE001 — la Libreta nunca rompe el flujo de tickets
            _logger.exception("No se pudo preparar la operacion para la Libreta")
            self._avisar_no_se_anoto(
                "El cliente YA PAGÓ, pero la operación no se pudo preparar para "
                "anotarla. NO le cobres otra vez. El carrito sigue aquí; avísale a Daniel.",
                titulo="Falta anotar la operación",
            )
            return False
        aviso = "Apartado y anticipo registrados" if len(entradas) > 1 else None
        return self._anotar(entradas, aviso_exito=aviso)

    def _armar_anotacion(
        self,
        tipo: str,
        *,
        cliente: str | None,
        pago_tarjeta: bool,
        anticipo: Decimal | None,
        anticipo_tarjeta: bool,
    ) -> list[dict]:
        """Foto completa de la operación, tomada del carrito UNA sola vez.

        Todo lo que el registro necesita va aquí (tipo, montos, descuento de
        empleada, piezas, cliente, hora, uuid): un reintento reutiliza esta
        misma foto y nunca vuelve a leer el carrito, que pudo cambiar."""
        import uuid as _uuid
        from datetime import timezone as _tz

        _subtotal, _descuento, total = self._compute_totals()
        total = Decimal(str(total)).quantize(Decimal("0.01"))
        neto = self._monto_neto_actual(total, pago_tarjeta=pago_tarjeta)
        origen = self._origen_satelite()
        pct_programa = self._pct_descuento_programa()
        entradas = [
            {
                "employee_code": str(self._employee_code or ""),
                "employee_name": str(self._employee_name or self._employee_code or ""),
                "tipo": tipo,
                "cliente": cliente,
                "items": [
                    {
                        "sku": it["sku"],
                        "nombre": it["nombre"],
                        "talla": it["talla"],
                        "cantidad": int(it["cantidad"]),
                        "precio": str(it["precio"]),
                        **self._marca_promo_para_libreta(it),
                        **self._marca_pct_empleada(it),
                    }
                    for it in self._items
                ],
                "monto_total": str(total),
                "monto_neto": str(neto),
                "pago_tarjeta": bool(pago_tarjeta),
                "descuento_empleada": bool(self._discount_active),
                **self._datos_compradora_para_cola(),
                **({"descuento_programa": str(pct_programa)} if pct_programa else {}),
                "origen": origen,
                "created_at": datetime.now(_tz.utc).astimezone().isoformat(),
                # Identidad persistente: la misma en cada reintento.
                "operacion_uuid": str(_uuid.uuid4()),
                **self._datos_cliente_para_cola(tipo, total),
            }
        ]
        if tipo == "apartado" and anticipo is not None and anticipo > 0:
            entradas.append(
                self._entrada_abono(
                    f"{cliente} · anticipo" if cliente else "anticipo",
                    Decimal(str(anticipo)).quantize(Decimal("0.01")),
                    pago_tarjeta=anticipo_tarjeta,
                    origen=origen,
                    operacion_uuid=str(_uuid.uuid4()),
                )
            )
        return entradas

    @staticmethod
    def _origen_satelite() -> str | None:
        try:
            from pos_uniformes.services.satellite_identity_service import get_satellite_id

            return get_satellite_id()
        except Exception:  # noqa: BLE001
            return None

    def _anotar(self, entradas: list[dict], *, aviso_exito: str | None = None) -> bool:
        """Guarda las entradas en la cola local. Si falla, retiene SOLO las
        que no se guardaron (las anteriores ya quedaron en la cola)."""
        from pos_uniformes.services import libreta_local_queue_service as cola

        hechas: list[dict] = []
        try:
            for entrada in entradas:
                # Idempotente por uuid: lo que ya entró no se duplica.
                cola.encolar_operacion(entrada)
                hechas.append(entrada)
        except Exception:  # noqa: BLE001 — la Libreta nunca rompe el flujo de tickets
            _logger.exception("No se pudo registrar la operacion en la Libreta")
            self._retener_anotacion(entradas, hechas=hechas)
            return False
        self._despues_de_encolar()
        if aviso_exito:
            self._flash_scan_hint(aviso_exito)
        return True

    def _retener_anotacion(self, entradas: list[dict], *, hechas: list[dict] | None = None) -> None:
        """El cliente ya pagó y no se pudo anotar: se guarda la foto exacta
        para «Reintentar anotar», en memoria Y en disco (data/sin_anotar), para
        que sobreviva a un cierre o reinicio. Queda un botón junto al escáner.

        `hechas` son las entradas que SÍ entraron a la cola antes del error.
        `encolar_operacion` escribe con reemplazo atómico, así que una entrada
        que lanzó error no quedó escrita; solo se separan si todas traen uuid
        (si no, no hay forma segura de reconocerlas y se conserva todo)."""
        from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

        hechas = list(hechas or [])
        op = sin_anotar.uuid_de_operacion(entradas)
        separable = bool(op) and all(e.get("operacion_uuid") for e in entradas)
        if separable:
            ok = {e["operacion_uuid"] for e in hechas}
            faltan = [e for e in entradas if e["operacion_uuid"] not in ok]
            confirmadas = sorted(ok)
        else:
            faltan, confirmadas = list(entradas), []
            if hechas:
                _logger.error(
                    "Libreta: anotación parcial SIN uuid; se conserva completa para revisión manual: %s",
                    sin_anotar.resumen_para_log(entradas),
                )
        clave = op or str(id(entradas))

        ya = {e.get("operacion_uuid") for e in self._anotaciones_pendientes}
        for entrada in faltan:
            uuid = entrada.get("operacion_uuid")
            if uuid is None or uuid not in ya:
                self._anotaciones_pendientes.append(entrada)
            if uuid:
                self._operacion_de[uuid] = clave

        if op:
            respaldada = self._respaldar(entradas, confirmadas, clave)
        else:
            respaldada = False
            self._sin_respaldo[clave] = {"entradas": list(entradas), "confirmadas": set()}
        _logger.error(
            "Libreta: operación cobrada SIN anotar. operacion=%s respaldo_en_disco=%s "
            "anotadas=%s faltan=%s :: %s",
            op, respaldada, confirmadas, [e.get("operacion_uuid") for e in faltan],
            sin_anotar.resumen_para_log(entradas),
        )
        self._actualizar_boton_anotar()
        self._mostrar_aviso_anotacion(ya_anotadas=[e for e in entradas if e in hechas] if separable else [])

    def _respaldar(self, entradas: list[dict], confirmadas: list[str], clave: str) -> bool:
        """Escribe el respaldo en disco. Si no se puede, la operación queda
        marcada «sin respaldo» (el aviso pide apuntarla en papel)."""
        from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

        try:
            sin_anotar.guardar(entradas, confirmadas=confirmadas)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Libreta: NO se pudo guardar el respaldo en disco de la operación %s :: %s",
                clave, sin_anotar.resumen_para_log(entradas),
            )
            previo = self._sin_respaldo.get(clave, {}).get("confirmadas", set())
            self._sin_respaldo[clave] = {
                "entradas": list(entradas), "confirmadas": set(confirmadas) | previo,
            }
            return False
        self._sin_respaldo.pop(clave, None)
        return True

    def _confirmar_respaldo(self, hechas: list[dict]) -> list[str]:
        """Anota en el respaldo que estas entradas ya entraron a la cola local.

        El respaldo NO se borra aquí: se conserva hasta que PostgreSQL confirme
        todas las entradas (`libreta_sin_anotar_service.conciliar_con_base`,
        al final del drenado). Si la operación no tenía respaldo (el disco
        había fallado), se intenta crearlo ahora, ya marcado «en cola».

        Devuelve las operaciones cuya marca no se pudo escribir. No es grave:
        al arrancar, lo pendiente se calcula contra la cola real y reencolar
        no duplica (uuid)."""
        from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

        por_op: dict[str, list[str]] = {}
        for e in hechas:
            uuid = e.get("operacion_uuid")
            if not uuid:
                continue
            self._ya_anotadas.add(uuid)
            clave = self._operacion_de.pop(uuid, None)
            if clave:
                por_op.setdefault(clave, []).append(uuid)
        problemas: list[str] = []
        for clave, uuids in por_op.items():
            sin_resp = self._sin_respaldo.get(clave)
            if sin_resp is not None:
                sin_resp["confirmadas"] |= set(uuids)
                ents = sin_resp["entradas"]
                if sin_anotar.uuid_de_operacion(ents) and self._respaldar(
                    ents, sorted(sin_resp["confirmadas"]), clave
                ):
                    continue  # respaldo creado (ya marcado en cola)
                todas = {e.get("operacion_uuid") for e in ents}
                if todas <= sin_resp["confirmadas"]:
                    # Todo quedó en la cola (durable): ya no es «sin respaldo».
                    self._sin_respaldo.pop(clave, None)
                continue
            try:
                sin_anotar.marcar_en_cola(clave, uuids)
            except ValueError:
                pass  # clave sin uuid: nunca tuvo archivo en disco
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Libreta: la operación %s SÍ quedó en la cola (%s) pero no se pudo "
                    "anotar en su respaldo; reintentarla no la duplica", clave, uuids,
                )
                problemas.append(clave)
        return problemas

    @staticmethod
    def _describir_entrada(entrada: dict) -> str:
        tipo = str(entrada.get("tipo") or "")
        monto = f"${Decimal(str(entrada.get('monto_total') or '0')):,.2f}"
        cliente = entrada.get("cliente")
        quien = str(entrada.get("employee_name") or entrada.get("employee_code") or "").strip()
        cuando = ""
        try:
            cuando = datetime.fromisoformat(str(entrada.get("created_at"))).strftime("%d/%m %H:%M")
        except (TypeError, ValueError):
            pass
        cola_txt = "".join(
            f" — {t}" for t in (f"vendió {quien}" if quien else "", cuando) if t
        )
        if tipo == "abono":
            return f"• Abono / anticipo de {monto}" + (f" ({cliente})" if cliente else "") + cola_txt
        piezas = sum(int(it.get("cantidad", 0) or 0) for it in entrada.get("items") or [])
        texto = f"• {'Apartado' if tipo == 'apartado' else 'Venta'} de {monto}, {piezas} pieza(s)"
        if cliente:
            texto += f", {cliente}"
        if entrada.get("descuento_empleada"):
            texto += ", con descuento de empleada"
        if entrada.get("pago_tarjeta"):
            texto += ", con tarjeta"
        return texto + cola_txt

    def _mostrar_aviso_anotacion(
        self, *, ya_anotadas: list[dict] | None = None, encabezado: str | None = None
    ) -> None:
        """Aviso de error con «Reintentar anotar». Es modal a la ventana del
        kiosko (WindowModal): hay que cerrarlo para seguir, pero no detiene
        el programa ni los hilos de fondo."""
        if not self._anotaciones_pendientes:
            return
        detalle = "\n".join(self._describir_entrada(e) for e in self._anotaciones_pendientes)
        partes = [
            encabezado
            or (
                "El cliente YA PAGÓ. Lo que falló fue GUARDAR la operación en esta "
                "computadora (el archivo de pendientes no se pudo usar en este momento)."
            ),
            "NO le vuelvas a cobrar y NO vuelvas a imprimir el ticket.",
        ]
        if ya_anotadas:
            partes.append(
                "Ya quedó anotado:\n" + "\n".join(self._describir_entrada(e) for e in ya_anotadas)
            )
        partes.append(f"Falta anotar:\n{detalle}")
        if self._sin_respaldo:
            partes.append(
                "⚠️ TAMPOCO se pudo guardar el respaldo en esta computadora. Si se cierra "
                "el programa, esta operación SE PIERDE. Apúntala AHORA en papel (qué se "
                "vendió, monto, quién la vendió y la hora) y avísale a Daniel."
            )
        else:
            partes.append(
                "Quedó guardada en esta computadora: aunque se cierre el programa, "
                "volverá a aparecer al abrirlo."
            )
        insistir = self._reintentos_fallidos < self._REINTENTOS_ANTES_DE_PARAR
        if insistir:
            partes.append(
                "Toca «Reintentar anotar»: se guarda exactamente esta misma operación. "
                "Si sigue fallando, el botón ⚠️ junto al escáner queda a la vista; "
                "avísale a Daniel."
            )
        else:
            partes.append(
                f"Ya se intentó {self._reintentos_fallidos} veces y sigue fallando: "
                "deja de reintentar por ahora y avísale a Daniel. Puedes seguir "
                "vendiendo; el botón ⚠️ junto al escáner queda a la vista para "
                "intentarlo más tarde."
            )
        partes.append(
            "(No es la impresora ni el internet: la subida al servidor es aparte "
            "y se hace sola.)"
        )
        texto = "\n\n".join(partes)
        try:
            anterior = getattr(self, "_aviso_anotacion", None)
            if anterior is not None:
                anterior.close()
            box = QMessageBox(QMessageBox.Icon.Warning, "Falta anotar la operación", texto, parent=self)
            if insistir:
                reintentar = box.addButton("Reintentar anotar", QMessageBox.ButtonRole.AcceptRole)
                reintentar.clicked.connect(self._reintentar_anotacion)
                _botones_sin_cortar(
                    reintentar,
                    box.addButton("Cerrar (queda pendiente)", QMessageBox.ButtonRole.RejectRole),
                )
            else:
                _botones_sin_cortar(
                    box.addButton("Entendido (queda pendiente)", QMessageBox.ButtonRole.RejectRole)
                )
            self._aviso_anotacion = box  # que no lo recoja el recolector
            box.open()
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudo mostrar el aviso de la Libreta")

    def _actualizar_boton_anotar(self) -> None:
        boton = getattr(self, "_btn_reintentar_anotar", None)
        if boton is None:
            return
        n = len(self._anotaciones_pendientes)
        boton.setText(f"⚠️ Falta anotar ({n}) · ya está cobrado · Reintentar")
        boton.setVisible(n > 0)

    def _reintentar_anotacion(self) -> bool:
        """Vuelve a guardar la MISMA foto: mismo tipo, montos, descuento,
        anticipo, empleada, hora y uuid. No lee el carrito, no imprime y no
        cobra.

        Tocarlo dos veces no duplica: mientras corre se ignora un segundo
        toque, y la cola rechaza un uuid que ya tiene. Si falla a medias, lo
        que sí entró deja de estar pendiente (en memoria y en disco)."""
        if self._reintentando_anotacion or not self._anotaciones_pendientes:
            return False
        self._reintentando_anotacion = True
        try:
            from pos_uniformes.services import libreta_local_queue_service as cola

            lote = list(self._anotaciones_pendientes)
            hechas: list[dict] = []
            fallo = False
            for entrada in lote:
                try:
                    cola.encolar_operacion(entrada)
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        "Libreta: el reintento de anotar volvió a fallar (uuid=%s)",
                        entrada.get("operacion_uuid"),
                    )
                    fallo = True
                    break
                hechas.append(entrada)
            if hechas:
                ids = {id(e) for e in hechas}
                self._anotaciones_pendientes = [e for e in self._anotaciones_pendientes if id(e) not in ids]
                problemas = self._confirmar_respaldo(hechas)
                _logger.warning(
                    "Libreta: reintento anotó %s; siguen pendientes %s",
                    [e.get("operacion_uuid") for e in hechas],
                    [e.get("operacion_uuid") for e in self._anotaciones_pendientes],
                )
            else:
                problemas = []
            self._actualizar_boton_anotar()
            if fallo:
                self._reintentos_fallidos += 1
                # Lo que no tiene respaldo en disco, se intenta respaldar otra vez.
                from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

                for clave, d in list(self._sin_respaldo.items()):
                    if sin_anotar.uuid_de_operacion(d["entradas"]):
                        self._respaldar(d["entradas"], sorted(d["confirmadas"]), clave)
                if hechas:
                    self._despues_de_encolar()
                self._mostrar_aviso_anotacion()  # solo el error; ningún aviso de éxito
                return False
            self._reintentos_fallidos = 0
            aviso = getattr(self, "_aviso_anotacion", None)
            if aviso is not None:
                try:
                    aviso.close()
                except Exception:  # noqa: BLE001
                    pass
                self._aviso_anotacion = None
            self._despues_de_encolar()
            self._flash_scan_hint("✅ Operación anotada (sin cobrar ni imprimir otra vez)")
            if problemas:
                # Sin aviso a la empleada: la operación SÍ quedó en la cola y,
                # si reaparece al arrancar, reintentarla no la duplica.
                _logger.warning("Libreta: respaldos sin marcar como encolados: %s", problemas)
            return True
        finally:
            self._reintentando_anotacion = False

    # ── C1: pendientes en disco al arrancar y al cerrar ──────────────────

    def _recuperar_pendientes_persistidos(self) -> bool:
        """Carga lo cobrado-sin-anotar de sesiones anteriores (sin cobrar ni
        imprimir). No duplica lo que ya está en memoria. Nunca truena:
        devuelve True si hay algo que avisar."""
        try:
            from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

            ops, revisar = sin_anotar.cargar(self._uuids_en_cola())
        except Exception:  # noqa: BLE001
            _logger.exception("Libreta: no se pudieron revisar los respaldos sin anotar")
            return False
        ya = {e.get("operacion_uuid") for e in self._anotaciones_pendientes}
        nuevas = 0
        for op in ops:
            antes = nuevas
            for entrada in op.faltantes:
                uuid = entrada["operacion_uuid"]
                if uuid in self._ya_anotadas:
                    continue
                self._operacion_de[uuid] = op.operacion_uuid
                if uuid not in ya:
                    self._anotaciones_pendientes.append(entrada)
                    ya.add(uuid)
                    nuevas += 1
            if nuevas > antes:
                _logger.warning(
                    "Libreta: recuperada operación cobrada sin anotar %s (guardada %s) :: %s",
                    op.operacion_uuid, op.guardado_at, sin_anotar.resumen_para_log(op.faltantes),
                )
        self._sin_anotar_revisar = list(revisar)
        self._actualizar_boton_anotar()
        return bool(nuevas or revisar)

    @staticmethod
    def _uuids_en_cola() -> set[str] | None:
        """Lo que está HOY en la cola local; None si no se pudo leer (entonces
        el respaldo usa su propia bitácora `en_cola`)."""
        try:
            from pos_uniformes.services import libreta_local_queue_service as cola

            return cola.uuids_en_cola()
        except Exception:  # noqa: BLE001
            _logger.warning("Libreta: no se pudo leer la cola para revisar respaldos", exc_info=True)
            return None

    def _avisar_pendientes_recuperados(self) -> None:
        if self._anotaciones_pendientes:
            n = len(self.claves_pendientes())
            self._mostrar_aviso_anotacion(
                encabezado=(
                    f"Al abrir el programa se encontraron {n} operación(es) que YA SE "
                    "COBRARON pero no quedaron anotadas en la Libreta (de una sesión "
                    "anterior; pudo venderlas otra empleada)."
                )
            )
        if self._sin_anotar_revisar:
            self._avisar_no_se_anoto(
                f"Hay {len(self._sin_anotar_revisar)} respaldo(s) de operaciones sin anotar "
                "que no se pudieron leer: "
                + ", ".join(self._sin_anotar_revisar)
                + ". No se borraron. Avísale a Daniel para revisarlos a mano.",
                titulo="Respaldos por revisar",
            )

    def claves_pendientes(self) -> set[str]:
        """Operaciones cobradas sin anotar, en memoria y en disco, contando
        UNA vez cada operación (por su uuid)."""
        claves = {
            self._operacion_de.get(e.get("operacion_uuid"), e.get("operacion_uuid") or str(id(e)))
            for e in self._anotaciones_pendientes
        }
        try:
            from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

            ops, _revisar = sin_anotar.cargar(self._uuids_en_cola())
        except Exception:  # noqa: BLE001
            ops = []
        for op in ops:
            if any(e["operacion_uuid"] not in self._ya_anotadas for e in op.faltantes):
                claves.add(op.operacion_uuid)
        return claves

    _CIERRE_TIMEOUT_MS = 90_000
    _REINTENTOS_ANTES_DE_PARAR = 3

    def confirmar_cierre(self) -> bool:
        """¿Se puede cerrar la ventana? Sin pendientes, sí. Con pendientes se
        pregunta (Cancelar / Cerrar de todos modos). Cerrar NO borra los
        respaldos en disco."""
        try:
            n = len(self.claves_pendientes())
        except Exception:  # noqa: BLE001 — revisar nunca impide cerrar
            _logger.exception("Libreta: no se pudo contar lo pendiente al cerrar")
            return True
        if n == 0:
            return True
        texto = (
            f"Hay {n} operación(es) que YA SE COBRARON y no están anotadas en la Libreta.\n\n"
            "Cerrar NO las borra: quedan guardadas en esta computadora y volverán a "
            "aparecer al abrir el programa. Pero hay que anotarlas cuanto antes "
            "(«Reintentar anotar»)."
        )
        if self._sin_respaldo:
            texto += (
                f"\n\n⚠️ {len(self._sin_respaldo)} de ellas NO tienen respaldo en disco: "
                "si cierras, SE PIERDEN. Apúntalas en papel antes de cerrar."
            )
        cerrar = self._preguntar_cierre(texto)
        if cerrar:
            if self._sin_respaldo:
                from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

                for clave, d in list(self._sin_respaldo.items()):
                    ents = d["entradas"]
                    if not (sin_anotar.uuid_de_operacion(ents)
                            and self._respaldar(ents, sorted(d["confirmadas"]), clave)):
                        _logger.error(
                            "Libreta: se cerró con una operación cobrada SIN anotar y SIN respaldo :: %s",
                            sin_anotar.resumen_para_log(ents),
                        )
            _logger.warning("Libreta: ventana cerrada con %s operación(es) pendiente(s) de anotar", n)
        return cerrar

    def _preguntar_cierre(self, texto: str) -> bool:
        """Cancelar (por omisión) o Cerrar de todos modos. Si nadie contesta en
        `_CIERRE_TIMEOUT_MS` se cierra: los pendientes quedan en disco y un
        reinicio desatendido (actualización) no se queda colgado."""
        box = QMessageBox(QMessageBox.Icon.Warning, "Operaciones sin anotar", texto, parent=self.window())
        cancelar = box.addButton("Cancelar (no cerrar)", QMessageBox.ButtonRole.RejectRole)
        cerrar = box.addButton("Cerrar de todos modos", QMessageBox.ButtonRole.DestructiveRole)
        _botones_sin_cortar(cancelar, cerrar)
        box.setDefaultButton(cancelar)
        box.setEscapeButton(cancelar)
        reloj = QTimer(box)
        reloj.setSingleShot(True)
        reloj.timeout.connect(cerrar.click)
        reloj.start(self._CIERRE_TIMEOUT_MS)
        box.exec()
        return box.clickedButton() is cerrar

    def _registrar_y_vaciar(
        self,
        tipo: str,
        *,
        cliente: str | None = None,
        pago_tarjeta: bool = False,
        anticipo: Decimal | None = None,
        anticipo_tarjeta: bool = False,
    ) -> bool:
        """Anota en la Libreta y vacía el carrito en el mismo acto.

        Si el carrito sobreviviera a la impresión, agregar una pieza más y
        reimprimir anotaría la venta dos veces (3 pzs y luego 4 = 7), y la
        siguiente clienta heredaría piezas ajenas. Los tickets ya quedaron
        armados como texto, así que reimprimir en la misma ventana sigue
        funcionando.

        También se vacía si la anotación falló pero quedó RETENIDA: la
        operación ya vive en «Reintentar anotar»; dejar el carrito invitaría a
        cobrarla o imprimirla otra vez. Devuelve True solo si quedó anotada."""
        extra = (
            {"anticipo": anticipo, "anticipo_tarjeta": anticipo_tarjeta}
            if tipo == "apartado"
            else {}
        )
        retenidas_antes = len(self._anotaciones_pendientes)
        anotada = bool(
            self._registrar_en_libreta(tipo, cliente=cliente, pago_tarjeta=pago_tarjeta, **extra)
        )
        if anotada or len(self._anotaciones_pendientes) > retenidas_antes:
            self._vaciar_carrito()
        return anotada

    def _despues_de_encolar(self) -> None:
        """Tras anotar: sube en background y, si al anotar se apartó un archivo
        de pendientes dañado, lo dice aquí mismo (una vez)."""
        try:
            self._drenar_libreta_en_background()
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudo lanzar el drenado de la Libreta", exc_info=True)
        try:
            from pos_uniformes.services import libreta_local_queue_service as cola

            apartado = cola.tomar_rescate_reciente()
        except Exception:  # noqa: BLE001
            apartado = None
        if apartado:
            self._avisar_no_se_anoto(
                "El archivo de ventas pendientes de esta terminal estaba dañado. "
                f"Se guardó aparte como «{apartado}» (no se borró) y se empezó uno "
                "nuevo; esta venta sí quedó anotada. Avísale a Daniel: las ventas "
                "que traía ese archivo hay que revisarlas.",
                titulo="Archivo de pendientes apartado",
            )

    def _avisar_no_se_anoto(self, texto: str, *, titulo: str = "Libreta") -> None:
        """Aviso que no detiene el mostrador (no es modal bloqueante)."""
        try:
            box = QMessageBox(QMessageBox.Icon.Warning, titulo, texto, parent=self)
            self._aviso_libreta = box  # que no lo recoja el recolector
            box.open()
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudo mostrar el aviso de la Libreta: %s", texto)

    def _vaciar_carrito(self) -> None:
        self._items.clear()
        self._compradora = None
        self._discount_active = False
        self._discount_check.setChecked(False)
        # El cliente es de ESTA venta: la siguiente no hereda su monedero.
        self._cliente = None
        self._usar_saldo = False
        self._usar_descuento_programa = False
        self._monedero_op = None
        self._refresh_items_table()
        self._refresh_totals()

    def _drenar_libreta_en_background(self) -> None:
        """Sube las operaciones pendientes a la base sin tocar el hilo de UI."""
        import threading

        def _worker() -> None:
            try:
                from pos_uniformes.services.satellite_startup_service import (
                    probe_database_host,
                )

                if not probe_database_host():
                    return
                from pos_uniformes.services import libreta_local_queue_service as cola

                from pos_uniformes.services import demanda_service

                with get_session() as session:
                    cola.drenar_pendientes(session)
                    demanda_service.drenar(session)
            except Exception:  # noqa: BLE001
                # Advertencia y no depuración: un drenado que falla callado fue
                # justo lo que escondió un día de ventas de Entrada (2026-10-15).
                _logger.warning("Drenado de libreta pospuesto", exc_info=True)

        threading.Thread(target=_worker, daemon=True, name="libreta-drain").start()

    def _scan_confirms_copy(self, raw: str) -> bool:
        """True solo si lo escaneado es el gafete de LA empleada en sesión."""
        code = self._clean_scanned_code(raw)
        return bool(code) and code == str(self._employee_code or "").upper()

    def _ask_card_payment(self) -> bool:
        """Pregunta si el pago fue con tarjeta (ventas con descuento de
        empleada, donde no aparece el diálogo de copia). Táctil: dos
        botones grandes, un toque responde."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Forma de pago")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
        )
        ly = QVBoxLayout()
        ly.setContentsMargins(22, 20, 22, 20)
        ly.setSpacing(14)
        title = QLabel("¿Cómo pagó?")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(title)

        respuesta = {"tarjeta": False}
        fila = QHBoxLayout()
        fila.setSpacing(10)
        _BTN = (
            "QPushButton {{ background: {bg}; color: {fg};"
            "  border: {borde}; border-radius: 14px;"
            "  min-height: 64px; font-size: 18px; font-weight: 800; }}"
            "QPushButton:pressed {{ background: {press}; }}"
        )
        btn_efectivo = QPushButton("💵  Efectivo")
        btn_efectivo.setStyleSheet(_BTN.format(
            bg="#f8f2e9", fg="#73341c", borde="1px solid #ddd0c0", press="#e8dbc7"))
        btn_tarjeta = QPushButton("💳  Tarjeta")
        btn_tarjeta.setStyleSheet(_BTN.format(
            bg="#a84f2d", fg="#ffffff", borde="none", press="#8a4326"))

        def _responder(tarjeta: bool) -> None:
            respuesta["tarjeta"] = tarjeta
            dlg.accept()

        for btn, es_tarjeta in ((btn_efectivo, False), (btn_tarjeta, True)):
            btn.setAutoDefault(False)
            btn.clicked.connect(lambda _=False, t=es_tarjeta: _responder(t))
            fila.addWidget(btn, 1)
        ly.addLayout(fila)
        dlg.setLayout(ly)
        dlg.exec()
        return respuesta["tarjeta"]

    def _ask_venta_options(self) -> tuple[bool, bool, bool]:
        """Pregunta copia interna y forma de pago en un solo diálogo.

        Devuelve (con_copia, pago_tarjeta, sin_ticket). Default: sin copia,
        efectivo, con ticket. "Sin ticket" (2026-09-09, pedido de Daniel):
        la venta se registra en la Libreta igual que siempre pero no sale
        papel; el ticket se reconstruye y reimprime después desde la Libreta.
        Escanear el gafete de la empleada en sesión equivale a "sí, con
        copia"; cualquier otro código se rechaza. Aquí NO va el
        ScannerEnterGuard: el escaneo es entrada legítima y el Enter del
        escáner cae en el input (los botones no son default, así que un
        Enter suelto no contesta nada)."""
        # Rediseño táctil (2026-09-05): botones grandes en vez de checkbox
        # chiquito — pensado para el dedo, no para el mouse.
        dlg = QDialog(self)
        dlg.setWindowTitle("Copia tienda")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
            "QLineEdit { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 44px; padding: 0 12px; font-size: 15px; }"
        )
        ly = QVBoxLayout()
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(12)

        title = QLabel("¿Imprimir copia para la tienda?")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(title)

        # ¿Cómo pagó? — dos toggles grandes y exclusivos (default: efectivo)
        pago_label = QLabel("¿Cómo pagó?")
        pago_label.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(pago_label)
        # Seleccionado = tinte claro con borde grueso (distinto del botón de
        # acción sólido, para que no se confundan a golpe de vista).
        _TOGGLE = (
            "QPushButton { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 56px; font-size: 17px; font-weight: 700; }"
            "QPushButton:checked { background: #f7e3d8; color: #73341c;"
            "  border: 3px solid #a84f2d; }"
        )
        pago_row = QHBoxLayout()
        pago_row.setSpacing(10)
        btn_efectivo = QPushButton("💵  Efectivo")
        btn_tarjeta = QPushButton("💳  Tarjeta")
        for btn in (btn_efectivo, btn_tarjeta):
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setStyleSheet(_TOGGLE)
            pago_row.addWidget(btn)
        btn_efectivo.setChecked(True)
        btn_efectivo.setText("✓ 💵  Efectivo")

        def _set_pago(tarjeta: bool) -> None:
            btn_tarjeta.setChecked(tarjeta)
            btn_efectivo.setChecked(not tarjeta)
            btn_efectivo.setText("✓ 💵  Efectivo" if not tarjeta else "💵  Efectivo")
            btn_tarjeta.setText("✓ 💳  Tarjeta" if tarjeta else "💳  Tarjeta")

        btn_efectivo.clicked.connect(lambda: _set_pago(False))
        btn_tarjeta.clicked.connect(lambda: _set_pago(True))
        ly.addLayout(pago_row)

        hint = QLabel("O escanea tu gafete: eso responde \"Sí, con copia\".")
        hint.setStyleSheet(f"font-size: 12px; color: {_MUTED};")

        scan_input = QLineEdit()
        scan_input.setPlaceholderText("Escanea tu gafete...")

        error_label = QLabel("")
        error_label.setStyleSheet(f"font-size: 12px; color: {_DANGER}; font-weight: 700;")
        error_label.setVisible(False)

        wants_copy = False
        sin_ticket = False

        def _accept_with_copy() -> None:
            nonlocal wants_copy
            wants_copy = True
            dlg.accept()

        def _accept_sin_ticket() -> None:
            nonlocal sin_ticket
            sin_ticket = True
            dlg.accept()

        def _on_scan() -> None:
            raw = scan_input.text()
            scan_input.clear()
            if not raw.strip():
                return
            if self._scan_confirms_copy(raw):
                _accept_with_copy()
            else:
                error_label.setText("Solo el gafete de la empleada en sesión autoriza la copia.")
                error_label.setVisible(True)
                scan_input.setFocus()

        scan_input.returnPressed.connect(_on_scan)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        # "Solo ticket" es la respuesta de todos los días: ese lleva el
        # terracota protagonista (pedido de Daniel).
        no_button = QPushButton("🧾  Solo ticket\ndel cliente")
        no_button.setStyleSheet(
            "QPushButton { background: #a84f2d; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 60px;"
            "  font-size: 17px; font-weight: 800; }"
            "QPushButton:pressed { background: #8a4326; }"
        )
        yes_button = QPushButton("🖨  Sí, con copia")
        yes_button.setStyleSheet(
            "QPushButton { background: #f8f2e9; color: #73341c;"
            "  border: 1px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 60px; font-size: 16px; font-weight: 700; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        for button in (no_button, yes_button):
            # Sin botón default: un Enter suelto no debe contestar el diálogo.
            button.setAutoDefault(False)
            button.setDefault(False)
        no_button.clicked.connect(dlg.reject)
        yes_button.clicked.connect(_accept_with_copy)
        btn_row.addWidget(no_button, 1)
        btn_row.addWidget(yes_button, 1)
        ly.addLayout(btn_row)

        # Sin papel: se registra igual, se reimprime después si hace falta.
        sin_ticket_button = QPushButton("🚫  Sin ticket (se registra, no se imprime)")
        sin_ticket_button.setObjectName("sinTicketButton")
        sin_ticket_button.setStyleSheet(
            "QPushButton { background: transparent; color: #73341c;"
            "  border: 2px dashed #c9b8a3; border-radius: 14px; min-height: 48px;"
            "  font-size: 15px; font-weight: 700; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        sin_ticket_button.setAutoDefault(False)
        sin_ticket_button.setDefault(False)
        sin_ticket_button.clicked.connect(_accept_sin_ticket)
        ly.addWidget(sin_ticket_button)

        ly.addSpacing(2)
        ly.addWidget(hint)
        ly.addWidget(scan_input)
        ly.addWidget(error_label)

        dlg.setLayout(ly)
        QTimer.singleShot(0, scan_input.setFocus)
        dlg.exec()
        # La forma de pago vale aunque conteste "solo ticket del cliente".
        return wants_copy, btn_tarjeta.isChecked(), sin_ticket

    def build_reprint_ticket(
        self,
        *,
        tipo: str,
        detalle: list[dict],
        cliente: str | None,
        employee_name: str,
        descuento_empleada: bool,
        created_at,
        monto_total=None,
        monto_monedero=None,
        pago_tarjeta: bool = False,
        descuento_programa=None,
    ) -> str | None:
        """Reconstruye el ticket de una operación YA registrada en la Libreta
        (para reimprimir si la impresora falló). No registra nada ni toca el
        carrito: presta el estado, arma el texto y lo devuelve todo como
        estaba. Abonos no tienen ticket → None.

        Una venta pagada en parte (o toda) con monedero lleva lo que se usó
        de saldo y el resto por cobrar con su método, tal como quedó
        guardado: sin eso el papel dice solo "TOTAL A PAGAR" y se cobraría
        el total otra vez. Es un dato histórico: NO se consulta el saldo de
        hoy ni el cashback. Sin monedero el ticket es el de siempre."""
        if tipo not in ("venta", "apartado"):
            return None
        items = [
            {
                "sku": str(line.get("sku", "")),
                "nombre": str(line.get("nombre", "")),
                "talla": str(line.get("talla", "")),
                "color": "",
                "precio": Decimal(str(line.get("precio", 0) or 0)),
                "cantidad": int(line.get("cantidad", 0) or 0),
                **({"promo_3pz": True} if line.get("promo_3pz") else {}),
                # E6: el % de empleada que tuvo, no el de hoy.
                **({"desc_empleada_pct": line["desc_empleada_pct"]} if line.get("desc_empleada_pct") else {}),
            }
            for line in (detalle or [])
        ]
        try:
            local_dt = created_at.astimezone() if created_at.tzinfo else created_at
            fecha_str = local_dt.strftime("%d/%m/%Y %H:%M")
        except Exception:  # noqa: BLE001
            fecha_str = None
        respaldo = (
            self._items, self._discount_active, self._employee_name, self._employee_code
        )
        respaldo_programa = getattr(self, "_descuento_programa_fijo", None)
        respaldo_compradora = self._compradora
        try:
            self._compradora = None  # la reimpresión no recalcula niveles
            self._items = items
            self._discount_active = bool(descuento_empleada)
            # E5-A: el % de mayoreo como quedó guardado, no el de hoy.
            self._descuento_programa_fijo = Decimal(str(descuento_programa)) if descuento_programa else None
            self._employee_name = employee_name or self._employee_name
            if tipo == "venta":
                canje = Decimal(str(monto_monedero or 0)).quantize(Decimal("0.01"))
                monedero = None
                if canje > 0:
                    _s, _d, total_items = self._compute_totals()
                    total = Decimal(str(monto_total if monto_total is not None else total_items))
                    monedero = {
                        "canje": canje,
                        "por_cobrar": max(total.quantize(Decimal("0.01")) - canje, Decimal("0.00")),
                        "metodo": "Tarjeta" if pago_tarjeta else "Efectivo",
                    }
                return self._build_venta_text(
                    fecha_str=fecha_str, reimpresion=True, monedero=monedero
                )
            return self._build_apartado_text(
                cliente or "", copy_label="CLIENTE", fecha_str=fecha_str, reimpresion=True
            )
        finally:
            (
                self._items, self._discount_active, self._employee_name, self._employee_code
            ) = respaldo
            self._descuento_programa_fijo = respaldo_programa
            self._compradora = respaldo_compradora

    # ─── Gasto de la tienda ──────────────────────────────────────────────

    #: Lo que más se compra de un día para otro.
    GASTOS_RAPIDOS = ("Bolsas", "Agua", "Papelería", "Limpieza", "Mandado", "Otro")

    def _on_gasto_tienda(self) -> None:
        """Apunta un gasto que salió del cajón. No es dinero de ella."""
        if not self._employee_code:
            QMessageBox.information(
                self, "Gasto", "Entra con tu gafete para apuntar un gasto."
            )
            return
        datos = self._ask_gasto()
        if datos is None:
            return
        from pos_uniformes.services.retiros_service import registrar_gasto

        try:
            with get_session() as session:
                registrar_gasto(
                    session,
                    monto=datos["monto"],
                    motivo=datos["motivo"],
                    employee_code=str(self._employee_code),
                )
        except Exception:  # noqa: BLE001
            _logger.exception("Venta rápida: no se pudo apuntar el gasto")
            self._avisar_sin_conexion()
            QMessageBox.warning(
                self, "Sin conexión",
                "No se pudo apuntar el gasto porque la PC principal no contesta.\n\n"
                "Apúntalo en un papel y vuelve a intentarlo cuando se quite el letrero "
                "rojo de arriba. No cierres el programa: las ventas siguen guardándose.",
            )
            return
        QMessageBox.information(
            self, "Apuntado",
            f"Gasto de ${datos['monto']:,.2f} apuntado.\n\n"
            "Ya le llegó a Daniel y el corte de hoy lo toma en cuenta.",
        )

    def _ask_gasto(self) -> dict | None:
        """Formulario táctil: cuánto y en qué. Devuelve {monto, motivo} o None."""
        from decimal import Decimal, InvalidOperation

        dlg = QDialog(self)
        dlg.setWindowTitle("Gasto de la tienda")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
            "QLineEdit { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 50px; padding: 0 14px; font-size: 18px; }"
        )
        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(10)

        titulo = QLabel("Gasto de la tienda")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(titulo)
        pista = QLabel(
            "Dinero del cajón que se usó para la tienda. A Daniel le llega el aviso "
            "y el corte de hoy ya lo descuenta."
        )
        pista.setWordWrap(True)
        pista.setStyleSheet("font-size: 12px; color: #8a8177;")
        ly.addWidget(pista)

        ly.addWidget(QLabel("¿Cuánto?"))
        monto_input = QLineEdit()
        monto_input.setPlaceholderText("0")
        ly.addWidget(monto_input)

        ly.addWidget(QLabel("¿En qué?"))
        motivo_input = QLineEdit()
        motivo_input.setPlaceholderText("Ej. bolsas, garrafón, taxi del mandado...")
        ly.addWidget(motivo_input)

        chips = QHBoxLayout()
        for que in self.GASTOS_RAPIDOS:
            chip = QPushButton(que)
            chip.setAutoDefault(False)
            if que == "Otro":
                chip.clicked.connect(lambda _c=False: (motivo_input.clear(), motivo_input.setFocus()))
            else:
                chip.clicked.connect(lambda _c=False, t=que: motivo_input.setText(t))
            chips.addWidget(chip)
        ly.addLayout(chips)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Apuntarlo")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(dlg.accept)
        botones.rejected.connect(dlg.reject)
        ly.addWidget(botones)

        while True:
            if dlg.exec() != int(QDialog.DialogCode.Accepted):
                return None
            crudo = monto_input.text().strip().replace("$", "").replace(",", "")
            try:
                monto = Decimal(crudo)
            except (InvalidOperation, ValueError):
                QMessageBox.information(dlg, "Gasto", "Escribe cuánto se gastó.")
                continue
            motivo = motivo_input.text().strip()
            if monto <= 0:
                QMessageBox.information(dlg, "Gasto", "El gasto tiene que ser mayor a cero.")
                continue
            if not motivo:
                QMessageBox.information(dlg, "Gasto", "Escribe en qué se gastó.")
                continue
            # Una cifra grande casi siempre es un dedazo: que lo confirme.
            if monto >= Decimal("1000"):
                ok = QMessageBox.question(
                    dlg, "Confirmar",
                    f"¿Seguro que fueron ${monto:,.2f} en {motivo}?",
                )
                if ok != QMessageBox.StandardButton.Yes:
                    continue
            return {"monto": monto, "motivo": motivo}

    # ─── Producto sin código ─────────────────────────────────────────────

    _SKU_SIN_CODIGO = "SIN-CODIGO"
    # Prendas de un toque en "Producto sin código" (Daniel, 2026-09-09).
    # 8 para que la cuadrícula 4×2 quede pareja; "Otro" limpia y deja escribir.
    PRENDAS_RAPIDAS = ("Blusa", "Playera", "Camisa", "Pantalón", "Chamarra", "Calceta", "Ropa interior", "Otro")

    def _on_producto_sin_codigo(self) -> None:
        if not self._employee_code:
            QMessageBox.warning(self, "Sin autorizar", "Escanea primero tu QR de empleada.")
            return
        datos = self._ask_producto_sin_codigo()
        if datos is None:
            self._scan_input.setFocus()
            return
        self._agregar_sin_codigo(datos["nombre"], datos["precio"], datos["cantidad"])
        self._flash_scan_hint("Agregado")
        self._scan_input.setFocus()

    def _agregar_sin_codigo(self, nombre: str, precio: Decimal, cantidad: int) -> None:
        """Línea manual del carrito. Misma descripción y precio → se suma a
        la línea existente. Va al ticket y a la Libreta como cualquier
        prenda (1 comisión por pieza; no toca inventario)."""
        nombre = " ".join(str(nombre).split())
        precio = Decimal(str(precio)).quantize(Decimal("0.01"))
        cantidad = max(1, int(cantidad))
        existente = next(
            (
                it for it in self._items
                if it["sku"] == self._SKU_SIN_CODIGO
                and it["nombre"].lower() == nombre.lower()
                and it["precio"] == precio
            ),
            None,
        )
        if existente:
            existente["cantidad"] += cantidad
        else:
            self._items.append(
                {
                    "sku": self._SKU_SIN_CODIGO,
                    "nombre": nombre,
                    "talla": "",
                    "color": "",
                    "precio": precio,
                    "cantidad": cantidad,
                }
            )
        self._refresh_items_table()
        self._refresh_totals()

    _ESTILO_TECLA = (
        "QPushButton { background: #ffffff; color: #2c2a27;"
        "  border: 1.5px solid #ddd0c0; border-radius: 12px;"
        "  min-height: 48px; font-size: 20px; font-weight: 700; }"
        "QPushButton:pressed { background: #f1e6d6; }"
    )
    _ESTILO_MONTO_INPUT = (
        "QLineEdit { background: #ffffff; color: #73341c;"
        "  border: 2px solid #a84f2d; border-radius: 12px;"
        "  min-height: 56px; padding: 0 14px; font-size: 26px; font-weight: 800; }"
    )

    @staticmethod
    def _teclado_numerico(destino: QLineEdit):
        """Teclado numérico en pantalla (táctil): 7 8 9 / 4 5 6 / 1 2 3 / . 0 ⌫.
        Escribe en `destino`; lo comparten 'producto sin código' y el
        anticipo del apartado."""
        from PyQt6.QtWidgets import QGridLayout

        teclado = QGridLayout()
        teclado.setSpacing(6)
        _TECLA = QuickSaleWidget._ESTILO_TECLA

        def _tecla(txt: str) -> None:
            actual = destino.text()
            if txt == "⌫":
                destino.setText(actual[:-1])
            elif txt == "." and "." in actual:
                return
            else:
                destino.setText(actual + txt)

        for i, txt in enumerate(("7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "⌫")):
            b = QPushButton(txt)
            b.setAutoDefault(False)
            b.setStyleSheet(_TECLA)
            b.setFixedHeight(56)  # alto fijo: el teclado no se estira
            b.clicked.connect(lambda _=False, t=txt: _tecla(t))
            teclado.addWidget(b, i // 3, i % 3)
        return teclado

    @staticmethod
    def _monto_de_texto(texto: str) -> Decimal | None:
        """'1,250.50' → Decimal; None si no es un monto."""
        raw = str(texto or "").strip().replace("$", "").replace(",", "")
        try:
            return Decimal(raw).quantize(Decimal("0.01"))
        except Exception:  # noqa: BLE001
            return None

    def _ask_producto_sin_codigo(self) -> dict | None:
        """Diálogo táctil: descripción, precio con teclado numérico en
        pantalla (no depende del teclado físico) y cantidad con −/+.
        Devuelve {nombre, precio, cantidad} o None si canceló."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Producto sin código")
        dlg.setMinimumWidth(520)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
            "QLineEdit { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 50px; padding: 0 14px; font-size: 18px; }"
        )
        ly = QVBoxLayout()
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(10)

        titulo = QLabel("Producto sin código")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(titulo)

        et = QLabel("¿Qué es?")
        et.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(et)
        nombre_input = QLineEdit()
        nombre_input.setPlaceholderText("Ej. Listón, parche, arreglo de bastilla...")

        # Chips de prendas (4×2, chicos): un toque llena "¿Qué es?" y salta
        # al precio. Escribir a mano quita la marca del chip.
        from PyQt6.QtWidgets import QButtonGroup, QGridLayout, QSizePolicy

        _CHIP = (
            "QPushButton { background: #ffffff; color: #2c2a27;"
            "  border: 1.5px solid #ddd0c0; border-radius: 10px;"
            "  min-height: 38px; padding: 0 6px; font-size: 14px; font-weight: 700; }"
            "QPushButton:checked { background: #f7e3d8; color: #73341c;"
            "  border: 2px solid #a84f2d; }"
            "QPushButton:pressed { background: #f1e6d6; }"
        )
        chips = QGridLayout()
        chips.setSpacing(6)
        grupo = QButtonGroup(dlg)
        grupo.setExclusive(True)
        columnas = 4

        def _elegir_prenda(nombre: str) -> None:
            if nombre == "Otro":
                nombre_input.blockSignals(True)
                nombre_input.clear()
                nombre_input.blockSignals(False)
                nombre_input.setFocus()
                return
            nombre_input.blockSignals(True)
            nombre_input.setText(nombre)
            nombre_input.blockSignals(False)
            precio_input.setFocus()

        for i, prenda in enumerate(self.PRENDAS_RAPIDAS):
            chip = QPushButton(prenda)
            chip.setObjectName("chipPrenda")
            chip.setCheckable(True)
            chip.setAutoDefault(False)
            chip.setStyleSheet(_CHIP)
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            chip.clicked.connect(lambda _=False, n=prenda: _elegir_prenda(n))
            grupo.addButton(chip)
            chips.addWidget(chip, i // columnas, i % columnas)
        for c in range(columnas):
            chips.setColumnStretch(c, 1)
        ly.addLayout(chips)
        ly.addWidget(nombre_input)

        def _desmarcar_chips(_t: str) -> None:
            marcado = grupo.checkedButton()
            if marcado is not None and marcado.text() != nombre_input.text():
                grupo.setExclusive(False)
                marcado.setChecked(False)
                grupo.setExclusive(True)

        nombre_input.textEdited.connect(_desmarcar_chips)

        et2 = QLabel("Precio por pieza")
        et2.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(et2)
        precio_input = QLineEdit()
        precio_input.setPlaceholderText("0.00")
        precio_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        precio_input.setStyleSheet(
            "QLineEdit { background: #ffffff; color: #73341c;"
            "  border: 2px solid #a84f2d; border-radius: 12px;"
            "  min-height: 56px; padding: 0 14px; font-size: 26px; font-weight: 800; }"
        )
        precio_row = QHBoxLayout()
        precio_row.setSpacing(8)
        signo = QLabel("$")
        signo.setStyleSheet("font-size: 28px; font-weight: 800; color: #73341c;")
        precio_row.addWidget(signo)
        precio_row.addWidget(precio_input, 1)
        ly.addLayout(precio_row)

        ly.addLayout(self._teclado_numerico(precio_input))

        # Cantidad en una sola fila, con el TOTAL en vivo a la derecha
        cant_row = QHBoxLayout()
        cant_row.setSpacing(10)
        et3 = QLabel("Cantidad")
        et3.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        cant_row.addWidget(et3)
        cantidad = {"n": 1}
        cant_label = QLabel("1")
        cant_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cant_label.setStyleSheet("font-size: 26px; font-weight: 800; color: #73341c;")
        cant_label.setFixedWidth(56)
        total_label = QLabel("Total: $0.00")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #73341c;")

        def _precio_actual() -> Decimal:
            raw = precio_input.text().strip().replace("$", "").replace(",", "")
            try:
                return Decimal(raw).quantize(Decimal("0.01"))
            except Exception:  # noqa: BLE001
                return Decimal("0.00")

        def _actualizar_total() -> None:
            total_label.setText(f"Total: ${_precio_actual() * cantidad['n']:,.2f}")

        def _cambiar_cant(d: int) -> None:
            cantidad["n"] = max(1, min(99, cantidad["n"] + d))
            cant_label.setText(str(cantidad["n"]))
            _actualizar_total()

        for txt, d in (("−", -1), ("+", 1)):
            b = QPushButton(txt)
            b.setAutoDefault(False)
            b.setStyleSheet(self._ESTILO_TECLA)
            b.setFixedSize(60, 52)
            b.clicked.connect(lambda _=False, dd=d: _cambiar_cant(dd))
            if txt == "−":
                cant_row.addWidget(b)
                cant_row.addWidget(cant_label)
            else:
                cant_row.addWidget(b)
        cant_row.addStretch(1)
        cant_row.addWidget(total_label)
        ly.addLayout(cant_row)
        precio_input.textChanged.connect(lambda _t: _actualizar_total())

        error_label = QLabel("")
        error_label.setStyleSheet(f"font-size: 13px; color: {_DANGER}; font-weight: 700;")
        error_label.setVisible(False)
        ly.addWidget(error_label)

        resultado: dict = {}

        def _confirmar() -> None:
            nombre = " ".join(nombre_input.text().split())
            raw = precio_input.text().strip().replace("$", "").replace(",", "")
            try:
                precio = Decimal(raw).quantize(Decimal("0.01"))
            except Exception:  # noqa: BLE001
                precio = Decimal("0.00")
            if not nombre:
                error_label.setText("Escribe qué es el producto.")
                error_label.setVisible(True)
                nombre_input.setFocus()
                return
            if precio <= 0:
                error_label.setText("Captura un precio válido.")
                error_label.setVisible(True)
                return
            resultado.update({"nombre": nombre, "precio": precio, "cantidad": cantidad["n"]})
            dlg.accept()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { background: #f8f2e9; color: #73341c;"
            "  border: 1px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 60px; font-size: 16px; font-weight: 700; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        btn_ok = QPushButton("🛒  Agregar al carrito")
        btn_ok.setStyleSheet(
            "QPushButton { background: #a84f2d; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 60px;"
            "  font-size: 17px; font-weight: 800; }"
            "QPushButton:pressed { background: #8a4326; }"
        )
        for button in (btn_cancel, btn_ok):
            button.setAutoDefault(False)
            button.setDefault(False)
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(_confirmar)
        btn_row.addWidget(btn_cancel, 1)
        btn_row.addWidget(btn_ok, 1)  # mitad y mitad: pie simétrico
        ly.addLayout(btn_row)

        dlg.setLayout(ly)
        QTimer.singleShot(0, nombre_input.setFocus)
        if dlg.exec() != QDialog.DialogCode.Accepted or not resultado:
            return None
        return resultado

    def _on_ticket_venta(self) -> None:
        if not self._items:
            QMessageBox.information(self, "Sin piezas", "Agrega piezas antes de generar ticket.")
            return
        # Una sola pregunta al imprimir: ¿copia? ¿pago con tarjeta? Con eso
        # la copia interna sale con la comisión descontada automáticamente y
        # la Libreta registra el neto — ya no hay checkbox en el diálogo de
        # impresión ni nada que apuntar a mano.
        if self._discount_active:
            wants_copy = True  # la COPIA EMPLEADA es automática
            card = self._ask_card_payment()
        else:
            wants_copy, card, sin_ticket = self._ask_venta_options()
            _s, _d, _t = self._compute_totals()
            if sin_ticket and self._canje_actual(_t) > 0:
                # Con saldo la venta se confirma en línea antes de todo.
                self._cobrar_con_monedero(card, False, sin_ticket=True)
                return
            if sin_ticket:
                # Se anota igual (piezas, comisiones, forma de pago) y el
                # carrito se vacía; nada va a la impresora. Reimpresión:
                # Libreta → 🖨 Reimprimir (build_reprint_ticket).
                if self._registrar_y_vaciar("venta", pago_tarjeta=card):
                    self._avisar_sin_ticket()
                self._scan_input.setFocus()
                return
        _subtotal, _desc, total_venta = self._compute_totals()
        if self._canje_actual(total_venta) > 0:
            self._cobrar_con_monedero(card, wants_copy)
            return
        tickets = [self._build_venta_text(monedero=self._monedero_para_ticket(total_venta, card))]
        if self._discount_active:
            tickets.append(self._build_employee_copy_text(terminal_commission=card))
        elif wants_copy:
            tickets.append(self._build_venta_text(store_copy=True, terminal_commission=card))
        # La Libreta registra HASTA que la impresión realmente arranca:
        # cerrar el diálogo sin imprimir no anota nada.
        route_tickets(
            self,
            "Ticket de venta",
            tickets,
            on_printed=lambda: self._registrar_y_vaciar("venta", pago_tarjeta=card),
            # "← Regresar": vuelve a la pregunta (copia / pago / sin ticket)
            # con el carrito intacto; nada se registró todavía.
            on_back=self._on_ticket_venta,
        )
        self._scan_input.setFocus()

    def _avisar_sin_ticket(self) -> None:
        """Confirmación breve, sin botón que tocar: se cierra sola."""
        aviso = QLabel("✅ Venta registrada sin ticket. Se puede reimprimir desde la Libreta.", self)
        aviso.setStyleSheet(
            "background: #2c2a27; color: #ffffff; border-radius: 12px;"
            " padding: 12px 18px; font-size: 15px; font-weight: 700;"
        )
        aviso.adjustSize()
        aviso.move(max(0, (self.width() - aviso.width()) // 2), max(0, self.height() - aviso.height() - 24))
        aviso.show()
        aviso.raise_()
        QTimer.singleShot(3500, aviso.deleteLater)

    def _on_abono(self) -> None:
        """Registra en la Libreta un abono a un apartado (sin comisión).

        No requiere carrito: la empleada anota cliente y monto — sustituye
        la anotación a mano en el ticket físico del apartado."""
        if not self._employee_code:
            QMessageBox.warning(self, "Sin autorizar", "Escanea primero tu QR de empleada.")
            return

        # Rediseño táctil (2026-09-05): toggles grandes de pago en vez del
        # checkbox chiquito; el botón de registrar es el protagonista.
        dlg = QDialog(self)
        dlg.setWindowTitle("Registrar abono")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
            "QLineEdit { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 48px; padding: 0 14px; font-size: 17px; }"
        )
        ly = QVBoxLayout()
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(12)

        titulo = QLabel("Abono a apartado")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(titulo)

        etiqueta_cliente = QLabel("Cliente (opcional)")
        etiqueta_cliente.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(etiqueta_cliente)
        cliente_input = QLineEdit()
        cliente_input.setPlaceholderText("Nombre del cliente...")
        ly.addWidget(cliente_input)

        etiqueta_monto = QLabel("Monto del abono")
        etiqueta_monto.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(etiqueta_monto)
        monto_input = QLineEdit()
        monto_input.setPlaceholderText("$ 0.00")
        monto_input.setStyleSheet(
            "QLineEdit { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 12px;"
            "  min-height: 52px; padding: 0 14px;"
            "  font-size: 22px; font-weight: 800; }"
        )
        ly.addWidget(monto_input)

        etiqueta_pago = QLabel("¿Cómo pagó?")
        etiqueta_pago.setStyleSheet(f"font-size: 13px; color: {_MUTED}; font-weight: 700;")
        ly.addWidget(etiqueta_pago)
        _TOGGLE = (
            "QPushButton { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 54px; font-size: 17px; font-weight: 700; }"
            "QPushButton:checked { background: #f7e3d8; color: #73341c;"
            "  border: 3px solid #a84f2d; }"
        )
        pago_row = QHBoxLayout()
        pago_row.setSpacing(10)
        btn_efectivo = QPushButton("✓ 💵  Efectivo")
        btn_tarjeta = QPushButton("💳  Tarjeta")
        for btn in (btn_efectivo, btn_tarjeta):
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setStyleSheet(_TOGGLE)
            pago_row.addWidget(btn)
        btn_efectivo.setChecked(True)

        def _set_pago(tarjeta: bool) -> None:
            btn_tarjeta.setChecked(tarjeta)
            btn_efectivo.setChecked(not tarjeta)
            btn_efectivo.setText("✓ 💵  Efectivo" if not tarjeta else "💵  Efectivo")
            btn_tarjeta.setText("✓ 💳  Tarjeta" if tarjeta else "💳  Tarjeta")

        btn_efectivo.clicked.connect(lambda: _set_pago(False))
        btn_tarjeta.clicked.connect(lambda: _set_pago(True))
        ly.addLayout(pago_row)

        error_label = QLabel("")
        error_label.setStyleSheet(f"font-size: 13px; color: {_DANGER}; font-weight: 700;")
        error_label.setVisible(False)
        ly.addWidget(error_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { background: #f8f2e9; color: #73341c;"
            "  border: 1px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 60px; font-size: 16px; font-weight: 700; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        btn_ok = QPushButton("💰  Registrar abono")
        btn_ok.setStyleSheet(
            "QPushButton { background: #a84f2d; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 60px;"
            "  font-size: 17px; font-weight: 800; }"
            "QPushButton:pressed { background: #8a4326; }"
        )
        for button in (btn_cancel, btn_ok):
            button.setAutoDefault(False)
            button.setDefault(False)
        btn_cancel.clicked.connect(dlg.reject)

        def _confirmar() -> None:
            nombre = cliente_input.text().strip() or None
            raw_monto = monto_input.text().strip().replace("$", "").replace(",", "")
            try:
                monto = Decimal(raw_monto).quantize(Decimal("0.01"))
            except Exception:  # noqa: BLE001
                monto = Decimal("0.00")
            if monto <= 0:
                error_label.setText("Captura un monto válido.")
                error_label.setVisible(True)
                return
            dlg.accept()
            self._registrar_abono(nombre, monto, pago_tarjeta=btn_tarjeta.isChecked())

        btn_ok.clicked.connect(_confirmar)
        btn_row.addWidget(btn_cancel, 1)
        btn_row.addWidget(btn_ok, 2)
        ly.addLayout(btn_row)

        dlg.setLayout(ly)
        QTimer.singleShot(0, cliente_input.setFocus)
        dlg.exec()
        self._scan_input.setFocus()

    def _registrar_abono(
        self,
        cliente: str | None,
        monto: Decimal,
        *,
        pago_tarjeta: bool,
        aviso: str = "Abono registrado",
    ) -> None:
        try:
            from pos_uniformes.services import libreta_local_queue_service as cola

            cola.encolar_operacion(
                self._entrada_abono(
                    cliente, monto, pago_tarjeta=pago_tarjeta, origen=self._origen_satelite()
                )
            )
            self._despues_de_encolar()
            self._flash_scan_hint(aviso)
        except Exception:  # noqa: BLE001
            _logger.exception("No se pudo registrar el abono en la Libreta")
            QMessageBox.warning(
                self, "Abono no registrado", "No se pudo guardar el abono; intentalo de nuevo."
            )

    def _entrada_abono(
        self,
        cliente: str | None,
        monto: Decimal,
        *,
        pago_tarjeta: bool,
        origen: str | None,
        operacion_uuid: str | None = None,
    ) -> dict:
        from datetime import timezone as _tz

        neto = self._apply_terminal_commission(monto) if pago_tarjeta else monto
        entrada = {
            "employee_code": str(self._employee_code or ""),
            "employee_name": str(self._employee_name or self._employee_code or ""),
            "tipo": "abono",
            "cliente": cliente,
            "items": [],
            "monto_total": str(monto),
            "monto_neto": str(neto),
            "pago_tarjeta": bool(pago_tarjeta),
            # Los abonos NO dan comisión — pero sí quedan registrados.
            "comisiones": 0,
            "descuento_empleada": False,
            "origen": origen,
            "created_at": datetime.now(_tz.utc).astimezone().isoformat(),
        }
        if operacion_uuid:
            # El anticipo de un apartado: identidad propia para reintentar.
            entrada["operacion_uuid"] = operacion_uuid
        return entrada

    def _on_ticket_apartado(self) -> None:
        if not self._items:
            QMessageBox.information(self, "Sin piezas", "Agrega piezas antes de generar ticket.")
            return

        total = sum(it["precio"] * it["cantidad"] for it in self._items)
        total_pzas = sum(it["cantidad"] for it in self._items)

        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo apartado")
        dlg.setFixedWidth(420)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {_WARM_BG}; }}
            QLabel#dlgTitle {{ font-size: 17px; font-weight: 600; color: {_TEXT}; }}
            QLabel#dlgSub {{ font-size: 12px; color: {_MUTED}; }}
            QLabel#dlgField {{ font-size: 13px; font-weight: 500; color: {_TEXT}; }}
            QLineEdit#dlgInput {{
                font-size: 15px; padding: 12px 16px;
                border: 1.5px solid {_BORDER}; border-radius: 10px;
                background: white; color: {_TEXT};
            }}
            QLineEdit#dlgInput:focus {{ border-color: {_BRAND}; }}
            QPushButton#dlgCancel {{
                font-size: 13px; padding: 10px 24px;
                background: transparent; color: {_MUTED};
                border: 1.5px solid {_BORDER}; border-radius: 10px;
            }}
            QPushButton#dlgCancel:hover {{ background: white; }}
            QPushButton#dlgOk {{
                font-size: 13px; font-weight: 600; padding: 10px 24px;
                background: {_BRAND}; color: white;
                border: none; border-radius: 10px;
            }}
            QPushButton#dlgOk:hover {{ background: {_BRAND_DARK}; }}
        """)

        ly = QVBoxLayout()
        ly.setContentsMargins(28, 24, 28, 24)
        ly.setSpacing(12)

        title = QLabel("Apartado")
        title.setObjectName("dlgTitle")
        ly.addWidget(title)

        sub = QLabel(f"{total_pzas} pieza{'s' if total_pzas != 1 else ''}  ·  Total: ${total:,.2f}")
        sub.setObjectName("dlgSub")
        ly.addWidget(sub)

        ly.addSpacing(4)

        field_label = QLabel("Nombre completo del cliente")
        field_label.setObjectName("dlgField")
        ly.addWidget(field_label)

        name_input = QLineEdit()
        name_input.setObjectName("dlgInput")
        name_input.setPlaceholderText("Nombre y apellidos...")
        ly.addWidget(name_input)

        # Anticipo: lo que la clienta deja HOY para apartar. Es dinero que
        # entra al cajón, así que se anota en la Libreta como abono (pedido
        # de Daniel 2026-09-06). Mínimo = 25% del total (regla del ticket).
        _sub, _desc, total_cobrar = self._compute_totals()
        minimo = self._round_total(
            (total_cobrar * self._MIN_LAYAWAY_PERCENT / Decimal("100")).quantize(
                Decimal("0.01")
            )
        )
        ly.addSpacing(4)
        anticipo_label = QLabel(
            f"Anticipo que deja hoy  (mínimo {self._MIN_LAYAWAY_PERCENT:.0f}%: ${minimo:,.2f})"
        )
        anticipo_label.setObjectName("dlgField")
        ly.addWidget(anticipo_label)
        anticipo_input = QLineEdit(f"{minimo:.2f}")
        anticipo_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        anticipo_input.setStyleSheet(self._ESTILO_MONTO_INPUT)
        anticipo_row = QHBoxLayout()
        anticipo_row.setSpacing(8)
        signo = QLabel("$")
        signo.setStyleSheet("font-size: 28px; font-weight: 800; color: #73341c;")
        anticipo_row.addWidget(signo)
        anticipo_row.addWidget(anticipo_input, 1)
        ly.addLayout(anticipo_row)
        ly.addLayout(self._teclado_numerico(anticipo_input))

        _TOGGLE = (
            "QPushButton { background: #ffffff; color: #2c2a27;"
            "  border: 2px solid #ddd0c0; border-radius: 14px;"
            "  min-height: 54px; font-size: 17px; font-weight: 700; }"
            "QPushButton:checked { background: #f7e3d8; color: #73341c;"
            "  border: 3px solid #a84f2d; }"
        )
        pago_row = QHBoxLayout()
        pago_row.setSpacing(10)
        btn_efectivo = QPushButton("✓ 💵  Efectivo")
        btn_tarjeta = QPushButton("💳  Tarjeta")
        for btn in (btn_efectivo, btn_tarjeta):
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setStyleSheet(_TOGGLE)
            pago_row.addWidget(btn)
        btn_efectivo.setChecked(True)

        def _set_pago(tarjeta: bool) -> None:
            btn_tarjeta.setChecked(tarjeta)
            btn_efectivo.setChecked(not tarjeta)
            btn_efectivo.setText("✓ 💵  Efectivo" if not tarjeta else "💵  Efectivo")
            btn_tarjeta.setText("✓ 💳  Tarjeta" if tarjeta else "💳  Tarjeta")

        btn_efectivo.clicked.connect(lambda: _set_pago(False))
        btn_tarjeta.clicked.connect(lambda: _set_pago(True))
        ly.addLayout(pago_row)

        error_label = QLabel("")
        error_label.setStyleSheet(f"font-size: 13px; color: {_DANGER}; font-weight: 700;")
        error_label.setVisible(False)
        ly.addWidget(error_label)

        ly.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("dlgCancel")
        btn_cancel.setAutoDefault(False)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_ok = QPushButton("Generar ticket")
        btn_ok.setObjectName("dlgOk")
        btn_ok.setAutoDefault(False)

        def _validar_y_aceptar() -> None:
            if not name_input.text().strip():
                error_label.setText("Escribe el nombre completo de la clienta.")
                error_label.setVisible(True)
                return
            monto = self._monto_de_texto(anticipo_input.text())
            if monto is None or monto <= 0:
                error_label.setText("Captura el anticipo que deja hoy.")
                error_label.setVisible(True)
                return
            if monto < minimo:
                error_label.setText(
                    f"El anticipo mínimo es ${minimo:,.2f} ({self._MIN_LAYAWAY_PERCENT:.0f}%)."
                )
                error_label.setVisible(True)
                return
            if monto > total_cobrar:
                error_label.setText(
                    f"El anticipo no puede pasar del total (${total_cobrar:,.2f})."
                )
                error_label.setVisible(True)
                return
            dlg.accept()

        btn_ok.clicked.connect(_validar_y_aceptar)
        btn_row.addWidget(btn_ok)
        ly.addLayout(btn_row)

        dlg.setLayout(ly)
        name_input.setFocus()
        name_input.returnPressed.connect(_validar_y_aceptar)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = name_input.text().strip()
        if not nombre:
            return
        anticipo = self._monto_de_texto(anticipo_input.text())
        if anticipo is not None and anticipo <= 0:
            anticipo = None
        anticipo_tarjeta = btn_tarjeta.isChecked()
        cliente_text = self._build_apartado_text(
            nombre, copy_label="CLIENTE", include_terms=True,
            anticipo=anticipo, anticipo_tarjeta=anticipo_tarjeta,
        )
        tienda_text = self._build_apartado_text(
            nombre, copy_label="COPIA TIENDA", include_terms=False,
            anticipo=anticipo, anticipo_tarjeta=anticipo_tarjeta,
        )
        route_tickets(
            self,
            "Apartado",
            [cliente_text, tienda_text],
            on_printed=lambda: self._registrar_y_vaciar(
                "apartado", cliente=nombre,
                anticipo=anticipo, anticipo_tarjeta=anticipo_tarjeta,
            ),
        )
        self._scan_input.setFocus()

    def _on_enviar_pedido(self) -> None:
        """Manda las piezas del carrito al tablero de pedidos del satélite."""
        if not self._items:
            QMessageBox.information(self, "Sin piezas", "Agrega piezas antes de enviar a preparar.")
            return
        from pos_uniformes.services import trabajos_service as svc
        from pos_uniformes.services.print_routing_cache_service import load_print_routing

        items = [
            {
                "sku": it.get("sku", ""),
                "nombre": it.get("nombre", ""),
                "talla": it.get("talla", ""),
                "cantidad": it.get("cantidad", 1),
            }
            for it in self._items
        ]
        try:
            _, origen = load_print_routing()
            with get_session() as session:
                svc.enviar_pedido(session, items, origen=origen)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "No se pudo enviar",
                f"No se pudo enviar el pedido al satélite.\n\n{exc}",
            )
            return
        QMessageBox.information(
            self,
            "Enviado a preparar",
            f"{len(items)} pieza(s) enviadas al tablero de pedidos del satélite.",
        )
        self._scan_input.setFocus()

    def _load_business_info(self) -> tuple[str, str, str]:
        # Memo por sesion: la info del negocio no cambia mientras se usa la app.
        if self._biz_info is not None:
            return self._biz_info
        self._biz_info = self._resolve_business_info()
        return self._biz_info

    def _resolve_business_info(self) -> tuple[str, str, str]:
        default = ("Uniformes", "", "")
        # Offline: usa el cache local -> evita el connect_timeout (5s) por ticket.
        if getattr(self.satellite, "offline_mode", False):
            cached = load_business_info_cache()
            return cached if cached and cached[0] else default
        # Online: la DB es la fuente de verdad; refresca el cache para offline.
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                info = (
                    config.nombre_negocio or "Uniformes",
                    config.telefono or "",
                    config.direccion or "",
                )
            try:
                save_business_info_cache(*info)
            except Exception:
                pass
            return info
        except Exception:
            # Marcarlo aquí ahorra el timeout de 5 s a todo lo que venga
            # después: este suele ser el primero que choca con la pared,
            # porque se arma un ticket en cuanto se cobra algo.
            self._avisar_sin_conexion()
            cached = load_business_info_cache()
            return cached if cached and cached[0] else default

    def _build_items_block(self, lines: list[str], items: list[dict] | None = None) -> None:
        first = True
        for it in self._items if items is None else items:
            if not first:
                lines.append(tk_mid())
            first = False
            for dl in textwrap.wrap(it["nombre"], width=_TIW) or [it["nombre"]]:
                lines.append(tk_line(dl))
            # La talla viaja con el precio en el mismo renglón. Antes ocupaba
            # uno para ella sola: tres renglones por prenda, y un ticket de diez
            # prendas era una escalera de treinta. Dice lo mismo en dos.
            sub = it["precio"] * it["cantidad"]
            meta = f"{it['cantidad']} x ${tk_fmt(it['precio'])}"
            if it["talla"]:
                meta = f"T.{it['talla']}  {meta}"
            tk_product_price(meta, f"${tk_fmt(sub)}", lines)

    @staticmethod
    def _append_terms(lines: list[str], terms: str) -> None:
        lines.append("")
        lines.append("Términos y Condiciones".center(_TW))
        for term_line in terms.split("\n"):
            lines.extend(
                textwrap.wrap(term_line, width=_TW, subsequent_indent="   ") or [term_line]
            )

    def _build_venta_text(
        self,
        *,
        store_copy: bool = False,
        terminal_commission: bool = False,
        fecha_str: str | None = None,
        reimpresion: bool = False,
        monedero: dict | None = None,
    ) -> str:
        """Ticket de venta. Con store_copy=True genera la copia interna:
        mismo formato de articulos y totales, pero sin los datos que ve el
        cliente (encabezado del negocio, leyendas y agradecimiento).

        terminal_commission=True (solo para la copia interna) muestra cada
        precio unitario ya con el 6% de la terminal descontado y redondeado."""
        biz_name, biz_phone, biz_addr = self._load_business_info()
        now = fecha_str or datetime.now().strftime("%d/%m/%Y %H:%M")
        items = self._commission_items() if terminal_commission else self._items
        subtotal, discount, total = self._compute_totals(items)

        lines: list[str] = []

        if store_copy:
            lines.append("COPIA TIENDA".center(_TW))
        else:
            # El MISMO encabezado que el POS principal: logo cuando se puede
            # y la dirección partida. Estaba escrito aparte aquí, y por eso
            # el kiosko imprimía el nombre a secas con la dirección saliéndose
            # del papel (Daniel, 2026-10-09).
            from pos_uniformes.services.sale_ticket_text_service import (
                encabezado_de_ticket,
            )

            lines += encabezado_de_ticket(biz_name, biz_addr, biz_phone)
        lines.append("Ticket de venta".center(_TW))
        if reimpresion:
            lines.append("*** REIMPRESIÓN ***".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Atendió:", self._employee_name or self._employee_code or "", lines)

        lines.append(tk_mid())
        lines.append(tk_center("ARTÍCULOS"))
        lines.append(tk_mid())
        self._build_items_block(lines, items)

        lines.append(tk_mid())
        # El resumen va junto, sin regla de por medio: cuántas piezas y cuánto
        # suman son la misma pregunta.
        piezas = sum(int(it["cantidad"]) for it in items)
        articulos = len(items)
        lines.append(
            tk_line(
                f"{articulos} artículo{'s' if articulos != 1 else ''}"
                f" · {piezas} pieza{'s' if piezas != 1 else ''}"
            )
        )
        lines.append(tk_row("Subtotal:", f"${tk_fmt(subtotal)}"))
        if discount > 0:
            lines.append(tk_row(self._etiqueta_descuento_ticket(), f"-${tk_fmt(discount)}"))
        # El total entre dos reglas dobles: es lo primero que se busca al
        # mirar el papel, y antes pesaba lo mismo que «Subtotal».
        # El total en su propio recuadro doble: es lo primero que se busca al
        # mirar el papel. No se puede unir al recuadro de arriba porque CP850 no
        # tiene las uniones simple↔doble, así que se cierra el de los artículos
        # y el total va aparte — que además lo hace resaltar más.
        lines.append(tk_bot())
        lines.append(tk_dbl_top())
        lines.append(tk_dbl_row("TOTAL A PAGAR:", f"${tk_fmt(total)}"))
        lines.append(tk_dbl_bot())
        if monedero:
            lines += lineas_ticket_monedero(monedero, tk_row)

        if not store_copy:
            self._append_terms(lines, self._TERMS_VENTA)
            lines.append("")
            lines.append("Gracias por su compra.".center(_TW))
            self._append_temporada(lines)

        return "\n".join(lines)

    @staticmethod
    def _append_temporada(lines: list[str]) -> None:
        """El detalle del calendario al pie del ticket, si hoy hay temporada.

        Va **después** del «Gracias por su compra» y solo en la copia del
        cliente: la de la tienda se archiva y no necesita adornos. La mayor
        parte del año no agrega nada — y eso está bien, porque un adorno que
        sale siempre deja de notarse.
        """
        # Se arma aparte y se agrega solo si salió completo: el dibujo de ASCII
        # se armaba FUERA de la red, y si tronaba se llevaba el ticket entero
        # (se vio el 20/10, primer día de Halloween, porque la prueba que lo
        # cuidaba nunca llegaba a esa línea).
        try:
            from pos_uniformes.services.temporada_service import (
                actual,
                marcador_de_ticket,
                renglones_de_ticket,
            )

            temporada = actual()
            if temporada is None:
                return
            marcador = marcador_de_ticket()
            if marcador:
                # El dibujo de verdad. Quien no sepa imprimir puntos lo cambia
                # por el de ASCII (`sin_marcadores`), que para eso sigue existiendo.
                adorno = ["", marcador, temporada.saludo.center(_TW)]
            else:
                adorno = [""] + [renglon.center(_TW) for renglon in renglones_de_ticket()]
        except Exception:  # noqa: BLE001 — un adorno jamás detiene un ticket
            return
        lines.extend(adorno)

    def _build_apartado_text(
        self,
        cliente: str,
        *,
        copy_label: str = "",
        include_terms: bool = True,
        fecha_str: str | None = None,
        reimpresion: bool = False,
        anticipo: Decimal | None = None,
        anticipo_tarjeta: bool = False,
    ) -> str:
        biz_name, biz_phone, biz_addr = self._load_business_info()
        now = fecha_str or datetime.now().strftime("%d/%m/%Y %H:%M")
        subtotal, discount, total = self._compute_totals()
        minimo = self._round_total(
            (total * self._MIN_LAYAWAY_PERCENT / Decimal("100")).quantize(Decimal("0.01"))
        )

        from pos_uniformes.services.sale_ticket_text_service import (
            encabezado_de_ticket,
        )

        lines: list[str] = []
        lines += encabezado_de_ticket(biz_name, biz_addr, biz_phone)
        lines.append("Ticket de apartado".center(_TW))
        if reimpresion:
            lines.append("*** REIMPRESIÓN ***".center(_TW))
        if copy_label:
            lines.append(f"- {copy_label} -".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Cliente:", cliente, lines)
        tk_field("Atendió:", self._employee_name or self._employee_code or "", lines)

        lines.append(tk_mid())
        lines.append(tk_center("PRODUCTOS"))
        lines.append(tk_mid())
        self._build_items_block(lines)

        lines.append(tk_mid())
        lines.append(tk_row("Subtotal:", f"${tk_fmt(subtotal)}"))
        if discount > 0:
            lines.append(tk_row(self._etiqueta_descuento_ticket(), f"-${tk_fmt(discount)}"))
        lines.append(tk_dbl())
        lines.append(tk_row("TOTAL:", f"${tk_fmt(total)}"))
        lines.append(tk_mid())
        lines.append(
            tk_row(
                f"Apartado minimo ({self._MIN_LAYAWAY_PERCENT:.0f}%):",
                f"${tk_fmt(minimo)}",
            )
        )
        # El anticipo NO se repite aquí (pedido de Daniel 2026-09-06): va
        # una sola vez, como primer renglón del registro de abonos.
        restante: Decimal | None = None
        if anticipo is not None:
            restante = (Decimal(str(total)) - anticipo).quantize(Decimal("0.01"))
        lines.append(tk_bot())

        lines.append("")
        lines.append("Registro de abonos".center(_TW))
        lines.append(tk_top())
        lines.append(tk_line("Fecha     Monto     Restante"))
        renglones = 5
        if anticipo is not None and restante is not None:
            # El anticipo (lo que dejó HOY) ocupa el primer renglón del
            # registro; marca la forma de pago si fue con tarjeta.
            forma = " (tarjeta)" if anticipo_tarjeta else ""
            lines.append(tk_mid())
            lines.append(
                tk_line(
                    f"{now[:5]:<9} ${tk_fmt(anticipo):<8} ${tk_fmt(restante)}{forma}"
                )
            )
            renglones = 4
        for _ in range(renglones):
            lines.append(tk_mid())
            lines.append(tk_line(""))
        lines.append(tk_bot())

        if include_terms:
            self._append_terms(lines, self._TERMS_APARTADO)

        lines.append("")
        lines.append("")
        lines.append(("_" * 28).center(_TW))
        lines.append("Firma del cliente".center(_TW))

        lines.append("")
        lines.append("Conserve su comprobante.".center(_TW))

        return "\n".join(lines)

    def _build_employee_copy_text(self, *, terminal_commission: bool = False) -> str:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        def _unit(precio, it=None) -> Decimal:
            # E6: el % de su nivel en ese renglón; si no trae, el 5 % de siempre.
            pct = Decimal(str((it or {}).get("desc_empleada_pct") or self._DISCOUNT_PERCENT))
            unit = (Decimal(str(precio)) * (Decimal("100") - pct) / Decimal("100")).quantize(Decimal("0.01"))
            if terminal_commission:
                unit = self._apply_terminal_commission(unit)
            return unit

        lines: list[str] = []
        lines.append("COPIA EMPLEADA".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Atendió:", self._employee_name or self._employee_code or "", lines)
        if self._compradora is not None:
            from pos_uniformes.services.incentivo_empleada_service import fmt_pct

            tk_field("Compra:", f"{self._compradora.nombre} ({fmt_pct(self._compradora.porcentaje)})", lines)

        lines.append(tk_mid())
        first = True
        for it in self._items:
            if not first:
                lines.append(tk_mid())
            first = False
            unit = _unit(it["precio"], it)
            sub = (unit * it["cantidad"]).quantize(Decimal("0.01"))
            for dl in textwrap.wrap(it["nombre"], width=_TIW) or [it["nombre"]]:
                lines.append(tk_line(dl))
            if it["talla"]:
                lines.append(tk_line(f"Talla: {it['talla']}"))
            tk_product_price(
                f"{it['cantidad']} x ${tk_fmt(unit)}",
                f"${tk_fmt(sub)}",
                lines,
            )

        raw_total = sum(
            _unit(it["precio"], it) * it["cantidad"] for it in self._items
        )
        total = self._round_total(raw_total.quantize(Decimal("0.01")))

        lines.append(tk_dbl())
        lines.append(tk_row("TOTAL:", f"${tk_fmt(total)}"))
        lines.append(tk_bot())

        return "\n".join(lines)

    def _on_logout(self) -> None:
        self._employee_code = None
        self._employee_name = None
        self._items.clear()
        self._compradora = None
        self._discount_active = False
        self._discount_check.setChecked(False)
        self._cliente = None
        self._usar_saldo = False
        self._usar_descuento_programa = False
        self._refresh_items_table()
        self._refresh_totals()
        self._sale_widget.setVisible(False)
        self._gate_widget.setVisible(True)
        self._gate_input.clear()
        self._gate_error.setVisible(False)
        self.refrescar_pie_gafete()
        QTimer.singleShot(0, self._gate_input.setFocus)

    # ─── API pública ─────────────────────────────────────────────────────

    def logout(self) -> None:
        """Cierra sesión, borra la venta y vuelve al escaneo de empleada."""
        self._on_logout()

    def is_session_active(self) -> bool:
        return bool(self._employee_code)

    def focus_input(self) -> None:
        if self._employee_code:
            self._scan_input.setFocus()
        else:
            self._gate_input.setFocus()
