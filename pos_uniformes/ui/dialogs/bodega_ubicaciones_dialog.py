"""Diálogo CRUD de ubicaciones de bodega (racks y niveles)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from pos_uniformes.services.bodega_service import BodegaService


class BodegaUbicacionesDialog(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Gestión de Ubicaciones")
        self.setMinimumSize(500, 400)
        self._init_ui()
        self._refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        # Formulario nueva ubicación
        form_group = QHBoxLayout()

        self.rack_input = QLineEdit()
        self.rack_input.setPlaceholderText("Rack (ej: A1)")
        self.rack_input.setMaximumWidth(100)
        form_group.addWidget(QLabel("Rack:"))
        form_group.addWidget(self.rack_input)

        self.nivel_input = QSpinBox()
        self.nivel_input.setMinimum(1)
        self.nivel_input.setMaximum(10)
        self.nivel_input.setValue(1)
        form_group.addWidget(QLabel("Nivel:"))
        form_group.addWidget(self.nivel_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Descripción (opcional)")
        form_group.addWidget(self.desc_input)

        btn_agregar = QPushButton("+ Agregar")
        btn_agregar.clicked.connect(self._on_agregar)
        form_group.addWidget(btn_agregar)

        layout.addLayout(form_group)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Código", "Rack", "Nivel", "Descripción", "Cajas"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla)

        # Botones
        bottom = QHBoxLayout()
        self.btn_desactivar = QPushButton("Desactivar seleccionada")
        self.btn_desactivar.clicked.connect(self._on_desactivar)
        bottom.addWidget(self.btn_desactivar)
        bottom.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        bottom.addWidget(btn_cerrar)
        layout.addLayout(bottom)

        self.setLayout(layout)

    def _refresh(self) -> None:
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session, activas=True)
            self.tabla.setRowCount(len(ubicaciones))
            for row, ub in enumerate(ubicaciones):
                self.tabla.setItem(row, 0, QTableWidgetItem(ub.codigo))
                self.tabla.setItem(row, 1, QTableWidgetItem(ub.rack))
                nivel_item = QTableWidgetItem(str(ub.nivel))
                nivel_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, 2, nivel_item)
                self.tabla.setItem(row, 3, QTableWidgetItem(ub.descripcion or ""))
                num_cajas = len(ub.cajas) if ub.cajas else 0
                cajas_item = QTableWidgetItem(str(num_cajas))
                cajas_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, 4, cajas_item)

                self.tabla.item(row, 0).setData(Qt.ItemDataRole.UserRole, ub.id)

    def _on_agregar(self) -> None:
        rack = self.rack_input.text().strip().upper()
        nivel = self.nivel_input.value()
        desc = self.desc_input.text().strip() or None

        if not rack:
            QMessageBox.warning(self, "Error", "El rack es obligatorio.")
            return

        with get_session() as session:
            try:
                BodegaService.crear_ubicacion(session, rack, nivel, descripcion=desc)
                session.commit()
            except Exception as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return

        self.rack_input.clear()
        self.desc_input.clear()
        self._refresh()

    def _on_desactivar(self) -> None:
        row = self.tabla.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Selecciona una ubicación.")
            return

        item = self.tabla.item(row, 0)
        ub_id = item.data(Qt.ItemDataRole.UserRole)
        codigo = item.text()

        resp = QMessageBox.question(
            self, "Confirmar",
            f"¿Desactivar ubicación {codigo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        with get_session() as session:
            try:
                BodegaService.desactivar_ubicacion(session, ub_id)
                session.commit()
            except ValueError as e:
                session.rollback()
                QMessageBox.warning(self, "Error", str(e))
                return

        self._refresh()
