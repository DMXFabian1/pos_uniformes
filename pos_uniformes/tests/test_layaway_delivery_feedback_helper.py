from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.layaway_closure_service import (
    LayawayDeliveryConfirmation,
    LayawayDeliveryResult,
)
from pos_uniformes.ui.helpers.layaway_delivery_feedback_helper import (
    build_layaway_delivery_confirmation_view,
    build_layaway_delivery_result_view,
)


class LayawayDeliveryFeedbackHelperTests(unittest.TestCase):
    def test_build_layaway_delivery_confirmation_view_mentions_final_payment_when_balance_exists(self) -> None:
        view = build_layaway_delivery_confirmation_view(
            LayawayDeliveryConfirmation(
                layaway_id=10,
                layaway_folio="AP-001",
                customer_label="CLI-001 · Maria",
                items_count=2,
                pieces_count=3,
                total=Decimal("439.50"),
                total_paid=Decimal("351.70"),
                balance_due=Decimal("87.80"),
            )
        )

        self.assertIn("saldo pendiente", view.message.lower())
        self.assertIn("abono final", view.message.lower())
        self.assertIn("Saldo actual: $87.80", view.message)

    def test_build_layaway_delivery_confirmation_view_includes_operational_summary(self) -> None:
        view = build_layaway_delivery_confirmation_view(
            LayawayDeliveryConfirmation(
                layaway_id=10,
                layaway_folio="AP-001",
                customer_label="CLI-001 · Maria",
                items_count=2,
                pieces_count=3,
                total=Decimal("439.50"),
                total_paid=Decimal("439.50"),
                balance_due=Decimal("0.00"),
            )
        )

        self.assertEqual(view.title, "Entregar apartado")
        self.assertIn("Folio: AP-001", view.message)
        self.assertIn("Cliente: CLI-001 · Maria", view.message)
        self.assertIn("Piezas: 3", view.message)
        self.assertIn("Total: $439.50", view.message)

    def test_build_layaway_delivery_result_view_invites_opening_ticket(self) -> None:
        view = build_layaway_delivery_result_view(
            LayawayDeliveryResult(
                layaway_folio="AP-001",
                sale_folio="ENT-AP-001",
                customer_label="CLI-001 · Maria",
                items_count=2,
                pieces_count=3,
                total=Decimal("439.50"),
                payment_registered_amount=Decimal("0.00"),
            )
        )

        self.assertEqual(view.title, "Apartado entregado")
        self.assertIn("venta ENT-AP-001", view.message)
        self.assertIn("Total final: $439.50", view.message)
        self.assertIn("abrir el ticket", view.message.lower())

    def test_build_layaway_delivery_result_view_mentions_final_payment_when_present(self) -> None:
        view = build_layaway_delivery_result_view(
            LayawayDeliveryResult(
                layaway_folio="AP-001",
                sale_folio="ENT-AP-001",
                customer_label="CLI-001 · Maria",
                items_count=2,
                pieces_count=3,
                total=Decimal("439.50"),
                payment_registered_amount=Decimal("87.80"),
            )
        )

        self.assertIn("Abono final registrado: $87.80", view.message)


if __name__ == "__main__":
    unittest.main()
