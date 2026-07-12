"""Calendario visual de conteos por mes (Fase 4).

Grid de mes que coloca cada escuela en el día de su próximo conteo. Las
vencidas (fecha pasada o nunca contadas) se muestran resaltadas arriba.
Complementa la lista del apartado admin. `session_factory` inyectable.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.conteo_calendario_service import (
    agrupar_calendario_por_dia,
    obtener_calendario_conteo,
)

_DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoCalendarioMesDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        hoy: date | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calendario de conteos")
        self._session_factory = session_factory or _default_session_factory
        self._hoy = hoy or date.today()
        self._anio = self._hoy.year
        self._mes = self._hoy.month
        self._estados: list = []
        self._build_ui()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        nav = QHBoxLayout()
        prev_btn = QPushButton("◀")
        prev_btn.setFixedWidth(44)
        prev_btn.clicked.connect(lambda: self._cambiar_mes(-1))
        next_btn = QPushButton("▶")
        next_btn.setFixedWidth(44)
        next_btn.clicked.connect(lambda: self._cambiar_mes(1))
        self._mes_label = QLabel("")
        self._mes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mes_label.setObjectName("guidedStepTitle")
        nav.addWidget(prev_btn)
        nav.addStretch()
        nav.addWidget(self._mes_label)
        nav.addStretch()
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self._vencidas_label = QLabel("")
        self._vencidas_label.setWordWrap(True)
        self._vencidas_label.setStyleSheet("color: #c0392b; font-weight: 700;")
        layout.addWidget(self._vencidas_label)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(4)
        layout.addWidget(self._grid_host, 1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(820, 620)

    def _cambiar_mes(self, delta: int) -> None:
        mes = self._mes + delta
        anio = self._anio
        if mes < 1:
            mes = 12
            anio -= 1
        elif mes > 12:
            mes = 1
            anio += 1
        self._mes, self._anio = mes, anio
        self._render()

    # ── Datos ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        session = self._session_factory()
        try:
            self._estados = obtener_calendario_conteo(session)
        finally:
            session.close()
        self._render()

    def _render(self) -> None:
        self._mes_label.setText(f"{_MESES[self._mes]} {self._anio}")

        vencidas = [e for e in self._estados if e.vencida]
        if vencidas:
            nombres = ", ".join(e.escuela_nombre for e in vencidas[:6])
            extra = f" y {len(vencidas) - 6} más" if len(vencidas) > 6 else ""
            self._vencidas_label.setText(f"⚠ {len(vencidas)} vencidas: {nombres}{extra}")
        else:
            self._vencidas_label.setText("")

        # Limpiar grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for col, nombre in enumerate(_DIAS_SEMANA):
            cab = QLabel(nombre)
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cab.setStyleSheet("font-weight: 700; color: #7a6d60;")
            self._grid.addWidget(cab, 0, col)

        por_dia = agrupar_calendario_por_dia(self._estados, self._anio, self._mes)
        # calendar.monthcalendar: filas de semanas, 0 = día fuera del mes. Lunes primero.
        semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(self._anio, self._mes)
        for fila, semana in enumerate(semanas, start=1):
            for col, dia in enumerate(semana):
                if dia == 0:
                    continue
                self._grid.addWidget(self._celda(dia, por_dia.get(dia, [])), fila, col)

    def _celda(self, dia: int, escuelas: list) -> QWidget:
        celda = QFrame()
        es_hoy = date(self._anio, self._mes, dia) == self._hoy
        borde = "#c45425" if es_hoy else "#e0d5c5"
        fondo = "#fdf3ea" if escuelas else "#fffdf8"
        celda.setStyleSheet(
            f"QFrame {{ background: {fondo}; border: {'2px' if es_hoy else '1px'} solid {borde};"
            " border-radius: 8px; } QLabel { border: none; background: transparent; }"
        )
        celda.setMinimumHeight(84)
        v = QVBoxLayout(celda)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(2)
        num = QLabel(str(dia))
        num.setStyleSheet("font-weight: 700; color: #5a4a3f;")
        v.addWidget(num)
        for e in escuelas[:3]:
            etq = QLabel(f"• {e.escuela_nombre}")
            etq.setStyleSheet("font-size: 11px; color: #7b2d14;")
            etq.setWordWrap(True)
            v.addWidget(etq)
        if len(escuelas) > 3:
            mas = QLabel(f"+{len(escuelas) - 3} más")
            mas.setStyleSheet("font-size: 11px; color: #8a7a6a;")
            v.addWidget(mas)
        v.addStretch()
        return celda
