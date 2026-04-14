"""Tests para sale_stock_policy."""

from __future__ import annotations

import unittest

from pos_uniformes.services.sale_stock_policy import (
    allow_negative_sale_stock,
    sale_stock_guard_enabled,
)


class SaleStockPolicyTests(unittest.TestCase):

    def test_guard_and_allow_are_inverse(self) -> None:
        self.assertNotEqual(sale_stock_guard_enabled(), allow_negative_sale_stock())

    def test_allow_negative_is_true_when_guard_disabled(self) -> None:
        # Con el flag actual (TEMPORARY_SALE_STOCK_GUARD_ENABLED = False)
        # allow_negative debe ser True
        if not sale_stock_guard_enabled():
            self.assertTrue(allow_negative_sale_stock())

    def test_guard_disabled_when_allow_negative(self) -> None:
        if allow_negative_sale_stock():
            self.assertFalse(sale_stock_guard_enabled())


if __name__ == "__main__":
    unittest.main()
