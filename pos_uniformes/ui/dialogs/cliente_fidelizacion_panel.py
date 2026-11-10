"""E4-D: pestaña «Fidelización» de la ficha, con las acciones del ADMIN.

Lo que se ve sale de `admin_programas_service.cargar_panel` y lo que se hace,
de `membresia_service` (que exige ADMIN y motivo). Cada acción va en su
propia sesión y se confirma sola; si falla, se dice por qué y no cambia nada.
"""

from __future__ import annotations

import logging
from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
        caja.setContentsMargins(4, 4, 4, 4)
        caja.setSpacing(12)
        fila_tarjetas = QWidget()
        fila_tarjetas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        tarjetas = QHBoxLayout(fila_tarjetas)
        tarjetas.setContentsMargins(0, 0, 0, 0)
        tarjetas.setSpacing(12)

        # Programa actual
        self.programa_card = QFrame()
        self.programa_card.setObjectName("cliProgramaCard")
        ly_prog = QVBoxLayout(self.programa_card)
        ly_prog.setContentsMargins(16, 14, 16, 14)
        ly_prog.setSpacing(4)
        ly_prog.addWidget(self._etiqueta("Programa actual"))
        fila_nombre = QHBoxLayout()
        fila_nombre.setSpacing(8)
        self.estrella_label = QLabel("★")
        self.estrella_label.setObjectName("cliEstrella")
        self.actual_label = QLabel("")
        self.actual_label.setObjectName("cliProgramaNombre")
        self.actual_label.setWordWrap(True)
        fila_nombre.addWidget(self.estrella_label)
        fila_nombre.addWidget(self.actual_label, 1)
        ly_prog.addLayout(fila_nombre)
        self.actual_desde_label = QLabel("")
        self.actual_desde_label.setObjectName("cliSubtitulo")
        ly_prog.addWidget(self.actual_desde_label)
        ly_prog.addStretch()
        fila_acciones = QHBoxLayout()
        self.inscribir_button = QPushButton("Inscribir o cambiar de programa…")
        self.sacar_button = QPushButton("Sacar del programa…")
        self.inscribir_button.setObjectName("toolbarSecondaryButton")
        self.sacar_button.setObjectName("cliPeligro")
        for b in (self.inscribir_button, self.sacar_button):
            b.setAutoDefault(False)
            fila_acciones.addWidget(b)
        fila_acciones.addStretch()
        ly_prog.addLayout(fila_acciones)
        tarjetas.addWidget(self.programa_card, 1)

        # Propuesta pendiente
        self.propuesta_card = QFrame()
        self.propuesta_card.setObjectName("cliPropuestaCard")
        ly_prop = QVBoxLayout(self.propuesta_card)
        ly_prop.setContentsMargins(16, 14, 16, 14)
        ly_prop.setSpacing(6)
        ly_prop.addWidget(self._etiqueta("Propuesta"))
        self.pendiente_label = QLabel("")
        self.pendiente_label.setWordWrap(True)
        self.pendiente_label.setMinimumHeight(66)
        self.pendiente_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        ly_prop.addWidget(self.pendiente_label)
        ly_prop.addStretch()
        fila_pendiente = QHBoxLayout()
        self.aprobar_button = QPushButton("Aprobar propuesta")
        self.rechazar_button = QPushButton("Rechazar propuesta…")
        self.aprobar_button.setObjectName("toolbarPrimaryButton")
        self.rechazar_button.setObjectName("toolbarGhostButton")
        for b in (self.aprobar_button, self.rechazar_button):
            b.setAutoDefault(False)
            fila_pendiente.addWidget(b)
        fila_pendiente.addStretch()
        ly_prop.addLayout(fila_pendiente)
        tarjetas.addWidget(self.propuesta_card, 1)
        caja.addWidget(fila_tarjetas)

        nota = QLabel("Por ahora los programas son una etiqueta: no cambian precios ni descuentos.")
        nota.setObjectName("cliNota")
        nota.setWordWrap(True)
        caja.addWidget(nota)

        historial = QLabel("HISTORIAL")
        historial.setObjectName("cliSeccion")
        caja.addWidget(historial)
        self.historial = QTableWidget(0, 5)
        self.historial.setHorizontalHeaderLabels(["Fecha", "Evento", "Programa", "Quién", "Motivo"])
        self.historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.historial.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.historial.verticalHeader().setVisible(False)
        self.historial.verticalHeader().setDefaultSectionSize(36)
        self.historial.setShowGrid(False)
        self.historial.setAlternatingRowColors(True)
        self.historial.setObjectName("cliTabla")
        encabezado = self.historial.horizontalHeader()
        for col in range(4):
            encabezado.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.historial.setMinimumHeight(150)
        caja.addWidget(self.historial, 1)
        self.historial_vacio = QLabel("Todavía no ha estado en ningún programa.")
        self.historial_vacio.setObjectName("cliVacio")
        self.historial_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caja.addWidget(self.historial_vacio)
        self.relleno = QWidget()
        self.relleno.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        caja.addWidget(self.relleno)

        self.aprobar_button.clicked.connect(self._aprobar)
        self.rechazar_button.clicked.connect(self._rechazar)
        self.inscribir_button.clicked.connect(self._inscribir)
        self.sacar_button.clicked.connect(self._sacar)
        self.recargar()

    @staticmethod
    def _etiqueta(texto: str) -> QLabel:
        etiqueta = QLabel(texto.upper())
        etiqueta.setObjectName("cliCampoEtiqueta")
        return etiqueta

    @staticmethod
    def _marcar(tarjeta: QFrame, propiedad: str, valor: bool) -> None:
        tarjeta.setProperty(propiedad, "true" if valor else "false")
        tarjeta.style().unpolish(tarjeta)
        tarjeta.style().polish(tarjeta)

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
            self.actual_label.setText(p.actual)
            desde = format_display_datetime(p.actual_desde) if p.actual_desde else ""
            self.actual_desde_label.setText(f"Desde el {desde}" if desde else "")
        else:
            self.actual_label.setText("Sin programa")
            self.actual_desde_label.setText("Se inscribe desde Venta Rápida o aquí.")
        self.estrella_label.setVisible(bool(p.actual))
        self._marcar(self.programa_card, "activo", bool(p.actual))
        if p.pendiente:
            pe = p.pendiente
            self.pendiente_label.setText(
                f"⏳ <b>{escape(pe.programa)}</b><br>"
                f"<span style='color:#6d665e'>La propuso {escape(pe.propuesta_por)} el "
                f"{escape(format_display_datetime(pe.fecha))}</span><br>«{escape(pe.motivo)}»"
            )
        else:
            self.pendiente_label.setText("Ninguna")
        self._marcar(self.propuesta_card, "pendiente", p.pendiente is not None)
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
        self.historial.setVisible(bool(p.historial))
        self.historial_vacio.setVisible(not p.historial)
        self.relleno.setVisible(not p.historial)
        # Lo que no aplica no se enseña (sigue desactivado, como antes).
        self.aprobar_button.setVisible(hay_pendiente)
        self.rechazar_button.setVisible(hay_pendiente)
        self.sacar_button.setVisible(p.actual is not None)

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
