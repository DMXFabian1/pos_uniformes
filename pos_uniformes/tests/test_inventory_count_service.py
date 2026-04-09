from __future__ import annotations

import unittest

from pos_uniformes.services.inventory_count_service import (
    InventoryCountRow,
    InventoryCountVariantView,
    accumulate_inventory_count_scan,
    build_inventory_count_payload,
    build_inventory_count_row,
    build_inventory_count_rows_from_snapshot_rows,
    build_inventory_count_summary,
    remove_inventory_count_row,
    update_inventory_count_row_counted_stock,
    upsert_inventory_count_row,
)


class InventoryCountServiceTests(unittest.TestCase):
    def test_build_inventory_count_row_calculates_delta(self) -> None:
        variant = InventoryCountVariantView(
            variante_id=7,
            sku="SKU000007",
            producto_nombre="Camisa blanca",
            talla="32",
            color="Blanco",
            escuela_nombre="General",
            stock_actual=5,
        )

        row = build_inventory_count_row(variant, counted_stock=3)

        self.assertEqual(row.delta, -2)
        self.assertEqual(row.stock_sistema, 5)
        self.assertEqual(row.stock_contado, 3)

    def test_upsert_inventory_count_row_replaces_existing_variant(self) -> None:
        rows = [
            InventoryCountRow(
                variante_id=3,
                sku="SKU000003",
                producto_nombre="Playera",
                stock_sistema=4,
                stock_contado=6,
                delta=2,
            )
        ]

        updated_rows = upsert_inventory_count_row(
            rows,
            InventoryCountRow(
                variante_id=3,
                sku="SKU000003",
                producto_nombre="Playera",
                stock_sistema=4,
                stock_contado=1,
                delta=-3,
            ),
        )

        self.assertEqual(len(updated_rows), 1)
        self.assertEqual(updated_rows[0].delta, -3)

    def test_summary_and_payload_only_apply_changed_rows(self) -> None:
        rows = [
            InventoryCountRow(
                variante_id=1,
                sku="SKU000001",
                producto_nombre="Bata",
                stock_sistema=2,
                stock_contado=4,
                delta=2,
            ),
            InventoryCountRow(
                variante_id=2,
                sku="SKU000002",
                producto_nombre="Playera",
                stock_sistema=5,
                stock_contado=5,
                delta=0,
            ),
            InventoryCountRow(
                variante_id=3,
                sku="SKU000003",
                producto_nombre="Pants",
                stock_sistema=8,
                stock_contado=6,
                delta=-2,
            ),
        ]

        summary = build_inventory_count_summary(rows)
        payload = build_inventory_count_payload(reference=" C-01 ", observation=" Piso ", rows=rows)

        self.assertEqual(summary.changed_rows, 2)
        self.assertEqual(summary.increases, 1)
        self.assertEqual(summary.decreases, 1)
        self.assertEqual(summary.zero_rows, 1)
        self.assertEqual(payload["reference"], "C-01")
        self.assertEqual(payload["observation"], "Piso")
        self.assertEqual(len(payload["rows"]), 2)

    def test_remove_inventory_count_row_drops_variant(self) -> None:
        rows = [
            InventoryCountRow(
                variante_id=1,
                sku="SKU000001",
                producto_nombre="Bata",
                stock_sistema=2,
                stock_contado=4,
                delta=2,
            ),
            InventoryCountRow(
                variante_id=2,
                sku="SKU000002",
                producto_nombre="Playera",
                stock_sistema=5,
                stock_contado=3,
                delta=-2,
            ),
        ]

        updated_rows = remove_inventory_count_row(rows, variante_id=1)

        self.assertEqual(len(updated_rows), 1)
        self.assertEqual(updated_rows[0].variante_id, 2)

    def test_build_inventory_count_rows_from_snapshot_rows_prefills_counted_with_system_stock(self) -> None:
        rows = build_inventory_count_rows_from_snapshot_rows(
            [
                {
                    "variante_id": 11,
                    "sku": "SKU000011",
                    "producto_nombre_base": "Bata",
                    "talla": "12",
                    "color": "Blanca",
                    "escuela_nombre": "General",
                    "stock_actual": 9,
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stock_sistema, 9)
        self.assertEqual(rows[0].stock_contado, 9)
        self.assertEqual(rows[0].delta, 0)

    def test_update_inventory_count_row_counted_stock_recalculates_delta(self) -> None:
        rows = [
            InventoryCountRow(
                variante_id=11,
                sku="SKU000011",
                producto_nombre="Bata",
                stock_sistema=9,
                stock_contado=9,
                delta=0,
            )
        ]

        updated_rows = update_inventory_count_row_counted_stock(
            rows,
            variante_id=11,
            counted_stock=6,
        )

        self.assertEqual(updated_rows[0].stock_contado, 6)
        self.assertEqual(updated_rows[0].delta, -3)

    def test_accumulate_inventory_count_scan_increments_existing_variant(self) -> None:
        variant = InventoryCountVariantView(
            variante_id=11,
            sku="SKU000011",
            producto_nombre="Bata",
            talla="12",
            color="Blanca",
            escuela_nombre="General",
            stock_actual=9,
        )
        rows = [
            InventoryCountRow(
                variante_id=11,
                sku="SKU000011",
                producto_nombre="Bata",
                stock_sistema=9,
                stock_contado=1,
                delta=-8,
            )
        ]

        updated_rows = accumulate_inventory_count_scan(rows, variant=variant)

        self.assertEqual(updated_rows[0].stock_contado, 2)
        self.assertEqual(updated_rows[0].delta, -7)


if __name__ == "__main__":
    unittest.main()
