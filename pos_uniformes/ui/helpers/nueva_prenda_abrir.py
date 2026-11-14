"""Conecta «＋ Nueva prenda» de Inventario con su ventana (tanda 3 del alta).

Aquí solo se cablea: la ventana es `ui/dialogs/nueva_prenda_dialog.py` y el
alta, `services/alta_prenda_service.py`. Lo que la ventana pide a la
principal (imprimir etiquetas, ver en Inventario, el formulario anterior,
refrescar) son manejadores que ya existían.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario

if TYPE_CHECKING:  # pragma: no cover
    from pos_uniformes.services.alta_prenda_service import ResultadoAlta
    from pos_uniformes.ui.main_window import MainWindow


def imprimir_etiquetas(window: "MainWindow", variante_ids: list[int]) -> None:
    ids = [int(v) for v in variante_ids if v]
    if not ids:
        return
    if len(ids) == 1:
        window._open_inventory_label_dialog_for_variant(ids[0])
    else:
        window._handle_inventory_print_label_batch(ids)


def ver_en_inventario(window: "MainWindow", resultado: "ResultadoAlta") -> None:
    """Pone el nombre de la prenda en el buscador de Inventario y elige su primera talla."""
    if not resultado.productos:
        return
    producto = resultado.productos[0]
    window.inventory_search_input.setText(producto.nombre)
    window._handle_inventory_filters_changed_reset_page()
    pantalla = getattr(window, "inventario_pantalla", None)
    if pantalla is not None and producto.tallas:
        pantalla.seleccionar(producto.tallas[0].variante_id)


def abrir_nueva_prenda(window: "MainWindow", *, session_factory=get_session):
    """Abre «Nueva prenda» (solo ADMIN). Devuelve el diálogo (para las pruebas)."""
    if getattr(window, "current_role", None) != RolUsuario.ADMIN:
        QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede dar de alta prendas.")
        return None
    from pos_uniformes.ui.dialogs.nueva_prenda_dialog import NuevaPrendaDialog

    dialogo = NuevaPrendaDialog(
        window,
        session_factory=session_factory,
        usuario_id=int(window.user_id),
        al_imprimir=lambda ids: imprimir_etiquetas(window, ids),
        al_ver=lambda resultado: ver_en_inventario(window, resultado),
        al_formulario_anterior=lambda: window._handle_create_product(),
        al_terminar=lambda _resultado: window.refresh_all(),
    )
    dialogo.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialogo.open()
    return dialogo


__all__ = ["abrir_nueva_prenda", "imprimir_etiquetas", "ver_en_inventario"]
