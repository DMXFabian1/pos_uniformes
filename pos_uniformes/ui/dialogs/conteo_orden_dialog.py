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
    QCheckBox,
    QComboBox,
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

from pos_uniformes.services.conteo_calendario_service import obtener_calendario_conteo
from pos_uniformes.services.conteo_service import (
    ESCUELA_ID_BASICOS,
    obtener_variantes_basicos_agrupadas,
)
from pos_uniformes.services.conteo_sheet_service import (
    build_conteo_sheets,
    build_conteo_sheets_basicos,
)


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

        # Por defecto solo las pendientes; el checkbox agrega las que están al
        # día para poder adelantarse y contarlas antes de que venzan.
        self._mostrar_al_dia = QCheckBox("Mostrar también las que están al día")
        self._mostrar_al_dia.toggled.connect(self.refresh)
        layout.addWidget(self._mostrar_al_dia)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_seleccion_cambiada)
        layout.addWidget(self._list, 1)

        # Filtro de tipo de pieza — solo visible cuando se elige Productos básicos.
        self._tipo_row = QWidget()
        tipo_layout = QHBoxLayout(self._tipo_row)
        tipo_layout.setContentsMargins(2, 0, 2, 0)
        tipo_layout.addWidget(QLabel("Tipo de pieza:"))
        self._tipo_combo = QComboBox()
        self._tipo_combo.setMinimumWidth(200)
        tipo_layout.addWidget(self._tipo_combo)
        tipo_layout.addStretch()
        self._tipo_row.setVisible(False)
        layout.addWidget(self._tipo_row)

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
            estados = obtener_calendario_conteo(session)
        finally:
            session.close()

        mostrar_al_dia = self._mostrar_al_dia.isChecked()
        # obtener_calendario_conteo ya ordena por urgencia (vencidas primero).
        visibles = [e for e in estados if e.vencida or mostrar_al_dia]

        self._list.clear()
        self._filas = []  # (nombre, detalle) — dato inspeccionable para tests
        for e in visibles:
            detalle, vencida = self._detalle_de(e)
            self._filas.append((e.escuela_nombre, detalle))
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (e.escuela_id, e.escuela_nombre))
            self._list.addItem(item)
            row = self._build_row(
                e.escuela_nombre, detalle, vencida=vencida, dias_sin_contar=e.dias_sin_contar
            )
            item.setSizeHint(row.sizeHint())
            self._list.setItemWidget(item, row)

        n_vencidas = sum(1 for e in visibles if e.vencida)
        hay = self._list.count() > 0
        self._print_btn.setEnabled(hay)
        if not hay:
            self._hint.setText("No hay escuelas con conteo configurado.")
        elif mostrar_al_dia:
            self._hint.setText(
                f"{self._list.count()} escuela(s) — {n_vencidas} pendiente(s). "
                "Elige una e imprime (puedes adelantarte con las que están al día)."
            )
        elif n_vencidas:
            self._hint.setText(f"{n_vencidas} escuela(s) requieren conteo. Elige una e imprime.")
        else:
            self._hint.setText(
                "Ninguna escuela requiere conteo por ahora. ✓  "
                "Marca la casilla para adelantar las que están al día."
            )
        if hay:
            self._list.setCurrentRow(0)

    @staticmethod
    def _detalle_de(e) -> tuple[str, bool]:
        """(texto del chip, es_vencida) para una escuela según su estado."""
        if e.vencida:
            if e.nunca_contada:
                return "nunca contada", True
            return f"vencida hace {abs(e.dias_para_vencer)} días", True
        if e.dias_para_vencer == 0:
            return "vence hoy", False
        if e.dias_para_vencer == 1:
            return "en 1 día", False
        return f"en {e.dias_para_vencer} días", False

    @staticmethod
    def _build_row(
        nombre: str, detalle: str, *, vencida: bool = True, dias_sin_contar: int | None = None
    ) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 7, 10, 7)
        izq = QVBoxLayout()
        izq.setSpacing(1)
        name = QLabel(nombre)
        name.setStyleSheet(
            "color: #5a4a3f; font-weight: 600; font-size: 14px; background: transparent; border: none;"
        )
        izq.addWidget(name)
        # Días sin contarse (por entidad). "Nunca" ya lo dice el chip, así que solo
        # se muestra cuando hay un último conteo.
        if dias_sin_contar is not None:
            d = 1 if dias_sin_contar == 0 else dias_sin_contar
            dias_lbl = QLabel(f"{d} día sin contar" if d == 1 else f"{d} días sin contar")
            dias_lbl.setStyleSheet(
                "color: #9a8b7f; font-size: 11px; background: transparent; border: none;"
            )
            izq.addWidget(dias_lbl)
        h.addLayout(izq)
        h.addStretch()
        chip = QLabel(detalle)
        # Rojo = vencida (ya toca); verde = al día (puedes adelantarte).
        if vencida:
            chip_css = "background: #fbe3e0; color: #b0341f;"
        else:
            chip_css = "background: #dcfce7; color: #166534;"
        chip.setStyleSheet(
            chip_css + " border: none; border-radius: 8px;"
            " padding: 2px 9px; font-size: 12px; font-weight: 700;"
        )
        h.addWidget(chip)
        return row

    # ── Filtro de tipo (solo básicos) ──────────────────────────────────────────

    def _on_seleccion_cambiada(self, current, _previous=None) -> None:
        """Muestra el filtro de tipo de pieza solo para Productos básicos."""
        es_basicos = (
            current is not None
            and current.data(Qt.ItemDataRole.UserRole)[0] == ESCUELA_ID_BASICOS
        )
        self._tipo_row.setVisible(es_basicos)
        if es_basicos:
            self._poblar_tipos_basicos()

    def _poblar_tipos_basicos(self) -> None:
        session = self._session_factory()
        try:
            grupos = obtener_variantes_basicos_agrupadas(session)
        except Exception:  # noqa: BLE001
            grupos = []
        finally:
            session.close()
        tipos = sorted({
            g["tipo_pieza"] for g in grupos
            if not g.get("virtual", False) and g["tipo_pieza"]
        })
        self._tipo_combo.clear()
        self._tipo_combo.addItem("Todos", None)
        for t in tipos:
            self._tipo_combo.addItem(t, t)

    # ── Acción ────────────────────────────────────────────────────────────────

    def _imprimir(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        escuela_id, escuela_nombre = item.data(Qt.ItemDataRole.UserRole)
        tipo_basicos = (
            self._tipo_combo.currentData() if escuela_id == ESCUELA_ID_BASICOS else None
        )

        session = self._session_factory()
        try:
            if escuela_id == ESCUELA_ID_BASICOS:
                sheets = build_conteo_sheets_basicos(session, tipo_pieza=tipo_basicos)
            else:
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
