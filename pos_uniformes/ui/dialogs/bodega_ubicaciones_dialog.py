"""Diálogo de ubicaciones de bodega (solo lectura — PISO y ALMACÉN fijos)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
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
        self.setWindowTitle("Ubicaciones")
        self.setMinimumSize(450, 250)
        self._init_ui()
        self._refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Ubicaciones fijas: Piso (sucursal) y Almacén (otro edificio)."))

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Ubicación", "Niveles", "Cajas", "Unidades"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla)

        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        bottom.addWidget(btn_cerrar)
        layout.addLayout(bottom)

        self.setLayout(layout)

    def _refresh(self) -> None:
        with get_session() as session:
            ubicaciones = BodegaService.listar_ubicaciones(session, activas=True)
            from collections import defaultdict
            by_rack: dict[str, list] = defaultdict(list)
            for ub in ubicaciones:
                by_rack[ub.rack].append(ub)

            self.tabla.setRowCount(len(by_rack))
            for row, (rack, ubs) in enumerate(sorted(by_rack.items())):
                total_cajas = sum(len(ub.cajas) if ub.cajas else 0 for ub in ubs)
                total_unidades = 0
                for ub in ubs:
                    if ub.cajas:
                        for caja in ub.cajas:
                            if caja.contenido:
                                total_unidades += sum(c.cantidad for c in caja.contenido)

                self.tabla.setItem(row, 0, QTableWidgetItem(rack))
                niveles_item = QTableWidgetItem(str(len(ubs)))
                niveles_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, 1, niveles_item)
                cajas_item = QTableWidgetItem(str(total_cajas))
                cajas_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, 2, cajas_item)
                unidades_item = QTableWidgetItem(str(total_unidades))
                unidades_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(row, 3, unidades_item)
