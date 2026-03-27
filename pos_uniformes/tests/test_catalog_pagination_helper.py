from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_pagination_helper import build_catalog_pagination_view


class CatalogPaginationHelperTests(unittest.TestCase):
    def test_build_catalog_pagination_view_returns_first_page(self) -> None:
        rows = [{"variante_id": index} for index in range(60)]

        view = build_catalog_pagination_view(rows, current_page_index=0, page_size=25)

        self.assertEqual(len(view.page_rows), 25)
        self.assertEqual(view.current_page_index, 0)
        self.assertEqual(view.total_pages, 3)
        self.assertEqual(view.page_rows[0]["variante_id"], 0)
        self.assertEqual(view.page_rows[-1]["variante_id"], 24)
        self.assertEqual(view.page_label, "1-25 de 60 | p. 1/3")
        self.assertFalse(view.previous_enabled)
        self.assertTrue(view.next_enabled)

    def test_build_catalog_pagination_view_clamps_page_and_handles_empty_rows(self) -> None:
        empty_view = build_catalog_pagination_view([], current_page_index=8, page_size=25)

        self.assertEqual(empty_view.current_page_index, 0)
        self.assertEqual(empty_view.total_pages, 1)
        self.assertEqual(empty_view.page_rows, [])
        self.assertEqual(empty_view.page_label, "0 de 0 | p. 1/1")
        self.assertFalse(empty_view.previous_enabled)
        self.assertFalse(empty_view.next_enabled)

    def test_build_catalog_pagination_view_returns_last_partial_page(self) -> None:
        rows = [{"variante_id": index} for index in range(60)]

        view = build_catalog_pagination_view(rows, current_page_index=2, page_size=25)

        self.assertEqual(len(view.page_rows), 10)
        self.assertEqual(view.page_rows[0]["variante_id"], 50)
        self.assertEqual(view.page_rows[-1]["variante_id"], 59)
        self.assertEqual(view.page_label, "51-60 de 60 | p. 3/3")
        self.assertTrue(view.previous_enabled)
        self.assertFalse(view.next_enabled)


if __name__ == "__main__":
    unittest.main()
