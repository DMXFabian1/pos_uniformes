"""Buscador y alta rápida de clientes en Venta Rápida (E1-B).

El diálogo no toca la base: recibe dos funciones (`buscar` y `registrar`) y
solo decide qué mostrar. Así se prueba sin base de datos y el kiosko decide
cómo y cuándo conectarse.

Flujo de alta en 3 pasos: buscar → «Registrar nuevo» → confirmar.
En el kiosko el teléfono es obligatorio y único (Daniel, 2026-11-10): si no
tiene 10 dígitos o ya hay un cliente con ese número, avisa con un error y no
registra. Las fichas que ya tienen ese número quedan en la lista para elegirlas
con «Es esta persona». El teléfono compartido con confirmación sigue solo en el
POS.
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
    mensaje_telefono_ya_registrado,
)
from pos_uniformes.services.clientes.telefono import normalizar_telefono
from pos_uniformes.ui.styles import kiosko_clientes_styles

Buscar = Callable[[str], list[ClienteEncontrado]]
Registrar = Callable[[str, str, bool], ClienteEncontrado]
Reenviar = Callable[[ClienteEncontrado], None]


def etiqueta_cliente(c: ClienteEncontrado) -> str:
    tel = f" · Tel {c.telefono_enmascarado}" if c.telefono_enmascarado else ""
    return f"{c.nombre} · {c.codigo}{tel}"


class ClienteRapidoDialog(QDialog):
    def __init__(
        self, parent: QWidget | None, *, buscar: Buscar, registrar: Registrar, reenviar: Reenviar | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._buscar = buscar
        self._registrar = registrar
        #: Reenvía la credencial del cliente elegido en la lista, sin ligarlo
        #: a la venta ni cerrar (por si al cliente se le borró; 2026-11-10).
        self._reenviar = reenviar
        self.elegido: ClienteEncontrado | None = None
        #: True si `elegido` se acaba de registrar aquí (no se eligió de la lista).
        self.es_nuevo = False

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
        acciones.addWidget(self.elegir_button)
        self.reenviar_button = QPushButton("📲 Reenviar credencial")
        self.reenviar_button.setObjectName("kcSecundario")
        self.reenviar_button.setAutoDefault(False)
        self.reenviar_button.setToolTip("Le manda otra vez su credencial por WhatsApp.")
        self.reenviar_button.setVisible(reenviar is not None)
        self.reenviar_button.clicked.connect(self._on_reenviar)
        acciones.addWidget(self.reenviar_button)
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
        self.registrar_button.clicked.connect(lambda _checked=False: self._on_registrar())
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
        self.reenviar_button.setEnabled(self.resultados.count() > 0)
        self._pila.setCurrentWidget(self.resultados if self.resultados.count() else self.vacio_label)

    def _avisar(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    # -- acciones -----------------------------------------------------------

    def _on_buscar(self) -> None:
        texto = self.busqueda_input.text().strip()
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

    def _on_reenviar(self) -> None:
        item = self.resultados.currentItem()
        if item is None or self._reenviar is None:
            return
        self._reenviar(item.data(Qt.ItemDataRole.UserRole))

    def _on_registrar(self) -> None:
        nombre = self.nombre_input.text().strip()
        telefono = self.telefono_input.text().strip()
        if not nombre:
            self._avisar("Falta el nombre", "Escribe el nombre completo del cliente.")
            return
        if normalizar_telefono(telefono) is None:
            self._avisar(
                "Teléfono inválido",
                "El teléfono es obligatorio y debe tener 10 dígitos. Sin él no se puede mandar la credencial.",
            )
            self.telefono_input.setFocus()
            return
        try:
            nuevo = self._registrar(nombre, telefono, False)
        except TelefonoInvalidoError as exc:
            self._avisar("Teléfono inválido", str(exc))
            return
        except CoincidenciasPorConfirmarError as exc:
            self._mostrar(exc.coincidencias)
            self.estado_label.setText("Ese teléfono ya está registrado. Si es la misma persona, elígela de la lista.")
            self._avisar("Teléfono ya registrado", mensaje_telefono_ya_registrado(exc.coincidencias))
            return
        except Exception as exc:  # noqa: BLE001
            self._avisar("No se pudo registrar", str(exc))
            return
        self.elegido = nuevo
        self.es_nuevo = True
        self.accept()
