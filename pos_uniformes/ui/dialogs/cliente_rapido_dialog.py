"""Buscador y alta rápida de clientes en Venta Rápida (E1-B).

El diálogo no toca la base: recibe dos funciones (`buscar` y `registrar`) y
solo decide qué mostrar. Así se prueba sin base de datos y el kiosko decide
cómo y cuándo conectarse.

Flujo de alta en 3 pasos: buscar → «Registrar nuevo» → confirmar.
Nunca crea en silencio un cliente con teléfono repetido: muestra las fichas
que coinciden con «Es esta persona» y, aparte, «Es otra persona con el mismo
teléfono», que pide confirmación.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.clientes.identidad_service import (
    ClienteEncontrado,
    CoincidenciasPorConfirmarError,
    TelefonoInvalidoError,
)
from pos_uniformes.ui.styles import kiosko_clientes_styles

Buscar = Callable[[str], list[ClienteEncontrado]]
Registrar = Callable[[str, str, bool], ClienteEncontrado]


def etiqueta_cliente(c: ClienteEncontrado) -> str:
    tel = f" · Tel {c.telefono_enmascarado}" if c.telefono_enmascarado else ""
    return f"{c.nombre} · {c.codigo}{tel}"


class ClienteRapidoDialog(QDialog):
    def __init__(self, parent: QWidget | None, *, buscar: Buscar, registrar: Registrar) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._buscar = buscar
        self._registrar = registrar
        self.elegido: ClienteEncontrado | None = None
        self._pendiente_compartido: tuple[str, str] | None = None

        kiosko_clientes_styles.aplicar(self)
        self.setMinimumSize(600, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        titulo = QLabel("¿Quién compra?")
        titulo.setObjectName("kcTitulo")
        subtitulo = QLabel("Busca a la persona. Si no aparece, regístrala abajo.")
        subtitulo.setObjectName("kcSubtitulo")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.busqueda_input = QLineEdit()
        self.busqueda_input.setPlaceholderText("Nombre, código o últimos dígitos del teléfono")
        self.busqueda_input.setClearButtonEnabled(True)
        self.busqueda_input.returnPressed.connect(self._on_buscar)
        self.buscar_button = QPushButton("Buscar")
        self.buscar_button.setObjectName("kcPrimario")
        self.buscar_button.setAutoDefault(False)
        self.buscar_button.clicked.connect(self._on_buscar)
        fila.addWidget(self.busqueda_input, 1)
        fila.addWidget(self.buscar_button)
        layout.addLayout(fila)

        self.estado_label = QLabel("")
        self.estado_label.setObjectName("kcEstado")
        self.estado_label.setWordWrap(True)
        layout.addWidget(self.estado_label)

        self.resultados = QListWidget()
        self.resultados.setObjectName("kcResultados")
        self.resultados.itemDoubleClicked.connect(lambda _i: self._on_elegir())
        self.vacio_label = QLabel("Aquí aparecen los clientes que encuentres.\nDoble clic o «Es esta persona» para elegir.")
        self.vacio_label.setObjectName("kcVacio")
        self.vacio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio_label.setWordWrap(True)
        self._pila = QStackedWidget()
        self._pila.addWidget(self.vacio_label)
        self._pila.addWidget(self.resultados)
        layout.addWidget(self._pila, 1)

        acciones = QHBoxLayout()
        acciones.setSpacing(10)
        self.elegir_button = QPushButton("Es esta persona")
        self.elegir_button.setObjectName("kcPrimario")
        self.elegir_button.setAutoDefault(False)
        self.elegir_button.clicked.connect(self._on_elegir)
        self.otra_persona_button = QPushButton("Es otra persona con el mismo teléfono")
        self.otra_persona_button.setObjectName("kcFantasma")
        self.otra_persona_button.setAutoDefault(False)
        self.otra_persona_button.setVisible(False)
        self.otra_persona_button.clicked.connect(self._on_otra_persona)
        acciones.addWidget(self.elegir_button)
        acciones.addWidget(self.otra_persona_button)
        acciones.addStretch()
        layout.addLayout(acciones)

        tarjeta = QFrame()
        tarjeta.setObjectName("kcTarjeta")
        alta = QVBoxLayout(tarjeta)
        alta.setContentsMargins(16, 14, 16, 16)
        alta.setSpacing(8)
        seccion = QLabel("REGISTRAR NUEVO")
        seccion.setObjectName("kcSeccion")
        alta.addWidget(seccion)
        campos = QGridLayout()
        campos.setHorizontalSpacing(10)
        campos.setVerticalSpacing(4)
        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Nombre completo")
        self.telefono_input = QLineEdit()
        self.telefono_input.setPlaceholderText("10 dígitos")
        self.telefono_input.setMaximumWidth(200)
        for col, (texto, campo) in enumerate((("Nombre", self.nombre_input), ("Teléfono", self.telefono_input))):
            etiqueta = QLabel(texto)
            etiqueta.setObjectName("kcCampo")
            campos.addWidget(etiqueta, 0, col)
            campos.addWidget(campo, 1, col)
        campos.setColumnStretch(0, 1)
        self.registrar_button = QPushButton("Registrar")
        self.registrar_button.setObjectName("kcSecundario")
        self.registrar_button.setAutoDefault(False)
        self.registrar_button.clicked.connect(lambda _checked=False: self._on_registrar(confirmar=False))
        campos.addWidget(self.registrar_button, 1, 2)
        alta.addLayout(campos)
        layout.addWidget(tarjeta)

        pie = QHBoxLayout()
        cancelar = QPushButton("Cancelar")
        cancelar.setObjectName("kcFantasma")
        cancelar.setAutoDefault(False)
        cancelar.clicked.connect(self.reject)
        pie.addStretch()
        pie.addWidget(cancelar)
        layout.addLayout(pie)
        self._actualizar_botones()
        self.busqueda_input.setFocus()

    # -- vista --------------------------------------------------------------

    def _mostrar(self, clientes: list[ClienteEncontrado]) -> None:
        self.resultados.clear()
        for c in clientes:
            tel = f"  ·  Tel {c.telefono_enmascarado}" if c.telefono_enmascarado else ""
            item = QListWidgetItem(f"{c.nombre}\n{c.codigo}{tel}")
            item.setToolTip(etiqueta_cliente(c))
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.resultados.addItem(item)
        if clientes:
            self.resultados.setCurrentRow(0)
        self._actualizar_botones()

    def _actualizar_botones(self) -> None:
        self.elegir_button.setEnabled(self.resultados.count() > 0)
        self._pila.setCurrentWidget(self.resultados if self.resultados.count() else self.vacio_label)
        self.otra_persona_button.setVisible(self._pendiente_compartido is not None)

    def _avisar(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    # -- acciones -----------------------------------------------------------

    def _on_buscar(self) -> None:
        texto = self.busqueda_input.text().strip()
        self._pendiente_compartido = None
        if not texto:
            self.estado_label.setText("Escribe un nombre, código o los últimos dígitos del teléfono.")
            self._mostrar([])
            return
        try:
            encontrados = self._buscar(texto)
        except Exception as exc:  # noqa: BLE001
            self._avisar("No se pudo buscar", str(exc))
            return
        self.estado_label.setText(
            f"{len(encontrados)} cliente(s) encontrado(s)." if encontrados else "Sin resultados. Puedes registrarlo abajo."
        )
        self._mostrar(encontrados)

    def _on_elegir(self) -> None:
        item = self.resultados.currentItem()
        if item is None:
            return
        self.elegido = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_registrar(self, confirmar: bool = False) -> None:
        nombre = self.nombre_input.text().strip()
        telefono = self.telefono_input.text().strip()
        if not nombre:
            self._avisar("Falta el nombre", "Escribe el nombre completo del cliente.")
            return
        try:
            nuevo = self._registrar(nombre, telefono, bool(confirmar))
        except TelefonoInvalidoError as exc:
            self._avisar("Teléfono inválido", str(exc))
            return
        except CoincidenciasPorConfirmarError as exc:
            self._pendiente_compartido = (nombre, telefono)
            self.estado_label.setText(
                f"{exc} Si es la misma persona, elígela con «Es esta persona». "
                "Si es otra persona con el mismo teléfono, usa el botón de al lado."
            )
            self._mostrar(exc.coincidencias)
            return
        except Exception as exc:  # noqa: BLE001
            self._avisar("No se pudo registrar", str(exc))
            return
        self.elegido = nuevo
        self.accept()

    def _on_otra_persona(self) -> None:
        if self._pendiente_compartido is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Teléfono compartido",
            "¿Confirmas que es OTRA persona que comparte el teléfono? Se registrará una ficha nueva "
            "y quedará constancia de las fichas con el mismo teléfono.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        self._on_registrar(confirmar=True)
