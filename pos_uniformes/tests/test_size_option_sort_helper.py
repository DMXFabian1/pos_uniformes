from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.size_option_sort_helper import sort_size_options


class SizeOptionSortHelperTests(unittest.TestCase):
    def test_sorts_numeric_sizes_naturally(self) -> None:
        self.assertEqual(
            sort_size_options(["10", "2", "4", "12", "8"]),
            ["2", "4", "8", "10", "12"],
        )

    def test_sorts_numeric_ranges_with_numeric_group(self) -> None:
        self.assertEqual(
            sort_size_options(["9-12", "3", "13-18", "0-2", "10", "3-5"]),
            ["0-2", "3", "3-5", "9-12", "10", "13-18"],
        )

    def test_places_alpha_sizes_after_numeric_values(self) -> None:
        self.assertEqual(
            sort_size_options(["MD", "4", "EXG", "CH", "10", "GD-EXG", "Unitalla"]),
            ["4", "10", "CH", "MD", "GD-EXG", "EXG", "Unitalla"],
        )


if __name__ == "__main__":
    unittest.main()
