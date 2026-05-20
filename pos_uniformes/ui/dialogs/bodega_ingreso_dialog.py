"""Diálogo de ingreso a caja de bodega — escaneo uno a uno con acumulación.

Usa Meilisearch para búsqueda tolerante a typos con fallback a ILIKE.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, QStringListModel, QTimer, Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, Variante
from pos_uniformes.services.bodega_service import BodegaService

logger = logging.getLogger(__name__)


class _IngresoRow:
    __slots__ = ("variante_id", "sku", "producto", "talla", "color", "stock_actual", "en_bodega", "disponible", "cantidad")

    def __init__(self, v: Variante, en_bodega: int) -> None:
        self.variante_id: int = v.id
        self.sku: str = v.sku or ""
        self.producto: str = v.producto.nombre if v.producto else ""
        self.talla: str = v.talla or ""
        self.color: str = v.color or ""
        self.stock_actual: int = v.stock_actual
        self.en_bodega: int = en_bodega
        self.disponible: int = max(0, v.stock_actual - en_bodega)
        self.cantidad: int = 0


class BodegaIngresoDialog(QDialog):
    def __init__(self, parent: QWidget, caja_id: int):
        super().__init__(parent)
        self._caja_id = caja_id
        self._rows: list[_IngresoRow] = []
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.setInterval(1200)
        self._feedback_timer.timeout.connect(self._reset_feedback)

        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(150)
        self._suggest_timer.timeout.connect(self._update_suggestions)

        self.setWindowTitle("Agregar producto a caja")
        self.setModal(True)
        self.resize(820, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ─── Header ──────────────────────────────────────────────────────
        with get_session() as session:
            from pos_uniformes.database.models import BodegaCaja, CATEGORIA_CAJA_LABELS
            caja = session.get(BodegaCaja, self._caja_id)
            if caja:
                cat_label = CATEGORIA_CAJA_LABELS.get(caja.categoria, "")
                header_text = f"Caja {caja.codigo} — {cat_label}"
                if caja.ubicacion:
                    header_text += f" · {caja.ubicacion.codigo}"
            else:
                header_text = "Caja"

        header = QLabel(header_text)
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #224863; padding: 2px 0;")
        layout.addWidget(header)

        hint = QLabel(
            "Escanea piezas una por una — cada lectura suma 1 automáticamente. "
            "También puedes buscar por nombre y ajustar cantidades en la tabla."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5f6d78; font-size: 11px; padding: 0 2px;")
        layout.addWidget(hint)

        # ─── Scan input ──────────────────────────────────────────────────
        scan_card = QFrame()
        scan_card.setStyleSheet(
            "QFrame { border: 1px solid #d9e5ef; border-radius: 8px; background: #fcfdfd; }"
        )
        scan_layout = QHBoxLayout()
        scan_layout.setContentsMargins(12, 10, 12, 10)
        scan_layout.setSpacing(8)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Escanea SKU o busca por nombre...")
        self.sku_input.setStyleSheet(
            "min-height: 40px; padding: 0 12px; border-radius: 12px; "
            "border: 2px solid #d7e4ee; background: white; font-size: 16px; font-weight: 600; color: #294f69;"
        )
        self.sku_input.installEventFilter(self)
        scan_layout.addWidget(self.sku_input, 1)

        self.btn_sumar = QPushButton("Sumar 1")
        self.btn_sumar.setStyleSheet(
            "min-height: 40px; padding: 0 16px; border-radius: 12px; "
            "background: #c45425; color: white; font-weight: bold;"
        )
        self.btn_sumar.clicked.connect(self._handle_scan)
        self.btn_sumar.setAutoDefault(False)
        self.btn_sumar.setDefault(False)
        scan_layout.addWidget(self.btn_sumar)

        scan_card.setLayout(scan_layout)
        layout.addWidget(scan_card)

        # ─── Feedback badge ──────────────────────────────────────────────
        self.feedback_label = QLabel("Listo para escanear")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setStyleSheet(
            "padding: 6px 12px; border-radius: 12px; font-weight: 700; "
            "background: #eef5fb; color: #456176; border: 1px solid #d1e1ee;"
        )
        layout.addWidget(self.feedback_label)

        # ─── Tabla de piezas ─────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "SKU", "Producto", "Talla", "Color", "Disponible", "Cantidad", "Restante",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(250)
        self.table.installEventFilter(self)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, h.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, h.ResizeMode.Stretch)
        h.setSectionResizeMode(2, h.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, h.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, h.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, h.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, h.ResizeMode.ResizeToContents)

        self.clear_selection_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.table)
        self.clear_selection_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.clear_selection_shortcut.activated.connect(self._clear_selection)
        layout.addWidget(self.table)

        # ─── Summary + actions ───────────────────────────────────────────
        self.summary_label = QLabel("0 piezas de 0 presentaciones")
        self.summary_label.setStyleSheet(
            "padding: 8px 10px; border-radius: 12px; background: #eef5fb; "
            "color: #4f6475; border: 1px solid #d1e1ee; font-weight: 600;"
        )
        layout.addWidget(self.summary_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.btn_restar = QPushButton("Restar 1")
        self.btn_restar.setStyleSheet(
            "padding: 6px 14px; border-radius: 10px; border: 1px solid #ccc; background: white;"
        )
        self.btn_restar.clicked.connect(self._handle_restar)
        self.btn_restar.setAutoDefault(False)
        self.btn_restar.setEnabled(False)
        footer.addWidget(self.btn_restar)

        self.btn_quitar = QPushButton("Quitar fila")
        self.btn_quitar.setStyleSheet(
            "padding: 6px 14px; border-radius: 10px; border: 1px solid #ccc; background: white;"
        )
        self.btn_quitar.clicked.connect(self._handle_quitar_fila)
        self.btn_quitar.setAutoDefault(False)
        self.btn_quitar.setEnabled(False)
        footer.addWidget(self.btn_quitar)

        footer.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Ingresar a caja")
            ok_btn.setAutoDefault(False)
            ok_btn.setDefault(False)
        buttons.accepted.connect(self._handle_confirm)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)

        layout.addLayout(footer)

        content = QWidget()
        content.setLayout(layout)
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.setLayout(outer)

        self.table.itemSelectionChanged.connect(self._refresh_action_state)

        # ─── Completer Meilisearch ───────────────────────────────────────
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setMaxVisibleItems(8)
        self._completer.activated.connect(self._on_completer_activated)
        self.sku_input.setCompleter(self._completer)
        self.sku_input.textChanged.connect(self._on_text_changed)

        self.sku_input.setFocus()

    # ─── Scan / lookup ───────────────────────────────────────────────────

    def _handle_scan(self) -> None:
        text = self.sku_input.text().strip()
        if not text:
            self.sku_input.setFocus()
            return

        existing = next((r for r in self._rows if r.sku.upper() == text.upper()), None)
        if existing:
            if existing.cantidad >= existing.disponible:
                self._set_feedback(f"{existing.sku}: no hay más disponible ({existing.disponible})", "warning")
                self.sku_input.clear()
                self.sku_input.setFocus()
                return
            existing.cantidad += 1
            self._refresh_table()
            self._set_feedback(f"{existing.sku} → {existing.cantidad} pz", "success")
            self.sku_input.clear()
            self.sku_input.setFocus()
            return

        with get_session() as session:
            variante = session.scalar(
                select(Variante)
                .options(joinedload(Variante.producto))
                .where(Variante.sku.ilike(text), Variante.activo.is_(True))
            )
            if variante:
                self._add_variante_from_db(session, variante)
                self.sku_input.clear()
                self.sku_input.setFocus()
                return

            # ── Meilisearch → variante IDs, fallback a ILIKE ──
            meili_variante_ids: list[int] | None = None
            try:
                from pos_uniformes.services import meilisearch_service
                if meilisearch_service.is_available():
                    hits = meilisearch_service.search(text, limit=200)
                    if hits:
                        meili_variante_ids = [int(h["id"]) for h in hits if h.get("id")]
            except Exception:
                logger.debug("Meilisearch no disponible, fallback a ILIKE")

            if meili_variante_ids:
                # Cargar variantes encontradas por Meilisearch
                variantes = list(session.scalars(
                    select(Variante)
                    .options(joinedload(Variante.producto))
                    .where(Variante.id.in_(meili_variante_ids), Variante.activo.is_(True))
                    .order_by(Variante.talla)
                ).unique().all())

                # Filtro local para refinar (ej. "gales verde" → solo verde)
                terms = text.lower().split()
                filtered: list[Variante] = []
                for v in variantes:
                    searchable = " ".join([
                        v.sku or "", v.producto.nombre if v.producto else "",
                        v.talla or "", v.color or "",
                    ]).lower()
                    if all(t in searchable for t in terms):
                        filtered.append(v)
                variantes = filtered or variantes  # si filtro vacía todo, usa Meilisearch puro

                added = 0
                for v in variantes:
                    if any(r.variante_id == v.id for r in self._rows):
                        continue
                    en_bodega = BodegaService._total_en_bodega_para_variante(session, v.id)
                    row = _IngresoRow(v, en_bodega)
                    if row.disponible > 0:
                        self._rows.append(row)
                        added += 1

                engine = "Meilisearch"
                if added:
                    self._refresh_table()
                    self._set_feedback(f"{added} variantes cargadas ({engine}) — ajusta cantidades", "success")
                else:
                    self._set_feedback(f"Sin stock disponible para bodega ({engine})", "warning")

                self.sku_input.clear()
                self.sku_input.setFocus()
                return

            # ── Fallback: ILIKE en nombre de producto ──
            pattern = f"%{text}%"
            productos = list(session.scalars(
                select(Producto)
                .where(Producto.nombre.ilike(pattern), Producto.activo.is_(True))
                .order_by(Producto.nombre)
                .limit(20)
            ).all())

            if not productos:
                self._set_feedback(f"No encontrado: {text}", "warning")
                self.sku_input.selectAll()
                self.sku_input.setFocus()
                return

            producto = productos[0]
            if len(productos) > 1:
                from PyQt6.QtWidgets import QInputDialog
                nombres = [p.nombre for p in productos]
                nombre, ok = QInputDialog.getItem(
                    self, "Seleccionar producto", "Producto:", nombres, 0, False
                )
                if not ok:
                    self.sku_input.setFocus()
                    return
                producto = next(p for p in productos if p.nombre == nombre)

            variantes = list(session.scalars(
                select(Variante)
                .options(joinedload(Variante.producto))
                .where(Variante.producto_id == producto.id, Variante.activo.is_(True))
                .order_by(Variante.talla)
            ).all())

            added = 0
            for v in variantes:
                if any(r.variante_id == v.id for r in self._rows):
                    continue
                en_bodega = BodegaService._total_en_bodega_para_variante(session, v.id)
                row = _IngresoRow(v, en_bodega)
                if row.disponible > 0:
                    self._rows.append(row)
                    added += 1

            if added:
                self._refresh_table()
                self._set_feedback(f"{producto.nombre}: {added} tallas cargadas (local) — ajusta cantidades", "success")
            else:
                self._set_feedback(f"{producto.nombre}: todas las tallas ya están en bodega", "warning")

            self.sku_input.clear()
            self.sku_input.setFocus()

    def _add_variante_from_db(self, session, variante: Variante) -> None:
        existing = next((r for r in self._rows if r.variante_id == variante.id), None)
        if existing:
            if existing.cantidad >= existing.disponible:
                self._set_feedback(f"{existing.sku}: no hay más disponible", "warning")
                return
            existing.cantidad += 1
            self._refresh_table()
            self._set_feedback(f"{existing.sku} → {existing.cantidad} pz", "success")
            return

        en_bodega = BodegaService._total_en_bodega_para_variante(session, variante.id)
        row = _IngresoRow(variante, en_bodega)
        if row.disponible <= 0:
            self._set_feedback(f"{row.sku}: sin stock disponible para bodega", "warning")
            return
        row.cantidad = 1
        self._rows.append(row)
        self._refresh_table()
        self._set_feedback(f"{row.sku} · {row.producto} {row.talla} — 1 pz", "success")

    # ─── Meilisearch suggestions ───────────────────────────────────────────

    def _on_text_changed(self, text: str) -> None:
        if text.strip() and len(text.strip()) >= 2:
            self._suggest_timer.start()

    def _update_suggestions(self) -> None:
        query = self.sku_input.text().strip()
        if not query or len(query) < 2:
            return
        try:
            from pos_uniformes.services import meilisearch_service
            if not meilisearch_service.is_available():
                return
            hits = meilisearch_service.search(query, limit=20)
            names: list[str] = []
            seen: set[str] = set()
            for h in hits:
                label = f"{h.get('sku', '')} — {h.get('nombre_base', '')} {h.get('talla', '')} {h.get('color', '')}".strip()
                if label and label not in seen:
                    seen.add(label)
                    names.append(label)
            self._completer_model.setStringList(names)
        except Exception:
            pass

    def _on_completer_activated(self, text: str) -> None:
        # El completer muestra "SKU — Nombre Talla Color", extraer SKU
        sku = text.split("—")[0].strip() if "—" in text else text.strip()
        self.sku_input.setText(sku)
        self._handle_scan()

    # ─── Table rendering ─────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            sku_item = QTableWidgetItem(row.sku)
            sku_item.setData(Qt.ItemDataRole.UserRole, row.variante_id)
            self.table.setItem(i, 0, sku_item)
            self.table.setItem(i, 1, QTableWidgetItem(row.producto))
            self.table.setItem(i, 2, QTableWidgetItem(row.talla))
            self.table.setItem(i, 3, QTableWidgetItem(row.color))

            disp_item = QTableWidgetItem(str(row.disponible))
            disp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 4, disp_item)

            spin = self.table.cellWidget(i, 5)
            if not isinstance(spin, QSpinBox):
                spin = QSpinBox()
                spin.setRange(0, row.disponible)
                spin.installEventFilter(self)
                line_edit = spin.lineEdit()
                if line_edit:
                    line_edit.installEventFilter(self)
                spin.valueChanged.connect(
                    lambda val, vid=row.variante_id: self._handle_spin_changed(vid, val)
                )
                self.table.setCellWidget(i, 5, spin)
            spin.blockSignals(True)
            spin.setMaximum(row.disponible)
            spin.setValue(row.cantidad)
            spin.blockSignals(False)

            restante = row.disponible - row.cantidad
            rest_item = QTableWidgetItem(str(restante))
            rest_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if restante == 0 and row.cantidad > 0:
                rest_item.setForeground(QColor("#c45425"))
            self.table.setItem(i, 6, rest_item)

        self._refresh_summary()
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        total_pz = sum(r.cantidad for r in self._rows)
        n_variantes = sum(1 for r in self._rows if r.cantidad > 0)
        self.summary_label.setText(f"{total_pz} piezas de {n_variantes} presentaciones a ingresar")

    def _refresh_action_state(self) -> None:
        has_selection = self.table.currentRow() >= 0
        self.btn_restar.setEnabled(has_selection)
        self.btn_quitar.setEnabled(has_selection)

    def _handle_spin_changed(self, variante_id: int, value: int) -> None:
        row = next((r for r in self._rows if r.variante_id == variante_id), None)
        if row:
            row.cantidad = value
            idx = self._rows.index(row)
            restante = row.disponible - row.cantidad
            rest_item = QTableWidgetItem(str(restante))
            rest_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if restante == 0 and row.cantidad > 0:
                rest_item.setForeground(QColor("#c45425"))
            self.table.setItem(idx, 6, rest_item)
            self._refresh_summary()

    # ─── Actions ─────────────────────────────────────────────────────────

    def _handle_restar(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return
        row = self._rows[idx]
        if row.cantidad > 0:
            row.cantidad -= 1
            self._refresh_table()
            self.table.selectRow(idx)
            self._set_feedback(f"{row.sku} → {row.cantidad} pz", "success")

    def _handle_quitar_fila(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return
        removed = self._rows.pop(idx)
        self._refresh_table()
        self._set_feedback(f"{removed.sku} quitado", "warning")
        self.sku_input.setFocus()

    def _clear_selection(self) -> None:
        sel = self.table.selectionModel()
        if sel:
            sel.clearSelection()
            sel.clearCurrentIndex()
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self._refresh_action_state()
        self.sku_input.setFocus()

    def _handle_confirm(self) -> None:
        items = [
            {"variante_id": r.variante_id, "cantidad": r.cantidad}
            for r in self._rows if r.cantidad > 0
        ]
        if not items:
            QMessageBox.information(self, "Nada que ingresar", "No se capturó ninguna cantidad.")
            return

        total = sum(i["cantidad"] for i in items)
        desglose = "\n".join(
            f"  {r.sku}  {r.talla} — {r.cantidad} pz"
            for r in self._rows if r.cantidad > 0
        )
        answer = QMessageBox.question(
            self,
            "Confirmar ingreso",
            f"¿Ingresar {total} piezas a la caja?\n\n{desglose}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        parent_widget = self.parent()
        creado_por = "ADMIN"
        if hasattr(parent_widget, "_get_usuario_actual"):
            creado_por = parent_widget._get_usuario_actual()

        with get_session() as session:
            try:
                total = BodegaService.ingreso_masivo(session, self._caja_id, items, creado_por)
                session.commit()
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return

        self.accept()

    # ─── Feedback ────────────────────────────────────────────────────────

    def _set_feedback(self, text: str, tone: str) -> None:
        styles = {
            "success": "background: #e6f6ec; color: #1f6a3b; border: 1px solid #b7e0c4;",
            "warning": "background: #fff4df; color: #8a5a0a; border: 1px solid #efd4a0;",
            "idle": "background: #eef5fb; color: #456176; border: 1px solid #d1e1ee;",
        }
        self.feedback_label.setText(text)
        self.feedback_label.setStyleSheet(
            "padding: 6px 12px; border-radius: 12px; font-weight: 700; "
            + styles.get(tone, styles["idle"])
        )
        self._feedback_timer.start()

    def _reset_feedback(self) -> None:
        self.feedback_label.setText("Listo para escanear")
        self.feedback_label.setStyleSheet(
            "padding: 6px 12px; border-radius: 12px; font-weight: 700; "
            "background: #eef5fb; color: #456176; border: 1px solid #d1e1ee;"
        )

    # ─── Event filter ────────────────────────────────────────────────────

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() == QEvent.Type.Wheel:
            target = watched
            while target is not None:
                if isinstance(target, QSpinBox):
                    return True
                target = target.parent() if callable(getattr(target, "parent", None)) else None

        if watched is self.sku_input and event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
        ):
            self._handle_scan()
            return True

        if watched is self.sku_input and event.type() == QEvent.Type.ShortcutOverride and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
        ):
            event.accept()
            return True

        return super().eventFilter(watched, event)
