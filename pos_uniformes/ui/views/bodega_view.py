"""Vista principal de la pestaña Bodega — cajas, búsqueda, detalle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select as sa_select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import BodegaCaja, BodegaUbicacion, EstadoCaja, Variante
from pos_uniformes.services.bodega_service import BodegaService

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_bodega_tab(window: "MainWindow") -> QWidget:
    return BodegaWidget(window)


class BodegaWidget(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.window = window
        self._selected_caja_id: int | None = None
        self._init_ui()
        self._refresh_cajas()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ─── Top bar: búsqueda + acciones ────────────────────────────────
        top_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto, SKU, talla o caja...")
        self.search_input.returnPressed.connect(self._on_search)
        top_bar.addWidget(self.search_input, 3)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self._on_search)
        top_bar.addWidget(self.btn_buscar)

        self.btn_nueva_caja = QPushButton("+ Nueva Caja")
        self.btn_nueva_caja.clicked.connect(self._on_nueva_caja)
        top_bar.addWidget(self.btn_nueva_caja)

        self.btn_ubicaciones = QPushButton("Ubicaciones")
        self.btn_ubicaciones.clicked.connect(self._on_gestionar_ubicaciones)
        top_bar.addWidget(self.btn_ubicaciones)

        main_layout.addLayout(top_bar)

        # ─── Splitter: lista cajas | detalle ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: lista de cajas
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Filtros
        filtros = QHBoxLayout()
        self.filtro_estado = QComboBox()
        self.filtro_estado.addItems(["Todas", "ACTIVA", "VACIA", "CERRADA"])
        self.filtro_estado.currentIndexChanged.connect(self._refresh_cajas)
        filtros.addWidget(QLabel("Estado:"))
        filtros.addWidget(self.filtro_estado)

        self.filtro_ubicacion = QComboBox()
        self.filtro_ubicacion.addItem("Todas", None)
        self.filtro_ubicacion.currentIndexChanged.connect(self._refresh_cajas)
        filtros.addWidget(QLabel("Ubicación:"))
        filtros.addWidget(self.filtro_ubicacion)
        filtros.addStretch()
        left_layout.addLayout(filtros)

        # Tabla de cajas
        self.tabla_cajas = QTableWidget()
        self.tabla_cajas.setColumnCount(5)
        self.tabla_cajas.setHorizontalHeaderLabels(["Código", "Ubicación", "Estado", "Prendas", "Última actividad"])
        self.tabla_cajas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_cajas.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_cajas.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_cajas.horizontalHeader().setStretchLastSection(True)
        self.tabla_cajas.itemSelectionChanged.connect(self._on_caja_selected)
        left_layout.addWidget(self.tabla_cajas)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # Panel derecho: detalle de caja
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(4, 0, 0, 0)

        # Header
        self.detalle_header = QLabel("Selecciona una caja")
        self.detalle_header.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self.detalle_header)

        self.detalle_ubicacion_label = QLabel("")
        right_layout.addWidget(self.detalle_ubicacion_label)

        # Acciones de caja
        acciones_caja = QHBoxLayout()
        self.btn_agregar = QPushButton("+ Agregar producto")
        self.btn_agregar.clicked.connect(self._on_agregar_producto)
        self.btn_agregar.setEnabled(False)
        acciones_caja.addWidget(self.btn_agregar)

        self.btn_retirar = QPushButton("- Retirar")
        self.btn_retirar.clicked.connect(self._on_retirar_producto)
        self.btn_retirar.setEnabled(False)
        acciones_caja.addWidget(self.btn_retirar)

        self.btn_mover = QPushButton("Mover caja")
        self.btn_mover.clicked.connect(self._on_mover_caja)
        self.btn_mover.setEnabled(False)
        acciones_caja.addWidget(self.btn_mover)

        self.btn_qr = QPushButton("Imprimir QR")
        self.btn_qr.clicked.connect(self._on_imprimir_qr)
        self.btn_qr.setEnabled(False)
        acciones_caja.addWidget(self.btn_qr)

        acciones_caja.addStretch()
        right_layout.addLayout(acciones_caja)

        # Contenido de caja
        contenido_group = QGroupBox("Contenido")
        contenido_layout = QVBoxLayout()
        self.tabla_contenido = QTableWidget()
        self.tabla_contenido.setColumnCount(5)
        self.tabla_contenido.setHorizontalHeaderLabels(["Producto", "Talla", "Color", "Cantidad", "SKU"])
        self.tabla_contenido.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_contenido.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_contenido.horizontalHeader().setStretchLastSection(True)
        contenido_layout.addWidget(self.tabla_contenido)
        contenido_group.setLayout(contenido_layout)
        right_layout.addWidget(contenido_group)

        # Historial
        historial_group = QGroupBox("Últimos movimientos")
        historial_layout = QVBoxLayout()
        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(5)
        self.tabla_historial.setHorizontalHeaderLabels(["Fecha", "Tipo", "Producto", "Cantidad", "Usuario"])
        self.tabla_historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_historial.horizontalHeader().setStretchLastSection(True)
        historial_layout.addWidget(self.tabla_historial)
        historial_group.setLayout(historial_layout)
        right_layout.addWidget(historial_group)

        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter)

        # ─── Resultados de búsqueda (oculto inicialmente) ────────────────
        self.search_results_group = QGroupBox("Resultados de búsqueda")
        search_layout = QVBoxLayout()
        self.tabla_busqueda = QTableWidget()
        self.tabla_busqueda.setColumnCount(6)
        self.tabla_busqueda.setHorizontalHeaderLabels(["Producto", "Talla", "Color", "Caja", "Ubicación", "Cantidad"])
        self.tabla_busqueda.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_busqueda.horizontalHeader().setStretchLastSection(True)
        search_layout.addWidget(self.tabla_busqueda)
        self.search_results_group.setLayout(search_layout)
        self.search_results_group.setVisible(False)
        main_layout.addWidget(self.search_results_group)

        self.setLayout(main_layout)

    # ─── Data loading ────────────────────────────────────────────────────

    def _refresh_cajas(self) -> None:
        with get_session() as session:
            estado_text = self.filtro_estado.currentText()
            estado = EstadoCaja(estado_text) if estado_text != "Todas" else None

            ub_data = self.filtro_ubicacion.currentData()
            ubicacion_id = int(ub_data) if ub_data is not None else None

            cajas = BodegaService.listar_cajas(
                session, estado=estado, ubicacion_id=ubicacion_id
            )

            self.tabla_cajas.setRowCount(len(cajas))
            for row, caja in enumerate(cajas):
                self.tabla_cajas.setItem(row, 0, QTableWidgetItem(caja.codigo))
                ub_str = caja.ubicacion.codigo if caja.ubicacion else "—"
                self.tabla_cajas.setItem(row, 1, QTableWidgetItem(ub_str))
                self.tabla_cajas.setItem(row, 2, QTableWidgetItem(caja.estado))

                total_prendas = sum(c.cantidad for c in caja.contenido) if caja.contenido else 0
                item_prendas = QTableWidgetItem(str(total_prendas))
                item_prendas.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_cajas.setItem(row, 3, item_prendas)

                self.tabla_cajas.setItem(row, 4, QTableWidgetItem(
                    caja.updated_at.strftime("%d/%m %H:%M") if caja.updated_at else "—"
                ))

                self.tabla_cajas.setItem(row, 0, QTableWidgetItem(caja.codigo))
                self.tabla_cajas.item(row, 0).setData(Qt.ItemDataRole.UserRole, caja.id)

            self._refresh_filtro_ubicaciones(session)

    def _refresh_filtro_ubicaciones(self, session) -> None:
        current = self.filtro_ubicacion.currentData()
        self.filtro_ubicacion.blockSignals(True)
        self.filtro_ubicacion.clear()
        self.filtro_ubicacion.addItem("Todas", None)
        ubicaciones = BodegaService.listar_ubicaciones(session)
        for ub in ubicaciones:
            self.filtro_ubicacion.addItem(ub.codigo, ub.id)
        if current is not None:
            idx = self.filtro_ubicacion.findData(current)
            if idx >= 0:
                self.filtro_ubicacion.setCurrentIndex(idx)
        self.filtro_ubicacion.blockSignals(False)

    def _on_caja_selected(self) -> None:
        rows = self.tabla_cajas.selectedItems()
        if not rows:
            self._selected_caja_id = None
            self._set_detalle_enabled(False)
            return

        row = self.tabla_cajas.currentRow()
        item = self.tabla_cajas.item(row, 0)
        if not item:
            return
        caja_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_caja_id = caja_id
        self._set_detalle_enabled(True)
        self._load_caja_detalle(caja_id)

    def _set_detalle_enabled(self, enabled: bool) -> None:
        self.btn_agregar.setEnabled(enabled)
        self.btn_retirar.setEnabled(enabled)
        self.btn_mover.setEnabled(enabled)
        self.btn_qr.setEnabled(enabled)

    def _load_caja_detalle(self, caja_id: int) -> None:
        with get_session() as session:
            caja = BodegaService.obtener_caja_detalle(session, caja_id)
            if not caja:
                return

            self.detalle_header.setText(f"Caja {caja.codigo}  [{caja.estado}]")
            ub_text = f"Ubicación: {caja.ubicacion.codigo}" if caja.ubicacion else "Sin ubicación asignada"
            self.detalle_ubicacion_label.setText(ub_text)

            # Contenido
            contenido = caja.contenido or []
            self.tabla_contenido.setRowCount(len(contenido))
            for row, c in enumerate(contenido):
                self.tabla_contenido.setItem(row, 0, QTableWidgetItem(c.variante.producto.nombre))
                self.tabla_contenido.setItem(row, 1, QTableWidgetItem(c.variante.talla))
                self.tabla_contenido.setItem(row, 2, QTableWidgetItem(c.variante.color))
                cant_item = QTableWidgetItem(str(c.cantidad))
                cant_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_contenido.setItem(row, 3, cant_item)
                self.tabla_contenido.setItem(row, 4, QTableWidgetItem(c.variante.sku))

            # Historial
            movimientos = BodegaService.historial_caja(session, caja_id, limit=20)
            self.tabla_historial.setRowCount(len(movimientos))
            for row, mov in enumerate(movimientos):
                self.tabla_historial.setItem(row, 0, QTableWidgetItem(
                    mov.created_at.strftime("%d/%m %H:%M")
                ))
                self.tabla_historial.setItem(row, 1, QTableWidgetItem(mov.tipo))
                prod_text = ""
                if mov.variante:
                    prod_text = f"{mov.variante.producto.nombre} {mov.variante.talla}"
                self.tabla_historial.setItem(row, 2, QTableWidgetItem(prod_text))
                cant_text = str(mov.cantidad) if mov.cantidad else "—"
                self.tabla_historial.setItem(row, 3, QTableWidgetItem(cant_text))
                self.tabla_historial.setItem(row, 4, QTableWidgetItem(mov.creado_por))

    # ─── Búsqueda ────────────────────────────────────────────────────────

    def _on_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.search_results_group.setVisible(False)
            return

        with get_session() as session:
            resultados = BodegaService.buscar_por_texto(session, query)

        self.tabla_busqueda.setRowCount(len(resultados))
        for row, r in enumerate(resultados):
            self.tabla_busqueda.setItem(row, 0, QTableWidgetItem(r["producto"]))
            self.tabla_busqueda.setItem(row, 1, QTableWidgetItem(r["talla"]))
            self.tabla_busqueda.setItem(row, 2, QTableWidgetItem(r["color"]))
            self.tabla_busqueda.setItem(row, 3, QTableWidgetItem(r["caja_codigo"]))
            self.tabla_busqueda.setItem(row, 4, QTableWidgetItem(r["ubicacion"] or "—"))
            cant_item = QTableWidgetItem(str(r["cantidad"]))
            cant_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla_busqueda.setItem(row, 5, cant_item)

        self.search_results_group.setVisible(True)

    # ─── Acciones ────────────────────────────────────────────────────────

    def _on_nueva_caja(self) -> None:
        dialog = NuevaCajaDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_cajas()

    def _on_gestionar_ubicaciones(self) -> None:
        from pos_uniformes.ui.dialogs.bodega_ubicaciones_dialog import BodegaUbicacionesDialog
        dialog = BodegaUbicacionesDialog(self)
        dialog.exec()
        self._refresh_cajas()

    def _on_agregar_producto(self) -> None:
        if not self._selected_caja_id:
            return
        from pos_uniformes.ui.dialogs.bodega_ingreso_dialog import BodegaIngresoDialog
        dialog = BodegaIngresoDialog(self, self._selected_caja_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_retirar_producto(self) -> None:
        if not self._selected_caja_id:
            return
        row = self.tabla_contenido.currentRow()
        if row < 0:
            QMessageBox.information(self, "Retirar", "Selecciona un producto de la tabla de contenido.")
            return

        sku = self.tabla_contenido.item(row, 4).text()
        cant_actual = int(self.tabla_contenido.item(row, 3).text())

        dialog = RetirarDialog(self, sku, cant_actual)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cantidad = dialog.cantidad()
            with get_session() as session:
                variante = session.scalar(
                    sa_select(Variante).where(Variante.sku == sku)
                )
                if variante:
                    try:
                        BodegaService.retirar_producto(
                            session, self._selected_caja_id, variante.id, cantidad,
                            creado_por=self._get_usuario_actual(),
                        )
                        session.commit()
                    except ValueError as e:
                        session.rollback()
                        QMessageBox.warning(self, "Error", str(e))
                        return
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_mover_caja(self) -> None:
        if not self._selected_caja_id:
            return
        dialog = MoverCajaDialog(self, self._selected_caja_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_caja_detalle(self._selected_caja_id)
            self._refresh_cajas()

    def _on_imprimir_qr(self) -> None:
        if not self._selected_caja_id:
            return
        from pos_uniformes.utils.qr_generator import QrGenerator
        with get_session() as session:
            caja = session.get(BodegaCaja, self._selected_caja_id)
            if not caja:
                return
            qr_data = BodegaService.generar_qr_data(caja)
            caja.qr_data = qr_data
            session.commit()
            qr_path = QrGenerator.generate_for_caja(caja)

        QMessageBox.information(
            self, "QR generado",
            f"Caja: {caja.codigo}\nArchivo: {qr_path}",
        )

    def _get_usuario_actual(self) -> str:
        if hasattr(self.window, "current_user") and self.window.current_user:
            return self.window.current_user.nombre
        return "ADMIN"


# ═══════════════════════════════════════════════════════════════════════════════
# DIÁLOGOS INTEGRADOS
# ═══════════════════════════════════════════════════════════════════════════════


class NuevaCajaDialog(QDialog):
    def __init__(self, parent: BodegaWidget):
        super().__init__(parent)
        self.setWindowTitle("Nueva Caja")
        self.setMinimumWidth(350)

        layout = QFormLayout()

        self.codigo_input = QLineEdit()
        self.codigo_input.setPlaceholderText("Ej: B-015")
        layout.addRow("Código:", self.codigo_input)

        self.ubicacion_combo = QComboBox()
        self.ubicacion_combo.addItem("Sin asignar", None)
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session)
            for ub in ubicaciones:
                self.ubicacion_combo.addItem(ub.codigo, ub.id)
        layout.addRow("Ubicación:", self.ubicacion_combo)

        self.notas_input = QLineEdit()
        layout.addRow("Notas:", self.notas_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def _on_accept(self) -> None:
        codigo = self.codigo_input.text().strip()
        if not codigo:
            QMessageBox.warning(self, "Error", "El código es obligatorio.")
            return

        ubicacion_id = self.ubicacion_combo.currentData()
        notas = self.notas_input.text().strip() or None

        with get_session() as session:
            try:
                BodegaService.crear_caja(session, codigo, ubicacion_id, notas)
                session.commit()
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return
        self.accept()


class RetirarDialog(QDialog):
    def __init__(self, parent: QWidget, sku: str, max_cantidad: int):
        super().__init__(parent)
        self.setWindowTitle(f"Retirar — {sku}")

        layout = QFormLayout()
        self._spin = QSpinBox()
        self._spin.setMinimum(1)
        self._spin.setMaximum(max_cantidad)
        self._spin.setValue(1)
        layout.addRow("Cantidad a retirar:", self._spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def cantidad(self) -> int:
        return self._spin.value()


class MoverCajaDialog(QDialog):
    def __init__(self, parent: BodegaWidget, caja_id: int):
        super().__init__(parent)
        self._caja_id = caja_id
        self._parent_widget = parent
        self.setWindowTitle("Mover Caja")

        layout = QFormLayout()
        self.ubicacion_combo = QComboBox()
        self.ubicacion_combo.addItem("Sin asignar", None)
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session)
            for ub in ubicaciones:
                self.ubicacion_combo.addItem(ub.codigo, ub.id)
        layout.addRow("Nueva ubicación:", self.ubicacion_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def _on_accept(self) -> None:
        nueva_ub = self.ubicacion_combo.currentData()
        with get_session() as session:
            try:
                BodegaService.mover_caja(
                    session, self._caja_id, nueva_ub,
                    creado_por=self._parent_widget._get_usuario_actual(),
                )
                session.commit()
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return
        self.accept()
