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

from PyQt6.QtCore import QSize, Qt, QTimer
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


#: Búsqueda mientras se escribe: espera a que la empleada deje de teclear.
BUSCAR_AL_ESCRIBIR_MS = 400
MINIMO_PARA_BUSCAR = 3


def iniciales(nombre: str) -> str:
    partes = [p for p in (nombre or "").replace(".", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def sugerencia_de_alta(texto: str) -> tuple[str, str]:
    """(nombre, teléfono) para el alta a partir de lo que se buscó sin éxito."""
    limpio = (texto or "").strip()
    digitos = "".join(ch for ch in limpio if ch.isdigit())
    if digitos and len(digitos) == len(limpio.replace(" ", "").replace("-", "")):
        return "", digitos if len(digitos) == 10 else ""
    if limpio.upper().startswith("CLI-"):
        return "", ""
    return " ".join(p[:1].upper() + p[1:] for p in limpio.split()), ""


class _FilaCliente(QFrame):
    """Una tarjeta por cliente: iniciales, nombre, código y teléfono enmascarado."""

    def __init__(self, c: ClienteEncontrado) -> None:
        super().__init__()
        self.setObjectName("kcFila")
        self.setProperty("sel", False)
        ly = QHBoxLayout(self)
        ly.setContentsMargins(12, 8, 14, 8)
        ly.setSpacing(12)
        avatar = QLabel(iniciales(c.nombre))
        avatar.setObjectName("kcAvatar")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(avatar)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        nombre = QLabel(c.nombre)
        nombre.setObjectName("kcFilaNombre")
        detalle = QLabel(f"{c.codigo}  ·  Tel {c.telefono_enmascarado}" if c.telefono_enmascarado else c.codigo)
        detalle.setObjectName("kcFilaDetalle")
        textos.addWidget(nombre)
        textos.addWidget(detalle)
        ly.addLayout(textos, 1)
        self.check = QLabel("✓")
        self.check.setObjectName("kcFilaCheck")
        self.check.setVisible(False)
        ly.addWidget(self.check)
        for w in (avatar, nombre, detalle, self.check):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def marcar(self, si: bool) -> None:
        self.setProperty("sel", si)
        self.check.setVisible(si)
        self.style().unpolish(self)
        self.style().polish(self)


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
        self.setMinimumSize(620, 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        titulo = QLabel("¿Quién compra?")
        titulo.setObjectName("kcTitulo")
        subtitulo = QLabel("Escribe su nombre, código o los últimos dígitos del teléfono. Si no aparece, regístrala abajo.")
        subtitulo.setWordWrap(True)
        subtitulo.setObjectName("kcSubtitulo")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.busqueda_input = QLineEdit()
        self.busqueda_input.setPlaceholderText("🔎  Ej. Daniel, CLI-000015 o 4287")
        self.busqueda_input.setClearButtonEnabled(True)
        self.busqueda_input.returnPressed.connect(self._on_buscar)
        # Busca sola al dejar de escribir; Enter o «Buscar» siguen sirviendo.
        self._buscar_timer = QTimer(self)
        self._buscar_timer.setSingleShot(True)
        self._buscar_timer.setInterval(BUSCAR_AL_ESCRIBIR_MS)
        self._buscar_timer.timeout.connect(lambda: self._on_buscar(en_vivo=True))
        self.busqueda_input.textEdited.connect(self._al_escribir)
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
        self.resultados.setSpacing(0)
        self.resultados.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.resultados.itemDoubleClicked.connect(lambda _i: self._on_elegir())
        self.resultados.currentRowChanged.connect(lambda _r: self._pintar_seleccion())
        self.vacio_label = QLabel("🔎\n\nAquí aparecen los clientes que encuentres.\nDoble clic o «Es esta persona» para elegir.")
        self.vacio_label.setObjectName("kcVacio")
        self.vacio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio_label.setWordWrap(True)
        self._pila = QStackedWidget()
        self._pila.addWidget(self.vacio_label)
        self._pila.addWidget(self.resultados)
        layout.addWidget(self._pila, 1)

        acciones = QHBoxLayout()
        acciones.setSpacing(10)
        self.elegir_button = QPushButton("✓ Es esta persona")
        self.elegir_button.setObjectName("kcPrimario")
        self.elegir_button.setAutoDefault(False)
        self.elegir_button.clicked.connect(self._on_elegir)
        acciones.addStretch()
        self.reenviar_button = QPushButton("📲 Reenviar credencial")
        self.reenviar_button.setObjectName("kcSecundario")
        self.reenviar_button.setAutoDefault(False)
        self.reenviar_button.setToolTip("Le manda otra vez su credencial por WhatsApp.")
        self.reenviar_button.setVisible(reenviar is not None)
        self.reenviar_button.clicked.connect(self._on_reenviar)
        acciones.addWidget(self.reenviar_button)
        acciones.addWidget(self.elegir_button)
        layout.addLayout(acciones)

        tarjeta = QFrame()
        tarjeta.setObjectName("kcTarjeta")
        alta = QVBoxLayout(tarjeta)
        alta.setContentsMargins(16, 14, 16, 16)
        alta.setSpacing(8)
        seccion = QLabel("＋ REGISTRAR NUEVO")
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
        self.telefono_pista = QLabel("")
        self.telefono_pista.setObjectName("kcPista")
        campos.addWidget(self.telefono_pista, 2, 1)
        self.telefono_input.textChanged.connect(self._pintar_pista_telefono)
        self.nombre_input.returnPressed.connect(self.telefono_input.setFocus)
        self.telefono_input.returnPressed.connect(self._on_registrar)
        alta.addLayout(campos)
        self._nombre_sugerido = ""
        self._pintar_pista_telefono()
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
            # El texto queda para leer y buscar; lo que se ve es la tarjeta.
            item = QListWidgetItem(f"{c.nombre}\n{c.codigo}{tel}")
            item.setToolTip(etiqueta_cliente(c))
            item.setData(Qt.ItemDataRole.UserRole, c)
            item.setSizeHint(QSize(0, 66))
            self.resultados.addItem(item)
            self.resultados.setItemWidget(item, _FilaCliente(c))
        if clientes:
            self.resultados.setCurrentRow(0)
        self._pintar_seleccion()
        self._actualizar_botones()

    def _pintar_seleccion(self) -> None:
        actual = self.resultados.currentRow()
        for fila in range(self.resultados.count()):
            tarjeta = self.resultados.itemWidget(self.resultados.item(fila))
            if isinstance(tarjeta, _FilaCliente):
                tarjeta.marcar(fila == actual)

    def _pintar_pista_telefono(self) -> None:
        n = sum(ch.isdigit() for ch in self.telefono_input.text())
        listo = normalizar_telefono(self.telefono_input.text()) is not None
        self.telefono_pista.setText("✓ Teléfono listo" if listo else f"{n}/10 dígitos")
        self.telefono_pista.setProperty("ok", listo)
        self.telefono_pista.style().unpolish(self.telefono_pista)
        self.telefono_pista.style().polish(self.telefono_pista)

    def _al_escribir(self, texto: str) -> None:
        if len(texto.strip()) >= MINIMO_PARA_BUSCAR:
            self._buscar_timer.start()
        else:
            self._buscar_timer.stop()

    def _actualizar_botones(self) -> None:
        self.elegir_button.setEnabled(self.resultados.count() > 0)
        self.reenviar_button.setEnabled(self.resultados.count() > 0)
        self._pila.setCurrentWidget(self.resultados if self.resultados.count() else self.vacio_label)

    def _avisar(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    # -- acciones -----------------------------------------------------------

    def _on_buscar(self, en_vivo: bool = False) -> None:
        self._buscar_timer.stop()
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
        if encontrados:
            n = len(encontrados)
            self.estado_label.setText(f"{n} cliente{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}.")
        else:
            self.estado_label.setText(f"No encontramos «{texto}». Regístrala abajo ↓")
            self._sugerir_alta(texto, enfocar=not en_vivo)
        self._mostrar(encontrados)

    def _sugerir_alta(self, texto: str, *, enfocar: bool) -> None:
        """Lo que se buscó sin éxito pasa al alta, sin pisar lo que ella ya escribió."""
        nombre, telefono = sugerencia_de_alta(texto)
        if nombre and self.nombre_input.text().strip() in ("", self._nombre_sugerido):
            self.nombre_input.setText(nombre)
            self._nombre_sugerido = nombre
        if telefono and not self.telefono_input.text().strip():
            self.telefono_input.setText(telefono)
        if enfocar:
            vacio = self.nombre_input if not self.nombre_input.text().strip() else self.telefono_input
            vacio.setFocus()

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
