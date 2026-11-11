"""E4-D: ventana «Programas» (Configuración > Clientes, solo ADMIN).

Lista los programas con sus miembros y propuestas, y deja editar nombre,
descripción y estado. No se borran programas: se pausan o cierran.
"""

from __future__ import annotations

import logging
from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.fidelizacion import admin_programas_service as aps
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.ui.styles import clientes_styles

_logger = logging.getLogger(__name__)

COLUMNAS = ("Programa", "Monedero", "Estado", "Cómo se entra", "Tipo al aprobar", "Vigencia", "Miembros", "Propuestas")
_COL_ESTADO, _COL_MIEMBROS, _COL_PROPUESTAS = 2, 6, 7
#: Color de la columna Estado: (fondo, letra).
ESTADO_TONOS = {
    "Activo": ("#e5f2eb", "#245241"),
    "Pausado": ("#fbf0cf", "#8a5a00"),
    "Cerrado": ("#ece8e1", "#6e675f"),
}
ESTADO_AYUDA = (
    "Pausado o cerrado: ya no se inscribe ni se aprueba a nadie nuevo. "
    "Quien ya es miembro lo sigue siendo."
)


class EditarProgramaDialog(QDialog):
    def __init__(self, parent: QWidget | None, fila: aps.FilaPrograma) -> None:
        super().__init__(parent)
        clientes_styles.aplicar(self)
        self.setWindowTitle(f"Editar {fila.nombre}")
        self.setMinimumWidth(480)
        self.resultado: tuple[str, str, str] | None = None
        #: E5-A: el % de Monedero elegido (None = sin cambio).
        self.tasa_resultado: float | None = None
        self._tasa_original = float(fila.tasa)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(18, 18, 18, 14)
        ly.setSpacing(12)
        titulo = QLabel(f"Editar {fila.nombre}")
        titulo.setObjectName("cliTitulo")
        ly.addWidget(titulo)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.nombre_input = QLineEdit(fila.nombre)
        self.descripcion_input = QPlainTextEdit(fila.descripcion)
        self.descripcion_input.setFixedHeight(80)
        self.estado_combo = QComboBox()
        for estado in aps.ESTADOS_EDITABLES:
            self.estado_combo.addItem(aps.ESTADO_ETIQUETAS[estado], estado)
        actual = self.estado_combo.findText(fila.estado)
        self.estado_combo.setCurrentIndex(max(0, actual))
        form.addRow("Nombre", self.nombre_input)
        form.addRow("Descripción", self.descripcion_input)
        form.addRow("Estado", self.estado_combo)
        self.tasa_input = QDoubleSpinBox()
        self.tasa_input.setRange(0, 100)
        self.tasa_input.setDecimals(1)
        self.tasa_input.setSingleStep(0.5)
        self.tasa_input.setSuffix(" %")
        self.tasa_input.setValue(self._tasa_original)
        self.tasa_input.setToolTip("De cada compra, este % va al Monedero del miembro. Aplica desde que guardas.")
        form.addRow("Monedero", self.tasa_input)
        form.addRow("Vigencia", QLabel(f"{fila.vigencia} (por ahora no se cambia)"))
        ly.addLayout(form)
        ayuda = QLabel(ESTADO_AYUDA)
        ayuda.setWordWrap(True)
        ayuda.setObjectName("cliNota")
        ly.addWidget(ayuda)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.setObjectName("toolbarGhostButton")
        cancelar.clicked.connect(self.reject)
        self.guardar_button = QPushButton("Guardar")
        self.guardar_button.setObjectName("toolbarPrimaryButton")
        self.guardar_button.clicked.connect(self._guardar)
        for b in (cancelar, self.guardar_button):
            b.setAutoDefault(False)
            botones.addWidget(b)
        ly.addLayout(botones)

    def _guardar(self) -> None:
        self.resultado = (
            self.nombre_input.text().strip(),
            self.descripcion_input.toPlainText().strip(),
            str(self.estado_combo.currentData()),
        )
        tasa = round(float(self.tasa_input.value()), 2)
        self.tasa_resultado = None if abs(tasa - self._tasa_original) < 0.005 else tasa
        self.accept()


class ProgramasDialog(QDialog):
    def __init__(self, parent: QWidget | None, session_factory, *, usuario_id: int) -> None:
        super().__init__(parent)
        clientes_styles.aplicar(self)
        self.setWindowTitle("Programas")
        self.setMinimumSize(900, 460)
        self._session_factory = session_factory
        self._usuario_id = int(usuario_id)
        self.filas: list[aps.FilaPrograma] = []
        ly = QVBoxLayout(self)
        ly.setContentsMargins(18, 18, 18, 14)
        ly.setSpacing(12)
        encabezado = QFrame()
        encabezado.setObjectName("cliHeaderCard")
        ly_enc = QHBoxLayout(encabezado)
        ly_enc.setContentsMargins(18, 14, 18, 14)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel("Programas de fidelización")
        titulo.setObjectName("cliTitulo")
        subtitulo = QLabel("Por ahora los programas son una etiqueta: no cambian precios ni descuentos.")
        subtitulo.setObjectName("cliSubtitulo")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        ly_enc.addLayout(textos, 1)
        self.resumen_label = QLabel("")
        self.resumen_label.setObjectName("cliContador")
        ly_enc.addWidget(self.resumen_label, 0, Qt.AlignmentFlag.AlignVCenter)
        ly.addWidget(encabezado)
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(40)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setObjectName("cliTabla")
        self.tabla.doubleClicked.connect(lambda _i: self._editar())
        ly.addWidget(self.tabla, 1)
        self.descripcion = QLabel("")
        self.descripcion.setObjectName("cliNota")
        self.descripcion.setWordWrap(True)
        ly.addWidget(self.descripcion)
        self.tabla.itemSelectionChanged.connect(self._mostrar_descripcion)
        pie = QHBoxLayout()
        self.editar_button = QPushButton("Editar…")
        self.editar_button.setObjectName("toolbarSecondaryButton")
        self.editar_button.clicked.connect(self._editar)
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("toolbarGhostButton")
        cerrar.clicked.connect(self.reject)
        for b in (self.editar_button, cerrar):
            b.setAutoDefault(False)
        pie.addWidget(self.editar_button)
        pie.addStretch()
        pie.addWidget(cerrar)
        ly.addLayout(pie)
        self.recargar()

    def recargar(self) -> None:
        try:
            with self._session_factory() as session:
                self.filas = aps.listar_programas(session, usuario_id=self._usuario_id)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Programas: no se pudieron leer")
            self.filas = []
            self.descripcion.setText(f"No se pudieron leer los programas: {exc}")
        self.tabla.setRowCount(len(self.filas))
        for r, f in enumerate(self.filas):
            for c, valor in enumerate((f.nombre, f.monedero, f.estado, f.ingreso, f.tipo_sugerido, f.vigencia,
                                       str(f.miembros), str(f.pendientes))):
                item = QTableWidgetItem(valor)
                if c == 0:
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                if c == _COL_ESTADO and valor in ESTADO_TONOS:
                    fondo, letra = ESTADO_TONOS[valor]
                    item.setBackground(QColor(fondo))
                    item.setForeground(QColor(letra))
                if c in (1, _COL_ESTADO, _COL_MIEMBROS, _COL_PROPUESTAS):
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                if c == _COL_PROPUESTAS and f.pendientes:
                    item.setForeground(QColor("#8a5a00"))
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                self.tabla.setItem(r, c, item)
        self.tabla.resizeColumnsToContents()
        self.tabla.horizontalHeader().setStretchLastSection(True)
        miembros = sum(f.miembros for f in self.filas)
        pendientes = sum(f.pendientes for f in self.filas)
        self.resumen_label.setText(
            f"{miembros} miembro{'s' if miembros != 1 else ''} · "
            f"{pendientes} propuesta{'s' if pendientes != 1 else ''}"
        )
        self.editar_button.setEnabled(bool(self.filas))
        if self.filas and not self.tabla.selectedItems():
            self.tabla.selectRow(0)

    def _seleccionada(self) -> aps.FilaPrograma | None:
        filas = {i.row() for i in self.tabla.selectedItems()}
        return self.filas[filas.pop()] if len(filas) == 1 else None

    def _mostrar_descripcion(self) -> None:
        f = self._seleccionada()
        if f is None:
            self.descripcion.setText("")
            return
        texto = f"<b>{escape(f.nombre)}</b>"
        if f.descripcion:
            texto += f" — {escape(f.descripcion)}"
        self.descripcion.setText(texto)

    def _editar(self) -> None:
        f = self._seleccionada()
        if f is None:
            return
        dialogo = EditarProgramaDialog(self, f)
        if dialogo.exec() != int(QDialog.DialogCode.Accepted) or dialogo.resultado is None:
            return
        nombre, descripcion, estado = dialogo.resultado
        tasa = getattr(dialogo, "tasa_resultado", None)
        try:
            with self._session_factory() as session:
                aps.editar_programa(session, usuario_id=self._usuario_id, clave=f.clave,
                                    nombre=nombre, descripcion=descripcion, estado=estado, tasa=tasa)
                session.commit()
        except (ms.NoSePuede, PermissionError) as exc:
            QMessageBox.warning(self, "Programas", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Programas: no se pudo guardar %s", f.clave)
            QMessageBox.critical(self, "Programas", f"No se pudo guardar.\n\n{exc}")
            return
        self.recargar()
