from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.inventory_overview_service import (
    InventoryOverviewSnapshot,
    load_inventory_overview_snapshot,
)


class InventoryOverviewServiceTests(unittest.TestCase):
    def test_loads_snapshot_using_catalog_row_overrides_and_last_movement(self) -> None:
        variant = SimpleNamespace(
            id=8,
            sku="SKU-008",
            talla="16",
            color="Azul Marino",
            stock_actual=4,
            precio_venta=Decimal("249.00"),
            activo=False,
            producto=SimpleNamespace(nombre="Chamarra Deportiva | Patria | Chamarra #4"),
        )
        movement = SimpleNamespace(
            tipo_movimiento=SimpleNamespace(value="ajuste_entrada"),
            cantidad=3,
            created_at=datetime(2026, 3, 19, 9, 45),
        )
        session = SimpleNamespace(
            get=lambda _model, _variant_id: variant,
            scalar=lambda _query: movement,
        )

        snapshot = load_inventory_overview_snapshot(
            session,
            variant_id=8,
            catalog_rows=[
                {
                    "variante_id": 8,
                    "producto_nombre_base": "Chamarra Deportiva",
                    "producto_activo": False,
                    "variante_activo": False,
                    "apartado_cantidad": 2,
                    "origen_etiqueta": "LEGACY",
                    "escuela_nombre": "Patria",
                    "tipo_prenda_nombre": "Deportivo",
                    "tipo_pieza_nombre": "Chamarra",
                }
            ],
        )

        self.assertEqual(
            snapshot,
            InventoryOverviewSnapshot(
                sku="SKU-008",
                product_name="Chamarra Deportiva",
                product_active=False,
                variant_active=False,
                stock_actual=4,
                apartado_cantidad=2,
                talla="16",
                color="Azul Marino",
                precio_venta=Decimal("249.00"),
                origen_etiqueta="LEGACY",
                escuela_nombre="Patria",
                tipo_prenda_nombre="Deportivo",
                tipo_pieza_nombre="Chamarra",
                movement_type="Ajuste Entrada",
                movement_quantity=3,
                movement_date="2026-03-19 09:45",
            ),
        )

    def test_loads_snapshot_with_variant_fallbacks_without_matching_catalog_row(self) -> None:
        variant = SimpleNamespace(
            id=9,
            sku="SKU-009",
            talla="CH",
            color="Blanco",
            stock_actual=0,
            precio_venta=Decimal("199.00"),
            activo=True,
            producto=SimpleNamespace(nombre="Playera Polo | Morelos | Playera #7"),
        )
        session = SimpleNamespace(
            get=lambda _model, _variant_id: variant,
            scalar=lambda _query: None,
        )

        snapshot = load_inventory_overview_snapshot(
            session,
            variant_id=9,
            catalog_rows=[],
        )

        self.assertEqual(snapshot.product_name, "Playera Polo | Morelos | Playera")
        self.assertTrue(snapshot.product_active)
        self.assertTrue(snapshot.variant_active)
        self.assertEqual(snapshot.apartado_cantidad, 0)
        self.assertEqual(snapshot.origen_etiqueta, "NUEVO")
        self.assertEqual(snapshot.escuela_nombre, "General")
        self.assertEqual(snapshot.tipo_prenda_nombre, "-")
        self.assertEqual(snapshot.tipo_pieza_nombre, "-")
        self.assertIsNone(snapshot.movement_type)
        self.assertIsNone(snapshot.movement_quantity)
        self.assertEqual(snapshot.movement_date, "")

    def test_raises_for_missing_variant(self) -> None:
        session = SimpleNamespace(
            get=lambda _model, _variant_id: None,
            scalar=lambda _query: None,
        )

        with self.assertRaisesRegex(ValueError, "Presentacion no encontrada"):
            load_inventory_overview_snapshot(
                session,
                variant_id=99,
                catalog_rows=[],
            )


if __name__ == "__main__":
    unittest.main()
