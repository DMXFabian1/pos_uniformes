from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services import sale_checkout_service
from pos_uniformes.services.sale_checkout_service import load_sale_client_checkout_snapshot


class SaleCheckoutServiceTests(unittest.TestCase):
    def test_load_sale_client_checkout_snapshot_returns_empty_without_client(self) -> None:
        snapshot = load_sale_client_checkout_snapshot(SimpleNamespace(get=lambda *_args: None), selected_client_id=None)

        self.assertIsNone(snapshot.client)
        self.assertEqual(snapshot.client_name_for_notice, "")

    def test_load_sale_client_checkout_snapshot_raises_when_client_missing(self) -> None:
        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=object(),
        ):
            with self.assertRaisesRegex(ValueError, "No se pudo cargar el cliente seleccionado"):
                load_sale_client_checkout_snapshot(SimpleNamespace(get=lambda *_args: None), selected_client_id=14)

    def test_load_sale_client_checkout_snapshot_loads_client(self) -> None:
        client = SimpleNamespace(nombre="Maria", nivel_lealtad="LEAL", descuento_preferente=Decimal("10.00"))
        session = SimpleNamespace(get=lambda *_args: client)

        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=object(),
        ):
            snapshot = load_sale_client_checkout_snapshot(session, selected_client_id=5)

        self.assertIs(snapshot.client, client)
        self.assertEqual(snapshot.client_name_for_notice, "Maria")

    def test_ya_no_hay_aviso_de_cambio_de_nivel(self) -> None:
        # 2026-11-12: «el nivel viejo retíralo» (Daniel). El aviso de cambio
        # de nivel después de cobrar se retiró junto con la revisión.
        self.assertFalse(hasattr(sale_checkout_service, "resolve_sale_loyalty_transition_notice"))


if __name__ == "__main__":
    unittest.main()
