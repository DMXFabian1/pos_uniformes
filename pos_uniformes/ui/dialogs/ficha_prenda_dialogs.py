"""Las ventanitas de la ficha de la prenda (tanda 4 del alta, 2026-11-15).

Desde la ficha de Inventario, ya con la prenda elegida:

- `TallaNuevaDialog`: la talla gris que se tocó («EXG ＋ $305») en una
  confirmación corta: la frase, el precio (editable) y lo que llega.
- `OtroColorDialog`: «＋ Otro color»: el color (lista cerrada con «¿Quisiste
  decir…?») y «Así queda» corto; copia todas las tallas con sus precios.
- `CorregirPrendaDialog`: «✏️ Corregir prenda»: el nombre sin la escuela, el
  color de toda la prenda y, plegados, los precios de cada talla. Si un
  precio baja, sale el aviso rojo de Inventario antes de guardar.

Un solo botón vino por ventana; Cancelar no crea ni cambia nada. Las reglas
viven en `services/alta_ficha_service.py` y `services/corregir_prenda_service.py`;
aquí solo hay pantalla. Cada consulta abre y cierra su sesión.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError

from pos_uniformes.database.models import Usuario
from pos_uniformes.services import alta_ficha_service as af
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import corregir_prenda_service as cp
from pos_uniformes.services import nueva_prenda_service as nps
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import (
    ACCION_CREAR,
    ACCION_DEJAR,
    ACCION_USAR,
    preguntar_quisiste_decir,
)
from pos_uniformes.ui.helpers.nueva_prenda_tallas import leer_cantidad, leer_precio, texto_precio
from pos_uniformes.ui.styles.nueva_prenda_styles import build_nueva_prenda_stylesheet

#: Cuánto espera tras la última tecla para volver a planear.
REBOTE_MS = 300


def _etiqueta(nombre: str, texto: str = "", *, envolver: bool = True) -> QLabel:
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


def _poner(etiqueta: QLabel, texto: str) -> None:
    etiqueta.setText(texto)
    etiqueta.setVisible(bool(texto))


class _Ventanita(QDialog):
    """Lo común: título, subtítulo, tarjeta blanca, barra con Cancelar y un botón vino."""

    ANCHO = 560

    def __init__(self, parent: QWidget | None, *, session_factory: Callable[[], Any], usuario_id: int,
                 titulo: str, preguntar=preguntar_quisiste_decir) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.usuario_id = int(usuario_id)
        self.preguntar = preguntar
        self.resultado = None
        self._guardando = False
        self.setObjectName("npDialogo")
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setStyleSheet(build_nueva_prenda_stylesheet())
        self.setMinimumWidth(self.ANCHO)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(24, 18, 24, 16)
        raiz.setSpacing(10)
        self.titulo = _etiqueta("npTitulo", titulo)
        self.sub = _etiqueta("npSub")
        raiz.addWidget(self.titulo)
        raiz.addWidget(self.sub)
        self.tarjeta = QFrame()
        self.tarjeta.setObjectName("npTarjetaBlanca")
        self.cuerpo = QVBoxLayout(self.tarjeta)
        self.cuerpo.setContentsMargins(20, 16, 20, 16)
        self.cuerpo.setSpacing(10)
        raiz.addWidget(self.tarjeta, 1)
        self.error = _etiqueta("npError")
        self.error.hide()
        raiz.addWidget(self.error)
        barra = QHBoxLayout()
        barra.setSpacing(10)
        self.cancelar = _boton("npCancelar", "Cancelar")
        self.cancelar.clicked.connect(self.reject)
        self.bloqueo = _etiqueta("npBloqueo", envolver=False)
        self.principal = _boton("npPrincipal", "Guardar")
        self.principal.clicked.connect(self._al_principal)
        barra.addWidget(self.cancelar)
        barra.addStretch(1)
        barra.addWidget(self.bloqueo)
        barra.addWidget(self.principal)
        raiz.addLayout(barra)
        self.rebote = QTimer(self)
        self.rebote.setSingleShot(True)
        self.rebote.setInterval(REBOTE_MS)
        self.rebote.timeout.connect(self.replanear)

    def _con_sesion(self, hacer: Callable[[Any], Any]) -> Any:
        with self.session_factory() as session:
            try:
                return hacer(session)
            finally:
                session.rollback()

    def _usuario(self, session) -> Usuario:
        usuario = session.get(Usuario, self.usuario_id)
        if usuario is None:
            raise PermissionError("No se encontró el usuario.")
        return usuario

    def _fila(self, titulo: str, widget: QWidget, nota: QWidget | None = None) -> None:
        fila = QHBoxLayout()
        fila.setSpacing(12)
        etiqueta = _etiqueta("npEtiqueta", titulo, envolver=False)
        etiqueta.setMinimumWidth(96)
        fila.addWidget(etiqueta)
        fila.addWidget(widget)
        if nota is not None:
            fila.addWidget(nota, 1)
        else:
            fila.addStretch(1)
        self.cuerpo.addLayout(fila)

    def _al_principal(self) -> None:
        if self._guardando or not self.principal.isEnabled():
            return
        self.rebote.stop()
        self.replanear()
        if not self.principal.isEnabled():
            return
        self._guardando = True
        self.principal.setEnabled(False)
        try:
            self.resultado = self.guardar()
        except PermissionError:
            self._fallo("solo un ADMIN puede cambiar el catálogo.")
            return
        except (ValueError, SQLAlchemyError) as exc:
            self._fallo(str(exc).split("\n")[0] or exc.__class__.__name__)
            return
        finally:
            self._guardando = False
        if self.resultado is not None:
            self.accept()
        else:
            self.principal.setEnabled(True)  # se canceló un aviso: se puede volver a intentar

    def _fallo(self, texto: str) -> None:
        self.error.setText(f"No se guardó nada: {texto}")
        self.error.show()
        self.principal.setEnabled(True)

    def _pintar_barra(self, texto_boton: str, bloqueo: str) -> None:
        self.principal.setText(texto_boton)
        self.bloqueo.setText(bloqueo)
        self.principal.setEnabled(not bloqueo)

    # Las subclases ponen:
    def replanear(self) -> None:  # pragma: no cover - abstracto
        raise NotImplementedError

    def guardar(self):  # pragma: no cover - abstracto
        raise NotImplementedError


def _primer_error(errores: list[str]) -> str:
    return errores[0].split("\n")[0] if errores else ""


# ── Talla que falta ────────────────────────────────────────────────────────

class TallaNuevaDialog(_Ventanita):
    def __init__(self, parent: QWidget | None, *, session_factory, usuario_id: int, producto_id: int, talla: str,
                 nota_hermanas: str = "", **kw) -> None:
        super().__init__(parent, session_factory=session_factory, usuario_id=usuario_id,
                         titulo=f"Agregar la talla {talla}", **kw)
        self.producto_id = int(producto_id)
        self.talla = talla
        self.plan: af.PlanTallasNuevas | None = None
        self.frase = _etiqueta("npFrase")
        self.cuerpo.addWidget(self.frase)
        self.precio = QLineEdit()
        self.precio.setObjectName("npPrecio")
        self.precio.setFixedWidth(110)
        self.precio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.donde = _etiqueta("npDonde")
        self._fila("PRECIO", self.precio, self.donde)
        self.sugerencia = _boton("npSugerencia", "")
        self.sugerencia.hide()
        self.sugerencia.clicked.connect(self._usar_sugerencia)
        self.cuerpo.addWidget(self.sugerencia, 0, Qt.AlignmentFlag.AlignLeft)
        self.llegan = QLineEdit()
        self.llegan.setObjectName("npLlegan")
        self.llegan.setFixedWidth(110)
        self.llegan.setPlaceholderText("—")
        self.llegan.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._fila("LLEGAN HOY", self.llegan, _etiqueta("npNotaChica", "Opcional: entra como entrada normal."))
        self.nota = _etiqueta("npNota", nota_hermanas)
        self.nota.setVisible(bool(nota_hermanas))
        self.cuerpo.addWidget(self.nota)
        self.precio.textEdited.connect(lambda _t: self.rebote.start())
        self.llegan.textEdited.connect(lambda _t: self.rebote.start())
        self._primera = True
        self.replanear()

    def replanear(self) -> None:
        precio = None if self._primera else leer_precio(self.precio.text())
        llegan = leer_cantidad(self.llegan.text())

        def planear(s):
            return af.planear_tallas_nuevas(s, self.producto_id, {self.talla: precio}, llegan={self.talla: llegan})

        try:
            self.plan = self._con_sesion(planear)
        except ValueError as exc:
            self.plan = None
            self._pintar_barra("Agregar talla", str(exc))
            return
        t = self.plan.tallas[0]
        if self._primera:
            self.precio.setText(texto_precio(t.precio))
            self._primera = False
        self.sub.setText(self.plan.nombre)
        self.frase.setText(self.plan.resumen)
        if t.error:
            self.donde.setText(t.error)
            tono = "danger" if self.precio.text().strip() or t.precio is not None else ""
        elif t.aviso:
            self.donde.setText(t.aviso)
            tono = "warning"
        else:
            self.donde.setText(t.origen_precio)
            tono = ""
        self.donde.setProperty("tono", tono)
        _repulir(self.donde)
        if t.sugerencia_5_9 is not None:
            self.sugerencia.setText(f"¿${t.sugerencia_5_9:.0f}?")
            self.sugerencia.show()
        else:
            self.sugerencia.hide()
        bloqueo = _primer_error(self.plan.todos_los_errores)
        self._pintar_barra(f"Agregar talla {t.talla}", bloqueo)

    def _usar_sugerencia(self) -> None:
        t = self.plan.tallas[0] if self.plan else None
        if t is not None and t.sugerencia_5_9 is not None:
            self.precio.setText(texto_precio(t.sugerencia_5_9))
            self.replanear()

    def guardar(self):
        plan = self.plan
        return self._con_sesion(lambda s: af.aplicar_tallas_nuevas(s, plan, self._usuario(s), commit=True))


# ── Otro color ─────────────────────────────────────────────────────────────

class _ComboColor(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("npCombo")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumWidth(240)


def _elegir_color(dialogo: _Ventanita, texto: str, ops: nps.Opciones, confirmados: list[str]) -> str | None:
    """El color escrito, pasado por «¿Quisiste decir…?». None si se canceló."""
    texto = valores.limpiar(texto)
    if not texto or texto in ops.colores:
        return texto
    revision = valores.revisar_valor(valores.CAMPO_COLOR, texto, ops.usos_color or {})
    if not revision.necesita_pregunta:
        return revision.valor
    eleccion = dialogo.preguntar(dialogo, revision, True)
    if eleccion.accion == ACCION_USAR:
        return eleccion.valor
    if eleccion.accion == ACCION_DEJAR:
        return revision.escrito
    if eleccion.accion == ACCION_CREAR:
        confirmados.append(revision.escrito)
        return revision.escrito
    return None


class OtroColorDialog(_Ventanita):
    def __init__(self, parent: QWidget | None, *, session_factory, usuario_id: int, producto_id: int, **kw) -> None:
        super().__init__(parent, session_factory=session_factory, usuario_id=usuario_id,
                         titulo="Otro color", **kw)
        self.producto_id = int(producto_id)
        self.plan: af.PlanOtroColor | None = None
        self.confirmados: list[str] = []
        self.color_elegido = ""
        self.ops = self._con_sesion(nps.opciones)
        self.antes = self._con_sesion(lambda s: af.leer_ficha(s, self.producto_id))
        if self.antes is not None:
            self.sub.setText(f"{self.antes.nombre} · hoy en {', '.join(self.antes.colores)}")
        self.color = _ComboColor()
        self.color.addItem("Elige…")
        self.color.addItems([c for c in self.ops.colores if self.antes is None or c not in self.antes.colores])
        self.color.setCurrentIndex(0)
        self.color.activated.connect(lambda _i: self._al_color())
        self.color.lineEdit().editingFinished.connect(self._al_color)
        self._fila("COLOR NUEVO", self.color)
        self.cuerpo.addWidget(_etiqueta("npSeccion", "ASÍ QUEDA", envolver=False))
        self.frase = _etiqueta("npFrase")
        self.avisos = _etiqueta("npFichaLinea")
        self.avisos.setProperty("tono", "warning")
        self.nota = _etiqueta("npNota", "Copia todas las tallas activas con sus precios. Existencia en 0; "
                                        "lo que llegue se da de entrada como siempre.")
        for w in (self.frase, self.avisos, self.nota):
            self.cuerpo.addWidget(w)
        self.replanear()

    def _al_color(self) -> None:
        texto = valores.limpiar(self.color.currentText())
        if texto in ("", "Elige…") or texto == self.color_elegido:
            return
        elegido = _elegir_color(self, texto, self.ops, self.confirmados)
        if elegido is None:
            self.color.setCurrentText(self.color_elegido or "Elige…")
            return
        self.elegir(elegido)

    def elegir(self, color: str) -> None:
        self.color_elegido = color
        self.color.blockSignals(True)
        self.color.setCurrentText(color)
        self.color.blockSignals(False)
        self.replanear()

    def replanear(self) -> None:
        if not self.color_elegido:
            self.frase.setText("Elige el color nuevo: se copian todas las tallas con sus precios.")
            _poner(self.avisos, "")
            self._pintar_barra("Crear en el color nuevo", "Elige el color.")
            return
        try:
            self.plan = self._con_sesion(lambda s: af.planear_otro_color(
                s, self.producto_id, self.color_elegido, confirmados=self.confirmados))
        except ValueError as exc:
            self._pintar_barra("Crear en el color nuevo", str(exc))
            return
        self.frase.setText(self.plan.resumen or "")
        _poner(self.avisos, "\n".join(f"⚠ {a}" for a in dict.fromkeys(self.plan.todos_los_avisos)))
        n = len(self.plan.tallas)
        texto = f"Crear {'1 talla' if n == 1 else f'{n} tallas'} en {self.plan.color}"
        self._pintar_barra(texto, _primer_error(self.plan.todos_los_errores))

    def guardar(self):
        plan = self.plan
        return self._con_sesion(lambda s: af.aplicar_otro_color(s, plan, self._usuario(s), commit=True))


# ── Corregir prenda ────────────────────────────────────────────────────────

def _confirmar_bajas(parent, bajas) -> bool:
    from pos_uniformes.ui.helpers.inventario_acciones import confirmar_bajas_de_precio

    return confirmar_bajas_de_precio(parent, bajas)


class CorregirPrendaDialog(_Ventanita):
    ANCHO = 600

    def __init__(self, parent: QWidget | None, *, session_factory, usuario_id: int, producto_id: int,
                 confirmar_bajas: Callable[[QWidget, list], bool] = _confirmar_bajas, **kw) -> None:
        super().__init__(parent, session_factory=session_factory, usuario_id=usuario_id,
                         titulo="Corregir prenda", **kw)
        self.producto_id = int(producto_id)
        self.confirmar_bajas = confirmar_bajas
        self.confirmados: list[str] = []
        self.ops = self._con_sesion(nps.opciones)
        self.plan: cp.PlanCorreccion = self._con_sesion(lambda s: cp.planear_correccion(s, self.producto_id))
        plan = self.plan
        self.color_elegido = plan.color_antes
        self.sub.setText("Cambia el nombre y el color de todas las tallas a la vez. "
                         "Se quedan los códigos, los precios y la existencia.")

        self.nombre = QLineEdit(plan.nombre_sin_escuela_antes)
        self.nombre.setObjectName("npCampo")
        self.nombre.setMinimumWidth(300)
        escuela = _etiqueta("npNotaChica", f"+ {plan.escuela}" if plan.escuela else "sin escuela", envolver=False)
        self._fila("NOMBRE", self.nombre, escuela)

        self.color = _ComboColor()
        self.color.addItems(list(self.ops.colores))
        if plan.color_antes:
            if self.color.findText(plan.color_antes) < 0:
                self.color.addItem(plan.color_antes)
            self.color.setCurrentText(plan.color_antes)
            self._fila("COLOR", self.color)
        else:
            self.color.setEnabled(False)
            self.color.setCurrentText(", ".join(plan.colores_antes))
            self._fila("COLOR", self.color, _etiqueta(
                "npNotaChica", "Tiene tallas de varios colores: el color se corrige talla por talla."))
        self.color.activated.connect(lambda _i: self._al_color())
        self.color.lineEdit().editingFinished.connect(self._al_color)

        # ▸ Precios (plegado): para corregir un precio de la misma vez.
        self.plegable = QToolButton()
        self.plegable.setObjectName("npPlegable")
        self.plegable.setCheckable(True)
        self.plegable.setText(f"▸ Precios de las {len(plan.tallas)} tallas")
        self.plegable.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plegable.toggled.connect(self._plegar)
        self.cuerpo.addWidget(self.plegable, 0, Qt.AlignmentFlag.AlignLeft)
        self.panel = QScrollArea()
        self.panel.setObjectName("npScroll")
        self.panel.setWidgetResizable(True)
        self.panel.setFrameShape(QFrame.Shape.NoFrame)
        self.panel.setMaximumHeight(170)
        vista = QWidget()
        vista.setObjectName("npScrollVista")
        rejilla = QGridLayout(vista)
        rejilla.setContentsMargins(0, 0, 8, 0)
        rejilla.setHorizontalSpacing(10)
        rejilla.setVerticalSpacing(4)
        self.campos_precio: dict[int, QLineEdit] = {}
        for i, t in enumerate(plan.tallas):
            fila, col = divmod(i, 3)
            rejilla.addWidget(_etiqueta("npTalla", t.talla, envolver=False), fila, col * 2)
            campo = QLineEdit(texto_precio(t.precio))
            campo.setObjectName("npPrecio")
            campo.setFixedWidth(84)
            campo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            campo.textEdited.connect(lambda _t: self.rebote.start())
            rejilla.addWidget(campo, fila, col * 2 + 1)
            self.campos_precio[t.variante_id] = campo
        self.panel.setWidget(vista)
        self.panel.hide()
        self.cuerpo.addWidget(self.panel)

        self.cuerpo.addWidget(_etiqueta("npSeccion", "ASÍ QUEDA", envolver=False))
        self.vista_previa = _etiqueta("npFichaNombre")
        self.frase = _etiqueta("npFichaLinea")
        self.etiquetas = _etiqueta("npNota")
        self.bajan = _etiqueta("npFichaLinea")
        self.bajan.setProperty("tono", "danger")
        for w in (self.vista_previa, self.frase, self.etiquetas, self.bajan):
            self.cuerpo.addWidget(w)
        self.nombre.textEdited.connect(lambda _t: self.rebote.start())
        self.replanear()

    def _plegar(self, abierto: bool) -> None:
        self.panel.setVisible(abierto)
        self.plegable.setText(("▾" if abierto else "▸") + self.plegable.text()[1:])
        self.adjustSize()

    def _al_color(self) -> None:
        if not self.color.isEnabled():
            return
        texto = valores.limpiar(self.color.currentText())
        if not texto or texto == self.color_elegido:
            return
        elegido = _elegir_color(self, texto, self.ops, self.confirmados)
        if elegido is None:
            self.color.setCurrentText(self.color_elegido or "")
            return
        self.cambiar_color(elegido)

    def cambiar_color(self, color: str) -> None:
        """El color nuevo; si el nombre llevaba el anterior, también lo cambia."""
        anterior = self.color_elegido
        self.color_elegido = color
        self.color.blockSignals(True)
        self.color.setCurrentText(color)
        self.color.blockSignals(False)
        self.nombre.setText(cp.nombre_con_color_nuevo(self.nombre.text(), anterior, color))
        self.replanear()

    def precios_escritos(self) -> dict[int, object]:
        return {vid: leer_precio(c.text()) for vid, c in self.campos_precio.items()}

    def replanear(self) -> None:
        color = self.color_elegido if self.color.isEnabled() else None
        self.plan = self._con_sesion(lambda s: cp.planear_correccion(
            s, self.producto_id, nombre_sin_escuela=self.nombre.text(), color=color,
            precios_nuevos=self.precios_escritos(), confirmados=self.confirmados))
        plan = self.plan
        self.vista_previa.setText(plan.nombre or plan.nombre_antes)
        self.frase.setText(plan.resumen)
        _poner(self.etiquetas, plan.texto_etiquetas)
        _poner(self.bajan, (f"🔻 {len(plan.bajas)} {'precio baja' if len(plan.bajas) == 1 else 'precios bajan'}: "
                            "se te pedirá confirmar.") if plan.bajas else "")
        bloqueo = _primer_error(plan.errores) or ("" if plan.hay_cambios else "Sin cambios todavía.")
        self._pintar_barra("Guardar cambios", bloqueo)

    def guardar(self):
        plan = self.plan
        permitir = False
        if plan.bajas:
            if not self.confirmar_bajas(self, plan.bajas):
                return None  # Cancelar en el aviso rojo: no se cambia nada
            permitir = True
        return self._con_sesion(lambda s: cp.aplicar_correccion(
            s, plan, self._usuario(s), permitir_bajar=permitir, commit=True))


__all__ = ["CorregirPrendaDialog", "OtroColorDialog", "TallaNuevaDialog"]
