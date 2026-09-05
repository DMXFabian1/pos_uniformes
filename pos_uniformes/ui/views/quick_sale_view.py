"""Venta Rápida — escaneo rápido con lista editable y gate de empleada."""

from __future__ import annotations

import logging
import re
import textwrap
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
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
QLabel#gateEmoji {{ font-size: 36px; }}
QLabel#gateTitle {{
    font-size: 18px; font-weight: 600; color: {_TEXT};
}}
QLabel#gateHint {{
    font-size: 13px; color: {_MUTED};
}}
QLineEdit#gateInput {{
    font-size: 18px; padding: 14px 20px;
    border: 1.5px solid {_BORDER}; border-radius: 10px;
    background: {_WARM_BG}; color: {_TEXT}; min-width: 320px;
}}
QLineEdit#gateInput:focus {{ border-color: {_BRAND}; background: white; }}
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


class QuickSaleWidget(QWidget):
    """Página de Venta Rápida para la app satélite."""

    _SCAN_HINT_DEFAULT = "Enter para agregar"

    def __init__(self, satellite: "QuoteSatelliteWindow"):
        super().__init__()
        self.satellite = satellite
        self._employee_code: str | None = None
        self._employee_name: str | None = None
        self._items: list[dict] = []
        self._discount_active = False
        self._biz_info: tuple[str, str, str] | None = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._gate_widget = self._build_gate()
        layout.addWidget(self._gate_widget)

        self._sale_widget = self._build_sale_view()
        self._sale_widget.setVisible(False)
        layout.addWidget(self._sale_widget)

        self.setLayout(layout)

    # ─── Gate de empleada ────────────────────────────────────────────────

    def _build_gate(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("gateRoot")
        wrapper.setStyleSheet(_GATE_STYLE)
        outer = QVBoxLayout()
        outer.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setObjectName("gateCard")
        cl = QVBoxLayout()
        cl.setContentsMargins(48, 40, 48, 40)
        cl.setSpacing(12)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        emoji = QLabel("📋")
        emoji.setObjectName("gateEmoji")
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(emoji)

        title = QLabel("Venta rapida")
        title.setObjectName("gateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        hint = QLabel("Escanea tu QR de empleada para comenzar")
        hint.setObjectName("gateHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(hint)

        cl.addSpacing(8)

        self._gate_input = QLineEdit()
        self._gate_input.setObjectName("gateInput")
        self._gate_input.setPlaceholderText("VEND-1")
        self._gate_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gate_input.returnPressed.connect(self._on_gate_scan)
        cl.addWidget(self._gate_input, 0, Qt.AlignmentFlag.AlignCenter)

        self._gate_error = QLabel("")
        self._gate_error.setObjectName("gateError")
        self._gate_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gate_error.setVisible(False)
        cl.addWidget(self._gate_error)

        card.setLayout(cl)
        outer.addStretch()
        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()
        wrapper.setLayout(outer)
        return wrapper

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

            if not emp:
                self._gate_error.setText(f"Codigo '{code}' no encontrado o inactivo.")
                self._gate_error.setVisible(True)
                self._gate_input.clear()
                self._gate_input.setFocus()
                return
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
        # Filas altas: los botones +/−/eliminar se tocan con el dedo.
        self._items_table.verticalHeader().setDefaultSectionSize(52)
        self._items_table.setStyleSheet(f"""
            QTableWidget {{
                background: white; border: none; font-size: 13px; color: {_TEXT};
            }}
            QTableWidget::item {{
                padding: 8px 10px; border-bottom: 1px solid #f0e6db;
            }}
            QTableWidget::item:alternate {{ background: {_WARM_BG}; }}
            QTableWidget::item:selected {{ background: {_BRAND_LIGHT}; color: {_TEXT}; }}
            QHeaderView::section {{
                background: {_WARM_BG}; color: {_MUTED}; font-weight: 600;
                font-size: 11px; padding: 8px 10px; border: none;
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
            if self.satellite.offline_mode:
                snap = self.satellite._kiosk_lookup_from_cache(sku)
            else:
                with get_session() as session:
                    snap = load_quote_kiosk_lookup_snapshot(session, sku=sku)
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
                "nombre": snap.product_name,
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
            self._items_table.setRowHeight(row, 52)

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
        if self._discount_active and self._items:
            meta += f"  ·  Desc. (-${discount:,.2f})"
        self._total_meta.setText(meta)

    def _build_row_actions(self, row: int) -> QWidget:
        """[−] [+] [🗑] por renglón, tamaño dedo (pedido de Daniel)."""
        _BASE = (
            "QPushButton {{ background: #ffffff; border: 1.5px solid {borde};"
            "  border-radius: 10px; font-size: 17px; font-weight: 800;"
            "  color: {color}; }}"
            "QPushButton:pressed {{ background: {press}; }}"
        )
        btn_minus = QPushButton("−")
        btn_minus.setToolTip("Quitar 1 pieza")
        btn_minus.setStyleSheet(_BASE.format(borde=_BORDER, color=_TEXT, press="#f1e6d6"))
        btn_minus.clicked.connect(lambda checked=False, r=row: self._on_remove(r))

        btn_plus = QPushButton("+")
        btn_plus.setToolTip("Agregar 1 pieza")
        btn_plus.setStyleSheet(_BASE.format(borde=_BORDER, color=_TEXT, press="#f1e6d6"))
        btn_plus.clicked.connect(lambda checked=False, r=row: self._on_add_one(r))

        btn_trash = QPushButton("🗑")
        btn_trash.setToolTip("Eliminar la línea completa")
        btn_trash.setStyleSheet(_BASE.format(borde="#e2b7ad", color=_DANGER, press="#fde3dd"))
        btn_trash.clicked.connect(lambda checked=False, r=row: self._on_delete_line(r))

        holder = QWidget()
        holder.setFixedHeight(52)
        ly = QHBoxLayout(holder)
        ly.setContentsMargins(0, 0, 6, 0)
        ly.setSpacing(5)
        for btn in (btn_minus, btn_plus, btn_trash):
            btn.setFixedSize(48, 42)  # tamaño exacto: nunca se corta
            ly.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
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
        else:
            self._discount_active = False
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
        if self._discount_active:
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
            self._items.clear()
            self._refresh_items_table()
            self._refresh_totals()
            self._scan_input.setFocus()

    # ─── Tickets ─────────────────────────────────────────────────────────

    _TERMS_VENTA = (
        "1. Revise su mercancia antes de retirarse del establecimiento.\n"
        "2. Tiene 15 dias naturales para realizar cambios presentando este ticket. La prenda debe estar en buen estado y con sus etiquetas.\n"
        "3. Conserve este ticket como comprobante de pago.\n"
        "4. Para cualquier aclaracion, presente este ticket.\n"
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
        neto = Decimal("0.00")
        for it in self._items:
            unit = Decimal(str(it["precio"]))
            if self._discount_active:
                unit = (unit * discount_factor).quantize(Decimal("0.01"))
            unit = self._apply_terminal_commission(unit)
            neto += unit * int(it["cantidad"])
        return neto.quantize(Decimal("0.01"))

    def _registrar_en_libreta(
        self, tipo: str, *, cliente: str | None = None, pago_tarjeta: bool = False
    ) -> None:
        """Anota la operación en la Libreta: local primero (nunca bloquea el
        mostrador ni pierde el registro), y un hilo la sube a la base.

        Sustituye la libreta física y la copia de ticket que solo servía
        para registrar."""
        try:
            from datetime import timezone as _tz

            from pos_uniformes.services import libreta_local_queue_service as cola

            _subtotal, _descuento, total = self._compute_totals()
            total = Decimal(str(total)).quantize(Decimal("0.01"))
            neto = self._monto_neto_actual(total, pago_tarjeta=pago_tarjeta)
            # Reimprimir el mismo ticket no debe anotar la venta dos veces.
            key = (
                tipo,
                cliente,
                str(total),
                tuple((it["sku"], int(it["cantidad"])) for it in self._items),
            )
            if key == getattr(self, "_last_libreta_key", None):
                return
            self._last_libreta_key = key

            origen: str | None = None
            try:
                from pos_uniformes.services.satellite_identity_service import get_satellite_id

                origen = get_satellite_id()
            except Exception:  # noqa: BLE001
                pass

            cola.encolar_operacion(
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
                        }
                        for it in self._items
                    ],
                    "monto_total": str(total),
                    "monto_neto": str(neto),
                    "pago_tarjeta": bool(pago_tarjeta),
                    "descuento_empleada": bool(self._discount_active),
                    "origen": origen,
                    "created_at": datetime.now(_tz.utc).astimezone().isoformat(),
                }
            )
            self._drenar_libreta_en_background()
        except Exception:  # noqa: BLE001 — la Libreta nunca rompe el flujo de tickets
            _logger.exception("No se pudo registrar la operacion en la Libreta")

    def _registrar_y_vaciar(
        self, tipo: str, *, cliente: str | None = None, pago_tarjeta: bool = False
    ) -> None:
        """Anota en la Libreta y vacía el carrito en el mismo acto.

        Si el carrito sobreviviera a la impresión, agregar una pieza más y
        reimprimir anotaría la venta dos veces (3 pzs y luego 4 = 7), y la
        siguiente clienta heredaría piezas ajenas. Los tickets ya quedaron
        armados como texto, así que reimprimir en la misma ventana sigue
        funcionando."""
        self._registrar_en_libreta(tipo, cliente=cliente, pago_tarjeta=pago_tarjeta)
        self._items.clear()
        self._discount_active = False
        self._discount_check.setChecked(False)
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

                with get_session() as session:
                    cola.drenar_pendientes(session)
            except Exception:  # noqa: BLE001
                _logger.debug("Drenado de libreta pospuesto", exc_info=True)

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

    def _ask_venta_options(self) -> tuple[bool, bool]:
        """Pregunta copia interna y forma de pago en un solo diálogo.

        Devuelve (con_copia, pago_tarjeta). Default: sin copia, efectivo.
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

        def _accept_with_copy() -> None:
            nonlocal wants_copy
            wants_copy = True
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

        ly.addSpacing(2)
        ly.addWidget(hint)
        ly.addWidget(scan_input)
        ly.addWidget(error_label)

        dlg.setLayout(ly)
        QTimer.singleShot(0, scan_input.setFocus)
        dlg.exec()
        # La forma de pago vale aunque conteste "solo ticket del cliente".
        return wants_copy, btn_tarjeta.isChecked()

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
            wants_copy, card = self._ask_venta_options()
        tickets = [self._build_venta_text()]
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
        )
        self._scan_input.setFocus()

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
        self, cliente: str | None, monto: Decimal, *, pago_tarjeta: bool
    ) -> None:
        try:
            from datetime import timezone as _tz

            from pos_uniformes.services import libreta_local_queue_service as cola

            neto = monto
            if pago_tarjeta:
                neto = self._apply_terminal_commission(monto)
            origen: str | None = None
            try:
                from pos_uniformes.services.satellite_identity_service import get_satellite_id

                origen = get_satellite_id()
            except Exception:  # noqa: BLE001
                pass
            cola.encolar_operacion(
                {
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
            )
            self._drenar_libreta_en_background()
            self._flash_scan_hint("Abono registrado")
        except Exception:  # noqa: BLE001
            _logger.exception("No se pudo registrar el abono en la Libreta")
            QMessageBox.warning(
                self, "Abono no registrado", "No se pudo guardar el abono; intentalo de nuevo."
            )

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

        ly.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("dlgCancel")
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_ok = QPushButton("Generar ticket")
        btn_ok.setObjectName("dlgOk")
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_ok)
        ly.addLayout(btn_row)

        dlg.setLayout(ly)
        name_input.setFocus()
        name_input.returnPressed.connect(dlg.accept)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = name_input.text().strip()
        if not nombre:
            return
        cliente_text = self._build_apartado_text(
            nombre, copy_label="CLIENTE", include_terms=True
        )
        tienda_text = self._build_apartado_text(
            nombre, copy_label="COPIA TIENDA", include_terms=False
        )
        route_tickets(
            self,
            "Apartado",
            [cliente_text, tienda_text],
            on_printed=lambda: self._registrar_y_vaciar("apartado", cliente=nombre),
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
            if it["talla"]:
                lines.append(tk_line(f"Talla: {it['talla']}"))
            sub = it["precio"] * it["cantidad"]
            tk_product_price(
                f"{it['cantidad']} x ${tk_fmt(it['precio'])}",
                f"${tk_fmt(sub)}",
                lines,
            )

    @staticmethod
    def _append_terms(lines: list[str], terms: str) -> None:
        lines.append("")
        lines.append("Terminos y Condiciones".center(_TW))
        for term_line in terms.split("\n"):
            lines.extend(
                textwrap.wrap(term_line, width=_TW, subsequent_indent="   ") or [term_line]
            )

    def _build_venta_text(
        self, *, store_copy: bool = False, terminal_commission: bool = False
    ) -> str:
        """Ticket de venta. Con store_copy=True genera la copia interna:
        mismo formato de articulos y totales, pero sin los datos que ve el
        cliente (encabezado del negocio, leyendas y agradecimiento).

        terminal_commission=True (solo para la copia interna) muestra cada
        precio unitario ya con el 6% de la terminal descontado y redondeado."""
        biz_name, biz_phone, biz_addr = self._load_business_info()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        items = self._commission_items() if terminal_commission else self._items
        subtotal, discount, total = self._compute_totals(items)

        lines: list[str] = []

        if store_copy:
            lines.append("COPIA TIENDA".center(_TW))
        else:
            lines.append(biz_name.center(_TW))
            if biz_addr:
                lines.append(biz_addr.center(_TW))
            if biz_phone:
                lines.append(f"Tel: {biz_phone}".center(_TW))
        lines.append("Ticket de venta".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Atendio:", self._employee_name or self._employee_code or "", lines)

        lines.append(tk_mid())
        lines.append(tk_center("ARTICULOS"))
        lines.append(tk_mid())
        self._build_items_block(lines, items)

        lines.append(tk_mid())
        lines.append(tk_row("Subtotal:", f"${tk_fmt(subtotal)}"))
        if self._discount_active:
            lines.append(tk_row("Descuento:", f"-${tk_fmt(discount)}"))
        lines.append(tk_dbl())
        lines.append(tk_row("TOTAL A PAGAR:", f"${tk_fmt(total)}"))
        lines.append(tk_bot())

        if not store_copy:
            self._append_terms(lines, self._TERMS_VENTA)
            lines.append("")
            lines.append("Gracias por su compra.".center(_TW))

        return "\n".join(lines)

    def _build_apartado_text(
        self,
        cliente: str,
        *,
        copy_label: str = "",
        include_terms: bool = True,
    ) -> str:
        biz_name, biz_phone, biz_addr = self._load_business_info()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        subtotal, discount, total = self._compute_totals()
        minimo = self._round_total(
            (total * self._MIN_LAYAWAY_PERCENT / Decimal("100")).quantize(Decimal("0.01"))
        )

        lines: list[str] = []

        lines.append(biz_name.center(_TW))
        if biz_addr:
            lines.append(biz_addr.center(_TW))
        if biz_phone:
            lines.append(f"Tel: {biz_phone}".center(_TW))
        lines.append("Ticket de apartado".center(_TW))
        if copy_label:
            lines.append(f"- {copy_label} -".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Cliente:", cliente, lines)
        tk_field("Atendio:", self._employee_name or self._employee_code or "", lines)

        lines.append(tk_mid())
        lines.append(tk_center("PRODUCTOS"))
        lines.append(tk_mid())
        self._build_items_block(lines)

        lines.append(tk_mid())
        lines.append(tk_row("Subtotal:", f"${tk_fmt(subtotal)}"))
        if self._discount_active:
            lines.append(tk_row("Descuento:", f"-${tk_fmt(discount)}"))
        lines.append(tk_dbl())
        lines.append(tk_row("TOTAL:", f"${tk_fmt(total)}"))
        lines.append(tk_mid())
        lines.append(
            tk_row(
                f"Apartado minimo ({self._MIN_LAYAWAY_PERCENT:.0f}%):",
                f"${tk_fmt(minimo)}",
            )
        )
        lines.append(tk_bot())

        lines.append("")
        lines.append("Registro de abonos".center(_TW))
        lines.append(tk_top())
        lines.append(tk_line("Fecha     Monto     Restante"))
        for _ in range(5):
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
        factor = (Decimal("100") - self._DISCOUNT_PERCENT) / Decimal("100")

        def _unit(precio) -> Decimal:
            unit = (Decimal(str(precio)) * factor).quantize(Decimal("0.01"))
            if terminal_commission:
                unit = self._apply_terminal_commission(unit)
            return unit

        lines: list[str] = []
        lines.append("COPIA EMPLEADA".center(_TW))

        lines.append(tk_top())
        tk_field("Fecha:", now, lines)
        tk_field("Atendio:", self._employee_name or self._employee_code or "", lines)

        lines.append(tk_mid())
        first = True
        for it in self._items:
            if not first:
                lines.append(tk_mid())
            first = False
            unit = _unit(it["precio"])
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
            _unit(it["precio"]) * it["cantidad"] for it in self._items
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
        self._discount_active = False
        self._discount_check.setChecked(False)
        self._refresh_items_table()
        self._refresh_totals()
        self._sale_widget.setVisible(False)
        self._gate_widget.setVisible(True)
        self._gate_input.clear()
        self._gate_error.setVisible(False)
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
