from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_label_print_helper import (
    build_inventory_label_print_layout,
    pixels_to_mm,
)


class InventoryLabelPrintHelperTests(unittest.TestCase):
    def test_pixels_to_mm_uses_label_dpi(self) -> None:
        self.assertEqual(pixels_to_mm(300), 25.4)
        self.assertEqual(pixels_to_mm(150), 12.7)

    def test_build_inventory_label_print_layout_marks_landscape_labels(self) -> None:
        layout = build_inventory_label_print_layout(992, 271)

        self.assertEqual(layout.orientation, "landscape")
        self.assertEqual(layout.width_mm, 83.99)
        self.assertEqual(layout.height_mm, 22.94)

    def test_build_inventory_label_print_layout_marks_portrait_labels(self) -> None:
        layout = build_inventory_label_print_layout(271, 992)

        self.assertEqual(layout.orientation, "portrait")
        self.assertEqual(layout.width_mm, 22.94)
        self.assertEqual(layout.height_mm, 83.99)


if __name__ == "__main__":
    unittest.main()
