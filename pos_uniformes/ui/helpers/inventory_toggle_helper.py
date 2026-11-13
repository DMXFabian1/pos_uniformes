"""Desactivar una talla o toda la prenda, siempre preguntando antes (tanda 2, 2026-11-13).

Antes los botones decían «Prod.» y «Pres.» y desactivaban con un solo clic, al
lado de la impresión de etiquetas. Ahora dicen lo que hacen y piden
confirmación con los avisos del programa (`avisos_bonitos` les da la cara: el
primer párrafo sale como título). Activar no pregunta: no quita nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from pos_uniformes.utils.product_name import sanitize_product_display_name

BOTON_TALLA = {True: "Desactivar esta talla…", False: "Activar esta talla"}
BOTON_PRENDA = {True: "Desactivar toda la prenda…", False: "Activar toda la prenda"}


@dataclass(frozen=True)
class Confirmacion:
    titulo: str
    texto: str
    boton_si: str


def etiqueta_boton_talla(activa: bool) -> str:
    return BOTON_TALLA[bool(activa)]


def etiqueta_boton_prenda(activa: bool) -> str:
    return BOTON_PRENDA[bool(activa)]


def confirmacion_desactivar_talla(producto: object, talla: object, color: object = "") -> Confirmacion:
    nombre = sanitize_product_display_name(str(producto or "").strip()) or "esta prenda"
    color_txt = f" ({str(color).strip()})" if str(color or "").strip() else ""
    return Confirmacion(
        titulo="Desactivar talla",
        texto=(
            f"¿Desactivar la talla {str(talla or '').strip() or '—'} de {nombre}{color_txt}?\n\n"
            "No se borra, deja de venderse. La puedes volver a activar desde su ficha."
        ),
        boton_si="Desactivar talla",
    )


def confirmacion_desactivar_prenda(producto: object, tallas: int | None = None) -> Confirmacion:
    nombre = sanitize_product_display_name(str(producto or "").strip()) or "esta prenda"
    if tallas and tallas > 1:
        cuales = f"Sus {tallas} tallas dejan de venderse."
    elif tallas == 1:
        cuales = "Su única talla deja de venderse."
    else:
        cuales = "Todas sus tallas dejan de venderse."
    return Confirmacion(
        titulo="Desactivar prenda",
        texto=(
            f"¿Desactivar toda la prenda {nombre}?\n\n"
            f"{cuales} No se borra: la puedes volver a activar desde su ficha."
        ),
        boton_si="Desactivar prenda",
    )


def contar_tallas_de_prenda(filas: Iterable[Mapping[str, object]], producto_id: object) -> int | None:
    """Cuántas tallas de la prenda se venden hoy (las ya desactivadas no cuentan)."""
    if producto_id in (None, ""):
        return None
    try:
        pid = int(producto_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    total = sum(
        1
        for fila in filas
        if _entero(fila.get("producto_id")) == pid and fila.get("variante_activa", True) is not False
    )
    return total or None


def preguntar(parent, confirmacion: Confirmacion) -> bool:
    """Aviso del programa con «Cancelar» por defecto. True si dijo que sí."""
    from PyQt6.QtWidgets import QMessageBox

    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setWindowTitle(confirmacion.titulo)
    caja.setText(confirmacion.texto)
    si = caja.addButton(confirmacion.boton_si, QMessageBox.ButtonRole.DestructiveRole)
    no = caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caja.setDefaultButton(no)
    caja.setEscapeButton(no)
    caja.exec()
    return caja.clickedButton() is si


def _entero(valor: object) -> int | None:
    try:
        return int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
