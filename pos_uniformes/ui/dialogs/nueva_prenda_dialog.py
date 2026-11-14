"""«＋ Nueva prenda»: primero a qué se parece, luego un solo paso (tanda 3, 2026-11-13).

Reemplaza al asistente de 4 pasos y ~25 campos (que queda en «⋯ → Usar el
formulario anterior»). El recorrido para una prenda de escuela:

0. **¿Qué vas a dar de alta?** Tres tarjetas y abajo «Últimas altas · Hacer
   otra igual». «Escuela igual a otra» llega en la tanda 5 (se ve como
   «Próximamente»); «Prenda general o de temporada», hasta la tanda 4, abre
   el formulario anterior.
1. **¿Para qué escuela?** Buscador sin acentos; cada escuela con su nivel y
   cuántas prendas tiene.
2. **Ya tiene / Le falta**, comparada con las de su nivel. Se toca la pieza.
3. **La pantalla principal**: «Copiado de: … ▾», color (lista cerrada con
   «¿Quisiste decir…?»), tallas marcables con PRECIO, DE DÓNDE y LLEGAN,
   «▸ Más datos», «＋ Hacer la misma para otras escuelas» y, a la derecha,
   «Así queda». Un solo botón vino: «Dar de alta 10 tallas».
4. **Una frase para confirmar**: [Revisar otra vez] [Sí, dar de alta].
   Se guarda todo junto o nada (`alta_prenda_service.aplicar`).
5. **✓ Listo**: [Imprimir etiquetas], [Otra prenda para esta escuela],
   [Esta misma pieza para otra escuela], [Ver en Inventario].

La lógica vive en `services/alta_prenda_service.py` (plan → aplicar) y
`services/nueva_prenda_service.py` (lo que se lee y las frases). Aquí solo
hay pantalla. Cada consulta abre y cierra su propia sesión (`session_factory`)
para no dejar nada tomado.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from pos_uniformes.database.models import Usuario
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import conjunto_service, hermanos_service
from pos_uniformes.services import nueva_prenda_service as nps
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import (
    ACCION_CREAR,
    ACCION_DEJAR,
    ACCION_USAR,
    preguntar_quisiste_decir,
)
from pos_uniformes.ui.helpers.nueva_prenda_ficha import FichaAsiQueda
from pos_uniformes.ui.helpers.nueva_prenda_tallas import TablaTallas, leer_precio, texto_precio
from pos_uniformes.ui.styles.inventario_styles import CAFE
from pos_uniformes.ui.styles.nueva_prenda_styles import (
    ALTO,
    ANCHO,
    ANCHO_FICHA,
    build_nueva_prenda_stylesheet,
    sombra,
)

PUERTA, ESCUELA, FALTA, PRINCIPAL, CONFIRMAR, LISTO = range(6)

TARJETA_ESCUELA = "escuela"
TARJETA_IGUAL = "igual"
TARJETA_GENERAL = "general"

TEXTO_PRONTO_IGUAL = (
    "«Escuela igual a otra» llega en la próxima actualización. Mientras, da de alta pieza por pieza "
    "con «Prenda para una escuela»: al terminar, «Esta misma pieza para otra escuela» la repite."
)


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


class _MarcaFoco(QObject):
    """`foco="si"` en el marco del buscador mientras su campo tiene el foco."""

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


class _Combo(QComboBox):
    """Combo con su flecha café pintada (el tema de la ventana principal la quita)."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("npCombo")

    def paintEvent(self, evento) -> None:  # noqa: N802 - API de Qt
        super().paintEvent(evento)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(CAFE))
        x, y = self.width() - 18, self.height() / 2 - 2
        pintor.drawPolygon(QPolygonF([QPointF(x, y), QPointF(x + 8, y), QPointF(x + 4, y + 5)]))
        pintor.end()


class _BotonFalta(QPushButton):
    """«＋ Pants Suelto ……… lo tienen 41 de 44» (y si es conjunto, de qué se arma)."""

    def __init__(self, pieza: str, nota: str) -> None:
        super().__init__()
        self.setObjectName("npFalta")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)
        self.setMinimumHeight(48)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(16, 0, 16, 0)
        self.nombre = _etiqueta("npFaltaNombre", f"＋  {pieza}")
        self.nota = _etiqueta("npFaltaNota", nota)
        for w in (self.nombre, self.nota):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        fila.addWidget(self.nombre)
        fila.addStretch(1)
        fila.addWidget(self.nota)


class _TarjetaGrande(QPushButton):
    """Una tarjeta de la puerta: icono, título, texto y pie."""

    def __init__(self, icono: str, titulo: str, texto: str, pie: str = "", *, pronto: bool = False) -> None:
        super().__init__()
        self.setObjectName("npTarjeta")
        self.setProperty("pronto", "si" if pronto else "no")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(190)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(22, 20, 22, 18)
        caja.setSpacing(6)
        arriba = QHBoxLayout()
        arriba.addWidget(_etiqueta("npTarjetaIcono", icono))
        arriba.addStretch(1)
        if pronto:
            arriba.addWidget(_etiqueta("npPronto", "PRÓXIMAMENTE"), 0, Qt.AlignmentFlag.AlignTop)
        caja.addLayout(arriba)
        self.titulo = _etiqueta("npTarjetaTitulo", titulo, envolver=True)
        self.texto = _etiqueta("npTarjetaTexto", texto, envolver=True)
        self.pie = _etiqueta("npTarjetaPie", pie, envolver=True)
        for w in (self.titulo, self.texto, self.pie):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            caja.addWidget(w)
        self.pie.setVisible(bool(pie))
        caja.addStretch(1)
        sombra(self)


class NuevaPrendaDialog(QDialog):
    """La ventana. `session_factory()` devuelve una sesión nueva (con `with`).

    Callbacks (los pone `nueva_prenda_abrir`; en pruebas se dejan vacíos):
    - `al_imprimir(ids)`: abrir las etiquetas de las tallas creadas.
    - `al_ver(resultado)`: llevar Inventario a lo que se creó.
    - `al_formulario_anterior()`: abrir el asistente viejo.
    - `al_terminar(resultado)`: refrescar la ventana principal tras guardar.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        session_factory: Callable[[], Any],
        usuario_id: int,
        al_imprimir: Callable[[list[int]], object] | None = None,
        al_ver: Callable[[alta.ResultadoAlta], object] | None = None,
        al_formulario_anterior: Callable[[], object] | None = None,
        al_terminar: Callable[[alta.ResultadoAlta], object] | None = None,
        preguntar=preguntar_quisiste_decir,
    ) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.usuario_id = int(usuario_id)
        self.al_imprimir = al_imprimir
        self.al_ver = al_ver
        self.al_formulario_anterior = al_formulario_anterior
        self.al_terminar = al_terminar
        self.preguntar = preguntar

        # Estado del recorrido.
        self.escuela: nps.EscuelaParaElegir | None = None
        self.nivel: str | None = None
        self.pieza: str | None = None
        self.modelo_forzado: int | None = None
        self.directo = False  # «Hacer otra igual»: de la escuela a la pantalla principal
        self.plan: alta.PlanPrenda | None = None
        self.planes: list[alta.PlanPrenda] = []
        self.sin_pieza: hermanos_service.SinPieza | None = None
        self.otras_marcadas: set[int] = set()
        self.resultado: alta.ResultadoAlta | None = None
        self._color_elegido = False
        self.escuelas: list[nps.EscuelaParaElegir] = []
        self.ops = nps.Opciones()

        self.setObjectName("npDialogo")
        self.setWindowTitle("Nueva prenda")
        self.setModal(True)
        self.setStyleSheet(build_nueva_prenda_stylesheet())
        self.resize(ANCHO, ALTO)
        self.setMinimumSize(1080, 640)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 18, 26, 16)
        raiz.setSpacing(12)
        # Encabezado: «‹ Atrás», título y subtítulo.
        self.atras = _boton("npAtras", "‹ Atrás")
        self.atras.clicked.connect(self._atras)
        self.titulo = _etiqueta("npTitulo", envolver=True)
        self.sub = _etiqueta("npSub", envolver=True)
        cabeza = QVBoxLayout()
        cabeza.setSpacing(2)
        cabeza.addWidget(self.atras, 0, Qt.AlignmentFlag.AlignLeft)
        cabeza.addWidget(self.titulo)
        cabeza.addWidget(self.sub)
        raiz.addLayout(cabeza)

        self.pasos = QStackedWidget()
        self.pasos.setObjectName("npPasos")
        raiz.addWidget(self.pasos, 1)
        for armar in (self._armar_puerta, self._armar_escuela, self._armar_falta, self._armar_principal,
                      self._armar_confirmar, self._armar_listo):
            self.pasos.addWidget(armar())

        # Barra de abajo.
        barra = QFrame()
        barra.setObjectName("npBarra")
        fila = QHBoxLayout(barra)
        fila.setContentsMargins(0, 10, 0, 0)
        fila.setSpacing(10)
        self.cancelar = _boton("npCancelar", "Cancelar")
        self.cancelar.clicked.connect(self.reject)
        self.bloqueo = _etiqueta("npBloqueo")
        self.secundarios: list[QPushButton] = []
        self.principal = _boton("npPrincipal", "Dar de alta")
        self.principal.clicked.connect(self._al_principal)
        fila.addWidget(self.cancelar)
        fila.addStretch(1)
        fila.addWidget(self.bloqueo)
        self._fila_barra = fila
        fila.addWidget(self.principal)
        raiz.addWidget(barra)

        self._cargar_inicio()
        self._ir(PUERTA)

    # ── Sesiones ──────────────────────────────────────────────────────────
    def _con_sesion(self, hacer: Callable[[Any], Any]) -> Any:
        with self.session_factory() as session:
            try:
                return hacer(session)
            finally:
                session.rollback()

    def _cargar_inicio(self) -> None:
        def leer(s):
            return nps.escuelas_para_elegir(s), nps.ultimas_altas(s), nps.opciones(s)

        self.escuelas, ultimas, self.ops = self._con_sesion(leer)
        self._mostrar_ultimas(ultimas)
        self._llenar_lista_escuelas()
        self._llenar_opciones()

    # ── Navegación ────────────────────────────────────────────────────────
    def _ir(self, paso: int) -> None:
        self.pasos.setCurrentIndex(paso)
        self.atras.setVisible(paso in (ESCUELA, FALTA, PRINCIPAL))
        self.cancelar.setText("Cerrar" if paso == LISTO else "Cancelar")
        for boton in self.secundarios:
            self._fila_barra.removeWidget(boton)
            boton.hide()
            boton.deleteLater()
        self.secundarios = []
        self.bloqueo.clear()
        self.principal.setVisible(paso in (PRINCIPAL, CONFIRMAR, LISTO))
        self.principal.setEnabled(True)
        if paso == PUERTA:
            self.titulo.setText("Nueva prenda")
            self.sub.setText("¿Qué vas a dar de alta? Empieza por algo parecido: copiamos tallas y precios de la caja.")
        elif paso == ESCUELA:
            self.titulo.setText(f"¿Para qué escuela es {self.pieza}?" if self.directo and self.pieza
                                else "¿Para qué escuela?")
            self.sub.setText("Busca sin acentos. Cada escuela dice su nivel y cuántas prendas tiene.")
            self.buscar.setFocus()
        elif paso == FALTA:
            self.titulo.setText(self.escuela.nombre if self.escuela else "")
            nivel = (self.nivel or "").lower()
            self.sub.setText(f"Lo que ya tiene y lo que le falta, comparada con las demás de {nivel}."
                             if nivel else "¿De qué nivel es la prenda?")
        elif paso == PRINCIPAL:
            self.titulo.setText(f"{self.pieza} para {self.escuela.nombre}" if self.escuela else "")
            self.sub.setText("Revisa tallas y precios; lo demás ya viene de la prenda modelo.")
            self._pintar_barra_principal()
        elif paso == CONFIRMAR:
            self.titulo.setText("¿Damos de alta?")
            self.sub.setText("Se guarda todo junto: la prenda, sus tallas, su lugar en el uniforme y la receta.")
            self.error_confirmar.clear()
            self.error_confirmar.hide()
            self.frase.setText(nps.frase_confirmar(self.planes))
            detalle = nps.detalle_confirmar(self.planes)
            self.detalle_confirmar.setText(detalle)
            self.detalle_confirmar.setVisible(bool(detalle))
            self.principal.setText("Sí, dar de alta")
            self._secundario("Revisar otra vez", lambda: self._ir(PRINCIPAL))
        elif paso == LISTO:
            self.titulo.setText("Nueva prenda")
            self.sub.setText("Ya está en Inventario. ¿Qué sigue?")
            self.principal.setText("Imprimir etiquetas")
            self._secundario("Ver en Inventario", self._ver_en_inventario)
            self._secundario("Esta misma pieza para otra escuela", self._misma_para_otra)
            self._secundario("Otra prenda para esta escuela", self._otra_para_esta)

    def _secundario(self, texto: str, alHacer: Callable[[], object]) -> QPushButton:
        boton = _boton("npSecundario", texto)
        boton.clicked.connect(lambda _=False: alHacer())
        self._fila_barra.insertWidget(self._fila_barra.indexOf(self.principal), boton)
        self.secundarios.append(boton)
        return boton

    def _atras(self) -> None:
        paso = self.pasos.currentIndex()
        if paso == ESCUELA:
            self.directo = False
            self.modelo_forzado = None
            self._ir(PUERTA)
        elif paso == FALTA:
            self._ir(ESCUELA)
        elif paso == PRINCIPAL:
            if self.directo:
                self._ir(ESCUELA)
            else:
                self.modelo_forzado = None
                self._ir(FALTA)

    def _al_principal(self) -> None:
        paso = self.pasos.currentIndex()
        if paso == PRINCIPAL:
            # La descripción no avisa al escribir: se pasa al plan (y a las
            # otras escuelas) justo antes de confirmar, para guardar lo que se ve.
            self._rehacer_planes()
            if self.planes and all(p.puede_aplicar for p in self.planes):
                self._ir(CONFIRMAR)
        elif paso == CONFIRMAR:
            self._dar_de_alta()
        elif paso == LISTO:
            self._imprimir()

    # ── 0. Puerta ─────────────────────────────────────────────────────────
    def _armar_puerta(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(0, 8, 0, 0)
        caja.setSpacing(16)
        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(16)
        self.tarjetas = {
            TARJETA_ESCUELA: _TarjetaGrande(
                "🏫", "Prenda para una escuela",
                "Pants, playera, chamarra… copiada de la misma pieza de otra escuela. Para una o varias escuelas.",
                "Escuela → pieza que le falta → revisar"),
            TARJETA_IGUAL: _TarjetaGrande(
                "⧉", "Escuela igual a otra",
                "Copia el uniforme completo de una escuela, con otros colores.", pronto=True),
            TARJETA_GENERAL: _TarjetaGrande(
                "👕", "Prenda general o de temporada",
                "Calcetas, batas, chamarras de temporada… sin escuela.",
                "Por ahora abre el formulario anterior"),
        }
        self.tarjetas[TARJETA_ESCUELA].clicked.connect(self._empezar_escuela)
        self.tarjetas[TARJETA_IGUAL].clicked.connect(self._pronto_igual)
        self.tarjetas[TARJETA_GENERAL].clicked.connect(self._formulario_anterior)
        for t in self.tarjetas.values():
            tarjetas.addWidget(t, 1)
        caja.addLayout(tarjetas)
        self.nota_puerta = _etiqueta("npNota", envolver=True)
        self.nota_puerta.hide()
        caja.addWidget(self.nota_puerta)

        self.titulo_ultimas = _etiqueta("npSeccion", "ÚLTIMAS ALTAS · HACER OTRA IGUAL")
        caja.addWidget(self.titulo_ultimas)
        self.rejilla_ultimas = QGridLayout()
        self.rejilla_ultimas.setHorizontalSpacing(12)
        self.rejilla_ultimas.setVerticalSpacing(10)
        caja.addLayout(self.rejilla_ultimas)
        caja.addStretch(1)
        return pagina

    def _mostrar_ultimas(self, ultimas: list[nps.UltimaAlta]) -> None:
        self.ultimas = list(ultimas)
        self.titulo_ultimas.setVisible(bool(ultimas))
        for i, u in enumerate(ultimas):
            marco = QFrame()
            marco.setObjectName("npUltima")
            fila = QHBoxLayout(marco)
            fila.setContentsMargins(14, 8, 10, 8)
            textos = QVBoxLayout()
            textos.setSpacing(0)
            nombre = _etiqueta("npUltimaNombre", u.nombre, envolver=True)
            textos.addWidget(nombre)
            textos.addWidget(_etiqueta("npUltimaDetalle", u.detalle))
            fila.addLayout(textos, 1)
            boton = _boton("npEnlace", "Hacer otra igual")
            boton.clicked.connect(lambda _=False, u=u: self._hacer_otra_igual(u))
            fila.addWidget(boton)
            self.rejilla_ultimas.addWidget(marco, i // 2, i % 2)

    def _empezar_escuela(self) -> None:
        self.directo = False
        self.modelo_forzado = None
        self.pieza = None
        self._ir(ESCUELA)

    def _pronto_igual(self) -> None:
        self.nota_puerta.setText(TEXTO_PRONTO_IGUAL)
        self.nota_puerta.show()

    def _formulario_anterior(self) -> None:
        self.reject()
        if self.al_formulario_anterior is not None:
            QTimer.singleShot(0, self.al_formulario_anterior)

    def _hacer_otra_igual(self, u: nps.UltimaAlta) -> None:
        self.directo = True
        self.pieza = u.tipo_pieza
        self.modelo_forzado = u.producto_id
        self.nivel = u.nivel
        self._ir(ESCUELA)

    # ── 1. Escuela ────────────────────────────────────────────────────────
    def _armar_escuela(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(0, 4, 0, 0)
        caja.setSpacing(12)
        marco = QFrame()
        marco.setObjectName("npBuscador")
        fila = QHBoxLayout(marco)
        fila.setContentsMargins(16, 4, 12, 4)
        fila.addWidget(_etiqueta("npBuscadorIcono", "⌕"))
        self.buscar = QLineEdit()
        self.buscar.setObjectName("npBuscar")
        self.buscar.setPlaceholderText("Nombre de la escuela (p. ej. «ignacio allende»)")
        self.buscar.setClearButtonEnabled(True)
        fila.addWidget(self.buscar, 1)
        self._foco_buscar = _MarcaFoco(marco, self.buscar)
        caja.addWidget(marco)
        self.lista = QListWidget()
        self.lista.setObjectName("npLista")
        caja.addWidget(self.lista, 1)
        self.vacio_escuelas = _etiqueta("npVacio", "🔎 No hay escuelas con ese nombre. Revisa cómo se escribe.",
                                        envolver=True)
        self.vacio_escuelas.hide()
        caja.addWidget(self.vacio_escuelas)
        self.buscar.textChanged.connect(lambda _t: self._llenar_lista_escuelas())
        self.buscar.returnPressed.connect(self._elegir_primera)
        self.lista.itemActivated.connect(self._elegir_escuela_item)
        self.lista.itemClicked.connect(self._elegir_escuela_item)
        return pagina

    def _llenar_lista_escuelas(self) -> None:
        if not hasattr(self, "lista"):
            return
        visibles = nps.filtrar_escuelas(self.escuelas, self.buscar.text())
        self.lista.clear()
        for e in visibles:
            item = QListWidgetItem(f"{e.nombre}   ·   {e.detalle}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.lista.addItem(item)
        self.vacio_escuelas.setVisible(not visibles)
        if visibles:
            self.lista.setCurrentRow(0)

    def _elegir_primera(self) -> None:
        item = self.lista.currentItem() or self.lista.item(0)
        if item is not None:
            self._elegir_escuela_item(item)

    def _elegir_escuela_item(self, item: QListWidgetItem) -> None:
        self.elegir_escuela(item.data(Qt.ItemDataRole.UserRole))

    def elegir_escuela(self, escuela: nps.EscuelaParaElegir) -> None:
        self.escuela = escuela
        if self.directo:
            self.nivel = escuela.nivel or self.nivel
            self._abrir_principal()
            return
        self.nivel = escuela.nivel
        self.modelo_forzado = None
        self._mostrar_falta()
        self._ir(FALTA)

    # ── 2. Ya tiene / Le falta ────────────────────────────────────────────
    def _armar_falta(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QHBoxLayout(pagina)
        caja.setContentsMargins(0, 4, 0, 0)
        caja.setSpacing(16)

        izquierda = QFrame()
        izquierda.setObjectName("npTarjetaBlanca")
        self.caja_falta = QVBoxLayout(izquierda)
        self.caja_falta.setContentsMargins(20, 16, 20, 16)
        self.caja_falta.setSpacing(8)
        caja.addWidget(izquierda, 3)

        derecha = QFrame()
        derecha.setObjectName("npTarjetaBlanca")
        derecha.setFixedWidth(ANCHO_FICHA)
        self.caja_tiene = QVBoxLayout(derecha)
        self.caja_tiene.setContentsMargins(20, 16, 20, 16)
        self.caja_tiene.setSpacing(6)
        caja.addWidget(derecha)
        return pagina

    @staticmethod
    def _vaciar(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                NuevaPrendaDialog._vaciar(item.layout())

    def _mostrar_falta(self) -> None:
        self._vaciar(self.caja_falta)
        self._vaciar(self.caja_tiene)
        if not self.nivel:
            self.caja_falta.addWidget(_etiqueta("npSeccion", "¿DE QUÉ NIVEL ES LA PRENDA?"))
            self.caja_falta.addWidget(_etiqueta(
                "npNota", "Esta escuela todavía no tiene prendas. Elige el nivel para compararla con las demás.",
                envolver=True))
            for nivel in self.ops.niveles:
                boton = _boton("npFalta", nivel)
                boton.clicked.connect(lambda _=False, n=nivel: self._elegir_nivel(n))
                self.caja_falta.addWidget(boton)
            self.caja_falta.addStretch(1)
            self.caja_tiene.addWidget(_etiqueta("npVacio", "🏫 Aquí aparece lo que la escuela ya tiene.", envolver=True))
            self.caja_tiene.addStretch(1)
            return
        try:
            comp = self._con_sesion(lambda s: hermanos_service.comparar_escuela(s, self.escuela.escuela_id, self.nivel))
        except ValueError as exc:
            self.caja_falta.addWidget(_etiqueta("npNota", str(exc), envolver=True))
            return
        self.comparacion = comp
        titulo = f"LE FALTA · COMPARADA CON {comp.escuelas_del_nivel} DE {comp.nivel.upper()}"
        self.caja_falta.addWidget(_etiqueta("npSeccion", titulo))
        self.botones_falta: dict[str, QPushButton] = {}
        if comp.le_falta:
            for pieza in comp.le_falta:
                nota = pieza.texto
                if pieza.tipo_pieza in conjunto_service.TIPOS_CONJUNTO:
                    nota = f"es un conjunto: se le propone su receta · {nota}"
                boton = _BotonFalta(pieza.tipo_pieza, nota)
                boton.clicked.connect(lambda _=False, p=pieza.tipo_pieza: self.elegir_pieza(p))
                self.botones_falta[pieza.tipo_pieza] = boton
                self.caja_falta.addWidget(boton)
        else:
            self.caja_falta.addWidget(_etiqueta(
                "npVacio", f"✓ Tiene todo lo que tienen las demás de {comp.nivel.lower()}. "
                "Si es otra pieza, elígela abajo.", envolver=True))
        self.caja_falta.addSpacing(8)
        otra = QHBoxLayout()
        otra.addWidget(_etiqueta("npEtiqueta", "OTRA PIEZA"))
        self.combo_pieza = _Combo()
        self.combo_pieza.addItem("Elige…", None)
        for p in self.ops.piezas:
            self.combo_pieza.addItem(p, p)
        self.combo_pieza.activated.connect(
            lambda _i: self.combo_pieza.currentData() and self.elegir_pieza(self.combo_pieza.currentData()))
        otra.addWidget(self.combo_pieza, 1)
        self.caja_falta.addLayout(otra)
        self.caja_falta.addStretch(1)

        self.caja_tiene.addWidget(_etiqueta("npSeccion", "YA TIENE"))
        if comp.ya_tiene:
            for pieza in comp.ya_tiene:
                for nombre in pieza.productos or (pieza.tipo_pieza,):
                    self.caja_tiene.addWidget(_etiqueta("npTiene", f"✓ {nombre}", envolver=True))
        else:
            self.caja_tiene.addWidget(_etiqueta("npVacio", "Todavía no tiene prendas.", envolver=True))
        self.caja_tiene.addStretch(1)

    def _elegir_nivel(self, nivel: str) -> None:
        self.nivel = nivel
        self._mostrar_falta()
        self._ir(FALTA)

    def elegir_pieza(self, pieza: str) -> None:
        self.pieza = pieza
        self._abrir_principal()

    # ── 3. Pantalla principal ─────────────────────────────────────────────
    def _armar_principal(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QHBoxLayout(pagina)
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
        self.scroll_principal = scroll
        caja.addWidget(scroll, 1)

        # «Copiado de: … (igual en 14 escuelas) · cambiar ▾»
        modelo = QHBoxLayout()
        modelo.setSpacing(8)
        self.modelo = _etiqueta("npModelo", envolver=True)
        modelo.addWidget(self.modelo, 1)
        self.boton_modelo = _boton("npCambiar", "cambiar ▾")
        self.menu_modelo = QMenu(self.boton_modelo)
        self.menu_modelo.setObjectName("npMenu")
        self.boton_modelo.setMenu(self.menu_modelo)
        modelo.addWidget(self.boton_modelo, 0, Qt.AlignmentFlag.AlignTop)
        izq.addLayout(modelo)

        color = QHBoxLayout()
        color.addWidget(_etiqueta("npEtiqueta", "COLOR"))
        self.color = _Combo()
        self.color.setEditable(True)
        self.color.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.color.setMinimumWidth(220)
        self.color.lineEdit().editingFinished.connect(self._al_escribir_color)
        self.color.activated.connect(lambda _i: self._al_escribir_color())
        color.addWidget(self.color)
        color.addStretch(1)
        izq.addLayout(color)

        self.tabla = TablaTallas()
        self.tabla.marcada.connect(self._al_marcar)
        self.tabla.precio_cambiado.connect(self._al_precio)
        self.tabla.sugerencia_aceptada.connect(self._al_sugerencia)
        self.tabla.llegan_cambiado.connect(self._al_llegan)
        izq.addWidget(self.tabla)
        otra_talla = QHBoxLayout()
        self.otra_talla = _Combo()
        self.otra_talla.setMinimumWidth(220)
        self.otra_talla.activated.connect(lambda _i: self._al_otra_talla())
        otra_talla.addWidget(self.otra_talla)
        otra_talla.addStretch(1)
        izq.addLayout(otra_talla)

        # ▸ Más datos
        self.mas_datos = QToolButton()
        self.mas_datos.setObjectName("npPlegable")
        self.mas_datos.setCheckable(True)
        self.mas_datos.setText("▸ Más datos (marca, género, escudo, costo, descripción)")
        self.mas_datos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mas_datos.toggled.connect(self._plegar_mas_datos)
        izq.addWidget(self.mas_datos, 0, Qt.AlignmentFlag.AlignLeft)
        self.panel_mas = QFrame()
        self.panel_mas.setObjectName("npPanel")
        rejilla = QGridLayout(self.panel_mas)
        rejilla.setContentsMargins(16, 12, 16, 12)
        rejilla.setHorizontalSpacing(12)
        rejilla.setVerticalSpacing(8)
        self.marca = _Combo()
        self.genero = _Combo()
        self.escudo = _Combo()
        self.costo = QLineEdit()
        self.costo.setObjectName("npCampo")
        self.costo.setPlaceholderText("$ por pieza (opcional)")
        self.descripcion = QPlainTextEdit()
        self.descripcion.setObjectName("npTexto")
        self.descripcion.setFixedHeight(56)
        for fila, (titulo, w) in enumerate((("MARCA", self.marca), ("GÉNERO", self.genero), ("ESCUDO", self.escudo),
                                            ("COSTO", self.costo), ("DESCRIPCIÓN", self.descripcion))):
            rejilla.addWidget(_etiqueta("npEtiqueta", titulo), fila, 0)
            rejilla.addWidget(w, fila, 1)
        rejilla.setColumnStretch(1, 1)
        self.marca.activated.connect(lambda _i: self._al_mas_datos())
        self.genero.activated.connect(lambda _i: self._al_mas_datos())
        self.escudo.activated.connect(lambda _i: self._al_mas_datos())
        self.costo.editingFinished.connect(self._al_mas_datos)
        self.panel_mas.hide()
        izq.addWidget(self.panel_mas)

        # ＋ Hacer la misma para otras escuelas
        self.otras = QToolButton()
        self.otras.setObjectName("npPlegable")
        self.otras.setCheckable(True)
        self.otras.setCursor(Qt.CursorShape.PointingHandCursor)
        self.otras.toggled.connect(self._plegar_otras)
        izq.addWidget(self.otras, 0, Qt.AlignmentFlag.AlignLeft)
        self.panel_otras = QFrame()
        self.panel_otras.setObjectName("npPanel")
        caja_otras = QVBoxLayout(self.panel_otras)
        caja_otras.setContentsMargins(16, 10, 16, 10)
        caja_otras.setSpacing(4)
        enlaces = QHBoxLayout()
        todas = _boton("npEnlace", "Marcar todas")
        ninguna = _boton("npEnlace", "Ninguna")
        todas.clicked.connect(lambda: self._marcar_otras(True))
        ninguna.clicked.connect(lambda: self._marcar_otras(False))
        enlaces.addWidget(todas)
        enlaces.addWidget(ninguna)
        enlaces.addStretch(1)
        caja_otras.addLayout(enlaces)
        self.rejilla_otras = QGridLayout()
        self.rejilla_otras.setHorizontalSpacing(16)
        caja_otras.addLayout(self.rejilla_otras)
        self.casillas_otras: dict[int, QCheckBox] = {}
        self.panel_otras.hide()
        izq.addWidget(self.panel_otras)
        izq.addStretch(1)

        self.ficha = FichaAsiQueda()
        self.ficha.setFixedWidth(ANCHO_FICHA)
        caja.addWidget(self.ficha)
        return pagina

    def _llenar_opciones(self) -> None:
        self.color.blockSignals(True)
        self.color.clear()
        self.color.addItems(list(self.ops.colores))
        self.color.blockSignals(False)
        for combo, lista in ((self.marca, self.ops.marcas), (self.genero, self.ops.generos),
                             (self.escudo, self.ops.escudos)):
            combo.clear()
            if combo is not self.marca:
                combo.addItem("—", None)
            for valor in lista:
                combo.addItem(valor, valor)

    def _abrir_principal(self) -> None:
        self._color_elegido = False
        self.otras_marcadas = set()
        self.otras.setChecked(False)
        self.mas_datos.setChecked(False)
        try:
            self.plan = self._con_sesion(lambda s: alta.planear_desde_modelo(
                s, self.escuela.escuela_id, self.pieza, nivel=self.nivel, modelo_id=self.modelo_forzado))
        except ValueError as exc:
            self.plan = None
            self.bloqueo.setText(str(exc))
            return
        self.nivel = self.plan.nivel or self.nivel
        self.sin_pieza = None
        if self.nivel and self.pieza:
            self.sin_pieza = self._con_sesion(lambda s: hermanos_service.escuelas_sin_pieza(s, self.pieza, self.nivel))
        self._llenar_otras()
        self._pintar_mas_datos()
        self._rehacer_planes()
        self._ir(PRINCIPAL)
        self.scroll_principal.verticalScrollBar().setValue(0)

    def _pintar_mas_datos(self) -> None:
        plan = self.plan
        for combo, valor in ((self.marca, plan.marca), (self.genero, plan.genero), (self.escudo, plan.escudo)):
            if valor and combo.findData(valor) < 0:
                combo.addItem(valor, valor)
            combo.setCurrentIndex(max(0, combo.findData(valor)))
        costos = {t.costo for t in plan.tallas if t.costo is not None}
        self.costo.setText(texto_precio(costos.pop()) if len(costos) == 1 else "")
        self.descripcion.setPlainText(plan.descripcion or "")

    def _llenar_otras(self) -> None:
        self._vaciar(self.rejilla_otras)
        self.casillas_otras = {}
        escuelas = [e for e in (self.sin_pieza.escuelas if self.sin_pieza else ())
                    if e.escuela_id != self.escuela.escuela_id]
        nivel = (self.nivel or "").lower()
        self.otras.setText(f"＋ Hacer la misma para otras escuelas (le falta a {len(escuelas)} de {nivel})")
        self.otras.setVisible(bool(escuelas))
        for i, e in enumerate(escuelas):
            casilla = QCheckBox(e.escuela)
            casilla.setObjectName("npOtraEscuela")
            casilla.toggled.connect(lambda v, eid=e.escuela_id: self._al_otra(eid, v))
            self.casillas_otras[e.escuela_id] = casilla
            self.rejilla_otras.addWidget(casilla, i // 2, i % 2)

    def _plegar_mas_datos(self, abierto: bool) -> None:
        self.panel_mas.setVisible(abierto)
        self.mas_datos.setText(("▾" if abierto else "▸") + " Más datos (marca, género, escudo, costo, descripción)")

    def _plegar_otras(self, abierto: bool) -> None:
        self.panel_otras.setVisible(abierto)
        self.otras.setText(("▾" if abierto else "＋") + self.otras.text()[1:])

    def _marcar_otras(self, valor: bool) -> None:
        for casilla in self.casillas_otras.values():
            casilla.blockSignals(True)
            casilla.setChecked(valor)
            casilla.blockSignals(False)
        self.otras_marcadas = set(self.casillas_otras) if valor else set()
        self._rehacer_planes()

    def marcar_otra_escuela(self, escuela: str, valor: bool = True) -> None:
        """Para las pruebas y para «Esta misma pieza…»: marca una escuela por nombre."""
        for eid, casilla in self.casillas_otras.items():
            if casilla.text() == escuela:
                if not self.otras.isChecked():
                    self.otras.setChecked(True)
                casilla.setChecked(valor)
                return
        raise ValueError(f"«{escuela}» no está entre las escuelas a las que les falta.")

    # ── Lo que se toca en la pantalla principal ───────────────────────────
    def _al_marcar(self, talla: str, valor: bool) -> None:
        if self.plan is None:
            return
        hacer = alta.marcar_talla if valor else alta.desmarcar_talla
        self._con_sesion(lambda s: hacer(s, self.plan, talla))
        self._rehacer_planes()

    def _llenar_otra_talla(self) -> None:
        """«＋ Otra talla…»: las de la lista oficial que no están en la tabla
        (para una pieza sin modelo o una talla que nadie tiene todavía)."""
        en_tabla = {valores.normalizar(t.talla) for t in self.plan.tallas + self.plan.tallas_posibles}
        self.otra_talla.blockSignals(True)
        self.otra_talla.clear()
        self.otra_talla.addItem("＋ Otra talla…", None)
        for talla in valores.TALLAS_SUGERIDAS:
            if valores.normalizar(talla) not in en_tabla:
                self.otra_talla.addItem(talla, talla)
        self.otra_talla.setCurrentIndex(0)
        self.otra_talla.blockSignals(False)

    def agregar_talla(self, talla: str) -> None:
        """Una talla que no trae el modelo ni sus hermanas: entra marcada y sin precio."""
        self.plan.tallas_posibles.append(alta.TallaPlan(talla=talla, precio=None))
        self._con_sesion(lambda s: alta.marcar_talla(s, self.plan, talla))
        self._rehacer_planes()

    def _al_otra_talla(self) -> None:
        talla = self.otra_talla.currentData()
        if talla:
            self.agregar_talla(talla)

    def _talla(self, talla: str):
        return next((t for t in self.plan.tallas if t.talla == talla), None)

    def _al_precio(self, talla: str, precio) -> None:
        t = self._talla(talla)
        if t is None:
            return
        t.precio = precio
        self._completar()

    def _al_sugerencia(self, talla: str) -> None:
        t = self._talla(talla)
        if t is None or t.sugerencia_5_9 is None:
            return
        t.precio = t.sugerencia_5_9
        self._completar()

    def _al_llegan(self, talla: str, cuantas: int) -> None:
        t = self._talla(talla)
        if t is None:
            return
        t.llegan = int(cuantas)
        if self.plan.es_conjunto:
            self._completar()
        else:
            self.ficha.mostrar(self.planes)

    def _al_mas_datos(self) -> None:
        plan = self.plan
        if plan is None:
            return
        plan.marca = self.marca.currentData() or plan.marca
        plan.genero = self.genero.currentData()
        plan.escudo = self.escudo.currentData()
        costo = leer_precio(self.costo.text())
        for t in plan.tallas + plan.tallas_posibles:
            t.costo = costo
        self._completar()

    def _al_escribir_color(self) -> None:
        if self.plan is None:
            return
        texto = valores.limpiar(self.color.currentText())
        if not texto or texto == self.plan.color:
            self._pintar_color()
            return
        if texto in self.ops.colores:
            self.cambiar_color(texto)
            return
        revision = valores.revisar_valor(valores.CAMPO_COLOR, texto, self.ops.usos_color or {})
        if not revision.necesita_pregunta:
            self.cambiar_color(revision.valor)
            return
        eleccion = self.preguntar(self, revision, True)
        if eleccion.accion == ACCION_USAR:
            self.cambiar_color(eleccion.valor)
        elif eleccion.accion == ACCION_DEJAR:
            self.cambiar_color(revision.escrito)
        elif eleccion.accion == ACCION_CREAR:
            self.plan.confirmados = tuple(self.plan.confirmados) + (revision.escrito,)
            self.cambiar_color(revision.escrito)
        else:
            self._pintar_color()

    def cambiar_color(self, color: str) -> None:
        plan = self.plan
        plan.nombre_sin_escuela = alta.cambiar_color_en_nombre(plan.nombre_sin_escuela, plan.color, color)
        plan.color = color
        self._color_elegido = True
        self._completar()

    def cambiar_modelo(self, modelo_id: int) -> None:
        color = self.plan.color if self._color_elegido else None
        llegan = {t.talla: t.llegan for t in self.plan.tallas if t.llegan}
        self.modelo_forzado = int(modelo_id)
        self.plan = self._con_sesion(lambda s: alta.planear_desde_modelo(
            s, self.escuela.escuela_id, self.pieza, nivel=self.nivel, modelo_id=self.modelo_forzado,
            color=color, llegan=llegan))
        self._pintar_mas_datos()
        self._rehacer_planes()

    def _al_otra(self, escuela_id: int, valor: bool) -> None:
        if valor:
            self.otras_marcadas.add(escuela_id)
        else:
            self.otras_marcadas.discard(escuela_id)
        self._rehacer_planes()

    # ── Planes ────────────────────────────────────────────────────────────
    def _completar(self) -> None:
        self._con_sesion(lambda s: alta.completar(s, self.plan))
        self._rehacer_planes()

    def _planes_de_otras(self, session) -> list[alta.PlanPrenda]:
        plan = self.plan
        ids = [eid for eid in self.casillas_otras if eid in self.otras_marcadas]
        if not ids or not plan.tallas:
            return []
        precios = {t.talla: t.precio for t in plan.tallas if t.precio is not None}
        costos = {t.talla: t.costo for t in plan.tallas if t.costo is not None}
        otros = alta.planear_varias_escuelas(
            session, ids, plan.tipo_pieza or self.pieza,
            nivel=plan.nivel, modelo_id=plan.modelo_id, color=plan.color, nombre=plan.nombre_sin_escuela,
            tallas=[t.talla for t in plan.tallas], precios_a_mano=precios, costos=costos,
            confirmados=plan.confirmados, saltar_skus=len(plan.tallas),
        )
        for p in otros:
            p.marca, p.genero, p.escudo, p.descripcion = plan.marca, plan.genero, plan.escudo, plan.descripcion
            alta.completar(session, p)
        return otros

    def _rehacer_planes(self) -> None:
        if self.plan is None:
            return
        self.plan.descripcion = self.descripcion.toPlainText().strip() or None
        self.planes = [self.plan] + self._con_sesion(self._planes_de_otras)
        self._pintar_principal()

    def _pintar_color(self) -> None:
        self.color.blockSignals(True)
        if self.color.findText(self.plan.color) < 0:
            self.color.addItem(self.plan.color)
        self.color.setCurrentText(self.plan.color)
        self.color.blockSignals(False)

    def _pintar_principal(self) -> None:
        plan = self.plan
        if plan.modelo_nombre:
            self.modelo.setText(plan.modelo_texto)
        else:
            self.modelo.setText(plan.modelo_texto or "Sin prenda modelo: pon tallas y precios.")
        self.menu_modelo.clear()
        for m in plan.alternativas:
            accion = self.menu_modelo.addAction(f"{m.nombre}  ·  {m.texto_rango}  ·  {m.texto_iguales}")
            accion.triggered.connect(lambda _=False, mid=m.producto_id: self.cambiar_modelo(mid))
        self.boton_modelo.setVisible(bool(plan.alternativas))
        self._pintar_color()
        self.tabla.mostrar(plan)
        self._llenar_otra_talla()
        self.ficha.mostrar(self.planes)
        if self.pasos.currentIndex() == PRINCIPAL:
            self._pintar_barra_principal()

    def _pintar_barra_principal(self) -> None:
        self.principal.setText(nps.texto_boton(self.planes))
        nota = nps.nota_bloqueo(self.planes)
        self.bloqueo.setText(nota)
        self.principal.setEnabled(not nota)

    # ── 4. Confirmar ──────────────────────────────────────────────────────
    def _armar_confirmar(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(0, 24, 0, 0)
        caja.setSpacing(16)
        marco = QFrame()
        marco.setObjectName("npTarjetaBlanca")
        dentro = QVBoxLayout(marco)
        dentro.setContentsMargins(28, 24, 28, 24)
        dentro.setSpacing(12)
        self.frase = _etiqueta("npFrase", envolver=True)
        dentro.addWidget(self.frase)
        self.detalle_confirmar = _etiqueta("npFichaLinea", envolver=True)
        dentro.addWidget(self.detalle_confirmar)
        dentro.addWidget(_etiqueta(
            "npNota", "Si algo falla no se guarda nada. La bitácora anota de qué prenda se copió.", envolver=True))
        self.error_confirmar = _etiqueta("npError", envolver=True)
        self.error_confirmar.hide()
        dentro.addWidget(self.error_confirmar)
        caja.addWidget(marco)
        caja.addStretch(1)
        return pagina

    def _dar_de_alta(self) -> None:
        def guardar(s):
            usuario = s.get(Usuario, self.usuario_id)
            if usuario is None:
                raise PermissionError("No se encontró el usuario.")
            return alta.aplicar(s, self.planes, usuario, alta.ORIGEN_POS, commit=True)

        try:
            self.resultado = self._con_sesion(guardar)
        except PermissionError:
            self._error_al_guardar("solo un ADMIN puede dar de alta prendas.")
            return
        except IntegrityError:
            self._error_al_guardar("otra caja dio de alta algo igual mientras tanto. Revisa otra vez.")
            return
        except (ValueError, SQLAlchemyError) as exc:
            self._error_al_guardar(str(exc).split("\n")[0] or exc.__class__.__name__)
            return
        if self.al_terminar is not None:
            self.al_terminar(self.resultado)
        self.texto_listo.setText(nps.frase_listo(self.resultado))
        self._ir(LISTO)

    def _error_al_guardar(self, texto: str) -> None:
        self.error_confirmar.setText(f"No se dio de alta: {texto}")
        self.error_confirmar.show()

    # ── 5. Listo ──────────────────────────────────────────────────────────
    def _armar_listo(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("npPaso")
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(0, 24, 0, 0)
        caja.setSpacing(16)
        marco = QFrame()
        marco.setObjectName("npTarjetaBlanca")
        dentro = QVBoxLayout(marco)
        dentro.setContentsMargins(28, 24, 28, 24)
        dentro.setSpacing(10)
        dentro.addWidget(_etiqueta("npListo", "✓ Listo"))
        self.texto_listo = _etiqueta("npFrase", envolver=True)
        dentro.addWidget(self.texto_listo)
        dentro.addWidget(_etiqueta(
            "npNota", "Las etiquetas salen sin precio, como las de uniforme. "
            "La existencia que llegó entró como entrada normal: se puede corregir.", envolver=True))
        caja.addWidget(marco)
        caja.addStretch(1)
        return pagina

    def variantes_creadas(self) -> list[int]:
        if self.resultado is None:
            return []
        return [t.variante_id for p in self.resultado.productos for t in p.tallas]

    def _imprimir(self) -> None:
        ids = self.variantes_creadas()
        self.accept()
        if self.al_imprimir is not None and ids:
            QTimer.singleShot(0, lambda: self.al_imprimir(ids))

    def _ver_en_inventario(self) -> None:
        resultado = self.resultado
        self.accept()
        if self.al_ver is not None and resultado is not None:
            QTimer.singleShot(0, lambda: self.al_ver(resultado))

    def _otra_para_esta(self) -> None:
        self.directo = False
        self.modelo_forzado = None
        self._recargar()
        self._mostrar_falta()
        self._ir(FALTA)

    def _misma_para_otra(self) -> None:
        producto = self.resultado.productos[0] if self.resultado and self.resultado.productos else None
        self.directo = True
        self.modelo_forzado = producto.producto_id if producto else None
        self._recargar()
        self.buscar.clear()
        self._ir(ESCUELA)

    def _recargar(self) -> None:
        """Después de un alta cambian las prendas de cada escuela y las últimas altas."""
        self._vaciar(self.rejilla_ultimas)
        self._cargar_inicio()


__all__ = ["NuevaPrendaDialog", "PUERTA", "ESCUELA", "FALTA", "PRINCIPAL", "CONFIRMAR", "LISTO"]
