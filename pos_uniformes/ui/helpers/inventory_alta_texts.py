"""Avisos al dar de alta tallas en Inventario, en palabras de la tienda (tanda 2, 2026-11-13).

Antes: «Se crearon 6 presentaciones para '…'», «SKU creados», «Rango: A -> B»,
«Incidencias» y, en las altas sueltas, «Talla 'SKU000004' creada correctamente»
(llamaba talla a un código). Ahora se nombra la talla y la prenda.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from pos_uniformes.utils.product_name import sanitize_product_display_name

TITULO_ERROR_LOTE = "No se pudieron crear las tallas"
_MAX_CODIGOS = 8
_MAX_ERRORES = 4


def mensaje_tallas_creadas(
    nombre: object,
    creadas: int,
    codigos: Sequence[str] = (),
    errores: Sequence[str] = (),
) -> str:
    prenda = _prenda(nombre)
    if creadas == 1:
        texto = f"Se agregó 1 talla a «{prenda}»."
    else:
        texto = f"Se agregaron {creadas} tallas a «{prenda}»."
    if codigos:
        lista = ", ".join(codigos[:_MAX_CODIGOS])
        if len(codigos) > _MAX_CODIGOS:
            lista += f" y {len(codigos) - _MAX_CODIGOS} más"
        texto += f"\n\nCódigos: {lista}."
    if errores:
        detalle = "\n".join(errores[:_MAX_ERRORES])
        if len(errores) > _MAX_ERRORES:
            detalle += f"\n… y {len(errores) - _MAX_ERRORES} más."
        texto += f"\n\nNo se pudieron crear:\n{detalle}"
    return texto


def mensaje_talla_creada(fila: Mapping[str, object] | None, codigo: object) -> str:
    """«Talla 10 (Azul marino) de «Pants…» lista.» Sin la fila, cae al código."""
    if fila:
        talla = str(fila.get("talla") or "").strip()
        color = str(fila.get("color") or "").strip()
        prenda = _prenda(fila.get("producto_nombre_base") or fila.get("producto_nombre"))
        if talla:
            color_txt = f" ({color})" if color else ""
            return f"Talla {talla}{color_txt} de «{prenda}» lista."
    return f"Talla nueva lista (código {str(codigo or '').strip().upper() or '—'})."


def _prenda(nombre: object) -> str:
    return sanitize_product_display_name(str(nombre or "").strip()) or "la prenda"
