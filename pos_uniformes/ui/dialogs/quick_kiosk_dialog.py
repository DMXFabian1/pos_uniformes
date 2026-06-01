"""Diálogo de consulta rápida de precios (Ctrl+K).

Versión ligera del kiosko: escanea o escribe un SKU y muestra
producto, talla, color, precio y stock. Se puede abrir desde
cualquier parte de la app sin interrumpir el flujo actual.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.quote_kiosk_lookup_service import (
    QuoteKioskLookupSnapshot,
    load_quote_kiosk_lookup_snapshot,
)

# ── Estilos ─────────────────────────────────────────────────────────────────

_BRAND = "#87492c"
_BRAND_LIGHT = "#f5ebe0"
_CARD_BG = "#fffaf5"

_DIALOG_STYLE = f"""
QDialog {{
    background: {_BRAND_LIGHT};
}}
QLabel#kioskTitle {{
    font-size: 14px; font-weight: 700; color: {_BRAND};
}}
QLineEdit#kioskInput {{
    font-size: 18px; padding: 10px 14px;
    border: 2px solid #d4a574; border-radius: 8px;
    background: white; color: #333;
}}
QLineEdit#kioskInput:focus {{
    border-color: {_BRAND};
}}
QPushButton#kioskBtn {{
    font-size: 14px; font-weight: 600; padding: 10px 20px;
    background: {_BRAND}; color: white; border: none; border-radius: 8px;
}}
QPushButton#kioskBtn:hover {{ background: #6b3a22; }}
QLabel#kioskProduct {{
    font-size: 22px; font-weight: 700; color: #333;
}}
QLabel#kioskDetail {{
    font-size: 14px; color: #666;
}}
QLabel#kioskPrice {{
    font-size: 48px; font-weight: 800; color: {_BRAND};
}}
QLabel#kioskStock {{
    font-size: 14px; font-weight: 600;
}}
QLabel#kioskSchool {{
    font-size: 13px; color: #888;
}}
QLabel#kioskError {{
    font-size: 14px; color: #c0392b; font-weight: 600;
}}
QWidget#kioskCard {{
    background: {_CARD_BG}; border: 1px solid #e8d5c4;
    border-radius: 10px;
}}
QWidget#kioskRecent {{
    background: {_CARD_BG}; border: 1px solid #e8d5c4;
    border-radius: 10px;
}}
"""


class QuickKioskDialog(QDialog):
    """Consulta rápida de precios — se abre con Ctrl+K."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Consulta de Precios")
        self.setModal(False)
        self.setMinimumSize(600, 420)
        self.resize(640, 480)
        self.setStyleSheet(_DIALOG_STYLE)

        self._recent: list[QuoteKioskLookupSnapshot] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Scan bar ──
        scan_row = QHBoxLayout()
        title = QLabel("CONSULTA DE PRECIOS")
        title.setObjectName("kioskTitle")
        scan_row.addWidget(title)
        scan_row.addStretch()

        self._input = QLineEdit()
        self._input.setObjectName("kioskInput")
        self._input.setPlaceholderText("Escanea o escribe un SKU...")
        self._input.setFixedWidth(280)
        self._input.returnPressed.connect(self._on_lookup)
        scan_row.addWidget(self._input)

        btn = QPushButton("Consultar")
        btn.setObjectName("kioskBtn")
        btn.clicked.connect(self._on_lookup)
        scan_row.addWidget(btn)
        layout.addLayout(scan_row)

        # ── Product card ──
        self._card = _ProductCard()
        layout.addWidget(self._card)

        # ── Recent scans ──
        recent_label = QLabel("Consultas recientes")
        recent_label.setStyleSheet(f"font-size:12px;font-weight:600;color:{_BRAND};margin-top:4px;")
        layout.addWidget(recent_label)

        self._recent_table = QTableWidget(0, 4)
        self._recent_table.setObjectName("kioskRecent")
        self._recent_table.setHorizontalHeaderLabels(["SKU", "Producto", "Talla", "Precio"])
        self._recent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._recent_table.verticalHeader().setVisible(False)
        self._recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._recent_table.setAlternatingRowColors(True)
        self._recent_table.setMaximumHeight(180)
        self._recent_table.setStyleSheet("""
            QTableWidget { background: white; border: 1px solid #e8d5c4; border-radius: 6px; font-size: 12px; }
            QTableWidget::item { padding: 4px 8px; }
            QHeaderView::section { background: #f5ebe0; color: #87492c; font-weight: 600;
                                   font-size: 11px; padding: 4px; border: none; border-bottom: 1px solid #d4a574; }
        """)
        layout.addWidget(self._recent_table)

        # Focus on input
        QTimer.singleShot(0, self._input.setFocus)

    def _on_lookup(self) -> None:
        sku = self._input.text().strip()
        if not sku:
            return

        try:
            with get_session() as session:
                snap = load_quote_kiosk_lookup_snapshot(session, sku=sku)
            self._card.show_product(snap)
            self._add_recent(snap)
        except ValueError as exc:
            self._card.show_error(str(exc))

        self._input.clear()
        self._input.setFocus()

    def _add_recent(self, snap: QuoteKioskLookupSnapshot) -> None:
        # Avoid duplicates at top
        self._recent = [r for r in self._recent if r.sku != snap.sku]
        self._recent.insert(0, snap)
        self._recent = self._recent[:20]
        self._refresh_recent_table()

    def _refresh_recent_table(self) -> None:
        self._recent_table.setRowCount(len(self._recent))
        for i, snap in enumerate(self._recent):
            self._recent_table.setItem(i, 0, QTableWidgetItem(snap.sku))
            self._recent_table.setItem(i, 1, QTableWidgetItem(snap.product_name))
            self._recent_table.setItem(i, 2, QTableWidgetItem(f"{snap.size_label} {snap.color_label}".strip()))

            price_item = QTableWidgetItem(f"${snap.price:,.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._recent_table.setItem(i, 3, price_item)

        self._recent_table.resizeRowsToContents()

    def showEvent(self, event):
        super().showEvent(event)
        self._input.setFocus()
        self._input.selectAll()


class _ProductCard(QLabel):
    """Card que muestra el producto consultado o un mensaje de error."""

    def __init__(self):
        super().__init__()
        self.setObjectName("kioskCard")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(140)
        self.setWordWrap(True)
        self.setStyleSheet(f"""
            QLabel#kioskCard {{
                background: {_CARD_BG}; border: 1px solid #e8d5c4;
                border-radius: 10px; padding: 20px;
            }}
        """)
        self.show_empty()

    def show_empty(self) -> None:
        self.setText(
            '<div style="text-align:center;color:#aaa;font-size:16px;">'
            'Escanea un SKU para consultar el precio'
            '</div>'
        )

    def show_error(self, msg: str) -> None:
        self.setText(
            f'<div style="text-align:center;color:#c0392b;font-size:15px;font-weight:600;">'
            f'{msg}</div>'
        )

    def show_product(self, snap: QuoteKioskLookupSnapshot) -> None:
        self.setText(
            f'<div style="text-align:center;">'
            f'<div style="font-size:13px;color:#888;">{snap.school_name} &middot; {snap.piece_type_name}</div>'
            f'<div style="font-size:22px;font-weight:700;color:#333;margin:4px 0;">{snap.product_name}</div>'
            f'<div style="font-size:14px;color:#666;">{snap.size_label} &middot; {snap.color_label}</div>'
            f'<div style="font-size:48px;font-weight:800;color:#87492c;margin:8px 0;">${snap.price:,.2f}</div>'
            f'<div style="font-size:11px;color:#aaa;margin-top:4px;">SKU: {snap.sku}</div>'
            f'</div>'
        )
