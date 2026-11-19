"""Diálogos viejos de Inventario que salieron de `main_window.py` (2026-11-19).

Pruebas de humo: cada diálogo se arma offscreen con dobles mínimos y
devuelve lo mismo que antes, y el método de `MainWindow` (que conservan su
nombre porque `inventario_acciones` y otras pruebas lo usan) solo delega.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout

from pos_uniformes.ui import main_window as main_window_module
from pos_uniformes.ui.main_window import MainWindow


class _DialogoQueAcepta(QDialog):
    """Doble de `_create_modal_dialog`: no se abre, acepta al instante."""

    ultimo: "_DialogoQueAcepta | None" = None

    def exec(self) -> int:  # noqa: D401 - firma de Qt
        _DialogoQueAcepta.ultimo = self
        return int(QDialog.DialogCode.Accepted)


def _crear_dialogo(title: str, helper_text: str | None = None, width: int = 460, **_kwargs):
    dialog = _DialogoQueAcepta()
    dialog.setWindowTitle(title)
    layout = QVBoxLayout()
    dialog.setLayout(layout)
    return dialog, layout


def _fila(vid: int, *, stock: int = 5, precio: str = "289.00", activa: bool = True) -> dict[str, object]:
    return {
        "variante_id": vid,
        "sku": f"SKU-{vid}",
        "producto_nombre_base": "Pants Muestra",
        "talla": "8",
        "color": "Azul",
        "stock_actual": stock,
        "apartado_cantidad": 0,
        "precio_venta": precio,
        "costo_referencia": None,
        "variante_activa": activa,
    }


class _ConQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class PrecioEnLoteTests(_ConQt):
    def test_sin_filas_avisa_igual_que_antes(self) -> None:
        from pos_uniformes.ui.dialogs.inventory_bulk_price_dialog import prompt_inventory_bulk_price_data

        with self.assertRaisesRegex(ValueError, "cambio masivo de precio"):
            prompt_inventory_bulk_price_data(
                selected_ids=[],
                filtered_rows=[],
                create_modal_dialog=_crear_dialogo,
                generate_reference=lambda prefix="AJL": f"{prefix}-X",
            )

    def test_aceptar_sin_tocar_devuelve_el_lote_sin_cambios(self) -> None:
        from pos_uniformes.ui.dialogs.inventory_bulk_price_dialog import prompt_inventory_bulk_price_data

        resultado = prompt_inventory_bulk_price_data(
            selected_ids=[1],
            filtered_rows=[_fila(1), _fila(2, precio="310.00")],
            create_modal_dialog=_crear_dialogo,
            generate_reference=lambda prefix="AJL": f"{prefix}-X",
        )

        self.assertEqual(resultado["tipo_fuente"], "SELECCION")
        self.assertEqual(resultado["tipo_operacion"], "SET")
        self.assertEqual(resultado["referencia"], "PRL-X")
        self.assertEqual(
            resultado["items"],
            [{"variante_id": 1, "precio_nuevo": "289.00", "estado": "SIN CAMBIOS"}],
        )

    def test_main_window_solo_delega(self) -> None:
        ventana = SimpleNamespace(
            _selected_inventory_variant_ids=lambda: [7],
            inventory_filtered_rows=(_fila(7),),
            _create_modal_dialog=object(),
            _generate_inventory_batch_reference=object(),
        )
        with patch.object(main_window_module, "prompt_inventory_bulk_price_data", return_value={"ok": 1}) as falso:
            self.assertEqual(MainWindow._prompt_inventory_bulk_price_data(ventana), {"ok": 1})
        falso.assert_called_once_with(
            selected_ids=[7],
            filtered_rows=[_fila(7)],
            create_modal_dialog=ventana._create_modal_dialog,
            generate_reference=ventana._generate_inventory_batch_reference,
        )


class AjusteEnLoteTests(_ConQt):
    def test_sin_filas_avisa_igual_que_antes(self) -> None:
        from pos_uniformes.ui.dialogs.inventory_bulk_adjustment_dialog import (
            prompt_inventory_bulk_adjustment_data,
        )

        with self.assertRaisesRegex(ValueError, "ajuste masivo"):
            prompt_inventory_bulk_adjustment_data(
                selected_ids=[],
                filtered_rows=[],
                create_modal_dialog=_crear_dialogo,
                generate_reference=lambda prefix="AJL": f"{prefix}-X",
            )

    def test_aceptar_sin_tocar_devuelve_el_lote_sin_cambios(self) -> None:
        from pos_uniformes.ui.dialogs.inventory_bulk_adjustment_dialog import (
            prompt_inventory_bulk_adjustment_data,
        )

        resultado = prompt_inventory_bulk_adjustment_data(
            selected_ids=[],
            filtered_rows=[_fila(1, stock=4), _fila(2, stock=0)],
            create_modal_dialog=_crear_dialogo,
            generate_reference=lambda prefix="AJL": f"{prefix}-X",
        )

        self.assertEqual(resultado["tipo_fuente"], "FILTRADO")
        self.assertEqual(resultado["tipo_ajuste"], "STOCK_FINAL")
        self.assertEqual(resultado["referencia"], "AJL-X")
        self.assertEqual(
            resultado["items"],
            [
                {"variante_id": 1, "valor": 4, "estado": 0},
                {"variante_id": 2, "valor": 0, "estado": 0},
            ],
        )

    def test_main_window_solo_delega(self) -> None:
        ventana = SimpleNamespace(
            _selected_inventory_variant_ids=lambda: [],
            inventory_filtered_rows=(_fila(3),),
            _create_modal_dialog=object(),
            _generate_inventory_batch_reference=object(),
        )
        with patch.object(
            main_window_module, "prompt_inventory_bulk_adjustment_data", return_value=None
        ) as falso:
            self.assertIsNone(MainWindow._prompt_inventory_bulk_adjustment_data(ventana))
        falso.assert_called_once_with(
            selected_ids=[],
            filtered_rows=[_fila(3)],
            create_modal_dialog=ventana._create_modal_dialog,
            generate_reference=ventana._generate_inventory_batch_reference,
        )


class _SesionFalsa:
    """Doble de `get_session()`: cada `scalars(...).all()` saca la siguiente lista."""

    def __init__(self, *listas: list[object]) -> None:
        self._listas = list(listas)

    def __call__(self) -> "_SesionFalsa":
        return self

    def __enter__(self) -> "_SesionFalsa":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def scalars(self, _consulta: object) -> SimpleNamespace:
        lista = self._listas.pop(0)
        return SimpleNamespace(all=lambda: lista)


def _variante(vid: int, stock: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=vid,
        sku=f"SKU-{vid}",
        stock_actual=stock,
        producto=SimpleNamespace(nombre="Pants Muestra"),
    )


class CorregirExistenciaTests(_ConQt):
    def test_sin_presentaciones_avisa_igual_que_antes(self) -> None:
        from pos_uniformes.ui.dialogs import inventory_adjustment_dialog as modulo

        with patch.object(modulo, "get_session", _SesionFalsa([])):
            with self.assertRaisesRegex(ValueError, "No hay presentaciones activas"):
                modulo.prompt_inventory_adjustment_data(
                    create_modal_dialog=_crear_dialogo,
                    set_combo_value=MainWindow._set_combo_value,
                    prefill_variant_id=lambda: None,
                )

    def test_aceptar_sin_tocar_no_cambia_la_existencia(self) -> None:
        from pos_uniformes.ui.dialogs import inventory_adjustment_dialog as modulo

        with patch.object(modulo, "get_session", _SesionFalsa([_variante(1, 3), _variante(2, 9)])):
            resultado = modulo.prompt_inventory_adjustment_data(
                create_modal_dialog=_crear_dialogo,
                set_combo_value=MainWindow._set_combo_value,
                prefill_variant_id=lambda: 2,
            )

        self.assertEqual(
            resultado,
            {
                "variante_id": 2,
                "cantidad": 0,
                "stock_actual": 9,
                "stock_final": 9,
                "referencia": "",
                "observacion": "",
            },
        )

    def test_main_window_solo_delega(self) -> None:
        ventana = SimpleNamespace(
            _create_modal_dialog=object(),
            _set_combo_value=object(),
            _dialog_prefill_variant_id=object(),
        )
        with patch.object(main_window_module, "prompt_inventory_adjustment_data", return_value=None) as falso:
            self.assertIsNone(MainWindow._prompt_inventory_adjustment_data(ventana))
        falso.assert_called_once_with(
            create_modal_dialog=ventana._create_modal_dialog,
            set_combo_value=ventana._set_combo_value,
            prefill_variant_id=ventana._dialog_prefill_variant_id,
        )


class EntradaDeMercanciaTests(_ConQt):
    def test_sin_proveedor_activo_avisa_igual_que_antes(self) -> None:
        from pos_uniformes.ui.dialogs import inventory_purchase_dialog as modulo

        with patch.object(modulo, "get_session", _SesionFalsa([], [_variante(1, 3)])):
            with self.assertRaisesRegex(ValueError, "al menos un proveedor activo"):
                modulo.prompt_purchase_data(
                    create_modal_dialog=_crear_dialogo,
                    set_combo_value=MainWindow._set_combo_value,
                    prefill_variant_id=lambda: None,
                )

    def test_aceptar_devuelve_proveedor_y_presentacion_elegidos(self) -> None:
        from pos_uniformes.ui.dialogs import inventory_purchase_dialog as modulo

        proveedores = [SimpleNamespace(id=10, nombre="Proveedor Muestra")]
        with patch.object(modulo, "get_session", _SesionFalsa(proveedores, [_variante(1, 3), _variante(2, 0)])):
            resultado = modulo.prompt_purchase_data(
                create_modal_dialog=_crear_dialogo,
                set_combo_value=MainWindow._set_combo_value,
                prefill_variant_id=lambda: 2,
            )

        self.assertEqual(
            resultado,
            {"proveedor_id": 10, "variante_id": 2, "cantidad": 1, "costo": "", "documento": ""},
        )

    def test_main_window_solo_delega(self) -> None:
        ventana = SimpleNamespace(
            _create_modal_dialog=object(),
            _set_combo_value=object(),
            _dialog_prefill_variant_id=object(),
        )
        with patch.object(main_window_module, "prompt_purchase_data", return_value=None) as falso:
            self.assertIsNone(MainWindow._prompt_purchase_data(ventana))
        falso.assert_called_once_with(
            create_modal_dialog=ventana._create_modal_dialog,
            set_combo_value=ventana._set_combo_value,
            prefill_variant_id=ventana._dialog_prefill_variant_id,
        )


if __name__ == "__main__":
    unittest.main()
