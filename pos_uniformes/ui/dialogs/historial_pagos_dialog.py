"""Historial de pagos a empleadas (solo dueño): Libreta → 💵 Pagos.

Filtro por mes y empleada; cada pago con su desglose (base + comisiones −
faltas), quién lo registró, y totales por empleada y del periodo.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
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

logger = logging.getLogger(__name__)

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
COLUMNAS = ("Fecha", "Empleada", "Periodo", "Base", "Comisiones", "Faltas", "Total", "Registró")


def _item(texto: str, centrado: bool = True, negrita: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    if centrado:
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if negrita:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def filas_tabla(pagos: list) -> list[tuple[str, ...]]:
    """Filas de texto para la tabla (puro, testeable)."""
    filas = []
    for p in pagos:
        desde = p.desde.strftime("%d/%m") if p.desde else "inicio"
        filas.append((
            p.fecha.strftime("%d/%m/%Y"),
            p.employee_name or p.employee_code,
            f"{desde} → {p.hasta:%d/%m}",
            f"${Decimal(p.sueldo_base):,.2f}",
            f"{int(p.comisiones or 0)} × ${Decimal(p.tarifa_comision):,.2f} = ${Decimal(p.monto_comisiones):,.2f}",
            f"{int(p.faltas or 0)} (−${Decimal(p.descuento_faltas):,.2f})" if int(p.faltas or 0) else "0",
            f"${Decimal(p.total):,.2f}",
            str(p.creado_por or ""),
        ))
    return filas


class HistorialPagosDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, hoy: date | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pagos a empleadas")
        self._hoy = hoy or date.today()
        self.resize(980, 640)

        self.mes_combo = QComboBox()
        y, m = self._hoy.year, self._hoy.month
        for _ in range(12):
            self.mes_combo.addItem(f"{_MESES[m - 1].capitalize()} {y}", (y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        self.emp_combo = QComboBox()
        self.emp_combo.addItem("Todas las empleadas", None)
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.recargar)
        self.mes_combo.currentIndexChanged.connect(lambda _i: self.recargar())
        self.emp_combo.currentIndexChanged.connect(lambda _i: self.recargar())

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Mes:"))
        filtros.addWidget(self.mes_combo)
        filtros.addWidget(QLabel("Empleada:"))
        filtros.addWidget(self.emp_combo)
        filtros.addWidget(self.refresh_button)
        filtros.addStretch()

        self.totales_label = QLabel("")
        self.totales_label.setWordWrap(True)
        self.totales_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #73341c;")

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setObjectName("libretaTabla")
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)

        self.resumen_tabla = QTableWidget(0, 5)
        self.resumen_tabla.setObjectName("libretaTabla")
        self.resumen_tabla.setHorizontalHeaderLabels(["Empleada", "Pagos", "Comisiones", "Faltas", "Total pagado"])
        self.resumen_tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.resumen_tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.resumen_tabla.verticalHeader().setVisible(False)
        self.resumen_tabla.setMaximumHeight(180)

        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(cerrar)

        ly = QVBoxLayout()
        ly.setContentsMargins(16, 14, 16, 14)
        ly.setSpacing(8)
        ly.addLayout(filtros)
        ly.addWidget(self.totales_label)
        ly.addWidget(QLabel("Por empleada en el mes:"))
        ly.addWidget(self.resumen_tabla)
        ly.addWidget(QLabel("Cada pago:"))
        ly.addWidget(self.tabla, 1)
        ly.addLayout(pie)
        self.setLayout(ly)

        self._cargar_empleadas()
        self.recargar()

    def _cargar_empleadas(self) -> None:
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Empleada

            with get_session() as session:
                filas = session.query(Empleada).filter(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo).all()
                for e in filas:
                    if e.codigo.upper() in ("VEND-1", "ENC-1"):
                        continue
                    self.emp_combo.addItem(e.nombre_completo, e.codigo.upper())
        except Exception:  # noqa: BLE001
            logger.exception("Historial de pagos: no se pudieron cargar empleadas")

    def _rango(self) -> tuple[date, date]:
        from pos_uniformes.services.nomina_service import rango_mes

        y, m = self.mes_combo.currentData()
        return rango_mes(y, m)

    def recargar(self) -> None:
        from pos_uniformes.services.nomina_service import listar_pagos, resumir_pagos_por_empleada

        desde, hasta = self._rango()
        code = self.emp_combo.currentData()
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                pagos = listar_pagos(session, desde=desde, hasta=hasta, employee_code=code)
                for p in pagos:
                    session.expunge(p)
        except Exception:  # noqa: BLE001
            logger.exception("Historial de pagos: fallo la consulta")
            pagos = []
            self.totales_label.setText("Sin conexión con la PC principal.")
        self.pintar(pagos)

    def pintar(self, pagos: list) -> None:
        from pos_uniformes.services.nomina_service import resumir_pagos_por_empleada

        filas = filas_tabla(pagos)
        self.tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, texto in enumerate(fila):
                self.tabla.setItem(i, j, _item(texto, centrado=j not in (1, 2), negrita=(j == 6)))
        totales = resumir_pagos_por_empleada(pagos)
        self.resumen_tabla.setRowCount(len(totales))
        for i, t in enumerate(totales):
            self.resumen_tabla.setItem(i, 0, _item(t.employee_name, centrado=False))
            self.resumen_tabla.setItem(i, 1, _item(str(t.pagos)))
            self.resumen_tabla.setItem(i, 2, _item(f"{t.comisiones} (${t.monto_comisiones:,.2f})"))
            self.resumen_tabla.setItem(i, 3, _item(f"{t.faltas} (−${t.descuento_faltas:,.2f})" if t.faltas else "0"))
            self.resumen_tabla.setItem(i, 4, _item(f"${t.total:,.2f}", negrita=True))
        total = sum((t.total for t in totales), Decimal("0.00"))
        if pagos:
            self.totales_label.setText(
                f"{len(pagos)} pago(s) en el mes · Total pagado: ${total:,.2f}"
            )
        elif not self.totales_label.text().startswith("Sin conexión"):
            self.totales_label.setText("No hay pagos registrados en este mes.")
