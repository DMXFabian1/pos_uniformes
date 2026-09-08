"""Equipo (solo dueño): dar de baja por temporada y reactivar empleadas.

Libreta → 👥 Equipo. Lista activas e inactivas con su descanso, último pago
y último movimiento; un botón por fila cambia el estado. Nada se borra.
"""

from __future__ import annotations

import logging
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

COLUMNAS = ("Empleada", "Gafete", "Estado", "Descanso", "Último pago", "Último movimiento", "")


def _fecha(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


class EquipoDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Equipo")
        self.resize(900, 520)
        self._fichas: list = []

        hint = QLabel(
            "Dar de baja no borra nada: su Libreta, pagos y calendario se quedan. Solo deja de "
            "aparecer en pendientes, pagos y ranking, y su gafete deja de entrar. Reactivar la regresa."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8177; font-size: 12px;")

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setObjectName("libretaTabla")
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #73341c; font-weight: 700;")
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addWidget(self.status, 1)
        pie.addWidget(cerrar)

        ly = QVBoxLayout()
        ly.setContentsMargins(16, 14, 16, 14)
        ly.addWidget(hint)
        ly.addWidget(self.tabla, 1)
        ly.addLayout(pie)
        self.setLayout(ly)
        self.recargar()

    def recargar(self) -> None:
        from pos_uniformes.services.equipo_service import listar_equipo

        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                self._fichas = listar_equipo(session)
        except Exception:  # noqa: BLE001
            logger.exception("Equipo: no se pudo cargar")
            self._fichas = []
            self.status.setText("Sin conexión con la PC principal.")
        self.pintar(self._fichas)

    def pintar(self, fichas: list) -> None:
        self._fichas = list(fichas)
        self.tabla.setRowCount(len(fichas))
        for i, f in enumerate(fichas):
            valores = (
                f.nombre,
                f.codigo,
                "Activa" if f.activa else "De baja",
                f.descanso,
                _fecha(f.ultimo_pago),
                _fecha(f.ultimo_movimiento),
            )
            for j, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                if j:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not f.activa:
                    item.setForeground(Qt.GlobalColor.gray)
                self.tabla.setItem(i, j, item)
            btn = QPushButton("⛔ Dar de baja" if f.activa else "✅ Reactivar")
            btn.setObjectName("secondaryButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(lambda _c=False, ficha=f: self._cambiar(ficha))
            self.tabla.setCellWidget(i, len(COLUMNAS) - 1, btn)

    def _cambiar(self, ficha) -> None:
        from pos_uniformes.services.equipo_service import cambiar_estado

        if ficha.activa:
            pregunta = f"¿Dar de baja a {ficha.nombre}?\n\nDeja de aparecer en pagos y pendientes y su gafete no entra. Se puede reactivar cuando regrese."
        else:
            pregunta = f"¿Reactivar a {ficha.nombre}?"
        if QMessageBox.question(self, "Equipo", pregunta, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                cambiar_estado(session, ficha.codigo, activa=not ficha.activa)
        except ValueError as exc:
            QMessageBox.warning(self, "Equipo", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Equipo: no se pudo cambiar el estado")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.status.setText(f"{ficha.nombre.split()[0]} {'dada de baja' if ficha.activa else 'reactivada'}.")
        self.recargar()
