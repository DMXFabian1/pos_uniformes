"""Diálogo para administrar recordatorios del calendario (pagos/descansos/notas).

Lista los existentes (con opción de borrar) y un formulario para agregar uno
nuevo: tipo, título, recurrencia (fecha específica / cada mes / cada semana),
monto opcional y notas. `session_factory` inyectable para tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.recordatorio_service import (
    TIPO_ICONO,
    TIPO_LABEL,
    crear_recordatorio,
    eliminar_recordatorio,
    listar_recordatorios,
)

_DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class RecordatoriosDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recordatorios")
        self._session_factory = session_factory or _default_session_factory
        self._build_ui()
        self._refrescar_lista()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setStyleSheet(
            "QDialog { background: #faf6f0; }"
            "QLabel { color: #1a1a1a; background: transparent; }"
            "QLineEdit, QComboBox, QSpinBox, QDateEdit {"
            "  background: #ffffff; border: 1px solid #d8ccc2; border-radius: 6px; padding: 5px 7px; }"
            "QListWidget { background: #fffdf8; border: 1px solid #e0d5c5; border-radius: 10px; padding: 4px; }"
            "QPushButton#primaryButton { background: #87492c; color: white; border: none;"
            "  border-radius: 8px; padding: 7px 14px; font-weight: 700; }"
            "QPushButton#primaryButton:hover { background: #5c3019; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        titulo = QLabel("Recordatorios")
        titulo.setStyleSheet("font-size: 16px; font-weight: 800; color: #7b2d14;")
        layout.addWidget(titulo)

        self._lista = QListWidget()
        layout.addWidget(self._lista, 1)

        del_row = QHBoxLayout()
        self._del_btn = QPushButton("🗑  Borrar seleccionado")
        self._del_btn.clicked.connect(self._borrar_seleccionado)
        del_row.addWidget(self._del_btn)
        del_row.addStretch()
        layout.addLayout(del_row)

        # ── Formulario de alta ──
        alta = QLabel("Agregar recordatorio")
        alta.setStyleSheet("font-weight: 700; color: #5c3019; margin-top: 6px;")
        layout.addWidget(alta)

        form = QFormLayout()
        self._tipo_combo = QComboBox()
        for t in ("pago", "descanso", "nota"):
            self._tipo_combo.addItem(f"{TIPO_ICONO[t]}  {TIPO_LABEL[t]}", t)
        self._tipo_combo.currentIndexChanged.connect(self._actualizar_visibilidad)
        form.addRow("Tipo:", self._tipo_combo)

        self._titulo_edit = QLineEdit()
        self._titulo_edit.setPlaceholderText("Ej. Renta local, Descanso Juan, Nómina")
        form.addRow("Título:", self._titulo_edit)

        self._recurrencia_combo = QComboBox()
        self._recurrencia_combo.addItem("Fecha específica", "unica")
        self._recurrencia_combo.addItem("Cada mes (día fijo)", "mensual")
        self._recurrencia_combo.addItem("Cada semana", "semanal")
        self._recurrencia_combo.currentIndexChanged.connect(self._cambiar_recurrencia)
        form.addRow("Se repite:", self._recurrencia_combo)

        # Campo que cambia según la recurrencia.
        self._cuando_stack = QStackedWidget()
        self._fecha_edit = QDateEdit(QDate.currentDate())
        self._fecha_edit.setCalendarPopup(True)
        self._fecha_edit.setDisplayFormat("dd/MM/yyyy")
        # Ambos arrancan en HOY: si agregas un descanso/pago "hoy" y no cambias
        # nada, se agenda en el día de hoy (antes el semanal caía siempre en lunes).
        hoy = date.today()
        self._dia_mes_spin = QSpinBox()
        self._dia_mes_spin.setRange(1, 31)
        self._dia_mes_spin.setValue(hoy.day)
        self._dia_semana_combo = QComboBox()
        for i, d in enumerate(_DIAS_SEMANA):
            self._dia_semana_combo.addItem(d, i)
        self._dia_semana_combo.setCurrentIndex(hoy.weekday())  # 0=lun..6=dom
        self._cuando_stack.addWidget(self._fecha_edit)       # idx 0 = unica
        self._cuando_stack.addWidget(self._dia_mes_spin)     # idx 1 = mensual
        self._cuando_stack.addWidget(self._dia_semana_combo)  # idx 2 = semanal
        form.addRow("Cuándo:", self._cuando_stack)

        self._monto_edit = QLineEdit()
        self._monto_edit.setPlaceholderText("Opcional")
        self._monto_edit.setValidator(QDoubleValidator(0.0, 9_999_999.0, 2))
        self._monto_label = QLabel("Monto:")
        form.addRow(self._monto_label, self._monto_edit)

        self._notas_edit = QLineEdit()
        self._notas_edit.setPlaceholderText("Opcional")
        form.addRow("Notas:", self._notas_edit)
        layout.addLayout(form)

        self._agregar_btn = QPushButton("Agregar recordatorio")
        self._agregar_btn.setObjectName("primaryButton")
        self._agregar_btn.clicked.connect(self._agregar)
        layout.addWidget(self._agregar_btn)

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self.resize(460, 620)
        self._actualizar_visibilidad()

    def _cambiar_recurrencia(self) -> None:
        self._cuando_stack.setCurrentIndex(self._recurrencia_combo.currentIndex())

    def _actualizar_visibilidad(self) -> None:
        # El monto solo tiene sentido para pagos.
        es_pago = self._tipo_combo.currentData() == "pago"
        self._monto_label.setVisible(es_pago)
        self._monto_edit.setVisible(es_pago)

    # ── Datos ───────────────────────────────────────────────────────────────
    def _refrescar_lista(self) -> None:
        session = self._session_factory()
        try:
            recs = listar_recordatorios(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sin conexión", f"No se pudieron cargar:\n{exc}")
            return
        finally:
            session.close()
        self._lista.clear()
        for r in recs:
            item = QListWidgetItem(self._texto_recordatorio(r))
            item.setData(Qt.ItemDataRole.UserRole, r.id)
            self._lista.addItem(item)
        if not recs:
            self._lista.addItem(QListWidgetItem("— Sin recordatorios —"))

    @staticmethod
    def _texto_recordatorio(r) -> str:
        if r.recurrencia == "unica":
            cuando = r.fecha.strftime("%d/%m/%Y") if r.fecha else "—"
        elif r.recurrencia == "mensual":
            cuando = f"cada mes, día {r.dia_mes}"
        else:
            cuando = f"cada {_DIAS_SEMANA[r.dia_semana].lower()}" if r.dia_semana is not None else "cada semana"
        monto = f" · ${r.monto:,.2f}" if r.monto is not None else ""
        return f"{TIPO_ICONO.get(r.tipo, '')}  {r.titulo} · {cuando}{monto}"

    def _agregar(self) -> None:
        recurrencia = self._recurrencia_combo.currentData()
        tipo = self._tipo_combo.currentData()
        # El monto solo aplica a pagos: si el usuario lo escribió y luego cambió a
        # descanso/nota, el campo queda oculto pero con texto — se ignora.
        monto = self._monto_edit.text().strip() if tipo == "pago" else None
        kwargs = dict(
            tipo=tipo,
            titulo=self._titulo_edit.text(),
            recurrencia=recurrencia,
            monto=(monto or None),
            notas=self._notas_edit.text(),
        )
        if recurrencia == "unica":
            kwargs["fecha"] = self._fecha_edit.date().toPyDate()
        elif recurrencia == "mensual":
            kwargs["dia_mes"] = self._dia_mes_spin.value()
        else:
            kwargs["dia_semana"] = self._dia_semana_combo.currentData()

        session = self._session_factory()
        try:
            crear_recordatorio(session, **kwargs)
            session.commit()
        except ValueError as exc:
            QMessageBox.warning(self, "Faltan datos", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{exc}")
            return
        finally:
            session.close()
        self._titulo_edit.clear()
        self._monto_edit.clear()
        self._notas_edit.clear()
        self._refrescar_lista()

    def _borrar_seleccionado(self) -> None:
        item = self._lista.currentItem()
        if item is None:
            return
        rec_id = item.data(Qt.ItemDataRole.UserRole)
        if rec_id is None:
            return
        if QMessageBox.question(
            self, "Borrar", f"¿Borrar «{item.text()}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        session = self._session_factory()
        try:
            eliminar_recordatorio(session, int(rec_id))
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo borrar:\n{exc}")
            return
        finally:
            session.close()
        self._refrescar_lista()
