from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICING_KEY,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
    THREE_PIECE_PLAYERA_PRICE,
    build_three_piece_playera_price_note,
    build_three_piece_playera_price_override,
)


class SportsUniformPricingServiceTests(unittest.TestCase):
    def test_build_three_piece_playera_price_override_uses_fixed_price(self) -> None:
        override = build_three_piece_playera_price_override(SimpleNamespace(precio_venta=Decimal("189.00")))

        self.assertEqual(override["precio_unitario"], THREE_PIECE_PLAYERA_PRICE)
        self.assertEqual(override["precio_base"], Decimal("189.00"))
        self.assertEqual(override["pricing_rule_key"], THREE_PIECE_PLAYERA_PRICING_KEY)
        self.assertEqual(override["pricing_rule_label"], THREE_PIECE_PLAYERA_PRICING_LABEL)

    def test_build_three_piece_playera_price_note_mentions_fixed_price_and_base(self) -> None:
        note = build_three_piece_playera_price_note(SimpleNamespace(precio_venta="189.00"))

        self.assertIn("100.00", note)
        self.assertIn("189.00", note)


if __name__ == "__main__":
    unittest.main()
