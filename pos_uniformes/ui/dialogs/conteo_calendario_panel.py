"""Panel embebible del calendario de conteos.

El mismo contenido (tabla de escuelas + estado + edición de frecuencia + accesos
a calendario visual y orden de impresión) se usa en dos lados: como página del
kiosko y dentro de `ConteoCalendarioDialog` (POS "Mas" y admin del satélite).

Datos de `conteo_calendario_service`; guardar con `guardar_config_conteo`.
`session_factory` inyectable para tests.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
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

_STYLES = (
    "#calTitulo { color: #7b2d14; font-size: 20px; font-weight: 800; background: transparent; }"
    "#calHint { color: #8a7a6a; background: transparent; }"
    "#calResumen { color: #5a4a3f; font-weight: 800; background: transparent; }"
    "QTableWidget { background: #fffdf8; border: 1px solid #e0d5c5; border-radius: 10px;"
    "  gridline-color: #efe6d8; alternate-background-color: #f8f0e6; }"
    "QTableWidget::item { padding: 6px 8px; color: #5a4a3f; }"
    "QHeaderView::section { background: #f3e7d6; color: #7b2d14; font-weight: 800;"
    "  border: none; padding: 8px; }"
)


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoCalendarioPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        show_title: bool = True,
        refresh_on_init: bool = True,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory or _default_session_factory
        self._spins: dict[int, QSpinBox] = {}
        self._build_ui(show_title)
        if refresh_on_init:
            self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, show_title: bool) -> None:
        self.setStyleSheet(_STYLES)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if show_title:
            titulo = QLabel("Calendario de conteos")
            titulo.setObjectName("calTitulo")
            layout.addWidget(titulo)

        hint = QLabel(
            "Frecuencia de conteo por escuela. Ajusta los días y pulsa «Guardar frecuencias»."
        )
        hint.setObjectName("calHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._resumen_label = QLabel("")
        self._resumen_label.setObjectName("calResumen")
        layout.addWidget(self._resumen_label)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Escuela", "Días vigencia", "Último conteo", "Próxima", "Estado"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(40)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(4, 172)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        save_btn = QPushButton("Guardar frecuencias")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._guardar)
        refresh_btn = QPushButton("Refrescar")
        refresh_btn.clicked.connect(self.refresh)
        calendario_btn = QPushButton("📅 Ver calendario")
        calendario_btn.clicked.connect(self._abrir_calendario_mes)
        orden_btn = QPushButton("🖨 Imprimir orden")
        orden_btn.clicked.connect(self._abrir_orden)
        actions.addWidget(save_btn)
        actions.addWidget(refresh_btn)
        actions.addWidget(calendario_btn)
        actions.addWidget(orden_btn)
        actions.addStretch()
        layout.addLayout(actions)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            session = self._session_factory()
            try:
                calendario = obtener_calendario_conteo(session)
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — sin conexión: mostrar vacío, no crashear
            self._spins = {}
            self._table.setRowCount(0)
            self._resumen_label.setText("Sin conexión con la base de datos.")
            return

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
            self._table.setCellWidget(fila, 4, self._estado_pill(e))

        self._resumen_label.setText(
            f"{len(calendario)} escuelas · {vencidas} requieren conteo"
        )

    def _abrir_calendario_mes(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_calendario_mes_dialog import (
            ConteoCalendarioMesDialog,
        )

        ConteoCalendarioMesDialog(self, session_factory=self._session_factory).exec()

    def _abrir_orden(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_orden_dialog import ConteoOrdenDialog

        ConteoOrdenDialog(self, session_factory=self._session_factory).exec()

    @staticmethod
    def _estado_texto(e) -> str:
        if e.nunca_contada:
            return "Nunca contada"
        if e.vencida:
            return f"Vencida (hace {abs(e.dias_para_vencer)}d)"
        return f"Al día ({e.dias_para_vencer}d)"

    def _estado_pill(self, e) -> QWidget:
        if e.nunca_contada or e.vencida:
            bg, fg = "#fbe3e0", "#b0341f"
        elif e.dias_para_vencer is not None and e.dias_para_vencer <= 7:
            bg, fg = "#fbeecb", "#a06a10"
        else:
            bg, fg = "#e3f0e0", "#2e7d32"
        lbl = QLabel(self._estado_texto(e))
        lbl.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 9px; padding: 3px 10px; font-weight: 700;"
        )
        cont = QWidget()
        h = QHBoxLayout(cont)
        h.setContentsMargins(6, 3, 6, 3)
        h.addWidget(lbl)
        h.addStretch()
        return cont

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
