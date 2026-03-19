from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_selection_helper import (
    collect_selected_inventory_variant_ids,
    find_catalog_row_by_variant_id,
    find_inventory_row_index_by_variant_id,
    normalize_inventory_variant_id,
    resolve_selected_catalog_row,
)


class InventorySelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_catalog_row_prefers_inventory_variant_id(self) -> None:
        catalog_rows = [
            {"variante_id": 7, "sku": "SKU-007"},
            {"variante_id": 8, "sku": "SKU-008"},
        ]

        selected = resolve_selected_catalog_row(
            inventory_variant_id="8",
            catalog_table_row=0,
            catalog_rows=catalog_rows,
        )

        self.assertEqual(selected, {"variante_id": 8, "sku": "SKU-008"})

    def test_resolve_selected_catalog_row_falls_back_to_catalog_table_row(self) -> None:
        catalog_rows = [
            {"variante_id": 7, "sku": "SKU-007"},
            {"variante_id": 8, "sku": "SKU-008"},
        ]

        selected = resolve_selected_catalog_row(
            inventory_variant_id=None,
            catalog_table_row=1,
            catalog_rows=catalog_rows,
        )

        self.assertEqual(selected, {"variante_id": 8, "sku": "SKU-008"})

    def test_find_catalog_row_by_variant_id_returns_none_for_unknown_variant(self) -> None:
        selected = find_catalog_row_by_variant_id(
            [{"variante_id": 7, "sku": "SKU-007"}],
            "99",
        )

        self.assertIsNone(selected)

    def test_collect_selected_inventory_variant_ids_deduplicates_and_skips_invalid(self) -> None:
        selected_ids = collect_selected_inventory_variant_ids([7, "7", None, "x", 8, "8", 9])

        self.assertEqual(selected_ids, [7, 8, 9])

    def test_find_inventory_row_index_by_variant_id_supports_string_and_int_values(self) -> None:
        row_index = find_inventory_row_index_by_variant_id([None, "7", 8, "9"], 8)

        self.assertEqual(row_index, 2)

    def test_normalize_inventory_variant_id_rejects_invalid_values(self) -> None:
        self.assertEqual(normalize_inventory_variant_id("12"), 12)
        self.assertIsNone(normalize_inventory_variant_id("abc"))
        self.assertIsNone(normalize_inventory_variant_id(None))


if __name__ == "__main__":
    unittest.main()
