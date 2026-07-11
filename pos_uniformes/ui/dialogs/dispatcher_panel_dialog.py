"""Panel del despachador del satélite (Fase 2): ver y controlar la cola.

Muestra los trabajos en una tabla, con filtros por estado/tipo y acciones:
reimprimir, reintentar, cancelar y reordenar (subir/bajar) los pendientes.
Se refresca solo cada pocos segundos y también cuando el despachador termina
un trabajo (si se le conecta a su `on_event`).

La lógica de datos va por `trabajo_queue_view_service` y `trabajos_service`; el
`session_factory` se inyecta para poder probar el panel sin una DB real.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajo_queue_view_service as view
from pos_uniformes.services import trabajos_service as svc

# (etiqueta visible, valor de filtro) — None = "Todos".
_ESTADO_FILTROS: list[tuple[str, EstadoTrabajo | None]] = [
    ("Todos", None),
    ("En espera", EstadoTrabajo.PENDIENTE),
    ("En proceso", EstadoTrabajo.EN_PROCESO),
    ("Hecho", EstadoTrabajo.HECHO),
    ("Error", EstadoTrabajo.ERROR),
    ("Cancelado", EstadoTrabajo.CANCELADO),
]
_TIPO_FILTROS: list[tuple[str, TipoTrabajo | None]] = [
    ("Todos", None),
    ("Ticket", TipoTrabajo.TICKET),
    ("Etiqueta", TipoTrabajo.ETIQUETA),
    ("Conteo", TipoTrabajo.CONTEO),
    ("Pedido", TipoTrabajo.PEDIDO),
]

_COLUMNAS = ["ID", "Tipo", "Estado", "Origen", "Detalle", "Mensaje"]


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class DispatcherPanelDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        auto_refresh_ms: int = 2500,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cola del satélite")
        self._session_factory = session_factory or _default_session_factory
        self._rows: list[view.RowView] = []

        self._build_ui()
        self.refresh()

        if auto_refresh_ms > 0:
            self._timer = QTimer(self)
            self._timer.setInterval(auto_refresh_ms)
            self._timer.timeout.connect(self.refresh)
            self._timer.start()

    # ── Construcción ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        self._summary = QLabel("")
        layout.addWidget(self._summary)

        filtros = QHBoxLayout()
        self._estado_combo = QComboBox()
        for etiqueta, _ in _ESTADO_FILTROS:
            self._estado_combo.addItem(etiqueta)
        self._estado_combo.currentIndexChanged.connect(self.refresh)
        self._tipo_combo = QComboBox()
        for etiqueta, _ in _TIPO_FILTROS:
            self._tipo_combo.addItem(etiqueta)
        self._tipo_combo.currentIndexChanged.connect(self.refresh)
        filtros.addWidget(QLabel("Estado:"))
        filtros.addWidget(self._estado_combo)
        filtros.addWidget(QLabel("Tipo:"))
        filtros.addWidget(self._tipo_combo)
        filtros.addStretch()
        refresh_btn = QPushButton("↻ Actualizar")
        refresh_btn.clicked.connect(self.refresh)
        filtros.addWidget(refresh_btn)
        layout.addLayout(filtros)

        self._table = QTableWidget(0, len(_COLUMNAS))
        self._table.setHorizontalHeaderLabels(_COLUMNAS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Detalle
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Mensaje
        self._table.itemSelectionChanged.connect(self._update_action_buttons)
        layout.addWidget(self._table)

        acciones = QHBoxLayout()
        self._btn_subir = QPushButton("↑ Subir")
        self._btn_subir.clicked.connect(lambda: self._mover(-1))
        self._btn_bajar = QPushButton("↓ Bajar")
        self._btn_bajar.clicked.connect(lambda: self._mover(1))
        self._btn_reimprimir = QPushButton("Reimprimir")
        self._btn_reimprimir.clicked.connect(self._reimprimir)
        self._btn_reintentar = QPushButton("Reintentar")
        self._btn_reintentar.clicked.connect(self._reintentar)
        self._btn_cancelar = QPushButton("Cancelar")
        self._btn_cancelar.clicked.connect(self._cancelar)
        for b in (
            self._btn_subir,
            self._btn_bajar,
            self._btn_reimprimir,
            self._btn_reintentar,
            self._btn_cancelar,
        ):
            acciones.addWidget(b)
        acciones.addStretch()
        layout.addLayout(acciones)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(760, 520)

    # ── Datos ────────────────────────────────────────────────────────────────

    def _filtros_actuales(self) -> tuple[list[EstadoTrabajo] | None, list[TipoTrabajo] | None]:
        _, estado = _ESTADO_FILTROS[self._estado_combo.currentIndex()]
        _, tipo = _TIPO_FILTROS[self._tipo_combo.currentIndex()]
        return ([estado] if estado else None), ([tipo] if tipo else None)

    def refresh(self) -> None:
        estados, tipos = self._filtros_actuales()
        seleccion = self._selected_row_id()
        session = self._session_factory()
        try:
            self._rows = view.listar_para_vista(session, estados=estados, tipos=tipos)
            conteo = view.contar_por_estado(session)
        finally:
            session.close()

        self._summary.setText(
            f"En espera: {conteo[EstadoTrabajo.PENDIENTE]}   ·   "
            f"En proceso: {conteo[EstadoTrabajo.EN_PROCESO]}   ·   "
            f"Hecho: {conteo[EstadoTrabajo.HECHO]}   ·   "
            f"Error: {conteo[EstadoTrabajo.ERROR]}   ·   "
            f"Cancelado: {conteo[EstadoTrabajo.CANCELADO]}"
        )

        self._table.setRowCount(len(self._rows))
        for fila, row in enumerate(self._rows):
            valores = [
                str(row.id),
                row.tipo_texto,
                row.estado_texto,
                row.origen,
                row.detalle,
                row.error_msg or "",
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.id)
                self._table.setItem(fila, col, item)

        if seleccion is not None:
            self._seleccionar_id(seleccion)
        self._update_action_buttons()

    # ── Selección y acciones ──────────────────────────────────────────────────

    def _selected_row_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        first = self._table.item(items[0].row(), 0)
        return None if first is None else int(first.text())

    def _selected_row_view(self) -> view.RowView | None:
        rid = self._selected_row_id()
        return next((r for r in self._rows if r.id == rid), None)

    def _seleccionar_id(self, trabajo_id: int) -> None:
        for fila in range(self._table.rowCount()):
            item = self._table.item(fila, 0)
            if item is not None and int(item.text()) == trabajo_id:
                self._table.selectRow(fila)
                return

    def _update_action_buttons(self) -> None:
        row = self._selected_row_view()
        self._btn_reimprimir.setEnabled(bool(row and row.puede_reimprimir))
        self._btn_reintentar.setEnabled(bool(row and row.puede_reintentar))
        self._btn_cancelar.setEnabled(bool(row and row.puede_cancelar))
        puede_mover = bool(row and row.estado == EstadoTrabajo.PENDIENTE)
        self._btn_subir.setEnabled(puede_mover)
        self._btn_bajar.setEnabled(puede_mover)

    def _accion(self, fn: Callable[[Session, int], object], trabajo_id: int) -> None:
        session = self._session_factory()
        try:
            fn(session, trabajo_id)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.warning(self, "No se pudo completar", str(exc))
        finally:
            session.close()
        self.refresh()

    def _reimprimir(self) -> None:
        rid = self._selected_row_id()
        if rid is not None:
            self._accion(svc.reimprimir, rid)

    def _reintentar(self) -> None:
        rid = self._selected_row_id()
        if rid is not None:
            self._accion(svc.reintentar, rid)

    def _cancelar(self) -> None:
        rid = self._selected_row_id()
        if rid is None:
            return
        if (
            QMessageBox.question(
                self, "Cancelar trabajo", f"¿Cancelar el trabajo #{rid}?"
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._accion(svc.cancelar, rid)

    def _mover(self, delta: int) -> None:
        """Sube/baja el pendiente seleccionado dentro del orden de pendientes."""
        rid = self._selected_row_id()
        if rid is None:
            return
        pendientes = [r.id for r in self._rows if r.estado == EstadoTrabajo.PENDIENTE]
        if rid not in pendientes:
            return
        i = pendientes.index(rid)
        j = i + delta
        if not (0 <= j < len(pendientes)):
            return
        pendientes[i], pendientes[j] = pendientes[j], pendientes[i]
        session = self._session_factory()
        try:
            svc.reordenar(session, pendientes)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.warning(self, "No se pudo reordenar", str(exc))
        finally:
            session.close()
        self.refresh()
        self._seleccionar_id(rid)
