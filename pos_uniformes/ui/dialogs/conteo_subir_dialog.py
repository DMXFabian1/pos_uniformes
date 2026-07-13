"""Formulario para subir (registrar) el conteo físico de una escuela.

Qt-nativo, reusa el MISMO backend que el conteo del panel de uniformes:
`obtener_variantes_para_conteo` para traer las piezas y `registrar_conteos_lote`
para guardar (actualiza `ultimo_conteo_at` → reinicia el ciclo del calendario).

Solo admin (se abre desde el menú admin del satélite, Ctrl+Shift+A).
`session_factory` inyectable para tests.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
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
    ESCUELA_ID_BASICOS,
    NOMBRE_BASICOS,
    ConteoInput,
    obtener_variantes_agrupadas_por_producto,
    obtener_variantes_basicos_agrupadas,
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
        # Paleta del panel de uniformes (café/crema) para un look coherente.
        self.setStyleSheet(
            """
            QDialog { background: #f7f5f2; }
            QLabel { color: #1a1a1a; background: transparent; }
            QComboBox, QSpinBox {
                background: #ffffff; color: #1a1a1a;
                border: 1px solid #e5e5e5; border-radius: 6px; padding: 3px 6px;
            }
            QTableWidget {
                background: #ffffff; alternate-background-color: #faf7f3;
                color: #1a1a1a; border: 1px solid #e5e5e5; border-radius: 8px;
            }
            QTableWidget::item { padding: 4px 6px; }
            QHeaderView::section {
                background: #f5ebe0; color: #5c3019; font-weight: 600;
                border: none; padding: 7px 6px;
            }
            QPushButton {
                background: #ffffff; color: #87492c;
                border: 1px solid #e5d9cd; border-radius: 8px; padding: 6px 14px;
            }
            QPushButton:hover { background: #f5ebe0; }
            QPushButton#primaryButton {
                background: #87492c; color: #ffffff; border: none; font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #5c3019; }
            QPushButton#primaryButton:disabled { background: #d8ccc2; color: #f7f5f2; }
            """
        )

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
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Talla", "Color", "Sistema", "Físico"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setAlternatingRowColors(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
        # Entrada especial: productos básicos (sin escuela), al inicio.
        self._escuela_combo.addItem(f"— {NOMBRE_BASICOS} —", ESCUELA_ID_BASICOS)
        for e in escuelas:
            self._escuela_combo.addItem(e["escuela_nombre"], e["escuela_id"])

    def _cargar_piezas(self) -> None:
        escuela_id = self._escuela_combo.currentData()
        if escuela_id is None:
            return
        session = self._session_factory()
        try:
            if int(escuela_id) == ESCUELA_ID_BASICOS:
                grupos_raw = obtener_variantes_basicos_agrupadas(session)
            else:
                grupos_raw = obtener_variantes_agrupadas_por_producto(session, int(escuela_id))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudieron cargar las piezas:\n{exc}")
            return
        finally:
            session.close()

        self._variant_ids = []
        self._fisico_spins = []

        # Misma estructura que el panel de uniformes: se agrupa por producto y se
        # EXCLUYEN los productos virtuales (Pants 3pz, Chamarra) — esos no se
        # cuentan directo, se arman de sus componentes (Pants 2pz + playera).
        grupos: list[tuple[str, list]] = [
            (g["producto_nombre"], g["variantes"])
            for g in grupos_raw
            if not g.get("virtual", False) and g["variantes"]
        ]
        total_piezas = sum(len(items) for _, items in grupos)

        total_filas = sum(1 + len(items) for _, items in grupos)
        self._table.clearSpans()
        self._table.setRowCount(0)
        self._table.setRowCount(total_filas)

        fila = 0
        for producto, items in grupos:
            self._agregar_encabezado(fila, f"{producto}  ·  {len(items)} pzs")
            fila += 1
            for v in items:
                self._table.setItem(fila, 0, QTableWidgetItem(f"  {v.talla}"))
                self._table.setItem(fila, 1, QTableWidgetItem(v.color))
                sistema_item = QTableWidgetItem(str(v.stock_tienda))
                sistema_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(fila, 2, sistema_item)
                spin = QSpinBox()
                spin.setRange(0, 99999)
                spin.setValue(v.stock_tienda)  # default = sistema (sin diferencia)
                spin.valueChanged.connect(
                    lambda _val, f=fila, s=v.stock_tienda, sp=spin: (
                        self._resaltar_diferencia(f, s, sp)
                    )
                )
                self._table.setCellWidget(fila, 3, spin)
                self._variant_ids.append(v.variante_id)
                self._fisico_spins.append(spin)
                fila += 1

        hay = total_piezas > 0
        self._registrar_btn.setEnabled(hay)
        if hay:
            self._hint.setText(
                f"{total_piezas} piezas. Captura el «Físico» de cada una y pulsa «Registrar conteo»."
            )
        else:
            self._hint.setText("Esta escuela no tiene piezas para contar.")

    def _agregar_encabezado(self, fila: int, texto: str) -> None:
        """Fila-encabezado de un producto: negrita, con fondo, ocupa todo el ancho."""
        item = QTableWidgetItem(texto)
        fuente = QFont()
        fuente.setBold(True)
        item.setFont(fuente)
        item.setBackground(QBrush(QColor("#f5ebe0")))  # --brand-light
        item.setForeground(QBrush(QColor("#5c3019")))  # --brand-dark
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # no seleccionable
        self._table.setItem(fila, 0, item)
        self._table.setSpan(fila, 0, 1, self._table.columnCount())

    def _resaltar_diferencia(self, fila: int, sistema: int, spin: QSpinBox) -> None:
        """Colorea la fila según el físico capturado vs. el sistema.

        Rojo = hay MENOS de lo registrado (faltante); naranja = hay de más.
        """
        fisico = spin.value()
        if fisico < sistema:  # faltante: menos uniformes de los registrados
            fila_bg, spin_border, spin_txt = "#fef2f2", "#dc2626", "#b91c1c"
        elif fisico > sistema:  # sobrante
            fila_bg, spin_border, spin_txt = "#fff7ed", "#ea580c", "#c2410c"
        else:  # coincide
            fila_bg, spin_border, spin_txt = None, None, None

        for col in (0, 1, 2):
            item = self._table.item(fila, col)
            if item is None:
                continue
            item.setBackground(QBrush(QColor(fila_bg)) if fila_bg else QBrush())

        if spin_border:
            spin.setStyleSheet(
                f"QSpinBox {{ background: {fila_bg}; color: {spin_txt};"
                f" font-weight: 700; border: 1px solid {spin_border};"
                " border-radius: 6px; padding: 3px 6px; }"
            )
        else:
            spin.setStyleSheet("")

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
