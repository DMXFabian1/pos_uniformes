"""«Prenda general o de temporada» en «Nueva prenda» (tanda 4 del alta, 2026-11-15).

Calcetas, batas, chalecos de temporada… sin escuela ni uniforme. Una sola
pantalla, a la izquierda lo que se escribe y a la derecha la ficha «Así queda»:

- NOMBRE. Si hay una prenda general parecida, se ofrece «Igual que esta,
  otro modelo» (copia tallas, precios, marca y tipo; solo cambia el nombre).
  Si las tallas del modelo no son uno de los juegos, se copian tal cual
  («Como el modelo: CH · MD · GD»), con sus precios.
- TALLAS: un juego cerrado (Unitalla, Infantil·Adulto, Infantil·Juvenil·Adulto
  o CH·MD·GD·EXG).
- PRECIO: uno para todas o, con «Precio por talla», uno por talla. Llegan hoy
  y Costo son opcionales.
- MARCA y COLOR se eligen siempre (no se adivinan). PIEZA y GÉNERO se
  proponen con lo que dice el nombre («Chaleco Mujer…») y TIPO DE PRENDA con
  la pieza; lo que se elige a mano ya no se toca. La CATEGORÍA se llena sola
  con la que más usa ese tipo (casi siempre es el mismo nombre) y solo se
  enseña con «Cambiar».

El plan lo arma `alta_prenda_service.planear_general` (el mismo motor que la
prenda de escuela); aquí solo hay pantalla. Lo que todavía falta (el color,
la pieza…) se dice en ámbar en la barra, no en rojo en la ficha.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import nueva_prenda_service as nps
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import ACCION_CREAR, ACCION_DEJAR, ACCION_USAR
from pos_uniformes.ui.helpers.inventario_ficha_prenda import Flujo
from pos_uniformes.ui.helpers.nueva_prenda_ficha import FichaAsiQueda
from pos_uniformes.ui.helpers.nueva_prenda_tallas import leer_cantidad, leer_precio, texto_precio
from pos_uniformes.ui.styles.nueva_prenda_styles import ANCHO_FICHA

ELIGE = "Elige…"
SOLA = "Se llena sola"
REBOTE_MS = 300
#: Lo que solo dice «falta elegir»: va en la barra (ámbar), no en la ficha (rojo).
PENDIENTES = ("Elige ", "Falta la ", "Falta el ", "Marca al menos")
#: Las tallas del modelo cuando no son uno de los juegos de un toque.
JUEGO_MODELO = "Como el modelo"
NOTA_PIE = "Pieza, género y tipo salen del nombre (cámbialos si no van). Llegan hoy y Costo son opcionales."


def _etiqueta(nombre: str, texto: str = "", *, envolver: bool = False) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName(nombre)
    etiqueta.setWordWrap(envolver)
    return etiqueta


def _boton(nombre: str, texto: str) -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName(nombre)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    boton.setAutoDefault(False)
    return boton


def _combo(opciones, *, editable: bool = False, primero: str | None = ELIGE) -> QComboBox:
    combo = QComboBox()
    combo.setObjectName("npCombo")
    combo.setEditable(editable)
    if editable:
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    if primero is not None:
        combo.addItem(primero)
    combo.addItems(list(opciones))
    combo.setMinimumWidth(150)
    return combo


def _texto(combo: QComboBox) -> str:
    texto = valores.limpiar(combo.currentText())
    return "" if texto in (ELIGE, "—", SOLA) else texto


def _poner_combo(combo: QComboBox, texto: str | None) -> None:
    combo.blockSignals(True)
    texto = texto or ""
    if texto and combo.findText(texto) < 0:
        combo.addItem(texto)
    if texto:
        combo.setCurrentText(texto)
    else:
        combo.setCurrentIndex(0)
    combo.blockSignals(False)


def es_pendiente(error: str) -> bool:
    return error.startswith(PENDIENTES)


class FormularioGeneral(QWidget):
    """La pantalla de la prenda general. Avisa con `cambio` cada vez que hay plan nuevo."""

    cambio = pyqtSignal()
    #: «Usar el formulario anterior» (por si acaso, como en la tanda 3).
    anterior = pyqtSignal()

    def __init__(self, *, con_sesion: Callable[[Callable[[Any], Any]], Any], preguntar,
                 confirmar_marca: Callable[[QWidget, str], bool] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("npPaso")
        self.con_sesion = con_sesion
        self.preguntar = preguntar
        self.confirmar_marca = confirmar_marca or _confirmar_marca
        self.ops = nps.Opciones()
        self.plan: alta.PlanPrenda | None = None
        self.parecidas: list[alta.Parecida] = []
        self.modelo: alta.Parecida | None = None
        self.confirmados: list[str] = []
        self.color_elegido = ""
        self.juego: str | None = None
        self.tallas_modelo: tuple[str, ...] = ()
        #: Combos que la persona eligió a mano: la sugerencia del nombre ya no los toca.
        self.a_mano: set[str] = set()
        self._sugerido_para = ""
        self.por_talla = False
        self.campos: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        self._buscado = ""

        caja = QHBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(16)
        scroll = QScrollArea()
        scroll.setObjectName("npScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        vista = QWidget()
        vista.setObjectName("npScrollVista")
        izq = QVBoxLayout(vista)
        izq.setContentsMargins(0, 0, 8, 0)
        izq.setSpacing(10)
        scroll.setWidget(vista)
        self.scroll = scroll
        caja.addWidget(scroll, 1)

        # NOMBRE y las parecidas
        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self._titulo("NOMBRE"))
        self.nombre = QLineEdit()
        self.nombre.setObjectName("npCampo")
        self.nombre.setPlaceholderText("Como va en la etiqueta: «Chaleco Mujer KY18005», «Calceta Blanca»")
        self.nombre.textChanged.connect(lambda _t: self.rebote.start())
        fila.addWidget(self.nombre, 1)
        izq.addLayout(fila)
        self.caja_parecidas = QFrame()
        self.caja_parecidas.setObjectName("npParecida")
        self.lista_parecidas = QVBoxLayout(self.caja_parecidas)
        self.lista_parecidas.setContentsMargins(14, 8, 14, 8)
        self.lista_parecidas.setSpacing(4)
        self.caja_parecidas.hide()
        izq.addWidget(self.caja_parecidas)
        self.fila_modelo = QHBoxLayout()
        self.texto_modelo = _etiqueta("npModelo", envolver=True)
        self.quitar_modelo = _boton("npEnlace", "Quitar")
        self.quitar_modelo.clicked.connect(lambda: self.usar_modelo(None))
        self.fila_modelo.addWidget(self.texto_modelo, 1)
        self.fila_modelo.addWidget(self.quitar_modelo)
        izq.addLayout(self.fila_modelo)
        self.texto_modelo.hide()
        self.quitar_modelo.hide()

        # TALLAS (en renglones si la ventana es angosta: 1366×768 a 125 %)
        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self._titulo("TALLAS"), 0, Qt.AlignmentFlag.AlignTop)
        caja_juegos = QWidget()
        caja_juegos.setObjectName("npScrollVista")
        flujo = Flujo(caja_juegos, espacio=8)
        self.grupo_juegos = QButtonGroup(self)
        self.grupo_juegos.setExclusive(True)
        self.juegos: dict[str, QPushButton] = {}
        for nombre in valores.JUEGOS_TALLAS:
            boton = _boton("npJuego", nombre)
            boton.setCheckable(True)
            boton.clicked.connect(lambda _=False, n=nombre: self.elegir_juego(n))
            self.grupo_juegos.addButton(boton)
            self.juegos[nombre] = boton
            flujo.addWidget(boton)
        self.boton_modelo = _boton("npJuego", JUEGO_MODELO)
        self.boton_modelo.setCheckable(True)
        self.boton_modelo.clicked.connect(lambda _=False: self.elegir_juego(JUEGO_MODELO))
        self.boton_modelo.hide()
        self.grupo_juegos.addButton(self.boton_modelo)
        self.juegos[JUEGO_MODELO] = self.boton_modelo
        flujo.addWidget(self.boton_modelo)
        fila.addWidget(caja_juegos, 1)
        izq.addLayout(fila)

        # PRECIO
        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self._titulo("PRECIO"))
        self.precio = QLineEdit()
        self.precio.setObjectName("npCampo")
        self.precio.setPlaceholderText("$")
        self.precio.setFixedWidth(110)
        self.precio.textChanged.connect(lambda _t: self.rebote.start())
        fila.addWidget(self.precio)
        self.nota_precio = _etiqueta("npNotaChica", "el mismo para todas las tallas")
        fila.addWidget(self.nota_precio)
        self.boton_por_talla = _boton("npEnlace", "Precio por talla")
        self.boton_por_talla.clicked.connect(lambda: self.precio_por_talla(not self.por_talla))
        fila.addWidget(self.boton_por_talla)
        fila.addStretch(1)
        izq.addLayout(fila)

        self.tabla = QFrame()
        self.tabla.setObjectName("npTallas")
        self.rejilla = QGridLayout(self.tabla)
        self.rejilla.setContentsMargins(16, 10, 16, 10)
        self.rejilla.setHorizontalSpacing(18)
        self.rejilla.setVerticalSpacing(6)
        self.tabla.hide()
        izq.addWidget(self.tabla)

        # MARCA, COLOR, TIPO, PIEZA, GÉNERO, COSTO (y la categoría, plegada)
        datos = QGridLayout()
        datos.setHorizontalSpacing(12)
        datos.setVerticalSpacing(8)
        self.marca = _combo((), editable=True)
        self.color = _combo((), editable=True)
        self.tipo_prenda = _combo(())
        self.pieza = _combo(())
        self.categoria = _combo((), primero=SOLA)
        self.genero = _combo((), primero="—")
        self.costo = QLineEdit()
        self.costo.setObjectName("npCampo")
        self.costo.setPlaceholderText("$ por pieza (opcional)")
        for i, (titulo, w) in enumerate((("MARCA", self.marca), ("COLOR", self.color),
                                         ("TIPO DE PRENDA", self.tipo_prenda), ("PIEZA", self.pieza),
                                         ("GÉNERO", self.genero), ("COSTO", self.costo))):
            datos.addWidget(self._titulo(titulo), i // 2, (i % 2) * 2)
            datos.addWidget(w, i // 2, (i % 2) * 2 + 1)
        # La categoría casi siempre es el tipo de prenda: se llena sola y solo
        # se enseña si se pide (antes salían dos combos con «Temporada»).
        self.titulo_categoria = self._titulo("CATEGORÍA")
        datos.addWidget(self.titulo_categoria, 3, 0)
        datos.addWidget(self.categoria, 3, 1)
        self.titulo_categoria.hide()
        self.categoria.hide()
        datos.setColumnStretch(1, 1)
        datos.setColumnStretch(3, 1)
        izq.addLayout(datos)
        fila = QHBoxLayout()
        fila.setSpacing(6)
        self.nota_categoria = _etiqueta("npNotaChica")
        self.boton_categoria = _boton("npEnlace", "Cambiar")
        self.boton_categoria.clicked.connect(self.mostrar_categoria)
        fila.addWidget(self.nota_categoria)
        fila.addWidget(self.boton_categoria)
        fila.addStretch(1)
        # «Usar el formulario anterior» en el mismo renglón: a 1366×768 todo cabe sin desplazar.
        self.boton_anterior = _boton("npEnlace", "Usar el formulario anterior")
        self.boton_anterior.clicked.connect(self.anterior.emit)
        fila.addWidget(self.boton_anterior)
        izq.addLayout(fila)
        self.marca.activated.connect(lambda _i: self._al_marca())
        self.marca.lineEdit().editingFinished.connect(self._al_marca)
        self.color.activated.connect(lambda _i: self._al_color())
        self.color.lineEdit().editingFinished.connect(self._al_color)
        for nombre, combo in (("tipo_prenda", self.tipo_prenda), ("pieza", self.pieza),
                              ("categoria", self.categoria), ("genero", self.genero)):
            combo.activated.connect(lambda _i, n=nombre: self._elegido_a_mano(n))
        self.costo.textChanged.connect(lambda _t: self.rebote.start())
        izq.addWidget(_etiqueta("npNotaChica", NOTA_PIE, envolver=True))
        izq.addStretch(1)

        self.ficha = FichaAsiQueda()
        scroll_ficha = QScrollArea()
        scroll_ficha.setObjectName("npScroll")
        scroll_ficha.setWidgetResizable(True)
        scroll_ficha.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_ficha.setFrameShape(QFrame.Shape.NoFrame)
        scroll_ficha.setWidget(self.ficha)
        scroll_ficha.setFixedWidth(ANCHO_FICHA)
        self.scroll_ficha = scroll_ficha
        caja.addWidget(scroll_ficha)

        self.rebote = QTimer(self)
        self.rebote.setSingleShot(True)
        self.rebote.setInterval(REBOTE_MS)
        self.rebote.timeout.connect(self.replanear)

    @staticmethod
    def _titulo(texto: str) -> QLabel:
        etiqueta = _etiqueta("npEtiqueta", texto)
        etiqueta.setMinimumWidth(96)
        return etiqueta

    # ── Opciones y arranque ───────────────────────────────────────────────
    def poner_opciones(self, ops: nps.Opciones) -> None:
        self.ops = ops
        for combo, lista in ((self.marca, ops.marcas), (self.color, ops.colores),
                             (self.tipo_prenda, ops.tipos_prenda), (self.pieza, ops.piezas),
                             (self.categoria, ops.categorias), (self.genero, ops.generos)):
            primero = combo.itemText(0)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(primero)
            combo.addItems(list(lista))
            combo.blockSignals(False)

    def empezar(self) -> None:
        """Todo en blanco (al entrar o con «Otra prenda general»)."""
        self.rebote.stop()
        self.modelo = None
        self.confirmados = []
        self.color_elegido = ""
        self.juego = None
        self.tallas_modelo = ()
        self.a_mano = set()
        self._sugerido_para = ""
        self.boton_modelo.hide()
        self.titulo_categoria.hide()
        self.categoria.hide()
        self.boton_categoria.show()
        self._buscado = ""
        self.parecidas = []
        self.nombre.blockSignals(True)
        self.nombre.clear()
        self.nombre.blockSignals(False)
        for w in (self.precio, self.costo):
            w.blockSignals(True)
            w.clear()
            w.blockSignals(False)
        for combo in (self.marca, self.color, self.tipo_prenda, self.pieza, self.categoria, self.genero):
            _poner_combo(combo, None)
        self.grupo_juegos.setExclusive(False)
        for boton in self.juegos.values():
            boton.setChecked(False)
        self.grupo_juegos.setExclusive(True)
        self.precio_por_talla(False, replanear=False)
        self._armar_tabla({})
        self._pintar_parecidas()
        self._pintar_modelo()
        self.replanear()
        self.nombre.setFocus()

    # ── Lo que se toca ────────────────────────────────────────────────────
    def escribir_nombre(self, texto: str) -> None:
        self.nombre.setText(texto)
        self.replanear()

    def _elegido_a_mano(self, nombre: str) -> None:
        self.a_mano.add(nombre)
        self.replanear()

    def mostrar_categoria(self) -> None:
        self.titulo_categoria.show()
        self.categoria.show()
        self.boton_categoria.hide()

    def elegir_juego(self, juego: str, precios: dict | None = None) -> None:
        self.juego = juego
        self.juegos[juego].setChecked(True)
        anteriores = {t: (p.text(), l.text()) for t, (p, l) in self.campos.items()}
        self._armar_tabla(anteriores, precios)
        self.replanear()

    def precio_por_talla(self, valor: bool, *, replanear: bool = True) -> None:
        self.por_talla = valor
        self.boton_por_talla.setText("Mismo precio para todas" if valor else "Precio por talla")
        self.precio.setEnabled(not valor)
        self.nota_precio.setText("se escribe abajo, talla por talla" if valor else "el mismo para todas las tallas")
        if valor:
            unico = self.precio.text()
            for p, _l in self.campos.values():
                if not p.text():
                    p.setText(unico)
        for p, _l in self.campos.values():
            p.setVisible(valor)
        if self.campos:
            self.titulo_precio.setVisible(valor)
        if replanear:
            self.replanear()

    def _armar_tabla(self, anteriores: dict, precios: dict | None = None) -> None:
        while self.rejilla.count():
            item = self.rejilla.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.campos = {}
        tallas = self.tallas_elegidas()
        self.tabla.setVisible(bool(tallas))
        if not tallas:
            return
        self.rejilla.addWidget(_etiqueta("npColTitulo", "TALLA"), 0, 0)
        self.titulo_precio = _etiqueta("npColTitulo", "PRECIO")
        self.rejilla.addWidget(self.titulo_precio, 0, 1)
        self.rejilla.addWidget(_etiqueta("npColTitulo", "LLEGAN HOY"), 0, 2)
        for i, talla in enumerate(tallas, start=1):
            self.rejilla.addWidget(_etiqueta("npTallaGeneral", talla), i, 0)
            precio = QLineEdit()
            precio.setObjectName("npPrecio")
            precio.setPlaceholderText("$")
            precio.setFixedWidth(100)
            llegan = QLineEdit()
            llegan.setObjectName("npLlegan")
            llegan.setPlaceholderText("0")
            llegan.setFixedWidth(80)
            antes = anteriores.get(talla, ("", ""))
            de_modelo = (precios or {}).get(talla)
            precio.setText(texto_precio(de_modelo) if de_modelo is not None else antes[0])
            llegan.setText(antes[1])
            precio.textChanged.connect(lambda _t: self.rebote.start())
            llegan.textChanged.connect(lambda _t: self.rebote.start())
            precio.setVisible(self.por_talla)
            self.rejilla.addWidget(precio, i, 1)
            self.rejilla.addWidget(llegan, i, 2)
            self.campos[talla] = (precio, llegan)
        self.rejilla.setColumnStretch(3, 1)
        self.titulo_precio.setVisible(self.por_talla)

    def _al_marca(self) -> None:
        texto = _texto(self.marca)
        if not texto:
            self.replanear()
            return
        conocida = next((m for m in self.ops.marcas if valores.normalizar(m) == valores.normalizar(texto)), None)
        if conocida:
            _poner_combo(self.marca, conocida)
        elif texto not in self.confirmados:
            if self.confirmar_marca(self, texto):
                self.confirmados.append(texto)
            else:
                _poner_combo(self.marca, None)
        self.replanear()

    def _al_color(self) -> None:
        texto = _texto(self.color)
        if not texto or texto == self.color_elegido:
            self.replanear()
            return
        elegido = self._revisar_color(texto)
        if elegido is None:
            _poner_combo(self.color, self.color_elegido or None)
        else:
            self.elegir_color(elegido)
            return
        self.replanear()

    def _revisar_color(self, texto: str) -> str | None:
        if texto in self.ops.colores:
            return texto
        revision = valores.revisar_valor(valores.CAMPO_COLOR, texto, self.ops.usos_color or {})
        if not revision.necesita_pregunta:
            return revision.valor
        eleccion = self.preguntar(self, revision, True)
        if eleccion.accion == ACCION_USAR:
            return eleccion.valor
        if eleccion.accion == ACCION_DEJAR:
            return revision.escrito
        if eleccion.accion == ACCION_CREAR:
            self.confirmados.append(revision.escrito)
            return revision.escrito
        return None

    def elegir_color(self, color: str) -> None:
        self.color_elegido = color
        _poner_combo(self.color, color)
        self.replanear()

    def elegir(self, combo: QComboBox, texto: str) -> None:
        """Para pruebas: elige en un combo cerrado, como a mano."""
        _poner_combo(combo, texto)
        for nombre in ("tipo_prenda", "pieza", "categoria", "genero"):
            if getattr(self, nombre) is combo:
                self.a_mano.add(nombre)
        self.replanear()

    def _sugerir(self) -> None:
        """Pieza y género desde el nombre, y el tipo desde la pieza. Solo lo que
        no se eligió a mano ni vino de un modelo; el color nunca."""
        texto = valores.limpiar(self.nombre.text())
        if texto == self._sugerido_para or self.modelo is not None:
            return
        self._sugerido_para = texto
        pieza, genero = alta.sugerir_de_nombre(texto, self.ops.piezas, self.ops.generos)
        if "pieza" not in self.a_mano:
            _poner_combo(self.pieza, pieza)
        if "genero" not in self.a_mano:
            _poner_combo(self.genero, genero)
        if "tipo_prenda" not in self.a_mano:
            pieza = _texto(self.pieza)
            try:
                tipo = self.con_sesion(lambda s: alta.tipo_prenda_para(s, pieza)) if pieza else None
            except Exception:  # noqa: BLE001 - sin sugerencia, se elige a mano
                tipo = None
            if tipo is not None and self.tipo_prenda.findText(tipo) < 0:
                tipo = None  # solo de la lista cerrada
            _poner_combo(self.tipo_prenda, tipo)

    # ── «Igual que esta, otro modelo» ─────────────────────────────────────
    def _buscar_parecidas(self) -> None:
        texto = valores.limpiar(self.nombre.text())
        if texto == self._buscado:
            return
        self._buscado = texto
        try:
            self.parecidas = self.con_sesion(lambda s: alta.parecidas_generales(s, texto)) if texto else []
        except Exception:  # noqa: BLE001 - sin sugerencias, se sigue escribiendo
            self.parecidas = []
        if self.modelo is not None:
            self.parecidas = [p for p in self.parecidas if p.producto_id != self.modelo.producto_id]
        self._pintar_parecidas()

    def _pintar_parecidas(self) -> None:
        while self.lista_parecidas.count():
            item = self.lista_parecidas.takeAt(0)
            if item.layout() is not None:
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget() is not None:
                        sub.widget().deleteLater()
            elif item.widget() is not None:
                item.widget().deleteLater()
        self.botones_parecidas: dict[int, QPushButton] = {}
        if not self.parecidas or self.modelo is not None:
            self.caja_parecidas.hide()
            return
        self.lista_parecidas.addWidget(_etiqueta("npNotaChica", "Ya hay una parecida:"))
        for p in self.parecidas:
            fila = QHBoxLayout()
            fila.addWidget(_etiqueta("npTiene", f"{p.nombre} · {p.texto}", envolver=True), 1)
            boton = _boton("npEnlace", "Igual que esta, otro modelo")
            boton.clicked.connect(lambda _=False, pid=p.producto_id: self.usar_parecida(pid))
            fila.addWidget(boton)
            self.lista_parecidas.addLayout(fila)
            self.botones_parecidas[p.producto_id] = boton
        self.caja_parecidas.show()

    def usar_parecida(self, producto_id: int) -> None:
        datos = self.con_sesion(lambda s: alta.datos_de_modelo(s, producto_id))
        self.usar_modelo(datos)

    def usar_modelo(self, datos: alta.Parecida | None) -> None:
        self.modelo = datos
        if datos is not None:
            tallas = [t for t, _p in datos.tallas]
            juego = next((j for j, ts in valores.JUEGOS_TALLAS.items() if list(ts) == tallas), None)
            precios = datos.precios
            if juego is None and tallas:
                # Tallas que no son un juego (CH·MD·GD, 2·4·6…): se copian tal cual.
                juego = JUEGO_MODELO
                self.tallas_modelo = tuple(tallas)
                self.boton_modelo.setText(f"{JUEGO_MODELO}: {' · '.join(tallas)}")
                self.boton_modelo.show()
            else:
                self.boton_modelo.hide()
            if juego:
                distintos = len(set(precios.values())) > 1
                self.precio_por_talla(distintos, replanear=False)
                if not distintos and precios:
                    self.precio.setText(texto_precio(next(iter(precios.values()))))
                self.elegir_juego(juego, precios if distintos else None)
            for combo, valor in ((self.marca, datos.marca), (self.tipo_prenda, datos.tipo_prenda),
                                 (self.pieza, datos.tipo_pieza), (self.categoria, datos.categoria),
                                 (self.genero, datos.genero)):
                _poner_combo(combo, valor)
            # El color no se copia: el modelo nuevo casi siempre es otro color.
            self.parecidas = []
        else:
            self._sugerido_para = ""  # sin modelo, el nombre vuelve a proponer pieza y género
            if self.juego == JUEGO_MODELO:
                # Sus tallas ya no valen: a elegir un juego otra vez.
                self.juego = None
                self.tallas_modelo = ()
                self.grupo_juegos.setExclusive(False)
                self.boton_modelo.setChecked(False)
                self.grupo_juegos.setExclusive(True)
                self._armar_tabla({})
            self.boton_modelo.hide()
        self._pintar_parecidas()
        self._pintar_modelo()
        self.replanear()

    def _pintar_modelo(self) -> None:
        m = self.modelo
        self.texto_modelo.setText(f"Igual que: {m.nombre} ({m.texto}). Solo cambian el nombre y el color."
                                  if m else "")
        self.texto_modelo.setVisible(m is not None)
        self.quitar_modelo.setVisible(m is not None)

    # ── Plan ──────────────────────────────────────────────────────────────
    def tallas_elegidas(self) -> list[str]:
        if self.juego == JUEGO_MODELO:
            return list(self.tallas_modelo)
        return list(valores.JUEGOS_TALLAS.get(self.juego or "", ()))

    def replanear(self) -> None:
        self.rebote.stop()
        self._buscar_parecidas()
        self._sugerir()
        tallas = self.tallas_elegidas()
        por_talla = None
        if self.por_talla:
            por_talla = {t: leer_precio(p.text()) for t, (p, _l) in self.campos.items()}
        llegan = {t: leer_cantidad(l.text()) for t, (_p, l) in self.campos.items() if leer_cantidad(l.text())}
        m = self.modelo
        datos = dict(
            tallas=tallas, marca=_texto(self.marca), color=self.color_elegido or _texto(self.color),
            tipo_prenda=_texto(self.tipo_prenda), tipo_pieza=_texto(self.pieza),
            categoria=_texto(self.categoria) or None, genero=_texto(self.genero) or None,
            precio=None if self.por_talla else leer_precio(self.precio.text()), precios_por_talla=por_talla,
            llegan=llegan, costo=leer_precio(self.costo.text()),
            modelo_id=m.producto_id if m else None, modelo_nombre=m.nombre if m else None,
            confirmados=tuple(self.confirmados),
        )
        nombre = self.nombre.text()
        self.plan = self.con_sesion(lambda s: alta.planear_general(s, nombre, **datos))
        self.nota_categoria.setText(f"Categoría: {self.plan.categoria} (sale sola del tipo)."
                                    if self.plan.categoria else "La categoría sale sola del tipo de prenda.")
        self._pintar_ficha()
        self.cambio.emit()

    def _pintar_ficha(self) -> None:
        plan = self.plan
        self.ficha.mostrar([plan])
        if not plan.nombre_sin_escuela:
            self.ficha.nombre.setText("Escribe el nombre")
        if not plan.tallas:
            self.ficha.rango.setText("Elige las tallas")
        self.ficha.sub.setText(" · ".join(x for x in ("Prenda general", plan.marca, plan.tipo_pieza) if x))
        reales = [e for e in plan.errores if not es_pendiente(e)]
        self.ficha.errores.setText("\n".join(dict.fromkeys(reales)))
        self.ficha.errores.setVisible(bool(reales))
        self.ficha.titulo_avisos.setVisible(bool(reales) or not self.ficha.avisos.isHidden())
        if not self.color_elegido and not _texto(self.color):
            self.ficha.color.setText("Color: elígelo")

    def nota_bloqueo(self) -> str:
        """Lo que falta, en una línea (ámbar en la barra)."""
        plan = self.plan
        if plan is None:
            return "Escribe el nombre."
        if not plan.nombre_sin_escuela:
            return "Escribe el nombre."
        if not plan.tallas:
            return "Elige las tallas."
        return nps.nota_bloqueo([plan])

    @property
    def planes(self) -> list[alta.PlanPrenda]:
        return [self.plan] if self.plan is not None else []


def _confirmar_marca(padre: QWidget, marca: str) -> bool:
    caja = QMessageBox(padre)
    caja.setWindowTitle("Marca nueva")
    caja.setText(f"«{marca}» no está en la lista de marcas. ¿Es una marca nueva?")
    si = caja.addButton("Sí, es nueva", QMessageBox.ButtonRole.AcceptRole)
    no = caja.addButton("Elegir de la lista", QMessageBox.ButtonRole.RejectRole)
    caja.setDefaultButton(no)
    caja.exec()
    return caja.clickedButton() is si


__all__ = ["FormularioGeneral", "es_pendiente"]
