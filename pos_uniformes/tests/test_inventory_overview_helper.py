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

        self.assertEqual(view.overview_label, "Elige una talla")
        self.assertEqual(view.status_badge.text, "Sin selección")
        self.assertEqual(view.status_badge.tone, "neutral")
        self.assertEqual(view.catalog_selection_label, "Elige una talla en Inventario para hacer cambios.")
        self.assertEqual(view.stock_badge.text, "—")  # «Sin stock» se leía como «agotado»
        self.assertEqual(view.toggle_product_label, "Desactivar toda la prenda…")
        self.assertEqual(view.toggle_variant_label, "Desactivar esta talla…")

    def test_builds_error_view(self) -> None:
        view = build_error_inventory_overview_view()

        self.assertEqual(view.overview_label, "No se pudo cargar la talla elegida.")
        self.assertEqual(view.status_badge.text, "Error")
        self.assertEqual(view.status_badge.tone, "danger")
        self.assertEqual(view.stock_badge.text, "—")

    def test_builds_complete_view_for_selected_variant(self) -> None:
        view = build_inventory_overview_view(
            sku="SKU-001",
            product_name="Playera deportiva",
            product_active=True,
            variant_active=False,
            stock_actual=2,
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
        self.assertEqual(view.status_badge.text, "Desactivada")
        self.assertEqual(view.status_badge.tone, "muted")
        self.assertEqual(view.stock_badge.text, "Quedan pocas")
        self.assertEqual(view.stock_badge.tone, "warning")
        self.assertEqual(
            view.stock_hint_label,
            "Talla CH · Azul · $199",
        )
        self.assertEqual(
            view.meta_label,
            "Hay 2 · General",
        )
        self.assertEqual(
            view.last_movement_label,
            "Último movimiento: Ajuste Salida \u22121 · 2026-03-18 10:40",
        )
        self.assertEqual(
            view.catalog_selection_label,
            "SKU-001 | Playera deportiva | Deportivo | Playera | precio 199.00 | stock 2",
        )
        self.assertEqual(view.toggle_product_label, "Desactivar toda la prenda…")
        self.assertEqual(view.toggle_variant_label, "Activar esta talla")

    def test_ficha_dice_el_mismo_precio_rebajado_que_la_tabla(self) -> None:
        comunes = dict(
            sku="SKU000008",
            product_name="Pants",
            product_active=True,
            variant_active=True,
            stock_actual=5,
            talla="6",
            color="Azul marino",
            precio_venta=Decimal("250.00"),
            origen_etiqueta="NUEVO",
            escuela_nombre="General",
            tipo_prenda_nombre="Deportivo",
            tipo_pieza_nombre="Pants",
            movement_type=None,
            movement_quantity=None,
            movement_date="",
        )
        con_oferta = build_inventory_overview_view(**comunes, rebaja_tipo="oferta", rebaja_precio=Decimal("175"))
        self.assertEqual(con_oferta.stock_hint_label, "Talla 6 · Azul marino · Oferta $175")
        sin_oferta = build_inventory_overview_view(**comunes)
        self.assertEqual(sin_oferta.stock_hint_label, "Talla 6 · Azul marino · $250")

    def test_sanitizes_legacy_hash_in_product_name(self) -> None:
        view = build_inventory_overview_view(
            sku="SKU-001",
            product_name="Playera deportiva | Patria | Deportivo | Playera #4",
            product_active=True,
            variant_active=True,
            stock_actual=5,
            talla="14",
            color="Azul",
            precio_venta=Decimal("199.00"),
            origen_etiqueta="LEGACY",
            escuela_nombre="Patria",
            tipo_prenda_nombre="Deportivo",
            tipo_pieza_nombre="Playera",
            movement_type=None,
            movement_quantity=None,
            movement_date="",
        )

        self.assertEqual(view.product_label, "Playera deportiva | Patria | Deportivo | Playera")
        self.assertNotIn("#4", view.product_label)

    def test_ficha_marca_negativo_en_rojo(self) -> None:
        view = build_inventory_overview_view(
            sku="SKU-009",
            product_name="Pants",
            product_active=True,
            variant_active=True,
            stock_actual=-1,
            talla="8",
            color="Azul",
            precio_venta=Decimal("299.00"),
            origen_etiqueta="NUEVO",
            escuela_nombre="General",
            tipo_prenda_nombre="Deportivo",
            tipo_pieza_nombre="Pants 2pz",
            movement_type=None,
            movement_quantity=None,
            movement_date="",
        )
        self.assertEqual(view.stock_badge.text, "En negativo")
        self.assertEqual(view.stock_badge.tone, "danger")


    def _ficha_3pz(self, stock: int, *, es_conjunto: bool):
        return build_inventory_overview_view(
            sku="SKU-3PZ",
            product_name="Pants 3pz JS",
            product_active=True,
            variant_active=True,
            stock_actual=stock,
            talla="10",
            color="Rojo",
            precio_venta=Decimal("450.00"),
            origen_etiqueta="NUEVO",
            escuela_nombre="Justo Sierra",
            tipo_prenda_nombre="Deportivo",
            tipo_pieza_nombre="-",  # la fila de Catálogo no estaba en su filtro
            movement_type=None,
            movement_quantity=None,
            movement_date="",
            es_conjunto=es_conjunto,
        )

    def test_ficha_de_conjunto_clasifica_igual_que_la_tabla(self) -> None:
        self.assertEqual(self._ficha_3pz(2, es_conjunto=True).stock_badge.text, "Conjunto")
        self.assertEqual(self._ficha_3pz(2, es_conjunto=True).stock_badge.tone, "neutral")
        cero = self._ficha_3pz(0, es_conjunto=True)
        self.assertEqual((cero.stock_badge.text, cero.stock_badge.tone), ("Agotada", "danger"))
        self.assertEqual(self._ficha_3pz(2, es_conjunto=False).stock_badge.text, "Quedan pocas")

class FichaDiceSiSeVendeTests(unittest.TestCase):
    """Tanda 2: sin columna «Estado», la ficha dice «Desactivada»."""

    def _ficha(self, *, product_active: bool, variant_active: bool):
        return build_inventory_overview_view(
            sku="SKU-9", product_name="Pants", product_active=product_active, variant_active=variant_active,
            stock_actual=3, talla="10", color="Azul", precio_venta=Decimal("320"), origen_etiqueta="NUEVO",
            escuela_nombre="General", tipo_prenda_nombre="-", tipo_pieza_nombre="-",
            movement_type=None, movement_quantity=None, movement_date="",
        )

    def test_activa(self) -> None:
        self.assertEqual(self._ficha(product_active=True, variant_active=True).status_badge.text, "Activa")

    def test_talla_desactivada(self) -> None:
        badge = self._ficha(product_active=True, variant_active=False).status_badge
        self.assertEqual((badge.text, badge.tone), ("Desactivada", "muted"))

    def test_prenda_desactivada_gana(self) -> None:
        badge = self._ficha(product_active=False, variant_active=True).status_badge
        self.assertEqual((badge.text, badge.tone), ("Prenda desactivada", "muted"))


if __name__ == "__main__":
    unittest.main()
