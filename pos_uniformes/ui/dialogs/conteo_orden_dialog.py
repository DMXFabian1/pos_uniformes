"""Orden de conteo pendiente para el kiosko (Fase 2).

Lista las escuelas cuyo conteo está vencido y permite imprimir sus hojas de
conteo (que salen por el satélite vía `open_conteo_print_dialog`). Pensado para
que los trabajadores tengan siempre una orden de conteo lista.

`session_factory` y `print_sheets` se inyectan para poder probar el diálogo sin
DB ni impresión reales.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
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

from pos_uniformes.services.conteo_calendario_service import escuelas_con_conteo_vencido
from pos_uniformes.services.conteo_sheet_service import build_conteo_sheets


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoOrdenDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        print_sheets: Callable[[str, list[str]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Orden de conteo pendiente")
        self._session_factory = session_factory or _default_session_factory
        self._print_sheets = print_sheets or self._default_print_sheets
        self._build_ui()
        self.refresh()

    def _default_print_sheets(self, title: str, sheets: list[str]) -> None:
        from pos_uniformes.ui.dialogs.conteo_print_dialog import open_conteo_print_dialog

        open_conteo_print_dialog(self, title, sheets)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        self._hint = QLabel("Escuelas que ya requieren conteo:")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        actions = QHBoxLayout()
        self._print_btn = QPushButton("Imprimir hojas de conteo")
        self._print_btn.setObjectName("primaryButton")
        self._print_btn.clicked.connect(self._imprimir)
        actions.addWidget(self._print_btn)
        actions.addStretch()
        layout.addLayout(actions)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(460, 420)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        session = self._session_factory()
        try:
            vencidas = escuelas_con_conteo_vencido(session)
        finally:
            session.close()

        self._list.clear()
        for e in vencidas:
            if e.nunca_contada:
                detalle = "nunca contada"
            else:
                detalle = f"vencida hace {abs(e.dias_para_vencer)} días"
            item = QListWidgetItem(f"{e.escuela_nombre}  ·  {detalle}")
            item.setData(Qt.ItemDataRole.UserRole, (e.escuela_id, e.escuela_nombre))
            self._list.addItem(item)

        hay = self._list.count() > 0
        self._print_btn.setEnabled(hay)
        if hay:
            self._hint.setText(f"{self._list.count()} escuela(s) requieren conteo. Elige una e imprime.")
            self._list.setCurrentRow(0)
        else:
            self._hint.setText("Ninguna escuela requiere conteo por ahora. ✓")

    # ── Acción ────────────────────────────────────────────────────────────────

    def _imprimir(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        escuela_id, escuela_nombre = item.data(Qt.ItemDataRole.UserRole)

        session = self._session_factory()
        try:
            sheets = build_conteo_sheets(session, escuela_id, escuela_nombre)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudieron generar las hojas:\n{exc}")
            return
        finally:
            session.close()

        if not sheets:
            QMessageBox.information(
                self, "Sin hojas", f"{escuela_nombre} no tiene productos para contar."
            )
            return

        self._print_sheets(f"Conteo — {escuela_nombre}", sheets)
