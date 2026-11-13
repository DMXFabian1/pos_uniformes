"""«¿Quisiste decir…?» al guardar una prenda (tanda 1 del alta, 2026-11-13).

Cuando lo escrito en escuela, tipo, pieza, atributo, nivel, categoría, talla
o color no es un valor que ya existe (o es una escritura vieja como «Uni» o
«Blanca»), se pregunta antes de guardar:

    «Blanca» se parece a «Blanco» (125 tallas).
    [Usar Blanco]  [Es otro, crearlo]  [Corregir]

«Usar…» es el botón por defecto. Nada nuevo se crea sin que el usuario toque
«Es otro, crearlo». Una escuela nueva pregunta «¿Es la misma que…?» y solo
ADMIN la puede crear.

La decisión (qué preguntar) vive en `services/catalogo_valores_service.py`;
aquí solo está la ventanita y el recorrido de los campos del formulario.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from PyQt6.QtWidgets import QMessageBox, QWidget

from pos_uniformes.services.catalogo_valores_service import (
    CAMPO_ESCUELA,
    Revision,
    limpiar,
    revisar_valor,
)

ACCION_USAR = "usar"
ACCION_CREAR = "crear"
ACCION_DEJAR = "dejar"
ACCION_CORREGIR = "corregir"


@dataclass(frozen=True)
class Eleccion:
    accion: str
    valor: str = ""


@dataclass(frozen=True)
class Campo:
    """Un valor del formulario a revisar. `clave` lo identifica (p. ej.
    «escuela» o «talla:3»); `inicial` es lo que traía al abrir (al editar,
    lo que no se tocó no se pregunta)."""

    clave: str
    campo: str
    texto: str
    inicial: str = ""


@dataclass
class Resultado:
    valores: dict[str, str] = field(default_factory=dict)
    nuevos: dict[str, list[str]] = field(default_factory=dict)

    def nuevos_de(self, campo: str) -> list[str]:
        return list(self.nuevos.get(campo, []))


Preguntar = Callable[[QWidget | None, Revision, bool], Eleccion]


def preguntar_quisiste_decir(parent: QWidget | None, revision: Revision, puede_crear: bool = True) -> Eleccion:
    """Muestra la pregunta y devuelve lo que eligió el usuario."""
    es_escuela = revision.campo == CAMPO_ESCUELA and not revision.existe
    box = QMessageBox(parent)
    box.setObjectName("quisisteDecirDialog")
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("¿Es la misma escuela?" if es_escuela else "¿Quisiste decir…?")
    box.setText(revision.texto_pregunta())
    if not puede_crear:
        box.setInformativeText("Solo ADMIN puede crear una escuela nueva.")
    elif revision.sugerencias and not revision.existe:
        box.setInformativeText(
            "Si de verdad es otra, créala; si no, usa la que ya existe para no duplicar."
            if es_escuela
            else "Si de verdad es otro, créalo; si no, usa el que ya existe para no duplicar."
        )
    botones: dict[object, Eleccion] = {}
    primero = None
    for parecido in revision.sugerencias:
        texto = f"Sí, es «{parecido.valor}»" if es_escuela else f"Usar {parecido.valor}"
        boton = box.addButton(texto, QMessageBox.ButtonRole.AcceptRole)
        botones[boton] = Eleccion(ACCION_USAR, parecido.valor)
        primero = primero or boton
    if revision.existe:
        boton = box.addButton(f"Dejar «{revision.escrito}»", QMessageBox.ButtonRole.ActionRole)
        botones[boton] = Eleccion(ACCION_DEJAR, revision.escrito)
    elif puede_crear:
        if es_escuela:
            texto = "No, es otra: crearla" if revision.sugerencias else "Crear la escuela"
        else:
            texto = "Es otro, crearlo"
        boton = box.addButton(texto, QMessageBox.ButtonRole.ActionRole)
        botones[boton] = Eleccion(ACCION_CREAR, revision.escrito)
        primero = primero or boton
    corregir = box.addButton("Corregir", QMessageBox.ButtonRole.RejectRole)
    botones[corregir] = Eleccion(ACCION_CORREGIR)
    box.setDefaultButton(primero or corregir)
    box.setEscapeButton(corregir)
    box.exec()
    return botones.get(box.clickedButton(), Eleccion(ACCION_CORREGIR))


def confirmar_valores(
    parent: QWidget | None,
    campos: Iterable[Campo],
    *,
    usos_de: Callable[[str], dict[str, int]],
    puede_crear_escuela: bool,
    preguntar: Preguntar = preguntar_quisiste_decir,
) -> Resultado | None:
    """Revisa cada campo y pregunta lo necesario. None = el usuario quiere
    corregir (el formulario se queda abierto)."""
    resultado = Resultado()
    cache: dict[str, dict[str, int]] = {}

    def usos(campo: str) -> dict[str, int]:
        if campo not in cache:
            cache[campo] = usos_de(campo)
        return cache[campo]

    for campo in campos:
        texto = limpiar(campo.texto)
        if not texto or (campo.inicial and texto == limpiar(campo.inicial)):
            resultado.valores[campo.clave] = texto
            continue
        revision = revisar_valor(campo.campo, texto, usos(campo.campo))
        if not revision.necesita_pregunta:
            resultado.valores[campo.clave] = revision.valor
            continue
        puede_crear = puede_crear_escuela if campo.campo == CAMPO_ESCUELA else True
        eleccion = preguntar(parent, revision, puede_crear)
        if eleccion.accion == ACCION_USAR:
            resultado.valores[campo.clave] = eleccion.valor
        elif eleccion.accion == ACCION_DEJAR:
            resultado.valores[campo.clave] = revision.escrito
        elif eleccion.accion == ACCION_CREAR and puede_crear:
            resultado.valores[campo.clave] = revision.escrito
            resultado.nuevos.setdefault(campo.campo, []).append(revision.escrito)
        else:
            return None
    return resultado
