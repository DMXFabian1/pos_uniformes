"""Diálogo de ingreso rápido a caja — matriz de tallas."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, Variante
from pos_uniformes.services.bodega_service import BodegaService


class BodegaIngresoDialog(QDialog):
    def __init__(self, parent: QWidget, caja_id: int):
        super().__init__(parent)
        self._caja_id = caja_id
        self._variantes: list[Variante] = []
        self._spin_boxes: list[tuple[int, QSpinBox]] = []
        self.setWindowTitle("Agregar producto a caja")
        self.setMinimumSize(420, 500)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        # Buscador de producto
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto por nombre o SKU...")
        self.search_input.returnPressed.connect(self._on_buscar)
        search_layout.addWidget(self.search_input, 3)

        self.btn_buscar = self._make_button("Buscar", self._on_buscar)
        search_layout.addWidget(self.btn_buscar)
        layout.addLayout(search_layout)

        # Producto seleccionado
        self.producto_label = QLabel("")
        self.producto_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.producto_label)

        # Scroll area para la matriz de tallas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.matrix_container = QWidget()
        self.matrix_layout = QVBoxLayout()
        self.matrix_layout.setSpacing(4)
        self.matrix_container.setLayout(self.matrix_layout)
        self.scroll.setWidget(self.matrix_container)
        layout.addWidget(self.scroll, 1)

        # Botones
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def _make_button(self, text: str, slot) -> QWidget:
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        return btn

    def _on_buscar(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return

        with get_session() as session:
            pattern = f"%{query}%"
            productos = list(session.scalars(
                select(Producto)
                .where(Producto.nombre.ilike(pattern), Producto.activo.is_(True))
                .order_by(Producto.nombre)
                .limit(20)
            ).all())

            if not productos:
                variante = session.scalar(
                    select(Variante)
                    .options(joinedload(Variante.producto))
                    .where(Variante.sku.ilike(pattern), Variante.activo.is_(True))
                )
                if variante:
                    productos = [variante.producto]

            if not productos:
                QMessageBox.information(self, "Sin resultados", "No se encontró el producto.")
                return

            producto = productos[0]
            if len(productos) > 1:
                from PyQt6.QtWidgets import QInputDialog
                nombres = [p.nombre for p in productos]
                nombre, ok = QInputDialog.getItem(
                    self, "Seleccionar producto", "Producto:", nombres, 0, False
                )
                if not ok:
                    return
                producto = next(p for p in productos if p.nombre == nombre)

            variantes = list(session.scalars(
                select(Variante)
                .where(Variante.producto_id == producto.id, Variante.activo.is_(True))
                .order_by(Variante.talla)
            ).all())

            self._build_matrix(session, producto, variantes)

    def _build_matrix(self, session, producto: Producto, variantes: list[Variante]) -> None:
        self._variantes = variantes
        self._spin_boxes.clear()
        self.producto_label.setText(producto.nombre)

        # Limpiar layout anterior
        while self.matrix_layout.count():
            child = self.matrix_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not variantes:
            self.matrix_layout.addWidget(QLabel("No hay variantes activas."))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        for v in variantes:
            en_bodega = BodegaService._total_en_bodega_para_variante(session, v.id)
            disponible = v.stock_actual - en_bodega

            row_widget = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(4, 2, 4, 2)

            label = QLabel(f"{v.talla} / {v.color}")
            label.setMinimumWidth(120)
            row_layout.addWidget(label)

            stock_label = QLabel(f"Stock: {v.stock_actual}  En bodega: {en_bodega}  Disp: {disponible}")
            stock_label.setStyleSheet("color: #666;")
            row_layout.addWidget(stock_label, 1)

            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(max(0, disponible))
            spin.setValue(0)
            spin.setMinimumWidth(70)
            row_layout.addWidget(spin)

            row_widget.setLayout(row_layout)
            self.matrix_layout.addWidget(row_widget)
            self._spin_boxes.append((v.id, spin))

        self.matrix_layout.addStretch()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _on_accept(self) -> None:
        items = []
        for variante_id, spin in self._spin_boxes:
            cantidad = spin.value()
            if cantidad > 0:
                items.append({"variante_id": variante_id, "cantidad": cantidad})

        if not items:
            QMessageBox.information(self, "Nada que ingresar", "No se capturó ninguna cantidad.")
            return

        parent_widget = self.parent()
        creado_por = "ADMIN"
        if hasattr(parent_widget, "_get_usuario_actual"):
            creado_por = parent_widget._get_usuario_actual()

        with get_session() as session:
            try:
                total = BodegaService.ingreso_masivo(session, self._caja_id, items, creado_por)
                session.commit()
                QMessageBox.information(self, "Listo", f"Se ingresaron {total} prendas a la caja.")
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return

        self.accept()
