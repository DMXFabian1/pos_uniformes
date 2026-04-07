from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICING_KEY,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
)
from pos_uniformes.ui.helpers.quote_sports_uniform_helper import (
    add_quote_scan_variants,
    build_quote_presupuesto_inputs,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import SaleSportsUniformResolution


def _build_variant(
    *,
    sku: str,
    product_name: str,
    school_name: str = "Patria",
    level_name: str = "Secundaria",
    price: str = "199.00",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        sku=sku,
        precio_venta=price,
        talla="CH",
        color="Azul",
        producto=SimpleNamespace(
            nombre=product_name,
            nombre_base=product_name,
            escuela=SimpleNamespace(nombre=school_name),
            nivel_educativo=SimpleNamespace(nombre=level_name),
        ),
    )


class QuoteSportsUniformHelperTests(unittest.TestCase):
    @patch("pos_uniformes.ui.helpers.quote_sports_uniform_helper.resolve_sale_scan_variants")
    def test_add_quote_scan_variants_applies_three_piece_price_and_description(self, resolution_mock) -> None:
        base_variant = _build_variant(sku="P2-001", product_name="Pants deportivo 2pz", price="350.00")
        playera_variant = _build_variant(sku="PLY-001", product_name="Playera deportiva", price="189.00")
        resolution_mock.return_value = SaleSportsUniformResolution(
            variants=(base_variant, playera_variant),
            composed_as_three_pieces=True,
            selected_playera_sku="PLY-001",
            size_hint="Sugerida.",
        )
        quote_cart: list[dict[str, object]] = []

        result = add_quote_scan_variants(
            None,
            SimpleNamespace(),
            quote_cart=quote_cart,
            scanned_variant=base_variant,
            quantity=1,
            variant_loader=lambda _session, _sku: None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(quote_cart), 2)
        playera_line = next(item for item in quote_cart if item["sku"] == "PLY-001")
        self.assertEqual(playera_line["precio_unitario"], Decimal("100.00"))
        self.assertEqual(playera_line["pricing_rule_key"], THREE_PIECE_PLAYERA_PRICING_KEY)
        self.assertEqual(playera_line["pricing_rule_label"], THREE_PIECE_PLAYERA_PRICING_LABEL)
        self.assertIn(THREE_PIECE_PLAYERA_PRICING_LABEL, str(playera_line["producto_nombre"]))
        self.assertIn("Playera aplicada a $100.00", result.feedback_message)

    def test_build_quote_presupuesto_inputs_preserves_special_pricing_metadata(self) -> None:
        inputs = build_quote_presupuesto_inputs(
            [
                {
                    "sku": "PLY-001",
                    "cantidad": 2,
                    "precio_unitario": Decimal("100.00"),
                    "producto_nombre": "Playera deportiva (Conjunto deportivo 3pz)",
                    "pricing_rule_key": THREE_PIECE_PLAYERA_PRICING_KEY,
                    "pricing_rule_label": THREE_PIECE_PLAYERA_PRICING_LABEL,
                }
            ]
        )

        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].precio_unitario, Decimal("100.00"))
        self.assertEqual(inputs[0].pricing_rule_key, THREE_PIECE_PLAYERA_PRICING_KEY)
        self.assertEqual(inputs[0].pricing_rule_label, THREE_PIECE_PLAYERA_PRICING_LABEL)
        self.assertEqual(inputs[0].descripcion_snapshot, "Playera deportiva (Conjunto deportivo 3pz)")


if __name__ == "__main__":
    unittest.main()
