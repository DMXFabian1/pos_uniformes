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
        self.setStyleSheet(
            "QDialog { background: #faf6f0; }"
            "#ordTitulo { color: #7b2d14; font-size: 16px; font-weight: 800; background: transparent; }"
            "QListWidget { background: #fffdf8; border: 1px solid #e0d5c5; border-radius: 10px;"
            "  padding: 4px; outline: none; }"
            "QListWidget::item { border-radius: 8px; margin: 1px; }"
            "QListWidget::item:selected { background: #f3e2cf; }"
            "QListWidget::item:hover { background: #f7ede0; }"
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)
        self._hint = QLabel("Escuelas que ya requieren conteo:")
        self._hint.setObjectName("ordTitulo")
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
        self.resize(520, 460)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        session = self._session_factory()
        try:
            vencidas = escuelas_con_conteo_vencido(session)
        finally:
            session.close()

        self._list.clear()
        self._filas = []  # (nombre, detalle) — dato inspeccionable para tests
        for e in vencidas:
            if e.nunca_contada:
                detalle = "nunca contada"
            else:
                detalle = f"vencida hace {abs(e.dias_para_vencer)} días"
            self._filas.append((e.escuela_nombre, detalle))
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (e.escuela_id, e.escuela_nombre))
            self._list.addItem(item)
            row = self._build_row(e.escuela_nombre, detalle)
            item.setSizeHint(row.sizeHint())
            self._list.setItemWidget(item, row)

        hay = self._list.count() > 0
        self._print_btn.setEnabled(hay)
        if hay:
            self._hint.setText(f"{self._list.count()} escuela(s) requieren conteo. Elige una e imprime.")
            self._list.setCurrentRow(0)
        else:
            self._hint.setText("Ninguna escuela requiere conteo por ahora. ✓")

    @staticmethod
    def _build_row(nombre: str, detalle: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 7, 10, 7)
        name = QLabel(nombre)
        name.setStyleSheet(
            "color: #5a4a3f; font-weight: 600; font-size: 14px; background: transparent; border: none;"
        )
        h.addWidget(name)
        h.addStretch()
        chip = QLabel(detalle)
        chip.setStyleSheet(
            "background: #fbe3e0; color: #b0341f; border: none; border-radius: 8px;"
            " padding: 2px 9px; font-size: 12px; font-weight: 700;"
        )
        h.addWidget(chip)
        return row

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
