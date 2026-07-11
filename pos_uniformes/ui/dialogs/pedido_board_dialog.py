"""Tablero de pedidos del satélite (Fase 5), estilo cocina.

Tres columnas —Por preparar · Preparando · Listos— con los PEDIDO agrupados por
estado. Alguien en el satélite toma un pedido (pendiente→preparando) y luego lo
marca listo (preparando→hecho). Los pedidos NO se imprimen; el despachador los
ignora y aquí se atienden a mano.

Como el resto de la GUI de la cola: la lógica de datos va por
`trabajo_queue_view_service` / `trabajos_service` y el `session_factory` se
inyecta para poder probar el tablero sin una DB real.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services import trabajo_queue_view_service as view
from pos_uniformes.services import trabajos_service as svc

_COLUMNAS = [
    ("pendiente", "🕒  Por preparar"),
    ("preparando", "👐  Preparando"),
    ("listo", "✓  Listos"),
]


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class PedidoBoardDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        auto_refresh_ms: int = 3000,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tablero de pedidos")
        self._session_factory = session_factory or _default_session_factory
        self._rows_by_id: dict[int, view.RowView] = {}
        self._selected_id: int | None = None
        self._suppress_selection = False

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

        columnas = QHBoxLayout()
        self._listas: dict[str, QListWidget] = {}
        for clave, titulo in _COLUMNAS:
            col = QVBoxLayout()
            label = QLabel(titulo)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lista = QListWidget()
            lista.itemSelectionChanged.connect(
                lambda c=clave: self._on_seleccion(c)
            )
            self._listas[clave] = lista
            col.addWidget(label)
            col.addWidget(lista)
            columnas.addLayout(col)
        layout.addLayout(columnas)

        acciones = QHBoxLayout()
        self._btn_tomar = QPushButton("▶ Tomar")
        self._btn_tomar.clicked.connect(self._tomar)
        self._btn_listo = QPushButton("✓ Marcar listo")
        self._btn_listo.clicked.connect(self._marcar_listo)
        self._btn_cancelar = QPushButton("✕ Cancelar")
        self._btn_cancelar.clicked.connect(self._cancelar)
        for b in (self._btn_tomar, self._btn_listo, self._btn_cancelar):
            acciones.addWidget(b)
        acciones.addStretch()
        refresh_btn = QPushButton("↻ Actualizar")
        refresh_btn.clicked.connect(self.refresh)
        acciones.addWidget(refresh_btn)
        layout.addLayout(acciones)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(880, 520)

    # ── Datos ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        session = self._session_factory()
        try:
            columnas = view.pedidos_por_columna(session)
        finally:
            session.close()

        self._rows_by_id = {}
        self._suppress_selection = True
        for clave, _ in _COLUMNAS:
            lista = self._listas[clave]
            lista.clear()
            for row in columnas.get(clave, []):
                self._rows_by_id[row.id] = row
                texto = f"#{row.id}  ·  {row.detalle}"
                if row.origen:
                    texto += f"   ({row.origen})"
                item = QListWidgetItem(texto)
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                lista.addItem(item)
        self._suppress_selection = False

        if self._selected_id in self._rows_by_id:
            self._reseleccionar(self._selected_id)
        else:
            self._selected_id = None
        self._update_action_buttons()

    # ── Selección ─────────────────────────────────────────────────────────────

    def _on_seleccion(self, clave_activa: str) -> None:
        if self._suppress_selection:
            return
        lista = self._listas[clave_activa]
        items = lista.selectedItems()
        if not items:
            return
        # Selección única global: limpiar las otras columnas.
        self._suppress_selection = True
        for clave, otra in self._listas.items():
            if clave != clave_activa:
                otra.clearSelection()
        self._suppress_selection = False
        self._selected_id = int(items[0].data(Qt.ItemDataRole.UserRole))
        self._update_action_buttons()

    def _reseleccionar(self, trabajo_id: int) -> None:
        self._suppress_selection = True
        for lista in self._listas.values():
            for i in range(lista.count()):
                item = lista.item(i)
                if int(item.data(Qt.ItemDataRole.UserRole)) == trabajo_id:
                    item.setSelected(True)
                    self._suppress_selection = False
                    return
        self._suppress_selection = False

    def _selected_row(self) -> view.RowView | None:
        if self._selected_id is None:
            return None
        return self._rows_by_id.get(self._selected_id)

    def _update_action_buttons(self) -> None:
        row = self._selected_row()
        self._btn_tomar.setEnabled(bool(row and row.puede_tomar))
        self._btn_listo.setEnabled(bool(row and row.puede_marcar_listo))
        self._btn_cancelar.setEnabled(bool(row and row.puede_cancelar))

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _accion(self, fn: Callable[[Session, int], object]) -> None:
        if self._selected_id is None:
            return
        session = self._session_factory()
        try:
            fn(session, self._selected_id)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.warning(self, "No se pudo completar", str(exc))
        finally:
            session.close()
        self.refresh()

    def _tomar(self) -> None:
        self._accion(svc.tomar_pedido)

    def _marcar_listo(self) -> None:
        self._accion(svc.marcar_pedido_listo)

    def _cancelar(self) -> None:
        if self._selected_id is None:
            return
        if (
            QMessageBox.question(
                self, "Cancelar pedido", f"¿Cancelar el pedido #{self._selected_id}?"
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._accion(svc.cancelar)
