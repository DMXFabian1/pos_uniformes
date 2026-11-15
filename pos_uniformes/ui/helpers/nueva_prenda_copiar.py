"""«Escuela igual a otra» en «Nueva prenda» (tanda 5 del alta, 2026-11-15).

Dos pantallas, antes de los mismos pasos 4 (confirmar) y 5 (✓ Listo):

1. **¿De qué escuela y para cuál?** Dos buscadores sin acentos; cada escuela
   con su nivel y cuántas prendas tiene. El destino puede ser una escuela
   nueva (solo ADMIN): antes de crearla pregunta «¿Es la misma que…?» con las
   parecidas por nombre («Ignacio Allende (Jaral)»).
2. **La lista**: cada prenda del origen con su estado (NUEVA, YA ESTÁ, CAMBIA
   COLOR, SE LIGA); se desmarcan las que no lleva. «Color para todas» (cada
   color del origen → el nuevo) y, en cada fila, su propio color (gana).
   A la derecha, la ficha «Así queda».

El plan lo arma `copiar_escuela_service` (sobre el motor del alta); aquí solo
hay pantalla.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import copiar_escuela_service as ce
from pos_uniformes.services import nueva_prenda_service as nps
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import ACCION_CREAR, ACCION_DEJAR, ACCION_USAR
from pos_uniformes.ui.helpers.nueva_prenda_ficha import FichaAsiQueda
from pos_uniformes.ui.styles.nueva_prenda_styles import ANCHO_FICHA

ORIGEN, DESTINO = "origen", "destino"
ANCHO_ESTADO = 118
ANCHO_COLOR = 140
#: El estado de cada fila, para su color (`npEstado[estado=…]`).
TONO_ESTADO = {
    ce.ESTADO_NUEVA: "nueva",
    ce.ESTADO_YA_ESTA: "ya",
    ce.ESTADO_CAMBIA_COLOR: "cambia",
    ce.ESTADO_SE_LIGA: "liga",
}


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


def _repulir(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _con_scroll(pagina: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName("npScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    pagina.setObjectName("npScrollVista")
    scroll.setWidget(pagina)
    return scroll


class _MarcaFoco(QObject):
    def __init__(self, marco: QWidget, campo: QWidget) -> None:
        super().__init__(marco)
        self.marco = marco
        marco.setProperty("foco", "no")
        campo.installEventFilter(self)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:  # noqa: N802 - API de Qt
        if evento.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.marco.setProperty("foco", "si" if evento.type() == QEvent.Type.FocusIn else "no")
            _repulir(self.marco)
        return False


class _ComboColor(QComboBox):
    """Color de lista cerrada; lo escrito pasa por «¿Quisiste decir…?»."""

    elegido = pyqtSignal(str)

    def __init__(self, colores) -> None:
        super().__init__()
        self.setObjectName("npCombo")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItems(list(colores))
        self.setMinimumWidth(150)
        self.lineEdit().editingFinished.connect(self._avisar)
        self.activated.connect(lambda _i: self._avisar())
        self._ultimo = ""

    def poner(self, color: str) -> None:
        self.blockSignals(True)
        if color and self.findText(color) < 0:
            self.addItem(color)
        self.setCurrentText(color)
        self.blockSignals(False)
        self._ultimo = color

    def _avisar(self) -> None:
        texto = valores.limpiar(self.currentText())
        if texto and texto != self._ultimo:
            self._ultimo = texto
            self.elegido.emit(texto)


class _Columna(QFrame):
    """Un buscador de escuela con su lista («1 · De qué escuela copias»)."""

    elegida = pyqtSignal(object)

    def __init__(self, titulo: str, ayuda: str) -> None:
        super().__init__()
        self.setObjectName("npTarjetaBlanca")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(18, 14, 18, 14)
        caja.setSpacing(8)
        caja.addWidget(_etiqueta("npSeccion", titulo))
        marco = QFrame()
        marco.setObjectName("npBuscador")
        fila = QHBoxLayout(marco)
        fila.setContentsMargins(14, 2, 10, 2)
        fila.addWidget(_etiqueta("npBuscadorIcono", "⌕"))
        self.buscar = QLineEdit()
        self.buscar.setObjectName("npBuscar")
        self.buscar.setPlaceholderText(ayuda)
        self.buscar.setClearButtonEnabled(True)
        fila.addWidget(self.buscar, 1)
        self._foco = _MarcaFoco(marco, self.buscar)
        caja.addWidget(marco)
        self.lista = QListWidget()
        self.lista.setObjectName("npLista")
        caja.addWidget(self.lista, 1)
        self.elegida_texto = _etiqueta("npTiene", envolver=True)
        self.elegida_texto.hide()
        caja.addWidget(self.elegida_texto)
        # Si la lista se esconde (al preguntar «¿Es la misma que…?»), lo de arriba no se estira.
        caja.addStretch(0)
        self.escuelas: list[ce.EscuelaParaCopiar] = []
        self.buscar.textChanged.connect(lambda _t: self.llenar())
        self.lista.itemClicked.connect(lambda item: self.elegida.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.lista.itemActivated.connect(lambda item: self.elegida.emit(item.data(Qt.ItemDataRole.UserRole)))

    def llenar(self, quitar: int | None = None) -> None:
        self.lista.clear()
        for e in ce.filtrar_escuelas(self.escuelas, self.buscar.text()):
            if e.escuela_id == quitar:
                continue
            item = QListWidgetItem(f"{e.nombre}   ·   {e.detalle}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.lista.addItem(item)

    def marcar(self, escuela: ce.EscuelaParaCopiar | None, texto: str = "") -> None:
        self.elegida_texto.setText(texto or (f"✓ {escuela.nombre} · {escuela.detalle}" if escuela else ""))
        self.elegida_texto.setVisible(bool(self.elegida_texto.text()))


class _Fila(QFrame):
    """Una prenda del origen: casilla, estado, tallas y precio, color."""

    def __init__(self, pieza: ce.PiezaACopiar, colores) -> None:
        super().__init__()
        self.setObjectName("npFila")
        self.producto_id = pieza.origen.producto_id
        fila = QHBoxLayout(self)
        fila.setContentsMargins(4, 6, 4, 6)
        fila.setSpacing(10)
        self.casilla = QCheckBox()
        self.casilla.setObjectName("npTalla")
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.nombre = _etiqueta("npCopiaNombre", envolver=True)
        self.detalle = _etiqueta("npDonde", envolver=True)
        textos.addWidget(self.nombre)
        textos.addWidget(self.detalle)
        self.estado = _etiqueta("npEstado")
        self.estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # El estado en su columna (a la derecha, del mismo ancho en todas las filas).
        columna = QWidget()
        columna.setObjectName("npCeldaEstado")
        columna.setFixedWidth(ANCHO_ESTADO)
        caja_estado = QHBoxLayout(columna)
        caja_estado.setContentsMargins(0, 0, 0, 0)
        caja_estado.addStretch(1)
        caja_estado.addWidget(self.estado)
        self.color = _ComboColor(colores)
        self.color.setFixedWidth(ANCHO_COLOR)
        fila.addWidget(self.casilla, 0, Qt.AlignmentFlag.AlignTop)
        fila.addLayout(textos, 1)
        fila.addWidget(columna, 0, Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(self.color, 0, Qt.AlignmentFlag.AlignVCenter)
        self.sin_color = _etiqueta("npDonde", "—")
        self.sin_color.setFixedWidth(ANCHO_COLOR)
        fila.addWidget(self.sin_color, 0, Qt.AlignmentFlag.AlignVCenter)

    def mostrar(self, p: ce.PiezaACopiar, destino: str = "") -> None:
        self.casilla.blockSignals(True)
        self.casilla.setChecked(p.marcada)
        self.casilla.blockSignals(False)
        # Sin la escuela (ya está en el título): el nombre con el que queda.
        nombre = CatalogService.nombre_sin_escuela(p.nombre, destino) if p.marcada else p.origen.nombre_sin_escuela
        self.nombre.setText(nombre)
        self.nombre.setProperty("marcada", "si" if p.marcada else "no")
        partes = [p.origen.texto_rango]
        if p.estado == ce.ESTADO_CAMBIA_COLOR and p.marcada:
            partes.append(f"{p.destino_color} → {p.color}")
        if p.estado == ce.ESTADO_NUEVA and p.marcada:
            partes.append("mismos precios")
        if p.estado == ce.ESTADO_SE_LIGA or (p.ligar and p.estado != ce.ESTADO_NUEVA):
            partes.append(f"va en {p.origen.grupo}" if p.origen.grupo else "va en su uniforme")
        errores = p.todos_los_errores if p.marcada else []
        avisos = p.avisos if p.marcada else []
        if errores:
            partes = [errores[0].split("\n")[0]]
        elif avisos:
            partes.append(avisos[0])
        self.detalle.setText(" · ".join(partes))
        self.detalle.setProperty("tono", "danger" if errores else ("warning" if avisos else ""))
        self.estado.setText(p.estado)
        self.estado.setProperty("estado", TONO_ESTADO.get(p.estado, "") if p.marcada else "fuera")
        general = p.origen.general
        self.color.setVisible(not general)
        self.sin_color.setVisible(general)
        if not general:
            self.color.poner(p.color)
            self.color.setEnabled(p.marcada)
        for w in (self.nombre, self.detalle, self.estado):
            _repulir(w)


class FormularioCopiar(QObject):
    """Las dos pantallas de «Escuela igual a otra». `cambio` avisa cada vez
    que hay plan nuevo; `listo_escuelas` cuando ya están origen y destino."""

    cambio = pyqtSignal()
    listo_escuelas = pyqtSignal()

    def __init__(self, *, con_sesion: Callable[[Callable[[Any], Any]], Any], preguntar,
                 puede_crear_escuela: Callable[[], bool], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.con_sesion = con_sesion
        self.preguntar = preguntar
        self.puede_crear_escuela = puede_crear_escuela
        self.ops = nps.Opciones()
        self.escuelas: list[ce.EscuelaParaCopiar] = []
        self.origen: ce.EscuelaParaCopiar | None = None
        self.destino: ce.EscuelaParaCopiar | None = None
        #: Nombre de la escuela nueva y si ya se contestó «¿Es la misma que…?».
        self.nueva: str = ""
        self.nueva_confirmada = False
        self.plan: ce.PlanCopia | None = None
        self.filas: dict[int, _Fila] = {}
        self.combos_todas: dict[str, _ComboColor] = {}
        self.pagina_escuelas = self._armar_escuelas()
        self.pagina_lista = self._armar_lista()

    # ── 1. Escuelas ───────────────────────────────────────────────────────
    def _armar_escuelas(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QHBoxLayout(pagina)
        caja.setContentsMargins(0, 4, 0, 0)
        caja.setSpacing(16)
        self.col_origen = _Columna("1 · DE QUÉ ESCUELA COPIAS", "La que ya tiene el uniforme")
        self.col_destino = _Columna("2 · PARA QUÉ ESCUELA", "La que lo va a llevar, o una nueva")
        self.col_origen.elegida.connect(self.elegir_origen)
        self.col_destino.elegida.connect(self.elegir_destino)
        caja.addWidget(self.col_origen, 1)
        caja.addWidget(self.col_destino, 1)

        # Escuela nueva: «＋ … es una escuela nueva» y la pregunta «¿Es la misma que…?».
        destino = self.col_destino.layout()
        self.boton_nueva = _boton("npEnlace", "")
        self.boton_nueva.clicked.connect(self.preguntar_si_es_la_misma)
        self.boton_nueva.hide()
        destino.insertWidget(destino.indexOf(self.col_destino.lista) + 1, self.boton_nueva)
        self.panel_misma = QFrame()
        self.panel_misma.setObjectName("npPanel")
        self.caja_misma = QVBoxLayout(self.panel_misma)
        self.caja_misma.setContentsMargins(16, 12, 16, 12)
        self.caja_misma.setSpacing(6)
        self.panel_misma.hide()
        destino.insertWidget(destino.indexOf(self.boton_nueva) + 1, self.panel_misma)
        self.col_destino.buscar.textChanged.connect(lambda _t: self._pintar_boton_nueva())
        return pagina

    def poner_escuelas(self, escuelas: list[ce.EscuelaParaCopiar], ops: nps.Opciones) -> None:
        self.escuelas = list(escuelas)
        self.ops = ops
        self.col_origen.escuelas = [e for e in self.escuelas if e.prendas]
        self.col_destino.escuelas = list(self.escuelas)
        self.col_origen.llenar()
        self.col_destino.llenar()

    def empezar(self) -> None:
        self.origen = self.destino = None
        self.nueva, self.nueva_confirmada = "", False
        self.plan = None
        for col in (self.col_origen, self.col_destino):
            col.buscar.clear()
            col.marcar(None)
        self.panel_misma.hide()
        self._pintar_boton_nueva()

    def elegir_origen(self, escuela: ce.EscuelaParaCopiar) -> None:
        self.origen = escuela
        self.col_origen.marcar(escuela)
        if self.destino is not None and self.destino.escuela_id == escuela.escuela_id:
            self.destino = None
            self.col_destino.marcar(None)
        self.col_destino.llenar(quitar=escuela.escuela_id)
        self._quizas_listo()

    def elegir_destino(self, escuela: ce.EscuelaParaCopiar) -> None:
        self.destino = escuela
        self.nueva, self.nueva_confirmada = "", False
        self.panel_misma.hide()
        self._pintar_boton_nueva()
        self.col_destino.marcar(escuela)
        self._quizas_listo()

    def _pintar_boton_nueva(self) -> None:
        texto = valores.limpiar(self.col_destino.buscar.text())
        if self.nueva and valores.normalizar(texto) != valores.normalizar(self.nueva):
            # Se escribió otra cosa: la escuela nueva de antes ya no cuenta.
            self.nueva, self.nueva_confirmada = "", False
            self.panel_misma.hide()
            self.col_destino.marcar(self.destino)
            self.cambio.emit()
        existe = any(valores.normalizar(e.nombre) == valores.normalizar(texto) for e in self.escuelas)
        visible = bool(texto) and not existe and self.puede_crear_escuela() and self.panel_misma.isHidden() \
            and not self.nueva_confirmada
        self.boton_nueva.setText(f"＋ «{texto}» es una escuela nueva")
        self.boton_nueva.setVisible(visible)
        self.col_destino.lista.setVisible(self.panel_misma.isHidden())

    def preguntar_si_es_la_misma(self) -> None:
        """«¿Es la misma que Ignacio Allende (Jaral)?» con las parecidas."""
        nombre = valores.limpiar(self.col_destino.buscar.text())
        if not nombre or not self.puede_crear_escuela():
            return
        self.nueva, self.nueva_confirmada = nombre, False
        self.destino = None
        self.col_destino.marcar(None)
        excluir = (self.origen.nombre,) if self.origen is not None else ()
        parecidas = self.con_sesion(lambda s: ce.escuelas_parecidas(s, nombre, excluir=excluir))
        while self.caja_misma.count():
            item = self.caja_misma.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if parecidas:
            titulo = f"¿«{nombre}» es la misma que…?"
        else:
            titulo = f"No hay otra escuela con un nombre parecido a «{nombre}»."
        self.caja_misma.addWidget(_etiqueta("npFaltaNombre", titulo, envolver=True))
        self.botones_misma: dict[str, QPushButton] = {}
        por_nombre = {e.nombre: e for e in self.escuelas}
        for p in parecidas:
            e = por_nombre.get(p.valor)
            detalle = f" · {e.detalle}" if e else ""
            boton = _boton("npFalta", f"Sí, es {p.valor}{detalle}")
            boton.clicked.connect(lambda _=False, e=e: e and self._es_la_misma(e))
            self.botones_misma[p.valor] = boton
            self.caja_misma.addWidget(boton)
        self.boton_es_otra = _boton("npFalta", f"No, es otra: crear «{nombre}»" if parecidas
                                    else f"Sí, crear «{nombre}»")
        self.boton_es_otra.clicked.connect(self.confirmar_nueva)
        self.caja_misma.addWidget(self.boton_es_otra)
        self.caja_misma.addWidget(_etiqueta(
            "npNotaChica", "Si es la misma, se copia a la que ya existe: así no quedan dos escuelas iguales.",
            envolver=True))
        self.panel_misma.show()
        self._pintar_boton_nueva()
        self._quizas_listo()

    def _es_la_misma(self, escuela: ce.EscuelaParaCopiar) -> None:
        self.col_destino.buscar.clear()
        self.elegir_destino(escuela)

    def confirmar_nueva(self) -> None:
        if not self.nueva or not self.puede_crear_escuela():
            return
        self.nueva_confirmada = True
        self.panel_misma.hide()
        self._pintar_boton_nueva()
        self.col_destino.marcar(None, f"＋ {self.nueva} · escuela nueva (se crea al copiar)")
        self._quizas_listo()

    @property
    def escuelas_listas(self) -> bool:
        return self.origen is not None and (self.destino is not None or self.nueva_confirmada)

    def nota_escuelas(self) -> str:
        if self.origen is None:
            return "Elige de qué escuela copias."
        if self.nueva and not self.nueva_confirmada:
            return "Contesta si es la misma escuela."
        if self.destino is None and not self.nueva_confirmada:
            return "Elige para qué escuela es."
        return ""

    def _quizas_listo(self) -> None:
        self.cambio.emit()
        if self.escuelas_listas:
            self.listo_escuelas.emit()

    # ── 2. La lista ───────────────────────────────────────────────────────
    def _armar_lista(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QHBoxLayout(pagina)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(16)
        vista = QWidget()
        izq = QVBoxLayout(vista)
        izq.setContentsMargins(0, 0, 8, 0)
        izq.setSpacing(10)
        self.scroll_lista = _con_scroll(vista)
        caja.addWidget(self.scroll_lista, 1)

        self.titulo_todas = _etiqueta("npSeccion", "COLOR PARA TODAS")
        izq.addWidget(self.titulo_todas)
        self.rejilla_todas = QGridLayout()
        self.rejilla_todas.setHorizontalSpacing(12)
        self.rejilla_todas.setVerticalSpacing(6)
        izq.addLayout(self.rejilla_todas)

        self.marco_lista = QFrame()
        self.marco_lista.setObjectName("npTallas")
        self.caja_lista = QVBoxLayout(self.marco_lista)
        self.caja_lista.setContentsMargins(16, 10, 16, 10)
        self.caja_lista.setSpacing(0)
        cabeza = QHBoxLayout()
        cabeza.setContentsMargins(4, 0, 4, 6)
        cabeza.addWidget(_etiqueta("npColTitulo", "PRENDA"), 1)
        estado = _etiqueta("npColTitulo", "ESTADO")
        estado.setFixedWidth(ANCHO_ESTADO)
        estado.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cabeza.addWidget(estado)
        cabeza.addSpacing(10)
        color = _etiqueta("npColTitulo", "COLOR")
        color.setFixedWidth(ANCHO_COLOR)
        cabeza.addWidget(color)
        self.caja_lista.addLayout(cabeza)
        izq.addWidget(self.marco_lista)
        self.nota_lista = _etiqueta("npNotaChica", envolver=True)
        izq.addWidget(self.nota_lista)
        izq.addStretch(1)

        self.ficha = FichaAsiQueda()
        scroll_ficha = _con_scroll(self.ficha)
        self.ficha.setObjectName("npFicha")
        scroll_ficha.setFixedWidth(ANCHO_FICHA)
        self.scroll_ficha = scroll_ficha
        caja.addWidget(scroll_ficha)
        return pagina

    def abrir_lista(self) -> bool:
        """Arma el plan de las escuelas elegidas y las filas. False si no se pudo."""
        if not self.escuelas_listas:
            return False
        destino: str | int = self.destino.escuela_id if self.destino is not None else self.nueva
        try:
            self.plan = self.con_sesion(lambda s: ce.planear_copia(
                s, self.origen.escuela_id, destino, escuela_nueva=self.nueva_confirmada))
        except ValueError:
            self.plan = None
            return False
        self._armar_filas()
        self._pintar()
        self.scroll_lista.verticalScrollBar().setValue(0)
        return True

    @staticmethod
    def _vaciar(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                FormularioCopiar._vaciar(item.layout())

    def _armar_filas(self) -> None:
        self._vaciar(self.rejilla_todas)
        self.combos_todas = {}
        for i, (color, n) in enumerate(self.plan.colores_del_origen):
            prendas = "1 prenda" if n == 1 else f"{n} prendas"
            self.rejilla_todas.addWidget(_etiqueta("npTallaGeneral", f"{color}  ·  {prendas}"), i, 0)
            self.rejilla_todas.addWidget(_etiqueta("npDonde", "→"), i, 1)
            combo = _ComboColor(self.ops.colores)
            combo.elegido.connect(lambda texto, c=color, w=combo: self._al_color_todas(c, texto, w))
            self.combos_todas[color] = combo
            self.rejilla_todas.addWidget(combo, i, 2)
        self.rejilla_todas.setColumnStretch(3, 1)
        for fila in self.filas.values():
            self.caja_lista.removeWidget(fila)
            fila.deleteLater()
        self.filas = {}
        for p in self.plan.piezas:
            fila = _Fila(p, self.ops.colores)
            pid = p.origen.producto_id
            fila.casilla.toggled.connect(lambda v, pid=pid: self.marcar(pid, v))
            fila.color.elegido.connect(lambda texto, pid=pid, w=fila.color: self._al_color_de(pid, texto, w))
            self.filas[pid] = fila
            self.caja_lista.addWidget(fila)

    def _pintar(self) -> None:
        plan = self.plan
        for color, combo in self.combos_todas.items():
            combo.poner(plan.color_para_todas(color))
        for p in plan.piezas:
            self.filas[p.origen.producto_id].mostrar(p, plan.destino)
        notas = []
        if plan.solo_en_destino:
            notas.append("Solo en el destino (no se tocan): " + ", ".join(plan.solo_en_destino) + ".")
        notas.append("Las prendas nuevas llevan los mismos precios que el origen y entran sin existencia.")
        self.nota_lista.setText(" ".join(notas))
        self._pintar_ficha()
        self.cambio.emit()

    def _pintar_ficha(self) -> None:
        plan, f = self.plan, self.ficha
        f.nombre.setText(plan.destino)
        f.sub.setText(f"igual que {plan.origen}" + (" · escuela nueva" if plan.es_nueva else ""))
        n, t = len(plan.nuevas), plan.tallas_nuevas
        f.rango.setText(f"{n} {'prenda nueva' if n == 1 else 'prendas nuevas'} · {t} {'talla' if t == 1 else 'tallas'}"
                        if n else "Sin prendas nuevas")
        lineas = []
        precios_ = [x.precio for p in plan.planes for x in p.tallas if x.precio is not None]
        if precios_:
            lo, hi = min(precios_), max(precios_)
            lineas.append(f"Precios del origen: {'$%.0f' % lo if lo == hi else '$%.0f a $%.0f' % (lo, hi)} · sin existencia")
        f._poner(f.color, "\n".join(lineas))
        grupos = sorted({p.grupo for p in plan.planes if p.ligar and p.grupo})
        ligan = [p for p in plan.ligan]
        uniforme = []
        if grupos:
            uniforme.append(f"Quedan en su uniforme: {', '.join(grupos)}")
        if ligan:
            uniforme.append("Se ligan al uniforme: " + ", ".join(p.origen.nombre_sin_escuela for p in ligan))
        f._poner(f.uniforme, "\n".join(uniforme))
        recetas = list(dict.fromkeys(p.receta_texto for p in plan.planes if p.receta_texto))
        f._poner(f.receta, "\n".join(recetas))
        cambian = [f"{p.nombre}: {p.destino_color} → {p.color}" for p in plan.cambian]
        f._poner(f.llegan, ("Cambian de color (mismos códigos y precios):\n" + "\n".join(f"• {c}" for c in cambian))
                 if cambian else "")
        ya = [p for p in plan.marcadas if p.estado == ce.ESTADO_YA_ESTA]
        f._poner(f.otras, f"Ya están y no se tocan: {len(ya)}" if ya else "")
        avisos = list(dict.fromkeys(plan.avisos + [a for p in plan.marcadas for a in
                                                     ((p.plan.todos_los_avisos if p.plan else []) + p.avisos)]))
        f._poner(f.avisos, "\n".join(f"⚠ {a}" for a in avisos[:6]))
        errores = [e for e in plan.errores]
        f._poner(f.errores, "\n".join(errores))
        f.titulo_avisos.setVisible(bool(avisos or errores))
        for w in (f.avisos, f.errores):
            _repulir(w)

    def _replanear(self, **cambios) -> None:
        self.plan = self.con_sesion(lambda s: ce.replanear(s, self.plan, **cambios))
        self._pintar()

    def marcar(self, producto_id: int, valor: bool = True) -> None:
        self.plan = self.con_sesion(lambda s: ce.marcar(s, self.plan, producto_id, valor))
        self._pintar()

    def _revisar_color(self, texto: str) -> tuple[str | None, tuple[str, ...]]:
        """El color a usar y los confirmados nuevos (None si se canceló)."""
        if texto in self.ops.colores:
            return texto, ()
        revision = valores.revisar_valor(valores.CAMPO_COLOR, texto, self.ops.usos_color or {})
        if not revision.necesita_pregunta:
            return revision.valor, ()
        eleccion = self.preguntar(self.pagina_lista, revision, True)
        if eleccion.accion == ACCION_USAR:
            return eleccion.valor, ()
        if eleccion.accion == ACCION_DEJAR:
            return revision.escrito, ()
        if eleccion.accion == ACCION_CREAR:
            return revision.escrito, (revision.escrito,)
        return None, ()

    def _al_color_todas(self, color_origen: str, texto: str, combo: _ComboColor | None = None) -> None:
        color, nuevos = self._revisar_color(texto)
        if color is None:
            self._pintar()
            return
        self.cambiar_color_todas(color_origen, color, confirmados=nuevos)

    def _al_color_de(self, producto_id: int, texto: str, combo: _ComboColor | None = None) -> None:
        color, nuevos = self._revisar_color(texto)
        if color is None:
            self._pintar()
            return
        self.cambiar_color_de(producto_id, color, confirmados=nuevos)

    def cambiar_color_todas(self, color_origen: str, color: str, *, confirmados: tuple[str, ...] = ()) -> None:
        colores = {**self.plan.colores, color_origen: color}
        self._replanear(colores=colores, confirmados=tuple(self.plan.confirmados) + tuple(confirmados))

    def cambiar_color_de(self, producto_id: int, color: str, *, confirmados: tuple[str, ...] = ()) -> None:
        color_de = {**self.plan.color_de, int(producto_id): color}
        self._replanear(color_de=color_de, confirmados=tuple(self.plan.confirmados) + tuple(confirmados))

    def fila(self, nombre: str) -> _Fila:
        """Para las pruebas: la fila de la prenda del origen con ese nombre (sin escuela)."""
        for p in self.plan.piezas:
            if p.origen.nombre_sin_escuela == nombre or p.origen.nombre == nombre:
                return self.filas[p.origen.producto_id]
        raise KeyError(nombre)


__all__ = ["FormularioCopiar", "TONO_ESTADO"]
