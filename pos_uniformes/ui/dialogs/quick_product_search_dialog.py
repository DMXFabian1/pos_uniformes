"""Diálogo de búsqueda rápida de producto para el flujo de caja (Ctrl+S).

Usa Meilisearch para búsqueda instantánea tolerante a typos.
Fallback a filtro local si Meilisearch no está disponible.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QStringListModel
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class QuickProductSearchDialog(QDialog):
    """Búsqueda rápida de producto con Meilisearch + tabla de resultados."""

    sku_selected = pyqtSignal(str, int)
    sku_to_kiosk = pyqtSignal(str, int)

    def __init__(self, parent=None, catalog_rows: list[dict] | None = None, *, kiosk_mode: bool = False, **_kwargs):
        super().__init__(parent)
        self.setWindowTitle("Buscar producto")
        self.setModal(True)
        self.setMinimumSize(780, 560)
        self.resize(850, 640)

        self._kiosk_mode = kiosk_mode
        self._catalog_rows = catalog_rows or []
        if not self._catalog_rows:
            self._load_catalog()

        self._result_rows: list[dict] = []
        self._build_ui()
        self._bind_events()

        # Focus en el input al abrir
        QTimer.singleShot(50, self._search_input.setFocus)

    def _load_catalog(self) -> None:
        try:
            with get_session() as session:
                self._catalog_rows = load_catalog_snapshot_rows(session)
        except Exception:
            self._catalog_rows = []

    # ── UI ──

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Buscar producto")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #3a2a1a;")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("ghostButton")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        root.addLayout(header)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Escribe nombre, SKU, talla, color, escuela…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(40)
        self._search_input.setStyleSheet(
            "QLineEdit { font-size: 15px; padding: 8px 12px;"
            " border: 2px solid #c4b9a8; border-radius: 8px;"
            " background: #fffaf2; color: #3a2a1a; }"
            "QLineEdit:focus { border-color: #87492c; }"
        )

        # Completer predictivo
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setMaxVisibleItems(8)
        self._completer.activated.connect(self._on_completer_activated)
        self._search_input.setCompleter(self._completer)

        root.addWidget(self._search_input)

        # Info label
        self._info_label = QLabel("Escribe para buscar entre todos los productos.")
        self._info_label.setStyleSheet("font-size: 12px; color: #8a7a6a;")
        root.addWidget(self._info_label)

        # Results table
        columns = ["SKU", "Producto", "Talla", "Color", "Precio"]
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(280)
        root.addWidget(self._table, 1)

        # Detail + actions bar
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(10)

        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet("font-size: 13px; color: #3a2a1a;")
        self._detail_label.setWordWrap(True)
        actions_bar.addWidget(self._detail_label, 1)

        qty_label = QLabel("Cant:")
        qty_label.setStyleSheet("font-size: 13px; color: #6B4226;")
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 100)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(60)
        self._qty_spin.setMinimumHeight(36)

        add_label = "Agregar a presupuesto" if self._kiosk_mode else "Agregar a venta"
        self._add_btn = QPushButton(add_label)
        self._add_btn.setObjectName("primaryButton")
        self._add_btn.setMinimumHeight(40)
        self._add_btn.setMinimumWidth(160)
        self._add_btn.setEnabled(False)

        self._kiosk_btn = QPushButton("Agregar a consulta")
        self._kiosk_btn.setObjectName("secondaryButton")
        self._kiosk_btn.setMinimumHeight(40)
        self._kiosk_btn.setEnabled(False)
        self._kiosk_btn.setVisible(self._kiosk_mode)

        actions_bar.addWidget(qty_label)
        actions_bar.addWidget(self._qty_spin)
        actions_bar.addWidget(self._kiosk_btn)
        actions_bar.addWidget(self._add_btn)
        root.addLayout(actions_bar)

        self.setLayout(root)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)
        QShortcut(QKeySequence("Return"), self._table).activated.connect(self._handle_add)

    def _bind_events(self) -> None:
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._run_search)

        self._suggest_timer = QTimer()
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(150)
        self._suggest_timer.timeout.connect(self._update_suggestions)

        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._run_search)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._handle_add)
        self._add_btn.clicked.connect(self._handle_add)
        self._kiosk_btn.clicked.connect(self._handle_kiosk)

    # ── Search ──

    def _on_text_changed(self, text: str) -> None:
        if text.strip():
            self._search_timer.start()
            self._suggest_timer.start()
        else:
            self._table.setRowCount(0)
            self._result_rows = []
            self._info_label.setText("Escribe para buscar entre todos los productos.")
            self._add_btn.setEnabled(False)
            self._kiosk_btn.setEnabled(False)
            self._detail_label.setText("")

    def _run_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            return

        hits: list[dict] = []
        used_meili = False

        # Intentar Meilisearch primero (pre-filtra por relevancia)
        source_rows = self._catalog_rows
        try:
            from pos_uniformes.services import meilisearch_service
            if meilisearch_service.is_available():
                raw_hits = meilisearch_service.search(query, limit=500)
                if raw_hits:
                    hit_skus = {str(h.get("sku", "")) for h in raw_hits}
                    source_rows = [r for r in self._catalog_rows if str(r.get("sku", "")) in hit_skus]
                    used_meili = True
        except Exception:
            pass

        # Con Meilisearch (matchingStrategy=all) el texto ya quedó resuelto con
        # typos y sinónimos — re-filtrar por substring los mataría. El filtro
        # de términos solo corre como fallback local.
        q_lower = query.lower()
        terms = q_lower.split()
        for row in source_rows:
                if not row.get("producto_activo") or not row.get("variante_activo"):
                    continue
                if not used_meili:
                    searchable = " ".join([
                        str(row.get("sku", "")),
                        str(row.get("producto_nombre_base", "")),
                        str(row.get("talla", "")),
                        str(row.get("color", "")),
                        str(row.get("escuela_nombre", "")),
                        str(row.get("tipo_prenda_nombre", "")),
                        str(row.get("tipo_pieza_nombre", "")),
                    ]).lower()
                    if not all(t in searchable for t in terms):
                        continue
                hits.append(row)
                if len(hits) >= 200:
                    break

        self._result_rows = hits
        self._populate_table(hits)
        engine = "Meilisearch" if used_meili else "local"
        self._info_label.setText(f"{len(hits)} resultado{'s' if len(hits) != 1 else ''} ({engine})")

    def _populate_table(self, rows: list[dict]) -> None:
        self._table.setRowCount(0)
        for idx, row in enumerate(rows):
            sku = str(row.get("sku", ""))
            nombre = str(row.get("producto_nombre_base", ""))
            talla = str(row.get("talla", ""))
            color = str(row.get("color", ""))
            precio = Decimal(str(row.get("precio_venta", 0))).quantize(Decimal("0.01"))

            self._table.insertRow(idx)
            values = [sku, nombre, talla, color, f"${precio}"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | (
                        Qt.AlignmentFlag.AlignRight if col == 4 else Qt.AlignmentFlag.AlignLeft
                    )
                )
                self._table.setItem(idx, col, cell)

        for col in [0, 2, 3, 4]:
            self._table.resizeColumnToContents(col)

        if rows:
            self._table.selectRow(0)

    def _update_suggestions(self) -> None:
        query = self._search_input.text().strip()
        if not query or len(query) < 2:
            return
        try:
            from pos_uniformes.services import meilisearch_service
            if not meilisearch_service.is_available():
                return
            hits = meilisearch_service.search(query, limit=20)
            names = []
            seen: set[str] = set()
            for h in hits:
                name = str(h.get("nombre_base", ""))
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
            self._completer_model.setStringList(names)
        except Exception:
            pass

    def _on_completer_activated(self, text: str) -> None:
        self._search_input.setText(text)
        self._run_search()

    # ── Selection & Add ──

    def _on_selection_changed(self) -> None:
        row_idx = self._table.currentRow()
        if row_idx < 0 or row_idx >= len(self._result_rows):
            self._add_btn.setEnabled(False)
            self._kiosk_btn.setEnabled(False)
            self._detail_label.setText("")
            return
        self._add_btn.setEnabled(True)
        self._kiosk_btn.setEnabled(True)
        row = self._result_rows[row_idx]
        sku = str(row.get("sku", ""))
        nombre = str(row.get("producto_nombre_base", ""))
        talla = str(row.get("talla", ""))
        color = str(row.get("color", ""))
        precio = Decimal(str(row.get("precio_venta", 0))).quantize(Decimal("0.01"))
        escuela = str(row.get("escuela_nombre", ""))
        parts = [f"{sku} | {nombre}"]
        if talla:
            parts.append(f"Talla {talla}")
        if color and color.lower() not in ("sin color", "ad hoc"):
            parts.append(f"Color {color}")
        if escuela and escuela != "General":
            parts.append(escuela)
        parts.append(f"${precio}")
        self._detail_label.setText("  ·  ".join(parts))

    def _handle_add(self) -> None:
        row_idx = self._table.currentRow()
        if row_idx < 0 or row_idx >= len(self._result_rows):
            return
        sku = str(self._result_rows[row_idx].get("sku", ""))
        if not sku:
            return
        self.sku_selected.emit(sku, self._qty_spin.value())
        self._qty_spin.setValue(1)

    def _handle_kiosk(self) -> None:
        row_idx = self._table.currentRow()
        if row_idx < 0 or row_idx >= len(self._result_rows):
            return
        sku = str(self._result_rows[row_idx].get("sku", ""))
        if not sku:
            return
        self.sku_to_kiosk.emit(sku, self._qty_spin.value())
        self._qty_spin.setValue(1)
