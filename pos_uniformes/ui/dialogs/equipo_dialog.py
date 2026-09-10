"""Equipo (solo dueño): dar de baja por temporada y reactivar empleadas.

Libreta → 👥 Equipo. Lista activas e inactivas con su descanso, último pago
y último movimiento; un botón por fila cambia el estado. Nada se borra.
"""

from __future__ import annotations

import logging
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
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

logger = logging.getLogger(__name__)

COLUMNAS = ("Empleada", "Gafete", "Estado", "Horario", "Último pago", "Último movimiento", "", "")


def _fecha(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


class EquipoDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Equipo")
        self.resize(900, 520)
        self._fichas: list = []

        hint = QLabel(
            "Dar de baja no borra nada: su Libreta, pagos y calendario se quedan. Solo deja de "
            "aparecer en pendientes, pagos y ranking, y su gafete deja de entrar. Reactivar la regresa."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8177; font-size: 12px;")

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setObjectName("libretaTabla")
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #73341c; font-weight: 700;")
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addWidget(self.status, 1)
        pie.addWidget(cerrar)

        ly = QVBoxLayout()
        ly.setContentsMargins(16, 14, 16, 14)
        ly.addWidget(hint)
        ly.addWidget(self.tabla, 1)
        ly.addLayout(pie)
        self.setLayout(ly)
        self.recargar()

    def recargar(self) -> None:
        from pos_uniformes.services.equipo_service import listar_equipo

        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                self._fichas = listar_equipo(session)
        except Exception:  # noqa: BLE001
            logger.exception("Equipo: no se pudo cargar")
            self._fichas = []
            self.status.setText("Sin conexión con la PC principal.")
        self.pintar(self._fichas)

    def pintar(self, fichas: list) -> None:
        self._fichas = list(fichas)
        self.tabla.setRowCount(len(fichas))
        for i, f in enumerate(fichas):
            valores = (
                f.nombre,
                f.codigo,
                "Activa" if f.activa else "De baja",
                f.descanso,
                _fecha(f.ultimo_pago),
                _fecha(f.ultimo_movimiento),
            )
            for j, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                if j:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not f.activa:
                    item.setForeground(Qt.GlobalColor.gray)
                self.tabla.setItem(i, j, item)
            btn_h = QPushButton("✏️ Horario")
            btn_h.setObjectName("secondaryButton")
            btn_h.setAutoDefault(False)
            btn_h.clicked.connect(lambda _c=False, ficha=f: self._editar_horario(ficha))
            self.tabla.setCellWidget(i, len(COLUMNAS) - 2, btn_h)
            btn = QPushButton("⛔ Dar de baja" if f.activa else "✅ Reactivar")
            btn.setObjectName("secondaryButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(lambda _c=False, ficha=f: self._cambiar(ficha))
            self.tabla.setCellWidget(i, len(COLUMNAS) - 1, btn)

    def _editar_horario(self, ficha) -> None:
        if HorarioDialog(self, codigo=ficha.codigo, nombre=ficha.nombre).exec() == QDialog.DialogCode.Accepted:
            self.status.setText(f"Horario de {ficha.nombre.split()[0]} guardado.")
            self.recargar()

    def _cambiar(self, ficha) -> None:
        from pos_uniformes.services.equipo_service import cambiar_estado

        if ficha.activa:
            pregunta = f"¿Dar de baja a {ficha.nombre}?\n\nDeja de aparecer en pagos y pendientes y su gafete no entra. Se puede reactivar cuando regrese."
        else:
            pregunta = f"¿Reactivar a {ficha.nombre}?"
        if QMessageBox.question(self, "Equipo", pregunta, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                cambiar_estado(session, ficha.codigo, activa=not ficha.activa)
        except ValueError as exc:
            QMessageBox.warning(self, "Equipo", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Equipo: no se pudo cambiar el estado")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.status.setText(f"{ficha.nombre.split()[0]} {'dada de baja' if ficha.activa else 'reactivada'}.")
        self.recargar()


class HorarioDialog(QDialog):
    """Tipo de empleada y sus días.

    Semana completa: sueldo fijo, un día de descanso. Por días: solo ciertos
    días (p.ej. fines de semana), cobra por día trabajado al terminar sus
    días; si una semana viene más días, se le apuntan como "trabajó".
    """

    def __init__(self, parent: QWidget | None, *, codigo: str, nombre: str) -> None:
        super().__init__(parent)
        from PyQt6.QtCore import QDate
        from PyQt6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QFormLayout, QGroupBox

        from pos_uniformes.services.calendario_empleadas_service import (
            MODO_POR_DIA,
            MODO_SEMANA,
            WEEKDAY_NAMES,
            cargar_horario,
        )

        self._codigo = codigo
        self.setWindowTitle(f"Horario · {nombre}")
        self.setMinimumWidth(460)
        horario = None
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                horario = cargar_horario(session, codigo)
        except Exception:  # noqa: BLE001
            logger.exception("Horario: no se pudo cargar")

        self.modo = QComboBox()
        self.modo.addItem("Semana completa (sueldo fijo, un descanso)", MODO_SEMANA)
        self.modo.addItem("Por días (solo ciertos días, cobra por día)", MODO_POR_DIA)
        self.descanso = QComboBox()
        self.descanso.addItem("Sin descanso fijo", None)
        for idx, n in enumerate(WEEKDAY_NAMES):
            self.descanso.addItem(n.capitalize(), idx)
        self.dias_box = QGroupBox("Días que trabaja")
        dias_ly = QHBoxLayout()
        self.dias_checks = []
        for idx, n in enumerate(WEEKDAY_NAMES):
            cb = QCheckBox(n[:3].capitalize())
            self.dias_checks.append(cb)
            dias_ly.addWidget(cb)
        self.dias_box.setLayout(dias_ly)
        self.ultimo_pago = QDateEdit()
        self.ultimo_pago.setCalendarPopup(True)
        self.ultimo_pago.setDisplayFormat("dd/MM/yyyy")
        self.sin_pago = QCheckBox("Todavía no se le ha pagado (sin fecha)")

        if horario is not None:
            self.modo.setCurrentIndex(1 if horario.por_dia else 0)
            if horario.descanso_weekday is not None:
                self.descanso.setCurrentIndex(horario.descanso_weekday + 1)
            for d in horario.dias_trabajo:
                if 0 <= d <= 6:
                    self.dias_checks[d].setChecked(True)
            if horario.fecha_ultimo_pago:
                f = horario.fecha_ultimo_pago
                self.ultimo_pago.setDate(QDate(f.year, f.month, f.day))
            else:
                self.ultimo_pago.setDate(QDate.currentDate())
                self.sin_pago.setChecked(True)
        else:
            self.ultimo_pago.setDate(QDate.currentDate())
            self.sin_pago.setChecked(True)

        form = QFormLayout()
        form.addRow("Tipo:", self.modo)
        form.addRow("Descanso fijo:", self.descanso)
        form.addRow(self.dias_box)
        form.addRow("Último pago:", self.ultimo_pago)
        form.addRow("", self.sin_pago)
        hint = QLabel(
            "Por días: cobra sueldo/6 por cada día trabajado, al terminar sus días de la semana. "
            "Si una semana viene más días, apúntalos como 'trabajó' en su calendario (tú o el encargado)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8177; font-size: 12px;")

        botones = QHBoxLayout()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        ok = QPushButton("Guardar")
        ok.setObjectName("primaryButton")
        ok.clicked.connect(self._guardar)
        botones.addWidget(cancelar)
        botones.addWidget(ok, 1)

        ly = QVBoxLayout()
        ly.setContentsMargins(16, 14, 16, 14)
        ly.addLayout(form)
        ly.addWidget(hint)
        ly.addLayout(botones)
        self.setLayout(ly)
        self.modo.currentIndexChanged.connect(lambda _i: self._refrescar_modo())
        self.sin_pago.toggled.connect(lambda v: self.ultimo_pago.setEnabled(not v))
        self._refrescar_modo()
        self.ultimo_pago.setEnabled(not self.sin_pago.isChecked())

    def _refrescar_modo(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import MODO_POR_DIA

        por_dia = self.modo.currentData() == MODO_POR_DIA
        self.dias_box.setVisible(por_dia)
        self.descanso.setEnabled(not por_dia)

    def dias_marcados(self) -> list[int]:
        return [i for i, cb in enumerate(self.dias_checks) if cb.isChecked()]

    def _guardar(self) -> None:
        from datetime import date as _date

        from pos_uniformes.services.calendario_empleadas_service import MODO_POR_DIA, guardar_horario

        modo = self.modo.currentData()
        dias = self.dias_marcados()
        if modo == MODO_POR_DIA and not dias:
            QMessageBox.warning(self, "Horario", "Marca al menos un día que trabaje.")
            return
        q = self.ultimo_pago.date()
        fecha = None if self.sin_pago.isChecked() else _date(q.year(), q.month(), q.day())
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                guardar_horario(
                    session,
                    self._codigo,
                    descanso_weekday=self.descanso.currentData(),
                    ciclo_dias_pago=7,
                    modo_pago=modo,
                    dias_trabajo=dias,
                    fecha_ultimo_pago=fecha,
                    actualizar_ultimo_pago=True,
                )
        except Exception:  # noqa: BLE001
            logger.exception("Horario: no se pudo guardar")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.accept()
