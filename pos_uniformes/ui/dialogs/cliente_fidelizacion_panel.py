"""E4-D: pestaña «Fidelización» de la ficha, con las acciones del ADMIN.

Lo que se ve sale de `admin_programas_service.cargar_panel` y lo que se hace,
de `membresia_service` (que exige ADMIN y motivo). Cada acción va en su
propia sesión y se confirma sola; si falla, se dice por qué y no cambia nada.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.fidelizacion import admin_programas_service as aps
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.utils.date_format import format_display_datetime

_logger = logging.getLogger(__name__)


class FidelizacionPanel(QWidget):
    def __init__(self, session_factory, *, cliente_id: int, usuario_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._cliente_id = int(cliente_id)
        self._usuario_id = int(usuario_id)
        self.hubo_cambios = False
        self.panel: aps.PanelPrograma | None = None

        caja = QVBoxLayout(self)
        form = QFormLayout()
        self.actual_label = QLabel("")
        self.pendiente_label = QLabel("")
        self.pendiente_label.setWordWrap(True)
        form.addRow("Programa", self.actual_label)
        form.addRow("Propuesta", self.pendiente_label)
        caja.addLayout(form)

        fila_pendiente = QHBoxLayout()
        self.aprobar_button = QPushButton("Aprobar propuesta")
        self.rechazar_button = QPushButton("Rechazar propuesta…")
        for b in (self.aprobar_button, self.rechazar_button):
            b.setObjectName("toolbarSecondaryButton")
            b.setAutoDefault(False)
            fila_pendiente.addWidget(b)
        fila_pendiente.addStretch()
        caja.addLayout(fila_pendiente)

        fila_acciones = QHBoxLayout()
        self.inscribir_button = QPushButton("Inscribir o cambiar de programa…")
        self.sacar_button = QPushButton("Sacar del programa…")
        self.inscribir_button.setObjectName("toolbarSecondaryButton")
        self.sacar_button.setObjectName("toolbarGhostButton")
        for b in (self.inscribir_button, self.sacar_button):
            b.setAutoDefault(False)
            fila_acciones.addWidget(b)
        fila_acciones.addStretch()
        caja.addLayout(fila_acciones)

        nota = QLabel("Es una etiqueta: por ahora ningún programa cambia precios ni descuentos.")
        nota.setObjectName("subtleLine")
        caja.addWidget(nota)

        caja.addWidget(QLabel("Historial"))
        self.historial = QTableWidget(0, 5)
        self.historial.setHorizontalHeaderLabels(["Fecha", "Evento", "Programa", "Quién", "Motivo"])
        self.historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.historial.verticalHeader().setVisible(False)
        self.historial.setObjectName("dataTable")
        self.historial.horizontalHeader().setStretchLastSection(True)
        caja.addWidget(self.historial, 1)

        self.aprobar_button.clicked.connect(self._aprobar)
        self.rechazar_button.clicked.connect(self._rechazar)
        self.inscribir_button.clicked.connect(self._inscribir)
        self.sacar_button.clicked.connect(self._sacar)
        self.recargar()

    # ─── Lectura ─────────────────────────────────────────────────────────

    def recargar(self) -> None:
        try:
            with self._session_factory() as session:
                self.panel = aps.cargar_panel(session, cliente_id=self._cliente_id, usuario_id=self._usuario_id)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Fidelización: no se pudo leer el programa del cliente %s", self._cliente_id)
            self.panel = None
            self.actual_label.setText(f"No se pudo leer: {exc}")
            self.pendiente_label.setText("")
            for b in (self.aprobar_button, self.rechazar_button, self.inscribir_button, self.sacar_button):
                b.setEnabled(False)
            return
        p = self.panel
        if p.actual:
            desde = format_display_datetime(p.actual_desde) if p.actual_desde else ""
            self.actual_label.setText(f"★ {p.actual}" + (f"  (desde {desde})" if desde else ""))
        else:
            self.actual_label.setText("Sin programa")
        if p.pendiente:
            pe = p.pendiente
            self.pendiente_label.setText(
                f"⏳ {pe.programa}, la propuso {pe.propuesta_por} el {format_display_datetime(pe.fecha)}.\n«{pe.motivo}»"
            )
        else:
            self.pendiente_label.setText("Ninguna")
        hay_pendiente = p.pendiente is not None
        self.aprobar_button.setEnabled(hay_pendiente)
        self.rechazar_button.setEnabled(hay_pendiente)
        self.inscribir_button.setEnabled(not hay_pendiente and bool(p.destinos))
        self.inscribir_button.setToolTip("Primero aprueba o rechaza la propuesta." if hay_pendiente else "")
        self.sacar_button.setEnabled(p.actual is not None)
        self.historial.setRowCount(len(p.historial))
        for r, fila in enumerate(p.historial):
            valores = (format_display_datetime(fila.fecha), fila.evento, fila.programa, fila.quien, fila.motivo)
            for c, valor in enumerate(valores):
                self.historial.setItem(r, c, QTableWidgetItem(valor))
        self.historial.resizeColumnsToContents()

    # ─── Acciones ────────────────────────────────────────────────────────

    def _motivo(self, titulo: str, pregunta: str) -> str | None:
        texto, ok = QInputDialog.getText(self, titulo, pregunta)
        texto = (texto or "").strip()
        if not ok:
            return None
        if len(texto) < ms.MOTIVO_ADMIN_MINIMO:
            QMessageBox.warning(self, titulo, f"Escribe un motivo de al menos {ms.MOTIVO_ADMIN_MINIMO} caracteres.")
            return None
        return texto

    def _hacer(self, titulo: str, accion) -> bool:
        try:
            with self._session_factory() as session:
                accion(session)
                session.commit()
        except (ms.NoSePuede, PermissionError) as exc:
            QMessageBox.warning(self, titulo, str(exc))
            self.recargar()
            return False
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Fidelización: falló «%s»", titulo)
            QMessageBox.critical(self, titulo, f"No se pudo guardar.\n\n{exc}")
            self.recargar()
            return False
        self.hubo_cambios = True
        self.recargar()
        return True

    def _aprobar(self) -> None:
        pe = self.panel.pendiente if self.panel else None
        if pe is None:
            return
        respuesta = QMessageBox.question(
            self, "Aprobar propuesta", f"¿Aprobar la entrada a {pe.programa}?\n\n"
            "Si tenía otro programa, se reemplaza, y su tipo de cliente se ajusta al del programa.",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        self._hacer("Aprobar propuesta",
                    lambda s: ms.aprobar_por_admin(s, pe.membresia_id, usuario_id=self._usuario_id))

    def _rechazar(self) -> None:
        pe = self.panel.pendiente if self.panel else None
        if pe is None:
            return
        motivo = self._motivo("Rechazar propuesta", "¿Por qué no? (lo verá quien la propuso)")
        if motivo is None:
            return
        self._hacer("Rechazar propuesta",
                    lambda s: ms.rechazar_por_admin(s, pe.membresia_id, usuario_id=self._usuario_id, motivo=motivo))

    def _inscribir(self) -> None:
        if not self.panel or not self.panel.destinos:
            return
        nombres = [nombre for _clave, nombre in self.panel.destinos]
        elegido, ok = QInputDialog.getItem(self, "Inscribir o cambiar", "Programa:", nombres, 0, False)
        if not ok or not elegido:
            return
        clave = self.panel.destinos[nombres.index(elegido)][0]
        motivo = self._motivo("Inscribir o cambiar", f"¿Por qué entra a {elegido}?")
        if motivo is None:
            return
        self._hacer("Inscribir o cambiar", lambda s: ms.inscribir_por_admin(
            s, cliente_id=self._cliente_id, programa_clave=clave, usuario_id=self._usuario_id, motivo=motivo))

    def _sacar(self) -> None:
        if not self.panel or not self.panel.actual:
            return
        motivo = self._motivo("Sacar del programa", f"¿Por qué sale de {self.panel.actual}?")
        if motivo is None:
            return
        self._hacer("Sacar del programa", lambda s: ms.sacar_del_programa(
            s, cliente_id=self._cliente_id, usuario_id=self._usuario_id, motivo=motivo))
