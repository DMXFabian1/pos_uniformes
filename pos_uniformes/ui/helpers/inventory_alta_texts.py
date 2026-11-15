"""Avisos al dar de alta tallas en Inventario, en palabras de la tienda (tanda 2, 2026-11-13).

Antes: «Se crearon 6 presentaciones para '…'», «SKU creados», «Rango: A -> B»,
«Incidencias» y, en las altas sueltas, «Talla 'SKU000004' creada correctamente»
(llamaba talla a un código). Ahora se nombra la talla y la prenda.
Tanda 5 del alta: el aviso del lote de tallas se fue con el asistente viejo.
"""

from __future__ import annotations

from typing import Mapping

from pos_uniformes.utils.product_name import sanitize_product_display_name

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
