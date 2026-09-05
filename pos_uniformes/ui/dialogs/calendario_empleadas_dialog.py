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
from decimal import Decimal

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
        is_encargado: bool = False,
    ):
        super().__init__(parent)
        self._code = str(employee_code).strip().upper()
        self._is_owner = bool(is_owner)
        # Encargado (el papá): marca faltas/descansos de cualquier empleada,
        # pero sin pagos, sin config de horarios y sin banner de comisiones.
        self._es_encargado = bool(is_encargado) and not self._is_owner
        self._gestiona = self._is_owner or self._es_encargado
        self._horario: HorarioEmpleada | None = None
        self._online = False

        if self._is_owner:
            titulo_ventana = "Calendario de empleadas"
        elif self._es_encargado:
            titulo_ventana = "Calendario — encargado"
        else:
            titulo_ventana = "Calendario"
        self.setWindowTitle(titulo_ventana)
        self.resize(560, 640 if self._gestiona else 540)
        is_owner = self._is_owner  # el resto del constructor decide con esto
        self.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
        )

        ly = QVBoxLayout()
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(10)

        # ── Selector de empleada (dueño y encargado) ──
        self._combo: QComboBox | None = None
        if self._gestiona:
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
        if not self._gestiona:
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

        # ── Marcar días: dueño Y encargado ──
        if self._gestiona:
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

        # ── Pagos y configuración: SOLO dueño ──
        if is_owner:
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
        # El encargado gestiona días, no ve productividad ni pagos.
        self.banner.setVisible(not self._es_encargado)
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
        # Cada modo (empleada/encargado/dueño) tiene su propio juego de
        # botones; se habilitan los que existan.
        for nombre in (
            "btn_pedir",
            "btn_cambiar",
            "btn_falta",
            "btn_descanso",
            "btn_trabajo",
            "btn_quitar",
            "btn_pago",
            "btn_guardar",
        ):
            btn = getattr(self, nombre, None)
            if btn is not None:
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


_MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _fecha_en_palabras(fecha: date) -> str:
    return f"{WEEKDAY_NAMES[fecha.weekday()]} {fecha.day} de {_MESES_ES[fecha.month - 1]}"


class CalendarioEncargadoDialog(QDialog):
    """Modo ultra-simple para el encargado (León, papá de Daniel — no le
    gusta la tecnología): tres preguntas con botones GRANDES, confirmación
    en palabras llanas y botón de "me equivoqué". Nada de combos, tablas
    ni configuración."""

    _BTN = (
        "QPushButton { background: #ffffff; color: #2c2a27;"
        " border: 2px solid #ddd0c0; border-radius: 16px;"
        " font-size: 22px; font-weight: 700; min-height: 68px; }"
        "QPushButton:pressed { background: #f1e6d6; }"
    )
    _BTN_ACENTO = (
        "QPushButton { background: #a84f2d; color: #ffffff; border: none;"
        " border-radius: 16px; font-size: 22px; font-weight: 800; min-height: 68px; }"
        "QPushButton:pressed { background: #8a4326; }"
    )
    _BTN_SUAVE = (
        "QPushButton { background: #f4ede2; color: #73341c;"
        " border: 1px solid #ddd0c0; border-radius: 12px;"
        " font-size: 17px; font-weight: 700; min-height: 52px; }"
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Calendario")
        self.resize(560, 660)
        self.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
        )
        self._sel_code: str | None = None
        self._sel_nombre: str = ""
        self._sel_tipo: str | None = None
        self._ultima_marca: tuple[str, date] | None = None

        from PyQt6.QtWidgets import QStackedWidget

        self._pila = QStackedWidget()
        raiz = QVBoxLayout()
        raiz.setContentsMargins(22, 20, 22, 20)
        raiz.addWidget(self._pila, 1)
        self.setLayout(raiz)

        self._pg_menu = self._pagina_menu()
        self._pg_quien = self._pagina_quien()
        self._pg_que = self._pagina_que()
        self._pg_cuando = self._pagina_cuando()
        self._pg_listo = self._pagina_listo()
        self._pg_cortes = self._pagina_cortes()
        self._pg_corte = self._pagina_corte_hoy()
        for p in (
            self._pg_menu,
            self._pg_quien,
            self._pg_que,
            self._pg_cuando,
            self._pg_listo,
            self._pg_cortes,
            self._pg_corte,
        ):
            self._pila.addWidget(p)
        self._pila.setCurrentWidget(self._pg_menu)

    # ── Páginas ──────────────────────────────────────────────────────────

    def _titulo(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 26px; font-weight: 800; color: #73341c;")
        return lbl

    def _pagina_menu(self) -> QWidget:
        """Pantalla de inicio de León: dos cosas, en grande."""
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(14)
        ly.addWidget(self._titulo("¿Qué quieres hacer?"))
        btn_apuntar = QPushButton("🗓  Apuntar falta o descanso")
        btn_apuntar.setStyleSheet(self._BTN)
        btn_apuntar.clicked.connect(self._ir_a_quien)
        ly.addWidget(btn_apuntar)
        btn_cortes = QPushButton("💵  Ver cortes")
        btn_cortes.setStyleSheet(self._BTN)
        btn_cortes.clicked.connect(self._ir_a_cortes)
        ly.addWidget(btn_cortes)
        btn_hacer = QPushButton("🧾  Hacer corte de hoy")
        btn_hacer.setStyleSheet(self._BTN)
        btn_hacer.clicked.connect(self._ir_a_corte_hoy)
        ly.addWidget(btn_hacer)
        ly.addStretch()
        salir = QPushButton("Salir")
        salir.setStyleSheet(self._BTN_SUAVE)
        salir.clicked.connect(self.accept)
        ly.addWidget(salir)
        pagina.setLayout(ly)
        return pagina

    def _pagina_cortes(self) -> QWidget:
        """Cortes anteriores: SOLO fecha y cifra — lo que Daniel entregó."""
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(10)
        ly.addWidget(self._titulo("Cortes"))
        self._cortes_lista = QVBoxLayout()
        self._cortes_lista.setSpacing(8)
        ly.addLayout(self._cortes_lista)
        ly.addStretch()
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_menu))
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

    def _ir_a_cortes(self) -> None:
        while self._cortes_lista.count():
            item = self._cortes_lista.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.libreta_service import listar_cortes

            with get_session() as session:
                cortes = listar_cortes(session, limit=10)
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudieron cargar los cortes")
            cortes = None
        if cortes is None:
            aviso = QLabel("No hay conexión.\nCierra e intenta otra vez.")
            aviso.setStyleSheet("font-size: 22px; font-weight: 700; color: #a33b25;")
            self._cortes_lista.addWidget(aviso)
        elif not cortes:
            vacio = QLabel("Todavía no hay cortes guardados.")
            vacio.setStyleSheet("font-size: 20px; font-weight: 600;")
            self._cortes_lista.addWidget(vacio)
        else:
            for corte in cortes:
                fila = QLabel(
                    f"{_fecha_en_palabras(corte.fecha)}   —   "
                    f"${corte.monto_final:,.2f}"
                )
                fila.setStyleSheet(
                    "background: #ffffff; border: 2px solid #ddd0c0;"
                    " border-radius: 14px; padding: 14px 16px;"
                    " font-size: 21px; font-weight: 700; color: #2c2a27;"
                )
                self._cortes_lista.addWidget(fila)
        self._pila.setCurrentWidget(self._pg_cortes)

    def _pagina_corte_hoy(self) -> QWidget:
        """Confirmación del corte de León: la cifra CALCULADA, sin editar."""
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(14)
        ly.addWidget(self._titulo("Corte de hoy"))
        ly.addStretch()
        self._corte_texto = QLabel("")
        self._corte_texto.setWordWrap(True)
        self._corte_texto.setStyleSheet(
            "font-size: 30px; font-weight: 800; color: #2c2a27;"
        )
        ly.addWidget(self._corte_texto)
        ly.addStretch()
        self._btn_corte_ok = QPushButton("🖨  Imprimir corte")
        self._btn_corte_ok.setStyleSheet(self._BTN_ACENTO)
        self._btn_corte_ok.clicked.connect(self._hacer_corte)
        ly.addWidget(self._btn_corte_ok)
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_menu))
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

    def _datos_corte_hoy(self):
        """(cortes, por_empleada, monto) de las operaciones de hoy."""
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.libreta_service import (
            listar_operaciones,
            resumir_por_dia,
            resumir_por_empleada,
            ventana_hoy,
        )

        desde, hasta = ventana_hoy()
        with get_session() as session:
            rows = listar_operaciones(session, desde=desde, hasta=hasta)
        cortes = resumir_por_dia(rows)
        monto = sum((c.monto_en_caja for c in cortes), Decimal("0.00"))
        return cortes, resumir_por_empleada(rows), monto

    def _ir_a_corte_hoy(self) -> None:
        try:
            self._corte_datos = self._datos_corte_hoy()
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo calcular el corte")
            QMessageBox.warning(self, "Sin conexión", "Inténtalo otra vez.")
            return
        cortes, _por_emp, monto = self._corte_datos
        if not cortes:
            self._mostrar_listo("Hoy todavía no hay ventas.", con_deshacer=False)
            return
        self._corte_texto.setText(f"VENTA DE HOY:\n\n${monto:,.2f}")
        self._btn_corte_ok.setEnabled(True)
        self._pila.setCurrentWidget(self._pg_corte)

    def _hacer_corte(self) -> None:
        """Guarda la cifra calculada (León no puede editarla) e imprime."""
        cortes, por_empleada, monto = self._corte_datos
        try:
            from datetime import date as _date

            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.libreta_service import guardar_corte

            with get_session() as session:
                guardar_corte(
                    session,
                    fecha=_date.today(),
                    monto_final=monto,
                    operaciones=sum(c.operaciones for c in cortes),
                    piezas=sum(c.piezas for c in cortes),
                    periodo_label="HOY",
                    creado_por="ENC-1",
                )
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo guardar el corte")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        try:
            from pos_uniformes.ui.helpers.libreta_corte_ticket_helper import (
                build_corte_ticket_text,
            )
            from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

            texto = build_corte_ticket_text(
                periodo_label="HOY",
                cortes=cortes,
                por_empleada=por_empleada,
                generado_por="ENC-1",
            )
            route_tickets(self, "Corte de Libreta", [texto])
        except Exception:  # noqa: BLE001 — guardado ya quedó; la impresión no lo tira
            logger.exception("Encargado: fallo la impresión del corte")
        self._mostrar_listo(f"✅ Corte hecho:\n\n${monto:,.2f}", con_deshacer=False)

    def _pagina_quien(self) -> QWidget:
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(12)
        ly.addWidget(self._titulo("¿De quién quieres apuntar algo?"))
        self._quien_botones = QVBoxLayout()
        self._quien_botones.setSpacing(12)
        ly.addLayout(self._quien_botones)
        ly.addStretch()
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_menu))
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

    def _pagina_que(self) -> QWidget:
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(12)
        self._que_titulo = self._titulo("")
        ly.addWidget(self._que_titulo)
        # Solo dos opciones: "sí trabajó" confundía a León — si algo sale
        # mal, para eso está "Me equivoqué"; lo fino lo ajusta Daniel.
        for texto, tipo in (
            ("🚫  Faltó", FALTA),
            ("🛌  Le doy descanso", DESCANSO),
        ):
            btn = QPushButton(texto)
            btn.setStyleSheet(self._BTN)
            btn.clicked.connect(lambda _=False, t=tipo: self._elegir_tipo(t))
            ly.addWidget(btn)
        ly.addStretch()
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(self._ir_a_quien)
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

    def _pagina_cuando(self) -> QWidget:
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(12)
        self._cuando_titulo = self._titulo("¿Qué día?")
        ly.addWidget(self._cuando_titulo)
        self._btn_hoy = QPushButton("")
        self._btn_hoy.setStyleSheet(self._BTN_ACENTO)
        self._btn_hoy.clicked.connect(lambda: self._aplicar(date.today()))
        ly.addWidget(self._btn_hoy)
        self._btn_manana = QPushButton("")
        self._btn_manana.setStyleSheet(self._BTN)
        self._btn_manana.clicked.connect(
            lambda: self._aplicar(date.today() + __import__("datetime").timedelta(days=1))
        )
        ly.addWidget(self._btn_manana)
        otro = QPushButton("📅  Otro día")
        otro.setStyleSheet(self._BTN)
        otro.clicked.connect(lambda: self._cal.setVisible(True))
        ly.addWidget(otro)
        self._cal = _CalendarioPintado()
        self._cal.setVisible(False)
        self._cal.clicked.connect(
            lambda q: self._aplicar(date(q.year(), q.month(), q.day()))
        )
        ly.addWidget(self._cal, 1)
        ly.addStretch()
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_que))
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

    def _pagina_listo(self) -> QWidget:
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(14)
        ly.addStretch()
        self._listo_texto = QLabel("")
        self._listo_texto.setWordWrap(True)
        self._listo_texto.setStyleSheet(
            "font-size: 28px; font-weight: 800; color: #2c2a27;"
        )
        ly.addWidget(self._listo_texto)
        ly.addStretch()
        listo = QPushButton("✅  Listo")
        listo.setStyleSheet(self._BTN_ACENTO)
        listo.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_menu))
        ly.addWidget(listo)
        self._btn_deshacer = QPushButton("❌  Me equivoqué (borrar)")
        self._btn_deshacer.setStyleSheet(self._BTN_SUAVE)
        self._btn_deshacer.clicked.connect(self._deshacer)
        ly.addWidget(self._btn_deshacer)
        pagina.setLayout(ly)
        return pagina

    def _mostrar_listo(self, texto: str, *, con_deshacer: bool) -> None:
        self._listo_texto.setText(texto)
        # Un corte no se "des-hace" con un botón: el deshacer es solo para
        # las marcas de falta/descanso recién apuntadas.
        self._btn_deshacer.setVisible(con_deshacer)
        self._pila.setCurrentWidget(self._pg_listo)

    # ── Flujo ────────────────────────────────────────────────────────────

    def _ir_a_quien(self) -> None:
        while self._quien_botones.count():
            item = self._quien_botones.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Empleada

            with get_session() as session:
                filas = (
                    session.query(Empleada)
                    .filter(Empleada.activo.is_(True))
                    .order_by(Empleada.nombre_completo)
                    .all()
                )
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo listar empleadas")
            filas = []
        if not filas:
            aviso = QLabel("No hay conexión.\nCierra e intenta otra vez.")
            aviso.setStyleSheet("font-size: 22px; font-weight: 700; color: #a33b25;")
            self._quien_botones.addWidget(aviso)
        for emp in filas:
            code = str(emp.codigo).upper()
            if code in ("VEND-1", "ENC-1"):
                continue  # Daniel y el propio León no se apuntan aquí
            nombre = (emp.nombre_completo or emp.codigo).split()[0]
            btn = QPushButton(f"👤  {nombre}")
            btn.setStyleSheet(self._BTN)
            btn.clicked.connect(
                lambda _=False, c=code, n=nombre: self._elegir_empleada(c, n)
            )
            self._quien_botones.addWidget(btn)
        self._pila.setCurrentWidget(self._pg_quien)

    def _elegir_empleada(self, code: str, nombre: str) -> None:
        self._sel_code, self._sel_nombre = code, nombre
        self._que_titulo.setText(f"¿Qué pasó con {nombre}?")
        self._pila.setCurrentWidget(self._pg_que)

    def _elegir_tipo(self, tipo: str) -> None:
        self._sel_tipo = tipo
        hoy = date.today()
        from datetime import timedelta

        self._btn_hoy.setText(f"Hoy ({_fecha_en_palabras(hoy)})")
        self._btn_manana.setText(f"Mañana ({_fecha_en_palabras(hoy + timedelta(days=1))})")
        self._cal.setVisible(False)
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.calendario_empleadas_service import cargar_horario

            with get_session() as session:
                self._cal.set_horario(cargar_horario(session, self._sel_code))
        except Exception:  # noqa: BLE001
            self._cal.set_horario(None)
        self._pila.setCurrentWidget(self._pg_cuando)

    def _aplicar(self, fecha: date) -> None:
        if not self._sel_code or not self._sel_tipo:
            return
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                marcar_dia(
                    session,
                    self._sel_code,
                    fecha,
                    self._sel_tipo,
                    nota="apuntado por León (ENC-1)",
                )
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo apuntar")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self._ultima_marca = (self._sel_code, fecha)
        verbo = {
            FALTA: "faltó",
            DESCANSO: "descansa",
            TRABAJO: "sí trabajó",
        }[self._sel_tipo]
        self._mostrar_listo(
            f"✅ Apuntado:\n\n{self._sel_nombre} {verbo} el {_fecha_en_palabras(fecha)}.",
            con_deshacer=True,
        )

    def _deshacer(self) -> None:
        if self._ultima_marca is None:
            self._ir_a_quien()
            return
        code, fecha = self._ultima_marca
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                quitar_marca(session, code, fecha)
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo deshacer")
            QMessageBox.warning(self, "No se borró", "Inténtalo otra vez.")
            return
        self._ultima_marca = None
        self._mostrar_listo("Borrado. Como si nada. 👍", con_deshacer=False)
