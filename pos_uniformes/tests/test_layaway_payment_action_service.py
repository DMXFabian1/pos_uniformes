from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_payment_action_service import register_layaway_payment


class LayawayPaymentActionServiceTests(unittest.TestCase):
    def test_register_layaway_payment_uses_apartado_service(self) -> None:
        usuario = object()
        apartado = object()
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            registrar_abono=lambda **kwargs: None,
        )

        with patch(
            "pos_uniformes.services.layaway_payment_action_service._resolve_layaway_payment_action_dependencies",
            return_value=(fake_apartado_service, object()),
        ):
            register_layaway_payment(
                session,
                layaway_id=10,
                user_id=7,
                payment_input=SimpleNamespace(
                    amount=Decimal("100.00"),
                    payment_method="Efectivo",
                    cash_amount=Decimal("100.00"),
                    reference="REF-1",
                    notes="Pago",
                ),
            )


if __name__ == "__main__":
    unittest.main()
