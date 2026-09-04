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
        self._recordatorio_btn = QPushButton("➕ Recordatorio")
        self._recordatorio_btn.setObjectName("mesNavBtn")
        self._recordatorio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recordatorio_btn.clicked.connect(self._abrir_recordatorios)
        # Recordatorios RETIRADOS del calendario (pedido de Daniel 2026-09-04):
        # los descansos/pagos ya llegan solos desde el calendario de la
        # Libreta y esto quedaba redundante. Para revivirlos: borrar esta
        # línea y el early-return de refresh()/_agregar_recordatorio_en.
        self._recordatorio_btn.setVisible(False)
        nav.addWidget(prev_btn)
        nav.addStretch()
        nav.addWidget(self._mes_label)
        nav.addStretch()
        nav.addWidget(self._recordatorio_btn)
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
        if not self._hoy_fijo:
            self._hoy = date.today()  # kiosko 24/7: al refrescar, "hoy" es hoy
        try:
            session = self._session_factory()
            try:
                self._estados = obtener_calendario_conteo(session)
                # Recordatorios retirados de este calendario: no se cargan.
                self._recordatorios = []
                self._completados = set()
                # Sincronía con el calendario de la Libreta: descansos y
                # pagos de las empleadas se pintan aquí solos (faltas no —
                # esas son del calendario privado).
                try:
                    from pos_uniformes.services.calendario_empleadas_service import (
                        chips_calendario_mes,
                    )

                    self._emp_chips = chips_calendario_mes(
                        session, self._anio, self._mes, self._hoy
                    )
                except Exception:  # noqa: BLE001
                    self._emp_chips = {}
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
        """Clic en un día del calendario: abre alta con esa fecha precargada."""
        return  # recordatorios retirados: el clic en el día ya no abre nada

    def _render(self) -> None:
        self._mes_label.setText(f"{_MESES[self._mes]} {self._anio}")

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
        self._chip_mes.setText(f"📅  {este_mes} este mes")
        self._render_banner_proximos(proximos_recordatorios(self._recordatorios, self._hoy, dias=7))

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
                self._grid.addWidget(
                    self._celda(dia, por_dia.get(dia, []), rec_por_dia.get(dia, []), col),
                    fila, col,
                )

    @staticmethod
    def _celda_vacia() -> QWidget:
        celda = QFrame()
        celda.setStyleSheet("QFrame { background: #f6f1e8; border: none; border-radius: 12px; }")
        celda.setMinimumHeight(72)
        return celda

    def _celda(self, dia: int, escuelas: list, recordatorios: list | None = None, col: int = 0) -> QWidget:
        recordatorios = recordatorios or []
        celda = _DiaCelda()
        # Sin recordatorios, el día ya no es clicable: cursor normal.
        fecha_celda = date(self._anio, self._mes, dia)
        celda.clicked.connect(lambda f=fecha_celda: self._agregar_recordatorio_en(f))
        es_hoy = fecha_celda == self._hoy
        es_finde = col >= 5
        if es_hoy:
            fondo, borde, grosor = "#fdf4ec", "#d1622f", "2px"
        elif escuelas or recordatorios:
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
            mas = QLabel(f"+{len(chips) - 3} más")
            mas.setStyleSheet("font-size: 11px; color: #8a7a6a; background: transparent; border: none;")
            v.addWidget(mas)
        v.addStretch()
        return celda

    # Colores por tipo de recordatorio.
    _REC_COLORS = {
        "pago": ("#dcedff", "#1e4e8c"),
        "descanso": ("#e7dcff", "#5b3a99"),
        "nota": ("#eee7dc", "#6b5a45"),
    }

    def _chip_empleada(self, tipo: str, nombre: str) -> QLabel:
        """Chip auto-sincronizado desde el calendario de la Libreta."""
        icono = "🛌" if tipo == "descanso" else "💵"
        bg, fg = self._REC_COLORS.get(tipo, ("#eee", "#444"))
        chip = QLabel(f"{icono} {nombre}")
        chip.setToolTip(
            f"{'Descansa' if tipo == 'descanso' else 'Día de pago de'} {nombre}"
            " (viene del calendario de la Libreta)"
        )
        chip.setStyleSheet(
            f"background: {bg}; color: {fg}; border: none; border-radius: 7px;"
            " padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
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
