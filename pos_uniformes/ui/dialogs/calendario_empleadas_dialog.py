"""Calendario de empleadas dentro de la Libreta (satélite).

Empleada: consulta sus descansos, faltas y su próximo pago, con el banner
de comisiones acumuladas desde el último pago.

Dueño (VEND-1): además elige empleada, configura su horario (día de
descanso fijo + ciclo de pago en días trabajados), marca faltas/descansos
sobre el calendario y registra "le pagué este día" (que reinicia el ciclo
y el banner de comisiones).
"""

from __future__ import annotations

import logging
from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    FALTA,
    PAGO,
    TRABAJO,
    WEEKDAY_NAMES,
    HorarioEmpleada,
    comisiones_desde_ultimo_pago,
    estado_del_dia,
    guardar_horario,
    marcar_dia,
    quitar_marca,
    registrar_pago,
    resumen_empleada,
)

logger = logging.getLogger(__name__)

# Colores dark-mode-proof (mismos tonos crema/terracota del satélite).
_COLORES_DIA = {
    DESCANSO: ("#dce8f7", "#2b5c8a"),
    FALTA: ("#f6d3cb", "#a33b25"),
    PAGO: ("#d9ecd0", "#3d6b2f"),
}


class _CalendarioPintado(QCalendarWidget):
    """Calendario que pinta cada día según el horario de la empleada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.horario: HorarioEmpleada | None = None
        self.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setGridVisible(False)
        self.setStyleSheet(
            "QCalendarWidget QWidget { background: #f9f4ea; color: #2c2a27; }"
            "QCalendarWidget QToolButton { color: #2c2a27; background: #f4ede2;"
            "  border-radius: 6px; padding: 4px 10px; font-weight: 600; }"
            "QCalendarWidget QAbstractItemView { background: #ffffff;"
            "  color: #2c2a27; selection-background-color: #a84f2d;"
            "  selection-color: #ffffff; outline: none; }"
        )

    def set_horario(self, horario: HorarioEmpleada | None) -> None:
        self.horario = horario
        self.updateCells()

    def paintCell(self, painter, rect, qdate: QDate) -> None:  # noqa: N802
        dia = date(qdate.year(), qdate.month(), qdate.day())
        estado = (
            estado_del_dia(self.horario, dia) if self.horario is not None else TRABAJO
        )
        colores = _COLORES_DIA.get(estado)
        fuera_de_mes = qdate.month() != self.monthShown()
        painter.save()
        if self.selectedDate() == qdate:
            # La vista pinta el fondo de selección terracota: encima va el
            # número en blanco y negritas (si no, número invisible).
            painter.fillRect(rect.adjusted(2, 2, -2, -2), QColor("#a84f2d"))
            painter.setPen(QColor("#ffffff"))
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
        elif colores and not fuera_de_mes:
            fondo, texto = colores
            painter.fillRect(rect.adjusted(2, 2, -2, -2), QColor(fondo))
            painter.setPen(QColor(texto))
        elif fuera_de_mes:
            painter.setPen(QColor("#b9b1a5"))
        else:
            painter.setPen(QColor("#2c2a27"))
        if dia == date.today():
            font = QFont(painter.font())
            font.setUnderline(True)
            painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))
        painter.restore()


class CalendarioEmpleadasDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        employee_code: str,
        employee_name: str,
        is_owner: bool,
    ):
        super().__init__(parent)
        self._code = str(employee_code).strip().upper()
        self._is_owner = bool(is_owner)
        self._horario: HorarioEmpleada | None = None
        self._online = False

        self.setWindowTitle("Calendario" if not is_owner else "Calendario de empleadas")
        self.resize(560, 640 if is_owner else 540)
        self.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
        )

        ly = QVBoxLayout()
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(10)

        # ── Selector de empleada (solo dueño) ──
        self._combo: QComboBox | None = None
        if is_owner:
            fila = QHBoxLayout()
            fila.addWidget(QLabel("Empleada:"))
            self._combo = QComboBox()
            self._combo.setMinimumWidth(240)
            fila.addWidget(self._combo)
            fila.addStretch()
            ly.addLayout(fila)

        # ── Banner: comisiones desde el último pago ──
        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background: #a84f2d; color: #ffffff; border-radius: 10px;"
            "padding: 10px 14px; font-size: 15px; font-weight: 700;"
        )
        ly.addWidget(self.banner)

        self.resumen = QLabel("")
        self.resumen.setWordWrap(True)
        self.resumen.setStyleSheet("font-size: 13px; color: #5f594f;")
        ly.addWidget(self.resumen)

        self.estado_conexion = QLabel(
            "Sin conexion con la PC principal: el calendario no esta disponible."
        )
        self.estado_conexion.setStyleSheet("color: #a33b25; font-weight: 600;")
        self.estado_conexion.setVisible(False)
        ly.addWidget(self.estado_conexion)

        self.cal = _CalendarioPintado()
        ly.addWidget(self.cal, 1)

        leyenda = QLabel(
            '<span style="background:#dce8f7; color:#2b5c8a;">&nbsp;Descanso&nbsp;</span> '
            '<span style="background:#f6d3cb; color:#a33b25;">&nbsp;Falta&nbsp;</span> '
            '<span style="background:#d9ecd0; color:#3d6b2f;">&nbsp;Pago&nbsp;</span> '
            "&nbsp;(hoy va subrayado)"
        )
        leyenda.setStyleSheet("font-size: 12px;")
        ly.addWidget(leyenda)

        # ── Acciones del dueño sobre el día seleccionado ──
        if is_owner:
            acciones = QHBoxLayout()
            acciones.setSpacing(8)
            self.btn_falta = QPushButton("Marcar falta")
            self.btn_descanso = QPushButton("Descanso ese día")
            self.btn_trabajo = QPushButton("Sí trabajó")
            self.btn_quitar = QPushButton("Quitar marca")
            for btn, tipo in (
                (self.btn_falta, FALTA),
                (self.btn_descanso, DESCANSO),
                (self.btn_trabajo, TRABAJO),
            ):
                btn.clicked.connect(lambda _=False, t=tipo: self._marcar(t))
                acciones.addWidget(btn)
            self.btn_quitar.clicked.connect(self._quitar)
            acciones.addWidget(self.btn_quitar)
            ly.addLayout(acciones)

            fila_pago = QHBoxLayout()
            self.btn_pago = QPushButton("💵 Le pagué este día")
            self.btn_pago.setStyleSheet(
                "background: #3d6b2f; color: #ffffff; font-weight: 700;"
                "border-radius: 8px; padding: 8px 14px;"
            )
            self.btn_pago.clicked.connect(self._pagar)
            fila_pago.addWidget(self.btn_pago)
            fila_pago.addStretch()
            ly.addLayout(fila_pago)

            # ── Configuración del horario ──
            config = QHBoxLayout()
            config.setSpacing(8)
            config.addWidget(QLabel("Descanso fijo:"))
            self.combo_descanso = QComboBox()
            self.combo_descanso.addItem("Sin descanso fijo", None)
            for idx, nombre in enumerate(WEEKDAY_NAMES):
                self.combo_descanso.addItem(nombre.capitalize(), idx)
            config.addWidget(self.combo_descanso)
            config.addWidget(QLabel("Pago cada"))
            self.spin_ciclo = QSpinBox()
            self.spin_ciclo.setRange(1, 31)
            self.spin_ciclo.setValue(7)  # semanal: cobran el mismo día cada semana
            self.spin_ciclo.setSuffix(" días")
            config.addWidget(self.spin_ciclo)
            self.btn_guardar = QPushButton("Guardar horario")
            self.btn_guardar.clicked.connect(self._guardar_config)
            config.addWidget(self.btn_guardar)
            config.addStretch()
            ly.addLayout(config)

        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(cerrar)
        ly.addLayout(pie)
        self.setLayout(ly)

        if self._combo is not None:
            self._cargar_empleadas(employee_code, employee_name)
            self._combo.currentIndexChanged.connect(lambda _i: self._recargar())
        self._recargar()

    # ── Datos ────────────────────────────────────────────────────────────

    def _codigo_activo(self) -> str:
        if self._combo is not None and self._combo.currentData():
            return str(self._combo.currentData())
        return self._code

    def _cargar_empleadas(self, employee_code: str, employee_name: str) -> None:
        assert self._combo is not None
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Empleada

            with get_session() as session:
                filas = (
                    session.query(Empleada)
                    .filter(Empleada.activo.is_(True))
                    .order_by(Empleada.codigo)
                    .all()
                )
            for emp in filas:
                self._combo.addItem(f"{emp.codigo} — {emp.nombre_completo}", emp.codigo)
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: no se pudo listar empleadas")
        if self._combo.count() == 0:
            self._combo.addItem(f"{employee_code} — {employee_name}", employee_code)

    def _recargar(self) -> None:
        from pos_uniformes.services.satellite_startup_service import probe_database_host

        self._online = probe_database_host(0.5)
        self.estado_conexion.setVisible(not self._online)
        if not self._online:
            self.cal.set_horario(None)
            self.banner.setVisible(False)
            self.resumen.setText("")
            self._habilitar_acciones(False)
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.calendario_empleadas_service import cargar_horario

            code = self._codigo_activo()
            with get_session() as session:
                self._horario = cargar_horario(session, code)
                comisiones = comisiones_desde_ultimo_pago(session, code, self._horario)
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: fallo la carga")
            self.estado_conexion.setVisible(True)
            self._habilitar_acciones(False)
            return
        self.cal.set_horario(self._horario)
        self.banner.setVisible(True)
        self.banner.setText(f"⭐ Comisiones desde el último pago: {comisiones}")
        self.resumen.setText(resumen_empleada(self._horario, date.today()))
        self._habilitar_acciones(True)
        if self._is_owner:
            self.combo_descanso.setCurrentIndex(
                0
                if self._horario.descanso_weekday is None
                else self._horario.descanso_weekday + 1
            )
            self.spin_ciclo.setValue(self._horario.ciclo_dias_pago)

    def _habilitar_acciones(self, on: bool) -> None:
        if not self._is_owner:
            return
        for btn in (
            self.btn_falta,
            self.btn_descanso,
            self.btn_trabajo,
            self.btn_quitar,
            self.btn_pago,
            self.btn_guardar,
        ):
            btn.setEnabled(on)

    # ── Acciones del dueño ───────────────────────────────────────────────

    def _fecha_seleccionada(self) -> date:
        q = self.cal.selectedDate()
        return date(q.year(), q.month(), q.day())

    def _con_sesion(self, fn) -> bool:
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                fn(session)
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: no se pudo guardar")
            QMessageBox.warning(
                self, "Sin conexión", "No se pudo guardar. Revisa la conexión."
            )
            return False

    def _marcar(self, tipo: str) -> None:
        fecha = self._fecha_seleccionada()
        if self._con_sesion(
            lambda s: marcar_dia(s, self._codigo_activo(), fecha, tipo)
        ):
            self._recargar()

    def _quitar(self) -> None:
        fecha = self._fecha_seleccionada()
        if self._con_sesion(lambda s: quitar_marca(s, self._codigo_activo(), fecha)):
            self._recargar()

    def _pagar(self) -> None:
        fecha = self._fecha_seleccionada()
        code = self._codigo_activo()
        confirmar = QMessageBox.question(
            self,
            "Registrar pago",
            f"¿Registrar que a {code} se le pagó el {fecha.strftime('%d/%b/%Y')}?\n"
            "Esto reinicia su ciclo y su contador de comisiones.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmar != QMessageBox.StandardButton.Yes:
            return
        if self._con_sesion(lambda s: registrar_pago(s, code, fecha)):
            self._recargar()

    def _guardar_config(self) -> None:
        descanso = self.combo_descanso.currentData()
        ciclo = int(self.spin_ciclo.value())
        if self._con_sesion(
            lambda s: guardar_horario(
                s,
                self._codigo_activo(),
                descanso_weekday=descanso,
                ciclo_dias_pago=ciclo,
            )
        ):
            self._recargar()
