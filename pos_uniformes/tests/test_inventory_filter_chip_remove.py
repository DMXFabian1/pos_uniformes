"""Los chips de filtro activo de Inventario se pueden quitar todos.

2026-11-13: «Conteo», «Precio» y «$ exacto» se creaban como chip pero al
cerrarlos no pasaba nada (faltaban en _handle_remove_inventory_filter_token).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit  # noqa: E402

from pos_uniformes.services.active_filter_service import ActiveFilterToken  # noqa: E402
from pos_uniformes.ui.main_window import MainWindow  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _combo(*datos: str) -> QComboBox:
    combo = QComboBox()
    combo.addItem("todos", "")
    for dato in datos:
        combo.addItem(dato, dato)
    combo.setCurrentIndex(1)
    return combo


class QuitarChipsInventarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.refrescos = 0

        def _refrescar() -> None:
            self.refrescos += 1

        self.ventana = SimpleNamespace(
            inventory_use_filter_combo=_combo("school_only"),
            inventory_status_filter_combo=_combo("active"),
            inventory_stock_filter_combo=_combo("negative"),
            inventory_origin_filter_combo=_combo("legacy"),
            inventory_duplicate_filter_combo=_combo("fallback"),
            inventory_conteo_filter_combo=_combo("stale"),
            inventory_precio_filter_combo=_combo("under_100"),
            inventory_search_input=QLineEdit("pants"),
            inventory_precio_text_input=QLineEdit("249"),
            inventory_brand_filter_combo=None,
            inventory_school_filter_combo=None,
            inventory_type_filter_combo=None,
            inventory_piece_filter_combo=None,
            inventory_size_filter_combo=None,
            inventory_color_filter_combo=None,
            _handle_inventory_filters_changed_reset_page=_refrescar,
        )

    def _quitar(self, key: str, value: str = "x") -> None:
        MainWindow._handle_remove_inventory_filter_token(
            self.ventana, ActiveFilterToken(key=key, display_text=key, value=value)
        )

    def test_quitar_conteo(self) -> None:
        self._quitar("conteo")
        self.assertEqual(self.ventana.inventory_conteo_filter_combo.currentIndex(), 0)
        self.assertEqual(self.refrescos, 1)

    def test_quitar_precio(self) -> None:
        self._quitar("precio")
        self.assertEqual(self.ventana.inventory_precio_filter_combo.currentIndex(), 0)
        self.assertEqual(self.refrescos, 1)

    def test_quitar_precio_exacto(self) -> None:
        self._quitar("precio_exacto", "$249")
        self.assertEqual(self.ventana.inventory_precio_text_input.text(), "")
        self.assertEqual(self.refrescos, 1)

    def test_quitar_texto_y_stock_sigue_funcionando(self) -> None:
        self._quitar("texto", "pants")
        self._quitar("stock")
        self.assertEqual(self.ventana.inventory_search_input.text(), "")
        self.assertEqual(self.ventana.inventory_stock_filter_combo.currentIndex(), 0)
        self.assertEqual(self.refrescos, 2)


if __name__ == "__main__":
    unittest.main()
