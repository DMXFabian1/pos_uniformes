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
    ANTICIPACION_DIAS,
    DESCANSO,
    FALTA,
    PAGO,
    TRABAJO,
    WEEKDAY_NAMES,
    HorarioEmpleada,
    aplicar_intercambio,
    aplicar_solicitud_descanso,
    cargar_horarios_todos,
    comisiones_desde_ultimo_pago,
    dias_libres_cercanos,
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

        # ── Autoservicio de la empleada: pedir/cambiar SIN pasar por Daniel.
        # Las reglas (cupo 1 por día, 7 días de anticipación) deciden solas.
        if not is_owner:
            autoservicio = QHBoxLayout()
            autoservicio.setSpacing(10)
            self.btn_pedir = QPushButton("🙋 Pedir descanso este día")
            self.btn_pedir.setStyleSheet(
                "background: #a84f2d; color: #ffffff; font-weight: 700;"
                "border-radius: 12px; min-height: 48px; font-size: 15px;"
            )
            self.btn_pedir.clicked.connect(self._pedir_descanso)
            autoservicio.addWidget(self.btn_pedir, 1)
            self.btn_cambiar = QPushButton("🔄 Cambiar con compañera")
            self.btn_cambiar.setStyleSheet(
                "background: #f8f2e9; color: #73341c; font-weight: 700;"
                "border: 1px solid #ddd0c0;"
                "border-radius: 12px; min-height: 48px; font-size: 15px;"
            )
            self.btn_cambiar.clicked.connect(self._abrir_intercambio)
            autoservicio.addWidget(self.btn_cambiar, 1)
            ly.addLayout(autoservicio)

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
            self.btn_pedir.setEnabled(on)
            self.btn_cambiar.setEnabled(on)
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

    # ── Autoservicio (empleada) ──────────────────────────────────────────

    def _pedir_descanso(self) -> None:
        """Aprueba o rechaza SOLO, con las reglas — sin pasar por Daniel."""
        fecha = self._fecha_seleccionada()
        hoy = date.today()
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                horarios = cargar_horarios_todos(session)
                ok, msg = aplicar_solicitud_descanso(
                    session, horarios, self._code, fecha, hoy
                )
                if not ok:
                    libres = dias_libres_cercanos(horarios, self._code, hoy)
                    if libres:
                        msg += "\n\nDías que SÍ puedes pedir: " + ", ".join(
                            f.strftime("%a %d/%b") for f in libres
                        )
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: fallo la solicitud de descanso")
            QMessageBox.warning(self, "Sin conexión", "No se pudo pedir. Intenta de nuevo.")
            return
        if ok:
            QMessageBox.information(self, "Descanso aprobado ✅", msg)
            self._recargar()
        else:
            QMessageBox.warning(self, "No se pudo", msg)

    def _proximos_descansos(self, horario: HorarioEmpleada, hoy: date) -> list[date]:
        """Descansos futuros elegibles para intercambio (respetando la
        anticipación), en las próximas 5 semanas."""
        from datetime import timedelta

        dias = []
        dia = hoy + timedelta(days=ANTICIPACION_DIAS)
        for _ in range(35):
            if estado_del_dia(horario, dia) == DESCANSO:
                dias.append(dia)
            dia += timedelta(days=1)
        return dias

    def _abrir_intercambio(self) -> None:
        """A elige compañera y días; B acepta pasando su gafete. Sin Daniel."""
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Empleada

            with get_session() as session:
                horarios = cargar_horarios_todos(session)
                nombres = {
                    str(e.codigo).upper(): (e.nombre_completo or e.codigo).split()[0]
                    for e in session.query(Empleada).filter(Empleada.activo.is_(True))
                }
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: no se pudo cargar para intercambio")
            QMessageBox.warning(self, "Sin conexión", "No se pudo abrir. Intenta de nuevo.")
            return

        hoy = date.today()
        mios = self._proximos_descansos(
            horarios.get(self._code, HorarioEmpleada(employee_code=self._code)), hoy
        )
        if not mios:
            QMessageBox.information(
                self,
                "Sin descansos que cambiar",
                "No tienes descansos programados (con anticipación) para intercambiar.",
            )
            return

        from PyQt6.QtWidgets import QLineEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Cambiar descanso con compañera")
        dlg.setStyleSheet(self.styleSheet())
        dlg.resize(460, 360)
        ly = QVBoxLayout()
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(10)

        ly.addWidget(QLabel("Doy mi descanso del:"))
        combo_mio = QComboBox()
        for f in mios:
            combo_mio.addItem(f.strftime("%A %d/%b"), f)
        ly.addWidget(combo_mio)

        ly.addWidget(QLabel("Compañera:"))
        combo_b = QComboBox()
        ly.addWidget(combo_b)
        ly.addWidget(QLabel("Y tomo su descanso del:"))
        combo_suyo = QComboBox()
        ly.addWidget(combo_suyo)

        for code in sorted(horarios):
            if code != self._code and code != "VEND-1":
                combo_b.addItem(f"{nombres.get(code, code)} ({code})", code)

        def _rellenar_suyos() -> None:
            combo_suyo.clear()
            code_b = combo_b.currentData()
            if not code_b:
                return
            for f in self._proximos_descansos(horarios[code_b], hoy):
                combo_suyo.addItem(f.strftime("%A %d/%b"), f)

        combo_b.currentIndexChanged.connect(lambda _i: _rellenar_suyos())
        _rellenar_suyos()

        ly.addWidget(QLabel("Para aceptar, tu compañera pasa SU gafete:"))
        gafete = QLineEdit()
        gafete.setEchoMode(QLineEdit.EchoMode.Password)
        gafete.setPlaceholderText("Escanear gafete de la compañera...")
        ly.addWidget(gafete)

        estado = QLabel("")
        estado.setStyleSheet("color: #a33b25; font-weight: 600;")
        ly.addWidget(estado)

        botones = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(dlg.reject)
        botones.addWidget(btn_cancelar)
        btn_ok = QPushButton("🔄 Confirmar cambio")
        btn_ok.setStyleSheet(
            "background: #a84f2d; color: #ffffff; font-weight: 700;"
            "border-radius: 10px; min-height: 44px;"
        )
        botones.addWidget(btn_ok, 1)
        ly.addLayout(botones)
        dlg.setLayout(ly)

        def _confirmar() -> None:
            code_b = combo_b.currentData()
            fecha_a, fecha_b = combo_mio.currentData(), combo_suyo.currentData()
            escaneado = gafete.text().strip().upper()
            gafete.clear()
            if not code_b or fecha_a is None or fecha_b is None:
                estado.setText("Elige compañera y los dos días.")
                return
            if escaneado != code_b:
                estado.setText("Ese gafete no es de la compañera elegida.")
                return
            try:
                from pos_uniformes.database.connection import get_session

                with get_session() as session:
                    horarios_frescos = cargar_horarios_todos(session)
                    ok, msg = aplicar_intercambio(
                        session, horarios_frescos, self._code, fecha_a, code_b, fecha_b, hoy
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Calendario: fallo el intercambio")
                estado.setText("No se pudo guardar. Intenta de nuevo.")
                return
            if ok:
                QMessageBox.information(dlg, "Cambio hecho ✅", msg)
                dlg.accept()
                self._recargar()
            else:
                estado.setText(msg)

        btn_ok.clicked.connect(_confirmar)
        gafete.returnPressed.connect(_confirmar)
        dlg.exec()

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
