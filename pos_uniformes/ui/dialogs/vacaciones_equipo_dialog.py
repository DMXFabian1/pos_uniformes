"""Vacaciones del equipo (Libreta de Daniel): todo se gestiona desde aquí.

Daniel captura la fecha de ingreso verificada, registra vacaciones (quedan
aprobadas al momento), las cancela, marca primas pagadas y decide a quién le
abre pedirlas desde su propia Libreta. Solo pinta y llama a
`vacaciones_service`: las reglas viven ahí.
"""

from __future__ import annotations

import logging
from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

DUENO = "VEND-1"
_ESTADOS = {
    "pedido": "⏳ pedidas", "aprobado": "✅ aprobadas", "rechazado": "✖️ rechazadas",
    "cancelado": "↩️ canceladas", "vencido": "⌛ vencidas", "revocado": "↩️ deshechas",
}


def _q(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _tabla(columnas: list[str], alto: int) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setMaximumHeight(alto)
    return t


class VacacionesEquipoDialog(QDialog):
    def __init__(self, parent, *, session_factory, quien: str = DUENO) -> None:
        super().__init__(parent)
        self._F = session_factory
        self._quien = quien
        self._equipo: list = []
        self._code: str | None = None
        self.setWindowTitle("Vacaciones del equipo")
        self.setMinimumWidth(720)
        self.setStyleSheet(
            "QDialog { background: #f4ede2; } QLabel { color: #2c2a27; background: transparent; }"
        )
        ly = QVBoxLayout(self)
        ly.setContentsMargins(18, 16, 18, 14)
        ly.setSpacing(7)
        t = QLabel("🏖️ Vacaciones del equipo")
        t.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        ly.addWidget(t)
        ayuda = QLabel("Por ahora solo tú las registras. Ellas las verán y pedirán cuando les abras "
                       "«Le dejo pedir desde su Libreta».")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("font-size: 12px; color: #8a8177;")
        ly.addWidget(ayuda)

        self.tabla_equipo = _tabla(["Empleada", "Ingreso", "Años", "Disponibles", "Pide ella"], 170)
        self.tabla_equipo.itemSelectionChanged.connect(self._elegir)
        ly.addWidget(self.tabla_equipo)

        self.titulo = QLabel("Elige a alguien de la lista.")
        self.titulo.setStyleSheet("font-size: 15px; font-weight: 800; margin-top: 4px;")
        ly.addWidget(self.titulo)
        self.revisar = QLabel("")
        self.revisar.setWordWrap(True)
        self.revisar.setStyleSheet("color: #a33b25; font-weight: 600;")
        ly.addWidget(self.revisar)

        exp = QHBoxLayout()
        exp.addWidget(QLabel("Ingreso verificado:"))
        self.ingreso = QDateEdit()
        self.ingreso.setCalendarPopup(True)
        self.ingreso.setDisplayFormat("dd/MM/yyyy")
        exp.addWidget(self.ingreso)
        self.con_antiguedad = QCheckBox("Antigüedad reconocida desde")
        exp.addWidget(self.con_antiguedad)
        self.antiguedad = QDateEdit()
        self.antiguedad.setCalendarPopup(True)
        self.antiguedad.setDisplayFormat("dd/MM/yyyy")
        exp.addWidget(self.antiguedad)
        self.btn_expediente = QPushButton("Guardar")
        self.btn_expediente.clicked.connect(self._guardar_expediente)
        exp.addWidget(self.btn_expediente)
        ly.addLayout(exp)
        self.condiciones = QLineEdit()
        self.condiciones.setPlaceholderText("Condiciones especiales de su contrato (si hay más días que la ley)")
        ly.addWidget(self.condiciones)

        self.periodos = _tabla(["Año", "Le tocan", "Apartados", "Disfrutados", "Disponibles", "Conceder antes del"], 110)
        ly.addWidget(self.periodos)

        reg = QHBoxLayout()
        reg.addWidget(QLabel("Registrar vacaciones del"))
        hoy = date.today()
        self.desde = QDateEdit(_q(hoy))
        self.hasta = QDateEdit(_q(hoy))
        for w in (self.desde, self.hasta):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
            w.dateChanged.connect(lambda _d: self._contar())
        reg.addWidget(self.desde)
        reg.addWidget(QLabel("al"))
        reg.addWidget(self.hasta)
        self.btn_registrar = QPushButton("Registrar")
        self.btn_registrar.setStyleSheet(
            "QPushButton { background: #a84f2d; color: #fff; font-weight: 700; border-radius: 8px; padding: 6px 14px; }"
            "QPushButton:disabled { background: #d8cbbb; color: #8a8177; }"
        )
        self.btn_registrar.clicked.connect(self._registrar)
        reg.addWidget(self.btn_registrar)
        ly.addLayout(reg)
        self.cuenta = QLabel("")
        self.cuenta.setWordWrap(True)
        self.cuenta.setStyleSheet("font-size: 12px; color: #8a8177;")
        ly.addWidget(self.cuenta)

        self.solicitudes = _tabla(["#", "Fechas", "Días", "Estado", "Prima"], 130)
        for col in (0, 1, 2):
            self.solicitudes.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        ly.addWidget(self.solicitudes)
        acciones = QHBoxLayout()
        self.btn_aprobar = QPushButton("Aprobar")
        self.btn_aprobar.clicked.connect(lambda: self._resolver("aprobar"))
        self.btn_rechazar = QPushButton("Rechazar")
        self.btn_rechazar.clicked.connect(lambda: self._resolver("rechazar"))
        self.btn_cancelar = QPushButton("Cancelar (devuelve lo no disfrutado)")
        self.btn_cancelar.clicked.connect(lambda: self._resolver("cancelar"))
        self.btn_prima = QPushButton("Prima pagada")
        self.btn_prima.clicked.connect(self._prima_pagada)
        for b in (self.btn_aprobar, self.btn_rechazar, self.btn_cancelar, self.btn_prima):
            acciones.addWidget(b)
        ly.addLayout(acciones)

        abajo = QHBoxLayout()
        self.autoservicio = QCheckBox("Le dejo pedir desde su Libreta")
        self.autoservicio.clicked.connect(self._cambiar_autoservicio)
        abajo.addWidget(self.autoservicio)
        abajo.addStretch(1)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        abajo.addWidget(cerrar)
        ly.addLayout(abajo)
        self.recargar()

    # ── datos ──
    def recargar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        try:
            with self._F() as session:
                self._equipo = vs.equipo(session)
        except Exception:  # noqa: BLE001
            logger.exception("Vacaciones del equipo: no se pudo cargar")
            self.titulo.setText("No se pudo leer. Revisa la conexión.")
            return
        actual = self._code
        self.tabla_equipo.blockSignals(True)
        self.tabla_equipo.setRowCount(len(self._equipo))
        fila_actual = None
        for i, (code, nombre, e) in enumerate(self._equipo):
            valores = [
                nombre,
                f"{e.fecha_ingreso:%d/%m/%Y}" if e.completo else "📁 falta",
                str(e.anios_cumplidos) if e.completo else "—",
                str(e.disponible) if e.completo else "—",
                "sí" if e.autoservicio else "no",
            ]
            for j, v in enumerate(valores):
                self.tabla_equipo.setItem(i, j, QTableWidgetItem(v))
            if code == actual:
                fila_actual = i
        self.tabla_equipo.blockSignals(False)
        if fila_actual is not None:
            self.tabla_equipo.selectRow(fila_actual)
        self._pintar()

    def _seleccion(self):
        for code, nombre, e in self._equipo:
            if code == self._code:
                return code, nombre, e
        return None

    def _elegir(self) -> None:
        filas = self.tabla_equipo.selectionModel().selectedRows()
        if filas:
            self._code = self._equipo[filas[0].row()][0]
        self._pintar()

    def _pintar(self) -> None:
        sel = self._seleccion()
        hay = sel is not None
        for w in (self.ingreso, self.con_antiguedad, self.antiguedad, self.btn_expediente,
                  self.condiciones, self.desde, self.hasta, self.btn_registrar, self.autoservicio,
                  self.btn_aprobar, self.btn_rechazar, self.btn_cancelar, self.btn_prima):
            w.setEnabled(hay)
        if not hay:
            self.periodos.setRowCount(0)
            self.solicitudes.setRowCount(0)
            return
        code, nombre, e = sel
        self.titulo.setText(f"{nombre} ({code})")
        self.revisar.setText(e.revisar or "")
        self.revisar.setVisible(bool(e.revisar))
        if e.completo:
            self.ingreso.setDate(_q(e.fecha_ingreso))
            self.con_antiguedad.setChecked(e.antiguedad_desde is not None)
            self.antiguedad.setDate(_q(e.antiguedad_desde or e.fecha_ingreso))
        else:
            self.ingreso.setDate(_q(date.today()))
            self.con_antiguedad.setChecked(False)
        # Con periodos ya generados la fecha no se mueve (se corrige con ajuste).
        fijo = bool(e.periodos)
        for w in (self.ingreso, self.con_antiguedad, self.antiguedad):
            w.setEnabled(not fijo)
        self.condiciones.setText(e.condiciones_especiales or "")
        self.autoservicio.setChecked(e.autoservicio)
        self.autoservicio.setEnabled(e.completo)
        self.btn_registrar.setEnabled(e.completo and e.disponible > 0)
        self.periodos.setRowCount(len(e.periodos))
        for i, pv in enumerate(e.periodos):
            for j, v in enumerate([pv.periodo.anio_servicio, pv.periodo.dias_correspondientes,
                                   pv.saldo.reservado + pv.pedidos, pv.saldo.disfrutado,
                                   pv.saldo.disponible - pv.pedidos, f"{pv.periodo.fecha_limite:%d/%m/%Y}"]):
                self.periodos.setItem(i, j, QTableWidgetItem(str(v)))
        primas = {p.solicitud_id: p for p in e.primas}
        self.solicitudes.setRowCount(len(e.solicitudes))
        for i, s in enumerate(e.solicitudes):
            p = primas.get(s.id)
            prima = f"${p.monto:,.2f} {p.estado}" if p else "—"
            for j, v in enumerate([s.id, f"{s.desde:%d/%m/%Y} – {s.hasta:%d/%m/%Y}", s.dias,
                                   _ESTADOS.get(s.estado, s.estado), prima]):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self.solicitudes.setItem(i, j, item)
        self._contar()

    def _contar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs
        from pos_uniformes.services.calendario_empleadas_service import cargar_horario

        sel = self._seleccion()
        if sel is None:
            self.cuenta.setText("")
            return
        desde, hasta = self.desde.date().toPyDate(), self.hasta.date().toPyDate()
        if hasta < desde:
            self.cuenta.setText("El último día va después del primero.")
            return
        try:
            with self._F() as session:
                dias = vs.dias_laborables(cargar_horario(session, sel[0]), desde, hasta)
                fuera = {d: q for d, q in vs.cobertura(session, desde, hasta, excluir=sel[0]).items() if q}
        except Exception:  # noqa: BLE001
            self.cuenta.setText("")
            return
        texto = (f"{len(dias)} día{'s' if len(dias) != 1 else ''} laborable"
                 f"{'s' if len(dias) != 1 else ''} (sus descansos no cuentan).")
        if fuera:
            texto += " También faltan: " + "; ".join(
                f"{d:%d/%m} {', '.join(q)}" for d, q in list(fuera.items())[:5])
        self.cuenta.setText(texto)

    def _solicitud_elegida(self) -> int | None:
        filas = self.solicitudes.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Vacaciones", "Elige una solicitud de la lista.")
            return None
        return self.solicitudes.item(filas[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    # ── acciones ──
    def _hacer(self, fn, ok: str | None = None) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        try:
            with self._F() as session:
                fn(session)
                session.commit()
        except vs.NoSePuede as exc:
            QMessageBox.information(self, "Vacaciones", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Vacaciones del equipo: falló la operación")
            QMessageBox.warning(self, "Sin conexión", "No se pudo guardar. Intenta de nuevo.")
            return
        if ok:
            QMessageBox.information(self, "Listo", ok)
        self.recargar()

    def _guardar_expediente(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        code = self._code
        ingreso = self.ingreso.date().toPyDate()
        reconocida = self.antiguedad.date().toPyDate() if self.con_antiguedad.isChecked() else None
        condiciones = self.condiciones.text()

        def _fn(session):
            vs.capturar_expediente(session, code, fecha_ingreso=ingreso, quien=self._quien,
                                   antiguedad_desde=reconocida,
                                   condiciones_especiales=condiciones or None, origen="libreta")
            vs.generar_periodos(session, code, quien=self._quien)

        self._hacer(_fn, "Expediente guardado.")

    def _registrar(self) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        code, nombre, _e = self._seleccion()
        desde, hasta = self.desde.date().toPyDate(), self.hasta.date().toPyDate()
        self._hacer(lambda session: vs.registrar_por_dueno(
            session, employee_code=code, nombre=nombre, desde=desde, hasta=hasta, quien=self._quien,
        ), f"Vacaciones de {nombre.split()[0]} registradas. Ya están en el calendario.")

    def _resolver(self, que: str) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        sid = self._solicitud_elegida()
        if sid is None:
            return
        motivo = ""
        if que in ("rechazar", "cancelar"):
            motivo, ok = QInputDialog.getText(self, "Motivo", "¿Por qué? (lo verá ella)")
            if not ok:
                return
        acciones = {
            "aprobar": lambda s: vs.aprobar(s, sid, quien=self._quien, origen="libreta"),
            "rechazar": lambda s: vs.rechazar(s, sid, quien=self._quien, respuesta=motivo, origen="libreta"),
            "cancelar": lambda s: vs.cancelar(s, sid, quien=self._quien, motivo=motivo or "cancelada por Daniel",
                                              origen="libreta"),
        }
        self._hacer(acciones[que])

    def _prima_pagada(self) -> None:
        from pos_uniformes.database.models import PrimaVacacional
        from pos_uniformes.services import vacaciones_service as vs

        sid = self._solicitud_elegida()
        if sid is None:
            return

        def _fn(session):
            prima = session.query(PrimaVacacional).filter(PrimaVacacional.solicitud_id == sid).first()
            if prima is None:
                raise vs.NoSePuede("Esa solicitud no tiene prima registrada.")
            vs.marcar_prima_pagada(session, prima.id, quien=self._quien, origen="libreta")

        self._hacer(_fn, "Prima marcada como pagada.")

    def _cambiar_autoservicio(self, marcado: bool) -> None:
        from pos_uniformes.services import vacaciones_service as vs

        code = self._code
        self._hacer(lambda s: vs.habilitar_autoservicio(s, code, marcado, quien=self._quien))
