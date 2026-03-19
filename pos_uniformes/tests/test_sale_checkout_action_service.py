from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_checkout_action_service import (
    SaleCheckoutResult,
    complete_sale_checkout,
)


class SaleCheckoutActionServiceTests(unittest.TestCase):
    def test_complete_sale_checkout_confirms_sale_and_logs_manual_promo(self) -> None:
        usuario = object()
        cliente = object()
        venta = SimpleNamespace(subtotal=None, descuento_porcentaje=None, descuento_monto=None, total=None)
        client_snapshot = SimpleNamespace(client=cliente)
        fake_checkout = SimpleNamespace(
            load_sale_client_checkout_snapshot=lambda session, selected_client_id: client_snapshot,
            resolve_sale_loyalty_transition_notice=lambda snapshot, build_notice: "Cambio de nivel",
        )
        manual_calls: list[dict[str, object]] = []
        fake_manual = SimpleNamespace(log_authorized_promo=lambda session, **kwargs: manual_calls.append(kwargs))
        fake_venta_service = SimpleNamespace(
            crear_borrador=lambda **kwargs: venta,
            confirmar_venta=lambda session, venta: None,
        )
        fake_item_input = lambda **kwargs: kwargs
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)

        with patch(
            "pos_uniformes.services.sale_checkout_action_service._resolve_sale_checkout_action_dependencies",
            return_value=(object(), fake_venta_service, fake_item_input, fake_manual, fake_checkout),
        ):
            result = complete_sale_checkout(
                session,
                user_id=7,
                folio="V-001",
                sale_cart=[{"sku": "SKU-1", "cantidad": 2}],
                subtotal=Decimal("200.00"),
                discount_percent=Decimal("10.00"),
                applied_discount=Decimal("20.00"),
                total=Decimal("180.00"),
                selected_client_id=1,
                breakdown={
                    "loyalty_discount": Decimal("5.00"),
                    "promo_discount": Decimal("10.00"),
                    "winner_source": "PROMOCION_MANUAL",
                },
                payment_method="Efectivo",
                note_parts=["nota"],
                build_notice=lambda *args: "Cambio de nivel",
            )

        self.assertEqual(
            result,
            SaleCheckoutResult(
                folio="V-001",
                total=Decimal("180.00"),
                payment_method="Efectivo",
                loyalty_transition_notice="Cambio de nivel",
            ),
        )
        self.assertEqual(venta.total, Decimal("180.00"))
        self.assertEqual(len(manual_calls), 1)


if __name__ == "__main__":
    unittest.main()
