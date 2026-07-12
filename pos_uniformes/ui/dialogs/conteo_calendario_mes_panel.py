"""Calendario visual de conteos por mes — widget embebible.

Grid de mes con cada escuela en el día de su próximo conteo. Se usa como vista
principal de la página "Calendario" del kiosko y dentro de
`ConteoCalendarioMesDialog` (que lo abre el admin). `session_factory` inyectable.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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

_STYLES = (
    "#mesNavBtn { background: #efe4d4; border: none; border-radius: 18px;"
    "  color: #7b2d14; font-size: 15px; font-weight: 800; }"
    "#mesNavBtn:hover { background: #e6d6bf; }"
    "#mesTitulo { color: #7b2d14; font-size: 21px; font-weight: 800; background: transparent; }"
    "#mesVencidas { background: #fdecec; color: #c0392b; font-weight: 700;"
    "  border: 1px solid #f0c0bd; border-radius: 10px; padding: 8px 12px; }"
    "#diaCabecera { color: #a0876f; font-size: 12px; font-weight: 800; background: transparent; }"
)


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoCalendarioMesPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        hoy: date | None = None,
        refresh_on_init: bool = True,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory or _default_session_factory
        self._hoy = hoy or date.today()
        self._anio = self._hoy.year
        self._mes = self._hoy.month
        self._estados: list = []
        self._build_ui()
        if refresh_on_init:
            self.refresh()

    def _build_ui(self) -> None:
        self.setStyleSheet(_STYLES)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        nav = QHBoxLayout()
        prev_btn = QPushButton("◀")
        prev_btn.setObjectName("mesNavBtn")
        prev_btn.setFixedSize(36, 36)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(lambda: self._cambiar_mes(-1))
        next_btn = QPushButton("▶")
        next_btn.setObjectName("mesNavBtn")
        next_btn.setFixedSize(36, 36)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(lambda: self._cambiar_mes(1))
        self._mes_label = QLabel("")
        self._mes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mes_label.setObjectName("mesTitulo")
        nav.addWidget(prev_btn)
        nav.addStretch()
        nav.addWidget(self._mes_label)
        nav.addStretch()
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        sumario = QHBoxLayout()
        sumario.setSpacing(8)
        _chip_qss = "border-radius: 13px; padding: 6px 14px; font-weight: 800; font-size: 13px;"
        self._chip_vencidas = QLabel("")
        self._chip_vencidas.setStyleSheet(f"background: #fbe3e0; color: #b0341f; {_chip_qss}")
        self._chip_aldia = QLabel("")
        self._chip_aldia.setStyleSheet(f"background: #e3f0e0; color: #2e7d32; {_chip_qss}")
        self._chip_mes = QLabel("")
        self._chip_mes.setStyleSheet(f"background: #f1e5d1; color: #7b2d14; {_chip_qss}")
        for c in (self._chip_vencidas, self._chip_aldia, self._chip_mes):
            sumario.addWidget(c)
        sumario.addStretch()
        layout.addLayout(sumario)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(8)
        # Columnas de ancho IGUAL (si no, la última se come todo el ancho).
        for c in range(7):
            self._grid.setColumnStretch(c, 1)
        layout.addWidget(self._grid_host, 1)

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

    def refresh(self) -> None:
        try:
            session = self._session_factory()
            try:
                self._estados = obtener_calendario_conteo(session)
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — sin conexión: calendario vacío, no crashear
            self._estados = []
        self._render()

    def _render(self) -> None:
        self._mes_label.setText(f"{_MESES[self._mes]} {self._anio}")

        por_dia = agrupar_calendario_por_dia(self._estados, self._anio, self._mes)
        vencidas = [e for e in self._estados if e.vencida]
        al_dia = [e for e in self._estados if not e.vencida]
        este_mes = sum(len(v) for v in por_dia.values())
        self._chip_vencidas.setText(f"🔴  {len(vencidas)} requieren conteo")
        self._chip_aldia.setText(f"🟢  {len(al_dia)} al día")
        self._chip_mes.setText(f"📅  {este_mes} este mes")

        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for r in range(8):
            self._grid.setRowStretch(r, 0)  # reset (meses varían de 4 a 6 semanas)

        for col, nombre in enumerate(_DIAS_SEMANA):
            cab = QLabel(nombre)
            cab.setObjectName("diaCabecera")
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(cab, 0, col)

        semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(self._anio, self._mes)
        for fila, semana in enumerate(semanas, start=1):
            self._grid.setRowStretch(fila, 1)  # semanas de alto igual, llenan el espacio
            for col, dia in enumerate(semana):
                if dia == 0:
                    self._grid.addWidget(self._celda_vacia(), fila, col)
                    continue
                self._grid.addWidget(self._celda(dia, por_dia.get(dia, []), col), fila, col)

    @staticmethod
    def _celda_vacia() -> QWidget:
        celda = QFrame()
        celda.setStyleSheet("QFrame { background: #f6f1e8; border: none; border-radius: 12px; }")
        celda.setMinimumHeight(72)
        return celda

    def _celda(self, dia: int, escuelas: list, col: int = 0) -> QWidget:
        celda = QFrame()
        es_hoy = date(self._anio, self._mes, dia) == self._hoy
        es_finde = col >= 5
        if es_hoy:
            fondo, borde, grosor = "#fdf4ec", "#d1622f", "2px"
        elif escuelas:
            fondo, borde, grosor = "#fffdf8", "#e2d0b6", "1px"
        elif es_finde:
            fondo, borde, grosor = "#f7f1e6", "#eadfcd", "1px"
        else:
            fondo, borde, grosor = "#fffefb", "#eae0cf", "1px"
        celda.setStyleSheet(
            f"QFrame {{ background: {fondo}; border: {grosor} solid {borde}; border-radius: 12px; }}"
        )
        celda.setMinimumHeight(72)
        v = QVBoxLayout(celda)
        v.setContentsMargins(9, 7, 9, 7)
        v.setSpacing(3)
        num = QLabel(str(dia))
        if es_hoy:
            num.setFixedSize(26, 26)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(
                "background: #c45425; color: white; border-radius: 13px;"
                " font-weight: 800; font-size: 12px;"
            )
            num_row = QHBoxLayout()
            num_row.setContentsMargins(0, 0, 0, 0)
            num_row.addWidget(num)
            num_row.addStretch()
            v.addLayout(num_row)
        else:
            num.setStyleSheet(
                "font-weight: 800; font-size: 13px; background: transparent; border: none;"
                f" color: {'#b3a08a' if es_finde else '#8a7358'};"
            )
            v.addWidget(num)
        for e in escuelas[:3]:
            v.addWidget(self._chip(e))
        if len(escuelas) > 3:
            mas = QLabel(f"+{len(escuelas) - 3} más")
            mas.setStyleSheet("font-size: 11px; color: #8a7a6a; background: transparent; border: none;")
            v.addWidget(mas)
        v.addStretch()
        return celda

    @staticmethod
    def _chip(e) -> QLabel:
        if e.vencida:
            bg, fg = "#fbe3e0", "#b0341f"
        elif e.dias_para_vencer is not None and e.dias_para_vencer <= 7:
            bg, fg = "#fbeecb", "#a06a10"
        else:
            bg, fg = "#f1e5d1", "#7b2d14"
        nombre = e.escuela_nombre
        texto = nombre if len(nombre) <= 15 else nombre[:14] + "…"
        chip = QLabel(texto)
        chip.setToolTip(nombre)
        chip.setStyleSheet(
            f"background: {bg}; color: {fg}; border: none; border-radius: 7px;"
            " padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        return chip
