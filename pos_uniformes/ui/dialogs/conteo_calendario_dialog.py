"""Apartado admin del calendario de conteos (Fase 1).

Tabla de todas las escuelas con su estado de conteo (última fecha, próxima
fecha, vencida) y edición de la frecuencia (`dias_vigencia`) por escuela.

Los datos salen de `conteo_calendario_service`; guardar usa
`conteo_service.guardar_config_conteo`. El `session_factory` se inyecta para
poder probar el diálogo sin una DB real.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.conteo_calendario_service import obtener_calendario_conteo
from pos_uniformes.services.conteo_service import guardar_config_conteo

_ROJO = QColor("#c0392b")
_VERDE = QColor("#2e7d32")
_AMBAR = QColor("#b8860b")


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoCalendarioDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calendario de conteos")
        self._session_factory = session_factory or _default_session_factory
        self._spins: dict[int, QSpinBox] = {}
        self._build_ui()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        hint = QLabel(
            "Frecuencia de conteo por escuela. En rojo, las que ya toca contar. "
            "Ajusta los días y pulsa «Guardar frecuencias»."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._resumen_label = QLabel("")
        layout.addWidget(self._resumen_label)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Escuela", "Días vigencia", "Último conteo", "Próxima", "Estado"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        save_btn = QPushButton("Guardar frecuencias")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._guardar)
        refresh_btn = QPushButton("Refrescar")
        refresh_btn.clicked.connect(self.refresh)
        actions.addWidget(save_btn)
        actions.addWidget(refresh_btn)
        actions.addStretch()
        layout.addLayout(actions)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(760, 520)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        session = self._session_factory()
        try:
            calendario = obtener_calendario_conteo(session)
        finally:
            session.close()

        self._spins = {}
        self._table.setRowCount(len(calendario))
        vencidas = 0
        for fila, e in enumerate(calendario):
            if e.vencida:
                vencidas += 1

            self._table.setItem(fila, 0, QTableWidgetItem(e.escuela_nombre))

            spin = QSpinBox()
            spin.setRange(1, 365)
            spin.setValue(e.dias_vigencia)
            spin.setSuffix(" días")
            self._spins[e.escuela_id] = spin
            self._table.setCellWidget(fila, 1, spin)

            ultimo = e.ultimo_conteo.date().isoformat() if e.ultimo_conteo else "Nunca"
            self._table.setItem(fila, 2, QTableWidgetItem(ultimo))

            proxima = e.proxima_fecha.isoformat() if e.proxima_fecha else "—"
            self._table.setItem(fila, 3, QTableWidgetItem(proxima))

            estado_item = QTableWidgetItem(self._estado_texto(e))
            estado_item.setForeground(QBrush(self._estado_color(e)))
            self._table.setItem(fila, 4, estado_item)

        self._resumen_label.setText(
            f"{len(calendario)} escuelas · {vencidas} requieren conteo"
        )

    @staticmethod
    def _estado_texto(e) -> str:
        if e.nunca_contada:
            return "Nunca contada"
        if e.vencida:
            return f"Vencida (hace {abs(e.dias_para_vencer)}d)"
        return f"Al día ({e.dias_para_vencer}d)"

    @staticmethod
    def _estado_color(e) -> QColor:
        if e.nunca_contada or e.vencida:
            return _ROJO
        if e.dias_para_vencer is not None and e.dias_para_vencer <= 7:
            return _AMBAR
        return _VERDE

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _guardar(self) -> None:
        session = self._session_factory()
        try:
            for escuela_id, spin in self._spins.items():
                guardar_config_conteo(session, escuela_id, spin.value())
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")
            return
        finally:
            session.close()
        QMessageBox.information(self, "Guardado", "Frecuencias de conteo actualizadas.")
        self.refresh()
