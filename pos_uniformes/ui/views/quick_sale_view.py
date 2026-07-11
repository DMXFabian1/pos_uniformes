"""Venta Rápida — escaneo rápido con lista editable y gate de empleada."""

from __future__ import annotations

import logging
import textwrap
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
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
    def _clean_scanned_code(raw: str) -> str:
        clean = "".join(c for c in raw if c.isprintable()).strip()
        # QR scanner sends HID keycodes; Spanish keyboard maps : → Ñ, - → '
        clean = clean.replace("Ñ", ":").replace("ñ", ":").replace("'", "-")
        clean = clean.upper()
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

        scan_hint = QLabel("Enter para agregar")
        scan_hint.setObjectName("scanHint")
        sb_layout.addWidget(scan_hint)

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
        self._items_table.setColumnWidth(4, 50)
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

    def _on_scan_and_add(self) -> None:
        sku = self._scan_input.text().strip().upper()
        if not sku:
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

            btn_del = QPushButton("✕")
            btn_del.setToolTip("Quitar 1 pieza (o eliminar si solo queda 1)")
            btn_del.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1.5px solid {_BORDER}; "
                f"border-radius: 6px; font-size: 14px; font-weight: 600; color: {_MUTED}; }}"
                f"QPushButton:hover {{ color: {_DANGER}; border-color: {_DANGER}; background: #fef0ee; }}"
            )
            btn_del.clicked.connect(lambda checked, r=row: self._on_remove(r))
            self._items_table.setCellWidget(row, 4, btn_del)

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

    @staticmethod
    def _round_total(total: Decimal) -> Decimal:
        integer_part = total.to_integral_value(rounding=ROUND_FLOOR)
        cents = (total - integer_part).quantize(Decimal("0.01"))
        if cents <= Decimal("0.19"):
            return integer_part
        if cents <= Decimal("0.69"):
            return (integer_part + Decimal("0.50")).quantize(Decimal("0.01"))
        return (integer_part + Decimal("1.00")).quantize(Decimal("0.01"))

    def _compute_totals(self) -> tuple[Decimal, Decimal, Decimal]:
        subtotal = Decimal(str(sum(it["precio"] * it["cantidad"] for it in self._items)))
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

    def _on_ticket_venta(self) -> None:
        if not self._items:
            QMessageBox.information(self, "Sin piezas", "Agrega piezas antes de generar ticket.")
            return
        tickets = [self._build_venta_text()]
        if self._discount_active:
            tickets.append(self._build_employee_copy_text())
        route_tickets(self, "Ticket de venta", tickets)
        self._scan_input.setFocus()

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
        route_tickets(self, "Apartado", [cliente_text, tienda_text])
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

    def _build_items_block(self, lines: list[str]) -> None:
        first = True
        for it in self._items:
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

    def _build_venta_text(self) -> str:
        biz_name, biz_phone, biz_addr = self._load_business_info()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        subtotal, discount, total = self._compute_totals()

        lines: list[str] = []

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
        self._build_items_block(lines)

        lines.append(tk_mid())
        lines.append(tk_row("Subtotal:", f"${tk_fmt(subtotal)}"))
        if self._discount_active:
            lines.append(tk_row("Descuento:", f"-${tk_fmt(discount)}"))
        lines.append(tk_dbl())
        lines.append(tk_row("TOTAL A PAGAR:", f"${tk_fmt(total)}"))
        lines.append(tk_bot())

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

    def _build_employee_copy_text(self) -> str:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        factor = (Decimal("100") - self._DISCOUNT_PERCENT) / Decimal("100")

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
            unit = (Decimal(str(it["precio"])) * factor).quantize(Decimal("0.01"))
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
            (Decimal(str(it["precio"])) * factor).quantize(Decimal("0.01")) * it["cantidad"]
            for it in self._items
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
