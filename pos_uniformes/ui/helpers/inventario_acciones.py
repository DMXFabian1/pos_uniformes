"""Manejadores de la pestaña Inventario que salieron de `main_window.py` (tanda 5).

`main_window.py` es el coordinador y solo conecta: sus métodos
`_handle_inventory_*` siguen existiendo (los llaman el menú «⋯», la barra de
lote y las pruebas por nombre) pero delegan aquí. El código se movió tal
cual, sin cambiar lo que hace; los diálogos `_prompt_inventory_*` siguen en
la ventana.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from PyQt6.QtWidgets import QMessageBox

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario, Usuario, Variante
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.inventario_service import AjusteMasivoFilaInput, InventarioService

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def corregir_existencia(window: "MainWindow") -> None:
    """«Corregir existencia» de una talla (antes `MainWindow._handle_inventory_adjustment`)."""
    if window.current_role != RolUsuario.ADMIN:
        QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede ajustar inventario.")
        return

    try:
        data = window._prompt_inventory_adjustment_data()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(window, "Datos incompletos", str(exc))
        return
    if data is None:
        return

    variante_id = data["variante_id"]
    if not variante_id:
        QMessageBox.warning(window, "Datos incompletos", "Selecciona una presentacion.")
        return

    signed_quantity = int(data["cantidad"])
    if signed_quantity == 0:
        QMessageBox.information(window, "Sin cambios", "El stock final coincide con el stock actual.")
        return
    reference = str(data["referencia"]).strip() or f"ADJ-{uuid4().hex[:8].upper()}"
    note = str(data["observacion"]).strip() or None
    target_stock = int(data.get("stock_final", 0))

    try:
        with get_session() as session:
            user = session.get(Usuario, window.user_id)
            variante = session.get(Variante, int(variante_id))
            if user is None or variante is None:
                raise ValueError("Usuario o presentacion no encontrada.")
            InventarioService.registrar_ajuste_manual(
                session=session,
                variante=variante,
                cantidad=signed_quantity,
                usuario=user,
                referencia=reference,
                observacion=note,
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(window, "Ajuste fallido", str(exc))
        return

    window.refresh_all()
    window._set_combo_value(window.inventory_variant_combo, variante_id)
    QMessageBox.information(
        window,
        "Inventario actualizado",
        f"Ajuste {reference} aplicado correctamente. Stock final: {target_stock}.",
    )


def corregir_existencias_en_lote(window: "MainWindow") -> None:
    """«Corregir existencias» en lote (antes `MainWindow._handle_inventory_bulk_adjustment`)."""
    if window.current_role != RolUsuario.ADMIN:
        QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede ajustar inventario en lote.")
        return

    try:
        data = window._prompt_inventory_bulk_adjustment_data()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(window, "Ajuste masivo no disponible", str(exc))
        return
    if data is None:
        return

    items = [
        AjusteMasivoFilaInput(variante_id=int(item["variante_id"]), valor_capturado=int(item["valor"]))
        for item in data.get("items", [])
    ]
    if not items:
        QMessageBox.warning(window, "Sin filas", "No hay filas para ajustar en el lote.")
        return

    reference = str(data["referencia"]).strip()
    motive = str(data["motivo"]).strip() or "Ajuste masivo desde interfaz POS."
    note = str(data["observacion"]).strip() or None

    try:
        with get_session() as session:
            user = session.get(Usuario, window.user_id)
            if user is None:
                raise ValueError("Usuario no encontrado.")
            lote, preview = InventarioService.aplicar_ajuste_masivo(
                session=session,
                usuario=user,
                tipo_fuente=str(data["tipo_fuente"]),
                tipo_ajuste=str(data["tipo_ajuste"]),
                referencia=reference,
                motivo=motive,
                observacion=note,
                filas_input=items,
            )
            session.commit()
            lote_id = int(lote.id)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(window, "Ajuste masivo fallido", str(exc))
        return

    window.refresh_all()
    QMessageBox.information(
        window,
        "Ajuste masivo aplicado",
        (
            f"Lote {reference} aplicado correctamente.\n"
            f"ID lote: {lote_id}\n"
            f"Filas: {preview.total_filas}\n"
            f"Validas: {preview.filas_validas}\n"
            f"Unidades +: {preview.unidades_positivas}\n"
            f"Unidades -: {preview.unidades_negativas}"
        ),
    )


def cambiar_precios_en_lote(window: "MainWindow") -> None:
    """«Precios en lote» (antes `MainWindow._handle_inventory_bulk_price_update`)."""
    if window.current_role != RolUsuario.ADMIN:
        QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede actualizar precios en lote.")
        return

    try:
        data = window._prompt_inventory_bulk_price_data()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(window, "Precio masivo no disponible", str(exc))
        return
    if data is None:
        return

    items = [
        (int(item["variante_id"]), Decimal(str(item["precio_nuevo"])))
        for item in data.get("items", [])
        if str(item.get("estado", "")) != "ERROR"
    ]
    if not items:
        QMessageBox.warning(window, "Sin filas", "No hay filas validas para actualizar precio en el lote.")
        return

    reference = str(data["referencia"]).strip()
    motive = str(data["motivo"]).strip() or "Cambio masivo de precio desde interfaz POS."
    note = str(data["observacion"]).strip() or None

    try:
        with get_session() as session:
            user = session.get(Usuario, window.user_id)
            if user is None:
                raise ValueError("Usuario no encontrado.")
            resumen = CatalogService.aplicar_cambio_masivo_precio(
                session=session,
                usuario=user,
                referencia=reference,
                motivo=motive,
                observacion=note,
                precios_por_variante=items,
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(window, "Precio masivo fallido", str(exc))
        return

    window.refresh_all()
    QMessageBox.information(
        window,
        "Precio masivo aplicado",
        (
            f"Lote {reference} aplicado correctamente.\n"
            f"Filas: {resumen['total_filas']}\n"
            f"Actualizadas: {resumen['aplicadas']}\n"
            f"Suben: {resumen['suben']}\n"
            f"Bajan: {resumen['bajan']}\n"
            f"Sin cambios: {resumen['sin_cambios']}"
        ),
    )


def conteo_fisico_viejo(window: "MainWindow") -> None:
    """«Conteo físico» viejo, escondido desde la tanda 5 (antes `MainWindow._handle_inventory_count`)."""
    if window.current_role != RolUsuario.ADMIN:
        QMessageBox.warning(window, "Sin permisos", "Solo ADMIN puede realizar conteos fisicos.")
        return

    try:
        data = window._prompt_inventory_count_data()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(window, "Conteo no disponible", str(exc))
        return
    if data is None:
        return

    conteos = list(data.get("conteos", []))
    if not conteos:
        QMessageBox.information(window, "Sin diferencias", "No se detectaron diferencias entre sistema y conteo.")
        return

    reference = str(data["referencia"]).strip() or f"CONTEO-{uuid4().hex[:8].upper()}"
    note = str(data["observacion"]).strip() or "Conteo fisico desde interfaz POS."
    todos_variante_ids: list[int] = [int(v) for v in data.get("todos_variante_ids", [])]

    try:
        with get_session() as session:
            user = session.get(Usuario, window.user_id)
            if user is None:
                raise ValueError("Usuario no encontrado.")
            now = datetime.now(tz=timezone.utc)
            applied_ids: set[int] = set()
            for row in conteos:
                variante = session.get(Variante, int(row["variante_id"]))
                if variante is None:
                    raise ValueError("Presentacion no encontrada durante el conteo.")
                InventarioService.registrar_ajuste_manual(
                    session=session,
                    variante=variante,
                    cantidad=int(row["delta"]),
                    usuario=user,
                    referencia=reference,
                    observacion=(
                        f"{note} Stock sistema {row['stock_sistema']} -> contado {row['stock_contado']}."
                    ),
                )
                variante.ultimo_conteo_at = now
                applied_ids.add(int(row["variante_id"]))
            for variante_id in todos_variante_ids:
                if variante_id not in applied_ids:
                    v = session.get(Variante, variante_id)
                    if v is not None:
                        v.ultimo_conteo_at = now
            session.commit()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(window, "Conteo fallido", str(exc))
        return

    window.refresh_all()
    QMessageBox.information(
        window,
        "Conteo aplicado",
        f"Conteo {reference} aplicado correctamente. Filas ajustadas: {len(conteos)}.",
    )
