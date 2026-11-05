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
from datetime import date, timedelta
from decimal import Decimal

from PyQt6.QtCore import QDate, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QTextCharFormat
from PyQt6.QtWidgets import (
    QFrame,
    QCalendarWidget,
    QComboBox,
    QDialog,
    QGridLayout,
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
    dias_para_pago,
    estado_del_dia,
    fecha_proximo_pago,
    guardar_horario,
    marcar_dia,
    proximo_descanso,
    quitar_marca,
    registrar_pago,
    resumen_empleada,
)

from pos_uniformes.services.nombres_empleadas_service import mostrar as _nombre_de
logger = logging.getLogger(__name__)

# Colores dark-mode-proof (mismos tonos crema/terracota del satélite).
_COLORES_DIA = {
    DESCANSO: ("#dce8f7", "#2b5c8a"),
    FALTA: ("#f6d3cb", "#a33b25"),
    PAGO: ("#d9ecd0", "#3d6b2f"),
    # Vacaciones: su propio color, para no confundirlas con descanso ni falta.
    "vacaciones": ("#efe2f7", "#6b3d8a"),
}


_ESTILO_DIALOGO = """
QDialog { background: #f4ede2; }
QLabel { color: #2c2a27; background: transparent; }
QWidget#calTarjeta { background: #fdfaf6; border: 1px solid #ddd0c0; border-radius: 16px; }
QLabel#calSeccion { color: #7b2d14; font-size: 12px; font-weight: 800; }
QLabel#calDiaTitulo { color: #2c2a27; font-size: 21px; font-weight: 800; }
QLabel#calDiaCuando { color: #a84f2d; background: #f7e3d8; border-radius: 9px; padding: 3px 9px;
                      font-size: 12px; font-weight: 800; }
QLabel#calOrigen { color: #5f564c; font-size: 13px; }
QLabel#calNota { color: #8a8177; font-size: 12px; }
QLabel#calFichaTitulo { color: #8a8177; font-size: 11px; font-weight: 800; }
QLabel#calFichaValor { color: #2c2a27; font-size: 17px; font-weight: 800; }
QLabel#calFichaPie { color: #8a8177; font-size: 11px; }
QWidget#calFicha { background: #fdfaf6; border: 1px solid #ddd0c0; border-radius: 14px; }
QWidget#calFichaFuerte { background: #a84f2d; border: none; border-radius: 14px; }
QWidget#calFichaFuerte QLabel#calFichaTitulo, QWidget#calFichaFuerte QLabel#calFichaPie { color: #f7e3d8; }
QWidget#calFichaFuerte QLabel#calFichaValor { color: #ffffff; font-size: 26px; }
QComboBox, QSpinBox { background: #ffffff; color: #2c2a27; border: 1.5px solid #ddd0c0; border-radius: 10px;
                      min-height: 38px; padding: 0 10px; font-size: 14px; font-weight: 600; }
QComboBox#calEmpleada { min-height: 46px; font-size: 16px; font-weight: 800; color: #73341c; }
QComboBox QAbstractItemView { background: #ffffff; color: #2c2a27; selection-background-color: #f7e3d8;
                              selection-color: #73341c; }
QPushButton { background: #ffffff; color: #2c2a27; border: 1.5px solid #ddd0c0; border-radius: 12px;
              min-height: 46px; padding: 0 14px; font-size: 14px; font-weight: 700; }
QPushButton:pressed { background: #f1e6d6; }
QPushButton:disabled { color: #b5aa9c; background: #f4eee4; border-color: #e6dccd; }
QPushButton#calFalta { border-left: 6px solid #c0533c; }
QPushButton#calDescanso { border-left: 6px solid #4d83b8; }
QPushButton#calTrabajo { border-left: 6px solid #8a8177; }
QPushButton#calPago { background: #3d6b2f; color: #ffffff; border: none; min-height: 54px; font-size: 16px; font-weight: 800; }
QPushButton#calPago:pressed { background: #325826; }
QPushButton#calPago:disabled { background: #c9d6c2; color: #f4f7f2; }
QPushButton#calPrimario { background: #a84f2d; color: #ffffff; border: none; font-weight: 800; }
QPushButton#calPrimario:disabled { background: #d9c7bb; color: #f8f2e9; }
QPushButton#calSuave { background: #f8f2e9; color: #73341c; border: 1px solid #ddd0c0; }
"""


class _CalendarioPintado(QCalendarWidget):
    """Calendario que pinta cada día según el horario de la empleada.

    Rediseñado el 2026-11-05: celdas redondeadas, HOY con un aro (antes solo
    iba subrayado y se perdía), el día elegido relleno, y la barra del mes sin
    los botones grises de fábrica."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.horario: HorarioEmpleada | None = None
        self.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setGridVisible(False)
        encabezado = QTextCharFormat()
        encabezado.setForeground(QColor("#8a8177"))
        encabezado.setFontWeight(QFont.Weight.Bold)
        self.setHeaderTextFormat(encabezado)
        for dia in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):   # sin el rojo de fábrica
            self.setWeekdayTextFormat(dia, encabezado)
        self.setStyleSheet(
            "QCalendarWidget QWidget { background: #fdfaf6; color: #2c2a27; alternate-background-color: #fdfaf6; }"
            "QCalendarWidget QWidget#qt_calendar_navigationbar { background: #fdfaf6; }"
            "QCalendarWidget QToolButton { color: #73341c; background: transparent; border: none;"
            "  border-radius: 10px; padding: 6px 12px; font-size: 17px; font-weight: 800; min-height: 30px; }"
            "QCalendarWidget QToolButton:hover { background: #f1e6d6; }"
            "QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }"
            "QCalendarWidget QSpinBox { min-height: 28px; font-size: 16px; font-weight: 800; color: #73341c; }"
            "QCalendarWidget QAbstractItemView { background: #fdfaf6; color: #2c2a27; font-size: 15px;"
            "  selection-background-color: transparent; selection-color: #2c2a27; outline: none; }"
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
        elegido = self.selectedDate() == qdate
        hoy = dia == date.today()
        caja = QRectF(rect).adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        fuente = QFont(painter.font())
        fuente.setBold(elegido or hoy or bool(colores and not fuera_de_mes))
        painter.setFont(fuente)
        if elegido:
            painter.setBrush(QColor("#a84f2d"))
            painter.drawRoundedRect(caja, 10, 10)
            tinta = QColor("#ffffff")
        elif colores and not fuera_de_mes:
            fondo, texto = colores
            painter.setBrush(QColor(fondo))
            painter.drawRoundedRect(caja, 10, 10)
            tinta = QColor(texto)
        elif fuera_de_mes:
            tinta = QColor("#c4bbae")
        else:
            tinta = QColor("#2c2a27")
        if hoy and not elegido:
            # HOY: un aro terracota. Subrayado se perdía entre los números.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#a84f2d"), 2))
            painter.drawRoundedRect(caja, 10, 10)
        painter.setPen(tinta)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))
        painter.restore()


SIEMPRE = "siempre"     # respuesta de `preguntar_desde_cuando`: corregir toda la historia


def texto_del_cambio(viejo: int | None, nuevo: int | None, desde: date) -> str:
    """«Hasta el domingo 8 de nov sigue descansando en sábado. Desde el lunes 9 de nov descansa en lunes.»"""
    def dia(w: int | None) -> str:
        return "sin descanso fijo" if w is None else f"descansando en {WEEKDAY_NAMES[w]}"

    def desde_txt(w: int | None) -> str:
        return "ya no tiene descanso fijo" if w is None else f"descansa en {WEEKDAY_NAMES[w]}"

    vispera = desde - timedelta(days=1)
    return (f"Hasta el {_fecha_corta(vispera)} sigue {dia(viejo)}.\n"
            f"Desde el {_fecha_corta(desde)} {desde_txt(nuevo)}.")


def lunes_siguiente(hoy: date) -> date:
    """El lunes de la semana que viene: un cambio de descanso se acomoda mejor
    con la semana entera que partiéndola a la mitad."""
    return hoy + timedelta(days=7 - hoy.weekday())


def preguntar_desde_cuando(
    parent: QWidget | None, *, nombre: str, viejo: int | None, nuevo: int | None,
    minimo: date | None = None, hoy: date | None = None,
):
    """¿Desde qué día vale el descanso nuevo? Devuelve la fecha, `SIEMPRE` si
    fue un error de captura (se corrige toda la historia) o None si canceló.

    Antes el cambio no preguntaba nada y repintaba el pasado: los sábados que
    Stayce sí descansó se habrían vuelto días trabajados (2026-11-05)."""
    from PyQt6.QtWidgets import QCheckBox, QDialogButtonBox

    hoy = hoy or date.today()
    propuesta = lunes_siguiente(hoy)
    if minimo is not None and propuesta < minimo:
        propuesta = minimo
    dlg = QDialog(parent)
    dlg.setWindowTitle("Cambiar el descanso fijo")
    dlg.setStyleSheet(_ESTILO_DIALOGO)
    dlg.resize(460, 560)
    ly = QVBoxLayout(dlg)
    ly.setContentsMargins(18, 16, 18, 16)
    ly.setSpacing(10)
    titulo = QLabel(f"¿Desde qué día cambia el descanso de {nombre}?")
    titulo.setObjectName("calDiaTitulo")
    titulo.setWordWrap(True)
    ly.addWidget(titulo)
    nota = QLabel("Los días de antes se quedan como estaban; solo cambia de ese día en adelante.")
    nota.setObjectName("calNota")
    nota.setWordWrap(True)
    ly.addWidget(nota)
    cal = _CalendarioPintado()
    if minimo is not None:
        cal.setMinimumDate(QDate(minimo.year, minimo.month, minimo.day))
    cal.setSelectedDate(QDate(propuesta.year, propuesta.month, propuesta.day))
    ly.addWidget(cal, 1)
    resumen = QLabel("")
    resumen.setObjectName("calOrigen")
    resumen.setWordWrap(True)
    resumen.setStyleSheet("font-size: 14px; font-weight: 700; color: #2c2a27;")
    ly.addWidget(resumen)
    error = QCheckBox("Fue un error de captura: siempre debió ser así (cambia también el pasado)")
    error.setStyleSheet("color: #5f564c; font-size: 12px;")
    ly.addWidget(error)

    def elegida() -> date:
        q = cal.selectedDate()
        return date(q.year(), q.month(), q.day())

    def pintar() -> None:
        cal.setEnabled(not error.isChecked())
        if error.isChecked():
            resumen.setText("Se cambia en toda su historia, como si siempre hubiera descansado así.")
        else:
            resumen.setText(texto_del_cambio(viejo, nuevo, elegida()))

    cal.selectionChanged.connect(pintar)
    error.toggled.connect(lambda _v: pintar())
    pintar()
    botones = QDialogButtonBox()
    aceptar = botones.addButton("Cambiar el descanso", QDialogButtonBox.ButtonRole.AcceptRole)
    aceptar.setObjectName("calPrimario")
    cancelar = botones.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
    cancelar.setObjectName("calSuave")
    botones.accepted.connect(dlg.accept)
    botones.rejected.connect(dlg.reject)
    ly.addWidget(botones)
    dlg.resumen = resumen          # para las pruebas
    dlg.calendario = cal
    dlg.error_de_captura = error
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return SIEMPRE if error.isChecked() else elegida()


def guardar_cambio_de_descanso(
    parent: QWidget | None, session_factory, *, code: str, nombre: str, viejo: int | None, nuevo: int | None,
    minimo: date | None, creado_por: str, **otros,
) -> bool:
    """Guarda el horario; si el descanso fijo cambió, primero pregunta desde
    cuándo. False si canceló o no se pudo. `otros` va tal cual a `guardar_horario`."""
    desde = None
    if viejo is not None and nuevo != viejo:
        respuesta = preguntar_desde_cuando(parent, nombre=nombre, viejo=viejo, nuevo=nuevo, minimo=minimo)
        if respuesta is None:
            return False
        desde = None if respuesta == SIEMPRE else respuesta
    try:
        with session_factory() as session:
            guardar_horario(session, code, descanso_weekday=nuevo, descanso_desde=desde, creado_por=creado_por, **otros)
        return True
    except ValueError as exc:
        QMessageBox.warning(parent, "Descanso fijo", str(exc))
        return False
    except Exception:  # noqa: BLE001
        logger.exception("Horario: no se pudo guardar")
        QMessageBox.warning(parent, "Sin conexión", "No se pudo guardar. Revisa la conexión.")
        return False


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
        # Encargado (ENC-1): marca faltas/descansos de cualquier empleada,
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
        self.resize(940, 660)
        is_owner = self._is_owner  # el resto del constructor decide con esto
        self.setStyleSheet(_ESTILO_DIALOGO)

        def seccion(texto: str) -> QLabel:
            etiqueta = QLabel(texto)
            etiqueta.setObjectName("calSeccion")
            return etiqueta

        def ficha(titulo: str, *, fuerte: bool = False) -> tuple[QWidget, QLabel, QLabel]:
            """Una ficha de dato: título chico, valor grande y un pie."""
            caja = QWidget()
            caja.setObjectName("calFichaFuerte" if fuerte else "calFicha")
            v = QVBoxLayout(caja)
            v.setContentsMargins(14, 9, 14, 9)
            v.setSpacing(1)
            t_ = QLabel(titulo)
            t_.setObjectName("calFichaTitulo")
            valor = QLabel("—")
            valor.setObjectName("calFichaValor")
            pie = QLabel("")
            pie.setObjectName("calFichaPie")
            for w in (t_, valor, pie):
                v.addWidget(w)
            return caja, valor, pie

        ly = QVBoxLayout()
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(12)

        # ── Arriba: de quién es el calendario, y sus tres datos ──
        cabecera = QHBoxLayout()
        cabecera.setSpacing(10)
        self._combo: QComboBox | None = None
        if self._gestiona:
            self._combo = QComboBox()
            self._combo.setObjectName("calEmpleada")
            self._combo.setMinimumWidth(250)
            cabecera.addWidget(self._combo, 0, Qt.AlignmentFlag.AlignVCenter)
        # `banner` sigue siendo la etiqueta de las comisiones (lo usa la Libreta).
        self._ficha_comisiones, self.banner, self._pie_comisiones = ficha("COMISIONES", fuerte=True)
        self._pie_comisiones.setText("desde el último pago")
        ficha_descanso, self._valor_descanso, self._pie_descanso = ficha("🛌 SIGUIENTE DESCANSO")
        ficha_pago, self._valor_pago, self._pie_pago = ficha("💵 PRÓXIMO PAGO")
        cabecera.addWidget(self._ficha_comisiones, 1)
        cabecera.addWidget(ficha_descanso, 1)
        cabecera.addWidget(ficha_pago, 1)
        ly.addLayout(cabecera)

        # La línea de siempre; se conserva para quien la lea, pero ya no se enseña:
        # lo que decía está en las fichas.
        self.resumen = QLabel("")
        self.resumen.setVisible(False)

        self.estado_conexion = QLabel(
            "Sin conexion con la PC principal: el calendario no esta disponible."
        )
        self.estado_conexion.setStyleSheet("color: #a33b25; font-weight: 700; font-size: 14px;")
        self.estado_conexion.setVisible(False)
        ly.addWidget(self.estado_conexion)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(12)

        # ── Izquierda: el mes ──
        tarjeta_cal = QWidget()
        tarjeta_cal.setObjectName("calTarjeta")
        v_cal = QVBoxLayout(tarjeta_cal)
        v_cal.setContentsMargins(12, 10, 12, 12)
        v_cal.setSpacing(8)
        self.cal = _CalendarioPintado()
        v_cal.addWidget(self.cal, 1)
        leyenda = QLabel(
            '<span style="background:#dce8f7; color:#2b5c8a;">&nbsp;Descanso&nbsp;</span>&nbsp; '
            '<span style="background:#f6d3cb; color:#a33b25;">&nbsp;Falta&nbsp;</span>&nbsp; '
            '<span style="background:#d9ecd0; color:#3d6b2f;">&nbsp;Pago&nbsp;</span>&nbsp; '
            '<span style="background:#efe2f7; color:#6b3d8a;">&nbsp;Vacaciones&nbsp;</span>&nbsp; '
            '<span style="color:#a84f2d;">◯</span> hoy'
        )
        leyenda.setStyleSheet("font-size: 12px; font-weight: 600;")
        v_cal.addWidget(leyenda)
        cuerpo.addWidget(tarjeta_cal, 5)

        # ── Derecha: el día elegido y lo que se puede hacer con él ──
        tarjeta_dia = QWidget()
        tarjeta_dia.setObjectName("calTarjeta")
        tarjeta_dia.setFixedWidth(372)
        v_dia = QVBoxLayout(tarjeta_dia)
        v_dia.setContentsMargins(16, 14, 16, 14)
        v_dia.setSpacing(8)
        v_dia.addWidget(seccion("DÍA ELEGIDO"))
        fila_dia = QHBoxLayout()
        fila_dia.setSpacing(8)
        # El día con todas sus letras: los botones de abajo actúan sobre ÉL. Antes
        # no se decía en ningún lado y «Le pagué este día» se fue a un domingo
        # que todavía no llegaba (2026-11-05).
        self.dia_titulo = QLabel("")
        self.dia_titulo.setObjectName("calDiaTitulo")
        self.dia_titulo.setWordWrap(True)
        fila_dia.addWidget(self.dia_titulo, 1)
        self.dia_cuando = QLabel("")
        self.dia_cuando.setObjectName("calDiaCuando")
        fila_dia.addWidget(self.dia_cuando, 0, Qt.AlignmentFlag.AlignTop)
        v_dia.addLayout(fila_dia)
        # De dónde salió lo de ese día (fijo, cambio, intercambio, vacaciones…).
        self.origen = QLabel("")
        self.origen.setObjectName("calOrigen")
        self.origen.setWordWrap(True)
        v_dia.addWidget(self.origen)
        self.cal.selectionChanged.connect(self._mostrar_origen)

        # ── Autoservicio de la empleada: pedir/cambiar SIN pasar por Daniel.
        # Las reglas (cupo 1 por día, 7 días de anticipación) deciden solas.
        if not self._gestiona:
            v_dia.addSpacing(6)
            v_dia.addWidget(seccion("TU DESCANSO"))
            self.btn_pedir = QPushButton("🙋 Pedir descanso este día")
            self.btn_pedir.setObjectName("calPrimario")
            self.btn_pedir.clicked.connect(self._pedir_descanso)
            v_dia.addWidget(self.btn_pedir)
            self.btn_cambiar = QPushButton("🔄 Cambiar con compañera")
            self.btn_cambiar.setObjectName("calSuave")
            self.btn_cambiar.clicked.connect(self._abrir_intercambio)
            v_dia.addWidget(self.btn_cambiar)

        # ── Marcar días: dueño Y encargado ──
        if self._gestiona:
            v_dia.addSpacing(6)
            v_dia.addWidget(seccion("ASISTENCIA DE ESE DÍA"))
            acciones = QGridLayout()
            acciones.setSpacing(8)
            self.btn_falta = QPushButton("Faltó")
            self.btn_falta.setObjectName("calFalta")
            self.btn_descanso = QPushButton("Descansó")
            self.btn_descanso.setObjectName("calDescanso")
            self.btn_trabajo = QPushButton("Sí trabajó")
            self.btn_trabajo.setObjectName("calTrabajo")
            self.btn_quitar = QPushButton("Quitar marca")
            self.btn_quitar.setObjectName("calSuave")
            for k, (btn, tipo) in enumerate((
                (self.btn_falta, FALTA),
                (self.btn_descanso, DESCANSO),
                (self.btn_trabajo, TRABAJO),
            )):
                btn.clicked.connect(lambda _=False, t=tipo: self._marcar(t))
                acciones.addWidget(btn, k // 2, k % 2)
            self.btn_quitar.clicked.connect(self._quitar)
            acciones.addWidget(self.btn_quitar, 1, 1)
            v_dia.addLayout(acciones)

        # ── Pagos y configuración: SOLO dueño ──
        if is_owner:
            v_dia.addSpacing(6)
            v_dia.addWidget(seccion("PAGO"))
            self.btn_pago = QPushButton("💵 Le pagué este día")
            self.btn_pago.setObjectName("calPago")
            self.btn_pago.clicked.connect(self._pagar)
            v_dia.addWidget(self.btn_pago)
            self.pago_nota = QLabel("")
            self.pago_nota.setObjectName("calNota")
            self.pago_nota.setWordWrap(True)
            v_dia.addWidget(self.pago_nota)
            # Un pago que se registró otro día (desde el bot, al día siguiente):
            # se corrige aquí sin deshacerlo (Stayce, 2026-10-20).
            self.btn_mover_pago = QPushButton("📅 Cambiar la fecha de un pago")
            self.btn_mover_pago.setObjectName("calSuave")
            self.btn_mover_pago.clicked.connect(self._mover_fecha_pago)
            v_dia.addWidget(self.btn_mover_pago)
        v_dia.addStretch(1)
        cuerpo.addWidget(tarjeta_dia)
        ly.addLayout(cuerpo, 1)

        # ── Abajo: el horario fijo (solo dueño) y cerrar ──
        pie = QHBoxLayout()
        pie.setSpacing(8)
        if is_owner:
            pie.addWidget(seccion("HORARIO FIJO"))
            pie.addWidget(QLabel("Descansa el"))
            self.combo_descanso = QComboBox()
            self.combo_descanso.addItem("Sin descanso fijo", None)
            for idx, nombre in enumerate(WEEKDAY_NAMES):
                self.combo_descanso.addItem(nombre.capitalize(), idx)
            pie.addWidget(self.combo_descanso)
            pie.addWidget(QLabel("y cobra cada"))
            self.spin_ciclo = QSpinBox()
            self.spin_ciclo.setRange(1, 31)
            self.spin_ciclo.setValue(7)  # semanal: cobran el mismo día cada semana
            self.spin_ciclo.setSuffix(" días")
            pie.addWidget(self.spin_ciclo)
            self.btn_guardar = QPushButton("Guardar horario")
            self.btn_guardar.setObjectName("calSuave")
            self.btn_guardar.clicked.connect(self._guardar_config)
            pie.addWidget(self.btn_guardar)
        pie.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("calSuave")
        cerrar.setMinimumWidth(120)
        cerrar.clicked.connect(self.accept)
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
            self._ficha_comisiones.setVisible(False)
            self.resumen.setText("")
            for etiqueta in (self._valor_descanso, self._valor_pago):
                etiqueta.setText("—")
            for etiqueta in (self._pie_descanso, self._pie_pago):
                etiqueta.setText("")
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
        self._ficha_comisiones.setVisible(not self._es_encargado)
        self.banner.setText(f"⭐ {comisiones}")
        self.banner.setToolTip(f"Comisiones desde el último pago: {comisiones}")
        hoy = date.today()
        self.resumen.setText(resumen_empleada(self._horario, hoy))
        descanso = proximo_descanso(self._horario, hoy)
        if descanso is None:
            self._valor_descanso.setText("Sin descanso fijo")
            self._pie_descanso.setText("")
        else:
            self._valor_descanso.setText(_fecha_corta(descanso).capitalize())
            self._pie_descanso.setText(_cuanto_falta(descanso, hoy))
        proximo = fecha_proximo_pago(self._horario, hoy)
        if proximo is None:
            self._valor_pago.setText("Sin ciclo de pago")
            self._pie_pago.setText("")
        else:
            faltan = dias_para_pago(self._horario, hoy) or 0
            self._valor_pago.setText("¡Hoy!" if proximo <= hoy or faltan == 0 else _fecha_corta(proximo).capitalize())
            self._pie_pago.setText("le toca cobrar" if proximo <= hoy or faltan == 0 else _cuanto_falta(proximo, hoy))
        self._habilitar_acciones(True)
        self._mostrar_origen()
        if self._is_owner:
            self.combo_descanso.setCurrentIndex(
                0
                if self._horario.descanso_weekday is None
                else self._horario.descanso_weekday + 1
            )
            self.spin_ciclo.setValue(self._horario.ciclo_dias_pago)
            desde = self._horario.descanso_desde
            self.combo_descanso.setToolTip(
                "" if desde is None else
                f"Desde el {_fecha_corta(desde)}. Antes descansaba en "
                f"{'ningún día fijo' if self._horario.descansos_anteriores[-1][1] is None else WEEKDAY_NAMES[self._horario.descansos_anteriores[-1][1]]}."
            )

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

    def _mostrar_origen(self) -> None:
        """El día elegido, dicho con todas sus letras, y lo que se puede hacer con él."""
        from pos_uniformes.services.calendario_empleadas_service import origen_del_dia

        fecha, hoy = self._fecha_seleccionada(), date.today()
        self.dia_titulo.setText(_fecha_en_palabras(fecha).capitalize())
        self.dia_cuando.setText("HOY" if fecha == hoy else _cuanto_falta(fecha, hoy).upper())
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                texto = origen_del_dia(session, self._codigo_activo(), fecha)
        except Exception:  # noqa: BLE001 — sin conexión no se dice nada
            texto = ""
        self.origen.setText(texto)
        self._acomodar_pago(fecha, hoy)

    def _acomodar_pago(self, fecha: date, hoy: date) -> None:
        """El botón de pago dice a QUÉ día se refiere, y no se ofrece en uno que
        todavía no llega ni en uno que ya tiene pago.

        El 5 de noviembre «Le pagué este día», con el domingo 8 elegido, registró
        el pago de la semana en curso y dejó las comisiones en cero: el botón no
        decía el día y nada lo impedía."""
        btn = getattr(self, "btn_pago", None)
        if btn is None:
            return
        btn.setText(f"💵 Le pagué el {_fecha_corta(fecha)}")
        ya_pagado = self._horario is not None and estado_del_dia(self._horario, fecha) == PAGO
        if fecha > hoy:
            btn.setEnabled(False)
            self.pago_nota.setText("Ese día todavía no llega. Si le pagas hoy por adelantado, elige el día de hoy.")
        elif ya_pagado:
            btn.setEnabled(False)
            self.pago_nota.setText("Ese día ya tiene un pago registrado.")
        else:
            btn.setEnabled(self._online)
            self.pago_nota.setText("Registra el pago en ese día y arranca el siguiente ciclo." if fecha == hoy
                                   else "Para apuntar un pago que se hizo ese día y no se registró.")

    def _marcar(self, tipo: str) -> None:
        fecha = self._fecha_seleccionada()
        if self._con_sesion(
            lambda s: marcar_dia(
                s, self._codigo_activo(), fecha, tipo, actor=self._code, origen="calendario"
            )
        ):
            self._recargar()

    def _quitar(self) -> None:
        fecha = self._fecha_seleccionada()
        if self._con_sesion(lambda s: quitar_marca(
            s, self._codigo_activo(), fecha, actor=self._code, origen="calendario"
        )):
            self._recargar()

    def _pagar(self) -> None:
        """Pago con monto calculado (1300 + 2/comisión − faltas) y desglose."""
        from pos_uniformes.ui.dialogs.corte_caja_dialog import confirmar_pago

        code = self._codigo_activo()
        nombre = self._combo.currentText() if self._combo is not None else code
        # La fecha seleccionada en el calendario: sirve para pagar adelantado
        # o para apuntar un pago que se hizo otro día y se olvidó registrar.
        pago = confirmar_pago(
            self, employee_code=code, employee_name=nombre, creado_por="VEND-1", fecha=self._fecha_seleccionada()
        )
        if pago is not None:
            self._recargar()

    def _mover_fecha_pago(self) -> None:
        """Elige uno de los últimos pagos de la empleada y le cambia el día."""
        from PyQt6.QtCore import QDate
        from PyQt6.QtWidgets import QCalendarWidget, QDialog, QDialogButtonBox, QListWidget, QVBoxLayout

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services import nomina_service as nom

        code = self._codigo_activo()
        try:
            with get_session() as session:
                pagos = nom.listar_pagos(
                    session, desde=date.today() - timedelta(days=60), hasta=date.today(), employee_code=code,
                )
                pagos = [(int(p.id), p.fecha, p.total) for p in pagos]
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: no se pudieron leer los pagos")
            QMessageBox.warning(self, "Sin conexión", "No se pudieron leer los pagos.")
            return
        if not pagos:
            QMessageBox.information(self, "Sin pagos", "No hay pagos de los últimos 60 días para esta persona.")
            return
        pagos.sort(key=lambda x: x[1], reverse=True)

        dlg = QDialog(self)
        dlg.setWindowTitle("Cambiar la fecha de un pago")
        dlg.setMinimumWidth(420)
        ly = QVBoxLayout(dlg)
        ly.addWidget(QLabel("¿Cuál pago?"))
        lista = QListWidget()
        for pid, fecha, total in pagos:
            lista.addItem(f"{WEEKDAY_NAMES[fecha.weekday()]} {fecha:%d/%m}  ·  ${total:,.2f}")
        lista.setCurrentRow(0)
        ly.addWidget(lista)
        ly.addWidget(QLabel("¿Qué día fue en realidad?"))
        cal = QCalendarWidget()
        cal.setMaximumDate(QDate.currentDate())
        sel = self._fecha_seleccionada()
        cal.setSelectedDate(QDate(sel.year, sel.month, sel.day))
        ly.addWidget(cal)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(dlg.accept)
        botones.rejected.connect(dlg.reject)
        ly.addWidget(botones)
        if dlg.exec() != QDialog.DialogCode.Accepted or lista.currentRow() < 0:
            return
        pago_id, fecha_vieja, _total = pagos[lista.currentRow()]
        nueva = cal.selectedDate().toPyDate()
        try:
            with get_session() as session:
                r = nom.mover_fecha_pago(session, pago_id, nueva, creado_por="VEND-1")
                session.commit()
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "No se pudo", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Calendario: no se pudo mover el pago")
            QMessageBox.warning(self, "Sin conexión", "No se pudo guardar. Revisa la conexión.")
            return
        extra = " Su siguiente pago también se recorrió." if r["ciclo_movido"] else ""
        from pos_uniformes.services.telegram_pagos_service import _ajuste_comisiones

        extra += _ajuste_comisiones(r)
        QMessageBox.information(
            self, "Pago movido",
            f"El pago de ${r['total']:,.2f} pasó del {fecha_vieja:%d/%m} al {nueva:%d/%m}.{extra}",
        )
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
                    session, horarios, self._code, fecha, hoy,
                    nombre=_nombre_de(self._code), origen="calendario",
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
            mio = combo_mio.currentData()
            for f in self._proximos_descansos(horarios[code_b], hoy):
                # D4: solo días de la misma semana que el mío.
                if mio is not None and f.isocalendar()[:2] != mio.isocalendar()[:2]:
                    continue
                combo_suyo.addItem(f.strftime("%A %d/%b"), f)

        combo_b.currentIndexChanged.connect(lambda _i: _rellenar_suyos())
        combo_mio.currentIndexChanged.connect(lambda _i: _rellenar_suyos())
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
                        session, horarios_frescos, self._code, fecha_a, code_b, fecha_b, hoy,
                        nombre_a=_nombre_de(self._code), nombre_b=_nombre_de(code_b),
                        origen="calendario",
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
        from pos_uniformes.database.connection import get_session

        h = self._horario
        if guardar_cambio_de_descanso(
            self, get_session,
            code=self._codigo_activo(),
            nombre=_nombre_de(self._codigo_activo(), corto=True),
            viejo=h.descanso_weekday if h is not None else None,
            nuevo=self.combo_descanso.currentData(),
            minimo=(h.descanso_desde + timedelta(days=1)) if (h is not None and h.descanso_desde) else None,
            creado_por=self._code,
            ciclo_dias_pago=int(self.spin_ciclo.value()),
        ):
            self._recargar()
        elif h is not None:
            # Canceló: el combo vuelve a decir lo que de verdad está guardado.
            self.combo_descanso.setCurrentIndex(0 if h.descanso_weekday is None else h.descanso_weekday + 1)


_MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _fecha_en_palabras(fecha: date) -> str:
    return f"{WEEKDAY_NAMES[fecha.weekday()]} {fecha.day} de {_MESES_ES[fecha.month - 1]}"


def _fecha_corta(fecha: date) -> str:
    """«domingo 8 de nov»: para un botón o una ficha."""
    return f"{WEEKDAY_NAMES[fecha.weekday()]} {fecha.day} de {_MESES_ES[fecha.month - 1][:3]}"


def _cuanto_falta(fecha: date, hoy: date) -> str:
    """«hoy», «mañana», «en 3 días», «ayer», «hace 4 días»."""
    dias = (fecha - hoy).days
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias == -1:
        return "ayer"
    return f"en {dias} días" if dias > 0 else f"hace {-dias} días"


class CalendarioEncargadoDialog(QDialog):
    """Modo ultra-simple para el encargado (ENC-1 — no le
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
        self._pg_corte = self._pagina_corte()
        self._pg_pagar = self._pagina_pagar()
        for p in (
            self._pg_menu,
            self._pg_quien,
            self._pg_que,
            self._pg_cuando,
            self._pg_listo,
            self._pg_cortes,
            self._pg_corte,
            self._pg_pagar,
        ):
            self._pila.addWidget(p)
        self._pila.setCurrentWidget(self._pg_menu)
        self._cargar_resumen_menu()

    # ── Páginas ──────────────────────────────────────────────────────────

    def _titulo(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 26px; font-weight: 800; color: #73341c;")
        return lbl

    def _pagina_menu(self) -> QWidget:
        """Pantalla de inicio del encargado: dos cosas, en grande."""
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(14)
        ly.addWidget(self._titulo("¿Qué quieres hacer?"))
        # Resumen del día del encargado en TARJETAS (rediseño 2026-09-09): quién
        # descansa hoy/mañana y a quién le toca pago, una línea por persona
        # en grande. Antes era un párrafo apretado (y con "Friday" en inglés).
        from PyQt6.QtWidgets import QHBoxLayout as _QH

        # Selector por nombre: QLabel hereda de QFrame y si no, los textos
        # de adentro también salían con recuadro.
        self._TARJETA = (
            "QFrame#tarjetaResumen { background: #ffffff; border: 2px solid #ddd0c0; border-radius: 14px; }"
            "QFrame#tarjetaResumen QLabel { border: none; background: transparent; }"
        )
        fila = _QH()
        fila.setSpacing(10)
        self._card_hoy, self._card_hoy_valor = self._tarjeta_resumen("🛌  HOY DESCANSA")
        self._card_man, self._card_man_valor = self._tarjeta_resumen("🛌  MAÑANA DESCANSA")
        fila.addWidget(self._card_hoy, 1)
        fila.addWidget(self._card_man, 1)
        ly.addLayout(fila)
        self._card_pagos = QFrame()
        self._card_pagos.setObjectName("tarjetaResumen")
        self._card_pagos.setStyleSheet(self._TARJETA)
        self._card_pagos_ly = QVBoxLayout(self._card_pagos)
        self._card_pagos_ly.setContentsMargins(14, 10, 14, 12)
        self._card_pagos_ly.setSpacing(4)
        ly.addWidget(self._card_pagos)
        # Línea chica: horario del corte / avisos de conexión.
        self._resumen_menu = QLabel("")
        self._resumen_menu.setWordWrap(True)
        self._resumen_menu.setStyleSheet("font-size: 14px; font-weight: 600; color: #8a7358;")
        ly.addWidget(self._resumen_menu)
        ly.addSpacing(4)
        # El corte es lo de todos los días: va primero y en terracota.
        btn_hacer = QPushButton("🧾  Hacer corte")
        btn_hacer.setStyleSheet(self._BTN_ACENTO)
        btn_hacer.clicked.connect(self._ir_a_corte_hoy)
        ly.addWidget(btn_hacer)
        btn_apuntar = QPushButton("🗓  Apuntar falta o descanso")
        btn_apuntar.setStyleSheet(self._BTN)
        btn_apuntar.clicked.connect(self._ir_a_quien)
        ly.addWidget(btn_apuntar)
        btn_retiro = QPushButton("💸  Saqué dinero del cajón")
        btn_retiro.setStyleSheet(self._BTN)
        btn_retiro.clicked.connect(self._apuntar_retiro)
        ly.addWidget(btn_retiro)
        btn_cortes = QPushButton("💵  Ver cortes")
        btn_cortes.setStyleSheet(self._BTN)
        btn_cortes.clicked.connect(self._ir_a_cortes)
        ly.addWidget(btn_cortes)
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

    def _pagina_corte(self) -> QWidget:
        """Previa del corte del encargado: venta, a quién pagar, cuánto se retira.
        Un solo botón; nada que contar ni capturar."""
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(14)
        ly.addWidget(self._titulo("Corte"))
        ly.addStretch()
        self._corte_texto = QLabel("")
        self._corte_texto.setWordWrap(True)
        self._corte_texto.setStyleSheet("font-size: 26px; font-weight: 800; color: #2c2a27;")
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

    def _ir_a_corte_hoy(self) -> None:
        """Muestra la previa (venta, pagos de hoy, retiro) antes de imprimir."""
        from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_previa_corte_encargado

        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.corte_caja_service import estado_caja, pagos_que_tocan_hoy

            with get_session() as session:
                estado = estado_caja(session)
                avisos = pagos_que_tocan_hoy(session)
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo calcular el corte")
            QMessageBox.warning(self, "Sin conexión", "Inténtalo otra vez.")
            return
        if not estado.resumen.operaciones and not avisos:
            self._mostrar_listo("Todavía no hay ventas desde el último corte.", con_deshacer=False)
            return
        self._corte_texto.setText(texto_previa_corte_encargado(estado, avisos))
        self._pila.setCurrentWidget(self._pg_corte)

    def _hacer_corte(self) -> None:
        """Guarda el corte con la cifra calculada, registra los pagos del día e imprime."""
        from pos_uniformes.ui.dialogs.corte_caja_dialog import hacer_corte_automatico

        resultado = hacer_corte_automatico(self, creado_por="ENC-1")
        if resultado is None:
            return
        auto, _texto = resultado
        lineas = [f"✅ Corte hecho:\n\nVenta ${Decimal(auto.estado.resumen.efectivo):,.2f}"]
        for p in auto.pagos:
            lineas.append(f"Pagar a {_nombre_de(p.employee_name or p.employee_code, corto=True)}: ${Decimal(p.total):,.2f}")
        retiro = Decimal(auto.corte.monto_final) - Decimal(auto.corte.reactivo_final)
        lineas.append(f"\nSe retira ${retiro:,.2f}")
        self._mostrar_listo("\n".join(lineas), con_deshacer=False)

    def _apuntar_retiro(self) -> None:
        """Proveedor, renta, cambio...: se descuenta solo en el corte."""
        from pos_uniformes.ui.dialogs.corte_caja_dialog import apuntar_retiro

        retiro = apuntar_retiro(self, creado_por="ENC-1", grande=True)
        if retiro is not None:
            self._mostrar_listo(
                f"✅ Apuntado:\n\n${Decimal(retiro.monto):,.2f} para {retiro.motivo}\n\nEl corte lo descuenta solo.",
                con_deshacer=False,
            )

    def _tarjeta_resumen(self, titulo: str):
        caja = QFrame()
        caja.setObjectName("tarjetaResumen")
        caja.setStyleSheet(self._TARJETA)
        cl = QVBoxLayout(caja)
        cl.setContentsMargins(14, 10, 14, 12)
        cl.setSpacing(2)
        t = QLabel(titulo)
        t.setStyleSheet("font-size: 12px; font-weight: 800; color: #a0876f; letter-spacing: 1px;")
        v = QLabel("—")
        v.setWordWrap(True)
        v.setStyleSheet("font-size: 22px; font-weight: 800; color: #2c2a27;")
        cl.addWidget(t)
        cl.addWidget(v)
        return caja, v

    @staticmethod
    def _nombre_pila(nombre: str) -> str:
        return (nombre or "").split()[0] if nombre else ""

    def _pintar_resumen_menu(self, resumen) -> None:
        """Tarjetas: descansos con nombre de pila; pagos una línea por persona."""
        from pos_uniformes.services.nomina_service import cuando_pago

        self._card_hoy_valor.setText(", ".join(self._nombre_pila(n) for n in resumen.descansan_hoy) or "nadie")
        self._card_man_valor.setText(", ".join(self._nombre_pila(n) for n in resumen.descansan_manana) or "nadie")
        while self._card_pagos_ly.count():
            w = self._card_pagos_ly.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        t = QLabel("💵  PAGOS")
        t.setStyleSheet("font-size: 12px; font-weight: 800; color: #a0876f; letter-spacing: 1px;")
        self._card_pagos_ly.addWidget(t)
        if not resumen.pagos:
            v = QLabel("Nadie cobra en los próximos 7 días.")
            v.setStyleSheet("font-size: 18px; font-weight: 700; color: #2c2a27;")
            self._card_pagos_ly.addWidget(v)
            return
        for a in resumen.pagos[:5]:
            cuando = cuando_pago(a)
            urgente = cuando == "HOY" or cuando.startswith("ATRASADO")
            fila = QLabel(f"{self._nombre_pila(a.employee_name)}  ·  <b>{cuando}</b>  ·  ${a.total_estimado:,.2f}")
            fila.setTextFormat(Qt.TextFormat.RichText)
            fila.setStyleSheet(
                "font-size: 19px; font-weight: 700; color: %s;" % ("#a84f2d" if urgente else "#2c2a27")
            )
            self._card_pagos_ly.addWidget(fila)
        if len(resumen.pagos) > 5:
            mas = QLabel(f"+{len(resumen.pagos) - 5} más")
            mas.setStyleSheet("font-size: 14px; color: #8a7358;")
            self._card_pagos_ly.addWidget(mas)

    def _cargar_resumen_menu(self) -> None:
        """Quién descansa hoy/mañana y pagos de la semana, en tarjetas."""
        texto = ""
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.nomina_service import ResumenEncargado, resumen_para_encargado

            with get_session() as session:
                try:
                    self._pintar_resumen_menu(resumen_para_encargado(session))
                except Exception:  # noqa: BLE001 — base sin migrar: no dejar la sesión rota
                    logger.exception("Encargado: no se pudo cargar el resumen")
                    session.rollback()
                    self._pintar_resumen_menu(ResumenEncargado([], [], []))
                    texto = "Sin conexión con la PC principal."
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: sin sesión para el resumen")
            texto = "Sin conexión con la PC principal."
        try:
            from datetime import date as _date

            from pos_uniformes.services.horario_tienda_service import hora_corte

            normal = hora_corte(_date(2026, 9, 7)).strftime("%H:%M")      # lunes
            temprano = hora_corte(_date(2026, 9, 10)).strftime("%H:%M")   # jueves
            # El corte por hora está apagado: Daniel lo ordena desde su celular
            # o el encargado lo hace con el botón. Nada de "se hace solo".
            texto = (texto + "  " if texto else "") + f"🧾 Hora del corte: {normal} (jueves y domingo {temprano})."
        except Exception:  # noqa: BLE001
            pass
        self._resumen_menu.setText(texto)

    def _ir_a_pagar(self) -> None:
        """Lista a las empleadas con lo que se les pagaría hoy; un toque paga."""
        while self._pagar_botones.count():
            item = self._pagar_botones.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.nomina_service import avisos_de_pago

            with get_session() as session:
                avisos = avisos_de_pago(session, dias=365)
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudieron cargar los pagos")
            QMessageBox.warning(self, "Sin conexión", "Inténtalo otra vez.")
            return
        if not avisos:
            self._mostrar_listo("No hay empleadas con horario configurado.", con_deshacer=False)
            return
        for a in avisos:
            if a.dias_para_pago is None:
                cuando = "sin fecha"
            elif a.dias_para_pago < 0:
                cuando = f"atrasado {-a.dias_para_pago} día(s)"
            elif a.dias_para_pago == 0:
                cuando = "HOY"
            else:
                cuando = f"en {a.dias_para_pago} día(s)"
            btn = QPushButton(f"{a.employee_name}\n{cuando} · ${a.total_estimado:,.2f}")
            btn.setStyleSheet(self._BTN)
            btn.clicked.connect(
                lambda _c=False, code=a.employee_code, nombre=a.employee_name: self._pagar_a(code, nombre)
            )
            self._pagar_botones.addWidget(btn)
        self._pila.setCurrentWidget(self._pg_pagar)

    def _pagar_a(self, code: str, nombre: str) -> None:
        from pos_uniformes.ui.dialogs.corte_caja_dialog import confirmar_pago

        pago = confirmar_pago(self, employee_code=code, employee_name=nombre, creado_por="ENC-1", grande=True)
        if pago is not None:
            self._mostrar_listo(
                f"✅ Pagado a {nombre}:\n\n${Decimal(pago.total):,.2f}\n\nSale del cajón; el corte lo descuenta solo.",
                con_deshacer=False,
            )

    def _pagina_pagar(self) -> QWidget:
        pagina = QWidget()
        ly = QVBoxLayout()
        ly.setSpacing(12)
        ly.addWidget(self._titulo("¿A quién le pagas?"))
        self._pagar_botones = QVBoxLayout()
        self._pagar_botones.setSpacing(10)
        ly.addLayout(self._pagar_botones)
        ly.addStretch()
        regresar = QPushButton("← Regresar")
        regresar.setStyleSheet(self._BTN_SUAVE)
        regresar.clicked.connect(lambda: self._pila.setCurrentWidget(self._pg_menu))
        ly.addWidget(regresar)
        pagina.setLayout(ly)
        return pagina

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
        # "Vino a trabajar" es para las que van por días (p.ej. Naye, fines
        # de semana): cuando ayuda un día extra se apunta y se le paga.
        for texto, tipo in (
            ("🚫  Faltó", FALTA),
            ("🛌  Le doy descanso", DESCANSO),
            ("✅  Vino a trabajar (día extra)", TRABAJO),
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
                continue  # el dueño y el propio encargado no se apuntan aquí
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
                    nota="apuntado por el encargado (ENC-1)",
                    actor="ENC-1", origen="calendario",
                )
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo apuntar")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self._ultima_marca = (self._sel_code, fecha)
        verbo = {
            FALTA: "faltó",
            DESCANSO: "descansa",
            TRABAJO: "vino a trabajar",
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
                quitar_marca(session, code, fecha, actor="ENC-1", origen="calendario")
        except Exception:  # noqa: BLE001
            logger.exception("Encargado: no se pudo deshacer")
            QMessageBox.warning(self, "No se borró", "Inténtalo otra vez.")
            return
        self._ultima_marca = None
        self._mostrar_listo("Borrado. Como si nada. 👍", con_deshacer=False)
