"""Formulario para subir (registrar) el conteo físico de una escuela.

Qt-nativo, reusa el MISMO backend que el conteo del panel de uniformes:
`obtener_variantes_para_conteo` para traer las piezas y `registrar_conteos_lote`
para guardar (actualiza `ultimo_conteo_at` → reinicia el ciclo del calendario).

Solo admin (se abre desde el menú admin del satélite, Ctrl+Shift+A).
`session_factory` inyectable para tests.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from pos_uniformes.services.catalog_school_link_service import list_all_schools
from pos_uniformes.services.conteo_service import (
    ConteoInput,
    obtener_variantes_para_conteo,
    registrar_conteos_lote,
)


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoSubirDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        contado_por: str = "admin (satélite)",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Subir conteo")
        self._session_factory = session_factory or _default_session_factory
        self._contado_por = contado_por
        self._variant_ids: list[int] = []
        self._fisico_spins: list[QSpinBox] = []
        self._build_ui()
        self._cargar_escuelas()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        top = QHBoxLayout()
        top.addWidget(QLabel("Escuela:"))
        self._escuela_combo = QComboBox()
        self._escuela_combo.setMinimumWidth(260)
        top.addWidget(self._escuela_combo, 1)
        self._cargar_btn = QPushButton("Cargar piezas")
        self._cargar_btn.clicked.connect(self._cargar_piezas)
        top.addWidget(self._cargar_btn)
        layout.addLayout(top)

        self._hint = QLabel("Elige una escuela y carga sus piezas para capturar el conteo.")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Producto", "Talla", "Color", "Sistema", "Físico"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._registrar_btn = QPushButton("Registrar conteo")
        self._registrar_btn.setObjectName("primaryButton")
        self._registrar_btn.setEnabled(False)
        self._registrar_btn.clicked.connect(self._registrar)
        actions.addWidget(self._registrar_btn)
        actions.addStretch()
        layout.addLayout(actions)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(680, 560)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _cargar_escuelas(self) -> None:
        session = self._session_factory()
        try:
            escuelas = list_all_schools(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sin conexión", f"No se pudieron cargar las escuelas:\n{exc}")
            return
        finally:
            session.close()
        self._escuela_combo.clear()
        for e in escuelas:
            self._escuela_combo.addItem(e["escuela_nombre"], e["escuela_id"])

    def _cargar_piezas(self) -> None:
        escuela_id = self._escuela_combo.currentData()
        if escuela_id is None:
            return
        session = self._session_factory()
        try:
            variantes = obtener_variantes_para_conteo(session, int(escuela_id))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudieron cargar las piezas:\n{exc}")
            return
        finally:
            session.close()

        self._variant_ids = []
        self._fisico_spins = []
        self._table.setRowCount(len(variantes))
        for fila, v in enumerate(variantes):
            self._table.setItem(fila, 0, QTableWidgetItem(v.producto_nombre))
            self._table.setItem(fila, 1, QTableWidgetItem(v.talla))
            self._table.setItem(fila, 2, QTableWidgetItem(v.color))
            self._table.setItem(fila, 3, QTableWidgetItem(str(v.stock_tienda)))
            spin = QSpinBox()
            spin.setRange(0, 99999)
            spin.setValue(v.stock_tienda)  # default = sistema (sin diferencia)
            self._table.setCellWidget(fila, 4, spin)
            self._variant_ids.append(v.variante_id)
            self._fisico_spins.append(spin)

        hay = len(variantes) > 0
        self._registrar_btn.setEnabled(hay)
        if hay:
            self._hint.setText(
                f"{len(variantes)} piezas. Captura el «Físico» de cada una y pulsa «Registrar conteo»."
            )
        else:
            self._hint.setText("Esta escuela no tiene piezas para contar.")

    def _registrar(self) -> None:
        conteos = [
            ConteoInput(variante_id=vid, stock_fisico=spin.value())
            for vid, spin in zip(self._variant_ids, self._fisico_spins)
        ]
        if not conteos:
            return
        session = self._session_factory()
        try:
            resultado = registrar_conteos_lote(session, conteos, self._contado_por)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo registrar el conteo:\n{exc}")
            return
        finally:
            session.close()
        QMessageBox.information(
            self,
            "Conteo registrado",
            f"Se registraron {resultado.total_contados} piezas "
            f"({resultado.con_diferencia} con diferencia). El calendario se actualizó.",
        )
        self.accept()
