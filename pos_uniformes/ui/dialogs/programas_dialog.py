"""E4-D: ventana «Programas» (Configuración > Clientes, solo ADMIN).

Lista los programas con sus miembros y propuestas, y deja editar nombre,
descripción y estado. No se borran programas: se pausan o cierran.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
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

_logger = logging.getLogger(__name__)

COLUMNAS = ("Programa", "Estado", "Cómo se entra", "Tipo al aprobar", "Vigencia", "Miembros", "Propuestas")
ESTADO_AYUDA = (
    "Pausado o cerrado: ya no se inscribe ni se aprueba a nadie nuevo. "
    "Quien ya es miembro lo sigue siendo."
)


class EditarProgramaDialog(QDialog):
    def __init__(self, parent: QWidget | None, fila: aps.FilaPrograma) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editar {fila.nombre}")
        self.setMinimumWidth(440)
        self.resultado: tuple[str, str, str] | None = None
        ly = QVBoxLayout(self)
        form = QFormLayout()
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
        form.addRow("Vigencia", QLabel(f"{fila.vigencia} (por ahora no se cambia)"))
        ly.addLayout(form)
        ayuda = QLabel(ESTADO_AYUDA)
        ayuda.setWordWrap(True)
        ayuda.setObjectName("subtleLine")
        ly.addWidget(ayuda)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
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
        self.accept()


class ProgramasDialog(QDialog):
    def __init__(self, parent: QWidget | None, session_factory, *, usuario_id: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Programas")
        self.setMinimumSize(820, 360)
        self._session_factory = session_factory
        self._usuario_id = int(usuario_id)
        self.filas: list[aps.FilaPrograma] = []
        ly = QVBoxLayout(self)
        aviso = QLabel("Por ahora los programas son una etiqueta: no cambian precios ni descuentos.")
        aviso.setObjectName("subtleLine")
        ly.addWidget(aviso)
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setObjectName("dataTable")
        self.tabla.doubleClicked.connect(lambda _i: self._editar())
        ly.addWidget(self.tabla, 1)
        self.descripcion = QLabel("")
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
            for c, valor in enumerate((f.nombre, f.estado, f.ingreso, f.tipo_sugerido, f.vigencia,
                                       str(f.miembros), str(f.pendientes))):
                self.tabla.setItem(r, c, QTableWidgetItem(valor))
        self.tabla.resizeColumnsToContents()
        self.editar_button.setEnabled(bool(self.filas))
        if self.filas and not self.tabla.selectedItems():
            self.tabla.selectRow(0)

    def _seleccionada(self) -> aps.FilaPrograma | None:
        filas = {i.row() for i in self.tabla.selectedItems()}
        return self.filas[filas.pop()] if len(filas) == 1 else None

    def _mostrar_descripcion(self) -> None:
        f = self._seleccionada()
        self.descripcion.setText(f.descripcion if f else "")

    def _editar(self) -> None:
        f = self._seleccionada()
        if f is None:
            return
        dialogo = EditarProgramaDialog(self, f)
        if dialogo.exec() != int(QDialog.DialogCode.Accepted) or dialogo.resultado is None:
            return
        nombre, descripcion, estado = dialogo.resultado
        try:
            with self._session_factory() as session:
                aps.editar_programa(session, usuario_id=self._usuario_id, clave=f.clave,
                                    nombre=nombre, descripcion=descripcion, estado=estado)
                session.commit()
        except (ms.NoSePuede, PermissionError) as exc:
            QMessageBox.warning(self, "Programas", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Programas: no se pudo guardar %s", f.clave)
            QMessageBox.critical(self, "Programas", f"No se pudo guardar.\n\n{exc}")
            return
        self.recargar()
