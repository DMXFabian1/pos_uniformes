"""Avisos al pasar el mouse en la pestaña Inventario, en palabras de la tienda (tanda 2, 2026-11-13).

Antes vivían en `MainWindow._configure_help_texts`, sin acentos y con jerga
(«presentacion», «stock», «preview», «La logica completa se integrara…»), y
como esa función corre después de armar la vista, pisaba los textos nuevos de
`inventory_view.py`. Ahora hay una sola fuente: este mapa, que se aplica al
final de `_configure_help_texts`.
"""

from __future__ import annotations

AYUDA_IMPRIMIR_ETIQUETA = "Con una talla elegida imprime su etiqueta; con varias, las imprime en lote."

# atributo de MainWindow → aviso
AYUDAS_INVENTARIO: dict[str, str] = {
    "inventory_category_button": "Crear una categoría nueva (p. ej. Uniformes, Accesorios).",
    "inventory_brand_button": "Crear una marca nueva.",
    "purchase_button": "Sumar a la talla elegida la mercancía que llegó del proveedor.",
    "inventory_adjust_button": "Corregir a mano cuántas hay de la talla elegida, con su motivo.",
    "inventory_count_button": "Contar las piezas y corregir las diferencias contra lo que dice el sistema.",
    "inventory_bulk_adjust_button": "Corregir cuántas hay de varias tallas a la vez.",
    "inventory_bulk_price_button": "Cambiar el precio de varias tallas a la vez.",
    "inventory_print_label_button": AYUDA_IMPRIMIR_ETIQUETA,
    "inventory_generate_all_qr_button": "Guarda el QR de las tallas elegidas en la tabla (la etiqueta ya lo hace sola).",
    "inventory_search_input": (
        "Busca por prenda, escuela, talla, color, marca o código. "
        "Para afinar, también acepta «sku:», «producto:» o «color:»."
    ),
    "inventory_clear_filters_button": "Quita todos los filtros y vuelve a mostrar todas las tallas.",
}


def aplicar_ayudas_inventario(window) -> None:
    """Pone el aviso (y la línea de estado) a cada control de Inventario que exista."""
    for nombre, texto in AYUDAS_INVENTARIO.items():
        widget = getattr(window, nombre, None)
        if widget is None:
            continue
        widget.setToolTip(texto)
        widget.setStatusTip(texto)
        widget.setWhatsThis(texto)
