"""Historial de conteos: la ventana del dueño para auditar.

Daniel (2026-09-22): *"¿cómo puedo compararlo con conteos anteriores?, ¿cómo
saco pedidos?, debería existir una ventana para auditar esto, ver cómo
evoluciona"*. Hasta ahora todo eso existía pero solo se alcanzaba desde
adentro de Revisar o con doble clic en una tabla escondida.

Izquierda: cada escuela y tipo de básicos, con cuándo se contó por última vez.
Derecha: **sus conteos, uno por renglón** (cuándo, quién, cuántas tallas, qué
tanto se movió, qué se pidió) y, para el elegido, los tres botones que antes
estaban enterrados:

- **Comparar con el anterior** → `ConteoComparativoDialog`
- **Revisar / pedido** → `ConteoRevisionDialog` (decidir qué pedir)
- **Hoja de pedido** → `PedidoHojaDialog`

Arriba de todo, **Cómo evoluciona** (`EscuelaHistoriaDialog`): las ventas por
semana de esa escuela y qué talla se pide más.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import get_session

COLUMNAS = ("Cuándo", "Quién", "Tallas", "Faltaron", "Sobraron", "Pedido", "Estado")
_COL_CUANDO, _COL_QUIEN, _COL_TALLAS, _COL_FALTARON, _COL_SOBRARON, _COL_PEDIDO, _COL_ESTADO = range(7)

_ESTILO = """
QDialog { background: #fdfaf6; }
QLabel { color: #3b2a20; }
QTableWidget { background: #fff; border: 1px solid #e6d8cb; border-radius: 8px; gridline-color: #f1e8e0;
               alternate-background-color: #fdf8f3; color: #3b2a20; }
QTableWidget::item:selected { background: #f4d4bb; color: #4a1505; }
QHeaderView::section { background: #f3ece4; color: #6b4c36; font-weight: 700; padding: 6px; border: none;
                       border-bottom: 1px solid #e6d8cb; }
QListWidget { border: 1px solid #e6d8cb; border-radius: 8px; background: #fff; outline: none; }
QListWidget::item { padding: 8px 10px; color: #4a382c; }
QListWidget::item:selected { background: #f4d4bb; color: #4a1505; font-weight: 600; }
QLineEdit { border: 1.5px solid #dcc9ba; border-radius: 8px; padding: 6px 10px; background: #fffdf9; }
QPushButton { background: #fff; border: 1px solid #dcc9ba; border-radius: 8px; padding: 7px 14px; color: #8a4a22; }
QPushButton:hover { background: #fdf3ec; }
QPushButton:disabled { color: #c3b3a6; }
QPushButton#primario { background: #a8481f; color: #fff; border: none; font-weight: 700; }
QPushButton#primario:hover { background: #8f3c19; }
"""

def _default_session_factory() -> Session:
    return get_session()


def abrir_historial_conteos(parent=None, *, session_factory=None) -> None:
    ConteoHistorialDialog(parent, session_factory=session_factory).exec()


class ConteoHistorialDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, session_factory: Callable[[], Session] | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory or _default_session_factory
        self._alcances: list = []          # FilaTablero
        self._conteos: list = []           # ConteoDelHistorial del alcance elegido
        self._elegido = None
        self.setWindowTitle("Historial de conteos")
        self.setStyleSheet(_ESTILO)
        self.resize(1100, 660)
        self._build_ui()
        self._cargar_alcances()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(16, 14, 16, 14)
        raiz.setSpacing(10)

        titulo = QLabel("Historial de conteos")
        titulo.setStyleSheet("font-size: 18px; font-weight: 800; color: #5c3019;")
        raiz.addWidget(titulo)
        ayuda = QLabel("Elige una escuela o un tipo de básicos: a la derecha están todos sus conteos. "
                       "Toca uno para compararlo con el anterior, decidir el pedido o sacar la hoja.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #8a7b70; font-size: 12px;")
        raiz.addWidget(ayuda)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(14)

        izq = QVBoxLayout()
        izq.setSpacing(8)
        self._buscar = QLineEdit()
        self._buscar.setPlaceholderText("Buscar escuela o básico…")
        self._buscar.textChanged.connect(self._pintar_alcances)
        izq.addWidget(self._buscar)
        self._lista = QListWidget()
        self._lista.setFixedWidth(280)
        self._lista.currentItemChanged.connect(self._alcance_elegido)
        izq.addWidget(self._lista, 1)
        cuerpo.addLayout(izq)

        der = QVBoxLayout()
        der.setSpacing(8)
        cabecera = QHBoxLayout()
        self._titulo_alcance = QLabel("Elige una escuela")
        self._titulo_alcance.setStyleSheet("font-size: 16px; font-weight: 800; color: #5c3019;")
        cabecera.addWidget(self._titulo_alcance, 1)
        self._evolucion_btn = QPushButton("📈 Cómo evoluciona")
        self._evolucion_btn.setToolTip("Piezas vendidas por semana y qué talla se pide más")
        self._evolucion_btn.clicked.connect(self._abrir_evolucion)
        self._evolucion_btn.setEnabled(False)
        cabecera.addWidget(self._evolucion_btn)
        der.addLayout(cabecera)

        self._resumen = QLabel("")
        self._resumen.setStyleSheet("color: #8a7b70; font-size: 12.5px;")
        der.addWidget(self._resumen)

        self._tabla = QTableWidget(0, len(COLUMNAS))
        self._tabla.setHorizontalHeaderLabels(COLUMNAS)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.itemSelectionChanged.connect(self._conteo_elegido)
        self._tabla.cellDoubleClicked.connect(lambda *_a: self._abrir_comparativo())
        hh = self._tabla.horizontalHeader()
        hh.setSectionResizeMode(_COL_QUIEN, QHeaderView.ResizeMode.Stretch)
        for col in (_COL_CUANDO, _COL_TALLAS, _COL_FALTARON, _COL_SOBRARON, _COL_PEDIDO, _COL_ESTADO):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        der.addWidget(self._tabla, 1)

        acciones = QFrame()
        acciones_ly = QHBoxLayout(acciones)
        acciones_ly.setContentsMargins(0, 0, 0, 0)
        acciones_ly.setSpacing(8)
        self._comparar_btn = QPushButton("⇄ Comparar con el anterior")
        self._comparar_btn.clicked.connect(self._abrir_comparativo)
        self._revisar_btn = QPushButton("Revisar / decidir el pedido")
        self._revisar_btn.setObjectName("primario")
        self._revisar_btn.clicked.connect(self._abrir_revision)
        self._hoja_btn = QPushButton("🧾 Hoja de pedido")
        self._hoja_btn.clicked.connect(self._abrir_hoja)
        for b in (self._comparar_btn, self._revisar_btn, self._hoja_btn):
            b.setEnabled(False)
            acciones_ly.addWidget(b)
        acciones_ly.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        acciones_ly.addWidget(cerrar)
        der.addWidget(acciones)

        cuerpo.addLayout(der, 1)
        raiz.addLayout(cuerpo, 1)

    # --------------------------------------------------------------- datos
    def _cargar_alcances(self) -> None:
        from pos_uniformes.services import conteo_jornada_service as jn

        try:
            with self._session_factory() as session:
                self._alcances = jn.tablero_conteos(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo leer el historial", str(exc))
            self._alcances = []
        self._pintar_alcances()

    def _pintar_alcances(self) -> None:
        filtro = self._buscar.text().strip().lower()
        self._lista.clear()
        for i, fila in enumerate(self._alcances):
            if filtro and filtro not in fila.titulo.lower():
                continue
            item = QListWidgetItem(f"{fila.titulo}\n{fila.ultimo.texto()}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._lista.addItem(item)

    def _alcance_elegido(self, actual, _antes=None) -> None:
        if actual is None:
            return
        self._elegido = self._alcances[int(actual.data(Qt.ItemDataRole.UserRole))]
        self._titulo_alcance.setText(self._elegido.titulo)
        self._evolucion_btn.setEnabled(True)
        self._cargar_conteos()

    def _cargar_conteos(self) -> None:
        from pos_uniformes.services import conteo_jornada_service as jn

        if self._elegido is None:
            return
        try:
            with self._session_factory() as session:
                self._conteos = jn.historial_de_alcance(
                    session, self._elegido.escuela_id, self._elegido.tipo_pieza,
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo leer el historial", str(exc))
            self._conteos = []
        self._pintar_conteos()

    def _pintar_conteos(self) -> None:
        self._tabla.setRowCount(len(self._conteos))
        for i, c in enumerate(self._conteos):
            cuando = c.terminada_at.astimezone().strftime("%d/%m/%Y %H:%M") if c.terminada_at is not None and c.terminada_at.tzinfo else (
                c.terminada_at.strftime("%d/%m/%Y %H:%M") if c.terminada_at is not None else ""
            )
            valores = (
                cuando, c.quien, str(c.tallas),
                f"−{c.faltaron}" if c.faltaron else "—",
                f"+{c.sobraron}" if c.sobraron else "—",
                str(c.pedido_piezas) if c.pedido_piezas else "—",
                c.estado,
            )
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col != _COL_QUIEN:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tabla.setItem(i, col, item)
        self._resumen.setText(self._texto_resumen())
        if self._conteos:
            self._tabla.selectRow(0)
        else:
            self._actualizar_botones()

    def _texto_resumen(self) -> str:
        if not self._conteos:
            return "Todavía no se ha contado. Cuando alguien lo cuente, aquí queda su historia."
        veces = len(self._conteos)
        pedido = sum(c.pedido_piezas for c in self._conteos)
        faltaron = sum(c.faltaron for c in self._conteos)
        partes = [f"{veces} conteo{'s' if veces != 1 else ''}"]
        if faltaron:
            partes.append(f"{faltaron} piezas que no aparecieron en total")
        if pedido:
            partes.append(f"{pedido} piezas pedidas a partir de estos conteos")
        return "  ·  ".join(partes)

    # ------------------------------------------------------------ acciones
    def _conteo_actual(self):
        fila = self._tabla.currentRow()
        if 0 <= fila < len(self._conteos):
            return self._conteos[fila]
        return None

    def _conteo_elegido(self) -> None:
        self._actualizar_botones()

    def _actualizar_botones(self) -> None:
        c = self._conteo_actual()
        self._comparar_btn.setEnabled(c is not None)
        self._revisar_btn.setEnabled(c is not None)
        self._hoja_btn.setEnabled(c is not None and c.pedido_piezas > 0)
        if c is not None:
            self._revisar_btn.setText("Revisar / decidir el pedido" if c.revisada_at is None else "Ver el pedido que decidiste")

    def _abrir_comparativo(self) -> None:
        c = self._conteo_actual()
        if c is None:
            return
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoComparativoDialog

        ConteoComparativoDialog(self, jornada_id=c.jornada_id, session_factory=self._session_factory).exec()

    def _abrir_evolucion(self) -> None:
        if self._elegido is None:
            return
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import EscuelaHistoriaDialog

        EscuelaHistoriaDialog(
            self, escuela_id=self._elegido.escuela_id, tipo_pieza=self._elegido.tipo_pieza,
            session_factory=self._session_factory,
        ).exec()

    def _abrir_revision(self) -> None:
        from pos_uniformes.services.conteo_jornada_service import DUENO_CODE, ref
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoRevisionDialog

        c = self._conteo_actual()
        if c is None:
            return
        try:
            with self._session_factory() as session:
                jornada = session.get(ConteoJornada, c.jornada_id)
                foto = ref(jornada) if jornada is not None else None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        if foto is None:
            return
        dlg = ConteoRevisionDialog(self, jornada=foto, revisada_por=DUENO_CODE, session_factory=self._session_factory)
        dlg.exec()
        self._cargar_conteos()

    def _abrir_hoja(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.revision_service import html_pedido, revisar, texto_pedido
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import PedidoHojaDialog

        c = self._conteo_actual()
        if c is None:
            return
        try:
            with self._session_factory() as session:
                jornada = session.get(ConteoJornada, c.jornada_id)
                if jornada is None:
                    return
                revision = revisar(session, jornada)
                texto, html, titulo = texto_pedido(revision), html_pedido(revision), f"Pedido · {revision.titulo}"
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo armar la hoja", str(exc))
            return
        PedidoHojaDialog(self, texto=texto, html=html, titulo=titulo).exec()
