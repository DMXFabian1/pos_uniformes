"""E4-C: programa del cliente en Venta Rápida (kiosko).

Mixin para `QuickSaleWidget`. Es una franja propia debajo de la barra del
Monedero, que no se toca. Muestra en qué programa está el cliente ligado a la
venta y deja a la empleada:

- inscribirlo a Maximoda Club (queda activo al instante; el cliente que se
  registra en el kiosko ya entra solo, desde 2026-11-10), o
- proponerlo a Profesional o Mayorista con un motivo (lo aprueba el dueño
  por Telegram).

Mientras haya una propuesta esperando, la franja la vuelve a leer cada
`REVISAR_PROPUESTA_MS`: cuando Daniel aprueba o rechaza por Telegram, cambia
sola y se le avisa a la empleada (2026-11-10: «ya aprobé y no hubo cambios
inmediatos»).

Es solo una etiqueta: no cambia precios, ni la venta, ni el Monedero, ni la
cola sin conexión. Sin conexión no se inscribe ni se propone (D3). Cambiar de
programa o sacar a alguien es solo en el POS con ADMIN (P-E4-7).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton

from pos_uniformes.ui.styles import kiosko_clientes_styles

_logger = logging.getLogger(__name__)

SIN_CONEXION_TOOLTIP = "Sin conexión: inscríbelo después."
SOLO_EN_POS_TOOLTIP = "Cambiar de programa se hace en el POS."
#: Cada cuánto se revisa una propuesta que espera respuesta (una consulta).
REVISAR_PROPUESTA_MS = 15_000


def aviso_de_respuesta(nombre: str, antes: "_Leido", ahora: "_Leido") -> str | None:
    """Qué decirle a la empleada cuando la propuesta deja de estar pendiente."""
    if not antes.pendiente or ahora.pendiente:
        return None
    if ahora.activa == antes.pendiente:
        return f"✅ Aprobado: {nombre} ya es miembro de {ahora.activa}"
    return f"La propuesta de {nombre} a {antes.pendiente} no se aprobó"


@dataclass(frozen=True)
class EstadoBarraPrograma:
    texto: str
    puede_club: bool
    puede_proponer: bool
    tooltip: str = ""


def estado_para_barra(*, en_linea: bool, activa: str | None, activa_clave: str | None,
                      pendiente: str | None, hay_empleada: bool = True) -> EstadoBarraPrograma:
    """Qué dice la franja y qué botones quedan activos. Sin Qt ni base."""
    if not en_linea:
        return EstadoBarraPrograma("★ Programa: sin conexión", False, False, SIN_CONEXION_TOOLTIP)
    if pendiente:
        corto = pendiente.replace("Maximoda ", "")
        return EstadoBarraPrograma(f"⏳ Propuesta a {corto}: esperando aprobación", False, False,
                                   "Ya hay una propuesta en curso para este cliente.")
    if activa:
        texto = f"★ Miembro {activa}"
        if activa_clave in ("CLUB", "LEAL"):  # E5-A: desde Leal también se propone
            return EstadoBarraPrograma(texto, False, hay_empleada)
        return EstadoBarraPrograma(texto, False, False, SOLO_EN_POS_TOOLTIP)
    return EstadoBarraPrograma("★ Sin programa", hay_empleada, hay_empleada)


@dataclass(frozen=True)
class _Leido:
    cliente_id: int
    activa: str | None
    activa_clave: str | None
    pendiente: str | None


class ProgramaClienteMixin:
    """Usa de QuickSaleWidget: _cliente, _employee_code, _en_linea,
    _avisar_sin_conexion y _flash_scan_hint."""

    # ─── Franja ──────────────────────────────────────────────────────────

    def _build_programa_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("programaBar")
        bar.setStyleSheet(kiosko_clientes_styles.FRANJA_PROGRAMA)
        ly = QHBoxLayout()
        ly.setContentsMargins(14, 6, 10, 6)
        ly.setSpacing(8)
        self._programa_label = QLabel("")
        self._programa_label.setTextFormat(Qt.TextFormat.PlainText)
        ly.addWidget(self._programa_label, 1)
        self._btn_inscribir_club = QPushButton("★ Inscribir a Maximoda Club")
        self._btn_inscribir_club.setObjectName("kcFranjaClub")
        self._btn_inscribir_club.setAutoDefault(False)
        self._btn_inscribir_club.clicked.connect(self._on_inscribir_club)
        ly.addWidget(self._btn_inscribir_club)
        self._btn_proponer_programa = QPushButton("Proponer programa…")
        self._btn_proponer_programa.setAutoDefault(False)
        self._btn_proponer_programa.clicked.connect(self._on_proponer_programa)
        ly.addWidget(self._btn_proponer_programa)
        bar.setLayout(ly)
        bar.setVisible(False)
        self._programa_bar = bar
        self._programa_leido: _Leido | None = None
        self._programa_timer = QTimer(bar)
        self._programa_timer.setInterval(REVISAR_PROPUESTA_MS)
        self._programa_timer.timeout.connect(self._revisar_propuesta)
        return bar

    def _pintar_programa_bar(self) -> None:
        bar = getattr(self, "_programa_bar", None)
        if bar is None:
            return
        c = getattr(self, "_cliente", None)
        cliente_id = c.get("id") if c else None
        en_linea = bool(c and c.get("en_linea") and self._en_linea())
        bar.setVisible(bool(c))
        if not c:
            self._programa_leido = None
            self._vigilar_propuesta(False)
            return
        leido = None
        if en_linea and cliente_id:
            leido = self._programa_leido
            if leido is None or leido.cliente_id != int(cliente_id):
                leido = self._leer_programa(int(cliente_id))
            if leido is None:
                en_linea = False
        estado = estado_para_barra(
            en_linea=en_linea,
            activa=leido.activa if leido else None,
            activa_clave=leido.activa_clave if leido else None,
            pendiente=leido.pendiente if leido else None,
            hay_empleada=bool(getattr(self, "_employee_code", None)),
        )
        self._programa_label.setText(estado.texto)
        self._btn_inscribir_club.setEnabled(estado.puede_club)
        self._btn_proponer_programa.setEnabled(estado.puede_proponer)
        self._btn_inscribir_club.setToolTip(estado.tooltip if not estado.puede_club else "")
        self._btn_proponer_programa.setToolTip(estado.tooltip if not estado.puede_proponer else "")
        self._vigilar_propuesta(bool(en_linea and leido and leido.pendiente))

    def _vigilar_propuesta(self, si: bool) -> None:
        timer = getattr(self, "_programa_timer", None)
        if timer is None:
            return
        if si and not timer.isActive():
            timer.start()
        elif not si and timer.isActive():
            timer.stop()

    def _revisar_propuesta(self) -> None:
        """Vuelve a leer el programa del cliente ligado mientras espera respuesta."""
        c = getattr(self, "_cliente", None)
        antes = getattr(self, "_programa_leido", None)
        if not c or antes is None or not antes.pendiente or int(c.get("id") or 0) != antes.cliente_id:
            self._vigilar_propuesta(False)
            return
        ahora = self._leer_programa(antes.cliente_id)
        if ahora is not None:
            aviso = aviso_de_respuesta(str(c.get("nombre") or "El cliente"), antes, ahora)
            if aviso:
                self._flash_scan_hint(aviso)
        self._pintar_programa_bar()

    def _leer_programa(self, cliente_id: int) -> _Leido | None:
        """Una consulta por cliente ligado (no en cada tecla). None si falla."""
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.fidelizacion import membresia_service as ms

            with get_session() as session:
                e = ms.estado_de_cliente(session, cliente_id)
                leido = _Leido(
                    cliente_id=int(cliente_id),
                    activa=e.activa.programa.nombre if e.activa else None,
                    activa_clave=e.activa.programa.clave if e.activa else None,
                    pendiente=e.pendiente.programa.nombre if e.pendiente else None,
                )
        except Exception as exc:  # noqa: BLE001 — la venta sigue aunque esto falle
            from pos_uniformes.ui.helpers.quick_sale_monedero_helper import _es_error_de_red

            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
            else:
                _logger.exception("Programa: no se pudo leer el del cliente %s", cliente_id)
            self._programa_leido = None
            return None
        self._programa_leido = leido
        return leido

    def _releer_programa(self) -> None:
        self._programa_leido = None
        self._pintar_programa_bar()

    # ─── Acciones ────────────────────────────────────────────────────────

    def _programa_puede_actuar(self) -> bool:
        c = getattr(self, "_cliente", None)
        if not c or not c.get("id"):
            return False
        if not self._en_linea() or not c.get("en_linea"):
            QMessageBox.information(self, "Programa", SIN_CONEXION_TOOLTIP)
            return False
        return True

    def _on_inscribir_club(self) -> None:
        if not self._programa_puede_actuar():
            return
        c = self._cliente
        respuesta = QMessageBox.question(
            self,
            "Maximoda Club",
            f"¿Inscribir a {c['nombre']} a Maximoda Club?\n\n"
            "Queda como miembro desde hoy. Por ahora no cambia ningún precio.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        def hacer(session, ms):
            ms.inscribir_por_empleada(session, cliente_id=int(c["id"]), programa_clave="CLUB",
                                      employee_code=str(self._employee_code or ""))
            session.commit()

        if self._programa_ejecutar(hacer):
            self._flash_scan_hint(f"{c['nombre']} ya es miembro de Maximoda Club")

    def _on_proponer_programa(self) -> bool:
        """True si la propuesta quedó guardada."""
        if not self._programa_puede_actuar():
            return False
        from pos_uniformes.ui.dialogs.proponer_programa_dialog import ProponerProgramaDialog

        c = self._cliente
        dialogo = ProponerProgramaDialog(self, nombre_cliente=str(c["nombre"]))
        if dialogo.exec() != int(QDialog.DialogCode.Accepted) or dialogo.resultado is None:
            return False
        clave, motivo = dialogo.resultado

        def hacer(session, ms):
            from pos_uniformes.services import telegram_membresias_service as tm

            m = ms.proponer(session, cliente_id=int(c["id"]), programa_clave=clave,
                            employee_code=str(self._employee_code or ""), motivo=motivo)
            session.commit()
            # Ya quedó guardada: el aviso nunca truena y, si no sale, queda en
            # la cola de alertas y en el recordatorio diario.
            tm.avisar_a_daniel(session, m)

        if self._programa_ejecutar(hacer):
            self._flash_scan_hint("Propuesta enviada: esperando aprobación")
            return True
        return False

    def _programa_ejecutar(self, hacer) -> bool:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.fidelizacion import membresia_service as ms
        from pos_uniformes.ui.helpers.quick_sale_monedero_helper import _es_error_de_red

        ok = False
        try:
            with get_session() as session:
                hacer(session, ms)
            ok = True
        except (ms.NoSePuede, PermissionError) as exc:
            QMessageBox.warning(self, "Programa", str(exc))
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
                QMessageBox.information(self, "Programa", SIN_CONEXION_TOOLTIP)
            else:
                _logger.exception("Programa: no se pudo guardar")
                QMessageBox.warning(self, "Programa", f"No se pudo guardar.\n\n{exc}")
        self._releer_programa()
        return ok
