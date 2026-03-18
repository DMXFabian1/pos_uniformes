from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.inventory_overview_helper import (
    build_empty_inventory_overview_view,
    build_error_inventory_overview_view,
    build_inventory_overview_view,
)


class InventoryOverviewHelperTests(unittest.TestCase):
    def test_builds_empty_view(self) -> None:
        view = build_empty_inventory_overview_view()

        self.assertEqual(view.overview_label, "Selecciona una presentacion")
        self.assertEqual(view.status_badge.text, "Sin seleccion")
        self.assertEqual(view.status_badge.tone, "neutral")
        self.assertEqual(view.catalog_selection_label, "Selecciona una presentacion en inventario para gestionar cambios.")
        self.assertEqual(view.toggle_product_label, "Prod.")
        self.assertEqual(view.toggle_variant_label, "Pres.")

    def test_builds_error_view(self) -> None:
        view = build_error_inventory_overview_view()

        self.assertEqual(view.overview_label, "No se pudo cargar la presentacion seleccionada.")
        self.assertEqual(view.status_badge.text, "Error")
        self.assertEqual(view.status_badge.tone, "danger")
        self.assertEqual(view.stock_badge.text, "Sin stock")

    def test_builds_complete_view_for_selected_variant(self) -> None:
        view = build_inventory_overview_view(
            sku="SKU-001",
            product_name="Playera deportiva",
            product_active=True,
            variant_active=False,
            stock_actual=2,
            apartado_cantidad=1,
            talla="CH",
            color="Azul",
            precio_venta=Decimal("199.00"),
            origen_etiqueta="LEGACY",
            escuela_nombre="General",
            tipo_prenda_nombre="Deportivo",
            tipo_pieza_nombre="Playera",
            movement_type="Ajuste Salida",
            movement_quantity=-1,
            movement_date="2026-03-18 10:40",
        )

        self.assertEqual(view.overview_label, "SKU-001")
        self.assertEqual(view.product_label, "Playera deportiva")
        self.assertEqual(view.status_badge.text, "INACTIVA")
        self.assertEqual(view.status_badge.tone, "muted")
        self.assertEqual(view.stock_badge.text, "Bajo")
        self.assertEqual(view.stock_badge.tone, "warning")
        self.assertEqual(
            view.stock_hint_label,
            "Talla CH | Color Azul | Precio 199.00 | LEGACY",
        )
        self.assertEqual(
            view.meta_label,
            "Stock actual 2 | Apartado 1 | Escuela General",
        )
        self.assertEqual(
            view.last_movement_label,
            "Ultimo movimiento: Ajuste Salida | -1 | 2026-03-18 10:40",
        )
        self.assertEqual(
            view.catalog_selection_label,
            "SKU-001 | Playera deportiva | Deportivo | Playera | precio 199.00 | stock 2 | apartado 1",
        )
        self.assertEqual(view.toggle_product_label, "Desactivar prod.")
        self.assertEqual(view.toggle_variant_label, "Activar var.")


if __name__ == "__main__":
    unittest.main()
