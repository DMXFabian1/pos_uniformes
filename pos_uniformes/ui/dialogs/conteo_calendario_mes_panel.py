"""Calendario visual de conteos por mes — widget embebible.

Grid de mes con cada escuela en el día de su próximo conteo. Se usa como vista
principal de la página "Calendario" del kiosko y dentro de
`ConteoCalendarioMesDialog` (que lo abre el admin). `session_factory` inyectable.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _DiaCelda(QFrame):
    """Celda de día del calendario que emite `clicked` al pulsarla."""

    clicked = pyqtSignal()

    def mousePressEvent(self, ev) -> None:  # noqa: N802 (API de Qt)
        self.clicked.emit()
        super().mousePressEvent(ev)


class _ChipRecordatorio(QLabel):
    """Chip de recordatorio; emite `clicked` y NO propaga al día (para no abrir alta)."""

    clicked = pyqtSignal()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        self.clicked.emit()
        ev.accept()  # consume el clic: no llega a la celda del día
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

# Estilo moderno (Daniel, 2026-11-12: «misma temática moderna» que la caja):
# fondo crema, el mes en una tarjeta blanca con sombra, días sin bordes duros
# y hoy marcado en vino.
VINO = "#6b1f3a"
HOY = "#e8692f"
_STYLES = (
    "#mesNavBtn { background: #ffffff; border: 1px solid #ece2d6; border-radius: 20px;"
    "  color: #2c2118; font-size: 18px; font-weight: 800; }"
    "#mesNavBtn:hover { background: #f6eee4; }"
    "#mesNavBtn:pressed { background: #ecdfcf; }"
    "#mesHoyBtn { background: #ffffff; border: 1px solid #ece2d6; border-radius: 20px;"
    "  color: #2c2118; font-size: 14px; font-weight: 800; padding: 0 18px; min-height: 40px; }"
    "#mesHoyBtn:hover { background: #f6eee4; }"
    "#mesTitulo { color: #2c2118; font-size: 30px; font-weight: 900; background: transparent; }"
    "#mesTarjeta { background: #ffffff; border: 1px solid #efe6db; border-radius: 22px; }"
    "#mesGrid { background: #ffffff; }"
    "#diaCelda { background: #fbf8f4; border: 1.5px solid transparent; border-radius: 14px; }"
    "#diaCelda:hover { border: 1.5px solid #e0cdb8; background: #fffdfa; }"
    "#diaCelda[finde=\"true\"] { background: #eaf1fb; }"
    "#diaCelda[finde=\"true\"]:hover { background: #f1f6fd; border: 1.5px solid #bcd0ec; }"
    f"#diaCelda[hoy=\"true\"] {{ background: #fff3e8; border: 2px solid {HOY}; }}"
    "#diaPista { color: #a8957f; font-size: 11px; font-weight: 700; background: transparent; border: none; }"
    "#mesVencidas { background: #fdecec; color: #c0392b; font-weight: 700;"
    "  border: 1px solid #f0c0bd; border-radius: 10px; padding: 8px 12px; }"
    "#diaCabecera { color: #a8957f; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;"
    "  background: transparent; padding-bottom: 4px; }"
    "#mesResumen { border-radius: 16px; padding: 0 14px; min-height: 32px; font-weight: 800; font-size: 13px; }"
    "#mesLeyenda { color: #6b5a45; font-size: 13px; font-weight: 700; background: transparent; }"
)

# (fondo, texto, punto) de cada tipo de chip.
# Más alegre (Daniel, 2026-11-12): pasteles vivos y los emojis de siempre.
_COLOR_DESCANSO = ("#ebe3ff", "#5130a3", "🛌")
_COLOR_PAGO = ("#d9f5e3", "#1b7341", "💵")
_COLOR_FALTA = ("#ffe0db", "#b02a17", "❌")
_COLOR_NOTA = ("#f3eee7", "#6b5a45", "📝")
_COLOR_CONTEO = ("#ffe9cc", "#9a4a00", "📋")
_COLOR_VENCIDA = ("#ffd9d3", "#b02a17", "🔴")
_COLOR_PRONTO = ("#fff1bf", "#8a5a00", "🟡")
_EMOJI_MES = ["", "🎉", "💘", "🌱", "🌷", "🌼", "☀️", "🏖️", "🎒", "🇲🇽", "🎃", "🍂", "🎄"]


def _chip_qss(bg: str, fg: str) -> str:
    return (
        f"background: {bg}; color: {fg}; border: none; border-radius: 8px;"
        " padding: 3px 8px; font-size: 12px; font-weight: 700;"
    )


def _texto_chip(emoji: str, texto: str) -> str:
    return f"{emoji} {texto}"


def _sombra(widget) -> None:
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(30)
    efecto.setOffset(0, 4)
    efecto.setColor(QColor(90, 40, 30, 28))
    widget.setGraphicsEffect(efecto)


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
        # Si se inyecta `hoy` (tests) queda fijo; si no, refresh() lo actualiza a
        # la fecha real para que un kiosko 24/7 no quede con el "hoy" de ayer.
        self._hoy_fijo = hoy is not None
        self._hoy = hoy or date.today()
        self._anio = self._hoy.year
        self._mes = self._hoy.month
        self._estados: list = []
        self._recordatorios: list = []
        self._completados: set = set()  # (recordatorio_id, fecha) marcados como hechos
        self._emp_chips: dict = {}  # {fecha: [(tipo, nombre)]} sincronizado de la Libreta
        self._build_ui()
        if refresh_on_init:
            self.refresh()

    def _build_ui(self) -> None:
        self.setStyleSheet(_STYLES)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self._mes_label = QLabel("")
        self._mes_label.setObjectName("mesTitulo")
        nav.addWidget(self._mes_label)
        nav.addStretch()
        self._recordatorio_btn = QPushButton("➕ Recordatorio")
        self._recordatorio_btn.setObjectName("mesHoyBtn")
        self._recordatorio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recordatorio_btn.clicked.connect(self._abrir_recordatorios)
        # Recordatorios RETIRADOS del calendario (pedido de Daniel 2026-09-04):
        # los descansos/pagos ya llegan solos desde el calendario de la
        # Libreta y esto quedaba redundante. Para revivirlos: borrar esta
        # línea y el early-return de refresh()/_agregar_recordatorio_en.
        self._recordatorio_btn.setVisible(False)
        nav.addWidget(self._recordatorio_btn)
        prev_btn = QPushButton("‹")
        prev_btn.setObjectName("mesNavBtn")
        prev_btn.setFixedSize(40, 40)
        prev_btn.setToolTip("Mes anterior")
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(lambda: self._cambiar_mes(-1))
        nav.addWidget(prev_btn)
        self._hoy_btn = QPushButton("Hoy")
        self._hoy_btn.setObjectName("mesHoyBtn")
        self._hoy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hoy_btn.clicked.connect(self._ir_a_hoy)
        nav.addWidget(self._hoy_btn)
        next_btn = QPushButton("›")
        next_btn.setObjectName("mesNavBtn")
        next_btn.setFixedSize(40, 40)
        next_btn.setToolTip("Mes siguiente")
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(lambda: self._cambiar_mes(1))
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        # Banner de próximos recordatorios (oculto si no hay nada cercano).
        self._proximos_label = QLabel("")
        self._proximos_label.setWordWrap(True)
        self._proximos_label.setStyleSheet(
            "background: #eef4ff; color: #2b4a7a; border: 1px solid #c7d6ef;"
            " border-radius: 10px; padding: 8px 12px; font-weight: 600;"
        )
        self._proximos_label.setVisible(False)
        layout.addWidget(self._proximos_label)

        sumario = QHBoxLayout()
        sumario.setSpacing(8)
        self._chip_vencidas = QLabel("")
        self._chip_aldia = QLabel("")
        self._chip_mes = QLabel("")
        for c, (bg, fg, _p) in (
            (self._chip_vencidas, _COLOR_VENCIDA),
            (self._chip_aldia, _COLOR_PAGO),
            (self._chip_mes, ("#ffe9cc", "#9a4a00", "")),
        ):
            c.setObjectName("mesResumen")
            c.setStyleSheet(f"background: {bg}; color: {fg};")
            sumario.addWidget(c)
        sumario.addStretch()
        leyenda = QLabel(
            "   ".join(
                _texto_chip(punto, nombre)
                for nombre, (_b, _f, punto) in (
                    ("Descansa", _COLOR_DESCANSO), ("Día de pago", _COLOR_PAGO),
                    ("Faltó", _COLOR_FALTA), ("Conteo", _COLOR_CONTEO),
                )
            ) + "    🟦 Fin de semana"
        )
        leyenda.setObjectName("mesLeyenda")
        sumario.addWidget(leyenda)
        layout.addLayout(sumario)

        tarjeta = QFrame()
        tarjeta.setObjectName("mesTarjeta")
        _sombra(tarjeta)
        t_ly = QVBoxLayout(tarjeta)
        t_ly.setContentsMargins(16, 14, 16, 16)
        self._grid_host = QWidget()
        self._grid_host.setObjectName("mesGrid")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        # Columnas de ancho IGUAL (si no, la última se come todo el ancho).
        for c in range(7):
            self._grid.setColumnStretch(c, 1)
        t_ly.addWidget(self._grid_host)
        layout.addWidget(tarjeta, 1)

    def _ir_a_hoy(self) -> None:
        if (self._anio, self._mes) == (self._hoy.year, self._hoy.month):
            return
        self._anio, self._mes = self._hoy.year, self._hoy.month
        self._cambiar_mes(0)

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
        # Descansos, pagos y faltas se cargan POR MES: sin esto, al pasar a
        # octubre o a diciembre el calendario salía sin nada de las empleadas
        # (se quedaba con lo del mes en que se abrió). Daniel, 2026-11-05.
        try:
            session = self._session_factory()
            try:
                self._emp_chips = self._chips_de_empleadas(session)
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — sin conexión: el mes sale sin ellas
            self._emp_chips = {}
        self._render()

    def _chips_de_empleadas(self, session) -> dict:
        try:
            from pos_uniformes.services.calendario_empleadas_service import chips_calendario_mes

            return chips_calendario_mes(session, self._anio, self._mes, self._hoy)
        except Exception:  # noqa: BLE001
            return {}

    def refresh(self) -> None:
        if not self._hoy_fijo:
            self._hoy = date.today()  # kiosko 24/7: al refrescar, "hoy" es hoy
        try:
            session = self._session_factory()
            try:
                self._estados = obtener_calendario_conteo(session)
                # Recordatorios retirados de este calendario: no se cargan.
                self._recordatorios = []
                self._completados = set()
                # Sincronía con el calendario de la Libreta: descansos,
                # pagos y faltas de las empleadas se pintan aquí solos.
                self._emp_chips = self._chips_de_empleadas(session)
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — sin conexión: calendario vacío, no crashear
            self._estados = []
            self._recordatorios = []
            self._completados = set()
            self._emp_chips = {}
        self._render()

    def _abrir_recordatorios(self, fecha_inicial: date | None = None) -> None:
        from pos_uniformes.ui.dialogs.recordatorio_dialog import RecordatoriosDialog

        RecordatoriosDialog(
            self, session_factory=self._session_factory, fecha_inicial=fecha_inicial
        ).exec()
        self.refresh()

    def _agregar_recordatorio_en(self, fecha: date) -> None:
        """Clic en un día del calendario: detalle del día (2026-09-09).

        Quién descansa, a quién le toca pago, conteos, y consulta de pago
        con gafete (la empleada ve el suyo; dueño y encargado ven todos)."""
        from pos_uniformes.ui.dialogs.dia_calendario_dialog import DiaCalendarioDialog

        DiaCalendarioDialog(self, fecha, session_factory=self._session_factory, hoy=self._hoy).exec()

    def _render(self) -> None:
        self._mes_label.setText(f"{_EMOJI_MES[self._mes]}  {_MESES[self._mes]} {self._anio}")

        por_dia = agrupar_calendario_por_dia(self._estados, self._anio, self._mes)
        from pos_uniformes.services.recordatorio_service import (
            proximos_recordatorios,
            recordatorios_del_mes,
        )

        rec_por_dia = recordatorios_del_mes(self._recordatorios, self._anio, self._mes)
        vencidas = [e for e in self._estados if e.vencida]
        al_dia = [e for e in self._estados if not e.vencida]
        este_mes = sum(len(v) for v in por_dia.values())
        self._chip_vencidas.setText(f"🔴  {len(vencidas)} requieren conteo")
        self._chip_aldia.setText(f"🟢  {len(al_dia)} al día")
        self._chip_mes.setText(f"📅  {este_mes} conteos este mes")
        self._chip_vencidas.setVisible(bool(vencidas))
        self._render_banner_proximos(proximos_recordatorios(self._recordatorios, self._hoy, dias=7))

        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for r in range(8):
            self._grid.setRowStretch(r, 0)  # reset (meses varían de 4 a 6 semanas)

        for col, nombre in enumerate(_DIAS_SEMANA):
            cab = QLabel(nombre.upper())
            cab.setObjectName("diaCabecera")
            if col >= 5:
                cab.setStyleSheet("color: #4a6c9b;")
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(cab, 0, col)

        semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(self._anio, self._mes)
        for fila, semana in enumerate(semanas, start=1):
            self._grid.setRowStretch(fila, 1)  # semanas de alto igual, llenan el espacio
            for col, dia in enumerate(semana):
                if dia == 0:
                    self._grid.addWidget(self._celda_vacia(), fila, col)
                    continue
                self._grid.addWidget(
                    self._celda(dia, por_dia.get(dia, []), rec_por_dia.get(dia, []), col),
                    fila, col,
                )

    @staticmethod
    def _celda_vacia() -> QWidget:
        celda = QFrame()
        celda.setStyleSheet("QFrame { background: transparent; border: none; }")
        celda.setMinimumHeight(72)
        return celda

    def _celda(self, dia: int, escuelas: list, recordatorios: list | None = None, col: int = 0) -> QWidget:
        recordatorios = recordatorios or []
        celda = _DiaCelda()
        celda.setObjectName("diaCelda")
        # Todo día se puede tocar: abre el detalle (descansos, pagos, conteos).
        celda.setCursor(Qt.CursorShape.PointingHandCursor)
        fecha_celda = date(self._anio, self._mes, dia)
        celda.clicked.connect(lambda f=fecha_celda: self._agregar_recordatorio_en(f))
        es_hoy = fecha_celda == self._hoy
        es_finde = col >= 5
        emp_del_dia = getattr(self, "_emp_chips", {}).get(fecha_celda, [])
        celda.setProperty("hoy", "true" if es_hoy else "false")
        celda.setProperty("finde", "true" if es_finde else "false")
        celda.setProperty("ocupado", "true" if (escuelas or recordatorios or emp_del_dia) else "false")
        celda.setToolTip(f"Toca para ver el detalle del {dia}")
        celda.setMinimumHeight(84)
        v = QVBoxLayout(celda)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)
        num = QLabel(str(dia))
        if es_hoy:
            num.setFixedSize(28, 28)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(
                f"background: {HOY}; color: white; border-radius: 14px;"
                " font-weight: 900; font-size: 13px;"
            )
            num_row = QHBoxLayout()
            num_row.setContentsMargins(0, 0, 0, 0)
            num_row.addWidget(num)
            num_row.addStretch()
            v.addLayout(num_row)
        else:
            num.setStyleSheet(
                "font-weight: 800; font-size: 14px; background: transparent; border: none;"
                f" padding-left: 4px; color: {'#4a6c9b' if es_finde else '#5c4d40'};"
            )
            v.addWidget(num)
        # Recordatorios primero (pagos/descansos/notas), luego lo que viene
        # del calendario de la Libreta (descansos/pagos de empleadas) y al
        # final los conteos.
        chips = [
            self._chip_recordatorio(r, fecha_celda, (r.id, fecha_celda) in self._completados)
            for r in recordatorios
        ]
        chips += [
            self._chip_empleada(tipo, nombre)
            for tipo, nombre in getattr(self, "_emp_chips", {}).get(fecha_celda, [])
        ]
        chips += [self._chip(e) for e in escuelas]
        for w in chips[:3]:
            v.addWidget(w)
        if len(chips) > 3:
            mas = QLabel(f"+{len(chips) - 3} más · toca para ver")
            mas.setObjectName("diaPista")
            v.addWidget(mas)
        v.addStretch()
        return celda

    # Colores por tipo de recordatorio.
    _REC_COLORS = {
        "pago": ("#dcedff", "#1e4e8c"),
        "descanso": ("#e7dcff", "#5b3a99"),
        "falta": ("#f6d3cb", "#a33b25"),
        "nota": ("#eee7dc", "#6b5a45"),
    }

    def _chip_empleada(self, tipo: str, nombre: str) -> QLabel:
        """Chip auto-sincronizado desde el calendario de la Libreta."""
        bg, fg, punto = {"descanso": _COLOR_DESCANSO, "falta": _COLOR_FALTA}.get(tipo, _COLOR_PAGO)
        chip = QLabel(_texto_chip(punto, nombre))
        que = {"descanso": "Descansa", "falta": "Faltó"}.get(tipo, "Día de pago de")
        chip.setToolTip(f"{que} {nombre} (viene del calendario de la Libreta)")
        chip.setStyleSheet(_chip_qss(bg, fg))
        return chip

    def _chip_recordatorio(self, r, fecha, completado: bool) -> QLabel:
        from pos_uniformes.services.recordatorio_service import TIPO_ICONO

        texto = r.titulo if len(r.titulo) <= 13 else r.titulo[:12] + "…"
        chip = _ChipRecordatorio()
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        if completado:
            # Hecho/pagado: gris + tachado + ✓.
            chip.setText(f"✓ {texto}")
            chip.setToolTip(f"{r.titulo} — hecho (clic para desmarcar)")
            chip.setStyleSheet(
                "background: #e7e3dc; color: #9a9088; border: none; border-radius: 7px;"
                " padding: 2px 7px; font-size: 11px; font-weight: 700; text-decoration: line-through;"
            )
        else:
            bg, fg = self._REC_COLORS.get(r.tipo, ("#eee", "#444"))
            chip.setText(f"{TIPO_ICONO.get(r.tipo, '')} {texto}")
            chip.setToolTip(f"{r.titulo} (clic para marcar hecho)")
            chip.setStyleSheet(
                f"background: {bg}; color: {fg}; border: none; border-radius: 7px;"
                " padding: 2px 7px; font-size: 11px; font-weight: 700;"
            )
        chip.clicked.connect(lambda rid=r.id, f=fecha: self._toggle_completado(rid, f))
        return chip

    def _toggle_completado(self, recordatorio_id: int, fecha: date) -> None:
        """Marca/desmarca una ocurrencia como hecha (clic en su chip)."""
        from pos_uniformes.services.recordatorio_service import toggle_completado

        session = self._session_factory()
        try:
            nuevo = toggle_completado(session, recordatorio_id, fecha)
            session.commit()
        except Exception:  # noqa: BLE001 — no romper el calendario
            session.rollback()
            return
        finally:
            session.close()
        # Actualiza el set en memoria y re-pinta (sin re-consultar todo).
        if nuevo:
            self._completados.add((recordatorio_id, fecha))
        else:
            self._completados.discard((recordatorio_id, fecha))
        self._render()

    def _render_banner_proximos(self, proximos: list) -> None:
        """Banner con los recordatorios de los próximos días (o se oculta)."""
        if not proximos:
            self._proximos_label.setVisible(False)
            return
        from pos_uniformes.services.recordatorio_service import TIPO_ICONO

        partes = []
        for fecha, r in proximos[:5]:
            if fecha == self._hoy:
                cuando = "hoy"
            elif (fecha - self._hoy).days == 1:
                cuando = "mañana"
            else:
                cuando = f"en {(fecha - self._hoy).days} días"
            partes.append(f"{TIPO_ICONO.get(r.tipo, '')} {r.titulo} ({cuando})")
        extra = f"  +{len(proximos) - 5} más" if len(proximos) > 5 else ""
        self._proximos_label.setText("Próximos:  " + "   ·   ".join(partes) + extra)
        self._proximos_label.setVisible(True)

    @staticmethod
    def _chip(e) -> QLabel:
        if e.vencida:
            bg, fg, punto = _COLOR_VENCIDA
        elif e.dias_para_vencer is not None and e.dias_para_vencer <= 7:
            bg, fg, punto = _COLOR_PRONTO
        else:
            bg, fg, punto = _COLOR_CONTEO
        nombre = e.escuela_nombre
        texto = nombre if len(nombre) <= 15 else nombre[:14] + "…"
        chip = QLabel(_texto_chip(punto, texto))
        chip.setToolTip(nombre)
        chip.setStyleSheet(_chip_qss(bg, fg))
        return chip
