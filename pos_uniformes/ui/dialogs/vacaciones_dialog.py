"""Mis vacaciones (Libreta del kiosko): saldo, periodos, solicitudes y pedir.

Solo pinta y llama a `vacaciones_service`: ninguna regla vive aquí. Se abre
con el gafete de la empleada; las respuestas de Daniel que todavía no había
visto se marcan vistas al cerrar.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QHeaderView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

_ESTADOS = {
    "pedido": "⏳ esperando a Daniel",
    "aprobado": "✅ aprobadas",
    "rechazado": "✖️ no aprobadas",
    "cancelado": "↩️ canceladas",
    "vencido": "⌛ vencidas sin respuesta",
    "revocado": "↩️ deshechas",
}


def _d(f: date) -> str:
    return f"{f:%d/%m/%Y}"


class VacacionesDialog(QDialog):
    def __init__(self, parent, *, employee_code: str, nombre: str, session_factory) -> None:
        super().__init__(parent)
        self._code = str(employee_code).strip().upper()
        self._nombre = nombre
        self._session_factory = session_factory
        self._sin_ver: list[int] = []
        self.setWindowTitle("Mis vacaciones")
        self.setMinimumWidth(560)
        self.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; background: transparent; }"
        )
        ly = QVBoxLayout(self)
        ly.setContentsMargins(20, 18, 20, 16)
        ly.setSpacing(8)
        titulo = QLabel("🏖️ Mis vacaciones")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(titulo)
        self.resumen = QLabel("")
        self.resumen.setWordWrap(True)
        self.resumen.setStyleSheet("font-size: 14px;")
        ly.addWidget(self.resumen)
        self.respuestas = QLabel("")
        self.respuestas.setWordWrap(True)
        self.respuestas.setStyleSheet(
            "font-size: 13px; font-weight: 600; background: #fbf3e4;"
            "border: 1px solid #e3c99a; border-radius: 8px; padding: 6px 10px;"
        )
        ly.addWidget(self.respuestas)

        self.periodos = QTableWidget(0, 5)
        self.periodos.setHorizontalHeaderLabels(["Año", "Le tocan", "Apartados", "Disfrutados", "Disponibles"])
        self.periodos.verticalHeader().setVisible(False)
        self.periodos.setMaximumHeight(130)
        self.periodos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ly.addWidget(self.periodos)

        self.solicitudes = QTableWidget(0, 3)
        self.solicitudes.setHorizontalHeaderLabels(["Fechas", "Días", "Estado"])
        self.solicitudes.verticalHeader().setVisible(False)
        self.solicitudes.setMaximumHeight(150)
        cab = self.solicitudes.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        ly.addWidget(self.solicitudes)

        pedir = QLabel("Pedir vacaciones (Daniel las aprueba desde su celular):")
        pedir.setStyleSheet("font-weight: 700; margin-top: 6px;")
        ly.addWidget(pedir)
        fila = QHBoxLayout()
        hoy = date.today()
        self.desde = QDateEdit(QDate(hoy.year, hoy.month, hoy.day))
        self.hasta = QDateEdit(QDate(hoy.year, hoy.month, hoy.day))
        for w in (self.desde, self.hasta):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
            w.setMinimumDate(QDate(hoy.year, hoy.month, hoy.day))
            w.dateChanged.connect(lambda _d: self._contar())
        fila.addWidget(QLabel("Del"))
        fila.addWidget(self.desde)
        fila.addWidget(QLabel("al"))
        fila.addWidget(self.hasta)
        ly.addLayout(fila)
        self.cuenta = QLabel("")
        self.cuenta.setWordWrap(True)
        self.cuenta.setStyleSheet("font-size: 12px; color: #8a8177;")
        ly.addWidget(self.cuenta)
        self.nota = QLineEdit()
        self.nota.setPlaceholderText("Nota para Daniel (opcional)")
        ly.addWidget(self.nota)

        botones = QHBoxLayout()
        self.btn_cancelar = QPushButton("Retirar mi solicitud pendiente")
        self.btn_cancelar.clicked.connect(self._retirar)
        botones.addWidget(self.btn_cancelar)
        self.btn_pedir = QPushButton("Pedir estas vacaciones")
        self.btn_pedir.setStyleSheet(
            "QPushButton { background: #a84f2d; color: #ffffff; font-weight: 700;"
            "  border-radius: 10px; min-height: 40px; }"
            "QPushButton:disabled { background: #d8cbbb; color: #8a8177; }"
        )
        self.btn_pedir.clicked.connect(self._pedir)
        botones.addWidget(self.btn_pedir, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        ly.addLayout(botones)
        self.recargar()

    # ── datos ──
    def recargar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        try:
            with self._session_factory() as session:
                e = vs.expediente(session, self._code)
                sin_ver = vs.respuestas_sin_ver(session, self._code)
                textos = [vs.texto_de_respuesta(s) for s in sin_ver]
                self._sin_ver = [s.id for s in sin_ver]
        except Exception:  # noqa: BLE001
            logger.exception("Vacaciones: no se pudo cargar el expediente")
            self.resumen.setText("No se pudo leer tu expediente. Revisa la conexión.")
            self.btn_pedir.setEnabled(False)
            return
        self._expediente = e
        self.respuestas.setText("\n\n".join(textos))
        self.respuestas.setVisible(bool(textos))
        if not e.completo:
            self.resumen.setText(
                "📁 Tu expediente está pendiente de completar: falta "
                + ", ".join(e.falta) + ". Pídele a Daniel que la capture."
            )
            self.btn_pedir.setEnabled(False)
        else:
            texto = (f"Ingreso: {_d(e.fecha_ingreso)} · {e.anios_cumplidos} año(s) cumplidos · "
                     f"<b>{e.disponible} días disponibles</b>")
            if e.anios_cumplidos == 0:
                texto += "<br>Las vacaciones empiezan a contar al cumplir tu primer año."
            self.resumen.setText(texto)
            self.btn_pedir.setEnabled(e.disponible > 0)
        self.periodos.setRowCount(len(e.periodos))
        for i, pv in enumerate(e.periodos):
            valores = [pv.periodo.anio_servicio, pv.periodo.dias_correspondientes,
                       pv.saldo.reservado + pv.pedidos, pv.saldo.disfrutado, pv.saldo.disponible - pv.pedidos]
            for j, v in enumerate(valores):
                self.periodos.setItem(i, j, QTableWidgetItem(str(v)))
        self.solicitudes.setRowCount(len(e.solicitudes))
        self._pendiente = None
        for i, s in enumerate(e.solicitudes):
            if s.estado == "pedido" and self._pendiente is None:
                self._pendiente = s.id
            self.solicitudes.setItem(i, 0, QTableWidgetItem(f"{_d(s.desde)} – {_d(s.hasta)}"))
            self.solicitudes.setItem(i, 1, QTableWidgetItem(str(s.dias)))
            self.solicitudes.setItem(i, 2, QTableWidgetItem(_ESTADOS.get(s.estado, s.estado)))
        self.btn_cancelar.setVisible(self._pendiente is not None)
        self._contar()

    def _contar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs
        from pos_uniformes.services.calendario_empleadas_service import cargar_horario

        desde, hasta = self.desde.date().toPyDate(), self.hasta.date().toPyDate()
        if hasta < desde:
            self.cuenta.setText("El último día va después del primero.")
            return
        try:
            with self._session_factory() as session:
                dias = vs.dias_laborables(cargar_horario(session, self._code), desde, hasta)
        except Exception:  # noqa: BLE001
            self.cuenta.setText("")
            return
        texto = (f"Son {len(dias)} día{'s' if len(dias) != 1 else ''} que te toca trabajar "
                 "(tus descansos no cuentan).")
        if 0 < len(dias) < vs.DIAS_CONTINUOS_MINIMOS:
            texto += f" La ley te da derecho a {vs.DIAS_CONTINUOS_MINIMOS} seguidos si los quieres."
        self.cuenta.setText(texto)

    # ── acciones ──
    def _pedir(self) -> None:
        from pos_uniformes.services import telegram_vacaciones_service as tvac
        from pos_uniformes.services import vacaciones_service as vs

        try:
            with self._session_factory() as session:
                s = vs.pedir(
                    session, employee_code=self._code, nombre=self._nombre,
                    desde=self.desde.date().toPyDate(), hasta=self.hasta.date().toPyDate(),
                    motivo=self.nota.text(), origen="kiosko",
                )
                session.commit()
                tvac.avisar_a_daniel(session, s)
        except vs.NoSePuede as exc:
            QMessageBox.information(self, "Vacaciones", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Vacaciones: no se pudo pedir")
            QMessageBox.warning(self, "Sin conexión", "No se pudo mandar. Intenta de nuevo.")
            return
        QMessageBox.information(self, "Listo", "Tu solicitud ya le llegó a Daniel.")
        self.nota.clear()
        self.recargar()

    def _retirar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        if self._pendiente is None:
            return
        try:
            with self._session_factory() as session:
                vs.cancelar(session, self._pendiente, quien=self._code, origen="kiosko")
                session.commit()
        except vs.NoSePuede as exc:
            QMessageBox.information(self, "Vacaciones", str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("Vacaciones: no se pudo retirar")
        self.recargar()

    def done(self, result: int) -> None:  # noqa: D401 — al cerrar, lo leído queda visto
        from pos_uniformes.services import vacaciones_service as vs

        if self._sin_ver:
            try:
                with self._session_factory() as session:
                    for sid in self._sin_ver:
                        vs.marcar_vista(session, sid, self._code)
                    session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Vacaciones: no se pudo marcar como visto")
        super().done(result)
