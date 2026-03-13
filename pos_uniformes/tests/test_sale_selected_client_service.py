from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.database.models import NivelLealtad
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import load_sale_selected_client_benefit


class SaleSelectedClientServiceTests(unittest.TestCase):
    def test_returns_none_when_no_client_is_selected(self) -> None:
        session = SimpleNamespace(get=lambda _model, _id: None)

        result = load_sale_selected_client_benefit(
            session,
            selected_client_id=None,
            normalize_discount_value=normalize_discount_value,
        )

        self.assertIsNone(result)

    def test_returns_none_when_selected_client_does_not_exist(self) -> None:
        session = SimpleNamespace(get=lambda _model, _id: None)

        result = load_sale_selected_client_benefit(
            session,
            selected_client_id=10,
            normalize_discount_value=normalize_discount_value,
        )

        self.assertIsNone(result)

    def test_returns_resolved_benefit_for_selected_client(self) -> None:
        client = SimpleNamespace(
            descuento_preferente=Decimal("0.00"),
            nivel_lealtad=NivelLealtad.PROFESOR,
        )
        session = SimpleNamespace(get=lambda _model, _id: client)

        with patch(
            "pos_uniformes.services.sale_selected_client_service.LoyaltyService.discount_for_level",
            return_value=Decimal("15.00"),
        ):
            result = load_sale_selected_client_benefit(
                session,
                selected_client_id=10,
                normalize_discount_value=normalize_discount_value,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.discount_percent, Decimal("15.00"))
        self.assertEqual(result.source_label, "Profesor")


if __name__ == "__main__":
    unittest.main()
